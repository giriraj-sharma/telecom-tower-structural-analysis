import math
from typing import List, Dict, Any
from app.models.schemas import (
    TowerInput, 
    AnalysisOutput, 
    CriticalMember, 
    IntermediateCalculations,
    CostEstimate
)
from app.engine.tower_geometry import TowerGeometryBuilder
from app.engine.dead_loads import DeadLoadCalculator
from app.engine.wind_loads import WindLoadCalculator
from app.engine.capacity_checks import CapacityChecker
from app.engine.structural_solver import StructuralSolver
from app.engine.load_combinations import LoadCombinationManager
from app.engine.optimizer import CostModel

class TowerAnalysisService:
    @staticmethod
    def analyze(params: TowerInput) -> AnalysisOutput:
        # 1. Geometry
        geo_builder = TowerGeometryBuilder(params)
        nodes, initial_members, geo_summary = geo_builder.generate_mesh()
        
        # 2. Dead Loads
        dead_calc = DeadLoadCalculator(params, geo_builder)
        dead_data = dead_calc.calculate_panel_dead_loads()
        
        # 3. Wind Loads
        wind_calc = WindLoadCalculator(params, geo_builder)
        wind_data = wind_calc.calculate_wind_profile()
        
        # 4. Capacity & Solver
        cap_checker = CapacityChecker(params)
        solver = StructuralSolver(params, geo_builder, dead_calc, wind_calc, cap_checker)
        
        # 5. Load Combinations
        combo_mgr = LoadCombinationManager(solver)
        combination_results, governing_combo, raw_outputs = combo_mgr.evaluate_all()
        
        # Get governing solver details
        gov_raw = raw_outputs[governing_combo.combination_id]
        panel_profiles = gov_raw["panel_profiles"]
        
        # 6. Update 3D wireframe members with stress results
        updated_members = combo_mgr.update_3d_members(initial_members, gov_raw)
        
        # 7. Intermediate Calculations
        h_total_m = params.height_m
        h_total_mm = h_total_m * 1000.0
        allowable_defl_mm = h_total_mm / 100.0 # Standard telecom serviceability limit H/100
        
        # Bottom panel leg capacity check details
        base_panel = panel_profiles[0]
        leg_cap_info = cap_checker.get_leg_capacity(base_panel.panel_height_m)
        
        # Equivalent inertias
        i_base = gov_raw["panel_inertias_m4"][0]
        i_top = gov_raw["panel_inertias_m4"][-1]
        
        intermediate_calcs = IntermediateCalculations(
            basic_wind_speed_ms=round(wind_data["v_ms"], 2),
            air_density_kg_m3=round(wind_data["air_density"], 3),
            base_velocity_pressure_kpa=round(wind_data["base_qz_kpa"], 3),
            top_velocity_pressure_kpa=round(wind_data["top_qz_kpa"], 3),
            exposure_coefficient_kz_top=round(wind_data["kz_top"], 3),
            gust_factor_gh=round(params.gust_factor, 2),
            total_tower_steel_mass_kg=round(dead_data["total_steel_mass_kg"], 1),
            total_equipment_mass_kg=round(dead_data["total_equipment_mass_kg"], 1),
            total_appurtenance_vertical_load_kn=round(dead_data["total_equipment_dead_load_kn"], 2),
            total_tower_dead_load_kn=round(dead_data["total_tower_dead_load_kn"], 2),
            total_dead_load_kn=round(dead_data["total_dead_load_kn"], 2),
            total_wind_shear_kn=round(governing_combo.base_shear_kn, 2),
            overturning_moment_knm=round(governing_combo.overturning_moment_knm, 2),
            equivalent_inertia_base_m4=round(i_base, 5),
            equivalent_inertia_top_m4=round(i_top, 5),
            euler_buckling_stress_leg_mpa=round(leg_cap_info["fe_mpa"], 1),
            critical_buckling_stress_leg_mpa=round(leg_cap_info["fcr_mpa"], 1),
            nominal_leg_capacity_kn=round(leg_cap_info["comp_cap_kn"], 2),
            allowable_deflection_h_ratio="H / 100",
            allowable_deflection_mm=round(allowable_defl_mm, 1),
            top_tilt_angle_deg=round(gov_raw["top_tilt_deg"], 3),
            base_leg_compression_kn=round(gov_raw["max_base_compression_kn"], 2),
            base_leg_uplift_kn=round(gov_raw["max_base_uplift_kn"], 2)
        )
        
        # 8. Critical Member & Critical Members Table
        critical_member = CriticalMember(
            member_id=gov_raw["critical_member_id"],
            member_type=gov_raw["critical_member_type"],
            elevation_m=gov_raw["critical_member_elevation_m"],
            section_description=gov_raw["critical_member_section"],
            governing_load_combination=governing_combo.name,
            axial_force_kn=gov_raw["critical_member_axial_kn"],
            capacity_kn=gov_raw["critical_member_capacity_kn"],
            slenderness_ratio=gov_raw["critical_member_slenderness"],
            critical_stress_mpa=gov_raw["critical_member_stress_mpa"],
            utilization_ratio=gov_raw["critical_member_utilization"],
            status=CapacityChecker.evaluate_status(gov_raw["critical_member_utilization"])
        )
        
        # Build Critical Members Table across panels
        crit_table: List[CriticalMember] = []
        for p in panel_profiles:
            # Add leg check for each panel
            l_cap = cap_checker.get_leg_capacity(p.panel_height_m)
            crit_table.append(CriticalMember(
                member_id=f"LEG_P{p.panel_index}",
                member_type="Leg",
                elevation_m=p.elevation_bottom_m,
                section_description=f"{params.leg_section_type} {params.leg_dimension_mm}x{params.leg_thickness_mm}mm",
                governing_load_combination=governing_combo.name,
                axial_force_kn=p.leg_compression_kn,
                capacity_kn=p.leg_capacity_kn,
                slenderness_ratio=round(l_cap["slenderness"], 1),
                critical_stress_mpa=round(l_cap["fcr_mpa"], 1),
                utilization_ratio=p.leg_utilization,
                status=CapacityChecker.evaluate_status(p.leg_utilization)
            ))
            # Add diagonal brace check for each panel
            b_diag_len = math.sqrt(p.panel_height_m**2 + p.face_width_m**2)
            b_cap = cap_checker.get_brace_capacity(b_diag_len, params.bracing_type)
            crit_table.append(CriticalMember(
                member_id=f"BRACE_P{p.panel_index}",
                member_type="Diagonal Brace",
                elevation_m=p.elevation_mid_m,
                section_description=f"{params.brace_section_type} {params.brace_dimension_mm}x{params.brace_thickness_mm}mm",
                governing_load_combination=governing_combo.name,
                axial_force_kn=p.brace_force_kn,
                capacity_kn=round(b_cap["effective_cap_kn"], 2),
                slenderness_ratio=round(b_cap["slenderness"], 1),
                critical_stress_mpa=round(b_cap["fcr_mpa"], 1),
                utilization_ratio=p.brace_utilization,
                status=CapacityChecker.evaluate_status(p.brace_utilization)
            ))
            
        # Sort critical table with highest utilization first
        crit_table.sort(key=lambda m: m.utilization_ratio, reverse=True)
        
        # 9. Cost Breakdown
        cost_breakdown = CostModel.calculate_cost(
            dead_data["total_steel_mass_kg"], 
            params.base_width_m, 
            governing_combo.overturning_moment_knm
        )
        
        overall_status = governing_combo.status
        safety_factor = round(1.0 / max(0.01, governing_combo.max_overall_utilization), 2)
        
        return AnalysisOutput(
            tower_type=params.tower_type,
            height_m=params.height_m,
            base_width_m=params.base_width_m,
            top_width_m=params.top_width_m,
            overall_status=overall_status,
            max_utilization=governing_combo.max_overall_utilization,
            safety_factor=safety_factor,
            governing_load_combination=governing_combo.name,
            critical_member=critical_member,
            max_deflection_mm=governing_combo.max_deflection_mm,
            deflection_ratio=governing_combo.deflection_ratio,
            top_tilt_angle_deg=gov_raw["top_tilt_deg"],
            base_shear_kn=governing_combo.base_shear_kn,
            overturning_moment_knm=governing_combo.overturning_moment_knm,
            max_base_compression_kn=gov_raw["max_base_compression_kn"],
            max_base_uplift_kn=gov_raw["max_base_uplift_kn"],
            total_steel_weight_tonnes=round(dead_data["total_steel_mass_kg"] / 1000.0, 2),
            estimated_cost_usd=cost_breakdown.total_estimated_cost_usd,
            intermediate_calculations=intermediate_calcs,
            load_combinations=combination_results,
            critical_members_table=crit_table,
            panel_profiles=panel_profiles,
            cost_breakdown=cost_breakdown,
            nodes=nodes,
            members=updated_members
        )

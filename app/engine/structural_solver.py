import math
from typing import List, Dict, Any, Tuple
from app.models.schemas import TowerInput, PanelProfileData
from app.engine.tower_geometry import TowerGeometryBuilder
from app.engine.dead_loads import DeadLoadCalculator
from app.engine.wind_loads import WindLoadCalculator
from app.engine.capacity_checks import CapacityChecker

class StructuralSolver:
    def __init__(self, 
                 params: TowerInput, 
                 geometry: TowerGeometryBuilder, 
                 dead_calc: DeadLoadCalculator, 
                 wind_calc: WindLoadCalculator,
                 capacity_checker: CapacityChecker):
        self.params = params
        self.geometry = geometry
        self.dead_calc = dead_calc
        self.wind_calc = wind_calc
        self.capacity_checker = capacity_checker
        
        self.num_legs = 3 if params.tower_type == "3-leg" else 4
        self.e_steel = params.steel_elastic_modulus_gpa * 1e9 # Pa
        
    def solve(self, 
              factor_dead: float = 1.0, 
              factor_wind: float = 1.0, 
              factor_equip: float = 1.0) -> Dict[str, Any]:
        """
        Solves structural equilibrium for specific load combination factors
        """
        dead_data = self.dead_calc.calculate_panel_dead_loads()
        wind_data = self.wind_calc.calculate_wind_profile()
        
        num_p = self.geometry.num_panels
        h_p = self.geometry.panel_height
        is_3leg = self.params.tower_type == "3-leg"
        
        # Factored panel wind forces (kN)
        factored_wind_kn = []
        for i in range(num_p):
            f_tower = wind_data["panel_tower_wind_force_kn"][i] * factor_wind
            f_equip = wind_data["panel_equipment_wind_force_kn"][i] * factor_wind # wind on equipment scales with wind
            factored_wind_kn.append(f_tower + f_equip)
            
        # Factored vertical dead loads (kN)
        factored_dead_cum_kn = []
        for i in range(num_p):
            w_tower = dead_data["cum_steel_kn"][i] * factor_dead
            w_equip = dead_data["cum_equip_kn"][i] * factor_equip
            factored_dead_cum_kn.append(w_tower + w_equip)
            
        # Cumulative shear and overturning moment along height
        cum_shear_kn = [0.0] * num_p
        cum_moment_knm = [0.0] * num_p
        
        for i in range(num_p):
            z_b = self.geometry.panels[i].z_bottom
            v_i = sum(factored_wind_kn[k] for k in range(i, num_p))
            m_i = sum(factored_wind_kn[k] * (self.geometry.panels[k].z_mid - z_b) for k in range(i, num_p))
            cum_shear_kn[i] = v_i
            cum_moment_knm[i] = m_i
            
        base_shear_kn = cum_shear_kn[0]
        base_moment_knm = cum_moment_knm[0]
        
        # Member internal forces and utilization per panel
        panel_profiles: List[PanelProfileData] = []
        
        # Deflection integration accumulators
        # Curvature kappa(z) = M(z) / (E * I(z))
        panel_curvatures = [0.0] * num_p
        panel_inertias_m4 = [0.0] * num_p
        
        # Calculate leg and brace forces
        for i in range(num_p):
            panel = self.geometry.panels[i]
            w_avg = panel.width_mid
            m_val = cum_moment_knm[i] # kNm
            v_val = cum_shear_kn[i]   # kN
            d_val = factored_dead_cum_kn[i] # kN
            
            # Leg unbraced length
            leg_len = math.sqrt(h_p**2 + ((panel.width_bottom - panel.width_top) / 2.0)**2)
            leg_cap = self.capacity_checker.get_leg_capacity(leg_len)
            
            # Leg axial force from overturning moment
            if is_3leg:
                # 3-leg equilateral: apex leg takes 2 * M / (sqrt(3) * B)
                p_leg_moment = (2.0 * m_val) / (math.sqrt(3.0) * max(0.5, w_avg))
            else:
                # 4-leg square: critical diagonal wind takes M / (sqrt(2) * B)
                p_leg_moment = m_val / (math.sqrt(2.0) * max(0.5, w_avg))
                
            # Gravity load per leg
            p_leg_gravity = d_val / float(self.num_legs)
            
            # Max leg compression (kN) and tension uplift (kN)
            leg_comp_kn = p_leg_moment + p_leg_gravity
            leg_tens_kn = p_leg_moment - p_leg_gravity
            
            # Leg utilization
            u_comp = leg_comp_kn / max(0.1, leg_cap["comp_cap_kn"])
            u_tens = leg_tens_kn / max(0.1, leg_cap["tens_cap_kn"]) if leg_tens_kn > 0 else 0.0
            leg_utilization = max(u_comp, u_tens)
            
            # Brace force and capacity
            diag_len = math.sqrt(h_p**2 + w_avg**2)
            brace_cap = self.capacity_checker.get_brace_capacity(diag_len, self.params.bracing_type)
            
            # Shear resisted by braces
            # For X-brace: 2 diagonals per face share load in tension/compression
            if is_3leg:
                eff_faces = math.sqrt(3.0) # 2 inclined faces at 60 deg = 2 * sin(60) = 1.732
            else:
                eff_faces = math.sqrt(2.0) if factor_wind > 0 else 2.0 # 45-deg diagonal wind
                
            cos_theta = w_avg / max(0.1, diag_len)
            diag_divisor = 2.0 if self.params.bracing_type == "X-brace" else 1.0
            brace_force_kn = abs(v_val) / max(0.1, (eff_faces * diag_divisor * cos_theta))
            brace_utilization = brace_force_kn / max(0.1, brace_cap["effective_cap_kn"])
            
            # Tower equivalent cross-sectional inertia I(z) (m4)
            a_leg = self.capacity_checker.a_leg
            if is_3leg:
                i_tower = 0.5 * a_leg * (w_avg ** 2)
            else:
                i_tower = a_leg * (w_avg ** 2)
            panel_inertias_m4[i] = i_tower
            
            # Curvature in 1/m: M (Nm) / (E * I)
            # m_val is in kNm = 1000 Nm
            # E is in Pa (N/m2)
            m_nm = m_val * 1000.0
            kappa = m_nm / (self.e_steel * max(1e-6, i_tower))
            panel_curvatures[i] = kappa
            
            panel_profiles.append(PanelProfileData(
                panel_index=i + 1,
                elevation_bottom_m=round(panel.z_bottom, 2),
                elevation_top_m=round(panel.z_top, 2),
                elevation_mid_m=round(panel.z_mid, 2),
                face_width_m=round(w_avg, 2),
                panel_height_m=round(h_p, 2),
                wind_velocity_pressure_kpa=round(wind_data["panel_qz_kpa"][i], 3),
                solidity_ratio=round(wind_data["panel_solidity"][i], 3),
                force_coefficient_cf=round(wind_data["panel_cf"][i], 2),
                tower_wind_force_kn=round(wind_data["panel_tower_wind_force_kn"][i] * factor_wind, 2),
                equipment_wind_force_kn=round(wind_data["panel_equipment_wind_force_kn"][i] * factor_wind, 2),
                total_wind_force_kn=round(factored_wind_kn[i], 2),
                cumulative_shear_kn=round(v_val, 2),
                cumulative_moment_knm=round(m_val, 2),
                cumulative_dead_load_kn=round(d_val, 2),
                deflection_mm=0.0, # will populate below
                leg_compression_kn=round(leg_comp_kn, 2),
                leg_tension_kn=round(leg_tens_kn, 2),
                leg_capacity_kn=round(leg_cap["comp_cap_kn"], 2),
                leg_utilization=round(leg_utilization, 3),
                brace_force_kn=round(brace_force_kn, 2),
                brace_capacity_kn=round(brace_cap["comp_cap_kn"], 2),
                brace_utilization=round(brace_utilization, 3)
            ))
            
        # Numerical integration for Deflection & Tilt
        # Rotation theta(z) = integral kappa dz
        # Deflection delta(z) = integral theta dz + shear distortion
        rotation_rad = 0.0
        deflection_m = 0.0
        
        # Calculate deflection from ground level upwards
        for i in range(num_p):
            # Panel average curvature
            k_mid = panel_curvatures[i]
            # incremental angle d_theta = kappa * dz
            delta_theta = k_mid * h_p
            # deflection increment = rotation * dz + 0.5 * kappa * dz^2
            delta_disp = (rotation_rad * h_p) + (0.5 * k_mid * (h_p ** 2))
            
            # Add lattice shear deformation increment
            # delta_s = V * h_p / (G * A_web_eff)
            w_avg = self.geometry.panels[i].width_mid
            diag_len = math.sqrt(h_p**2 + w_avg**2)
            a_brace = self.capacity_checker.a_brace
            shear_disp = (cum_shear_kn[i] * 1000.0 * (diag_len ** 3)) / (2.0 * self.e_steel * a_brace * (w_avg ** 2) * max(1.0, h_p))
            
            rotation_rad += delta_theta
            deflection_m += delta_disp + max(0.0, shear_disp)
            
            # Store in panel profile (in mm)
            panel_profiles[i].deflection_mm = round(deflection_m * 1000.0, 2)
            
        max_deflection_mm = deflection_m * 1000.0
        top_tilt_deg = rotation_rad * (180.0 / math.pi)
        
        # Allowable deflection check: typically H / 100 or H / 200
        h_total_mm = self.geometry.height * 1000.0
        deflection_ratio_val = int(h_total_mm / max(0.1, max_deflection_mm))
        deflection_ratio_str = f"H / {deflection_ratio_val}"
        
        # Find maximum utilization and critical member
        max_leg_util = max(p.leg_utilization for p in panel_profiles)
        max_brace_util = max(p.brace_utilization for p in panel_profiles)
        max_util = max(max_leg_util, max_brace_util)
        
        # Determine critical member
        if max_leg_util >= max_brace_util:
            # Leg is critical (usually bottom panel)
            crit_panel = max(panel_profiles, key=lambda p: p.leg_utilization)
            crit_member_id = f"LEG_P{crit_panel.panel_index}_BASE"
            crit_type = "Leg"
            crit_axial = crit_panel.leg_compression_kn
            crit_cap = crit_panel.leg_capacity_kn
            crit_elev = crit_panel.elevation_bottom_m
            crit_desc = f"{self.params.leg_section_type} {self.params.leg_dimension_mm}x{self.params.leg_thickness_mm}mm"
            leg_cap_info = self.capacity_checker.get_leg_capacity(crit_panel.panel_height_m)
            crit_slenderness = leg_cap_info["slenderness"]
            crit_stress = leg_cap_info["fcr_mpa"]
            crit_util = crit_panel.leg_utilization
        else:
            # Brace is critical
            crit_panel = max(panel_profiles, key=lambda p: p.brace_utilization)
            crit_member_id = f"DIAG_P{crit_panel.panel_index}_FACE1"
            crit_type = "Diagonal Brace"
            crit_axial = crit_panel.brace_force_kn
            brace_cap_info = self.capacity_checker.get_brace_capacity(
                math.sqrt(crit_panel.panel_height_m**2 + crit_panel.face_width_m**2),
                self.params.bracing_type
            )
            crit_slenderness = brace_cap_info["slenderness"]
            crit_stress = brace_cap_info["fcr_mpa"]
            crit_cap = brace_cap_info["effective_cap_kn"]
            crit_util = crit_panel.brace_utilization
            
        status = CapacityChecker.evaluate_status(max_util)
        
        return {
            "base_shear_kn": base_shear_kn,
            "overturning_moment_knm": base_moment_knm,
            "max_base_compression_kn": panel_profiles[0].leg_compression_kn,
            "max_base_uplift_kn": panel_profiles[0].leg_tension_kn,
            "max_deflection_mm": max_deflection_mm,
            "deflection_ratio_str": deflection_ratio_str,
            "top_tilt_deg": top_tilt_deg,
            "max_leg_utilization": max_leg_util,
            "max_brace_utilization": max_brace_util,
            "max_utilization": max_util,
            "status": status,
            "critical_member_id": crit_member_id,
            "critical_member_type": crit_type,
            "critical_member_elevation_m": crit_elev,
            "critical_member_section": crit_desc,
            "critical_member_axial_kn": crit_axial,
            "critical_member_capacity_kn": crit_cap,
            "critical_member_slenderness": crit_slenderness,
            "critical_member_stress_mpa": crit_stress,
            "critical_member_utilization": crit_util,
            "panel_profiles": panel_profiles,
            "panel_inertias_m4": panel_inertias_m4
        }

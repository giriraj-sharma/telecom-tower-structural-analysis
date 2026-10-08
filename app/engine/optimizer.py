import math
from typing import List, Dict, Any, Tuple
from app.models.schemas import (
    TowerInput, 
    AnalysisOutput, 
    OptimizationResponse, 
    OptimizationCandidate,
    CostEstimate,
    LoadCombinationResult
)
from app.engine.tower_geometry import TowerGeometryBuilder
from app.engine.dead_loads import DeadLoadCalculator
from app.engine.wind_loads import WindLoadCalculator
from app.engine.capacity_checks import CapacityChecker
from app.engine.structural_solver import StructuralSolver
from app.engine.load_combinations import LoadCombinationManager

class CostModel:
    @staticmethod
    def calculate_cost(steel_mass_kg: float, base_width_m: float, overturning_moment_knm: float) -> CostEstimate:
        # Industry typical telecom tower costs (USD):
        # Raw structural steel (galvanized ASTM A36 / S355): ~$2.20 / kg
        # Tower fabrication, CNC cutting, hole punching, hot-dip galvanizing: ~$1.10 / kg
        # Foundation base cost (concrete pad & stub piers) scaling with moment & width:
        # Hardware, step bolts, ladder, antenna brackets:
        steel_cost = steel_mass_kg * 2.20
        fab_galv_cost = steel_mass_kg * 1.10
        hardware_cost = 1400.0 + (0.12 * steel_mass_kg)
        foundation_cost = 5500.0 + (3.8 * overturning_moment_knm) + (110.0 * (base_width_m ** 2))
        
        total_cost = steel_cost + fab_galv_cost + hardware_cost + foundation_cost
        
        return CostEstimate(
            steel_mass_kg=round(steel_mass_kg, 1),
            steel_cost_usd=round(steel_cost, 2),
            fabrication_galvanizing_usd=round(fab_galv_cost, 2),
            foundation_estimate_usd=round(foundation_cost, 2),
            hardware_and_accessories_usd=round(hardware_cost, 2),
            total_estimated_cost_usd=round(total_cost, 2)
        )

class TowerOptimizer:
    def __init__(self, baseline_params: TowerInput):
        self.baseline_params = baseline_params
        
    def analyze_single_configuration(self, params: TowerInput) -> Tuple[Dict[str, Any], LoadCombinationResult, CostEstimate]:
        geo_builder = TowerGeometryBuilder(params)
        dead_calc = DeadLoadCalculator(params, geo_builder)
        wind_calc = WindLoadCalculator(params, geo_builder)
        cap_checker = CapacityChecker(params)
        solver = StructuralSolver(params, geo_builder, dead_calc, wind_calc, cap_checker)
        combo_mgr = LoadCombinationManager(solver)
        
        results, governing, raw_outputs = combo_mgr.evaluate_all()
        dead_data = dead_calc.calculate_panel_dead_loads()
        steel_mass = dead_data["total_steel_mass_kg"]
        cost_breakdown = CostModel.calculate_cost(steel_mass, params.base_width_m, governing.overturning_moment_knm)
        
        return raw_outputs[governing.combination_id], governing, cost_breakdown

    def run_optimization(self, baseline_output: AnalysisOutput) -> OptimizationResponse:
        candidates: List[OptimizationCandidate] = []
        base = self.baseline_params
        
        # Define candidate variations to explore:
        # 1. 3-Leg vs 4-Leg
        # 2. Base width adjustments (compact, balanced, wide)
        # 3. Leg diameter & wall thickness variations
        # 4. Bracing dimensions
        
        configs_to_test = [
            # Candidate 1: Baseline configuration
            {
                "name": f"Baseline ({base.tower_type}, B={base.base_width_m}m)",
                "tower_type": base.tower_type,
                "base_width_m": base.base_width_m,
                "leg_dim": base.leg_dimension_mm,
                "leg_t": base.leg_thickness_mm,
                "brace_dim": base.brace_dimension_mm,
                "brace_t": base.brace_thickness_mm
            },
            # Candidate 2: Compact footprint (Narrow base -20%, thicker legs)
            {
                "name": f"Compact Footprint ({base.tower_type}, B={round(base.base_width_m*0.8, 2)}m)",
                "tower_type": base.tower_type,
                "base_width_m": round(max(2.0, base.base_width_m * 0.8), 2),
                "leg_dim": round(base.leg_dimension_mm * 1.15, 1),
                "leg_t": round(base.leg_thickness_mm * 1.25, 1),
                "brace_dim": base.brace_dimension_mm,
                "brace_t": base.brace_thickness_mm
            },
            # Candidate 3: Wide Spread Base (+25% width, lighter legs)
            {
                "name": f"Wide Spread ({base.tower_type}, B={round(base.base_width_m*1.25, 2)}m, Light Legs)",
                "tower_type": base.tower_type,
                "base_width_m": round(base.base_width_m * 1.25, 2),
                "leg_dim": round(max(60.0, base.leg_dimension_mm * 0.90), 1),
                "leg_t": round(max(4.0, base.leg_thickness_mm * 0.85), 1),
                "brace_dim": round(max(40.0, base.brace_dimension_mm * 0.90), 1),
                "brace_t": round(max(3.0, base.brace_thickness_mm * 0.85), 1)
            },
            # Candidate 4: Ultra-Lightweight Optimized
            {
                "name": f"Material-Optimized ({base.tower_type}, Tuned Sections)",
                "tower_type": base.tower_type,
                "base_width_m": round(base.base_width_m * 1.10, 2),
                "leg_dim": round(base.leg_dimension_mm * 0.95, 1),
                "leg_t": round(base.leg_thickness_mm * 0.90, 1),
                "brace_dim": round(base.brace_dimension_mm * 0.92, 1),
                "brace_t": round(base.brace_thickness_mm * 0.90, 1)
            },
            # Candidate 5: Alternate leg count (if 4-leg -> 3-leg; if 3-leg -> 4-leg)
            {
                "name": f"Alternate Topology ({'3-leg' if base.tower_type == '4-leg' else '4-leg'} Triangular/Square)",
                "tower_type": "3-leg" if base.tower_type == "4-leg" else "4-leg",
                "base_width_m": base.base_width_m,
                "leg_dim": round(base.leg_dimension_mm * (1.10 if base.tower_type == "4-leg" else 0.92), 1),
                "leg_t": round(base.leg_thickness_mm * (1.10 if base.tower_type == "4-leg" else 0.92), 1),
                "brace_dim": base.brace_dimension_mm,
                "brace_t": base.brace_thickness_mm
            },
            # Candidate 6: Heavy Duty / High Safety Margin (+30% capacity)
            {
                "name": f"Heavy-Duty Reinforced ({base.tower_type}, Robust)",
                "tower_type": base.tower_type,
                "base_width_m": base.base_width_m,
                "leg_dim": round(base.leg_dimension_mm * 1.25, 1),
                "leg_t": round(base.leg_thickness_mm * 1.30, 1),
                "brace_dim": round(base.brace_dimension_mm * 1.20, 1),
                "brace_t": round(base.brace_thickness_mm * 1.20, 1)
            }
        ]
        
        idx = 1
        for cfg in configs_to_test:
            # Create copy of params with new properties
            cand_params = self.baseline_params.model_copy(update={
                "tower_type": cfg["tower_type"],
                "base_width_m": cfg["base_width_m"],
                "leg_dimension_mm": cfg["leg_dim"],
                "leg_thickness_mm": cfg["leg_t"],
                "brace_dimension_mm": cfg["brace_dim"],
                "brace_thickness_mm": cfg["brace_t"]
            })
            
            raw_sol, governing, cost = self.analyze_single_configuration(cand_params)
            
            cand = OptimizationCandidate(
                candidate_id=f"OPT-{idx:02d}",
                name=cfg["name"],
                tower_type=cfg["tower_type"],
                base_width_m=cfg["base_width_m"],
                leg_dimension_mm=cfg["leg_dim"],
                leg_thickness_mm=cfg["leg_t"],
                brace_dimension_mm=cfg["brace_dim"],
                brace_thickness_mm=cfg["brace_t"],
                steel_mass_kg=cost.steel_mass_kg,
                max_utilization=governing.max_overall_utilization,
                max_deflection_mm=governing.max_deflection_mm,
                safety_factor=round(1.0 / max(0.01, governing.max_overall_utilization), 2),
                estimated_cost_usd=cost.total_estimated_cost_usd,
                status=governing.status,
                is_recommended=False,
                rank=0
            )
            candidates.append(cand)
            idx += 1
            
        # Filter viable candidates (SAFE or WARNING with max_util <= 1.00)
        viable_candidates = [c for c in candidates if c.max_utilization <= 1.00]
        
        if viable_candidates:
            # Select lowest cost among viable designs
            recommended = min(viable_candidates, key=lambda c: c.estimated_cost_usd)
        else:
            # Fallback to least-failing
            recommended = min(candidates, key=lambda c: c.max_utilization)
            
        recommended.is_recommended = True
        
        # Rank all candidates: first viable by cost, then non-viable by utilization
        viable_sorted = sorted([c for c in candidates if c.max_utilization <= 1.00], key=lambda c: c.estimated_cost_usd)
        failing_sorted = sorted([c for c in candidates if c.max_utilization > 1.00], key=lambda c: c.max_utilization)
        
        all_ranked = viable_sorted + failing_sorted
        for r_idx, c in enumerate(all_ranked, 1):
            c.rank = r_idx
            
        # Summary description
        savings = baseline_output.estimated_cost_usd - recommended.estimated_cost_usd
        weight_diff = (baseline_output.cost_breakdown.steel_mass_kg - recommended.steel_mass_kg)
        
        if savings > 0:
            summary = (
                f"Recommended design '{recommended.name}' achieves a cost reduction of "
                f"${savings:,.2f} ({round((savings/baseline_output.estimated_cost_usd)*100, 1)}%) "
                f"and saves {weight_diff:,.0f} kg of structural steel while maintaining a governing utilization of "
                f"{round(recommended.max_utilization*100, 1)}% (Safety Factor = {recommended.safety_factor})."
            )
        else:
            summary = (
                f"Baseline configuration is near-optimal. Recommended design '{recommended.name}' "
                f"provides the best structural safety-to-cost trade-off with utilization of "
                f"{round(recommended.max_utilization*100, 1)}% (SF = {recommended.safety_factor})."
            )
            
        return OptimizationResponse(
            baseline_configuration=baseline_output,
            recommended_configuration=recommended,
            candidates=candidates,
            tradeoff_summary=summary
        )

from typing import List, Dict, Any, Tuple
from app.models.schemas import TowerInput, LoadCombinationResult, CriticalMember, GeometryMember
from app.engine.structural_solver import StructuralSolver
from app.engine.capacity_checks import CapacityChecker

class LoadCombinationManager:
    def __init__(self, solver: StructuralSolver):
        self.solver = solver
        
        # The 5 primary requested load combinations + 1 factored ultimate combination
        self.combinations_def = [
            {
                "id": "LC1",
                "name": "Dead Only",
                "desc": "1.0 * Tower Self Weight",
                "factors": {"dead": 1.0, "wind": 0.0, "equip": 0.0}
            },
            {
                "id": "LC2",
                "name": "Wind Only",
                "desc": "1.0 * Lateral Wind Load",
                "factors": {"dead": 0.0, "wind": 1.0, "equip": 0.0}
            },
            {
                "id": "LC3",
                "name": "Dead + Wind",
                "desc": "1.0 * Dead + 1.0 * Wind",
                "factors": {"dead": 1.0, "wind": 1.0, "equip": 0.0}
            },
            {
                "id": "LC4",
                "name": "Equipment + Wind",
                "desc": "1.0 * Equipment + 1.0 * Wind",
                "factors": {"dead": 0.0, "wind": 1.0, "equip": 1.0}
            },
            {
                "id": "LC5",
                "name": "Dead + Equipment + Wind",
                "desc": "1.0 * Dead + 1.0 * Equipment + 1.0 * Wind (Governing Service)",
                "factors": {"dead": 1.0, "wind": 1.0, "equip": 1.0}
            },
            {
                "id": "LC6_ULS",
                "name": "Factored Strength (1.2D + 1.6W + 1.2E)",
                "desc": "TIA-222 / AISC Ultimate Limit State Factored Design",
                "factors": {"dead": 1.2, "wind": 1.6, "equip": 1.2}
            }
        ]
        
    def evaluate_all(self) -> Tuple[List[LoadCombinationResult], LoadCombinationResult, Dict[str, Any]]:
        results: List[LoadCombinationResult] = []
        raw_solver_outputs: Dict[str, Dict[str, Any]] = {}
        
        for comb in self.combinations_def:
            f = comb["factors"]
            sol = self.solver.solve(factor_dead=f["dead"], factor_wind=f["wind"], factor_equip=f["equip"])
            raw_solver_outputs[comb["id"]] = sol
            
            res = LoadCombinationResult(
                combination_id=comb["id"],
                name=comb["name"],
                description=comb["desc"],
                factors=f,
                base_shear_kn=round(sol["base_shear_kn"], 2),
                overturning_moment_knm=round(sol["overturning_moment_knm"], 2),
                max_deflection_mm=round(sol["max_deflection_mm"], 2),
                deflection_ratio=sol["deflection_ratio_str"],
                max_leg_compression_kn=round(sol["max_base_compression_kn"], 2),
                max_leg_tension_uplift_kn=round(sol["max_base_uplift_kn"], 2),
                max_leg_utilization=round(sol["max_leg_utilization"], 3),
                max_brace_utilization=round(sol["max_brace_utilization"], 3),
                max_overall_utilization=round(sol["max_utilization"], 3),
                critical_member_id=sol["critical_member_id"],
                status=sol["status"]
            )
            results.append(res)
            
        # Determine governing combination
        # The governing service load combination is typically LC5 (Dead + Equipment + Wind)
        # or LC6_ULS if considering factored strength.
        # Find the one with highest overall utilization:
        governing = max(results, key=lambda r: r.max_overall_utilization)
        
        return results, governing, raw_solver_outputs

    def update_3d_members(self, members: List[GeometryMember], governing_output: Dict[str, Any]) -> List[GeometryMember]:
        """
        Assigns utilization and status to 3D wireframe members based on governing analysis
        """
        panel_profiles = governing_output["panel_profiles"]
        num_panels = len(panel_profiles)
        
        updated: List[GeometryMember] = []
        for m in members:
            # Parse panel index from member id, e.g. "LEG_P1_L1" -> panel 0
            parts = m.id.split("_")
            p_str = parts[1] if len(parts) > 1 and parts[1].startswith("P") else "P1"
            try:
                p_idx = max(0, min(num_panels - 1, int(p_str.replace("P", "")) - 1))
            except Exception:
                p_idx = 0
                
            panel_data = panel_profiles[p_idx]
            
            if m.type == "leg":
                util = panel_data.leg_utilization
            elif m.type == "diagonal":
                util = panel_data.brace_utilization
            else: # horizontal
                util = panel_data.brace_utilization * 0.45 # horizontals carry minor secondary loads
                
            status = CapacityChecker.evaluate_status(util)
            updated.append(GeometryMember(
                id=m.id,
                type=m.type,
                start_node=m.start_node,
                end_node=m.end_node,
                utilization=round(util, 3),
                status=status
            ))
            
        return updated

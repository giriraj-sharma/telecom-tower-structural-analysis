import pytest
from app.presets.demo_towers import get_demo_tower
from app.engine.tower_geometry import TowerGeometryBuilder
from app.engine.dead_loads import DeadLoadCalculator
from app.engine.wind_loads import WindLoadCalculator
from app.engine.capacity_checks import CapacityChecker
from app.engine.structural_solver import StructuralSolver
from app.engine.load_combinations import LoadCombinationManager

def test_five_required_load_combinations_present():
    t40 = get_demo_tower("40m")
    geo = TowerGeometryBuilder(t40)
    dead_calc = DeadLoadCalculator(t40, geo)
    wind_calc = WindLoadCalculator(t40, geo)
    cap_checker = CapacityChecker(t40)
    solver = StructuralSolver(t40, geo, dead_calc, wind_calc, cap_checker)
    combo_mgr = LoadCombinationManager(solver)
    
    results, governing, _ = combo_mgr.evaluate_all()
    
    # Must have all required combinations
    combo_names = [c.name for c in results]
    assert any("Dead Only" in name for name in combo_names)
    assert any("Wind Only" in name for name in combo_names)
    assert any("Dead + Wind" in name for name in combo_names)
    assert any("Equipment + Wind" in name for name in combo_names)
    assert any("Dead + Equipment + Wind" in name for name in combo_names)
    
    # Governing combination must have maximum overall utilization
    max_util = max(r.max_overall_utilization for r in results)
    assert governing.max_overall_utilization == max_util

def test_dead_only_has_zero_lateral_shear():
    t40 = get_demo_tower("40m")
    geo = TowerGeometryBuilder(t40)
    dead_calc = DeadLoadCalculator(t40, geo)
    wind_calc = WindLoadCalculator(t40, geo)
    cap_checker = CapacityChecker(t40)
    solver = StructuralSolver(t40, geo, dead_calc, wind_calc, cap_checker)
    combo_mgr = LoadCombinationManager(solver)
    
    results, _, _ = combo_mgr.evaluate_all()
    dead_only = next(r for r in results if r.combination_id == "LC1")
    
    assert dead_only.base_shear_kn == 0.0
    assert dead_only.overturning_moment_knm == 0.0
    assert dead_only.max_deflection_mm == 0.0

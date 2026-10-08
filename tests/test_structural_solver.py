import pytest
from app.presets.demo_towers import get_demo_tower
from app.engine.tower_geometry import TowerGeometryBuilder
from app.engine.dead_loads import DeadLoadCalculator
from app.engine.wind_loads import WindLoadCalculator
from app.engine.capacity_checks import CapacityChecker
from app.engine.structural_solver import StructuralSolver

def test_equilibrium_shear_and_moment():
    t40 = get_demo_tower("40m")
    geo = TowerGeometryBuilder(t40)
    dead_calc = DeadLoadCalculator(t40, geo)
    wind_calc = WindLoadCalculator(t40, geo)
    cap_checker = CapacityChecker(t40)
    solver = StructuralSolver(t40, geo, dead_calc, wind_calc, cap_checker)
    
    sol = solver.solve(factor_dead=1.0, factor_wind=1.0, factor_equip=1.0)
    
    # Base shear must match sum of panel wind forces
    panel_forces = [p.total_wind_force_kn for p in sol["panel_profiles"]]
    assert sol["base_shear_kn"] == pytest.approx(sum(panel_forces), rel=1e-2)
    assert sol["overturning_moment_knm"] > 1000.0 # significant moment for 40m tower

def test_deflection_monotonic_increase():
    t40 = get_demo_tower("40m")
    geo = TowerGeometryBuilder(t40)
    dead_calc = DeadLoadCalculator(t40, geo)
    wind_calc = WindLoadCalculator(t40, geo)
    cap_checker = CapacityChecker(t40)
    solver = StructuralSolver(t40, geo, dead_calc, wind_calc, cap_checker)
    
    sol = solver.solve(factor_dead=1.0, factor_wind=1.0, factor_equip=1.0)
    profiles = sol["panel_profiles"]
    
    # Lateral deflection must increase from bottom to top
    for i in range(len(profiles) - 1):
        assert profiles[i].deflection_mm <= profiles[i+1].deflection_mm
    assert sol["max_deflection_mm"] == pytest.approx(profiles[-1].deflection_mm, rel=1e-3)

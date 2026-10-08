import pytest
from app.presets.demo_towers import get_demo_tower
from app.engine.capacity_checks import CapacityChecker

def test_euler_and_aisc_column_buckling():
    t40 = get_demo_tower("40m")
    checker = CapacityChecker(t40)
    
    # Calculate for typical leg segment (2.5m, radius of gyration ~0.04m)
    slenderness, fe_mpa, fcr_mpa = checker.calculate_column_buckling_stress(2.5, 0.04, k_factor=0.85)
    
    assert slenderness > 10.0
    assert slenderness < 120.0
    assert fcr_mpa <= t40.steel_yield_strength_mpa
    assert fcr_mpa > 100.0

def test_status_thresholds():
    assert CapacityChecker.evaluate_status(0.50) == "SAFE"
    assert CapacityChecker.evaluate_status(0.84) == "SAFE"
    assert CapacityChecker.evaluate_status(0.85) == "WARNING"
    assert CapacityChecker.evaluate_status(0.99) == "WARNING"
    assert CapacityChecker.evaluate_status(1.00) == "WARNING"
    assert CapacityChecker.evaluate_status(1.01) == "FAIL"
    assert CapacityChecker.evaluate_status(1.50) == "FAIL"

def test_leg_capacities():
    t40 = get_demo_tower("40m")
    checker = CapacityChecker(t40)
    cap = checker.get_leg_capacity(2.5)
    
    assert cap["comp_cap_kn"] > 0
    assert cap["tens_cap_kn"] > 0
    # Compressive buckling capacity is generally <= tension yield capacity
    assert cap["comp_cap_kn"] <= cap["tens_cap_kn"]

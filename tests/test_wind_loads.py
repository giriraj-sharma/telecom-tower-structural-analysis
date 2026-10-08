import pytest
from app.presets.demo_towers import get_demo_tower
from app.engine.tower_geometry import TowerGeometryBuilder
from app.engine.wind_loads import WindLoadCalculator

def test_wind_velocity_pressure_increases_with_height():
    t40 = get_demo_tower("40m")
    geo = TowerGeometryBuilder(t40)
    wind_calc = WindLoadCalculator(t40, geo)
    
    qz_base = wind_calc.get_velocity_pressure_kpa(5.0)
    qz_mid = wind_calc.get_velocity_pressure_kpa(20.0)
    qz_top = wind_calc.get_velocity_pressure_kpa(40.0)
    
    assert qz_base < qz_mid < qz_top
    assert qz_top > 0.8 # Typical range for 160 km/h wind in Exposure C

def test_terrain_exposure_coefficients():
    t40 = get_demo_tower("40m")
    geo = TowerGeometryBuilder(t40)
    
    # Compare Exposure B, C, D at height 30m
    t40.terrain_category = "Exposure B - Urban"
    calc_b = WindLoadCalculator(t40, geo)
    kz_b = calc_b.get_exposure_coefficient(30.0)
    
    t40.terrain_category = "Exposure C - Open"
    calc_c = WindLoadCalculator(t40, geo)
    kz_c = calc_c.get_exposure_coefficient(30.0)
    
    t40.terrain_category = "Exposure D - Coastal"
    calc_d = WindLoadCalculator(t40, geo)
    kz_d = calc_d.get_exposure_coefficient(30.0)
    
    assert kz_b < kz_c < kz_d

def test_wind_force_profile():
    t40 = get_demo_tower("40m")
    geo = TowerGeometryBuilder(t40)
    wind_calc = WindLoadCalculator(t40, geo)
    profile = wind_calc.calculate_wind_profile()
    
    assert profile["base_shear_kn"] > 0
    assert profile["overturning_moment_knm"] > 0
    assert len(profile["panel_total_wind_force_kn"]) == geo.num_panels
    assert sum(profile["panel_total_wind_force_kn"]) == pytest.approx(profile["base_shear_kn"], rel=1e-3)

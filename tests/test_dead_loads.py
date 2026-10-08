import pytest
from app.presets.demo_towers import get_demo_tower
from app.engine.tower_geometry import TowerGeometryBuilder
from app.engine.dead_loads import DeadLoadCalculator, SectionProperties

def test_section_properties_chs():
    # Outer diameter 114.3mm, wall 8.0mm
    area, inertia, r_gyr = SectionProperties.calculate_area_and_inertia("CHS", 114.3, 8.0)
    assert area > 0.002 # ~26.7 cm2 = 0.00267 m2
    assert inertia > 1e-6
    assert r_gyr > 0.03 # ~3.7 cm

def test_section_properties_angle():
    # Equal angle 65x65x6mm
    area, inertia, r_gyr = SectionProperties.calculate_area_and_inertia("Angle", 65.0, 6.0)
    assert area > 0.0007 # ~7.4 cm2
    assert r_gyr > 0.01

def test_dead_loads_cumulative():
    t40 = get_demo_tower("40m")
    geo = TowerGeometryBuilder(t40)
    dead_calc = DeadLoadCalculator(t40, geo)
    data = dead_calc.calculate_panel_dead_loads()
    
    assert data["total_steel_mass_kg"] > 4000 # tower weighs multiple tonnes
    assert data["total_equipment_mass_kg"] > 0
    assert data["cum_total_dead_kn"][0] > data["cum_total_dead_kn"][-1]
    assert data["total_dead_load_kn"] == pytest.approx(data["cum_total_dead_kn"][0], rel=1e-3)

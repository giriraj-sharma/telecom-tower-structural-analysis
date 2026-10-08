from typing import Dict
from app.models.schemas import TowerInput, EquipmentItem

DEMO_CONFIGURATIONS: Dict[str, TowerInput] = {
    "30m": TowerInput(
        tower_type="3-leg",
        height_m=30.0,
        base_width_m=3.6,
        top_width_m=1.2,
        panel_height_m=2.5,
        bracing_type="X-brace",
        leg_section_type="CHS",
        leg_dimension_mm=101.6,
        leg_thickness_mm=7.1,
        brace_section_type="Angle",
        brace_dimension_mm=60.0,
        brace_thickness_mm=5.0,
        steel_yield_strength_mpa=355.0,
        steel_elastic_modulus_gpa=200.0,
        steel_density_kg_m3=7850.0,
        wind_speed_kmh=140.0,
        terrain_category="Exposure B - Urban",
        gust_factor=1.20,
        equipment_items=[
            EquipmentItem(name="3-Sector Panel Antennas", weight_kg=32.0, projected_area_m2=0.70, drag_coefficient=1.3, elevation_m=30.0, quantity=3),
            EquipmentItem(name="0.6m Solid Microwave Dish", weight_kg=45.0, projected_area_m2=0.45, drag_coefficient=1.2, elevation_m=27.0, quantity=1),
            EquipmentItem(name="Remote Radio Units (RRUs)", weight_kg=18.0, projected_area_m2=0.20, drag_coefficient=1.1, elevation_m=29.0, quantity=3)
        ]
    ),
    "40m": TowerInput(
        tower_type="4-leg",
        height_m=40.0,
        base_width_m=4.8,
        top_width_m=1.5,
        panel_height_m=2.5,
        bracing_type="X-brace",
        leg_section_type="CHS",
        leg_dimension_mm=127.0,
        leg_thickness_mm=8.8,
        brace_section_type="Angle",
        brace_dimension_mm=75.0,
        brace_thickness_mm=6.0,
        steel_yield_strength_mpa=355.0,
        steel_elastic_modulus_gpa=200.0,
        steel_density_kg_m3=7850.0,
        wind_speed_kmh=160.0,
        terrain_category="Exposure C - Open",
        gust_factor=1.20,
        equipment_items=[
            EquipmentItem(name="3-Sector 4G/5G Panels", weight_kg=38.0, projected_area_m2=0.85, drag_coefficient=1.3, elevation_m=40.0, quantity=3),
            EquipmentItem(name="1.2m Microwave Dish (Link A)", weight_kg=75.0, projected_area_m2=1.20, drag_coefficient=1.2, elevation_m=36.0, quantity=1),
            EquipmentItem(name="1.2m Microwave Dish (Link B)", weight_kg=75.0, projected_area_m2=1.20, drag_coefficient=1.2, elevation_m=32.0, quantity=1),
            EquipmentItem(name="Remote Radio Units (RRUs)", weight_kg=22.0, projected_area_m2=0.25, drag_coefficient=1.1, elevation_m=38.0, quantity=6)
        ]
    ),
    "50m": TowerInput(
        tower_type="4-leg",
        height_m=50.0,
        base_width_m=7.0,
        top_width_m=1.8,
        panel_height_m=2.5,
        bracing_type="X-brace",
        leg_section_type="CHS",
        leg_dimension_mm=193.7,
        leg_thickness_mm=11.0,
        brace_section_type="Angle",
        brace_dimension_mm=90.0,
        brace_thickness_mm=8.0,
        steel_yield_strength_mpa=355.0,
        steel_elastic_modulus_gpa=200.0,
        steel_density_kg_m3=7850.0,
        wind_speed_kmh=185.0,
        terrain_category="Exposure D - Coastal",
        gust_factor=1.25,
        equipment_items=[
            EquipmentItem(name="6-Sector Multi-Carrier Array", weight_kg=48.0, projected_area_m2=1.10, drag_coefficient=1.3, elevation_m=50.0, quantity=6),
            EquipmentItem(name="1.8m Parabolic High-Capacity Dish", weight_kg=110.0, projected_area_m2=2.60, drag_coefficient=1.25, elevation_m=44.0, quantity=2),
            EquipmentItem(name="1.2m Hub Microwave Dish", weight_kg=75.0, projected_area_m2=1.20, drag_coefficient=1.2, elevation_m=38.0, quantity=1),
            EquipmentItem(name="High-Power RRUs + DC Breakers", weight_kg=25.0, projected_area_m2=0.30, drag_coefficient=1.1, elevation_m=48.0, quantity=12)
        ]
    )
}

def get_demo_tower(key: str) -> TowerInput:
    return DEMO_CONFIGURATIONS.get(key, DEMO_CONFIGURATIONS["40m"]).model_copy(deep=True)

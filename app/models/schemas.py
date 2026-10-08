from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

class EquipmentItem(BaseModel):
    name: str = "Sector Antenna"
    weight_kg: float = Field(default=35.0, description="Weight in kg")
    projected_area_m2: float = Field(default=0.8, description="Frontal projected area in m²")
    drag_coefficient: float = Field(default=1.3, description="Aerodynamic drag coefficient Cd")
    elevation_m: float = Field(default=40.0, description="Mounting elevation in meters")
    quantity: int = Field(default=3, description="Quantity of antennas")

class TowerInput(BaseModel):
    tower_type: Literal["3-leg", "4-leg"] = Field(default="4-leg", description="Tower geometry configuration")
    height_m: float = Field(default=40.0, ge=10.0, le=120.0, description="Total tower height in meters")
    base_width_m: float = Field(default=4.5, ge=1.0, le=25.0, description="Tower width at ground base in meters")
    top_width_m: float = Field(default=1.5, ge=0.5, le=10.0, description="Tower width at top in meters")
    panel_height_m: float = Field(default=2.5, ge=1.0, le=6.0, description="Nominal panel height in meters")
    bracing_type: Literal["X-brace", "Warren", "K-brace"] = Field(default="X-brace", description="Lattice bracing scheme")
    
    # Member Cross-Section Dimensions
    leg_section_type: Literal["CHS", "Angle"] = Field(default="CHS", description="Leg member profile: Circular Hollow Section (CHS) or Equal Angle")
    leg_dimension_mm: float = Field(default=114.3, ge=30.0, le=500.0, description="Leg outer diameter or angle leg width in mm")
    leg_thickness_mm: float = Field(default=8.0, ge=3.0, le=50.0, description="Leg wall thickness in mm")
    
    brace_section_type: Literal["Angle", "CHS"] = Field(default="Angle", description="Bracing member profile")
    brace_dimension_mm: float = Field(default=65.0, ge=20.0, le=250.0, description="Bracing width/outer diameter in mm")
    brace_thickness_mm: float = Field(default=6.0, ge=2.0, le=30.0, description="Bracing thickness in mm")
    
    # Material Properties
    steel_yield_strength_mpa: float = Field(default=355.0, ge=200.0, le=700.0, description="Steel yield strength Fy in MPa (e.g., S355)")
    steel_elastic_modulus_gpa: float = Field(default=200.0, ge=150.0, le=220.0, description="Young's Modulus in GPa (default 200 GPa)")
    steel_density_kg_m3: float = Field(default=7850.0, ge=7000.0, le=8500.0, description="Steel density in kg/m³")
    
    # Wind Loading
    wind_speed_kmh: float = Field(default=160.0, ge=50.0, le=300.0, description="Basic design wind speed in km/h (3-second gust)")
    terrain_category: Literal["Exposure B - Urban", "Exposure C - Open", "Exposure D - Coastal"] = Field(
        default="Exposure C - Open", description="Terrain roughness exposure"
    )
    gust_factor: float = Field(default=1.20, ge=1.0, le=1.6, description="Gust response factor Gh")
    
    # Equipment Loading
    equipment_items: List[EquipmentItem] = Field(
        default_factory=lambda: [
            EquipmentItem(name="3-Sector Panel Antennas", weight_kg=35.0, projected_area_m2=0.85, drag_coefficient=1.3, elevation_m=40.0, quantity=3),
            EquipmentItem(name="1.2m Microwave Dish", weight_kg=75.0, projected_area_m2=1.20, drag_coefficient=1.2, elevation_m=36.0, quantity=2),
            EquipmentItem(name="Remote Radio Units (RRUs)", weight_kg=22.0, projected_area_m2=0.25, drag_coefficient=1.1, elevation_m=38.0, quantity=6)
        ]
    )

class PanelProfileData(BaseModel):
    panel_index: int
    elevation_bottom_m: float
    elevation_top_m: float
    elevation_mid_m: float
    face_width_m: float
    panel_height_m: float
    wind_velocity_pressure_kpa: float
    solidity_ratio: float
    force_coefficient_cf: float
    tower_wind_force_kn: float
    equipment_wind_force_kn: float
    total_wind_force_kn: float
    cumulative_shear_kn: float
    cumulative_moment_knm: float
    cumulative_dead_load_kn: float
    deflection_mm: float
    leg_compression_kn: float
    leg_tension_kn: float
    leg_capacity_kn: float
    leg_utilization: float
    brace_force_kn: float
    brace_capacity_kn: float
    brace_utilization: float

class CriticalMember(BaseModel):
    member_id: str
    member_type: Literal["Leg", "Diagonal Brace", "Horizontal"]
    elevation_m: float
    section_description: str
    governing_load_combination: str
    axial_force_kn: float
    capacity_kn: float
    slenderness_ratio: float
    critical_stress_mpa: float
    utilization_ratio: float
    status: Literal["SAFE", "WARNING", "FAIL"]

class LoadCombinationResult(BaseModel):
    combination_id: str
    name: str
    description: str
    factors: Dict[str, float]
    base_shear_kn: float
    overturning_moment_knm: float
    max_deflection_mm: float
    deflection_ratio: str
    max_leg_compression_kn: float
    max_leg_tension_uplift_kn: float
    max_leg_utilization: float
    max_brace_utilization: float
    max_overall_utilization: float
    critical_member_id: str
    status: Literal["SAFE", "WARNING", "FAIL"]

class IntermediateCalculations(BaseModel):
    basic_wind_speed_ms: float
    air_density_kg_m3: float
    base_velocity_pressure_kpa: float
    top_velocity_pressure_kpa: float
    exposure_coefficient_kz_top: float
    gust_factor_gh: float
    total_tower_steel_mass_kg: float
    total_equipment_mass_kg: float
    total_appurtenance_vertical_load_kn: float
    total_tower_dead_load_kn: float
    total_dead_load_kn: float
    total_wind_shear_kn: float
    overturning_moment_knm: float
    equivalent_inertia_base_m4: float
    equivalent_inertia_top_m4: float
    euler_buckling_stress_leg_mpa: float
    critical_buckling_stress_leg_mpa: float
    nominal_leg_capacity_kn: float
    allowable_deflection_h_ratio: str
    allowable_deflection_mm: float
    top_tilt_angle_deg: float
    base_leg_compression_kn: float
    base_leg_uplift_kn: float

class CostEstimate(BaseModel):
    steel_mass_kg: float
    steel_cost_usd: float
    fabrication_galvanizing_usd: float
    foundation_estimate_usd: float
    hardware_and_accessories_usd: float
    total_estimated_cost_usd: float

class GeometryNode(BaseModel):
    id: int
    x: float
    y: float
    z: float

class GeometryMember(BaseModel):
    id: str
    type: Literal["leg", "diagonal", "horizontal"]
    start_node: int
    end_node: int
    utilization: float
    status: Literal["SAFE", "WARNING", "FAIL"]

class AnalysisOutput(BaseModel):
    tower_type: str
    height_m: float
    base_width_m: float
    top_width_m: float
    overall_status: Literal["SAFE", "WARNING", "FAIL"]
    max_utilization: float
    safety_factor: float
    governing_load_combination: str
    critical_member: CriticalMember
    max_deflection_mm: float
    deflection_ratio: str
    top_tilt_angle_deg: float
    base_shear_kn: float
    overturning_moment_knm: float
    max_base_compression_kn: float
    max_base_uplift_kn: float
    total_steel_weight_tonnes: float
    estimated_cost_usd: float
    
    intermediate_calculations: IntermediateCalculations
    load_combinations: List[LoadCombinationResult]
    critical_members_table: List[CriticalMember]
    panel_profiles: List[PanelProfileData]
    cost_breakdown: CostEstimate
    
    # 3D Geometry data for visualization
    nodes: List[GeometryNode]
    members: List[GeometryMember]

class OptimizationCandidate(BaseModel):
    candidate_id: str
    name: str
    tower_type: str
    base_width_m: float
    leg_dimension_mm: float
    leg_thickness_mm: float
    brace_dimension_mm: float
    brace_thickness_mm: float
    steel_mass_kg: float
    max_utilization: float
    max_deflection_mm: float
    safety_factor: float
    estimated_cost_usd: float
    status: Literal["SAFE", "WARNING", "FAIL"]
    is_recommended: bool = False
    rank: int = 0

class OptimizationResponse(BaseModel):
    baseline_configuration: AnalysisOutput
    recommended_configuration: OptimizationCandidate
    candidates: List[OptimizationCandidate]
    tradeoff_summary: str

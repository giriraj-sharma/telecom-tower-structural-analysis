import math
from typing import List, Dict, Any, Tuple
from app.models.schemas import TowerInput, EquipmentItem
from app.engine.tower_geometry import TowerGeometryBuilder, PanelGeometry

class SectionProperties:
    @staticmethod
    def calculate_area_and_inertia(section_type: str, dimension_mm: float, thickness_mm: float) -> Tuple[float, float, float]:
        """
        Returns (Area in m2, Moment of inertia I in m4, Radius of gyration r in m)
        dimension_mm:
          - for CHS: outer diameter (OD)
          - for Angle: leg width (b)
        """
        dim_m = dimension_mm / 1000.0
        t_m = thickness_mm / 1000.0
        
        if section_type == "CHS":
            # Circular Hollow Section
            d_outer = dim_m
            d_inner = max(0.001, d_outer - 2.0 * t_m)
            area = (math.pi / 4.0) * (d_outer**2 - d_inner**2)
            inertia = (math.pi / 64.0) * (d_outer**4 - d_inner**4)
            radius_gyration = math.sqrt(inertia / area) if area > 0 else 0.01
        else:
            # Equal Angle section (L b x b x t)
            # Area ~= 2 * b * t - t^2
            b = dim_m
            t = t_m
            area = (2.0 * b - t) * t
            # Approximate minor axis radius of gyration r_z ~= 0.19 * b for equal angles (critical for buckling)
            # Moment of inertia about minor axis: I_z = A * r_z^2
            radius_gyration = 0.195 * b
            inertia = area * (radius_gyration**2)
            
        return area, inertia, radius_gyration

class DeadLoadCalculator:
    def __init__(self, params: TowerInput, geometry: TowerGeometryBuilder):
        self.params = params
        self.geometry = geometry
        self.density = params.steel_density_kg_m3
        
        # Properties
        self.a_leg, self.i_leg, self.r_leg = SectionProperties.calculate_area_and_inertia(
            params.leg_section_type, params.leg_dimension_mm, params.leg_thickness_mm
        )
        self.a_brace, self.i_brace, self.r_brace = SectionProperties.calculate_area_and_inertia(
            params.brace_section_type, params.brace_dimension_mm, params.brace_thickness_mm
        )
        # Horizontals typically same or slightly lighter than diagonals
        self.a_horiz, self.i_horiz, self.r_horiz = self.a_brace, self.i_brace, self.r_brace
        
    def calculate_panel_dead_loads(self) -> Dict[str, Any]:
        num_legs = 3 if self.params.tower_type == "3-leg" else 4
        num_faces = num_legs
        
        panel_steel_mass_kg: List[float] = []
        panel_equipment_mass_kg: List[float] = [0.0] * self.geometry.num_panels
        
        # Connection factor: +12% for gussets, bolts, splices, galvanizing
        connection_factor = 1.12
        # Ladder & waveguide run allowance: 20 kg/m
        ladder_feedline_kg_per_m = 20.0
        
        for panel in self.geometry.panels:
            h_p = panel.height
            w_b = panel.width_bottom
            w_t = panel.width_top
            w_avg = panel.width_mid
            
            # Leg mass
            # Leg inclination length
            leg_len = math.sqrt(h_p**2 + ((w_b - w_t) / 2.0)**2)
            mass_legs = num_legs * leg_len * self.a_leg * self.density
            
            # Horizontal mass (at top of panel)
            mass_horiz = num_faces * w_t * self.a_horiz * self.density
            
            # Diagonals
            if self.params.bracing_type == "X-brace":
                diag_len = math.sqrt(h_p**2 + w_avg**2)
                mass_diag = num_faces * 2.0 * diag_len * self.a_brace * self.density
            elif self.params.bracing_type == "Warren":
                diag_len = math.sqrt(h_p**2 + w_avg**2)
                mass_diag = num_faces * 1.0 * diag_len * self.a_brace * self.density
            else: # K-brace
                diag_len = math.sqrt((h_p / 2.0)**2 + (w_avg / 2.0)**2) * 2.0
                mass_diag = num_faces * 2.0 * diag_len * self.a_brace * self.density
                
            panel_bare_steel = mass_legs + mass_horiz + mass_diag
            panel_total_steel = (panel_bare_steel * connection_factor) + (ladder_feedline_kg_per_m * h_p)
            panel_steel_mass_kg.append(panel_total_steel)
            
        # Distribute equipment items to nearest panel
        for eq in self.params.equipment_items:
            total_eq_weight = eq.weight_kg * eq.quantity
            # Find matching panel index
            p_idx = min(self.geometry.num_panels - 1, max(0, int(eq.elevation_m / self.geometry.panel_height)))
            panel_equipment_mass_kg[p_idx] += total_eq_weight
            
        # Cumulative from top downwards
        cum_steel_kn = [0.0] * self.geometry.num_panels
        cum_equip_kn = [0.0] * self.geometry.num_panels
        cum_total_dead_kn = [0.0] * self.geometry.num_panels
        
        g = 9.80665 / 1000.0 # kN per kg
        
        running_steel_kn = 0.0
        running_equip_kn = 0.0
        
        # Traverse from top (index num_panels - 1) down to 0
        for i in reversed(range(self.geometry.num_panels)):
            running_steel_kn += panel_steel_mass_kg[i] * g
            running_equip_kn += panel_equipment_mass_kg[i] * g
            cum_steel_kn[i] = running_steel_kn
            cum_equip_kn[i] = running_equip_kn
            cum_total_dead_kn[i] = running_steel_kn + running_equip_kn
            
        total_steel_mass = sum(panel_steel_mass_kg)
        total_equip_mass = sum(eq.weight_kg * eq.quantity for eq in self.params.equipment_items)
        
        return {
            "panel_steel_mass_kg": panel_steel_mass_kg,
            "panel_equipment_mass_kg": panel_equipment_mass_kg,
            "cum_steel_kn": cum_steel_kn,
            "cum_equip_kn": cum_equip_kn,
            "cum_total_dead_kn": cum_total_dead_kn,
            "total_steel_mass_kg": total_steel_mass,
            "total_equipment_mass_kg": total_equip_mass,
            "total_tower_dead_load_kn": total_steel_mass * g,
            "total_equipment_dead_load_kn": total_equip_mass * g,
            "total_dead_load_kn": (total_steel_mass + total_equip_mass) * g
        }

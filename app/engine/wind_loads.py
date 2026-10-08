import math
from typing import List, Dict, Any, Tuple
from app.models.schemas import TowerInput, EquipmentItem
from app.engine.tower_geometry import TowerGeometryBuilder

class WindLoadCalculator:
    def __init__(self, params: TowerInput, geometry: TowerGeometryBuilder):
        self.params = params
        self.geometry = geometry
        
        # Wind velocity conversion
        self.v_ms = params.wind_speed_kmh / 3.6
        self.air_density = 1.225 # kg/m3 standard at sea level
        self.k_d = 0.85 # TIA-222 lattice directionality factor
        self.k_zt = 1.0 # Topographic factor
        self.g_h = params.gust_factor
        
    def get_exposure_coefficient(self, z: float) -> float:
        """
        Calculates Kz velocity pressure coefficient based on terrain exposure
        """
        z_eff = max(4.57, z) # minimum height per TIA-222
        exposure = self.params.terrain_category
        
        if "Exposure B" in exposure:
            zg = 365.76
            alpha = 7.0
            kz = 2.01 * (z_eff / zg) ** (2.0 / alpha)
            return max(0.70, min(1.80, kz))
        elif "Exposure D" in exposure:
            zg = 213.36
            alpha = 11.5
            kz = 2.01 * (z_eff / zg) ** (2.0 / alpha)
            return max(1.03, min(2.20, kz))
        else: # Exposure C (default)
            zg = 274.32
            alpha = 9.5
            kz = 2.01 * (z_eff / zg) ** (2.0 / alpha)
            return max(0.85, min(2.01, kz))
            
    def get_velocity_pressure_kpa(self, z: float) -> float:
        """
        qz = 0.613 * Kz * Kd * Kzt * V^2 (N/m2), returned in kPa
        """
        kz = self.get_exposure_coefficient(z)
        qz_pa = 0.613 * kz * self.k_d * self.k_zt * (self.v_ms ** 2)
        return qz_pa / 1000.0 # kPa

    def calculate_wind_profile(self) -> Dict[str, Any]:
        d_leg_m = self.params.leg_dimension_mm / 1000.0
        d_brace_m = self.params.brace_dimension_mm / 1000.0
        is_3leg = self.params.tower_type == "3-leg"
        
        panel_qz_kpa: List[float] = []
        panel_solidity: List[float] = []
        panel_cf: List[float] = []
        panel_tower_wind_force_kn: List[float] = []
        panel_equipment_wind_force_kn: List[float] = [0.0] * self.geometry.num_panels
        panel_total_wind_force_kn: List[float] = []
        
        for panel in self.geometry.panels:
            z_mid = panel.z_mid
            qz = self.get_velocity_pressure_kpa(z_mid)
            panel_qz_kpa.append(qz)
            
            # Panel gross face area
            w_avg = panel.width_mid
            h_p = panel.height
            gross_area = w_avg * h_p
            
            # Projected steel area on one face
            # 2 legs visible per face
            leg_proj = 2.0 * d_leg_m * h_p
            # Diagonals on one face
            if self.params.bracing_type == "X-brace":
                diag_len = math.sqrt(h_p**2 + w_avg**2)
                diag_proj = 2.0 * d_brace_m * diag_len
            elif self.params.bracing_type == "Warren":
                diag_len = math.sqrt(h_p**2 + w_avg**2)
                diag_proj = 1.0 * d_brace_m * diag_len
            else: # K-brace
                diag_len = math.sqrt((h_p / 2.0)**2 + (w_avg / 2.0)**2) * 2.0
                diag_proj = 2.0 * d_brace_m * diag_len
            # Horizontal member at top
            horiz_proj = 1.0 * d_brace_m * panel.width_top
            
            solid_area = leg_proj + diag_proj + horiz_proj
            phi = max(0.06, min(0.48, solid_area / max(gross_area, 0.1)))
            panel_solidity.append(phi)
            
            # Force coefficient Cf per TIA-222 / ASCE 7
            if is_3leg:
                cf = 3.4 * (phi ** 2) - 4.7 * phi + 3.4
                cf = max(1.4, min(2.5, cf))
                # For triangular tower, wind on face vs corner has shielding factor
                shielding = 1.0 + (1.0 - phi) ** 1.8
            else:
                cf = 4.0 * (phi ** 2) - 5.9 * phi + 4.0
                cf = max(1.4, min(2.6, cf))
                # For square tower: windward face + leeward face with shielding
                shielding = 1.0 + (1.0 - phi) ** 2.0
                
            panel_cf.append(cf)
            
            # Tower lattice wind force (kN) = qz (kPa) * Gh * Cf * solid_area (m2) * shielding
            f_tower_kn = qz * self.g_h * cf * solid_area * shielding
            panel_tower_wind_force_kn.append(f_tower_kn)
            
        # Equipment wind forces
        for eq in self.params.equipment_items:
            qz_eq = self.get_velocity_pressure_kpa(eq.elevation_m)
            # F_eq = qz * Gh * Cd * Area * qty
            f_eq_kn = qz_eq * self.g_h * eq.drag_coefficient * eq.projected_area_m2 * eq.quantity
            p_idx = min(self.geometry.num_panels - 1, max(0, int(eq.elevation_m / self.geometry.panel_height)))
            panel_equipment_wind_force_kn[p_idx] += f_eq_kn

        for i in range(self.geometry.num_panels):
            f_tot = panel_tower_wind_force_kn[i] + panel_equipment_wind_force_kn[i]
            panel_total_wind_force_kn.append(f_tot)
            
        # Cumulative wind shear and overturning moment from top down
        cum_shear_kn = [0.0] * self.geometry.num_panels
        cum_moment_knm = [0.0] * self.geometry.num_panels
        
        running_shear = 0.0
        # Calculate shear and moment at each panel elevation bottom
        for i in range(self.geometry.num_panels):
            # Shear at base of panel i includes all wind forces above z_bottom[i]
            shear_at_panel = sum(panel_total_wind_force_kn[k] for k in range(i, self.geometry.num_panels))
            # Moment at z_bottom[i] = sum(F_k * (z_mid[k] - z_bottom[i]))
            moment_at_panel = sum(panel_total_wind_force_kn[k] * (self.geometry.panels[k].z_mid - self.geometry.panels[i].z_bottom) 
                                 for k in range(i, self.geometry.num_panels))
            cum_shear_kn[i] = shear_at_panel
            cum_moment_knm[i] = moment_at_panel
            
        base_shear_kn = cum_shear_kn[0]
        overturning_moment_knm = cum_moment_knm[0]
        
        return {
            "v_ms": self.v_ms,
            "air_density": self.air_density,
            "base_qz_kpa": self.get_velocity_pressure_kpa(1.0),
            "top_qz_kpa": self.get_velocity_pressure_kpa(self.geometry.height),
            "kz_top": self.get_exposure_coefficient(self.geometry.height),
            "panel_qz_kpa": panel_qz_kpa,
            "panel_solidity": panel_solidity,
            "panel_cf": panel_cf,
            "panel_tower_wind_force_kn": panel_tower_wind_force_kn,
            "panel_equipment_wind_force_kn": panel_equipment_wind_force_kn,
            "panel_total_wind_force_kn": panel_total_wind_force_kn,
            "cum_shear_kn": cum_shear_kn,
            "cum_moment_knm": cum_moment_knm,
            "base_shear_kn": base_shear_kn,
            "overturning_moment_knm": overturning_moment_knm
        }

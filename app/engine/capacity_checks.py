import math
from typing import Dict, Any, Tuple
from app.models.schemas import TowerInput
from app.engine.dead_loads import SectionProperties

class CapacityChecker:
    def __init__(self, params: TowerInput):
        self.params = params
        self.fy = params.steel_yield_strength_mpa # MPa (N/mm2)
        self.e_steel = params.steel_elastic_modulus_gpa * 1000.0 # MPa
        self.phi_c = 0.90 # AISC LRFD compression resistance factor
        self.phi_t = 0.90 # AISC LRFD tension resistance factor
        
        # Section properties
        self.a_leg, self.i_leg, self.r_leg = SectionProperties.calculate_area_and_inertia(
            params.leg_section_type, params.leg_dimension_mm, params.leg_thickness_mm
        )
        self.a_brace, self.i_brace, self.r_brace = SectionProperties.calculate_area_and_inertia(
            params.brace_section_type, params.brace_dimension_mm, params.brace_thickness_mm
        )
        
        # Slenderness limits
        # Transition slenderness: lambda_c = 4.71 * sqrt(E / Fy)
        self.lambda_transition = 4.71 * math.sqrt(self.e_steel / self.fy)
        
    def calculate_column_buckling_stress(self, length_m: float, radius_gyration_m: float, k_factor: float = 1.0) -> Tuple[float, float, float]:
        """
        Calculates (lambda slenderness, Fe Euler stress MPa, Fcr critical buckling stress MPa)
        """
        r_eff = max(0.005, radius_gyration_m)
        slenderness = (k_factor * length_m) / r_eff
        
        # Elastic Euler buckling stress Fe
        fe_mpa = (math.pi ** 2 * self.e_steel) / (slenderness ** 2)
        
        # AISC 360-16 / Eurocode column curve
        if slenderness <= self.lambda_transition:
            # Inelastic buckling
            exponent = self.fy / fe_mpa
            fcr_mpa = (0.658 ** exponent) * self.fy
        else:
            # Elastic buckling
            fcr_mpa = 0.877 * fe_mpa
            
        fcr_mpa = min(self.fy, max(1.0, fcr_mpa))
        return slenderness, fe_mpa, fcr_mpa

    def get_leg_capacity(self, unbraced_length_m: float) -> Dict[str, Any]:
        """
        Leg member capacity: compression (buckling) and tension (yielding)
        """
        k_factor = 0.85 # leg is continuous across panel joints
        slenderness, fe_mpa, fcr_mpa = self.calculate_column_buckling_stress(
            unbraced_length_m, self.r_leg, k_factor
        )
        
        # Compression design capacity in kN: phi_c * Ag * Fcr * 10^3 kN
        # Ag is in m2, Fcr is in MPa (MN/m2). Ag * Fcr is MN = 1000 kN
        comp_cap_kn = self.phi_c * (self.a_leg * fcr_mpa * 1000.0)
        
        # Tension design capacity in kN: phi_t * Ag * Fy * 1000
        tens_cap_kn = self.phi_t * (self.a_leg * self.fy * 1000.0)
        
        return {
            "slenderness": slenderness,
            "fe_mpa": fe_mpa,
            "fcr_mpa": fcr_mpa,
            "comp_cap_kn": comp_cap_kn,
            "tens_cap_kn": tens_cap_kn,
            "area_cm2": self.a_leg * 10000.0,
            "radius_gyration_cm": self.r_leg * 100.0
        }

    def get_brace_capacity(self, length_m: float, bracing_type: str = "X-brace") -> Dict[str, Any]:
        """
        Bracing member capacity.
        For X-brace, the crossing diagonal provides lateral restraint at mid-intersection
        giving effective buckling length factor K = 0.50 per TIA-222 Section 4.5.3 / Eurocode 3.
        For Warren or K-brace, K = 0.90 - 1.00.
        """
        k_factor = 0.50 if bracing_type == "X-brace" else 0.90
        slenderness, fe_mpa, fcr_mpa = self.calculate_column_buckling_stress(
            length_m, self.r_brace, k_factor
        )
        comp_cap_kn = self.phi_c * (self.a_brace * fcr_mpa * 1000.0)
        tens_cap_kn = self.phi_t * (self.a_brace * self.fy * 1000.0)
        
        # Effective capacity for cross-braced panel:
        # Cross diagonals share shear through tension-compression equilibrium.
        # Under peak wind, the tension diagonal provides reliable ductile tension capacity.
        effective_cap_kn = tens_cap_kn if bracing_type == "X-brace" else comp_cap_kn
        
        return {
            "slenderness": slenderness,
            "fe_mpa": fe_mpa,
            "fcr_mpa": fcr_mpa,
            "comp_cap_kn": comp_cap_kn,
            "tens_cap_kn": tens_cap_kn,
            "effective_cap_kn": effective_cap_kn,
            "area_cm2": self.a_brace * 10000.0,
            "radius_gyration_cm": self.r_brace * 100.0
        }

    @staticmethod
    def evaluate_status(utilization: float) -> str:
        if utilization > 1.00:
            return "FAIL"
        elif utilization >= 0.85:
            return "WARNING"
        else:
            return "SAFE"

"""
Absorption Calculator - Sabine and Eyring equations

Calculates required absorption to achieve target reverberation time.

Sabine Equation (for live rooms):
T60 = 0.161 * V / A  (metric)
T60 = 0.049 * V / A  (imperial)

Eyring Equation (for dead rooms):
T60 = 0.161 * V / (-S * ln(1 - α_avg))  (metric)

Where:
- V = room volume
- A = total absorption (Sabins)
- S = total surface area
- α_avg = average absorption coefficient
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class SurfaceType(Enum):
    """Common room surface types with absorption coefficients"""
    CONCRETE = "concrete"
    DRYWALL = "drywall"
    PLYWOOD = "plywood"
    CARPET = "carpet"
    HARDWOOD = "hardwood"
    GLASS = "glass"
    BRICK = "brick"
    ACOUSTIC_TILE = "acoustic_tile"


# Absorption coefficients at octave band centers
# Format: {surface_type: {frequency: coefficient}}
ABSORPTION_COEFFICIENTS = {
    SurfaceType.CONCRETE: {
        125: 0.01, 250: 0.01, 500: 0.02, 1000: 0.02, 2000: 0.02, 4000: 0.03
    },
    SurfaceType.DRYWALL: {
        125: 0.29, 250: 0.10, 500: 0.05, 1000: 0.04, 2000: 0.07, 4000: 0.09
    },
    SurfaceType.PLYWOOD: {
        125: 0.28, 250: 0.22, 500: 0.17, 1000: 0.09, 2000: 0.10, 4000: 0.11
    },
    SurfaceType.CARPET: {
        125: 0.01, 250: 0.02, 500: 0.06, 1000: 0.15, 2000: 0.25, 4000: 0.45
    },
    SurfaceType.HARDWOOD: {
        125: 0.15, 250: 0.11, 500: 0.10, 1000: 0.07, 2000: 0.06, 4000: 0.07
    },
    SurfaceType.GLASS: {
        125: 0.35, 250: 0.25, 500: 0.18, 1000: 0.12, 2000: 0.07, 4000: 0.04
    },
    SurfaceType.BRICK: {
        125: 0.03, 250: 0.03, 500: 0.03, 1000: 0.04, 2000: 0.05, 4000: 0.07
    },
    SurfaceType.ACOUSTIC_TILE: {
        125: 0.10, 250: 0.20, 500: 0.40, 1000: 0.55, 2000: 0.60, 4000: 0.55
    }
}

# Treatment material absorption coefficients
TREATMENT_COEFFICIENTS = {
    "2_inch_fiberglass": {
        "name": "2\" Fiberglass (OC 703 or equivalent)",
        "coefficients": {125: 0.22, 250: 0.82, 500: 1.00, 1000: 1.00, 2000: 1.00, 4000: 1.00},
        "nrc": 0.95
    },
    "4_inch_fiberglass": {
        "name": "4\" Fiberglass (OC 703 or equivalent)",
        "coefficients": {125: 0.84, 250: 1.00, 500: 1.00, 1000: 1.00, 2000: 1.00, 4000: 1.00},
        "nrc": 1.00
    },
    "2_inch_rockwool": {
        "name": "2\" Mineral Wool (Rockwool)",
        "coefficients": {125: 0.30, 250: 0.75, 500: 1.00, 1000: 1.00, 2000: 1.00, 4000: 1.00},
        "nrc": 0.95
    },
    "4_inch_rockwool": {
        "name": "4\" Mineral Wool (Rockwool)",
        "coefficients": {125: 0.80, 250: 1.00, 500: 1.00, 1000: 1.00, 2000: 1.00, 4000: 1.00},
        "nrc": 1.00
    },
    "bass_trap_corner": {
        "name": "Corner Bass Trap (thick porous)",
        "coefficients": {125: 0.90, 250: 1.00, 500: 1.00, 1000: 1.00, 2000: 1.00, 4000: 1.00},
        "nrc": 1.00
    },
    "membrane_absorber": {
        "name": "Membrane/Diaphragmatic Absorber",
        "coefficients": {125: 0.85, 250: 0.60, 500: 0.30, 1000: 0.10, 2000: 0.05, 4000: 0.05},
        "nrc": 0.40
    },
    "acoustic_foam_2inch": {
        "name": "2\" Acoustic Foam",
        "coefficients": {125: 0.11, 250: 0.30, 500: 0.68, 1000: 0.95, 2000: 1.00, 4000: 0.97},
        "nrc": 0.75
    },
    "acoustic_foam_4inch": {
        "name": "4\" Acoustic Foam",
        "coefficients": {125: 0.24, 250: 0.60, 500: 0.95, 1000: 1.00, 2000: 1.00, 4000: 1.00},
        "nrc": 0.90
    },
    "diffuser_qrd": {
        "name": "QRD Diffuser",
        "coefficients": {125: 0.15, 250: 0.25, 500: 0.30, 1000: 0.25, 2000: 0.20, 4000: 0.15},
        "nrc": 0.25
    }
}


@dataclass
class Surface:
    """Represents a room surface"""
    name: str
    area: float  # square meters or feet
    surface_type: SurfaceType
    
    def get_absorption(self, frequency: int) -> float:
        """Get absorption (Sabins) at a frequency"""
        coef = ABSORPTION_COEFFICIENTS.get(self.surface_type, {}).get(frequency, 0.1)
        return self.area * coef


@dataclass
class AbsorptionResult:
    """Result of absorption calculation"""
    current_t60: Dict[int, float]
    target_t60: float
    current_absorption: Dict[int, float]
    required_absorption: Dict[int, float]
    missing_absorption: Dict[int, float]
    recommended_treatment: List[Dict]
    room_volume: float
    surface_area: float


class AbsorptionCalculator:
    """
    Calculates room absorption and required treatment.
    
    Uses Sabine equation for live rooms (α < 0.2) and
    Eyring equation for dead rooms (α > 0.2).
    """
    
    # Octave band center frequencies
    FREQUENCIES = [125, 250, 500, 1000, 2000, 4000]
    
    # Constants
    SABINE_METRIC = 0.161
    SABINE_IMPERIAL = 0.049
    
    def __init__(self, length: float, width: float, height: float,
                 use_metric: bool = True):
        """
        Initialize absorption calculator.
        
        Args:
            length, width, height: Room dimensions
            use_metric: If True, dimensions in meters
        """
        self.length = length
        self.width = width
        self.height = height
        self.use_metric = use_metric
        self.sabine_constant = self.SABINE_METRIC if use_metric else self.SABINE_IMPERIAL
        
        self.surfaces: List[Surface] = []
        self._setup_default_surfaces()
    
    @property
    def volume(self) -> float:
        return self.length * self.width * self.height
    
    @property
    def surface_area(self) -> float:
        return 2 * (
            self.length * self.width +
            self.length * self.height +
            self.width * self.height
        )
    
    def _setup_default_surfaces(self):
        """Set up default room surfaces (drywall walls, concrete floor, drywall ceiling)"""
        # Floor
        self.surfaces.append(Surface(
            name="Floor",
            area=self.length * self.width,
            surface_type=SurfaceType.HARDWOOD
        ))
        
        # Ceiling
        self.surfaces.append(Surface(
            name="Ceiling",
            area=self.length * self.width,
            surface_type=SurfaceType.DRYWALL
        ))
        
        # Front wall
        self.surfaces.append(Surface(
            name="Front Wall",
            area=self.width * self.height,
            surface_type=SurfaceType.DRYWALL
        ))
        
        # Rear wall
        self.surfaces.append(Surface(
            name="Rear Wall",
            area=self.width * self.height,
            surface_type=SurfaceType.DRYWALL
        ))
        
        # Left wall
        self.surfaces.append(Surface(
            name="Left Wall",
            area=self.length * self.height,
            surface_type=SurfaceType.DRYWALL
        ))
        
        # Right wall
        self.surfaces.append(Surface(
            name="Right Wall",
            area=self.length * self.height,
            surface_type=SurfaceType.DRYWALL
        ))
    
    def set_surface_material(self, surface_name: str, surface_type: SurfaceType):
        """Change the material of a surface"""
        for surface in self.surfaces:
            if surface.name.lower() == surface_name.lower():
                surface.surface_type = surface_type
                return
        raise ValueError(f"Surface '{surface_name}' not found")
    
    def calculate_total_absorption(self, frequency: int) -> float:
        """Calculate total absorption at a frequency"""
        return sum(s.get_absorption(frequency) for s in self.surfaces)
    
    def calculate_average_alpha(self, frequency: int) -> float:
        """Calculate average absorption coefficient at a frequency"""
        total_absorption = self.calculate_total_absorption(frequency)
        return total_absorption / self.surface_area
    
    def calculate_t60_sabine(self, frequency: int) -> float:
        """
        Calculate T60 using Sabine equation.
        
        T60 = 0.161 * V / A (metric)
        """
        absorption = self.calculate_total_absorption(frequency)
        if absorption == 0:
            return float('inf')
        return self.sabine_constant * self.volume / absorption
    
    def calculate_t60_eyring(self, frequency: int) -> float:
        """
        Calculate T60 using Eyring equation.
        
        T60 = 0.161 * V / (-S * ln(1 - α))
        
        More accurate for dead rooms (α > 0.2)
        """
        alpha = self.calculate_average_alpha(frequency)
        
        # Prevent log(0) or log(negative)
        if alpha >= 1.0:
            return 0.0
        if alpha <= 0:
            return float('inf')
        
        return self.sabine_constant * self.volume / (-self.surface_area * np.log(1 - alpha))
    
    def calculate_t60(self, frequency: int) -> float:
        """
        Calculate T60 using appropriate equation.
        
        Uses Eyring for dead rooms (target < 0.5s), Sabine for live rooms.
        """
        alpha = self.calculate_average_alpha(frequency)
        
        # Use Eyring for higher absorption
        if alpha > 0.2:
            return self.calculate_t60_eyring(frequency)
        else:
            return self.calculate_t60_sabine(frequency)
    
    def calculate_required_absorption(self, target_t60: float, frequency: int) -> float:
        """
        Calculate required absorption to achieve target T60.
        
        From Eyring: A = 0.161 * V / T60
        """
        return self.sabine_constant * self.volume / target_t60
    
    def analyze(self, target_t60: float = 0.25) -> AbsorptionResult:
        """
        Perform complete absorption analysis.
        
        Args:
            target_t60: Target reverberation time (seconds)
            
        Returns:
            AbsorptionResult with current state and required treatment
        """
        current_t60 = {}
        current_absorption = {}
        required_absorption = {}
        missing_absorption = {}
        
        for freq in self.FREQUENCIES:
            current_t60[freq] = self.calculate_t60(freq)
            current_absorption[freq] = self.calculate_total_absorption(freq)
            required_absorption[freq] = self.calculate_required_absorption(target_t60, freq)
            missing_absorption[freq] = max(0, required_absorption[freq] - current_absorption[freq])
        
        # Generate treatment recommendations
        recommended_treatment = self._recommend_treatment(missing_absorption, target_t60)
        
        return AbsorptionResult(
            current_t60=current_t60,
            target_t60=target_t60,
            current_absorption=current_absorption,
            required_absorption=required_absorption,
            missing_absorption=missing_absorption,
            recommended_treatment=recommended_treatment,
            room_volume=self.volume,
            surface_area=self.surface_area
        )
    
    def _recommend_treatment(self, missing_absorption: Dict[int, float],
                            target_t60: float) -> List[Dict]:
        """Generate treatment recommendations based on missing absorption"""
        recommendations = []
        
        # Analyze where absorption is most needed
        bass_deficit = (missing_absorption.get(125, 0) + missing_absorption.get(250, 0)) / 2
        mid_deficit = (missing_absorption.get(500, 0) + missing_absorption.get(1000, 0)) / 2
        high_deficit = (missing_absorption.get(2000, 0) + missing_absorption.get(4000, 0)) / 2
        
        # Bass traps for low frequency
        if bass_deficit > 0:
            trap_material = TREATMENT_COEFFICIENTS["4_inch_rockwool"]
            # Calculate required area
            avg_coef = (trap_material["coefficients"][125] + trap_material["coefficients"][250]) / 2
            required_area = bass_deficit / avg_coef
            
            recommendations.append({
                "type": "bass_trap",
                "material": trap_material["name"],
                "area_needed": round(required_area, 1),
                "location": "Room corners (floor-wall-ceiling junctions)",
                "priority": "high" if bass_deficit > mid_deficit else "medium",
                "description": (
                    f"Install {required_area:.1f} {'m²' if self.use_metric else 'ft²'} "
                    f"of bass trapping to control low frequencies"
                )
            })
        
        # Broadband absorbers for mid frequencies
        if mid_deficit > 0:
            absorber_material = TREATMENT_COEFFICIENTS["2_inch_rockwool"]
            avg_coef = (absorber_material["coefficients"][500] + absorber_material["coefficients"][1000]) / 2
            required_area = mid_deficit / avg_coef
            
            recommendations.append({
                "type": "broadband_absorber",
                "material": absorber_material["name"],
                "area_needed": round(required_area, 1),
                "location": "First reflection points (side walls, ceiling)",
                "priority": "high",
                "description": (
                    f"Install {required_area:.1f} {'m²' if self.use_metric else 'ft²'} "
                    f"of broadband absorption at first reflection points"
                )
            })
        
        # High frequency usually doesn't need specific treatment
        if high_deficit > mid_deficit * 1.5:
            recommendations.append({
                "type": "high_frequency_absorber",
                "material": "Acoustic foam or thin fabric panels",
                "area_needed": round(high_deficit, 1),
                "location": "Distributed on walls and ceiling",
                "priority": "low",
                "description": "High frequencies often controlled by furnishings and other treatment"
            })
        
        return recommendations
    
    def get_surface_breakdown(self) -> List[Dict]:
        """Get absorption breakdown by surface"""
        breakdown = []
        for surface in self.surfaces:
            surface_data = {
                "name": surface.name,
                "area": surface.area,
                "material": surface.surface_type.value,
                "absorption_by_frequency": {}
            }
            for freq in self.FREQUENCIES:
                surface_data["absorption_by_frequency"][freq] = round(
                    surface.get_absorption(freq), 2
                )
            breakdown.append(surface_data)
        return breakdown


def calculate_panel_count(missing_absorption: float, panel_area: float = 0.5,
                         panel_coefficient: float = 1.0) -> int:
    """
    Calculate number of panels needed.
    
    Args:
        missing_absorption: Required absorption in Sabins
        panel_area: Area of each panel (m² or ft²)
        panel_coefficient: Absorption coefficient of panel material
        
    Returns:
        Number of panels (rounded up)
    """
    if panel_coefficient <= 0:
        return 0
    
    absorption_per_panel = panel_area * panel_coefficient
    return int(np.ceil(missing_absorption / absorption_per_panel))

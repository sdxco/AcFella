"""
Schroeder Frequency and Transition Analysis

The Schroeder frequency (fc) marks the transition between:
- Modal behavior (below fc): Room acts as a resonator with distinct modes
- Statistical behavior (above fc): Room acts as a reflector with diffuse field

Formula: fc = 2000 * sqrt(T60 / V)
Where T60 is reverberation time (s) and V is volume (m³)

Below the Schroeder frequency: Bass traps needed
Above the Schroeder frequency: Absorbers and diffusers effective
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SchroederAnalysis:
    """Results of Schroeder frequency analysis"""
    schroeder_frequency: float
    modal_density: float
    room_volume: float
    t60: float
    transition_region_low: float
    transition_region_high: float
    
    @property
    def bass_trap_range(self) -> str:
        return f"20 Hz - {self.schroeder_frequency:.0f} Hz"
    
    @property
    def absorber_range(self) -> str:
        return f"{self.schroeder_frequency:.0f} Hz - 4000 Hz"


class SchroederAnalyzer:
    """
    Analyzes the Schroeder frequency and modal density of a room.
    
    Based on Manfred Schroeder's work on room acoustics and the
    Master Handbook of Acoustics.
    """
    
    SPEED_OF_SOUND = 344.0  # m/s at 20°C
    
    def __init__(self, volume: float, t60: float = 0.3, use_metric: bool = True):
        """
        Initialize Schroeder analyzer.
        
        Args:
            volume: Room volume
            t60: Reverberation time (seconds)
            use_metric: If True, volume is in m³; otherwise ft³
        """
        self.use_metric = use_metric
        
        # Convert to metric if needed
        if use_metric:
            self.volume = volume
        else:
            self.volume = volume * 0.0283168  # ft³ to m³
            
        self.t60 = t60
    
    def calculate_schroeder_frequency(self) -> float:
        """
        Calculate the Schroeder frequency (crossover frequency).
        
        fc = 2000 * sqrt(T60 / V)
        """
        return 2000 * np.sqrt(self.t60 / self.volume)
    
    def calculate_modal_density(self, frequency: float) -> float:
        """
        Calculate modal density (modes per Hz) at a given frequency.
        
        n(f) = 4πV * f² / c³
        
        Where V is volume and c is speed of sound.
        """
        c = self.SPEED_OF_SOUND
        return (4 * np.pi * self.volume * frequency**2) / (c**3)
    
    def calculate_modal_overlap(self, frequency: float) -> float:
        """
        Calculate modal overlap factor.
        
        M = n(f) * Δf
        
        Where Δf is the -3dB bandwidth of a mode.
        For M > 3, the field can be considered diffuse.
        """
        # Mode bandwidth approximation
        delta_f = 2.2 / self.t60  # Approximate -3dB bandwidth
        return self.calculate_modal_density(frequency) * delta_f
    
    def analyze(self) -> SchroederAnalysis:
        """Perform complete Schroeder analysis"""
        fc = self.calculate_schroeder_frequency()
        
        # Modal density at Schroeder frequency
        md = self.calculate_modal_density(fc)
        
        # Transition region (typically ±1/3 octave around fc)
        factor = 2 ** (1/6)  # 1/3 octave
        
        return SchroederAnalysis(
            schroeder_frequency=fc,
            modal_density=md,
            room_volume=self.volume,
            t60=self.t60,
            transition_region_low=fc / factor,
            transition_region_high=fc * factor
        )
    
    def get_treatment_zones(self) -> Dict[str, any]:
        """
        Define treatment zones based on Schroeder frequency.
        
        Returns recommendations for each frequency zone.
        """
        fc = self.calculate_schroeder_frequency()
        
        return {
            "schroeder_frequency": round(fc, 1),
            "zones": [
                {
                    "name": "Deep Bass Zone",
                    "range": "20 Hz - 80 Hz",
                    "low": 20,
                    "high": 80,
                    "behavior": "Strong modal behavior",
                    "treatment": "Pressure-based bass traps (membrane/diaphragmatic)",
                    "placement": "Room corners (tri-corners for maximum effect)",
                    "priority": "critical" if fc > 100 else "high"
                },
                {
                    "name": "Upper Bass Zone",
                    "range": "80 Hz - 300 Hz",
                    "low": 80,
                    "high": 300,
                    "behavior": "Modal to transition",
                    "treatment": "Thick porous absorbers (4-6 inches) or tuned bass traps",
                    "placement": "Wall-ceiling corners, behind listening position",
                    "priority": "high"
                },
                {
                    "name": "Low-Mid Zone",
                    "range": "300 Hz - 1000 Hz",
                    "low": 300,
                    "high": 1000,
                    "behavior": "Mostly diffuse field",
                    "treatment": "Broadband absorbers (2-4 inches)",
                    "placement": "First reflection points",
                    "priority": "high"
                },
                {
                    "name": "Mid-High Zone",
                    "range": "1000 Hz - 4000 Hz",
                    "low": 1000,
                    "high": 4000,
                    "behavior": "Diffuse field",
                    "treatment": "Absorbers + Diffusers",
                    "placement": "Rear wall, ceiling",
                    "priority": "medium"
                },
                {
                    "name": "High Frequency Zone",
                    "range": "4000 Hz - 20000 Hz",
                    "low": 4000,
                    "high": 20000,
                    "behavior": "Ray acoustics",
                    "treatment": "Thin absorbers, diffusers, or natural room absorption",
                    "placement": "Generally self-treating via furnishings",
                    "priority": "low"
                }
            ],
            "recommendation": self._get_recommendation(fc)
        }
    
    def _get_recommendation(self, fc: float) -> str:
        """Generate recommendation based on Schroeder frequency"""
        if fc < 100:
            return (
                f"Low Schroeder frequency ({fc:.0f} Hz) indicates a large room. "
                "Modal problems are limited to deep bass. Focus on broadband treatment."
            )
        elif fc < 200:
            return (
                f"Moderate Schroeder frequency ({fc:.0f} Hz) is typical for home studios. "
                "Balance bass trapping with mid-frequency absorption."
            )
        elif fc < 300:
            return (
                f"High Schroeder frequency ({fc:.0f} Hz) indicates a small room. "
                "Modal behavior extends into upper bass. Prioritize corner bass traps."
            )
        else:
            return (
                f"Very high Schroeder frequency ({fc:.0f} Hz) indicates a very small room. "
                "Strong modal problems expected. Maximum bass trapping required. "
                "Consider if room is suitable for critical listening."
            )
    
    def calculate_minimum_distance_for_diffuser(self, design_frequency: float = 500) -> float:
        """
        Calculate minimum listening distance from a diffuser.
        
        Rule: Listener should be at least 3 wavelengths from diffuser
        to avoid near-field distortion.
        
        Args:
            design_frequency: Design frequency of diffuser (Hz)
            
        Returns:
            Minimum distance in meters
        """
        wavelength = self.SPEED_OF_SOUND / design_frequency
        return 3 * wavelength
    
    def get_frequency_behavior(self, frequency: float) -> Dict[str, any]:
        """
        Describe the acoustic behavior at a specific frequency.
        """
        fc = self.calculate_schroeder_frequency()
        modal_overlap = self.calculate_modal_overlap(frequency)
        modal_density = self.calculate_modal_density(frequency)
        
        if frequency < fc / 2:
            behavior = "Strong modal"
            treatment = "Bass traps"
        elif frequency < fc:
            behavior = "Transitional (modal dominant)"
            treatment = "Thick absorbers + bass traps"
        elif frequency < fc * 2:
            behavior = "Transitional (diffuse dominant)"
            treatment = "Broadband absorbers"
        else:
            behavior = "Diffuse field"
            treatment = "Absorbers + Diffusers"
        
        return {
            "frequency": frequency,
            "schroeder_frequency": round(fc, 1),
            "modal_overlap": round(modal_overlap, 2),
            "modal_density": modal_density,
            "is_modal": frequency < fc,
            "behavior": behavior,
            "recommended_treatment": treatment
        }


def calculate_schroeder_from_dimensions(length: float, width: float, height: float,
                                        t60: float = 0.3, use_metric: bool = True) -> SchroederAnalysis:
    """
    Convenience function to calculate Schroeder frequency from room dimensions.
    """
    volume = length * width * height
    analyzer = SchroederAnalyzer(volume, t60, use_metric)
    return analyzer.analyze()

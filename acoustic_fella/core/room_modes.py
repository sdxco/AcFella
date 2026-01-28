"""
Room Mode Calculator - Calculates standing waves in rectangular rooms

Implements the Rayleigh equation for room modes:
f = (c/2) * sqrt((p/L)² + (q/W)² + (r/H)²)

Where:
- c = speed of sound (344 m/s or 1130 ft/s)
- L, W, H = room length, width, height
- p, q, r = mode integers (0, 1, 2, 3...)

Mode Types:
- Axial: Only one dimension (most energetic, -3dB per reflection)
- Tangential: Two dimensions (-6dB per reflection) 
- Oblique: Three dimensions (-9dB per reflection)
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Dict
from enum import Enum


class ModeType(Enum):
    AXIAL = "axial"
    TANGENTIAL = "tangential"
    OBLIQUE = "oblique"


@dataclass
class RoomMode:
    """Represents a single room mode"""
    frequency: float
    p: int  # Length mode number
    q: int  # Width mode number
    r: int  # Height mode number
    mode_type: ModeType
    wavelength: float
    
    @property
    def mode_string(self) -> str:
        return f"({self.p},{self.q},{self.r})"
    
    @property
    def energy_factor(self) -> float:
        """Relative energy factor based on mode type"""
        if self.mode_type == ModeType.AXIAL:
            return 1.0
        elif self.mode_type == ModeType.TANGENTIAL:
            return 0.5
        else:
            return 0.25


class RoomModeCalculator:
    """
    Calculates room modes for rectangular rooms using the Rayleigh equation.
    
    Based on Master Handbook of Acoustics, Chapter on Room Modes.
    """
    
    # Speed of sound at 20°C
    SPEED_OF_SOUND_METRIC = 344.0  # m/s
    SPEED_OF_SOUND_IMPERIAL = 1130.0  # ft/s
    
    def __init__(self, length: float, width: float, height: float, 
                 use_metric: bool = True, temperature_c: float = 20.0):
        """
        Initialize room mode calculator.
        
        Args:
            length: Room length (longest dimension)
            width: Room width
            height: Room height
            use_metric: If True, dimensions are in meters; otherwise feet
            temperature_c: Temperature in Celsius for speed of sound correction
        """
        self.length = length
        self.width = width
        self.height = height
        self.use_metric = use_metric
        self.temperature_c = temperature_c
        
        # Calculate speed of sound with temperature correction
        # c = 331.3 + 0.606 * T (m/s)
        if use_metric:
            self.speed_of_sound = 331.3 + 0.606 * temperature_c
        else:
            self.speed_of_sound = (331.3 + 0.606 * temperature_c) * 3.281
        
        self._modes: List[RoomMode] = []
        
    @property
    def volume(self) -> float:
        """Room volume in cubic meters or cubic feet"""
        return self.length * self.width * self.height
    
    @property
    def surface_area(self) -> float:
        """Total surface area of the room"""
        return 2 * (
            self.length * self.width +
            self.length * self.height +
            self.width * self.height
        )
    
    def calculate_mode_frequency(self, p: int, q: int, r: int) -> float:
        """
        Calculate the frequency of a specific room mode using Rayleigh equation.
        
        f = (c/2) * sqrt((p/L)² + (q/W)² + (r/H)²)
        """
        term = np.sqrt(
            (p / self.length) ** 2 +
            (q / self.width) ** 2 +
            (r / self.height) ** 2
        )
        return (self.speed_of_sound / 2) * term
    
    def get_mode_type(self, p: int, q: int, r: int) -> ModeType:
        """Determine the type of mode based on active dimensions"""
        active_dims = sum([p > 0, q > 0, r > 0])
        
        if active_dims == 1:
            return ModeType.AXIAL
        elif active_dims == 2:
            return ModeType.TANGENTIAL
        else:
            return ModeType.OBLIQUE
    
    def calculate_all_modes(self, max_frequency: float = 300.0, 
                           max_mode_order: int = 10) -> List[RoomMode]:
        """
        Calculate all room modes up to a maximum frequency.
        
        Args:
            max_frequency: Maximum frequency to calculate (Hz)
            max_mode_order: Maximum mode order (p, q, r values)
            
        Returns:
            List of RoomMode objects sorted by frequency
        """
        modes = []
        
        for p in range(max_mode_order + 1):
            for q in range(max_mode_order + 1):
                for r in range(max_mode_order + 1):
                    # Skip the (0,0,0) mode
                    if p == 0 and q == 0 and r == 0:
                        continue
                    
                    freq = self.calculate_mode_frequency(p, q, r)
                    
                    if freq <= max_frequency:
                        mode_type = self.get_mode_type(p, q, r)
                        wavelength = self.speed_of_sound / freq
                        
                        mode = RoomMode(
                            frequency=freq,
                            p=p,
                            q=q,
                            r=r,
                            mode_type=mode_type,
                            wavelength=wavelength
                        )
                        modes.append(mode)
        
        # Sort by frequency
        modes.sort(key=lambda m: m.frequency)
        self._modes = modes
        return modes
    
    def get_axial_modes(self, max_frequency: float = 300.0) -> List[RoomMode]:
        """Get only axial modes (most energetic)"""
        if not self._modes:
            self.calculate_all_modes(max_frequency)
        return [m for m in self._modes if m.mode_type == ModeType.AXIAL]
    
    def get_modes_in_band(self, low_freq: float, high_freq: float) -> List[RoomMode]:
        """Get modes within a frequency band"""
        if not self._modes:
            self.calculate_all_modes(max(high_freq, 300.0))
        return [m for m in self._modes if low_freq <= m.frequency <= high_freq]
    
    def analyze_mode_spacing(self) -> Dict[str, any]:
        """
        Analyze mode spacing to identify potential problems.
        
        Returns analysis including:
        - Average mode spacing
        - Minimum spacing (potential problem areas)
        - Mode clusters (multiple modes within 5Hz)
        """
        if not self._modes:
            self.calculate_all_modes()
        
        if len(self._modes) < 2:
            return {"error": "Not enough modes to analyze"}
        
        # Calculate spacings
        frequencies = [m.frequency for m in self._modes]
        spacings = np.diff(frequencies)
        
        # Find clusters (modes within 5Hz of each other)
        clusters = []
        i = 0
        while i < len(frequencies):
            cluster = [frequencies[i]]
            j = i + 1
            while j < len(frequencies) and frequencies[j] - frequencies[i] <= 5:
                cluster.append(frequencies[j])
                j += 1
            if len(cluster) > 1:
                clusters.append({
                    "frequencies": cluster,
                    "center": np.mean(cluster),
                    "count": len(cluster)
                })
            i = j if j > i + 1 else i + 1
        
        return {
            "total_modes": len(self._modes),
            "average_spacing": float(np.mean(spacings)),
            "min_spacing": float(np.min(spacings)),
            "max_spacing": float(np.max(spacings)),
            "std_spacing": float(np.std(spacings)),
            "clusters": clusters,
            "problem_frequencies": [c["center"] for c in clusters if c["count"] >= 3]
        }
    
    def bonello_analysis(self, max_frequency: float = 200.0) -> Dict[str, any]:
        """
        Perform Bonello criterion analysis.
        
        Divides spectrum into 1/3 octave bands and checks if mode count
        increases monotonically. A good room should have increasing or
        constant mode count in each subsequent band.
        
        Returns:
            Dict with band analysis and pass/fail status
        """
        if not self._modes:
            self.calculate_all_modes(max_frequency)
        
        # 1/3 octave band center frequencies (20 Hz to 200 Hz)
        band_centers = [20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200]
        
        # Calculate band edges (1/3 octave: multiply/divide by 2^(1/6))
        factor = 2 ** (1/6)
        
        band_analysis = []
        previous_count = 0
        passes_criterion = True
        problem_bands = []
        
        for center in band_centers:
            if center > max_frequency:
                break
                
            low = center / factor
            high = center * factor
            
            modes_in_band = self.get_modes_in_band(low, high)
            count = len(modes_in_band)
            
            # Check Bonello criterion
            if count < previous_count and previous_count > 0:
                passes_criterion = False
                problem_bands.append(center)
            
            band_analysis.append({
                "center_frequency": center,
                "low_frequency": round(low, 1),
                "high_frequency": round(high, 1),
                "mode_count": count,
                "modes": [m.mode_string for m in modes_in_band],
                "passes": count >= previous_count or previous_count == 0
            })
            
            previous_count = count
        
        return {
            "passes_bonello": passes_criterion,
            "band_analysis": band_analysis,
            "problem_bands": problem_bands,
            "recommendation": (
                "Room dimensions are acceptable" if passes_criterion
                else f"Consider adjusting room dimensions. Problem bands at {problem_bands} Hz"
            )
        }
    
    def get_optimal_ratios(self) -> Dict[str, any]:
        """
        Calculate room ratios and compare to optimal ratios.
        
        Optimal ratios from various sources:
        - Bolt (1946): 1 : 1.28 : 1.54
        - IEC: 1 : 1.4 : 1.9
        - Sepmeyer: 1 : 1.14 : 1.39
        - Louden: 1 : 1.4 : 1.9
        """
        dims = sorted([self.height, self.width, self.length])
        
        # Normalize to smallest dimension
        ratios = [d / dims[0] for d in dims]
        
        # Optimal ratios
        optimal_sets = {
            "Bolt": [1.0, 1.28, 1.54],
            "IEC": [1.0, 1.4, 1.9],
            "Sepmeyer A": [1.0, 1.14, 1.39],
            "Sepmeyer B": [1.0, 1.28, 1.54],
            "Louden": [1.0, 1.4, 1.9]
        }
        
        # Calculate deviation from each optimal set
        comparisons = {}
        for name, optimal in optimal_sets.items():
            deviation = np.sqrt(sum((r - o) ** 2 for r, o in zip(ratios, optimal)))
            comparisons[name] = {
                "optimal_ratios": optimal,
                "deviation": round(deviation, 3),
                "match_quality": "Excellent" if deviation < 0.1 else
                                "Good" if deviation < 0.2 else
                                "Fair" if deviation < 0.3 else "Poor"
            }
        
        best_match = min(comparisons.items(), key=lambda x: x[1]["deviation"])
        
        return {
            "current_ratios": [round(r, 2) for r in ratios],
            "dimensions_sorted": dims,
            "comparisons": comparisons,
            "best_match": best_match[0],
            "best_deviation": best_match[1]["deviation"]
        }
    
    def get_problematic_frequencies(self, threshold_db: float = 3.0) -> List[Dict]:
        """
        Identify frequencies that are likely to be problematic.
        
        Looks for:
        - Mode clusters (multiple modes within 5Hz)
        - Strong axial modes at common bass frequencies
        - Modes near common musical frequencies
        """
        if not self._modes:
            self.calculate_all_modes()
        
        problems = []
        
        # Common musical bass notes (Hz)
        bass_notes = {
            "E1": 41.2, "F1": 43.7, "G1": 49.0, "A1": 55.0,
            "B1": 61.7, "C2": 65.4, "D2": 73.4, "E2": 82.4,
            "F2": 87.3, "G2": 98.0, "A2": 110.0, "B2": 123.5
        }
        
        for mode in self._modes:
            if mode.mode_type == ModeType.AXIAL:
                # Check if near a musical note
                for note, freq in bass_notes.items():
                    if abs(mode.frequency - freq) < 3:  # Within 3Hz
                        problems.append({
                            "frequency": mode.frequency,
                            "mode": mode.mode_string,
                            "type": "axial_near_note",
                            "note": note,
                            "severity": "high",
                            "recommendation": f"Strong mode at {mode.frequency:.1f}Hz near {note}. Bass trap recommended."
                        })
        
        # Check for clusters
        analysis = self.analyze_mode_spacing()
        for cluster in analysis.get("clusters", []):
            if cluster["count"] >= 2:
                problems.append({
                    "frequency": cluster["center"],
                    "modes": cluster["frequencies"],
                    "type": "cluster",
                    "severity": "high" if cluster["count"] >= 3 else "medium",
                    "recommendation": f"Mode cluster at {cluster['center']:.1f}Hz. Strong bass buildup expected."
                })
        
        return problems
    
    def generate_report(self) -> Dict[str, any]:
        """Generate a comprehensive room mode analysis report"""
        self.calculate_all_modes()
        
        return {
            "room_info": {
                "length": self.length,
                "width": self.width,
                "height": self.height,
                "volume": round(self.volume, 2),
                "surface_area": round(self.surface_area, 2),
                "unit": "meters" if self.use_metric else "feet"
            },
            "modes": {
                "total": len(self._modes),
                "axial": len([m for m in self._modes if m.mode_type == ModeType.AXIAL]),
                "tangential": len([m for m in self._modes if m.mode_type == ModeType.TANGENTIAL]),
                "oblique": len([m for m in self._modes if m.mode_type == ModeType.OBLIQUE]),
                "first_10": [{"freq": m.frequency, "mode": m.mode_string, "type": m.mode_type.value} 
                            for m in self._modes[:10]]
            },
            "ratio_analysis": self.get_optimal_ratios(),
            "bonello": self.bonello_analysis(),
            "spacing_analysis": self.analyze_mode_spacing(),
            "problems": self.get_problematic_frequencies()
        }

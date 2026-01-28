"""
Reverberation Time Analyzer

Analyzes reverberation time from impulse responses using
Schroeder's backwards integration method.

Supports:
- T60 (full decay time)
- T30 (extrapolated from -5dB to -35dB)
- T20 (extrapolated from -5dB to -25dB)
- EDT (Early Decay Time, first 10dB)

Target for studio control rooms: 200-300ms (0.2-0.3s)
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from scipy import signal
from scipy.ndimage import uniform_filter1d


@dataclass
class DecayAnalysis:
    """Results of decay time analysis"""
    t60: float
    t30: float
    t20: float
    edt: float
    frequency: Optional[int]
    decay_curve: np.ndarray
    time_axis: np.ndarray
    
    def meets_target(self, target_low: float = 0.2, target_high: float = 0.3) -> bool:
        """Check if T60 is within target range"""
        return target_low <= self.t60 <= target_high
    
    @property
    def quality_rating(self) -> str:
        """Rate the decay characteristics"""
        if 0.2 <= self.t60 <= 0.3:
            return "Excellent for studio work"
        elif 0.15 <= self.t60 < 0.2:
            return "Slightly dead - may sound dry"
        elif 0.3 < self.t60 <= 0.4:
            return "Slightly live - acceptable"
        elif self.t60 < 0.15:
            return "Too dead - add diffusion"
        else:
            return "Too live - add absorption"


class ReverberationAnalyzer:
    """
    Analyzes reverberation characteristics from impulse responses.
    
    Uses Schroeder's backwards integration for accurate decay measurement.
    Based on Master Handbook of Acoustics and Springer Handbook of Acoustics.
    """
    
    def __init__(self, sample_rate: int = 48000):
        """
        Initialize analyzer.
        
        Args:
            sample_rate: Sample rate of impulse response (Hz)
        """
        self.sample_rate = sample_rate
        
    def schroeder_integration(self, impulse_response: np.ndarray) -> np.ndarray:
        """
        Perform Schroeder backwards integration.
        
        The decay curve is computed as:
        E(t) = ∫_t^∞ p²(τ)dτ
        
        In practice, we integrate from the end backwards.
        """
        # Square the impulse response
        squared = impulse_response ** 2
        
        # Backwards cumulative sum (reverse, cumsum, reverse)
        backwards_sum = np.cumsum(squared[::-1])[::-1]
        
        # Convert to dB (avoid log(0))
        backwards_sum = np.maximum(backwards_sum, 1e-20)
        decay_db = 10 * np.log10(backwards_sum / backwards_sum[0])
        
        return decay_db
    
    def calculate_decay_time(self, decay_curve: np.ndarray,
                            start_db: float, end_db: float) -> float:
        """
        Calculate decay time between two dB levels.
        
        Args:
            decay_curve: Decay curve in dB
            start_db: Starting level (e.g., -5)
            end_db: Ending level (e.g., -35)
            
        Returns:
            Decay time in seconds
        """
        # Find indices where curve crosses start and end levels
        try:
            start_idx = np.where(decay_curve <= start_db)[0][0]
            end_idx = np.where(decay_curve <= end_db)[0][0]
        except IndexError:
            # Decay doesn't reach target level
            return float('nan')
        
        # Calculate time
        samples = end_idx - start_idx
        time = samples / self.sample_rate
        
        # Extrapolate to 60dB decay
        db_range = abs(end_db - start_db)
        t60 = time * (60 / db_range)
        
        return t60
    
    def analyze_impulse_response(self, impulse_response: np.ndarray) -> DecayAnalysis:
        """
        Perform complete decay analysis on an impulse response.
        
        Args:
            impulse_response: Impulse response array
            
        Returns:
            DecayAnalysis with all decay parameters
        """
        # Normalize
        ir = impulse_response / np.max(np.abs(impulse_response))
        
        # Get decay curve
        decay_curve = self.schroeder_integration(ir)
        
        # Create time axis
        time_axis = np.arange(len(ir)) / self.sample_rate
        
        # Calculate decay times
        t30 = self.calculate_decay_time(decay_curve, -5, -35)
        t20 = self.calculate_decay_time(decay_curve, -5, -25)
        edt = self.calculate_decay_time(decay_curve, 0, -10) * 6  # Extrapolate to 60dB
        
        # T60 is typically T30 (most reliable in small rooms)
        t60 = t30
        
        return DecayAnalysis(
            t60=t60,
            t30=t30,
            t20=t20,
            edt=edt,
            frequency=None,
            decay_curve=decay_curve,
            time_axis=time_axis
        )
    
    def analyze_by_frequency_bands(self, impulse_response: np.ndarray,
                                   frequencies: List[int] = None) -> Dict[int, DecayAnalysis]:
        """
        Analyze decay time in octave bands.
        
        Args:
            impulse_response: Full bandwidth impulse response
            frequencies: Center frequencies to analyze
            
        Returns:
            Dict mapping frequency to DecayAnalysis
        """
        if frequencies is None:
            frequencies = [63, 125, 250, 500, 1000, 2000, 4000, 8000]
        
        results = {}
        
        for freq in frequencies:
            # Design bandpass filter for this octave
            low = freq / np.sqrt(2)
            high = freq * np.sqrt(2)
            
            # Normalize to Nyquist
            nyquist = self.sample_rate / 2
            low_norm = max(low / nyquist, 0.001)
            high_norm = min(high / nyquist, 0.999)
            
            try:
                # Design butterworth bandpass
                b, a = signal.butter(4, [low_norm, high_norm], btype='band')
                
                # Filter the IR
                filtered_ir = signal.filtfilt(b, a, impulse_response)
                
                # Analyze this band
                analysis = self.analyze_impulse_response(filtered_ir)
                analysis.frequency = freq
                results[freq] = analysis
                
            except Exception as e:
                # Skip bands that can't be analyzed
                continue
        
        return results
    
    def calculate_clarity(self, impulse_response: np.ndarray,
                         early_time_ms: float = 80) -> float:
        """
        Calculate clarity index (C80 or C50).
        
        C = 10 * log10(E_early / E_late)
        
        Args:
            impulse_response: Impulse response
            early_time_ms: Early time limit in ms (80 for music, 50 for speech)
            
        Returns:
            Clarity index in dB
        """
        early_samples = int((early_time_ms / 1000) * self.sample_rate)
        
        # Find direct sound (max value)
        direct_idx = np.argmax(np.abs(impulse_response))
        
        # Calculate early and late energy
        early_end = direct_idx + early_samples
        
        early_energy = np.sum(impulse_response[:early_end] ** 2)
        late_energy = np.sum(impulse_response[early_end:] ** 2)
        
        if late_energy < 1e-20:
            return float('inf')
        
        return 10 * np.log10(early_energy / late_energy)
    
    def calculate_definition(self, impulse_response: np.ndarray,
                            early_time_ms: float = 50) -> float:
        """
        Calculate definition (D50).
        
        D = E_early / E_total
        
        Returns value between 0 and 1.
        """
        early_samples = int((early_time_ms / 1000) * self.sample_rate)
        direct_idx = np.argmax(np.abs(impulse_response))
        early_end = direct_idx + early_samples
        
        early_energy = np.sum(impulse_response[:early_end] ** 2)
        total_energy = np.sum(impulse_response ** 2)
        
        if total_energy < 1e-20:
            return 1.0
        
        return early_energy / total_energy
    
    def analyze_frequency_response_decay(self, 
                                        frequency_response: np.ndarray,
                                        frequencies: np.ndarray) -> Dict:
        """
        Estimate decay characteristics from frequency response measurements.
        
        This is a rough approximation when only FR is available.
        Based on relationship between modal Q and decay time.
        """
        # Find peaks in low frequency region (modes)
        low_freq_mask = frequencies < 300
        low_freq_response = frequency_response[low_freq_mask]
        low_frequencies = frequencies[low_freq_mask]
        
        # Find peaks
        peaks, properties = signal.find_peaks(low_freq_response, 
                                              height=-20, prominence=3)
        
        if len(peaks) == 0:
            return {"error": "No clear modes detected"}
        
        # Estimate Q factor and decay from peak width
        mode_analysis = []
        for peak_idx in peaks:
            freq = low_frequencies[peak_idx]
            # Estimate -3dB width
            peak_height = low_freq_response[peak_idx]
            target = peak_height - 3
            
            # Find bandwidth
            left = peak_idx
            right = peak_idx
            while left > 0 and low_freq_response[left] > target:
                left -= 1
            while right < len(low_freq_response) - 1 and low_freq_response[right] > target:
                right += 1
            
            if right > left:
                bandwidth = low_frequencies[right] - low_frequencies[left]
                q = freq / bandwidth if bandwidth > 0 else 10
                
                # Rough T60 estimate: T60 ≈ 2.2 / bandwidth
                estimated_t60 = 2.2 / bandwidth if bandwidth > 0 else 1.0
                
                mode_analysis.append({
                    "frequency": freq,
                    "q_factor": q,
                    "estimated_decay": min(estimated_t60, 2.0)
                })
        
        return {
            "modes_detected": len(peaks),
            "mode_analysis": mode_analysis,
            "average_modal_decay": np.mean([m["estimated_decay"] for m in mode_analysis])
        }


class RoomTargets:
    """Target reverberation times for different room purposes"""
    
    TARGETS = {
        "mixing_mastering": {
            "t60_min": 0.2,
            "t60_max": 0.3,
            "edt_ratio": 1.0,  # EDT should equal T60
            "description": "Dead room for accurate monitoring"
        },
        "music_production": {
            "t60_min": 0.25,
            "t60_max": 0.35,
            "edt_ratio": 1.0,
            "description": "Controlled but slightly live"
        },
        "vocal_recording": {
            "t60_min": 0.2,
            "t60_max": 0.4,
            "edt_ratio": 0.9,
            "description": "Clean with minimal reflections"
        },
        "live_recording": {
            "t60_min": 0.4,
            "t60_max": 0.8,
            "edt_ratio": 1.1,
            "description": "Natural ambience for instruments"
        },
        "podcast_voiceover": {
            "t60_min": 0.15,
            "t60_max": 0.25,
            "edt_ratio": 1.0,
            "description": "Very dead for speech clarity"
        }
    }
    
    @classmethod
    def get_target(cls, room_type: str) -> Dict:
        """Get target parameters for room type"""
        return cls.TARGETS.get(room_type, cls.TARGETS["mixing_mastering"])
    
    @classmethod
    def evaluate(cls, measured_t60: float, room_type: str) -> Dict:
        """Evaluate measured T60 against target"""
        target = cls.get_target(room_type)
        
        in_range = target["t60_min"] <= measured_t60 <= target["t60_max"]
        
        if in_range:
            status = "optimal"
            action = "No changes needed"
        elif measured_t60 < target["t60_min"]:
            status = "too_dead"
            deficit = target["t60_min"] - measured_t60
            action = f"Room is {deficit*1000:.0f}ms too dead. Consider adding diffusion or removing absorption."
        else:
            status = "too_live"
            excess = measured_t60 - target["t60_max"]
            action = f"Room is {excess*1000:.0f}ms too live. Add absorption treatment."
        
        return {
            "measured": measured_t60,
            "target_min": target["t60_min"],
            "target_max": target["t60_max"],
            "target_mid": (target["t60_min"] + target["t60_max"]) / 2,
            "in_range": in_range,
            "status": status,
            "action": action
        }

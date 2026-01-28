"""
REW (Room EQ Wizard) File Parser

Parses various REW export formats:
- .txt (frequency response, impulse response)
- .mdat (measurement data)
- Impulse response WAV files

Extracts:
- Frequency response data
- Phase response
- Impulse response
- Step response
- Waterfall data (if available)
"""

import numpy as np
import re
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import struct


@dataclass
class FrequencyResponseData:
    """Parsed frequency response data"""
    frequencies: np.ndarray
    magnitudes: np.ndarray  # in dB SPL
    phases: Optional[np.ndarray] = None
    
    @property
    def frequency_range(self) -> Tuple[float, float]:
        return (float(self.frequencies[0]), float(self.frequencies[-1]))
    
    def get_magnitude_at(self, frequency: float) -> float:
        """Get magnitude at specific frequency (interpolated)"""
        return float(np.interp(frequency, self.frequencies, self.magnitudes))
    
    def get_average_level(self, low: float = 20, high: float = 20000) -> float:
        """Get average level in frequency range"""
        mask = (self.frequencies >= low) & (self.frequencies <= high)
        return float(np.mean(self.magnitudes[mask]))
    
    def get_deviation(self, low: float = 20, high: float = 20000,
                     target: Optional[float] = None) -> float:
        """Calculate standard deviation from flat (or target)"""
        mask = (self.frequencies >= low) & (self.frequencies <= high)
        data = self.magnitudes[mask]
        if target is None:
            target = np.mean(data)
        return float(np.std(data - target))


@dataclass
class ImpulseResponseData:
    """Parsed impulse response data"""
    samples: np.ndarray
    sample_rate: int
    
    @property
    def duration(self) -> float:
        """Duration in seconds"""
        return len(self.samples) / self.sample_rate
    
    @property
    def time_axis(self) -> np.ndarray:
        """Time axis in seconds"""
        return np.arange(len(self.samples)) / self.sample_rate


@dataclass 
class REWMeasurement:
    """Complete REW measurement data"""
    name: str
    frequency_response: Optional[FrequencyResponseData] = None
    impulse_response: Optional[ImpulseResponseData] = None
    metadata: Dict = field(default_factory=dict)
    
    # Analysis results (populated by analyzers)
    t60: Optional[Dict[int, float]] = None
    modal_analysis: Optional[Dict] = None


class REWParser:
    """
    Parser for Room EQ Wizard export files.
    
    Supports:
    - Frequency response text exports
    - Impulse response text exports
    - WAV impulse responses
    """
    
    def __init__(self):
        self.supported_formats = ['.txt', '.mdat', '.wav', '.frd']
    
    def parse_file(self, filepath: Union[str, Path]) -> REWMeasurement:
        """
        Parse a REW export file.
        
        Args:
            filepath: Path to the REW export file
            
        Returns:
            REWMeasurement with parsed data
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        suffix = filepath.suffix.lower()
        
        if suffix == '.txt':
            return self._parse_txt_file(filepath)
        elif suffix == '.frd':
            return self._parse_frd_file(filepath)
        elif suffix == '.wav':
            return self._parse_wav_file(filepath)
        elif suffix == '.mdat':
            return self._parse_mdat_file(filepath)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")
    
    def _parse_txt_file(self, filepath: Path) -> REWMeasurement:
        """Parse REW text export file"""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Determine file type from content
        if 'IR Windows' in content or 'impulse' in content.lower():
            return self._parse_ir_txt(content, filepath.stem)
        else:
            return self._parse_fr_txt(content, filepath.stem)
    
    def _parse_fr_txt(self, content: str, name: str) -> REWMeasurement:
        """Parse frequency response text data"""
        lines = content.strip().split('\n')
        
        frequencies = []
        magnitudes = []
        phases = []
        metadata = {}
        
        in_data = False
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Parse metadata (lines with *)
            if line.startswith('*'):
                # Extract metadata
                if ':' in line:
                    key, value = line[1:].split(':', 1)
                    metadata[key.strip()] = value.strip()
                continue
            
            # Check for data start markers
            if 'freq' in line.lower() or 'hz' in line.lower():
                in_data = True
                continue
            
            # Try to parse numeric data
            try:
                parts = line.replace(',', ' ').split()
                
                if len(parts) >= 2:
                    freq = float(parts[0])
                    mag = float(parts[1])
                    
                    # Skip if frequency seems invalid
                    if freq < 1 or freq > 100000:
                        continue
                    
                    frequencies.append(freq)
                    magnitudes.append(mag)
                    
                    if len(parts) >= 3:
                        phases.append(float(parts[2]))
                    
                    in_data = True
                    
            except (ValueError, IndexError):
                continue
        
        if len(frequencies) == 0:
            raise ValueError("No frequency response data found in file")
        
        fr_data = FrequencyResponseData(
            frequencies=np.array(frequencies),
            magnitudes=np.array(magnitudes),
            phases=np.array(phases) if phases else None
        )
        
        return REWMeasurement(
            name=name,
            frequency_response=fr_data,
            metadata=metadata
        )
    
    def _parse_ir_txt(self, content: str, name: str) -> REWMeasurement:
        """Parse impulse response text data"""
        lines = content.strip().split('\n')
        
        samples = []
        sample_rate = 48000  # Default
        metadata = {}
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
            
            # Parse metadata
            if line.startswith('*'):
                if 'rate' in line.lower():
                    # Try to extract sample rate
                    match = re.search(r'(\d+)', line)
                    if match:
                        sample_rate = int(match.group(1))
                continue
            
            # Parse sample data
            try:
                parts = line.split()
                if len(parts) >= 1:
                    # Time, Sample format or just sample values
                    if len(parts) == 2:
                        samples.append(float(parts[1]))
                    else:
                        samples.append(float(parts[0]))
            except ValueError:
                continue
        
        if len(samples) == 0:
            raise ValueError("No impulse response data found in file")
        
        ir_data = ImpulseResponseData(
            samples=np.array(samples),
            sample_rate=sample_rate
        )
        
        return REWMeasurement(
            name=name,
            impulse_response=ir_data,
            metadata=metadata
        )
    
    def _parse_frd_file(self, filepath: Path) -> REWMeasurement:
        """Parse FRD (frequency response data) file format"""
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        frequencies = []
        magnitudes = []
        phases = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('*'):
                continue
            
            try:
                parts = line.split()
                if len(parts) >= 2:
                    frequencies.append(float(parts[0]))
                    magnitudes.append(float(parts[1]))
                    if len(parts) >= 3:
                        phases.append(float(parts[2]))
            except ValueError:
                continue
        
        fr_data = FrequencyResponseData(
            frequencies=np.array(frequencies),
            magnitudes=np.array(magnitudes),
            phases=np.array(phases) if phases else None
        )
        
        return REWMeasurement(
            name=filepath.stem,
            frequency_response=fr_data
        )
    
    def _parse_wav_file(self, filepath: Path) -> REWMeasurement:
        """Parse WAV impulse response file"""
        try:
            from scipy.io import wavfile
            sample_rate, data = wavfile.read(filepath)
        except ImportError:
            # Fallback to manual WAV parsing
            sample_rate, data = self._read_wav_manual(filepath)
        
        # Convert to mono if stereo
        if len(data.shape) > 1:
            data = np.mean(data, axis=1)
        
        # Normalize
        if data.dtype == np.int16:
            data = data.astype(np.float64) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float64) / 2147483648.0
        
        ir_data = ImpulseResponseData(
            samples=data,
            sample_rate=sample_rate
        )
        
        return REWMeasurement(
            name=filepath.stem,
            impulse_response=ir_data
        )
    
    def _read_wav_manual(self, filepath: Path) -> Tuple[int, np.ndarray]:
        """Manual WAV file reader (no scipy dependency)"""
        with open(filepath, 'rb') as f:
            # RIFF header
            riff = f.read(4)
            if riff != b'RIFF':
                raise ValueError("Not a valid WAV file")
            
            size = struct.unpack('<I', f.read(4))[0]
            wave = f.read(4)
            if wave != b'WAVE':
                raise ValueError("Not a valid WAV file")
            
            # Find fmt chunk
            sample_rate = 44100
            bits_per_sample = 16
            num_channels = 1
            
            while True:
                chunk_id = f.read(4)
                if len(chunk_id) < 4:
                    break
                    
                chunk_size = struct.unpack('<I', f.read(4))[0]
                
                if chunk_id == b'fmt ':
                    audio_format = struct.unpack('<H', f.read(2))[0]
                    num_channels = struct.unpack('<H', f.read(2))[0]
                    sample_rate = struct.unpack('<I', f.read(4))[0]
                    byte_rate = struct.unpack('<I', f.read(4))[0]
                    block_align = struct.unpack('<H', f.read(2))[0]
                    bits_per_sample = struct.unpack('<H', f.read(2))[0]
                    
                    # Skip any extra format bytes
                    if chunk_size > 16:
                        f.read(chunk_size - 16)
                        
                elif chunk_id == b'data':
                    # Read audio data
                    if bits_per_sample == 16:
                        data = np.frombuffer(f.read(chunk_size), dtype=np.int16)
                    elif bits_per_sample == 24:
                        raw = f.read(chunk_size)
                        # 24-bit to 32-bit conversion
                        data = np.zeros(chunk_size // 3, dtype=np.int32)
                        for i in range(len(data)):
                            bytes_3 = raw[i*3:(i+1)*3]
                            val = struct.unpack('<i', bytes_3 + (b'\x00' if bytes_3[2] < 128 else b'\xff'))[0]
                            data[i] = val
                    elif bits_per_sample == 32:
                        data = np.frombuffer(f.read(chunk_size), dtype=np.float32)
                    else:
                        raise ValueError(f"Unsupported bit depth: {bits_per_sample}")
                    
                    if num_channels > 1:
                        data = data.reshape(-1, num_channels)
                    
                    return sample_rate, data
                else:
                    # Skip unknown chunk
                    f.read(chunk_size)
            
            raise ValueError("No data chunk found in WAV file")
    
    def _parse_mdat_file(self, filepath: Path) -> REWMeasurement:
        """
        Parse REW .mdat file format.
        
        MDAT is a binary format containing measurement data.
        This is a simplified parser for the most common data.
        """
        with open(filepath, 'rb') as f:
            # Read header
            header = f.read(256)
            
            # Try to identify structure
            # MDAT files can vary in structure
            
            # For now, attempt to extract frequency response
            # This is a basic implementation - full MDAT parsing would require
            # reverse-engineering the format specification
            
            # Read remaining data
            data = f.read()
        
        # Return empty measurement with note about format
        return REWMeasurement(
            name=filepath.stem,
            metadata={
                "format": "mdat",
                "note": "MDAT parsing is limited. Export as TXT from REW for full support."
            }
        )


class REWAnalyzer:
    """
    Analyzes REW measurements for room acoustics assessment.
    """
    
    def __init__(self, measurement: REWMeasurement):
        self.measurement = measurement
        self.fr = measurement.frequency_response
        self.ir = measurement.impulse_response
    
    def analyze_frequency_response(self, target_level: Optional[float] = None) -> Dict:
        """
        Analyze frequency response for flatness and problem areas.
        """
        if self.fr is None:
            return {"error": "No frequency response data available"}
        
        if target_level is None:
            # Use average as target
            target_level = self.fr.get_average_level(200, 4000)
        
        # Calculate deviations in different bands
        bass = self.fr.magnitudes[(self.fr.frequencies >= 20) & (self.fr.frequencies < 200)]
        mids = self.fr.magnitudes[(self.fr.frequencies >= 200) & (self.fr.frequencies < 2000)]
        highs = self.fr.magnitudes[(self.fr.frequencies >= 2000) & (self.fr.frequencies <= 20000)]
        
        # Find peaks and dips
        peaks = self._find_peaks_dips(True)
        dips = self._find_peaks_dips(False)
        
        # Overall flatness score (±3dB target)
        full_range = self.fr.magnitudes[
            (self.fr.frequencies >= 20) & (self.fr.frequencies <= 20000)
        ]
        within_3db = np.sum(np.abs(full_range - target_level) <= 3) / len(full_range) * 100
        
        return {
            "target_level": round(target_level, 1),
            "bass_average": round(np.mean(bass), 1) if len(bass) > 0 else None,
            "bass_deviation": round(np.std(bass), 1) if len(bass) > 0 else None,
            "mids_average": round(np.mean(mids), 1) if len(mids) > 0 else None,
            "mids_deviation": round(np.std(mids), 1) if len(mids) > 0 else None,
            "highs_average": round(np.mean(highs), 1) if len(highs) > 0 else None,
            "highs_deviation": round(np.std(highs), 1) if len(highs) > 0 else None,
            "overall_deviation": round(self.fr.get_deviation(20, 20000, target_level), 1),
            "flatness_score": round(within_3db, 1),
            "peaks": peaks[:5],  # Top 5
            "dips": dips[:5],
            "meets_target": within_3db >= 80,
            "recommendation": self._get_fr_recommendation(bass, mids, target_level, peaks, dips)
        }
    
    def _find_peaks_dips(self, find_peaks: bool = True) -> List[Dict]:
        """Find significant peaks or dips in response"""
        if self.fr is None:
            return []
        
        from scipy import signal as sig
        
        # Only look at bass region for modal problems
        mask = self.fr.frequencies < 500
        freqs = self.fr.frequencies[mask]
        mags = self.fr.magnitudes[mask]
        
        if find_peaks:
            indices, props = sig.find_peaks(mags, prominence=3, height=-10)
        else:
            indices, props = sig.find_peaks(-mags, prominence=3, height=-80)
        
        results = []
        for i, idx in enumerate(indices):
            results.append({
                "frequency": round(freqs[idx], 1),
                "level": round(mags[idx], 1),
                "prominence": round(props["prominences"][i], 1) if "prominences" in props else None,
                "type": "peak" if find_peaks else "dip"
            })
        
        # Sort by prominence
        results.sort(key=lambda x: x.get("prominence", 0) or 0, reverse=True)
        return results
    
    def _get_fr_recommendation(self, bass: np.ndarray, mids: np.ndarray,
                               target: float, peaks: List, dips: List) -> str:
        """Generate recommendation based on FR analysis"""
        recommendations = []
        
        # Check bass level
        if len(bass) > 0:
            bass_avg = np.mean(bass)
            if bass_avg > target + 3:
                recommendations.append(
                    f"Bass is {bass_avg - target:.1f}dB hot. Add bass trapping."
                )
            elif bass_avg < target - 3:
                recommendations.append(
                    f"Bass is {target - bass_avg:.1f}dB weak. Check speaker placement or boundary reinforcement."
                )
        
        # Check for severe peaks
        for peak in peaks[:3]:
            if peak.get("prominence", 0) > 6:
                recommendations.append(
                    f"Severe peak at {peak['frequency']:.0f}Hz (+{peak['prominence']:.1f}dB). "
                    f"Likely a room mode - add targeted bass trap."
                )
        
        # Check for severe dips
        for dip in dips[:3]:
            if dip.get("prominence", 0) > 6:
                recommendations.append(
                    f"Severe dip at {dip['frequency']:.0f}Hz (-{dip['prominence']:.1f}dB). "
                    f"Likely a null point - consider moving listening position."
                )
        
        if not recommendations:
            recommendations.append("Frequency response is relatively good. Fine-tune with measurement-based EQ.")
        
        return " | ".join(recommendations)
    
    def identify_modal_problems(self, room_modes: List[float] = None) -> Dict:
        """
        Identify where room modes are causing problems.
        
        Args:
            room_modes: List of calculated room mode frequencies
            
        Returns:
            Analysis of modal problems
        """
        if self.fr is None:
            return {"error": "No frequency response data available"}
        
        problems = []
        
        # Look for peaks in bass region
        peaks = self._find_peaks_dips(True)
        
        for peak in peaks:
            if peak["frequency"] < 300:
                # Check if this matches a room mode
                matches_mode = False
                matching_mode = None
                
                if room_modes:
                    for mode in room_modes:
                        if abs(peak["frequency"] - mode) < 5:  # Within 5Hz
                            matches_mode = True
                            matching_mode = mode
                            break
                
                problems.append({
                    "frequency": peak["frequency"],
                    "excess_db": peak.get("prominence", 0),
                    "matches_mode": matches_mode,
                    "matching_mode": matching_mode,
                    "severity": "high" if peak.get("prominence", 0) > 6 else "medium",
                    "treatment": f"Bass trap tuned to {peak['frequency']:.0f}Hz"
                })
        
        return {
            "modal_problems": problems,
            "total_problems": len(problems),
            "worst_frequency": problems[0]["frequency"] if problems else None,
            "requires_treatment": len(problems) > 0
        }


def parse_rew_export(filepath: Union[str, Path]) -> REWMeasurement:
    """
    Convenience function to parse a REW export file.
    
    Args:
        filepath: Path to REW export file
        
    Returns:
        REWMeasurement with parsed data
    """
    parser = REWParser()
    return parser.parse_file(filepath)

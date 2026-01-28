"""
Speaker and Listener Placement Optimizer

Calculates optimal positions for speakers and listening position
based on room dimensions and acoustic principles.

Key principles:
- 38% rule for listening position (avoiding 50% null point)
- Equilateral triangle for stereo imaging
- SBIR (Speaker Boundary Interference Response) management
- Symmetry for stereo balance
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class Position3D:
    """3D position in room coordinates"""
    x: float  # Left-right (0 = left wall)
    y: float  # Front-back (0 = front wall)
    z: float  # Up-down (0 = floor)
    
    def to_dict(self) -> Dict:
        return {"x": self.x, "y": self.y, "z": self.z}
    
    def distance_to(self, other: 'Position3D') -> float:
        return np.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )


@dataclass
class SpeakerPlacement:
    """Complete speaker placement recommendation"""
    left_speaker: Position3D
    right_speaker: Position3D
    listening_position: Position3D
    speaker_angle: float  # Degrees
    speaker_distance: float  # Distance from listener to each speaker
    toe_in_angle: float  # Degrees to angle speakers inward
    notes: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "left_speaker": self.left_speaker.to_dict(),
            "right_speaker": self.right_speaker.to_dict(),
            "listening_position": self.listening_position.to_dict(),
            "speaker_angle": self.speaker_angle,
            "speaker_distance": self.speaker_distance,
            "toe_in_angle": self.toe_in_angle,
            "notes": self.notes
        }


class SpeakerPlacementOptimizer:
    """
    Optimizes speaker and listener placement for room acoustics.
    
    Based on principles from:
    - Master Handbook of Acoustics
    - Industry best practices for studio monitoring
    """
    
    # Standard ear height when seated
    EAR_HEIGHT_METRIC = 1.2  # meters
    EAR_HEIGHT_IMPERIAL = 3.9  # feet
    
    def __init__(self, length: float, width: float, height: float,
                 use_metric: bool = True):
        """
        Initialize optimizer.
        
        Args:
            length: Room length (front to back)
            width: Room width (left to right)
            height: Room height
            use_metric: True for meters, False for feet
        """
        self.length = length
        self.width = width
        self.height = height
        self.use_metric = use_metric
        self.unit = "m" if use_metric else "ft"
        
        self.ear_height = self.EAR_HEIGHT_METRIC if use_metric else self.EAR_HEIGHT_IMPERIAL
    
    def calculate_optimal_placement(self, 
                                   speaker_type: str = "nearfield",
                                   preference: str = "balanced") -> SpeakerPlacement:
        """
        Calculate optimal speaker and listener placement.
        
        Args:
            speaker_type: "nearfield", "midfield", or "main"
            preference: "balanced", "imaging", or "bass"
            
        Returns:
            SpeakerPlacement with all positions
        """
        notes = []
        
        # 1. Calculate listening position (38% rule as starting point)
        listener_y = self.length * 0.38
        listener_x = self.width / 2  # Centered
        
        # Adjust based on preference
        if preference == "imaging":
            # Move listener forward for better direct sound
            listener_y = min(listener_y, self.length * 0.35)
            notes.append("Listener moved forward for enhanced imaging.")
        elif preference == "bass":
            # Check for null points and adjust
            # Avoid 50%, 33%, 25% points
            null_points = [0.5, 0.33, 0.25, 0.67, 0.75]
            for null in null_points:
                null_y = self.length * null
                if abs(listener_y - null_y) < self.length * 0.05:
                    # Too close to null point, adjust
                    listener_y = self.length * 0.38  # Reset to 38%
                    notes.append(f"Avoided null point at {int(null*100)}% of room length.")
                    break
        
        listening_position = Position3D(listener_x, listener_y, self.ear_height)
        
        # 2. Calculate speaker positions
        speaker_distance = self._calculate_speaker_distance(speaker_type)
        
        # Distance from front wall
        speaker_y = self._calculate_speaker_front_distance(speaker_type)
        
        # Create equilateral triangle (60° stereo angle)
        # For equilateral: speaker spread = speaker distance to listener
        speaker_spread = speaker_distance
        
        # Limit speaker spread by room width
        max_spread = self.width * 0.8  # Leave 10% on each side
        if speaker_spread > max_spread:
            speaker_spread = max_spread
            notes.append(f"Speaker spread limited by room width to {speaker_spread:.2f}{self.unit}")
        
        # Minimum distance from side walls
        min_side_distance = 0.6 if self.use_metric else 2.0  # 60cm / 2ft minimum
        
        # Calculate speaker X positions (symmetric about center)
        speaker_left_x = listener_x - (speaker_spread / 2)
        speaker_right_x = listener_x + (speaker_spread / 2)
        
        # Enforce minimum side wall distance
        if speaker_left_x < min_side_distance:
            speaker_left_x = min_side_distance
            speaker_right_x = self.width - min_side_distance
            speaker_spread = speaker_right_x - speaker_left_x
            notes.append(f"Speakers moved away from side walls (min {min_side_distance}{self.unit})")
        
        left_speaker = Position3D(speaker_left_x, speaker_y, self.ear_height)
        right_speaker = Position3D(speaker_right_x, speaker_y, self.ear_height)
        
        # 3. Calculate actual angle and distance
        actual_distance = listening_position.distance_to(left_speaker)
        
        # Stereo angle calculation
        half_spread = speaker_spread / 2
        distance_to_plane = listener_y - speaker_y
        stereo_half_angle = np.degrees(np.arctan(half_spread / distance_to_plane))
        stereo_angle = stereo_half_angle * 2
        
        # 4. Calculate toe-in
        toe_in = self._calculate_toe_in(stereo_angle, speaker_type)
        
        # 5. SBIR analysis
        sbir_notes = self._analyze_sbir(left_speaker, right_speaker)
        notes.extend(sbir_notes)
        
        # 6. Additional notes
        if stereo_angle < 55:
            notes.append(f"Stereo angle ({stereo_angle:.0f}°) is narrow. May reduce stereo width.")
        elif stereo_angle > 65:
            notes.append(f"Stereo angle ({stereo_angle:.0f}°) is wide. May create hole-in-middle.")
        else:
            notes.append(f"Stereo angle ({stereo_angle:.0f}°) is optimal for equilateral triangle.")
        
        return SpeakerPlacement(
            left_speaker=left_speaker,
            right_speaker=right_speaker,
            listening_position=listening_position,
            speaker_angle=round(stereo_angle, 1),
            speaker_distance=round(actual_distance, 2),
            toe_in_angle=round(toe_in, 1),
            notes=notes
        )
    
    def _calculate_speaker_distance(self, speaker_type: str) -> float:
        """Calculate optimal distance from listener to speakers"""
        if speaker_type == "nearfield":
            # Nearfields: 1-2 meters / 3-6 feet
            return 1.5 if self.use_metric else 4.5
        elif speaker_type == "midfield":
            # Midfields: 2-4 meters / 6-12 feet
            return 2.5 if self.use_metric else 8.0
        else:  # main monitors
            return 3.5 if self.use_metric else 11.0
    
    def _calculate_speaker_front_distance(self, speaker_type: str) -> float:
        """Calculate distance from front wall to speakers"""
        # Avoid SBIR issues - keep speakers away from front wall
        # Rule of thumb: 1/4 wavelength of crossover frequency
        
        if speaker_type == "nearfield":
            # Small speakers - can be closer
            return max(0.6 if self.use_metric else 2.0, self.length * 0.1)
        elif speaker_type == "midfield":
            return max(0.9 if self.use_metric else 3.0, self.length * 0.12)
        else:
            return max(1.2 if self.use_metric else 4.0, self.length * 0.15)
    
    def _calculate_toe_in(self, stereo_angle: float, speaker_type: str) -> float:
        """Calculate toe-in angle for speakers"""
        # Toe-in aims speakers toward or behind listening position
        
        if speaker_type == "nearfield":
            # Nearfields often benefit from toe-in toward listener
            if stereo_angle > 60:
                return stereo_angle / 2 - 5  # Less toe-in for wide angle
            else:
                return stereo_angle / 2  # Point directly at listener
        else:
            # Midfield/mains may benefit from less toe-in
            return stereo_angle / 2 - 10
    
    def _analyze_sbir(self, left: Position3D, right: Position3D) -> List[str]:
        """
        Analyze Speaker Boundary Interference Response issues.
        
        SBIR occurs when reflected sound from boundaries interferes
        with direct sound, causing comb filtering.
        """
        notes = []
        c = 344 if self.use_metric else 1130  # Speed of sound
        
        # Check distances to boundaries
        distances = {
            "front wall": left.y,
            "side wall (left)": left.x,
            "side wall (right)": self.width - right.x,
            "floor": left.z,
            "ceiling": self.height - left.z
        }
        
        for boundary, distance in distances.items():
            # Calculate SBIR cancellation frequency
            # Cancellation at f = c / (4 * distance)
            if distance > 0:
                sbir_freq = c / (4 * distance)
                
                if 40 < sbir_freq < 300:  # Problem range
                    notes.append(
                        f"SBIR cancellation at {sbir_freq:.0f}Hz from {boundary} "
                        f"(distance: {distance:.2f}{self.unit}). Consider bass trap or repositioning."
                    )
        
        return notes
    
    def calculate_subwoofer_positions(self, num_subs: int = 1) -> List[Dict]:
        """
        Calculate optimal subwoofer positions.
        
        Options:
        - Single sub: Front wall center or corner
        - Two subs: Front wall, 1/4 and 3/4 width
        - Four subs: Midpoint of each wall
        """
        positions = []
        
        if num_subs == 1:
            # Single sub - front wall center or corner
            positions.append({
                "position": Position3D(self.width / 2, 0.1, 0).to_dict(),
                "name": "Front wall center",
                "notes": "Good for general use. May excite all length modes."
            })
            positions.append({
                "position": Position3D(0.1, 0.1, 0).to_dict(),
                "name": "Front left corner",
                "notes": "Maximum bass output. May have uneven response."
            })
            
        elif num_subs == 2:
            # Two subs - 1/4 and 3/4 width on front wall
            positions.append({
                "position": Position3D(self.width * 0.25, 0.1, 0).to_dict(),
                "name": "Front wall, 1/4 width",
                "notes": "Dual sub configuration for smoother response."
            })
            positions.append({
                "position": Position3D(self.width * 0.75, 0.1, 0).to_dict(),
                "name": "Front wall, 3/4 width",
                "notes": "Pair with first sub for width mode cancellation."
            })
            
        elif num_subs >= 4:
            # Four subs - DBA (Double Bass Array) configuration
            positions = [
                {
                    "position": Position3D(self.width / 2, 0.1, self.height * 0.25).to_dict(),
                    "name": "Front wall, lower",
                    "notes": "DBA front array - lower position"
                },
                {
                    "position": Position3D(self.width / 2, 0.1, self.height * 0.75).to_dict(),
                    "name": "Front wall, upper",
                    "notes": "DBA front array - upper position"
                },
                {
                    "position": Position3D(self.width / 2, self.length - 0.1, self.height * 0.25).to_dict(),
                    "name": "Rear wall, lower (cancellation)",
                    "notes": "DBA rear array - inverted polarity, delayed"
                },
                {
                    "position": Position3D(self.width / 2, self.length - 0.1, self.height * 0.75).to_dict(),
                    "name": "Rear wall, upper (cancellation)",
                    "notes": "DBA rear array - inverted polarity, delayed"
                }
            ]
        
        return positions
    
    def generate_placement_report(self, speaker_type: str = "nearfield") -> Dict:
        """Generate comprehensive placement report"""
        placement = self.calculate_optimal_placement(speaker_type)
        sub_positions = self.calculate_subwoofer_positions(1)
        
        return {
            "room_dimensions": {
                "length": self.length,
                "width": self.width,
                "height": self.height,
                "unit": self.unit
            },
            "speaker_type": speaker_type,
            "placement": placement.to_dict(),
            "subwoofer_options": sub_positions,
            "setup_instructions": [
                f"1. Mark listening position at ({placement.listening_position.x:.2f}, "
                f"{placement.listening_position.y:.2f}){self.unit} from front-left corner.",
                f"2. Place left speaker at ({placement.left_speaker.x:.2f}, "
                f"{placement.left_speaker.y:.2f}){self.unit}.",
                f"3. Place right speaker at ({placement.right_speaker.x:.2f}, "
                f"{placement.right_speaker.y:.2f}){self.unit}.",
                f"4. Angle speakers {placement.toe_in_angle:.0f}° inward (toe-in).",
                f"5. Set speaker height so tweeters are at ear level "
                f"({self.ear_height:.2f}{self.unit}).",
                "6. Verify symmetry by measuring distance from each speaker to listener.",
                "7. Run measurement sweep to verify frequency response."
            ],
            "common_mistakes": [
                "Placing speakers in corners (excites all modes)",
                "Listening position at 50% of room length (null point)",
                "Asymmetric placement (uneven stereo image)",
                "Speakers too close to walls (SBIR issues)",
                "Tweeters not at ear level (comb filtering)"
            ]
        }


def quick_speaker_placement(length: float, width: float, height: float,
                           use_metric: bool = True) -> Dict:
    """
    Quick speaker placement calculation.
    
    Returns simplified placement guide.
    """
    optimizer = SpeakerPlacementOptimizer(length, width, height, use_metric)
    placement = optimizer.calculate_optimal_placement()
    
    unit = "m" if use_metric else "ft"
    
    return {
        "listening_position": {
            "from_front_wall": f"{placement.listening_position.y:.2f} {unit}",
            "description": "Center of room width, 38% of room length"
        },
        "speaker_positions": {
            "left": f"({placement.left_speaker.x:.2f}, {placement.left_speaker.y:.2f}) {unit}",
            "right": f"({placement.right_speaker.x:.2f}, {placement.right_speaker.y:.2f}) {unit}",
            "distance_from_front": f"{placement.left_speaker.y:.2f} {unit}"
        },
        "angles": {
            "stereo_angle": f"{placement.speaker_angle:.0f}°",
            "toe_in": f"{placement.toe_in_angle:.0f}°"
        },
        "distance_to_speakers": f"{placement.speaker_distance:.2f} {unit}"
    }

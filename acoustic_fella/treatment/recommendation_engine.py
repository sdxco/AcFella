"""
Treatment Recommendation Engine

Generates comprehensive acoustic treatment plans based on:
- Room dimensions and modes
- REW measurements
- Target application (mixing, mastering, recording, etc.)

Outputs:
- Bass trap specifications and placement
- Absorber panel specifications and placement
- Diffuser specifications and placement
- Priority order for treatment
- Bill of materials
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

from ..core.room_modes import RoomModeCalculator, ModeType
from ..core.absorption import AbsorptionCalculator, TREATMENT_COEFFICIENTS
from ..core.schroeder import SchroederAnalyzer


class TreatmentType(Enum):
    BASS_TRAP_POROUS = "bass_trap_porous"
    BASS_TRAP_MEMBRANE = "bass_trap_membrane"
    BASS_TRAP_HELMHOLTZ = "bass_trap_helmholtz"
    BROADBAND_ABSORBER = "broadband_absorber"
    DIFFUSER_QRD = "diffuser_qrd"
    DIFFUSER_SKYLINE = "diffuser_skyline"
    CLOUD_ABSORBER = "cloud_absorber"


class TreatmentLocation(Enum):
    FRONT_WALL = "front_wall"
    REAR_WALL = "rear_wall"
    LEFT_WALL = "left_wall"
    RIGHT_WALL = "right_wall"
    CEILING = "ceiling"
    FLOOR_WALL_CORNER = "floor_wall_corner"
    CEILING_WALL_CORNER = "ceiling_wall_corner"
    TRI_CORNER = "tri_corner"
    FIRST_REFLECTION_LEFT = "first_reflection_left"
    FIRST_REFLECTION_RIGHT = "first_reflection_right"
    FIRST_REFLECTION_CEILING = "first_reflection_ceiling"


@dataclass
class TreatmentItem:
    """Single treatment item specification"""
    treatment_type: TreatmentType
    location: TreatmentLocation
    position: Dict[str, float]  # x, y, z coordinates
    dimensions: Dict[str, float]  # width, height, depth
    material: str
    target_frequencies: List[float]
    priority: int  # 1 = highest
    estimated_cost: Optional[float] = None
    construction_notes: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "type": self.treatment_type.value,
            "location": self.location.value,
            "position": self.position,
            "dimensions": self.dimensions,
            "material": self.material,
            "target_frequencies": self.target_frequencies,
            "priority": self.priority,
            "estimated_cost": self.estimated_cost,
            "construction_notes": self.construction_notes
        }


@dataclass
class TreatmentPlan:
    """Complete treatment plan for a room"""
    room_type: str
    target_t60: float
    items: List[TreatmentItem] = field(default_factory=list)
    total_absorption_added: Dict[int, float] = field(default_factory=dict)
    estimated_final_t60: float = 0.0
    estimated_total_cost: float = 0.0
    notes: List[str] = field(default_factory=list)
    
    def add_item(self, item: TreatmentItem):
        self.items.append(item)
        if item.estimated_cost:
            self.estimated_total_cost += item.estimated_cost
    
    def get_by_priority(self) -> List[TreatmentItem]:
        """Get items sorted by priority"""
        return sorted(self.items, key=lambda x: x.priority)
    
    def get_by_location(self, location: TreatmentLocation) -> List[TreatmentItem]:
        """Get items for a specific location"""
        return [item for item in self.items if item.location == location]
    
    def get_bill_of_materials(self) -> Dict:
        """Generate bill of materials"""
        materials = {}
        for item in self.items:
            key = item.material
            if key not in materials:
                materials[key] = {
                    "material": key,
                    "total_area": 0,
                    "count": 0,
                    "items": []
                }
            
            area = item.dimensions.get("width", 0) * item.dimensions.get("height", 0)
            materials[key]["total_area"] += area
            materials[key]["count"] += 1
            materials[key]["items"].append({
                "location": item.location.value,
                "dimensions": item.dimensions
            })
        
        return materials


class TreatmentRecommendationEngine:
    """
    Generates acoustic treatment recommendations based on room analysis.
    
    Uses principles from Master Handbook of Acoustics and industry best practices.
    """
    
    def __init__(self, length: float, width: float, height: float,
                 use_metric: bool = True, room_type: str = "mixing_mastering"):
        """
        Initialize treatment engine.
        
        Args:
            length, width, height: Room dimensions
            use_metric: True for meters, False for feet
            room_type: Target application
        """
        self.length = length
        self.width = width
        self.height = height
        self.use_metric = use_metric
        self.room_type = room_type
        self.unit = "m" if use_metric else "ft"
        
        # Target parameters by room type
        self.targets = {
            "mixing_mastering": {"t60": 0.25, "tolerance": 3},
            "music_production": {"t60": 0.30, "tolerance": 3},
            "vocal_recording": {"t60": 0.20, "tolerance": 2},
            "podcast": {"t60": 0.20, "tolerance": 2},
            "live_recording": {"t60": 0.50, "tolerance": 4}
        }
        
        # Initialize calculators
        self.mode_calc = RoomModeCalculator(length, width, height, use_metric)
        self.absorption_calc = AbsorptionCalculator(length, width, height, use_metric)
        self.schroeder = SchroederAnalyzer(length * width * height, 
                                           self.targets[room_type]["t60"], use_metric)
    
    def generate_treatment_plan(self, current_t60: Optional[float] = None,
                               measured_modes: Optional[List[float]] = None) -> TreatmentPlan:
        """
        Generate a complete treatment plan.
        
        Args:
            current_t60: Measured T60 if available
            measured_modes: Problem frequencies from measurements
            
        Returns:
            Complete TreatmentPlan
        """
        target = self.targets[self.room_type]
        plan = TreatmentPlan(
            room_type=self.room_type,
            target_t60=target["t60"]
        )
        
        # 1. Calculate room modes
        modes = self.mode_calc.calculate_all_modes()
        axial_modes = self.mode_calc.get_axial_modes()
        
        # 2. Get Schroeder frequency
        schroeder_analysis = self.schroeder.analyze()
        
        # 3. Analyze absorption requirements
        absorption = self.absorption_calc.analyze(target["t60"])
        
        # 4. Generate bass trap recommendations
        self._add_bass_traps(plan, axial_modes, schroeder_analysis)
        
        # 5. Generate first reflection treatment
        self._add_first_reflection_treatment(plan)
        
        # 6. Generate rear wall treatment
        self._add_rear_wall_treatment(plan, schroeder_analysis)
        
        # 7. Add ceiling cloud if needed
        self._add_ceiling_treatment(plan)
        
        # 8. Add additional absorption if needed
        if current_t60 and current_t60 > target["t60"]:
            self._add_supplemental_absorption(plan, current_t60, target["t60"])
        
        # 9. Add notes
        self._add_plan_notes(plan, schroeder_analysis, absorption)
        
        return plan
    
    def _add_bass_traps(self, plan: TreatmentPlan, axial_modes: List,
                       schroeder_analysis) -> None:
        """Add bass trap recommendations to plan"""
        # Priority 1: Tri-corners (where 3 surfaces meet)
        # These are the most effective positions for bass traps
        
        tri_corners = [
            {"name": "Front-Left-Floor", "x": 0, "y": 0, "z": 0},
            {"name": "Front-Right-Floor", "x": self.width, "y": 0, "z": 0},
            {"name": "Front-Left-Ceiling", "x": 0, "y": 0, "z": self.height},
            {"name": "Front-Right-Ceiling", "x": self.width, "y": 0, "z": self.height},
            {"name": "Rear-Left-Floor", "x": 0, "y": self.length, "z": 0},
            {"name": "Rear-Right-Floor", "x": self.width, "y": self.length, "z": 0},
            {"name": "Rear-Left-Ceiling", "x": 0, "y": self.length, "z": self.height},
            {"name": "Rear-Right-Ceiling", "x": self.width, "y": self.length, "z": self.height}
        ]
        
        # Determine trap size based on lowest mode
        lowest_mode = axial_modes[0].frequency if axial_modes else 50
        wavelength = 344 / lowest_mode if self.use_metric else 1130 / lowest_mode
        
        # Trap depth should be at least 1/4 wavelength for effectiveness
        # Practical limit: 30-60cm (1-2ft)
        trap_depth = min(wavelength / 4, 0.6 if self.use_metric else 2.0)
        trap_depth = max(trap_depth, 0.3 if self.use_metric else 1.0)
        
        # Add corner bass traps (highest priority)
        for i, corner in enumerate(tri_corners[:4]):  # Front 4 corners
            plan.add_item(TreatmentItem(
                treatment_type=TreatmentType.BASS_TRAP_POROUS,
                location=TreatmentLocation.TRI_CORNER,
                position={"x": corner["x"], "y": corner["y"], "z": corner["z"]},
                dimensions={
                    "width": trap_depth,
                    "height": self.height if "Floor" in corner["name"] else trap_depth,
                    "depth": trap_depth
                },
                material="4\" (100mm) Rockwool/Fiberglass, density 48-96 kg/m³",
                target_frequencies=[m.frequency for m in axial_modes[:3]],
                priority=1,
                construction_notes=(
                    f"Corner bass trap at {corner['name']}. "
                    f"Use rigid fiberglass or mineral wool. "
                    f"Frame with wood and cover with acoustically transparent fabric."
                )
            ))
        
        # Add rear corner traps
        for i, corner in enumerate(tri_corners[4:]):
            plan.add_item(TreatmentItem(
                treatment_type=TreatmentType.BASS_TRAP_POROUS,
                location=TreatmentLocation.TRI_CORNER,
                position={"x": corner["x"], "y": corner["y"], "z": corner["z"]},
                dimensions={
                    "width": trap_depth,
                    "height": self.height if "Floor" in corner["name"] else trap_depth,
                    "depth": trap_depth
                },
                material="4\" (100mm) Rockwool/Fiberglass, density 48-96 kg/m³",
                target_frequencies=[m.frequency for m in axial_modes[:3]],
                priority=2,
                construction_notes=(
                    f"Corner bass trap at {corner['name']}. "
                    f"Extend floor-to-ceiling for maximum effect."
                )
            ))
    
    def _add_first_reflection_treatment(self, plan: TreatmentPlan) -> None:
        """Add first reflection point treatment"""
        # Calculate speaker and listener positions first
        speaker_distance = self.width * 0.3  # Speakers 30% from side walls
        listener_y = self.length * 0.38  # 38% rule for listener
        speaker_y = self.length * 0.15  # Speakers at 15% of length
        
        # Mirror point calculation for side walls
        # First reflection hits wall at average of speaker and listener positions
        reflection_y = (speaker_y + listener_y) / 2
        
        # Side wall reflections
        for side, x_pos in [("left", 0), ("right", self.width)]:
            location = (TreatmentLocation.FIRST_REFLECTION_LEFT if side == "left" 
                       else TreatmentLocation.FIRST_REFLECTION_RIGHT)
            
            plan.add_item(TreatmentItem(
                treatment_type=TreatmentType.BROADBAND_ABSORBER,
                location=location,
                position={
                    "x": x_pos,
                    "y": reflection_y,
                    "z": self.height * 0.4  # Ear height when seated
                },
                dimensions={
                    "width": 1.2 if self.use_metric else 4.0,  # 1.2m or 4ft wide
                    "height": 1.2 if self.use_metric else 4.0,
                    "depth": 0.1 if self.use_metric else 0.33  # 4 inches
                },
                material="4\" (100mm) Rockwool/Fiberglass panel",
                target_frequencies=[250, 500, 1000, 2000, 4000],
                priority=2,
                construction_notes=(
                    f"First reflection panel on {side} wall. "
                    f"Center at ear height (1.2m/4ft from floor). "
                    f"Use mirror trick: sit at listening position, have someone "
                    f"slide mirror along wall - panel goes where you see the speaker."
                )
            ))
        
        # Ceiling reflection
        plan.add_item(TreatmentItem(
            treatment_type=TreatmentType.CLOUD_ABSORBER,
            location=TreatmentLocation.FIRST_REFLECTION_CEILING,
            position={
                "x": self.width / 2,
                "y": reflection_y,
                "z": self.height
            },
            dimensions={
                "width": 1.8 if self.use_metric else 6.0,
                "height": 1.2 if self.use_metric else 4.0,
                "depth": 0.15 if self.use_metric else 0.5
            },
            material="6\" (150mm) Rockwool/Fiberglass cloud panel",
            target_frequencies=[125, 250, 500, 1000, 2000],
            priority=2,
            construction_notes=(
                "Ceiling cloud above listening position. "
                "Suspend 6-12 inches below ceiling for air gap. "
                "Larger is better - extend from speaker plane to behind listener."
            )
        ))
    
    def _add_rear_wall_treatment(self, plan: TreatmentPlan, 
                                schroeder_analysis) -> None:
        """Add rear wall treatment (diffusion or absorption)"""
        # Check minimum distance for diffusion
        listener_y = self.length * 0.38
        distance_to_rear = self.length - listener_y
        min_diffuser_distance = self.schroeder.calculate_minimum_distance_for_diffuser()
        
        if distance_to_rear >= min_diffuser_distance:
            # Room is large enough for diffusion
            plan.add_item(TreatmentItem(
                treatment_type=TreatmentType.DIFFUSER_QRD,
                location=TreatmentLocation.REAR_WALL,
                position={
                    "x": self.width / 2,
                    "y": self.length,
                    "z": self.height * 0.4
                },
                dimensions={
                    "width": self.width * 0.6,  # Cover 60% of wall
                    "height": 1.2 if self.use_metric else 4.0,
                    "depth": 0.15 if self.use_metric else 0.5
                },
                material="QRD (Quadratic Residue Diffuser) - Prime 7 or 13",
                target_frequencies=[500, 1000, 2000, 4000],
                priority=3,
                construction_notes=(
                    "Quadratic Residue Diffuser on rear wall. "
                    "Center at ear height. Can be built from wood strips "
                    "at calculated depths. See construction guide for well depths."
                )
            ))
        else:
            # Room too small - use absorption instead
            plan.add_item(TreatmentItem(
                treatment_type=TreatmentType.BROADBAND_ABSORBER,
                location=TreatmentLocation.REAR_WALL,
                position={
                    "x": self.width / 2,
                    "y": self.length,
                    "z": self.height * 0.4
                },
                dimensions={
                    "width": self.width * 0.6,
                    "height": 1.2 if self.use_metric else 4.0,
                    "depth": 0.1 if self.use_metric else 0.33
                },
                material="4\" (100mm) Rockwool/Fiberglass panel",
                target_frequencies=[250, 500, 1000, 2000, 4000],
                priority=3,
                construction_notes=(
                    "Absorption panel on rear wall. "
                    f"Room is too small for diffusion (need {min_diffuser_distance:.1f}{self.unit} "
                    f"minimum distance, have {distance_to_rear:.1f}{self.unit})."
                )
            ))
            
            plan.notes.append(
                f"Room length of {self.length}{self.unit} is below minimum for rear wall diffusion. "
                f"Using absorption instead."
            )
    
    def _add_ceiling_treatment(self, plan: TreatmentPlan) -> None:
        """Add additional ceiling treatment if needed"""
        # The cloud handles first reflections, but we may need more coverage
        # for flutter echo control
        pass  # Cloud added in first reflection section is typically sufficient
    
    def _add_supplemental_absorption(self, plan: TreatmentPlan,
                                    current_t60: float, target_t60: float) -> None:
        """Add additional absorption to meet T60 target"""
        # Calculate additional absorption needed
        additional_absorption = self.absorption_calc.analyze(target_t60)
        
        if any(v > 0 for v in additional_absorption.missing_absorption.values()):
            plan.notes.append(
                f"Current T60 ({current_t60:.2f}s) exceeds target ({target_t60:.2f}s). "
                f"Additional absorption panels recommended."
            )
    
    def _add_plan_notes(self, plan: TreatmentPlan, schroeder_analysis,
                       absorption) -> None:
        """Add helpful notes to the plan"""
        # Schroeder frequency note
        plan.notes.append(
            f"Schroeder frequency: {schroeder_analysis.schroeder_frequency:.0f}Hz. "
            f"Bass traps are critical below this frequency."
        )
        
        # Room ratio assessment
        ratio_analysis = self.mode_calc.get_optimal_ratios()
        plan.notes.append(
            f"Room ratios: {ratio_analysis['current_ratios']}. "
            f"Best match: {ratio_analysis['best_match']} "
            f"({ratio_analysis['comparisons'][ratio_analysis['best_match']]['match_quality']})."
        )
        
        # Bonello criterion
        bonello = self.mode_calc.bonello_analysis()
        if bonello["passes_bonello"]:
            plan.notes.append("Room passes Bonello criterion for modal distribution.")
        else:
            plan.notes.append(
                f"Room fails Bonello criterion. Problem bands: {bonello['problem_bands']}Hz. "
                f"Extra bass trapping needed at these frequencies."
            )
        
        # Priority guidance
        plan.notes.append(
            "Installation priority: 1) Corner bass traps, 2) First reflection panels, "
            "3) Rear wall treatment, 4) Additional absorption as needed."
        )
        
        # Measurement recommendation
        plan.notes.append(
            "Measure with REW after each treatment stage to verify improvements "
            "and adjust placement as needed."
        )


def generate_quick_recommendations(length: float, width: float, height: float,
                                  room_type: str = "mixing_mastering",
                                  use_metric: bool = True) -> Dict:
    """
    Generate quick treatment recommendations without full plan.
    
    Returns simplified recommendations for common cases.
    """
    engine = TreatmentRecommendationEngine(length, width, height, use_metric, room_type)
    mode_calc = engine.mode_calc
    
    # Quick analysis
    modes = mode_calc.calculate_all_modes(200)
    axial_modes = mode_calc.get_axial_modes(200)
    bonello = mode_calc.bonello_analysis()
    ratios = mode_calc.get_optimal_ratios()
    
    schroeder = engine.schroeder.analyze()
    
    recommendations = {
        "room_info": {
            "dimensions": f"{length} x {width} x {height} {'m' if use_metric else 'ft'}",
            "volume": length * width * height,
            "schroeder_frequency": round(schroeder.schroeder_frequency, 0)
        },
        "modal_analysis": {
            "first_mode": round(axial_modes[0].frequency, 1) if axial_modes else None,
            "total_modes_under_200hz": len([m for m in modes if m.frequency < 200]),
            "passes_bonello": bonello["passes_bonello"],
            "ratio_quality": ratios["comparisons"][ratios["best_match"]]["match_quality"]
        },
        "quick_recommendations": [
            {
                "item": "Corner Bass Traps",
                "quantity": "4-8 (all corners)",
                "minimum_depth": "4 inches (100mm)",
                "priority": "Critical"
            },
            {
                "item": "First Reflection Panels",
                "quantity": "3 (2 side walls + 1 ceiling)",
                "size": "2ft x 4ft (60cm x 120cm)",
                "priority": "High"
            },
            {
                "item": "Rear Wall Treatment",
                "type": "Diffuser" if (length - length * 0.38) > 3 else "Absorber",
                "priority": "Medium"
            }
        ],
        "problem_frequencies": [round(m.frequency, 0) for m in axial_modes[:5]]
    }
    
    return recommendations

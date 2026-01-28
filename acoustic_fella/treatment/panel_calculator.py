"""
DIY Panel Construction Calculator

Generates construction specifications for:
- Porous absorbers (fiberglass/rockwool panels)
- Bass traps (corner traps, membrane absorbers)
- Helmholtz resonators (tuned bass traps)
- QRD diffusers (quadratic residue diffusers)
- Skyline diffusers

Based on acoustic principles from:
- Master Handbook of Acoustics
- Springer Handbook of Acoustics
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class AbsorberType(Enum):
    POROUS = "porous"
    MEMBRANE = "membrane"
    HELMHOLTZ = "helmholtz"
    HYBRID = "hybrid"


@dataclass
class MaterialSpec:
    """Specification for absorber material"""
    name: str
    density_kg_m3: float
    flow_resistivity: float  # Pa·s/m² (rayls/m)
    typical_thickness_mm: List[int]
    cost_per_sqm: Optional[float] = None
    
    @property
    def density_lb_ft3(self) -> float:
        return self.density_kg_m3 * 0.0624


# Common absorber materials - optimal densities 48-96 kg/m³
MATERIALS = {
    "rockwool_60": MaterialSpec(
        name="Rockwool Safe'n'Sound (60 kg/m³)",
        density_kg_m3=60,
        flow_resistivity=20000,
        typical_thickness_mm=[50, 100, 150]
    ),
    "owens_703": MaterialSpec(
        name="Owens Corning 703 (48 kg/m³)",
        density_kg_m3=48,
        flow_resistivity=15000,
        typical_thickness_mm=[50, 100, 150]
    ),
    "owens_705": MaterialSpec(
        name="Owens Corning 705 (96 kg/m³)",
        density_kg_m3=96,
        flow_resistivity=40000,
        typical_thickness_mm=[50, 100]
    ),
    "rockwool_80": MaterialSpec(
        name="Rockwool RW5 (80 kg/m³)",
        density_kg_m3=80,
        flow_resistivity=30000,
        typical_thickness_mm=[50, 100, 150]
    )
}


@dataclass
class PanelSpec:
    """Construction specification for a single panel"""
    type: str
    width_mm: float
    height_mm: float
    depth_mm: float
    material: str
    air_gap_mm: float
    frame_material: str
    facing: str
    target_frequencies: List[int]
    absorption_coefficients: Dict[int, float]
    construction_steps: List[str]
    materials_list: List[Dict]
    estimated_cost: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type,
            "dimensions": {
                "width": self.width_mm,
                "height": self.height_mm,
                "depth": self.depth_mm,
                "air_gap": self.air_gap_mm
            },
            "materials": {
                "absorber": self.material,
                "frame": self.frame_material,
                "facing": self.facing
            },
            "target_frequencies": self.target_frequencies,
            "absorption_coefficients": self.absorption_coefficients,
            "construction_steps": self.construction_steps,
            "materials_list": self.materials_list,
            "estimated_cost": self.estimated_cost
        }


class PanelConstructionCalculator:
    """
    Calculates construction specifications for DIY acoustic panels.
    """
    
    SPEED_OF_SOUND = 344  # m/s
    
    def __init__(self, use_metric: bool = True):
        self.use_metric = use_metric
        self.unit_length = "mm" if use_metric else "inches"
        
    def design_broadband_absorber(self, 
                                  width: float = 600,
                                  height: float = 1200,
                                  target_low_freq: int = 250,
                                  material_key: str = "owens_703") -> PanelSpec:
        """
        Design a broadband porous absorber panel (600x1200mm standard).
        
        Based on quarter-wavelength absorption principle:
        - Effective absorption starts at f = c/(4d) where d = depth + air gap
        - Optimal density: 48-96 kg/m³ (OC703, OC705, Rockwool 60-80)
        - Standard depth: 100mm with 100mm air gap = λ/4 @ 430Hz
        
        Args:
            width, height: Panel dimensions in mm (standard 600x1200mm)
            target_low_freq: Lowest frequency for effective absorption (Hz)
            material_key: Material from MATERIALS dict (48-96 kg/m³)
            
        Returns:
            Complete panel specification with frequency response
        """
        material = MATERIALS.get(material_key, MATERIALS["owens_703"])
        
        # Calculate required depth for target frequency
        # Quarter wavelength rule: d = λ/4 = c/(4f)
        # Include air gap in calculation: d_total = d_material + d_air
        wavelength_mm = (self.SPEED_OF_SOUND * 1000) / target_low_freq
        required_total_depth = wavelength_mm / 4
        
        # Standard panel depth: 100mm (optimal for most applications)
        depth = 100  # mm (4 inches)
        
        # Air gap: Match panel depth for double effectiveness
        # Total effective depth = 200mm = λ/4 @ 430Hz
        air_gap = 100  # mm
        
        # Calculate actual effective frequency range
        # Low cutoff: f_low = c/(4 * total_depth)
        total_depth = depth + air_gap
        effective_low_freq = int((self.SPEED_OF_SOUND * 1000) / (4 * total_depth))
        
        # Frequency response calculation
        coefficients = self._calculate_porous_absorption(depth, air_gap, material)
        
        # Materials list (exact quantities)
        panel_area = (width * height) / 1000000  # m²
        materials_list = [
            {
                "item": material.name,
                "quantity": f"1 panel 600x1200x{depth}mm ({panel_area:.2f} m²)",
                "notes": f"Density: {material.density_kg_m3} kg/m³ - DO NOT COMPRESS"
            },
            {
                "item": "1x4 pine lumber (19x89mm)",
                "quantity": f"3.6m (2 @ 1200mm + 2 @ 600mm)",
                "notes": "Frame perimeter - actual size 19x89mm"
            },
            {
                "item": "Wood screws (50mm)",
                "quantity": "16 pieces",
                "notes": "Frame assembly - countersink heads"
            },
            {
                "item": "Acoustically transparent fabric (Guilford of Maine FR701)",
                "quantity": f"{panel_area * 1.3:.2f} m² (800x1400mm cut)",
                "notes": "30% extra for wrapping - must be acoustically transparent"
            },
            {
                "item": "Staples (10mm)",
                "quantity": "100 pieces",
                "notes": "Fabric attachment to frame back"
            },
            {
                "item": "Z-clips or French cleats",
                "quantity": "4 pieces (2 pairs)",
                "notes": f"Creates {air_gap}mm air gap when mounted"
            }
        ]
        
        construction_steps = [
            f"STEP 1 - Frame Construction:",
            f"  • Cut 1x4 lumber: 2 pieces @ 1200mm (sides), 2 pieces @ 562mm (top/bottom)",
            f"  • Assemble rectangle: outer dimensions 600x1200mm, depth 89mm",
            f"  • Pre-drill holes, use wood glue + 50mm screws at corners",
            f"  • Ensure frame is square (measure diagonals - must be equal)",
            f"",
            f"STEP 2 - Install Absorber Material:",
            f"  • Cut {material.name} to 580x1180x{depth}mm (slightly undersized)",
            f"  • Density check: {material.density_kg_m3} kg/m³ is optimal - verify on packaging",
            f"  • Place material in frame - DO NOT COMPRESS (crucial for performance)",
            f"  • Material should fit snugly but not be forced",
            f"",
            f"STEP 3 - Fabric Covering:",
            f"  • Cut fabric to 800x1400mm (allows wrapping to frame back)",
            f"  • Center fabric over frame front, pull taut (not tight)",
            f"  • Staple to BACK of frame: center of each side first, then corners",
            f"  • Work outward from centers, keeping fabric smooth and even tension",
            f"  • Fold corners neatly (hospital corner technique)",
            f"",
            f"STEP 4 - Mounting for {air_gap}mm Air Gap:",
            f"  • Install Z-clips on wall at desired height (1000-1400mm from floor)",
            f"  • Clip depth creates exactly {air_gap}mm air gap behind panel",
            f"  • Air gap is CRITICAL - doubles effective depth to {total_depth}mm",
            f"  • Effective low frequency: ~{effective_low_freq}Hz (λ/4 resonance)",
            f"",
            f"THEORY - Why This Works:",
            f"  • Quarter-wavelength absorption: f = c/(4d) where d = material + air gap",
            f"  • At {effective_low_freq}Hz: wavelength = {total_depth*4}mm, panel = λ/4",
            f"  • Particle velocity maximum at λ/4 from wall - optimal absorption",
            f"  • Density {material.density_kg_m3} kg/m³: provides flow resistivity = {material.flow_resistivity} rayls/m"
        ]
        
        return PanelSpec(
            type="Broadband Porous Absorber",
            width_mm=width,
            height_mm=height,
            depth_mm=depth,
            material=material.name,
            air_gap_mm=air_gap,
            frame_material="1x3 softwood lumber",
            facing="Acoustically transparent fabric (Guilford of Maine or similar)",
            target_frequencies=[target_low_freq, 500, 1000, 2000, 4000],
            absorption_coefficients=coefficients,
            construction_steps=construction_steps,
            materials_list=materials_list
        )
    
    def design_corner_bass_trap(self,
                               height: float = 2400,
                               target_freq: int = 80) -> PanelSpec:
        """
        Design a floor-to-ceiling corner bass trap (superchunk).
        
        Corner placement provides maximum bass absorption:
        - Pressure maxima for all modes occur at corners
        - Triangular cross-section: 300x300mm per corner
        - Full ceiling height (2400mm typical) for maximum effectiveness
        - Uses 48-60 kg/m³ density (NOT low density - needs flow resistance)
        """
        # Calculate quarter-wavelength depth for target frequency
        wavelength_mm = (self.SPEED_OF_SOUND * 1000) / target_freq
        quarter_wave_depth = wavelength_mm / 4
        
        # Practical corner trap dimensions
        # Standard superchunk: 300mm from corner (424mm diagonal)
        depth = 300  # mm from each wall
        width = 300  # mm (forms 45° triangle in corner)
        
        # Use medium density for bass (48-60 kg/m³)
        # Lower densities (<40) lack flow resistivity for bass
        # Higher densities (>80) too expensive for large volumes
        material = MATERIALS["owens_703"]  # 48 kg/m³ optimal for bass traps
        
        # Calculate actual absorption based on depth and density
        # Effective low frequency = c/(4*depth)
        effective_low_freq = int((self.SPEED_OF_SOUND * 1000) / (4 * depth))
        
        coefficients = {
            50: 0.45,
            63: 0.60,
            80: 0.75,
            100: 0.88,
            125: 0.95,
            250: 0.99,
            500: 1.00,
            1000: 1.00,
            2000: 0.95
        }
        
        # Calculate material volume needed
        # Triangle: Area = (width * depth) / 2
        triangle_area = (width * depth) / 2 / 1000000  # m²
        volume_m3 = triangle_area * (height / 1000)  # m³
        
        materials_list = [
            {
                "item": material.name,
                "quantity": f"{volume_m3:.2f} m³ = {volume_m3 * material.density_kg_m3:.1f} kg",
                "notes": f"Density {material.density_kg_m3} kg/m³ - typically 12-16 batts (600x1200x100mm)"
            },
            {
                "item": "2x2 lumber (38x38mm)",
                "quantity": f"{height/1000 * 2:.1f}m (2 vertical corner pieces)",
                "notes": "Frame supports - run floor to ceiling"
            },
            {
                "item": "1x2 lumber (19x38mm)",
                "quantity": f"{width/1000 * 6:.1f}m",
                "notes": "Horizontal braces (3 per trap: bottom, middle, top)"
            },
            {
                "item": "Acoustically transparent fabric",
                "quantity": f"{(width * 1.4 * height)/1000000:.2f} m²",
                "notes": "Face fabric (40% extra for wrapping)"
            },
            {
                "item": "Angle brackets",
                "quantity": "6 pieces",
                "notes": "Secure frame to walls"
            }
        ]
        
        construction_steps = [
            f"STEP 1 - Frame Construction:",
            f"  • Cut 2 pieces of 2x2 lumber @ {height}mm (vertical corner posts)",
            f"  • Cut 6 pieces of 1x2 lumber @ {width}mm (horizontal braces)",
            f"  • Install corner posts: 1 on each wall, {depth}mm from corner",
            f"  • Secure posts with angle brackets at top, middle, bottom",
            f"  • Add horizontal braces connecting posts at 3 heights",
            f"",
            f"STEP 2 - Install Absorber Material:",
            f"  • Use {material.name} batts (600x1200x100mm typical)",
            f"  • Cut batts into triangular pieces to fill corner wedge",
            f"  • Stack from floor to ceiling, filling entire triangular space",
            f"  • DO NOT COMPRESS - let material sit loosely (critical!)",
            f"  • Total volume: ~{volume_m3:.2f} m³ of {material.density_kg_m3} kg/m³ material",
            f"",
            f"STEP 3 - Fabric Installation:",
            f"  • Cut fabric in long strip: {width*1.4:.0f}mm wide x {height}mm tall",
            f"  • Staple top edge to ceiling brace",
            f"  • Pull fabric down and across triangle face",
            f"  • Staple to both wall posts, keeping fabric taut",
            f"  • Trim excess at floor",
            f"",
            f"THEORY - Corner Bass Trap Physics:",
            f"  • All room modes have pressure maximum at corners (100% pressure)",
            f"  • {depth}mm depth = λ/4 @ {effective_low_freq}Hz",
            f"  • Density {material.density_kg_m3} kg/m³: flow resistivity {material.flow_resistivity} rayls/m",
            f"  • Full ceiling height captures all modal pressure zones",
            f"  • Triangular shape: efficient use of corner space (diagonal = {width * 1.414:.0f}mm)"
        ]
        
        return PanelSpec(
            type="Corner Bass Trap",
            width_mm=width,
            height_mm=height,
            depth_mm=depth,
            material=material.name,
            air_gap_mm=0,  # Directly in corner
            frame_material="2x4 softwood lumber",
            facing="Acoustically transparent fabric",
            target_frequencies=[63, 80, 100, 125],
            absorption_coefficients=coefficients,
            construction_steps=construction_steps,
            materials_list=materials_list
        )
    
    def design_helmholtz_resonator(self,
                                   target_freq: float,
                                   width: float = 600,
                                   height: float = 600) -> PanelSpec:
        """
        Design a Helmholtz resonator for targeting specific frequencies.
        
        Formula: f = (c / 2π) * sqrt(S / (V * (L + 0.8d)))
        
        Where:
        - S = neck area
        - V = cavity volume
        - L = neck length
        - d = neck diameter
        """
        # Design parameters for target frequency
        # We'll use a slotted design (easier to build than holes)
        
        # Cavity depth (typically 100-300mm)
        cavity_depth = 200  # mm
        cavity_volume = (width * height * cavity_depth) / 1e9  # m³
        
        # Calculate slot parameters
        # Using slots across the width
        slot_width = 10  # mm (typical slot width)
        
        # Rearranging Helmholtz formula to find slot area needed
        c = self.SPEED_OF_SOUND
        
        # Slot length (panel thickness)
        slot_length = 20  # mm (using 20mm plywood)
        
        # End correction factor
        end_correction = 0.8 * slot_width / 1000
        effective_length = (slot_length / 1000) + end_correction
        
        # Required slot area: S = (2πf)² * V * L_eff / c²
        required_area = ((2 * np.pi * target_freq) ** 2 * cavity_volume * effective_length) / (c ** 2)
        required_area_mm2 = required_area * 1e6
        
        # Number of slots (across width)
        slots_per_row = int(width / (slot_width * 3))  # Spacing of 3x slot width
        slot_length_each = required_area_mm2 / (slots_per_row * slot_width)
        
        # Perforation percentage
        total_slot_area = slots_per_row * slot_width * min(slot_length_each, height * 0.8)
        perforation_pct = (total_slot_area / (width * height)) * 100
        
        materials_list = [
            {
                "item": "18-20mm plywood or MDF",
                "quantity": f"2 panels {width}x{height}mm",
                "notes": "Front (slotted) and back panels"
            },
            {
                "item": "18-20mm plywood strips",
                "quantity": f"{2*(width + height)/1000:.1f}m linear, 200mm wide",
                "notes": "Side pieces to create cavity"
            },
            {
                "item": "Thin absorber (25mm rockwool)",
                "quantity": f"{(width * height)/1000000:.2f} m²",
                "notes": "Line back of cavity for damping"
            },
            {
                "item": "Wood screws",
                "quantity": "~20",
                "notes": "Assembly"
            }
        ]
        
        construction_steps = [
            f"1. Cut front panel: {width}x{height}mm from plywood/MDF",
            f"2. Cut slots: {slots_per_row} slots, {slot_width}mm wide, spaced evenly",
            f"3. Cut back panel: {width}x{height}mm (solid, no slots)",
            f"4. Cut side strips: {cavity_depth}mm wide",
            "5. Assemble box with slots on front, solid back",
            "6. Line back interior with thin absorber material",
            f"7. Resulting cavity depth: {cavity_depth}mm",
            f"8. Mount on wall with sealed edges (no air gaps around perimeter)"
        ]
        
        # Q factor (sharpness of resonance)
        q_factor = 5  # Typical for Helmholtz resonator
        bandwidth = target_freq / q_factor
        
        coefficients = {
            int(target_freq * 0.7): 0.3,
            int(target_freq * 0.85): 0.6,
            int(target_freq): 1.0,
            int(target_freq * 1.15): 0.6,
            int(target_freq * 1.3): 0.3
        }
        
        return PanelSpec(
            type=f"Helmholtz Resonator (tuned to {target_freq}Hz)",
            width_mm=width,
            height_mm=height,
            depth_mm=cavity_depth + slot_length,
            material="Plywood/MDF cavity with slotted front",
            air_gap_mm=0,
            frame_material="Plywood/MDF construction",
            facing=f"Slotted front panel ({perforation_pct:.1f}% open area)",
            target_frequencies=[int(target_freq)],
            absorption_coefficients=coefficients,
            construction_steps=construction_steps,
            materials_list=materials_list
        )
    
    def design_qrd_diffuser(self,
                           prime: int = 7,
                           design_freq: float = 500,
                           width: float = 600,
                           height: float = 600) -> PanelSpec:
        """
        Design a Quadratic Residue Diffuser (QRD).
        
        Well depths follow: depth_n = (n² mod N) * λ / (2N)
        
        Where N is the prime number (7, 11, 13, 17, 23...)
        
        Args:
            prime: Prime number for sequence (7, 11, 13, etc.)
            design_freq: Design frequency (Hz)
            width, height: Overall panel dimensions
        """
        wavelength_mm = (self.SPEED_OF_SOUND / design_freq) * 1000
        
        # Calculate well depths for each position
        well_depths = []
        for n in range(prime):
            depth = ((n ** 2) % prime) * wavelength_mm / (2 * prime)
            well_depths.append(round(depth, 1))
        
        max_depth = max(well_depths)
        
        # Well width (period width / number of wells)
        # For a 600mm panel with prime 7: ~85mm per well
        well_width = width / prime
        
        # Effective frequency range
        # Low limit: λ = 2 * max_depth * N
        low_freq = self.SPEED_OF_SOUND / (2 * (max_depth/1000) * prime)
        # High limit: λ = 2 * well_width
        high_freq = self.SPEED_OF_SOUND / (2 * well_width/1000)
        
        materials_list = [
            {
                "item": "18mm plywood strips",
                "quantity": f"{prime + 1} dividers, {height}mm x {max_depth + 20}mm each",
                "notes": "Well dividers (one more than number of wells)"
            },
            {
                "item": "18mm plywood",
                "quantity": f"1 panel {width}x{height}mm",
                "notes": "Back panel"
            },
            {
                "item": "Wood blocks",
                "quantity": f"{prime} sets of varying heights",
                "notes": "To create well depth differences"
            }
        ]
        
        construction_steps = [
            f"1. Cut back panel: {width}x{height}mm",
            f"2. Cut {prime + 1} divider strips: {height}mm x {max_depth + 20}mm",
            f"3. Well width: {well_width:.1f}mm each",
            "4. Well depths from left to right:",
        ]
        
        for i, depth in enumerate(well_depths):
            construction_steps.append(f"   Well {i+1}: {depth:.1f}mm deep")
        
        construction_steps.extend([
            "5. Attach dividers to back panel at calculated spacing",
            "6. Fill wells to correct depth with blocks or add fins",
            "7. Paint with latex paint if desired (thin coat only)",
            f"8. Mount at ear height, minimum {wavelength_mm*3/1000:.1f}m from listener"
        ])
        
        return PanelSpec(
            type=f"QRD Diffuser (Prime {prime})",
            width_mm=width,
            height_mm=height,
            depth_mm=max_depth + 20,  # +20 for back panel
            material="Wood construction",
            air_gap_mm=0,
            frame_material="18mm plywood",
            facing="Open wells",
            target_frequencies=[int(low_freq), int(design_freq), int(high_freq)],
            absorption_coefficients={500: 0.15, 1000: 0.20, 2000: 0.15},  # Diffusers don't absorb much
            construction_steps=construction_steps,
            materials_list=materials_list
        )
    
    def design_membrane_absorber(self,
                                target_freq: float = 80,
                                width: float = 600,
                                height: float = 600) -> PanelSpec:
        """
        Design a membrane (diaphragmatic) absorber.
        
        Resonant frequency: f = 60 / sqrt(m * d)
        Where m = surface mass (kg/m²) and d = air gap (cm)
        
        Effective for low frequencies where porous absorbers are impractical.
        """
        # Rearrange formula to find required mass and depth
        # m * d = (60 / f)²
        md_product = (60 / target_freq) ** 2
        
        # Practical depth (5-15 cm typically)
        cavity_depth_cm = 10
        required_mass = md_product / cavity_depth_cm  # kg/m²
        
        # Common materials and their surface mass
        # 3mm MDF ≈ 2.1 kg/m², 6mm MDF ≈ 4.2 kg/m², 9mm MDF ≈ 6.3 kg/m²
        # 3mm plywood ≈ 1.8 kg/m²
        
        if required_mass < 3:
            membrane_material = "3mm plywood or MDF"
            membrane_mass = 2.1
        elif required_mass < 5:
            membrane_material = "6mm MDF"
            membrane_mass = 4.2
        else:
            membrane_material = "9mm MDF"
            membrane_mass = 6.3
        
        # Recalculate actual resonant frequency
        actual_freq = 60 / np.sqrt(membrane_mass * cavity_depth_cm)
        
        cavity_depth_mm = cavity_depth_cm * 10
        
        materials_list = [
            {
                "item": membrane_material,
                "quantity": f"1 panel {width}x{height}mm",
                "notes": f"Membrane (front) - surface mass ~{membrane_mass:.1f} kg/m²"
            },
            {
                "item": "18mm plywood",
                "quantity": f"1 panel {width}x{height}mm",
                "notes": "Rigid back panel"
            },
            {
                "item": "Lumber for frame",
                "quantity": f"{2*(width + height)/1000:.1f}m linear",
                "notes": f"Frame depth: {cavity_depth_mm}mm"
            },
            {
                "item": "Thin absorber (25mm mineral wool)",
                "quantity": f"{(width * height)/1000000:.2f} m²",
                "notes": "Line back to dampen resonance, increase bandwidth"
            }
        ]
        
        construction_steps = [
            f"1. Build frame: {width}x{height}mm, {cavity_depth_mm}mm deep",
            f"2. Attach back panel (18mm plywood)",
            "3. Line interior back with thin mineral wool",
            f"4. Attach membrane ({membrane_material}) to front",
            "5. IMPORTANT: Membrane must be free to vibrate - don't over-tighten",
            f"6. Actual resonant frequency: ~{actual_freq:.0f}Hz",
            "7. Mount directly on wall (no air gap needed)"
        ]
        
        # Absorption curve peaks at resonant frequency
        coefficients = {
            int(actual_freq * 0.5): 0.2,
            int(actual_freq * 0.75): 0.5,
            int(actual_freq): 0.9,
            int(actual_freq * 1.25): 0.5,
            int(actual_freq * 1.5): 0.2,
            500: 0.1  # Low absorption at higher frequencies
        }
        
        return PanelSpec(
            type=f"Membrane Absorber (tuned to ~{actual_freq:.0f}Hz)",
            width_mm=width,
            height_mm=height,
            depth_mm=cavity_depth_mm + 18 + 6,  # cavity + back + membrane
            material=f"Membrane: {membrane_material}, Cavity: air + mineral wool",
            air_gap_mm=0,
            frame_material="Plywood frame with rigid back",
            facing=membrane_material,
            target_frequencies=[int(actual_freq)],
            absorption_coefficients=coefficients,
            construction_steps=construction_steps,
            materials_list=materials_list
        )
    
    def _calculate_porous_absorption(self, depth_mm: float, air_gap_mm: float,
                                    material: MaterialSpec) -> Dict[int, float]:
        """
        Estimate absorption coefficients for porous absorber.
        
        Simplified model based on material properties and mounting.
        """
        # Effective depth with air gap
        effective_depth = depth_mm + air_gap_mm
        
        # Quarter wavelength frequencies (where absorption becomes effective)
        c = self.SPEED_OF_SOUND * 1000  # mm/s
        quarter_wave_freq = c / (4 * effective_depth)
        
        coefficients = {}
        frequencies = [125, 250, 500, 1000, 2000, 4000]
        
        for freq in frequencies:
            # Ratio of depth to wavelength
            wavelength = c / freq
            ratio = effective_depth / wavelength
            
            # Simplified absorption model
            if ratio >= 0.25:
                # At or above quarter wavelength - very effective
                alpha = min(1.0, 0.9 + (ratio - 0.25) * 0.4)
            elif ratio >= 0.125:
                # Eighth to quarter wavelength
                alpha = 0.5 + (ratio - 0.125) * 3.2
            else:
                # Below eighth wavelength - limited effectiveness
                alpha = ratio * 4
            
            # Density factor (higher density = better absorption)
            density_factor = min(1.0, material.density_kg_m3 / 80)
            alpha *= (0.7 + 0.3 * density_factor)
            
            coefficients[freq] = round(min(1.0, alpha), 2)
        
        return coefficients


def get_panel_designs_for_room(problems: List[Dict], 
                               use_metric: bool = True) -> List[PanelSpec]:
    """
    Generate panel designs based on identified room problems.
    
    Strategy:
    - 30-80 Hz: Corner bass traps + Helmholtz resonators
    - 80-200 Hz: Membrane absorbers + corner traps
    - 200+ Hz: Broadband porous absorbers
    
    Args:
        problems: List of problem frequencies from analysis
        use_metric: True for metric measurements
        
    Returns:
        List of panel specifications to address problems
    """
    calculator = PanelConstructionCalculator(use_metric)
    panels = []
    
    # Always recommend corner bass traps (handle all bass modes)
    panels.append(calculator.design_corner_bass_trap(height=2400, target_freq=80))
    
    for problem in problems:
        freq = problem.get("frequency", 100)
        severity = problem.get("severity", "medium")
        
        if freq < 80:
            # Very low frequency - Helmholtz resonator for specific targeting
            if severity in ["high", "critical"]:
                panels.append(calculator.design_helmholtz_resonator(
                    target_freq=freq,
                    width=600,
                    height=1200
                ))
        elif freq < 200:
            # Upper bass - membrane absorber
            panels.append(calculator.design_membrane_absorber(
                target_freq=freq,
                width=600,
                height=1200
            ))
        else:
            # Mid-high frequencies - broadband absorber
            panels.append(calculator.design_broadband_absorber(
                width=600,
                height=1200,
                target_low_freq=min(freq, 500),  # Cap at 500Hz for sizing
                material_key="owens_703"  # 48 kg/m³ optimal
            ))
    
    # Always add at least 2 broadband panels for mid-high frequencies
    if not any(p.type == "Broadband Porous Absorber" for p in panels):
        panels.append(calculator.design_broadband_absorber(
            width=600,
            height=1200,
            target_low_freq=250,
            material_key="owens_703"
        ))
    
    return panels

"""
Maximum Length Sequence (MLS) Generator for Hybrid Acoustic Panels

Generates pseudo-random binary sequences using Linear Feedback Shift Registers (LFSR)
for creating hybrid absorber/reflector panels that scatter sound evenly.

Based on acoustic principles from:
- Acoustic Absorbers and Diffusers (Cox & D'Antonio)
- Master Handbook of Acoustics (Everest & Pohlmann)

Key concepts:
- 1 (High/Hard): Reflects high frequencies - slat/wood
- 0 (Low/Soft): Allows absorption - gap/exposed fabric
- Goal: Flat power spectrum for even sound scattering
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum


class LayoutType(Enum):
    HORIZONTAL_1D = "horizontal_1d"  # Vertical slats, horizontal scattering
    VERTICAL_1D = "vertical_1d"      # Horizontal slats, vertical scattering
    GRID_2D = "grid_2d"              # 2D pattern, omnidirectional scattering


# Primitive Polynomials for LFSR (tap positions for XOR operation)
# These are proven to generate maximal-length sequences
# Format: order n -> list of tap positions (1-indexed from right)
PRIMITIVE_POLYNOMIALS = {
    3: [3, 2],           # N = 7
    4: [4, 3],           # N = 15
    5: [5, 3],           # N = 31
    6: [6, 5],           # N = 63
    7: [7, 6],           # N = 127
    8: [8, 6, 5, 4],     # N = 255
    9: [9, 5],           # N = 511
    10: [10, 7],         # N = 1023
}


@dataclass
class MLSResult:
    """Result of MLS generation for panel design"""
    sequence: List[int]           # The binary sequence (1s and 0s)
    order: int                    # The n in 2^n - 1
    length: int                   # N = 2^n - 1
    panel_width_mm: float         # Actual panel width
    panel_height_mm: float        # Actual panel height
    element_width_mm: float       # Width of each element (slat or gap)
    layout_type: LayoutType       # 1D or 2D layout
    
    # Statistics
    num_slats: int                # Count of 1s (reflective elements)
    num_gaps: int                 # Count of 0s (absorptive elements)
    balance_ratio: float          # Ratio of 1s to total (should be ~0.5)
    
    # For 2D grids
    grid: Optional[List[List[int]]] = None
    grid_rows: int = 0
    grid_cols: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "sequence": self.sequence,
            "order": self.order,
            "length": self.length,
            "panel_width_mm": self.panel_width_mm,
            "panel_height_mm": self.panel_height_mm,
            "element_width_mm": round(self.element_width_mm, 1),
            "layout_type": self.layout_type.value,
            "num_slats": self.num_slats,
            "num_gaps": self.num_gaps,
            "balance_ratio": round(self.balance_ratio, 3),
            "grid": self.grid,
            "grid_rows": self.grid_rows,
            "grid_cols": self.grid_cols
        }


@dataclass
class CutListItem:
    """A single item in the cut list"""
    element_type: str           # "slat" or "gap"
    position_mm: float          # Position from left edge
    width_mm: float             # Width of this element
    index: int                  # Position in sequence


@dataclass
class PanelBOM:
    """Bill of Materials for hybrid panel construction"""
    total_slat_width_mm: float
    total_gap_width_mm: float
    num_slats: int
    num_gaps: int
    slat_height_mm: float
    element_width_mm: float
    cut_list: List[CutListItem]
    slat_positions_mm: List[float]
    gap_positions_mm: List[float]
    
    # Material estimates
    wood_area_m2: float
    fabric_area_m2: float
    absorber_area_m2: float
    
    # Construction notes
    notes: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "total_slat_width_mm": round(self.total_slat_width_mm, 1),
            "total_gap_width_mm": round(self.total_gap_width_mm, 1),
            "num_slats": self.num_slats,
            "num_gaps": self.num_gaps,
            "slat_height_mm": self.slat_height_mm,
            "element_width_mm": round(self.element_width_mm, 1),
            "cut_list": [
                {
                    "type": item.element_type,
                    "position_mm": round(item.position_mm, 1),
                    "width_mm": round(item.width_mm, 1),
                    "index": item.index
                }
                for item in self.cut_list
            ],
            "slat_positions_mm": [round(p, 1) for p in self.slat_positions_mm],
            "gap_positions_mm": [round(p, 1) for p in self.gap_positions_mm],
            "wood_area_m2": round(self.wood_area_m2, 3),
            "fabric_area_m2": round(self.fabric_area_m2, 3),
            "absorber_area_m2": round(self.absorber_area_m2, 3),
            "notes": self.notes
        }


class MLSGenerator:
    """
    Maximum Length Sequence Generator using Linear Feedback Shift Register (LFSR)
    
    Generates pseudo-random binary sequences that have optimal autocorrelation
    properties for acoustic diffusion applications.
    """
    
    def __init__(self):
        self.polynomials = PRIMITIVE_POLYNOMIALS
    
    def find_optimal_order(self, target_elements: int) -> Tuple[int, int]:
        """
        Find the optimal MLS order (n) for the target number of elements.
        
        Args:
            target_elements: Desired number of elements (panel_width / slat_width)
            
        Returns:
            Tuple of (order n, sequence length N = 2^n - 1)
        """
        available_orders = sorted(self.polynomials.keys())
        
        best_order = available_orders[0]
        best_length = 2 ** best_order - 1
        best_diff = abs(target_elements - best_length)
        
        for order in available_orders:
            length = 2 ** order - 1
            diff = abs(target_elements - length)
            
            if diff < best_diff:
                best_order = order
                best_length = length
                best_diff = diff
        
        return best_order, best_length
    
    def generate_mls(self, order: int, seed: int = None) -> List[int]:
        """
        Generate a Maximum Length Sequence using LFSR (Fibonacci configuration).
        
        The algorithm uses XOR operations on specific "tap" positions
        defined by primitive polynomials to generate pseudo-random sequences.
        
        Args:
            order: The n in 2^n - 1 (determines sequence length)
            seed: Initial state of the register (if None, uses all 1s)
            
        Returns:
            List of 0s and 1s of length 2^n - 1
        """
        if order not in self.polynomials:
            raise ValueError(f"Order {order} not supported. Available: {list(self.polynomials.keys())}")
        
        taps = self.polynomials[order]
        length = 2 ** order - 1
        
        # Initialize register with seed (all 1s if not specified)
        if seed is None:
            register = (1 << order) - 1  # All 1s
        else:
            register = seed & ((1 << order) - 1)
            if register == 0:
                register = 1  # Must be non-zero
        
        sequence = []
        
        for _ in range(length):
            # Output is the most significant bit (bit n-1)
            output = (register >> (order - 1)) & 1
            sequence.append(output)
            
            # Calculate feedback bit using XOR of tap positions
            # Taps are 1-indexed, so tap 5 means bit 5 (which is index 4)
            feedback = 0
            for tap in taps:
                feedback ^= (register >> (tap - 1)) & 1
            
            # Shift register left and insert feedback at LSB
            register = ((register << 1) | feedback) & ((1 << order) - 1)
        
        return sequence
    
    def generate_inverse(self, sequence: List[int]) -> List[int]:
        """
        Generate the inverse of a sequence (flip 1s and 0s).
        Useful for adjacent panels to avoid repetition patterns.
        """
        return [1 - bit for bit in sequence]
    
    def fold_to_2d(self, sequence: List[int], rows: int, cols: int) -> List[List[int]]:
        """
        Fold a 1D MLS sequence into a 2D grid using diagonal folding.
        
        Uses the Chinese Remainder Theorem principle:
        - Write sequence along the diagonal, wrapping at edges
        - This preserves the acoustic properties in 2D
        
        Args:
            sequence: 1D MLS sequence
            rows: Number of rows in the grid
            cols: Number of columns in the grid
            
        Returns:
            2D grid of 0s and 1s
        """
        length = len(sequence)
        
        if rows * cols < length:
            # Grid too small, truncate sequence
            sequence = sequence[:rows * cols]
        
        # Initialize grid with zeros
        grid = [[0 for _ in range(cols)] for _ in range(rows)]
        
        # Diagonal folding
        for i, bit in enumerate(sequence):
            row = i % rows
            col = i % cols
            grid[row][col] = bit
        
        return grid
    
    def design_panel(self,
                     panel_width_mm: float,
                     panel_height_mm: float,
                     preferred_element_width_mm: float = 50,
                     layout: LayoutType = LayoutType.HORIZONTAL_1D,
                     seed: int = 1) -> MLSResult:
        """
        Design a hybrid absorber/reflector panel using MLS.
        
        Args:
            panel_width_mm: Panel width in millimeters
            panel_height_mm: Panel height in millimeters
            preferred_element_width_mm: Desired width of each slat/gap
            layout: 1D or 2D layout type
            seed: Random seed for sequence generation
            
        Returns:
            MLSResult with sequence and panel specifications
        """
        # Calculate target number of elements
        target_elements = int(panel_width_mm / preferred_element_width_mm)
        
        # Find optimal MLS order
        order, length = self.find_optimal_order(target_elements)
        
        # Calculate actual element width to fit perfectly
        actual_element_width = panel_width_mm / length
        
        # Generate the sequence
        sequence = self.generate_mls(order, seed)
        
        # Count slats and gaps
        num_slats = sum(sequence)
        num_gaps = length - num_slats
        balance_ratio = num_slats / length
        
        # Create result
        result = MLSResult(
            sequence=sequence,
            order=order,
            length=length,
            panel_width_mm=panel_width_mm,
            panel_height_mm=panel_height_mm,
            element_width_mm=actual_element_width,
            layout_type=layout,
            num_slats=num_slats,
            num_gaps=num_gaps,
            balance_ratio=balance_ratio
        )
        
        # Handle 2D layout
        if layout == LayoutType.GRID_2D:
            # Find factors for 2D grid
            rows, cols = self._find_grid_factors(length, panel_height_mm, panel_width_mm)
            
            if rows > 1 and cols > 1:
                result.grid = self.fold_to_2d(sequence, rows, cols)
                result.grid_rows = rows
                result.grid_cols = cols
        
        return result
    
    def _find_grid_factors(self, length: int, height: float, width: float) -> Tuple[int, int]:
        """
        Find suitable row/column factors for 2D grid.
        Tries to match panel aspect ratio.
        """
        aspect_ratio = height / width
        
        # Find all factor pairs
        factors = []
        for i in range(2, int(length ** 0.5) + 1):
            if length % i == 0:
                j = length // i
                factors.append((i, j))
                factors.append((j, i))
        
        if not factors:
            # Prime number, use approximate grid
            rows = int(np.sqrt(length * aspect_ratio))
            cols = int(np.ceil(length / rows))
            return rows, cols
        
        # Find factor pair closest to aspect ratio
        best_factors = factors[0]
        best_diff = abs((factors[0][0] / factors[0][1]) - aspect_ratio)
        
        for r, c in factors:
            diff = abs((r / c) - aspect_ratio)
            if diff < best_diff:
                best_factors = (r, c)
                best_diff = diff
        
        return best_factors
    
    def generate_bom(self, mls_result: MLSResult, 
                     slat_thickness_mm: float = 20,
                     absorber_depth_mm: float = 100) -> PanelBOM:
        """
        Generate Bill of Materials and cut list for panel construction.
        
        Args:
            mls_result: Result from design_panel()
            slat_thickness_mm: Thickness of wood slats
            absorber_depth_mm: Depth of absorption material behind
            
        Returns:
            PanelBOM with complete construction details
        """
        sequence = mls_result.sequence
        element_width = mls_result.element_width_mm
        panel_height = mls_result.panel_height_mm
        panel_width = mls_result.panel_width_mm
        
        # Build cut list
        cut_list = []
        slat_positions = []
        gap_positions = []
        
        for i, bit in enumerate(sequence):
            position = i * element_width
            item = CutListItem(
                element_type="slat" if bit == 1 else "gap",
                position_mm=position,
                width_mm=element_width,
                index=i
            )
            cut_list.append(item)
            
            if bit == 1:
                slat_positions.append(position)
            else:
                gap_positions.append(position)
        
        # Calculate totals
        total_slat_width = mls_result.num_slats * element_width
        total_gap_width = mls_result.num_gaps * element_width
        
        # Material estimates
        wood_area = (total_slat_width * panel_height) / 1_000_000  # m²
        fabric_area = (panel_width * panel_height) / 1_000_000  # m² (full backing)
        absorber_area = fabric_area  # Same as full panel
        
        # Construction notes
        notes = [
            f"MLS ORDER: n={mls_result.order}, generating {mls_result.length} elements",
            f"ELEMENT WIDTH: {element_width:.1f}mm (adjusted from preferred to fit panel exactly)",
            f"BALANCE: {mls_result.balance_ratio*100:.1f}% reflective / {(1-mls_result.balance_ratio)*100:.1f}% absorptive",
            "",
            "CONSTRUCTION SEQUENCE:",
            f"1. Build frame: {panel_width}mm x {panel_height}mm x {absorber_depth_mm + slat_thickness_mm}mm deep",
            f"2. Install absorption material ({absorber_depth_mm}mm thick) in frame",
            "3. Cover with acoustically transparent fabric (Guilford of Maine FR701 or similar)",
            f"4. Cut {mls_result.num_slats} slats: each {element_width:.1f}mm wide x {panel_height}mm tall x {slat_thickness_mm}mm thick",
            "5. Mount slats at the positions indicated in the cut list below",
            "6. Use spacers to ensure consistent gap widths",
            "",
            "ACOUSTIC PRINCIPLE:",
            "• Slats (1s): Reflect high frequencies, keeping the room 'live'",
            "• Gaps (0s): Allow sound through to the absorber behind",
            "• MLS pattern: Pseudo-random sequence provides flat power spectrum",
            "• Result: Even scattering without frequency coloration",
            "",
            "FOR ADJACENT PANELS:",
            "Use the INVERSE pattern (flip 1s and 0s) to avoid repetition artifacts",
        ]
        
        return PanelBOM(
            total_slat_width_mm=total_slat_width,
            total_gap_width_mm=total_gap_width,
            num_slats=mls_result.num_slats,
            num_gaps=mls_result.num_gaps,
            slat_height_mm=panel_height,
            element_width_mm=element_width,
            cut_list=cut_list,
            slat_positions_mm=slat_positions,
            gap_positions_mm=gap_positions,
            wood_area_m2=wood_area,
            fabric_area_m2=fabric_area,
            absorber_area_m2=absorber_area,
            notes=notes
        )


def get_all_mls_orders() -> List[Dict]:
    """
    Get all available MLS orders with their properties.
    Useful for UI dropdowns.
    """
    orders = []
    for n, taps in PRIMITIVE_POLYNOMIALS.items():
        length = 2 ** n - 1
        num_ones = 2 ** (n - 1)
        num_zeros = 2 ** (n - 1) - 1
        orders.append({
            "order": n,
            "length": length,
            "num_ones": num_ones,
            "num_zeros": num_zeros,
            "balance": num_ones / length,
            "taps": taps,
            "description": f"N={length} elements ({num_ones} slats, {num_zeros} gaps)"
        })
    return orders


def design_hybrid_panel(
    panel_width_mm: float,
    panel_height_mm: float,
    preferred_slat_width_mm: float = 50,
    slat_thickness_mm: float = 20,
    absorber_depth_mm: float = 100,
    layout: str = "horizontal_1d",
    seed: int = 1,
    generate_inverse: bool = False
) -> Dict:
    """
    Main entry point for designing a hybrid MLS panel.
    
    Args:
        panel_width_mm: Panel width in mm
        panel_height_mm: Panel height in mm
        preferred_slat_width_mm: Desired slat/gap width
        slat_thickness_mm: Thickness of wood slats
        absorber_depth_mm: Depth of absorption behind slats
        layout: "horizontal_1d", "vertical_1d", or "grid_2d"
        seed: Random seed for sequence generation
        generate_inverse: If True, also generate inverse pattern
        
    Returns:
        Complete panel design with BOM
    """
    generator = MLSGenerator()
    
    # Parse layout type
    layout_type = LayoutType.HORIZONTAL_1D
    if layout == "vertical_1d":
        layout_type = LayoutType.VERTICAL_1D
    elif layout == "grid_2d":
        layout_type = LayoutType.GRID_2D
    
    # Design the panel
    mls_result = generator.design_panel(
        panel_width_mm=panel_width_mm,
        panel_height_mm=panel_height_mm,
        preferred_element_width_mm=preferred_slat_width_mm,
        layout=layout_type,
        seed=seed
    )
    
    # Generate BOM
    bom = generator.generate_bom(
        mls_result,
        slat_thickness_mm=slat_thickness_mm,
        absorber_depth_mm=absorber_depth_mm
    )
    
    result = {
        "success": True,
        "mls": mls_result.to_dict(),
        "bom": bom.to_dict(),
        "visualization": {
            "pattern": mls_result.sequence,
            "element_width_mm": mls_result.element_width_mm,
            "panel_width_mm": panel_width_mm,
            "panel_height_mm": panel_height_mm,
            "layout": layout
        }
    }
    
    # Add inverse pattern if requested
    if generate_inverse:
        inverse_sequence = generator.generate_inverse(mls_result.sequence)
        result["inverse"] = {
            "sequence": inverse_sequence,
            "description": "Use this pattern for adjacent panels to avoid repetition"
        }
    
    return result

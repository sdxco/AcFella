"""
Nearfield Speaker & Listener Placement Optimizer

Grid-search optimizer for nearfield monitoring in small/medium rooms.
Evaluates many candidate listener positions and returns the best ones
based on composite acoustic criteria:

- Standing-wave pressure at listener (avoid nulls & peaks)
- SBIR (Speaker Boundary Interference Response) management
- Equilateral triangle stereo geometry (ITU-R BS.775, 60° target)
- Null-point avoidance (50%, 33%, 25%, 67%, 75% of length)
- Symmetry enforcement (listener on center axis)

Coordinate system:
  x = left-right (0 = left wall, width = right wall)
  y = front-back (0 = front wall where speakers sit, length = rear wall)
  z = floor-ceiling (0 = floor)
  Front wall is the NARROW wall (width dimension).
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

C_METRIC = 344   # speed of sound m/s
C_IMPERIAL = 1130
EAR_H_M = 1.2
EAR_H_FT = 3.9


@dataclass
class Position3D:
    x: float
    y: float
    z: float

    def to_dict(self) -> Dict:
        return {"x": round(self.x, 3), "y": round(self.y, 3), "z": round(self.z, 3)}

    def distance_to(self, other: "Position3D") -> float:
        return float(np.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2))


@dataclass
class SpeakerPlacement:
    left_speaker: Position3D
    right_speaker: Position3D
    listening_position: Position3D
    speaker_angle: float
    speaker_distance: float
    toe_in_angle: float
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
    Nearfield placement optimizer.
    Grid-searches listener depth and evaluates composite acoustic quality.
    Returns ranked candidate placements for the interactive canvas.
    """

    def __init__(self, length: float, width: float, height: float,
                 use_metric: bool = True):
        self.length = length   # front-back (depth)
        self.width = width     # left-right
        self.height = height
        self.use_metric = use_metric
        self.unit = "m" if use_metric else "ft"
        self.c = C_METRIC if use_metric else C_IMPERIAL
        self.ear_h = EAR_H_M if use_metric else EAR_H_FT

    # ── helpers ───────────────────────────────────────────────

    def _sbir_issues(self, sp: Position3D) -> List[Dict]:
        """SBIR cancellation frequencies for a speaker position."""
        issues = []
        walls = {
            "front wall": sp.y,
            "left wall": sp.x,
            "right wall": self.width - sp.x,
            "floor": sp.z,
            "ceiling": self.height - sp.z,
        }
        for wall, d in walls.items():
            if d > 0:
                f = self.c / (4 * d)
                if 40 < f < 300:
                    sev = "critical" if f < 100 else "moderate" if f < 200 else "minor"
                    issues.append({"severity": sev, "freq": round(f),
                                   "wall": wall, "dist": round(d, 2),
                                   "description": f"SBIR dip at {f:.0f} Hz from {wall} ({d:.2f}{self.unit})"})
        return issues

    def _mode_pressure(self, y_pos: float) -> List[Dict]:
        """Standing-wave pressure at depth y for first 4 modes of each axis."""
        modes = []
        center_x = self.width / 2
        for dim_label, dim_len, pos in [("Length", self.length, y_pos),
                                         ("Width", self.width, center_x),
                                         ("Height", self.height, self.ear_h)]:
            for n in range(1, 5):
                freq = round(n * self.c / (2 * dim_len), 1)
                if freq > 500:
                    continue
                pct = round(abs(np.cos(n * np.pi * pos / dim_len)) * 100)
                modes.append({"dim": dim_label, "n": n, "freq": freq, "pct": pct})
        return modes

    def _score_candidate(self, listener_y: float, speaker_y: float,
                         spread: float) -> Tuple[float, Dict]:
        """
        Score a candidate placement 0-100.
        Returns (score, detail_dict).
        """
        score = 50.0
        detail = {}

        # ── 38% proximity bonus ──────────────────────────
        ratio = listener_y / self.length
        dev = abs(ratio - 0.38)
        if dev < 0.03:
            score += 15
        elif dev < 0.08:
            score += 8
        else:
            score -= dev * 40
        detail["depth_pct"] = round(ratio * 100, 1)

        # ── null-point penalty ────────────────────────────
        for null in (0.25, 0.33, 0.5, 0.67, 0.75):
            if abs(ratio - null) < 0.03:
                score -= 12

        # ── mode-pressure penalty (prefer mid-range %) ────
        modes = self._mode_pressure(listener_y)
        bad = sum(1 for m in modes if m["dim"] == "Length" and (m["pct"] < 15 or m["pct"] > 85))
        score -= bad * 3
        detail["modes"] = modes

        # ── SBIR penalty (capped — every room has boundary issues) ─
        left_sp = Position3D(self.width / 2 - spread / 2, speaker_y, self.ear_h)
        sbir = self._sbir_issues(left_sp)
        sbir_pen = 0
        for iss in sbir:
            sbir_pen += 1 if iss["severity"] == "minor" else 3 if iss["severity"] == "moderate" else 6
        score -= min(sbir_pen, 15)          # cap total SBIR hit
        detail["sbir"] = sbir

        # ── stereo-angle bonus ────────────────────────────
        depth = listener_y - speaker_y
        if depth > 0:
            angle = 2 * np.degrees(np.arctan((spread / 2) / depth))
            if 55 <= angle <= 65:
                score += 10
            elif 50 <= angle <= 70:
                score += 5
            else:
                score -= 5
            detail["stereo_angle"] = round(angle, 1)
        else:
            detail["stereo_angle"] = 0

        # ── rear-wall distance bonus ──────────────────────
        rear_gap = self.length - listener_y
        if rear_gap < 0.8:
            score -= 8
        elif rear_gap > 1.2:
            score += 3

        return max(10, min(100, score)), detail

    # ── main entry point ──────────────────────────────────────

    def optimize(self) -> Dict:
        """
        Grid-search many listener depths, build equilateral-triangle
        geometry for each, return ranked candidates + best placement.
        """
        speaker_y = max(0.3 if self.use_metric else 1.0, self.length * 0.08)
        min_side = 0.5 if self.use_metric else 1.6

        # Candidate depths: 20%-50% of length in 1% steps
        candidates = []
        for pct in range(20, 51):
            ly = self.length * pct / 100
            depth = ly - speaker_y
            if depth < 0.5:
                continue

            # Equilateral triangle: spread = 2*depth/sqrt(3) → 60° angle
            spread = depth * 2 / np.sqrt(3)
            max_spread = self.width - 2 * min_side
            spread = min(spread, max_spread)

            center_x = self.width / 2
            left_x = max(min_side, center_x - spread / 2)
            right_x = min(self.width - min_side, center_x + spread / 2)
            spread = right_x - left_x

            score, detail = self._score_candidate(ly, speaker_y, spread)

            left_sp = Position3D(round(left_x, 3), round(speaker_y, 3), self.ear_h)
            right_sp = Position3D(round(right_x, 3), round(speaker_y, 3), self.ear_h)
            listener = Position3D(round(center_x, 3), round(ly, 3), self.ear_h)

            actual_dist = listener.distance_to(left_sp)
            angle = detail.get("stereo_angle", 60)
            toe_in = angle / 2 if angle <= 60 else angle / 2 - 5

            candidates.append({
                "listener_y": round(ly, 3),
                "depth_pct": detail["depth_pct"],
                "score": round(score, 1),
                "placement": {
                    "left_speaker": left_sp.to_dict(),
                    "right_speaker": right_sp.to_dict(),
                    "listening_position": listener.to_dict(),
                    "speaker_angle": round(angle, 1),
                    "speaker_distance": round(actual_dist, 2),
                    "toe_in_angle": round(toe_in, 1),
                    "speaker_spread": round(spread, 3),
                },
                "modes": detail["modes"],
                "sbir": detail["sbir"],
            })

        # Sort by score descending
        candidates.sort(key=lambda c: c["score"], reverse=True)

        # Best placement
        best = candidates[0] if candidates else None

        # Sub options
        sub_options = self._sub_positions()

        return {
            "room": {"length": self.length, "width": self.width,
                     "height": self.height, "unit": self.unit},
            "speaker_y": round(speaker_y, 3),
            "best": best,
            "candidates": candidates,
            "sub_options": sub_options,
        }

    def _sub_positions(self) -> List[Dict]:
        """Three recommended subwoofer positions."""
        return [
            {"name": "Front center", "x": round(self.width / 2, 3), "y": 0.1,
             "note": "Even excitation of length modes"},
            {"name": "Front left corner", "x": 0.1, "y": 0.1,
             "note": "Maximum output, uneven response"},
            {"name": "Front ¼ width", "x": round(self.width * 0.25, 3), "y": 0.1,
             "note": "Avoids center-width mode peak"},
        ]

    # ── legacy wrappers kept for other routes ────────────────

    def calculate_optimal_placement(self, speaker_type="nearfield",
                                     preference="balanced") -> SpeakerPlacement:
        result = self.optimize()
        best = result["best"]
        pl = best["placement"]
        return SpeakerPlacement(
            left_speaker=Position3D(pl["left_speaker"]["x"], pl["left_speaker"]["y"], pl["left_speaker"]["z"]),
            right_speaker=Position3D(pl["right_speaker"]["x"], pl["right_speaker"]["y"], pl["right_speaker"]["z"]),
            listening_position=Position3D(pl["listening_position"]["x"], pl["listening_position"]["y"], pl["listening_position"]["z"]),
            speaker_angle=pl["speaker_angle"],
            speaker_distance=pl["speaker_distance"],
            toe_in_angle=pl["toe_in_angle"],
            notes=[],
        )

    def generate_three_options(self, speaker_type="nearfield") -> List[Dict]:
        """Legacy — redirect to optimize()."""
        return [self.optimize()["best"]]

    def generate_placement_report(self, speaker_type="nearfield") -> Dict:
        return self.optimize()

    def calculate_subwoofer_positions(self, num_subs=1):
        return self._sub_positions()


def quick_speaker_placement(length, width, height, use_metric=True):
    opt = SpeakerPlacementOptimizer(length, width, height, use_metric)
    pl = opt.calculate_optimal_placement()
    unit = "m" if use_metric else "ft"
    return {
        "listening_position": {"from_front_wall": f"{pl.listening_position.y:.2f} {unit}"},
        "speaker_positions": {
            "left": f"({pl.left_speaker.x:.2f}, {pl.left_speaker.y:.2f}) {unit}",
            "right": f"({pl.right_speaker.x:.2f}, {pl.right_speaker.y:.2f}) {unit}",
        },
        "angles": {"stereo_angle": f"{pl.speaker_angle:.0f}°", "toe_in": f"{pl.toe_in_angle:.0f}°"},
        "distance_to_speakers": f"{pl.speaker_distance:.2f} {unit}",
    }

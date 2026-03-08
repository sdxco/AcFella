"""
Nearfield Speaker & Listener Placement Optimizer

Grid-search optimizer for nearfield monitoring in small/medium rooms.
Evaluates many candidate listener positions and returns ranked results
based on composite acoustic criteria:

  - Standing-wave pressure at listener (cosine pressure distribution)
  - SBIR (Speaker Boundary Interference Response) — Allison effect
  - Equilateral triangle stereo imaging (ITU-R BS.775-3, 60° target)
  - Null-point avoidance (fractional room-length positions)
  - Rear-wall proximity (comb-filtering / ITDG management)
  - First-reflection-path analysis at listener

Scientific references:
  - 38% rule: Bolt & Allison — minimises coincidence with axial nulls
  - SBIR: f_cancel = c/(4·d) for quarter-wave cancellation at boundary d
  - Standing waves: P(x) = |cos(nπx/L)| for mode n along dimension L
  - Stereo triangle: θ = 2·arctan(spread/2/depth), target 60° ± 5°
  - Room modes: f(p,q,r) = (c/2)·√((p/L)²+(q/W)²+(r/H)²)
  - Critical distance approx: d_c ≈ 0.057·√(V/T60)

Coordinate system:
  x = left-right (0 = left wall, width = right wall)
  y = front-back (0 = front wall where speakers sit, length = rear wall)
  z = floor-ceiling (0 = floor)
  Front wall is the NARROW wall (width dimension).
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

C_METRIC = 344   # speed of sound m/s  (20 °C dry air)
C_IMPERIAL = 1130
EAR_H_M = 1.2   # seated ear height
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

    def _room_modes(self, max_freq: float = 300) -> List[Dict]:
        """Axial, tangential, and oblique modes up to max_freq."""
        modes = []
        for p in range(0, 6):
            for q in range(0, 6):
                for r in range(0, 6):
                    if p + q + r == 0:
                        continue
                    f = (self.c / 2) * np.sqrt(
                        (p / self.length) ** 2 +
                        (q / self.width) ** 2 +
                        (r / self.height) ** 2)
                    if f > max_freq:
                        continue
                    axial = sum([p > 0, q > 0, r > 0])
                    kind = "axial" if axial == 1 else "tangential" if axial == 2 else "oblique"
                    modes.append({"p": p, "q": q, "r": r,
                                  "freq": round(f, 1), "type": kind})
        modes.sort(key=lambda m: m["freq"])
        return modes

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

    def _first_reflection_distances(self, listener_y: float) -> Dict:
        """Distances from listener to first reflection points on each wall."""
        cx = self.width / 2
        return {
            "rear_wall": round(self.length - listener_y, 3),
            "left_wall": round(cx, 3),
            "right_wall": round(self.width - cx, 3),
            "floor": round(self.ear_h, 3),
            "ceiling": round(self.height - self.ear_h, 3),
        }

    def _score_candidate(self, listener_y: float, speaker_y: float,
                         spread: float) -> Tuple[float, Dict]:
        """
        Score a candidate placement 0-100.
        Weights:
          38% rule proximity        : up to +15
          Null-point avoidance      : up to -12 each
          Mode flatness (length)    : up to -4 per bad mode
          Mode flatness (all axes)  : up to -2 per bad mode
          SBIR penalty (capped -15) : proportional to severity
          Stereo angle              : +10 ideal, +5 ok, -5 bad
          Rear-wall ITDG            : -8 too close, +3 good
          Front-wall coupling       : bonus for speaker < 0.6m from front
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

        # ── mode-pressure penalty ─────────────────────────
        # Only penalize LENGTH modes — Width and Height positions are fixed
        # (listener must be centered for symmetry; ear height is constant)
        modes = self._mode_pressure(listener_y)
        for m in modes:
            if m["dim"] != "Length":
                continue
            is_bad = m["pct"] < 15 or m["pct"] > 85
            is_marginal = m["pct"] < 25 or m["pct"] > 70
            if is_bad:
                score -= 5
            elif is_marginal:
                score -= 2
        detail["modes"] = modes

        # ── SBIR penalty (capped — floor/ceiling SBIR is universal) ─
        left_sp = Position3D(self.width / 2 - spread / 2, speaker_y, self.ear_h)
        sbir = self._sbir_issues(left_sp)
        sbir_pen = 0
        for iss in sbir:
            # Only penalize side/front wall SBIR heavily; floor/ceiling is universal
            if iss["wall"] in ("floor", "ceiling"):
                sbir_pen += 1
            else:
                sbir_pen += 2 if iss["severity"] == "minor" else 4 if iss["severity"] == "moderate" else 7
        score -= min(sbir_pen, 12)
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

        # ── rear-wall distance ────────────────────────────
        rear_gap = self.length - listener_y
        if rear_gap < 0.6:
            score -= 10
        elif rear_gap < 0.8:
            score -= 5
        elif rear_gap > 1.2:
            score += 3

        # ── front-wall coupling for speakers ──────────────
        # Speakers close to front wall get half-space loading boost (good for nearfield)
        if speaker_y < 0.6:
            score += 2

        return max(10, min(100, score)), detail

    # ── main entry point ──────────────────────────────────────

    def optimize(self) -> Dict:
        """
        Grid-search many listener depths, build equilateral-triangle
        geometry for each, return ranked candidates + best placement
        + room-specific recommendations.
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

        best = candidates[0] if candidates else None
        sub_options = self._sub_positions()
        recommendations = self._generate_recommendations(best, candidates)

        return {
            "room": {"length": self.length, "width": self.width,
                     "height": self.height, "unit": self.unit},
            "speaker_y": round(speaker_y, 3),
            "best": best,
            "candidates": candidates,
            "sub_options": sub_options,
            "recommendations": recommendations,
        }

    # ── recommendations engine ────────────────────────────────

    def _generate_recommendations(self, best: Optional[Dict],
                                   candidates: List[Dict]) -> List[Dict]:
        """Generate room-specific actionable recommendations."""
        recs = []
        L, W, H = self.length, self.width, self.height
        unit = self.unit

        if not best:
            return [{"type": "error", "title": "No valid placement found",
                     "detail": "Room dimensions too small for nearfield monitoring."}]

        bp = best["placement"]
        ly = best["listener_y"]
        ratio = ly / L
        rear = L - ly
        spread = bp["speaker_spread"]
        angle = bp["speaker_angle"]
        score = best["score"]

        # ── Optimal Position ──────────────────────────────
        recs.append({
            "type": "position",
            "title": "Optimal Listening Position",
            "detail": (f"Place your listening point at {ly:.2f}{unit} from the front wall "
                       f"({best['depth_pct']:.0f}% of room length). "
                       f"This position scores {score:.0f}/100 based on standing-wave avoidance, "
                       f"stereo geometry, and boundary interference analysis."),
            "metric": f"{ly:.2f}{unit}",
        })

        # ── Monitor Setup ─────────────────────────────────
        recs.append({
            "type": "monitors",
            "title": "Monitor Placement",
            "detail": (f"Speakers at {bp['left_speaker']['y']:.2f}{unit} from front wall, "
                       f"spread {spread:.2f}{unit} apart "
                       f"({bp['left_speaker']['x']:.2f}{unit} and {bp['right_speaker']['x']:.2f}{unit} from left wall). "
                       f"This forms a {angle:.0f}° stereo triangle at {bp['speaker_distance']:.2f}{unit} distance. "
                       f"Toe-in each monitor {bp['toe_in_angle']:.0f}° toward the listening point."),
            "metric": f"{angle:.0f}°",
        })

        # ── Room Ratio Analysis ───────────────────────────
        ratios = sorted([L / H, W / H, L / W])
        # Bolt area check (simplified)
        aspect = L / W
        if 1.1 <= aspect <= 1.9:
            recs.append({"type": "ok", "title": "Room Proportions",
                         "detail": f"Length/Width ratio of {aspect:.2f} is within the favorable range (1.1–1.9). "
                                   f"This room has reasonable modal distribution."})
        elif aspect < 1.1:
            recs.append({"type": "warning", "title": "Nearly Square Room",
                         "detail": f"Length/Width ratio of {aspect:.2f} is close to 1:1. "
                                   f"Axial modes in both dimensions will cluster at similar frequencies, "
                                   f"causing reinforced peaks and nulls. Consider heavy absorption at mode frequencies."})
        else:
            recs.append({"type": "warning", "title": "Elongated Room",
                         "detail": f"Length/Width ratio of {aspect:.2f} is quite elongated. "
                                   f"Low-frequency length modes will be widely spaced with deep nulls. "
                                   f"Position monitors on the narrow wall for shorter path to listener."})

        # ── 38% Rule Adherence ────────────────────────────
        dev38 = abs(ratio - 0.38)
        if dev38 < 0.03:
            recs.append({"type": "ok", "title": "38% Rule",
                         "detail": f"Listener at {best['depth_pct']:.0f}% — right in the 38% sweet zone. "
                                   f"This minimizes coincidence with the first three axial mode nulls along the room length."})
        elif dev38 < 0.08:
            y38 = L * 0.38
            recs.append({"type": "info", "title": "Near the 38% Sweet Zone",
                         "detail": f"Listener at {best['depth_pct']:.0f}% is close to the 38% rule ({y38:.2f}{unit}). "
                                   f"The optimizer chose {best['depth_pct']:.0f}% because it has better overall modal "
                                   f"behavior in this specific room."})
        else:
            recs.append({"type": "warning", "title": "Outside 38% Zone",
                         "detail": f"Best position at {best['depth_pct']:.0f}% deviates from the 38% rule. "
                                   f"In this room, modal penalties at 38% push the optimum elsewhere. "
                                   f"The position was chosen for lowest combined standing-wave pressure."})

        # ── Rear Wall ─────────────────────────────────────
        if rear < 0.8:
            recs.append({"type": "warning", "title": "Rear Wall Proximity",
                         "detail": f"Only {rear:.2f}{unit} behind the listener. Strong comb-filtering from "
                                   f"rear-wall reflections is likely. Install broadband absorption (min 100mm thick "
                                   f"mineral wool/fiberglass) on the rear wall behind the listening position."})
        elif rear < 1.2:
            recs.append({"type": "info", "title": "Rear Wall Distance",
                         "detail": f"{rear:.2f}{unit} to rear wall — acceptable but tight. "
                                   f"A 50–100mm absorber panel on the rear wall will reduce comb filtering and "
                                   f"tighten the low-mid response at the listening position."})
        else:
            recs.append({"type": "ok", "title": "Rear Wall Distance",
                         "detail": f"{rear:.2f}{unit} to rear wall — good separation. "
                                   f"Rear reflections arrive with sufficient delay to be perceptually distinct. "
                                   f"Absorption is still beneficial but not critical."})

        # ── Stereo Width ──────────────────────────────────
        max_spread = W - 2 * (0.5 if self.use_metric else 1.6)
        spread_limited = spread >= max_spread - 0.05
        if spread_limited and angle < 55:
            recs.append({"type": "warning", "title": "Width-Limited Stereo",
                         "detail": f"Room width ({W:.2f}{unit}) limits speaker spread to {spread:.2f}{unit}, "
                                   f"giving only {angle:.0f}° stereo angle. For a 60° equilateral triangle, "
                                   f"you would need {ly - bp['left_speaker']['y']:.2f}{unit} × 2/√3 = "
                                   f"{(ly - bp['left_speaker']['y']) * 2 / np.sqrt(3):.2f}{unit} spread, "
                                   f"but the room is only {W:.2f}{unit} wide. "
                                   f"Moving the listener closer to the speakers can help."})
        elif angle >= 55 and angle <= 65:
            recs.append({"type": "ok", "title": "Stereo Imaging",
                         "detail": f"Stereo angle of {angle:.0f}° creates an equilateral triangle — "
                                   f"ideal for accurate phantom center and stereo imaging per ITU-R BS.775-3."})

        # ── SBIR Summary ─────────────────────────────────
        sbir = best.get("sbir", [])
        critical_sbir = [s for s in sbir if s["severity"] == "critical"]
        if critical_sbir:
            freqs = ", ".join(f"{s['freq']}Hz ({s['wall']})" for s in critical_sbir)
            recs.append({"type": "warning", "title": "Critical SBIR Dips",
                         "detail": f"Speaker boundary interference causes deep cancellations at: {freqs}. "
                                   f"These are quarter-wavelength nulls from nearby walls. "
                                   f"Soffit-mounting speakers into the front wall eliminates front-wall SBIR. "
                                   f"Otherwise, thick broadband absorbers at first reflection points help."})

        # ── Sub Recommendation ────────────────────────────
        f1_L = self.c / (2 * L)
        f1_W = self.c / (2 * W)
        sub_positions = self._sub_positions()
        best_sub = sub_positions[0] if sub_positions else None
        recs.append({
            "type": "sub",
            "title": "Subwoofer Placement",
            "detail": (f"Best position: {best_sub['name']} (score {best_sub['score']:.0f}/100) — "
                       f"{best_sub['note']}. "
                       f"First axial modes: {f1_L:.0f}Hz (length), {f1_W:.0f}Hz (width). "
                       f"Use the sub position selector to compare all {len(sub_positions)} evaluated positions.") if best_sub else
                      (f"First axial modes: {f1_L:.0f}Hz (length), {f1_W:.0f}Hz (width). "
                       f"Place sub at front wall center for smoothest response."),
            "metric": f"{f1_L:.0f}Hz",
        })

        # ── Score Context ─────────────────────────────────
        top3 = candidates[:3]
        alt_text = ""
        if len(top3) > 1:
            alt_depths = [f"{c['depth_pct']:.0f}%" for c in top3[1:]]
            alt_text = f" Alternative good positions: {', '.join(alt_depths)}."
        recs.append({
            "type": "summary",
            "title": "Overall Assessment",
            "detail": (f"This room scores {score:.0f}/100 at the optimal position. "
                       + ("Excellent — minimal treatment needed. " if score >= 70 else
                          "Good foundation — targeted treatment will improve it significantly. " if score >= 50 else
                          "Challenging room — acoustic treatment is strongly recommended. ")
                       + alt_text),
            "metric": f"{score:.0f}",
        })

        return recs

    def _sub_positions(self) -> List[Dict]:
        """
        Research-backed subwoofer position evaluator.

        Evaluates candidate positions based on:
          - Mode coupling evenness (std-dev of pressure across room modes)
          - Boundary gain (quarter/half/full-space loading)
          - Length-mode drive (should excite all length modes)
          - Width-mode decoupling (avoid center-width resonance buildup)

        Key references:
          - Everest & Pohlmann, "Master Handbook of Acoustics" 7th ed:
            Front-wall center drives all length modes evenly.
            Corner placement gives +9 dB (eighth-space) but excites all modes.
          - Cox & D'Antonio, "Acoustic Absorbers and Diffusers" 3rd ed:
            Asymmetric placement reduces mode reinforcement pile-up.
          - Toole, "Sound Reproduction" 3rd ed:
            Multiple subs at opposing midpoints cancel odd-order modes.
          - Allison effect: SBIR dip at f=c/(4d) from nearest boundary.
        """
        L, W, H = self.length, self.width, self.height
        c = self.c
        u = self.unit

        # Collect axial and tangential modes up to 200 Hz
        modes = []
        for p in range(0, 5):
            for q in range(0, 5):
                for r in range(0, 4):
                    if p + q + r == 0:
                        continue
                    f = (c / 2) * np.sqrt((p / L) ** 2 + (q / W) ** 2 + (r / H) ** 2)
                    if f > 200:
                        continue
                    modes.append((p, q, r, f))

        def score_position(x: float, y: float, z: float = 0.1) -> float:
            """Score a sub position 0–100 based on mode coupling evenness."""
            pressures = []
            for p_m, q_m, r_m, freq in modes:
                # Standing wave pressure: product of cos terms
                pr = 1.0
                if p_m > 0:
                    pr *= abs(np.cos(p_m * np.pi * y / L))
                if q_m > 0:
                    pr *= abs(np.cos(q_m * np.pi * x / W))
                if r_m > 0:
                    pr *= abs(np.cos(r_m * np.pi * z / H))
                pressures.append(pr)

            if not pressures:
                return 50.0

            arr = np.array(pressures)
            mean_p = float(np.mean(arr))
            std_p = float(np.std(arr))

            # Evenness score — lower std relative to mean = more even
            evenness = max(0, 1 - std_p / max(mean_p, 0.01))

            # Mean coupling — we want decent coupling (not at a null)
            coupling = min(1.0, mean_p / 0.6)

            # Boundary gain bonus — closer to walls = more loading
            walls = [y, x, W - x, z, H - z]
            near_walls = sum(1 for d in walls if d < 0.25)
            gain_bonus = near_walls * 0.04  # +4% per nearby wall

            score = 40 * evenness + 40 * coupling + 20 * gain_bonus
            return round(min(100, max(10, score)), 1)

        # Candidate positions (research-backed)
        candidates = [
            {
                "name": "Front wall center",
                "x": round(W / 2, 3), "y": 0.08,
                "note": f"Drives all length modes evenly, null on 1st width mode — smoothest single-sub position (Everest/Toole)",
            },
            {
                "name": "Front wall quarter-width",
                "x": round(W * 0.25, 3), "y": 0.08,
                "note": f"Avoids 1st width-mode center peak, good length coupling — balanced compromise",
            },
            {
                "name": "Front corner (left)",
                "x": 0.12, "y": 0.12,
                "note": f"Eighth-space loading (+9 dB max output) — excites all modes; least flat but loudest",
            },
            {
                "name": "Front wall third-width",
                "x": round(W / 3, 3), "y": 0.08,
                "note": f"Decouples from 1st and 3rd width modes — even response when width modes are problematic",
            },
            {
                "name": "Side wall midpoint",
                "x": 0.08, "y": round(L * 0.38, 3),
                "note": f"38% depth drives length modes from the side — use when front wall is blocked",
            },
        ]

        # Score each and sort
        for cand in candidates:
            cand["score"] = score_position(cand["x"], cand["y"], 0.1)

        candidates.sort(key=lambda c: c["score"], reverse=True)
        return candidates

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

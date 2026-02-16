"""
Porous Absorber Calculator

Implements Delany-Bazley (1970) and Miki (1990) models for predicting
the acoustic absorption coefficient of porous materials backed by a
rigid wall, optionally with an air gap.

Reference:
  - Delany & Bazley, "Acoustical properties of fibrous absorbent materials"
    Applied Acoustics 3(2), 1970
  - Miki, "Acoustical properties of porous materials - modifications of
    Delany-Bazley models" J. Acoust. Soc. Jpn. 11(1), 1990
  - Allard & Champoux, "New empirical equations for sound propagation
    in rigid frame fibrous materials" J. Acoust. Soc. Am. 91(6), 1992
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, List


@dataclass
class PorousAbsorberResult:
    """Result from a porous absorber calculation."""
    frequencies: np.ndarray
    absorption_normal: np.ndarray       # Normal incidence
    absorption_random: np.ndarray       # Random (diffuse field) incidence
    impedance_real: np.ndarray
    impedance_imag: np.ndarray
    nrc: float                          # Noise Reduction Coefficient
    saa: float                          # Sound Absorption Average
    effective_low_freq: float           # Frequency where alpha > 0.5
    total_depth_mm: float               # Thickness + air gap
    model: str


class PorousAbsorberCalculator:
    """
    Calculate absorption coefficients of porous absorbers using
    Delany-Bazley or Miki empirical models.
    """

    # Speed of sound and air density at 20C, 1atm
    C0 = 343.0          # m/s
    RHO0 = 1.204        # kg/m^3
    Z0 = C0 * RHO0      # Characteristic impedance of air

    # ----------------------------------------------------------------
    # Material presets: flow_resistivity in Pa.s/m^2
    # ----------------------------------------------------------------
    MATERIALS = {
        'oc703': {'name': 'Owens Corning 703', 'sigma': 25000, 'density_kg_m3': 48},
        'oc705': {'name': 'Owens Corning 705', 'sigma': 50000, 'density_kg_m3': 96},
        'rockwool_rw3': {'name': 'Rockwool RW3 (60kg/m3)', 'sigma': 18000, 'density_kg_m3': 60},
        'rockwool_rw5': {'name': 'Rockwool RW5 (100kg/m3)', 'sigma': 36000, 'density_kg_m3': 100},
        'rockwool_sns': {'name': 'Rockwool Safe-n-Sound', 'sigma': 22000, 'density_kg_m3': 45},
        'melamine_foam': {'name': 'Melamine Foam', 'sigma': 8500, 'density_kg_m3': 10},
        'polyester_50': {'name': 'Polyester Fiber (50mm)', 'sigma': 12000, 'density_kg_m3': 30},
        'fiberglass_light': {'name': 'Fiberglass (light)', 'sigma': 10000, 'density_kg_m3': 24},
        'fiberglass_dense': {'name': 'Fiberglass (dense)', 'sigma': 40000, 'density_kg_m3': 80},
        'cotton_batts': {'name': 'Cotton Batts', 'sigma': 15000, 'density_kg_m3': 35},
    }

    def __init__(self):
        pass

    # ----------------------------------------------------------------
    # Delany-Bazley model
    # ----------------------------------------------------------------
    def _delany_bazley(self, freq: np.ndarray, sigma: float):
        """
        Delany-Bazley empirical model.
        Returns characteristic impedance Zc and propagation constant gamma.
        """
        X = self.RHO0 * freq / sigma  # dimensionless frequency parameter

        # Characteristic impedance
        Zc_real = self.Z0 * (1 + 0.0571 * X ** (-0.754))
        Zc_imag = -self.Z0 * 0.087 * X ** (-0.732)
        Zc = Zc_real + 1j * Zc_imag

        # Propagation constant
        k0 = 2 * np.pi * freq / self.C0
        alpha_val = k0 * 0.189 * X ** (-0.595)
        beta_val = k0 * (1 + 0.0978 * X ** (-0.700))
        gamma = alpha_val + 1j * beta_val

        return Zc, gamma

    # ----------------------------------------------------------------
    # Miki model (improved Delany-Bazley)
    # ----------------------------------------------------------------
    def _miki(self, freq: np.ndarray, sigma: float):
        """
        Miki model - improved coefficients.
        Returns characteristic impedance Zc and propagation constant gamma.
        """
        X = self.RHO0 * freq / sigma

        Zc_real = self.Z0 * (1 + 0.070 * X ** (-0.632))
        Zc_imag = -self.Z0 * 0.107 * X ** (-0.632)
        Zc = Zc_real + 1j * Zc_imag

        k0 = 2 * np.pi * freq / self.C0
        alpha_val = k0 * 0.160 * X ** (-0.618)
        beta_val = k0 * (1 + 0.109 * X ** (-0.618))
        gamma = alpha_val + 1j * beta_val

        return Zc, gamma

    # ----------------------------------------------------------------
    # Surface impedance with transfer matrix
    # ----------------------------------------------------------------
    def _surface_impedance(self, Zc, gamma, thickness_m, air_gap_m):
        """
        Calculate surface impedance of porous layer backed by rigid wall
        with optional air gap, using transfer matrix method.
        """
        if air_gap_m > 0:
            # Air gap impedance (rigid-backed air layer)
            k0 = gamma.imag  # approximate wavenumber in air = beta from model
            # For air gap: use actual air wavenumber
            freq = np.abs(gamma.imag) * self.C0 / (2 * np.pi)
            k_air = 2 * np.pi * freq / self.C0
            Z_back = -1j * self.Z0 / np.tan(k_air * air_gap_m)
        else:
            # Rigid wall backing
            Z_back = None

        # Porous layer surface impedance via transfer matrix
        cosh_gd = np.cosh(gamma * thickness_m)
        sinh_gd = np.sinh(gamma * thickness_m)

        if Z_back is not None:
            # Transfer matrix: layer in front of air gap
            Z_surface = Zc * (Z_back * cosh_gd + Zc * sinh_gd) / (Z_back * sinh_gd + Zc * cosh_gd)
        else:
            # Directly on rigid wall: Z = Zc * coth(gamma * d)
            Z_surface = Zc * cosh_gd / sinh_gd

        return Z_surface

    # ----------------------------------------------------------------
    # Absorption coefficients
    # ----------------------------------------------------------------
    def _normal_incidence_absorption(self, Z_surface):
        """Normal incidence absorption coefficient."""
        r = (Z_surface - self.Z0) / (Z_surface + self.Z0)
        alpha = 1 - np.abs(r) ** 2
        return np.clip(alpha, 0, 1)

    def _random_incidence_absorption(self, Z_surface):
        """
        Random incidence (diffuse field) absorption.
        Uses Paris formula integration over angles 0 to ~78 degrees.
        """
        n_angles = 72
        theta = np.linspace(0.001, np.radians(78), n_angles)
        alpha_sum = np.zeros(len(Z_surface), dtype=float)
        sin_cos_sum = 0.0

        for t in theta:
            cos_t = np.cos(t)
            sin_t = np.sin(t)
            # Oblique incidence reflection
            r = (Z_surface * cos_t - self.Z0) / (Z_surface * cos_t + self.Z0)
            alpha_t = 1 - np.abs(r) ** 2
            alpha_sum += np.clip(alpha_t, 0, 1) * sin_t * cos_t
            sin_cos_sum += sin_t * cos_t

        alpha_random = alpha_sum / sin_cos_sum
        return np.clip(alpha_random, 0, 1)

    # ----------------------------------------------------------------
    # NRC and SAA
    # ----------------------------------------------------------------
    @staticmethod
    def _calc_nrc(freqs, alpha):
        """NRC = average of alpha at 250, 500, 1000, 2000 Hz."""
        nrc_freqs = [250, 500, 1000, 2000]
        values = []
        for f in nrc_freqs:
            idx = np.argmin(np.abs(freqs - f))
            values.append(alpha[idx])
        return round(np.mean(values), 2)

    @staticmethod
    def _calc_saa(freqs, alpha):
        """SAA = average at 12 third-octave bands from 200-2500 Hz."""
        saa_freqs = [200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500]
        values = []
        for f in saa_freqs:
            idx = np.argmin(np.abs(freqs - f))
            values.append(alpha[idx])
        return round(np.mean(values), 2)

    # ----------------------------------------------------------------
    # Main calculation
    # ----------------------------------------------------------------
    def calculate(
        self,
        thickness_mm: float = 100,
        flow_resistivity: float = 10000,
        air_gap_mm: float = 0,
        model: str = 'miki',
        freq_min: float = 20,
        freq_max: float = 20000,
        n_points: int = 500,
    ) -> PorousAbsorberResult:
        """
        Calculate absorption coefficient vs frequency.

        Args:
            thickness_mm: Absorber thickness in mm
            flow_resistivity: Flow resistivity in Pa.s/m^2
            air_gap_mm: Air gap behind absorber in mm
            model: 'delany_bazley' or 'miki'
            freq_min: Minimum frequency (Hz)
            freq_max: Maximum frequency (Hz)
            n_points: Number of frequency points

        Returns:
            PorousAbsorberResult with all computed data
        """
        thickness_m = thickness_mm / 1000.0
        air_gap_m = air_gap_mm / 1000.0
        freq = np.logspace(np.log10(freq_min), np.log10(freq_max), n_points)

        # Get material properties
        if model == 'delany_bazley':
            Zc, gamma = self._delany_bazley(freq, flow_resistivity)
        else:
            Zc, gamma = self._miki(freq, flow_resistivity)

        # Surface impedance
        Z_surface = self._surface_impedance(Zc, gamma, thickness_m, air_gap_m)

        # Absorption coefficients
        alpha_normal = self._normal_incidence_absorption(Z_surface)
        alpha_random = self._random_incidence_absorption(Z_surface)

        # Key metrics
        nrc = self._calc_nrc(freq, alpha_random)
        saa = self._calc_saa(freq, alpha_random)

        # Effective low frequency (where alpha_random > 0.5)
        eff_low = freq_max
        for i, a in enumerate(alpha_random):
            if a >= 0.5:
                eff_low = freq[i]
                break

        return PorousAbsorberResult(
            frequencies=freq,
            absorption_normal=alpha_normal,
            absorption_random=alpha_random,
            impedance_real=Z_surface.real,
            impedance_imag=Z_surface.imag,
            nrc=nrc,
            saa=saa,
            effective_low_freq=round(eff_low, 1),
            total_depth_mm=thickness_mm + air_gap_mm,
            model=model,
        )

    def compare_configurations(self, configs: List[dict]) -> List[PorousAbsorberResult]:
        """Calculate multiple configurations for comparison."""
        return [self.calculate(**cfg) for cfg in configs]

    def get_material_presets(self) -> Dict:
        """Return material presets dict."""
        return dict(self.MATERIALS)

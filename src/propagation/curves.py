"""
Distance <-> field-strength interpolation over the digitized FCC groundwave curves.

Provides:
  - field_strength(freq_khz, conductivity_mScm, distance_km) -> mV/m
  - distance_for_field_strength(freq_khz, conductivity_mScm, target_mvm) -> km

Both interpolate in log-log space (matching how the source charts are drawn)
across two axes: distance (using the digitized curve points) and conductivity
(bracketing between the two nearest of the 17 standard FCC conductivity
values, when the requested value isn't one of them exactly - e.g. real
ground conductivity from FCC Figure M3 is rarely a round number).

Frequency selection uses the FCC graph whose band covers the requested
frequency, not interpolation between graphs - this matches standard FCC
engineering practice (each graph is drawn for a specific frequency, valid
across its labeled band).
"""
import json
import os
import numpy as np

CONDUCTIVITIES = [5000, 40, 30, 20, 15, 10, 8, 7, 6, 5, 4, 3, 2, 1.5, 1, 0.5, 0.1]  # mS/m, high to low
CONDUCTIVITY_KEYS = ['5000','40','30','20','15','10','8','7','6','5','4','3','2','1.5','1','0.5','0.1']

_DATA_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data',
                          'digitized_curves', 'all_frequencies.json')

# Center frequencies of the 20 FCC graphs, in kHz. Band edges are the
# midpoints between adjacent centers, so every AM channel (535-1705 kHz,
# 10 kHz steps in the Americas) maps unambiguously to exactly one graph.
_CENTER_FREQS = [550,580,610,640,670,700,740,790,840,890,940,1000,1070,1140,1210,1290,1380,1470,1560,1655]


class GroundwaveCurves:
    def __init__(self, data_path=None):
        path = data_path or _DATA_PATH
        with open(path) as f:
            self._raw = json.load(f)
        self._merged_cache = {}  # (freq_key, conductivity_key) -> np.array([[km, mvm], ...])

    # ---- frequency selection ----

    def nearest_graph_frequency(self, freq_khz):
        """Return the FCC graph center frequency (kHz) whose band covers freq_khz."""
        diffs = [abs(freq_khz - c) for c in _CENTER_FREQS]
        return _CENTER_FREQS[int(np.argmin(diffs))]

    # ---- curve merging ----

    def _merged_curve(self, freq_key, conductivity_key):
        """Stitch the top (0.1-50km) and bottom (10-5000km) panels into one
        continuous, sorted, deduplicated curve. Top panel is used up to 10km;
        bottom panel beyond that (both agree to <1% in the overlap zone)."""
        cache_key = (freq_key, conductivity_key)
        if cache_key in self._merged_cache:
            return self._merged_cache[cache_key]

        entry = self._raw[str(freq_key)]
        top = entry['top'][conductivity_key]
        bottom = entry['bottom'][conductivity_key]

        top_part = [(km, mvm) for km, mvm in top if km <= 10.0]
        bottom_part = [(km, mvm) for km, mvm in bottom if km > 10.0]
        merged = sorted(top_part + bottom_part, key=lambda t: t[0])

        arr = np.array(merged)
        self._merged_cache[cache_key] = arr
        return arr

    # ---- single-conductivity interpolation (distance axis, log-log) ----

    def _field_strength_single_conductivity(self, freq_khz, conductivity_key, distance_km):
        freq_key = self.nearest_graph_frequency(freq_khz)
        curve = self._merged_curve(freq_key, conductivity_key)
        kms, mvms = curve[:,0], curve[:,1]
        if distance_km < kms[0] or distance_km > kms[-1]:
            raise ValueError(
                f"distance_km={distance_km} outside digitized range "
                f"[{kms[0]:.3f}, {kms[-1]:.1f}] for {conductivity_key} mS/m at {freq_khz} kHz"
            )
        log_mvm = np.interp(np.log10(distance_km), np.log10(kms), np.log10(mvms))
        return 10**log_mvm

    def _distance_single_conductivity(self, freq_khz, conductivity_key, target_mvm):
        freq_key = self.nearest_graph_frequency(freq_khz)
        curve = self._merged_curve(freq_key, conductivity_key)
        kms, mvms = curve[:,0], curve[:,1]
        if target_mvm > mvms[0] or target_mvm < mvms[-1]:
            raise ValueError(
                f"target_mvm={target_mvm} outside digitized range "
                f"[{mvms[-1]:.6f}, {mvms[0]:.2f}] for {conductivity_key} mS/m at {freq_khz} kHz"
            )
        # mvms is descending; np.interp needs increasing x, so reverse both arrays
        log_km = np.interp(np.log10(target_mvm), np.log10(mvms[::-1]), np.log10(kms[::-1]))
        return 10**log_km

    # ---- conductivity-axis bracketing (log-log) ----

    def _bracket_conductivities(self, conductivity_mScm):
        """Find the two standard conductivity curves bracketing the requested value.
        Returns (hi_key, lo_key, weight_hi) where weight_hi is 1.0 exactly at hi,
        0.0 exactly at lo (i.e. it's the log-space fraction of the way from lo to hi)."""
        if conductivity_mScm >= CONDUCTIVITIES[0]:
            return CONDUCTIVITY_KEYS[0], CONDUCTIVITY_KEYS[0], 1.0
        if conductivity_mScm <= CONDUCTIVITIES[-1]:
            return CONDUCTIVITY_KEYS[-1], CONDUCTIVITY_KEYS[-1], 1.0
        for i in range(len(CONDUCTIVITIES)-1):
            hi, lo = CONDUCTIVITIES[i], CONDUCTIVITIES[i+1]
            if lo <= conductivity_mScm <= hi:
                weight_hi = (np.log10(conductivity_mScm) - np.log10(lo)) / (np.log10(hi) - np.log10(lo))
                return CONDUCTIVITY_KEYS[i], CONDUCTIVITY_KEYS[i+1], weight_hi
        raise ValueError(f"conductivity_mScm={conductivity_mScm} not bracketable (unexpected)")

    # ---- public API ----

    def field_strength(self, freq_khz, conductivity_mScm, distance_km):
        """Field strength in mV/m at the given distance, for a station at freq_khz
        over ground of the given conductivity (mS/m). Interpolates in log-log space
        over both distance and conductivity."""
        hi_key, lo_key, weight_hi = self._bracket_conductivities(conductivity_mScm)
        if hi_key == lo_key:
            return self._field_strength_single_conductivity(freq_khz, hi_key, distance_km)
        v_hi = self._field_strength_single_conductivity(freq_khz, hi_key, distance_km)
        v_lo = self._field_strength_single_conductivity(freq_khz, lo_key, distance_km)
        log_v = weight_hi*np.log10(v_hi) + (1-weight_hi)*np.log10(v_lo)
        return 10**log_v

    def distance_for_field_strength(self, freq_khz, conductivity_mScm, target_mvm):
        """Inverse of field_strength(): distance (km) at which the field strength
        drops to target_mvm, for the given frequency and conductivity."""
        hi_key, lo_key, weight_hi = self._bracket_conductivities(conductivity_mScm)
        if hi_key == lo_key:
            return self._distance_single_conductivity(freq_khz, hi_key, target_mvm)
        d_hi = self._distance_single_conductivity(freq_khz, hi_key, target_mvm)
        d_lo = self._distance_single_conductivity(freq_khz, lo_key, target_mvm)
        log_d = weight_hi*np.log10(d_hi) + (1-weight_hi)*np.log10(d_lo)
        return 10**log_d


_default_instance = None

def get_default():
    global _default_instance
    if _default_instance is None:
        _default_instance = GroundwaveCurves()
    return _default_instance

def field_strength(freq_khz, conductivity_mScm, distance_km):
    return get_default().field_strength(freq_khz, conductivity_mScm, distance_km)

def distance_for_field_strength(freq_khz, conductivity_mScm, target_mvm):
    return get_default().distance_for_field_strength(freq_khz, conductivity_mScm, target_mvm)

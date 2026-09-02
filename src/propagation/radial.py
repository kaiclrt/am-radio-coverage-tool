"""
Single-radial groundwave coverage calculator.

Combines the three previous phases into one pipeline:
  1. Walk outward from a transmitter along a compass bearing, sampling
     ground conductivity (terrain.py) at intervals to build a mixed-path
     segment list.
  2. Feed that segment list into the Kirke method (kirke.py) to get field
     strength as a function of distance, or the distance to a target
     contour.
  3. Scale results by the station's actual field intensity at 1km (RMS),
     since the FCC's digitized curves (curves.py) are drawn assuming a
     100 mV/m at 1km reference - a real station's RMS is almost never
     exactly that.

On RMS: this must be the station's actual (licensed/measured) field
intensity at 1km, not derived from transmitter power alone - antenna
efficiency, ground system quality, and directional pattern all affect it
in ways a simple power formula can't capture reliably. This is a standard,
published quantity for any licensed AM station (found on the station's
license or proof-of-performance). A theoretical estimate is provided as a
clearly-labeled fallback for exploratory use only.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import terrain
from curves import GroundwaveCurves
from curves import get_default as get_curves
from kirke import Segment, mixed_path_distance_for_field_strength, mixed_path_field_strength

EARTH_RADIUS_KM = 6371.0088
CHART_REFERENCE_RMS_MVM = 100.0  # the FCC curves' own assumed field intensity at 1km


def destination_point(
    lat: float, lon: float, bearing_deg: float, distance_km: float, R: float = EARTH_RADIUS_KM
) -> tuple[float, float]:
    """Great-circle destination point, given a start point, bearing (degrees,
    0=North, 90=East), and distance (km)."""
    lat1 = np.radians(lat)
    lon1 = np.radians(lon)
    brng = np.radians(bearing_deg)
    d_R = distance_km / R
    lat2 = np.arcsin(np.sin(lat1)*np.cos(d_R) + np.cos(lat1)*np.sin(d_R)*np.cos(brng))
    lon2 = lon1 + np.arctan2(np.sin(brng)*np.sin(d_R)*np.cos(lat1),
                              np.cos(d_R) - np.sin(lat1)*np.sin(lat2))
    return float(np.degrees(lat2)), float(np.degrees(lon2))


def estimate_theoretical_rms(power_kw: float) -> float:
    """Estimate field intensity (mV/m) at 1km for a station of a given power,
    using the standard broadcast-engineering convention: 1 kW is treated as
    producing exactly the FCC groundwave curves' own reference value of
    100 mV/m at 1km (i.e. no scaling is needed to read the charts directly
    for a 1kW station), and field intensity scales with sqrt(power) for
    other power levels - E1 = 100 * sqrt(power_kw).

    This is NOT a theoretical lossless-antenna maximum (an earlier version
    of this function used 300*sqrt(P), derived from idealized far-field
    monopole theory - that number is real physics, but it isn't what
    broadcast engineers or the FCC's own charts actually assume in
    practice). Verified against a real worked example from a Philippine
    broadcast engineering course (TUP Visayas ECE 423): a 1kW station's
    distance-to-contour calculation required no RMS scaling at all to match
    the textbook's chart-reading answer (matching this convention, not the
    300*sqrt(P) one), and a 25kW example matched this convention to within
    ~6.5% (normal manual chart-reading tolerance) versus ~53% off using the
    old 300*sqrt(P) formula.

    Still an estimate, not a substitute for a station's actual
    licensed/measured RMS - antenna efficiency, ground system quality, and
    height/pattern effects all cause real stations to vary around this
    convention. Prefer real RMS data wherever available.
    """
    return 100.0 * np.sqrt(power_kw)


def build_conductivity_segments(
    tx_lat: float,
    tx_lon: float,
    bearing_deg: float,
    max_distance_km: float,
    sample_interval_km: float = 2.0,
    min_segment_km: float = 1.0,
) -> list[Segment]:
    """Walk outward from (tx_lat, tx_lon) along bearing_deg, sampling ground
    conductivity every sample_interval_km, and merge consecutive
    same-conductivity samples into (conductivity_mScm, length_km) segments
    suitable for the Kirke method.

    Note: this makes one terrain lookup per sample point, each of which may
    involve a live network request (ESA WorldCover). For a long radial at
    fine resolution this can mean many requests - sample_interval_km trades
    off segment-boundary precision against speed/request count.
    """
    n_samples = int(np.ceil(max_distance_km / sample_interval_km)) + 1
    sample_distances = np.linspace(0, max_distance_km, n_samples)

    conductivities: list[float] = []
    for d in sample_distances:
        lat, lon = destination_point(tx_lat, tx_lon, bearing_deg, d)
        cond, terrain_type, wc_class = terrain.get_conductivity(lat, lon)
        conductivities.append(cond)

    # Merge consecutive equal-conductivity samples into segments
    segments: list[Segment] = []
    seg_start_idx = 0
    for i in range(1, len(conductivities)):
        if conductivities[i] != conductivities[seg_start_idx]:
            seg_len = sample_distances[i] - sample_distances[seg_start_idx]
            segments.append((conductivities[seg_start_idx], seg_len))
            seg_start_idx = i
    # final segment
    seg_len = sample_distances[-1] - sample_distances[seg_start_idx]
    segments.append((conductivities[seg_start_idx], seg_len))

    # merge segments shorter than min_segment_km into a neighbor (avoids
    # degenerate near-zero-length segments from sampling noise)
    if len(segments) > 1:
        merged = [segments[0]]
        for cond, length in segments[1:]:
            if length < min_segment_km:
                prev_cond, prev_len = merged[-1]
                merged[-1] = (prev_cond, prev_len + length)
            else:
                merged.append((cond, length))
        segments = merged

    return segments


def radial_field_strength(
    tx_lat: float,
    tx_lon: float,
    bearing_deg: float,
    freq_khz: float,
    rms_at_1km_mvm: float,
    distance_km: float,
    sample_interval_km: float = 2.0,
    curves: GroundwaveCurves | None = None,
) -> float:
    """Field strength (mV/m) at distance_km along a radial from the
    transmitter, accounting for terrain-based conductivity changes and
    scaled to the station's actual RMS at 1km."""
    curves = curves or get_curves()
    segments = build_conductivity_segments(tx_lat, tx_lon, bearing_deg,
                                            distance_km, sample_interval_km)
    chart_value = mixed_path_field_strength(freq_khz, segments, distance_km, curves=curves)
    return chart_value * (rms_at_1km_mvm / CHART_REFERENCE_RMS_MVM)


def radial_distance_for_field_strength(
    tx_lat: float,
    tx_lon: float,
    bearing_deg: float,
    freq_khz: float,
    rms_at_1km_mvm: float,
    target_mvm: float,
    max_search_km: float = 500.0,
    sample_interval_km: float = 2.0,
    curves: GroundwaveCurves | None = None,
) -> float:
    """Distance (km) along a radial at which field strength drops to
    target_mvm - e.g. for finding a station's contour distance in a given
    direction. Builds segments out to max_search_km; raises if the target
    isn't reached within that range (increase max_search_km and retry)."""
    curves = curves or get_curves()
    segments = build_conductivity_segments(tx_lat, tx_lon, bearing_deg,
                                            max_search_km, sample_interval_km)
    # convert the target (real-world mV/m) into the chart's own reference
    # scale before doing the inverse lookup
    chart_target = target_mvm / (rms_at_1km_mvm / CHART_REFERENCE_RMS_MVM)
    return mixed_path_distance_for_field_strength(freq_khz, segments, chart_target, curves=curves)

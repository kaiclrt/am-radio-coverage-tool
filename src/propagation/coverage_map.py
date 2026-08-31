"""
Multi-radial coverage mapping - wraps the single-radial calculator
(radial.py) across multiple compass bearings to build a full coverage map.

Default is the 8 cardinal directions (N, NE, E, SE, S, SW, W, NW), per the
project's original scope, with optional finer angular resolution (16, 36,
360, or any n) when more precision is needed - e.g. for irregular terrain
where 8 radials would miss a significant conductivity feature.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from curves import get_default as get_curves
from radial import (
    destination_point,
    radial_distance_for_field_strength,
    radial_field_strength,
)

CARDINAL_BEARINGS_8 = {
    0: 'N', 45: 'NE', 90: 'E', 135: 'SE',
    180: 'S', 225: 'SW', 270: 'W', 315: 'NW',
}


def generate_bearings(n_radials=8):
    """Evenly-spaced compass bearings (degrees, 0=North, clockwise),
    starting at North. n_radials=8 gives the standard cardinal directions."""
    return list(np.linspace(0, 360, n_radials, endpoint=False))


def bearing_label(bearing_deg, n_radials=8):
    """Human-readable label for a bearing, e.g. 'N', 'NE'. Only meaningful
    for n_radials=8 (the standard cardinal set) - returns the numeric
    bearing as a string for other resolutions."""
    if n_radials == 8:
        return CARDINAL_BEARINGS_8.get(round(bearing_deg) % 360, f"{bearing_deg:.0f}")
    return f"{bearing_deg:.0f}"


def coverage_contour(tx_lat, tx_lon, freq_khz, rms_at_1km_mvm, target_mvm,
                      n_radials=8, max_search_km=500.0, sample_interval_km=2.0,
                      curves=None):
    """Distance to a target field-strength contour (e.g. an interference
    protection threshold, or a service-area boundary) along each of
    n_radials evenly-spaced bearings from the transmitter.

    Returns a list of dicts, one per bearing:
        {'bearing_deg', 'label', 'distance_km', 'lat', 'lon'}
    or, if that bearing's target isn't reached within max_search_km:
        {'bearing_deg', 'label', 'distance_km': None, 'lat': None, 'lon': None, 'error': str}
    A per-bearing failure doesn't abort the whole map - partial results are
    often still useful, and the error is preserved for the caller to
    inspect or retry with a larger max_search_km.
    """
    curves = curves or get_curves()
    bearings = generate_bearings(n_radials)
    results = []

    for bearing in bearings:
        entry = {'bearing_deg': bearing, 'label': bearing_label(bearing, n_radials)}
        try:
            distance = radial_distance_for_field_strength(
                tx_lat, tx_lon, bearing, freq_khz, rms_at_1km_mvm, target_mvm,
                max_search_km=max_search_km, sample_interval_km=sample_interval_km,
                curves=curves,
            )
            lat, lon = destination_point(tx_lat, tx_lon, bearing, distance)
            entry.update({'distance_km': distance, 'lat': lat, 'lon': lon})
        except ValueError as e:
            entry.update({'distance_km': None, 'lat': None, 'lon': None, 'error': str(e)})
        results.append(entry)

    return results


def coverage_profile(tx_lat, tx_lon, freq_khz, rms_at_1km_mvm,
                      n_radials=8, max_distance_km=200.0, n_points=20,
                      sample_interval_km=2.0, curves=None):
    """Field strength at n_points evenly-spaced distances (up to
    max_distance_km) along each of n_radials bearings - a full decay
    profile per radial, useful for graded/filled coverage maps rather than
    a single contour line.

    Returns a list of dicts, one per bearing:
        {'bearing_deg', 'label', 'points': [{'distance_km', 'field_mvm', 'lat', 'lon'}, ...]}
    """
    curves = curves or get_curves()
    bearings = generate_bearings(n_radials)
    query_distances = np.linspace(max_distance_km / n_points, max_distance_km, n_points)
    results = []

    for bearing in bearings:
        points = []
        for d in query_distances:
            field = radial_field_strength(
                tx_lat, tx_lon, bearing, freq_khz, rms_at_1km_mvm, float(d),
                sample_interval_km=sample_interval_km, curves=curves,
            )
            lat, lon = destination_point(tx_lat, tx_lon, bearing, d)
            points.append({'distance_km': float(d), 'field_mvm': field, 'lat': lat, 'lon': lon})
        results.append({
            'bearing_deg': bearing,
            'label': bearing_label(bearing, n_radials),
            'points': points,
        })

    return results

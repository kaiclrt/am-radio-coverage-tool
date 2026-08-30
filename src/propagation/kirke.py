"""
Kirke method (equivalent-distance method) for groundwave field strength over
mixed-conductivity paths, per 47 CFR 73.183(e).

As described in FCC MM Docket 88-510 (FCC 88-326), paragraph 24: "Section
73.183(e) of the FCC rules prescribes the procedure to be used when
calculating groundwave field strength over paths containing more than one
conductivity value (mixed paths). This is referred to as the equivalent
distance method or 'Kirke method' after H. L. Kirke who described several
calculation methodologies and compared results of calculations with actual
measurements in 1949."

Method, for a path crossing from conductivity sigma_1 into sigma_2 at
distance d1 from the transmitter:
  a) Read field strength E1 at d1, using the sigma_1 curve.
  b) Field strength is continuous across the boundary. Find the "equivalent
     distance" d_eq on the sigma_2 curve that would produce that same field
     strength E1 (i.e. invert the sigma_2 curve at value E1).
  c) The real remaining distance travelled within the new segment is added
     to d_eq, and the sigma_2 curve is read again at (d_eq + remaining
     distance) to get the field strength at the true distance.
  d) For a third, fourth, ... segment, repeat (b) and (c) sequentially -
     each boundary crossing converts the carried-over field strength into
     an equivalent distance on the new segment's curve, then advances by
     the real remaining distance in that segment.

This captures the "recovery effect" (and its opposite) when a path crosses
from poor to good conductivity ground, or vice versa - a pure single-curve
lookup at total distance would not.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from curves import get_default as get_curves


def _walk_segments(freq_khz, segments, query_distance_km, curves):
    """Shared walk logic for both mixed_path_field_strength() and
    mixed_path_distance_for_field_strength(). Returns (field_strength_mvm,
    segment_index, distance_into_segment_km, equivalent_distance_km) for
    whichever segment contains query_distance_km - or, if query_distance_km
    is None, walks the full path and returns the final field strength.
    """
    cumulative = 0.0
    current_field = None
    d_eq = 0.0  # equivalent distance offset within the *current* segment

    for i, (conductivity, length) in enumerate(segments):
        seg_start = cumulative
        seg_end = cumulative + length
        is_last_segment = (i == len(segments) - 1)
        stop_here = (query_distance_km is not None and query_distance_km <= seg_end) or \
                    (query_distance_km is None and is_last_segment)

        if i == 0:
            d_eq = 0.0  # first segment starts at the transmitter, no carry-over
        else:
            d_eq = curves.distance_for_field_strength(freq_khz, conductivity, current_field)

        if stop_here:
            if query_distance_km is None:
                effective_len = length
            else:
                effective_len = max(0.0, min(length, query_distance_km - seg_start))
            current_field = curves.field_strength(freq_khz, conductivity, d_eq + effective_len)
            return current_field, i, effective_len, d_eq

        current_field = curves.field_strength(freq_khz, conductivity, d_eq + length)
        cumulative = seg_end

    raise ValueError(
        f"query_distance_km={query_distance_km} exceeds total path length "
        f"({cumulative} km) covered by the given segments"
    )


def mixed_path_field_strength(freq_khz, segments, distance_km=None, curves=None):
    """Field strength (mV/m) along a mixed-conductivity radial, using the
    Kirke/equivalent-distance method.

    segments: list of (conductivity_mScm, length_km) tuples, in order from
        the transmitter outward. A single-segment list reduces to a plain
        single-conductivity lookup.
    distance_km: distance from the transmitter to evaluate at. Must be
        within the total length of the segments. If None, evaluates at the
        end of the full path (sum of all segment lengths).
    """
    if not segments:
        raise ValueError("segments must contain at least one (conductivity, length) pair")
    curves = curves or get_curves()
    field, *_ = _walk_segments(freq_khz, segments, distance_km, curves)
    return field


def mixed_path_distance_for_field_strength(freq_khz, segments, target_mvm, curves=None):
    """Inverse of mixed_path_field_strength(): the distance (km) from the
    transmitter at which the field strength drops to target_mvm, along a
    mixed-conductivity radial. Raises ValueError if the target is never
    reached within the given segments (i.e. field strength at the end of
    the path is still above target_mvm - extend the segment list to cover
    more distance).
    """
    if not segments:
        raise ValueError("segments must contain at least one (conductivity, length) pair")
    curves = curves or get_curves()

    cumulative = 0.0
    current_field = None
    for i, (conductivity, length) in enumerate(segments):
        seg_start = cumulative
        seg_end = cumulative + length

        if i == 0:
            d_eq = 0.0
        else:
            d_eq = curves.distance_for_field_strength(freq_khz, conductivity, current_field)

        field_at_seg_end = curves.field_strength(freq_khz, conductivity, d_eq + length)

        if field_at_seg_end <= target_mvm:
            # target is reached within this segment - invert directly
            d_at_target = curves.distance_for_field_strength(freq_khz, conductivity, target_mvm)
            within_segment = d_at_target - d_eq
            return seg_start + within_segment

        current_field = field_at_seg_end
        cumulative = seg_end

    raise ValueError(
        f"target_mvm={target_mvm} not reached within the given segments "
        f"(field strength at end of path is {current_field:.6f} mV/m, "
        f"total path length {cumulative} km); extend the segment list"
    )

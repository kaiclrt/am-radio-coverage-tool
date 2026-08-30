# Kirke (Equivalent-Distance) Mixed-Path Method

## Regulatory basis

47 CFR §73.183(e) prescribes the procedure for calculating groundwave field
strength over paths that cross more than one ground conductivity zone. Per
FCC MM Docket 88-510 (FCC 88-326, ¶24), this is the **"equivalent distance
method"** or **"Kirke method"**, after H. L. Kirke, who described several
calculation methodologies and compared results against actual measurements
in 1949. The same docket (¶25) notes the method is known to be imperfect,
but that no better alternative was found worth adopting after industry
review (AFCCE, and broadcast engineer Robert A. Jones, both endorsed
keeping it as-is) - so it remains the FCC's official method today.

Note: this is **not** the same as Millington's method, a different (also
respected) mixed-path technique described in the broadcast engineering
literature - see the digitization/curve-fitting discussion earlier in this
project's history for how that distinction was confirmed against the
primary source.

## The method

For a path crossing from conductivity σ₁ into σ₂ at distance d₁ from the
transmitter:

1. Read field strength E₁ at d₁, using the σ₁ curve.
2. Field strength is continuous across the boundary - it can't jump. Find
   the **equivalent distance** d_eq on the σ₂ curve that would produce
   that same field strength E₁ (i.e., invert the σ₂ curve at value E₁).
3. The real remaining distance travelled within the new segment is added
   to d_eq, and the σ₂ curve is read again at (d_eq + remaining distance)
   to get the field strength at the true distance.
4. For a third, fourth, ... segment, repeat steps 2-3 sequentially - each
   boundary crossing converts the carried-over field strength into an
   equivalent distance on the new segment's curve, then advances by the
   real remaining distance in that segment.

This captures the "recovery effect" (signal partially recovers when
crossing from poor to good conductivity ground) and its opposite
(degradation, crossing from good to poor) - a naive single-curve lookup at
total distance would miss both.

## Implementation

`src/propagation/kirke.py` provides:

- **`mixed_path_field_strength(freq_khz, segments, distance_km=None)`**
  Field strength (mV/m) at a given distance along a mixed-conductivity
  radial. `segments` is a list of `(conductivity_mScm, length_km)` tuples,
  in order outward from the transmitter. If `distance_km` is omitted,
  evaluates at the end of the full path.

- **`mixed_path_distance_for_field_strength(freq_khz, segments, target_mvm)`**
  Inverse: the distance (km) at which field strength drops to `target_mvm`
  along the path. Needed for contour-distance calculations (e.g. "how far
  until the signal drops to the interference-protection threshold").

Both build directly on the interpolation layer (`curves.py`) from the
previous phase - specifically its forward and inverse single-conductivity
lookups, which are exactly the two primitives steps 1-2 above need.

## Validation

Tested in `tests/test_kirke.py` (14 tests):

- **Degenerate case**: splitting a *uniform*-conductivity path into
  multiple fake segments must give an identical result to treating it as
  one segment - this is the simplest possible correctness check, since any
  bug in the boundary-crossing math would show up as a discontinuity even
  when there's no real conductivity change.
- **Bounding**: a genuinely mixed path's result must fall strictly between
  what either conductivity alone would give over the same total distance -
  the method blends, it doesn't extrapolate outside that range.
- **Recovery effect**: explicitly tested that a poor→good transition
  leaves the signal stronger than if poor conductivity had continued the
  whole way (matching the FCC/NBS description of what a correct mixed-path
  method must capture).
- **Round-trip**: `mixed_path_field_strength` then
  `mixed_path_distance_for_field_strength` recovers the original distance,
  across both 2-segment and 4-segment paths.
- **Monotonicity**: field strength keeps decreasing across every segment
  boundary in a 4-segment path (no discontinuous jumps).

# Multi-Radial Coverage Map

## What this is

Wraps the single-radial calculator (`radial.py`) across multiple compass
bearings to build a full coverage map, per the project's original scope:
"minimum of the eight cardinal directions and optional scaling as needed
for more accurate calculations."

This is almost entirely orchestration on top of already-validated pieces -
the real engineering work (curve digitization, interpolation, terrain
conductivity, Kirke method) was done in the previous four phases.

## Two output modes

**`coverage_contour(...)`** - distance to a single target field-strength
contour (e.g. a protected-service or interference threshold) along each
bearing. Returns one distance per bearing - useful for drawing a coverage
*outline*.

**`coverage_profile(...)`** - full field-strength-vs-distance curve along
each bearing (multiple sample points out to a max distance). Returns a
decay profile per bearing - useful for a graded/filled coverage map (e.g.
color-coded by signal strength), not just an outline.

Both return the same basic shape: a list of per-bearing dicts, each
carrying the bearing's compass label (`N`, `NE`, etc. for the standard
8-radial case), distance(s), and destination lat/lon coordinates - ready
to hand to a mapping library without further geometry work.

## Angular resolution

`n_radials` defaults to 8 (the standard cardinal directions), but accepts
any value - 16, 36, 360, etc. - for finer resolution where terrain is
irregular enough that 8 radials might miss a significant conductivity
feature (e.g. a coastline or mountain range that a cardinal bearing
happens to run parallel to rather than across). `generate_bearings(n)`
produces evenly-spaced bearings starting at North; `bearing_label()` gives
compass labels only for the 8-radial case (finer resolutions get numeric
labels, since "NNE" naming is somewhat arbitrary as resolution increases -
easy to add later if actually needed).

## Partial-failure handling

`coverage_contour`'s target field strength might not be reached within
`max_search_km` along some bearings (e.g. a very poor-conductivity
direction where the signal drops below target well before the search
range's end, versus a very good-conductivity direction that never quite
drops that low within a modest search range). Rather than aborting the
whole map over one bad bearing, each bearing's result independently
carries either a distance or an error message - a map with 7 valid
bearings and 1 clearly-flagged failure is more useful than no map at all.

## Validation

Tested in `tests/test_coverage_map.py` (13 tests, all offline via mocked
terrain data):

- Bearing generation: correct cardinal directions/labels for the default
  8-radial case, correct even spacing for other resolutions (16, 36).
- Uniform terrain in all directions gives identical contour distances on
  every bearing (the simplest possible sanity check).
- Deliberately asymmetric terrain (poor conductivity to the north, good
  elsewhere) correctly produces a shorter contour distance specifically on
  the northern bearing - confirms the terrain sampling is actually
  direction-sensitive, not just running the same calculation 8 times.
- Per-bearing failure handling doesn't crash the whole map.
- Profile mode: correct point counts, monotonic decay within each bearing,
  valid coordinates on every point.

No live/real-network test yet for this module specifically - it's a thin
wrapper over `radial.py`, which already has live end-to-end validation
against real Manila coordinates from the previous phase.

## Not yet built

- No visualization/rendering (this module produces structured data only -
  plotting on an actual map is a separate concern, likely for the web UI
  phase).
- No interpolation *between* radials (e.g. filling in a smooth polygon
  between 8 contour points) - the caller currently gets raw per-bearing
  results and would need to do that themselves if drawing a filled shape
  rather than just markers/points.

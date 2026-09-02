# Single-Radial Coverage Calculator

## What this is

The point where the previous three phases (curve digitization,
interpolation, terrain-based conductivity, Kirke mixed-path method) come
together into an actual usable calculation: given a transmitter location,
frequency, power (as RMS at 1km), and a compass bearing, predict field
strength at any distance along that bearing - or find the distance at
which field strength drops to a target value (a coverage/interference
contour).

## Pipeline

1. **`destination_point(lat, lon, bearing_deg, distance_km)`** - standard
   great-circle formula, used to walk outward from the transmitter along a
   bearing.
2. **`build_conductivity_segments(...)`** - samples ground conductivity
   (via `terrain.py`) at regular intervals along the radial, then merges
   consecutive equal-conductivity samples into `(conductivity, length)`
   segments. Segments shorter than `min_segment_km` (default 1km) are
   absorbed into a neighbor, so a single anomalous sample (e.g. one
   WorldCover pixel of a small pond) doesn't produce a spurious tiny
   segment.
3. **`radial_field_strength(...)`** / **`radial_distance_for_field_strength(...)`**
   - feed the segment list into the Kirke method (`kirke.py`), then scale
   the result by the station's actual RMS at 1km relative to the FCC
   curves' own assumed reference (100 mV/m at 1km - the "INVERSE DISTANCE
   100 mV/m AT 1 km" asymptote drawn on every FCC groundwave graph).

## On RMS (station field intensity at 1km)

This must be the station's actual, licensed/measured field intensity at
1km - **not** derived from transmitter power alone. Antenna efficiency,
ground system quality, height, and (for directional arrays) azimuth all
affect real-world RMS in ways a simple formula can't capture reliably.
This is a standard published quantity found on a station's license or
proof-of-performance measurements.

`estimate_theoretical_rms(power_kw)` is provided as a fallback for use when
only power is known - it applies the standard broadcast-engineering
convention (E₁ = 100·√P mV/m at 1km, i.e. 1kW is treated as directly
producing the FCC charts' own 100 mV/m-at-1km reference), not a
theoretical lossless-antenna physics maximum (an earlier version of this
function used 300·√P, derived that way - see CHANGELOG.md for how that
was found to be wrong, overestimating coverage by ~53% in a real
worked-example comparison against a Philippine broadcast engineering
course). Real stations still vary around this convention depending on
antenna efficiency and ground system quality - prefer actual licensed RMS
data wherever available.
fall meaningfully short of in practice. Prefer real RMS data whenever
available.

## Performance note

`build_conductivity_segments` makes one terrain lookup per sample point,
each potentially a live network request to ESA WorldCover. For a long
radial at fine resolution, this can mean many requests -
`sample_interval_km` (default 2km) trades off segment-boundary precision
against speed/request count. No caching or coarse-then-refine strategy is
implemented yet; if this proves too slow in practice, that's a reasonable
follow-up optimization (e.g. cache samples across multiple bearings that
happen to pass near the same location, or start coarse and only refine
resolution near detected boundaries).

## Validation

Tested in `tests/test_radial.py` (11 offline + 1 live):

- Great-circle math checked against the well-known fact that ~111.19km is
  very close to 1 degree of latitude anywhere on Earth.
- Segment-building tested with mocked terrain data (no live network needed
  for most tests) - uniform terrain, a single transition, and spurious
  short-segment merging.
- RMS scaling confirmed exactly linear (3x RMS -> exactly 3x field
  strength), and confirmed to exactly match a plain curve lookup when RMS
  equals the chart's own 100 mV/m reference.
- Round-trip (field strength -> distance -> field strength) consistency
  across a 2-segment mixed path.
- One live smoke test (opt-in via `RUN_LIVE_TERRAIN_TESTS=1`) runs a real
  radial out of Manila and confirms monotonic decay - the actual
  end-to-end integration test against live WorldCover data.

## Not yet built

- No 8-cardinal-radial wrapper yet (this module handles one bearing at a
  time) - that's the next phase.
- No handling of directional antenna patterns (RMS is currently treated as
  constant with azimuth) - would need per-bearing RMS input for
  directional stations.

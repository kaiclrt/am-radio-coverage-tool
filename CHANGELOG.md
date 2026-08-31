# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project intends to follow [Semantic Versioning](https://semver.org/)
once it reaches a first tagged release (currently pre-release, 0.1.0).

## [Unreleased]

### Added
- FCC groundwave curve digitization for all 20 official frequency bands
  (535–1705 kHz), extracted from the FCC's vector PDF graphs and validated
  by pixel-perfect overlay against the source charts. See
  `docs/digitization.md`.
- Distance↔field-strength interpolation (log-log, both directions),
  including interpolation across ground conductivity values that fall
  between the 17 standard FCC curves. See `docs/digitization.md`.
- Terrain-based global ground conductivity estimation: ESA WorldCover
  (free, CC-BY-4.0, 10m resolution) land cover classification, mapped to
  conductivity via the FCC's own 1939 terrain-conductivity table, with
  offline ocean/lake disambiguation. Built as a free alternative after
  confirming ITU-R P.832 (the obvious "official" global source) is a paid
  product, not redistributable. See `docs/conductivity.md`.
- Kirke (equivalent-distance) mixed-path method per 47 CFR §73.183(e), for
  groundwave field strength calculations across paths crossing multiple
  conductivity zones. See `docs/kirke_method.md`.
- Single-radial coverage calculator: combines the curve, conductivity, and
  Kirke-method layers into `radial_field_strength()` and
  `radial_distance_for_field_strength()`, with RMS scaling relative to the
  FCC curves' own 100 mV/m-at-1km reference. See `docs/radial_calculator.md`.
- Multi-radial coverage mapping: `coverage_contour()` and
  `coverage_profile()`, wrapping the single-radial calculator across the 8
  cardinal directions by default, with support for arbitrary angular
  resolution. See `docs/coverage_map.md`.
- CI via GitHub Actions: runs the full offline test suite (pytest) on every
  push/PR to `main`, across Python 3.10, 3.11, and 3.12.
- Installation instructions and dependency groups (`[dev]`, `[terrain]`) in
  README.md.
- Test suite: 61 offline tests plus opt-in live-network tests
  (`RUN_LIVE_TERRAIN_TESTS=1`) covering real ESA WorldCover queries and a
  full end-to-end radial calculation against real Manila, Philippines
  coordinates.

### Fixed
- Inverted weight bug in conductivity-bracketing interpolation
  (`curves.py`): a conductivity value that exactly matched one of the 17
  standard FCC curves was silently returning its *neighboring* curve's
  data instead of its own, due to a sign inversion in the log-space
  interpolation weight. Caught by testing before it reached any
  downstream calculation.
- Off-by-epsilon bug in radial segment building (`radial.py`): an
  unnecessary defensive offset at the transmitter's own coordinates was
  shaving a tiny amount off the total path length, causing boundary
  errors in the Kirke lookup at the far end of a radial.
- Curve-ordering bug in bottom-panel digitization (`gwdigitizer/core.py`):
  greedy nearest-value matching occasionally swapped adjacent
  conductivities (e.g. 20/30 mS/m) when their field-strength values were
  numerically close. Fixed by switching to rank-order assignment, since
  groundwave curves are physically guaranteed non-crossing.
- ESA WorldCover tile-fetch handling for points over open ocean
  (`terrain.py`): WorldCover only publishes tiles containing land, so
  points far from any coast return HTTP 404. Added a fallback that treats
  a missing tile as a signal of open ocean, confirmed against an offline
  landmask before concluding salt water (rather than silently
  misclassifying on any fetch error).
- Curve-label clustering for tightly-spaced legend entries at higher AM
  frequencies (`gwdigitizer/core.py`): distance-based clustering
  incorrectly merged adjacent conductivity labels when leader-line
  endpoints were within a few pixels of each other; switched to
  pair-based grouping.
- Low-frequency curve-merge handling (`gwdigitizer/core.py`): at the
  lowest AM frequencies (550–640 kHz), 2–3 high-conductivity curves are
  visually merged into a single line in the FCC's own source artwork
  (genuinely near-identical at that frequency, not a digitization
  artifact). Detected via monotonic alignment against the complete
  bottom-panel curve set, with the affected conductivity's data
  documented as duplicated from its nearest neighbor rather than silently
  treated as independently measured.

### Changed
- Consolidated dependency management to `pyproject.toml` only. The
  previous `requirements.txt` had already drifted out of sync (missing
  the terrain module's dependencies), which was itself the motivating
  example for removing it.

### Deferred
- FCC `m3.seq` ground conductivity data (continental US, higher precision
  than the terrain-based estimate) - the terrain-based approach already
  covers the US, just less precisely; `m3.seq` integration is a documented
  future upgrade, not a current gap.
- Web UI.

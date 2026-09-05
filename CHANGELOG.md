# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project intends to follow [Semantic Versioning](https://semver.org/)
once it reaches a first tagged release (currently pre-release, 0.1.0).

## [Unreleased]

### Security
- Hardened the Docker deployment after an audit of it (see
  `docs/api.md`'s hardening list, now items 8-10):
  - **Published container ports bound to `127.0.0.1`** instead of
    `0.0.0.0`. The API has no auth and CORS only constrains browsers, so
    a `0.0.0.0` publish put the raw API (and the raw UI) on the whole
    LAN - confirmed with a headerless `curl` against `:5000`. nginx still
    reaches the API over the internal compose network; flip the frontend
    to `8080:80` to expose the UI deliberately.
  - **`ProxyFix(x_for=1)` on the API** (`api/app.py`): behind nginx,
    `flask-limiter` and the request log were keying on nginx's container
    IP, so the coverage rate limit was one global bucket shared by all
    users and every log line showed `172.18.0.x`. Now they see the real
    client IP from `X-Forwarded-For`. `x_for=1` is safe precisely because
    the port binding above keeps nginx the only path in (no forged
    `X-Forwarded-For`). nginx also now sends `X-Forwarded-Proto`.
  - **API container runs as non-root** (`appuser`, uid 1000) in
    `api/Dockerfile` - nothing at runtime needs root.
  - `FRONTEND_ORIGIN` parsing now tolerates whitespace around commas.

### Added
- Docker support (`docker-compose.yml`, `api/Dockerfile`,
  `frontend/Dockerfile`): `docker compose up --build` runs the whole web
  UI (API + frontend) with only Docker installed, no local Python/Node
  setup. The frontend's nginx reverse-proxies `/api/*` to the api
  container server-side, so the browser only ever talks to one origin and
  flask-cors's restriction never comes into play in this setup. Building
  and running the real containers (not just writing the Dockerfiles)
  surfaced four genuine bugs, all fixed:
  - `api/app.py` bound Flask's default `127.0.0.1`, invisible to anything
    outside its own container (including another container and Docker's
    own port publishing) - now binds `0.0.0.0` (override via `FLASK_HOST`).
  - `python:3.12-slim` is missing `libexpat.so.1`, which rasterio's wheel
    dynamically links against at import time (not at install time) -
    `terrain.py`'s broad `except ImportError` silently swallowed this into
    a generic 500. Fixed in `api/Dockerfile` with `apt-get install
    libexpat1`.
  - nginx cached the `api` container's IP at startup and never
    re-resolved it, so every request silently hung after `api` got
    recreated (e.g. rebuilding it alone during development) until
    `frontend` was manually restarted. Fixed with a Docker-DNS `resolver`
    + variable indirection in `frontend/nginx.conf`.
  - nginx's 60s default `proxy_read_timeout` was too tight for the
    coverage endpoints - a real request during testing took ~3.5 minutes
    on a slow connection (no code defect, just live network calls to ESA
    WorldCover taking a while). Raised to 300s.
  - (found alongside, in the core engine rather than Docker/nginx):
    `coverage_contour()`'s per-bearing isolation only caught `ValueError`,
    so a transient `RasterioIOError` from one flaky terrain lookup crashed
    the whole multi-bearing request instead of failing just that bearing -
    see the `coverage_map.py` entry below.
  See `docs/api.md`'s "Running with Docker" section for the full story on
  each.

### Fixed
- **`coverage_contour()` crashed the whole map on a non-`ValueError`
  per-bearing failure** (`coverage_map.py`): the per-bearing `try/except`
  only caught `ValueError` (target not reached within `max_search_km`),
  but a transient terrain-lookup failure - e.g.
  `rasterio.errors.RasterioIOError` from a truncated network read
  streaming an ESA WorldCover tile - isn't a `ValueError`, so it
  propagated past the per-bearing boundary and crashed the entire
  multi-bearing request with a generic 500, contradicting the function's
  own documented contract ("a per-bearing failure doesn't abort the whole
  map"). Reproduced live (not hypothetically) via the Docker setup when a
  fresh WSL2 network dropped a tile read mid-transfer. Fixed by catching
  `Exception` broadly in that loop, matching the same reasoning `terrain.py`
  already uses for its own broad-except ocean-fallback path (and why
  ruff's BLE rule is deliberately disabled project-wide - see
  `pyproject.toml`). `coverage_profile()` has the same theoretical
  exposure and is not yet fixed - see `docs/coverage_map.md`'s "Known
  limitations" for why it's deferred (not currently used by the web UI).

### Added
- Web UI frontend scaffold (`frontend/`): Vite + React + TypeScript,
  Tailwind CSS v4, shadcn/ui (source copied into `frontend/src/components/ui/`),
  Leaflet via react-leaflet, ESLint + Prettier - the stack locked in
  `docs/web_ui_stack.md`. Implements the full input/output interface from
  `docs/web_ui_design.md`: the three target-field-strength modes (Primary
  Service Contour / Day-Night Protection Contours / Custom Contour, with
  Day-Night rendering two contours on the map at once) and the two
  power/RMS modes (Licensed/Measured RMS / Estimate from Transmitter
  Power, the latter with an editable result field and a persistent warning
  banner). Talks to the existing Flask API in `api/` (via the Vite
  dev-server proxy) rather than duplicating any propagation logic;
  handles the API's per-bearing partial-failure shape (`distance_km: null`
  + `error`) so one bad radial doesn't break the map, and respects its
  rate limits and input bounds (explicit-submit recalculation, debounced
  RMS estimate). CI (`.github/workflows/tests.yml`) gains a `frontend` job
  running ESLint, Prettier `--check`, and a type-checked build. No
  lockfile is committed, mirroring the Python side's version-ranges-only
  dependency policy.

### Fixed
- **Sea-facing bearings from a coastal transmitter crashed terrain
  classification** (`terrain.py`): ESA WorldCover masks open water to `0`
  (nodata) inside tiles that also cover land, but `classify_terrain()` only
  had a fallback for a *missing* tile (HTTP 404). A `0` therefore hit the
  "unrecognized class code" path and raised, so e.g. the SW/W bearings from
  a Manila transmitter (straight out over Manila Bay) failed with
  `Unrecognized WorldCover class code: 0` while land bearings succeeded -
  surfaced by the web frontend, which shows per-bearing errors. Fixed by
  routing nodata through the same offline-landmask check as a missing tile
  (not-land → `salt_water`; genuine land → still raises, since nodata over
  real land is a coastline-registration gap, not a sea path). Regression
  tests added in `tests/test_terrain.py` (`TestNodataHandling`, mocked - no
  network).

### Fixed
- **API error handler was swallowing intentional HTTP responses**
  (`api/app.py`): the catch-all `@app.errorhandler(Exception)` added for
  clean error messages caught *everything*, including flask-limiter's
  `429 Too Many Requests`, silently converting it into a generic `500`
  and defeating the rate limiter entirely. Caught by testing (a
  dedicated test asserting `429` appears among repeated-request statuses
  failed until this was fixed) before it shipped. Fixed by excluding
  `werkzeug.exceptions.HTTPException` from the catch-all.

### Fixed
- **`estimate_theoretical_rms()` used the wrong formula** (`radial.py`): was
  `300·√P` mV/m, a theoretical lossless-monopole physics maximum nobody
  actually achieves. Found while comparing this tool against a real
  worked example from a Philippine broadcast engineering course (TUP
  Visayas ECE 423, "AM Coverage Mapping and Prediction," which uses the
  same FCC charts and the same Kirke/equivalent-distance method this
  project independently arrived at). The textbook's convention treats
  1kW as directly producing the chart's own 100 mV/m-at-1km reference
  value (`100·√P`), with no additional scaling for a 1kW station -
  verified by reproducing two of the textbook's own worked examples: a
  1kW case matched the textbook's manually-read answer to within ~2.5%,
  while the old 300·√P formula was off by ~53% on a 25kW case. Fixed to
  `100·√P`, matching actual broadcast-engineering and FCC-chart
  convention rather than idealized physics.

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

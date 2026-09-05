# API Layer

Thin Flask JSON API wrapping `src/propagation/` for the web frontend - all
propagation logic stays exactly where it already lives and is tested; this
layer just exposes it over HTTP.

## Endpoints

### `GET /api/health`
Liveness check. Returns `{"status": "ok"}`.

### `POST /api/estimate-rms`
Power (kW) → estimated field intensity at 1km (mV/m), via
`estimate_theoretical_rms()` (broadcast-engineering convention, see
`docs/radial_calculator.md`).

```json
// Request
{"power_kw": 5}
// Response
{"rms_at_1km_mvm": 223.60679774997897}
```

### `POST /api/coverage/contour`
Distance to one or more target field-strength contours, per bearing.
Supports all three target modes from `docs/web_ui_design.md` via the
`targets` object - a single entry for Primary Service Contour or Custom
Contour, two entries (`day`/`night`, or any labels) for Day/Night mode.

```json
// Request
{
  "tx_lat": 14.6, "tx_lon": 121.0, "freq_khz": 1140,
  "rms_at_1km_mvm": 223.6,
  "targets": {"day": 0.5, "night": 2.5},
  "n_radials": 8, "max_search_km": 500, "sample_interval_km": 2.0
}
// Response
{
  "contours": {
    "day":   [{"bearing_deg": 0, "label": "N", "distance_km": ..., "lat": ..., "lon": ...}, ...],
    "night": [{"bearing_deg": 0, "label": "N", "distance_km": ..., "lat": ..., "lon": ...}, ...]
  }
}
```

A per-bearing failure (target not reached within `max_search_km`) doesn't
fail the whole request - that bearing's entry has `distance_km: null` and
an `error` field instead (same partial-failure design as
`coverage_contour()` itself - see `docs/coverage_map.md`).

### `POST /api/coverage/profile`
Full field-strength-vs-distance decay curve per bearing (for graded/filled
maps rather than a single outline).

```json
// Request
{
  "tx_lat": 14.6, "tx_lon": 121.0, "freq_khz": 1140,
  "rms_at_1km_mvm": 223.6,
  "n_radials": 8, "max_distance_km": 200, "n_points": 20, "sample_interval_km": 2.0
}
// Response
{"profile": [{"bearing_deg": 0, "label": "N", "points": [{"distance_km", "field_mvm", "lat", "lon"}, ...]}, ...]}
```

## Validation

All endpoints validate required fields and value ranges before calling
into the propagation engine, returning `400` with a descriptive `error`
message on bad input rather than letting an unhandled exception surface
as a generic 500.

## Hardening

Six items, all implemented and verified (both via `tests/test_api.py` and
a live smoke test against a real running server, not just Flask's
in-process test client):

1. **Debug mode off by default.** Flask's debug mode exposes Werkzeug's
   interactive debugger, which allows arbitrary code execution if
   reachable by anyone but the developer. `api/app.py`'s `__main__` block
   only enables it if `FLASK_DEBUG=1` is explicitly set - never on by
   accident.

2. **Bounded expensive parameters.** `terrain.get_conductivity()` makes a
   live network request per sample point, so unbounded `n_radials`,
   `n_points`, or a tiny `sample_interval_km` could trigger an excessive
   number of them (accidental typo or deliberate abuse). Individual caps:
   `n_radials` ≤ 360, `n_points` ≤ 200, `sample_interval_km` ≥ 0.5km,
   `max_search_km`/`max_distance_km` ≤ 5000km (matching the digitized
   curves' own range). A **combined** budget check
   (`n_radials × search_distance / sample_interval_km ≤ 2000`) also
   exists, since individually-valid values can still combine to an
   excessive total - caught by a dedicated regression test.

3. **Clean error handling.** A catch-all `@app.errorhandler(Exception)`
   logs full detail server-side but returns a generic message to the
   client, so unexpected errors never leak stack traces or internal file
   paths. Deliberately excludes `werkzeug.exceptions.HTTPException` (404,
   429, and other intentional HTTP-level responses) - an earlier version
   of this handler caught *everything*, which silently converted
   flask-limiter's `429 Too Many Requests` into a generic `500`, defeating
   the rate limiter. Caught by testing, fixed before it shipped.

4. **Rate limiting** (`flask-limiter`): 60/minute default across all
   endpoints, 10/minute on the two coverage endpoints specifically (the
   expensive ones), 30/minute on the RMS estimator. In-memory storage,
   sufficient for a single-process deployment - would need Redis or
   similar if ever scaled to multiple workers.

5. **Restricted CORS.** Locked to the frontend dev server's origin(s)
   (`http://localhost:5173`, `http://127.0.0.1:5173` by default) rather
   than wide open, via `flask-cors`. Override with the `FRONTEND_ORIGIN`
   env var (comma-separated) for other deployments.

6. **Request logging.** Every request logs its method/path/remote address
   on entry and its status code on completion, via Python's standard
   `logging` module.

7. **Binds `0.0.0.0` by default**, not Flask's own `127.0.0.1` default -
   needed so the server is reachable from outside its own process
   namespace (another Docker container, a separate deployment host), not
   just from the same machine. Not a new exposure beyond what items 1-6
   above already assume (no auth, no HTTPS - see below); override with
   `FLASK_HOST` if a deployment specifically needs to restrict this.
   Discovered via testing the Docker setup (see "Running with Docker"
   below) - `127.0.0.1` inside a container is invisible to everything
   outside that exact container, including Docker's own port publishing.

### What's still deferred

No authentication (fine for local/personal use; would need adding before
any multi-user or public deployment), no HTTPS (a local-development
concern, not this layer's job), and the rate-limit storage is in-memory
(single-process only). None of these matter for the tool's current scope
but are worth revisiting before any real deployment beyond local
development.

## Running locally

```bash
pip install -e .[api,terrain]
python api/app.py
```

`terrain` (rasterio + global-land-mask) is needed alongside `api` for any
*real* coverage calculation - `coverage_contour()`/`coverage_profile()`
call `terrain.get_conductivity()` per sample point. Without it the server
still starts and `/api/health`/`/api/estimate-rms` work fine, but the two
coverage endpoints fail with a generic 500 (the underlying `ImportError`
is logged server-side, not returned to the client - see the error-handler
note above).

Serves on `http://127.0.0.1:5000` in Flask's development server (not for
production use - see Flask's own docs for WSGI deployment options if this
is ever deployed beyond local development).

CORS is enabled (`flask-cors`) since the frontend (Vite dev server) runs
on a different port during development.

## Running with Docker

```bash
docker compose up --build
```

Builds and runs two containers (see `docker-compose.yml`, `api/Dockerfile`,
`frontend/Dockerfile`): the API on `http://localhost:5000`, and the built
frontend served by nginx on `http://localhost:8080`. nginx reverse-proxies
`/api/*` to the api container server-side (`frontend/nginx.conf`), so the
browser only ever talks to one origin (`:8080`) and flask-cors's
restriction never comes into play in this setup - `FRONTEND_ORIGIN` in
`docker-compose.yml` only matters for something hitting `:5000` directly.

Two real bugs were only found by actually building and running this, not
by inspecting the Dockerfile - consistent with this project's "validate
against real data/behavior, not just that it looks right" philosophy
(see `CONTRIBUTING.md`):

- **`api/app.py` bound `127.0.0.1`** (Flask's own default), which is
  invisible to anything outside that exact container - including another
  container on the same Docker network and Docker's own port publishing.
  Confirmed via a 502 from nginx and a failed `curl` straight at the
  published port. Fixed by binding `0.0.0.0` (see hardening item 7 above).
- **`libexpat.so.1` missing from the `python:3.12-slim` base image** -
  rasterio's wheel bundles GDAL/PROJ, but GDAL still dynamically links
  against a couple of the *slim* image's stripped-out system libraries.
  The import failure was swallowed by `terrain.py`'s
  `except ImportError: _HAS_RASTERIO = False` (see `docs/conductivity.md`),
  surfacing only as a generic 500 - the real cause only showed up by
  running `python -c "import rasterio"` inside the built container. Fixed
  in `api/Dockerfile` with `apt-get install libexpat1`.

## Testing

`tests/test_api.py` (26 tests) uses Flask's test client with mocked
terrain data (same pattern as the rest of the test suite - no live
network needed), covering both the original endpoint behavior and the
hardening added afterward (input bounds, combined sample-budget
enforcement, rate limiting genuinely firing, debug-mode-off default).
Additionally verified with a real live HTTP smoke test during development
(actual running server, real `requests` calls, checking CORS headers and
rate-limit behavior against genuine repeated requests) to confirm
behavior matches a genuinely running server, not just the test harness -
this is how the error-handler bug in item 3 above was actually caught.

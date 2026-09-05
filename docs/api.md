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

Ten items, all implemented and verified (both via `tests/test_api.py` and
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

8. **Published container ports bound to `127.0.0.1`.** Because the API
   has no auth and CORS only constrains browsers (a `curl`/script sends
   no `Origin` and doesn't care about the response headers), a `0.0.0.0`
   port publish would put the raw API - and the raw UI - on the whole
   LAN. `docker-compose.yml` binds both to loopback
   (`127.0.0.1:5000`, `127.0.0.1:8080`); nginx still reaches the API over
   the internal compose network. Flip the frontend to `8080:80` to
   expose the UI on purpose.

9. **`ProxyFix` for one proxy hop.** `flask-limiter` and the request log
   key on `request.remote_addr`, which behind nginx is nginx's own
   container IP - so every user shares one rate-limit bucket and the log
   shows `172.18.0.x` for everyone. `api/app.py` wraps the app in
   `werkzeug.middleware.proxy_fix.ProxyFix(x_for=1)` so both see the real
   client IP from `X-Forwarded-For`. `x_for=1` (trust exactly one hop) is
   only safe because item 8 keeps the raw port off the network: nginx is
   the sole path in, so a client can't inject a forged `X-Forwarded-For`.
   Run with no proxy and there's simply no header to read - it falls back
   to the real `remote_addr`.

10. **API container runs as non-root.** `api/Dockerfile` creates an
    unprivileged `appuser` (uid 1000) and `USER`s to it before `CMD` -
    nothing at runtime needs root (port 5000 isn't privileged, the
    process only reads its own files and makes outbound HTTPS). Shrinks
    the blast radius of a container-escape or code-exec bug and stops an
    accidental write from clobbering system files. The `nginx` image
    keeps its default model (root master, workers drop to the `nginx`
    user).

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

Several real bugs were only found by actually building and running this,
not by inspecting the Dockerfile - consistent with this project's
"validate against real data/behavior, not just that it looks right"
philosophy (see `CONTRIBUTING.md`):

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
- **nginx cached a stale IP for the `api` upstream.** A static
  `proxy_pass http://api:5000/...` resolves that hostname once (at nginx
  startup) and keeps the resolved IP for the worker's lifetime. Docker
  assigns the `api` container a *new* internal IP every time it's
  recreated (e.g. `docker compose up -d --build api` after a code change,
  without touching `frontend`) - every request then silently hung with
  nothing ever reaching the api container's logs, until `frontend` was
  restarted. Fixed in `frontend/nginx.conf` with a `resolver 127.0.0.11`
  (Docker's embedded DNS) plus a `set $api_upstream ...; proxy_pass
  $api_upstream;` indirection, which forces nginx to actually re-resolve
  on a short TTL instead of caching indefinitely.
- **The coverage endpoints can genuinely take minutes**, not seconds, on
  an unreliable connection - one real request during testing took ~3.5
  minutes end-to-end (well past nginx's 60s default `proxy_read_timeout`,
  which returned a premature 504) purely because of slow live network
  calls to ESA WorldCover, no code defect involved. Raised
  `proxy_read_timeout`/`proxy_send_timeout` to 300s in `frontend/nginx.conf`
  to match this endpoint's actual worst-case latency rather than an
  arbitrary default.

A fourth, related bug was in the core engine, not Docker/nginx:
`coverage_contour()`'s per-bearing failure isolation only caught
`ValueError` (target not reached), so a transient `RasterioIOError` from
one of those slow/flaky terrain lookups (a truncated tile read) crashed
the *entire* multi-bearing request with a 500 instead of failing just that
one bearing - see `docs/coverage_map.md`.

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

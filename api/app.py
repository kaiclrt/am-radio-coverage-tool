"""
Flask API wrapping src/propagation/ for the web UI.

Endpoints:
  POST /api/coverage/contour   - one or more target field-strength contours
  POST /api/coverage/profile   - full decay profile per bearing
  POST /api/estimate-rms       - power (kW) -> estimated RMS (mV/m)
  GET  /api/health             - liveness check

Request/response bodies are JSON. See docs/web_ui_design.md for the input
modes (Primary Service Contour / Day-Night / Custom; Licensed RMS /
Estimate from Power) this API is designed to serve.

See docs/api.md for hardening notes (rate limits, input bounds, debug-mode
safety, CORS, logging) and what's still deferred until an actual
deployment is planned.
"""
from __future__ import annotations

import logging
import os
import sys

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from propagation.coverage_map import coverage_contour, coverage_profile
from propagation.radial import estimate_theoretical_rms

# --- Bounds on expensive/abusable parameters --------------------------------
# terrain.get_conductivity() makes a live network request per sample point,
# so these bounds exist to stop a single request from triggering an
# excessive number of them (accidental typo or deliberate abuse) - not just
# to reject nonsensical values.
MAX_N_RADIALS = 360           # full one-degree resolution is already more
                               # than enough; no legitimate use needs more
MAX_N_POINTS = 200            # profile mode's per-bearing point count
MIN_SAMPLE_INTERVAL_KM = 0.5  # prevents e.g. 0.001km intervals over long
                               # distances from generating huge sample counts
MAX_SEARCH_KM = 5000.0        # matches the digitized curves' own max range
MAX_SAMPLES_PER_REQUEST = 2000  # (n_radials) x (search distance / interval)
                                 # combined cap, since any single bound above
                                 # can still be combined with the others to
                                 # produce an excessive total sample count

# --- Logging ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
logger = logging.getLogger('am_coverage_api')

app = Flask(__name__)

# Trust exactly one proxy hop's X-Forwarded-* headers. In the Docker setup
# every request arrives via the frontend's nginx, so without this the rate
# limiter and request log key on nginx's container IP - i.e. all users
# share one bucket and the log shows 172.18.0.x for everyone. x_for=1 (not
# more) is the safe value precisely because there is never more than one
# proxy in front: the API's own port is bound to 127.0.0.1
# (docker-compose.yml), so nginx is the only reachable path in and a client
# can't inject a forged X-Forwarded-For. Running the API with no proxy at
# all is also fine - there's just no X-Forwarded-For to read, so it falls
# back to the real remote_addr.
#
# The type: ignore is because wrapping app.wsgi_app is Flask's own
# documented middleware pattern, but mypy models wsgi_app as a plain method.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)  # type: ignore[method-assign]

# CORS: restricted to the frontend dev server's origin(s) by default rather
# than wide open. Override via the FRONTEND_ORIGIN env var (comma-separated)
# for other deployments. Whitespace around commas is tolerated.
_default_origins = 'http://localhost:5173,http://127.0.0.1:5173'
_allowed_origins = [
    o.strip() for o in os.environ.get('FRONTEND_ORIGIN', _default_origins).split(',') if o.strip()
]
CORS(app, origins=_allowed_origins)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=['60 per minute'],
    storage_uri='memory://',  # fine for a single-process dev/small deployment;
                               # switch to Redis if ever scaled to multiple workers
)


@app.before_request
def _log_request_start():
    g.request_summary = f"{request.method} {request.path}"
    logger.info(f"-> {g.request_summary} from {get_remote_address()}")


@app.after_request
def _log_request_end(response):
    logger.info(f"<- {g.get('request_summary', request.path)} {response.status_code}")
    return response


def _error(message: str, status: int = 400):
    return jsonify({'error': message}), status


@app.errorhandler(Exception)
def _handle_unexpected_error(e):
    """Catch-all: never let an unhandled exception's internal details (stack
    trace, file paths, etc.) reach the client - log the full detail
    server-side, return a generic message to the caller.

    Deliberately excludes werkzeug.exceptions.HTTPException (404, 429/rate
    limit, and other intentional HTTP-level responses raised by Flask
    itself or extensions like flask-limiter) - those already carry the
    correct status code and a safe message, and must not be flattened into
    a generic 500. Only genuinely unexpected exceptions should hit this
    handler."""
    if isinstance(e, HTTPException):
        return e
    logger.exception('Unhandled exception during request')
    return _error('Internal server error', 500)


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/api/estimate-rms', methods=['POST'])
@limiter.limit('30 per minute')
def estimate_rms():
    data = request.get_json(silent=True) or {}
    try:
        power_kw = float(data['power_kw'])
    except (KeyError, TypeError, ValueError):
        return _error("Missing or invalid 'power_kw' (expected a number, in kW)")
    if power_kw <= 0:
        return _error("'power_kw' must be positive")
    if power_kw > 1_000_000:
        return _error("'power_kw' is implausibly large")

    rms = estimate_theoretical_rms(power_kw)
    return jsonify({'rms_at_1km_mvm': rms})


def _parse_common_fields(data: dict):
    """Shared required-field parsing and bounds-checking for the two
    coverage endpoints. Returns (fields_dict, error_response) -
    error_response is None on success."""
    required = ['tx_lat', 'tx_lon', 'freq_khz', 'rms_at_1km_mvm']
    missing = [f for f in required if f not in data]
    if missing:
        return None, _error(f"Missing required field(s): {', '.join(missing)}")
    try:
        fields = {
            'tx_lat': float(data['tx_lat']),
            'tx_lon': float(data['tx_lon']),
            'freq_khz': float(data['freq_khz']),
            'rms_at_1km_mvm': float(data['rms_at_1km_mvm']),
            'n_radials': int(data.get('n_radials', 8)),
            'sample_interval_km': float(data.get('sample_interval_km', 2.0)),
        }
    except (TypeError, ValueError):
        return None, _error('One or more fields could not be parsed as numbers')

    if not (-90 <= fields['tx_lat'] <= 90):
        return None, _error("'tx_lat' must be between -90 and 90")
    if not (-180 <= fields['tx_lon'] <= 180):
        return None, _error("'tx_lon' must be between -180 and 180")
    if fields['rms_at_1km_mvm'] <= 0:
        return None, _error("'rms_at_1km_mvm' must be positive")
    if not (1 <= fields['n_radials'] <= MAX_N_RADIALS):
        return None, _error(f"'n_radials' must be between 1 and {MAX_N_RADIALS}")
    if fields['sample_interval_km'] < MIN_SAMPLE_INTERVAL_KM:
        return None, _error(f"'sample_interval_km' must be at least {MIN_SAMPLE_INTERVAL_KM}")

    return fields, None


def _check_sample_budget(n_radials: int, search_km: float, sample_interval_km: float):
    """Combined cap: no single field-level bound above stops someone from
    combining large-but-individually-valid values (e.g. max n_radials with
    the smallest allowed sample_interval_km over the largest allowed
    search distance) to still produce an excessive total sample count."""
    samples_per_radial = search_km / sample_interval_km
    total_samples = n_radials * samples_per_radial
    if total_samples > MAX_SAMPLES_PER_REQUEST:
        return _error(
            f'Requested parameters would require ~{int(total_samples)} terrain '
            f'samples, exceeding the limit of {MAX_SAMPLES_PER_REQUEST}. '
            f'Reduce n_radials, increase sample_interval_km, or reduce the search distance.'
        )
    return None


@app.route('/api/coverage/contour', methods=['POST'])
@limiter.limit('10 per minute')
def contour():
    """Distance to one or more target field-strength contours, per bearing.

    Body:
        tx_lat, tx_lon, freq_khz, rms_at_1km_mvm  (required)
        targets: {label: target_mvm, ...}  (required) - e.g.
            {"day": 0.5, "night": 2.5} for Day/Night mode, or
            {"primary": 1.0} for Primary Service Contour mode
        n_radials (default 8), max_search_km (default 500),
        sample_interval_km (default 2.0)
    """
    data = request.get_json(silent=True) or {}
    fields, err = _parse_common_fields(data)
    if err:
        return err

    targets = data.get('targets')
    if not targets or not isinstance(targets, dict):
        return _error("'targets' must be a non-empty object, e.g. {\"primary\": 1.0}")
    if len(targets) > 10:
        return _error("'targets' may contain at most 10 entries")
    try:
        targets = {label: float(v) for label, v in targets.items()}
    except (TypeError, ValueError):
        return _error("All 'targets' values must be numbers (mV/m)")
    if any(v <= 0 for v in targets.values()):
        return _error("All 'targets' values must be positive")

    max_search_km = float(data.get('max_search_km', 500.0))
    if not (0 < max_search_km <= MAX_SEARCH_KM):
        return _error(f"'max_search_km' must be between 0 and {MAX_SEARCH_KM}")

    budget_err = _check_sample_budget(fields['n_radials'], max_search_km,
                                       fields['sample_interval_km'])
    if budget_err:
        return budget_err

    results = {}
    for label, target_mvm in targets.items():
        results[label] = coverage_contour(
            fields['tx_lat'], fields['tx_lon'], fields['freq_khz'],
            fields['rms_at_1km_mvm'], target_mvm,
            n_radials=fields['n_radials'], max_search_km=max_search_km,
            sample_interval_km=fields['sample_interval_km'],
        )

    return jsonify({'contours': results})


@app.route('/api/coverage/profile', methods=['POST'])
@limiter.limit('10 per minute')
def profile():
    """Full field-strength-vs-distance decay profile per bearing.

    Body:
        tx_lat, tx_lon, freq_khz, rms_at_1km_mvm  (required)
        max_distance_km (default 200), n_points (default 20),
        n_radials (default 8), sample_interval_km (default 2.0)
    """
    data = request.get_json(silent=True) or {}
    fields, err = _parse_common_fields(data)
    if err:
        return err

    max_distance_km = float(data.get('max_distance_km', 200.0))
    if not (0 < max_distance_km <= MAX_SEARCH_KM):
        return _error(f"'max_distance_km' must be between 0 and {MAX_SEARCH_KM}")

    n_points = int(data.get('n_points', 20))
    if not (1 <= n_points <= MAX_N_POINTS):
        return _error(f"'n_points' must be between 1 and {MAX_N_POINTS}")

    budget_err = _check_sample_budget(fields['n_radials'], max_distance_km,
                                       fields['sample_interval_km'])
    if budget_err:
        return budget_err

    result = coverage_profile(
        fields['tx_lat'], fields['tx_lon'], fields['freq_khz'],
        fields['rms_at_1km_mvm'],
        n_radials=fields['n_radials'], max_distance_km=max_distance_km,
        n_points=n_points, sample_interval_km=fields['sample_interval_km'],
    )
    return jsonify({'profile': result})


if __name__ == '__main__':
    # Debug mode exposes Werkzeug's interactive debugger, which allows
    # arbitrary code execution if reachable by anyone but the developer -
    # default OFF, opt in explicitly and only for local development.
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    # Flask's own default (127.0.0.1) only accepts connections from inside
    # the same network namespace as the process itself - fine when the
    # frontend runs on the same host, but unreachable from another Docker
    # container (confirmed via docker-compose.yml's frontend service
    # getting a 502) or a genuinely separate deployment host. 0.0.0.0 is
    # not a new exposure beyond what's already true here (no auth, no
    # HTTPS - see the hardening notes above); override with FLASK_HOST if
    # a deployment specifically needs to restrict this.
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    app.run(host=host, debug=debug_mode, port=5000)

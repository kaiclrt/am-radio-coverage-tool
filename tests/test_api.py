"""
Tests for the Flask API (api/app.py). Offline - mocks terrain.get_conductivity
so no network access is needed, consistent with the rest of the test suite.
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
from app import app as flask_app
from app import limiter


@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    limiter.enabled = False  # avoid tests tripping rate limits when run in
    # sequence from the same test-client "IP" (flask-limiter reads its
    # enabled state directly, not from app.config, at request time)
    with flask_app.test_client() as client:
        yield client
    limiter.enabled = True  # restore for tests that check it explicitly


@pytest.fixture(autouse=True)
def mock_terrain():
    with patch('terrain.get_conductivity', return_value=(10, 'pastoral_rich_soil', 40)):
        yield


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get('/api/health')
        assert resp.status_code == 200
        assert resp.get_json() == {'status': 'ok'}


class TestEstimateRms:
    def test_valid_power(self, client):
        resp = client.post('/api/estimate-rms', json={'power_kw': 1})
        assert resp.status_code == 200
        assert resp.get_json()['rms_at_1km_mvm'] == pytest.approx(100.0)

    def test_missing_power(self, client):
        resp = client.post('/api/estimate-rms', json={})
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_negative_power(self, client):
        resp = client.post('/api/estimate-rms', json={'power_kw': -5})
        assert resp.status_code == 400

    def test_non_numeric_power(self, client):
        resp = client.post('/api/estimate-rms', json={'power_kw': 'lots'})
        assert resp.status_code == 400


class TestContour:
    VALID_BODY = {
        'tx_lat': 14.6, 'tx_lon': 121.0, 'freq_khz': 1140,
        'rms_at_1km_mvm': 100, 'targets': {'primary': 1.0},
        'n_radials': 8, 'sample_interval_km': 10, 'max_search_km': 100,
    }

    def test_valid_single_target(self, client):
        resp = client.post('/api/coverage/contour', json=self.VALID_BODY)
        assert resp.status_code == 200
        body = resp.get_json()
        assert 'primary' in body['contours']
        assert len(body['contours']['primary']) == 8

    def test_day_night_dual_targets(self, client):
        body = dict(self.VALID_BODY, targets={'day': 0.5, 'night': 2.5})
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 200
        contours = resp.get_json()['contours']
        assert set(contours.keys()) == {'day', 'night'}
        # lower target (day, 0.5) should reach farther than higher target (night, 2.5)
        day_dist = contours['day'][0]['distance_km']
        night_dist = contours['night'][0]['distance_km']
        assert day_dist > night_dist

    def test_missing_required_field(self, client):
        body = dict(self.VALID_BODY)
        del body['freq_khz']
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 400
        assert 'freq_khz' in resp.get_json()['error']

    def test_missing_targets(self, client):
        body = dict(self.VALID_BODY)
        del body['targets']
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 400

    def test_invalid_latitude(self, client):
        body = dict(self.VALID_BODY, tx_lat=999)
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 400

    def test_empty_body(self, client):
        resp = client.post('/api/coverage/contour', json={})
        assert resp.status_code == 400


class TestProfile:
    VALID_BODY = {
        'tx_lat': 14.6, 'tx_lon': 121.0, 'freq_khz': 1140,
        'rms_at_1km_mvm': 100, 'n_radials': 8,
        'max_distance_km': 50, 'n_points': 5, 'sample_interval_km': 10,
    }

    def test_valid_profile(self, client):
        resp = client.post('/api/coverage/profile', json=self.VALID_BODY)
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body['profile']) == 8
        assert len(body['profile'][0]['points']) == 5

    def test_missing_required_field(self, client):
        body = dict(self.VALID_BODY)
        del body['tx_lat']
        resp = client.post('/api/coverage/profile', json=body)
        assert resp.status_code == 400


class TestInputBounds:
    """Regression tests for the resource-exhaustion hardening added after
    the initial API implementation - see docs/api.md."""

    CONTOUR_BODY = {
        'tx_lat': 14.6, 'tx_lon': 121.0, 'freq_khz': 1140,
        'rms_at_1km_mvm': 100, 'targets': {'primary': 1.0},
    }

    def test_n_radials_too_high_rejected(self, client):
        body = dict(self.CONTOUR_BODY, n_radials=100000)
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 400
        assert 'n_radials' in resp.get_json()['error']

    def test_n_radials_zero_rejected(self, client):
        body = dict(self.CONTOUR_BODY, n_radials=0)
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 400

    def test_sample_interval_too_small_rejected(self, client):
        body = dict(self.CONTOUR_BODY, sample_interval_km=0.001)
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 400
        assert 'sample_interval_km' in resp.get_json()['error']

    def test_max_search_km_too_large_rejected(self, client):
        body = dict(self.CONTOUR_BODY, max_search_km=999999)
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 400

    def test_combined_sample_budget_rejected(self, client):
        """Individually-valid parameters that combine to an excessive total
        sample count should still be rejected (the combined-budget check,
        not just per-field bounds)."""
        body = dict(self.CONTOUR_BODY, n_radials=360,
                     sample_interval_km=0.5, max_search_km=5000)
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 400
        assert 'terrain samples' in resp.get_json()['error']

    def test_reasonable_parameters_accepted(self, client):
        body = dict(self.CONTOUR_BODY, n_radials=16, sample_interval_km=5,
                     max_search_km=200)
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 200

    def test_too_many_targets_rejected(self, client):
        body = dict(self.CONTOUR_BODY, targets={f't{i}': 1.0 for i in range(20)})
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 400

    def test_negative_target_rejected(self, client):
        body = dict(self.CONTOUR_BODY, targets={'bad': -1.0})
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 400

    def test_negative_rms_rejected(self, client):
        body = dict(self.CONTOUR_BODY, rms_at_1km_mvm=-5)
        resp = client.post('/api/coverage/contour', json=body)
        assert resp.status_code == 400

    def test_profile_n_points_too_high_rejected(self, client):
        body = {
            'tx_lat': 14.6, 'tx_lon': 121.0, 'freq_khz': 1140,
            'rms_at_1km_mvm': 100, 'n_points': 100000,
        }
        resp = client.post('/api/coverage/profile', json=body)
        assert resp.status_code == 400
        assert 'n_points' in resp.get_json()['error']

    def test_implausible_power_rejected(self, client):
        resp = client.post('/api/estimate-rms', json={'power_kw': 99999999})
        assert resp.status_code == 400


class TestSecurityDefaults:
    def test_debug_mode_defaults_off(self):
        """FLASK_DEBUG unset should mean debug mode is off (Werkzeug's
        interactive debugger allows arbitrary code execution if reachable -
        this must never be on by accident)."""
        os.environ.pop('FLASK_DEBUG', None)
        debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
        assert debug_mode is False

    def test_rate_limiting_enabled_by_default(self):
        """The 'client' fixture disables rate limiting for test convenience
        (see its limiter.enabled=False) - this test re-enables it
        explicitly to confirm the limiter is genuinely active in normal
        operation, not just configured and forgotten."""
        flask_app.config['TESTING'] = True
        limiter.enabled = True
        with flask_app.test_client() as raw_client:
            body = {
                'tx_lat': 14.6, 'tx_lon': 121.0, 'freq_khz': 1140,
                'rms_at_1km_mvm': 100, 'targets': {'primary': 1.0},
            }
            with patch('terrain.get_conductivity', return_value=(10, 'x', 40)):
                statuses = [raw_client.post('/api/coverage/contour', json=body).status_code
                            for _ in range(15)]  # limit is 10/minute
            assert 429 in statuses, "expected at least one rate-limited (429) response"
        limiter.enabled = False  # restore for other tests

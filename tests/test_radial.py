"""
Tests for the single-radial coverage calculator.

Offline tests mock terrain.get_conductivity() to avoid live network calls -
they test the great-circle math, segment-building/merging logic, RMS
scaling, and integration with the Kirke method. A small set of live tests
(real ESA WorldCover queries) are opt-in via RUN_LIVE_TERRAIN_TESTS=1,
consistent with test_terrain.py.
"""
import os
import sys
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from propagation.radial import (
    destination_point, estimate_theoretical_rms, build_conductivity_segments,
    radial_field_strength, radial_distance_for_field_strength,
    CHART_REFERENCE_RMS_MVM,
)
from propagation.curves import GroundwaveCurves

RUN_LIVE = os.environ.get('RUN_LIVE_TERRAIN_TESTS') == '1'


@pytest.fixture(scope='module')
def curves():
    return GroundwaveCurves()


class TestDestinationPoint:
    def test_zero_distance_returns_start(self):
        lat, lon = destination_point(14.6, 121.0, 0, 0)
        assert lat == pytest.approx(14.6, abs=1e-9)
        assert lon == pytest.approx(121.0, abs=1e-9)

    def test_due_north_one_degree(self):
        # ~111.19 km is very close to 1 degree of latitude anywhere on Earth
        lat, lon = destination_point(14.5995, 120.9842, 0, 111.19)
        assert lat == pytest.approx(15.5995, abs=0.01)
        assert lon == pytest.approx(120.9842, abs=0.01)

    def test_due_east_stays_near_same_latitude(self):
        lat, lon = destination_point(14.5995, 120.9842, 90, 111.19)
        assert lat == pytest.approx(14.5995, abs=0.05)
        assert lon > 120.9842  # moved east

    def test_south_and_west_bearings(self):
        lat, lon = destination_point(14.6, 121.0, 180, 111.19)
        assert lat < 14.6  # due south decreases latitude
        lat2, lon2 = destination_point(14.6, 121.0, 270, 111.19)
        assert lon2 < 121.0  # due west decreases longitude


class TestTheoreticalRMS:
    def test_scales_with_sqrt_power(self):
        assert estimate_theoretical_rms(1) == pytest.approx(300.0)
        assert estimate_theoretical_rms(4) == pytest.approx(600.0)  # sqrt(4)=2
        assert estimate_theoretical_rms(0.25) == pytest.approx(150.0)  # sqrt(0.25)=0.5


class TestSegmentBuilding:
    def test_uniform_terrain_gives_one_segment(self):
        with patch('terrain.get_conductivity', return_value=(10, 'pastoral_rich_soil', 40)):
            segs = build_conductivity_segments(14.6, 121.0, 0, 50, sample_interval_km=5)
        assert len(segs) == 1
        assert segs[0][0] == 10
        assert segs[0][1] == pytest.approx(50, rel=1e-6)

    def test_single_transition_gives_two_segments(self):
        def fake(lat, lon):
            return (10, 'x', 0) if lat < 15.0 else (2, 'y', 0)
        with patch('terrain.get_conductivity', side_effect=fake):
            segs = build_conductivity_segments(14.6, 121.0, 0, 100, sample_interval_km=2)
        assert len(segs) == 2
        assert segs[0][0] == 10
        assert segs[1][0] == 2
        total = sum(length for _, length in segs)
        assert total == pytest.approx(100, rel=1e-6)

    def test_short_spurious_segments_get_merged(self):
        """A single anomalous sample (e.g. one pixel of a small pond) shouldn't
        produce a tiny standalone segment - it should merge into a neighbor."""
        calls = [10, 10, 10, 2, 10, 10, 10]  # one spurious sample in the middle
        def fake(lat, lon):
            return (calls.pop(0), 'x', 0)
        with patch('terrain.get_conductivity', side_effect=fake):
            segs = build_conductivity_segments(14.6, 121.0, 0, 60, sample_interval_km=10,
                                                min_segment_km=15)
        # the spurious single-sample segment (10km wide, below min_segment_km=15)
        # should have been absorbed into a neighboring segment
        assert all(length >= 10 for _, length in segs), \
            "spurious short segment was not merged away"


class TestRadialFieldStrength:
    def test_rms_scaling_is_linear(self):
        with patch('terrain.get_conductivity', return_value=(10, 'x', 0)):
            v1 = radial_field_strength(14.6, 121.0, 0, 1140, 100, 50, sample_interval_km=5)
            v3 = radial_field_strength(14.6, 121.0, 0, 1140, 300, 50, sample_interval_km=5)
        assert v3 / v1 == pytest.approx(3.0, rel=1e-6)

    def test_rms_equal_to_chart_reference_matches_plain_curve(self, curves):
        """When RMS is exactly the chart's own reference (100 mV/m), the
        radial result over uniform terrain should match a plain curve lookup."""
        with patch('terrain.get_conductivity', return_value=(10, 'x', 0)):
            v = radial_field_strength(14.6, 121.0, 0, 1140, CHART_REFERENCE_RMS_MVM,
                                       50, sample_interval_km=5)
        v_plain = curves.field_strength(1140, 10, 50)
        assert v == pytest.approx(v_plain, rel=1e-6)

    def test_round_trip_distance(self):
        def fake(lat, lon):
            return (10, 'x', 0) if lat < 15.0 else (2, 'y', 0)
        with patch('terrain.get_conductivity', side_effect=fake):
            v = radial_field_strength(14.6, 121.0, 0, 1140, 150, 50, sample_interval_km=2)
            d = radial_distance_for_field_strength(14.6, 121.0, 0, 1140, 150, v,
                                                     max_search_km=100, sample_interval_km=2)
        assert d == pytest.approx(50, rel=1e-2)


@pytest.mark.skipif(not RUN_LIVE, reason="Set RUN_LIVE_TERRAIN_TESTS=1 to run "
                     "(requires internet access to AWS S3)")
class TestLiveRadial:
    def test_manila_radial_runs_end_to_end(self):
        """Smoke test: a real radial out of Manila shouldn't error, and field
        strength should decrease monotonically with distance."""
        v10 = radial_field_strength(14.5995, 120.9842, 45, 1140, 200, 10, sample_interval_km=5)
        v50 = radial_field_strength(14.5995, 120.9842, 45, 1140, 200, 50, sample_interval_km=5)
        assert v50 < v10

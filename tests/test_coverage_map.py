"""
Tests for the multi-radial coverage map (coverage_contour, coverage_profile).

Offline tests mock terrain.get_conductivity() - no live network needed.
"""
import os
import sys
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from propagation.coverage_map import (
    generate_bearings, bearing_label, coverage_contour, coverage_profile,
)


class TestBearingGeneration:
    def test_eight_cardinal_bearings(self):
        bearings = generate_bearings(8)
        assert bearings == pytest.approx([0, 45, 90, 135, 180, 225, 270, 315])

    def test_eight_cardinal_labels(self):
        labels = [bearing_label(b) for b in generate_bearings(8)]
        assert labels == ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

    def test_sixteen_bearings_evenly_spaced(self):
        bearings = generate_bearings(16)
        assert len(bearings) == 16
        diffs = [b2 - b1 for b1, b2 in zip(bearings, bearings[1:])]
        assert all(d == pytest.approx(22.5) for d in diffs)

    def test_arbitrary_resolution(self):
        bearings = generate_bearings(36)
        assert len(bearings) == 36
        assert bearings[1] == pytest.approx(10.0)


class TestCoverageContour:
    def test_uniform_terrain_gives_equal_distances_all_bearings(self):
        with patch('terrain.get_conductivity', return_value=(10, 'x', 0)):
            results = coverage_contour(14.6, 121.0, 1140, 200, 2.0,
                                        n_radials=8, max_search_km=300, sample_interval_km=10)
        distances = [r['distance_km'] for r in results]
        assert all(d is not None for d in distances)
        assert all(d == pytest.approx(distances[0], rel=1e-6) for d in distances)

    def test_result_count_matches_n_radials(self):
        with patch('terrain.get_conductivity', return_value=(10, 'x', 0)):
            results = coverage_contour(14.6, 121.0, 1140, 200, 2.0,
                                        n_radials=16, max_search_km=300, sample_interval_km=10)
        assert len(results) == 16

    def test_asymmetric_terrain_gives_asymmetric_distances(self):
        def fake(lat, lon):
            return (2, 'poor', 20) if lat > 14.6 else (30, 'good', 40)
        with patch('terrain.get_conductivity', side_effect=fake):
            results = coverage_contour(14.6, 121.0, 1140, 200, 2.0,
                                        n_radials=8, max_search_km=300, sample_interval_km=5)
        by_label = {r['label']: r['distance_km'] for r in results}
        assert by_label['N'] < by_label['S']  # poor conductivity north, good south

    def test_destination_coordinates_are_populated(self):
        with patch('terrain.get_conductivity', return_value=(10, 'x', 0)):
            results = coverage_contour(14.6, 121.0, 1140, 200, 2.0,
                                        n_radials=8, max_search_km=300, sample_interval_km=10)
        for r in results:
            assert r['lat'] is not None
            assert r['lon'] is not None

    def test_unreachable_target_fails_gracefully_per_bearing(self):
        """A per-bearing failure (target not reached within max_search_km)
        should not crash the whole map - it should be captured in the
        result with distance_km=None and an error message."""
        with patch('terrain.get_conductivity', return_value=(0.1, 'urban', 50)):
            results = coverage_contour(14.6, 121.0, 1140, 200, 2.0,
                                        n_radials=8, max_search_km=2, sample_interval_km=1)
        assert len(results) == 8
        for r in results:
            assert r['distance_km'] is None
            assert 'error' in r


class TestCoverageProfile:
    def test_result_count_matches_n_radials(self):
        with patch('terrain.get_conductivity', return_value=(10, 'x', 0)):
            profile = coverage_profile(14.6, 121.0, 1140, 200,
                                        n_radials=8, max_distance_km=100,
                                        n_points=10, sample_interval_km=10)
        assert len(profile) == 8

    def test_points_per_bearing_matches_n_points(self):
        with patch('terrain.get_conductivity', return_value=(10, 'x', 0)):
            profile = coverage_profile(14.6, 121.0, 1140, 200,
                                        n_radials=8, max_distance_km=100,
                                        n_points=10, sample_interval_km=10)
        for entry in profile:
            assert len(entry['points']) == 10

    def test_monotonic_decay_within_each_bearing(self):
        with patch('terrain.get_conductivity', return_value=(10, 'x', 0)):
            profile = coverage_profile(14.6, 121.0, 1140, 200,
                                        n_radials=8, max_distance_km=100,
                                        n_points=10, sample_interval_km=10)
        for entry in profile:
            fields = [p['field_mvm'] for p in entry['points']]
            assert all(a > b for a, b in zip(fields, fields[1:]))

    def test_each_point_has_coordinates(self):
        with patch('terrain.get_conductivity', return_value=(10, 'x', 0)):
            profile = coverage_profile(14.6, 121.0, 1140, 200,
                                        n_radials=8, max_distance_km=100,
                                        n_points=5, sample_interval_km=10)
        for entry in profile:
            for p in entry['points']:
                assert p['lat'] is not None and p['lon'] is not None

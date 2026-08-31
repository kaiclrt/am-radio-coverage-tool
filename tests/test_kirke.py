"""
Tests for the Kirke (equivalent-distance) mixed-path groundwave method.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from propagation.curves import GroundwaveCurves
from propagation.kirke import mixed_path_distance_for_field_strength, mixed_path_field_strength


@pytest.fixture(scope='module')
def curves():
    return GroundwaveCurves()


class TestDegenerateCases:
    """A 'mixed path' that isn't actually mixed should reduce to a plain
    single-conductivity lookup, regardless of how the path is artificially
    split into segments."""

    def test_single_segment_matches_plain_lookup(self, curves):
        v_plain = curves.field_strength(1140, 10, 50)
        v_kirke = mixed_path_field_strength(1140, [(10, 50)], curves=curves)
        assert v_kirke == pytest.approx(v_plain)

    def test_uniform_conductivity_split_two_ways(self, curves):
        v_plain = curves.field_strength(1140, 10, 50)
        v_split = mixed_path_field_strength(1140, [(10, 20), (10, 30)], curves=curves)
        assert v_split == pytest.approx(v_plain)

    def test_uniform_conductivity_split_five_ways(self, curves):
        v_plain = curves.field_strength(1140, 10, 50)
        v_split = mixed_path_field_strength(
            1140, [(10, 10)] * 5, curves=curves)
        assert v_split == pytest.approx(v_plain)


class TestMixedPathBounding:
    """A genuinely mixed path's field strength must fall between what
    either conductivity alone would give over the full distance - the
    Kirke method blends between them, it doesn't extrapolate beyond."""

    def test_poor_then_good_is_bounded(self, curves):
        segments = [(2, 30), (30, 70)]
        v_mixed = mixed_path_field_strength(1140, segments, curves=curves)
        v_all_poor = curves.field_strength(1140, 2, 100)
        v_all_good = curves.field_strength(1140, 30, 100)
        assert v_all_poor < v_mixed < v_all_good

    def test_good_then_poor_is_bounded(self, curves):
        segments = [(30, 30), (2, 70)]
        v_mixed = mixed_path_field_strength(1140, segments, curves=curves)
        v_all_poor = curves.field_strength(1140, 2, 100)
        v_all_good = curves.field_strength(1140, 30, 100)
        assert v_all_poor < v_mixed < v_all_good

    def test_recovery_effect_poor_to_good(self, curves):
        """Crossing into better conductivity partway through should leave
        the signal stronger than if poor conductivity had continued the
        whole way - this is the 'recovery effect' the FCC's NPRM and the
        Wait (1956) NBS paper describe as the key thing Millington/Kirke-style
        methods must capture correctly."""
        segments = [(2, 30), (30, 70)]
        v_mixed = mixed_path_field_strength(1140, segments, curves=curves)
        v_all_poor = curves.field_strength(1140, 2, 100)
        assert v_mixed > v_all_poor


class TestRoundTrip:
    def test_two_segment_round_trip(self, curves):
        segments = [(2, 30), (30, 70)]
        v = mixed_path_field_strength(1140, segments, 100, curves=curves)
        d = mixed_path_distance_for_field_strength(1140, segments, v, curves=curves)
        assert d == pytest.approx(100, rel=1e-3)

    def test_four_segment_round_trip(self, curves):
        segments = [(30, 5), (10, 15), (5, 30), (2, 50)]
        v = mixed_path_field_strength(1140, segments, curves=curves)  # full path, 100km
        d = mixed_path_distance_for_field_strength(1140, segments, v, curves=curves)
        assert d == pytest.approx(100, rel=1e-3)


class TestIntermediateQueries:
    def test_query_within_first_segment(self, curves):
        segments = [(30, 5), (10, 15), (5, 30), (2, 50)]
        v = mixed_path_field_strength(1140, segments, 3, curves=curves)
        v_plain = curves.field_strength(1140, 30, 3)
        assert v == pytest.approx(v_plain)  # still within segment 1, no crossing yet

    def test_query_mid_third_segment(self, curves):
        segments = [(30, 5), (10, 15), (5, 30), (2, 50)]
        v = mixed_path_field_strength(1140, segments, 35, curves=curves)  # 5+15+15
        assert v > 0  # sanity: doesn't error, produces a positive value

    def test_monotonic_decay_across_boundaries(self, curves):
        """Field strength must keep decreasing with distance even as the
        path crosses conductivity boundaries (no discontinuous jump)."""
        segments = [(30, 5), (10, 15), (5, 30), (2, 50)]
        distances = [1, 4, 6, 19, 21, 34, 36, 60, 99]
        values = [mixed_path_field_strength(1140, segments, d, curves=curves) for d in distances]
        assert all(a > b for a, b in zip(values, values[1:]))


class TestErrorHandling:
    def test_empty_segments_raises(self, curves):
        with pytest.raises(ValueError):
            mixed_path_field_strength(1140, [], curves=curves)

    def test_distance_beyond_path_raises(self, curves):
        with pytest.raises(ValueError):
            mixed_path_field_strength(1140, [(10, 50)], 999, curves=curves)

    def test_unreachable_target_field_strength_raises(self, curves):
        with pytest.raises(ValueError):
            mixed_path_distance_for_field_strength(1140, [(10, 10)], 0.0000001, curves=curves)

"""
Tests for the distance <-> field-strength interpolation module.

Unlike test_digitizer.py, these run against the committed digitized JSON
data (data/digitized_curves/all_frequencies.json), not the source PDFs, so
no environment variable / external files are needed.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from propagation.curves import GroundwaveCurves


@pytest.fixture(scope='module')
def gc():
    return GroundwaveCurves()


class TestFrequencySelection:
    def test_exact_match(self, gc):
        assert gc.nearest_graph_frequency(1140) == 1140

    def test_nearest_below_midpoint(self, gc):
        # 1070 and 1140 centers -> midpoint 1105; 1075 is below it
        assert gc.nearest_graph_frequency(1075) == 1070

    def test_nearest_above_midpoint(self, gc):
        assert gc.nearest_graph_frequency(1130) == 1140


class TestForwardInterpolation:
    def test_monotonic_decay_with_distance(self, gc):
        # 300km chosen to stay within the digitized range for all conductivities
        # tested elsewhere in this suite (low-conductivity curves hit the chart's
        # floor, 0.0001 mV/m, well before 1000km - that's expected physical
        # behavior, not a bug, so this test avoids that edge deliberately).
        vals = [gc.field_strength(1140, 10, d) for d in [1, 10, 50, 100, 300]]
        assert all(a > b for a, b in zip(vals, vals[1:]))

    def test_conductivity_ordering(self, gc):
        """Higher conductivity must give higher field strength at a fixed distance."""
        v_low = gc.field_strength(1140, 1, 100)
        v_high = gc.field_strength(1140, 30, 100)
        assert v_high > v_low

    def test_interpolated_conductivity_is_bracketed(self, gc):
        """A conductivity between two standard values must give a result between
        their two curves (this was previously broken by an inverted weight bug)."""
        v_lo = gc.field_strength(1140, 10, 50)
        v_mid = gc.field_strength(1140, 12, 50)
        v_hi = gc.field_strength(1140, 15, 50)
        assert v_lo < v_mid < v_hi

    def test_exact_standard_conductivity_matches_single_curve(self, gc):
        """When conductivity exactly equals a standard value, bracketing should
        return that curve's value exactly, not an adjacent one (regression test
        for the inverted-weight bug)."""
        v_exact = gc.field_strength(1140, 10, 50)
        v_single = gc._field_strength_single_conductivity(1140, '10', 50)
        assert v_exact == pytest.approx(v_single)

    def test_conductivity_clamping_above_range(self, gc):
        v_5000 = gc.field_strength(1140, 5000, 50)
        v_above = gc.field_strength(1140, 50000, 50)
        assert v_above == pytest.approx(v_5000)

    def test_conductivity_clamping_below_range(self, gc):
        v_01 = gc.field_strength(1140, 0.1, 50)
        v_below = gc.field_strength(1140, 0.001, 50)
        assert v_below == pytest.approx(v_01)


class TestInverseInterpolation:
    def test_round_trip_distance(self, gc):
        for d0 in [1, 10, 50, 100, 300]:
            v = gc.field_strength(1140, 10, d0)
            d1 = gc.distance_for_field_strength(1140, 10, v)
            assert d1 == pytest.approx(d0, rel=1e-3)

    def test_round_trip_with_interpolated_conductivity(self, gc):
        for c in [3, 12, 25]:
            v = gc.field_strength(1140, c, 100)
            d = gc.distance_for_field_strength(1140, c, v)
            assert d == pytest.approx(100, rel=1e-2)


class TestPanelStitching:
    def test_continuous_across_10km_boundary(self, gc):
        """Top and bottom panels are stitched at km=10; value should be
        continuous (no jump) across that boundary."""
        v_below = gc.field_strength(1140, 10, 9.9)
        v_above = gc.field_strength(1140, 10, 10.1)
        assert v_below == pytest.approx(v_above, rel=0.05)


class TestOutOfRange:
    def test_distance_too_far_raises(self, gc):
        with pytest.raises(ValueError):
            gc.field_strength(1140, 10, 100000)

    def test_distance_too_close_raises(self, gc):
        with pytest.raises(ValueError):
            gc.field_strength(1140, 10, 0.001)

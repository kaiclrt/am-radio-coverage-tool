"""
Basic regression tests for the groundwave curve digitizer.

Requires the FCC source PDFs (not committed to this repo). Set the
GW_GRAPHS_DIR environment variable to point at the extracted graphs
directory, or tests will be skipped.

    GW_GRAPHS_DIR=/path/to/graphs pytest tests/
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from gwdigitizer.core import CONDUCTIVITIES, assign_all_curves

GRAPHS_DIR = os.environ.get('GW_GRAPHS_DIR')
skip_reason = "Set GW_GRAPHS_DIR to the extracted FCC graphs directory to run these tests"


@pytest.mark.skipif(GRAPHS_DIR is None, reason=skip_reason)
class TestDigitizer:

    def test_1140khz_all_conductivities_present(self):
        top, bottom, notes = assign_all_curves(os.path.join(GRAPHS_DIR, '1140.pdf'))
        assert set(top.keys()) == set(CONDUCTIVITIES)
        assert set(bottom.keys()) == set(CONDUCTIVITIES)
        assert notes == []  # 1140 kHz has no known merge issues

    def test_1140khz_monotonic_decay(self):
        """Field strength should strictly decrease with distance for every curve."""
        top, bottom, notes = assign_all_curves(os.path.join(GRAPHS_DIR, '1140.pdf'))
        for label, pts in {**top, **bottom}.items():
            values = [mvm for km, mvm in pts]
            assert all(a >= b for a, b in zip(values, values[1:])), \
                f"{label} mS/m curve is not monotonically decreasing"

    def test_1140khz_conductivity_ordering_at_fixed_distance(self):
        """At any given distance, higher conductivity must give higher field strength."""
        top, bottom, notes = assign_all_curves(os.path.join(GRAPHS_DIR, '1140.pdf'))
        # sample bottom panel at km=100 (all curves should still be defined there)
        import numpy as np
        vals_at_100 = {}
        for label, pts in bottom.items():
            kms = [p[0] for p in pts]
            mvms = [p[1] for p in pts]
            if min(kms) <= 100 <= max(kms):
                vals_at_100[label] = np.interp(100, kms, mvms)
        ordered_labels = [lbl for lbl in CONDUCTIVITIES if lbl in vals_at_100]
        ordered_vals = [vals_at_100[lbl] for lbl in ordered_labels]
        assert all(a >= b for a, b in zip(ordered_vals, ordered_vals[1:])), \
            "Curves are not correctly ordered by conductivity at km=100"

    def test_1560khz_tight_label_spacing_case(self):
        """Regression test for the pair-based clustering fix (previously failed)."""
        top, bottom, notes = assign_all_curves(os.path.join(GRAPHS_DIR, '1560.pdf'))
        assert len(top) == 17
        assert len(bottom) == 17

    def test_550khz_low_frequency_merge_case(self):
        """Regression test for the low-frequency merged-curve fallback."""
        top, bottom, notes = assign_all_curves(os.path.join(GRAPHS_DIR, '550.pdf'))
        assert len(top) == 17
        assert len(bottom) == 17
        assert len(notes) == 1
        assert '30 mS/m' in notes[0] and '40 mS/m' in notes[0]

    def test_all_20_frequencies(self):
        freqs = [
            550, 580, 610, 640, 670, 700, 740, 790, 840, 890,
            940, 1000, 1070, 1140, 1210, 1290, 1380, 1470, 1560, 1655,
        ]
        for f in freqs:
            top, bottom, notes = assign_all_curves(os.path.join(GRAPHS_DIR, f'{f}.pdf'))
            assert len(top) == 17, f"{f} kHz: top panel incomplete"
            assert len(bottom) == 17, f"{f} kHz: bottom panel incomplete"

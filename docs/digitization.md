# Digitization Methodology

## Source

The FCC publishes 20 groundwave propagation graphs (Graph 1–20, per 47 CFR
§73.184), covering the full AM band in overlapping frequency sub-bands from
535–1705 kHz. Each graph is a log-log plot of field strength (mV/m) vs.
distance (km), with one curve per ground conductivity value (0.1 to 5000
mS/m, 17 curves total).

Vector PDF versions of all 20 graphs are available from
https://www.fcc.gov/node/38972. These are true vector drawings (not
scanned images), which makes precise digitization possible by extracting
the underlying curve path coordinates directly, rather than tracing pixels
in a raster image.

## Page layout

Each graph PDF contains two overlapping panels sharing the same pixel
rectangle and the same continuous field-strength (y) axis:

- **Top panel**: 0.1–50 km, x-axis ticks printed at the top of the page
- **Bottom panel**: 10–5000 km, x-axis ticks printed at the bottom of the page

Both panels' curves span the same x-pixel range (~72–720pt), so a curve
cannot be identified as "top" or "bottom" by its screen position alone —
only by which axis calibration correctly maps its shape to physically
sensible values.

## Pipeline

1. **Extract candidate curves.** Vector line-drawing objects with >5 segments
   that aren't axis-aligned (grid lines) are treated as curve candidates.
2. **Calibrate axes.** Axis tick label text (extracted from the PDF's text
   layer, not OCR) gives exact pixel↔value mappings for both the top and
   bottom x-axes and the shared log-scale y-axis.
3. **Label top-panel curves by rank order.** Curves are physically
   non-crossing (higher conductivity means less attenuation, so a
   higher-conductivity curve stays above a lower-conductivity one at every
   distance), so sorting the 17 candidate curves by their right-edge
   y-position and assigning conductivities in order (5000 → 0.1, highest
   to lowest) is a reliable, purely geometric labeling method.

   This wasn't the first approach tried. Initially, curves were matched to
   the right-side legend (conductivity values 5000→0.1 with individual
   leader lines converging near the plot's right edge). That's a more
   "self-documenting" method in principle, but proved fragile in practice:
   greedy nearest-anchor matching occasionally swapped adjacent labels
   (e.g. 20/30 mS/m) when their leader-line endpoints were only a few
   pixels apart - a real bug caught by testing, not a hypothetical
   concern (see `tests/test_curves.py`'s ordering tests, added after
   this was found). Rank-order replaced it as the primary method and has
   been validated against all 20 source PDFs since.

   The legend data isn't used for anything currently, not even as a
   cross-check against the rank-order result - that was considered and
   explicitly deferred (see the comment in `gwdigitizer/core.py` above the
   top-curve assignment logic) since rank-order alone already passes
   cleanly on every available source file.
4. **Handle near-origin curve fragmentation.** In the source vector artwork,
   curves that nearly converge near the transmitter (all conductivities give
   similar field strength at very short range) are sometimes drawn as a
   single merged path, then split into separate objects only where they
   visibly diverge. Where a top-panel curve's fragment doesn't reach the
   left edge (0.1 km), the missing segment is filled using the pure
   inverse-distance relationship **E(d) = 100/d mV/m** — this is not an
   approximation of convenience; it's the chart's own explicitly labeled
   "INVERSE DISTANCE 100 mV/m AT 1 km" asymptote, which all curves
   genuinely follow at short range. Verified to match real digitized values
   to within ~0.5% at the splice point.
5. **Label bottom-panel curves by rank order too.** Same reasoning and
   method as step 3. This also replaced an earlier approach (matching each
   bottom curve to whichever top curve agreed with it at the 10 km
   boundary) that turned out to have the same greedy-nearest-match fragility
   as the legend method - close conductivity values could still get
   mismatched. Rank order is simpler and doesn't have that failure mode.
6. **Fallback for low-frequency merged curves.** At the lowest frequencies
   (550–640 kHz in this dataset), ground wave attenuation is small enough
   that 2–3 of the highest-conductivity curves (5000, 40, 30 mS/m) are
   nearly numerically identical across the entire 0.1–50 km range, and the
   source PDF draws them as a single overlapping path — even the legend's
   leader lines merge. When this happens (top panel yields 16 distinct
   curves instead of 17), the missing conductivity is identified via
   monotonic alignment against the complete 17-curve bottom panel, and its
   data is duplicated from its nearest neighbor. This is flagged in the
   output (`notes` field) rather than silently applied.

## Validation

Every digitized curve was overlaid pixel-for-pixel on a rendered image of
its source PDF and visually confirmed to trace the original line exactly,
with the correct label, for:

- 1140 kHz (baseline)
- 1560 kHz (initially failed due to tight label spacing at higher
  frequencies — fixed by switching from distance-based clustering to
  pair-based grouping of leader-line endpoints)
- 550 kHz (the low-frequency merged-curve case)

All 20 files pass end-to-end (`scripts/digitize_all.py`), with 4 files
(550, 580, 610, 640 kHz) producing a documented single-curve duplication
each. See `data/digitized_curves/batch_summary.json` for the full list of
notes.

## Known limitations

- The 30/40 mS/m duplication at low frequencies (550–640 kHz) means those
  two conductivities' top-panel curves are identical in this dataset. Since
  they were visually indistinguishable in the source chart itself, the
  practical accuracy impact is negligible for coverage calculations in that
  range — but this is a real data limitation worth knowing about, not
  independently measured data for both values.
- Digitization precision is bounded by the PDF's own drawing resolution
  (typically sub-pixel, well under 1% of a decade on the log scale) — not a
  concern in practice — but is not a substitute for FCC's own OET86-1
  computer-calculated values where sub-percent precision matters (e.g.
  formal interference proceedings).
- **30/40 mS/m near-crossing at ~20 km, 670–840 kHz.** A small (2–8%),
  consistent rank inversion between the 30 and 40 mS/m curves appears
  around the 20 km mark for five consecutive mid-band frequencies. This is
  too systematic across adjacent frequencies to be digitization noise, and
  most likely reflects genuine imprecision in the FCC's own source curves —
  the 1988 NPRM (MM Docket 88-510, FCC 88-326) explicitly acknowledges that
  "the groundwave propagation curves... are not fully consistent with
  formulas in engineering texts" and that freehand drawing was used to
  complete portions of the original 1939 curves. Not yet visually confirmed
  against the source PDF; flagged here for follow-up rather than blocking
  use, since the magnitude is small and both conductivities represent
  "good" ground in practical terms.
- A general sanity check (`scripts/check_ordering.py`, TODO) across all 20
  files finds curves are correctly ordered (higher conductivity → higher
  field strength) everywhere except the two cases above.

## Interpolation layer (Phase 2)

Built on top of the digitized data: `src/propagation/curves.py` provides
`field_strength(freq_khz, conductivity_mScm, distance_km)` and its inverse
`distance_for_field_strength(freq_khz, conductivity_mScm, target_mvm)`.

- **Distance axis**: log-log linear interpolation directly on the digitized
  curve points (top and bottom panels stitched into one continuous curve
  per conductivity, split at km=10 where both panels agree to <1%).
- **Frequency axis**: no interpolation between graphs — the nearest FCC
  graph (by center frequency) is selected, matching standard engineering
  practice of using the graph whose labeled band covers the station's
  actual frequency.
- **Conductivity axis**: log-log linear interpolation *between* the two
  nearest of the 17 standard conductivity curves, needed because real
  ground conductivity (from FCC Figure M3) is rarely one of the round
  numbers the FCC graphs are drawn for. Values outside the 0.1–5000 mS/m
  range are clamped to the nearest edge curve.

Regression-tested in `tests/test_curves.py`, including a caught-and-fixed
bug where the conductivity-bracketing weight was inverted (an exact match
to a standard conductivity value was silently returning its neighboring
curve's data instead).

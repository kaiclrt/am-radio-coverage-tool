# AM Radio Coverage Calculator

[![Tests](https://github.com/kaiclrt/am-radio-coverage-tool/actions/workflows/tests.yml/badge.svg)](https://github.com/kaiclrt/am-radio-coverage-tool/actions/workflows/tests.yml)

Ground wave coverage prediction tool for AM broadcast stations, built on the
FCC's official groundwave propagation curves (47 CFR §73.184) and
terrain-based ground conductivity estimation for global coverage.

## Status: core propagation engine complete

Every phase of the original scope is implemented and tested: digitized FCC
curves for all 20 frequency bands, distance↔field-strength interpolation,
global terrain-based conductivity estimation, the Kirke mixed-path method
(47 CFR §73.183(e)), a single-radial coverage calculator, and an 8-radial
(or finer) coverage map. See the roadmap below for what's built and what's
still open (a web UI, mainly).

See [`docs/digitization.md`](docs/digitization.md) and the other `docs/*.md`
files for methodology, validation, and known limitations of each phase.
See [`CHANGELOG.md`](CHANGELOG.md) for a categorized summary of what's been
built, fixed, and deferred.

## Installation

Requires Python 3.9+ (CI actively tests 3.10, 3.11, 3.12 - see
`.github/workflows/tests.yml`). Clone the repo, then install in editable mode:

```bash
git clone git@github.com:kaiclrt/am-radio-coverage-tool.git
cd am-radio-coverage-tool
pip install -e .
```

That installs the core dependencies (`numpy`, `pymupdf`) needed for curve
digitization and interpolation. Optional dependency groups:

```bash
pip install -e .[dev]       # pytest, for running the test suite
pip install -e .[terrain]   # rasterio + global-land-mask, for terrain-based
                             # conductivity estimation (see docs/conductivity.md)
pip install -e .[dev,terrain]  # both together
```

`pyproject.toml` is the single source of truth for dependencies - there's
no separate `requirements.txt` to keep in sync with it.

Run the test suite (excluding `test_digitizer.py`, which needs the FCC's
source PDFs - see `scripts/digitize_all.py` for why those aren't bundled
in this repo):

```bash
python -m pytest tests/ --ignore=tests/test_digitizer.py -v
```

### Tested dependency versions

`pyproject.toml` declares version ranges (a floor of what's known to work,
a ceiling to avoid an untested future major version silently breaking
things), not exact pins - this project isn't a library other packages
depend on, so a full lockfile would add more overhead than benefit at this
stage. The specific versions below have been confirmed working (all tests
passing) across two independent environments (Linux/sandbox and Windows):

| Package | Tested version(s) |
|---|---|
| Python | 3.10, 3.11, 3.12 (CI-tested); 3.12.10 (Windows, confirmed) |
| numpy | 2.4.4, 2.5.2 |
| pymupdf | 1.28.2 |
| pytest | 9.1.1 |
| ruff | 0.16.5 |
| rasterio | 1.5.1 |
| global-land-mask | (latest as of terrain module development) |

## Roadmap

- [x] Digitize all 20 FCC groundwave graphs
- [x] Distance↔field-strength interpolation (both directions, log-log,
      including interpolation across conductivity values not exactly on
      the standard FCC curves)
- [x] Terrain-based global ground conductivity estimation (ESA WorldCover +
      FCC's 1939 terrain-conductivity table + offline ocean/lake
      disambiguation) - see `docs/conductivity.md`
- [x] Kirke/equivalent-distance mixed-path method (§73.183(e)) - see
      `docs/kirke_method.md`
- [x] Single-radial coverage calculator (TX location + power + bearing →
      contour distance) - see `docs/radial_calculator.md`
- [x] 8-cardinal-radial coverage map, with optional finer angular
      resolution - see `docs/coverage_map.md`
- [ ] FCC M3 conductivity dataset (`m3.seq`) for higher-precision US data
      (optional upgrade, deferred - terrain-based estimation covers the US
      too, just less precisely)
- [ ] Web UI

## Data provenance & license

- FCC groundwave curves: public domain (U.S. government work), sourced from
  https://www.fcc.gov/node/38972
- FCC 1939 terrain-conductivity table: public domain (U.S. government work),
  Federal Register
- ESA WorldCover land cover data: CC-BY-4.0 (attribution required - see
  `docs/conductivity.md`)
- Digitized derivative data and all code in this repo: MIT License (see LICENSE)
- **Not used**: ITU-R P.832 (World Atlas of Ground Conductivities) is a paid,
  copyrighted product (~441 CHF) and is deliberately not used anywhere in
  this project - see `docs/conductivity.md` for the terrain-based
  alternative built instead

## Regulatory basis

- 47 CFR §73.183 — groundwave field strength calculation procedures
- 47 CFR §73.184 — groundwave propagation curves (Graphs 1–20)
- Mixed-path method: "Kirke method" / equivalent-distance method, per
  §73.183(e), described in FCC MM Docket 88-510 (FCC 88-326)

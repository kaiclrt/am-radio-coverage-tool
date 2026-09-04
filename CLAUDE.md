# Project Context for Claude Code

This file is read automatically by Claude Code at the start of a session.
It summarizes how this project works and where to find deeper context -
it's a pointer/summary, not a replacement for the docs it references.

## What this is

An AM radio ground wave coverage prediction tool, built on FCC's official
groundwave propagation curves (47 CFR §73.184) and terrain-based global
ground conductivity estimation. Full Python propagation engine + Flask API
are complete and tested; a web frontend is the current phase.

## Read these first, in this order

1. **`README.md`** - project overview, roadmap, what's built
2. **`CONTRIBUTING.md`** - how this project actually works: testing
   philosophy, data-provenance discipline, code style, the general shape
   of how a phase gets built. Written from real patterns established
   across the whole project's history, not aspirational guidelines.
3. **`docs/web_ui_stack.md`** - the frontend technology stack, locked in
   and justified (Flask API + React/TypeScript + Vite + Tailwind CSS v4 +
   shadcn/ui + Leaflet/react-leaflet + ESLint/Prettier)
4. **`docs/web_ui_design.md`** - the exact input/output interface design:
   target field strength modes (Primary Service Contour, Day/Night
   Protection Contours, Custom Contour) and power/RMS modes (Licensed
   RMS, Estimate from Power), including the exact subtext copy for each
5. **`docs/api.md`** - the Flask API's endpoints, request/response shapes,
   and hardening (rate limits, input bounds) the frontend needs to work
   within (e.g. `n_radials` capped at 360, contour/profile endpoints
   rate-limited to 10/minute)
6. The other `docs/*.md` files cover the Python propagation engine itself
   (digitization, interpolation, terrain conductivity, Kirke method,
   radial/coverage-map calculators) - read these if working on `src/` or
   `api/`, not usually needed for pure frontend work.

## How this project works (condensed from CONTRIBUTING.md)

- **Validate against real data before trusting a change, not just
  existing tests.** This project has caught multiple real bugs (a
  digitizer ordering bug, an inverted interpolation weight, an off-by-one
  RMS formula caught via comparison against a real textbook and a real
  NTC station permit) specifically because changes were checked against
  ground truth, not just "tests still pass."
- **Self-consistency checks over hand-computed expected values** where
  possible - e.g. testing that splitting a uniform path into fake
  segments gives the same result as one segment.
- **Document abandoned approaches**, not just what was kept - several
  modules have comments explaining an earlier approach that was tried and
  replaced, so it doesn't get silently reintroduced later.
- **Be honest about limitations in the docs**, not just code comments -
  every `docs/*.md` file has a "Known limitations" section.
- **Confirm data licensing explicitly** before using any new external
  source - this project deliberately avoided a paid/copyrighted dataset
  (ITU-R P.832) after checking its actual terms, building a free
  alternative instead.
- **Every phase gets its own `docs/<topic>.md`** file (methodology,
  validation, limitations), plus a `CHANGELOG.md` entry and a README
  roadmap checkbox update.

## Code quality tooling already in place (Python side)

- **ruff** (lint) + **mypy** (types), both configured deliberately
  leniently rather than maximally strict - see `[tool.ruff.lint]` and
  `[tool.mypy]` in `pyproject.toml` for the reasoning. Both wired into CI
  (`.github/workflows/tests.yml`).
- Apply the same philosophy to the frontend: **ESLint + Prettier**,
  catching real issues without being maximally opinionated, wired into
  the same CI workflow once frontend work begins.

## Current task: frontend scaffolding

Build `frontend/` per the stack and design docs above. The Flask API
(`api/app.py`) is already complete, tested, and hardened - the frontend's
job is to consume it, not duplicate any of its logic. Key things the
frontend needs to handle correctly (from `docs/web_ui_design.md` and
`docs/api.md`):

- Three target-field-strength modes, with Day/Night needing **two**
  simultaneous contour results shown on the map at once (the API's
  `targets` object already supports this - pass e.g.
  `{"day": 0.5, "night": 2.5}`)
- Two RMS/power input modes, with "Estimate from Power" requiring an
  editable result field and a persistent warning banner (not just a
  one-time disclaimer)
- Graceful handling of the API's per-bearing partial-failure shape
  (`distance_km: null` + `error` field on a bearing that didn't reach its
  target) - don't let one bad bearing break the whole map render
- Respect the API's rate limits and input bounds when designing request
  patterns (e.g. don't fire a new API request on every keystroke of a
  numeric input - debounce, or require explicit submission)

## Repo structure

```
am-radio-coverage-tool/
├── src/               Python propagation engine (curves, terrain, kirke,
│                      radial, coverage_map, gwdigitizer) - stable, tested
├── api/               Flask API wrapping src/ as JSON - stable, tested
├── frontend/           <- build this
├── tests/             Python tests (pytest)
├── data/              Digitized FCC curve data (committed, small)
├── docs/              Per-phase methodology/design docs (see above)
└── .github/workflows/ CI (currently Python-only; extend for frontend)
```

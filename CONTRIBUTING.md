# Contributing

This project follows a few conventions that emerged organically during
development and are worth keeping consistent going forward - both for
outside contributors and for future-you picking this back up after a
break.

## Development philosophy

**Validate against real data before trusting a change, not just against
existing tests.** Several real bugs in this project were only caught
because a change was checked against the actual FCC source PDFs, real
WorldCover queries, or a visual overlay against the original chart - not
just because the existing test suite still passed. Tests can be wrong or
incomplete; the source data doesn't lie. When touching anything in
`src/gwdigitizer/` specifically, re-run `tests/test_digitizer.py` against
real FCC PDFs (`GW_GRAPHS_DIR=/path/to/pdfs`) before considering the
change done, even for changes that look purely cosmetic (e.g. reformatting
code) - see the ruff cleanup in this project's history for a case where
that discipline mattered.

**Prefer self-consistency checks over hand-computed expected values,
where possible.** A recurring, effective testing pattern in this project:
if a function is fed a degenerate/trivial input, does it reduce to
something independently verifiable? E.g. `mixed_path_field_strength()`
tested against a *uniform* path split into multiple fake segments -
if the segment-boundary math has a bug, splitting a uniform path would
reveal it as a discontinuity, even though there's no real conductivity
change to get "wrong." This catches a wider class of bugs than
computing one hand-checked example.

**Document what you tried and abandoned, not just what you kept.**
Several modules have comments explaining an earlier approach that was
tried and replaced (e.g. `gwdigitizer/core.py`'s comment on why
legend-based curve labeling was replaced by rank-order labeling). This
matters because the "obvious" first approach is often the one that turns
out to be fragile, and a future contributor (including future-you) might
otherwise reintroduce it.

**Be honest about limitations in the docs, not just in code comments.**
Every `docs/*.md` file has a "Known limitations" or equivalent section.
Approximations, heuristics, and untested edge cases are named explicitly
rather than glossed over - e.g. `docs/conductivity.md`'s note on the
untested large-lake edge case in the ocean-fallback logic.

## Data provenance and licensing

Before adding any new external data source, confirm its license
explicitly - don't assume "publicly accessible" means "freely
redistributable." This project deliberately avoided ITU-R P.832 (a paid,
copyrighted dataset) after specifically checking its terms, and
`docs/conductivity.md`/`data/digitized_curves/` document the license of
every data source actually used. If a source is copyrighted but usable at
runtime (e.g. via a live API), that's different from being safe to bundle
in the repo - keep that distinction explicit in any new data integration.

## Testing conventions

- **Offline tests are the default** and should not require network access
  or external files. Mock dependencies (see `tests/test_radial.py`,
  `tests/test_coverage_map.py` for the pattern - `unittest.mock.patch` on
  `terrain.get_conductivity`) rather than skipping coverage entirely.
- **Live/network tests are opt-in**, gated behind an environment variable
  (`RUN_LIVE_TERRAIN_TESTS=1`) and skipped by default - including in CI.
  This keeps CI fast and independent of external service availability,
  while still giving a real end-to-end check available on demand.
- **`test_digitizer.py` needs the FCC's source PDFs** (`GW_GRAPHS_DIR=...`)
  and is excluded from CI entirely for that reason (see
  `scripts/digitize_all.py`'s docstring for why those PDFs aren't
  committed to the repo).
- Run the full offline suite before committing:
  ```bash
  python -m pytest tests/ --ignore=tests/test_digitizer.py -v
  ```

## Code style

- **ruff** enforces a deliberately conservative rule set (pycodestyle
  errors, pyflakes, import sorting, pyupgrade) - see the comment in
  `pyproject.toml`'s `[tool.ruff.lint]` section for why more opinionated
  rule categories (security-lint, blind-except, simplify) are excluded.
  Run `ruff check src/ tests/ scripts/` before committing; CI enforces
  this too.
- No enforced type hints yet (a documented gap - see the project roadmap).

## Commit and documentation conventions

- Commit messages explain **why**, not just what - especially for bug
  fixes, where the message should describe what was actually wrong, not
  just "fix bug." See this project's git history for the established
  tone/detail level.
- Each major phase/feature gets a `docs/<topic>.md` file covering
  methodology, validation approach, and known limitations - not just a
  docstring. Update `CHANGELOG.md` and the README roadmap checklist
  alongside any phase-level change.
- If a change reveals that existing documentation is stale (this has
  happened more than once in this project - see the CHANGELOG's "Fixed"
  section), fix the documentation in the same change rather than leaving
  it for later.

## Adding a new capability

Rough shape that's worked well so far, based on how each phase in this
project was actually built:

1. Scope it narrowly and validate the approach against real data/sources
   early, before writing much code around it.
2. Build the core logic with offline-testable units where possible (mock
   what needs network/external access).
3. Test degenerate/self-consistent cases first, then real/asymmetric
   cases.
4. Write the `docs/<topic>.md` file - this often surfaces gaps or
   inconsistencies worth fixing before calling it done.
5. Update `README.md`'s roadmap and `CHANGELOG.md`.
6. Make sure CI is green (tests + ruff) before considering it complete.

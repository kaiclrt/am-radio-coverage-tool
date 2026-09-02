# Web UI Technology Stack

Finalized before implementation, alongside [`web_ui_design.md`](web_ui_design.md)
(the input/output interface design).

| Layer | Choice | Why |
|---|---|---|
| Backend API | Flask, wrapping `src/propagation/` as JSON endpoints | Keeps all propagation logic exactly where it already lives and is tested; Flask is a thin, familiar layer on top (matches prior tools in this broader project ecosystem) |
| Frontend framework | React + TypeScript | Matches the project owner's active learning path; TypeScript continues the type-safety discipline already established on the Python side (`mypy`), especially valuable given the amount of structured data (bearings, contour results, profile points) already modeled as `TypedDict`s in `coverage_map.py` |
| Build tool | Vite | Current standard for React projects; fast, minimal config |
| Styling | Tailwind CSS | Utility-first, no separate CSS files to maintain, pairs naturally with React components |
| Components | shadcn/ui | Accessible, pre-styled components sitting on Tailwind; source is copied into the repo rather than an opaque npm dependency, so components stay customizable |
| Map | Leaflet, via `react-leaflet` | Free, open-source, no API key required - the Mapbox/Google Maps alternatives would need a key and usage billing for no real benefit here |
| JS/TS lint & format | ESLint + Prettier | Mirrors the ruff + mypy discipline already in place on the Python side; wired into the same CI workflow |

## Project structure

```
am-radio-coverage-tool/
├── src/               (existing Python propagation engine - unchanged)
├── api/               (new: Flask app wrapping src/ as JSON endpoints)
├── frontend/          (new: Vite + React + TS app)
│   ├── src/
│   │   ├── components/
│   │   ├── lib/
│   │   └── ...
│   └── package.json
├── tests/             (existing Python tests - unchanged)
└── ...
```

## Rejected alternatives (for context)

- **Flask + Jinja templates + vanilla JS**: simpler (matches the pattern
  used by earlier, smaller internal tools), but this project's actual UI
  needs - an interactive map, live recalculation as inputs change,
  per-bearing result displays - are exactly what a proper frontend
  framework is good at. Chose the slightly higher-complexity option
  deliberately rather than defaulting to the simpler one.
- **Mapbox GL / Google Maps**: would require an API key and usage-based
  billing; Leaflet does everything needed here for free.

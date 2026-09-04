# Frontend — AM Radio Coverage Calculator

Web UI for the coverage engine. Consumes the Flask API in [`../api`](../api)
(`python api/app.py`, documented in [`../docs/api.md`](../docs/api.md)); it
does **not** duplicate any propagation logic.

Stack (locked in [`../docs/web_ui_stack.md`](../docs/web_ui_stack.md)):
Vite + React + TypeScript, Tailwind CSS v4, shadcn/ui (source copied into
`src/components/ui/`), Leaflet via react-leaflet, ESLint + Prettier.

## Prerequisites

Node.js ≥ 20 and npm. Neither is bundled with this repo; install from
<https://nodejs.org/> or via `nvm`. (This folder was scaffolded without a
local Node install, so `node_modules/` and `package-lock.json` do not exist
yet — the first `npm install` creates them.)

## Running in development

```bash
# 1. Start the API (from the repo root, in its own terminal)
pip install -e .[api]
python api/app.py            # serves http://127.0.0.1:5000

# 2. Start the frontend (from this folder)
npm install
npm run dev                  # serves http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:5000` (see
`vite.config.ts`), so the browser stays same-origin and the API's
restricted CORS is never exercised in dev. Point the proxy elsewhere with
`VITE_API_TARGET`. For a deployed build that talks to an absolute API
origin, set `VITE_API_BASE_URL` at build time instead.

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Vite dev server with HMR |
| `npm run build` | Type-check (`tsc -b`) then production build to `dist/` |
| `npm run preview` | Serve the built `dist/` locally |
| `npm run lint` | ESLint (flat config, `eslint.config.js`) |
| `npm run format` | Prettier write over `src/` |
| `npm run format:check` | Prettier check (CI-friendly) |

## How the design maps to the code

See [`../docs/web_ui_design.md`](../docs/web_ui_design.md) for the full
interface design. Implementation:

- **Target field strength** — `src/components/TargetFieldStrengthField.tsx`.
  Three mutually-exclusive modes (Primary Service Contour / Day-Night
  Protection Contours / Custom Contour). Day-Night sends
  `targets: {day, night}` in one request and renders **two** contours on
  the map at once (distinct colour, dashed for night). Subtext copy is
  verbatim from the design doc.
- **Power / RMS** — `src/components/PowerRmsField.tsx`. Licensed/Measured
  RMS (direct entry) or Estimate from Transmitter Power (kW →
  `POST /api/estimate-rms` → result written into an **editable** RMS field
  so it can be adjusted down for real-world losses). A **persistent**
  warning banner is shown the whole time Estimate mode is active, not just
  once — it survives re-renders and toggling away and back.
- **Composition** — `src/lib/coverage.ts` (`buildContourRequest`) combines
  whichever target mode with whichever power mode into a single
  `/api/coverage/contour` body.
- **Partial failure** — a bearing that didn't reach its target comes back
  as `distance_km: null` + `error`. `bearingsToLatLngs` drops those before
  building the Leaflet polygon (one bad radial never breaks the ring), and
  `ResultsPanel` lists them explicitly with their error text.
- **Rate limits / input bounds** — recalculation is an explicit button
  press, never per-keystroke. The kW → RMS estimate is debounced (500 ms).
  Both respect the caps in `../docs/api.md` (coverage 10/min, estimate
  30/min, combined sample budget). A `429` surfaces as a readable message.

## Notes

- `src/components/ui/` is shadcn/ui source, copied in on purpose (see the
  stack doc) — edit it directly; ESLint ignores it.
- Tailwind v4 is configured entirely in `src/index.css` (`@import
  "tailwindcss"`, `@theme`, CSS variables) + the `@tailwindcss/vite`
  plugin — there is no `tailwind.config.js`.

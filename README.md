# AM Radio Coverage Calculator

Ground wave coverage prediction tool for AM broadcast stations, built on the
FCC's official groundwave propagation curves (47 CFR §73.184) and ground
conductivity data (FCC Figure M3).

## Status: Phase 1 complete — curve digitization

All 20 FCC groundwave propagation graphs (covering 535–1705 kHz in 20 frequency
bands) have been digitized from the official vector PDFs into structured,
interpolatable (distance_km, field_strength_mV/m) data per conductivity value
(0.1 to 5000 mS/m).

See [`docs/digitization.md`](docs/digitization.md) for methodology and known
limitations.

## Roadmap

- [x] Digitize all 20 FCC groundwave graphs
- [x] Distance↔field-strength interpolation (both directions, log-log,
      including interpolation across conductivity values not exactly on
      the standard FCC curves)
- [x] Terrain-based global ground conductivity estimation (ESA WorldCover +
      FCC's 1939 terrain-conductivity table + offline ocean/lake
      disambiguation) - see `docs/conductivity.md`
- [ ] FCC M3 conductivity dataset (`m3.seq`) for higher-precision US data
      (optional upgrade, deferred - terrain-based estimation covers the US
      too, just less precisely)
- [ ] Implement Kirke/equivalent-distance mixed-path method (§73.183(e))
- [ ] Single-radial coverage calculator (TX location + power + bearing → contour distance)
- [ ] 8-cardinal-radial coverage map, with optional finer angular resolution
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

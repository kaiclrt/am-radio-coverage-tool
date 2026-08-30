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

- [x] Digitize all 20 FCC groundwave graphs (this phase)
- [ ] Build distance↔field-strength interpolation (both directions, log-log)
- [ ] Parse FCC M3 ground conductivity dataset (`m3.seq`)
- [ ] Implement Kirke/equivalent-distance mixed-path method (§73.183(e))
- [ ] Single-radial coverage calculator (TX location + power + bearing → contour distance)
- [ ] 8-cardinal-radial coverage map, with optional finer angular resolution
- [ ] Web UI

## Data provenance & license

- FCC groundwave curves: public domain (U.S. government work), sourced from
  https://www.fcc.gov/node/38972
- FCC M3 conductivity map: public domain, sourced from FCC Media Bureau
- Digitized derivative data and all code in this repo: MIT License (see LICENSE)

## Regulatory basis

- 47 CFR §73.183 — groundwave field strength calculation procedures
- 47 CFR §73.184 — groundwave propagation curves (Graphs 1–20)
- Mixed-path method: "Kirke method" / equivalent-distance method, per
  §73.183(e), described in FCC MM Docket 88-510 (FCC 88-326)

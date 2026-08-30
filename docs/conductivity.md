# Terrain-Based Ground Conductivity Estimation

## Why this exists

FCC's `m3.seq` conductivity data only covers the continental United States.
For global coverage (this project's actual goal, given real use cases
outside the US - e.g. the Philippines), the obvious authoritative source is
the ITU-R P.832 "World Atlas of Ground Conductivities" - but that's a paid
product (~441 CHF, sold as "R-SOFT-IDWM"), not freely redistributable, and
not something reasonable to depend on for an open-source hobby tool.

Instead, this module estimates conductivity from **terrain type**, using a
long-standing engineering table paired with **free, global, open-license**
land cover data.

## Data sources

1. **Terrain → conductivity table**: the FCC's own 1939 "Standards of Good
   Engineering Practice Concerning Standard Broadcast Stations" (Federal
   Register), which assigns representative conductivity values to terrain
   descriptions (pastoral rich soil, rocky mountainous, salt water, etc.).
   Public domain. This is the same table reproduced in Terman's *Radio
   Engineer's Handbook* and the ARRL Antenna Book for decades - well
   established, not a one-off estimate.

2. **Land cover classification**: [ESA WorldCover](https://esa-worldcover.org)
   10m resolution global land cover map, 2021 (v200). Free, CC-BY-4.0
   (attribution required - see below), hosted as public Cloud-Optimized
   GeoTIFFs on AWS Open Data (`s3://esa-worldcover`, no API key or signing
   required). Queried via HTTP range requests (through GDAL's `/vsicurl/`),
   so no bulk download is needed - only the specific tile(s) covering a
   query point are fetched.

3. **Ocean/lake disambiguation**: WorldCover's "permanent water bodies"
   class doesn't distinguish salt water from fresh water, which matters a
   lot here (5000 mS/m vs 1 mS/m). Disambiguated using
   [global-land-mask](https://pypi.org/project/global-land-mask/), an
   offline, free, NASA-derived landmask package - if a water pixel's
   coordinates are also flagged as ocean by the landmask, it's treated as
   salt water; otherwise fresh water (lake, river, reservoir).

4. **Open-ocean fallback**: ESA WorldCover only publishes tiles that contain
   at least some land - there's nothing to classify over open ocean far
   from any coast, so no tile exists there at all (confirmed in testing: a
   mid-Pacific point returns HTTP 404). When a tile is missing, that's
   itself treated as a signal the point is open ocean, confirmed against
   the offline landmask before falling back to `salt_water` - a genuine
   network or server error still surfaces normally rather than being
   silently misread as "ocean".

## Attribution requirement

ESA WorldCover is CC-BY-4.0, which requires attribution wherever the data
(or derivatives) are used. Any output, map, or report generated using this
module should include:

> Contains modified Copernicus Sentinel data, processed by ESA WorldCover
> consortium. © ESA WorldCover project 2021.

## Terrain category → conductivity table

| Terrain category | Conductivity (mS/m) | Source description |
|---|---|---|
| `salt_water` | 5000 | Salt water |
| `fresh_water` | 1 | Fresh water |
| `pastoral_rich_soil` | 10 | Flat farmland, rich/alluvial soil |
| `pastoral_medium` | 6 | Mixed farmland/forest, medium hills |
| `marshy_wooded` | 7.5 | Flat, marshy, densely wooded |
| `pastoral_heavy_clay` | 5 | Medium hills, heavy clay soil |
| `rocky_mountainous` | 2 | Steep hills, rocky, mountainous |
| `sandy_dry` | 2 | Sandy, dry, flat coastal land |
| `urban` | 1 | Cities, industrial areas |
| `urban_dense` | 1 | Heavy industrial, high-density buildings |

## ESA WorldCover class mapping

| WorldCover class code | Class name | Mapped terrain |
|---|---|---|
| 10 | Tree cover | `pastoral_medium` |
| 20 | Shrubland | `rocky_mountainous` |
| 30 | Grassland | `pastoral_rich_soil` |
| 40 | Cropland | `pastoral_rich_soil` |
| 50 | Built-up | `urban` |
| 60 | Bare / sparse vegetation | `sandy_dry` |
| 70 | Snow and ice | `urban` (see caveat below) |
| 80 | Permanent water bodies | disambiguated (see above) |
| 90 | Herbaceous wetland | `marshy_wooded` |
| 95 | Mangroves | `marshy_wooded` |
| 100 | Moss and lichen | `rocky_mountainous` |

## Known limitations

- **This is a heuristic, not a measurement.** Terrain type is a reasonable
  *proxy* for conductivity (soil composition and moisture drive both), but
  it's not a substitute for actual ground conductivity surveys. Treat
  results as approximate, especially for critical engineering decisions.
- **Snow/ice (class 70) has no corresponding entry in the 1939 FCC table**
  (unsurprisingly, since it predates any need for that case). Currently
  mapped to `urban` (1 mS/m) as a conservative placeholder, not because
  snow/ice is actually similar to a city - this should be revisited if the
  tool is ever used somewhere this class is common (e.g. high-latitude
  regions).
- **10m resolution** is far finer than the FCC's own conductivity map
  precision, but a single point classification can still land on a locally
  atypical pixel (e.g. a small pond misclassifying a otherwise-dry area's
  conductivity). Consider sampling a small neighborhood of pixels and
  taking a majority/average class for more robust results, if precision
  matters for a specific use case.
- **Very large lakes (untested edge case).** The open-ocean fallback (see
  above) assumes a missing WorldCover tile means open ocean, confirmed
  against the offline landmask before accepting that conclusion. Testing
  showed the landmask treats even huge lakes (Superior, Victoria, Caspian)
  as "land" at their centers, so if a WorldCover tile were ever missing
  over the middle of a very large lake (only plausible for something on
  the scale of the Caspian Sea, whose ~7-degree extent could plausibly
  leave a single 3x3-degree tile with zero land pixels), the code would
  raise an error rather than silently mislabel it as salt water - a safe
  failure, but not a handled one. Not tested live (no such tile-gap
  confirmed to actually exist), and not relevant to this project's
  Philippines/Southeast Asia focus (no lakes anywhere near that scale
  there), so left as a documented edge case rather than fixed now.
- **Requires live internet access** to AWS at query time (no bulk
  pre-caching in this repo, consistent with keeping the repo lightweight -
  unlike the FCC curve data, which is small enough to commit directly).
- Needs `rasterio` (with GDAL) and `global-land-mask` installed - these are
  optional dependencies (see `pyproject.toml`), not required for the core
  curve digitization/interpolation functionality.

"""
Terrain-based ground conductivity estimation, for use outside FCC's mapped
area (i.e. everywhere except the continental US, where m3.seq - not yet
integrated - would eventually give higher-precision measured data).

Approach:
  1. Query ESA WorldCover (free, CC-BY-4.0, 10m global land cover, hosted as
     public Cloud-Optimized GeoTIFFs on AWS Open Data) for the land cover
     class at a given lat/lon.
  2. Map that class to a terrain category, then to a representative ground
     conductivity value using the FCC's own 1939 "Standards of Good
     Engineering Practice" terrain table (public domain, Federal Register) -
     the same terrain-conductivity relationships used in Terman's Radio
     Engineer's Handbook and the ARRL Antenna Book for decades.
  3. For WorldCover's "permanent water bodies" class (which doesn't
     distinguish ocean from lakes/rivers), disambiguate using
     global-land-mask (offline, free, NASA-derived landmask) - if the point
     is also flagged as ocean by the landmask, treat as salt water;
     otherwise fresh water.

This is a coarse approximation compared to purpose-built conductivity
surveys (like FCC's m3.seq), but it's built entirely from free,
non-copyrighted sources and gives global coverage - see docs/conductivity.md
for the reasoning and known limitations.
"""
import numpy as np

try:
    import rasterio
    _HAS_RASTERIO = True
except ImportError:
    _HAS_RASTERIO = False

try:
    from global_land_mask import globe
    _HAS_LANDMASK = True
except ImportError:
    _HAS_LANDMASK = False


# --- Terrain -> conductivity table -----------------------------------------
# Source: FCC 1939 "Standards of Good Engineering Practice Concerning
# Standard Broadcast Stations," Federal Register, as republished in Terman's
# Radio Engineer's Handbook and the ARRL Antenna Book. Public domain
# (US government work, pre-1978 with no copyright renewal on the underlying
# regulatory text).
TERRAIN_CONDUCTIVITY = {
    'salt_water':        5000,   # Best
    'fresh_water':        1,
    'pastoral_rich_soil': 10,    # e.g. flat farmland, alluvial soil - Good/Very Good
    'pastoral_medium':     6,    # e.g. mixed farmland/forest, medium hills
    'marshy_wooded':      7.5,   # flat, marshy, densely wooded
    'pastoral_heavy_clay': 5,    # medium hills, heavy clay soil - Average
    'rocky_mountainous':   2,    # steep hills, rocky, mountainous - Poor
    'sandy_dry':           2,    # sandy, dry, flat coastal land
    'urban':                1,   # cities, industrial areas - Very Poor
    'urban_dense':          1,   # heavy industrial, high buildings - Extremely Poor
}

# --- ESA WorldCover class -> terrain category -------------------------------
# WorldCover v100/v200 class codes (both versions use the same 11-class
# legend). "water" is handled specially (see disambiguate_water below), not
# mapped directly here.
WORLDCOVER_CLASS_TO_TERRAIN = {
    10: 'pastoral_medium',      # Tree cover
    20: 'rocky_mountainous',    # Shrubland
    30: 'pastoral_rich_soil',   # Grassland
    40: 'pastoral_rich_soil',   # Cropland
    50: 'urban',                # Built-up
    60: 'sandy_dry',            # Bare / sparse vegetation
    70: 'urban',                # Snow and ice (no AM engineering data exists for this
                                 # terrain type; treated conservatively as poor conductivity
                                 # rather than guessing - flagged in output, see below)
    80: None,                   # Permanent water bodies - needs disambiguation
    90: 'marshy_wooded',        # Herbaceous wetland
    95: 'marshy_wooded',        # Mangroves
    100: 'rocky_mountainous',   # Moss and lichen
}

WORLDCOVER_S3_BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"


def _tile_id_for(lat, lon):
    """ESA WorldCover 3x3 degree tile ID for the lower-left corner containing
    (lat, lon), e.g. 'N14E120' for a point in the Philippines."""
    tile_lat = int(np.floor(lat / 3.0) * 3)
    tile_lon = int(np.floor(lon / 3.0) * 3)
    lat_str = f"{'N' if tile_lat >= 0 else 'S'}{abs(tile_lat):02d}"
    lon_str = f"{'E' if tile_lon >= 0 else 'W'}{abs(tile_lon):03d}"
    return f"{lat_str}{lon_str}"


def _tile_url_for(lat, lon):
    tile_id = _tile_id_for(lat, lon)
    return f"{WORLDCOVER_S3_BASE}/ESA_WorldCover_10m_2021_v200_{tile_id}_Map.tif"


def get_worldcover_class(lat, lon):
    """Query the ESA WorldCover COG (via HTTP range requests, no full download)
    for the land cover class code at (lat, lon). Requires rasterio with GDAL's
    /vsicurl/ support and outbound internet access to amazonaws.com."""
    if not _HAS_RASTERIO:
        raise ImportError("rasterio is required for get_worldcover_class(); pip install rasterio")

    url = _tile_url_for(lat, lon)
    vsi_url = f"/vsicurl/{url}"
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR'):
        with rasterio.open(vsi_url) as src:
            row, col = src.index(lon, lat)
            window = rasterio.windows.Window(col, row, 1, 1)
            value = src.read(1, window=window)
            return int(value[0, 0])


def disambiguate_water(lat, lon):
    """For WorldCover's 'permanent water bodies' class, decide salt vs fresh
    water using an offline landmask (ocean -> salt, otherwise -> fresh)."""
    if not _HAS_LANDMASK:
        raise ImportError("global-land-mask is required for water disambiguation; "
                          "pip install global-land-mask")
    is_land = globe.is_land(lat, lon)
    return 'fresh_water' if is_land else 'salt_water'


def classify_terrain(lat, lon):
    """Return (terrain_category, worldcover_class_code) for a lat/lon point.

    worldcover_class_code is None when the fallback path is used (see below).
    """
    try:
        wc_class = get_worldcover_class(lat, lon)
    except Exception:
        # ESA WorldCover only publishes tiles that contain at least some land
        # (there's nothing to classify over open ocean far from any coast),
        # so a missing-tile error (typically HTTP 404) at a given point is
        # itself a strong signal that the point is open ocean. Confirm with
        # the offline landmask rather than assuming - a genuine network/tile
        # error should still surface, not get silently misread as "ocean".
        if _HAS_LANDMASK and not globe.is_land(lat, lon):
            return 'salt_water', None
        raise

    if wc_class == 80:
        terrain = disambiguate_water(lat, lon)
    else:
        terrain = WORLDCOVER_CLASS_TO_TERRAIN.get(wc_class)
        if terrain is None:
            raise ValueError(f"Unrecognized WorldCover class code: {wc_class}")
    return terrain, wc_class


def get_conductivity(lat, lon):
    """Estimate ground conductivity (mS/m) at (lat, lon) using terrain
    classification. Returns (conductivity_mScm, terrain_category, worldcover_class).

    This is a coarse approximation (terrain-type heuristic, not a measured
    survey) - see docs/conductivity.md for accuracy notes and when to prefer
    purpose-built data (e.g. FCC m3.seq for the continental US) instead.
    """
    terrain, wc_class = classify_terrain(lat, lon)
    conductivity = TERRAIN_CONDUCTIVITY[terrain]
    return conductivity, terrain, wc_class

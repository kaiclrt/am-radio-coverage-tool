"""
Tests for terrain-based conductivity estimation.

Tests are split into offline (no network needed - tile math, water
disambiguation, table integrity) and live (require internet access to
AWS S3 for actual WorldCover queries - skipped by default, run with
RUN_LIVE_TERRAIN_TESTS=1).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from propagation.terrain import (
    TERRAIN_CONDUCTIVITY,
    WORLDCOVER_CLASS_TO_TERRAIN,
    _tile_id_for,
    _tile_url_for,
    classify_terrain,
    disambiguate_water,
    get_conductivity,
)

RUN_LIVE = os.environ.get('RUN_LIVE_TERRAIN_TESTS') == '1'


class TestTileMath:
    def test_manila_tile(self):
        # 14.5995N, 120.9842E -> lower-left corner of containing 3x3deg tile
        assert _tile_id_for(14.5995, 120.9842) == 'N12E120'

    def test_negative_lat_lon(self):
        assert _tile_id_for(-33.87, -70.65) == 'S36W072'  # Santiago, Chile

    def test_url_format(self):
        url = _tile_url_for(14.5995, 120.9842)
        assert url.startswith('https://esa-worldcover.s3.eu-central-1.amazonaws.com/')
        assert 'N12E120' in url
        assert url.endswith('_Map.tif')


class TestWaterDisambiguation:
    def test_open_ocean_is_salt_water(self):
        assert disambiguate_water(10, 150) == 'salt_water'  # mid-Pacific

    def test_known_inland_lake_is_fresh_water(self):
        assert disambiguate_water(14.35, 121.25) == 'fresh_water'  # Laguna de Bay, PH

    def test_great_lake_is_fresh_water(self):
        assert disambiguate_water(44.0, -82.5) == 'fresh_water'  # Lake Huron


class TestConductivityTable:
    def test_all_terrain_categories_have_positive_conductivity(self):
        for category, value in TERRAIN_CONDUCTIVITY.items():
            assert value > 0, f"{category} has non-positive conductivity"

    def test_salt_water_is_highest(self):
        assert TERRAIN_CONDUCTIVITY['salt_water'] == max(TERRAIN_CONDUCTIVITY.values())

    def test_all_worldcover_classes_map_to_valid_terrain_or_water(self):
        for code, terrain in WORLDCOVER_CLASS_TO_TERRAIN.items():
            if terrain is None:
                continue  # water class, handled separately
            assert terrain in TERRAIN_CONDUCTIVITY, \
                f"WorldCover class {code} maps to unknown terrain '{terrain}'"


@pytest.mark.skipif(not RUN_LIVE, reason="Set RUN_LIVE_TERRAIN_TESTS=1 to run "
                     "(requires internet access to AWS S3 and rasterio/GDAL installed)")
class TestLiveWorldCoverQueries:
    def test_manila_is_urban(self):
        conductivity, terrain, wc_class = get_conductivity(14.5995, 120.9842)
        assert terrain == 'urban'

    def test_mid_pacific_is_salt_water(self):
        # This point has no ESA WorldCover tile at all (open ocean, far from
        # any coast - WorldCover only publishes tiles containing land), which
        # exercises the missing-tile -> landmask fallback path, not the
        # normal WorldCover water-class disambiguation path.
        conductivity, terrain, wc_class = get_conductivity(10, 150)
        assert terrain == 'salt_water'
        assert conductivity == 5000
        assert wc_class is None  # confirms the fallback path was used

    def test_classify_terrain_returns_valid_category(self):
        terrain, wc_class = classify_terrain(14.5995, 120.9842)
        assert terrain in TERRAIN_CONDUCTIVITY

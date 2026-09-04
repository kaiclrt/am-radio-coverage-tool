"""
Tests for terrain-based conductivity estimation.

Tests are split into offline (no network needed - tile math, water
disambiguation, table integrity) and live (require internet access to
AWS S3 for actual WorldCover queries - skipped by default, run with
RUN_LIVE_TERRAIN_TESTS=1).
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from propagation import terrain as terrain_mod
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


class TestNodataHandling:
    """WorldCover returns 0 (nodata) - not a land-cover class - for open
    water inside a tile that also covers land, which is what a sea-facing
    bearing from a coastal transmitter hits. Regression tests for that path
    (previously raised 'Unrecognized WorldCover class code: 0')."""

    def test_nodata_over_water_falls_back_to_salt_water(self):
        with patch.object(terrain_mod, 'get_worldcover_class', return_value=0), \
             patch.object(terrain_mod.globe, 'is_land', return_value=False):
            terrain, wc_class = classify_terrain(14.55, 120.30)  # Manila Bay
        assert terrain == 'salt_water'
        assert wc_class is None  # signals the fallback path was taken

    def test_nodata_conductivity_is_salt_water_value(self):
        with patch.object(terrain_mod, 'get_worldcover_class', return_value=0), \
             patch.object(terrain_mod.globe, 'is_land', return_value=False):
            conductivity, terrain, wc_class = get_conductivity(14.55, 120.30)
        assert conductivity == TERRAIN_CONDUCTIVITY['salt_water']
        assert terrain == 'salt_water'

    def test_nodata_over_land_still_raises(self):
        # nodata where the landmask insists it's land is a genuine gap, not a
        # sea bearing - must surface, not get silently mislabelled as ocean.
        with patch.object(terrain_mod, 'get_worldcover_class', return_value=0), \
             patch.object(terrain_mod.globe, 'is_land', return_value=True):
            with pytest.raises(ValueError, match='nodata'):
                classify_terrain(14.60, 121.00)

    def test_genuine_unrecognized_class_still_raises(self):
        # A real out-of-legend code (not 0) should still be a hard error.
        with patch.object(terrain_mod, 'get_worldcover_class', return_value=42):
            with pytest.raises(ValueError, match='Unrecognized WorldCover class code: 42'):
                classify_terrain(14.60, 121.00)


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

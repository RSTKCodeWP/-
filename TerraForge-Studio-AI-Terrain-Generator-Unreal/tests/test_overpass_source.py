"""
Tests for the Overpass vector source.

The response fixtures below reproduce the shape Overpass returns for an
``out geom`` query, including the messy tag values that appear in real OSM
data. The HTTP layer is stubbed, so these run offline.

NOTE: unlike the SRTM source, the live request path could not be exercised
against the real service from the development environment - outbound requests
to overpass-api.de are blocked by egress policy. Parsing, query construction,
retry and fallback behaviour are covered here; the network round-trip itself is
covered only by the ``network`` marked test, which is deselected by default.
"""

from __future__ import annotations

import json

import pytest

from realworldmapgen.core.sources.base import BoundingBox, DataSourceConfig
from realworldmapgen.core.sources.overpass import OverpassSource

BBOX = BoundingBox(north=37.802, south=37.795, east=-122.398, west=-122.408)


@pytest.fixture
def source() -> OverpassSource:
    return OverpassSource(
        DataSourceConfig(enabled=True, timeout=30, retry_attempts=2),
        endpoints=["https://overpass.example/api"],
    )


#: A road, a building and an untagged way, shaped as Overpass returns them.
SAMPLE_RESPONSE = {
    "elements": [
        {
            "type": "way",
            "id": 12345,
            "geometry": [
                {"lat": 37.7960, "lon": -122.4070},
                {"lat": 37.7970, "lon": -122.4060},
                {"lat": 37.7980, "lon": -122.4050},
            ],
            "tags": {
                "highway": "residential",
                "name": "Example Street",
                "lanes": "2",
                "maxspeed": "50",
                "surface": "asphalt",
                "oneway": "yes",
            },
        },
        {
            "type": "way",
            "id": 67890,
            "geometry": [
                {"lat": 37.7990, "lon": -122.4040},
                {"lat": 37.7995, "lon": -122.4040},
                {"lat": 37.7995, "lon": -122.4030},
                {"lat": 37.7990, "lon": -122.4030},
            ],
            "tags": {"building": "yes", "building:levels": "4", "height": "12"},
        },
        # No recognised tag: must be skipped rather than emitted untyped.
        {
            "type": "way",
            "id": 11111,
            "geometry": [
                {"lat": 37.7960, "lon": -122.4000},
                {"lat": 37.7961, "lon": -122.4001},
            ],
            "tags": {"barrier": "fence"},
        },
        # Nodes are returned alongside ways and must be ignored.
        {"type": "node", "id": 222, "lat": 37.7, "lon": -122.4, "tags": {"highway": "crossing"}},
    ]
}


def stub_transport(monkeypatch, source, *, responses):
    """Replace httpx.AsyncClient with a scripted stub. Returns the call log."""
    calls = []

    class _Response:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, endpoint, content):
            calls.append((endpoint, content.decode()))
            outcome = responses[min(len(calls) - 1, len(responses) - 1)]
            if isinstance(outcome, Exception):
                raise outcome
            status, payload = outcome
            return _Response(status, payload)

    import realworldmapgen.core.sources.overpass as module

    monkeypatch.setattr(module, "asyncio", module.asyncio)
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return calls


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------
def test_query_uses_overpass_bbox_ordering(source):
    """Overpass expects (south, west, north, east), not the GeoJSON order."""
    query = source._build_query(BBOX, ["roads"])

    assert f"{BBOX.south},{BBOX.west},{BBOX.north},{BBOX.east}" in query


def test_query_requests_geometry(source):
    """`out geom` is what makes ways carry their own coordinates."""
    assert source._build_query(BBOX, ["roads"]).strip().endswith("out geom;")


def test_query_covers_each_requested_type(source):
    query = source._build_query(BBOX, ["roads", "buildings", "landuse"])

    assert '["highway"]' in query
    assert '["building"]' in query
    assert '["landuse"]' in query


def test_query_excludes_footpaths(source):
    query = source._build_query(BBOX, ["roads"])
    assert "footway" in query and "cycleway" in query


def test_query_is_none_without_supported_types(source):
    assert source._build_query(BBOX, ["nonsense"]) is None


# ---------------------------------------------------------------------------
# Response conversion
# ---------------------------------------------------------------------------
def test_roads_become_linestrings(source):
    collection = source._to_geojson(SAMPLE_RESPONSE)
    road = next(f for f in collection["features"] if f["properties"]["type"] == "road")

    assert road["geometry"]["type"] == "LineString"
    assert road["properties"]["name"] == "Example Street"
    assert road["properties"]["lanes"] == 2
    assert road["properties"]["maxspeed"] == 50
    assert road["properties"]["oneway"] is True


def test_coordinates_are_lon_lat(source):
    """GeoJSON is (lon, lat); Overpass reports the two separately."""
    collection = source._to_geojson(SAMPLE_RESPONSE)
    road = next(f for f in collection["features"] if f["properties"]["type"] == "road")

    lon, lat = road["geometry"]["coordinates"][0]
    assert lon == pytest.approx(-122.4070)
    assert lat == pytest.approx(37.7960)


def test_buildings_become_closed_polygons(source):
    collection = source._to_geojson(SAMPLE_RESPONSE)
    building = next(f for f in collection["features"] if f["properties"]["type"] == "building")

    assert building["geometry"]["type"] == "Polygon"
    ring = building["geometry"]["coordinates"][0]
    # A GeoJSON ring must repeat its first position as the last.
    assert ring[0] == ring[-1]
    assert building["properties"]["levels"] == 4


def test_untagged_and_non_way_elements_are_skipped(source):
    collection = source._to_geojson(SAMPLE_RESPONSE)

    ids = {f["properties"]["osm_id"] for f in collection["features"]}
    assert ids == {"12345", "67890"}


def test_degenerate_geometry_is_skipped(source):
    payload = {
        "elements": [
            {"type": "way", "id": 1, "geometry": [{"lat": 1.0, "lon": 2.0}], "tags": {"highway": "residential"}},
            {"type": "way", "id": 2, "geometry": [], "tags": {"building": "yes"}},
        ]
    }
    assert source._to_geojson(payload)["features"] == []


def test_two_point_building_is_skipped(source):
    """A ring needs four positions once closed; two points cannot form an area."""
    payload = {
        "elements": [
            {
                "type": "way",
                "id": 3,
                "geometry": [{"lat": 1.0, "lon": 2.0}, {"lat": 1.1, "lon": 2.1}],
                "tags": {"building": "yes"},
            }
        ]
    }
    assert source._to_geojson(payload)["features"] == []


def test_empty_response_yields_empty_collection(source):
    collection = source._to_geojson({"elements": []})
    assert collection == {"type": "FeatureCollection", "features": []}


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2", 2),
        ("50 mph", 50),
        ("2;3", 2),
        ("  4 ", 4),
        ("none", None),
        ("", None),
        (None, None),
    ],
)
def test_numeric_tags_tolerate_real_world_values(source, raw, expected):
    """OSM numeric tags are free text; parsing must not raise on junk."""
    assert source._parse_int(raw) == expected


def test_output_is_serializable(source):
    """The result is written to disk as GeoJSON, so it must serialize."""
    collection = source._to_geojson(SAMPLE_RESPONSE)
    assert json.loads(json.dumps(collection)) == collection


# ---------------------------------------------------------------------------
# Request path
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_vector_data_returns_features(source, monkeypatch):
    stub_transport(monkeypatch, source, responses=[(200, SAMPLE_RESPONSE)])

    collection = await source.get_vector_data(BBOX, ["roads", "buildings"])

    assert collection is not None
    assert len(collection["features"]) == 2


@pytest.mark.asyncio
async def test_result_is_cached(source, monkeypatch):
    calls = stub_transport(monkeypatch, source, responses=[(200, SAMPLE_RESPONSE)])

    await source.get_vector_data(BBOX, ["roads"])
    await source.get_vector_data(BBOX, ["roads"])

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_oversized_area_is_refused(monkeypatch):
    """Overpass is a shared service; huge boxes are skipped, not submitted."""
    source = OverpassSource(DataSourceConfig(enabled=True), max_area_km2=1.0)
    calls = stub_transport(monkeypatch, source, responses=[(200, SAMPLE_RESPONSE)])

    huge = BoundingBox(north=38.0, south=37.0, east=-122.0, west=-123.0)
    assert await source.get_vector_data(huge, ["roads"]) is None
    assert calls == []


@pytest.mark.asyncio
async def test_rate_limit_is_retried(source, monkeypatch):
    calls = stub_transport(
        monkeypatch, source, responses=[(429, None), (200, SAMPLE_RESPONSE)]
    )
    monkeypatch.setattr("asyncio.sleep", _no_sleep)

    collection = await source.get_vector_data(BBOX, ["roads"])

    assert collection is not None
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_falls_back_to_the_next_endpoint(monkeypatch):
    source = OverpassSource(
        DataSourceConfig(enabled=True, retry_attempts=1),
        endpoints=["https://first.example/api", "https://second.example/api"],
    )
    calls = stub_transport(monkeypatch, source, responses=[(500, None), (200, SAMPLE_RESPONSE)])

    collection = await source.get_vector_data(BBOX, ["roads"])

    assert collection is not None
    assert [endpoint for endpoint, _ in calls] == [
        "https://first.example/api",
        "https://second.example/api",
    ]


@pytest.mark.asyncio
async def test_returns_none_when_every_endpoint_fails(source, monkeypatch):
    stub_transport(monkeypatch, source, responses=[(500, None)])

    assert await source.get_vector_data(BBOX, ["roads"]) is None


@pytest.mark.asyncio
async def test_connection_errors_do_not_propagate(source, monkeypatch):
    stub_transport(monkeypatch, source, responses=[ConnectionError("boom")])
    monkeypatch.setattr("asyncio.sleep", _no_sleep)

    assert await source.get_vector_data(BBOX, ["roads"]) is None


@pytest.mark.asyncio
async def test_elevation_and_imagery_are_not_provided(source):
    assert await source.get_elevation_data(BBOX, 256) is None
    assert await source.get_imagery_data(BBOX, 256) is None


@pytest.mark.asyncio
async def test_availability_follows_the_enabled_flag():
    assert await OverpassSource(DataSourceConfig(enabled=True)).is_available() is True
    assert await OverpassSource(DataSourceConfig(enabled=False)).is_available() is False


async def _no_sleep(_seconds):
    return None


# ---------------------------------------------------------------------------
# Live service (opt-in: pytest -m network)
# ---------------------------------------------------------------------------
@pytest.mark.network
@pytest.mark.asyncio
async def test_real_overpass_returns_roads():
    """Downtown San Francisco has roads; verifies the live request path."""
    live = OverpassSource(DataSourceConfig(enabled=True, timeout=60))

    collection = await live.get_vector_data(BBOX, ["roads"])

    assert collection is not None
    roads = [f for f in collection["features"] if f["properties"]["type"] == "road"]
    assert len(roads) > 0
    assert all(f["geometry"]["type"] == "LineString" for f in roads)

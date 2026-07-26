"""Tile proxy, cache, MBTiles, and tile source registry."""

from __future__ import annotations

import shutil
import sqlite3
import urllib.error
import urllib.request as urlreq
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import Response

from .config import ROOT_DIR, aio, cfg

router = APIRouter()

TILE_CACHE = ROOT_DIR / "tile_cache"
MBTILES_DIR = ROOT_DIR / "mbtiles"

_TILE_MAX = cfg.TILE_CACHE_MAX
_TILE_MAX_BYTES = 2 * 1024 * 1024
_tile_count = -1


TILE_URLS = {
    "6": "https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}",
    "7": "https://wprd01.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=7",
    "8": "https://wprd01.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=8",
    "osm": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "osm_sat": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "google_sat": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    "google_street": "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
    "google_hybrid": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    "google_terrain": "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
    "carto_dark": "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    "carto_light": "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    "esri_topo": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    "tdt_vec": "https://t0.tianditu.gov.cn/vec_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=vec&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=",
    "tdt_sat": "https://t0.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=",
    "tdt_label": "https://t0.tianditu.gov.cn/cia_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cia&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=",
}

TILE_SOURCES = {
    "amap": {
        "name": "Amap (Gaode)",
        "sat": "6",
        "vec": "7",
        "label": "8",
        "gcj02": True,
        "region": "china",
    },
    "google_sat": {
        "name": "Google Satellite",
        "sat": "google_sat",
        "vec": "google_street",
        "label": None,
        "gcj02": False,
        "region": "global",
    },
    "google_hybrid": {
        "name": "Google Hybrid",
        "sat": "google_hybrid",
        "vec": "google_street",
        "label": None,
        "gcj02": False,
        "region": "global",
    },
    "osm": {
        "name": "OpenStreetMap",
        "sat": "osm_sat",
        "vec": "osm",
        "label": None,
        "gcj02": False,
        "region": "global",
    },
    "carto_dark": {
        "name": "CartoDB Dark",
        "sat": "carto_dark",
        "vec": "carto_dark",
        "label": None,
        "gcj02": False,
        "region": "global",
    },
    "carto_light": {
        "name": "CartoDB Light",
        "sat": "carto_light",
        "vec": "carto_light",
        "label": None,
        "gcj02": False,
        "region": "global",
    },
    "esri": {
        "name": "Esri Satellite + Topo",
        "sat": "osm_sat",
        "vec": "esri_topo",
        "label": None,
        "gcj02": False,
        "region": "global",
    },
    "tianditu": {
        "name": "Tianditu",
        "sat": "tdt_sat",
        "vec": "tdt_vec",
        "label": "tdt_label",
        "gcj02": False,
        "region": "china",
    },
}


@router.get("/api/tile_sources")
async def api_tile_sources():
    return TILE_SOURCES


@router.get("/api/tile/{style}/{z}/{x}/{y}")
async def api_tile(style: str, z: int, x: int, y: int):
    if style not in TILE_URLS:
        return Response(status_code=404, content="unknown tile style")
    global _tile_count
    cache_dir = TILE_CACHE / style / str(z) / str(x)
    cache_file = cache_dir / ("%d.png" % y)
    if cache_file.exists():
        data = await aio(cache_file.read_bytes)
        return Response(content=data, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"})
    url = TILE_URLS.get(style, TILE_URLS["6"]).format(x=x, y=y, z=z)
    try:
        req = urlreq.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = await aio(lambda: urlreq.urlopen(req, timeout=cfg.TILE_DOWNLOAD_TIMEOUT).read(_TILE_MAX_BYTES + 1))
        if len(data) > _TILE_MAX_BYTES:
            return Response(status_code=502, content="Tile too large")
        if _tile_count < 0:
            _tile_count = await aio(lambda: sum(1 for _ in TILE_CACHE.rglob("*.png")) if TILE_CACHE.exists() else 0)
        if _tile_count < _TILE_MAX:
            cache_dir.mkdir(parents=True, exist_ok=True)
            await aio(cache_file.write_bytes, data)
            _tile_count += 1
        return Response(content=data, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"})
    except (OSError, urllib.error.URLError):
        return Response(status_code=404, content="tile unavailable")


@router.get("/api/tile_cache")
async def api_tile_cache():
    if not TILE_CACHE.exists():
        return {"size": 0, "count": 0}

    def _count_cache():
        total = count = 0
        for f in TILE_CACHE.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
                count += 1
        return total, count

    total, count = await aio(_count_cache)
    return {"size": total, "count": count}


@router.post("/api/tile_bulk_download", tags=["Map"])
async def api_tile_bulk_download(request: Request):
    """Download tiles for a bounding box at specified zoom levels."""
    import math

    body = await request.json()
    lat_min, lat_max = float(body.get("lat_min", 0)), float(body.get("lat_max", 0))
    lon_min, lon_max = float(body.get("lon_min", 0)), float(body.get("lon_max", 0))
    _MERC_LAT = 85.05112878
    lat_min = max(-_MERC_LAT, min(_MERC_LAT, lat_min))
    lat_max = max(-_MERC_LAT, min(_MERC_LAT, lat_max))
    z_min = max(0, min(int(body.get("z_min", 10)), 18))
    z_max = min(max(z_min, int(body.get("z_max", 16))), 18)
    style = body.get("style", "6")
    if style not in TILE_URLS:
        return {"total": 0, "downloaded": 0, "skipped": 0, "truncated": False}
    total = downloaded = skipped = 0
    for z in range(z_min, z_max + 1):
        n = 2**z
        x_min = int((lon_min + 180) / 360 * n)
        x_max = int((lon_max + 180) / 360 * n)
        y_min = int(
            (1 - math.log(math.tan(math.radians(lat_max)) + 1 / math.cos(math.radians(lat_max))) / math.pi) / 2 * n
        )
        y_max = int(
            (1 - math.log(math.tan(math.radians(lat_min)) + 1 / math.cos(math.radians(lat_min))) / math.pi) / 2 * n
        )
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                total += 1
                cache_file = TILE_CACHE / style / str(z) / str(x) / ("%d.png" % y)
                if cache_file.exists():
                    skipped += 1
                    continue
                url = TILE_URLS.get(style, TILE_URLS["6"]).format(x=x, y=y, z=z)
                try:
                    req = urlreq.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    data = await aio(
                        lambda: urlreq.urlopen(req, timeout=cfg.TILE_DOWNLOAD_TIMEOUT).read(_TILE_MAX_BYTES + 1)
                    )
                    if len(data) > _TILE_MAX_BYTES:
                        continue
                    cache_file.parent.mkdir(parents=True, exist_ok=True)
                    await aio(cache_file.write_bytes, data)
                    downloaded += 1
                except (OSError, urllib.error.URLError):
                    pass
                if total > 5000:
                    return {"total": total, "downloaded": downloaded, "skipped": skipped, "truncated": True}
    return {"total": total, "downloaded": downloaded, "skipped": skipped, "truncated": False}


@router.post("/api/tile_cache_clear")
async def api_tile_cache_clear():
    global _tile_count
    if TILE_CACHE.exists():
        await aio(shutil.rmtree, TILE_CACHE)
    _tile_count = 0
    return {"ok": True}


@router.get("/api/mbtiles/list")
async def api_mbtiles_list():
    if not MBTILES_DIR.exists():
        return {"files": []}
    return {"files": [f.name for f in sorted(MBTILES_DIR.glob("*.mbtiles"))]}


@router.get("/api/mbtiles/{name}/{z}/{x}/{y}")
async def api_mbtiles_tile(name: str, z: int, x: int, y: int):
    if Path(name).name != name or not name.endswith(".mbtiles"):
        return Response(status_code=404, content="not found")
    path = (MBTILES_DIR / name).resolve()
    try:
        path.relative_to(MBTILES_DIR.resolve())
    except ValueError:
        return Response(status_code=404, content="not found")
    if not path.exists():
        return Response(status_code=404, content="not found")
    tms_y = (1 << z) - 1 - y

    def _read_mbtile() -> bytes | None:
        conn = sqlite3.connect(str(path))
        try:
            row = conn.execute(
                "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?", (z, x, tms_y)
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    try:
        data = await aio(_read_mbtile)
        if data:
            return Response(content=data, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"})
    except (OSError, sqlite3.Error):
        pass
    return Response(status_code=404, content="tile not found")

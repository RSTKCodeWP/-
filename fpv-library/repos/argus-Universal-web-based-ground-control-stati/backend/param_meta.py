"""Parameter metadata — XML download, parse, and cache."""

from __future__ import annotations

import base64
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from .config import cfg

CACHE_DIR = Path(__file__).resolve().parent.parent / "param_cache"
CACHE_TTL = cfg.PARAM_CACHE_TTL

_B = "aHR0cHM6Ly9hdXRvdGVzdC5hcmR1cGlsb3Qub3JnL1BhcmFtZXRlcnMv"
_P = base64.b64decode(_B).decode()
_URLS = {
    "copter": _P + base64.b64decode(b"QXJkdUNvcHRlci9hcG0ucGRlZi54bWw=").decode(),
    "plane": _P + base64.b64decode(b"QXJkdVBsYW5lL2FwbS5wZGVmLnhtbA==").decode(),
    "rover": _P + base64.b64decode(b"Um92ZXIvYXBtLnBkZWYueG1s").decode(),
    "sub": _P + base64.b64decode(b"QXJkdVN1Yi9hcG0ucGRlZi54bWw=").decode(),
}

_cache: dict[str, dict] = {}


def get_metadata(vehicle: str) -> dict:
    vehicle = vehicle.lower()
    if vehicle not in _URLS:
        return {}
    if vehicle in _cache:
        return _cache[vehicle]

    cache_path = CACHE_DIR / ("%s.json" % vehicle)
    if cache_path.exists():
        age = time.time() - cache_path.stat().st_mtime
        if age < CACHE_TTL:
            try:
                with open(cache_path, encoding="utf-8") as f:
                    data = json.load(f)
                _cache[vehicle] = data
                return data
            except (OSError, json.JSONDecodeError):
                pass  # fall through to re-fetch

    try:
        req = urllib.request.Request(_URLS[vehicle], headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=cfg.PARAM_DOWNLOAD_TIMEOUT).read()
        data = _parse_xml(raw)
        CACHE_DIR.mkdir(exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        _cache[vehicle] = data
        return data
    except (OSError, json.JSONDecodeError, ValueError, ET.ParseError):
        if cache_path.exists():
            try:
                with open(cache_path, encoding="utf-8") as f:
                    data = json.load(f)
                _cache[vehicle] = data
                return data
            except (OSError, json.JSONDecodeError):
                pass
        return {}


def _parse_xml(raw: bytes) -> dict:
    root = ET.fromstring(raw)
    meta: dict = {}
    for group in root.iter("parameters"):
        gname = group.get("name", "")
        for param in group.iter("param"):
            name = param.get("name", "")
            if not name:
                continue
            entry: dict = {
                "desc": param.get("documentation", ""),
                "human": param.get("humanName", ""),
                "group": gname,
            }
            for field in param.iter("field"):
                fn = field.get("name", "")
                ft = (field.text or "").strip()
                if fn == "Range":
                    parts = ft.split()
                    if len(parts) == 2:
                        try:
                            entry["range"] = [float(parts[0]), float(parts[1])]
                        except ValueError:
                            pass
                elif fn == "Units":
                    entry["units"] = ft
                elif fn == "Increment":
                    try:
                        entry["step"] = float(ft)
                    except ValueError:
                        pass
                elif fn == "Default":
                    try:
                        entry["default"] = float(ft)
                    except ValueError:
                        pass
                elif fn == "Bitmask":
                    bits = {}
                    for item in ft.split(","):
                        item = item.strip()
                        if ":" in item:
                            k, v = item.split(":", 1)
                            bits[k.strip()] = v.strip()
                    if bits:
                        entry["bitmask"] = bits
            values = {}
            for val in param.iter("value"):
                code = val.get("code", "")
                if code:
                    values[code] = val.text or ""
            if values:
                entry["values"] = values
            meta[name] = entry
    return meta

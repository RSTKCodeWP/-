"""Contract: every `t('xxx')` call in the frontend has a matching key in the
zh.ts and en.ts locale files (the eager-loaded defaults — other locales lazy
load and fall back to zh/en if missing).

Catches:
  - typos in `t('cal.foo')` that silently render the literal key as text
  - dead keys nobody references — usually leftover from removed features
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
ZH = SRC / "lib" / "locales" / "zh.ts"
EN = SRC / "lib" / "locales" / "en.ts"

_FRONTEND_SUFFIXES = {".svelte", ".ts"}

# Keys generated dynamically at runtime — exclude from "missing" detection.
# Document each one's call site so future readers know why it's whitelisted.
DYNAMIC_KEY_PREFIXES = (
    # Toast/event messages where the variable suffix is a runtime value (mode
    # name, vehicle type, error message) — t() is called with a constructed
    # string and there's no static key to look up. These shouldn't even pass
    # the regex below if the call site uses `${...}` interpolation; included
    # here defensively in case any do.
)

# Locale keys defined in zh.ts but with NO literal reference anywhere in the
# frontend source. Almost all of these are translations for features that
# were planned or removed but the locale entries linger (no AdsbPanel
# component, no FftPanel, no rally UI calling these specific labels, ...).
# Snapshotted so that *new* orphans fail loud — cleanup of existing entries
# is welcome but not required.
KNOWN_ORPHAN_LOCALE_KEYS: set[str] = {
    "app.subtitle",
    "adsb.aircraft",
    "adsb.altitude",
    "adsb.distance",
    "adsb.noTraffic",
    "adsb.title",
    "ar.disable",
    "ar.enable",
    "compass3d.coverage",
    "confirm.armAndFly",
    "conn.noProfiles",
    "conn.reconnecting",
    "fft.amplitude",
    "fft.frequency",
    "fft.harmonics",
    "fft.notchFreq",
    "fft.notchHint",
    "fft.peak",
    "fltdb.count",
    "fltdb.delete",
    "fltdb.noData",
    "fltdb.replay",
    "fltdb.title",
    "frame.boat",
    "frame.quadplane",
    "frame.rover",
    "frame.sub",
    "inspector.expanded",
    "kml.overlay",
    "logview.timeline",
    "multi.observer",
    "pid.reset",
    "plugin.load",
    "plugin.noPlugins",
    "plugin.title",
    "posSource.bad",
    "posSource.good",
    "posSource.optFlow.bad",
    "posSource.optFlow.good",
    "posSource.optFlow.warn",
    "posSource.warn",
    "prearm.fail",
    "prearm.pass",
    "prearm.unknown",
    "preflight.save",
    "rally.add",
    "rally.clear",
    "rally.hint",
    "rally.title",
    "rally.upload",
    "rally.uploaded",
    "rccal.mapping",
    "rccal.step1",
    "rccal.step2",
    "rccal.step3",
    "safety.parachute",
    "safety.parachuteConfirm",
    "safety.terminate",
    "safety.terminateConfirm",
    "sched.status.completed",
    "sched.status.pending",
    "settings.flightParams",
    "settings.mapRegion",
    "settings.safety",
    "settings.ui",
    "settings.zhLabel",
    "toast.armFail",
    "toast.arming",
    "toast.invalidValue",
    "toast.missionStart",
    "toast.outOfRange",
    "toast.takeoffFail",
    "units.fpm",
    "units.ft",
    "units.imperial",
    "units.kts",
    "units.metric",
    "units.mi",
    "units.mph",
    "video.screenshot",
}


def _iter_frontend_sources() -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for path in SRC.rglob("*"):
        if path.suffix not in _FRONTEND_SUFFIXES:
            continue
        if "locales" in path.parts or "node_modules" in path.parts:
            continue
        if path.name.endswith(".test.ts"):
            continue
        files.append((path, path.read_text(encoding="utf-8", errors="ignore")))
    return files


def _t_call_keys() -> set[str]:
    """Extract every literal-string key passed to t(...)."""
    out: set[str] = set()
    # Match t('key') or t("key") — only literal strings, no template literals
    pattern = re.compile(r"""\bt\(\s*['"]([a-zA-Z][a-zA-Z0-9._]*)['"]\s*[,)]""")
    for _, src in _iter_frontend_sources():
        out.update(pattern.findall(src))
    return out


def _locale_keys(locale_path: Path) -> set[str]:
    """Extract keys defined in a locales/*.ts file. Format is:
    export default { 'key.name': 'value', ... } or `export const X = { ... }`.
    """
    src = locale_path.read_text(encoding="utf-8")
    return set(re.findall(r"""['"]([a-zA-Z][a-zA-Z0-9._]*)['"]\s*:""", src))


class TestLocaleContract:
    def test_every_t_call_resolves_in_zh(self):
        used = _t_call_keys()
        zh = _locale_keys(ZH)
        missing = used - zh
        # Any whitelisted dynamic prefixes are removed before asserting
        missing = {k for k in missing if not any(k.startswith(p) for p in DYNAMIC_KEY_PREFIXES)}
        assert not missing, (
            f"\n{len(missing)} t() keys missing from zh.ts (will render as literal text):\n"
            + "\n".join(f"  {k}" for k in sorted(missing))
        )

    def test_every_t_call_resolves_in_en(self):
        used = _t_call_keys()
        en = _locale_keys(EN)
        missing = used - en
        missing = {k for k in missing if not any(k.startswith(p) for p in DYNAMIC_KEY_PREFIXES)}
        assert not missing, f"\n{len(missing)} t() keys missing from en.ts:\n" + "\n".join(
            f"  {k}" for k in sorted(missing)
        )

    def test_zh_and_en_define_the_same_keys(self):
        zh = _locale_keys(ZH)
        en = _locale_keys(EN)
        only_zh = zh - en
        only_en = en - zh
        assert not only_zh and not only_en, (
            f"\nzh.ts and en.ts have diverged:\n  Only in zh: {sorted(only_zh)}\n  Only in en: {sorted(only_en)}\n"
        )

    def test_no_new_orphan_locale_keys(self):
        """Every key in zh.ts should be referenced from some component, either
        directly via `t('key')` or indirectly via a string literal that
        eventually flows into a t() call (e.g. titleKey: 'cal.gyroTitle').

        Snapshots the currently-orphan set; any deviation fails. Adding a new
        unused key fails immediately (typically a typo or a leftover from a
        removed feature). Cleaning up a known-orphan also fails — that forces
        us to delete the allowlist entry rather than letting it drift."""
        zh = _locale_keys(ZH)
        all_src = "\n".join(src for _, src in _iter_frontend_sources())
        orphans = {k for k in zh if f"'{k}'" not in all_src and f'"{k}"' not in all_src}
        new = orphans - KNOWN_ORPHAN_LOCALE_KEYS
        fixed = KNOWN_ORPHAN_LOCALE_KEYS - orphans
        assert not new and not fixed, (
            f"\nLocale orphan set drifted from snapshot:\n"
            f"  New orphan keys (typo or removed feature?): {sorted(new)}\n"
            f"  Now-used keys (remove from KNOWN_ORPHAN_LOCALE_KEYS): {sorted(fixed)}\n"
        )

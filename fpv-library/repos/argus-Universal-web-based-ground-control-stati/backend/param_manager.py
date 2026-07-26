"""Parameter management — MAVLink PARAM protocol."""

from __future__ import annotations

import json
import math
import struct
import time
from pathlib import Path
from typing import TYPE_CHECKING

from .config import cfg
from .locale_text import lt

if TYPE_CHECKING:
    from .drone_link import DroneLink


def _pad(p: bytes, n: int) -> bytes:
    return p if len(p) >= n else p + b"\x00" * (n - len(p))


class ParamManager:
    def __init__(self, link: DroneLink):
        self._link = link
        self.params: dict[str, dict] = {}
        self.total_count = -1
        self.received_count = 0
        self.fetching = False
        self._fetch_start = 0.0
        self._complete_emitted = False
        # Indices we've seen. After the initial PARAM_REQUEST_LIST burst
        # completes (no new params for `PARAM_GAP_FILL_DELAY`), we scan for
        # gaps and re-request the missing ones individually via msg 20
        # (PARAM_REQUEST_READ).
        self._received_indices: set[int] = set()
        self._last_value_time = 0.0
        self._gap_fill_attempts: dict[int, int] = {}  # index -> retry count
        self._list_attempts = 0  # PARAM_REQUEST_LIST re-sends (dropped-request recovery)
        self._messages: list[dict] = []  # kept for backward compat with ws_manager cursor
        # Bumped every request_all() (which clears _messages). ws_manager uses
        # this to reset its length-based cursor: without it, a fresh fetch that
        # refills to the SAME length as the prior one within a single push
        # cycle collides on the strict-`>` reset guard and delivers 0 params
        # (empty param panel). Same failure the event cursor solved with seq.
        self._fetch_gen = 0

    def request_all(self) -> None:
        self.params.clear()
        self.total_count = -1
        self.received_count = 0
        self.fetching = True
        self._complete_emitted = False
        self._fetch_gen += 1
        self._fetch_start = time.time()
        self._last_value_time = self._fetch_start
        self._received_indices.clear()
        self._gap_fill_attempts.clear()
        self._list_attempts = 0
        # Drop stale messages so the next ws_manager cursor doesn't replay
        # values from a previous (now invalidated) fetch.
        self._messages.clear()
        self._link.add_event(lt("param_reading", self._link.locale), "param_reading")
        self._request_list()

    def _request_list(self) -> None:
        # MAV PARAM_REQUEST_LIST msg id 21: target_system u8 @0, target_component
        # u8 @1. The FC replies with a PARAM_VALUE stream carrying param_count.
        from .crc_extras import CRC_EXTRA
        from .pllink_proto import bm

        self._list_attempts += 1
        payload = struct.pack("<BB", self._link.vehicle.sysid, 1)
        self._link.send(bm(21, payload, self._link.sq, CRC_EXTRA[21]))

    def _request_one(self, index: int) -> None:
        # MAV PARAM_REQUEST_READ msg id 20, CRC extra 214.
        # Wire layout (sorted by size):
        #   0..1   param_index (int16)
        #   2      target_system (u8)
        #   3      target_component (u8)
        #   4..19  param_id (char[16]) — empty when looking up by index
        from .crc_extras import CRC_EXTRA
        from .pllink_proto import bm

        payload = struct.pack("<hBB", index, self._link.vehicle.sysid, 1) + b"\x00" * 16
        self._link.send(bm(20, payload, self._link.sq, CRC_EXTRA[20]))

    def handle_param_value(self, p: bytes, pl: int) -> None:
        if pl < 1:
            return
        p = _pad(p, 25)
        value = struct.unpack_from("<f", p, 0)[0]
        count = struct.unpack_from("<H", p, 4)[0]
        index = struct.unpack_from("<H", p, 6)[0]
        name = bytes(p[8:24]).split(b"\x00")[0].decode("ascii", "replace")
        ptype = p[24]
        # An empty name means the frame is garbage / all-zero — refuse to
        # poison the params dict with a {"": ...} entry that would show up
        # as a blank row in the UI.
        if not name:
            return

        self._last_value_time = time.time()
        if self.total_count < 0:
            self.total_count = count
        # Index 0xFFFF is what AP sends for replies to PARAM_REQUEST_READ
        # (since the user looked up by name). Don't add it to received_indices,
        # but still count the param.
        if index != 0xFFFF:
            self._received_indices.add(index)

        if name not in self.params:
            self.received_count += 1

        self.params[name] = {
            "name": name,
            "value": value,
            "type": ptype,
            "index": index,
        }

        self._messages.append(
            {
                "type": "param_value",
                "name": name,
                "value": value,
                "ptype": ptype,
                "index": index,
                "total": self.total_count,
                "received": self.received_count,
            }
        )
        # Cap message buffer on every append (not just on completion) so a
        # stuck/incomplete fetch can't grow unbounded.
        if len(self._messages) > 2000:
            self._messages = self._messages[-1000:]

        if self.received_count >= self.total_count > 0 and not self._complete_emitted:
            self._complete_emitted = True
            self.fetching = False
            elapsed = time.time() - self._fetch_start
            self._link.add_event(lt("param_done", self._link.locale) % (self.received_count, elapsed), "param_done")
            self._messages.append(
                {
                    "type": "params_complete",
                    "count": self.received_count,
                }
            )

    def set_param(self, name: str, value: float) -> None:
        # AP silently rejects NaN/Inf and we'd have no way to retry. Validate
        # caller side so the UI sees an immediate error rather than the
        # parameter "appearing to set" then unchanged on the next read.
        if math.isnan(value) or math.isinf(value):
            self._link.add_event(lt("param_nan", self._link.locale) % name, "param_set_fail")
            return
        param = self.params.get(name)
        ptype = param["type"] if param else 9
        from .crc_extras import CRC_EXTRA
        from .pllink_proto import bm

        name_bytes = name.encode("ascii")[:16].ljust(16, b"\x00")
        payload = (
            struct.pack("<f", value)
            + struct.pack("<BB", self._link.vehicle.sysid, 1)
            + name_bytes
            + struct.pack("<B", ptype)
        )
        self._link.send(bm(23, payload, self._link.sq, CRC_EXTRA[23]))
        self._link.add_event(lt("param_set", self._link.locale) % (name, value), "param_set")

    def save_to_file(self, path: str | None = None) -> str:
        if not path:
            save_dir = Path(__file__).resolve().parent.parent / "params"
            save_dir.mkdir(exist_ok=True)
            path = str(save_dir / ("params_%s.json" % time.strftime("%Y%m%d_%H%M%S")))
            self._prune_backups(save_dir)
        data = {name: p["value"] for name, p in sorted(self.params.items())}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self._link.add_event(lt("param_saved", self._link.locale) % (len(data), Path(path).name), "param_saved")
        return path

    @staticmethod
    def _prune_backups(save_dir: Path, keep: int = 20) -> None:
        files = sorted(save_dir.glob("params_*.json"), key=lambda f: f.stat().st_mtime)
        for old in files[:-keep] if len(files) > keep else []:
            old.unlink(missing_ok=True)

    def load_from_file(self, path: str) -> list[str]:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self._link.add_event(lt("param_load_err", self._link.locale) % e, "param_load_err")
            return []
        if not isinstance(data, dict):
            self._link.add_event(lt("param_load_err", self._link.locale) % "not a JSON object", "param_load_err")
            return []
        changed = []
        for name, value in data.items():
            # bool is a subclass of int — exclude it so JSON `true`/`false` don't become 1.0/0.0 on the wire.
            # Also exclude non-finite floats (Inf/-Inf): set_param rejects them, but without this guard
            # `changed.append` + `time.sleep` still run, inflating param_loaded count and load time.
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                continue
            current = self.params.get(name)
            if current and abs(current["value"] - value) > 1e-7:
                self.set_param(name, value)
                changed.append(name)
                time.sleep(cfg.PARAM_LOAD_SPACING)
        self._link.add_event(lt("param_loaded", self._link.locale) % (len(data), len(changed)), "param_loaded")
        return changed

    def check_timeout(self) -> None:
        if not self.fetching:
            return
        now = time.time()
        # If we've been waiting `PARAM_GAP_FILL_DELAY` seconds since the last
        # PARAM_VALUE but still don't have everything, the FC either finished
        # streaming with packet loss OR has stopped responding entirely.
        # Fill known gaps with PARAM_REQUEST_READ (msg 20). Each missing
        # index gets up to 3 retries.
        gap_delay = getattr(cfg, "PARAM_GAP_FILL_DELAY", 2.0)
        max_retries = 3
        # Dropped initial request: if not a single PARAM_VALUE has come back,
        # total_count is still unknown and the gap-fill below (which needs it)
        # can never engage — the whole fetch would silently time out. Re-send
        # PARAM_REQUEST_LIST a few times before giving up. This is the common
        # failure on a lossy/ churny link: one dropped msg 21 stalls everything.
        if self.total_count <= 0 and now - self._last_value_time > gap_delay:
            if self._list_attempts <= max_retries:
                self._request_list()
                self._last_value_time = now  # back off until next tick
        if self.total_count > 0 and now - self._last_value_time > gap_delay:
            missing = [i for i in range(self.total_count) if i not in self._received_indices]
            # Throttle: only send up to 10 per cycle so we don't flood the FC.
            for i in missing[:10]:
                attempts = self._gap_fill_attempts.get(i, 0)
                if attempts >= max_retries:
                    continue
                self._gap_fill_attempts[i] = attempts + 1
                self._request_one(i)
            self._last_value_time = now  # back off until next tick

        if now - self._fetch_start > cfg.PARAM_FETCH_TIMEOUT:
            self.fetching = False
            n_missing = max(0, (self.total_count or 0) - len(self._received_indices))
            self._link.add_event(lt("param_timeout", self._link.locale), "param_timeout")
            self._messages.append({"type": "param_timeout", "missing": n_missing})

    def get_status(self) -> dict:
        return {
            "param_count": self.received_count,
            "param_total": self.total_count,
            "param_fetching": self.fetching,
        }

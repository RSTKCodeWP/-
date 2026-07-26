from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from . import commands
from .config import cfg
from .drone_link import DroneLink
from .locale_text import lt

logger = logging.getLogger(__name__)

_VALID_LOCALES = frozenset(("zh", "en", "ja", "ko", "de", "fr", "es", "pt", "ru", "ar"))


def validate_port(port) -> bool:
    return isinstance(port, str) and len(port) <= 200 and "\x00" not in port


def sanitize_baud(baud) -> int:
    try:
        baud = int(baud)
    except (TypeError, ValueError):
        return cfg.SERIAL_BAUD
    return baud if baud in cfg.VALID_BAUD_RATES else cfg.SERIAL_BAUD


def sanitize_protocol(protocol) -> str:
    return protocol if protocol in cfg.VALID_PROTOCOLS else "auto"


class WSManager:
    def __init__(self, link: DroneLink):
        self.link = link
        self._clients: set[WebSocket] = set()
        # Connection order (earliest first). `set` gives no ordering, so we
        # track it separately to identify the session operator — the
        # earliest-connected client — for the implicit-pilot rule below.
        self._order: list[WebSocket] = []
        self._pilot_ws: WebSocket | None = None
        self._roles: dict[int, str] = {}

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def broadcast(self, msg: dict) -> None:
        text = json.dumps(msg)
        for ws in list(self._clients):
            try:
                await ws.send_text(text)
            except Exception:
                # WebSocketDisconnect inherits from Exception, not from any
                # of the legacy stdlib network errors — catching it specifically
                # would require importing the WS-impl class. A bare Exception
                # here is correct because broadcast() failures should never
                # take down the receive_loop of another (still-healthy) client.
                self._clients.discard(ws)

    async def handle_client(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)
        self._order.append(ws)
        try:
            recv_task = asyncio.create_task(self._receive_loop(ws))
            push_task = asyncio.create_task(self._push_loop(ws))
            done, pending = await asyncio.wait(
                [recv_task, push_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
            for t in done:
                if t.exception() is not None:
                    pass
        except (ConnectionError, RuntimeError):
            pass
        finally:
            self._clients.discard(ws)
            self._order = [c for c in self._order if c is not ws]
            # Clear this client's role + pilot reference so the next observer
            # to call request_handoff doesn't auto-promote because the dead
            # ws is no longer `in self._clients` (auditor finding).
            self._roles.pop(id(ws), None)
            if self._pilot_ws is ws:
                self._pilot_ws = None

    async def _receive_loop(self, ws: WebSocket) -> None:
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                msg_type = msg.get("type", "")
                if msg_type == "connect":
                    port = msg.get("port", "tcp:localhost:5770")
                    baud = msg.get("baud", cfg.SERIAL_BAUD)
                    protocol = msg.get("protocol", "auto")
                    if not validate_port(port):
                        await ws.send_text(
                            json.dumps(
                                {
                                    "type": "connect_result",
                                    "ok": False,
                                    "error": lt("err_connect", self.link.locale),
                                }
                            )
                        )
                        continue
                    baud = sanitize_baud(baud)
                    protocol = sanitize_protocol(protocol)
                    ok = await asyncio.to_thread(self.link.connect, port, baud, protocol=protocol)
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "connect_result",
                                "ok": ok,
                                "error": "" if ok else lt("err_connect", self.link.locale),
                            }
                        )
                    )
                elif msg_type == "disconnect":
                    await asyncio.to_thread(self.link.disconnect)
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "connect_result",
                                "ok": True,
                                "error": "",
                            }
                        )
                    )
                elif msg_type == "set_locale":
                    locale = msg.get("locale", "zh")
                    if locale in _VALID_LOCALES:
                        self.link.locale = locale
                elif msg_type == "set_role":
                    role = msg.get("role", "observer")
                    self._roles[id(ws)] = role
                    if role == "pilot":
                        self._pilot_ws = ws
                    await self.broadcast(
                        {
                            "type": "role_update",
                            "clients": self.client_count,
                            "pilot_connected": self._pilot_ws in self._clients,
                        }
                    )
                elif msg_type == "request_handoff":
                    if self._pilot_ws and self._pilot_ws != ws and self._pilot_ws in self._clients:
                        await self._pilot_ws.send_text(json.dumps({"type": "handoff_request", "from": id(ws)}))
                    else:
                        self._pilot_ws = ws
                        self._roles[id(ws)] = "pilot"
                        await ws.send_text(json.dumps({"type": "handoff_granted"}))
                elif msg_type == "handoff_accept":
                    target_id = msg.get("target")
                    for client in self._clients:
                        if id(client) == target_id:
                            self._pilot_ws = client
                            self._roles[id(client)] = "pilot"
                            self._roles[id(ws)] = "observer"
                            await client.send_text(json.dumps({"type": "handoff_granted"}))
                            await ws.send_text(json.dumps({"type": "handoff_released"}))
                            break
                elif msg_type == "command":
                    # Observer clients must not be able to control the
                    # vehicle. Auditor finding: previously every connected
                    # client could call commands.execute() — meaning a
                    # passive viewer could arm/takeoff. Reject unless this ws
                    # holds the pilot role (the implicit-pilot fallback
                    # below covers the single-client case where no role has
                    # been set yet).
                    role = self._roles.get(id(ws))
                    # With no explicit pilot assigned, command authority belongs
                    # to the earliest-connected client (the session operator);
                    # later joiners observe. The previous `client_count == 1`
                    # gate stripped the operator's authority the instant ANY
                    # second client connected — an observer opening the page
                    # silently disabled the operator's commands, with no way to
                    # reclaim them (nothing in the frontend sends set_role /
                    # request_handoff). Earliest-connected preserves the GCS
                    # "one operator, rest observe" default with zero UI wiring.
                    # Fallback (operator is None): tests populate _clients
                    # directly, bypassing _order — a lone client still commands.
                    operator = next((c for c in self._order if c in self._clients), None)
                    if operator is None:
                        operator = ws if self.client_count == 1 else None
                    is_implicit_pilot = self._pilot_ws is None and role is None and operator is ws
                    if role != "pilot" and not is_implicit_pilot:
                        await ws.send_text(
                            json.dumps(
                                {
                                    "type": "cmd_result",
                                    "ok": False,
                                    "error": lt("err_observer_no_cmd", self.link.locale),
                                }
                            )
                        )
                        continue
                    cmd = msg.get("cmd", "")
                    param = msg.get("param")
                    result = commands.execute(cmd, param, self.link, data=msg)
                    if result:
                        await ws.send_text(json.dumps({"type": "cmd_result", **result}))
        except WebSocketDisconnect:
            pass
        except (ConnectionError, RuntimeError):
            logger.warning("receive_loop error", exc_info=True)

    async def _push_loop(self, ws: WebSocket) -> None:
        # Use the monotonic emitted-count as our cursor for events. The array
        # itself is trimmed (100 → 50) periodically, so an index-based cursor
        # ended up replaying or dropping events depending on the cursor's
        # position at trim time (auditor drone_link C5).
        event_seq_cursor = self.link._events_emitted_total
        param_cursor = len(self.link.param_mgr._messages)
        param_gen = self.link.param_mgr._fetch_gen
        dl_cursor = len(self.link.mission._dl_messages)
        log_cursor = len(self.link.log_dl._log_messages)
        last_sent: dict = {}
        push_count = 0
        try:
            while True:
                state = self.link.get_state()
                push_count += 1
                if push_count % 10 == 1:
                    delta = state
                else:
                    delta = {k: v for k, v in state.items() if last_sent.get(k) != v}
                    delta["type"] = "state"
                    delta["connected"] = state["connected"]
                if delta:
                    await ws.send_text(json.dumps(delta))
                    last_sent.update(state)
                with self.link._state_lock:
                    events = list(self.link.events)
                    events_total = self.link._events_emitted_total
                    dlmsg = list(self.link.mission._dl_messages)
                    logmsg = list(self.link.log_dl._log_messages)
                    pmsg = list(self.link.param_mgr._messages)
                    param_gen_now = self.link.param_mgr._fetch_gen
                # Send any events with seq > our last-sent seq. The array may
                # have trimmed older entries; if cursor < oldest-available
                # seq, we accept the loss (the trimmed events are gone).
                if events_total > event_seq_cursor:
                    for ev in events:
                        if ev.get("seq", 0) > event_seq_cursor:
                            await ws.send_text(
                                json.dumps(
                                    {
                                        "type": "event",
                                        "time": ev["time"],
                                        "text": ev["text"],
                                        "event_type": ev.get("event_type", ""),
                                    }
                                )
                            )
                    event_seq_cursor = events_total
                if dl_cursor > len(dlmsg):
                    dl_cursor = 0
                if len(dlmsg) > dl_cursor:
                    for msg in dlmsg[dl_cursor:]:
                        await ws.send_text(json.dumps(msg))
                    dl_cursor = len(dlmsg)
                if log_cursor > len(logmsg):
                    log_cursor = 0
                if len(logmsg) > log_cursor:
                    for msg in logmsg[log_cursor:]:
                        await ws.send_text(json.dumps(msg))
                    log_cursor = len(logmsg)
                # A new request_all() clears _messages and refills it. Reset the
                # cursor on the generation change, not just on an observed length
                # drop: if the clear+refill lands within one push cycle and the
                # new length equals the old cursor, the length guard never fires
                # and 0 params are delivered (empty panel — the CI params flake).
                if param_gen_now != param_gen:
                    param_cursor = 0
                    param_gen = param_gen_now
                if param_cursor > len(pmsg):
                    param_cursor = 0
                if len(pmsg) > param_cursor:
                    batch = pmsg[param_cursor:]
                    pvals = [m for m in batch if m["type"] == "param_value"]
                    others = [m for m in batch if m["type"] != "param_value"]
                    if pvals:
                        await ws.send_text(
                            json.dumps(
                                {
                                    "type": "param_batch",
                                    "params": pvals,
                                }
                            )
                        )
                    for msg in others:
                        await ws.send_text(json.dumps(msg))
                    param_cursor = len(pmsg)
                if self.link.inspector_enabled:
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "inspector",
                                "messages": self.link.get_inspector_data(),
                            }
                        )
                    )
                with self.link._state_lock:
                    if self.link._console_buf:
                        text = "".join(self.link._console_buf)
                        self.link._console_buf.clear()
                    else:
                        text = ""
                if text:
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "console_output",
                                "text": text,
                            }
                        )
                    )
                interval = cfg.WS_PUSH_INTERVAL_CONNECTED if self.link.connected else cfg.WS_PUSH_INTERVAL_IDLE
                await asyncio.sleep(interval)
        except WebSocketDisconnect:
            pass
        except (ConnectionError, RuntimeError):
            logger.warning("push_loop error", exc_info=True)

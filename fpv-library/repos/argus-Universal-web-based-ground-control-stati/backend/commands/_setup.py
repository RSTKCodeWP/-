from __future__ import annotations

import struct
import time
from typing import TYPE_CHECKING

from ..crc_extras import CRC_EXTRA
from ..locale_text import lt
from ..pllink_proto import bm
from ._helpers import send_cmd

if TYPE_CHECKING:
    from ..drone_link import DroneLink


# --- Calibration ---


def cmd_cal_compass(link: DroneLink, param, data: dict):
    link.add_event(lt("cal_compass", link.locale), "cal_compass")
    link._mag_cal_pct = -1
    link._mag_cal_done = False
    send_cmd(link, 42424, p1=0, p2=0, p3=0, p4=0)


def cmd_cal_compass_accept(link: DroneLink, param, data: dict):
    send_cmd(link, 42425, p1=0)


def cmd_cal_accel(link: DroneLink, param, data: dict):
    link.add_event(lt("cal_accel", link.locale), "cal_accel")
    send_cmd(link, 241, p5=1)


def cmd_cal_gyro(link: DroneLink, param, data: dict):
    link.add_event(lt("cal_gyro", link.locale), "cal_gyro")
    send_cmd(link, 241, p1=1)


def cmd_cal_level(link: DroneLink, param, data: dict):
    link.add_event(lt("cal_level", link.locale), "cal_level")
    send_cmd(link, 241, p5=4)


def cmd_cal_baro(link: DroneLink, param, data: dict):
    link.add_event(lt("cal_baro", link.locale), "cal_baro")
    send_cmd(link, 241, p3=1)


def cmd_cal_accel_next(link: DroneLink, param, data: dict):
    # ArduPilot's AP_AccelCal::handle_command_ack (libraries/AP_AccelCal/AP_AccelCal.cpp)
    # has surprising semantics — the ACK fields are NOT a normal command/result
    # acknowledgement:
    #   if (packet.command > 6)                              return;  // not MAV_CMD code!
    #   if (packet.result != MAV_RESULT_TEMPORARILY_REJECTED) return;  // result MUST be 1
    #   if (_sysid != src_sysid || _compid != src_compid)    return;  // sender match
    # QGC sends command=0, result=1. MAVProxy sends command=1..6 (current pose),
    # result=1. We mirror QGC. sysid/compid match what cmd_cal_accel used to
    # start the cal (bm() defaults: sysid=255, compid=1).
    payload = struct.pack("<HB", 0, 1)
    link.send(bm(77, payload, link.sq, CRC_EXTRA[77]))


def cmd_cal_cancel(link: DroneLink, param, data: dict):
    # MAV_CMD_DO_CANCEL_MAG_CAL (42426) only cancels an in-progress compass
    # cal. ArduPilot has no MAVLink command to abort an accel calibration —
    # the FC stays in WAITING_FOR_ORIENTATION until either the next ACK
    # arrives or the FC reboots (AP_AccelCal::cancel() is internal-only). For
    # gyro/level/baro the cmd 241 calibration completes within ~1 sec so
    # cancellation isn't really meaningful. The frontend still resets its UI
    # state on cancel, which is what the user sees and expects.
    link.add_event(lt("cal_cancel", link.locale), "cal_cancel")
    send_cmd(link, 42426, p1=0)


# --- Parameters ---


def cmd_param_request_all(link: DroneLink, param, data: dict):
    link.param_mgr.request_all()


def cmd_param_set(link: DroneLink, param, data: dict):
    name = data.get("name", "")
    value = float(data.get("value", 0))
    if name:
        link.param_mgr.set_param(name, value)


def cmd_param_save(link: DroneLink, param, data: dict):
    # Writes a JSON backup to the GCS host filesystem (different from `param_save_to_flash`).
    path = link.param_mgr.save_to_file()
    return {"ok": True, "path": path}


def cmd_param_save_to_flash(link: DroneLink, param, data: dict):
    # MAV_CMD_PREFLIGHT_STORAGE (245), p1=1: write running params to FC non-volatile storage.
    # AP source: GCS_MAVLINK::handle_command_preflight_storage in libraries/GCS_MAVLink/GCS_Common.cpp.
    # AP typically auto-persists params on PARAM_SET, so this is a defensive write — useful when
    # users want explicit "save to flash" semantics independent of the JSON backup written by cmd_param_save.
    send_cmd(link, 245, p1=1)
    link.add_event(lt("param_saved_to_flash", link.locale), "param_saved_to_flash")


def cmd_param_load(link: DroneLink, param, data: dict):
    path = data.get("path", "")
    if not path:
        return None
    from pathlib import Path

    p = Path(path).resolve()
    params_dir = Path(__file__).resolve().parent.parent.parent / "params"
    # Use is_relative_to instead of string-prefix: the prefix check is bypassed
    # by sibling dirs that happen to share a prefix (e.g. /argus/params_evil/...)
    try:
        p.relative_to(params_dir)
    except ValueError:
        return {"ok": False, "error": "Path must be within params directory"}  # i18n-exempt
    if p.suffix != ".json":
        return {"ok": False, "error": "Only .json parameter files allowed"}  # i18n-exempt
    # load_from_file iterates with `time.sleep(PARAM_LOAD_SPACING)` between
    # sends to avoid overrunning the FC's param queue. For a 1000-param file
    # that's ~20s of blocking — and commands.execute() is called from inside
    # the async websocket receive loop, so a sync sleep would freeze the
    # event loop for that whole window. Spawn a daemon thread; progress
    # surfaces via the param_set events streamed back over the same ws.
    import threading

    threading.Thread(target=link.param_mgr.load_from_file, args=(str(p),), daemon=True).start()
    return {"ok": True, "started": True}


# --- Logs ---


def cmd_log_list(link: DroneLink, param, data: dict):
    # ArduPilot's AP_Logger rejects LOG_REQUEST_LIST when armed
    # (AP_Logger_MAVLinkLogTransfer.cpp:40). Surface that to the UI as a
    # typed error instead of the user seeing only a generic statustext.
    if link.vehicle.armed:
        return {"ok": False, "error": lt("err_no_log_armed", link.locale)}
    if link.log_dl._log_download_id != -1:
        return {"ok": False, "error": lt("err_log_busy", link.locale)}
    link.log_dl._log_list = []
    link.send(bm(117, struct.pack("<HHBB", 0, 0xFFFF, link.vehicle.sysid, 1), link.sq, CRC_EXTRA[117]))
    link.add_event(lt("log_list_req", link.locale), "log_list_req")


def cmd_log_download(link: DroneLink, param, data: dict):
    if link.vehicle.armed:
        return {"ok": False, "error": lt("err_no_log_armed", link.locale)}
    log_id = int(data.get("id", 0))
    lg = link.log_dl
    # A second download while one is in flight would silently corrupt both:
    # AP_Logger rejects the new request and we'd overwrite the in-progress
    # buffer (auditor finding C3). Refuse explicitly.
    if lg._log_download_id != -1:
        return {"ok": False, "error": lt("err_log_busy", link.locale)}
    log_entry = next((l for l in lg._log_list if l["id"] == log_id), None)
    if not log_entry:
        return {"ok": False, "error": lt("err_log_not_found", link.locale)}
    lg._log_download_id = log_id
    lg._log_download_size = log_entry["size"]
    lg._log_download_data = bytearray(log_entry["size"])
    lg._log_download_ofs = 0
    lg._log_recv_intervals = []
    lg._log_stall_retries = 0
    lg._log_last_progress_time = 0.0
    # Drop the previous download's payload messages (kept until now because
    # the cursor-based ws drain has no ack — see _finalize_log_download).
    # log_list survives: observers that joined late still need it.
    lg._log_messages = [m for m in lg._log_messages if m["type"] == "log_list"]
    # Arm the stall watchdog now so even a lost FIRST window gets retried
    # (check_log_dl_stall gates on last_data_time > 0).
    lg._log_last_data_time = time.time()
    link.add_event(lt("log_dl", link.locale) % (log_id, log_entry["size"] // 1024), "log_dl")
    # Request the WHOLE log in one LOG_REQUEST_DATA — the MAVProxy pattern
    # ArduPilot explicitly tolerates (AP_Logger_MAVLinkLogTransfer.cpp:112-113
    # names it) and caps in-spec (:144-152: transfer anchored to our ofs,
    # count capped to the remaining size). Windowed 4500 B requests paid one
    # ~20 ms round trip per window — an RTT-bound ~225 KB/s ceiling on a
    # ~700 KB/s USB link. Lost frames are re-requested from the coverage
    # intervals once the stream ends (handle_log_data gap-fill).
    lg._log_window_end = log_entry["size"]
    link.send(bm(119, struct.pack("<IIHBB", 0, log_entry["size"], log_id, link.vehicle.sysid, 1), link.sq, CRC_EXTRA[119]))


def cmd_log_cancel(link: DroneLink, param, data: dict):
    link.send(bm(122, struct.pack("<BB", link.vehicle.sysid, 1), link.sq, CRC_EXTRA[122]))
    lg = link.log_dl
    lg._log_download_id = -1
    # Free the buffer (auditor finding C6) — could be ~100MB after a partial
    # download of a large dataflash log.
    lg._log_download_data = bytearray()
    lg._log_download_size = 0
    lg._log_download_ofs = 0
    lg._log_window_end = 0
    # A stale emit offset would make the NEXT download silently skip emitting
    # its first _log_emit_ofs bytes (finalize base64s only from that mark) —
    # only _finalize_log_download resets it, and cancel skips finalize.
    lg._log_emit_ofs = 0
    lg._log_recv_intervals = []
    lg._log_stall_retries = 0
    lg._log_last_data_time = 0.0
    lg._log_last_progress_time = 0.0
    lg._log_messages = [m for m in lg._log_messages if m["type"] == "log_list"]
    link.add_event(lt("log_dl_cancel", link.locale), "log_dl_cancel")

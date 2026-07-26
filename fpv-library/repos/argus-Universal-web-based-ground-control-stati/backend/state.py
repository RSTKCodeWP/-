from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AttitudeState:
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    lat: float = 0.0
    lon: float = 0.0
    alt_rel: float = 0.0
    alt_msl: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0
    gs: float = 0.0
    airspeed: float = 0.0
    throttle: int = 0
    climb: float = 0.0
    hdg: float = 0.0
    home_lat: float = 0.0
    home_lon: float = 0.0
    # True once home has been set from FC (either inferred from first position
    # fix or received via HOME_POSITION msg 242). Using a flag rather than
    # checking home_lat != 0 ensures equator-based homes (lat == 0 within
    # ~111 m) are not treated as "unset".
    _home_set: bool = False
    dist_home: float = 0.0
    _prev_pos: tuple | None = None


@dataclass
class BatteryState:
    voltage: float = 0.0
    current: float = 0.0
    remaining: int = -1
    _bat_history: list[tuple[float, int]] = field(default_factory=list)
    bat_time_remaining: int = -1
    _bat_start_pct: int = -1
    battery_cells: list[float] = field(default_factory=list)


@dataclass
class GpsState:
    gps_fix: int = 0
    gps_sats: int = 0


@dataclass
class VehicleState:
    mode: int = 0
    armed: bool = False
    armed_time: float = 0.0
    vtype_raw: int = 0
    # HEARTBEAT.autopilot byte (MAV_AUTOPILOT enum). 0 = MAV_AUTOPILOT_GENERIC
    # (uninitialized — we use 0 as "not yet seen"), 3 = MAV_AUTOPILOT_ARDUPILOTMEGA,
    # 12 = MAV_AUTOPILOT_PX4. Anything else gets treated as ArduPilot for now —
    # the FC adapter system in src/lib/fc/ has PX4 mode tables but the rest of
    # the codebase (calibration handshakes, MAV_CMD enums, parameter semantics)
    # assumes ArduPilot. See CLAUDE.md ## PX4 Status.
    autopilot: int = 0
    force_plane: bool | None = None
    sysid: int = 1
    fw_version: str = ""
    fw_git: str = ""
    board_id: int = 0
    flight_summary: dict | None = None
    max_alt: float = 0.0
    max_speed: float = 0.0
    total_dist: float = 0.0


@dataclass
class MissionState:
    wp_seq: int = 0
    _mission_items: list[dict] = field(default_factory=list)
    _mission_pending: bool = False
    _seq_to_wp: dict[int, int] = field(default_factory=dict)
    _fence_items: list[dict] = field(default_factory=list)
    _fence_pending: bool = False
    _rally_items: list[dict] = field(default_factory=list)
    _rally_pending: bool = False
    # Upload-side watchdogs (one per pending kind). If the FC never requests
    # an item we re-queued, the pending flag would zombie forever — drone_link
    # main loop calls check_*_upload_timeout to clear them.
    _mission_ul_start_time: float = 0.0
    _fence_ul_start_time: float = 0.0
    _rally_ul_start_time: float = 0.0
    _dl_pending: bool = False
    _dl_total: int = 0
    _dl_items: list = field(default_factory=list)
    _dl_messages: list[dict] = field(default_factory=list)
    _dl_start_time: float = 0.0


@dataclass
class DiagnosticState:
    # Raw magnetometer field (milligauss, RAW_IMU xmag/ymag/zmag) — drives
    # the compass-calibration sample sphere in Compass3DPanel.
    mag_x: int = 0
    mag_y: int = 0
    mag_z: int = 0
    vibe_x: float = 0.0
    vibe_y: float = 0.0
    vibe_z: float = 0.0
    vibe_clip0: int = 0
    vibe_clip1: int = 0
    vibe_clip2: int = 0
    ekf_vel_var: float = 0.0
    ekf_pos_h_var: float = 0.0
    ekf_pos_v_var: float = 0.0
    ekf_compass_var: float = 0.0
    ekf_terrain_var: float = 0.0
    ekf_flags: int = 0
    wind_dir: float = 0.0
    wind_speed: float = 0.0
    terrain_alt: float = -1.0
    gimbal_pitch: float = 0.0
    gimbal_yaw: float = 0.0


@dataclass
class RcServoState:
    rc_channels: list[int] = field(default_factory=lambda: [0] * 16)
    rc_rssi: int = 0
    servo_out: list[int] = field(default_factory=lambda: [0] * 16)


@dataclass
class LogState:
    _log_list: list[dict] = field(default_factory=list)
    _log_download_id: int = -1
    _log_download_data: bytearray = field(default_factory=bytearray)
    _log_download_size: int = 0
    _log_download_ofs: int = 0
    # End offset of the currently-requested LOG_REQUEST_DATA window. AP
    # answers one request with one atomic burst and silently drops any new
    # request that arrives mid-burst — so the GCS must not re-request until
    # progress reaches this boundary (AP_Logger_MAVLinkLogTransfer.cpp:111).
    _log_window_end: int = 0
    # Stall watchdog (twin of transport.ts dlStallRetries). The window cadence
    # sends the next request only from handle_log_data — if the boundary frame
    # is lost, no LOG_DATA ever arrives again and the download would hang
    # forever. check_log_dl_stall() re-requests from the high-water mark.
    _log_last_data_time: float = 0.0
    _log_stall_retries: int = 0
    # Wall-clock throttle for log_progress messages. The old per-10-frames
    # cadence was tuned for 4500 B windows; a whole-log stream would emit
    # tens of thousands of progress messages and drown the ws drain.
    _log_last_progress_time: float = 0.0
    # Coverage of accepted LOG_DATA byte ranges as sorted disjoint [start,end)
    # intervals. Mid-window frame loss leaves zero-filled holes the high-water
    # cadence never revisits; covered-bytes short of the final size is the
    # only tell. Intervals (not a raw sum) because stall re-requests can
    # legitimately overlap late frames of the old burst — an inflated sum
    # would mask a real hole elsewhere.
    _log_recv_intervals: list[tuple[int, int]] = field(default_factory=list)
    # Offset already streamed to the frontend as log_chunk messages. Lets
    # handle_log_data emit fresh chunks of CHUNK_SIZE bytes as the bytearray
    # high-water mark grows, instead of waiting for the whole log and
    # base64-encoding it in one shot (peak memory ~5× the log size).
    _log_emit_ofs: int = 0
    _log_messages: list[dict] = field(default_factory=list)


@dataclass
class TrafficState:
    _adsb_vehicles: dict[int, dict] = field(default_factory=dict)

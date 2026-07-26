"""Dry-run hand-launch state machine for FPV AI Gate-Lock.

The state machine models the agreed MVP launch path without arming hardware or
publishing commands. It is intended to become the contract for the future
Betaflight FPV-AI fork and launcher UI.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

REPORT_SCHEMA = "fpv_ai_launch_state_report.v1"


class LaunchState(str, Enum):
    DISARMED = "DISARMED"
    TARGET_SEARCH = "TARGET_SEARCH"
    TARGET_CANDIDATE = "TARGET_CANDIDATE"
    TARGET_LOCKED = "TARGET_LOCKED"
    AI_PREARM_READY = "AI_PREARM_READY"
    BUTTON_CONFIRMED = "BUTTON_CONFIRMED"
    AI_ARM_REQUEST = "AI_ARM_REQUEST"
    ARMED_IDLE = "ARMED_IDLE"
    HAND_RELEASE_DETECTED = "HAND_RELEASE_DETECTED"
    STABILIZE = "STABILIZE"
    THROTTLE_RAMP = "THROTTLE_RAMP"
    AI_ACTIVE = "AI_ACTIVE"
    GATE_APPROACH = "GATE_APPROACH"
    GATE_PASS = "GATE_PASS"
    COMPLETE = "COMPLETE"
    MANUAL_KILL = "MANUAL_KILL"


@dataclass(frozen=True)
class LaunchConfig:
    throttle_ramp_ms: int = 200

    def __post_init__(self) -> None:
        if self.throttle_ramp_ms <= 0:
            raise ValueError("throttle_ramp_ms must be positive")


@dataclass(frozen=True)
class LaunchInputFrame:
    frame_index: int
    timestamp_ms: int
    target_state: str = "NO_TARGET"
    target_locked: bool = False
    button_pressed: bool = False
    throttle_low: bool = True
    fc_armed: bool = False
    hand_release_detected: bool = False
    stabilized: bool = False
    gate_passed: bool = False
    manual_kill: bool = False
    watchdog_ok: bool = True

    def __post_init__(self) -> None:
        if self.frame_index < 0:
            raise ValueError("frame_index must be non-negative")
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms must be non-negative")


class LaunchStateMachine:
    def __init__(self, config: LaunchConfig | None = None) -> None:
        self.config = config or LaunchConfig()
        self.state = LaunchState.DISARMED
        self.state_entered_ms = 0
        self.throttle_ramp_started_ms: int | None = None

    def update(self, frame: LaunchInputFrame) -> dict[str, Any]:
        previous_state = self.state
        transition_reason = "hold"
        blocking_reason = ""

        if frame.manual_kill:
            self._transition(LaunchState.MANUAL_KILL, frame.timestamp_ms)
            transition_reason = "manual_kill_requested"
            blocking_reason = "manual_kill"
        elif not frame.watchdog_ok:
            transition_reason = "watchdog_rejected_ai_command"
            blocking_reason = "watchdog_not_ok"
        else:
            transition_reason = self._advance(frame)

        return self._snapshot(
            frame,
            previous_state=previous_state,
            transition_reason=transition_reason,
            blocking_reason=blocking_reason,
        )

    def _advance(self, frame: LaunchInputFrame) -> str:
        if self.state is LaunchState.MANUAL_KILL:
            return "manual_kill_latched"
        if self.state is LaunchState.COMPLETE:
            return "mission_complete_latched"

        if self.state is LaunchState.DISARMED:
            if _is_locked(frame):
                self._transition(LaunchState.TARGET_LOCKED, frame.timestamp_ms)
                return "target_locked_from_disarmed"
            if _is_candidate(frame):
                self._transition(LaunchState.TARGET_CANDIDATE, frame.timestamp_ms)
                return "target_candidate_from_disarmed"
            self._transition(LaunchState.TARGET_SEARCH, frame.timestamp_ms)
            return "start_target_search"

        if self.state is LaunchState.TARGET_SEARCH:
            if _is_locked(frame):
                self._transition(LaunchState.TARGET_LOCKED, frame.timestamp_ms)
                return "target_locked"
            if _is_candidate(frame):
                self._transition(LaunchState.TARGET_CANDIDATE, frame.timestamp_ms)
                return "target_candidate"
            return "searching"

        if self.state is LaunchState.TARGET_CANDIDATE:
            if _is_locked(frame):
                self._transition(LaunchState.TARGET_LOCKED, frame.timestamp_ms)
                return "candidate_promoted_to_lock"
            if not _is_candidate(frame):
                self._transition(LaunchState.TARGET_SEARCH, frame.timestamp_ms)
                return "candidate_lost"
            return "candidate_hold"

        if self.state is LaunchState.TARGET_LOCKED:
            if not _is_locked(frame):
                self._transition(LaunchState.TARGET_CANDIDATE if _is_candidate(frame) else LaunchState.TARGET_SEARCH, frame.timestamp_ms)
                return "lock_not_stable"
            if frame.throttle_low:
                self._transition(LaunchState.AI_PREARM_READY, frame.timestamp_ms)
                return "prearm_ready_throttle_low"
            return "wait_for_throttle_low"

        if self.state is LaunchState.AI_PREARM_READY:
            if not _is_locked(frame):
                self._transition(LaunchState.TARGET_CANDIDATE if _is_candidate(frame) else LaunchState.TARGET_SEARCH, frame.timestamp_ms)
                return "prearm_cancelled_target_not_locked"
            if frame.button_pressed:
                self._transition(LaunchState.BUTTON_CONFIRMED, frame.timestamp_ms)
                return "operator_button_confirmed"
            return "ready_waiting_for_button"

        if self.state is LaunchState.BUTTON_CONFIRMED:
            if not _is_locked(frame):
                self._transition(LaunchState.TARGET_CANDIDATE if _is_candidate(frame) else LaunchState.TARGET_SEARCH, frame.timestamp_ms)
                return "button_confirm_cancelled_target_not_locked"
            if not frame.throttle_low:
                return "button_confirmed_wait_for_throttle_low"
            self._transition(LaunchState.AI_ARM_REQUEST, frame.timestamp_ms)
            return "ai_arm_request_throttle_low"

        if self.state is LaunchState.AI_ARM_REQUEST:
            if frame.fc_armed:
                self._transition(LaunchState.ARMED_IDLE, frame.timestamp_ms)
                return "flight_controller_armed_idle"
            return "waiting_for_flight_controller_arm_ack"

        if self.state is LaunchState.ARMED_IDLE:
            if frame.hand_release_detected:
                self._transition(LaunchState.HAND_RELEASE_DETECTED, frame.timestamp_ms)
                return "hand_release_detected"
            return "armed_idle_wait_for_hand_release"

        if self.state is LaunchState.HAND_RELEASE_DETECTED:
            self._transition(LaunchState.STABILIZE, frame.timestamp_ms)
            return "enter_stabilize"

        if self.state is LaunchState.STABILIZE:
            if frame.stabilized:
                self._transition(LaunchState.THROTTLE_RAMP, frame.timestamp_ms)
                return "stabilized_start_throttle_ramp"
            return "stabilizing"

        if self.state is LaunchState.THROTTLE_RAMP:
            if self._ramp_progress(frame.timestamp_ms) >= 1.0:
                self._transition(LaunchState.AI_ACTIVE, frame.timestamp_ms)
                return "throttle_ramp_complete"
            return "throttle_ramp_in_progress"

        if self.state is LaunchState.AI_ACTIVE:
            if frame.gate_passed:
                self._transition(LaunchState.GATE_PASS, frame.timestamp_ms)
                return "gate_passed_from_ai_active"
            if _is_candidate(frame):
                self._transition(LaunchState.GATE_APPROACH, frame.timestamp_ms)
                return "gate_approach"
            return "ai_active_recovery_hold"

        if self.state is LaunchState.GATE_APPROACH:
            if frame.gate_passed:
                self._transition(LaunchState.GATE_PASS, frame.timestamp_ms)
                return "gate_passed"
            return "approaching_gate"

        if self.state is LaunchState.GATE_PASS:
            self._transition(LaunchState.COMPLETE, frame.timestamp_ms)
            return "gate_pass_complete"

        raise AssertionError(f"unhandled launch state: {self.state}")

    def _transition(self, next_state: LaunchState, timestamp_ms: int) -> None:
        if next_state is self.state:
            return
        self.state = next_state
        self.state_entered_ms = timestamp_ms
        if next_state is LaunchState.THROTTLE_RAMP:
            self.throttle_ramp_started_ms = timestamp_ms

    def _ramp_progress(self, timestamp_ms: int) -> float:
        if self.throttle_ramp_started_ms is None:
            return 0.0
        elapsed_ms = max(0, timestamp_ms - self.throttle_ramp_started_ms)
        return min(1.0, elapsed_ms / self.config.throttle_ramp_ms)

    def _snapshot(
        self,
        frame: LaunchInputFrame,
        *,
        previous_state: LaunchState,
        transition_reason: str,
        blocking_reason: str,
    ) -> dict[str, Any]:
        ramp_progress = self._ramp_progress(frame.timestamp_ms)
        ai_control_allowed = (
            not blocking_reason
            and self.state
            in {
                LaunchState.THROTTLE_RAMP,
                LaunchState.AI_ACTIVE,
                LaunchState.GATE_APPROACH,
                LaunchState.GATE_PASS,
            }
        )
        arm_request = not blocking_reason and self.state is LaunchState.AI_ARM_REQUEST
        return {
            "schema": "fpv_ai_launch_state.v1",
            "frame_index": frame.frame_index,
            "timestamp_ms": frame.timestamp_ms,
            "previous_state": previous_state.value,
            "launch_state": self.state.value,
            "screen_state": _screen_state(self.state),
            "target_state": frame.target_state,
            "target_locked": frame.target_locked,
            "button_pressed": frame.button_pressed,
            "throttle_low": frame.throttle_low,
            "fc_armed": frame.fc_armed,
            "hand_release_detected": frame.hand_release_detected,
            "stabilized": frame.stabilized,
            "gate_passed": frame.gate_passed,
            "manual_kill": frame.manual_kill,
            "watchdog_ok": frame.watchdog_ok,
            "ai_control_allowed": ai_control_allowed,
            "arm_request": arm_request,
            "throttle_ramp_progress": round(ramp_progress, 3),
            "transition_reason": transition_reason,
            "blocking_reason": blocking_reason,
            "recommended_action": _recommended_action(self.state, blocking_reason),
        }


def run_launch_state_machine(
    frames: list[LaunchInputFrame],
    *,
    source_path: Path | str | None = None,
    config: LaunchConfig | None = None,
    source_schema: str = "",
) -> dict[str, Any]:
    if not frames:
        raise ValueError("at least one launch input frame is required")
    machine = LaunchStateMachine(config)
    events = [machine.update(frame) for frame in sorted(frames, key=lambda item: item.frame_index)]
    state_counts = Counter(str(event["launch_state"]) for event in events)
    blocking_count = sum(1 for event in events if event["blocking_reason"])
    status = "PASS" if blocking_count == 0 else "FAIL"
    return {
        "schema": REPORT_SCHEMA,
        "status": status,
        "generated_at": _utc_now(),
        "source_path": "" if source_path is None else str(source_path),
        "source_schema": source_schema,
        "summary": {
            "input_frame_count": len(frames),
            "event_count": len(events),
            "final_state": events[-1]["launch_state"],
            "complete_reached": bool(state_counts.get(LaunchState.COMPLETE.value, 0)),
            "ai_active_reached": bool(state_counts.get(LaunchState.AI_ACTIVE.value, 0)),
            "gate_pass_reached": bool(state_counts.get(LaunchState.GATE_PASS.value, 0)),
            "arm_request_count": state_counts.get(LaunchState.AI_ARM_REQUEST.value, 0),
            "manual_kill_count": state_counts.get(LaunchState.MANUAL_KILL.value, 0),
            "watchdog_blocked_count": sum(1 for event in events if event["blocking_reason"] == "watchdog_not_ok"),
            "max_throttle_ramp_progress": max(float(event["throttle_ramp_progress"]) for event in events),
            "training_launched": False,
            "cameras_opened": False,
            "uart_opened": False,
            "hardware_test_authorized": False,
            "flight_commands_published": False,
        },
        "state_counts": dict(sorted(state_counts.items())),
        "events": events,
        "safety_boundary": {
            "dry_run_only": True,
            "does_not_launch_training": True,
            "does_not_open_live_cameras": True,
            "does_not_open_uart": True,
            "does_not_authorize_hardware_test": True,
            "does_not_publish_flight_commands": True,
            "manual_kill_required_for_real_props": True,
        },
    }


def write_launch_state_machine_report(
    frames: list[LaunchInputFrame],
    *,
    report_json: Path,
    source_path: Path | str | None = None,
    config: LaunchConfig | None = None,
    source_schema: str = "",
) -> dict[str, Any]:
    report = run_launch_state_machine(frames, source_path=source_path, config=config, source_schema=source_schema)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    persisted_report = dict(report)
    persisted_report["report_path"] = str(report_json)
    report_json.write_text(json.dumps(persisted_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return persisted_report


def launch_inputs_from_command_sequence(command_sequence: Mapping[str, Any]) -> list[LaunchInputFrame]:
    rows = command_sequence.get("commands")
    if not isinstance(rows, list):
        raise ValueError("command sequence must contain a commands list")
    frames: list[LaunchInputFrame] = []
    for fallback_index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise ValueError(f"command row {fallback_index} must be an object")
        lock = row.get("lock")
        if not isinstance(lock, Mapping):
            raise ValueError(f"command row {fallback_index} missing lock object")
        frame_index = int(row.get("frame_index", fallback_index))
        timestamp_ms = int(row.get("timestamp_ms", lock.get("frame_timestamp_ms", 0)))
        frames.append(
            LaunchInputFrame(
                frame_index=frame_index,
                timestamp_ms=timestamp_ms,
                target_state=str(lock.get("tracking_state") or "NO_TARGET"),
                target_locked=bool(lock.get("target_locked", False)),
            )
        )
    return frames


def load_command_sequence(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("command sequence JSON must be an object")
    return payload


def build_synthetic_hand_launch_sequence() -> list[LaunchInputFrame]:
    def locked_frame(
        *,
        frame_index: int,
        timestamp_ms: int,
        button_pressed: bool = False,
        fc_armed: bool = False,
        hand_release_detected: bool = False,
        stabilized: bool = False,
        gate_passed: bool = False,
    ) -> LaunchInputFrame:
        return LaunchInputFrame(
            frame_index=frame_index,
            timestamp_ms=timestamp_ms,
            target_state="LOCKED",
            target_locked=True,
            button_pressed=button_pressed,
            fc_armed=fc_armed,
            hand_release_detected=hand_release_detected,
            stabilized=stabilized,
            gate_passed=gate_passed,
        )

    return [
        LaunchInputFrame(frame_index=0, timestamp_ms=0, target_state="NO_TARGET", target_locked=False),
        LaunchInputFrame(frame_index=1, timestamp_ms=33, target_state="CANDIDATE", target_locked=False),
        locked_frame(frame_index=2, timestamp_ms=66),
        locked_frame(frame_index=3, timestamp_ms=99),
        locked_frame(frame_index=4, timestamp_ms=132, button_pressed=True),
        locked_frame(frame_index=5, timestamp_ms=165),
        locked_frame(frame_index=6, timestamp_ms=198, fc_armed=True),
        locked_frame(frame_index=7, timestamp_ms=231, fc_armed=True, hand_release_detected=True),
        locked_frame(frame_index=8, timestamp_ms=264, fc_armed=True),
        locked_frame(frame_index=9, timestamp_ms=297, fc_armed=True, stabilized=True),
        locked_frame(frame_index=10, timestamp_ms=397, fc_armed=True, stabilized=True),
        locked_frame(frame_index=11, timestamp_ms=531, fc_armed=True, stabilized=True),
        locked_frame(frame_index=12, timestamp_ms=564, fc_armed=True, stabilized=True),
        locked_frame(frame_index=13, timestamp_ms=597, fc_armed=True, stabilized=True, gate_passed=True),
        locked_frame(frame_index=14, timestamp_ms=630, fc_armed=True, stabilized=True),
    ]


def _is_candidate(frame: LaunchInputFrame) -> bool:
    return frame.target_state in {"CANDIDATE", "LOCKED", "DEGRADED", "PREDICTIVE_TRACK", "REACQUIRE", "RECOVERED"}


def _is_locked(frame: LaunchInputFrame) -> bool:
    return frame.target_locked or frame.target_state in {"LOCKED", "RECOVERED"}


def _screen_state(state: LaunchState) -> str:
    mapping = {
        LaunchState.DISARMED: "NO TARGET",
        LaunchState.TARGET_SEARCH: "NO TARGET",
        LaunchState.TARGET_CANDIDATE: "CANDIDATE",
        LaunchState.TARGET_LOCKED: "LOCKED",
        LaunchState.AI_PREARM_READY: "READY TO LAUNCH",
        LaunchState.BUTTON_CONFIRMED: "READY TO LAUNCH",
        LaunchState.AI_ARM_REQUEST: "READY TO LAUNCH",
        LaunchState.ARMED_IDLE: "READY TO LAUNCH",
        LaunchState.HAND_RELEASE_DETECTED: "AI ACTIVE",
        LaunchState.STABILIZE: "AI ACTIVE",
        LaunchState.THROTTLE_RAMP: "AI ACTIVE",
        LaunchState.AI_ACTIVE: "AI ACTIVE",
        LaunchState.GATE_APPROACH: "AI ACTIVE",
        LaunchState.GATE_PASS: "COMPLETE",
        LaunchState.COMPLETE: "COMPLETE",
        LaunchState.MANUAL_KILL: "MANUAL KILL",
    }
    return mapping[state]


def _recommended_action(state: LaunchState, blocking_reason: str) -> str:
    if blocking_reason == "manual_kill":
        return "MANUAL_KILL"
    if blocking_reason == "watchdog_not_ok":
        return "REJECT_AI_CONTROL"
    mapping = {
        LaunchState.DISARMED: "HOLD_DISARMED",
        LaunchState.TARGET_SEARCH: "SEARCH_TARGET",
        LaunchState.TARGET_CANDIDATE: "HOLD_CANDIDATE",
        LaunchState.TARGET_LOCKED: "HOLD_LOCK",
        LaunchState.AI_PREARM_READY: "SHOW_READY_TO_LAUNCH",
        LaunchState.BUTTON_CONFIRMED: "PREPARE_ARM_REQUEST",
        LaunchState.AI_ARM_REQUEST: "REQUEST_AI_ARM",
        LaunchState.ARMED_IDLE: "WAIT_FOR_HAND_RELEASE",
        LaunchState.HAND_RELEASE_DETECTED: "HAND_RELEASE_DETECTED",
        LaunchState.STABILIZE: "STABILIZE",
        LaunchState.THROTTLE_RAMP: "RAMP_THROTTLE",
        LaunchState.AI_ACTIVE: "ENABLE_AI_CONTROL",
        LaunchState.GATE_APPROACH: "APPROACH_GATE",
        LaunchState.GATE_PASS: "MARK_GATE_PASS",
        LaunchState.COMPLETE: "COMPLETE",
        LaunchState.MANUAL_KILL: "MANUAL_KILL",
    }
    return mapping[state]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

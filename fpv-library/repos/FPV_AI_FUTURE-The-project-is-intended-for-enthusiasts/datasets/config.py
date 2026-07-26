"""Load and validate FPV racing gate dataset/runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from fpv_ai.control.speed import SpeedMode, SpeedPolicy, SpeedProfile
from fpv_ai.gates.lock import GateLockConfig

CONFIG_SCHEMA = "fpv_racing_gate_config.v1"
REQUIRED_MVP_LABELS = ("racing_gate", "partial_gate", "false_ring_hard_negative")
REQUIRED_SPEED_MODES = {
    "fixed_speed": SpeedMode.FIXED_SPEED,
    "adaptive_speed": SpeedMode.ADAPTIVE_SPEED,
    "race_speed": SpeedMode.RACE_SPEED,
}


@dataclass(frozen=True)
class DatasetSpec:
    path: Path
    train: str
    val: str
    test: str
    names: dict[int, str]
    optional_future_names: dict[int, str]


@dataclass(frozen=True)
class AugmentationSpec:
    scale_ladder: tuple[float, ...]
    required_effects: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeRpiSpec:
    primary_camera: str
    secondary_camera: str
    ai_accelerator: str
    command_transport: str
    adapter_mode: str
    rgb_camera_device: str
    thermal_camera_device: str
    launcher_button_gpio: int
    manual_kill_gpio: int
    uart_device: str
    uart_baud: int
    stale_ai_command_timeout_ms: int
    log_frames_commands_and_states: bool


@dataclass(frozen=True)
class HardwareAuthority:
    first_propeller_test_authorized_by: str
    software_does_not_authorize_hardware_tests: bool


@dataclass(frozen=True)
class MinimumHardwareProtection:
    manual_kill_switch_required: bool
    no_prop_bench_tests_required_before_powered_tests: bool
    stale_command_protection_required: bool


@dataclass(frozen=True)
class FpvRacingGateConfig:
    schema: str
    domain: str
    status: str
    dataset: DatasetSpec
    augmentation: AugmentationSpec
    target_lock: GateLockConfig
    speed_policy: SpeedPolicy
    runtime_rpi: RuntimeRpiSpec
    hardware_authority: HardwareAuthority
    minimum_hardware_protection: MinimumHardwareProtection


def load_fpv_racing_gate_config(path: Path | str = Path("configs/fpv_racing_gate.yaml")) -> FpvRacingGateConfig:
    config_path = Path(path)
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("FPV racing gate config must be a mapping")
    config = _parse_config(payload)
    validate_fpv_racing_gate_config(config)
    return config


def validate_fpv_racing_gate_config(config: FpvRacingGateConfig) -> None:
    if config.schema != CONFIG_SCHEMA:
        raise ValueError(f"unsupported config schema: {config.schema}")
    label_values = set(config.dataset.names.values())
    missing_labels = [label for label in REQUIRED_MVP_LABELS if label not in label_values]
    if missing_labels:
        raise ValueError(f"missing MVP dataset labels: {', '.join(missing_labels)}")
    if not config.augmentation.scale_ladder:
        raise ValueError("augmentation.scale_ladder must not be empty")
    if any(scale < 1.0 for scale in config.augmentation.scale_ladder):
        raise ValueError("augmentation.scale_ladder values must be >= 1")
    race_profile = config.speed_policy.profile(SpeedMode.RACE_SPEED)
    if not race_profile.adjustable_by_operator:
        raise ValueError("race speed must be adjustable by operator")
    if config.runtime_rpi.adapter_mode != "dry_run_disabled":
        raise ValueError("runtime_rpi.adapter_mode must remain dry_run_disabled until hardware tests are authorized")
    if config.runtime_rpi.launcher_button_gpio < 0 or config.runtime_rpi.manual_kill_gpio < 0:
        raise ValueError("runtime_rpi GPIO numbers must be non-negative")
    if config.runtime_rpi.uart_baud <= 0:
        raise ValueError("runtime_rpi.uart_baud must be positive")
    if config.hardware_authority.first_propeller_test_authorized_by != "project_owner":
        raise ValueError("first propeller test authority must remain project_owner")
    if not config.hardware_authority.software_does_not_authorize_hardware_tests:
        raise ValueError("software must not authorize hardware tests")
    protections = config.minimum_hardware_protection
    if not (
        protections.manual_kill_switch_required
        and protections.no_prop_bench_tests_required_before_powered_tests
        and protections.stale_command_protection_required
    ):
        raise ValueError("minimum hardware protections must remain enabled")


def _parse_config(payload: dict[str, Any]) -> FpvRacingGateConfig:
    return FpvRacingGateConfig(
        schema=_string(payload, "schema"),
        domain=_string(payload, "domain"),
        status=_string(payload, "status"),
        dataset=_dataset_spec(_mapping(payload, "dataset")),
        augmentation=_augmentation_spec(_mapping(payload, "augmentation")),
        target_lock=_target_lock_config(_mapping(payload, "target_lock")),
        speed_policy=_speed_policy(_mapping(payload, "speed_profiles")),
        runtime_rpi=_runtime_rpi_spec(_mapping(payload, "runtime_rpi")),
        hardware_authority=_hardware_authority(_mapping(payload, "hardware_authority")),
        minimum_hardware_protection=_minimum_hardware_protection(_mapping(payload, "minimum_hardware_protection")),
    )


def _dataset_spec(payload: dict[str, Any]) -> DatasetSpec:
    return DatasetSpec(
        path=Path(_string(payload, "path")),
        train=_string(payload, "train"),
        val=_string(payload, "val"),
        test=_string(payload, "test"),
        names=_int_keyed_string_mapping(_mapping(payload, "names")),
        optional_future_names=_int_keyed_string_mapping(
            _mapping(payload, "optional_future_names", required=False)
        ),
    )


def _augmentation_spec(payload: dict[str, Any]) -> AugmentationSpec:
    return AugmentationSpec(
        scale_ladder=tuple(float(value) for value in _list(payload, "scale_ladder")),
        required_effects=tuple(str(value) for value in _list(payload, "required_effects")),
    )


def _target_lock_config(payload: dict[str, Any]) -> GateLockConfig:
    return GateLockConfig(
        confidence_threshold=float(payload["confidence_threshold"]),
        degraded_confidence_threshold=float(payload["degraded_confidence_threshold"]),
        stable_frame_count=int(payload["stable_frame_count"]),
        max_center_jump_px=float(payload["max_center_jump_px"]),
        predictive_track_ms=int(payload["predictive_track_ms"]),
        reacquire_track_ms=int(payload["reacquire_track_ms"]),
    )


def _speed_policy(payload: dict[str, Any]) -> SpeedPolicy:
    profiles: dict[SpeedMode, SpeedProfile] = {}
    for key, expected_mode in REQUIRED_SPEED_MODES.items():
        spec = _mapping(payload, key)
        mode = SpeedMode(_string(spec, "mode"))
        if mode is not expected_mode:
            raise ValueError(f"speed profile {key} must use mode {expected_mode.value}")
        profiles[mode] = SpeedProfile(
            mode=mode,
            min_mps=float(spec["min_mps"]),
            default_mps=float(spec["default_mps"]),
            max_mps=float(spec["max_mps"]),
            operator_limit_mps=float(spec["operator_limit_mps"]),
            adjustable_by_operator=bool(spec.get("adjustable_by_operator", True)),
        )
    return SpeedPolicy(profiles)


def _runtime_rpi_spec(payload: dict[str, Any]) -> RuntimeRpiSpec:
    return RuntimeRpiSpec(
        primary_camera=_string(payload, "primary_camera"),
        secondary_camera=_string(payload, "secondary_camera"),
        ai_accelerator=_string(payload, "ai_accelerator"),
        command_transport=_string(payload, "command_transport"),
        adapter_mode=_string(payload, "adapter_mode"),
        rgb_camera_device=_string(payload, "rgb_camera_device"),
        thermal_camera_device=_string(payload, "thermal_camera_device"),
        launcher_button_gpio=int(payload["launcher_button_gpio"]),
        manual_kill_gpio=int(payload["manual_kill_gpio"]),
        uart_device=_string(payload, "uart_device"),
        uart_baud=int(payload["uart_baud"]),
        stale_ai_command_timeout_ms=int(payload["stale_ai_command_timeout_ms"]),
        log_frames_commands_and_states=bool(payload["log_frames_commands_and_states"]),
    )


def _hardware_authority(payload: dict[str, Any]) -> HardwareAuthority:
    return HardwareAuthority(
        first_propeller_test_authorized_by=_string(payload, "first_propeller_test_authorized_by"),
        software_does_not_authorize_hardware_tests=bool(payload["software_does_not_authorize_hardware_tests"]),
    )


def _minimum_hardware_protection(payload: dict[str, Any]) -> MinimumHardwareProtection:
    return MinimumHardwareProtection(
        manual_kill_switch_required=bool(payload["manual_kill_switch_required"]),
        no_prop_bench_tests_required_before_powered_tests=bool(
            payload["no_prop_bench_tests_required_before_powered_tests"]
        ),
        stale_command_protection_required=bool(payload["stale_command_protection_required"]),
    )


def _mapping(payload: dict[str, Any], key: str, *, required: bool = True) -> dict[str, Any]:
    value = payload.get(key)
    if value is None and not required:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    return value


def _list(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    return value


def _string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _int_keyed_string_mapping(payload: dict[str, Any]) -> dict[int, str]:
    result: dict[int, str] = {}
    for key, value in payload.items():
        if not isinstance(value, str) or not value:
            raise ValueError("dataset class names must be non-empty strings")
        result[int(key)] = value
    return result

"""Betaflight FPV-AI fork command and transport contracts."""

from __future__ import annotations

from fpv_ai.betaflight_link.c_reference import (
    build_betaflight_c_reference_report,
    generate_c_parser_text,
    generate_golden_fixture_text,
    write_betaflight_c_reference_outputs,
)
from fpv_ai.betaflight_link.build_hook_mapper import (
    build_betaflight_build_hook_mapper,
    write_betaflight_build_hook_mapper,
)
from fpv_ai.betaflight_link.commands import AICommand, CommandLimits
from fpv_ai.betaflight_link.fork_contract import (
    build_betaflight_fork_interface_contract,
    generate_c_header_text,
    write_betaflight_fork_interface_contract,
)
from fpv_ai.betaflight_link.fork_unit_tests import (
    build_betaflight_fork_unit_test_contract,
    write_betaflight_fork_unit_test_contract,
)
from fpv_ai.betaflight_link.fork_patch_plan import (
    build_betaflight_fork_patch_plan,
    write_betaflight_fork_patch_plan,
)
from fpv_ai.betaflight_link.fork_patch_bundle import (
    build_betaflight_fork_patch_bundle,
    write_betaflight_fork_patch_bundle,
)
from fpv_ai.betaflight_link.integration_manifest import (
    build_betaflight_fork_integration_manifest,
    write_betaflight_fork_integration_manifest,
)
from fpv_ai.betaflight_link.mode_state_machine import (
    build_betaflight_ai_mode_state_machine_contract,
    write_betaflight_ai_mode_state_machine_contract,
)
from fpv_ai.betaflight_link.mode_manager_c_reference import (
    build_betaflight_mode_manager_c_reference_report,
    generate_mode_manager_fixture_text,
    generate_mode_manager_header_text,
    generate_mode_manager_source_text,
    write_betaflight_mode_manager_c_reference_outputs,
)
from fpv_ai.betaflight_link.owner_decision_intake import (
    OwnerDecisionInput,
    build_betaflight_owner_decision_intake,
    target_profile_input_from_owner_decision_intake,
    write_betaflight_owner_decision_intake,
)
from fpv_ai.betaflight_link.owner_decision_presets import (
    build_betaflight_owner_decision_presets,
    built_in_owner_decision_input_from_preset,
    owner_decision_input_from_preset,
    write_betaflight_owner_decision_presets,
)
from fpv_ai.betaflight_link.owner_decision_review import (
    build_betaflight_owner_decision_review,
    write_betaflight_owner_decision_review,
)
from fpv_ai.betaflight_link.owner_target_promotion_gate import (
    build_betaflight_owner_target_promotion_gate,
    write_betaflight_owner_target_promotion_gate,
)
from fpv_ai.betaflight_link.owner_target_pipeline import (
    build_betaflight_owner_target_pipeline,
    write_betaflight_owner_target_pipeline,
)
from fpv_ai.betaflight_link.parser_sim import (
    ParserSimConfig,
    build_betaflight_parser_sim_report,
    write_betaflight_parser_sim_report,
)
from fpv_ai.betaflight_link.payload_decoder import (
    build_payload_decoder_contract,
    generate_payload_decoder_adapter_text,
    write_payload_decoder_contract,
)
from fpv_ai.betaflight_link.simulated_target_review import (
    build_betaflight_simulated_target_review,
    write_betaflight_simulated_target_review,
)
from fpv_ai.betaflight_link.target_profile import (
    TargetProfileInput,
    build_betaflight_target_profile,
    write_betaflight_target_profile,
)
from fpv_ai.betaflight_link.transport import LinkTimingConfig, decode_command_frame, encode_command_frame

__all__ = [
    "AICommand",
    "CommandLimits",
    "LinkTimingConfig",
    "OwnerDecisionInput",
    "ParserSimConfig",
    "TargetProfileInput",
    "build_betaflight_c_reference_report",
    "build_betaflight_ai_mode_state_machine_contract",
    "build_betaflight_build_hook_mapper",
    "build_betaflight_fork_interface_contract",
    "build_betaflight_fork_integration_manifest",
    "build_betaflight_fork_patch_bundle",
    "build_betaflight_fork_patch_plan",
    "build_betaflight_fork_unit_test_contract",
    "build_betaflight_mode_manager_c_reference_report",
    "build_betaflight_owner_decision_intake",
    "build_betaflight_owner_decision_presets",
    "build_betaflight_owner_decision_review",
    "build_betaflight_owner_target_promotion_gate",
    "build_betaflight_owner_target_pipeline",
    "build_betaflight_parser_sim_report",
    "build_betaflight_simulated_target_review",
    "build_betaflight_target_profile",
    "build_payload_decoder_contract",
    "built_in_owner_decision_input_from_preset",
    "decode_command_frame",
    "encode_command_frame",
    "generate_c_parser_text",
    "generate_c_header_text",
    "generate_golden_fixture_text",
    "generate_mode_manager_fixture_text",
    "generate_mode_manager_header_text",
    "generate_mode_manager_source_text",
    "generate_payload_decoder_adapter_text",
    "owner_decision_input_from_preset",
    "target_profile_input_from_owner_decision_intake",
    "write_betaflight_c_reference_outputs",
    "write_betaflight_ai_mode_state_machine_contract",
    "write_betaflight_build_hook_mapper",
    "write_betaflight_fork_interface_contract",
    "write_betaflight_fork_integration_manifest",
    "write_betaflight_fork_patch_bundle",
    "write_betaflight_fork_patch_plan",
    "write_betaflight_fork_unit_test_contract",
    "write_betaflight_mode_manager_c_reference_outputs",
    "write_betaflight_owner_decision_intake",
    "write_betaflight_owner_decision_presets",
    "write_betaflight_owner_decision_review",
    "write_betaflight_owner_target_promotion_gate",
    "write_betaflight_owner_target_pipeline",
    "write_betaflight_parser_sim_report",
    "write_betaflight_simulated_target_review",
    "write_betaflight_target_profile",
    "write_payload_decoder_contract",
]

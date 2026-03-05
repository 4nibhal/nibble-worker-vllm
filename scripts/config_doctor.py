#!/usr/bin/env python3
"""Lightweight runtime config contract checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


FORBIDDEN_ZERO_KEYS = {
    "NUM_GPU_BLOCKS_OVERRIDE",
    "MAX_CPU_LORAS",
    "MAX_PARALLEL_LOADING_WORKERS",
}

UNSET_OPTIONAL_VALUES = {"", "None", "none"}
ENABLE_FLASHINFER_KEY = "ENABLE_FLASHINFER"
DISABLE_FLASHINFER_PREFILL_KEY = "DISABLE_FLASHINFER_PREFILL"
FLASHINFER_TOOLCHAIN_READY_KEY = "FLASHINFER_TOOLCHAIN_READY"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _is_zero(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, str):
        return value.strip() == "0"
    return False


def _check_forbidden_zeros(hub: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    config = hub.get("config") if isinstance(hub, dict) else None
    presets = config.get("presets") if isinstance(config, dict) else None

    if not isinstance(presets, list):
        errors.append(".runpod/hub.json missing config.presets list")
        return errors

    for preset in presets:
        if not isinstance(preset, dict):
            continue

        preset_name = str(preset.get("name", "<unnamed>"))
        defaults = preset.get("defaults")
        if not isinstance(defaults, dict):
            continue

        for key in FORBIDDEN_ZERO_KEYS:
            if key in defaults and _is_zero(defaults.get(key)):
                errors.append(
                    f"preset '{preset_name}' sets forbidden zero value for {key}"
                )

    return errors


def _is_positive_int_or_string_int(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("+"):
            stripped = stripped[1:]
        return stripped.isdigit() and int(stripped) > 0
    return False


def _check_optional_override_values(hub: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    config = hub.get("config") if isinstance(hub, dict) else None
    presets = config.get("presets") if isinstance(config, dict) else None

    if not isinstance(presets, list):
        return warnings

    for preset in presets:
        if not isinstance(preset, dict):
            continue

        preset_name = str(preset.get("name", "<unnamed>"))
        defaults = preset.get("defaults")
        if not isinstance(defaults, dict):
            continue

        for key in FORBIDDEN_ZERO_KEYS:
            if key not in defaults:
                continue
            value = defaults.get(key)
            if isinstance(value, str) and value.strip() in UNSET_OPTIONAL_VALUES:
                continue
            if _is_positive_int_or_string_int(value):
                continue
            warnings.append(
                f"preset '{preset_name}' sets {key}={value!r}; expected one of '', 'None', 'none', or a positive integer"
            )

    return warnings


def _warn_language_model_only_compat(hub: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    config = hub.get("config") if isinstance(hub, dict) else None
    presets = config.get("presets") if isinstance(config, dict) else None

    if not isinstance(presets, list):
        return warnings

    for preset in presets:
        if not isinstance(preset, dict):
            continue

        preset_name = str(preset.get("name", "<unnamed>"))
        defaults = preset.get("defaults")
        if not isinstance(defaults, dict):
            continue

        raw_value = defaults.get("LANGUAGE_MODEL_ONLY")
        enabled = raw_value is True or (
            isinstance(raw_value, str) and raw_value.strip().lower() == "true"
        )
        if enabled:
            warnings.append(
                f"preset '{preset_name}' enables LANGUAGE_MODEL_ONLY; verify runtime uses pinned nightly vLLM 0.16.1rc1.dev257+g3b23d57c9 (or another build exposing AsyncEngineArgs.language_model_only) because stable 0.16.0 rejects this arg"
            )

    return warnings


def _as_bool_with_default(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default


def _is_qwen35_model_name(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.lower().replace("-", "").replace("_", "")
    return "qwen3.5" in value.lower() or "qwen35" in normalized


def _is_flashinfer_backend(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().upper().replace("-", "_")
    return normalized == "FLASHINFER"


def _check_flashinfer_opt_in_posture(
    hub: dict[str, Any],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    config = hub.get("config") if isinstance(hub, dict) else None
    presets = config.get("presets") if isinstance(config, dict) else None

    if not isinstance(presets, list):
        return errors, warnings

    for preset in presets:
        if not isinstance(preset, dict):
            continue

        preset_name = str(preset.get("name", "<unnamed>"))
        defaults = preset.get("defaults")
        if not isinstance(defaults, dict):
            continue

        if not _is_qwen35_model_name(defaults.get("MODEL_NAME")):
            continue

        disable_prefill = _as_bool_with_default(
            defaults.get(DISABLE_FLASHINFER_PREFILL_KEY),
            True,
        )
        attention_backend = defaults.get("ATTENTION_BACKEND")
        flashinfer_backend_requested = _is_flashinfer_backend(attention_backend)
        flashinfer_prefill_enabled = not disable_prefill
        flashinfer_opt_in = flashinfer_backend_requested and flashinfer_prefill_enabled

        if not flashinfer_opt_in:
            if flashinfer_backend_requested and not flashinfer_prefill_enabled:
                warnings.append(
                    f"preset '{preset_name}' sets ATTENTION_BACKEND=FLASHINFER but keeps {DISABLE_FLASHINFER_PREFILL_KEY}=true"
                )
            elif flashinfer_prefill_enabled and not flashinfer_backend_requested:
                warnings.append(
                    f"preset '{preset_name}' sets {DISABLE_FLASHINFER_PREFILL_KEY}=false but ATTENTION_BACKEND is not FLASHINFER"
                )
            continue

        enable_flashinfer = _as_bool_with_default(
            defaults.get(ENABLE_FLASHINFER_KEY),
            False,
        )
        toolchain_ready = _as_bool_with_default(
            defaults.get(FLASHINFER_TOOLCHAIN_READY_KEY),
            False,
        )

        if not enable_flashinfer:
            errors.append(
                f"preset '{preset_name}' opts into flashinfer but {ENABLE_FLASHINFER_KEY} is not true"
            )
        if not toolchain_ready:
            errors.append(
                f"preset '{preset_name}' opts into flashinfer without {FLASHINFER_TOOLCHAIN_READY_KEY}=true explicit posture"
            )

        if (
            _is_qwen35_model_name(defaults.get("MODEL_NAME"))
            and flashinfer_backend_requested
        ):
            warnings.append(
                f"preset '{preset_name}' enables FLASHINFER prefill on Qwen3.5; "
                "verify nvcc+ninja+C++ toolchain and startup probe to avoid gdn_prefill_sm90 JIT exit 127"
            )

    return errors, warnings


def _warn_env_key_mismatch(hub: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    config = hub.get("config") if isinstance(hub, dict) else None
    env = config.get("env") if isinstance(config, dict) else None

    if not isinstance(env, list):
        warnings.append(".runpod/hub.json missing config.env list")
        return warnings

    keys = {
        item.get("key")
        for item in env
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    }

    has_legacy = (
        "DEFAULT_MIN_BATCH_SIZE" in keys or "DEFAULT_BATCH_SIZE_GROWTH_FACTOR" in keys
    )
    has_runtime = "MIN_BATCH_SIZE" in keys or "BATCH_SIZE_GROWTH_FACTOR" in keys

    if has_legacy and not has_runtime:
        warnings.append(
            "hub env exposes DEFAULT_MIN_BATCH_SIZE/DEFAULT_BATCH_SIZE_GROWTH_FACTOR "
            "but runtime reads MIN_BATCH_SIZE/BATCH_SIZE_GROWTH_FACTOR"
        )

    return warnings


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        root = _repo_root()
    except Exception as exc:  # pragma: no cover - operational guard
        print(f"ERROR: could not determine repo root: {exc}")
        return 1

    aiwf_config_path = root / "aiwf.config.json"
    aiwf_request_path = root / "aiwf.request.json"
    hub_path = root / ".runpod" / "hub.json"

    try:
        aiwf_config = _load_json(aiwf_config_path)
    except Exception as exc:
        errors.append(f"failed to parse {aiwf_config_path.relative_to(root)}: {exc}")
        aiwf_config = None

    if isinstance(aiwf_config, dict):
        schema_rel = (
            aiwf_config.get("request_contract", {}).get("schema")
            if isinstance(aiwf_config.get("request_contract"), dict)
            else None
        )
        if not isinstance(schema_rel, str) or not schema_rel.strip():
            errors.append("aiwf.config.json missing request_contract.schema")
        else:
            schema_path = root / schema_rel
            if not schema_path.exists():
                warnings.append(f"declared schema path does not exist: {schema_rel}")

    try:
        _load_json(aiwf_request_path)
    except Exception as exc:
        errors.append(f"failed to parse {aiwf_request_path.relative_to(root)}: {exc}")

    try:
        hub = _load_json(hub_path)
    except Exception as exc:
        errors.append(f"failed to parse {hub_path.relative_to(root)}: {exc}")
        hub = None

    if isinstance(hub, dict):
        errors.extend(_check_forbidden_zeros(hub))
        warnings.extend(_check_optional_override_values(hub))
        warnings.extend(_warn_language_model_only_compat(hub))
        flashinfer_errors, flashinfer_warnings = _check_flashinfer_opt_in_posture(hub)
        errors.extend(flashinfer_errors)
        warnings.extend(flashinfer_warnings)
        warnings.extend(_warn_env_key_mismatch(hub))

    for msg in errors:
        print(f"ERROR: {msg}")
    for msg in warnings:
        print(f"WARN: {msg}")

    if errors:
        print("FAIL: config doctor")
        return 1

    print("PASS: config doctor")
    return 0


if __name__ == "__main__":
    sys.exit(main())

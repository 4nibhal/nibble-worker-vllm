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

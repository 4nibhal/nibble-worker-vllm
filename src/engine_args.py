import os
import json
import logging
import re
from typing import get_origin, get_args
from vllm import AsyncEngineArgs

try:
    from vllm import __version__ as VLLM_VERSION
except Exception:  # pragma: no cover - defensive fallback for unusual builds
    VLLM_VERSION = "unknown"
from vllm.model_executor.model_loader.tensorizer import TensorizerConfig
from src.utils import convert_limit_mm_per_prompt

# Backward-compat: env var names users already know → engine arg name
ENV_ALIASES = {
    "MODEL_NAME": "model",
    "MODEL_REVISION": "revision",
    "TOKENIZER_NAME": "tokenizer",
    "HUGGINGFACE_ACCESS_TOKEN": "hf_token",
    "HUGGING_FACE_HUB_TOKEN": "hf_token",
}

# Literal defaults from original worker (used when env/local do not set a value)
DEFAULT_ARGS = {
    "disable_log_stats": False,
    "enable_log_requests": False,
    "gpu_memory_utilization": 0.95,
    "pipeline_parallel_size": 1,
    "tensor_parallel_size": 1,
    "skip_tokenizer_init": False,
    "tokenizer_mode": "auto",
    "trust_remote_code": False,
    "load_format": "auto",
    "dtype": "auto",
    "kv_cache_dtype": "auto",
    "seed": 0,
    "worker_use_ray": False,
    "block_size": 16,
    "enable_prefix_caching": False,
    "disable_sliding_window": False,
    "swap_space": 4,
    "cpu_offload_gb": 0,
    "max_num_seqs": 256,
    "max_logprobs": 20,
    "enforce_eager": False,
    "max_seq_len_to_capture": 8192,
    "disable_custom_all_reduce": False,
    "tokenizer_pool_size": 0,
    "tokenizer_pool_type": "ray",
    "enable_lora": False,
    "max_loras": 1,
    "max_lora_rank": 16,
    "enable_prompt_adapter": False,
    "max_prompt_adapters": 1,
    "max_prompt_adapter_token": 0,
    "fully_sharded_loras": False,
    "lora_extra_vocab_size": 256,
    "lora_dtype": "auto",
    "device": "auto",
    "ray_workers_use_nsight": False,
    "num_lookahead_slots": 0,
    "scheduler_delay_factor": 0.0,
    "guided_decoding_backend": "outlines",
    "spec_decoding_acceptance_method": "rejection_sampler",
    "stream_interval": 1,
}

SAFE_MAX_NUM_BATCHED_TOKENS_CAP_DEFAULT = 8192
SAFE_MAX_MODEL_LEN_CAP_DEFAULT = 32768
LARGE_CONTEXT_CHUNKED_PREFILL_THRESHOLD = 32768
QWEN35_QUALITY_CONTEXT_TARGET = 131072
STRICT_CONFIG_ENV_KEY = "STRICT_CONFIG"

CRITICAL_NUMERIC_ENV_KEYS = {
    "MAX_MODEL_LEN",
    "MAX_NUM_BATCHED_TOKENS",
    "NUM_GPU_BLOCKS_OVERRIDE",
    "MAX_CPU_LORAS",
    "MAX_PARALLEL_LOADING_WORKERS",
    "SAFE_MAX_MODEL_LEN_CAP",
    "SAFE_MAX_NUM_BATCHED_TOKENS_CAP",
}

KNOWN_BAD_ZERO_OPTIONAL_OVERRIDES = {
    "NUM_GPU_BLOCKS_OVERRIDE": "num_gpu_blocks_override",
    "MAX_PARALLEL_LOADING_WORKERS": "max_parallel_loading_workers",
    "MAX_CPU_LORAS": "max_cpu_loras",
}

RUNTIME_PROFILE_SAFE = "safe"
RUNTIME_PROFILE_BALANCED = "balanced"
RUNTIME_PROFILE_THROUGHPUT = "throughput"
ALLOWED_RUNTIME_PROFILES = {
    RUNTIME_PROFILE_SAFE,
    RUNTIME_PROFILE_BALANCED,
    RUNTIME_PROFILE_THROUGHPUT,
}

MODEL_PROFILE_AUTO = "auto"
MODEL_PROFILE_QWEN3_5_27B = "qwen3_5_27b"
MODEL_PROFILE_GENERAL_7B = "general_7b"
MODEL_PROFILE_GENERAL_14B = "general_14b"
ALLOWED_MODEL_PROFILES = {
    MODEL_PROFILE_AUTO,
    MODEL_PROFILE_QWEN3_5_27B,
    MODEL_PROFILE_GENERAL_7B,
    MODEL_PROFILE_GENERAL_14B,
}

PROFILE_DEFAULTS = {
    MODEL_PROFILE_QWEN3_5_27B: {
        "max_model_len": 32768,
        "max_num_batched_tokens": 8192,
        "max_num_seqs": {
            RUNTIME_PROFILE_SAFE: 64,
            RUNTIME_PROFILE_BALANCED: 96,
            RUNTIME_PROFILE_THROUGHPUT: 128,
        },
        "gpu_memory_utilization": {
            RUNTIME_PROFILE_SAFE: 0.9,
            RUNTIME_PROFILE_BALANCED: 0.92,
            RUNTIME_PROFILE_THROUGHPUT: 0.95,
        },
        "enforce_eager": {
            RUNTIME_PROFILE_SAFE: True,
            RUNTIME_PROFILE_BALANCED: True,
            RUNTIME_PROFILE_THROUGHPUT: False,
        },
        "language_model_only": True,
        "enable_chunked_prefill": True,
    },
    MODEL_PROFILE_GENERAL_14B: {
        "max_model_len": 32768,
        "max_num_batched_tokens": 8192,
        "max_num_seqs": {
            RUNTIME_PROFILE_SAFE: 64,
            RUNTIME_PROFILE_BALANCED: 128,
            RUNTIME_PROFILE_THROUGHPUT: 160,
        },
        "gpu_memory_utilization": {
            RUNTIME_PROFILE_SAFE: 0.9,
            RUNTIME_PROFILE_BALANCED: 0.92,
            RUNTIME_PROFILE_THROUGHPUT: 0.95,
        },
        "enforce_eager": {
            RUNTIME_PROFILE_SAFE: True,
            RUNTIME_PROFILE_BALANCED: False,
            RUNTIME_PROFILE_THROUGHPUT: False,
        },
        "language_model_only": False,
        "enable_chunked_prefill": True,
    },
    MODEL_PROFILE_GENERAL_7B: {
        "max_model_len": 16384,
        "max_num_batched_tokens": 8192,
        "max_num_seqs": {
            RUNTIME_PROFILE_SAFE: 128,
            RUNTIME_PROFILE_BALANCED: 192,
            RUNTIME_PROFILE_THROUGHPUT: 256,
        },
        "gpu_memory_utilization": {
            RUNTIME_PROFILE_SAFE: 0.92,
            RUNTIME_PROFILE_BALANCED: 0.94,
            RUNTIME_PROFILE_THROUGHPUT: 0.96,
        },
        "enforce_eager": {
            RUNTIME_PROFILE_SAFE: False,
            RUNTIME_PROFILE_BALANCED: False,
            RUNTIME_PROFILE_THROUGHPUT: False,
        },
        "language_model_only": False,
        "enable_chunked_prefill": True,
    },
}


def _env_is_true(env_key: str) -> bool:
    return os.getenv(env_key, "").strip().lower() in ("true", "1", "yes", "on")


def _strict_config_enabled() -> bool:
    return _env_is_true(STRICT_CONFIG_ENV_KEY)


def _handle_critical_numeric_parse_error(
    env_key: str, raw_value: str, error: Exception
) -> None:
    is_critical = env_key in CRITICAL_NUMERIC_ENV_KEYS
    scope = "critical numeric env" if is_critical else "env"
    message = f"Invalid {scope} {env_key}={raw_value!r}: {error}"
    if _strict_config_enabled() and is_critical:
        raise ValueError(f"{message}. STRICT_CONFIG=true") from error
    logging.warning("%s; ignoring invalid value", message)


def _normalize_known_bad_zero_overrides(args: dict) -> None:
    for env_key, arg_key in KNOWN_BAD_ZERO_OPTIONAL_OVERRIDES.items():
        raw_value = os.getenv(env_key)
        if raw_value is None:
            continue
        value = raw_value.strip()
        if value in ("", "None", "none"):
            continue
        try:
            numeric_value = int(value)
        except ValueError as e:
            _handle_critical_numeric_parse_error(env_key, raw_value, e)
            continue

        if numeric_value == 0:
            message = (
                f"{env_key}=0 is unsupported and treated as unset; "
                "leave it empty/unset instead"
            )
            if _strict_config_enabled():
                raise ValueError(f"{message} (STRICT_CONFIG=true)")
            logging.warning(message)
            args[arg_key] = None
        elif numeric_value < 0:
            message = (
                f"{env_key}={numeric_value} is invalid; value must be positive or unset"
            )
            if _strict_config_enabled():
                raise ValueError(f"{message} (STRICT_CONFIG=true)")
            logging.warning("%s; treating as unset", message)
            args[arg_key] = None


def _env_has_explicit_value(env_key: str, zero_means_unset: bool = False) -> bool:
    raw_value = os.getenv(env_key)
    if raw_value is None:
        return False
    value = raw_value.strip()
    if value in ("", "None", "none"):
        return False
    if zero_means_unset and value == "0":
        return False
    return True


def _is_qwen3_5_model(model_name: str) -> bool:
    normalized = model_name.lower().replace("-", "").replace("_", "")
    return "qwen3.5" in model_name.lower() or "qwen35" in normalized


def _ensure_qwen3_5_runtime_compat(args: dict, valid_fields: dict) -> None:
    model_name = str(args.get("model", ""))
    if not _is_qwen3_5_model(model_name):
        return

    if "language_model_only" not in valid_fields:
        raise RuntimeError(
            "Incompatible runtime for Qwen3.5 text-only startup: this image uses "
            f"vLLM {VLLM_VERSION} without AsyncEngineArgs.language_model_only support. "
            "Rebuild with vLLM >= 0.16.1 (fork default), or switch MODEL_NAME to a model "
            "compatible with this runtime."
        )

    if args.get("language_model_only") is not True:
        raise RuntimeError(
            "Qwen3.5 startup requires LANGUAGE_MODEL_ONLY=true on this worker path to avoid "
            "unsupported multimodal architecture initialization "
            "(Qwen3_5ForConditionalGeneration)."
        )


def _infer_model_size_b(model_name: str):
    if not model_name:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*([bm])\b", model_name.lower())
    if not match:
        return None
    try:
        size = float(match.group(1))
        suffix = match.group(2)
        if suffix == "m":
            return size / 1000.0
        return size
    except ValueError:
        return None


def _resolve_model_profile(model_name: str) -> str:
    raw_profile = os.getenv("MODEL_PROFILE", MODEL_PROFILE_AUTO).strip().lower()
    if raw_profile and raw_profile not in ALLOWED_MODEL_PROFILES:
        logging.warning(
            "Invalid MODEL_PROFILE=%r; using %s",
            raw_profile,
            MODEL_PROFILE_AUTO,
        )
        raw_profile = MODEL_PROFILE_AUTO

    if raw_profile != MODEL_PROFILE_AUTO:
        return raw_profile

    if _is_qwen3_5_model(model_name):
        return MODEL_PROFILE_QWEN3_5_27B

    size_b = _infer_model_size_b(model_name)
    if size_b is None:
        return MODEL_PROFILE_GENERAL_14B
    if size_b >= 14:
        return MODEL_PROFILE_GENERAL_14B
    return MODEL_PROFILE_GENERAL_7B


def _resolve_runtime_profile(model_name: str) -> str:
    raw_profile = os.getenv("RUNTIME_PROFILE", "").strip().lower()
    if raw_profile:
        if raw_profile in ALLOWED_RUNTIME_PROFILES:
            return raw_profile
        logging.warning(
            "Invalid RUNTIME_PROFILE=%r; selecting profile from model size",
            raw_profile,
        )

    size_b = _infer_model_size_b(model_name)
    if size_b is None or size_b >= 14:
        return RUNTIME_PROFILE_SAFE
    return RUNTIME_PROFILE_BALANCED


def _compute_profile_defaults(model_name: str) -> dict:
    model_profile = _resolve_model_profile(model_name)
    runtime_profile = _resolve_runtime_profile(model_name)
    profile = PROFILE_DEFAULTS[model_profile]

    computed = {
        "max_model_len": profile["max_model_len"],
        "max_num_batched_tokens": profile["max_num_batched_tokens"],
        "max_num_seqs": profile["max_num_seqs"][runtime_profile],
        "gpu_memory_utilization": profile["gpu_memory_utilization"][runtime_profile],
        "enforce_eager": profile["enforce_eager"][runtime_profile],
        "language_model_only": profile["language_model_only"],
        "enable_chunked_prefill": profile["enable_chunked_prefill"],
    }
    logging.info(
        "Runtime profile defaults selected: runtime_profile=%s model_profile=%s",
        runtime_profile,
        model_profile,
    )
    return computed


def _get_safe_max_num_batched_tokens_cap() -> int:
    raw_cap = os.getenv("SAFE_MAX_NUM_BATCHED_TOKENS_CAP")
    if raw_cap is None:
        return SAFE_MAX_NUM_BATCHED_TOKENS_CAP_DEFAULT
    try:
        cap = int(raw_cap)
        if cap <= 0:
            raise ValueError("cap must be positive")
        return cap
    except ValueError:
        logging.warning(
            "Invalid SAFE_MAX_NUM_BATCHED_TOKENS_CAP=%r; using default %d",
            raw_cap,
            SAFE_MAX_NUM_BATCHED_TOKENS_CAP_DEFAULT,
        )
        return SAFE_MAX_NUM_BATCHED_TOKENS_CAP_DEFAULT


def _get_safe_max_model_len_cap() -> int:
    raw_cap = os.getenv("SAFE_MAX_MODEL_LEN_CAP")
    if raw_cap is None:
        return SAFE_MAX_MODEL_LEN_CAP_DEFAULT
    try:
        cap = int(raw_cap)
        if cap <= 0:
            raise ValueError("cap must be positive")
        return cap
    except ValueError:
        logging.warning(
            "Invalid SAFE_MAX_MODEL_LEN_CAP=%r; using default %d",
            raw_cap,
            SAFE_MAX_MODEL_LEN_CAP_DEFAULT,
        )
        return SAFE_MAX_MODEL_LEN_CAP_DEFAULT


def _resolve_field_type(field_type: type) -> type:
    """Resolve Optional/Union to the concrete type for conversion."""
    origin = get_origin(field_type)
    args = get_args(field_type) if hasattr(field_type, "__args__") else ()
    if origin is not None:
        # Optional[X] is Union[X, None]; X | None is UnionType
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return non_none[0]
    return field_type


def _convert_env_value_to_field_type(value: str, field_name: str, field_type: type):
    """Convert env var string to the type expected by AsyncEngineArgs for this field."""
    val = value.strip() if isinstance(value, str) else value
    if val in ("", "None", "none"):
        args = get_args(field_type) if hasattr(field_type, "__args__") else ()
        if type(None) in (args or ()):
            return None
        raise ValueError("empty value not allowed for non-optional field")
    effective_type = _resolve_field_type(field_type)
    # bool
    if effective_type is bool:
        return str(val).lower() in ("true", "1", "yes", "on")
    # int
    if effective_type is int:
        return int(val)
    # float
    if effective_type is float:
        return float(val)
    # str
    if effective_type is str:
        return str(val)
    # dict, list, or complex (try JSON)
    origin = get_origin(effective_type)
    if effective_type in (dict, list) or origin in (dict, list):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val
    # tuple (e.g. long_lora_scaling_factors) — comma-separated or JSON array
    if effective_type is tuple or origin is tuple:
        args = get_args(field_type) if hasattr(field_type, "__args__") else ()
        elem_types = [a for a in args if a is not Ellipsis]
        elem_type = elem_types[0] if elem_types else str
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return tuple(elem_type(x) for x in parsed)
        except (json.JSONDecodeError, TypeError):
            pass
        return tuple(elem_type(x.strip()) for x in str(val).split(",") if x.strip())
    # Fallback: try int, float, then str
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return str(val)


def _get_args_from_env_auto_discover() -> dict:
    """Auto-discover engine args from env vars using UPPERCASED field names.

    For every field in AsyncEngineArgs, check os.getenv(FIELD_NAME).
    E.g. MAX_MODEL_LEN=4096 -> max_model_len=4096.
    Uses same type conversion as before; supports all vLLM engine args without manual listing.
    """
    args = {}
    valid_fields = AsyncEngineArgs.__dataclass_fields__
    for field_name, field in valid_fields.items():
        env_key = field_name.upper()
        value = os.environ.get(env_key)
        if value is None:
            continue
        try:
            args[field_name] = _convert_env_value_to_field_type(
                value, field_name, field.type
            )
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            _handle_critical_numeric_parse_error(env_key, value, e)
    return args


def _apply_env_aliases(args: dict) -> None:
    """Apply ENV_ALIASES: if MODEL_NAME etc. are set, set the target engine arg."""
    valid_fields = AsyncEngineArgs.__dataclass_fields__
    for alias, target in ENV_ALIASES.items():
        value = os.environ.get(alias)
        if value is None or target not in valid_fields:
            continue
        try:
            args[target] = _convert_env_value_to_field_type(
                value, target, valid_fields[target].type
            )
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            logging.warning("Skip env alias %s=%r: %s", alias, value, e)


def get_speculative_config():
    """Build speculative decoding configuration from environment variables.

    Supports two modes:
    1. Full JSON config via SPECULATIVE_CONFIG env var
    2. Individual env vars for common settings
    """
    # Option 1: Full JSON configuration
    spec_config_json = os.getenv("SPECULATIVE_CONFIG")
    if spec_config_json:
        try:
            config = json.loads(spec_config_json)
            logging.info(f"Using speculative config from SPECULATIVE_CONFIG: {config}")
            return config
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse SPECULATIVE_CONFIG JSON: {e}")
            return None

    # Option 2: Build config from individual environment variables
    spec_method = os.getenv("SPECULATIVE_METHOD")
    spec_model = os.getenv("SPECULATIVE_MODEL")
    _num_spec_tokens = os.getenv("NUM_SPECULATIVE_TOKENS")
    _ngram_max = os.getenv("NGRAM_PROMPT_LOOKUP_MAX")
    _ngram_min = os.getenv("NGRAM_PROMPT_LOOKUP_MIN")

    # Convert numeric vars to int so '0' (hub.json default) is treated as unset
    num_spec_tokens = (int(_num_spec_tokens) or None) if _num_spec_tokens else None
    ngram_max = (int(_ngram_max) or None) if _ngram_max else None
    ngram_min = (int(_ngram_min) or None) if _ngram_min else None

    if not any([spec_method, spec_model, ngram_max]):
        return None

    config = {}

    # Determine method
    if spec_method:
        config["method"] = spec_method
    elif ngram_max and not spec_model:
        config["method"] = "ngram"
    elif spec_model:
        model_lower = spec_model.lower()
        if "eagle3" in model_lower:
            config["method"] = "eagle3"
        elif "eagle" in model_lower:
            config["method"] = "eagle"
        elif "medusa" in model_lower:
            config["method"] = "medusa"
        else:
            config["method"] = "draft_model"

    if spec_model:
        config["model"] = spec_model
    if num_spec_tokens:
        config["num_speculative_tokens"] = num_spec_tokens
    if ngram_max:
        config["prompt_lookup_max"] = ngram_max
    if ngram_min:
        config["prompt_lookup_min"] = ngram_min

    draft_tp = os.getenv("SPECULATIVE_DRAFT_TENSOR_PARALLEL_SIZE")
    if draft_tp:
        config["draft_tensor_parallel_size"] = int(draft_tp)

    spec_max_len = os.getenv("SPECULATIVE_MAX_MODEL_LEN")
    if spec_max_len:
        config["max_model_len"] = int(spec_max_len)

    disable_batch = os.getenv("SPECULATIVE_DISABLE_BY_BATCH_SIZE")
    if disable_batch:
        config["disable_by_batch_size"] = int(disable_batch)

    spec_quant = os.getenv("SPECULATIVE_QUANTIZATION")
    if spec_quant:
        config["quantization"] = spec_quant

    spec_revision = os.getenv("SPECULATIVE_MODEL_REVISION")
    if spec_revision:
        config["revision"] = spec_revision

    spec_eager = os.getenv("SPECULATIVE_ENFORCE_EAGER")
    if spec_eager:
        config["enforce_eager"] = spec_eager.lower() == "true"

    if config:
        logging.info(f"Built speculative config from env vars: {config}")
        return config

    return None


def _resolve_max_model_len(model, trust_remote_code=False, revision=None):
    """Resolve max_model_len from the model's HuggingFace config."""
    try:
        from transformers import AutoConfig

        config = AutoConfig.from_pretrained(
            model,
            trust_remote_code=trust_remote_code,
            revision=revision,
        )
        for attr in (
            "max_position_embeddings",
            "n_positions",
            "max_seq_len",
            "seq_length",
        ):
            val = getattr(config, attr, None)
            if val is not None:
                logging.info(f"Resolved max_model_len={val} from model config ({attr})")
                return val
    except Exception as e:
        logging.warning(f"Could not resolve max_model_len from model config: {e}")
    return None


def _detect_cuda_runtime():
    """Safely detect whether CUDA runtime is usable in current environment."""
    try:
        import torch
    except Exception as e:
        return False, 0, f"torch import failed: {e}"

    try:
        cuda_available = bool(torch.cuda.is_available())
    except Exception as e:
        return False, 0, f"torch.cuda.is_available() failed: {e}"

    try:
        num_gpus = int(torch.cuda.device_count())
    except Exception as e:
        return False, 0, f"torch.cuda.device_count() failed: {e}"

    if not cuda_available:
        return False, num_gpus, "torch.cuda.is_available() returned False"
    if num_gpus <= 0:
        return False, num_gpus, f"torch.cuda.device_count() returned {num_gpus}"

    try:
        current_index = int(torch.cuda.current_device())
        torch.cuda.get_device_properties(current_index)
    except RuntimeError as e:
        return False, num_gpus, f"CUDA usability probe failed: {e}"
    except Exception as e:
        return False, num_gpus, f"Unexpected CUDA usability probe failure: {e}"

    return True, num_gpus, None


def _device_env_is_explicit() -> bool:
    raw = os.getenv("DEVICE")
    if raw is None:
        return False
    value = raw.strip().lower()
    if value in ("", "none", "auto"):
        return False
    return True


def _local_args_to_engine_args(local: dict) -> dict:
    """Map local args (e.g. from /local_model_args.json) to engine arg names and filter."""
    valid = AsyncEngineArgs.__dataclass_fields__
    out = {}
    for k, v in local.items():
        target = ENV_ALIASES.get(k, k.lower().replace("-", "_"))
        if target not in valid or v in (None, "", "None"):
            continue
        out[target] = v
    return out


def get_local_args():
    """
    Retrieve local arguments from a JSON file.

    Returns:
        dict: Local arguments.
    """
    if not os.path.exists("/local_model_args.json"):
        return {}

    with open("/local_model_args.json", "r") as f:
        local_args = json.load(f)

    if local_args.get("MODEL_NAME") is None:
        logging.warning(
            "Model name not found in /local_model_args.json. There maybe was a problem when baking the model in."
        )

    logging.info(f"Using baked in model with args: {local_args}")
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_OFFLINE"] = "1"

    return local_args


def get_engine_args():
    # Start with worker custom defaults (only where we differ from vLLM)
    args = dict(DEFAULT_ARGS)

    # Auto-discover: every AsyncEngineArgs field from env UPPERCASED (e.g. MAX_MODEL_LEN)
    args.update(_get_args_from_env_auto_discover())

    # Backward-compat aliases (MODEL_NAME → model, etc.)
    _apply_env_aliases(args)

    # Local baked-in model overrides
    local = get_local_args()
    local_overrides = {}
    if local:
        local_overrides = _local_args_to_engine_args(local)
        args.update(local_overrides)

    # Filter to valid engine args and drop sentinel empty values
    valid_fields = AsyncEngineArgs.__dataclass_fields__
    args = {
        k: v
        for k, v in args.items()
        if k in valid_fields and v not in (None, "", "None")
    }

    model_name = str(args.get("model", ""))
    profile_defaults = _compute_profile_defaults(model_name)
    profile_env_map = {
        "max_model_len": "MAX_MODEL_LEN",
        "max_num_batched_tokens": "MAX_NUM_BATCHED_TOKENS",
        "max_num_seqs": "MAX_NUM_SEQS",
        "gpu_memory_utilization": "GPU_MEMORY_UTILIZATION",
        "enforce_eager": "ENFORCE_EAGER",
        "language_model_only": "LANGUAGE_MODEL_ONLY",
        "enable_chunked_prefill": "ENABLE_CHUNKED_PREFILL",
    }
    profile_zero_is_unset = {
        "max_model_len": True,
        "max_num_batched_tokens": True,
    }
    for key, value in profile_defaults.items():
        if key not in valid_fields:
            logging.info(
                "Skipping profile default %s because current vLLM AsyncEngineArgs does not expose this field.",
                key,
            )
            continue
        if key in local_overrides:
            continue
        env_key = profile_env_map.get(key)
        if env_key is None:
            continue
        if _env_has_explicit_value(
            env_key,
            zero_means_unset=profile_zero_is_unset.get(key, False),
        ):
            continue
        args[key] = value

    _ensure_qwen3_5_runtime_compat(args, valid_fields)

    # Special conversion for limit_mm_per_prompt (e.g. "image=1,video=0")
    limit_mm_env = os.getenv("LIMIT_MM_PER_PROMPT")
    if limit_mm_env is not None:
        args["limit_mm_per_prompt"] = convert_limit_mm_per_prompt(limit_mm_env)

    # if args.get("TENSORIZER_URI"): TODO: add back once tensorizer is ready
    #     args["load_format"] = "tensorizer"
    #     args["model_loader_extra_config"] = TensorizerConfig(tensorizer_uri=args["TENSORIZER_URI"], num_readers=None)
    #     logging.info(f"Using tensorized model from {args['TENSORIZER_URI']}")

    if args.get("load_format") == "bitsandbytes":
        args["quantization"] = args["load_format"]

    device_env_is_explicit = _device_env_is_explicit()
    cuda_runtime_available, num_gpus, cuda_probe_reason = _detect_cuda_runtime()

    if not device_env_is_explicit and not cuda_runtime_available:
        args["device"] = "cpu"
        logging.info(
            "CUDA runtime unavailable (%s); setting device='cpu' because DEVICE was not explicitly set.",
            cuda_probe_reason,
        )

    # Set tensor parallel size and max parallel loading workers if more than 1 GPU is available
    if num_gpus > 1 and cuda_runtime_available and args.get("device") != "cpu":
        args["tensor_parallel_size"] = num_gpus
        args["max_parallel_loading_workers"] = None
        if os.getenv("MAX_PARALLEL_LOADING_WORKERS"):
            logging.warning(
                "Overriding MAX_PARALLEL_LOADING_WORKERS with None because more than 1 GPU is available."
            )

    # Deprecated env args backwards compatibility
    if args.get("kv_cache_dtype") == "fp8_e5m2":
        args["kv_cache_dtype"] = "fp8"
        logging.warning("Using fp8_e5m2 is deprecated. Please use fp8 instead.")
    max_context_len_to_capture = os.getenv("MAX_CONTEXT_LEN_TO_CAPTURE")
    if max_context_len_to_capture:
        args["max_seq_len_to_capture"] = int(max_context_len_to_capture)
        logging.warning(
            "Using MAX_CONTEXT_LEN_TO_CAPTURE is deprecated. Please use MAX_SEQ_LEN_TO_CAPTURE instead."
        )

    # if "gemma-2" in args.get("model", "").lower():
    #     os.environ["VLLM_ATTENTION_BACKEND"] = "FLASHINFER"
    #     logging.info("Using FLASHINFER for gemma-2 model.")

    # Set max_num_batched_tokens to max_model_len for unlimited batching.
    # vLLM defaults max_num_batched_tokens to 2048 when None, which is too low.

    if args.get("max_model_len") == 0:
        args["max_model_len"] = None

    if args.get("max_num_batched_tokens") == 0:
        args["max_num_batched_tokens"] = None

    # RunPod forms may send 0 for optional numeric fields where unset is required.
    _normalize_known_bad_zero_overrides(args)

    max_model_len = args.get("max_model_len")
    explicit_max_model_len = os.getenv("MAX_MODEL_LEN") not in (
        None,
        "",
        "None",
        "none",
        "0",
    )
    resolved_model_max_model_len = None
    if not explicit_max_model_len or max_model_len is None:
        resolved_model_max_model_len = _resolve_max_model_len(
            args.get("model"),
            trust_remote_code=args.get("trust_remote_code", False),
            revision=args.get("revision"),
        )

    if max_model_len is None:
        max_model_len = resolved_model_max_model_len
        if max_model_len is not None:
            args["max_model_len"] = max_model_len
    elif (
        not explicit_max_model_len
        and resolved_model_max_model_len is not None
        and max_model_len > resolved_model_max_model_len
    ):
        logging.info(
            "Safety override: clamped computed max_model_len from %d to model config max %d",
            max_model_len,
            resolved_model_max_model_len,
        )
        max_model_len = resolved_model_max_model_len
        args["max_model_len"] = max_model_len

    if max_model_len is not None:
        model_len_cap = _get_safe_max_model_len_cap()
        if max_model_len > model_len_cap:
            if _env_is_true("ALLOW_UNSAFE_MAX_MODEL_LEN"):
                logging.warning(
                    "Unsafe override allowed: keeping max_model_len=%d above SAFE_MAX_MODEL_LEN_CAP=%d",
                    max_model_len,
                    model_len_cap,
                )
            else:
                if explicit_max_model_len:
                    logging.info(
                        "Safety override: capped explicit MAX_MODEL_LEN from %d to %d via SAFE_MAX_MODEL_LEN_CAP",
                        max_model_len,
                        model_len_cap,
                    )
                else:
                    logging.info(
                        "Safety override: capped auto max_model_len from %d to %d via SAFE_MAX_MODEL_LEN_CAP",
                        max_model_len,
                        model_len_cap,
                    )
                max_model_len = model_len_cap
                args["max_model_len"] = model_len_cap

    if _is_qwen3_5_model(model_name):
        requested_max_model_len = None
        raw_requested_max_model_len = os.getenv("MAX_MODEL_LEN")
        if raw_requested_max_model_len not in (None, "", "None", "none", "0"):
            try:
                requested_max_model_len = int(raw_requested_max_model_len)
            except ValueError:
                requested_max_model_len = None

        if (
            requested_max_model_len is not None
            and requested_max_model_len >= QWEN35_QUALITY_CONTEXT_TARGET
            and max_model_len is not None
            and max_model_len < QWEN35_QUALITY_CONTEXT_TARGET
        ):
            logging.warning(
                "Qwen3.5 quality guidance: requested MAX_MODEL_LEN=%d but effective max_model_len=%d; check SAFE_MAX_MODEL_LEN_CAP/model config caps.",
                requested_max_model_len,
                max_model_len,
            )

        if max_model_len is None or max_model_len < QWEN35_QUALITY_CONTEXT_TARGET:
            logging.warning(
                "Qwen3.5 quality guidance: MAX_MODEL_LEN=%s is below recommended 131072 for 128k context quality-first mode.",
                max_model_len,
            )

    explicit_max_num_batched_tokens = os.getenv("MAX_NUM_BATCHED_TOKENS") not in (
        None,
        "",
        "None",
        "none",
        "0",
    )
    max_num_batched_tokens = args.get("max_num_batched_tokens")
    if max_num_batched_tokens is not None and not explicit_max_num_batched_tokens:
        batched_tokens_cap = _get_safe_max_num_batched_tokens_cap()
        if max_num_batched_tokens > batched_tokens_cap:
            logging.info(
                "Safety override: capped computed max_num_batched_tokens from %d to %d via SAFE_MAX_NUM_BATCHED_TOKENS_CAP",
                max_num_batched_tokens,
                batched_tokens_cap,
            )
            args["max_num_batched_tokens"] = batched_tokens_cap

    if args.get("max_num_batched_tokens") is None and max_model_len is not None:
        cap = _get_safe_max_num_batched_tokens_cap()
        safe_batched_tokens = min(max_model_len, cap)
        args["max_num_batched_tokens"] = safe_batched_tokens
        if safe_batched_tokens < max_model_len:
            logging.info(
                "Safety override: capped auto max_num_batched_tokens from %d to %d via SAFE_MAX_NUM_BATCHED_TOKENS_CAP",
                max_model_len,
                safe_batched_tokens,
            )
        else:
            logging.info(f"Setting max_num_batched_tokens to {safe_batched_tokens}")

    if (
        max_model_len is not None
        and max_model_len > LARGE_CONTEXT_CHUNKED_PREFILL_THRESHOLD
        and args.get("enable_chunked_prefill") is False
    ):
        if _env_is_true("ALLOW_UNSAFE_DISABLE_CHUNKED_PREFILL"):
            logging.warning(
                "Unsafe override allowed: keeping enable_chunked_prefill=False for max_model_len=%d",
                max_model_len,
            )
        else:
            args["enable_chunked_prefill"] = True
            logging.info(
                "Safety override: forced enable_chunked_prefill=True for large context max_model_len=%d",
                max_model_len,
            )

    # VLLM_ATTENTION_BACKEND is deprecated, migrate to attention_backend
    if os.getenv("VLLM_ATTENTION_BACKEND"):
        logging.warning(
            "VLLM_ATTENTION_BACKEND env var is deprecated. "
            "Use ATTENTION_BACKEND instead (maps to --attention-backend CLI arg)."
        )
        if not args.get("attention_backend"):
            args["attention_backend"] = os.getenv("VLLM_ATTENTION_BACKEND")

    # DISABLE_LOG_REQUESTS is deprecated, use ENABLE_LOG_REQUESTS instead
    if os.getenv("DISABLE_LOG_REQUESTS"):
        logging.warning(
            "DISABLE_LOG_REQUESTS env var is deprecated. "
            "Use ENABLE_LOG_REQUESTS instead (default: False)."
        )
        # Honor old behavior: if DISABLE_LOG_REQUESTS=true, don't enable logging
        if os.getenv("DISABLE_LOG_REQUESTS", "False").lower() == "true":
            args["enable_log_requests"] = False

    # Add speculative decoding configuration if present
    speculative_config = get_speculative_config()
    if speculative_config:
        args["speculative_config"] = speculative_config

    return AsyncEngineArgs(**args)

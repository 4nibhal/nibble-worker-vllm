import multiprocessing
import sys
import traceback
from pathlib import Path

import runpod
from runpod import RunPodLogger

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

log = RunPodLogger()

vllm_engine = None
openai_engine = None


async def handler(job):
    try:
        from utils import JobInput

        job_input = JobInput(job["input"])
        engine = openai_engine if job_input.openai_route else vllm_engine
        results_generator = engine.generate(job_input)
        async for batch in results_generator:
            yield batch
    except Exception as exc:
        error_str = str(exc)
        full_traceback = traceback.format_exc()

        log.error(f"Error during inference: {error_str}")
        log.error(f"Full traceback:\n{full_traceback}")

        if "CUDA" in error_str or "cuda" in error_str:
            log.error("Terminating worker due to CUDA/GPU error")
            sys.exit(1)

        yield {"error": error_str}


if __name__ == "__main__" or multiprocessing.current_process().name == "MainProcess":
    try:
        from engine import OpenAIvLLMEngine, vLLMEngine

        vllm_engine = vLLMEngine()
        openai_engine = OpenAIvLLMEngine(vllm_engine)
        log.info("vLLM engines initialized successfully")
    except Exception as exc:
        log.error(f"Worker startup failed: {exc}\n{traceback.format_exc()}")
        sys.exit(1)

    runpod.serverless.start(
        {
            "handler": handler,
            "concurrency_modifier": lambda _: (
                vllm_engine.max_concurrency if vllm_engine else 1
            ),
            "return_aggregate_stream": True,
        }
    )

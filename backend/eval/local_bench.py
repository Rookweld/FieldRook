"""M017 local-inference benchmark: repeatable CPU-first measurements.

Measures already-installed Ollama models over the SAME task prompts the
local provider uses in production (triage / plan / reassess / synthesize),
so numbers describe the real reasoning path, not a synthetic micro-task.

Usage:
    python eval/local_bench.py [--models qwen3:4b ...] [--tasks triage,plan]
        [--cold] [--out DIR] [--timeout-s N]

What is measured per (model, task):
- wall latency (cold = first call after unload; warm = steady state)
- output chars + valid-JSON verdict + schema verdict (required keys present)
- token counts and tok/s where the server reports them (/api/chat probes)
- model memory footprint via /api/ps while loaded
- host CPU model, RAM, and Ollama CPU% sampled around generation

Nothing is downloaded, installed, or deleted. All requests stay on
loopback. Quality grading is structural here; qualitative grades live in
docs/LOCAL_AI.md with saved transcripts under eval/results/local-bench/.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OLLAMA = "http://127.0.0.1:11434"

TASKS: dict[str, dict] = {
    "triage": {
        "num_predict": 220,
        "timeout": 120,
        "prompt": (
            "You are FieldRook, a Windows troubleshooting assistant. Reply with ONLY "
            "this JSON object, no other text: {\"question\": \"<one clarifying question>\", "
            "\"why\": \"<why the answer changes the diagnosis>\", \"hypotheses\": "
            "[{\"title\": \"<possible cause>\", \"why\": \"<one line>\"}], \"next_check\": "
            "\"<one safe read-only check>\", \"unknowns\": [\"<what is still unknown>\"]}. "
            "At most 2 hypotheses and 2 unknowns. "
            "Problem: Excel will not open files from Teams on the user's laptop. "
            "Local Excel files open normally. No diagnostic tools have run yet."
        ),
        "required_keys": ["question", "why", "hypotheses", "next_check", "unknowns"],
    },
    "plan": {
        "num_predict": 380,
        "timeout": 180,
        "prompt": (
            "You are FieldRook, a Windows troubleshooting assistant. Reply with ONLY "
            "this JSON object, no other text: {\"steps\": [{\"instruction\": \"<what to do>\", "
            "\"why\": \"<why it matters>\", \"kind\": \"<TECHNICIAN_CHECK or "
            "CLARIFYING_QUESTION or EXTERNAL_SYSTEM_CHECK>\", \"expect\": \"<what "
            "different results would mean>\"}]}. At most 4 steps. "
            "Problem: Excel will not open files from Teams on the user's laptop. "
            "Known: local files open fine; the affected machine is a different "
            "computer, so no host measurements apply."
        ),
        "required_keys": ["steps"],
    },
    "reassess": {
        "num_predict": 220,
        "timeout": 120,
        "prompt": (
            "You are FieldRook, a Windows troubleshooting assistant. Reply with ONLY "
            "this JSON object, no other text: {\"verdict\": \"<one sentence: what the new "
            "observation means>\", \"weakened\": [\"<hypothesis titles now less likely>\"], "
            "\"next_step\": \"<the single most useful next check or question>\"}. "
            "Open hypotheses: [\"Teams file-access or permissions problem\", "
            "\"Damaged Excel installation\"]. "
            "New technician observation: local Excel files open normally."
        ),
        "required_keys": ["verdict", "weakened", "next_step"],
    },
    "synthesize": {
        "num_predict": 900,
        "timeout": 300,
        "prompt": (
            "You are FieldRook, a Windows troubleshooting assistant. Reply with ONLY "
            "this JSON object, no other text: {\"summary\": \"<2 sentences>\", "
            "\"understanding\": \"<reported vs observed>\", \"causes\": [{\"title\": ..., "
            "\"description\": ..., \"likelihood\": \"<high|medium|low>\"}], "
            "\"uncertainties\": [...], \"missing_evidence\": [...], "
            "\"questions\": [{\"question\": ..., \"why\": ...}]}. "
            "Problem: Excel will not open files from Teams on the user's laptop. "
            "Evidence: technician reports local files open fine (reported, not "
            "measured). Target: another computer; no host measurements apply."
        ),
        "required_keys": ["summary", "understanding", "causes", "uncertainties"],
    },
}


def _post(path: str, payload: dict, timeout: float) -> tuple[float, dict]:
    req = urllib.request.Request(
        OLLAMA + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return time.monotonic() - start, json.loads(response.read())
    except TimeoutError:
        return time.monotonic() - start, {"_timeout": True}
    except Exception as exc:  # noqa: BLE001 - bench must record, not crash
        return time.monotonic() - start, {"_error": f"{type(exc).__name__}: {exc}"}


def _get(path: str, timeout: float = 15.0) -> dict:
    with urllib.request.urlopen(OLLAMA + path, timeout=timeout) as response:
        return json.loads(response.read())


def unload_all() -> None:
    try:
        for entry in _get("/api/ps").get("models", []):
            _post("/api/generate", {"model": entry["name"], "keep_alive": 0}, 30.0)
    except Exception:  # noqa: BLE001 - best effort
        pass


def ollama_cpu_percent() -> float | None:
    """Coarse Ollama CPU% via Windows performance counters (best effort)."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_PerfFormattedData_PerfProc_Process "
             "-Filter \"Name LIKE 'ollama%'\" | Select-Object -ExpandProperty PercentProcessorTime"],
            capture_output=True, text=True, timeout=30,
        )
        values = [float(line) for line in out.stdout.splitlines() if line.strip().replace(".", "", 1).isdigit()]
        return round(sum(values), 1) if values else None
    except Exception:  # noqa: BLE001 - best effort
        return None


def loaded_model_size(model: str) -> int | None:
    try:
        for entry in _get("/api/ps").get("models", []):
            if entry.get("name") == model or entry.get("model") == model:
                return entry.get("size")
    except Exception:  # noqa: BLE001 - best effort
        pass
    return None


def loaded_model_processor(model: str) -> str:
    """GPU vs CPU placement from /api/ps (M018: never assume CPU-only)."""
    try:
        for entry in _get("/api/ps").get("models", []):
            if entry.get("name") == model or entry.get("model") == model:
                size = entry.get("size") or 0
                vram = entry.get("size_vram") or 0
                if size and vram >= size:
                    return "gpu"
                if vram:
                    return "split"
                return "cpu"
    except Exception:  # noqa: BLE001 - best effort
        pass
    return "unknown"


def host_info() -> dict:
    info: dict = {"platform": sys.platform}
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Processor).Name + '|' + "
             "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory + '|' + "
             "$env:NUMBER_OF_PROCESSORS"],
            capture_output=True, text=True, timeout=30,
        )
        parts = out.stdout.strip().split("|")
        info["cpu"] = parts[0].strip() if len(parts) > 0 else "?"
        info["ram_gb"] = round(int(parts[1]) / 1e9, 1) if len(parts) > 1 else 0
        info["logical_cpus"] = parts[2].strip() if len(parts) > 2 else "?"
    except Exception:  # noqa: BLE001 - best effort
        pass
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30,
        )
        info["gpu"] = out.stdout.strip().splitlines() or None
    except Exception:  # noqa: BLE001 - best effort
        info["gpu"] = None
    return info


VISION_IMAGE = Path("C:/Users/pontu/.fieldrook-tmp/m17dialog.png")
VISION_OVERRIDE: Path | None = None


def run_model(
    model: str,
    tasks: list[str],
    cold: bool,
    timeout_scale: float = 1.0,
    num_gpu: int | None = None,
) -> dict:
    """Benchmark one model through the production task path."""
    import asyncio
    import threading

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.analysis.local_tasks import TASK_LIMITS, TASK_REQUIRED_KEYS, missing_keys
    from app.config import Settings

    from app.analysis.provider import LocalEndpointProvider

    settings = Settings(
        model_api_key=None,
        model_base_url="https://api.meta.ai/v1",
        model_name="bench",
        fixtures_mode="always",
        command_timeout_s=5.0,
        model_timeout_s=300.0,
        local_model_url="http://127.0.0.1:11434/v1",
        local_model_name=model,
        local_api="auto",
        local_think="auto",
        local_num_gpu=num_gpu,
    )
    provider = LocalEndpointProvider(settings)
    if cold:
        unload_all()
        time.sleep(2.0)
    results: dict = {"model": model, "api_style": None, "tasks": {}, "requests": []}
    try:
        results["api_style"] = provider.api_style()
    except Exception as exc:  # noqa: BLE001 - recorded below
        results["fatal"] = str(exc)[:200]
        return results
    for index, task in enumerate(tasks):
        if task == "vision":
            from app.analysis.local_tasks import VISION_PROMPT

            spec = {"prompt": VISION_PROMPT, "timeout": 240, "image": True}
        else:
            spec = TASKS[task]
        timeout = spec["timeout"] * timeout_scale
        images = None
        vision_file = VISION_OVERRIDE or VISION_IMAGE
        if spec.get("image") and vision_file.exists():
            import base64 as _b64

            images = [_b64.b64encode(vision_file.read_bytes()).decode("ascii")]
        cpu_samples: list[float] = []
        stop = threading.Event()

        samples_taken = 0

        def sampler() -> None:
            nonlocal samples_taken
            while True:
                samples_taken += 1
                sample = ollama_cpu_percent()
                if sample is not None:
                    cpu_samples.append(sample)
                if stop.wait(1.0):
                    break

        thread = threading.Thread(target=sampler, daemon=True)
        thread.start()
        started = time.monotonic()
        try:
            parsed, warnings = asyncio.run(
                provider.run_task(task, spec["prompt"], timeout, images=images)
            )
        except Exception as exc:  # noqa: BLE001 - bench records, not crashes
            parsed, warnings = None, [f"harness: {type(exc).__name__}: {exc}"]
        raw_reply = None
        if parsed is None:
            # Reproduce once without repair to capture the raw failing text.
            try:
                reply = asyncio.run(
                    provider._ollama_chat(  # noqa: SLF001 - bench introspection
                        "http://127.0.0.1:11434", model,
                        [{"role": "user", "content": spec["prompt"]}],
                        True, 220, timeout,
                    )
                )
                raw_reply = str(reply.get("content") or "")[:2000]
            except Exception as exc:  # noqa: BLE001 - best effort
                raw_reply = f"<recapture failed: {exc}>"
        wall_s = round(time.monotonic() - started, 1)
        stop.set()
        thread.join(timeout=10.0)
        stats = dict(provider.last_stats)
        gaps = missing_keys(parsed, task) if parsed else list(TASK_REQUIRED_KEYS[task])
        null_keys = (
            [k for k in TASK_REQUIRED_KEYS[task] if parsed and parsed.get(k) is None]
            if parsed
            else []
        )
        # The bench vision fixture is known-readable: all-null = model could not
        # read it (a null field is honest only for genuinely unreadable images).
        blind = task == "vision" and parsed is not None and len(null_keys) == len(TASK_REQUIRED_KEYS[task])
        entry = {
            "cold": bool(cold and index == 0),
            "wall_s": wall_s,
            "valid_json": parsed is not None,
            "missing_keys": gaps,
            "null_keys": null_keys,
            "blind_vision": blind,
            "warnings": warnings,
            "stats": stats,
            "cpu_max": max(cpu_samples) if cpu_samples else None,
            "cpu_samples": samples_taken,
            "mem_bytes": loaded_model_size(model),
            "parsed": parsed,  # transcript for qualitative grading
            "raw_reply_on_failure": raw_reply,
        }
        results["tasks"][task + ("(cold)" if cold and index == 0 else "")] = entry
        results["requests"].append(
            {"model": model, "task": task, "timeout_s": timeout,
             "wall_s": wall_s, "ok": parsed is not None and not gaps and not blind}
        )
    results["processor"] = loaded_model_processor(model)
    results["num_gpu"] = num_gpu
    return results


def _print_result(result: dict) -> None:
    for name, entry in result.get("tasks", {}).items():
        stats = entry.get("stats") or {}
        toks = stats.get("eval_count")
        tps = (
            f"{toks / stats['eval_duration_s']:.1f} tok/s"
            if toks and stats.get("eval_duration_s")
            else "-"
        )
        mem = entry.get("mem_bytes")
        mem_s = f"{mem / 1e9:.1f}GB" if mem else "-"
        blind = " BLIND" if entry.get("blind_vision") else ""
        ttft = stats.get("first_token_s")
        ttft_s = f" ttft={ttft:5.1f}s" if ttft is not None else ""
        print(
            f"  {name:18} wall={entry['wall_s']:6.1f}s valid={entry['valid_json']!s:5} "
            f"gaps={entry['missing_keys'] or '-'} nulls={entry.get('null_keys') or '-'}{blind} "
            f"{tps:>12} mem={mem_s:>7} cpu_max={entry.get('cpu_max')}{ttft_s}",
            flush=True,
        )
        for warning in entry.get("warnings", []):
            print(f"    ! {warning}")


def main() -> int:
    parser = argparse.ArgumentParser(description="FieldRook local-inference benchmark")
    parser.add_argument("--models", nargs="*", default=["qwen3:4b", "qwen3-vl:8b"])
    parser.add_argument("--all", action="store_true", help="add gemma4:e4b and qwen3-coder:30b")
    parser.add_argument("--tasks", default="triage,plan,reassess,synthesize")
    parser.add_argument("--cold", action="store_true", help="unload before each model (first task is cold)")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "results" / "local-bench"))
    parser.add_argument("--timeout-scale", type=float, default=1.0)
    parser.add_argument("--repeat", type=int, default=1, help="run the task list N times per model (variance)")
    parser.add_argument("--num-gpu", type=int, default=None, help="force GPU layer count (0 = CPU-only)")
    parser.add_argument("--vision-image", default=None, help="override the vision fixture image")
    args = parser.parse_args()
    models = list(args.models)
    if args.all:
        for extra in ("gemma4:e4b", "qwen3-coder:30b"):
            if extra not in models:
                models.append(extra)
    tasks = [t.strip() for t in args.tasks.split(",") if t.strip() in (*TASKS, "vision")]
    if not tasks:
        print("no valid tasks selected")
        return 2
    if args.vision_image:
        globals()["VISION_OVERRIDE"] = Path(args.vision_image)
    host = host_info()
    print(f"host: {host.get('cpu')} | RAM {host.get('ram_gb')}GB | {host.get('logical_cpus')} logical CPUs")
    all_results: list[dict] = []
    for model in models:
        print(f"\n=== {model} ===", flush=True)
        reps = max(1, args.repeat)
        for rep in range(reps):
            # Only the first pass can be cold; repeats measure warm variance.
            result = run_model(model, tasks, args.cold and rep == 0, args.timeout_scale, args.num_gpu)
            result["rep"] = rep + 1
            all_results.append(result)
            if reps > 1:
                print(f"--- rep {rep + 1}/{reps} ---", flush=True)
            _print_result(result)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"bench-{stamp}.json"
    out_path.write_text(
        json.dumps({"created_at": stamp, "host": host, "results": all_results}, indent=2),
        encoding="utf-8",
    )
    print(f"\nresults: {out_path}")
    print(f"total local-model requests this run: {sum(len(r.get('requests', [])) for r in all_results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


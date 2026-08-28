#!/usr/bin/env python3
"""
Run a cycles-test binary and plot per-instance timing fields vs instance number.

Usage (from project root):
    python3 cycles_test/plot_cycles.py [binary] [--fields FIELD ...] [--runs N] [--output FILE]

Examples:
    # Plot all per-instance fields from time_test (default)
    python3 cycles_test/plot_cycles.py

    # Plot only instantiate and function-call time
    python3 cycles_test/plot_cycles.py cycles_test/time_test --fields instantiate call

    # Average over 5 runs
    python3 cycles_test/plot_cycles.py cycles_test/time_test --runs 5

    # Save to file instead of showing interactively
    python3 cycles_test/plot_cycles.py cycles_test/time_test --output out.png

    # Add one-time phase reference lines (horizontal)
    python3 cycles_test/plot_cycles.py cycles_test/time_test --onetime compile imports

Available per-instance field names (case-insensitive prefix match):
    instantiate, init_env, cast_export, call

Available one-time field names (shown as horizontal reference lines with --onetime):
    file_load, engine_store, compile, imports, find_export, prepare_args
"""

import argparse
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:
    sys.exit("Missing dependencies. Run: pip install matplotlib numpy")

# ── parsing helpers ────────────────────────────────────────────────────────────

# Labels exactly as printed by print_cycles_log()
ONE_TIME_LABELS = {
    "file_load":     "File Load:",
    "engine_store":  "Engine & Store:",
    "compile":       "Compile:",
    "imports":       "Imports:",
    "find_export":   "Find Export Func Index:",
    "prepare_args":  "Prepare Args:",
}

INSTANCE_LABELS = {
    "instantiate":  "Instantiate:",
    "init_env":     "Initialize Environment:",
    "cast_export":  "Cast Export To Func:",
    "call":         "Function Call:",
}

# Friendly display names for the legend
DISPLAY_NAMES = {
    "instantiate":  "Instantiate",
    "init_env":     "Init Environment",
    "cast_export":  "Cast Export → Func",
    "call":         "Function Call",
    "file_load":    "File Load",
    "engine_store": "Engine & Store",
    "compile":      "Compile",
    "imports":      "Imports",
    "find_export":  "Find Export Index",
    "prepare_args": "Prepare Args",
}


def _us_value(line: str) -> float:
    """Extract the µs float from a line like '    Instantiate: 58.27 us'."""
    m = re.search(r"([\d.]+)\s*us", line)
    if not m:
        raise ValueError(f"Cannot parse us value from: {line!r}")
    return float(m.group(1))


def parse_output(text: str):
    """
    Parse one run of a cycles-test binary's stdout.

    Returns:
        one_time  : dict[key → float µs]
        instances : list[dict[key → float µs]]  (one entry per Instance N)
    """
    one_time: dict[str, float] = {}
    instances: list[dict[str, float]] = []
    current_instance: dict[str, float] | None = None

    for line in text.splitlines():
        stripped = line.strip()

        # ── one-time fields ──────────────────────────────────────────────────
        for key, label in ONE_TIME_LABELS.items():
            if stripped.startswith(label):
                one_time[key] = _us_value(stripped)
                break

        # ── instance block boundaries ────────────────────────────────────────
        if re.match(r"Instance \d+:", stripped):
            if current_instance is not None:
                instances.append(current_instance)
            current_instance = {}
            continue

        # ── per-instance fields ──────────────────────────────────────────────
        if current_instance is not None:
            for key, label in INSTANCE_LABELS.items():
                if stripped.startswith(label):
                    current_instance[key] = _us_value(stripped)
                    break

    if current_instance:
        instances.append(current_instance)

    return one_time, instances


def run_binary(binary: str, binary_args: list) -> str:
    # `run` is a bash alias — use bash -i so aliases are loaded from ~/.bashrc
    invocation = shlex.join([binary] + binary_args)
    cmd = ["bash", "-ic", f"run {invocation}"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(binary).parent,  # run from its own directory so relative .wasm paths work
    )
    if result.returncode != 0 and not result.stdout:
        sys.exit(f"Binary failed:\n{result.stderr}")
    return result.stdout


# ── field name resolution ─────────────────────────────────────────────────────

ALL_INSTANCE_KEYS = list(INSTANCE_LABELS)
ALL_ONE_TIME_KEYS = list(ONE_TIME_LABELS)


def resolve_fields(requested: list[str], pool: list[str]) -> list[str]:
    """Case-insensitive prefix matching against pool."""
    resolved = []
    for req in requested:
        req_lower = req.lower()
        matches = [k for k in pool if k.startswith(req_lower)]
        if not matches:
            sys.exit(f"Unknown field '{req}'. Available: {', '.join(pool)}")
        if len(matches) > 1:
            sys.exit(f"Ambiguous field '{req}' matches: {', '.join(matches)}")
        resolved.append(matches[0])
    return resolved


# ── plotting ──────────────────────────────────────────────────────────────────

def plot(
    all_runs_instances: list[list[dict]],
    instance_fields: list[str],
    one_time_data: dict[str, float],
    onetime_fields: list[str],
    title: str,
    output: str | None,
):
    n_instances = len(all_runs_instances[0])
    x = np.arange(1, n_instances + 1)

    fig, ax = plt.subplots(figsize=(max(8, n_instances), 5))

    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    color_cycle = iter(colors)

    for field in instance_fields:
        # Average across runs
        values = np.array([
            [run[i].get(field, 0.0) for i in range(n_instances)]
            for run in all_runs_instances
        ])  # shape: (n_runs, n_instances)
        mean = values.mean(axis=0)
        color = next(color_cycle)
        label = DISPLAY_NAMES.get(field, field)

        if len(all_runs_instances) > 1:
            std = values.std(axis=0)
            ax.plot(x, mean, marker="o", label=label, color=color)
            ax.fill_between(x, mean - std, mean + std, alpha=0.2, color=color)
        else:
            ax.plot(x, mean, marker="o", label=label, color=color)

    # One-time reference lines
    for field in onetime_fields:
        val = one_time_data.get(field)
        if val is not None:
            color = next(color_cycle)
            ax.axhline(val, linestyle="--", color=color, alpha=0.7,
                       label=f"{DISPLAY_NAMES.get(field, field)} (one-time: {val:.2f} µs)")

    ax.set_xlabel("Instance #")
    ax.set_ylabel("Time (µs)")
    ax.set_title(title)
    ax.set_xticks(x)
    ax.legend(loc="upper right")
    ax.grid(True, linestyle=":", alpha=0.5)
    plt.tight_layout()

    if output:
        plt.savefig(output, dpi=150)
        print(f"Saved to {output}")
    else:
        plt.show()


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    # ── time_test parameters (edit these to change defaults) ──────────────────
    DEFAULT_MAIN_ITER     = 1    # -m: outer iterations averaged inside the binary
    DEFAULT_CALL_ITER     = 1    # -c: call iterations per instance
    DEFAULT_NUM_INSTANCES = 20   # -n: number of instances to create
    # ─────────────────────────────────────────────────────────────────────────

    parser = argparse.ArgumentParser(
        description="Run a cycles-test binary and plot per-instance timing fields.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "binary",
        nargs="?",
        default="cycles_test/time_test",
        help="Path to the test binary (default: cycles_test/time_test)",
    )
    parser.add_argument(
        "--fields", "-f",
        nargs="+",
        default=ALL_INSTANCE_KEYS,
        metavar="FIELD",
        help=f"Per-instance fields to plot. Available: {', '.join(ALL_INSTANCE_KEYS)}",
    )
    parser.add_argument(
        "--onetime", "-t",
        nargs="*",
        default=[],
        metavar="FIELD",
        help=(
            "One-time fields to draw as horizontal reference lines. "
            f"Available: {', '.join(ALL_ONE_TIME_KEYS)}"
        ),
    )
    parser.add_argument(
        "--runs", "-r",
        type=int, default=1, metavar="N",
        help="Number of times to run the binary and average results (default: 1)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None, metavar="FILE",
        help="Override output path (default: instances_plots/<datetime>.png)",
    )
    parser.add_argument(
        "--main-iter", "-m",
        type=int, default=DEFAULT_MAIN_ITER, metavar="N",
        help=f"Binary -m: outer iterations (default: {DEFAULT_MAIN_ITER})",
    )
    parser.add_argument(
        "--call-iter", "-c",
        type=int, default=DEFAULT_CALL_ITER, metavar="N",
        help=f"Binary -c: call iterations per instance (default: {DEFAULT_CALL_ITER})",
    )
    parser.add_argument(
        "--num-instances", "-n",
        type=int, default=DEFAULT_NUM_INSTANCES, metavar="N",
        help=f"Binary -n: number of instances (default: {DEFAULT_NUM_INSTANCES})",
    )
    args = parser.parse_args()

    binary = str(Path(args.binary).resolve())
    if not Path(binary).is_file():
        sys.exit(f"Binary not found: {binary}")

    binary_args = ["-m", str(args.main_iter), "-c", str(args.call_iter), "-n", str(args.num_instances)]

    instance_fields = resolve_fields(args.fields, ALL_INSTANCE_KEYS)
    onetime_fields = resolve_fields(args.onetime, ALL_ONE_TIME_KEYS) if args.onetime else []

    if args.output:
        out_path = args.output
    else:
        out_dir = Path(__file__).parent / "instances_plots"
        out_dir.mkdir(exist_ok=True)
        out_path = str(out_dir / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png")

    print(f"Running '{args.binary}' x{args.runs} (m={args.main_iter} c={args.call_iter} n={args.num_instances})...")
    all_runs_instances = []
    last_one_time: dict[str, float] = {}

    for i in range(args.runs):
        output = run_binary(binary, binary_args)
        one_time, instances = parse_output(output)
        if not instances:
            sys.exit("Could not parse any instance data from binary output.")
        all_runs_instances.append(instances)
        last_one_time = one_time
        print(f"  run {i+1}/{args.runs}: {len(instances)} instances parsed")

    title = (
        f"{Path(args.binary).name} — per-instance timing"
        f"  [m={args.main_iter}, c={args.call_iter}]"
        + (f"  (avg over {args.runs} script-runs)" if args.runs > 1 else "")
    )

    plot(
        all_runs_instances,
        instance_fields,
        last_one_time,
        onetime_fields,
        title,
        out_path,
    )


if __name__ == "__main__":
    main()

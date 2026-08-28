#!/usr/bin/env python3
"""
Run a cycles-test binary and plot Wasmer internal PERF steps vs instance number.

Parses [PERF] instnt/call lines emitted by wasmer_perf_dump() — one block per instance.

Usage (from project root):
    python3 cycles_test/plot_perf.py [binary] [--category instnt|call|all] [--runs N] [--output FILE]

Examples:
    python3 cycles_test/plot_perf.py
    python3 cycles_test/plot_perf.py cycles_test/time_test --category call
    python3 cycles_test/plot_perf.py --runs 5
    python3 cycles_test/plot_perf.py --output my_plot.png
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

# Matches lines emitted by wasmer_perf_dump():
#   [PERF] instnt S1 import_resolve    begin= ...  end= ...  delta= 3360 cyc  (1.400 us)
_PERF_RE = re.compile(
    r'^\[PERF\]\s+(instnt|call)\s+(.*?)\s+begin=\s+\d+\s+end=\s+\d+\s+delta=\s+\d+\s+cyc\s+\((\d+\.\d+)\s+us\)'
)


def _normalize_step(category: str, raw_name: str) -> str:
    """Collapse stack(new)/stack(pool) → stack so all instances share one line."""
    name = re.sub(r'stack\(.*?\)', 'stack', raw_name.strip())
    return f"{category} {name}"


def parse_output(text: str):
    """
    Parse wasmer_perf_dump() blocks from binary stdout.

    Returns a list of instance-dicts: [ {step_key: us, ...}, ... ]
    One dict per instance (each consecutive block of matching PERF lines).
    """
    instances: list[dict[str, float]] = []
    current: dict[str, float] = {}

    for line in text.splitlines():
        m = _PERF_RE.match(line.strip())
        if m:
            category, raw_name, us_str = m.group(1), m.group(2), m.group(3)
            key = _normalize_step(category, raw_name)
            current[key] = current.get(key, 0.0) + float(us_str)
        else:
            if current:
                instances.append(current)
                current = {}

    if current:
        instances.append(current)

    return instances


def run_binary(binary: str, binary_args: list) -> str:
    invocation = shlex.join([binary] + binary_args)
    cmd = ["bash", "-ic", f"run {invocation}"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(binary).parent,
    )
    if result.returncode != 0 and not result.stdout:
        sys.exit(f"Binary failed:\n{result.stderr}")
    return result.stdout


def plot(
    all_runs: list[list[dict]],
    category_filter: str,
    title: str,
    output: str,
):
    n_instances = len(all_runs[0])
    x = np.arange(1, n_instances + 1)

    # Collect all step keys across runs, split by category
    all_keys: list[str] = []
    seen = set()
    for run in all_runs:
        for inst in run:
            for k in inst:
                if k not in seen:
                    seen.add(k)
                    all_keys.append(k)

    instnt_keys = [k for k in all_keys if k.startswith("instnt")]
    call_keys   = [k for k in all_keys if k.startswith("call")]

    if category_filter == "instnt":
        groups = [("Instantiation steps", instnt_keys)]
    elif category_filter == "call":
        groups = [("Call steps", call_keys)]
    else:
        groups = [("Instantiation steps", instnt_keys), ("Call steps", call_keys)]

    n_plots = len(groups)
    fig, axes = plt.subplots(n_plots, 1, figsize=(max(10, n_instances), 4.5 * n_plots), squeeze=False)
    fig.suptitle(title, fontsize=12)

    for ax, (subtitle, keys) in zip(axes[:, 0], groups):
        # tab20 gives 20 distinct colors; cycle for safety if more steps exist
        cmap = plt.get_cmap("tab20")
        color_iter = iter(cmap(i / max(len(keys), 1)) for i in range(len(keys)))

        for key in keys:
            label = key.split(" ", 1)[1]   # strip "instnt "/" "call " prefix for legend
            values = np.array([
                [run[i].get(key, 0.0) for i in range(n_instances)]
                for run in all_runs
            ])
            mean = values.mean(axis=0)
            color = next(color_iter)

            ax.plot(x, mean, marker="o", label=label, color=color)
            if len(all_runs) > 1:
                std = values.std(axis=0)
                ax.fill_between(x, mean - std, mean + std, alpha=0.15, color=color)

        ax.set_title(subtitle)
        ax.set_xlabel("Instance #")
        ax.set_ylabel("Time (µs)")
        ax.set_xticks(x)
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(True, linestyle=":", alpha=0.5)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    print(f"Saved to {output}")


def main():
    # ── time_test parameters (edit these to change defaults) ──────────────────
    DEFAULT_MAIN_ITER     = 5    # -m: outer iterations; PERF blocks are averaged across them
    DEFAULT_CALL_ITER     = 1    # -c: call iterations per instance
    DEFAULT_NUM_INSTANCES = 20   # -n: number of instances to create
    # ─────────────────────────────────────────────────────────────────────────

    parser = argparse.ArgumentParser(
        description="Plot Wasmer internal PERF steps vs instance number.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("binary", nargs="?", default="cycles_test/time_test",
                        help="Path to test binary (default: cycles_test/time_test)")
    parser.add_argument("--category", "-g", choices=["instnt", "call", "all"], default="all",
                        help="Which category of steps to plot (default: all)")
    parser.add_argument("--runs", "-r", type=int, default=1, metavar="N",
                        help="Number of binary runs to average (default: 1)")
    parser.add_argument("--output", "-o", default=None, metavar="FILE",
                        help="Override output path (default: instantiate_plots/<datetime>.png)")
    parser.add_argument("--main-iter", "-m", type=int, default=DEFAULT_MAIN_ITER, metavar="N",
                        help=f"Binary -m: outer iterations (default: {DEFAULT_MAIN_ITER})")
    parser.add_argument("--call-iter", "-c", type=int, default=DEFAULT_CALL_ITER, metavar="N",
                        help=f"Binary -c: call iterations per instance (default: {DEFAULT_CALL_ITER})")
    parser.add_argument("--num-instances", "-n", type=int, default=DEFAULT_NUM_INSTANCES, metavar="N",
                        help=f"Binary -n: number of instances (default: {DEFAULT_NUM_INSTANCES})")
    args = parser.parse_args()

    binary = str(Path(args.binary).resolve())
    if not Path(binary).is_file():
        sys.exit(f"Binary not found: {binary}")

    binary_args = ["-m", str(args.main_iter), "-c", str(args.call_iter), "-n", str(args.num_instances)]

    if args.output:
        out_path = args.output
    else:
        out_dir = Path(__file__).parent / "instantiate_plots"
        out_dir.mkdir(exist_ok=True)
        out_path = str(out_dir / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png")

    print(f"Running '{args.binary}' x{args.runs} (m={args.main_iter} c={args.call_iter} n={args.num_instances})...")
    all_runs: list[list[dict]] = []

    n = args.num_instances
    m = args.main_iter

    for i in range(args.runs):
        raw = run_binary(binary, binary_args)
        blocks = parse_output(raw)
        if not blocks:
            sys.exit("No [PERF] instnt/call lines found — is wasmer_perf_dump() called in the binary?")
        expected = n * m
        if len(blocks) != expected:
            print(f"  Warning: expected {expected} PERF blocks (n={n} × m={m}), got {len(blocks)}")

        # Average the m repetitions for each instance slot:
        # blocks layout: [inst_0_run_0, inst_1_run_0, ..., inst_{n-1}_run_0,
        #                  inst_0_run_1, inst_1_run_1, ..., inst_{n-1}_run_1, ...]
        averaged: list[dict[str, float]] = []
        for slot in range(n):
            slot_blocks = blocks[slot::n]          # every n-th block starting at slot
            all_keys = set().union(*(b.keys() for b in slot_blocks))
            averaged.append({
                key: sum(b.get(key, 0.0) for b in slot_blocks) / len(slot_blocks)
                for key in all_keys
            })

        all_runs.append(averaged)
        print(f"  run {i+1}/{args.runs}: {n} instances (averaged over {m} outer iterations)")

    title = (
        f"{Path(args.binary).name} — Wasmer PERF steps  [m={args.main_iter}, c={args.call_iter}]"
        + (f"  (avg over {args.runs} runs)" if args.runs > 1 else "")
    )
    plot(all_runs, args.category, title, out_path)


if __name__ == "__main__":
    main()

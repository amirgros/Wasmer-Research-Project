#!/usr/bin/env python3
"""
Run a cycles-test binary and, like plot_instance.py/plot_instantiate.py, plot
a per-step line chart vs instance # for Wasmer's S2 memory allocation step
(wasm_instance_new's instnt S2 mem_alloc phase), plus print a grouped summary
table.

One line per *leaf* step (S2a, the mmap/mprotect syscalls, S2b-ii, S2c, S2d),
each named with its place in the hierarchy.

Parses every "[PERF] <label> begin=.. end=.. delta=.. cyc (.. us)" line emitted
by wasmer_perf_dump() and reconstructs the nesting of measured spans directly
from their begin/end TSC ranges -- a span is the parent of another if its
[begin, end] interval tightly encloses it. This needs no hardcoded label
hierarchy, so it picks up the S2 sub-steps (S2a vmctx_malloc, S2b
create_memories, S2c create_tables, S2d create_globals) and their nested
spans (mem S2b-i mmap+mprotect, mem S2b-ii vmdef_writeback, and the raw mmap
syscall / mprotect leaves) automatically.

Usage (from project root):
    python3 cycles_test/plot_mem_alloc.py [binary] [--runs N] [--output FILE]

Examples:
    python3 cycles_test/plot_mem_alloc.py
    python3 cycles_test/plot_mem_alloc.py cycles_test/time_test --runs 5
    python3 cycles_test/plot_mem_alloc.py --threshold 40 --output mem_alloc.png
"""

import argparse
import re
import shlex
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import numpy as np
except ImportError:
    sys.exit("Missing dependencies. Run: pip install matplotlib numpy")

# Matches lines emitted by wasmer_perf_dump(), e.g.:
#   [PERF] instnt S2b create_memories    begin=  ..  end=  ..  delta=  1234 cyc  (0.514 us)
_PERF_RE = re.compile(
    r'^\[PERF\]\s+(?P<label>.+?)\s+'
    r'begin=\s*(?P<begin>\d+)\s+end=\s*(?P<end>\d+)\s+'
    r'delta=\s*(?P<delta>\d+)\s+cyc\s+\((?P<us>[\d.]+)\s+us\)'
)

DEFAULT_ROOT = "instnt S2 mem_alloc"


# ── parsing + tree reconstruction ───────────────────────────────────────────

class Entry:
    __slots__ = ("label", "begin", "end", "delta", "us", "parent")

    def __init__(self, label, begin, end, delta, us):
        self.label = label
        self.begin = begin
        self.end = end
        self.delta = delta
        self.us = us
        self.parent = None


def parse_blocks(text: str) -> list:
    """Split stdout into one block per wasmer_perf_dump() call (a contiguous
    run of matching [PERF] lines), each block being one list of Entry."""
    blocks: list[list[Entry]] = []
    current: list[Entry] = []
    for line in text.splitlines():
        m = _PERF_RE.match(line.strip())
        if m:
            current.append(Entry(
                m.group("label"),
                int(m.group("begin")),
                int(m.group("end")),
                int(m.group("delta")),
                float(m.group("us")),
            ))
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)
    return blocks


def build_tree(entries: list) -> None:
    """Assign e.parent by interval containment: the tightest span whose
    [begin, end] encloses another span's is its immediate parent."""
    for e in entries:
        candidates = [
            o for o in entries
            if o is not e and o.begin <= e.begin and o.end >= e.end
        ]
        if candidates:
            e.parent = min(candidates, key=lambda o: o.end - o.begin)


class Stats:
    def __init__(self):
        self.cycles: list[int] = []
        self.us: list[float] = []
        self.pct_parent: list[float] = []
        self.parent_label: str | None = None
        self.n_blocks = 0


def aggregate(blocks: list):
    """Returns (stats_by_label, children_by_label[parent_label -> [child_label]])."""
    stats: dict[str, Stats] = {}
    children: dict[str, list] = {}

    for entries in blocks:
        build_tree(entries)
        for e in entries:
            s = stats.setdefault(e.label, Stats())
            s.cycles.append(e.delta)
            s.us.append(e.us)
            s.n_blocks += 1
            if e.parent is not None:
                s.parent_label = e.parent.label
                s.pct_parent.append(e.delta / e.parent.delta * 100.0)
                siblings = children.setdefault(e.parent.label, [])
                if e.label not in siblings:
                    siblings.append(e.label)

    return stats, children


def leaves_of(order: list, root: str, children: dict) -> list:
    """Labels in the subtree with no recorded children -- the finest-grained
    step available at each branch (e.g. the raw mmap/mprotect syscalls rather
    than the "mem S2b-i mmap+mprotect" span that wraps them)."""
    return [l for l in order if l != root and not children.get(l)]


# Category words that prefix a label but aren't part of its step code/name.
_CATEGORY_WORDS = {"instnt", "mem", "call"}
_CODE_RE = re.compile(r'^(S\d+[a-zA-Z]*(?:-[ivxIVX]+)?)\b')


def strip_category(label: str) -> str:
    parts = label.split(" ", 1)
    if len(parts) == 2 and parts[0] in _CATEGORY_WORDS:
        return parts[1]
    return label


def extract_code(label: str) -> str | None:
    m = _CODE_RE.match(strip_category(label))
    return m.group(1) if m else None


def display_name(label: str, stats: dict) -> str:
    """A name that always carries its place in the hierarchy: labels that
    already embed a step code (S2a, S2b-ii, ...) are used as-is; labels that
    don't (the raw mmap/mprotect syscalls) are prefixed with the nearest
    ancestor's code so e.g. "mmap syscall (none, reserve)" reads as
    "S2b-i mmap syscall (none, reserve)"."""
    stripped = strip_category(label)
    if extract_code(stripped):
        return stripped
    parent = stats[label].parent_label
    while parent is not None:
        code = extract_code(parent)
        if code:
            return f"{code} {stripped}"
        parent = stats[parent].parent_label
    return stripped


def subtree_order(root: str, children: dict) -> list:
    """DFS preorder (root, then each child's subtree), siblings sorted alphabetically."""
    order = [root]
    for child in sorted(children.get(root, [])):
        order.extend(subtree_order(child, children))
    return order


def depths_of(order: list, root: str, children: dict) -> dict:
    depth = {root: 0}
    for parent, kids in children.items():
        for k in kids:
            depth[k] = depth.get(parent, 0) + 1
    # depth may need a second pass if a parent's own depth wasn't resolved yet
    changed = True
    while changed:
        changed = False
        for parent, kids in children.items():
            if parent in depth:
                for k in kids:
                    want = depth[parent] + 1
                    if depth.get(k) != want:
                        depth[k] = want
                        changed = True
    return depth


# ── I/O ──────────────────────────────────────────────────────────────────────

def run_binary(binary: str, binary_args: list) -> str:
    # `run` is a bash alias (numactl pin) -- use bash -ic so aliases load from ~/.bashrc
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


# ── table + plot ─────────────────────────────────────────────────────────────

def fmt_mean_std(values: list, fmt: str) -> str:
    mean = statistics.mean(values)
    if len(values) > 1:
        std = statistics.stdev(values)
        return f"{mean:{fmt}} ± {std:{fmt}}"
    return f"{mean:{fmt}}"


def print_table(order: list, depth: dict, stats: dict, threshold: float, n_samples: int):
    header = f"{'label':<42} {'cycles':>24} {'us':>16} {'% parent':>12}  flag"
    print(header)
    print("-" * len(header))
    for label in order:
        s = stats[label]
        cyc_str = fmt_mean_std(s.cycles, ",.0f")
        us_str = fmt_mean_std(s.us, ".3f")
        if s.pct_parent:
            pct_mean = statistics.mean(s.pct_parent)
            pct_str = f"{pct_mean:.1f}%"
            flag = "⚠ >%.0f%%" % threshold if pct_mean > threshold else ""
        else:
            pct_str = "-"
            flag = ""
        seen = "" if s.n_blocks >= n_samples else f"  (seen {s.n_blocks}/{n_samples})"
        name = "  " * depth[label] + label
        print(f"{name:<42} {cyc_str:>24} {us_str:>16} {pct_str:>12}  {flag}{seen}")


def leaf_us_by_slot(runs_blocks: list, leaves: list, n: int, m: int) -> dict:
    """For each leaf label, returns an (n_runs, n_instances) array of its us
    cost averaged over the m main-iterations recorded for each instance slot.
    A slot/leaf combo with no matching entry in any of its m blocks (e.g. the
    mmap variant not taken on that run) is left as NaN so it plots as a gap
    instead of a misleading zero."""
    n_runs = len(runs_blocks)
    result = {leaf: np.full((n_runs, n), np.nan) for leaf in leaves}
    for r, blocks in enumerate(runs_blocks):
        block_dicts = [{e.label: e.us for e in entries} for entries in blocks]
        for slot in range(n):
            slot_dicts = block_dicts[slot::n]
            for leaf in leaves:
                vals = [d[leaf] for d in slot_dicts if leaf in d]
                if vals:
                    result[leaf][r, slot] = sum(vals) / len(vals)
    return result


def plot_by_instance(leaf_data: dict, names: dict, n_instances: int, n_runs: int, title: str, output: str):
    x = np.arange(1, n_instances + 1)
    fig, ax = plt.subplots(figsize=(max(10, n_instances), 5.5))

    cmap = plt.get_cmap("tab10")
    for i, (label, arr) in enumerate(leaf_data.items()):
        color = cmap(i / max(len(leaf_data), 1))
        mean = np.nanmean(arr, axis=0)
        ax.plot(x, mean, marker="o", label=names[label], color=color)
        if n_runs > 1:
            std = np.nanstd(arr, axis=0)
            ax.fill_between(x, mean - std, mean + std, alpha=0.15, color=color)

    ax.set_xlabel("Instance #")
    ax.set_ylabel("Time (µs)")
    ax.set_title(title)
    ax.set_xticks(x)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.5)

    plt.tight_layout()
    plt.savefig(output, dpi=150)
    print(f"Saved to {output}")


def main():
    # ── time_test parameters (edit these to change defaults) ──────────────
    DEFAULT_MAIN_ITER = 5
    DEFAULT_CALL_ITER = 1
    DEFAULT_NUM_INSTANCES = 20
    # ────────────────────────────────────────────────────────────────────

    parser = argparse.ArgumentParser(
        description="Plot and summarize the cost of each Wasmer memory-allocation (S2) step.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("binary", nargs="?", default="cycles_test/time_test",
                        help="Path to test binary (default: cycles_test/time_test)")
    parser.add_argument("--root", default=DEFAULT_ROOT, metavar="LABEL",
                        help=f"Root [PERF] label to scope the tree to (default: {DEFAULT_ROOT!r})")
    parser.add_argument("--runs", "-r", type=int, default=1, metavar="N",
                        help="Number of times to invoke the binary (default: 1)")
    parser.add_argument("--main-iter", "-m", type=int, default=DEFAULT_MAIN_ITER, metavar="N",
                        help=f"Binary -m: outer iterations (default: {DEFAULT_MAIN_ITER})")
    parser.add_argument("--call-iter", "-c", type=int, default=DEFAULT_CALL_ITER, metavar="N",
                        help=f"Binary -c: call iterations per instance (default: {DEFAULT_CALL_ITER})")
    parser.add_argument("--num-instances", "-n", type=int, default=DEFAULT_NUM_INSTANCES, metavar="N",
                        help=f"Binary -n: number of instances (default: {DEFAULT_NUM_INSTANCES})")
    parser.add_argument("--threshold", "-t", type=float, default=50.0, metavar="PCT",
                        help="Flag/highlight steps costing more than PCT of their parent's time (default: 50)")
    parser.add_argument("--output", "-o", default=None, metavar="FILE",
                        help="Override output path (default: mem_alloc_plots/<datetime>.png)")
    args = parser.parse_args()

    binary = str(Path(args.binary).resolve())
    if not Path(binary).is_file():
        sys.exit(f"Binary not found: {binary}")

    binary_args = ["-m", str(args.main_iter), "-c", str(args.call_iter), "-n", str(args.num_instances)]

    print(f"Running '{args.binary}' x{args.runs} (m={args.main_iter} c={args.call_iter} n={args.num_instances})...")
    runs_blocks = []
    all_blocks = []
    for i in range(args.runs):
        raw = run_binary(binary, binary_args)
        blocks = parse_blocks(raw)
        if not blocks:
            sys.exit("No [PERF] lines found -- is wasmer_perf_dump() called in the binary?")
        expected = args.num_instances * args.main_iter
        if len(blocks) != expected:
            print(f"  Warning: expected {expected} PERF blocks (n={args.num_instances} × m={args.main_iter}), got {len(blocks)}")
        runs_blocks.append(blocks)
        all_blocks.extend(blocks)
        print(f"  run {i + 1}/{args.runs}: {len(blocks)} PERF blocks parsed")

    stats, children = aggregate(all_blocks)
    if args.root not in stats:
        sys.exit(f"Root label {args.root!r} not found in PERF output. "
                  f"Available labels: {', '.join(sorted(stats))}")

    order = subtree_order(args.root, children)
    depth = depths_of(order, args.root, children)

    n_samples = len(all_blocks)
    print(f"\n=== Memory allocation ({args.root}) summary ({n_samples} instantiation(s) sampled) ===\n")
    print_table(order, depth, stats, args.threshold, n_samples)

    if args.output:
        by_instance_path = args.output
    else:
        out_dir = Path(__file__).parent / "mem_alloc_plots"
        out_dir.mkdir(exist_ok=True)
        by_instance_path = str(out_dir / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_by_instance.png")

    leaves = leaves_of(order, args.root, children)
    names = {leaf: display_name(leaf, stats) for leaf in leaves}
    leaf_data = leaf_us_by_slot(runs_blocks, leaves, args.num_instances, args.main_iter)

    by_instance_title = (
        f"{Path(args.binary).name} — {args.root} steps vs instance #"
        f"  [m={args.main_iter}]"
        + (f"  (avg over {args.runs} runs)" if args.runs > 1 else "")
    )
    plot_by_instance(leaf_data, names, args.num_instances, args.runs, by_instance_title, by_instance_path)


if __name__ == "__main__":
    main()

# Wasmer-Research-Project

Performance research measuring CPU cycle counts for WebAssembly execution
phases in the [Wasmer](https://wasmer.io/) runtime — file loading, engine/store
creation, module compilation, instantiation, export lookup, and function calls.

A companion patched clone of Wasmer (`wasmer_repo_patch/`) adds bespoke
instrumentation and an experimental linear memory pool for instance
create/destroy cycles, so the overhead can be broken down further than the
public C API exposes.

## Working directory conventions

Different tools in this repo assume different current directories — running
one from the wrong place either fails or silently writes output somewhere
unexpected:

| Tool | Run from | Why |
|---|---|---|
| `make`, test binaries (`./sum_test`, ...) | `cycles_test/` | Binaries `fopen()` their `.wasm` files with a path relative to cwd (e.g. `./wasm/time.wasm`) |
| `scripts/compile_wasm.sh` | anywhere | Paths are resolved from its own argument, not cwd |
| `scripts/flame_profile.sh`, `scripts/wasm_flame_graph.sh` | `cycles_test/` | They write to a `flame_graphs/` dir relative to cwd — run elsewhere and you'll create a stray `flame_graphs/` folder instead of using `cycles_test/flame_graphs/` |
| `cycles_test/plot_*.py` | repo root | Their default binary path (`cycles_test/time_test`) and usage examples assume root; their *output* directories (`instances_plots/`, `instantiate_plots/`, `mem_alloc_plots/`) are anchored to the script's own location, so this is safe regardless of cwd |

## How To Run

```bash
# Lock CPU frequency on core 1, set perf/FlameGraph env vars, and define run()
source ./scripts/env.sh

# Build all test binaries
cd cycles_test && make

# Run a test, pinned to the locked core (see "The `run` helper" below)
run ./time_test -m 5 -c 100 -n 20
run ./sum_test
run ./math_test
run ./print_test
```

### The `run` helper

`source ./scripts/env.sh` does two things for measurement accuracy: it locks
Core 1's *frequency* (via `cpupower`), and it defines a `run()` shell function
that pins the *process* to that same core:

```bash
run() { numactl -C $CORE -l "$@"; }
```

Locking the frequency alone is not enough — the OS scheduler can still
migrate a process across cores mid-run, which reintroduces exactly the
jitter the frequency lock was meant to remove. Always invoke test binaries
(and, ideally, the `plot_*.py`/flame-graph scripts) through `run` rather than
calling them directly, e.g. `run ./time_test -n 50` instead of
`./time_test -n 50`. This is the same `numactl -C 1 -l` pinning that
`flame_profile.sh`/`wasm_flame_graph.sh` already use internally for
profiling runs — `run` just makes it available for plain (non-profiling)
measurement runs too.

## `time_test`: the main testing platform

`time_test` is the primary/most actively maintained benchmark and the one
new experiments should be built from — it's the only test with a CLI, it
calls `wasmer_perf_dump()`/`wasmer_perf_reset()` (feeding the `plot_*.py`
tools below), and it prints linear-memory-pool hit/miss stats via
`wasmer_linear_memory_pool_stats()`.

```bash
run ./time_test -m <main_iterations> -c <call_iterations> -n <num_instances>
# defaults: -m 1 -c 1 -n 10
```

- **`-n` (num_instances)** — how many separate module instances to create.
  `cycles_log_t.instances_logs` is resized to this length, so each instance
  gets its own row of `inst_cycles` / `init_env` / `local_export_cycles` /
  `call_cycles` in the printed report (and in the `plot_instance.py` /
  `plot_instantiate.py` charts, one point per instance).
- **`-c` (call_iterations)** — how many times the target WASM function is
  called *within* each instance, back to back, before moving to the next
  instance. This isolates steady-state call overhead from one-time
  per-instance costs (instantiate/init/export-cast); `call_cycles` is
  averaged over this count by `devide_cycles_log()`.
- **`-m` (main_iterations)** — how many times the *entire* `test_call()` run
  (file load → engine/store → compile → imports → all `-n` instances) is
  repeated from scratch, so the one-time setup phases and every instance's
  numbers can be averaged across runs for less noisy output.

The other three tests (`sum_test`, `math_test`, `print_test`) hardcode these
three values in `main()` instead of exposing them as flags — edit the
`main_iterations`/`call_iterations`/`num_instances` locals directly if you
need different values from one of them.

### Are `sum_test` / `math_test` / `print_test` in sync with `time_test`?

Yes, structurally — all four were rebuilt clean against the current
`cycles_log_t` / `instance_log_t` in `statistics_tools.h` while preparing this
README, so none of them reference stale/renamed fields. `math_test.cpp` and
`print_test.cpp` share the exact same `test_call()` harness as
`time_test.cpp` (file/engine/store/compile → per-instance
instantiate/init/export/call), just without CLI parsing or the
`wasmer_perf_dump()` calls. `sum_test.cpp` is the oldest of the four and
still uses its own, slightly different `sum_test()` function: `sum.wasm`
needs no WASI imports, so it skips the WASI setup step entirely and never
populates `imports_cycles`, `global_export_cycles`, or `arg_cycles` (they
stay `0`) — that's expected given what it measures, not a bug.

## Compiling the tests

From `cycles_test/`:

```bash
make              # build every *.cpp in this dir into a same-named binary
make sum_test     # build just one
make clean        # remove built binaries
```

The Makefile auto-discovers `cycles_test/*.cpp` (`SOURCES = $(wildcard *.cpp)`)
and compiles each into a same-named executable — dropping a new
`cycles_test/newtest.cpp` in makes `make` pick it up automatically, no
Makefile edit needed.

## Compiling guest WASM modules

```bash
./scripts/compile_wasm.sh <source_file.cpp> <func1,func2,...>
# Example:
./scripts/compile_wasm.sh cycles_test/wasm/sum.cpp standalone_sum,sum_with_args
```

What it does:
1. Derives the output path by swapping the source's extension for `.wasm` in
   the same directory (`cycles_test/wasm/sum.cpp` → `cycles_test/wasm/sum.wasm`).
2. Turns the comma-separated function list into Emscripten's
   `EXPORTED_FUNCTIONS` array syntax, prefixing each name with `_` (the C
   symbol prefix Emscripten expects): `standalone_sum,sum_with_args` →
   `['_standalone_sum','_sum_with_args']`.
3. Runs `emcc <source> -o <out.wasm> --no-entry -s EXPORTED_FUNCTIONS=... -g
   -s ERROR_ON_UNDEFINED_SYMBOLS=0`. `--no-entry` skips requiring a `main()`
   (these are libraries, not standalone programs); `-g` is always on since
   this project only ever wants debuggable/inspectable builds;
   `ERROR_ON_UNDEFINED_SYMBOLS=0` tolerates the WASI imports the host side
   supplies at instantiation time.

Guest functions must additionally be marked `EMSCRIPTEN_KEEPALIVE` in the C++
source or they'll be dead-code-eliminated regardless of the export list.

## Flame graphs — limited usefulness in this project

```bash
./scripts/flame_profile.sh ./sum_test          # profile a host test binary directly
./scripts/wasm_flame_graph.sh ./wasm/sum.wasm  # profile via `wasmer run --profiler=perfmap`
```

Both work (perf record → stackcollapse → flamegraph.pl → SVG), but neither
resolves useful symbol names *inside* the JIT-compiled WASM guest code:

- `flame_profile.sh` profiles the host C++ binary directly. The host-side
  call stack (our `test_call()`, the Wasmer C API, libc, etc.) resolves
  fine, but the compiled WASM function bodies show up as unresolved/anonymous
  frames — there's no symbol table for JIT'd code by default.
- `wasm_flame_graph.sh` tries to fix that with Wasmer CLI's
  `--profiler=perfmap` (which emits a `/tmp/perf-<PID>.map` for `perf` to
  read), but it does so by invoking the `wasmer` CLI on the raw `.wasm` file
  — a different execution path than our C API test harness — and in
  practice still doesn't yield meaningful per-guest-function names for these
  Emscripten-compiled modules.

Net effect: flame graphs can confirm *that* time is spent inside Wasmer
runtime code vs. host code, but can't attribute cycles to individual guest
WASM functions the way this project's actual measurement tools can. For
that, prefer the `[PERF]`-tracing + `plot_*.py` pipeline described below,
which is purpose-built for this project's phase-level breakdown.

## Adjustments to Wasmer Repo

The tests link against a locally patched Wasmer checkout
(`/csl/amirgrossman/projects/tools/wasmer`). These changes are **not**
upstream/generic Wasmer profiling infrastructure — they're bespoke
instrumentation written specifically to feed this project's own statistics
collection and the `plot_*.py` graph-analysis scripts in `cycles_test/`:

- **`[PERF]` tracing** — internal timing spans (e.g. instantiation
  sub-steps, memory allocation) dumped via `wasmer_perf_dump()` /
  `wasmer_perf_reset()`. The `plot_instance.py` / `plot_instantiate.py` /
  `plot_mem_alloc.py` scripts parse this exact `[PERF] <label>
  begin=.. end=.. delta=..` text output — there's no other consumer of it.
- **A linear memory pool** (`USE_LINEAR_MEMORY_POOL` in `lib/vm/src/memory.rs`)
  that reuses linear memory mmaps across instance destroy/create cycles
  instead of `munmap`/`mmap`/`mprotect` on every instantiation.

The changes are captured as a patch in [wasmer_repo_patch/](wasmer_repo_patch/),
which includes the exact base commit to apply it against and build
instructions. Apply the patch, then build the C API with `make build-capi`
and point `cycles_test/Makefile`'s `WASMER_HOME` at the resulting
`package/lib/` directory.

## Project Tree

```
├── cycles_test/           # Host (C++) benchmark binaries + analysis scripts
│   ├── time_test.cpp      #   Main testing platform: CLI args, PERF dump, pool stats
│   ├── sum_test.cpp, math_test.cpp, print_test.cpp
│   │                      #   Same cycles_log_t/instance_log_t; params hardcoded in main()
│   ├── wasm/               #   Guest C++ sources + compiled .wasm modules
│   ├── statistics_tools.h #   cycles_log_t / instance_log_t + printing helpers
│   ├── includes.h         #   Common includes + Wasmer API headers
│   ├── plot_instance.py   #   Plot per-instance timing fields vs instance # (run from repo root)
│   ├── plot_instantiate.py#   Plot Wasmer internal PERF steps vs instance # (run from repo root)
│   ├── plot_mem_alloc.py  #   Plot S2 memory-allocation sub-step breakdown (run from repo root)
│   ├── flame_graphs/, instances_plots/, instantiate_plots/, mem_alloc_plots/
│   │                      #   Generated output (flame graphs, PNGs)
│   └── Makefile           #   Auto-builds every *.cpp in this dir
├── basic_test/            # Minimal standalone Wasmer C API smoke test
├── utils/get_cycles.h     # RDTSC-based get_cycles() wrapper
├── scripts/
│   ├── env.sh             #   Lock core 1 to 2.4GHz, set perf/FlameGraph env, define run()
│   ├── compile_wasm.sh    #   Compile a C++ source to .wasm via Emscripten
│   ├── flame_profile.sh   #   perf-based flame graph for a host test binary (run from cycles_test/)
│   └── wasm_flame_graph.sh#   Flame graph via `wasmer run --profiler=perfmap` (run from cycles_test/)
├── wasmer_repo_patch/     # Patch + instructions for the patched Wasmer clone
└── CLAUDE.md              # Detailed guidance for measured phases & workflow
```

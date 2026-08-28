# Wasmer-Research-Project
info...

## How To Run

env..
cycles..

## Adjustments to Wasmer Repo

add the commit of my perf trace code
how to compile...

## project tree

├── bin/                   # All executable artifacts (Git-ignored)
│   ├── wasm/              # Compiled .wasm modules (The payloads)
│   ├── main_platform      # The primary C++ Host/Wasmer runner
│   └── test_runner        # Secondary binary for batch processing
├── src/                   
│   ├── platform/          # The Host: C++ Wasmer implementation logic
│   │   ├── runner.cpp     # Orchestrates WASM loading/execution
│   │   └── runtime.cpp    # Wasmer engine & environment setup
│   ├── modules/           # The Guest: C++ source to be compiled to WASM
│   │   ├── core_logic/    # Main computational research kernels
│   │   └── bench_utils/   # Specialized WASM utilities
│   ├── tests/             # Per-test functions (Experiment definitions)
│   │   ├── experiment_1.cpp
│   │   └── experiment_2.cpp
│   └── common/            # Generic aux functions & shared headers
│       ├── math_helpers.hpp
│       └── shared_types.hpp
├── include/               # Public headers for the platform/modules
├── scripts/               # Build scripts (e.g., compile_to_wasm.sh)
├── data/                  # Input datasets and research output/logs
├── CMakeLists.txt         # Build configuration (or Makefile)
└── README.md              # Setup instructions and research goals

#!/bin/bash

# ==============================================================================
# WASM RESEARCH PROFILER (Cycles + Flame Graph)
# ==============================================================================
# USAGE:
#   ./scripts/flame_profile.sh <command_to_run> [args...]
#
#
# REQUIREMENTS:
# 1. FLAMEGRAPH_DIR must be exported (e.g., export FLAMEGRAPH_DIR=~/projects/FlameGraph)
# 2. Permissions for Core 1 counters must be set:
#    sudo sysctl -w kernel.perf_event_paranoid=-1
#    sudo sysctl -w kernel.kptr_restrict=0
# 3. 'perf', 'numactl', and 'perl' must be installed.
# ==============================================================================

# Check for required environment variable
if [ -z "$FLAMEGRAPH_DIR" ]; then
    echo "Error: FLAMEGRAPH_DIR is not set."
    echo "Please run env script with source: source ./scripts/env.sh"
    exit 1
fi

# Check if a command was provided
if [ -z "$1" ]; then
    echo "Usage: $0 <command_to_run> [args...]"
    echo "Example: $0 ./bin/my_test"
    exit 1
fi

# Variables for naming
FULL_CMD="$@"
CMD_BASE=$(basename "$1")
TIMESTAMP=$(date +%m%d_%H%M)
OUT_NAME="flame_${CMD_BASE}_${TIMESTAMP}.svg"
GRAPH_DIR="flame_graphs"

# Create output directory
mkdir -p "$GRAPH_DIR"

echo "-------------------------------------------------------"
echo "Target: $FULL_CMD"
echo "Output: $GRAPH_DIR/$OUT_NAME"
echo "-------------------------------------------------------"

# Phase 1: Record Cycles
# -e cycles: Hardware clock cycles
# -C 1: Pinning profiler to Core 1
# -g: Call-graph (stack traces)
echo "[1/3] Recording cycles on Core 1..."
perf record -o "$GRAPH_DIR/perf.data" -e cycles -C 1 -g -- numactl -C 1 -l $FULL_CMD

# Phase 2: Process Data
echo "[2/3] Processing perf.data..."
perf script -i "$GRAPH_DIR/perf.data" > "$GRAPH_DIR/out.perf"

# Phase 3: Generate SVG
echo "[3/3] Rendering Flame Graph..."
cat "$GRAPH_DIR/out.perf" | \
    "$FLAMEGRAPH_DIR/stackcollapse-perf.pl" | \
    "$FLAMEGRAPH_DIR/flamegraph.pl" > "$GRAPH_DIR/$OUT_NAME"

# Clean up intermediate files
rm "$GRAPH_DIR/out.perf"

echo "-------------------------------------------------------"
echo "Profiling Complete! Open $GRAPH_DIR/$OUT_NAME in your browser."
echo "-------------------------------------------------------"
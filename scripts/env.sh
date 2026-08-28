#!/bin/bash

# Use source when running

#------------- CPU Frequency Scaling Setup -------------
# 2.4GHz is the hardware's native 'Base' speed.
# 1 cycle = 0.4166... ns | 2.4 cycles = 1 ns | 12 cycles = 5 ns
CORE=1
FREQ="2400MHz"

echo "Locking Core $CORE to 2.4GHz Base Clock..."

# Set governor to performance (stops downclocking)
sudo cpupower -c $CORE frequency-set -g performance

# Force the range to stay at 2.4GHz
sudo cpupower -c $CORE frequency-set -u $FREQ -d $FREQ

echo "---------------------------------------"
cpupower -c $CORE frequency-info | grep -E "current policy|asserted"
echo "---------------------------------------"


#------------- Setup for PERF -------------
# Allow perf to record at any level (user and kernel)
sudo sysctl -w kernel.perf_event_paranoid=-1

# Allow perf to see kernel symbols (addresses)
sudo sysctl -w kernel.kptr_restrict=0


#------------- Set FlameGraph Directory -------------
export FLAMEGRAPH_DIR=~/projects/tools/FlameGraph
echo "FLAMEGRAPH_DIR set to: $FLAMEGRAPH_DIR"


#------------- "run" helper: pin a command to the locked core -------------
# Locking Core 1's frequency (above) is not enough on its own -- the OS
# scheduler can still migrate the process to a different core. `run` pins
# the process itself to Core $CORE via numactl, so it actually executes on
# the core whose clock we just fixed. Use this for every measurement run
# (./sum_test, ./time_test -m 5 -n 20, python3 cycles_test/plot_instance.py, ...);
# without it, cycle counts pick up noise from core migration.
run() {
    if [ -z "$1" ]; then
        echo "Usage: run <command> [args...]"
        return 1
    fi
    numactl -C $CORE -l "$@"
}
export -f run
echo "run() defined: pins its argument command to Core $CORE (e.g. run ./cycles_test/time_test -n 20)"
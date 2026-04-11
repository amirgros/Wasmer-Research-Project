#!/bin/bash


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
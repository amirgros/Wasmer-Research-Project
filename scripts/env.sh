#!/bin/bash

CORE=1
FREQ="2000MHz"

echo "Taming Core $CORE..."

# 1. Force Passive mode to regain control from hardware
if [ -f /sys/devices/system/cpu/intel_pstate/status ]; then
    echo "passive" | sudo tee /sys/devices/system/cpu/intel_pstate/status > /dev/null
fi

# 2. Disable Turbo (Try multiple known paths)
paths=(
    "/sys/devices/system/cpu/intel_pstate/no_turbo"
    "/sys/devices/system/cpu/cpufreq/boost"
)

for p in "${paths[@]}"; do
    if [ -f "$p" ]; then
        echo "1" | sudo tee "$p" > /dev/null 2>&1 || echo "Could not write to $p"
    fi
done

# 3. Set the frequency for Core 1
sudo cpupower -c $CORE frequency-set -g performance -u $FREQ -d $FREQ

echo "---------------------------------------"
cpupower -c $CORE frequency-info | grep -E "current policy|asserted"
echo "---------------------------------------"
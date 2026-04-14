#include <cstdint>
#include <vector>
#include <iostream>

using namespace std;

#define CLOCK_FREQ_GHZ 2.4
#define CYCLES_TO_US(cycles) ((cycles) / (CLOCK_FREQ_GHZ * 1e3))

typedef struct{
    uint64_t inst_cycles;
    uint64_t exeport_cycles;
    uint64_t arg_cycles;
    uint64_t call_cycles;
} instance_log_t;

typedef struct{
    uint64_t file_load_cycles;
    uint64_t engine_store_cycles;
    uint64_t compile_cycles;
    uint64_t imports_cycles;
    vector<instance_log_t> instances_logs;
} cycles_log_t;


inline void print_cycles_log(const cycles_log_t& log) {
    cout << "=== Cycles Log ===" << endl;
    cout << "File Load:      " << CYCLES_TO_US(log.file_load_cycles) << " us" << endl;
    cout << "Engine & Store: " << CYCLES_TO_US(log.engine_store_cycles) << " us" << endl;
    cout << "Compile:        " << CYCLES_TO_US(log.compile_cycles) << " us" << endl;
    cout << "Imports:        " << CYCLES_TO_US(log.imports_cycles) << " us" << endl;
    cout << "\nInstances (" << log.instances_logs.size() << "):" << endl;
    for (size_t i = 0; i < log.instances_logs.size(); i++) {
        cout << "  Instance " << (i + 1) << ":" << endl;
        cout << "    Instantiate: " << CYCLES_TO_US(log.instances_logs[i].inst_cycles) << " us" << endl;
        cout << "    Find Export: " << CYCLES_TO_US(log.instances_logs[i].exeport_cycles) << " us" << endl;
        cout << "    Prep Args:   " << CYCLES_TO_US(log.instances_logs[i].arg_cycles) << " us" << endl;
        cout << "    Function Call: " << CYCLES_TO_US(log.instances_logs[i].call_cycles) << " us" << endl;
    }
}

inline void devide_cycles_log(cycles_log_t& log, uint64_t divisor) {
    log.file_load_cycles /= divisor;
    log.engine_store_cycles /= divisor;
    log.compile_cycles /= divisor;
    log.imports_cycles /= divisor;
    for (size_t i = 0; i < log.instances_logs.size(); i++) {
        log.instances_logs[i].inst_cycles /= divisor;
        log.instances_logs[i].exeport_cycles /= divisor;
        log.instances_logs[i].arg_cycles /= divisor;
        log.instances_logs[i].call_cycles /= divisor;
    }
}
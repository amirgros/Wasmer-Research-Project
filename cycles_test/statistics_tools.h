#include <cstdint>
#include <vector>
#include <iostream>

using namespace std;

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
    vector<instance_log_t> instances_logs;
} cycles_log_t;


inline void print_cycles_log(const cycles_log_t& log) {
    cout << "=== Cycles Log ===" << endl;
    cout << "File Load:      " << log.file_load_cycles << " cycles" << endl;
    cout << "Engine & Store: " << log.engine_store_cycles << " cycles" << endl;
    cout << "Compile:        " << log.compile_cycles << " cycles" << endl;
    cout << "\nInstances (" << log.instances_logs.size() << "):" << endl;
    for (size_t i = 0; i < log.instances_logs.size(); i++) {
        cout << "  Instance " << (i + 1) << ":" << endl;
        cout << "    Instantiate: " << log.instances_logs[i].inst_cycles << " cycles" << endl;
        cout << "    Find Export: " << log.instances_logs[i].exeport_cycles << " cycles" << endl;
        cout << "    Prep Args:   " << log.instances_logs[i].arg_cycles << " cycles" << endl;
        cout << "    Function Call: " << log.instances_logs[i].call_cycles << " cycles" << endl;
    }
}

inline void devide_cycles_log(cycles_log_t& log, uint64_t divisor) {
    log.file_load_cycles /= divisor;
    log.engine_store_cycles /= divisor;
    log.compile_cycles /= divisor;
    for (size_t i = 0; i < log.instances_logs.size(); i++) {
        log.instances_logs[i].inst_cycles /= divisor;
        log.instances_logs[i].exeport_cycles /= divisor;
        log.instances_logs[i].arg_cycles /= divisor;
        log.instances_logs[i].call_cycles /= divisor;
    }
}
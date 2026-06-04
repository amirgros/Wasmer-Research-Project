#include "includes.h"


/**
 * @brief Executes a Wasmer test for a sum function with no args or exports.
 * 
 * @param[in,out] log A reference to a cycles_log_t structure that records the cycle counts
 * @param[in] print_flag A flag to control printing of debug information
 * @param[in] args_vec A vector of integer arguments to pass to the function
 * @param[in] func_name The name of the function to call in the WASM module (e.g., "standalone_sum", "sum_with_args", "long_standalone_sum")
 * 
 * @return int Returns 0 on successful completion of all tests and cleanups.
 *             Returns 1 for errors (+prints cause)
 */
int sum_test(cycles_log_t& log, bool print_flag, const vector<int>& args_vec, const char* func_name) {
    uint64_t cycles_diff_base;

    // 1. LOAD THE WASM FILE
    // We manually read the bytes from the file you compiled with Emscripten
    cycles_diff_base = get_cycles();
    FILE* file = fopen("./wasm/sum.wasm", "rb");
    if (!file) {
        printf("Error: Could not open sum.wasm. Make sure it is in the same folder!\n");
        return 1;
    }
    fseek(file, 0, SEEK_END);
    long len = ftell(file);
    rewind(file);

    wasm_byte_vec_t wasm_bytes;
    wasm_byte_vec_new_uninitialized(&wasm_bytes, len);
    fread(wasm_bytes.data, 1, len, file);
    fclose(file);
    if (print_flag) {
        cout << "Wasm file loaded. Cycle: " << (get_cycles() - cycles_diff_base) << endl;
    }
    log.file_load_cycles += (get_cycles() - cycles_diff_base);

    // 2. SETUP THE ENGINE & STORE
    cycles_diff_base = get_cycles();
    wasm_engine_t* engine = wasm_engine_new();
    wasm_store_t* store = wasm_store_new(engine); // MEM
    if (print_flag) {
        cout << "Engine and store created. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
    }
    log.engine_store_cycles += (get_cycles() - cycles_diff_base);

    // 3. COMPILE THE MODULE
    cycles_diff_base = get_cycles();
    wasm_module_t* module = wasm_module_new(store, &wasm_bytes);
    wasm_byte_vec_delete(&wasm_bytes); // Clean up the raw bytes
    if (!module) {
        printf("Error: Failed to compile the Wasm module!\n");
        return 1;
    }
    if (print_flag) {
        cout << "Module compiled successfully. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
    }
    log.compile_cycles += (get_cycles() - cycles_diff_base);

    // 4. INSTANTIATE (THE HANDSHAKE)
    for (int i = 0; i < log.instances_logs.size(); i++) {
        if (print_flag) {
            cout << "Instantiating module instance " << (i + 1) << "...\n";
        }
        // Since we aren't using WASI or printing yet, imports are empty
        cycles_diff_base = get_cycles();
        wasm_extern_vec_t imports = WASM_EMPTY_VEC;
        wasm_instance_t* instance = wasm_instance_new(store, module, &imports, NULL); // last argument is for traps
        if (!instance) {
            printf("Error: Failed to instantiate the module!\n");
            return 1;
        }
        log.instances_logs[i].inst_cycles += (get_cycles() - cycles_diff_base);
        if (print_flag) {
            cout << "Module instantiated successfully. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
        }

        // 5. FIND THE FUNCTION IN EXPORTS
        cycles_diff_base = get_cycles();
        wasm_extern_vec_t exports;
        wasm_instance_exports(instance, &exports); // doesn't recognize types yet (func, memory, etc.)
        
        // We also need the names of the exports (the functions in the guest code) to find ours
        wasm_exporttype_vec_t export_types;
        wasm_module_exports(module, &export_types);

        wasm_func_t* target_func = NULL;
        for (size_t i = 0; i < exports.size; i++) {
            const wasm_name_t* name = wasm_exporttype_name(export_types.data[i]);
            // Note: Emscripten adds a leading underscore to C functions
            if (strncmp(name->data, func_name, name->size) == 0) { // got the correct index
                target_func = wasm_extern_as_func(exports.data[i]); // cast the instance' export pointer to func
                break;
            }
        }

        if (!target_func) {
            printf("Error: Could not find WASM function in exports!\n");
            return 1;
        }
        if (print_flag) {
            cout << "Exported function found. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
        }
        // log.instances_logs[i].exeport_cycles += (get_cycles() - cycles_diff_base);

        // 6. PREPARE ARGUMENTS AND RESULTS
        cycles_diff_base = get_cycles();

        /* --- ARGUMENTS SECTION ---*/
        wasm_val_vec_t args;
        wasm_val_t* args_arr = nullptr;
        if (!args_vec.empty()) {
            args_arr = new wasm_val_t[args_vec.size()];
            for (size_t idx = 0; idx < args_vec.size(); idx++) {
                args_arr[idx] = WASM_I32_VAL(args_vec[idx]);
            }
            args.size = args_vec.size();
            args.data = args_arr;
        } else {
            args = WASM_EMPTY_VEC; 
        }

        // We expect 1 result (the sum)
        wasm_val_t res_val[1] = { WASM_INIT_VAL };
        wasm_val_vec_t results = WASM_ARRAY_VEC(res_val);
        if (print_flag) {
            cout << "Arguments and results prepared. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
        }
        // log.instances_logs[i].arg_cycles += (get_cycles() - cycles_diff_base);

        // 7. THE CALL
        cycles_diff_base = get_cycles();
        if (wasm_func_call(target_func, &args, &results)) {
            printf("Error: The Wasm function call failed!\n");
            return 1;
        }
        if (print_flag) {
            cout << "Function called successfully. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
        }
        log.instances_logs[i].call_cycles += (get_cycles() - cycles_diff_base);

        // 8. PRINT THE OUTPUT
        if (print_flag) {
            cout << "Result from WebAssembly: " << results.data[0].of.i32 << endl;
        }

        
        // CLEANUP
        if (args_arr) {
            delete[] args_arr;
        }
        wasm_exporttype_vec_delete(&export_types);
        wasm_extern_vec_delete(&exports);
        wasm_instance_delete(instance);
    }
    wasm_module_delete(module);
    wasm_store_delete(store);
    wasm_engine_delete(engine);

    return 0;
}


int main() {
    int main_iterations = 50;
    int call_iterations = 1;
    int num_instances = 2;
    bool print_flag = false;
    vector<int> args_vec = {1000000};
    const char* func_name = "loop_sum"; // "standalone_sum", "sum_with_args", "loop_sum"

    cycles_log_t* log = new cycles_log_t();
    log->imports_cycles = 0;
    log->instances_logs.resize(num_instances); 
    for (int i = 0; i < main_iterations; i++) {
        cout << "Running sum_test iteration " << (i + 1) << "...\n";
        sum_test(*log, print_flag, args_vec, func_name);
    }
    devide_cycles_log(*log, main_iterations, call_iterations);
    print_cycles_log(*log);
    delete log;
}
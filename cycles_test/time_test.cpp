#include "includes.h"


/**
 * @brief Executes a Wasmer test for a sum function with no args or exports.
 * 
 * @param[in,out] log A reference to a cycles_log_t structure that records the cycle counts
 * @param[in] print_flag A flag to control printing of debug information
 * @param[in] args_vec A vector of integer arguments to pass to the function
 * @param[in] file_name The name of the WASM file to load (e.g., "sum.wasm", "print.wasm")
 * @param[in] func_name The name of the function to call in the WASM module (e.g., "standalone_sum", "sum_with_args", "long_standalone_sum")
 * @param[in] call_iterations The number of times to call the target function for averaging cycles
 * 
 * @return int Returns 0 on successful completion of all tests and cleanups.
 *             Returns 1 for errors (+prints cause)
 */
int test_call(cycles_log_t& log, bool print_flag, const vector<int>& args_vec, const char* file_name, const char* func_name, uint64_t call_iterations) {
    uint64_t cycles_diff_base;

    // ---------------------------------------------------------------------------------------
  
    // 1. LOAD THE WASM FILE
    // We manually read the bytes from the file you compiled with Emscripten
    cycles_diff_base = get_cycles();
    FILE* file = fopen(file_name, "rb");
    if (!file) {
        printf("Error: Could not open %s. Make sure it is in the same folder!\n", file_name);
        return 1;
    }
    fseek(file, 0, SEEK_END);
    long len = ftell(file);
    rewind(file);

    wasm_byte_vec_t wasm_bytes;
    wasm_byte_vec_new_uninitialized(&wasm_bytes, len);
    fread(wasm_bytes.data, 1, len, file);
    fclose(file);
    log.file_load_cycles += (get_cycles() - cycles_diff_base);
    if (print_flag) {
        cout << "Wasm file loaded. Cycle: " << (get_cycles() - cycles_diff_base) << endl;
    }

    // ---------------------------------------------------------------------------------------
  

    // 2. SETUP THE ENGINE & STORE
    cycles_diff_base = get_cycles();
    // wasm_config_t* engine_config = wasm_config_new();
    // wasm_config_set_backend(engine_config, LLVM);

    // wasm_engine_t* engine = wasm_engine_new_with_config(engine_config);
    wasm_engine_t* engine = wasm_engine_new();

    wasm_store_t* store = wasm_store_new(engine); // MEM
    log.engine_store_cycles += (get_cycles() - cycles_diff_base);
    if (print_flag) {
        cout << "Engine and store created. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
    }

    // ---------------------------------------------------------------------------------------
  

    // 3. COMPILE THE MODULE
    cycles_diff_base = get_cycles();
    wasm_module_t* module = wasm_module_new(store, &wasm_bytes);
    wasm_byte_vec_delete(&wasm_bytes); // Clean up the raw bytes
    if (!module) {
        printf("Error: Failed to compile the Wasm module!\n");
        return 1;
    }
    log.compile_cycles += (get_cycles() - cycles_diff_base);
    if (print_flag) {
        cout << "Module compiled successfully. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
    }
    
    // ---------------------------------------------------------------------------------------
        
    // 4. SETUP THE WASI ENVIRONMENT AND IMPORTS
    cycles_diff_base = get_cycles();
    wasi_config_t* config = wasi_config_new("math_test_app"); // define permissions and env for called symbols. can map folders

    wasi_env_t* wasi_env = wasi_env_new(store, config);

    wasm_extern_vec_t imports;
    bool get_imports_result = wasi_get_imports(store, wasi_env, module, &imports);
    if (!get_imports_result) {
        printf("Error: Failed to get WASI imports!\n");
        return 1;
    }
    log.imports_cycles += (get_cycles() - cycles_diff_base);
    if (print_flag) {
        cout << "WASI imports created. Cycle: " << (get_cycles() - cycles_diff_base) << endl;
    }

    // wasm_extern_vec_t imports = WASM_EMPTY_VEC;

    // ---------------------------------------------------------------------------------------

    // 5. EXPORT FUNCTION STEP 1 - FIND FUNC INDEX
    cycles_diff_base = get_cycles();
    // We need the names of the exports (the functions name from the .wasm metadata) to find ours
    wasm_exporttype_vec_t export_types;
    wasm_module_exports(module, &export_types);

    int export_func_index = -1;
    for (size_t i = 0; i < export_types.size; i++) {
        const wasm_name_t* name = wasm_exporttype_name(export_types.data[i]);
        // Note: Emscripten adds a leading underscore to C functions
        if (strncmp(name->data, func_name, name->size) == 0) { // got the correct index
            export_func_index = i;
            break;
        }
    }

    if (export_func_index == -1) {
        printf("Error: Function '%s' not found in the Wasm module!\n", func_name);
        return 1;
    }
    log.global_export_cycles += (get_cycles() - cycles_diff_base);
    if (print_flag) {
        cout << "Exported function found. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
    }

    // ---------------------------------------------------------------------------------------

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
    log.arg_cycles += (get_cycles() - cycles_diff_base);
    if (print_flag) {
        cout << "Arguments and results prepared. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
    }


    // ---------------------------------------------------------------------------------------

    for (int i = 0; i < log.instances_logs.size(); i++) {
        if (print_flag) {
            cout << "Instantiating module instance " << (i + 1) << "...\n";
        }
                
        // ---------------------------------------------------------------------------------------
        
        // 7. INSTANTIATE (THE HANDSHAKE)
        cycles_diff_base = get_cycles();
        wasm_instance_t* instance = wasm_instance_new(store, module, &imports, NULL); // last argument is for traps
        if (!instance) {
            printf("Error: Failed to instantiate the module!\n");
            return 1;
        }
        log.instances_logs[i].inst_cycles += (get_cycles() - cycles_diff_base);
        if (print_flag) {
            cout << "Module instantiated successfully. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
        }

        // ---------------------------------------------------------------------------------------
    
        // 8. INITIALIZE THE WASI ENVIRONMENT
        cycles_diff_base = get_cycles();
        wasi_env_initialize_instance(wasi_env, store, instance);
        log.instances_logs[i].init_env += (get_cycles() - cycles_diff_base);
        if (print_flag) {
            cout << "Module instantiated successfully. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
        }

        // ---------------------------------------------------------------------------------------
    
        // 9. FIND THE FUNCTION IN EXPORTS
        cycles_diff_base = get_cycles();
        wasm_extern_vec_t exports;
        wasm_instance_exports(instance, &exports); // doesn't recognize types yet (func, memory, etc.)
         
        wasm_func_t* target_func = wasm_extern_as_func(exports.data[export_func_index]); // cast the instance' export pointer to func
        if (!target_func) {
            printf("Error: Could not find WASM function in exports!\n");
            return 1;
        }
        log.instances_logs[i].local_export_cycles += (get_cycles() - cycles_diff_base);
        if (print_flag) {
            cout << "Exported function found. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
        }

        // ---------------------------------------------------------------------------------------
  
        // 10. THE CALL
        for(uint64_t call_idx = 0; call_idx < call_iterations; call_idx++) {
            cycles_diff_base = get_cycles();
            if (wasm_func_call(target_func, &args, &results)) {
                printf("Error: The Wasm function call failed!\n");
                return 1;
            }
            log.instances_logs[i].call_cycles += (get_cycles() - cycles_diff_base);
            if (print_flag) {
                cout << "Function called successfully. Cycles: " << (get_cycles() - cycles_diff_base) << endl;
            }
        }

        // ---------------------------------------------------------------------------------------
  
        // 11. PRINT THE OUTPUT
        if (print_flag) {
            cout << "Result from WebAssembly: " << results.data[0].of.i32 << endl;
        }

        
        // 12.CLEANUP
        if (args_arr) {
            delete[] args_arr;
        }
        wasm_extern_vec_delete(&exports);
        wasm_instance_delete(instance);
    }
    // wasi_env_delete(wasi_env); 
    // wasm_extern_vec_delete(&wasi_imports);
    wasm_exporttype_vec_delete(&export_types);
    wasm_module_delete(module);
    wasm_store_delete(store);
    wasm_engine_delete(engine);

    return 0;
}


int main() {
    int main_iterations = 50;
    int call_iterations = 100;
    int num_instances = 1;
    bool print_flag = false;
    vector<int> args_vec = {};
    const char* file_name = "./wasm/time.wasm"; 
    const char* func_name = "wasm_time";

    cycles_log_t* log = new cycles_log_t();
    log->instances_logs.resize(num_instances); 

    // call
    for (int i = 0; i < main_iterations; i++) {
        cout << "Running sum_test iteration " << (i + 1) << "...\n";
        test_call(*log, print_flag, args_vec, file_name, func_name, call_iterations);
    }

    // statistics
    devide_cycles_log(*log, main_iterations, call_iterations);
    print_cycles_log(*log);

    // compare direct call
    int x = -1;
    uint64_t direct_call_cycles = 0; 
    uint64_t curr_loop_cycles = 0; 
    for (int i = 0; i < main_iterations*call_iterations; i++) {
        curr_loop_cycles = get_cycles(); 
        (int)time(NULL);
        direct_call_cycles += get_cycles() - curr_loop_cycles;
    }
    cout << "Direct call cycles (average): " << CYCLES_TO_US(direct_call_cycles / (main_iterations*call_iterations)) << " us" << endl;

    delete log;
}
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <iostream>
#include "wasmer.h"

using namespace std;
 
/**
 * @brief Reads the 64-bit Time-Stamp Counter.
 *
 * Returns the number of clock cycles since the last CPU reset.
 */
static inline uint64_t get_cycles() {
    uint32_t low, high;
   
    // "=a" (EAX) and "=d" (EDX) are the output registers for rdtsc.
    // __asm__ __volatile__ prevents the compiler from optimizing out
    // or reordering the instruction incorrectly.
    __asm__ __volatile__ (
        "rdtsc"
        : "=a" (low), "=d" (high)
    );
 
    return ((uint64_t)high << 32) | low;
}



int sum_test() {
    uint64_t cycles_diff_base;

    // 1. LOAD THE WASM FILE
    // We manually read the bytes from the file you compiled with Emscripten
    cycles_diff_base = get_cycles();
    FILE* file = fopen("../wasm_functions/sum.wasm", "rb");
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
    cout << "Wasm file loaded. Cycle: " << (get_cycles() - cycles_diff_base) << endl;

    // 2. SETUP THE ENGINE & STORE
    cycles_diff_base = get_cycles();
    wasm_engine_t* engine = wasm_engine_new();
    wasm_store_t* store = wasm_store_new(engine); // MEM
    cout << "Engine and store created. Cycles: " << (get_cycles() - cycles_diff_base) << endl;

    // 3. COMPILE THE MODULE
    cycles_diff_base = get_cycles();
    wasm_module_t* module = wasm_module_new(store, &wasm_bytes);
    wasm_byte_vec_delete(&wasm_bytes); // Clean up the raw bytes
    if (!module) {
        printf("Error: Failed to compile the Wasm module!\n");
        return 1;
    }
    cout << "Module compiled successfully. Cycles: " << (get_cycles() - cycles_diff_base) << endl;

    // 4. INSTANTIATE (THE HANDSHAKE)
    // Since we aren't using WASI or printing yet, imports are empty
    cycles_diff_base = get_cycles();
    wasm_extern_vec_t imports = WASM_EMPTY_VEC;
    wasm_instance_t* instance = wasm_instance_new(store, module, &imports, NULL); // last argument is for traps
    if (!instance) {
        printf("Error: Failed to instantiate the module!\n");
        return 1;
    }
    cout << "Module instantiated successfully. Cycles: " << (get_cycles() - cycles_diff_base) << endl;

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
        if (strncmp(name->data, "standalone_sum", name->size) == 0) { // got the correct index
            target_func = wasm_extern_as_func(exports.data[i]); // cast the instance' export pointer to func
            break;
        }
    }

    if (!target_func) {
        printf("Error: Could not find function standalone_sum in exports!\n");
        return 1;
    }
    cout << "Exported function found. Cycles: " << (get_cycles() - cycles_diff_base) << endl;

    // 6. PREPARE ARGUMENTS AND RESULTS
    cycles_diff_base = get_cycles();

    /* --- ARGUMENTS SECTION ---
       If your function takes two i32 arguments, change this to:
       wasm_val_t args_val[2] = { WASM_I32_VAL(10), WASM_I32_VAL(20) };
       wasm_val_vec_t args = WASM_ARRAY_VEC(args_val);
    */
    wasm_val_vec_t args = WASM_EMPTY_VEC; 

    // We expect 1 result (the sum)
    wasm_val_t res_val[1] = { WASM_INIT_VAL };
    wasm_val_vec_t results = WASM_ARRAY_VEC(res_val);
    cout << "Arguments and results prepared. Cycles: " << (get_cycles() - cycles_diff_base) << endl;

    // 7. THE CALL
    cycles_diff_base = get_cycles();
    if (wasm_func_call(target_func, &args, &results)) {
        printf("Error: The Wasm function call failed!\n");
        return 1;
    }
    cout << "Function called successfully. Cycles: " << (get_cycles() - cycles_diff_base) << endl;

    // 8. PRINT THE OUTPUT
    printf("Result from WebAssembly: %d\n", results.data[0].of.i32);

    // CLEANUP
    wasm_exporttype_vec_delete(&export_types);
    wasm_extern_vec_delete(&exports);
    wasm_instance_delete(instance);
    wasm_module_delete(module);
    wasm_store_delete(store);
    wasm_engine_delete(engine);

    return 0;
}


int main() {
    return sum_test();
}
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "wasmer.h"

int main() {
    // 1. LOAD THE WASM FILE
    // We manually read the bytes from the file you compiled with Emscripten
    FILE* file = fopen("sum.wasm", "rb");
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

    // 2. SETUP THE ENGINE & STORE
    wasm_engine_t* engine = wasm_engine_new();
    wasm_store_t* store = wasm_store_new(engine); // MEM

    // 3. COMPILE THE MODULE
    wasm_module_t* module = wasm_module_new(store, &wasm_bytes);
    wasm_byte_vec_delete(&wasm_bytes); // Clean up the raw bytes
    if (!module) {
        printf("Error: Failed to compile the Wasm module!\n");
        return 1;
    }

    // 4. INSTANTIATE (THE HANDSHAKE)
    // Since we aren't using WASI or printing yet, imports are empty
    wasm_extern_vec_t imports = WASM_EMPTY_VEC;
    wasm_instance_t* instance = wasm_instance_new(store, module, &imports, NULL); // last argument is for traps
    if (!instance) {
        printf("Error: Failed to instantiate the module!\n");
        return 1;
    }

    // 5. FIND THE FUNCTION IN EXPORTS
    wasm_extern_vec_t exports;
    wasm_instance_exports(instance, &exports); // doesn't recognize types yet (func, memory, etc.)
    
    // We also need the names of the exports (the functions in the guest code) to find ours
    wasm_exporttype_vec_t export_types;
    wasm_module_exports(module, &export_types);

    wasm_func_t* target_func = NULL;
    for (size_t i = 0; i < exports.size; i++) {
        const wasm_name_t* name = wasm_exporttype_name(export_types.data[i]);
        // Note: Emscripten adds a leading underscore to C functions
        if (strncmp(name->data, "_standalone_sum", name->size) == 0) { // got the correct index
            target_func = wasm_extern_as_func(exports.data[i]); // cast the instance' export pointer to func
            break;
        }
    }

    if (!target_func) {
        printf("Error: Could not find function _standalone_sum in exports!\n");
        return 1;
    }

    // 6. PREPARE ARGUMENTS AND RESULTS
    
    /* --- ARGUMENTS SECTION ---
       If your function takes two i32 arguments, change this to:
       wasm_val_t args_val[2] = { WASM_I32_VAL(10), WASM_I32_VAL(20) };
       wasm_val_vec_t args = WASM_ARRAY_VEC(args_val);
    */
    wasm_val_vec_t args = WASM_EMPTY_VEC; 

    // We expect 1 result (the sum)
    wasm_val_t res_val[1] = { WASM_INIT_VAL };
    wasm_val_vec_t results = WASM_ARRAY_VEC(res_val);

    // 7. THE CALL
    printf("Calling Wasm function...\n");
    if (wasm_func_call(target_func, &args, &results)) {
        printf("Error: The Wasm function call failed!\n");
        return 1;
    }

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
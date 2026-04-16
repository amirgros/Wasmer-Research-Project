#include <emscripten.h>
#include <math.h>

extern "C" { 
    EMSCRIPTEN_KEEPALIVE
    int wasm_abs(int x) {
        return fabs(x);
    }

    EMSCRIPTEN_KEEPALIVE
    int wasm_floor(int x) {
        return floor(x);
    }
}
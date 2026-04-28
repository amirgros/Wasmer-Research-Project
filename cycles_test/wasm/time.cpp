#include <emscripten.h>
#include <time.h>

extern "C" { // keep the functions names as they are
    EMSCRIPTEN_KEEPALIVE // don't remove during compilation
    int wasm_time() {
        
        return (int)time(NULL);
    }
}
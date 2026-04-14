#include <emscripten.h>
#include <stdio.h>

extern "C" { // keep the functions names as they are
    EMSCRIPTEN_KEEPALIVE // don't remove during compilation
    int hello() {
        printf("Hello, WebAssembly!\n");
        return 0;
    }
}
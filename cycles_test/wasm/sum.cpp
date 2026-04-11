#include <emscripten.h>

extern "C" { // keep the functions names as they are
    EMSCRIPTEN_KEEPALIVE // don't remove during compilation
    int standalone_sum(){
        return 5 + 7;
    }

    EMSCRIPTEN_KEEPALIVE
    int sum_with_args(int a, int b){
        return a + b;
    }

    EMSCRIPTEN_KEEPALIVE
    // sum 1 to n
    int loop_sum(int n){
        int sum = 0;
        for (int i = 0; i < n; ++i) {
            sum = (sum + i) ^ ((sum << 1) | (i & 3));
        }
        return sum;
    }
}

// emcc sum.cpp -o sum.wasm --no-entry -s EXPORTED_FUNCTIONS="['_standalone_sum', '_sum_with_args']"
// --no-entry: don't generate the main function, since we won't be using it
// -s EXPORTED_FUNCTIONS="['_standalone_sum']": export the standalone_sum function
#ifndef GET_CYCLES_H
#define GET_CYCLES_H

#include <stdint.h>

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
#endif // GET_CYCLES_H
#ifndef _DWT_CLOCK_H
#define _DWT_CLOCK_H
#include <stdint.h>
#include "stm32h723xx.h"
#define CORE_MHZ 480U 
#define DWT_CYCCNT   (*(volatile uint32_t *)0xE0001004)
#define DWT_CTRL     (*(volatile uint32_t *)0xE0001000)
#define DEM_CR       (*(volatile uint32_t *)0xE000EDFC)

void DWT_Init(void);
static inline uint32_t DWT_Cycles(void)
{
    return DWT_CYCCNT;
}
static inline uint32_t Ticks_to_us(uint32_t cycles)
{
    return cycles / CORE_MHZ;
}

#endif

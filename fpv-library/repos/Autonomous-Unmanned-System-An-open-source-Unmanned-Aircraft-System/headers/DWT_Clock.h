#ifndef _DWT_CLOCK_H
#define _DWT_CLOCK_H

#include <stdint.h>

#define CORE_MHZ 480U 
#define DWT_CYCCNT   (*(volatile uint32_t *)0xE0001004)
#define DWT_CTRL     (*(volatile uint32_t *)0xE0001000)
#define DEM_CR       (*(volatile uint32_t *)0xE000EDFC)

void DWT_us_TickInit(void);
uint32_t DWT_Get_us_Ticks(void);
uint32_t DWT_GetCurrentTimeIn_us(void);
uint32_t DWT_CyclesTo_us(uint32_t cycles);

#endif

#include "DWT_Clock.h"
#include "stm32h723xx.h"
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "Clocks.h"



void DWT_us_TickInit(void)
{
    CoreDebug->DEMCR |= (1 << 24);
    DWT->LAR = 0xC5ACCE55;
    DWT->CYCCNT = 0;
    DWT->CTRL |= (1 << 0);
}

uint32_t DWT_Get_us_Ticks(void)
{
    return DWT->CYCCNT;
}

uint32_t DWT_GetCurrentTimeIn_us(void)
{
    return DWT_Get_us_Ticks() / CORE_MHZ;
}

uint32_t DWT_CyclesTo_us(uint32_t cycles)
{
    return cycles / CORE_MHZ;
}























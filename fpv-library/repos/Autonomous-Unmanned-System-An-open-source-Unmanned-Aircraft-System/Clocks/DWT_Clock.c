#include "DWT_Clock.h"
#include "stm32h723xx.h"
#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "Clocks.h"




void DWT_Init(void)
{
    DEM_CR |= (1U << 24);
    DWT_CYCCNT = 0U;
    DWT_CTRL |= (1U << 0);
}






























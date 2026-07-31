#include "dma.h"
#include "stm32h723xx.h"
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stddef.h>



void dma1_clock_config(void)
{
    RCC->AHB1ENR |= (1 << 0);
}


















#include "HIL_Clock_test.h"
#include "stm32h723xx.h"
#include "Clocks.h"
#include "scheduler.h"
#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>


void UT_Cloct_Test(void)
{

    /* configure prescale */ 
    testclocks(MCO1_Prescaler_DIV_BY_1, MCO2_prescaler_DIV_BY_10);
    systemClockConfig_480Mhz();
    DebugLed();
    sysTickConfig_1KHz();
}

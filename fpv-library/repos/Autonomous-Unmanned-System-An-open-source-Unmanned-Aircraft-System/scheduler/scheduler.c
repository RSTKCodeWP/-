#include "DWT_Clock.h"
#include "stm32h723xx.h"
#include "scheduler.h"
#include "Clocks.h"
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>


/*
 * TASK TABLE LAYOUT  
 * { function of task, function name, task period time, task priority is task enabled}
*/ 

#ifdef MOCK_LIST
#include "mock_task.h"

Scheduler_Tasks SchedulerList[MAX_SCH_CNT] = 
{
    {RX_GCS_PAYLOAD_TASK, "Receive GCS Mission Payload task",40,0,true,0,false,0,0,0,false},
    {READ_IMU_TASK, "IMU Task", 1, 0, true,0,false,0,0,0,false},
    {IMU_DSP_TASK, "IMU DSP Task", 1, 0, true,0,false,0,0,0,false},
    {RUN_PID_TASK, "RUN PID TASK", 1, 0, true,0,false,0,0,0,false},
    {LOG_SYSTEM_HEALTH_TASK ,"SYS Health Task",20 ,1 ,true,0,false,0,0,0,false},
    {CHECK_BAT_HEALTH_TASK ,"BAT HEALTH TASK",20 ,1 ,true,0,false,0,0,0,false},
    {CHECK_COMPASS_TASK ,"COMPASS TASK",10 ,1 ,true,0,false,0,0,0,false},
    {ATTITUDE_ESTIMATION_TASK ,"ATT ESTI TASK",10 ,1 ,true,0,false,0,0,0,false},
    {CHECK_GPS_TASK ,"GPS TASK",10,1,true,0,false,0,0,0,false},
    {POSITION_ESTIMATION_TASK,"POS ESTI TASK",10,1,true,0,false,0,0,0,false},
    {FAILSAFE_TASK ,"FAILSAFE TASK",10,1,true,0,false,0,0,0,false},
    {CHECK_WAYPOINT_TASK ,"WAYPOINT TASK",10 ,2,true,0,false,0,0,0,false},
    {ALTHOLD_TASK ,"ALTHOLD TASK",10,2,true,0,false,0,0,0,false},
    {POSHOLD_TASK ,"POSHOLD TASK",10,2,true,0,false,0,0,0,false},
    {GET_Z_AXIS_ACCEL_TASK ," Z-AXIS ACCELEROMETER TASK",2,1,true,0,false,0,0,0,false},
    {GET_BAROMETER_DATA_TASK ,"BAROMETER TASK",20,2,true,0,false,0,0,0,false},
    {ALTITUDE_ESTIMATION_TASK ,"ALT ESTI TASK",8,2,true,0,false,0,0,0,false},
    {TX_TELEMETRY_PAYLOAD_TASK ,"TELEMETRY TASK",4,2,true,0,false,0,0,0,false},
}; 
#else
Scheduler_Tasks SchedulerList[MAX_SCH_CNT] = 
{
    {RX_GCS_PAYLOAD_TASK, "Receive GCS Mission Payload task",40,0,true,0,false,0,0,0,false},
    {READ_IMU_TASK, "IMU Task", 1, 0, true,0,false,0,0,0,false},
    {IMU_DSP_TASK, "IMU DSP Task", 1, 0, true,0,false,0,0,0,false},
    {RUN_PID_TASK, "RUN PID TASK", 1, 0, true,0,false,0,0,0,false},
    {LOG_SYSTEM_HEALTH_TASK ,"SYS Health Task",20 ,1 ,true,0,false,0,0,0,false},
    {CHECK_BAT_HEALTH_TASK ,"BAT HEALTH TASK",20 ,1 ,true,0,false,0,0,0,false},
    {CHECK_COMPASS_TASK ,"COMPASS TASK",10 ,1 ,true,0,false,0,0,0,false},
    {ATTITUDE_ESTIMATION_TASK ,"ATT ESTI TASK",10 ,1 ,true,0,false,0,0,0,false},
    {CHECK_GPS_TASK ,"GPS TASK",10,1,true,0,false,0,0,0,false},
    {POSITION_ESTIMATION_TASK,"POS ESTI TASK",10,1,true,0,false,0,0,0,false},
    {FAILSAFE_TASK ,"FAILSAFE TASK",10,1,true,0,false,0,0,0,false},
    {CHECK_WAYPOINT_TASK ,"WAYPOINT TASK",10 ,2,true,0,false,0,0,0,false},
    {ALTHOLD_TASK ,"ALTHOLD TASK",10,2,true,0,false,0,0,0,false},
    {POSHOLD_TASK ,"POSHOLD TASK",10,2,true,0,false,0,0,0,false},
    {GET_Z_AXIS_ACCEL_TASK ," Z-AXIS ACCELEROMETER TASK",2,1,true,0,false,0,0,0,false},
    {GET_BAROMETER_DATA_TASK ,"BAROMETER TASK",20,2,true,0,false,0,0,0,false},
    {ALTITUDE_ESTIMATION_TASK ,"ALT ESTI TASK",8,2,true,0,false,0,0,0,false},
    {TX_TELEMETRY_PAYLOAD_TASK ,"TELEMETRY TASK",4,2,true,0,false,0,0,0,false},
}; 
#endif


uint8_t SchedulerList_Length = sizeof(SchedulerList) / sizeof(SchedulerList[0]);
/* private globals */ 
static Scheduler_health healthStatus = {0};

/*
 * ===========================================================================
 *  sysTickConfig_1KHz -- SysTick interrupt firing every 1ms (1kHz)
 * ===========================================================================
 *  SysTick's CLKSOURCE bit is documented (RM0468/PM0253) as selecting
 *  between the processor clock (HCLK) and HCLK/8, but multiple ST
 *  community reports on H7-class silicon found CLKSOURCE doesn't behave
 *  as documented -- some saw SysTick running at the raw HCLK regardless
 *  of the bit, contradicting the /8 reference-clock path entirely. To
 *  sidestep that ambiguity, this function explicitly sets CLKSOURCE=1
 *  (processor clock / HCLK direct) and computes the reload value
 *  directly from HCLK -- the well-tested, portable choice used in the
 *  overwhelming majority of real SysTick examples across the whole
 *  STM32 family, regardless of this H7-specific documentation quirk.
 *
 *  Reload math: with HPRE=/2 on a 480MHz SYSCLK (per
 *  systemClockConfig_480Mhz), HCLK = 240MHz.
 *    RELOAD = (HCLK / target_Hz) - 1 = (240,000,000 / 1000) - 1 = 239999
 *  SysTick fires on the 1 -> 0 transition, so RELOAD+1 cycles actually
 *  elapse per tick -- 240000 cycles @ 240MHz = exactly 1.000ms.
 *
 *  SYST_RVR is a 24-bit register (max 0x00FFFFFF = 16,777,215); 239999
 *  fits comfortably.
 *
 *  IMPORTANT: call this AFTER systemClockConfig_480Mhz(), not before --
 *  unlike the MCO test functions, SysTick's reload value is computed
 *  from the ASSUMPTION that HCLK is already 240MHz. Calling this first
 *  would compute the reload against whatever HCLK was at reset (HSI-
 *  derived, much slower), giving a far slower-than-intended tick rate
 *  once the real clock config later kicks in.
 *
 *  You must also define a SysTick_Handler() somewhere in your project --
 *  the NVIC/CMSIS startup file expects that exact name in the vector
 *  table. This function only configures the timer; it does not define
 *  the handler itself.
 * ===========================================================================
 */


uint32_t Scheduler_get_us(void)
{
    return (DWT_Cycles() / CORE_MHZ);
}


void sysTickConfig_1KHz(void)
{
    const uint32_t HCLK_HZ = 240000000U; /* matches HPRE=/2 on 480MHz SYSCLK */
    const uint32_t TARGET_HZ = 1000U;    /* 1kHz = 1ms period */
    const uint32_t reload = (HCLK_HZ / TARGET_HZ) - 1U;
 
    SysTick->CTRL &= ~SysTick_CTRL_ENABLE_Msk; /* stop the timer while reconfiguring */
 
    SysTick->LOAD = reload;                    /* SYST_RVR: 24-bit reload value */

    SysTick->VAL  = 0U;                        /* SYST_CVR: clear current value
                                                    so the first period is full-length,
                                                    not whatever was left over */
 
    SysTick->CTRL = SysTick_CTRL_CLKSOURCE_Msk /* processor clock (HCLK), see note above */
                  | SysTick_CTRL_TICKINT_Msk   /* enable the SysTick exception */
                  | SysTick_CTRL_ENABLE_Msk;   /* start counting */
}

static volatile uint32_t msTicks = 0U;

void DebugLed(void)
{
    RCC->AHB4ENR |= (1 << 5); /* turning on clock for port F */
    GPIOF->MODER |= (1 << 8); /* use GPIOF Pin 4 */
    GPIOF->OTYPER &= ~(1 << 4);
    GPIOF->OSPEEDR |= (0b011 << 8);

}
 
void SysTick_Handler(void)
{
    GPIOF->ODR ^= (1 << 4);
    //printf("ms tick count: %d/n",msTicks);

    uint32_t currentTick = msTicks++;
    
    healthStatus.TotalTickTime = currentTick;

    for(uint8_t i = 0; i < SchedulerList_Length; i++)
    {
        Scheduler_Tasks *CurrentTask = &SchedulerList[i];

        if(!CurrentTask->isTaskEnabled)
        {
            continue;
        }

        if((uint16_t)(currentTick - CurrentTask->last_tick) >= CurrentTask->taskperiod)
        {
            if(CurrentTask->isTaskPending)
            {
                /* pervious task has not finished: missed_deadlines*/ 
                healthStatus.missed_deadlines++;
            }

            CurrentTask->isTaskPending = true;
        }
    }
}

/* =========================================================================
 * Superloop dispatcher
 * =========================================================================
 *
 * This function never returns.  Call it at the end of main() after all
 * peripherals and drivers are initialised.
 *
 * Execution model
 * ───────────────
 *  Each iteration of the outer while(1):
 *    1. Toggle the timing GPIO high (oscilloscope measurement point).
 *    2. Walk the task table in index order.
 *    3. For each pending task:
 *         a. Record start cycle count.
 *         b. Call the task function.
 *         c. Compute elapsed µs.
 *         d. Update max_exec_us and overrun counter.
 *         e. Mark task not pending, update last_tick, increment exec_count.
 *    4. Toggle the timing GPIO low.
 *    5. If no task was pending this iteration, execute WFI to save power.
 *
 * Overrun handling
 * ────────────────
 *  If a task exceeds SCHEDULER_OVERRUN_US the overrun counter increments.
 *  The task still completes – we don't pre-empt it.  Connect a logic
 *  analyser to SCHED_TIMING_PIN and filter for pulses longer than your
 *  budget to catch overruns in flight.
 */

void Scheduler_Init(void)
{
    /*init the DWT counter*/
    DWT_Init();
    /* init the Watchdog timers Tim7 deadman & IWDG */ 

    /*initialize SchedulerList variables*/
    for(uint8_t i = 0; i < SchedulerList_Length; i++)
    {
        SchedulerList[i].isTaskPending = false;
        SchedulerList[i].last_tick = (uint16_t)msTicks;
        SchedulerList[i].current_ticks = 0;
        SchedulerList[i].overruns = 0;
        SchedulerList[i].MaxTaskTime = 0;
        SchedulerList[i].flaggedstuck = false;
    }
    /* stagger initial tick count, so all high-rate tasks don't fire together
     * on the very first tick.  Offset each by (index * 1) ms so they
     * naturally spread across the first 16 ms window.*/ 
    for(uint8_t i = 0; i < SchedulerList_Length; i++)
    {
        SchedulerList[i].last_tick = (uint16_t)(msTicks - (i & 0x0F));
    }
}
/* Returns the current millisecond tick count. Rollover-safe when used
 * with subtraction-based timeout comparisons (see note above). */
uint32_t millis(void)
{
    return msTicks;
}
 
/* Simple blocking delay, built on the tick counter. Rollover-safe by
 * construction since it uses subtraction, not a target value. Mainly
 * useful for bring-up/debug; prefer non-blocking millis()-based checks
 * in real application code so the CPU isn't stuck spinning. */
void delay_ms(uint32_t ms)
{
    uint32_t start = millis();
    while ((millis() - start) < ms) { }
}
 













#include "DWT_Clock.h"
#include "stm32h723xx.h"
#include "scheduler.h"
#include "Clocks.h"
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#define TASK_OVERRUN 200U 
//extern Scheduler_health healthStatus;


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
    {TX_TELEMETRY_PAYLOAD_TASK ,"TELEMETRY TASK",4,2,true,0,false,0,0,0,false}
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

//extern Scheduler_Tasks SchedulerList[MAX_SCH_CNT];
uint8_t SchedulerList_Length = sizeof(SchedulerList) / sizeof(SchedulerList[0]);
Scheduler_health healthStatus = {0};

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

    /* init the Watchdog timers Tim3 deadman & IWDG */ 

    /*initialize SchedulerList variables*/
    for(uint8_t i = 0; i < SchedulerList_Length; i++)
    {
        SchedulerList[i].isTaskPending = false;
        SchedulerList[i].last_tick = msTicks;
        SchedulerList[i].TaskCount = 0;
        SchedulerList[i].overruns = 0;
        SchedulerList[i].MaxTaskTime = 0;
        SchedulerList[i].flaggedstuck = false;
    }
    /* stagger initial tick count, so all high-rate tasks don't fire together
     * on the very first tick.  Offset each by (index * 1) ms so they
     * naturally spread across the first 16 ms window.*/ 
    for(uint8_t i = 0; i < SchedulerList_Length; i++)
    {
        SchedulerList[i].last_tick = (msTicks - (i & 0x0F));
    }
}

void SchedulerRun(void)
{
    while(1)
    {
        uint32_t StartSchedulerTime = DWT_Get_us_Ticks();

        for(uint16_t i = 0; i < SchedulerList_Length; i++)
        {
            Scheduler_Tasks *runningTaskList = &SchedulerList[i];

            if(!runningTaskList[i].isTaskPending)
            {
                continue;
            }
            
            uint32_t TaskStartTime = DWT_Get_us_Ticks();
        
            StartTaskStopWatch();
            runningTaskList[i].task_func();
            StartTaskStopWatch();
            
            uint32_t ElaspedTimeIn_us = DWT_CyclesTo_us((DWT_Get_us_Ticks() - TaskStartTime));
            
            runningTaskList[i].isTaskPending = false;
            runningTaskList[i].last_tick = msTicks;
            runningTaskList[i].TaskCount++;

            if(ElaspedTimeIn_us > TASK_OVERRUN)
            {
                runningTaskList[i].overruns++;
                /*TODO: error handling for task overruns */ 
            }

            if(ElaspedTimeIn_us > runningTaskList[i].MaxTaskTime)
            {
                runningTaskList[i].MaxTaskTime = ElaspedTimeIn_us;
                /*TODO: error handling for missed task deadlines*/ 
            }
        }

        Toggle_IWTDG();
        /* calculate worst case loop time */ 
        uint32_t WorstCaseLoopTime = DWT_CyclesTo_us(DWT_Get_us_Ticks() - StartSchedulerTime);
        
        if(WorstCaseLoopTime > healthStatus.max_loop_time)
        {
            healthStatus.max_loop_time = WorstCaseLoopTime;
            /* TODO: error handling for worst case loop time. */ 
        }
    }
}







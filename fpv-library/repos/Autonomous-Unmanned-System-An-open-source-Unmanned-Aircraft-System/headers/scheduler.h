#ifndef _SCHEDULER_H_
#define _SCHEDULER_H_

#include <stdint.h>
#include <stdbool.h>
#define MAX_SCH_CNT 18 
#define MOCK_LIST 1 
/* 1 tick = 1 ms from SysTick ISR Handler
 * 1 ms = 1000 HZ
 * 4 ms = 250 HZ
 * 5 ms = 200 HZ
 * 10 ms = 100 HZ
 * 20 ms = 50 HZ
 * 100 ms = 10 HZ
 * 1000 ms = 1 HZ
 */ 
typedef void (*Task_Func)(void);
typedef struct 
{
    Task_Func task_func; /* function entry point */ /* must allocate memory on init*/  
    const char *taskName; /* task function name for debug printf*/ /* must allocate memory on init */  
    uint16_t taskperiod; /* amount of time each task will execute*/ 
    uint8_t taskpriority; /* 0 = highest priority*/ 
    bool isTaskEnabled; /* false = task is registered but execution is skipped*/ 
    volatile uint32_t last_tick;
    volatile bool isTaskPending;
    uint32_t TaskCount;
    uint32_t overruns;
    uint32_t MaxTaskTime;
    bool flaggedstuck;
}Scheduler_Tasks;
extern Scheduler_Tasks SchedulerList[MAX_SCH_CNT];
extern uint8_t SchedulerList_Length;

typedef struct
{
    uint32_t  TotalTickTime;
    uint32_t missed_deadlines;
    uint32_t max_loop_time;
    const char *currentTaskname; /* must allocate memory on init */ 
    const char *currentFlightMode; /* must allocate memory on init */ 

}Scheduler_health;
extern Scheduler_health healthStatus;

void Scheduler_Init(void);
void SchedulerRun(void);
uint32_t Scheduler_get_us(void);


#endif

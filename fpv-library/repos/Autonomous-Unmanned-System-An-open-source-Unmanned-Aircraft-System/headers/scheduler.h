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
    volatile uint16_t last_tick;
    volatile bool isTaskPending;
    uint32_t current_ticks;
    uint32_t overruns;
    uint32_t MaxTaskTime;
    bool flaggedstuck;
}Scheduler_Tasks;

typedef struct
{
    uint32_t  TotalTickTime;
    uint32_t missed_deadlines;
    uint32_t max_loop_time;
    const char *currentTaskname; /* must allocate memory on init */ 
    const char *currentFlightMode; /* must allocate memory on init */ 

}Scheduler_health;

void Scheduler_Init(void);
uint32_t Scheduler_get_us(void);
void sysTickConfig_1KHz(void);
void SysTick_Handler(void);
void delay_ms(uint32_t ms);
void DebugLed(void);
uint32_t millis(void);


#endif

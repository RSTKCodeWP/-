#include "stm32h723xx.h"
#include "Clocks.h"
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include "scheduler.h"

volatile uint32_t msTicks = 0U;
/*
 * ===========================================================================
 *  sysTickConfig_1KHz -- SysTick interrupt firing every 1ms (1kHz)
 * ===========================================================================
 *  Reload math: with HPRE=/2 on a 480MHz SYSCLK (per
 *  systemClockConfig_480Mhz), HCLK = 240MHz.
 *    RELOAD = (HCLK / target_Hz) - 1 = (240,000,000 / 1000) - 1 = 239999
 *  SysTick fires on the 1 -> 0 transition, so RELOAD+1 cycles actually
 *  elapse per tick -- 240000 cycles @ 240MHz = exactly 1.000ms.
 *
 * ===========================================================================
 */

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





void DebugLed(void)
{
    //RCC->AHB4ENR |= (1 << 5); /* turning on clock for port F */
    //GPIOF->MODER |= (1 << 8); /* use GPIOF Pin 4 */
    //GPIOF->OTYPER &= ~(1 << 4);
    //GPIOF->OSPEEDR |= (0b011 << 8);

    RCC->AHB4ENR |= (1U << 1); /* turn on clock for port B */
    GPIOB->MODER &= ~(3U << 0);
    GPIOB->MODER |= (1U << 0); /* use GPIOB pin 0 */ 
    GPIOB->OTYPER &= ~(1U << 0);
    GPIOB->PUPDR &= ~(3U << 0);



}
 
void SysTick_Handler(void)
{
    GPIOB->ODR ^= (1 << 0); 
    //printf("ms tick count: %d/n",msTicks);

    uint32_t currentTick = ++msTicks;
    
    healthStatus.TotalTickTime = currentTick;

    for(uint8_t i = 0; i < SchedulerList_Length; i++)
    {
        Scheduler_Tasks *CurrentTask = &SchedulerList[i];

        if(!CurrentTask->isTaskEnabled)
        {
            continue;
        }

        if((currentTick - CurrentTask->last_tick) >= CurrentTask->taskperiod)
        {
            if(CurrentTask->isTaskPending)
            {
                /* pervious task has not finished: missed_deadlines*/ 
                healthStatus.missed_deadlines++;
                CurrentTask->last_tick += CurrentTask->taskperiod; /* re-arm: count once per period */
                /*TODO: error handling to log which task missed deadline. */ 
                
            }

            CurrentTask->isTaskPending = true;
        }
    }
}
/*
* System core clock configuration functions;
* TIMER 3 @ 10ms timeout configuration; 
* Testclocks function for PLL clock Hardware testing;
* Independent watch dog initialize( 100 ms timeout)
*/ 


/* TIMER 3 configuration*/ 
void Timer3Init(void)
{
    /*config port B and peripheral clock for TIMER 3 */
    RCC->AHB4ENR |= (1 << 1);
    RCC->APB1LENR |= (1 << 1);
    /* config PORTB GPIO0 for alt function. */
    GPIOB->MODER &= ~(3U << 0);
    GPIOB->MODER |= (1 << 1);
    GPIOB->AFR[0] &= ~(0x0F << 0);
    GPIOB->AFR[0] |= (1 << 1);
    /*initialize timer 3: timer will start disabled, and start with the (StartTaskStopWatch) function */ 
    TIM3->CR1 &= ~(1 << 0); // disable the timer 3 
    TIM3->CR1 |= (1 << 3); // one-pulse mode 
    TIM3->CR1 &= ~(1 << 4); // upcounter mode 
    TIM3->DIER |= (1 << 0); // update interrupt enabled  
    TIM3->PSC = (240U - 1U); // 240 MHZ / 240 = 1 MHZ = 1 us tick; 
    TIM3->ARR = 10000U;       // timeout val: 10000 = 10ms; 1 tick = 1 us 
    TIM3->SR = 0;  // clear any pending flags
    NVIC_SetPriority(TIM3_IRQn,0); // highest priority set. 
    NVIC_EnableIRQ(TIM3_IRQn); // enable the interrupt. 
}

void TIM3_IRQHandler(void)
{
    TIM3->SR = 0;  // clear any pending flags
}
/* configure Independent watchdog: WDG will reset if not toggled in 100ms */ 
void IWTDG_Init(void)
{
   IWDG1->KR = 0x5555;
   IWDG1->PR |= (3U << 0);
   IWDG1->RLR = 100U;
   while((IWDG1->SR & 0x0F) != 0){}
   IWDG1->KR = 0xAAAA;
   IWDG1->KR = 0xCCCC;
}

void Toggle_IWTDG(void)
{
    /*TODO: error handling for which task hung and caused watchdog failure*/ 
    IWDG1->KR = 0xAAAA;
}

void StartTaskStopWatch(void)
{

    TIM3->CR1 &= ~(1 << 0); // disable the timer 3
    TIM3->CNT = 0;
    TIM3->SR = 0;
    TIM3->CR1 |= (1 << 0);
}

void EndTaskStopWatch(void)
{
    TIM3->CR1 &= ~(1 << 0); // disable the timer 3
}

void systemClockConfig_480Mhz(void)
{
    // Turn on HSI RCC->CR
    RCC->CR |= (1 << 0);
    // check if its ready

    while(!(RCC->CR & (1 << 2))){}

    /* 2. select the HSI as the PLLs clock source RCC->PLLCKS1ELR*/
    RCC->PLLCKSELR &= ~(1 << 0);
    /* --- PLL1: DIVM1=4 -> 16MHz input RCC->PLLCKSELR -------------------------------- */
    RCC->PLLCKSELR |= (4U << 4);
    /* --- PLL2: DIVM2=4 -> 16MHz input RCC->PLLCKSELR -------------------------------- */
    RCC->PLLCKSELR |= (4U << 12);
    /* --- PLL3: DIVM3=4 -> 16MHz input RCC->PLLCKSELR -------------------------------- */
    RCC->PLLCKSELR |= (4U << 20);
    /* PLL1 input freq range, VCO selection, fractional latch enable RCC->PLLCFGR */
    RCC->PLLCFGR |= (3U << 2);
    RCC->PLLCFGR &= ~(1 << 1);
    RCC->PLLCFGR &= ~(1 << 0);
    /* PLL2 input freq range, VCO selection, fractional latch enable RCC->PLLCFGR */
    RCC->PLLCFGR |= (3U << 6);
    RCC->PLLCFGR &= ~(1U << 5);
    RCC->PLLCFGR &= ~(1U << 4);
    /* PLL3 input freq range, VCO selection, fractional latch enable RCC->PLLCFGR */
    RCC->PLLCFGR |= (3U << 10);
    RCC->PLLCFGR &= ~(1U << 9);
    RCC->PLLCFGR &= ~(1U << 8);
    /* Enable the output dividers we use: PLL1: P only (SYSCLK) RCC->PLLCFGR */
    RCC->PLLCFGR |= (1U << 16); // p clk 
    RCC->PLLCFGR |= (1U << 17); // Q clk 
    /* Enable the output dividers we use: PLL2: P, Q, R (P drives SPI1/2/3 kernel; Q/R enabled for future use) */
    RCC->PLLCFGR |= (1U << 19); // P
    RCC->PLLCFGR |= (1U << 20); // Q not used
    RCC->PLLCFGR |= (1U << 21); // R not used 
    /* Enable the output dividers we use: PLL3: P,Q,R (R drives I2C1/2/3 kernel; Q drives SPI4/5 kernel;(P enabled for future use) RCC->PLLCFGR */ 
    RCC->PLLCFGR |= (1U << 22); // P not used 
    RCC->PLLCFGR |= (1U << 23); // Q 
    RCC->PLLCFGR |= (1U << 24); // R 
    /*PLL1DIVR: DIVN1=60, DIVP1=2 -> VCO 960MHz, SYSCLK 480MHz ----- RCC->PLL1DIVR */
    RCC->PLL1DIVR |= ((60U - 1U) << 0); // 960 MHZ 
    RCC->PLL1DIVR |= (1U << 9);  // P clk @ 480 MHZ 
    RCC->PLL1DIVR |= ((100U - 1U) << 16); // Q clk @ 9 MHZ 
    RCC->PLL1FRACR = 0;
    /*PLL2DIVR: DIVN2=15 -> VCO 240MHz exactly DIVP2=10 -> 24MHz (SPI1/2/3 kernel), DIVQ2=24 -> 10MHz, DIVR2=48 -> 5MHz RCC->PLL2DIVR */
    RCC->PLL2DIVR |= ((15U - 1U) << 0); // 240 MHZ 
    RCC->PLL2DIVR |= ((10U - 1U) << 9);// P clk output: 24 MHZ (SPI 1) 
    RCC->PLL2DIVR |= ((24U - 1U) << 16);// Q clk output 10 MHZ (not used) 
    RCC->PLL2DIVR |= ((48U - 1U) << 24);// R clk output 5 MHZ (not used)
    RCC->PLL2FRACR = 0;
     /*PLL3DIVR: DIVN3=15 -> VCO 240MHz exactly DIVP3=5 -> 48MHz, DIVQ3=24 -> 10MHz (SPI4/5 kernel, halved by
       SPI's mandatory /2 minimum divider to land at 5MHz exact at SCK),DIVR3=5 -> 48MHz (I2C1/2/3 kernel) RCC->PLL3DIVR */
    RCC->PLL3DIVR |= ((15U - 1U) << 0);// 240 MHZ 
    RCC->PLL3DIVR |= ((5U  - 1U) << 9); // P clk output 48 MHZ 
    RCC->PLL3DIVR |= ((24U - 1U) << 16);// Q clk output 10 MHZ (SPI 4: will half to 5 MHZ)
    RCC->PLL3DIVR |= ((5U  - 1U) << 24);// R clk output 48 MHZ (I2C1)
    RCC->PLL3FRACR = 0;
     /*    Turn on PLL1, PLL2, PLL3 and wait for all three to lock */
    RCC->CR |= ((1 << 24) | (1 << 26) | (1 << 28));
    while(!(RCC->CR & (1 << 25))){}
    while(!(RCC->CR & (1 << 27))){}
    while(!(RCC->CR & (1 << 29))){}
    /*
     * Bus prescalers BEFORE switching SYSCLK source.
     * Example: AHB = SYSCLK/2 = 240MHz, APBx = AHB/2 = 120MHz.
     * Adjust to your actual bus speed requirements.
       RCC->D1CFGR  */
    RCC->D1CFGR |= (8U << RCC_D1CFGR_HPRE_Pos);    /* HPRE  = /2  -> HCLK 240MHz */ 
    RCC->D1CFGR |= (8U << 0U);                     /* AHB/1/2/3/4  = / 2 -> 120MHZ */ 
    RCC->D1CFGR |= (4U << RCC_D1CFGR_D1PPRE_Pos);  /* APB3  = /2  -> 120MHz      */
    RCC->D2CFGR |= (4U << RCC_D2CFGR_D2PPRE1_Pos); /* APB1  = /2  -> 120MHz      */
    RCC->D2CFGR |= (4U << RCC_D2CFGR_D2PPRE2_Pos); /* APB2  = /2  -> 120MHz      */
    RCC->D3CFGR |= (4U << RCC_D3CFGR_D3PPRE_Pos);  /* APB4  = /2  -> 120MHz      */

    
    /* Switch SYSCLK source to PLL1 and confirm the switch took RCC->CFGR */
    RCC->CFGR |= (3U << 0); // sysClk routed to PLL1(P clk output) = 480 MHZ
    while ((RCC->CFGR & RCC_CFGR_SWS_Msk) != RCC_CFGR_SWS_PLL1) { }
}

 
void testclocks(int MCO1_prescale_val,int MCO1_Clock_Source, int MCO2_prescale_val,int MCO2_Clock_Source)
{
            /* MCO1 setup*/ //PA8 
            RCC->AHB4ENR |= (1U << 0); /* GPIOAEN */
            GPIOA->MODER &= ~(3U << (8*2));
            GPIOA->MODER |=  (2U << (8*2));        /* alternate function */
            GPIOA->AFR[1] &= ~(0xFU << ((8-8)*4));
            GPIOA->AFR[1] |=  (0x0U << ((8-8)*4)); /* AF0 = MCO */
            GPIOA->OSPEEDR |= (3U << (8*2));

            RCC->CFGR &= ~RCC_CFGR_MCO1_Msk;
            RCC->CFGR |=  (MCO1_Clock_Source << 22); /* 011 = PLL1Q */
            RCC->CFGR &= ~RCC_CFGR_MCO1PRE_Msk;
            RCC->CFGR |=  (MCO1_prescale_val << 18); /* /15 */



            /* MCO2 setup */ 
          
            RCC->AHB4ENR |= (1U << 2); /* GPIOCEN -- MCO2 is on PC9 */
            GPIOC->MODER &= ~(3U << (9*2));
            GPIOC->MODER |=  (2U << (9*2));
            GPIOC->AFR[1] &= ~(0xFU << ((9-8)*4));
            GPIOC->AFR[1] |=  (0x0U << ((9-8)*4)); /* AF0 = MCO */
            GPIOC->OSPEEDR |= (3U << (9*2)); 

            RCC->CFGR &= ~RCC_CFGR_MCO2_Msk;            
            RCC->CFGR |= (MCO2_Clock_Source << 29); 
            RCC->CFGR &= ~RCC_CFGR_MCO2PRE_Msk;
            RCC->CFGR |=  (MCO2_prescale_val << 25);
}
  

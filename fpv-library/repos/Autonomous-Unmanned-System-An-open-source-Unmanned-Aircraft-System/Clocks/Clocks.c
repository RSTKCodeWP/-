#include "stm32h723xx.h"
#include "Clocks.h"
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>




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
    RCC->D1CFGR |= (4U << RCC_D1CFGR_D1PPRE_Pos);  /* APB3  = /2  -> 120MHz      */
    RCC->D2CFGR |= (4U << RCC_D2CFGR_D2PPRE1_Pos); /* APB1  = /2  -> 120MHz      */
    RCC->D2CFGR |= (4U << RCC_D2CFGR_D2PPRE2_Pos); /* APB2  = /2  -> 120MHz      */
    RCC->D3CFGR |= (4U << RCC_D3CFGR_D3PPRE_Pos);  /* APB4  = /2  -> 120MHz      */
    
    /* Switch SYSCLK source to PLL1 and confirm the switch took RCC->CFGR */
    RCC->CFGR |= (3U << 0); // sysClk routed to PLL1(P clk output) = 480 MHZ
    while ((RCC->CFGR & RCC_CFGR_SWS_Msk) != RCC_CFGR_SWS_PLL1) { }
}

 
void testclocks(int MCO1_prescale_val, int MCO2_prescale_val)
{
            /* MCO1 setup*/ //PA8 
            RCC->AHB4ENR |= (1U << 0); /* GPIOAEN */
            GPIOA->MODER &= ~(3U << (8*2));
            GPIOA->MODER |=  (2U << (8*2));        /* alternate function */
            GPIOA->AFR[1] &= ~(0xFU << ((8-8)*4));
            GPIOA->AFR[1] |=  (0x0U << ((8-8)*4)); /* AF0 = MCO */
            GPIOA->OSPEEDR |= (3U << (8*2));

            RCC->CFGR &= ~RCC_CFGR_MCO1_Msk;
            RCC->CFGR |=  (0x3U << RCC_CFGR_MCO1_Pos); /* 011 = PLL1Q */
            RCC->CFGR &= ~RCC_CFGR_MCO1PRE_Msk;
            RCC->CFGR |=  (MCO1_prescale_val << RCC_CFGR_MCO1PRE_Pos); /* /15 */



            /* MCO2 setup */ 
          
            RCC->AHB4ENR |= (1U << 2); /* GPIOCEN -- MCO2 is on PC9, NOT PA9 */
            GPIOC->MODER &= ~(3U << (9*2));
            GPIOC->MODER |=  (2U << (9*2));
            GPIOC->AFR[1] &= ~(0xFU << ((9-8)*4));
            GPIOC->AFR[1] |=  (0x0U << ((9-8)*4)); /* AF0 = MCO */
            GPIOC->OSPEEDR |= (3U << (9*2)); 

            RCC->CFGR &= ~RCC_CFGR_MCO2_Msk;            
            RCC->CFGR |= (0x3U << RCC_CFGR_MCO2_Pos); 
            RCC->CFGR &= ~RCC_CFGR_MCO2PRE_Msk;
            RCC->CFGR |=  (MCO2_prescale_val << RCC_CFGR_MCO2PRE_Pos);
}
  

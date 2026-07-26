#include "stm32h723xx.h"
#include "SPI.h"
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include "stdbool.h"





void SPI_1_2_ClockConfig()
{
    /* SPI 1 clock source selsection RCC->D2CCIP2R */
    RCC->D2CCIP1R |= (1 << 12); // PLL2 P clk output
    /* SPI 1 enable clock */
    RCC->APB2ENR |= (1 <<12);
    /* SPI 2 enable clock */ 
    RCC->APB1LENR |= (1 << 14);
}

void SPI_4_ClockConfig()
{
    /*SPI 4 clock source selection RCC->D2CCIP2R */
    RCC->D2CCIP1R |= (2 << 16);// PLL3 Q clk output 
    /*SPI 4 enable clock*/ 
    RCC->APB2ENR |= (1 << 13);
}


void SPI_1_Clock_24MHZ()
{

}
void SPI_2_Clock_10MHZ()
{

}
void SPI_4_Clock_5MHZ()
{

}

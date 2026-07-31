#include "stm32h723xx.h"
#include "SPI.h"
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include "stdbool.h"

#define GY_ICM_2048V2

#ifdef GY_ICM_2048V2
/* dev board testing */ 
void SPI_Init(void)
{
    /* enable Port A and Port B peripheral clock source */
    RCC->AHB4ENR |= (3U << 0);

    /* config GPIOs & set to Alt.func 5 */ 
    GPIOA->MODER &= ~(3U << 8);  /* clear PA4 SPI1 Chip select */ 
    GPIOB->MODER &= ~(3U << 8);  /* clear PB4 SPI1 MISO */ 
    GPIOB->MODER &= ~(3U << 6);  /* clear PB3 SPI1 SCK */ 
    GPIOB->MODER &= ~(3U << 10); /* clear PB5 SPI1 MOSI */ 

    
    GPIOA->MODER |= (2U << 8);  /* PA4 SPI1 Chip select */ 
    GPIOB->MODER |= (2U << 8);  /* PB4 SPI1 MISO */ 
    GPIOB->MODER |= (2U << 6);  /* PB3 SPI1 SCK */ 
    GPIOB->MODER |= (2U << 10); /* PB5 SPI1 MOSI */

    GPIOA->OTYPER &= ~(1 << 4); /* output push pull */ 
    GPIOB->OTYPER &= ~(1 << 4); /* output push pull */ 
    GPIOB->OTYPER &= ~(1 << 3); /* output push pull */ 
    GPIOB->OTYPER &= ~(1 << 5); /* output push pull */

    
    GPIOA->PUPDR &= ~(3U << 8);  /* no pu/pd PA4  */ 
    GPIOB->PUPDR &= ~(3U << 8);  /* no pu/pd PB4  */ 
    GPIOB->PUPDR &= ~(3U << 6);  /* no pu/pd PB3  */ 
    GPIOB->PUPDR &= ~(3U << 10); /* no pu/pd PB5 */

    GPIOB->AFR[0] &= ~(0x0F << 12);
    GPIOB->AFR[0] |= (5U << 12);  /* SPI1 SCK PB3 */ 

    GPIOB->AFR[0] &= ~(0x0F << 16);
    GPIOB->AFR[0] |= (5U << 16);  /* SPI1 MISO PB4 */ 
    
    GPIOB->AFR[0] &= ~(0x0F << 20);
    GPIOB->AFR[0] |= (5U << 20);  /* SPI1 MOSI PB5 */

    GPIOA->AFR[0] &= ~(0x0F << 16);
    GPIOA->AFR[0] |= (5U << 16);  /* SPI1 Chip select PA4 */

    /* Set up SPI1 */
    SPI1->CFG1 &= ~(1U << 22); /* disable CRC */ 
    SPI1->CFG1 |= ((1U << 28)  /* Clock Rate @ 6-7 MHZ*/ 
                | (1U << 15)  /* TX DMA Enabled*/ 
                | (1U << 14)  /* RX DMA Enabled*/ 
                | (15U << 5)  /* FIFO: 16bits*/ 
                | (15U << 0)); /* SPI data framwe: 16bits*/

    SPI1->CFG2 &= ~((1U << 30)     /* CS is kept at active level till data transfer is completed. */ 
                |   (1U << 28)     /* CS is Active-Low */ 
                |   (1U << 25)     /* CPOL = 0 */ 
                |   (1U << 24)     /* CPHA = 0 */ 
                |   (1U << 23)     /* MSB transmitted first */ 
                |   (7U << 19)    /* SPI in Motorola mode */ 
                |   (3U << 17)    /* Full Duplex mode */ 
                |   (1U << 15)     /* No SWAP */
                |   (0x0F << 4)   /* no Delay */ 
                |   (0x0F << 0)); /* no extra delay */ 

    SPI1->CFG2 |=  ((1U << 31)  /* peripheral keeps control of GPIOs */ 
                |   (1U << 29)  /* CS is Enabled */ 
                |   (1U << 22));/* SPI in Master mode */ 

    SPI1->CR1 |= (1U <<16); /* AF config is locked*/ 

    /* Config the DMA */ 
    RCC->AHB1ENR |= (1 << 0); // DMA1 clock enable


}

void SPI1_Enable(void)
{
    SPI1->CR1 |= (1U << 0);
}

void SPI1_Disable(void)
{
    SPI1->CR1 &= ~(1U << 0);
}

#endif

void SPI_1_ClockConfig()
{
    /* SPI 1 clock source selsection RCC->D2CCIP2R */
    RCC->D2CCIP1R |= (1 << 12); // PLL2 P clk output
    /* SPI 1 enable clock */
    RCC->APB2ENR |= (1 <<12);
}
void SPI_2_ClockConfig()
{
    /* SPI clock source selsection RCC->D2CCIP2R */
    RCC->D2CCIP1R |= (1 << 12); // PLL2 P clk output
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

#ifndef _CLOCKS_H
#define _CLOCKS_H
#include <stdint.h>
/*Clock marcos*/ 
#define MCO1_PLL1_Q_CLK_OUT 3U  
#define MCO1_Prescaler_DIV_BY_1 1U  
#define MCO1_prescaler_DIV_BY_2 2U  
#define MCO1_prescaler_DIV_BY_3 3U  
#define MCO1_prescaler_DIV_BY_4 4U   
#define MCO1_prescaler_DIV_BY_5 5U   
#define MCO1_prescaler_DIV_BY_6 6U   
#define MCO1_prescaler_DIV_BY_7 7U   
#define MCO1_prescaler_DIV_BY_8 8U   
#define MCO1_prescaler_DIV_BY_9 9U   
#define MCO1_prescaler_DIV_BY_10 10U   
#define MCO1_prescaler_DIV_BY_11 11U   
#define MCO1_prescaler_DIV_BY_12 12U   
#define MCO1_prescaler_DIV_BY_13 13U   
#define MCO1_prescaler_DIV_BY_14 14U   
#define MCO1_prescaler_DIV_BY_15 15U  

#define MCO2_PLL2_P_CLK_OUT 1U 
#define MCO2_PLL1_P_CLK_OUT 3U 
#define MCO2_Prescaler_DIV_BY_1 1U  
#define MCO2_prescaler_DIV_BY_2 2U  
#define MCO2_prescaler_DIV_BY_3 3U  
#define MCO2_prescaler_DIV_BY_4 4U   
#define MCO2_prescaler_DIV_BY_5 5U   
#define MCO2_prescaler_DIV_BY_6 6U   
#define MCO2_prescaler_DIV_BY_7 7U   
#define MCO2_prescaler_DIV_BY_8 8U   
#define MCO2_prescaler_DIV_BY_9 9U   
#define MCO2_prescaler_DIV_BY_10 10U   
#define MCO2_prescaler_DIV_BY_11 11U   
#define MCO2_prescaler_DIV_BY_12 12U   
#define MCO2_prescaler_DIV_BY_13 13U   
#define MCO2_prescaler_DIV_BY_14 14U   
#define MCO2_prescaler_DIV_BY_15 15U  
void systemClockConfig_480Mhz(void);
void testclocks(int MCO1_prescale_val, int MCO2_prescale_val);
#endif

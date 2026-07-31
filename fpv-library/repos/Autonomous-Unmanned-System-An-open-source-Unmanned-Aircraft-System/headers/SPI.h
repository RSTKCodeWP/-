#ifndef _SPI_H
#define _SPI_H

////////////// GY-ICM20498 IMU SENSOR /////////////////////
void SPI_Init(void);
void SPI1_Enable(void);
void SPI1_Disable(void);

//////////////////////////////////////
void SPI_1_ClockConfig(void);
void SPI_2_ClockConfig(void);
void SPI_4_ClockConfig(void);
void SPI_1_Clock_24MHZ(void);
void SPI_2_Clock_10MHZ(void);
void SPI_4_Clock_5MHZ(void);

#endif


#include "mock_task.h"
#include "stm32h723xx.h"
#include "stdio.h"
#include "stdint.h"
#include "stdbool.h"
#include "stddef.h"


void RX_GCS_PAYLOAD_TASK(void) /* task period : 25 HZ = 40 ms */
{
}
void READ_IMU_TASK(void) /* task period: 1000 HZ = 1 ms */
{
}
void IMU_DSP_TASK(void) /* task period: 1000 HZ = 1 ms */
{
}
void RUN_PID_TASK(void) /* task period: 1000 HZ = 1 ms*/
{
}
void LOG_SYSTEM_HEALTH_TASK(void) /* task period: 50 HZ = 20 ms */
{
}
void CHECK_BAT_HEALTH_TASK(void) /* task period: 50 HZ = 20 ms */
{
}
void CHECK_COMPASS_TASK(void) /**/
{
}
void ATTITUDE_ESTIMATION_TASK(void) /**/
{
}
void CHECK_GPS_TASK(void) /**/
{
}
void POSITION_ESTIMATION_TASK(void) /**/
{
}
void FAILSAFE_TASK(void) /**/
{
}
void CHECK_WAYPOINT_TASK(void) /**/
{
}
void ALTHOLD_TASK(void) /**/
{
}
void POSHOLD_TASK(void) /**/
{
}
void GET_Z_AXIS_ACCEL_TASK(void) /**/
{
}
void GET_BAROMETER_DATA_TASK(void) /**/
{
}
void ALTITUDE_ESTIMATION_TASK(void) /**/
{
}
void TX_TELEMETRY_PAYLOAD_TASK(void) /**/
{
}













#ifndef _MOCK_TASK_H
#define _MOCK_TASK_H

void RX_GCS_PAYLOAD_TASK(void); /* task period : 25 HZ = 40 ms */ 
void READ_IMU_TASK(void); /* task period: 1000 HZ = 1 ms */ 
void IMU_DSP_TASK(void); /* task period: 1000 HZ = 1 ms */ 
void RUN_PID_TASK(void); /* task period: 1000 HZ = 1 ms*/ 
void LOG_SYSTEM_HEALTH_TASK(void); /* task period: 50 HZ = 20 ms */ 
void CHECK_BAT_HEALTH_TASK(void); /* task period: 50 HZ = 20 ms */ 
void CHECK_COMPASS_TASK(void); /* task period: 100 HZ = 10 ms */ 
void ATTITUDE_ESTIMATION_TASK(void); /* task period: 100 HZ = 10 ms*/ 
void CHECK_GPS_TASK(void); /* task period: 100 HZ = 10 ms */ 
void POSITION_ESTIMATION_TASK(void); /* task period: 100 HZ = 10 ms */
void FAILSAFE_TASK(void); /* task period: 100 HZ = 10 ms */ 
void CHECK_WAYPOINT_TASK(void); /* task period: 100 HZ = 10 ms */ 
void ALTHOLD_TASK(void); /* task period: 100 HZ = 10 ms */ 
void POSHOLD_TASK(void); /* task period: 100 HZ = 10 ms */ 
void GET_Z_AXIS_ACCEL_TASK(void); /* task period: 500 HZ = 2 ms */ 
void GET_BAROMETER_DATA_TASK(void); /* task period: 50 HZ = 20 ms */ 
void ALTITUDE_ESTIMATION_TASK(void); /* task period: 125 HZ = 8 ms */ 
void TX_TELEMETRY_PAYLOAD_TASK(void); /* task period: 250 HZ = 4 ms */ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 
/**/ 

#endif

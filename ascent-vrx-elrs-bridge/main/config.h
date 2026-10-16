#pragma once

/* UART: ELRS CRSF (420000 8N1) */
#define ELRS_UART_NUM       UART_NUM_1
#define ELRS_TX_GPIO        17
#define ELRS_RX_GPIO        18

/* UART: VRX side SH1.0 (ELRS passthrough) */
#define VRX_UART_NUM        UART_NUM_2
#define VRX_SIDE_TX_GPIO    16
#define VRX_SIDE_RX_GPIO    15

#define CRSF_BAUD           420000
#define CRSF_RX_BUF         2048
#define CRSF_TX_BUF         2048

/* VRX USB-C network profile (Caddx usb-c) */
#define VRX_HOST            "192.168.3.102"
#define VRX_CTRL_PORT       9001

#define BRIDGE_TASK_STACK   4096
#define BRIDGE_TASK_PRIO    12
#define UDP_TASK_STACK      4096
#define UDP_TASK_PRIO       5

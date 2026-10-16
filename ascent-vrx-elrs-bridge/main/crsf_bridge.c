#include "crsf_bridge.h"

#include "config.h"

#include "driver/uart.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "crsf_bridge";

static void uart_setup(uart_port_t port, int tx, int rx)
{
    const uart_config_t cfg = {
        .baud_rate = CRSF_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    ESP_ERROR_CHECK(uart_driver_install(port, CRSF_RX_BUF, CRSF_TX_BUF, 0, NULL, 0));
    ESP_ERROR_CHECK(uart_param_config(port, &cfg));
    ESP_ERROR_CHECK(uart_set_pin(port, tx, rx, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
}

static void bridge_task(void *arg)
{
    (void)arg;
    uint8_t buf[128];

    ESP_LOGI(TAG, "CRSF bridge active ELRS UART%d <-> VRX UART%d @ %d",
             ELRS_UART_NUM, VRX_UART_NUM, CRSF_BAUD);

    while (true) {
        const int from_elrs = uart_read_bytes(ELRS_UART_NUM, buf, sizeof(buf), pdMS_TO_TICKS(1));
        if (from_elrs > 0) {
            uart_write_bytes(VRX_UART_NUM, (const char *)buf, from_elrs);
        }

        const int from_vrx = uart_read_bytes(VRX_UART_NUM, buf, sizeof(buf), pdMS_TO_TICKS(1));
        if (from_vrx > 0) {
            uart_write_bytes(ELRS_UART_NUM, (const char *)buf, from_vrx);
        }
    }
}

esp_err_t crsf_bridge_start(void)
{
    uart_setup(ELRS_UART_NUM, ELRS_TX_GPIO, ELRS_RX_GPIO);
    uart_setup(VRX_UART_NUM, VRX_SIDE_TX_GPIO, VRX_SIDE_RX_GPIO);

    BaseType_t ok = xTaskCreatePinnedToCore(
        bridge_task, "crsf_bridge", BRIDGE_TASK_STACK, NULL, BRIDGE_TASK_PRIO, NULL, 0);
    return ok == pdPASS ? ESP_OK : ESP_FAIL;
}

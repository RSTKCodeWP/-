#include "config.h"
#include "console_cli.h"
#include "crsf_bridge.h"
#include "usb_rndis_net.h"
#include "vrx_udp.h"

#include "esp_log.h"
#include "nvs_flash.h"

static const char *TAG = "main";

void app_main(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }

    ESP_LOGI(TAG, "Ascent VRX bridge — CRSF UART + UDP via USB-C RNDIS");
    ESP_LOGI(TAG, "VRX target %s:%d", VRX_HOST, VRX_CTRL_PORT);

    ESP_ERROR_CHECK(crsf_bridge_start());
    ESP_ERROR_CHECK(usb_rndis_net_start());
    ESP_ERROR_CHECK(vrx_udp_init());
    ESP_ERROR_CHECK(console_cli_start());
}

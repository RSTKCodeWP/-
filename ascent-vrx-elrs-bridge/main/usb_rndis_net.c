#include "usb_rndis_net.h"

#include "config.h"

#include "esp_check.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "iot_eth.h"
#include "iot_eth_netif_glue.h"
#include "iot_usbh_rndis.h"
#include "usb/usb_host.h"

#include <stdio.h>
#include <string.h>

static const char *TAG = "usb_rndis";
static esp_netif_t *s_netif;
static iot_eth_driver_t *s_eth_driver;
static bool s_ready;
static char s_ip[16];

static void on_got_ip(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    (void)arg;
    (void)base;
    (void)id;
    const ip_event_got_ip_t *event = (const ip_event_got_ip_t *)data;
    snprintf(s_ip, sizeof(s_ip), IPSTR, IP2STR(&event->ip_info.ip));
    s_ready = true;
    ESP_LOGI(TAG, "RNDIS IP %s — VRX Ctrl UDP %s:%d", s_ip, VRX_HOST, VRX_CTRL_PORT);
}

static esp_err_t install_rndis(void)
{
    static const usb_device_match_id_t dev_match[] = {
        {
            .match_flags = USB_DEVICE_ID_MATCH_VENDOR | USB_DEVICE_ID_MATCH_PRODUCT,
            .idVendor = USB_DEVICE_VENDOR_ANY,
            .idProduct = USB_DEVICE_PRODUCT_ANY,
        },
        {0},
    };

    iot_usbh_rndis_config_t rndis_cfg = {
        .match_id_list = dev_match,
    };

    ESP_RETURN_ON_ERROR(iot_eth_new_usb_rndis(&rndis_cfg, &s_eth_driver), TAG, "new rndis");

    iot_eth_handle_t eth_handle = NULL;
    const iot_eth_config_t eth_cfg = {
        .driver = s_eth_driver,
        .stack_input = NULL,
    };
    ESP_RETURN_ON_ERROR(iot_eth_install(&eth_cfg, &eth_handle), TAG, "eth install");

    esp_netif_inherent_config_t eth_net_cfg = ESP_NETIF_INHERENT_DEFAULT_ETH();
    eth_net_cfg.if_key = "usb_rndis";
    eth_net_cfg.if_desc = "vrx_usb_c";

    const esp_netif_config_t netif_cfg = {
        .base = &eth_net_cfg,
        .driver = NULL,
        .stack = ESP_NETIF_NETSTACK_DEFAULT_ETH,
    };
    s_netif = esp_netif_new(&netif_cfg);
    ESP_RETURN_ON_FALSE(s_netif != NULL, ESP_FAIL, TAG, "netif");

    iot_eth_netif_glue_handle_t glue = iot_eth_new_netif_glue(eth_handle);
    ESP_RETURN_ON_FALSE(glue != NULL, ESP_FAIL, TAG, "glue");

    ESP_ERROR_CHECK(esp_netif_attach(s_netif, glue));
    ESP_ERROR_CHECK(iot_eth_start(eth_handle));
    ESP_ERROR_CHECK(esp_netif_set_default_netif(s_netif));

    ESP_LOGI(TAG, "Plug ESP32-S3 USB OTG → VRX Type-C; waiting for DHCP...");
    return ESP_OK;
}

esp_err_t usb_rndis_net_start(void)
{
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_ETH_GOT_IP, &on_got_ip, NULL));

    s_ready = false;
    s_ip[0] = '\0';
    return install_rndis();
}

bool usb_rndis_net_ready(void)
{
    return s_ready;
}

const char *usb_rndis_net_ip_str(void)
{
    return s_ip[0] ? s_ip : "(none)";
}

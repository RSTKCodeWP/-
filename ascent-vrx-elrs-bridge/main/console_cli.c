#include "console_cli.h"

#include "usb_rndis_net.h"
#include "vrx_udp.h"

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include <stdio.h>
#include <string.h>

static const char *TAG = "cli";

static void print_help(void)
{
    printf(
        "Commands:\r\n"
        "  help\r\n"
        "  net\r\n"
        "  status\r\n"
        "  key <up|down|left|right|confirm|back|pairing|recording>\r\n");
}

static void handle_line(char *line)
{
    while (*line == ' ' || *line == '\t') {
        line++;
    }
    if (line[0] == '\0') {
        return;
    }

    if (strcmp(line, "help") == 0) {
        print_help();
        return;
    }
    if (strcmp(line, "net") == 0) {
        printf("RNDIS ready=%d ip=%s\r\n", (int)usb_rndis_net_ready(), usb_rndis_net_ip_str());
        return;
    }
    if (strcmp(line, "status") == 0) {
        if (vrx_udp_request_status() == ESP_OK) {
            printf("status request sent\r\n");
        } else {
            printf("status failed (USB network?)\r\n");
        }
        return;
    }
    if (strncmp(line, "key ", 4) == 0) {
        const char *key = line + 4;
        if (vrx_udp_send_key(key) == ESP_OK) {
            printf("key %s sent\r\n", key);
        } else {
            printf("key send failed\r\n");
        }
        return;
    }

    printf("Unknown command. Type help.\r\n");
}

static void cli_task(void *arg)
{
    (void)arg;
    char line[96];
    size_t len = 0;

    vTaskDelay(pdMS_TO_TICKS(500));
    print_help();

    while (true) {
        const int c = getchar();
        if (c < 0) {
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }
        if (c == '\r' || c == '\n') {
            line[len] = '\0';
            handle_line(line);
            len = 0;
            continue;
        }
        if (c == 127 || c == 8) {
            if (len > 0) {
                len--;
            }
            continue;
        }
        if (len + 1 < sizeof(line)) {
            line[len++] = (char)c;
        }
    }
}

esp_err_t console_cli_start(void)
{
    BaseType_t ok = xTaskCreate(cli_task, "cli", 4096, NULL, 3, NULL);
    if (ok != pdPASS) {
        ESP_LOGE(TAG, "cli task");
        return ESP_FAIL;
    }
    return ESP_OK;
}

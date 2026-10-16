#include "vrx_udp.h"

#include "config.h"
#include "vrx_proto.h"
#include "usb_rndis_net.h"

#include "esp_log.h"
#include "lwip/err.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"

#include <errno.h>
#include <string.h>

static const char *TAG = "vrx_udp";
static int s_sock = -1;

static int ensure_socket(void)
{
    if (s_sock >= 0) {
        return s_sock;
    }
    if (!usb_rndis_net_ready()) {
        return -1;
    }

    s_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (s_sock < 0) {
        ESP_LOGE(TAG, "socket: errno %d", errno);
        return -1;
    }

    struct timeval tv = {.tv_sec = 0, .tv_usec = 200000};
    setsockopt(s_sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    return s_sock;
}

esp_err_t vrx_udp_init(void)
{
    return ESP_OK;
}

bool vrx_udp_network_ready(void)
{
    return usb_rndis_net_ready();
}

int vrx_udp_send(const uint8_t *frame, size_t len)
{
    const int sock = ensure_socket();
    if (sock < 0) {
        return -1;
    }

    struct sockaddr_in dest = {0};
    dest.sin_family = AF_INET;
    dest.sin_port = htons(VRX_CTRL_PORT);
    inet_pton(AF_INET, VRX_HOST, &dest.sin_addr);

    const int sent = sendto(sock, frame, len, 0, (struct sockaddr *)&dest, sizeof(dest));
    if (sent < 0) {
        ESP_LOGW(TAG, "sendto failed errno=%d", errno);
    }
    return sent;
}

esp_err_t vrx_udp_request_status(void)
{
    uint8_t frame[VRX_FRAME_MAX];
    const size_t n = vrx_build_get_status_packet(frame, sizeof(frame));
    if (n == 0) {
        return ESP_FAIL;
    }
    return vrx_udp_send(frame, n) >= 0 ? ESP_OK : ESP_FAIL;
}

static vrx_key_num_t key_from_name(const char *name)
{
    if (strcmp(name, "up") == 0) {
        return VRX_KEY_UP;
    }
    if (strcmp(name, "down") == 0) {
        return VRX_KEY_DOWN;
    }
    if (strcmp(name, "left") == 0) {
        return VRX_KEY_LEFT;
    }
    if (strcmp(name, "right") == 0) {
        return VRX_KEY_RIGHT;
    }
    if (strcmp(name, "confirm") == 0) {
        return VRX_KEY_CONFIRM;
    }
    if (strcmp(name, "back") == 0) {
        return VRX_KEY_BACK;
    }
    if (strcmp(name, "pairing") == 0) {
        return VRX_KEY_PAIRING;
    }
    if (strcmp(name, "recording") == 0) {
        return VRX_KEY_RECORDING;
    }
    return VRX_KEY_UP;
}

esp_err_t vrx_udp_send_key(const char *name)
{
    uint8_t frame[VRX_FRAME_MAX];
    const size_t n = vrx_build_key_packet(key_from_name(name), 0, frame, sizeof(frame));
    if (n == 0) {
        return ESP_FAIL;
    }
    return vrx_udp_send(frame, n) >= 0 ? ESP_OK : ESP_FAIL;
}

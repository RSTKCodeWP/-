#include "vrx_proto.h"

#include <string.h>

static uint16_t payload_checksum(const uint8_t *payload, size_t len)
{
    uint32_t sum = 0;
    for (size_t i = 0; i < len; i++) {
        sum += payload[i];
    }
    return (uint16_t)(sum & 0xFFFF);
}

size_t vrx_assemble_packet(uint8_t command, const uint8_t *payload, size_t payload_len,
                           uint8_t *out, size_t out_cap)
{
    const size_t need = 2 + 1 + 2 + payload_len + 2 + 2;
    if (out_cap < need || payload_len > 0xFFFF) {
        return 0;
    }

    size_t i = 0;
    out[i++] = VRX_HEADER_0;
    out[i++] = VRX_HEADER_1;
    out[i++] = command;
    out[i++] = (uint8_t)((payload_len >> 8) & 0xFF);
    out[i++] = (uint8_t)(payload_len & 0xFF);
    if (payload_len > 0) {
        memcpy(&out[i], payload, payload_len);
        i += payload_len;
    }
    const uint16_t csum = payload_checksum(payload, payload_len);
    out[i++] = (uint8_t)((csum >> 8) & 0xFF);
    out[i++] = (uint8_t)(csum & 0xFF);
    out[i++] = VRX_TAIL_0;
    out[i++] = VRX_TAIL_1;
    return i;
}

size_t vrx_build_key_packet(vrx_key_num_t key, uint8_t press_type, uint8_t *out, size_t out_cap)
{
    const uint8_t payload[] = {0x40, (uint8_t)key, press_type, 0x00};
    return vrx_assemble_packet(VRX_WRITE_CMD, payload, sizeof(payload), out, out_cap);
}

size_t vrx_build_get_status_packet(uint8_t *out, size_t out_cap)
{
    const uint8_t payload[] = {0x52, 0, 0, 0, 0, 0, 0, 0};
    return vrx_assemble_packet(VRX_READ_CMD, payload, sizeof(payload), out, out_cap);
}

size_t vrx_build_set_mode_packet(vrx_passthrough_mode_t mode, uint8_t *out, size_t out_cap)
{
    const uint8_t payload[] = {VRX_SET_MODE_SUBCMD, (uint8_t)mode, 0x00, 0x00, 0x00};
    return vrx_assemble_packet(VRX_PASSTHROUGH_CMD, payload, sizeof(payload), out, out_cap);
}

size_t vrx_build_set_frequency_packet(uint8_t band, uint8_t channel, uint8_t hop,
                                      uint8_t *out, size_t out_cap)
{
    const uint8_t payload[] = {0x50, band, channel, hop, 0, 0, 0, 0};
    return vrx_assemble_packet(VRX_WRITE_CMD, payload, sizeof(payload), out, out_cap);
}

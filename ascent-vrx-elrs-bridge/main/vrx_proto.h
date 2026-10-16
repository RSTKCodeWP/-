#pragma once

#include <stddef.h>
#include <stdint.h>

#define VRX_HEADER_0 0xFE
#define VRX_HEADER_1 0xEF
#define VRX_TAIL_0   0x0D
#define VRX_TAIL_1   0x0A

#define VRX_WRITE_CMD 0x22
#define VRX_READ_CMD  0xA2
#define VRX_PASSTHROUGH_CMD 0x23
#define VRX_SET_MODE_SUBCMD 0x02

typedef enum {
    VRX_MODE_NONE = 0,
    VRX_MODE_MAVLINK = 1,
    VRX_MODE_CRSF = 2,
    VRX_MODE_SBUS = 3,
    VRX_MODE_USER = 4,
    VRX_MODE_OSD = 5,
} vrx_passthrough_mode_t;

typedef enum {
    VRX_KEY_UP = 0,
    VRX_KEY_DOWN = 1,
    VRX_KEY_LEFT = 2,
    VRX_KEY_RIGHT = 3,
    VRX_KEY_CONFIRM = 4,
    VRX_KEY_PAIRING = 5,
    VRX_KEY_RECORDING = 6,
    VRX_KEY_BACK = 7,
    VRX_KEY_DEBUG3 = 9,
} vrx_key_num_t;

/** Max assembled frame size for typical commands. */
#define VRX_FRAME_MAX 64

size_t vrx_assemble_packet(uint8_t command, const uint8_t *payload, size_t payload_len,
                           uint8_t *out, size_t out_cap);

size_t vrx_build_key_packet(vrx_key_num_t key, uint8_t press_type, uint8_t *out, size_t out_cap);

size_t vrx_build_get_status_packet(uint8_t *out, size_t out_cap);

size_t vrx_build_set_mode_packet(vrx_passthrough_mode_t mode, uint8_t *out, size_t out_cap);

size_t vrx_build_set_frequency_packet(uint8_t band, uint8_t channel, uint8_t hop,
                                      uint8_t *out, size_t out_cap);

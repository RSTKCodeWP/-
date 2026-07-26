#pragma once

#include "macros.h"

typedef enum {
    HAL_PLATFORM_UNK,
    HAL_PLATFORM_I6,
    HAL_PLATFORM_I6C,
    HAL_PLATFORM_M6,
    HAL_PLATFORM_V1,
    HAL_PLATFORM_V2,
    HAL_PLATFORM_V3,
    HAL_PLATFORM_V4
} hal_platform;

typedef enum {
    OP_READ = 0b1,
    OP_WRITE = 0b10,
    OP_MODIFY = 0b11
} hal_register_op;

typedef struct {
    unsigned short width, height;
} hal_dim;

typedef struct {
    hal_dim dim;
    void *data;
} hal_bitmap;

typedef struct {
    unsigned short x, y, width, height;
} hal_rect;

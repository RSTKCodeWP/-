// types.h — Extended encoder attribute types for Divinus
// Added fields: minQp, maxQp, maxBitrate, statTime
// These map to Sigmastar MI VENC SDK parameters

#ifndef HAL_TYPES_H
#define HAL_TYPES_H

#include <stdint.h>

typedef enum {
    HAL_VIDCODEC_H264 = 0,
    HAL_VIDCODEC_H265,
    HAL_VIDCODEC_MJPG,
    HAL_VIDCODEC_UNSPEC = -1
} hal_vidcodec;

typedef enum {
    HAL_VIDMODE_CBR = 0,
    HAL_VIDMODE_VBR,
    HAL_VIDMODE_AVBR,
    HAL_VIDMODE_QP,
    HAL_VIDMODE_UNSPEC = -1
} hal_vidmode;

typedef enum {
    HAL_VIDPROFILE_BP = 0,   // Baseline
    HAL_VIDPROFILE_MP,       // Main
    HAL_VIDPROFILE_HP,       // High
    HAL_VIDPROFILE_UNSPEC = -1
} hal_vidprofile;

typedef struct {
    hal_vidcodec codec;
    hal_vidmode  mode;
    hal_vidprofile profile;
    unsigned int width;
    unsigned int height;
    unsigned int fps;
    unsigned int gop;
    unsigned int bitrate;     // Target bitrate in kbps

    // Encoder tuning fields (added for FPV optimization)
    unsigned int maxBitrate;  // AVBR hard ceiling in kbps
    unsigned int minQp;       // Minimum QP (prevents wasting bits)
    unsigned int maxQp;       // Maximum QP (graceful degradation)
    unsigned int statTime;    // AVBR adaptation window in seconds
} hal_vidconfig;

#endif // HAL_TYPES_H
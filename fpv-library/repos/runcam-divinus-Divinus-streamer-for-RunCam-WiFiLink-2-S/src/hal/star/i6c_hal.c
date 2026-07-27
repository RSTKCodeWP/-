/*
 * i6c_hal.c — Hardware Abstraction Layer for Sigmastar Infinity6E (SSC338Q)
 *
 * This file implements the video encoder interface for the MI VENC SDK.
 * Extended to support AVBR mode with minQp, maxQp, maxBitrate, statTime
 * and H.265 High Profile selection.
 *
 * Target: RunCam WiFiLink 2 (star6e / SSC338Q)
 * SDK: Sigmastar MI (Media Interface) VENC module
 */

#include "types.h"
#include <stdio.h>
#include <string.h>

/* Sigmastar MI SDK headers */
#include "mi_venc.h"
#include "mi_venc_datatype.h"

#define HAL_INFO(tag, fmt, ...)  printf("[%s] " fmt "\n", tag, ##__VA_ARGS__)
#define HAL_ERROR(tag, fmt, ...) printf("[%s] ERROR: " fmt "\n", tag, ##__VA_ARGS__)

/*
 * i6c_video_create_channel — Create and configure a VENC channel
 *
 * @channel: VENC channel index (0 = main stream)
 * @config:  Encoder configuration from divinus.yaml
 *
 * Returns 0 on success, negative on error.
 */
static int i6c_video_create_channel(int channel, hal_vidconfig *config)
{
    MI_VENC_ChnAttr_t chnAttr;
    MI_S32 ret;

    memset(&chnAttr, 0, sizeof(chnAttr));

    /* ─── Codec selection ─── */
    switch (config->codec) {
    case HAL_VIDCODEC_H265:
        chnAttr.stVeAttr.eType = E_MI_VENC_MODTYPE_H265E;
        chnAttr.stVeAttr.stAttrH265e.u32PicWidth  = config->width;
        chnAttr.stVeAttr.stAttrH265e.u32PicHeight = config->height;
        chnAttr.stVeAttr.stAttrH265e.u32MaxPicWidth  = config->width;
        chnAttr.stVeAttr.stAttrH265e.u32MaxPicHeight = config->height;
        break;

    case HAL_VIDCODEC_H264:
        chnAttr.stVeAttr.eType = E_MI_VENC_MODTYPE_H264E;
        chnAttr.stVeAttr.stAttrH264e.u32PicWidth  = config->width;
        chnAttr.stVeAttr.stAttrH264e.u32PicHeight = config->height;
        chnAttr.stVeAttr.stAttrH264e.u32MaxPicWidth  = config->width;
        chnAttr.stVeAttr.stAttrH264e.u32MaxPicHeight = config->height;
        break;

    case HAL_VIDCODEC_MJPG:
        chnAttr.stVeAttr.eType = E_MI_VENC_MODTYPE_JPEGE;
        break;

    default:
        HAL_ERROR("i6c", "Unsupported codec: %d", config->codec);
        return -1;
    }

    /* ─── Rate control mode ─── */
    if (config->codec == HAL_VIDCODEC_H265) {

        switch (config->mode) {
        case HAL_VIDMODE_AVBR:
        {
            chnAttr.stRcAttr.eRcMode = E_MI_VENC_RC_MODE_H265AVBR;

            MI_VENC_AttrH265eAvbr_t *avbr = &chnAttr.stRcAttr.stAttrH265eAvbr;
            avbr->u32Gop           = config->gop;
            avbr->u32SrcFrmRateNum = config->fps;
            avbr->u32SrcFrmRateDen = 1;
            avbr->u32BitRate       = config->bitrate;
            avbr->u32MaxBitRate    = config->maxBitrate;
            avbr->u32StatTime      = config->statTime;

            /* QP bounds for quality control */
            avbr->u32MinQp = config->minQp;
            avbr->u32MaxQp = config->maxQp;

            HAL_INFO("i6c", "H265 AVBR: target=%dkbps max=%dkbps QP=%d-%d stat=%ds GOP=%d",
                     config->bitrate, config->maxBitrate,
                     config->minQp, config->maxQp,
                     config->statTime, config->gop);
            break;
        }

        case HAL_VIDMODE_CBR:
        {
            chnAttr.stRcAttr.eRcMode = E_MI_VENC_RC_MODE_H265CBR;

            MI_VENC_AttrH265eCbr_t *cbr = &chnAttr.stRcAttr.stAttrH265eCbr;
            cbr->u32Gop           = config->gop;
            cbr->u32SrcFrmRateNum = config->fps;
            cbr->u32SrcFrmRateDen = 1;
            cbr->u32BitRate       = config->bitrate;

            HAL_INFO("i6c", "H265 CBR: %dkbps GOP=%d", config->bitrate, config->gop);
            break;
        }

        case HAL_VIDMODE_VBR:
        {
            chnAttr.stRcAttr.eRcMode = E_MI_VENC_RC_MODE_H265VBR;

            MI_VENC_AttrH265eVbr_t *vbr = &chnAttr.stRcAttr.stAttrH265eVbr;
            vbr->u32Gop           = config->gop;
            vbr->u32SrcFrmRateNum = config->fps;
            vbr->u32SrcFrmRateDen = 1;
            vbr->u32MaxBitRate    = config->maxBitrate;

            HAL_INFO("i6c", "H265 VBR: max=%dkbps GOP=%d", config->maxBitrate, config->gop);
            break;
        }

        default:
            HAL_ERROR("i6c", "Unsupported rate control mode: %d", config->mode);
            return -1;
        }

        /* ─── Profile selection for H.265 ─── */
        switch (config->profile) {
        case HAL_VIDPROFILE_HP:
            chnAttr.stVeAttr.stAttrH265e.eProfile = E_MI_VENC_H265E_HIGH;
            HAL_INFO("i6c", "H265 High Profile — 8x8 transform enabled");
            break;
        case HAL_VIDPROFILE_MP:
            chnAttr.stVeAttr.stAttrH265e.eProfile = E_MI_VENC_H265E_MAIN;
            HAL_INFO("i6c", "H265 Main Profile");
            break;
        default:
            chnAttr.stVeAttr.stAttrH265e.eProfile = E_MI_VENC_H265E_MAIN;
            HAL_INFO("i6c", "H265 Main Profile (default)");
            break;
        }
    }

    /* ─── Create the VENC channel ─── */
    ret = MI_VENC_CreateChn(channel, &chnAttr);
    if (ret != MI_SUCCESS) {
        HAL_ERROR("i6c", "Failed to create VENC channel %d: 0x%x", channel, ret);
        return -1;
    }

    /* ─── Start receiving frames ─── */
    MI_VENC_RecvPicParam_t recvParam;
    recvParam.s32RecvPicNum = -1; /* continuous */
    ret = MI_VENC_StartRecvPic(channel, &recvParam);
    if (ret != MI_SUCCESS) {
        HAL_ERROR("i6c", "Failed to start recv on channel %d: 0x%x", channel, ret);
        MI_VENC_DestroyChn(channel);
        return -1;
    }

    HAL_INFO("i6c", "VENC channel %d created: %dx%d @%dfps",
             channel, config->width, config->height, config->fps);

    return 0;
}

/*
 * i6c_video_destroy_channel — Destroy a VENC channel
 */
static int i6c_video_destroy_channel(int channel)
{
    MI_VENC_StopRecvPic(channel);
    MI_VENC_DestroyChn(channel);
    HAL_INFO("i6c", "VENC channel %d destroyed", channel);
    return 0;
}

/*
 * i6c_video_request_idr — Request an IDR frame (for wfb-ng recovery)
 */
static int i6c_video_request_idr(int channel)
{
    MI_S32 ret = MI_VENC_RequestIdr(channel, TRUE);
    if (ret != MI_SUCCESS) {
        HAL_ERROR("i6c", "Failed to request IDR on channel %d: 0x%x", channel, ret);
        return -1;
    }
    HAL_INFO("i6c", "IDR requested on channel %d", channel);
    return 0;
}
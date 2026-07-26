#pragma once

#include <stdbool.h>
#include <stdint.h>

enum NalUnitType {                    //   Table 7-1 NAL unit type codes
    NalUnitType_Unspecified = 0,      // Unspecified
    NalUnitType_CodedSliceNonIdr = 1, // Coded slice of a non-IDR picture
    NalUnitType_CodedSliceDataPartitionA = 2, // Coded slice data partition A
    NalUnitType_CodedSliceDataPartitionB = 3, // Coded slice data partition B
    NalUnitType_CodedSliceDataPartitionC = 4, // Coded slice data partition C
    NalUnitType_CodedSliceIdr = 5,            // Coded slice of an IDR picture
    NalUnitType_SEI = 6, // Supplemental enhancement information (SEI)
    NalUnitType_SPS = 7, // Sequence parameter set
    NalUnitType_PPS = 8, // Picture parameter set
    NalUnitType_AUD = 9, // Access unit delimiter
    NalUnitType_EndOfSequence = 10, // End of sequence
    NalUnitType_EndOfStream = 11,   // End of stream
    NalUnitType_Filler = 12,        // Filler data
    NalUnitType_SpsExt = 13,        // Sequence parameter set extension
                                    // 14..18           // Reserved
    NalUnitType_CodedSliceAux =
        19, // Coded slice of an auxiliary coded picture without partitioning
    // 20..23           // Reserved
    // 24..31           // Unspecified
    NalUnitType_VPS_HEVC = 32,
    NalUnitType_SPS_HEVC = 33,
    NalUnitType_PPS_HEVC = 34,
    NalUnitType_AUD_HEVC = 35,
    NalUnitType_EndOfSequence_HEVC = 36,
    NalUnitType_EndOfStream_HEVC = 37,
    NalUnitType_Filler_HEVC = 38,
    NalUnitType_SEI_HEVC = 39,
    NalUnitType_SEI_HEVC_2 = 40,
};

static inline unsigned int nal_find_startcode(const unsigned char *buf,
    unsigned int off, unsigned int len)
{
    for (; off + 2 < len; off++) {
        if (buf[off] == 0 && buf[off + 1] == 0) {
            if (buf[off + 2] == 1)
                return off;
            if (off + 3 < len && buf[off + 2] == 0 && buf[off + 3] == 1)
                return off;
        }
    }
    return len;
}

struct NAL {
    char isH265;
    char *data;
    uint64_t data_size;
    uint32_t picture_order_count;

    // NAL header
    bool forbidden_zero_bit;
    uint8_t ref_idc;
    uint8_t unit_type_value;
    enum NalUnitType unit_type;
};

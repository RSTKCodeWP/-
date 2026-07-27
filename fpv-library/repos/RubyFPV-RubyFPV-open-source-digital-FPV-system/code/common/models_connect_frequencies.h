#pragma once
#include "../base/base.h"
#include "../base/models.h"
#include "../base/shared_mem_radio.h"

void set_model_main_connect_frequency(u32 uModelId, u32 iFreq);
u32 get_model_main_connect_frequency(u32 uModelId);
bool is_vehicle_radio_link_used(Model* pModel, shared_mem_radio_stats* pSMRadioStats, int iVehicleRadioLinkIndex);

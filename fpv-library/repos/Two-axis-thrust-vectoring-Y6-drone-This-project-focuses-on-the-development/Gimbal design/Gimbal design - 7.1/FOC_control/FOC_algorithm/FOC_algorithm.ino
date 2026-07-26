#include <math.h>
#include <atomic>
#include "esp_attr.h"
#include "esp_err.h"
#include <SPI.h>
#include "esp_adc/adc_continuous.h"
#include "driver/mcpwm_prelude.h"

#define ADC_IA_CHANNEL ADC_CHANNEL_0
#define ADC_IB_CHANNEL ADC_CHANNEL_1

mcpwm_cmpr_handle_t comparador_U;
mcpwm_cmpr_handle_t comparador_V;
mcpwm_cmpr_handle_t comparador_W;
mcpwm_oper_handle_t oper_U = NULL;
mcpwm_oper_handle_t oper_V = NULL;
mcpwm_oper_handle_t oper_W = NULL;
adc_continuous_handle_t adc_handle = NULL;
const uint32_t PWM_PERIOD_TICKS = 40000;
int clk = 4;
int miso = 6;
int mosi = 3;
int cs_as5048a = 5;
int in1 = 11;
int in2 = 10;
int in3 = 9;
int en = 8;

int16_t LUT_cos_angle_index[1024];
int16_t LUT_sin_angle_index[1024];
uint32_t angle_index;
int I_a, I_b;
int I_beta;
int I_d, I_q;
int I_q_target;
int V_d, V_q;
int vdvq_module;
int V_alpha, V_beta;
int U, V, W;
int sector;
int t1, t0, t2;
float prov_angle = 0.0f;
uint32_t ini_encoder_val;
uint32_t current_encoder_val;
int32_t adc_offset_Ia = 2048;
int32_t adc_offset_Ib = 2048;

struct PI_properties {
  int K_p;
  int K_i_dt;
  int integral_val;
};

PI_properties I_d_properties;
PI_properties I_q_properties;

std::atomic<float> target_angle(0.0f);
std::atomic<int32_t> I_a_adc(0);
std::atomic<int32_t> I_b_adc(0);

void ESPNOW_procedure(void * pvParameters){
  while(true){
    // Procedimiento ESPNOW, interpolaciones...
    prov_angle = prov_angle + 0.00001f;
    while(prov_angle >= TWO_PI) prov_angle -= TWO_PI;
    while(prov_angle < 0.0f) prov_angle += TWO_PI;
    target_angle.store(prov_angle, std::memory_order_relaxed);
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

void ADC_lectures(void *pvParameters)
{
  uint8_t result[64];
  uint32_t ret_num;

  while(true)
  {
    esp_err_t ret = adc_continuous_read(
        adc_handle,
        result,
        sizeof(result),
        &ret_num,
        100);

    if(ret == ESP_OK)
    {
      for(int i=0;i<ret_num;i+=sizeof(adc_digi_output_data_t))
      {
        adc_digi_output_data_t *sample =
          (adc_digi_output_data_t*)&result[i];

        if(sample->type2.channel == ADC_IA_CHANNEL)
        {
          I_a_adc.store(sample->type2.data,
                        std::memory_order_relaxed);
        }
        else if(sample->type2.channel == ADC_IB_CHANNEL)
        {
          I_b_adc.store(sample->type2.data,
                        std::memory_order_relaxed);
        }
      }
    }
    Serial.printf("%d %d\n",
      I_a_adc.load(),
      I_b_adc.load());
    vTaskDelay(100);
  }
}

static bool IRAM_ATTR FOC_algorithm(mcpwm_timer_handle_t timer, const mcpwm_timer_event_data_t *edata, void *user_ctx){
  int32_t raw_Ia = I_a_adc.load(std::memory_order_relaxed);
  int32_t raw_Ib = I_b_adc.load(std::memory_order_relaxed);
  I_a = (raw_Ia - adc_offset_Ia) << 4;
  I_b = (raw_Ib - adc_offset_Ib) << 4;
  current_encoder_val = readEncoder() & 0x3FFF;
  int32_t mechanic_diff = (uint32_t)current_encoder_val - (uint32_t)ini_encoder_val;
  angle_index = ((mechanic_diff * 11) >> 4) & 1023;
  I_q_target = 4915; // This is the value for testing, 0.15f * 32768
  if(I_q_target > 32768) I_q_target = 32768;
  if(I_q_target < -32768) I_q_target = -32768;
  cp_transformations();
  int error_I_d = 0 - I_d;
  int error_I_q = I_q_target - I_q;
  V_d = PI_current_controller(&I_d_properties, error_I_d);
  V_q = PI_current_controller(&I_q_properties, error_I_q);
  vdvq_module = ((V_d * V_d) >> 15) + ((V_q * V_q) >> 15);
  int32_t abs_V_d = (V_d < 0) ? -V_d : V_d;
  int32_t abs_V_q = (V_q < 0) ? -V_q : V_q;
  int32_t max_V = (abs_V_d > abs_V_q) ? abs_V_d : abs_V_q;
  int32_t min_V = (abs_V_d > abs_V_q) ? abs_V_q : abs_V_d;
  int32_t vdvq_module_estimated = max_V + (min_V >> 2);
  if(vdvq_module_estimated > 188743){
    V_d = ((int64_t)V_d * 188743) / vdvq_module_estimated;
    V_q = ((int64_t)V_q * 188743) / vdvq_module_estimated;
  }
  inverse_park_transformation();
  svpwm_modulation();
  return false;
}

void setup_mcpwm(){
  mcpwm_timer_handle_t timer = NULL;
  mcpwm_timer_config_t timer_config = {
    .group_id = 0,
    .clk_src = MCPWM_TIMER_CLK_SRC_DEFAULT,
    .resolution_hz = 160000000, 
    .count_mode = MCPWM_TIMER_COUNT_MODE_UP_DOWN,
    .period_ticks = PWM_PERIOD_TICKS,
  };
  mcpwm_new_timer(&timer_config, &timer);
  mcpwm_operator_config_t oper_config_u = { .group_id = 0 };
  mcpwm_new_operator(&oper_config_u, &oper_U);
  mcpwm_operator_connect_timer(oper_U, timer);
  mcpwm_operator_config_t oper_config_v = { .group_id = 0 };
  mcpwm_new_operator(&oper_config_v, &oper_V);
  mcpwm_operator_connect_timer(oper_V, timer);
  mcpwm_operator_config_t oper_config_w = { .group_id = 0 };
  mcpwm_new_operator(&oper_config_w, &oper_W);
  mcpwm_operator_connect_timer(oper_W, timer);
  mcpwm_comparator_config_t cmpr_config = { .flags = { .update_cmp_on_tez = true } };
  mcpwm_new_comparator(oper_U, &cmpr_config, &comparador_U);
  mcpwm_new_comparator(oper_V, &cmpr_config, &comparador_V);
  mcpwm_new_comparator(oper_W, &cmpr_config, &comparador_W);
  mcpwm_gen_handle_t gen_u, gen_v, gen_w;
  mcpwm_generator_config_t gen_config = {};
  gen_config.gen_gpio_num = 8;  mcpwm_new_generator(oper_U, &gen_config, &gen_u);
  gen_config.gen_gpio_num = 9;  mcpwm_new_generator(oper_V, &gen_config, &gen_v);
  gen_config.gen_gpio_num = 10; mcpwm_new_generator(oper_W, &gen_config, &gen_w);
  mcpwm_gen_compare_event_action_t action_config;
  action_config.direction = MCPWM_TIMER_DIRECTION_UP;
  action_config.action = MCPWM_GEN_ACTION_HIGH;
  action_config.comparator = comparador_U;
  mcpwm_generator_set_action_on_compare_event(gen_u, action_config);
  action_config.comparator = comparador_V;
  mcpwm_generator_set_action_on_compare_event(gen_v, action_config);
  action_config.comparator = comparador_W;
  mcpwm_generator_set_action_on_compare_event(gen_w, action_config);
  action_config.direction = MCPWM_TIMER_DIRECTION_DOWN;
  action_config.action = MCPWM_GEN_ACTION_LOW;
  action_config.comparator = comparador_U;
  mcpwm_generator_set_action_on_compare_event(gen_u, action_config);
  action_config.comparator = comparador_V;
  mcpwm_generator_set_action_on_compare_event(gen_v, action_config);
  action_config.comparator = comparador_W;
  mcpwm_generator_set_action_on_compare_event(gen_w, action_config);
  mcpwm_timer_event_callbacks_t cbs = {
    .on_full = FOC_algorithm
  };
  mcpwm_timer_register_event_callbacks(timer, &cbs, NULL);
  mcpwm_timer_enable(timer);
  mcpwm_timer_start_stop(timer, MCPWM_TIMER_START_NO_STOP);
}

void setup(){
  pinMode(en, OUTPUT);
  digitalWrite(en, LOW);
  Serial.begin(115200);
  while (!Serial);
  pinMode(cs, OUTPUT);
  digitalWrite(cs, HIGH);
  SPI.begin(clk, miso, mosi, cs);
  adc_continuous_handle_cfg_t adc_handle_cfg = {
    .max_store_buf_size = 1024,
    .conv_frame_size = 64,
  };

  ESP_ERROR_CHECK(adc_continuous_new_handle(&adc_handle_cfg, &adc_handle));

  adc_digi_pattern_config_t pattern[2] = {};

  pattern[0].atten = ADC_ATTEN_DB_12;
  pattern[0].channel = ADC_IA_CHANNEL;
  pattern[0].unit = ADC_UNIT_1;
  pattern[0].bit_width = ADC_BITWIDTH_12;

  pattern[1].atten = ADC_ATTEN_DB_12;
  pattern[1].channel = ADC_IB_CHANNEL;
  pattern[1].unit = ADC_UNIT_1;
  pattern[1].bit_width = ADC_BITWIDTH_12;

  adc_continuous_config_t adc_config = {};
  adc_config.sample_freq_hz = 100000;
  adc_config.conv_mode = ADC_CONV_SINGLE_UNIT_1;
  adc_config.format = ADC_DIGI_OUTPUT_FORMAT_TYPE2;
  adc_config.pattern_num = 2;
  adc_config.adc_pattern = pattern;

  ESP_ERROR_CHECK(adc_continuous_config(adc_handle, &adc_config));

  ESP_ERROR_CHECK(adc_continuous_start(adc_handle));
  long sum_a = 0;
  long sum_b = 0;
  /*for(int i = 0; i < 32; i++){
    sum_a += adc_continuous_read(...);
    sum_b += adc_continuous_read(...);
    delay(2);
  }
  adc_offset_Ia = sum_a / 32;
  adc_offset_Ib = sum_b / 32;*/
  adc_offset_Ia = 2048;
  adc_offset_Ib = 2048;
  setup_mcpwm();
  for(int i = 0; i < 1024; i++){
    float angle_rad = ((float)i / 1024.0f) * TWO_PI;
    LUT_cos_angle_index[i] = (int16_t)(cos(angle_rad) * 32767.0f);
    LUT_sin_angle_index[i] = (int16_t)(sin(angle_rad) * 32767.0f);
  }
  uint32_t start_time = millis();
  I_d_properties.K_p = 39322; // This is a temporary estimated value, 1.2f * 32768
  I_d_properties.K_i_dt = 42; // This is a temporary estimated value, 0.05 * 0.000005 * 2^24
  I_d_properties.integral_val = 0;
  I_q_properties.K_p = 39322;
  I_q_properties.K_i_dt = 42;
  I_q_properties.integral_val = 0;
  digitalWrite(en, HIGH);
  V_alpha = 6553;
  V_beta = 0;
  angle_index = 0;
  inverse_park_transformation();
  svpwm_modulation();
  delay(500);
  int count = 0;
  uint16_t temporary;
  while(count != 2){
    temporary = readEncoder();
    count += 1;
  };
  ini_encoder_val = temporary & 0x3FFF;
  xTaskCreatePinnedToCore(
    ESPNOW_procedure,
    "Task_ESPNOW",
    4096,
    NULL,
    1,
    NULL,
    1
  );
  xTaskCreatePinnedToCore(
  ADC_lectures,
  "Task_ADCs",
  4096,
  NULL,
  3,
  NULL,
  0
  );
}

void loop(){}

uint16_t readEncoder(){
  SPI.beginTransaction(SPISettings(10000000, MSBFIRST, SPI_MODE1));
  digitalWrite(cs, LOW);
  uint16_t lectura = SPI.transfer16(0x3FFF);
  digitalWrite(cs, HIGH);
  SPI.endTransaction();
  return lectura;
}

inline void cp_transformations() {
  //***// Clarke transformation //***//
  // I_alpha = I_a
  I_beta = (((2 * I_b) + I_a) * 18919) >> 15; // 18919 is the inverse of sqrt(3) (0.57735) by 2^15

  //***// Park transformation //***//
  I_d = ((I_a * LUT_cos_angle_index[angle_index]) >> 15) + ((I_beta * LUT_sin_angle_index[angle_index]) >> 15);
  I_q = ((-I_a * LUT_sin_angle_index[angle_index]) >> 15) + ((I_beta * LUT_cos_angle_index[angle_index]) >> 15);
}

inline int PI_current_controller(PI_properties* properties, int error){
  properties->integral_val += (error * properties->K_i_dt) >> 15;
  if(properties->integral_val > 201326592) properties->integral_val = 201326592;
  if(properties->integral_val < -201326592) properties->integral_val = -201326592;
  return (((error * properties->K_p) >> 15) + (properties->integral_val >> 9));
}

inline void inverse_park_transformation(){
  //***// Inverse Park transformation //***//
  V_alpha = ((V_d * LUT_cos_angle_index[angle_index]) >> 15) - ((V_q * LUT_sin_angle_index[angle_index]) >> 15);
  V_beta = ((V_d * LUT_sin_angle_index[angle_index]) >> 15) + ((V_q * LUT_cos_angle_index[angle_index]) >> 15);
}

inline void svpwm_modulation(){
  //***// Inverse Clarke transformation //***//
  U = V_beta;
  V = ((V_alpha * 28378) >> 15) - ((V_beta * 16384) >> 15);
  W = ((-V_alpha * 28378) >> 15) - ((V_beta * 16384) >> 15);
  sector = 0;
  if (U > 0) sector += 1;
  if (V > 0) sector += 2;
  if (W > 0) sector += 4;
  switch(sector){
    case 3: t1 = W;  t2 = -V; break; // Sector 1
    case 1: t1 = -W; t2 = U;  break; // Sector 2
    case 5: t1 = V;  t2 = -U; break; // Sector 3
    case 4: t1 = -V; t2 = W;  break; // Sector 4
    case 6: t1 = U;  t2 = -W; break; // Sector 5
    case 2: t1 = -U; t2 = V;  break; // Sector 6
  }
  t0 = 32768 - t1 - t2;
  int32_t duty_u = 0, duty_v = 0, duty_w = 0;
  switch(sector){
    case 3: // Sector 1
      duty_u = t1 + t2 + (t0 >> 1);
      duty_v = t2 + (t0 >> 1);
      duty_w = (t0 >> 1);
      break;
    case 1: // Sector 2
      duty_u = t2 + (t0 >> 1);
      duty_v = t1 + t2 + (t0 >> 1);
      duty_w = (t0 >> 1);
      break;
    case 5: // Sector 3
      duty_u = (t0 >> 1);
      duty_v = t1 + t2 + (t0 >> 1);
      duty_w = t2 + (t0 >> 1);
      break;
    case 4: // Sector 4
      duty_u = (t0 >> 1);
      duty_v = t2 + (t0 >> 1);
      duty_w = t1 + t2 + (t0 >> 1);
      break;
    case 6: // Sector 5
      duty_u = t2 + (t0 >> 1);
      duty_v = (t0 >> 1);
      duty_w = t1 + t2 + (t0 >> 1);
      break;
    case 2: // Sector 6
      duty_u = t1 + t2 + (t0 >> 1);
      duty_v = (t0 >> 1);
      duty_w = t2 + (t0 >> 1);
      break;
  }
  uint32_t ticks_u = (duty_u * 4000) >> 15;
  uint32_t ticks_v = (duty_v * 4000) >> 15;
  uint32_t ticks_w = (duty_w * 4000) >> 15;
  mcpwm_comparator_set_compare_value(comparador_U, ticks_u);
  mcpwm_comparator_set_compare_value(comparador_V, ticks_v);
  mcpwm_comparator_set_compare_value(comparador_W, ticks_w);
}
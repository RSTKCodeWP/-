#include <esp_now.h>
#include <WiFi.h>
#include <AlfredoCRSF.h>
#include <HardwareSerial.h>

// Mavlink headers
#include <MAVLink_ardupilotmega.h>

typedef struct ControlPacket {
  int throttle;
  int roll;
  int pitch;
  int yaw;
  bool armed;
  bool toggleGpio;  // Add this field for GPIO toggle
} ControlPacket;

typedef struct HeartbeatPacket {
  bool isHeartbeat;
} HeartbeatPacket;

typedef struct AckPacket {
  bool heartbeatAck;
} AckPacket;

// Mavlink packet structure
typedef struct MavlinkPacket {
  uint8_t data[MAVLINK_MAX_PACKET_LEN];  // Mavlink packet data
  uint16_t len;                          // Length of the packet
  uint8_t target_system;                 // Target system ID
  uint8_t target_component;              // Target component ID
  uint32_t timestamp;                    // Timestamp when received
} MavlinkPacket;

typedef struct MavlinkTelemetry {
  float battery_voltage;
  float current;
  uint8_t battery_remaining;
  int32_t latitude;
  int32_t longitude;
  int32_t altitude;
  uint16_t heading;
  uint16_t ground_speed;
  uint16_t air_speed;
  int16_t pitch;
  int16_t roll;
  int16_t yaw;
  uint8_t flight_mode;
  uint8_t armed;
  uint8_t gps_fix_type;
  uint8_t gps_satellites_visible;
  uint32_t custom_mode;
  uint8_t base_mode;
  uint8_t system_status;
  uint16_t packet_drops;
} MavlinkTelemetry;

ControlPacket latestControl = {172, 992, 992, 992, false, false};

// Serial ports
HardwareSerial crsfSerialOut(1);
HardwareSerial mavlinkSerial(2);  // Use UART2 for Mavlink on GPIO20 (RX)

AlfredoCRSF crsfOut;

#define PIN_TX_OUT 10
#define PIN_RX_UNUSED -1
#define MAVLINK_RX_PIN 20          // GPIO20 for Mavlink RX (connect to T6 on SpeedyBee)
#define MAVLINK_TX_PIN 21          // Optional GPIO21 for Mavlink TX if needed
#define GPIO_2 2                   // Define GPIO pins
#define GPIO_8 8

bool connectionAlive = false;
unsigned long lastHeartbeatTime = 0;
const unsigned long HEARTBEAT_TIMEOUT = 2000;
bool gpioState = false;           // false = GPIO2 ON, GPIO8 OFF; true = GPIO2 OFF, GPIO8 ON
bool lastToggleState = false;     // Track previous toggle state to detect changes

// Mavlink variables
mavlink_message_t mav_msg;
mavlink_status_t mav_status;
MavlinkTelemetry telemetry = {0};
unsigned long lastMavlinkHeartbeat = 0;
const unsigned long MAVLINK_TIMEOUT = 5000;
bool mavlinkConnected = false;
uint8_t system_id = 1;            // Our system ID
uint8_t component_id = 1;         // Our component ID
uint8_t target_system = 1;        // Flight controller system ID
uint8_t target_component = 1;     // Flight controller component ID

// ESP-NOW peer address (replace with your transmitter MAC address)
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};  // Broadcast address
// OR use specific MAC: {0x24, 0x6F, 0x28, 0xXX, 0xXX, 0xXX}

// Forward declarations
void parseMavlinkMessage(mavlink_message_t* msg);
void sendMavlinkTelemetry();
void updateTelemetryFromMavlink(mavlink_message_t* msg);

void toggleGPIOs() {
  if (gpioState) {
    // GPIO2 OFF, GPIO8 ON
    digitalWrite(GPIO_2, LOW);
    digitalWrite(GPIO_8, HIGH);
    Serial.println("GPIO State: GPIO2 OFF, GPIO8 ON");
  } else {
    // GPIO2 ON, GPIO8 OFF
    digitalWrite(GPIO_2, HIGH);
    digitalWrite(GPIO_8, LOW);
    Serial.println("GPIO State: GPIO2 ON, GPIO8 OFF");
  }
}

// Callback when data is sent
void OnDataSent(const wifi_tx_info_t *info, esp_now_send_status_t status) {
  if (status == ESP_NOW_SEND_SUCCESS) {
    // Optional: track successful sends
  }
}

void onDataRecv(const esp_now_recv_info_t *info, const uint8_t *incomingData, int len) {
  if (len == sizeof(ControlPacket)) {
    memcpy(&latestControl, incomingData, len);
    Serial.println("✅ Control packet received:");
    Serial.print("Throttle: "); Serial.print(latestControl.throttle);
    Serial.print(", Roll: "); Serial.print(latestControl.roll);
    Serial.print(", Pitch: "); Serial.print(latestControl.pitch);
    Serial.print(", Yaw: "); Serial.print(latestControl.yaw);
    Serial.print(", Armed: "); Serial.print(latestControl.armed ? "YES" : "NO");
    Serial.print(", ToggleGPIO: "); Serial.println(latestControl.toggleGpio ? "ON" : "OFF");
    
    // Check if toggle command changed
    if (latestControl.toggleGpio != lastToggleState) {
      if (latestControl.toggleGpio) {
        // Toggle the GPIO state
        gpioState = !gpioState;
        toggleGPIOs();
      }
      lastToggleState = latestControl.toggleGpio;
    }
  } else if (len == sizeof(HeartbeatPacket)) {
    HeartbeatPacket hb;
    memcpy(&hb, incomingData, len);
    if (hb.isHeartbeat) {
      lastHeartbeatTime = millis();
      if (!connectionAlive) {
        connectionAlive = true;
        Serial.println("✅ Heartbeat received — connection established.");
      }

      // Respond with ACK
      AckPacket ack = {true};
      esp_now_send(info->src_addr, (uint8_t *)&ack, sizeof(ack));
      
      // Also send telemetry back
      sendMavlinkTelemetry();
    }
  }
}

void sendManualChannels() {
  crsf_channels_t ch = {0};

  if (connectionAlive) {
    ch.ch0 = latestControl.roll;
    ch.ch1 = latestControl.pitch;
    ch.ch2 = latestControl.throttle;
    ch.ch3 = latestControl.yaw;
    ch.ch4 = latestControl.armed ? 1805 : 172;
  } else {
    // Failsafe values
    ch.ch0 = ch.ch1 = 992;
    ch.ch2 = 172;
    ch.ch3 = 992;
    ch.ch4 = 172;
  }

  ch.ch5 = ch.ch6 = ch.ch7 = ch.ch8 = ch.ch9 = ch.ch10 = ch.ch11 = ch.ch12 = ch.ch13 = ch.ch14 = ch.ch15 = 172;

  crsfOut.writePacket(CRSF_SYNC_BYTE, CRSF_FRAMETYPE_RC_CHANNELS_PACKED, &ch, sizeof(ch));
}

// Parse incoming Mavlink messages
void parseMavlinkMessage(mavlink_message_t* msg) {
  switch (msg->msgid) {
    case MAVLINK_MSG_ID_HEARTBEAT: {
      mavlink_heartbeat_t heartbeat;
      mavlink_msg_heartbeat_decode(msg, &heartbeat);
      lastMavlinkHeartbeat = millis();
      
      if (!mavlinkConnected) {
        mavlinkConnected = true;
        Serial.println("📡 Mavlink connected!");
        
        // Request data stream
        mavlink_message_t req_msg;
        uint8_t req_buf[MAVLINK_MAX_PACKET_LEN];
        
        // Request data stream at specific rate
        mavlink_msg_request_data_stream_pack(system_id, component_id, &req_msg,
                                            target_system, target_component,
                                            MAV_DATA_STREAM_ALL, 10, 1);  // 10Hz
        uint16_t len = mavlink_msg_to_send_buffer(req_buf, &req_msg);
        mavlinkSerial.write(req_buf, len);
      }
      
      telemetry.base_mode = heartbeat.base_mode;
      telemetry.custom_mode = heartbeat.custom_mode;
      telemetry.system_status = heartbeat.system_status;
      telemetry.armed = (heartbeat.base_mode & MAV_MODE_FLAG_SAFETY_ARMED) ? 1 : 0;
      
      // Flight mode decoding
      if (telemetry.custom_mode >= 0 && telemetry.custom_mode < 16) {
        telemetry.flight_mode = telemetry.custom_mode;
      }
      break;
    }
    
    case MAVLINK_MSG_ID_SYS_STATUS: {
      mavlink_sys_status_t sys_status;
      mavlink_msg_sys_status_decode(msg, &sys_status);
      
      telemetry.battery_voltage = sys_status.voltage_battery / 1000.0f;  // mV to V
      telemetry.current = sys_status.current_battery / 100.0f;          // cA to A
      telemetry.battery_remaining = sys_status.battery_remaining;
      break;
    }
    
    case MAVLINK_MSG_ID_GPS_RAW_INT: {
      mavlink_gps_raw_int_t gps_raw;
      mavlink_msg_gps_raw_int_decode(msg, &gps_raw);
      
      telemetry.latitude = gps_raw.lat;
      telemetry.longitude = gps_raw.lon;
      telemetry.altitude = gps_raw.alt / 1000;  // mm to meters
      telemetry.ground_speed = gps_raw.vel / 100;  // cm/s to m/s
      telemetry.heading = gps_raw.cog / 100;  // cdeg to deg
      telemetry.gps_fix_type = gps_raw.fix_type;
      telemetry.gps_satellites_visible = gps_raw.satellites_visible;
      break;
    }
    
    case MAVLINK_MSG_ID_ATTITUDE: {
      mavlink_attitude_t attitude;
      mavlink_msg_attitude_decode(msg, &attitude);
      
      telemetry.pitch = attitude.pitch * RAD_TO_DEG;
      telemetry.roll = attitude.roll * RAD_TO_DEG;
      telemetry.yaw = attitude.yaw * RAD_TO_DEG;
      break;
    }
    
    case MAVLINK_MSG_ID_VFR_HUD: {
      mavlink_vfr_hud_t vfr_hud;
      mavlink_msg_vfr_hud_decode(msg, &vfr_hud);
      
      telemetry.ground_speed = vfr_hud.groundspeed;
      telemetry.air_speed = vfr_hud.airspeed;
      telemetry.heading = vfr_hud.heading;
      telemetry.altitude = vfr_hud.alt;
      break;
    }
    
    // Add more message parsers as needed
  }
  
  // Update packet drop counter
  if (msg->msgid != MAVLINK_MSG_ID_HEARTBEAT) {
    telemetry.packet_drops = mav_status.packet_rx_drop_count;
  }
}

// Send telemetry data over ESP-NOW
void sendMavlinkTelemetry() {
  if (!connectionAlive) return;
  
  // Send telemetry data
  esp_now_send(broadcastAddress, (uint8_t *)&telemetry, sizeof(telemetry));
}

// Forward raw Mavlink packets over ESP-NOW
void forwardMavlinkPacket(mavlink_message_t* msg) {
  if (!connectionAlive) return;
  
  MavlinkPacket mav_packet;
  uint16_t len = mavlink_msg_to_send_buffer(mav_packet.data, msg);
  mav_packet.len = len;
  mav_packet.target_system = msg->sysid;
  mav_packet.target_component = msg->compid;
  mav_packet.timestamp = millis();
  
  // Send via ESP-NOW
  esp_now_send(broadcastAddress, (uint8_t *)&mav_packet, sizeof(MavlinkPacket));
}

void setup() {
  Serial.begin(115200);
  Serial.println("Receiver Booting...");

  // Initialize GPIO pins
  pinMode(GPIO_2, OUTPUT);
  pinMode(GPIO_8, OUTPUT);
  
  // Set initial state: GPIO2 ON, GPIO8 OFF
  digitalWrite(GPIO_2, HIGH);
  digitalWrite(GPIO_8, LOW);
  gpioState = false;
  Serial.println("Initial GPIO State: GPIO2 ON, GPIO8 OFF");

  // Initialize Mavlink serial
  mavlinkSerial.begin(57600, SERIAL_8N1, MAVLINK_RX_PIN, MAVLINK_TX_PIN);
  Serial.println("Mavlink serial started on GPIO20");

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();

  if (esp_now_init() != ESP_OK) {
    Serial.println("ESP-NOW init failed");
    return;
  }

  // Register send callback
  esp_now_register_send_cb(OnDataSent);

  // Register peer
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }

  esp_now_register_recv_cb(onDataRecv);
  Serial.println("ESP-NOW Receiver Ready");

  crsfSerialOut.begin(CRSF_BAUDRATE, SERIAL_8N1, PIN_RX_UNUSED, PIN_TX_OUT);
  crsfOut.begin(crsfSerialOut);
  Serial.println("CRSF Started");
}

void loop() {
  unsigned long now = millis();

  // Check for Mavlink timeout
  if (now - lastMavlinkHeartbeat > MAVLINK_TIMEOUT) {
    if (mavlinkConnected) {
      mavlinkConnected = false;
      Serial.println("❌ Mavlink connection lost");
    }
  }

  // Check ESP-NOW connection timeout
  if (now - lastHeartbeatTime > HEARTBEAT_TIMEOUT) {
    if (connectionAlive) {
      connectionAlive = false;
      Serial.println("❌ ESP-NOW connection lost - heartbeat timeout.");
    }
  }

  // Read Mavlink data
  while (mavlinkSerial.available() > 0) {
    uint8_t c = mavlinkSerial.read();
    
    // Try to get a new message
    if (mavlink_parse_char(MAVLINK_COMM_0, c, &mav_msg, &mav_status)) {
      // Parse the message
      parseMavlinkMessage(&mav_msg);
      
      // Forward the raw packet over ESP-NOW (optional)
      // Uncomment if you want to forward raw packets:
      // forwardMavlinkPacket(&mav_msg);
    }
  }

  // Send telemetry periodically (every 500ms)
  static unsigned long lastTelemetrySend = 0;
  if (mavlinkConnected && connectionAlive && (now - lastTelemetrySend > 500)) {
    sendMavlinkTelemetry();
    lastTelemetrySend = now;
    
    // Optional: Print telemetry to serial
    Serial.printf("Battery: %.2fV, %.1fA, %d%%\n", 
                  telemetry.battery_voltage, 
                  telemetry.current, 
                  telemetry.battery_remaining);
  }

  // Send control channels
  if (connectionAlive) {
    sendManualChannels();
  }
  
  delay(20);
}
void read_Teensy(void *pvParameters){
  if(Serial1.available() < 0){

  }
}

void setup() {
  Serial1.begin(1000000);
  xTaskCreatePinnedToCore(
    read_Teensy,
    "Teensy_lecture",
    4096,
    NULL,
    3,
    NULL,
    0,
  );

  xTaskCreatePinnedToCore(
    send_packet,
    "Packet_sending",
    4096,
    NULL,
    3,
    NULL,
    1,
  );
}

void loop() {

}

#include <Arduino.h>

const int PIN_S = 6;
volatile int microsegundos_compartidos = 1000; 

void tareaConsolaSerial(void *pvParameters);
void tareaMotorPWM(void *pvParameters);

void setup() {
  Serial.begin(115200); 
  xTaskCreatePinnedToCore(
    tareaConsolaSerial,  
    "Tarea_Consola",     
    4096,                
    NULL,                
    1,                   
    NULL,                
    0                    
  );

  xTaskCreatePinnedToCore(
    tareaMotorPWM,       
    "Tarea_Motor",       
    4096,                
    NULL,                
    3,
    NULL,
    1
  );
}

void tareaConsolaSerial(void *pvParameters) {
  while(true) {
    if (Serial.available() > 0) {
      int porcentaje = Serial.parseInt();
      if (porcentaje >= 0 && porcentaje <= 100) {
        microsegundos_compartidos = map(porcentaje, 0, 100, 1000, 2000);
      }
      while(Serial.available() > 0) {
        Serial.read();
      }
    }
    
    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

void tareaMotorPWM(void *pvParameters) {
  pinMode(PIN_S, OUTPUT);
  unsigned long inicio = millis();
  while(millis() - inicio < 5000) {
    digitalWrite(PIN_S, HIGH);
    delayMicroseconds(1000);
    digitalWrite(PIN_S, LOW);
    delay(19);
  }
  while(1) {
    int tiempo_alto = microsegundos_compartidos; 
    digitalWrite(PIN_S, HIGH);
    delayMicroseconds(tiempo_alto);
    digitalWrite(PIN_S, LOW);
    int tiempo_bajo = 20 - (tiempo_alto / 1000);
    delay(tiempo_bajo);
  }
}

void loop() {
  vTaskDelay(pdMS_TO_TICKS(1000));
}
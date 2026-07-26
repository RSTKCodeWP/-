#include "compass_module.h"

#ifdef MODULE_COMPASS

CompassModule compassModule;

CompassModule::CompassModule() : currentAzimuth(0), isCalibrated(false), isActive(false) {}

bool CompassModule::begin() {
    Serial.println("[INIT] QMC5883L Compass Module...");
    compass.init();
    
    // Default calibration values. Should be replaced with actual calibration.
    // compass.setCalibration(-1000, 1000, -1000, 1000, -1000, 1000);
    
    isActive = true;
    return true;
}

void CompassModule::update() {
    if (!isActive) return;
    
    compass.read();
    
    // Return Azimuth reading
    int a = compass.getAzimuth();
    
    // Adjust if necessary based on module orientation
    
    // Simple low pass filter
    currentAzimuth = (currentAzimuth * 3 + a) / 4;
}

int CompassModule::getAzimuth() const {
    return currentAzimuth;
}

bool CompassModule::isValid() const {
    return isActive;
}

#endif // MODULE_COMPASS

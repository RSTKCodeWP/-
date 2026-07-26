#ifndef COMPASS_MODULE_H
#define COMPASS_MODULE_H

#include "config.h"

#ifdef MODULE_COMPASS
#include <Arduino.h>
#include <QMC5883LCompass.h>

class CompassModule {
private:
    QMC5883LCompass compass;
    int currentAzimuth;
    bool isCalibrated;
    bool isActive;

public:
    CompassModule();
    bool begin();
    void update();
    int getAzimuth() const;
    bool isValid() const;
};

extern CompassModule compassModule;

#endif // MODULE_COMPASS
#endif // COMPASS_MODULE_H

// telemetry.h

#ifndef TELEMETRY_H
#define TELEMETRY_H

struct TelemetryPacket {

    float batteryVoltage;

    float latitude;
    float longitude;

    int altitude;

    int signalStrength;

    bool gpsFix;
};

#endif
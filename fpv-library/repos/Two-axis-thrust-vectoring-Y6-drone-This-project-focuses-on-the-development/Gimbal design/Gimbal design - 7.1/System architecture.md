# Gimbal design - 7.1

System architecture

    BODY
        6S-5V Matek converter - 1x
        Teensy 4.1 - 1x
        ESP32-S3 SuperMini ESP-NOW command transmitter - 1x
        ESP32-S3 SuperMini ESP-NOW error report receiver - 1x
        1800MAh 100C 6S battery - 1x
        200A PDB - 1x
    BODY - AXIS 1
        Fixed side (BODY)
            6S-5V Matek converter - 1x
            ESP32-S3 SuperMini BODY - AXIS 1 local controller - 1x
            GM3506 gimbal motor with belt drive reduction system - 1x
            AS5048A SPI module - 1x
            DRV8313 FOC motor driver - 1x
        Rotating side (AXIS 1)
            Pulley for the GM3506 - 1x
        Extra rotating side (1:1 gear system)
            Diametrically magnetized magnet - 1x
        Shared interface components
            20A 2CH slip ring - 2x
            6703RS bearing - 2x
    AXIS 1 - AXIS 2
        Fixed side (AXIS 1)
            6S-5V Matek converter - 1x
            ESP32-S3 SuperMini AXIS 1 - AXIS 2 local controller - 1x
            GM3506 gimbal motor with belt drive reduction system - 1x
            AS5048A SPI module - 1x
            DRV8313 FOC motor driver - 1x
        Rotating side (AXIS 2)
            6S-5V Matek converter - 1x
            ESP32-S3 SuperMini ESCs local controller - 1x
            Pulley for the GM3506 - 1x
            2207 1800KV 6S motor - 2x
            HQProp MCK 5130 - 2x
            ESC AM32 40A 6S - 2x
            Motor holder structure - 1x
        Extra rotating side (1:1 gear system)
            Diametrically magnetized magnet - 1x
        Shared interface components
            20A 2CH slip ring - 2x
            6703RS bearing - 2x

# Gimbal design - 5.0

System architecture

    BODY - AXIS 1
        BODY
            Teensy 4.1 - 1x
            SN65HVD230 CAN transceiver - 1x
            120 ohm resistor for the CAN bus echo in parallel on the CAN transceiver - 1x
            6S battery - 1x
            6S-5/12V converter for the motor driver - 1x
            DRVxxxx FOC motor driver with CAN bus - 1x
            GM3506 gimbal motor with belt drive reduction system - 1x
            30A 4CH Senring - () part - 1x
            6CH gimbal motor power supply and CAN bus slip ring - () part - 1x
            Bearing - () part - 2x
            AS5048A SPI module - 1x
        AXIS 1
            Diametrically magnetized magnet - 1x
            30A 4CH Senring - () part - 1x
            6CH gimbal motor power supply and CAN bus slip ring - () part - 1x
            Bearing - () part - 2x
            Pulley for the GM3506 - 1x
    AXIS 1 - AXIS 2
        AXIS 1
            6S-5/12V converter for the motor driver - 1x
            DRVxxxx FOC motor driver with CAN bus - 1x
            GM3506 gimbal motor with belt drive reduction system - 1x
            30A 4CH Senring - () part - 1x
            4CH CAN bus slip ring - () part - 1x
            Bearing - () part - 2x
            AS5048A SPI module - 1x
        AXIS 2
            Diametrically magnetized magnet - 1x
            30A 4CH Senring - () part - 1x
            4CH CAN bus slip ring - () part - 1x
            Bearing - () part - 2x
            Pulley for the GM3506 - 1x
            2004 1800KV 6S motor - 2x
            2-in-1 ESC with CAN bus - 1x
            120 ohm resistor for the CAN bus echo in parallel on the 2-in-1 ESC - 1x
            Motor holder structure - 1x

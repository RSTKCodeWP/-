# Node Reference

All nodes are organized into 7 categories. Each node has typed input/output ports and configurable properties.

## Sensors

Sensor nodes read data from the flight controller. They have no inputs and provide output values each cycle.

| Node | Outputs | Properties | API |
| --- | --- | --- | --- |
| GPS Position | Latitude, Longitude, Altitude (m) | - | `gps:location(0)` |
| Baro Altitude | Altitude (m) | - | `baro:get_altitude()` |
| Battery | Voltage, Current (A), Remaining % | Battery Instance (0-3) | `battery` |
| Airspeed | Airspeed (m/s) | - | `ahrs:airspeed_estimate()` |
| RC Channel | Value (us) | Channel (1-16) | `rc:get_pwm(ch)` |
| Rangefinder | Distance (m) | Instance (0-3) | `rangefinder:distance_cm()` |
| Attitude | Roll, Pitch, Yaw (deg) | - | `ahrs:get_roll/pitch/yaw()` |
| Ground Speed | Speed (m/s) | - | `ahrs:groundspeed_vector()` |
| RC Aux Switch | State (0-2), Is High, Is Mid | Aux Function (0-999) | `rc:get_aux_cached()` |
| Rangefinder (Oriented) | Distance (m) | Orientation (Forward/Down/Up) | `rangefinder:distance_cm_orient()` |

## Logic

Logic nodes handle boolean and comparison operations for decision-making.

| Node | Inputs | Outputs | Properties |
| --- | --- | --- | --- |
| Compare | A (number), B (number) | Result (boolean) | Operator: >, <, ==, !=, >=, <= |
| If / Else | Condition (boolean) | True, False | - |
| AND | A (boolean), B (boolean) | Result (boolean) | - |
| OR | A (boolean), B (boolean) | Result (boolean) | - |
| NOT | Input (boolean) | Result (boolean) | - |
| Range Check | Value (number) | In Range (boolean) | Min, Max |
| Switch | Value (number) | Case 0, Case 1, Case 2, Default | Case 0/1/2 Values |

## Math

Math nodes perform numeric calculations.

| Node | Inputs | Outputs | Properties |
| --- | --- | --- | --- |
| Add | A, B | Result | - |
| Subtract | A, B | Result | - |
| Multiply | A, B | Result | - |
| Divide | A, B | Result (zero-safe) | - |
| Clamp | Value | Result | Min, Max |
| Map Range | Value | Result | Input Min/Max, Output Min/Max |
| Abs | Value | Result | - |
| Min | A, B | Result | - |
| Max | A, B | Result | - |

## Actions

Action nodes produce side effects like sending messages, controlling servos, or writing files. They require a **boolean trigger** input - the action only fires when the trigger is `true`.

| Node | Inputs | Properties | API |
| --- | --- | --- | --- |
| Send GCS Text | Trigger | Message, Severity (Emergency..Debug) | `gcs:send_text()` |
| Set Servo | Trigger, PWM (number) | Servo Number (1-16) | `SRV_Channels:set_output_pwm()` |
| Set Flight Mode | Trigger | Mode Number (0-30) | `vehicle:set_mode()` |
| Set Parameter | Trigger, Value (number) | Parameter Name | `param:set()` |
| Trigger Relay | Trigger | Relay Number (0-5), State (ON/OFF) | `relay:on/off()` |
| Log to File | Trigger, Value 1-3 (any) | File Name, Separator | `io.open/write/close` |
| Set LED | Trigger, R, G, B (numbers) | LED Instance (0-15) | `serialLED:set_RGB()` |

## Timing

Timing nodes control when and how often things happen.

| Node | Inputs | Outputs | Properties |
| --- | --- | --- | --- |
| Run Every | Trigger (boolean) | Flow (boolean) | Interval (100-60000 ms) |
| Debounce | Input (boolean) | Output (boolean) | Delay (50-10000 ms) |
| On Change | Value (number) | Changed (boolean) | - |
| Rising Edge | Input (boolean) | Triggered (boolean) | - |

## Variables

Variable nodes let you store and retrieve values that persist across update cycles.

| Node | Inputs | Outputs | Properties |
| --- | --- | --- | --- |
| Constant | - | Value (any) | Type (Number/String/Boolean), Value |
| Get Variable | - | Value (any) | Variable Name |
| Set Variable | Trigger, Value (any) | - | Variable Name |

## Flow

Utility nodes for organizing your graph.

| Node | Purpose |
| --- | --- |
| Comment | A text label for documentation - no effect on compiled code |

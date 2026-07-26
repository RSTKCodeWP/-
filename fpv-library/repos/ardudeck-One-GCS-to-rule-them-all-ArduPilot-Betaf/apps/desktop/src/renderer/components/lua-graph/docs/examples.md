# Examples

## Example 1: Low Battery Alert

**Goal:** Send a warning to the GCS when battery drops below 11.1V.

### Nodes

1. **Battery** sensor - reads voltage
2. **Constant** - value `11.1`
3. **Compare** - operator `<` (less than)
4. **Debounce** - 5000ms delay to avoid spamming
5. **Send GCS Text** - message "LOW BATTERY", severity Warning

### Connections

- Battery **Voltage** -> Compare **A**
- Constant **Value** -> Compare **B**
- Compare **Result** -> Debounce **Input**
- Debounce **Output** -> Send GCS Text **Trigger**

### Generated Lua

```lua
local WARN_SENT = false

function update()
  local voltage = battery:voltage(0)
  local is_low = voltage < 11.1

  if is_low and not WARN_SENT then
    gcs:send_text(4, "LOW BATTERY")
    WARN_SENT = true
  elseif not is_low then
    WARN_SENT = false
  end

  return update, 1000
end

return update, 1000
```

---

## Example 2: Geofence Distance Warning

**Goal:** Alert the pilot when the vehicle is more than 500m from home.

### Nodes

1. **GPS Position** sensor
2. **Constant** - value `500`
3. **Compare** - operator `>`
4. **Send GCS Text** - message "GEOFENCE WARNING"

> Note: GPS Position provides raw latitude/longitude. The compiler calculates distance from home using the ArduPilot `ahrs:get_home()` API.

---

## Example 3: Camera Trigger on RC Switch

**Goal:** Trigger a relay when RC channel 7 goes above 1700us.

### Nodes

1. **RC Channel** sensor - channel 7
2. **Constant** - value `1700`
3. **Compare** - operator `>`
4. **Rising Edge** - fire only on the transition
5. **Trigger Relay** - relay 0, state ON

### Connections

- RC Channel **Value** -> Compare **A**
- Constant **Value** -> Compare **B**
- Compare **Result** -> Rising Edge **Input**
- Rising Edge **Triggered** -> Trigger Relay **Trigger**

### Generated Lua

```lua
local prev_state = false

function update()
  local ch7 = rc:get_pwm(7)
  local is_high = ch7 > 1700

  local rising = is_high and not prev_state
  prev_state = is_high

  if rising then
    relay:on(0)
  end

  return update, 200
end

return update, 200
```

---

## Example 4: Terrain Follow with Rangefinder

**Goal:** Log rangefinder altitude to a CSV file every 2 seconds.

### Nodes

1. **Rangefinder** sensor - instance 0
2. **Run Every** - 2000ms interval
3. **Baro Altitude** sensor
4. **Log to File** - filename `terrain.csv`, comma separator

### Connections

- Run Every **Flow** -> Log to File **Trigger**
- Rangefinder **Distance** -> Log to File **Value 1**
- Baro Altitude **Altitude** -> Log to File **Value 2**

The resulting CSV file on the SD card will contain timestamped rangefinder and barometric altitude data.

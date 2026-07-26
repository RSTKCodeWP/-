# ArduPilot Lua API Reference

The graph editor generates code using the ArduPilot Lua scripting API. Here are the key bindings available and what they do.

## Core Objects

### gcs (Ground Control Station)

```lua
gcs:send_text(severity, message)
```

Send a message to the GCS. Severity levels: 0=Emergency, 1=Alert, 2=Critical, 3=Error, 4=Warning, 5=Notice, 6=Info, 7=Debug.

### vehicle

```lua
vehicle:set_mode(mode_number)
vehicle:get_mode()
vehicle:is_armed()
```

Control and query vehicle state. Mode numbers are vehicle-specific (e.g., Plane: 0=Manual, 10=Auto, 11=RTL).

### ahrs (Attitude and Heading)

```lua
ahrs:get_roll()     -- radians
ahrs:get_pitch()    -- radians
ahrs:get_yaw()      -- radians
ahrs:get_home()     -- Location object
ahrs:groundspeed_vector()
ahrs:airspeed_estimate()
```

Access attitude, position, and velocity data.

### baro (Barometer)

```lua
baro:get_altitude()  -- meters above ground
```

### battery

```lua
battery:voltage(instance)
battery:current_amps(instance)
battery:capacity_remaining_pct(instance)
```

Read battery data. Instance 0 is the primary battery.

### rc (Radio Control)

```lua
rc:get_pwm(channel)          -- 1-16, returns PWM in microseconds
rc:get_aux_cached(aux_fn)    -- returns switch position 0/1/2
```

Read RC input channels and aux switch states.

### SRV_Channels (Servo Outputs)

```lua
SRV_Channels:set_output_pwm(channel, pwm)
SRV_Channels:set_output_pwm_chan_timeout(channel, pwm, timeout_ms)
```

Control servo outputs. Use `set_output_pwm_chan_timeout` for temporary overrides.

### param (Parameters)

```lua
param:get(name)           -- returns value or nil
param:set(name, value)    -- returns true on success
param:set_and_save(name, value)
```

Read and write flight controller parameters.

### rangefinder

```lua
rangefinder:distance_cm(instance)
rangefinder:distance_cm_orient(orientation)
```

Orientations: 0=Forward, 24=Up, 25=Down.

### relay

```lua
relay:on(relay_num)
relay:off(relay_num)
relay:toggle(relay_num)
```

Control relay outputs (0-5).

### serialLED

```lua
serialLED:set_num_neopixel(instance, count)
serialLED:set_RGB(instance, led_index, r, g, b)
serialLED:send(instance)
```

Control NeoPixel / ProfiLED strips.

## Script Lifecycle

Every ArduPilot Lua script follows this pattern:

```lua
function update()
  -- Your logic here
  return update, interval_ms
end

return update, interval_ms
```

The `return update, interval_ms` tells ArduPilot to call `update()` again after `interval_ms` milliseconds. The graph editor handles this automatically based on the **Run Interval** setting.

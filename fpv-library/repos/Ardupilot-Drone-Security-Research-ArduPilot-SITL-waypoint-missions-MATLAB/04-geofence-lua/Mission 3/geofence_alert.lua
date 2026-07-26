-- Geofence Breach Alert System
-- Monitors drone position vs configured geofence and alerts on breach.

-- Read fence parameters once at load
local FENCE_ENABLE   = Parameter()
local FENCE_RADIUS   = Parameter()
local FENCE_ALT_MAX  = Parameter()
FENCE_ENABLE:init('FENCE_ENABLE')
FENCE_RADIUS:init('FENCE_RADIUS')
FENCE_ALT_MAX:init('FENCE_ALT_MAX')

-- Tunables
local CHECK_INTERVAL_MS = 1000     -- run every 1 second
local WARNING_FRACTION  = 0.80     -- warn at 80% of limit

-- State (so we don't spam identical messages every second)
local was_breached_radius = false
local was_breached_alt    = false
local was_warning_radius  = false
local was_warning_alt     = false
local breach_count        = 0

gcs:send_text(6, "GeoFence script loaded")  -- severity 6 = INFO

local function update()
    -- Bail out cleanly if fence is not enabled
    if FENCE_ENABLE:get() ~= 1 then
        return update, CHECK_INTERVAL_MS
    end

    local fence_radius  = FENCE_RADIUS:get()   -- meters
    local fence_alt_max = FENCE_ALT_MAX:get()  -- meters

    -- Get current position and home position (Location userdata)
    local pos  = ahrs:get_position()
    local home = ahrs:get_home()

    if pos == nil or home == nil then
        return update, CHECK_INTERVAL_MS
    end

    -- Horizontal distance from home, in meters
    local dist = pos:get_distance(home)

    -- Altitude above home (Location alt is in cm by default in ArduPilot)
    -- pos:alt() returns cm in the location's altitude frame; we use 'above home'
    local alt_m = (pos:alt() - home:alt()) / 100.0

    -- ----- Radius check -----
    if dist > fence_radius then
        if not was_breached_radius then
            breach_count = breach_count + 1
            -- severity 0 = EMERGENCY (highest), shows in red in GCS
            gcs:send_text(0, string.format(
                "*** FENCE BREACH (radius): %.1fm out of %.0fm fence ***",
                dist, fence_radius))
        end
        was_breached_radius = true
        was_warning_radius  = true   -- skip warning state
    elseif dist > fence_radius * WARNING_FRACTION then
        if not was_warning_radius then
            gcs:send_text(4, string.format(
                "GeoFence WARNING: approaching radius (%.1fm of %.0fm)",
                dist, fence_radius))
        end
        was_warning_radius  = true
        was_breached_radius = false
    else
        -- back inside, reset state
        if was_breached_radius or was_warning_radius then
            gcs:send_text(6, "GeoFence: back inside radius")
        end
        was_breached_radius = false
        was_warning_radius  = false
    end

    -- ----- Altitude check -----
    if alt_m > fence_alt_max then
        if not was_breached_alt then
            breach_count = breach_count + 1
            gcs:send_text(0, string.format(
                "*** FENCE BREACH (altitude): %.1fm above %.0fm ceiling ***",
                alt_m, fence_alt_max))
        end
        was_breached_alt = true
        was_warning_alt  = true
    elseif alt_m > fence_alt_max * WARNING_FRACTION then
        if not was_warning_alt then
            gcs:send_text(4, string.format(
                "GeoFence WARNING: approaching alt ceiling (%.1fm of %.0fm)",
                alt_m, fence_alt_max))
        end
        was_warning_alt  = true
        was_breached_alt = false
    else
        if was_breached_alt or was_warning_alt then
            gcs:send_text(6, "GeoFence: back below alt ceiling")
        end
        was_breached_alt = false
        was_warning_alt  = false
    end

    return update, CHECK_INTERVAL_MS
end

return update, 2000   -- first run 2 seconds after load

package telemetry

import (
	"math"
	"testing"
	"time"

	"github.com/alexbezu/goosd/internal/hud"
	"github.com/bluenviron/gomavlib/v3/pkg/dialects/common"
)

func TestMAVLinkSourceApplyMessages(t *testing.T) {
	source := &MAVLinkSource{
		now: time.Now,
		state: hud.State{
			Health: hud.HealthTelemetryLost,
		},
	}
	now := time.Date(2026, 5, 7, 12, 0, 0, 0, time.UTC)

	source.apply(&common.MessageHeartbeat{
		Autopilot:    common.MAV_AUTOPILOT_GENERIC,
		BaseMode:     common.MAV_MODE_FLAG_SAFETY_ARMED,
		CustomMode:   1,
		SystemStatus: common.MAV_STATE_ACTIVE,
	}, now)
	source.apply(&common.MessageAttitude{
		Roll:  float32(math.Pi / 6),
		Pitch: float32(-math.Pi / 12),
		Yaw:   float32(math.Pi),
	}, now)
	source.apply(&common.MessageVfrHud{
		Heading:     181,
		Alt:         123.4,
		Groundspeed: 22.5,
	}, now)
	source.apply(&common.MessageGpsRawInt{
		FixType:           common.GPS_FIX_TYPE_3D_FIX,
		Eph:               90,
		SatellitesVisible: 11,
	}, now)
	source.apply(&common.MessageBatteryStatus{
		Voltages:         [10]uint16{3700, 3710, 3690, math.MaxUint16, math.MaxUint16, math.MaxUint16, math.MaxUint16, math.MaxUint16, math.MaxUint16, math.MaxUint16},
		CurrentBattery:   842,
		BatteryRemaining: 73,
	}, now)
	source.apply(&common.MessageRadioStatus{
		Rssi:     198,
		Remrssi:  87,
		Remnoise: uint8(hud.WFBLinkJammed),
		Rxerrors: 3,
		Fixed:    12,
	}, now)
	source.apply(&common.MessageRcChannelsRaw{
		Rssi: 72,
	}, now)

	state := source.State(now)

	if !state.Health.Has(hud.HealthArmed) {
		t.Fatal("state should be armed")
	}
	if !state.Flight.ModeValid || state.Flight.Mode != "ACRO" {
		t.Fatalf("flight mode = %v/%q, want valid ACRO", state.Flight.ModeValid, state.Flight.Mode)
	}
	if state.Health.Has(hud.HealthTelemetryLost) {
		t.Fatal("telemetry should be marked present after a message")
	}
	if !closeEnough(state.Attitude.RollDeg, 30) {
		t.Fatalf("roll = %v, want 30", state.Attitude.RollDeg)
	}
	if !closeEnough(state.Attitude.PitchDeg, -15) {
		t.Fatalf("pitch = %v, want -15", state.Attitude.PitchDeg)
	}
	if state.Heading.Deg != 181 {
		t.Fatalf("heading = %v, want 181", state.Heading.Deg)
	}
	if !closeEnough(state.AltitudeM, 123.4) {
		t.Fatalf("altitude = %v, want 123.4", state.AltitudeM)
	}
	if !closeEnough(state.SpeedMS, 22.5) {
		t.Fatalf("speed = %v, want 22.5", state.SpeedMS)
	}
	if state.GPS.FixType != hud.GPSFix3D {
		t.Fatalf("gps fix = %v, want %v", state.GPS.FixType, hud.GPSFix3D)
	}
	if state.GPS.Satellites != 11 {
		t.Fatalf("satellites = %v, want 11", state.GPS.Satellites)
	}
	if state.GPS.HDOP != 0.9 {
		t.Fatalf("hdop = %v, want 0.9", state.GPS.HDOP)
	}
	if !state.Battery.RemainingPctValid || state.Battery.RemainingPct != 73 {
		t.Fatalf("battery pct = %v/%v, want valid 73", state.Battery.RemainingPctValid, state.Battery.RemainingPct)
	}
	if !state.Battery.VoltageValid || !closeEnough(state.Battery.VoltageV, 11.1) {
		t.Fatalf("battery voltage = %v/%v, want valid 11.1", state.Battery.VoltageValid, state.Battery.VoltageV)
	}
	if !state.Battery.CurrentValid || !closeEnough(state.Battery.CurrentA, 8.42) {
		t.Fatalf("battery current = %v/%v, want valid 8.42", state.Battery.CurrentValid, state.Battery.CurrentA)
	}
	if !state.Radio.RCRSSIValid || state.Radio.RCRSSI != 72 {
		t.Fatalf("rc rssi = %v/%v, want valid 72", state.Radio.RCRSSIValid, state.Radio.RCRSSI)
	}
	if !state.Radio.WFBRSSIValid || state.Radio.WFBRSSIDBm != -58 {
		t.Fatalf("wfb rssi = %v/%v, want valid -58", state.Radio.WFBRSSIValid, state.Radio.WFBRSSIDBm)
	}
	if !state.Radio.WFBLinkQualityValid || state.Radio.WFBLinkQualityPct != 87 {
		t.Fatalf("wfb link quality = %v/%v, want valid 87", state.Radio.WFBLinkQualityValid, state.Radio.WFBLinkQualityPct)
	}
	if state.Radio.WFBRxErrors != 3 || state.Radio.WFBFECFixed != 12 {
		t.Fatalf("wfb counters = F%d L%d, want F12 L3", state.Radio.WFBFECFixed, state.Radio.WFBRxErrors)
	}
	if !state.Radio.WFBFlags.Has(hud.WFBLinkJammed) {
		t.Fatalf("wfb flags = %v, want jammed", state.Radio.WFBFlags)
	}
}

func TestMAVLinkSourceTelemetryTimeout(t *testing.T) {
	now := time.Date(2026, 5, 7, 12, 0, 0, 0, time.UTC)
	source := &MAVLinkSource{
		state: hud.State{
			Health:    hud.HealthArmed,
			UpdatedAt: now,
		},
	}

	state := source.State(now.Add(4 * time.Second))

	if !state.Health.Has(hud.HealthTelemetryLost) {
		t.Fatal("telemetry timeout should set HealthTelemetryLost")
	}
}

func TestGPSFixType(t *testing.T) {
	tests := []struct {
		in   common.GPS_FIX_TYPE
		want hud.GPSFixType
	}{
		{common.GPS_FIX_TYPE_NO_FIX, hud.GPSFixNone},
		{common.GPS_FIX_TYPE_2D_FIX, hud.GPSFix2D},
		{common.GPS_FIX_TYPE_3D_FIX, hud.GPSFix3D},
		{common.GPS_FIX_TYPE_RTK_FIXED, hud.GPSFix3D},
	}

	for _, test := range tests {
		if got := gpsFixType(test.in); got != test.want {
			t.Fatalf("gpsFixType(%v) = %v, want %v", test.in, got, test.want)
		}
	}
}

func TestBatteryStatusLowAndUnknownValues(t *testing.T) {
	source := &MAVLinkSource{}
	now := time.Date(2026, 5, 7, 12, 0, 0, 0, time.UTC)

	source.apply(&common.MessageBatteryStatus{
		Voltages:         [10]uint16{math.MaxUint16, math.MaxUint16, math.MaxUint16, math.MaxUint16, math.MaxUint16, math.MaxUint16, math.MaxUint16, math.MaxUint16, math.MaxUint16, math.MaxUint16},
		CurrentBattery:   -1,
		BatteryRemaining: 20,
	}, now)

	state := source.State(now)

	if !state.Health.Has(hud.HealthLowBattery) {
		t.Fatal("battery remaining <= 20 should set low battery health")
	}
	if !state.Battery.RemainingPctValid || state.Battery.RemainingPct != 20 {
		t.Fatalf("battery pct = %v/%v, want valid 20", state.Battery.RemainingPctValid, state.Battery.RemainingPct)
	}
	if state.Battery.VoltageValid {
		t.Fatalf("battery voltage should be invalid, got %v", state.Battery.VoltageV)
	}
	if state.Battery.CurrentValid {
		t.Fatalf("battery current should be invalid, got %v", state.Battery.CurrentA)
	}
}

func TestRadioStatusUnknownValues(t *testing.T) {
	source := &MAVLinkSource{}
	now := time.Date(2026, 5, 7, 12, 0, 0, 0, time.UTC)

	source.apply(&common.MessageRadioStatus{
		Rssi:     math.MaxUint8,
		Remrssi:  math.MaxUint8,
		Remnoise: uint8(hud.WFBLinkLost),
		Rxerrors: 9,
		Fixed:    4,
	}, now)

	state := source.State(now)

	if state.Radio.RCRSSIValid {
		t.Fatalf("rc rssi should be invalid, got %d", state.Radio.RCRSSI)
	}
	if state.Radio.WFBRSSIValid {
		t.Fatalf("wfb rssi should be invalid, got %d", state.Radio.WFBRSSIDBm)
	}
	if state.Radio.WFBLinkQualityValid {
		t.Fatalf("wfb link quality should be invalid, got %d", state.Radio.WFBLinkQualityPct)
	}
	if !state.Radio.WFBFlags.Has(hud.WFBLinkLost) {
		t.Fatalf("wfb flags = %v, want link lost", state.Radio.WFBFlags)
	}
	if state.Radio.WFBRxErrors != 9 || state.Radio.WFBFECFixed != 4 {
		t.Fatalf("wfb counters = F%d L%d, want F4 L9", state.Radio.WFBFECFixed, state.Radio.WFBRxErrors)
	}
}

func TestFlightModeFromHeartbeat(t *testing.T) {
	tests := []struct {
		name string
		msg  common.MessageHeartbeat
		want string
	}{
		{
			name: "betaflight acro",
			msg: common.MessageHeartbeat{
				Autopilot:  common.MAV_AUTOPILOT_GENERIC,
				CustomMode: 1,
			},
			want: "ACRO",
		},
		{
			name: "betaflight stabilize",
			msg: common.MessageHeartbeat{
				Autopilot:  common.MAV_AUTOPILOT_GENERIC,
				CustomMode: 0,
			},
			want: "STAB",
		},
		{
			name: "auto flag",
			msg: common.MessageHeartbeat{
				BaseMode: common.MAV_MODE_FLAG_AUTO_ENABLED | common.MAV_MODE_FLAG_STABILIZE_ENABLED,
			},
			want: "AUTO",
		},
		{
			name: "guided flag",
			msg: common.MessageHeartbeat{
				BaseMode: common.MAV_MODE_FLAG_GUIDED_ENABLED,
			},
			want: "GUIDED",
		},
		{
			name: "manual flag",
			msg: common.MessageHeartbeat{
				BaseMode: common.MAV_MODE_FLAG_MANUAL_INPUT_ENABLED,
			},
			want: "MANUAL",
		},
		{
			name: "custom fallback",
			msg: common.MessageHeartbeat{
				BaseMode:   common.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
				CustomMode: 42,
			},
			want: "CUSTOM 42",
		},
	}

	for _, test := range tests {
		if got := flightMode(&test.msg); got != test.want {
			t.Fatalf("%s: flightMode() = %q, want %q", test.name, got, test.want)
		}
	}
}

func TestRCRSSIFromRcChannelsMessages(t *testing.T) {
	source := &MAVLinkSource{}
	now := time.Date(2026, 5, 7, 12, 0, 0, 0, time.UTC)

	source.apply(&common.MessageRcChannelsRaw{
		Rssi: 254,
	}, now)
	state := source.State(now)
	if !state.Radio.RCRSSIValid || state.Radio.RCRSSI != 100 {
		t.Fatalf("raw rc rssi = %v/%v, want valid 100", state.Radio.RCRSSIValid, state.Radio.RCRSSI)
	}

	source.apply(&common.MessageRcChannels{
		Rssi: 64,
	}, now)
	state = source.State(now)
	if !state.Radio.RCRSSIValid || state.Radio.RCRSSI != 64 {
		t.Fatalf("rc channels rssi = %v/%v, want valid 64", state.Radio.RCRSSIValid, state.Radio.RCRSSI)
	}

	source.apply(&common.MessageRcChannelsRaw{
		Rssi: math.MaxUint8,
	}, now)
	state = source.State(now)
	if !state.Radio.RCRSSIValid || state.Radio.RCRSSI != 64 {
		t.Fatalf("invalid rssi should preserve previous value, got %v/%v", state.Radio.RCRSSIValid, state.Radio.RCRSSI)
	}
}

func closeEnough(got, want float64) bool {
	return math.Abs(got-want) < 0.0001
}

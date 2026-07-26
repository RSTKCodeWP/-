package main

import (
	"testing"
	"time"

	"github.com/alexbezu/goosd/internal/hud"
)

func TestLayoutUsesHUDSize(t *testing.T) {
	game := NewGame(hud.NewSimulator(time.Now()))

	width, height := game.Layout(1, 1)

	if width != screenWidth || height != screenHeight {
		t.Fatalf("Layout() = %dx%d, want %dx%d", width, height, screenWidth, screenHeight)
	}
}

func TestNormalize360(t *testing.T) {
	tests := []struct {
		in   float64
		want float64
	}{
		{-1, 359},
		{0, 0},
		{361, 1},
		{720, 0},
	}

	for _, test := range tests {
		if got := normalize360(test.in); got != test.want {
			t.Fatalf("normalize360(%v) = %v, want %v", test.in, got, test.want)
		}
	}
}

func TestHealthTextPriority(t *testing.T) {
	tests := []struct {
		health hud.Health
		want   string
	}{
		{0, "DISARMED"},
		{hud.HealthArmed, "ARMED"},
		{hud.HealthArmed | hud.HealthLowBattery, "LOW BAT"},
		{hud.HealthArmed | hud.HealthTelemetryLost, "NO TELEMETRY"},
		{hud.HealthArmed | hud.HealthFailsafe | hud.HealthLowBattery, "FAILSAFE"},
	}

	for _, test := range tests {
		if got := healthText(test.health); got != test.want {
			t.Fatalf("healthText(%v) = %q, want %q", test.health, got, test.want)
		}
	}
}

func TestBatteryText(t *testing.T) {
	got := batteryText(hud.Battery{
		RemainingPct:      73,
		RemainingPctValid: true,
		VoltageV:          11.1,
		VoltageValid:      true,
		CurrentA:          8.42,
		CurrentValid:      true,
	})
	if got != "BAT 73% 11.1V 8.4A" {
		t.Fatalf("batteryText() = %q, want %q", got, "BAT 73% 11.1V 8.4A")
	}

	got = batteryText(hud.Battery{})
	if got != "BAT -- --.-V --.-A" {
		t.Fatalf("batteryText() = %q, want %q", got, "BAT -- --.-V --.-A")
	}
}

func TestRadioText(t *testing.T) {
	if got := radioText(hud.Radio{}); got != "RC --%" {
		t.Fatalf("radioText() = %q, want %q", got, "RC --%")
	}

	got := radioText(hud.Radio{RCRSSI: 82, RCRSSIValid: true})
	if got != "RC 82%" {
		t.Fatalf("radioText() = %q, want %q", got, "RC 82%")
	}
}

func TestFlightModeText(t *testing.T) {
	if got := flightModeText(hud.Flight{}); got != "MODE --" {
		t.Fatalf("flightModeText() = %q, want %q", got, "MODE --")
	}

	got := flightModeText(hud.Flight{Mode: "ACRO", ModeValid: true})
	if got != "MODE ACRO" {
		t.Fatalf("flightModeText() = %q, want %q", got, "MODE ACRO")
	}
}

func TestWFBText(t *testing.T) {
	base := hud.Radio{
		WFBRSSIDBm:          -58,
		WFBRSSIValid:        true,
		WFBLinkQualityPct:   96,
		WFBLinkQualityValid: true,
		WFBFECFixed:         12,
		WFBRxErrors:         3,
	}

	if got := wfbText(base); got != "WFB -58 96% F12 L3" {
		t.Fatalf("wfbText() = %q, want %q", got, "WFB -58 96% F12 L3")
	}

	base.WFBFlags = hud.WFBLinkJammed
	if got := wfbText(base); got != "WFB -58 96% JAMMED" {
		t.Fatalf("wfbText() = %q, want %q", got, "WFB -58 96% JAMMED")
	}

	base.WFBFlags = hud.WFBLinkLost
	if got := wfbText(base); got != "WFB LINK LOST" {
		t.Fatalf("wfbText() = %q, want %q", got, "WFB LINK LOST")
	}
}

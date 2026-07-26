package hud

import (
	"testing"
	"time"
)

func TestSimulatorState(t *testing.T) {
	start := time.Date(2026, 5, 7, 12, 0, 0, 0, time.UTC)
	sim := NewSimulator(start)

	state := sim.State(start.Add(2 * time.Second))

	if state.UpdatedAt != start.Add(2*time.Second) {
		t.Fatalf("UpdatedAt = %v, want %v", state.UpdatedAt, start.Add(2*time.Second))
	}
	if state.GPS.FixType != GPSFix3D {
		t.Fatalf("GPS fix = %v, want %v", state.GPS.FixType, GPSFix3D)
	}
	if !state.Health.Has(HealthArmed) {
		t.Fatal("simulated health should include HealthArmed")
	}
	if state.Heading.Deg < 0 || state.Heading.Deg >= 360 {
		t.Fatalf("heading = %v, want [0, 360)", state.Heading.Deg)
	}
}

func TestGPSFixTypeString(t *testing.T) {
	tests := []struct {
		fix  GPSFixType
		want string
	}{
		{GPSFixNone, "NO FIX"},
		{GPSFix2D, "2D"},
		{GPSFix3D, "3D"},
		{GPSFixType(99), "NO FIX"},
	}

	for _, test := range tests {
		if got := test.fix.String(); got != test.want {
			t.Fatalf("String() = %q, want %q", got, test.want)
		}
	}
}

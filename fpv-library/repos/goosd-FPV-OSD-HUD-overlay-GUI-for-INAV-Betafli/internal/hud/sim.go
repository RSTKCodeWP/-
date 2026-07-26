package hud

import (
	"math"
	"time"
)

type Simulator struct {
	start time.Time
}

func NewSimulator(now time.Time) *Simulator {
	return &Simulator{start: now}
}

func (s *Simulator) State(now time.Time) State {
	if s.start.IsZero() {
		s.start = now
	}

	t := now.Sub(s.start).Seconds()
	roll := 28 * math.Sin(t*0.7)
	pitch := 11 * math.Sin(t*0.43)
	heading := math.Mod(35+t*18, 360)
	altitude := 120 + 18*math.Sin(t*0.25)
	speed := 24 + 4*math.Sin(t*0.9)
	volt := 16.8 - t/10
	remain := int8((volt - 12) / (16.8 - 12) * 100)

	return State{
		Attitude: Attitude{
			RollDeg:  roll,
			PitchDeg: pitch,
			YawDeg:   heading,
		},
		Heading:   Heading{Deg: heading},
		AltitudeM: altitude,
		SpeedMS:   speed,
		GPS: GPS{
			FixType:    GPSFix3D,
			Satellites: 12,
			HDOP:       0.9,
		},
		Battery: Battery{
			RemainingPct:      remain,
			RemainingPctValid: true,
			VoltageV:          volt,
			VoltageValid:      true,
			CurrentA:          8.4,
			CurrentValid:      true,
		},
		Radio: Radio{
			RCRSSI:              82,
			RCRSSIValid:         true,
			WFBRSSIDBm:          -58,
			WFBRSSIValid:        true,
			WFBLinkQualityPct:   96,
			WFBLinkQualityValid: true,
		},
		Flight: Flight{
			Mode:      "ACRO",
			ModeValid: true,
		},
		Health:    HealthArmed,
		UpdatedAt: now,
	}
}

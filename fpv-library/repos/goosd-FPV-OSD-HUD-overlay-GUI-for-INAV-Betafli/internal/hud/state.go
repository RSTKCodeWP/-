package hud

import "time"

// State is the renderer-facing HUD snapshot. Telemetry listeners should
// convert transport-specific fields into this DTO before drawing.
type State struct {
	Attitude  Attitude
	Heading   Heading
	AltitudeM float64
	SpeedMS   float64
	GPS       GPS
	Battery   Battery
	Radio     Radio
	Flight    Flight
	Health    Health
	UpdatedAt time.Time
}

type Attitude struct {
	RollDeg  float64
	PitchDeg float64
	YawDeg   float64
}

type Heading struct {
	Deg float64
}

type GPS struct {
	FixType    GPSFixType
	Satellites uint8
	HDOP       float64
}

type Battery struct {
	RemainingPct      int8
	RemainingPctValid bool
	VoltageV          float64
	VoltageValid      bool
	CurrentA          float64
	CurrentValid      bool
}

type Radio struct {
	RCRSSI              uint8
	RCRSSIValid         bool
	WFBRSSIDBm          int8
	WFBRSSIValid        bool
	WFBLinkQualityPct   uint8
	WFBLinkQualityValid bool
	WFBRxErrors         uint16
	WFBFECFixed         uint16
	WFBFlags            WFBFlags
}

type Flight struct {
	Mode      string
	ModeValid bool
}

type WFBFlags uint8

const (
	WFBLinkLost WFBFlags = 1 << iota
	WFBLinkJammed
)

func (f WFBFlags) Has(flag WFBFlags) bool {
	return f&flag != 0
}

type GPSFixType uint8

const (
	GPSFixNone GPSFixType = iota
	GPSFix2D
	GPSFix3D
)

func (f GPSFixType) String() string {
	switch f {
	case GPSFix2D:
		return "2D"
	case GPSFix3D:
		return "3D"
	default:
		return "NO FIX"
	}
}

type Health uint32

const (
	HealthArmed Health = 1 << iota
	HealthFailsafe
	HealthLowBattery
	HealthTelemetryLost
)

func (h Health) Has(flag Health) bool {
	return h&flag != 0
}

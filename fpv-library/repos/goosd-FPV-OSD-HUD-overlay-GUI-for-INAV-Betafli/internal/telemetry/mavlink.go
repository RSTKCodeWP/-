package telemetry

import (
	"fmt"
	"math"
	"sync"
	"time"

	"github.com/alexbezu/goosd/internal/hud"
	"github.com/bluenviron/gomavlib/v3"
	"github.com/bluenviron/gomavlib/v3/pkg/dialects/common"
	"github.com/bluenviron/gomavlib/v3/pkg/message"
)

type MAVLinkSource struct {
	node *gomavlib.Node
	now  func() time.Time

	mu    sync.RWMutex
	state hud.State
}

func NewMAVLinkSource(listenAddr string) (*MAVLinkSource, error) {
	source := &MAVLinkSource{
		now: time.Now,
		state: hud.State{
			Health: hud.HealthTelemetryLost,
		},
	}

	node := &gomavlib.Node{
		Endpoints: []gomavlib.EndpointConf{
			gomavlib.EndpointUDPServer{Address: listenAddr},
		},
		Dialect:          common.Dialect,
		OutVersion:       gomavlib.V2,
		OutSystemID:      255,
		HeartbeatDisable: true,
	}
	if err := node.Initialize(); err != nil {
		return nil, err
	}

	source.node = node
	go source.run()

	return source, nil
}

func (s *MAVLinkSource) Close() {
	if s.node != nil {
		s.node.Close()
	}
}

func (s *MAVLinkSource) State(now time.Time) hud.State {
	s.mu.RLock()
	state := s.state
	s.mu.RUnlock()

	if state.UpdatedAt.IsZero() || now.Sub(state.UpdatedAt) > 3*time.Second {
		state.Health |= hud.HealthTelemetryLost
	}
	return state
}

func (s *MAVLinkSource) run() {
	for evt := range s.node.Events() {
		frame, ok := evt.(*gomavlib.EventFrame)
		if !ok {
			continue
		}
		s.apply(frame.Message(), s.now())
	}
}

func (s *MAVLinkSource) apply(message message.Message, now time.Time) {
	s.mu.Lock()
	defer s.mu.Unlock()

	state := s.state
	state.UpdatedAt = now
	state.Health &^= hud.HealthTelemetryLost

	switch msg := message.(type) {
	case *common.MessageAttitude: // 30
		state.Attitude.RollDeg = radiansToDegrees(msg.Roll)
		state.Attitude.PitchDeg = radiansToDegrees(msg.Pitch)
		state.Attitude.YawDeg = normalize360(radiansToDegrees(msg.Yaw))
	case *common.MessageVfrHud: // 74
		state.Heading.Deg = normalize360(float64(msg.Heading))
		state.AltitudeM = float64(msg.Alt)
		state.SpeedMS = float64(msg.Groundspeed)
	case *common.MessageGlobalPositionInt: // 33
		if msg.Hdg != math.MaxUint16 {
			state.Heading.Deg = normalize360(float64(msg.Hdg) / 100)
		}
		state.AltitudeM = float64(msg.Alt) / 1000
		state.SpeedMS = math.Hypot(float64(msg.Vx), float64(msg.Vy)) / 100
	case *common.MessageGpsRawInt: // 24
		state.GPS.FixType = gpsFixType(msg.FixType)
		state.GPS.Satellites = msg.SatellitesVisible
		if msg.Eph != math.MaxUint16 {
			state.GPS.HDOP = float64(msg.Eph) / 100
		}
		if state.SpeedMS == 0 && msg.Vel != math.MaxUint16 {
			state.SpeedMS = float64(msg.Vel) / 100
		}
	case *common.MessageHeartbeat:
		state.Health = heartbeatHealth(state.Health, msg)
		state.Flight.Mode = flightMode(msg)
		state.Flight.ModeValid = true
	case *common.MessageSysStatus:
		if msg.BatteryRemaining >= 0 && msg.BatteryRemaining <= 20 {
			state.Health |= hud.HealthLowBattery
		} else {
			state.Health &^= hud.HealthLowBattery
		}
	case *common.MessageBatteryStatus: // 147
		applyBatteryStatus(&state, msg)
	case *common.MessageRcChannelsRaw: // 35
		applyRCRSSI(&state, msg.Rssi)
	case *common.MessageRcChannels: // 65
		applyRCRSSI(&state, msg.Rssi)
	case *common.MessageRadioStatus: // 109
		applyRadioStatus(&state, msg)
	case *common.MessageRawImu: // 27
		// skipped
	default:
		fmt.Printf("Not implemented: %T\n", msg)
	}

	if state.Heading.Deg == 0 && state.Attitude.YawDeg != 0 {
		state.Heading.Deg = state.Attitude.YawDeg
	}

	s.state = state
}

func applyRCRSSI(state *hud.State, rssi uint8) {
	if rssi == math.MaxUint8 {
		return
	}
	state.Radio.RCRSSI = radioPercent(rssi)
	state.Radio.RCRSSIValid = true
}

func applyRadioStatus(state *hud.State, msg *common.MessageRadioStatus) {
	if msg.Rssi != math.MaxUint8 {
		applyRCRSSI(state, msg.Rssi)
		state.Radio.WFBRSSIDBm = int8(msg.Rssi)
		state.Radio.WFBRSSIValid = true
	}
	if msg.Remrssi != math.MaxUint8 {
		state.Radio.WFBLinkQualityPct = radioPercent(msg.Remrssi)
		state.Radio.WFBLinkQualityValid = true
	}
	state.Radio.WFBRxErrors = msg.Rxerrors
	state.Radio.WFBFECFixed = msg.Fixed
	state.Radio.WFBFlags = hud.WFBFlags(msg.Remnoise)
}

func radioPercent(value uint8) uint8 {
	if value > 100 {
		return 100
	}
	return value
}

func applyBatteryStatus(state *hud.State, msg *common.MessageBatteryStatus) {
	if msg.BatteryRemaining >= 0 {
		state.Battery.RemainingPct = msg.BatteryRemaining
		state.Battery.RemainingPctValid = true
		if msg.BatteryRemaining <= 20 {
			state.Health |= hud.HealthLowBattery
		} else {
			state.Health &^= hud.HealthLowBattery
		}
	}

	if voltageMV, ok := batteryVoltageMV(msg); ok {
		state.Battery.VoltageV = float64(voltageMV) / 1000
		state.Battery.VoltageValid = true
	}

	if msg.CurrentBattery >= 0 {
		state.Battery.CurrentA = float64(msg.CurrentBattery) / 100
		state.Battery.CurrentValid = true
	}
}

func batteryVoltageMV(msg *common.MessageBatteryStatus) (uint32, bool) {
	var total uint32
	for _, voltage := range msg.Voltages {
		if voltage == 0 || voltage == math.MaxUint16 {
			continue
		}
		total += uint32(voltage)
	}
	for _, voltage := range msg.VoltagesExt {
		if voltage == 0 || voltage == math.MaxUint16 {
			continue
		}
		total += uint32(voltage)
	}
	return total, total > 0
}

func heartbeatHealth(current hud.Health, msg *common.MessageHeartbeat) hud.Health {
	current &^= hud.HealthArmed | hud.HealthFailsafe

	if msg.BaseMode&common.MAV_MODE_FLAG_SAFETY_ARMED != 0 {
		current |= hud.HealthArmed
	}
	if msg.SystemStatus == common.MAV_STATE_CRITICAL ||
		msg.SystemStatus == common.MAV_STATE_EMERGENCY ||
		msg.SystemStatus == common.MAV_STATE_FLIGHT_TERMINATION {
		current |= hud.HealthFailsafe
	}

	return current
}

func flightMode(msg *common.MessageHeartbeat) string {
	if msg.BaseMode&common.MAV_MODE_FLAG_AUTO_ENABLED != 0 {
		return "AUTO"
	}
	if msg.BaseMode&common.MAV_MODE_FLAG_GUIDED_ENABLED != 0 {
		return "GUIDED"
	}
	if msg.BaseMode&common.MAV_MODE_FLAG_STABILIZE_ENABLED != 0 {
		return "STAB"
	}
	if msg.Autopilot == common.MAV_AUTOPILOT_GENERIC && msg.CustomMode == 1 {
		return "ACRO"
	}
	if msg.BaseMode&common.MAV_MODE_FLAG_MANUAL_INPUT_ENABLED != 0 {
		return "MANUAL"
	}
	if msg.Autopilot == common.MAV_AUTOPILOT_GENERIC && msg.CustomMode == 0 {
		return "STAB"
	}

	switch {
	case msg.BaseMode&common.MAV_MODE_FLAG_HIL_ENABLED != 0:
		return "HIL"
	case msg.BaseMode&common.MAV_MODE_FLAG_TEST_ENABLED != 0:
		return "TEST"
	case msg.BaseMode&common.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED != 0:
		return fmt.Sprintf("CUSTOM %d", msg.CustomMode)
	default:
		return "UNKNOWN"
	}
}

func gpsFixType(fix common.GPS_FIX_TYPE) hud.GPSFixType {
	switch fix {
	case common.GPS_FIX_TYPE_2D_FIX:
		return hud.GPSFix2D
	case common.GPS_FIX_TYPE_3D_FIX,
		common.GPS_FIX_TYPE_DGPS,
		common.GPS_FIX_TYPE_RTK_FLOAT,
		common.GPS_FIX_TYPE_RTK_FIXED,
		common.GPS_FIX_TYPE_STATIC,
		common.GPS_FIX_TYPE_PPP:
		return hud.GPSFix3D
	default:
		return hud.GPSFixNone
	}
}

func radiansToDegrees(radians float32) float64 {
	return float64(radians) * 180 / math.Pi
}

func normalize360(deg float64) float64 {
	deg = math.Mod(deg, 360)
	if deg < 0 {
		deg += 360
	}
	return deg
}

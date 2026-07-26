namespace ApexControl.Core.Models;

public class DroneTelemetry
{
    public bool IsConnected { get; set; }
    public bool IsLinkHealthy { get; set; }
    public string ConnectionStateText { get; set; } = "Disconnected";

    public bool IsArmed { get; set; }
    public string FlightMode { get; set; } = "-";

    public double Latitude { get; set; }
    public double Longitude { get; set; }
    public double RelativeAltitude { get; set; }

    public double AbsoluteAltitude { get; set; }
    public double GroundSpeed { get; set; }
    public double AirSpeed { get; set; }
    public double ClimbRate { get; set; }
    public int Heading { get; set; }
    public int ThrottlePercent { get; set; }

    public double BatteryVoltage { get; set; }
    public int BatteryRemaining { get; set; } = -1;

    public DateTime? LastTelemetryUtc { get; set; }
    public DateTime? LastHeartbeatUtc { get; set; }
    public DateTime? LastGpsUtc { get; set; }
    public DateTime? LastPositionUtc { get; set; }
    public DateTime? LastHudUtc { get; set; }

    public long TotalBytesReceived { get; set; }
    public long TotalDatagramsReceived { get; set; }

    public int HeartbeatCount { get; set; }
    public int PositionCount { get; set; }
    public int SystemStatusCount { get; set; }
    public int GpsRawCount { get; set; }
    public int VfrHudCount { get; set; }
    public int StatusTextCount { get; set; }
    public int CommandAckCount { get; set; }

    public byte GpsFixType { get; set; }
    public string GpsFixText { get; set; } = "No GPS";
    public int SatellitesVisible { get; set; } = -1;
    public double Hdop { get; set; }
    public double Vdop { get; set; }
    public bool HasGpsFix { get; set; }
    public bool IsGpsHealthy { get; set; }
    public string GpsHealthText { get; set; } = "No GPS";

    public DateTime? LastCommandSentUtc { get; set; }
    public DateTime? LastCommandAckUtc { get; set; }

    public ushort? LastCommandId { get; set; }
    public string LastCommandName { get; set; } = "-";

    public byte? LastCommandResult { get; set; }
    public string LastCommandResultText { get; set; } = "-";
    public string LastCommandStatus { get; set; } = "IDLE";

    public string LastStatusText { get; set; } = "-";
    public byte LastStatusSeverity { get; set; }
    public string LastPreArmMessage { get; set; } = "-";

    public bool IsHeartbeatFresh { get; set; }
    public bool IsPositionFresh { get; set; }
    public bool IsGpsFresh { get; set; }
    public bool IsHudFresh { get; set; }
}

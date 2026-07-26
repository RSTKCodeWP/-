using System;
using System.Threading.Tasks;
using ApexControl.Core.Models;
using ApexControl.Core.Services;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Microsoft.Maui.ApplicationModel;
using Microsoft.Maui.Devices;

namespace ApexControl.App.ViewModels;

public partial class MainViewModel : ObservableObject
{
    private readonly MavlinkTelemetryService telemetryService;

    [ObservableProperty]
    private DroneTelemetryViewModel drone = new();

    [ObservableProperty]
    private string connectionStatus = "Disconnected";

    [ObservableProperty]
    private double takeoffAltitude = 2;

    [ObservableProperty]
    private bool isConnecting;

    [ObservableProperty]
    private bool isDisconnecting;

    public MainViewModel()
    {
        telemetryService = new MavlinkTelemetryService();
        telemetryService.TelemetryUpdated += OnTelemetryUpdated;
    }

    public bool IsDesktop =>
        DeviceInfo.Idiom == DeviceIdiom.Desktop ||
        DeviceInfo.Idiom == DeviceIdiom.Tablet;

    public bool IsMobile =>
        DeviceInfo.Idiom == DeviceIdiom.Phone;

    public bool CanConnect =>
        !IsConnecting &&
        !IsDisconnecting &&
        !Drone.IsConnected;

    public bool CanDisconnect =>
        !IsConnecting &&
        !IsDisconnecting &&
        Drone.IsConnected;

    public bool CanSendCommands =>
        !IsConnecting &&
        !IsDisconnecting &&
        Drone.IsConnected &&
        Drone.IsLinkHealthy;

    partial void OnIsConnectingChanged(bool value)
    {
        RaiseCommandStateChanged();
    }

    partial void OnIsDisconnectingChanged(bool value)
    {
        RaiseCommandStateChanged();
    }

    private void OnTelemetryUpdated(object? sender, DroneTelemetry telemetry)
    {
        MainThread.BeginInvokeOnMainThread(() =>
        {
            Drone.IsConnected = telemetry.IsConnected;
            Drone.IsLinkHealthy = telemetry.IsLinkHealthy;
            Drone.ConnectionStateText = telemetry.ConnectionStateText;

            Drone.IsArmed = telemetry.IsArmed;
            Drone.FlightMode = telemetry.FlightMode;

            Drone.Latitude = telemetry.Latitude;
            Drone.Longitude = telemetry.Longitude;
            Drone.RelativeAltitude = telemetry.RelativeAltitude;
            Drone.AbsoluteAltitude = telemetry.AbsoluteAltitude;

            Drone.GroundSpeed = telemetry.GroundSpeed;
            Drone.AirSpeed = telemetry.AirSpeed;
            Drone.ClimbRate = telemetry.ClimbRate;
            Drone.Heading = telemetry.Heading;
            Drone.ThrottlePercent = telemetry.ThrottlePercent;

            Drone.BatteryVoltage = telemetry.BatteryVoltage;
            Drone.BatteryRemaining = telemetry.BatteryRemaining;

            Drone.LastTelemetryUtc = telemetry.LastTelemetryUtc;
            Drone.LastHeartbeatUtc = telemetry.LastHeartbeatUtc;
            Drone.LastGpsUtc = telemetry.LastGpsUtc;
            Drone.LastPositionUtc = telemetry.LastPositionUtc;
            Drone.LastHudUtc = telemetry.LastHudUtc;

            Drone.LastTelemetryText = FormatTime(telemetry.LastTelemetryUtc);
            Drone.LastHeartbeatText = FormatTime(telemetry.LastHeartbeatUtc);
            Drone.LastGpsText = FormatTime(telemetry.LastGpsUtc);
            Drone.LastPositionText = FormatTime(telemetry.LastPositionUtc);
            Drone.LastHudText = FormatTime(telemetry.LastHudUtc);

            Drone.TotalBytesReceived = telemetry.TotalBytesReceived;
            Drone.TotalDatagramsReceived = telemetry.TotalDatagramsReceived;

            Drone.HeartbeatCount = telemetry.HeartbeatCount;
            Drone.PositionCount = telemetry.PositionCount;
            Drone.SystemStatusCount = telemetry.SystemStatusCount;
            Drone.GpsRawCount = telemetry.GpsRawCount;
            Drone.VfrHudCount = telemetry.VfrHudCount;
            Drone.StatusTextCount = telemetry.StatusTextCount;
            Drone.CommandAckCount = telemetry.CommandAckCount;

            Drone.GpsFixType = telemetry.GpsFixType;
            Drone.GpsFixText = telemetry.GpsFixText;
            Drone.SatellitesVisible = telemetry.SatellitesVisible;
            Drone.Hdop = telemetry.Hdop;
            Drone.Vdop = telemetry.Vdop;
            Drone.HasGpsFix = telemetry.HasGpsFix;
            Drone.IsGpsHealthy = telemetry.IsGpsHealthy;
            Drone.GpsHealthText = telemetry.GpsHealthText;

            Drone.LastCommandSentUtc = telemetry.LastCommandSentUtc;
            Drone.LastCommandAckUtc = telemetry.LastCommandAckUtc;
            Drone.LastCommandSentText = FormatTime(telemetry.LastCommandSentUtc);
            Drone.LastCommandAckText = FormatTime(telemetry.LastCommandAckUtc);

            Drone.LastCommandId = telemetry.LastCommandId;
            Drone.LastCommandName = telemetry.LastCommandName;
            Drone.LastCommandResult = telemetry.LastCommandResult;
            Drone.LastCommandResultText = telemetry.LastCommandResultText;
            Drone.LastCommandStatus = telemetry.LastCommandStatus;

            Drone.LastStatusText = telemetry.LastStatusText;
            Drone.LastStatusSeverity = telemetry.LastStatusSeverity;
            Drone.LastPreArmMessage = telemetry.LastPreArmMessage;

            Drone.IsHeartbeatFresh = telemetry.IsHeartbeatFresh;
            Drone.IsPositionFresh = telemetry.IsPositionFresh;
            Drone.IsGpsFresh = telemetry.IsGpsFresh;
            Drone.IsHudFresh = telemetry.IsHudFresh;

            ConnectionStatus = string.IsNullOrWhiteSpace(telemetry.ConnectionStateText)
                ? "Disconnected"
                : telemetry.ConnectionStateText;

            RaiseCommandStateChanged();
        });
    }

    [RelayCommand]
    public async Task ConnectAsync()
    {
        if (!CanConnect)
            return;

        IsConnecting = true;
        ConnectionStatus = "Starting telemetry listener...";
        Drone.IsConnected = false;
        Drone.IsLinkHealthy = false;
        Drone.ConnectionStateText = "Connecting...";
        RaiseCommandStateChanged();

        try
        {
            await telemetryService.StartAsync();
            ConnectionStatus = "Listening on UDP 14550";
        }
        catch (Exception ex)
        {
            Drone.IsConnected = false;
            Drone.IsLinkHealthy = false;
            Drone.ConnectionStateText = "Disconnected";
            ConnectionStatus = $"Connection failed: {ex.Message}";
        }
        finally
        {
            IsConnecting = false;
            RaiseCommandStateChanged();
        }
    }

    [RelayCommand]
    public async Task DisconnectAsync()
    {
        if (!CanDisconnect && !IsConnecting)
            return;

        IsDisconnecting = true;
        ConnectionStatus = "Disconnecting...";
        RaiseCommandStateChanged();

        try
        {
            await telemetryService.StopAsync();
        }
        finally
        {
            Drone.IsConnected = false;
            Drone.IsLinkHealthy = false;
            Drone.ConnectionStateText = "Disconnected";
            ConnectionStatus = "Disconnected";
            IsDisconnecting = false;
            RaiseCommandStateChanged();
        }
    }

    [RelayCommand]
    public async Task ArmAsync()
    {
        if (!CanSendCommands)
        {
            ConnectionStatus = "Cannot ARM: no healthy MAVLink heartbeat";
            return;
        }

        await telemetryService.ArmAsync();
        ConnectionStatus = "ARM command sent";
    }

    [RelayCommand]
    public async Task DisarmAsync()
    {
        if (!CanSendCommands)
        {
            ConnectionStatus = "Cannot DISARM: no healthy MAVLink heartbeat";
            return;
        }

        await telemetryService.DisarmAsync();
        ConnectionStatus = "DISARM command sent";
    }

    [RelayCommand]
    public async Task SetGuidedModeAsync()
    {
        if (!CanSendCommands)
        {
            ConnectionStatus = "Cannot set GUIDED: no healthy MAVLink heartbeat";
            return;
        }

        await telemetryService.SetGuidedModeAsync();
        ConnectionStatus = "GUIDED mode command sent";
    }

    [RelayCommand]
    public async Task SetLoiterModeAsync()
    {
        if (!CanSendCommands)
        {
            ConnectionStatus = "Cannot set LOITER: no healthy MAVLink heartbeat";
            return;
        }

        await telemetryService.SetLoiterModeAsync();
        ConnectionStatus = "LOITER mode command sent";
    }

    [RelayCommand]
    public async Task SetStabilizeModeAsync()
    {
        if (!CanSendCommands)
        {
            ConnectionStatus = "Cannot set STABILIZE: no healthy MAVLink heartbeat";
            return;
        }

        await telemetryService.SetStabilizeModeAsync();
        ConnectionStatus = "STABILIZE mode command sent";
    }

    [RelayCommand]
    public async Task TakeoffAsync()
    {
        if (!CanSendCommands)
        {
            ConnectionStatus = "Cannot TAKEOFF: no healthy MAVLink heartbeat";
            return;
        }

        if (TakeoffAltitude <= 0)
            TakeoffAltitude = 2;

        await telemetryService.TakeoffAsync((float)TakeoffAltitude);
        ConnectionStatus = $"TAKEOFF command sent: {TakeoffAltitude:F1} m";
    }

    private void RaiseCommandStateChanged()
    {
        OnPropertyChanged(nameof(CanConnect));
        OnPropertyChanged(nameof(CanDisconnect));
        OnPropertyChanged(nameof(CanSendCommands));
    }

    private static string FormatTime(DateTime? utcTime)
    {
        return utcTime.HasValue
            ? utcTime.Value.ToLocalTime().ToString("HH:mm:ss")
            : "-";
    }

    public partial class DroneTelemetryViewModel : ObservableObject
    {
        [ObservableProperty] private bool isConnected;
        [ObservableProperty] private bool isLinkHealthy;
        [ObservableProperty] private string connectionStateText = "Disconnected";

        [ObservableProperty] private bool isArmed;
        [ObservableProperty] private string flightMode = "-";

        [ObservableProperty] private double latitude;
        [ObservableProperty] private double longitude;
        [ObservableProperty] private double relativeAltitude;
        [ObservableProperty] private double absoluteAltitude;

        [ObservableProperty] private double groundSpeed;
        [ObservableProperty] private double airSpeed;
        [ObservableProperty] private double climbRate;
        [ObservableProperty] private int heading;
        [ObservableProperty] private int throttlePercent;

        [ObservableProperty] private double batteryVoltage;
        [ObservableProperty] private int batteryRemaining = -1;

        [ObservableProperty] private DateTime? lastTelemetryUtc;
        [ObservableProperty] private DateTime? lastHeartbeatUtc;
        [ObservableProperty] private DateTime? lastGpsUtc;
        [ObservableProperty] private DateTime? lastPositionUtc;
        [ObservableProperty] private DateTime? lastHudUtc;

        [ObservableProperty] private string lastTelemetryText = "-";
        [ObservableProperty] private string lastHeartbeatText = "-";
        [ObservableProperty] private string lastGpsText = "-";
        [ObservableProperty] private string lastPositionText = "-";
        [ObservableProperty] private string lastHudText = "-";

        [ObservableProperty] private long totalBytesReceived;
        [ObservableProperty] private long totalDatagramsReceived;

        [ObservableProperty] private long heartbeatCount;
        [ObservableProperty] private long positionCount;
        [ObservableProperty] private long systemStatusCount;
        [ObservableProperty] private long gpsRawCount;
        [ObservableProperty] private long vfrHudCount;
        [ObservableProperty] private long statusTextCount;
        [ObservableProperty] private long commandAckCount;

        [ObservableProperty] private byte gpsFixType;
        [ObservableProperty] private string gpsFixText = "No GPS";
        [ObservableProperty] private int satellitesVisible = -1;
        [ObservableProperty] private double hdop;
        [ObservableProperty] private double vdop;
        [ObservableProperty] private bool hasGpsFix;
        [ObservableProperty] private bool isGpsHealthy;
        [ObservableProperty] private string gpsHealthText = "No GPS";

        [ObservableProperty] private DateTime? lastCommandSentUtc;
        [ObservableProperty] private DateTime? lastCommandAckUtc;
        [ObservableProperty] private string lastCommandSentText = "-";
        [ObservableProperty] private string lastCommandAckText = "-";

        [ObservableProperty] private ushort? lastCommandId;
        [ObservableProperty] private string lastCommandName = "-";
        [ObservableProperty] private byte? lastCommandResult;
        [ObservableProperty] private string lastCommandResultText = "-";
        [ObservableProperty] private string lastCommandStatus = "IDLE";

        [ObservableProperty] private string lastStatusText = "-";
        [ObservableProperty] private byte lastStatusSeverity;
        [ObservableProperty] private string lastPreArmMessage = "-";

        [ObservableProperty] private bool isHeartbeatFresh;
        [ObservableProperty] private bool isPositionFresh;
        [ObservableProperty] private bool isGpsFresh;
        [ObservableProperty] private bool isHudFresh;
    }
}

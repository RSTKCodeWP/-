using ApexControl.Core.Models;

using System;
using System.Buffers.Binary;
using System.Text;

namespace ApexControl.Core.Services;

public sealed class MavlinkTelemetryService : IAsyncDisposable
{
    private const byte MavlinkV1Magic = 0xFE;
    private const byte MavlinkV2Magic = 0xFD;

    private const int HeartbeatMessageId = 0;
    private const int SysStatusMessageId = 1;
    private const int GpsRawIntMessageId = 24;
    private const int GlobalPositionIntMessageId = 33;
    private const int VfrHudMessageId = 74;
    private const int CommandLongMessageId = 76;
    private const int CommandAckMessageId = 77;
    private const int StatusTextMessageId = 253;

    private const ushort MavCmdNavTakeoff = 22;
    private const ushort MavCmdDoSetMode = 176;
    private const ushort MavCmdComponentArmDisarm = 400;

    private const byte MavModeFlagCustomModeEnabled = 1;

    private const float ArduCopterModeStabilize = 0;
    private const float ArduCopterModeGuided = 4;
    private const float ArduCopterModeLoiter = 5;

    private readonly UdpDroneConnection connection;
    private readonly object telemetryLock = new();

    private byte sequence;
    private byte targetSystem = 1;
    private byte targetComponent = 1;

    private ushort? pendingCommandId;
    private string pendingCommandName = "-";
    private DateTime? pendingCommandSentUtc;

    private readonly TimeSpan heartbeatTimeout = TimeSpan.FromSeconds(3);
    private readonly TimeSpan commandAckTimeout = TimeSpan.FromSeconds(5);
    private readonly TimeSpan watchdogInterval = TimeSpan.FromMilliseconds(500);
    private readonly TimeSpan telemetryFreshnessTimeout = TimeSpan.FromSeconds(3);
    private readonly TimeSpan gpsFreshnessTimeout = TimeSpan.FromSeconds(5);
    private readonly TimeSpan hudFreshnessTimeout = TimeSpan.FromSeconds(3);

    private CancellationTokenSource? watchdogCts;
    private Task? watchdogTask;
    private bool lastWatchdogConnectedState;

    public event EventHandler<DroneTelemetry>? TelemetryUpdated;

    public DroneTelemetry CurrentTelemetry { get; } = new();

    public MavlinkTelemetryService(int udpPort = 14550)
    {
        connection = new UdpDroneConnection(udpPort, "127.0.0.1", udpPort);
        connection.BytesReceived += OnBytesReceived;
    }

    public Task StartAsync(CancellationToken cancellationToken = default)
    {
        lock (telemetryLock)
        {
            CurrentTelemetry.IsConnected = false;
            CurrentTelemetry.IsLinkHealthy = false;
            CurrentTelemetry.ConnectionStateText = "Listening";
            CurrentTelemetry.LastTelemetryUtc = null;
            CurrentTelemetry.LastHeartbeatUtc = null;

            pendingCommandId = null;
            pendingCommandName = "-";
            pendingCommandSentUtc = null;
            lastWatchdogConnectedState = false;
        }

        TelemetryUpdated?.Invoke(this, CurrentTelemetry);

        watchdogCts?.Cancel();
        watchdogCts?.Dispose();
        watchdogCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        watchdogTask = RunWatchdogAsync(watchdogCts.Token);

        return connection.StartAsync(cancellationToken);
    }

    public async Task StopAsync()
    {
        if (watchdogCts is not null)
        {
            await watchdogCts.CancelAsync();
        }

        if (watchdogTask is not null)
        {
            try
            {
                await watchdogTask;
            }
            catch (OperationCanceledException)
            {
            }
        }

        lock (telemetryLock)
        {
            CurrentTelemetry.IsConnected = false;
            CurrentTelemetry.IsLinkHealthy = false;
            CurrentTelemetry.ConnectionStateText = "Disconnected";
            CurrentTelemetry.LastHeartbeatUtc = null;

            pendingCommandId = null;
            pendingCommandName = "-";
            pendingCommandSentUtc = null;
        }

        TelemetryUpdated?.Invoke(this, CurrentTelemetry);
        await connection.StopAsync();
    }

    public async Task ArmAsync(CancellationToken cancellationToken = default)
    {
        await SendCommandLongAsync(
            MavCmdComponentArmDisarm,
            "ARM",
            1,
            0,
            0,
            0,
            0,
            0,
            0,
            cancellationToken);
    }

    public async Task DisarmAsync(CancellationToken cancellationToken = default)
    {
        await SendCommandLongAsync(
            MavCmdComponentArmDisarm,
            "DISARM",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            cancellationToken);
    }

    public async Task SetGuidedModeAsync(CancellationToken cancellationToken = default)
    {
        await SendCommandLongAsync(
            MavCmdDoSetMode,
            "SET GUIDED MODE",
            MavModeFlagCustomModeEnabled,
            ArduCopterModeGuided,
            0,
            0,
            0,
            0,
            0,
            cancellationToken);
    }

    public async Task SetLoiterModeAsync(CancellationToken cancellationToken = default)
    {
        await SendCommandLongAsync(
            MavCmdDoSetMode,
            "SET LOITER MODE",
            MavModeFlagCustomModeEnabled,
            ArduCopterModeLoiter,
            0,
            0,
            0,
            0,
            0,
            cancellationToken);
    }

    public async Task SetStabilizeModeAsync(CancellationToken cancellationToken = default)
    {
        await SendCommandLongAsync(
            MavCmdDoSetMode,
            "SET STABILIZE MODE",
            MavModeFlagCustomModeEnabled,
            ArduCopterModeStabilize,
            0,
            0,
            0,
            0,
            0,
            cancellationToken);
    }

    public async Task TakeoffAsync(float altitudeMeters, CancellationToken cancellationToken = default)
    {
        if (altitudeMeters <= 0)
        {
            altitudeMeters = 2;
        }

        await SendCommandLongAsync(
            MavCmdNavTakeoff,
            $"TAKEOFF {altitudeMeters:0.#} m",
            0,
            0,
            0,
            0,
            0,
            0,
            altitudeMeters,
            cancellationToken);
    }

    private async Task SendCommandLongAsync(
        ushort command,
        string commandName,
        float param1,
        float param2,
        float param3,
        float param4,
        float param5,
        float param6,
        float param7,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();

        lock (telemetryLock)
        {
            if (pendingCommandId.HasValue)
            {
                CurrentTelemetry.LastCommandId = command;
                CurrentTelemetry.LastCommandName = commandName;
                CurrentTelemetry.LastCommandResult = 255;
                CurrentTelemetry.LastCommandResultText = "BUSY";
                CurrentTelemetry.LastCommandStatus = "Another command is waiting for ACK";
                CurrentTelemetry.LastCommandAckUtc = null;
                CurrentTelemetry.LastCommandSentUtc = null;
                return;
            }

            pendingCommandId = command;
            pendingCommandName = commandName;
            pendingCommandSentUtc = DateTime.UtcNow;

            CurrentTelemetry.LastCommandId = command;
            CurrentTelemetry.LastCommandName = commandName;
            CurrentTelemetry.LastCommandResult = 255;
            CurrentTelemetry.LastCommandResultText = "WAITING_FOR_ACK";
            CurrentTelemetry.LastCommandStatus = $"{commandName}: waiting for ACK";
            CurrentTelemetry.LastCommandSentUtc = pendingCommandSentUtc;
            CurrentTelemetry.LastCommandAckUtc = null;
        }

        TelemetryUpdated?.Invoke(this, CurrentTelemetry);

        var packet = BuildCommandLongPacket(
            targetSystem,
            targetComponent,
            command,
            param1,
            param2,
            param3,
            param4,
            param5,
            param6,
            param7,
            cancellationToken);

        try
        {
            await connection.SendAsync(packet, cancellationToken);
        }
        catch (Exception ex)
        {
            lock (telemetryLock)
            {
                CurrentTelemetry.LastCommandId = command;
                CurrentTelemetry.LastCommandName = commandName;
                CurrentTelemetry.LastCommandResult = 254;
                CurrentTelemetry.LastCommandResultText = "SEND_FAILED";
                CurrentTelemetry.LastCommandStatus = $"{commandName}: send failed ({ex.Message})";
                CurrentTelemetry.LastCommandAckUtc = null;

                pendingCommandId = null;
                pendingCommandName = "-";
                pendingCommandSentUtc = null;
            }

            TelemetryUpdated?.Invoke(this, CurrentTelemetry);
            throw;
        }
    }

    private byte[] BuildCommandLongPacket(
        byte targetSystem,
        byte targetComponent,
        ushort command,
        float param1,
        float param2,
        float param3,
        float param4,
        float param5,
        float param6,
        float param7,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();

        Span<byte> payload = stackalloc byte[33];

        BinaryPrimitives.WriteSingleLittleEndian(payload.Slice(0, 4), param1);
        BinaryPrimitives.WriteSingleLittleEndian(payload.Slice(4, 4), param2);
        BinaryPrimitives.WriteSingleLittleEndian(payload.Slice(8, 4), param3);
        BinaryPrimitives.WriteSingleLittleEndian(payload.Slice(12, 4), param4);
        BinaryPrimitives.WriteSingleLittleEndian(payload.Slice(16, 4), param5);
        BinaryPrimitives.WriteSingleLittleEndian(payload.Slice(20, 4), param6);
        BinaryPrimitives.WriteSingleLittleEndian(payload.Slice(24, 4), param7);
        BinaryPrimitives.WriteUInt16LittleEndian(payload.Slice(28, 2), command);

        payload[30] = targetSystem;
        payload[31] = targetComponent;
        payload[32] = 0;

        var packet = new byte[10 + payload.Length + 2];

        packet[0] = MavlinkV2Magic;
        packet[1] = (byte)payload.Length;
        packet[2] = 0;
        packet[3] = 0;
        packet[4] = sequence++;
        packet[5] = 255;
        packet[6] = 190;
        packet[7] = (byte)(CommandLongMessageId & 0xFF);
        packet[8] = (byte)((CommandLongMessageId >> 8) & 0xFF);
        packet[9] = (byte)((CommandLongMessageId >> 16) & 0xFF);

        payload.CopyTo(packet.AsSpan(10));

        var crc = ComputeMavlinkV2Crc(packet.AsSpan(1, 9 + payload.Length), 152);

        packet[10 + payload.Length] = (byte)(crc & 0xFF);
        packet[11 + payload.Length] = (byte)((crc >> 8) & 0xFF);

        return packet;
    }

    private async Task RunWatchdogAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            bool shouldNotify = false;

            lock (telemetryLock)
            {
                var now = DateTime.UtcNow;

                bool healthy =
                    CurrentTelemetry.LastHeartbeatUtc.HasValue &&
                    (now - CurrentTelemetry.LastHeartbeatUtc.Value) <= heartbeatTimeout;

                CurrentTelemetry.IsLinkHealthy = healthy;
                CurrentTelemetry.IsConnected = healthy;

                CurrentTelemetry.IsHeartbeatFresh =
                    CurrentTelemetry.LastHeartbeatUtc.HasValue &&
                    (now - CurrentTelemetry.LastHeartbeatUtc.Value) <= telemetryFreshnessTimeout;

                CurrentTelemetry.IsPositionFresh =
                    CurrentTelemetry.LastPositionUtc.HasValue &&
                    (now - CurrentTelemetry.LastPositionUtc.Value) <= telemetryFreshnessTimeout;

                CurrentTelemetry.IsGpsFresh =
                    CurrentTelemetry.LastGpsUtc.HasValue &&
                    (now - CurrentTelemetry.LastGpsUtc.Value) <= gpsFreshnessTimeout;

                CurrentTelemetry.IsHudFresh =
                    CurrentTelemetry.LastHudUtc.HasValue &&
                    (now - CurrentTelemetry.LastHudUtc.Value) <= hudFreshnessTimeout;

                if (healthy)
                {
                    CurrentTelemetry.ConnectionStateText = "Connected";
                }
                else
                {
                    CurrentTelemetry.ConnectionStateText =
                        CurrentTelemetry.LastHeartbeatUtc.HasValue
                            ? "Heartbeat timeout"
                            : "Waiting for heartbeat";
                }

                if (!CurrentTelemetry.IsGpsFresh && CurrentTelemetry.GpsRawCount > 0)
                {
                    CurrentTelemetry.IsGpsHealthy = false;
                    CurrentTelemetry.GpsHealthText = "GPS stale";
                }

                if (pendingCommandId.HasValue &&
                    pendingCommandSentUtc.HasValue &&
                    (now - pendingCommandSentUtc.Value) > commandAckTimeout)
                {
                    CurrentTelemetry.LastCommandId = pendingCommandId.Value;
                    CurrentTelemetry.LastCommandName = pendingCommandName;
                    CurrentTelemetry.LastCommandResult = 255;
                    CurrentTelemetry.LastCommandResultText = "ACK_TIMEOUT";
                    CurrentTelemetry.LastCommandStatus = "No ACK received";
                    CurrentTelemetry.LastCommandAckUtc = null;

                    pendingCommandId = null;
                    pendingCommandName = "-";
                    pendingCommandSentUtc = null;

                    shouldNotify = true;
                }

                if (lastWatchdogConnectedState != healthy)
                {
                    lastWatchdogConnectedState = healthy;
                    shouldNotify = true;
                }
            }

            if (shouldNotify)
            {
                TelemetryUpdated?.Invoke(this, CurrentTelemetry);
            }

            await Task.Delay(watchdogInterval, cancellationToken);
        }
    }

    private static ushort ComputeMavlinkV2Crc(ReadOnlySpan<byte> buffer, byte crcExtra)
    {
        ushort crc = 0xFFFF;

        foreach (var b in buffer)
        {
            crc = AccumulateCrc(b, crc);
        }

        crc = AccumulateCrc(crcExtra, crc);
        return crc;
    }

    private static ushort AccumulateCrc(byte data, ushort crc)
    {
        byte tmp = (byte)(data ^ (byte)(crc & 0xFF));
        tmp ^= (byte)(tmp << 4);

        return (ushort)(
            (crc >> 8) ^
            (tmp << 8) ^
            (tmp << 3) ^
            (tmp >> 4));
    }

    private void OnBytesReceived(object? sender, byte[] bytes)
    {
        bool shouldNotify = false;

        lock (telemetryLock)
        {
            CurrentTelemetry.TotalDatagramsReceived++;
            CurrentTelemetry.TotalBytesReceived += bytes.Length;
            CurrentTelemetry.LastTelemetryUtc = DateTime.UtcNow;

            ParseMavlinkFrames(bytes);
            shouldNotify = true;
        }

        if (shouldNotify)
        {
            TelemetryUpdated?.Invoke(this, CurrentTelemetry);
        }
    }

    private void ParseMavlinkFrames(byte[] bytes)
    {
        int index = 0;

        while (index < bytes.Length)
        {
            byte magic = bytes[index];

            if (magic == MavlinkV1Magic)
            {
                if (!TryParseMavlinkV1Frame(bytes, index, out int frameLength))
                {
                    index++;
                    continue;
                }

                index += frameLength;
                continue;
            }

            if (magic == MavlinkV2Magic)
            {
                if (!TryParseMavlinkV2Frame(bytes, index, out int frameLength))
                {
                    index++;
                    continue;
                }

                index += frameLength;
                continue;
            }

            index++;
        }
    }

    private bool TryParseMavlinkV1Frame(byte[] bytes, int startIndex, out int frameLength)
    {
        frameLength = 0;

        if (startIndex + 6 > bytes.Length)
        {
            return false;
        }

        int payloadLength = bytes[startIndex + 1];
        frameLength = 6 + payloadLength + 2;

        if (startIndex + frameLength > bytes.Length)
        {
            return false;
        }

        byte sourceSystem = bytes[startIndex + 3];
        byte sourceComponent = bytes[startIndex + 4];
        int messageId = bytes[startIndex + 5];

        UpdateTargetEndpoint(sourceSystem, sourceComponent);

        ReadOnlySpan<byte> payload = bytes.AsSpan(startIndex + 6, payloadLength);
        ProcessMessage(messageId, payload);
        return true;
    }

    private bool TryParseMavlinkV2Frame(byte[] bytes, int startIndex, out int frameLength)
    {
        frameLength = 0;

        if (startIndex + 10 > bytes.Length)
        {
            return false;
        }

        int payloadLength = bytes[startIndex + 1];
        byte incompatibilityFlags = bytes[startIndex + 2];
        bool hasSignature = (incompatibilityFlags & 0x01) == 0x01;

        frameLength = 10 + payloadLength + 2 + (hasSignature ? 13 : 0);

        if (startIndex + frameLength > bytes.Length)
        {
            return false;
        }

        byte sourceSystem = bytes[startIndex + 5];
        byte sourceComponent = bytes[startIndex + 6];

        int messageId =
            bytes[startIndex + 7]
            | (bytes[startIndex + 8] << 8)
            | (bytes[startIndex + 9] << 16);

        UpdateTargetEndpoint(sourceSystem, sourceComponent);

        ReadOnlySpan<byte> payload = bytes.AsSpan(startIndex + 10, payloadLength);
        ProcessMessage(messageId, payload);
        return true;
    }

    private void UpdateTargetEndpoint(byte sourceSystem, byte sourceComponent)
    {
        if (sourceSystem == 0)
        {
            return;
        }

        targetSystem = sourceSystem;

        if (sourceComponent != 0)
        {
            targetComponent = sourceComponent;
        }
    }

    private void ProcessMessage(int messageId, ReadOnlySpan<byte> payload)
    {
        switch (messageId)
        {
            case HeartbeatMessageId:
                ProcessHeartbeat(payload);
                break;

            case SysStatusMessageId:
                ProcessSysStatus(payload);
                break;

            case GpsRawIntMessageId:
                ProcessGpsRawInt(payload);
                break;

            case GlobalPositionIntMessageId:
                ProcessGlobalPositionInt(payload);
                break;

            case VfrHudMessageId:
                ProcessVfrHud(payload);
                break;

            case CommandAckMessageId:
                ProcessCommandAck(payload);
                break;

            case StatusTextMessageId:
                ProcessStatusText(payload);
                break;
        }
    }

    private void ProcessHeartbeat(ReadOnlySpan<byte> payload)
    {
        if (payload.Length < 9)
        {
            return;
        }

        uint customMode = BinaryPrimitives.ReadUInt32LittleEndian(payload.Slice(0, 4));
        byte baseMode = payload[6];

        CurrentTelemetry.LastHeartbeatUtc = DateTime.UtcNow;
        CurrentTelemetry.IsConnected = true;
        CurrentTelemetry.IsLinkHealthy = true;
        CurrentTelemetry.ConnectionStateText = "Connected";

        CurrentTelemetry.IsArmed = (baseMode & 0x80) == 0x80;
        CurrentTelemetry.FlightMode = ConvertArduCopterMode(customMode);
        CurrentTelemetry.HeartbeatCount++;
    }

    private void ProcessSysStatus(ReadOnlySpan<byte> payload)
    {
        if (payload.Length < 31)
        {
            return;
        }

        ushort voltageBattery = BinaryPrimitives.ReadUInt16LittleEndian(payload.Slice(14, 2));
        sbyte batteryRemaining = unchecked((sbyte)payload[30]);

        CurrentTelemetry.BatteryVoltage = voltageBattery / 1000.0;
        CurrentTelemetry.BatteryRemaining = batteryRemaining;
        CurrentTelemetry.SystemStatusCount++;
    }

    private void ProcessGpsRawInt(ReadOnlySpan<byte> payload)
    {
        if (payload.Length < 30)
        {
            return;
        }

        byte fixType = payload[8];
        ushort eph = BinaryPrimitives.ReadUInt16LittleEndian(payload.Slice(21, 2));
        ushort epv = BinaryPrimitives.ReadUInt16LittleEndian(payload.Slice(23, 2));
        ushort vel = BinaryPrimitives.ReadUInt16LittleEndian(payload.Slice(25, 2));
        ushort cog = BinaryPrimitives.ReadUInt16LittleEndian(payload.Slice(27, 2));
        byte satellitesVisible = payload[29];

        CurrentTelemetry.GpsFixType = fixType;
        CurrentTelemetry.GpsFixText = ConvertGpsFixType(fixType);
        CurrentTelemetry.SatellitesVisible = satellitesVisible == byte.MaxValue ? -1 : satellitesVisible;
        CurrentTelemetry.Hdop = eph == ushort.MaxValue ? 0 : eph / 100.0;
        CurrentTelemetry.Vdop = epv == ushort.MaxValue ? 0 : epv / 100.0;

        if (vel != ushort.MaxValue)
        {
            CurrentTelemetry.GroundSpeed = vel / 100.0;
        }

        if (cog != ushort.MaxValue)
        {
            CurrentTelemetry.Heading = (int)Math.Round(cog / 100.0);
        }

        CurrentTelemetry.HasGpsFix = fixType >= 3;
        CurrentTelemetry.IsGpsHealthy =
            CurrentTelemetry.HasGpsFix &&
            CurrentTelemetry.SatellitesVisible >= 6 &&
            (CurrentTelemetry.Hdop <= 2.5 || CurrentTelemetry.Hdop == 0);

        CurrentTelemetry.GpsHealthText = BuildGpsHealthText(
            CurrentTelemetry.GpsFixText,
            CurrentTelemetry.SatellitesVisible,
            CurrentTelemetry.Hdop,
            CurrentTelemetry.IsGpsHealthy);

        CurrentTelemetry.GpsRawCount++;
        CurrentTelemetry.LastGpsUtc = DateTime.UtcNow;
    }

    private void ProcessGlobalPositionInt(ReadOnlySpan<byte> payload)
    {
        if (payload.Length < 28)
        {
            return;
        }

        int latitude = BinaryPrimitives.ReadInt32LittleEndian(payload.Slice(4, 4));
        int longitude = BinaryPrimitives.ReadInt32LittleEndian(payload.Slice(8, 4));
        int relativeAltitude = BinaryPrimitives.ReadInt32LittleEndian(payload.Slice(16, 4));
        short vx = BinaryPrimitives.ReadInt16LittleEndian(payload.Slice(20, 2));
        short vy = BinaryPrimitives.ReadInt16LittleEndian(payload.Slice(22, 2));
        ushort heading = BinaryPrimitives.ReadUInt16LittleEndian(payload.Slice(26, 2));

        CurrentTelemetry.Latitude = latitude / 10000000.0;
        CurrentTelemetry.Longitude = longitude / 10000000.0;
        CurrentTelemetry.RelativeAltitude = relativeAltitude / 1000.0;

        double velocityNorth = vx / 100.0;
        double velocityEast = vy / 100.0;
        CurrentTelemetry.GroundSpeed = Math.Sqrt(
            velocityNorth * velocityNorth +
            velocityEast * velocityEast);

        if (heading != ushort.MaxValue)
        {
            CurrentTelemetry.Heading = (int)Math.Round(heading / 100.0);
        }

        CurrentTelemetry.PositionCount++;
        CurrentTelemetry.LastPositionUtc = DateTime.UtcNow;
    }

    private void ProcessVfrHud(ReadOnlySpan<byte> payload)
    {
        if (payload.Length < 20)
        {
            return;
        }

        float airspeed = BinaryPrimitives.ReadSingleLittleEndian(payload.Slice(0, 4));
        float groundspeed = BinaryPrimitives.ReadSingleLittleEndian(payload.Slice(4, 4));
        short heading = BinaryPrimitives.ReadInt16LittleEndian(payload.Slice(8, 2));
        ushort throttle = BinaryPrimitives.ReadUInt16LittleEndian(payload.Slice(10, 2));
        float altitude = BinaryPrimitives.ReadSingleLittleEndian(payload.Slice(12, 4));
        float climb = BinaryPrimitives.ReadSingleLittleEndian(payload.Slice(16, 4));

        CurrentTelemetry.AirSpeed = airspeed;
        CurrentTelemetry.GroundSpeed = groundspeed;
        CurrentTelemetry.Heading = heading;
        CurrentTelemetry.ThrottlePercent = throttle;
        CurrentTelemetry.AbsoluteAltitude = altitude;
        CurrentTelemetry.ClimbRate = climb;

        CurrentTelemetry.VfrHudCount++;
        CurrentTelemetry.LastHudUtc = DateTime.UtcNow;
    }

    private void ProcessCommandAck(ReadOnlySpan<byte> payload)
    {
        if (payload.Length < 3)
        {
            return;
        }

        ushort command = BinaryPrimitives.ReadUInt16LittleEndian(payload.Slice(0, 2));
        byte result = payload[2];

        string commandName = ResolveAckCommandName(command);
        string resultText = ConvertMavResult(result);

        CurrentTelemetry.CommandAckCount++;
        CurrentTelemetry.LastCommandId = command;
        CurrentTelemetry.LastCommandName = commandName;
        CurrentTelemetry.LastCommandResult = result;
        CurrentTelemetry.LastCommandResultText = resultText;
        CurrentTelemetry.LastCommandAckUtc = DateTime.UtcNow;
        CurrentTelemetry.LastCommandStatus = $"{commandName}: {resultText}";

        if (pendingCommandId == command && result != 5)
        {
            pendingCommandId = null;
            pendingCommandName = "-";
            pendingCommandSentUtc = null;
        }
    }

    private void ProcessStatusText(ReadOnlySpan<byte> payload)
    {
        if (payload.Length < 2)
        {
            return;
        }

        byte severity = payload[0];
        int textByteCount = Math.Min(50, payload.Length - 1);
        ReadOnlySpan<byte> textBytes = payload.Slice(1, textByteCount);

        int textLength = textBytes.IndexOf((byte)0);
        if (textLength < 0)
        {
            textLength = textBytes.Length;
        }

        string text = Encoding.ASCII.GetString(textBytes.Slice(0, textLength)).Trim();
        if (string.IsNullOrWhiteSpace(text))
        {
            return;
        }

        string severityText = ConvertMavSeverity(severity);

        CurrentTelemetry.LastStatusSeverity = severity;
        CurrentTelemetry.LastStatusText = $"{severityText}: {text}";

        if (IsPreArmRelatedText(text))
        {
            CurrentTelemetry.LastPreArmMessage = $"{severityText}: {text}";
        }
    }

    private string ResolveAckCommandName(ushort command)
    {
        if (pendingCommandId == command &&
            !string.IsNullOrWhiteSpace(pendingCommandName) &&
            pendingCommandName != "-")
        {
            return pendingCommandName;
        }

        return ConvertMavCommandName(command);
    }

    private static bool IsPreArmRelatedText(string text)
    {
        return text.Contains("PreArm", StringComparison.OrdinalIgnoreCase)
            || text.Contains("Arm:", StringComparison.OrdinalIgnoreCase)
            || text.Contains("Arming", StringComparison.OrdinalIgnoreCase);
    }

    private static string ConvertArduCopterMode(uint customMode)
    {
        return customMode switch
        {
            0 => "STABILIZE",
            1 => "ACRO",
            2 => "ALT_HOLD",
            3 => "AUTO",
            4 => "GUIDED",
            5 => "LOITER",
            6 => "RTL",
            7 => "CIRCLE",
            9 => "LAND",
            11 => "DRIFT",
            13 => "SPORT",
            14 => "FLIP",
            15 => "AUTOTUNE",
            16 => "POSHOLD",
            17 => "BRAKE",
            18 => "THROW",
            19 => "AVOID_ADSB",
            20 => "GUIDED_NOGPS",
            21 => "SMART_RTL",
            22 => "FLOWHOLD",
            23 => "FOLLOW",
            24 => "ZIGZAG",
            25 => "SYSTEMID",
            26 => "AUTOROTATE",
            27 => "AUTO_RTL",
            _ => $"CUSTOM {customMode}"
        };
    }

    private static string ConvertGpsFixType(byte fixType)
    {
        return fixType switch
        {
            0 => "No GPS",
            1 => "No Fix",
            2 => "2D Fix",
            3 => "3D Fix",
            4 => "DGPS",
            5 => "RTK Float",
            6 => "RTK Fixed",
            7 => "Static",
            8 => "PPP",
            _ => $"Unknown ({fixType})"
        };
    }

    private static string BuildGpsHealthText(string fixText, int satellitesVisible, double hdop, bool isHealthy)
    {
        if (satellitesVisible < 0)
        {
            return $"{fixText} / Satellites unknown";
        }

        string health = isHealthy ? "Healthy" : "Weak";
        string hdopText = hdop > 0 ? $"HDOP {hdop:0.0}" : "HDOP unknown";

        return $"{health} / {fixText} / {satellitesVisible} sats / {hdopText}";
    }

    private static string ConvertMavCommandName(ushort command)
    {
        return command switch
        {
            MavCmdComponentArmDisarm => "ARM/DISARM",
            MavCmdNavTakeoff => "TAKEOFF",
            MavCmdDoSetMode => "SET MODE",
            _ => $"COMMAND {command}"
        };
    }

    private static string ConvertMavResult(byte result)
    {
        return result switch
        {
        0 => "ACCEPTED",
        1 => "TEMPORARILY_REJECTED",
        2 => "DENIED",
        3 => "UNSUPPORTED",
        4 => "FAILED",
        5 => "IN_PROGRESS",
            6 => "CANCELLED",
            7 => "COMMAND_LONG_ONLY",
            8 => "COMMAND_INT_ONLY",
            9 => "COMMAND_UNSUPPORTED_MAV_FRAME",
            _ => $"UNKNOWN_RESULT_{result}"
        };
    }

    private static string ConvertMavSeverity(byte severity)
    {
        return severity switch
        {
            0 => "EMERGENCY",
            1 => "ALERT",
            2 => "CRITICAL",
            3 => "ERROR",
            4 => "WARNING",
            5 => "NOTICE",
            6 => "INFO",
            7 => "DEBUG",
            _ => $"SEVERITY {severity}"
        };
    }

    public async ValueTask DisposeAsync()
    {
        connection.BytesReceived -= OnBytesReceived;

        if (watchdogCts is not null)
        {
            await watchdogCts.CancelAsync();
            watchdogCts.Dispose();
            watchdogCts = null;
        }

        if (watchdogTask is not null)
        {
            try
            {
                await watchdogTask;
            }
            catch (OperationCanceledException)
            {
            }
        }

        await connection.DisposeAsync();
    }
}
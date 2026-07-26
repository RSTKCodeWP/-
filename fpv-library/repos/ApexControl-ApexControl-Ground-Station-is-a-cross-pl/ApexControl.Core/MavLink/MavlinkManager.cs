using System;
using Asv.Mavlink;
using Asv.Mavlink.V2.Common;

namespace ApexControl.Core.MavLink
{
    public class MavlinkManager : IDisposable
    {
        private IMavlinkV2Connection? _connection;
        private IDisposable? _packetSubscription;

        public VehicleState Vehicle { get; } = new VehicleState();

        public void Connect(string connectionString = "udp://127.0.0.1:14550")
        {
            _connection = MavlinkV2Connection.Create(connectionString);

            _packetSubscription = _connection.Subscribe(ProcessPacket);
        }

        private void ProcessPacket(IPacketV2<IPayload> packet)
        {
            switch (packet.Payload)
            {
                case HeartbeatPayload hb:
                    Vehicle.IsArmed = hb.BaseMode.HasFlag(MavModeFlag.MavModeFlagSafetyArmed);
                    Vehicle.FlightMode = hb.CustomMode.ToString();
                    break;

                case GlobalPositionIntPayload gpi:
                    Vehicle.Latitude = gpi.Lat / 1e7;
                    Vehicle.Longitude = gpi.Lon / 1e7;
                    Vehicle.RelativeAltitude = gpi.RelativeAlt / 1000.0;
                    break;

                case SysStatusPayload sys:
                    Vehicle.BatteryVoltage = sys.VoltageBattery / 1000.0;
                    break;
            }
        }

        public void Dispose()
        {
            _packetSubscription?.Dispose();
            _connection?.Dispose();
        }
    }
}

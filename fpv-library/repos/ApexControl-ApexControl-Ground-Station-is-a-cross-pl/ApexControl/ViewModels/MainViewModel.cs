using ApexControl.Core.MavLink;
using CommunityToolkit.Mvvm.ComponentModel;
using System.Collections.ObjectModel;
using System.Data;

namespace ApexControl.ViewModels
{
    public partial class MainViewModel : ObservableObject
    {
        private readonly MavlinkManager _mavlinkManager;

        [ObservableProperty]
        private string _connectionStatus = "Disconnected";

        // ما ویژگی‌های Vehicle را اینجا مپ می‌کنیم تا UI تغییرات را بفهمد
        public VehicleState Drone => _mavlinkManager.Vehicle;

        public MainViewModel()
        {
            _mavlinkManager = new MavlinkManager();
        }

        // دستور برای دکمه اتصال
        public void Connect()
        {
            try
            {
                _mavlinkManager.Connect("udp://127.0.0.1:14550");
                ConnectionStatus = "Connected to SITL";
            }
            catch (Exception ex)
            {
                ConnectionStatus = $"Error: {ex.Message}";
            }
        }
    }
}

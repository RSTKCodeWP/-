using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace ApexControl.Core.MavLink
{
    public class VehicleState : INotifyPropertyChanged
    {
        private double _latitude;
        private double _longitude;
        private double _relativeAltitude;
        private double _batteryVoltage;
        private string _flightMode = "Unknown";
        private bool _isArmed;

        public double Latitude
        {
            get => _latitude;
            set => SetProperty(ref _latitude, value);
        }

        public double Longitude
        {
            get => _longitude;
            set => SetProperty(ref _longitude, value);
        }

        public double RelativeAltitude
        {
            get => _relativeAltitude;
            set => SetProperty(ref _relativeAltitude, value);
        }

        public double BatteryVoltage
        {
            get => _batteryVoltage;
            set => SetProperty(ref _batteryVoltage, value);
        }

        public string FlightMode
        {
            get => _flightMode;
            set => SetProperty(ref _flightMode, value);
        }

        public bool IsArmed
        {
            get => _isArmed;
            set => SetProperty(ref _isArmed, value);
        }

        // برای آپدیت خودکار در UI
        public event PropertyChangedEventHandler PropertyChanged;
        protected void SetProperty<T>(ref T storage, T value, [CallerMemberName] string propertyName = null)
        {
            if (Equals(storage, value)) return;
            storage = value;
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
        }
    }
}

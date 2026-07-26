class FlightData:

    def __init__(self):

        self.latitude = 0.0
        self.longitude = 0.0
        self.altitude = 0.0

        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0

        self.battery = 0.0

    def update_data(
        self,
        telemetry
    ):

        self.latitude = telemetry["latitude"]
        self.longitude = telemetry["longitude"]
        self.altitude = telemetry["altitude"]

        self.roll = telemetry["roll"]
        self.pitch = telemetry["pitch"]
        self.yaw = telemetry["yaw"]

        self.battery = telemetry["batteryVoltage"]

    def show(self):

        print("Latitude:", self.latitude)
        print("Longitude:", self.longitude)
        print("Altitude:", self.altitude)

        print("Roll:", self.roll)
        print("Pitch:", self.pitch)
        print("Yaw:", self.yaw)

        print("Battery:", self.battery)
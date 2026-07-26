import tkinter as tk

root = tk.Tk()

root.title("UAV Ground Dashboard")
root.geometry("1024x600")

title = tk.Label(
    root,
    text="LoRa UAV Ground Control Station",
    font=("Arial", 24, "bold")
)

title.pack(pady=20)

flight_mode = tk.Label(
    root,
    text="MODE: GUIDED",
    font=("Arial", 18)
)

flight_mode.pack()

battery = tk.Label(
    root,
    text="Battery: 11.8V",
    font=("Arial", 18)
)

battery.pack()

gps = tk.Label(
    root,
    text="GPS: LOCKED",
    font=("Arial", 18)
)

gps.pack()

altitude = tk.Label(
    root,
    text="Altitude: 120m",
    font=("Arial", 18)
)

altitude.pack()

root.mainloop()
gui/map_window.py
import folium
import webbrowser

MAP_FILE = "uav_map.html"

latitude = 28.6139
longitude = 77.2090

uav_map = folium.Map(
    location=[latitude, longitude],
    zoom_start=15
)

folium.Marker(
    [latitude, longitude],
    popup="UAV Position"
).add_to(uav_map)

uav_map.save(MAP_FILE)

webbrowser.open(MAP_FILE)

print("Map Generated")
gui/flight_data.py
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
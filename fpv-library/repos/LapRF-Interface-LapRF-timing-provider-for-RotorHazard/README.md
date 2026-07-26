# RotorHazard LapRF Interface

This plugin allows RotorHazard to interface with an Orqa/ImmersionRC LapRF 8-way to configure the device and use it as a lap data source.

## Installation

Install through the "Community Plugins" area within RotorHazard. Alternately, copy the `rh_interface_laprf` directory from inside `custom_plugins` into the plugins directory of your RotorHazard data directory.

## Usage

### Connecting LapRF Devices
On the `Settings` page, find the `LapRF General Setup` panel. Set the `Device Count` to the number of LapRF devices you intend to connect. Each device will be assigned 8 seats even while not connected. You will be prompted to restart the server to apply changes to this setting.

> [!Tip]
> You may set `Device Count` to 0 to disable the LapRF seats without deleting your configuration or removing the plugin. Addresses will be restored and used when you set `Device Count` to a positive number again.

On the `LapRF General Setup` panel, set the address for each device. You may use the IP address on a network, or USB port identifier for your system. All LapRF devices will disconnect when editing any address. When finished, press the `Connect` button to establish a connection to all devices. When connected, each `LapRF Device <n>` panel will populate with configuration and status information.

The `Disconnect` button will break the connection with all devices.

`Save to Device` will save settings such as gain, threshold, and min lap to each LapRF device's internal memory, to be recalled after the next startup.

### Configuring Devices
There are write-only fields in the `LapRF General Setup` panel which will apply values to every seat of every connected device. For example, if you enter "40" into `Set All Gains`, then the `Gain` value for all 8 seats of each device will be set to "40". These fields will go blank after entry because they do not read data back from the device. You can confirm the new value in each `LapRF Device <n>` panel.

Within each `LapRF Device <n>` panel, you may review status and view/change settings for each independent device. Settings are immediately sent to the LapRF and take effect when changed. They will not, however, be retained after the device is powered off unless you use the `Save to Device` function.

When connecting, RotorHazard will attempt to calculate a synchronization value between the server and LapRF device clocks. The result of this synchronization will be displayed at the top of the device panel. On a typical network, synchronization will quickly be determined within 1ms. On poor networks, synchronization may be initially high and settle over time as more samples are taken.

16-seat half-precision mode is not currently supported.

### Calibration
Calibrate each LapRF device using the `Gain` and `Threshold` settings. The LapRF does not use RotorHazard's Enter and Exit points, and Adaptive Calibration has no effect with LapRF Devices.

> [!Tip]
> It is recommended to set `Minimum Lap Time` to 1. Using a higher setting can mask false positive reads because only the first crossing will be recorded. There is no notification when crossings have been ignored, which may result in recording inaccurate times. If you are receiving multiple crossing records during a regular gate pass, adjust the `Gain` and `Threshold` settings until this no longer occurs.

### Marshaling
The LapRF does not send data which can be accurately used in RotorHazard's Marshal feature to recreate the race with different calibration values. When using the LapRF, the RSSI history will be blank and this feature is not available.

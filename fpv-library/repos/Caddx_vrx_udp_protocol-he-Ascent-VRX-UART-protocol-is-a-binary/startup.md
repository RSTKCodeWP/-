# Startup Commands

## Interactive Keyboard Control

Start the UDP VRX client in interactive keyboard mode. The program listens for
keyboard input, sends the corresponding simulated VRX key commands, and monitors
UDP responses. Press `Q` to exit.

```powershell
python udp_vrx_client.py keyboard
```

## Wireless Status Query

Send a wireless-status request to the default VRX endpoint
(`192.168.1.100:9001`) and then continuously listen for UDP responses. Press
`Ctrl+C` to stop.

```powershell
python udp_vrx_client.py status
```

## Dual Ctrl and OSD UDP Diagnostics

Start Ctrl UDP 9001 and OSD UDP 9200, send the OSD mode-switch packet on the
Ctrl channel, wait 500 ms, send probe bytes `11 12 13 14` on the OSD channel,
and print Ctrl responses plus reassembled MSP v1/v2 traffic. Press `Ctrl+C` to
close both sockets.

```powershell
python udp_vrx_client.py osd
```

Use the USB-C device profile:

```powershell
python udp_vrx_client.py --profile usb-c osd
```

Override endpoints explicitly:

```powershell
python udp_vrx_client.py --host 192.168.1.100 --ctrl-port 9001 --osd-port 9200 osd
```

Probe and listen without sending the OSD mode-switch packet:

```powershell
python udp_vrx_client.py osd --no-mode-switch
```

## Real USB-C Device Verification

For the real VRX at `192.168.3.102`, run this command from the repository
folder:

```powershell
python udp_vrx_client.py --profile usb-c osd
```

The command performs the following sequence:

1. Start Ctrl UDP `192.168.3.102:9001`;
2. Start OSD UDP `192.168.3.102:9200`;
3. Send the OSD mode-switch packet through Ctrl UDP;
4. Wait 500 ms;
5. Send `11 12 13 14` through OSD UDP;
6. Listen to both channels until `Ctrl+C`.

A valid Ctrl response is printed as a decoded VRX frame. MSP data is printed
only after a complete MSP v1/v2 frame reaches UDP 9200. If the output remains
`OSD=No rec`, the Ctrl channel is responding but the device has not sent OSD
UDP data to the local listener.

## Passthrough Mode Switch

Send only a mode-switch packet through Ctrl UDP 9001, then listen for Ctrl
responses:

```powershell
python udp_vrx_client.py set-mode osd
python udp_vrx_client.py set-mode crsf
```

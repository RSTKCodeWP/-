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

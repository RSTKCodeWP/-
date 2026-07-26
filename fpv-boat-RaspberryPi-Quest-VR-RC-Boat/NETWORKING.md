# Networking

Notes for keeping the Pi reachable — the recurring "unreachable / wrong IP"
pain has cost real time on this project.

## Current identity

- **Hostname:** `FPV-boat`  → reachable at `fpv-boat.local` if mDNS/avahi is up
- **IP (DHCP):** `10.0.0.26` (was `10.0.0.20` earlier — it drifts, hence the fix below)

If the viewer says "unreachable," first SSH in (or check on the Pi) with:

```sh
hostname -I          # what IP did DHCP actually assign?
```

Try `ping fpv-boat.local` from the client — if mDNS resolves, you don't need to
chase the numeric IP at all.

## Stop the IP from changing

**Option A — router DHCP reservation (recommended, OS-agnostic).**
Bind the Pi's WiFi MAC to a fixed IP in your router's admin panel. Get the MAC:

```sh
ip link show wlan0     # the "link/ether xx:xx:xx:xx:xx:xx" line
```

**Option B — static IP on the Pi.** Depends on the OS:

- **Bookworm (NetworkManager)** — check with `nmcli -t -f NAME connection show`:
  ```sh
  sudo nmcli connection modify "<wifi-name>" \
    ipv4.method manual ipv4.addresses 10.0.0.26/24 ipv4.gateway 10.0.0.1 ipv4.dns 10.0.0.1
  sudo nmcli connection up "<wifi-name>"
  ```

- **Bullseye or older (dhcpcd)** — append to `/etc/dhcpcd.conf`:
  ```
  interface wlan0
  static ip_address=10.0.0.26/24
  static routers=10.0.0.1
  static domain_name_servers=10.0.0.1
  ```
  then `sudo systemctl restart dhcpcd`.

## Keep WiFi power management off (fixes intermittent SSH drops)

`iwconfig wlan0 power off` only lasts until reboot. Make it persist:

- **Bookworm (NetworkManager):**
  ```sh
  sudo nmcli connection modify "<wifi-name>" 802-11-wireless.powersave 2   # 2 = disable
  sudo nmcli connection up "<wifi-name>"
  ```

- **Older (rc.local):** ensure `/etc/rc.local` contains `iwconfig wlan0 power off`
  before the `exit 0` line.

**Verify after an actual reboot** (don't trust that it saved):

```sh
sudo reboot
# then, once back up:
iwconfig wlan0 | grep -i "power management"   # want: Power Management:off
```

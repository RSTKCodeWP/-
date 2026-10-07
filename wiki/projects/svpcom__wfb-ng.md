# svpcom/wfb-ng

> Картка виставки. Зал: [Радіо і відеолінк](../halls/link.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [svpcom/wfb-ng](https://github.com/svpcom/wfb-ng) |
| Локальна тека | `wfb-ng-WiFi-FPV-Long-Range-Radio-Link` |
| У бібліотеці | keep |
| Категорії каталогу | `link` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

This is the next generation of long-range **packet** radio link based on **raw WiFi radio**

Main features: -------------- supports gstreamer and OpenGL (Linux X11/Wayland, etc). Compatible with any screen resolution.

> :warning: **Warranty/Disclaimer** <br /> > This is free software and comes with no warranty, as stated in parts 15 and 16 of the GPLv3 license. The creators and contributors of the software are not responsible for how it is used. > See [License and Support](https://github.com/svpcom/wfb-ng/wiki/License-and-Support) for details.

_З README.md, без переказу._

## Для чого

This is the next generation of long-range **packet** radio link based on **raw WiFi radio**

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Інженер радіолінка — у тексті є «wfb-ng».
- Розробник відеотракту — у тексті є «gstreamer».


## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `Changelog.md`
- `CONTRIBUTING.md`
- `debian/`
- `doc/`
- `docker/`
- `LICENSE.txt`
- `Makefile`
- `openwrt/`
- `README.md`
- `scripts/`
- `SECURITY.md`
- `setup.py`
- `src/`
- `stdeb.cfg`
- `version.py`
- `wfb_ng/`

Типи файлів за вибіркою (97 файлів, глибина до 3): Python (22), (без суфікса) (14), C (13), shell (11), .service (9), C++ (8).


## Що треба

- Маніфести збірки: Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Getting Started

For detailed instructions on how to get started read through
[PX4-Guide](https://docs.px4.io/main/en/companion_computer/video_streaming_wfb_ng_wifi.html)
and follow the [Setup HowTo](https://github.com/svpcom/wfb-ng/wiki/Setup-HOWTO)
### Quick start using Raspberry Pi

- Under [Releases](https://github.com/svpcom/wfb-ng/releases) download the latest image file (`*.img.gz`).
- Unpack the `*.img` file and flash it to 2-SD Cards.
- Plug the WiFi Adapters into the Raspberry Pis
- Boot the Pis and ssh into them using the following command (replace `192.168.0.111` with their IP-Address). Password: `raspberry`
```
ssh pi@192.168.0.111
```

For putty users don't forget to select: `Settings -> Window -> Translation -> Enable VT100 line drawing` checkbox before connect.

- On the Pi used as ground station:
```
sudo systemctl enable wifibroadcast@gs
sudo systemctl enable rtsp
sudo systemctl enable fpv-video
sudo systemctl enable osd
sudo reboot
```

- On the Pi used on the drone:
```
sudo systemctl enable wifibroadcast@drone
sudo systemctl enable fpv-camera
sudo reboot
```
- Done! You should be able to see the video from the FPV camera. To monitor the link use the following command on the ground station:
```
wfb-cli gs
```
### Quick start using Debian or Ubuntu Ground Station

- Install patched `RTL8812AU` or `RTL8812EU` driver:
```
sudo apt-get install dkms
# For 8812au:
git clone -b v5.2.20 https://github.com/svpcom/rtl8812au.git
cd rtl8812au/
# For 8812eu:
git clone -b v5.15.0.1 https://github.com/svpcom/rtl8812eu.git
cd rtl8812eu/
# For both:
sudo ./dkms-install.sh
```
- Get the name of the WiFi card by running:
```
ifconfig
```
- You should see output similar to:
```
wlan0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 2312
        ether 0c:91:60:0a:5a:8b  txqueuelen 1000  (Ethernet)
        RX packets 0  bytes 0 (0.0 B)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 0  bytes 0 (0.0 B)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0
```
- Run `$ ethtool -i wlan0` and ensure that it show right driver: `rtl88xxau_wfb` or `rtl8812eu`
- Download and run [install_gs.sh](https://raw.githubusercontent.com/svpcom/wfb-ng/refs/heads/master/scripts/install_gs.sh):
```
curl -o install_gs.sh https://raw.githubusercontent.com/svpcom/wfb-ng/refs/heads/master/scripts/install_gs.sh
sudo bash ./install_gs.sh
```
- Done! To monitor the link use the following command on the ground station:
```
wfb-cli gs
```


**Failing to get connection?**

1. Check WFB-ng GS logs with `sudo journalctl -xu wifibroadcast@gs`. If there is any errors then try to resolve it.
2. If there are any encryption errors then ensure that `drone.key` and `gs.key` on drone and gs corresponds each other.
2. Make sure the WiFi channel and link domain on the ground and on the drone are the same. To check, see `/etc/wifibroadcast.cfg` and ensure that `[common] wifi_channel` and `[drone] link_domain` / `[gs] link domain`  is the same on the ground and on the drone.

---
### Sample usage chain:

```
Camera --[RTP stream (UDP)]--> wfb_ng --//--[ RADIO ]--//--> wfb_ng --[RTP stream (UDP)]--> gstreamer --> Display
```

- For encoding video from OpenIPC-based security camera connected via ethernet to your PC or SBC you don't need a special pipeline. Just set `outgoing` to `udp://your_ip_address:5602` in [majestic.yaml](https://github.com/OpenIPC/wiki/blob/master/en/majestic-streamer.md#other-outgoing-options)

- For encoding video from a Raspberry Pi Camera (obsolete, latency is high comparing to OpenIPC):
 ```
 raspivid -n  -ex fixedfps -w 960 -h 540 -b 4000000 -fps 30 -vf -hf -t 0 -o - | \
                gst-launch-1.0 -v fdsrc ! h264parse ! rtph264pay config-interval=1 pt=35 ! udpsink sync=false host=127.0.0.1 port=5602
 ```

- For encoding video from Logitech C920 camera (obsolete, camera is EOL many years ago):
 ```
 gst-launch-1.0 uvch264src device=/dev/video0 initial-bitrate=6000000 average-bitrate=6000000 iframe-period=1000 name=src auto-start=true \
                src.vidsrc ! queue ! video/x-h264,width=1920,height=1080,framerate=30/1 ! h264parse ! rtph264pay ! udpsink host=localhost port=5602
 ```

- To decode:
 ```
 gst-launch-1.0 udpsrc port=5600 caps='application/x-rtp, media=(string)video, clock-rate=(int)90000, encoding-name=(string)H264' \
                ! rtph264depay ! avdec_h264 ! clockoverlay valignment=bottom ! autovideosink fps-update-interval=1000 sync=false
 ```

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../wfb-ng-WiFi-FPV-Long-Range-Radio-Link/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `wfb-ng-WiFi-FPV-Long-Range-Radio-Link/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/svpcom__wfb-ng.md`.

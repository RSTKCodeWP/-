# Встановлення AeroStab на Raspberry Pi Zero 2W

## Передумови

- Raspberry Pi OS **Bookworm 64-bit Lite**
- Hostname: `aerostab` (для http://aerostab.local:8080)
- Користувач `pi` у групах `dialout`, `video`, `spi` (інсталятор додає автоматично)

## Швидке встановлення

```bash
cd AeroStab
sudo bash deploy/install_pi.sh
sudo reboot
```

Після перезавантаження:

```
http://aerostab.local:8080
```

## Що робить install_pi.sh

1. Встановлює Python 3, picamera2, libcamera, avahi (mDNS).
2. Налаштовує `/boot/firmware/config.txt`:
   - `camera_auto_detect=1`, `dtoverlay=ov5647`
   - `enable_uart=1`, `dtoverlay=disable-bt` (UART на GPIO14/15)
   - `gpu_mem=128`, `dtparam=spi=on` (для PMW3901, опційно)
3. Копіює проєкт у `/opt/aerostab`.
4. Створює venv і встановлює `pip install -e .[pi,sensors]`.
5. Конфіг: `/etc/aerostab/config.yaml`, маска: `/etc/aerostab/mask.json`.
6. Реєструє systemd-сервіс `aerostab.service`.

## Перевірка після встановлення

```bash
sudo systemctl status aerostab
journalctl -u aerostab -f
python3 /opt/aerostab/scripts/selfcheck.py
```

У веб-інтерфейсі → вкладка **Перевірки** — усі пункти зелені.

## Оновлення

```bash
cd /opt/aerostab
sudo git pull   # або rsync з ПК
sudo .venv/bin/pip install -e .[pi,sensors]
sudo systemctl restart aerostab
```

## Логи

- Сервіс: `journalctl -u aerostab`
- CSV: `/var/log/aerostab/`
- Аналіз: `python3 /opt/aerostab/scripts/analyze_log.py -d /var/log/aerostab`

## Wi-Fi provisioning

```bash
sudo aerostab-wifi "SSID" "password"
```

# Запис SD-карти для Raspberry Pi Zero 2W

## Що потрібно

- Raspberry Pi Zero 2W
- microSD 16 GB+ (Class 10 / A1)
- Камера Frank-S01-V1.0 (OV5647 CSI)
- Блок живлення 5V ≥ 2.5A (рекомендовано з запасом)
- [Raspberry Pi Imager](https://www.raspberrypi.com/software/)

## Крок 1 — Raspberry Pi Imager

1. Вставте SD-карту в ПК.
2. Відкрийте **Raspberry Pi Imager**.
3. **Choose Device** → **Raspberry Pi Zero 2 W**.
4. **Choose OS** → **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (64-bit)**.
5. **Choose Storage** → ваша SD-карта.
6. Натисніть **Next** → **Edit Settings** (шестерня):

| Параметр | Значення |
|----------|----------|
| Hostname | `aerostab` |
| Username | `pi` |
| Password | ваш пароль |
| Wi-Fi SSID / пароль | ваша мережа |
| Enable SSH | увімкнено (password або ключ) |
| Locale | `uk_UA.UTF-8` або `en_GB.UTF-8` |

7. **Save** → **Yes** (записати) → **Yes** (перезаписати).

## Крок 2 — AeroStab bundle (авто-встановлення)

Після запису OS змонтуйте розділ **boot** (або `bootfs`):

```bash
# На ПК (Linux/macOS), з каталогу AeroStab:
bash image/build_sd_bundle.sh
```

Скрипт створить `dist/aerostab-sd-bundle.tar.gz`. Розпакуйте на boot-розділ:

```bash
sudo tar -xzf dist/aerostab-sd-bundle.tar.gz -C /media/$USER/bootfs/
```

На boot-розділі з'явиться папка `aerostab/` з прапорцем першого завантаження.

## Крок 3 — Перше увімкнення

1. Вставте SD в Pi Zero 2W.
2. Підключіть CSI-камеру Frank-S01.
3. Подайте живлення 5V.
4. Зачекайте ~5–10 хв (перше встановлення пакетів).
5. Відкрийте **http://aerostab.local:8080** (або IP з роутера).

Якщо mDNS не працює — знайдіть IP в роутері або підключіть монітор.

## Альтернатива без bundle

Після SSH на Pi:

```bash
git clone https://github.com/RSTKCodeWP/-/tree/main/AeroStab  # або скопіюйте репозиторій
cd AeroStab
sudo bash deploy/install_pi.sh && sudo reboot
```

Детальніше — розділ **Встановлення на Pi**.

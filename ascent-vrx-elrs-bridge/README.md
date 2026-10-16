# Ascent VRX Pro + ELRS через ESP32-S3 DevKit

Мінімальна прошивка: **прозорий CRSF-міст** (ELRS RX ↔ боковий SH1.0 VRX) і **UDP-керування VRX** по USB-C (профіль `192.168.3.102:9001`, протокол [Caddx_vrx_max_udp_protocol](https://github.com/CaddxFPV-Tech/Caddx_vrx_max_udp_protocol)).

## Ланцюг

```text
Пульт → ELRS TX ═══ RF ═══ ELRS RX → ESP32-S3 → VRX (боковий UART, ELRS passthrough) → VTX → FC
                              └─ USB-C (RNDIS) → UDP Ctrl :9001 → меню / частота / потужність VRX
```

## Налаштування VRX (один раз)

1. **Settings → Device → VRX UART** → **ELRS Passthrough** (для керування бортом через боковий порт).
2. Packet Rate на пульті **≤ 100 Hz** (рекомендація Caddx).
3. На FC — failsafe / RTH.

USB-C на VRX дає мережу `192.168.3.0/24`, пристрій VRX — **`192.168.3.102`**, Ctrl UDP **`9001`**.

## Підключення (ESP32-S3-DevKitC-1)

| Сигнал | ESP32-S3 GPIO | Куди |
|--------|---------------|------|
| ELRS RX (CRSF TX) | GPIO **18** (UART1 RX) | TX модуля ELRS |
| ELRS TX (CRSF RX) | GPIO **17** (UART1 TX) | RX модуля ELRS |
| VRX UART RX | GPIO **16** (UART2 TX) | **Сірий** RX на SH1.0 VRX |
| VRX UART TX | GPIO **15** (UART2 RX) | **Зелений** TX на SH1.0 VRX |
| GND | GND | **Чорний** GND на VRX + GND ELRS |
| 5 V ELRS | — | **Червоний** 5 V Out на VRX (не живити ELRS від 3.3 V ESP!) |

**USB-C:** ESP32-S3 **USB OTG (Host)** → кабель → USB-C VRX (мережа + UDP). Окремий USB на DevKit — лише прошивка / Serial Monitor.

Піни змінюються в `main/config.h`.

## Збірка (ESP-IDF)

Потрібен [ESP-IDF](https://docs.espressif.com/projects/esp-idf/) ≥ 5.1 і ціль `esp32s3`.

```bash
cd ascent-vrx-elrs-bridge
idf.py set-target esp32s3
idf.py build flash monitor
```

Компонент `espressif/iot_usbh_rndis` підтягується через `main/idf_component.yml`.

## Serial CLI (115200, USB-UART DevKit)

| Команда | Дія |
|---------|-----|
| `help` | Довідка |
| `status` | Запит wireless status (UDP) |
| `key up` / `down` / `left` / `right` / `confirm` / `back` | Симуляція кнопок VRX |
| `net` | IP на RNDIS та ping VRX |

## Принципи реалізації

- **CRSF:** окремий FreeRTOS task на ядрі 0, лише копіювання байтів UART↔UART, **420000 8N1**, без парсингу в hot path.
- **VRX UDP:** кадри `FE EF | CMD | LEN | payload | checksum | 0D 0A` як у офіційному клієнті; checksum = sum(payload) & 0xFFFF, BE.
- **Мережа:** DHCP на RNDIS від VRX, потім UDP на `VRX_HOST:VRX_CTRL_PORT`.

## Примітки

- Протокол UDP офіційно описаний для **Ascent VRX Max**; Ascent VRX Pro використовує той самий Ctrl UDP у PC Tool / GroundConfiguration — при відмінностях порівняйте з [UserManuals](https://github.com/CaddxFPV-Tech/Caddx_vrx_max_udp_protocol/tree/main/UserManuals).
- Якщо UDP не відповідає, перевірте підмережу, firewall і що USB-C VRX у режимі мережевого gadget.

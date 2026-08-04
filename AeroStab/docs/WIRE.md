# Проводка та налаштування ArduPilot

## UART між Pi Zero 2W і Flight Controller

| Pi GPIO | Pi pin | → FC |
|---------|--------|------|
| GPIO14 (TXD) | 8 | RX (TELEM) |
| GPIO15 (RXD) | 10 | TX (TELEM) |
| GND | 6, 9, 14… | GND |
| 5V | 2 або 4 | 5V (якщо FC приймає 5V logic) |

**Важливо:** TX Pi → RX FC, RX Pi → TX FC (перехрест).

Рекомендовано **TELEM2** на FC (не GPS-порт).

## Швидкість

- **230400** baud (за замовчуванням у `deploy/ardupilot_aerostab.param`)
- У веб-UI → Налаштування → MAVLink: `port: auto` або `/dev/serial0`

## ArduPilot параметри

Завантажте у Mission Planner / QGroundControl:

```
deploy/ardupilot_aerostab.param
```

Ключові параметри:

| Параметр | Значення | Опис |
|----------|----------|------|
| `SERIAL2_PROTOCOL` | 2 | MAVLink2 на TELEM2 |
| `SERIAL2_BAUD` | 230 | 230400 |
| `EK3_SRC1_POSXY` | 6 | ExternalNav (vision) |
| `EK3_SRC1_VELXY` | 6 | ExternalNav velocity |
| `EK3_SRC1_YAW` | 1 | Компас (не visual yaw) |
| `GPS1_TYPE` | 0 | GPS вимкнено |
| `ARMING_CHECK` | 8775 | Без GPS check |

Якщо TELEM на іншому порту — змініть `SERIALx_*` відповідно.

## Failsafe RTL

Додатково (опційно):

```
deploy/ardupilot_rtl_failsafe.param
```

## Камера Frank-S01

- CSI стрічка: синя сторона до Ethernet, срібна до USB (на Zero 2W).
- FOV за замовчуванням **72.4°** — перевірте сіткою 1 м на висоті ~1 м.

## Перший політ

1. Проводка + params завантажені.
2. Веб-UI → **Маска** — закрийте ніжки/пропи в кадрі.
3. Чекайте **FLIGHT OK**.
4. Arm у режимі **PosHold**, стіки в центрі.

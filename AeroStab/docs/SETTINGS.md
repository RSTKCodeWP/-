# Довідник налаштувань

Усі параметри доступні у веб-інтерфейсі → **Налаштування**. Зміни зберігаються в `/etc/aerostab/config.yaml`.

## Камера

| Параметр | Опис |
|----------|------|
| `backend` | `auto` / `picamera2` / `v4l2` / `synthetic` |
| `fov_deg` | Кут огляду. Frank-S01 ≈ 72.4° |
| `rotation_deg` | Поворот кадру (0, 90, 180, 270) |
| `show_grid` | Сітка 1 м для калібрування FOV |

## MAVLink

| Параметр | Опис |
|----------|------|
| `port` | `auto` — автодетект UART; або `/dev/serial0`, `tcp:127.0.0.1:5760` |
| `baud` | 230400 для TELEM2 |
| `send_vision_position` | VISION_POSITION_ESTIMATE → EKF |
| `send_optical_flow` | OPTICAL_FLOW (вимкнено за замовчуванням) |

## Висота

| `source` | Коли використовувати |
|----------|---------------------|
| `auto` | Rangefinder → baro relative → relative alt |
| `rangefinder` | Є дальномір на FC |
| `baro_relative` | Відносна баро-висота після ARM |
| `static` | Фіксована висота зависання |

**Не використовуйте AMSL** — ламає масштаб optical flow.

## Якість / failsafe

| Параметр | Опис |
|----------|------|
| `min_quality` | Мін. якість tracking (0–1) |
| `hold_last_on_drop` | Заморозити одометрію при втраті текстури |
| `hold_send_last_pose` | Продовжувати надсилати останню позу в EKF |
| `nav_valid_warmup_s` | Час прогріву перед NAV valid |

## Optical flow

- `max_corners` — кількість feature points
- `use_visual_yaw` — **false** для продакшену (yaw з компаса FC)
- `velocity_lpf_alpha` — згладжування швидкості

## GPS fusion

Увімкніть якщо є GPS на FC для корекції drift. Для чистого PosHold без GPS — **вимкнено**.

## PMW3901 (опційно)

Оптичний сенсор на SPI для допомоги при низькій текстурі. `blend_weight` 0–1 змішує з камерою.

## Гарячий reload vs перезапуск

| Секція | Без перезапуску |
|--------|-----------------|
| camera (FOV) | так |
| quality, estimator, odometry | так (частково) |
| mavlink port/baud | ні — `sudo systemctl restart aerostab` |
| camera backend | ні |

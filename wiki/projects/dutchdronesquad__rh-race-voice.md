# Race Voice

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [dutchdronesquad/rh-race-voice](https://github.com/dutchdronesquad/rh-race-voice) |
| Локальна тека | `fpv-library/repos/rh-race-voice-Local-server-side-voice-callouts-for-Ro` |
| У бібліотеці | watch |
| Категорії каталогу | `other` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-07-24 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

Server-side voice callouts for the [RotorHazard] timing platform, powered by [Piper TTS]. Audio is generated on the RotorHazard server and sent to `sendspin-service`, which streams to connected clients using the [Sendspin] protocol.

_З README.md, без переказу._

## Для чого

▶️ Local server-side voice callouts for RotorHazard

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

Теми GitHub: `piper-tts`, `python`, `rotorhazard`, `sendspin`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: ▶️ Local server-side voice callouts for RotorHazard

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `AGENTS.md`
- `CHANGELOG.md`
- `compose.yaml`
- `CONTRIBUTING.md`
- `custom_plugins/`
- `Dockerfile`
- `docs/`
- `LICENSE`
- `packaging/`
- `pyproject.toml`
- `Race Voice Plugin PVA.md`
- `README.md`
- `Sendspin Service Package PVA.md`
- `sendspin_player/`
- `sendspin_service/`
- `tools/`
- `uv.lock`

Типи файлів за вибіркою (75 файлів, глибина до 3): Python (21), Markdown (11), TypeScript (10), (без суфікса) (9), JSON (9), YAML (3).


## Що треба

### Requirements

- [RotorHazard] with RHAPI support for `Evt.RACE_STAGE_TONE` and `Evt.RACE_CLOCK_CALLOUT`.
- Python 3.12 or newer.
- `sendspin-service` installed on the RotorHazard host or another reachable machine.
- Network access from playback clients to `sendspin-service`.
- A browser on the playback device. RotorHazard serves the Sendspin player at `<RotorHazard UI base URL>/player`.

- Маніфести збірки: Python (pyproject.toml).
- pyproject name: `local-voice`.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Quick Start

1. Download `race_voice.zip` from the latest GitHub release.
2. In RotorHazard, open the plugin manager and upload the ZIP file.
3. Restart RotorHazard if requested.
4. Download the matching `sendspin-service_*.deb` from the same GitHub release and install it on the RotorHazard host.
5. Open the RotorHazard settings page and enable **Race Voice**.
6. Confirm **Sendspin service URL** points to the service, normally `http://127.0.0.1:8766`.
7. Open `<RotorHazard UI base URL>/player` from the playback device.
8. Use **Rebuild pre-cache** to prepare race-clock, schedule, pilot-name, and lap-number WAV files.
9. Use **Generate test phrase** or **Play audio check** to verify playback.

Set RotorHazard browser Voice Volume and Tone Volume to `0` on clients that should only use Race Voice audio.

The first generated phrase for a voice model downloads the Piper model into the RotorHazard data cache. That can take a moment depending on the server and network connection.

## Супутні документи в теці

- [`docs/architecture.md`](../../fpv-library/repos/rh-race-voice-Local-server-side-voice-callouts-for-Ro/docs/architecture.md)
- [`docs/pilot-filter-feature.md`](../../fpv-library/repos/rh-race-voice-Local-server-side-voice-callouts-for-Ro/docs/pilot-filter-feature.md)
- [`docs/usage.md`](../../fpv-library/repos/rh-race-voice-Local-server-side-voice-callouts-for-Ro/docs/usage.md)
- [`CONTRIBUTING.md`](../../fpv-library/repos/rh-race-voice-Local-server-side-voice-callouts-for-Ro/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/rh-race-voice-Local-server-side-voice-callouts-for-Ro/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/dutchdronesquad__rh-race-voice.md`.

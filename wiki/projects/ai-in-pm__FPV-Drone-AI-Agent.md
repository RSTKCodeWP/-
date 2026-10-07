# nanohawk-agent

> Картка виставки. Зал: [Польотні контролери і прошивки](../halls/fc.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [ai-in-pm/FPV-Drone-AI-Agent](https://github.com/ai-in-pm/FPV-Drone-AI-Agent) |
| Локальна тека | `fpv-library/repos/FPV-Drone-AI-Agent-AI-powered-autonomous-control-AI-Agent-f` |
| У бібліотеці | keep |
| Категорії каталогу | `fc`, `elrs`, `goggles`, `ai` |
| Зірки (каталог) | 1 |
| Оновлено upstream | 2026-03-08 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

**AI-powered autonomous control agent for the EMAX Nanohawk 1S FPV Drone.**

A modular C++20 desktop application that uses a local LLM to interpret natural-language commands and fly the Nanohawk via the Betaflight MSP serial protocol. No FPV goggles required. Live camera feed streams to your desktop. You type a prompt; the agent executes it on the drone.

EMAX Nanohawk 1S -- https://emax-usa.com/products/nanohawk-1s-ultralight-brushless-fpv-drone

_З README.md, без переказу._

## Для чого

AI-powered autonomous control AI Agent for the EMAX Nanohawk 1S FPV Drone.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Пілот, якому потрібні окуляри, VTX або OSD — у тексті є «goggles».
- Розробник польотного контролера — у тексті є «betaflight».
- Інженер радіолінка — у тексті є «expresslrs».


Теми GitHub: `ai-agent`, `autonomous-drone`, `betaflight`, `drone`, `emax`, `emax-nanohawk`, `expresslrs`, `flight-controller`, `fpv-drone`, `fpv-goggles`, `llama-cpp`, `mavlink`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: AI-powered autonomous control AI Agent for the EMAX Nanohawk 1S FPV Drone.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `BUILD_GUI.bat`
- `BUILD_SUMMARY.md`
- `ci/`
- `CMakeLists.txt`
- `CMakePresets.json`
- `config/`
- `docs/`
- `external/`
- `FPV Drone AI Agent-RAIL.md`
- `img_1.png`
- `include/`
- `models/`
- `QUICKSTART.md`
- `README.md`
- `scripts/`
- `src/`
- `test/`
- `tools/`
- `vcpkg.json`

Типи файлів за вибіркою (133 файлів, глибина до 3): C++ (75), Markdown (10), .bat (10), .exe (6), JSON (5), YAML (5).

Фрагмент README про будову:

### Safety Architecture

| Layer | Role | Failsafe |
|---|---|---|
| **LLM** | Natural-language -> strict JSON | Returns idle JSON if unavailable |
| **JsonPlanParser** | Schema validation | Rejects malformed mission plans |
| **SafetyEngine** | Hard-limit veto | Blocks execution on any breach |
| **AbortController** | Operator emergency stop | Disarms immediately |
| **MspClient.disarm()** | Final hardware failsafe | ch[4]=1000, throttle=1000 |
| **Manual TX** | Physical radio override | Always available; takes precedence |

**Key principle:** The LLM never directly controls motors. It outputs JSON. JSON goes through safety validation. Only validated, operator-authorized commands reach the MSP serial layer.

---

## Що треба

### Prerequisites

- Windows 10+ (Linux/macOS stubs compile but lack Windows serial/WiFi backends)
- CMake 3.26+, C++20 compiler (MinGW-w64 or MSVC)
- Optional for GUI: Qt 6.5+, OpenCV 4.8+, libcurl 7.85+

- Маніфести збірки: CMake.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## Супутні документи в теці

- [`docs/CONFIG_WIRING.md`](../../fpv-library/repos/FPV-Drone-AI-Agent-AI-powered-autonomous-control-AI-Agent-f/docs/CONFIG_WIRING.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/FPV-Drone-AI-Agent-AI-powered-autonomous-control-AI-Agent-f/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/ai-in-pm__FPV-Drone-AI-Agent.md`.

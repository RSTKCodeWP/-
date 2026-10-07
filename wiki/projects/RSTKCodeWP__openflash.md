# 🇬🇧 ENGLISH

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RSTKCodeWP/openflash](https://github.com/RSTKCodeWP/openflash) |
| Локальна тека | `openflash-Rust-NAND-Flash-Programmer` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | — |
| Оновлено upstream | — |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

**[ [English](#-what-is-openflash) · [Русский](#-что-такое-openflash) ]**

_З README.md, без переказу._

## Для чого

**[ [English](#-what-is-openflash) · [Русский](#-что-такое-openflash) ]**

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `CHANGELOG.md`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `LICENSE`
- `openflash/`
- `README.md`
- `ROADMAP.md`
- `SECURITY.md`

Типи файлів за вибіркою (64 файлів, глибина до 3): Rust (20), TOML (17), Markdown (13), JSON (5), (без суфікса) (4), TypeScript (3).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### 🏗️ Build from Source

```bash
# Prerequisites: Rust 1.70+, Node 18+

git clone https://github.com/openflash/openflash.git
cd openflash/openflash

# ┌─────────────────────────────────────────────────────────────┐
# │  GUI (Tauri + React)                                        │
# └─────────────────────────────────────────────────────────────┘
cd gui && npm i && cargo tauri dev

# ┌─────────────────────────────────────────────────────────────┐
# │  CLI                                                        │
# └─────────────────────────────────────────────────────────────┘
cargo build -p openflash-cli --release

# ┌─────────────────────────────────────────────────────────────┐
# │  Firmware (pick your platform)                              │
# └─────────────────────────────────────────────────────────────┘

# RP2040 (Raspberry Pi Pico)
cd firmware/rp2040
rustup target add thumbv6m-none-eabi
cargo build --release --target thumbv6m-none-eabi

# RP2350 (Raspberry Pi Pico 2)
cd firmware/rp2350
rustup target add thumbv8m.main-none-eabihf
cargo build --release --target thumbv8m.main-none-eabihf

# Teensy 4.x (USB High Speed!)
cd firmware/teensy4
rustup target add thumbv7em-none-eabihf
cargo build --release --target thumbv7em-none-eabihf
```

<br>
### 🏗️ Сборка из исходников

```bash
# Требования: Rust 1.70+, Node 18+

git clone https://github.com/openflash/openflash.git
cd openflash/openflash

# ┌─────────────────────────────────────────────────────────────┐
# │  GUI (Tauri + React)                                        │
# └─────────────────────────────────────────────────────────────┘
cd gui && npm i && cargo tauri dev

# ┌─────────────────────────────────────────────────────────────┐
# │  CLI                                                        │
# └─────────────────────────────────────────────────────────────┘
cargo build -p openflash-cli --release

# ┌─────────────────────────────────────────────────────────────┐
# │  Прошивка (выбери свою платформу)                           │
# └─────────────────────────────────────────────────────────────┘

# RP2040 (Raspberry Pi Pico)
cd firmware/rp2040
rustup target add thumbv6m-none-eabi
cargo build --release --target thumbv6m-none-eabi

# RP2350 (Raspberry Pi Pico 2)
cd firmware/rp2350
rustup target add thumbv8m.main-none-eabihf
cargo build --release --target thumbv8m.main-none-eabihf

# Teensy 4.x (USB High Speed!)
cd firmware/teensy4
rustup target add thumbv7em-none-eabihf
cargo build --release --target thumbv7em-none-eabihf
```

<br>

## Супутні документи в теці

- [`CONTRIBUTING.md`](../../openflash-Rust-NAND-Flash-Programmer/CONTRIBUTING.md)

## З чого зібрана картка

`catalog.json`, `openflash-Rust-NAND-Flash-Programmer/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RSTKCodeWP__openflash.md`.

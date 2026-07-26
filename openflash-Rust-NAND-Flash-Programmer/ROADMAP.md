# OpenFlash Roadmap

## Текущий статус: v3.0.0

---

## ✅ Завершённые версии

### v1.x — Foundation
- v1.0: Parallel NAND, 30+ чипов, Hamming/BCH ECC, SquashFS/UBIFS/JFFS2
- v1.1: SPI NAND (20+ чипов, QSPI)
- v1.2: eMMC support
- v1.3: AI-анализ (pattern recognition, anomaly detection)
- v1.4: Filesystem detection, OOB analysis, encryption key search, wear analysis
- v1.5: ESP32 & STM32F4 support
- v1.6: SPI NOR (30+ чипов), UFS, ONFI 5.0
- v1.7: Write operations, bad block management, wear leveling, chip cloning
- v1.8: Python API (pyopenflash), CLI, batch processing, plugins
- v1.9: ML chip identification, firmware unpacking, vulnerability scanning

### v2.x — Scale & Hardware
- v2.0: Multi-device, REST API, device farm, production line integration
- v2.1: OpenFlash PCB, TSOP-48 adapter, logic analyzer, JTAG/SWD
- v2.2: 150+ новых чипов
- v2.3: RP2350, Arduino GIGA, Raspberry Pi SBC, Orange Pi (9 платформ)
- v2.3.5: Teensy 4.x (USB HS 480Mbps!), Banana Pi (11 платформ)

### v3.0 — Cloud & Pro ← ТЕКУЩАЯ
- Cloud sync & backup
- Team collaboration
- Chip database crowdsourcing
- AI model updates OTA
- Enterprise support (Free/Pro/Enterprise tiers)

---

## 🚀 Будущие версии

### v3.1 — FPGA & High-Speed
**Цель:** Максимальная скорость и точность timing

| Фича | Описание |
|------|----------|
| FPGA programmer | Lattice iCE40/ECP5 для NV-DDR3/4 timing, 100+ MB/s |
| Tang Nano support | Sipeed Tang Nano 9K/20K — дешёвые FPGA ($15-30) |
| USB 3.0 bridge | FT601/FX3 для 300+ MB/s transfers |
| Parallel read optimization | Чтение нескольких страниц одновременно |
| DMA transfers | Zero-copy на всех платформах |

---

### v3.2 — Extended Flash Support
**Цель:** Поддержка всех типов flash памяти

| Фича | Описание |
|------|----------|
| OneNAND | Samsung KFM/KFN series (legacy devices) |
| HyperFlash | Cypress/Infineon S26KS/S26HL (automotive) |
| OctalSPI | Macronix MX25/MX66 OctaFlash |
| 3D NAND optimizations | Samsung V-NAND, Micron 3D TLC/QLC specific |
| QLC NAND | 4-bit per cell support с расширенным ECC |
| RPMB access | eMMC Replay Protected Memory Block |
| SD/microSD raw | Прямой доступ к raw NAND внутри SD карт |

---

### v3.3 — Forensics & Security
**Цель:** Профессиональные инструменты для forensics

| Фича | Описание |
|------|----------|
| Write-blocker mode | Hardware write protection, гарантированный read-only |
| Chain of custody | Криптографическое подтверждение целостности |
| Court-ready reports | PDF отчёты с hash verification для суда |
| Audit logging | Полный лог операций с timestamps и signatures |
| Encrypted storage | AES-256 шифрование дампов at rest |
| Data carving | Восстановление удалённых файлов из raw dumps |
| Timeline reconstruction | Временная шкала изменений на основе FS metadata |

---

### v3.4 — AI & Analysis v2
**Цель:** Продвинутый AI-анализ

| Фича | Описание |
|------|----------|
| Firmware similarity | Fuzzy hashing (TLSH/ssdeep) для поиска похожих прошивок |
| Backdoor detection | ML-детекция известных backdoor паттернов |
| Crypto key extraction | Автоматический поиск RSA/EC ключей, сертификатов |
| Bootloader analysis | U-Boot, Barebox, custom bootloader parsing |
| Device tree extraction | Автоматический парсинг DTB/FDT |
| Symbol recovery | Восстановление символов из stripped binaries |
| Diff analysis v2 | Semantic diff между версиями firmware |

---

### v3.5 — Developer Tools
**Цель:** Интеграция в workflow разработчиков

| Фича | Описание |
|------|----------|
| VS Code extension | Hex view, analysis, flash operations из IDE |
| GitHub Actions | CI/CD action для firmware verification |
| GitLab CI template | Готовый pipeline для embedded проектов |
| Rust crate (crates.io) | openflash-core как библиотека |
| C/C++ bindings | FFI для embedded toolchains |
| GDB integration | Чтение flash через GDB remote protocol |
| OpenOCD plugin | Интеграция с OpenOCD для debug + flash |

---

### v3.6 — RISC-V & New Platforms
**Цель:** Поддержка RISC-V и новых MCU

| Фича | Описание |
|------|----------|
| ESP32-C3/C6 | RISC-V варианты ESP32 |
| CH32V series | WCH CH32V103/203/303 — дешёвые RISC-V ($0.50-2) |
| GD32VF103 | GigaDevice RISC-V (совместим с STM32F103) |
| BL602/BL616 | Bouffalo Lab WiFi+BLE RISC-V |
| Milk-V Duo | RISC-V SBC ($9) |
| LicheePi 4A | TH1520 RISC-V SBC |
| BeagleV | StarFive RISC-V |

---

### v3.7 — Enterprise Scale
**Цель:** Масштабирование для production

| Фича | Описание |
|------|----------|
| Kubernetes operator | Auto-scaling device farm в k8s |
| Prometheus metrics | Мониторинг производительности |
| Grafana dashboards | Визуализация статистики |
| LDAP/SAML auth | Enterprise SSO |
| Multi-region cloud | Geo-distributed infrastructure |
| On-premise deploy | Self-hosted OpenFlash Cloud |
| Compliance (SOC2) | Сертификация для enterprise |

---

### v4.0 — Next Generation
**Цель:** Архитектурные улучшения

| Фича | Описание |
|------|----------|
| WebAssembly core | Анализ дампов в браузере без установки |
| Distributed dumping | Параллельное чтение одного чипа несколькими устройствами |
| Real-time collab | Совместный анализ как Google Docs |
| Plugin sandbox | WASM-изолированные плагины |
| Custom protocols | DSL для описания новых flash протоколов |
| Hardware abstraction | Унифицированный HAL для всех платформ |

---

## 🔧 Технический долг

| Область | Задачи |
|---------|--------|
| Performance | SIMD для ECC, async I/O везде, memory-mapped files |
| Testing | 90%+ coverage, hardware-in-the-loop tests, fuzzing |
| Documentation | API reference, video tutorials, cookbook |
| Code quality | Clippy pedantic, безопасный unsafe, no panics |

---

## 📊 Chip Database Goals

| Тип | Текущее | Цель v4.0 |
|-----|---------|-----------|
| Parallel NAND | 60+ | 150+ |
| SPI NAND | 55+ | 120+ |
| SPI NOR | 75+ | 200+ |
| eMMC | 40+ | 80+ |
| UFS | 10+ | 30+ |
| OneNAND | 0 | 20+ |
| HyperFlash | 0 | 15+ |

---

## 🎯 Приоритеты

1. **Скорость** — FPGA и USB 3.0 для 100+ MB/s
2. **Покрытие чипов** — максимум поддерживаемых устройств
3. **Forensics** — профессиональные инструменты
4. **AI** — умный анализ без ручной работы
5. **Интеграции** — встраивание в существующие workflow

---

*Последнее обновление: Январь 2026*

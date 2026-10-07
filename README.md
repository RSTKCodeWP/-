# RSTKCodeWP — FPV & drone open-source library

Монорепозиторій з **каталогом**, **дзеркалами** та **legacy-копіями** FPV/drone проєктів з GitHub.

## Швидка навігація

| Документ | Зміст |
|----------|--------|
| **[wiki/Home.md](wiki/Home.md)** | Виставкова вікі: ідея, для чого, для кого, функція, як, що треба, інструкція |
| **[MAP.md](MAP.md)** | Карта всіх тек монорепо — дерево, org-бібліотеки, статус mirror |
| **[REPOS.md](REPOS.md)** | Повний список усіх проєктів: опис · тека · дата · розмір |
| **[docs/STRUCTURE.md](docs/STRUCTURE.md)** | Структура тек і правила іменування |
| **[fpv-library/](fpv-library/)** | Автокаталог (discover → triage → sync) |
| **[fpv-library/THEMED.md](fpv-library/THEMED.md)** | Тематичні добірки (GCS, WFB, OpenIPC, Caddx…) |
| **[fpv-library/docs/ASCENT.md](fpv-library/docs/ASCENT.md)** | Walksnail / Caddx Ascent — прошивки та RE |
| **[fpv-library/HOOKS.md](fpv-library/HOOKS.md)** | Цікаві / watch репо |

## Структура (коротко)

```
/
├── MAP.md                   # автоген: карта тек + org-бібліотеки
├── REPOS.md                 # автоген: кожен репо + опис + розмір + дата
├── docs/STRUCTURE.md        # що означає кожна тека
├── fpv-library/
│   ├── catalog.json         # маніфест 520+ проєктів
│   ├── repos/               # дзеркала GitHub (auto-sync)
│   ├── scripts/             # discover, sync, triage, Caddx tools
│   ├── manifests/           # SHA256 релізів (firmware, ground config)
│   ├── docs/ASCENT.md       # Ascent firmware + RE index
│   ├── ground-config/       # завантажені Caddx Ground Configuration
│   ├── funnel-queries.txt   # широкий funnel discovery
│   ├── THEMED.md            # кураторський індекс
│   └── HOOKS.md             # hooks / watch list
├── Steer-iOS-RC-Car-FPV/    # legacy: ручні копії з описовою назвою теки
├── SkySweep32-ESP32-Drone-Detector/
└── …
```

**Іменування legacy-тек:** `RepoName-Короткий-Опис` (напр. `wfb-ng-WiFi-FPV-Long-Range-Radio-Link`).

**Іменування sync-тек:** `fpv-library/repos/{repo}-{опис-з-GitHub}/`.

## Команди

```bash
# Оновити повний індекс REPOS.md (опис, дати, розміри)
python3 fpv-library/scripts/generate_repo_index.py

# Пошук + sync
python3 fpv-library/scripts/discover_keywords.py --pages 1 --expand-owners
python3 fpv-library/scripts/sync.py --all --verdict keep --update-only

# Caddx релізи
python3 fpv-library/scripts/sync_caddx_ground_config.py --download
python3 fpv-library/scripts/download_caddx_firmware.py
```

## CI

[`.github/workflows/fpv-library-sync.yml`](.github/workflows/fpv-library-sync.yml) — щодня: discover → triage → sync → оновлення `REPOS.md` → commit.

## Legacy-групи (ручні копії в корені)

Деталі в [REPOS.md § Legacy](REPOS.md#legacy-копії-в-корені).

| Група | Приклади |
|-------|----------|
| FPVibe | `fpv-inventory-…`, `fpv-tools-…`, `flowchart-…` |
| bobberdolle1 (FPV) | `SkySweep32-…`, `GyroChad-…`, `openflash-…` |
| paulnurkkala | Betaflight Claude plugins, `hackrf-vtx-elrs-monitor-…` |
| Приклади | `Steer-iOS-RC-Car-FPV`, `wfb-ng-WiFi-FPV-Long-Range-Radio-Link` |

## Статистика

Див. заголовок [REPOS.md](REPOS.md) — кількість проєктів, сумарний розмір, дата оновлення каталогу.

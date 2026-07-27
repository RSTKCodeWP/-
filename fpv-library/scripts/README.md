# scripts — інструменти FPV Library

| Скрипт | Про що |
|--------|--------|
| `discover.py` | GitHub search + owner expansion |
| `discover_keywords.py` | Ротаційний пошук з `keywords.txt` |
| `discover_themes.py` | Тематичні запити (GCS, fiber, WFB…) |
| `triage_catalog.py` | keep / watch / skip → `HOOKS.md` |
| `sync.py` | Оновлення дзеркал з upstream |
| `generate_repo_index.py` | Генерація `REPOS.md` у корені |
| `sync_caddx_ground_config.py` | Caddx Ground Configuration: маніфест + download |
| `download_caddx_firmware.py` | Ascent firmware `.img` |
| `download_caddx_ground_config.py` | Один asset Ground Config |
| `register_legacy.py` | Реєстрація legacy-тек у `catalog.json` |

Модулі: `fpv_lib/` (catalog, gh, scoring, triage, blocklist).

# FPV Library — структура тек

Автоматичне дзеркало та каталог FPV/drone open-source з GitHub.

## Теки та файли

| Шлях | Про що |
|------|--------|
| [`catalog.json`](catalog.json) | Головний маніфест: `source`, `path`, `description`, `verdict`, дати sync |
| [`repos/`](repos/) | **Дзеркала** — git-копії upstream-репо (назва = repo + короткий опис) |
| [`scripts/`](scripts/) | CLI: discover, sync, triage, Caddx download, `generate_repo_index.py` |
| [`scripts/fpv_lib/`](scripts/fpv_lib/) | Спільні модулі: catalog, GitHub API, scoring, triage |
| [`manifests/`](manifests/) | JSON-маніфести релізів з SHA256 (firmware `.img`, Ground Configuration) |
| [`ground-config/`](ground-config/) | Завантажені Windows-бінарники Caddx Ground Configuration (не в git) |
| [`keywords.txt`](keywords.txt) | Пошукові ключові слова (ротація в CI) |
| [`blocklist.txt`](blocklist.txt) | Blocklist — не додавати в каталог |
| [`priority-sync.txt`](priority-sync.txt) | Завжди синхронізувати ці `owner/repo` |
| [`THEMED.md`](THEMED.md) | Кураторський індекс за темами |
| [`HOOKS.md`](HOOKS.md) | Цікаві репо та `watch` (генерується triage) |

## Скрипти

| Скрипт | Призначення |
|--------|-------------|
| `discover.py` | Пошук на GitHub + розширення по owner |
| `discover_keywords.py` | Ротаційний batch з `keywords.txt` |
| `discover_themes.py` | Тематичні запити (GCS, fiber, WFB…) |
| `triage_catalog.py` | keep / watch / skip → `HOOKS.md` |
| `sync.py` | `git pull` upstream для каталогу |
| `sync_caddx_ground_config.py` | Маніфест + завантаження Caddx Ground Configuration |
| `download_caddx_firmware.py` | Завантаження Ascent `.img` |
| `download_caddx_ground_config.py` | Завантаження одного asset Ground Config |
| `generate_repo_index.py` | Генерація [`../REPOS.md`](../REPOS.md) |
| `register_legacy.py` | Реєстрація legacy-тек у корені репо |

## Вердикти triage

| Verdict | Що робить sync |
|---------|----------------|
| `keep` | Синхронізується |
| `watch` | Лише в `HOOKS.md` |
| `skip` | Ігнорується |

## Повний список проєктів

→ **[REPOS.md](../REPOS.md)** — кожен репо: GitHub, опис, тека, дата оновлення, розмір.

→ **[THEMED.md](THEMED.md)** — найважливіше за категоріями.

Див. також [`../docs/STRUCTURE.md`](../docs/STRUCTURE.md).

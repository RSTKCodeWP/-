# Повне дзеркало FPV/drone репозиторіїв

Кожен корисний GitHub-проєкт → **повна git-копія** (submodule) → **щоденне автооновлення**.

```bash
git clone --recurse-submodules https://github.com/RSTKCodeWP/-.git
```

## Як це працює

```
discover (keywords/themes/funnel/org)
    → catalog.json (verdict: keep | watch | skip)
    → sync_daily.py (щодня о 06:00 UTC)
         ├─ Phase 1: git fetch + reset для існуючих mirrors
         ├─ Phase 2: повний git clone для нових keep (до N за запуск)
         └─ Phase 3: priority-sync.txt (завжди)
    → REPOS.md (індекс)
```

| Verdict | Що робить mirror |
|---------|------------------|
| **keep** | Повний git clone, щодня оновлюється |
| **watch** | Лише в каталозі + HOOKS.md, **не** клонується |
| **skip** | Ігнорується |

## Структура тек

| Шлях | Приклад |
|------|---------|
| `OpenIPC/<repo>/` | Уся організація OpenIPC (повні git-копії) |
| `fpv-library/repos/<slug>/` | Інші знайдені репо |
| `.fpv-library.json` | Метадані mirror (`mirror_mode: full-git`) |

## Команди

```bash
# Зареєструвати всі репо GitHub org
python3 fpv-library/scripts/discover_org.py --org OpenIPC --verdict keep

# Щоденний цикл (як у CI)
python3 fpv-library/scripts/sync_daily.py

# Тільки оновити існуючі
python3 fpv-library/scripts/sync.py --all --verdict keep --update-only

# Додати нові keep (25 найкорисніших за score)
python3 fpv-library/scripts/sync.py --all --verdict keep --new-only --max-per-run 25

# Один репо
python3 fpv-library/scripts/sync.py --source OpenIPC/firmware

# Міграція старих snapshot (без .git) → повний clone
python3 fpv-library/scripts/sync.py --source OpenIPC/msposd --force-reclone
```

## Повнота mirror

- **Git submodule** — повна копія з `.git`, історією, LFS, submodules
- **Клон монорепо** — `git clone --recurse-submodules`
- **Git LFS** — `git lfs pull` після clone/update
- **Submodules** — `git submodule update --init --recursive`
- Старі shallow snapshots (без `.git`) автоматично переклоновуються

## Backfill

Зараз у каталозі **~1537 keep**, склоновано **~200**.  
CI додає **~25 нових на день** — поступово, **без пропуску за розміром**.

## Розширений пошук

`discover_expand.py` — щодня з нашої бази:
- org вгору (усі репо організації)
- усі репо авторів з каталогу
- similarity search за topics/тематикою

## Перевірка після sync

Кожен mirror: HEAD == upstream, diff порожній, submodules OK.

## CI

`.github/workflows/fpv-library-sync.yml` — cron `0 6 * * *` (щодня).

Детальна політика: [`docs/MIRROR_POLICY.md`](../docs/MIRROR_POLICY.md)

# Повне дзеркало FPV/drone репозиторіїв

Кожен корисний GitHub-проєкт → **тека в цьому монорепо** → **щоденне автооновлення**.

## Як це працює

```
discover (keywords/themes/funnel)
    → catalog.json (verdict: keep | watch | skip)
    → sync_daily.py (щодня о 06:00 UTC)
         ├─ Phase 1: оновити всі вже склоновані (upstream SHA змінився → переклонувати)
         ├─ Phase 2: додати нові keep (до N за запуск)
         └─ Phase 3: priority-sync.txt (завжди)
    → REPOS.md (індекс)
```

| Verdict | Що робить mirror |
|---------|------------------|
| **keep** | Клонується в репо, щодня оновлюється |
| **watch** | Лише в каталозі + HOOKS.md, **не** клонується |
| **skip** | Ігнорується |

## Структура тек

| Шлях | Приклад |
|------|---------|
| `fpv-library/repos/<slug>/` | Більшість знайдених репо |
| `<RepoName-Опис>/` | Legacy / власні копії в корені |
| `.fpv-library.json` | Метадані mirror у кожній теці |

## Команди

```bash
# Щоденний цикл (як у CI)
python3 fpv-library/scripts/sync_daily.py

# Тільки оновити існуючі
python3 fpv-library/scripts/sync.py --all --verdict keep --update-only

# Додати нові keep (25 найкорисніших за score)
python3 fpv-library/scripts/sync.py --all --verdict keep --new-only --max-per-run 25

# Один репо
python3 fpv-library/scripts/sync.py --source ArduPilot/ardupilot

# Зареєструвати теки з кореня монорепо
python3 fpv-library/scripts/register_legacy.py
```

## Backfill

Зараз у каталозі **~1537 keep**, склоновано **~200**.  
CI додає **~25 нових на день** (налаштовується) — повний backfill за ~55 днів без перевантаження.

Великі репо (>800 MB) пропускаються при backfill — див. `--max-size-mb`.  
Їх можна додати вручну: `sync.py --source owner/repo`.

## CI

`.github/workflows/fpv-library-sync.yml` — cron `0 6 * * *` (щодня).

Workflow dispatch: параметр `backfill_per_run` для прискорення.

## Повнота mirror

- Клонується **повне дерево файлів** default branch (shallow clone, без історії git — економія місця)
- `.git` не зберігається — лише snapshot + `.fpv-library.json`
- GitHub Releases assets — окремо (Caddx manifests); загальний release mirror — planned

Детальна політика: [`docs/MIRROR_POLICY.md`](../docs/MIRROR_POLICY.md)

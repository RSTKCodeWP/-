# Політика дзеркалування / Mirror policy

## Мета

**Кожен корисний проєкт = повна git-копія upstream у монорепо RSTKCodeWP/-, з щоденним оновленням.**

Це **справжнє дзеркало репозиторію**: повний `git clone`, історія, гілки, теги, LFS, submodules.

У монорепо org-дзеркала (напр. `OpenIPC/*`) зберігаються як **git submodules** — при клонуванні:
```bash
git clone --recurse-submodules https://github.com/RSTKCodeWP/-.git
```

## Шари

| Шар | Механізм | Автооновлення |
|-----|----------|---------------|
| GitHub FPV/drone | `fpv-library/` + `sync.py` | ✅ щодня CI |
| GitHub org (напр. OpenIPC) | `discover_org.py` → `OpenIPC/<repo>/` | ✅ щодня CI |
| Кореневі теки | `register_legacy.py` | ✅ якщо в catalog keep |
| Власні продукти (AeroStab) | окрема гілка/тека | git push (не mirror) |
| Зовнішні (Drive, SD) | `vendor/` + LFS | ручний + скрипти |

## Життєвий цикл репо

1. **Discover** — `discover_*.py`, `discover_org.py` знаходить на GitHub
2. **Triage** — `triage_catalog.py` → `keep` / `watch` / `skip`
3. **Mirror** — `sync_daily.py` клонує/оновлює `keep` (повний git)
4. **Index** — `generate_repo_index.py` → `REPOS.md`

## Правила mirror

- **keep** → обов'язково на диску (backfill + daily update)
- **watch** → тільки метадані в каталозі
- **skip** / **blocklist** → не чіпати
- **priority-sync.txt** → синхронізується кожен день

## Структура тек

| Шлях | Приклад |
|------|---------|
| `OpenIPC/<repo>/` | Усі репо організації OpenIPC |
| `fpv-library/repos/<slug>/` | Інші знайдені репо (legacy layout) |
| `.fpv-library.json` | Метадані mirror (upstream SHA, дата sync) |

## Щоденний CI (06:00 UTC)

```
discover → discover_org(OpenIPC) → triage → sync_daily → REPOS.md → commit → push
```

`sync_daily.py`:
1. Оновити всі існуючі mirrors (`git fetch` + `reset --hard`)
2. Додати до 25 нових `keep` (`--new-only`)
3. Priority list

## Повнота mirror

| Що | Як |
|----|-----|
| Git history | `git submodule add` / повний `git clone` |
| `.git` | **зберігається** (submodule) |
| Клон монорепо | `git clone --recurse-submodules` |
| Оновлення | `git fetch --all --tags --prune` + `reset --hard origin/<branch>` |
| Git LFS | `git lfs pull` після clone/update |
| Submodules | `git submodule update --init --recursive` |
| Legacy snapshots | Авто-переклонування (було без `.git`) |

## Розмір і ліміти

| Параметр | Значення | Чому |
|----------|----------|------|
| `backfill_per_run` | 25 | Не перевантажити CI |
| `max_size_mb` | 800 | Пропустити гігантів при backfill |
| full git | так | Повна бібліотека, не shallow snapshot |

Гіганти (>800 MB): клонувати вручну або окремим job з LFS.

## OpenIPC — приклад org-бібліотеки

```bash
# Зареєструвати всі репо org як keep, шлях OpenIPC/<name>/
python3 fpv-library/scripts/discover_org.py --org OpenIPC --verdict keep

# Синхронізувати один репо
python3 fpv-library/scripts/sync.py --source OpenIPC/firmware

# Усі OpenIPC keep
python3 fpv-library/scripts/sync.py --all --verdict keep --source OpenIPC/firmware  # або цикл
```

## Реєстрація кореневих тек

```bash
python3 fpv-library/scripts/register_legacy.py
```

## Що не mirror-иться автоматично

- Приватні репо (потрібен PAT)
- Закриті бінарники (StabX ua-pilot.enc)
- GitHub Releases assets (окрім Caddx manifests)
- `watch` / `skip` verdict

## Моніторинг

- `REPOS.md` — скільки на диску, розміри, дати
- `catalog.json` → поля `synced_at`, `upstream_commit`
- `.fpv-library.json` у кожній теці (`mirror_mode: full-git`)

# Політика дзеркалування / Mirror policy

## Мета

**Кожен корисний проєкт = тека в монорепо RSTKCodeWP/-, яка щодня синхронізується з upstream.**

Що є в чужому GitHub `owner/repo` — те ж має бути у нас у відповідній теці (повний snapshot default branch).

## Шари

| Шар | Механізм | Автооновлення |
|-----|----------|---------------|
| GitHub FPV/drone | `fpv-library/` + `sync.py` | ✅ щодня CI |
| Кореневі теки | `register_legacy.py` | ✅ якщо в catalog keep |
| Власні продукти (AeroStab) | окрема гілка/тека | git push (не mirror) |
| Зовнішні (Drive, SD) | `vendor/` + LFS | ручний + скрипти |

## Життєвий цикл репо

1. **Discover** — `discover_*.py` знаходить на GitHub
2. **Triage** — `triage_catalog.py` → `keep` / `watch` / `skip`
3. **Mirror** — `sync_daily.py` клонує/оновлює `keep`
4. **Index** — `generate_repo_index.py` → `REPOS.md`

## Правила mirror

- **keep** → обов'язково на диску (backfill + daily update)
- **watch** → тільки метадані в каталозі
- **skip** / **blocklist** → не чіпати
- **priority-sync.txt** → синхронізується кожен день навіть якщо вже up-to-date queue

## Щоденний CI (06:00 UTC)

```
discover → triage → sync_daily → REPOS.md → commit → push
```

`sync_daily.py`:
1. Оновити всі існуючі mirrors (`--update-only`)
2. Додати до 25 нових `keep` (`--new-only --max-per-run 25`)
3. Priority list

## Розмір і ліміти

| Параметр | Значення | Чому |
|----------|----------|------|
| `backfill_per_run` | 25 | Не перевантажити CI |
| `max_size_mb` | 800 | Пропустити гігантів (ardupilot_wiki, binary) |
| shallow clone | depth=1 | Повні файли, без git history |

Гіганти (>800 MB): клонувати вручну або окремим job з LFS.

## Реєстрація кореневих тек

```bash
python3 fpv-library/scripts/register_legacy.py
```

Сканує `/workspace/*/` — шукає `git remote`, `.fpv-library.json`, або `MANUAL` map.

## Що не mirror-иться автоматично

- Приватні репо (потрібен PAT)
- Закриті бінарники (StabX ua-pilot.enc)
- GitHub Releases assets (окрім Caddx manifests)
- `watch` / `skip` verdict

## Моніторинг

- `REPOS.md` — скільки на диску, розміри, дати
- `catalog.json` → поля `synced_at`, `upstream_commit`
- `.fpv-library.json` у кожній теці

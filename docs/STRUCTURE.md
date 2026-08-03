# Структура репозиторію / Repository layout

Короткий опис кожної теки в монорепозиторії **RSTKCodeWP**.

## Корінь (`/`)

| Тека | Про що |
|------|--------|
| [`fpv-library/`](fpv-library/) | Автоматичний каталог і **повне дзеркало** FPV/drone GitHub-репо (discover → triage → daily sync) |
| [`docs/`](docs/) | Документація структури та специфікації |
| [`.github/workflows/`](.github/workflows/) | CI: щоденний **mirror sync** бібліотеки, перевірка релізів Caddx |
| [`REPOS.md`](../REPOS.md) | **Повний список** усіх проєктів: опис, шлях, дата, розмір (автогенерація) |
| [`docs/MIRROR_POLICY.md`](../docs/MIRROR_POLICY.md) | Політика: кожен keep = тека + щоденне автооновлення |
| [`README.md`](../README.md) | Головна навігація |

### Legacy-копії (корінь)

Ручні копії з **описовою назвою теки**: `RepoName-Короткий-Опис-Технологія`.

Приклади:

| Шаблон назви | Значення |
|--------------|----------|
| `Steer-iOS-RC-Car-FPV` | репо + платформа + призначення |
| `SkySweep32-ESP32-Drone-Detector` | репо + чіп + функція |
| `wfb-ng-WiFi-FPV-Long-Range-Radio-Link` | репо + протокол + роль |

Повний перелік: [REPOS.md § Legacy](../REPOS.md#legacy-копії-в-корені).

## FPV Library (`fpv-library/`)

Детальніше: [`fpv-library/STRUCTURE.md`](../fpv-library/STRUCTURE.md).

| Тека / файл | Про що |
|-------------|--------|
| `catalog.json` | Маніфест усіх відстежуваних GitHub-репо (шлях, verdict, опис, дати) |
| `repos/` | Дзеркала з GitHub — назва `owner-repo-короткий-опис` |
| `scripts/` | discover, sync, triage, завантаження Caddx, генерація `REPOS.md` |
| `manifests/` | SHA256-маніфести офіційних релізів (firmware, Ground Configuration) |
| `ground-config/` | Локальні завантаження **Caddx Ground Configuration** (бінарники в .gitignore) |
| `keywords.txt` | Ключові слова для ротаційного пошуку на GitHub |
| `funnel-queries.txt` | Широкі funnel-запити для discover |
| `blocklist.txt` | Репо, які ніколи не додавати (боти, шум) |
| `priority-sync.txt` | Пріоритетний список для щоденного sync |
| `THEMED.md` | Тематичний індекс (GCS, WFB, OpenIPC, Caddx, fiber…) |
| `docs/ASCENT.md` | Ascent firmware + RE index |
| `HOOKS.md` | Автогенерований список цікавих / `watch` репо |

## Іменування тек у `fpv-library/repos/`

Формат (автоматично при discover):

```
{repo-name}-{перші-слова-опису-з-GitHub}
```

Приклад: `Caddx_vrx_udp_protocol-he-Ascent-VRX-UART-protocol-is-a-binary`

Повний каталог з описом і розміром: **[REPOS.md](../REPOS.md)**.

## Оновлення документації

```bash
# Після sync або змін у catalog.json
python3 fpv-library/scripts/generate_repo_index.py
```

CI запускає це щодня після sync.

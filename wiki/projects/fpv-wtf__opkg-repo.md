# FPV.WTF OPKG Repository

> Картка виставки. Зал: [Окуляри і VRX](../halls/goggles.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [fpv-wtf/opkg-repo](https://github.com/fpv-wtf/opkg-repo) |
| Локальна тека | `fpv-library/repos/opkg-repo-Official-wtfos-OPKG-repository` |
| У бібліотеці | keep |
| Категорії каталогу | `goggles` |
| Зірки (каталог) | 22 |
| Оновлено upstream | 2025-04-12 |
| Ліцензія (з файлу LICENSE або згадки) | GPL-3.0 |

## Ідея

> Custom OPKG repository for the FPV.WTF project.

This is the official reposiotry from which the [WTFOS configurator](https://github.com/fpv-wtf/wtfos-configurator) pulls its packages.

_З README.md, без переказу._

## Для чого

Official wtfos OPKG repository.

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

Теми GitHub: `dji`, `fpv-wtf`, `opkg`, `repository`, `wtfos`.

## Функція

Окремого списку функцій у README немає.

Єдине формулювання функції, яке є в каталозі: Official wtfos OPKG repository.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `entware-armv7sf-k3.2/`
- `entware-packages.txt`
- `fetch-and-validate.py`
- `index.html`
- `LICENSE`
- `Makefile`
- `package-list.html`
- `Pipfile`
- `Pipfile.lock`
- `README.md`
- `repositories.json`
- `src/`

Типи файлів за вибіркою (51 файлів, глибина до 3): .ipk (34), (без суфікса) (5), Python (3), HTML (2), JSON (2), .lock (1).

Фрагмент README про будову:

### Available architectures

To limit the systems on which your package can be installed, add one of the architectures (from general to specific):

* `pigeon-all`
* `pigeon-glasses` (v1 & v2)
* `pigeon-glasses-v1` or `pigeon-glasses-v2`
* `pigeon-airside` (OG and Lite)
* `pigeon-airside-au` or `pigeon-airside-lite`

## Що треба

- Маніфести збірки: Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Usage

Add the following entry to your `opkg.conf`:

```
src/gz fpv.wtf http://repo.fpv.wtf/pigeon
```

Update `opkg` and list packages from repository:

```
opkg update
```

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/opkg-repo-Official-wtfos-OPKG-repository/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/fpv-wtf__opkg-repo.md`.

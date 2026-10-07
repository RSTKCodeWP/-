# Easy manage and update your [RotorHazard](https://github.com/RotorHazard/RotorHazard) installation.

> Картка виставки. Зал: [Інше](../halls/other.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [RotorHazard/RH_Install-Manager](https://github.com/RotorHazard/RH_Install-Manager) |
| Локальна тека | `fpv-library/repos/RH_Install-Manager-All-you-need-to-easily-manage-your-Rotor` |
| У бібліотеці | keep |
| Категорії каталогу | `other` |
| Зірки (каталог) | 7 |
| Оновлено upstream | 2026-03-16 |
| Ліцензія (з файлу LICENSE або згадки) | — |

## Ідея

> [!TIP] > Flash Raspberry Pi OS to your SD card, then start installing RotorHazard with one command: <br /> > `curl -sSL https://raw.githubusercontent.com/RotorHazard/Install-Manager/stable/scripts/auto_download.sh | bash`

> Support development of the Install Manager on [PayPal](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=ULZYQPB38C8UQ&source=url) or: > >[![Support me on Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/szafranski39306)

_З README.md, без переказу._

## Для чого

All you need to easily manage your RotorHazard timing software installation

_Опис із каталогу бібліотеки (те, що було на GitHub на момент запису)._

## Для кого

Маркери в описі, темах і вступі (не здогадка понад текст):

- Майстерня обладнання — у тексті є «pcb».


Теми GitHub: `drone`, `installer`, `manager`, `rotor`, `timer`, `timing`, `updater`.

## Функція

Список із розділу features / можливості в README:

- Choose which version of RotorHazard to install
- Preserves existing RotorHazard config file
- Backup of existing RotorHazard install
- Automatically detects used Pi model and performs system setup accordingly
- Works with official
- Possible to use with older PCBs or with custom-builds - described [here](how_to/hw_mod_instructions.txt)
- Hotspot: Configure always-on hotspot using Pi's built-in Wi-Fi and Ethernet port
- You lose the ability to connect to the internet using built in Wi-Fi
- [Auto-Hotspot:](./docs/AUTO_HOTSPOT.md) Automatically connect to known Wi-Fi if available, or become hotspot if no
- If your Pi has been configured to connect to Wi-Fi, this option allows you to use that Wi-Fi when in range,
- full

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `compatibility_check.py`
- `conf_wizard_rh.py`
- `conf_wizard_rhim.py`
- `distr-updater-config.json`
- `docs/`
- `firmware/`
- `how_to/`
- `modules.py`
- `net_ap/`
- `net_hotspot_auto_11.py`
- `net_hotspot_auto_12.py`
- `net_hotspot_manual_11.py`
- `net_hotspot_manual_12.py`
- `net_hotspot_menu.py`
- `nodes_flash.py`
- `nodes_flash_common.py`
- `nodes_update_old.py`
- `NuclearHazard/`
- `README.md`
- `resources/`
- `rhim.sh`
- `rpi_update.py`
- `scripts/`
- `self_update.py`

Типи файлів за вибіркою (117 файлів, глибина до 3): shell (27), .txt (20), .hex (20), Python (18), Markdown (7), .png (6).


## Що треба

У джерелах цього репозиторію цього немає.

## Інструкція

Окремого розділу Install, Usage, Build або «Інструкція» в README немає. Команди запуску сюди не додавались.

## Супутні документи в теці

- [`docs/AUTO_HOTSPOT.md`](../../fpv-library/repos/RH_Install-Manager-All-you-need-to-easily-manage-your-Rotor/docs/AUTO_HOTSPOT.md)
- [`docs/FAQ.md`](../../fpv-library/repos/RH_Install-Manager-All-you-need-to-easily-manage-your-Rotor/docs/FAQ.md)
- [`docs/features.md`](../../fpv-library/repos/RH_Install-Manager-All-you-need-to-easily-manage-your-Rotor/docs/features.md)

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/RH_Install-Manager-All-you-need-to-easily-manage-your-Rotor/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/RotorHazard__RH_Install-Manager.md`.

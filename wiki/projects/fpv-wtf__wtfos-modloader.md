# modloader for wtfos

> Картка виставки. Зал: [Окуляри і VRX](../halls/goggles.md).

## Паспорт

| Поле | Значення |
|------|----------|
| Джерело | [fpv-wtf/wtfos-modloader](https://github.com/fpv-wtf/wtfos-modloader) |
| Локальна тека | `fpv-library/repos/wtfos-modloader` |
| У бібліотеці | keep |
| Категорії каталогу | `goggles` |
| Зірки (каталог) | 8 |
| Оновлено upstream | 2024-12-02 |
| Ліцензія (з файлу LICENSE або згадки) | MIT |

## Ідея

modloader, along with it's companion `modmanager`, allow you to enable and disable of loading of shared libraries from /opt/etc/preload.d/ into the DJI glasses process.

_З README.md, без переказу._

## Для чого

modloader, along with it's companion `modmanager`, allow you to enable and disable of loading of shared libraries from /opt/etc/preload.d/ into the DJI glasses process.

_Окремого опису в каталозі немає. Це перший абзац README._

## Для кого

Аудиторія прямо не названа, і в описі немає маркерів (GCS, OSD, ELRS, прошивка, OpenIPC, KiCad).

## Функція

Окремого списку функцій у README немає.

## Як влаштовано

Корінь теки (без прихованих і без `node_modules` / `.git`):

- `ipk/`
- `LICENSE`
- `Makefile`
- `menu_hook/`
- `modloader`
- `modloader-o3/`
- `modloader_final/`
- `modmanager`
- `README.md`
- `tweak-enable-debug-menu/`

Типи файлів за вибіркою (45 файлів, глибина до 3): (без суфікса) (27), .mk (6), C (6), Markdown (1), JSON (1), .xml (1).

Фрагмент README про будову:

### How this works

DJI's services (i.e. when you start something with `setprop dji.something_service 1`) are managed by Android init, which only reads it's config files once during bootup from the / ramfs before we ever have a chance to modify them.

Thus, to inject shared libraries into the various services, we move the service binaries out of place (in the loopmount /system image) and replace them with symlinks to modloader.

When init executes the symlink, modloader determines the executed binaries name, inspects the folder /opt/etc/preload.d/${service_binary_name}/ for symlinks to files to load and populates **LD_PRELOAD** according to .so-s found in an alphabetic order. It then proceeds to call the original service binary by appending "_original" to the name determined earlier.

When mods are found for a binary, a final entry to LD_PRELOAD is appended for libmodloader_final.so, which gets loaded last after any other libraries, and clears the processes LD_PRELOAD environment variable. This is done to ensure any modifications don't get loaded needlessly into DJI's excessive shell spawns.

## Що треба

- Маніфести збірки: Make.

## Інструкція

Нижче скопійовані розділи README про встановлення, збірку або запуск. Команди не доповнювались.

### Usage

Install a mod through package management or place your shared library into **/opt/etc/preload.d/lib${your_mod_name}.so**.

Then, to enable your_mod_name on the DIY GUI process run the following:

    modmanager enable diy_glasses your_mod_name

To later disable it run:

    modmanager disable diy_glasses your_mod_name

To list enabled mods for DIY GUI run:

    modmanager list diy_glasses
Note that most packages will probably enable their respective mod for you by default on install.

**Shortcuts**

Since the DIY GUI has different process names on V1 and V2 Goggles the following shortcuts are available for you:

 - **diy_glasses** - dji_glassess on V1 and dji_gls_wm150 on V2
 - **fpv_glasses** - dji_glasses on V2

## З чого зібрана картка

`catalog.json`, `fpv-library/repos/wtfos-modloader/README.md`, маніфести збірки в корені теки, якщо вони є.

Сторінка: `wiki/projects/fpv-wtf__wtfos-modloader.md`.

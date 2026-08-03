# StabX — повний каталог джерел у AeroStab

Останнє оновлення: 2026-08-03

## Джерела (Academia Tech / uapilot)

| ID | Джерело | URL / шлях | Статус у репо |
|----|---------|------------|---------------|
| S1 | SD образ RAR | `image/ZERO-16G-2025-11-01-JR.rar` | ✅ Git LFS (~1.7 GB) |
| S2 | SD образ IMG | `image/extracted/*.img` | ⚠️ локально, .gitignore (~7.3 GB) |
| S3 | Google Drive (медіа/доки) | `image/stabx-drive/` | ⚠️ локально, .gitignore (~1.6 GB, 23 файли) |
| S4 | ArduPlane STABX FW | Drive folder `1YqU0y8PFPoRYXT9zpu3KWSGH_ifB57I1` | ✅ `deploy/stabx-reference/` (1 zip → bin+hwdef) |
| S5 | BOM spreadsheet | `docs.google.com/spreadsheets/d/1EK2ivnruir1vM7jP4dPWfKLPtNHdDFTZSqVXn1FO-Cc` | ❌ не експортовано |
| S6 | Google Doc «Оптична навігація» | Academia (без публічного URL) | ⚠️ узагальнено в `docs/STABX_REVERSE.md` |
| S7 | uapilot.online білди | `:5050` Download (ліцензія) | 🔒 недоступно без ключа |
| S8 | `ua-pilot.enc` | всередині SD / OTA | 🔒 зашифровано, не витягується |

## Що в `vendor/stabx/` після `scripts/mirror_stabx_sources.sh`

| Тека | Вміст |
|------|--------|
| `sd-image/scripts/` | autorun, firmware, wifi, run_usb, rtsp, inet, update, wipe |
| `sd-image/systemd/` | wifi-connect, usb-autostart, devmon, shred_logs |
| `sd-image/ui-res/` | HTML UI creepy (:8080), ua.txt, en.txt |
| `sd-image/binaries-refs/` | sha256 + strings head для lserv/creepy (не самі бінарники) |
| `sd-image/settings/` | camera profiles config.txt |
| `drive-docs/` | StabX.pdf, StabX – ENG.pdf |
| `drive-manifest/files.tsv` | індекс усіх файлів з `image/stabx-drive/` |
| `ardupilot-fw/` | копія deploy/stabx-reference |
| `MANIFEST.json` | sha256 усіх файлів vendor |

## Білди StabX (хронологія з документації)

| Білд | Статус |
|------|--------|
| 2026-07-08-MASK-V2 | 🔒 OTA через uapilot |
| 2026-06-18-MASK | 🔒 |
| 2026-06-11-HILLS | 🔒 |
| 2026-05-11-RTL-V2 | 🔒 |
| 2026-03-16-DUAL-V1 | 🔒 |
| 2026-01-14-FUSE-V2 | 🔒 |
| 2025-12-18-DIFF-V3 | 🔒 |
| 2025-11-25-DIFF-V2 | 🔒 |
| ZERO-16G-2025-11-01-JR (SD base) | ✅ S1 |

## Що **не можна** вивантажити без винятків

1. **Зашифровані бінарники** `ua-pilot.enc` — ядро навігації StabX
2. **OTA zip** з uapilot.online / lserv :5050
3. **Ліцензійні ключі** та BT pairing
4. **Повні .stabx** записи польотів (proprietary) — лише з живого пристрою

## Trash

- **У GitHub репо RSTKCodeWP/-** теки `Trash` **немає**
- **У SD образі StabX** — немає каталогу Trash; лише стандартні іконки `user-trash` (LXDE) і пакет `python3-send2trash`
- **`image/stabx-drive/`** — 23 файли з Google Drive (відео, PDF, фото), **не** з Trash

## Команди

```bash
# Оновити vendor mirror (потрібен sudo для mount)
bash scripts/mirror_stabx_sources.sh

# Аналіз SD образу
bash scripts/analyze_stabx_image.sh image/ZERO-16G-2025-11-01-JR.rar
```

## Політика коміту

| Артефакт | Git |
|----------|-----|
| RAR образ | Git LFS |
| IMG extracted | .gitignore |
| stabx-drive медіа | .gitignore + drive-manifest |
| vendor/stabx scripts/UI | git (текст, < few MB) |
| lserv/creepy binaries | лише hashes/strings refs |

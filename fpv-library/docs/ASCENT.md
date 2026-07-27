# Walksnail / Caddx Ascent — прошивки та розбір

Індекс усього, що є в **цьому репо** по Ascent (офіційні джерела + RE + exploit).

## Офіційні прошивки (Caddx)

Репо: [CaddxFPV-Tech/Caddx-Ascent-Firmware_Release](https://github.com/CaddxFPV-Tech/Caddx-Ascent-Firmware_Release)

Локально: `fpv-library/repos/Caddx-Ascent-Firmware_Release-Caddx-Ascent-Firmware-Release/manifest.json`

| Реліз | Дата | Примітка |
|-------|------|----------|
| **V17.5.15** | 2026-07-17 | Єдиний реліз у manifest зараз |

### Образи V17.5.15

| deviceId | Роль | Чіп | Файл | ~Розмір |
|----------|------|-----|------|---------|
| `Ascent_G_Gnd` | наземний VRX | cx485 | `Ascent_G_Gnd_17_5_15.img` | 47 MB |
| `Ascent_G_Sky` | повітря | cx486 | `Ascent_G_Sky_17_5_15.img` | 15 MB |
| `Ascent_H_Sky` | повітря | cx482 | `Ascent_H_Sky_17_5_15.img` | 14 MB |
| `Ascent_L_Gnd` | наземний | cx401 | `Ascent_L_Gnd_17_5_15.img` | 46 MB |

```bash
python3 fpv-library/scripts/download_caddx_firmware.py          # список
python3 fpv-library/scripts/download_caddx_firmware.py Ascent_G_Gnd
```

`.img` — контейнер **OTRA** (не кладемо в git, лише manifest + SHA256).

### Старіші версії в розборі

| Версія | Де зустрічається |
|--------|------------------|
| **16.5.7** | [HackMD RE](https://hackmd.io/@umeow0716/ryu63HDeGg), `extract-ascent-otra/download.sh`, exploit PoC (`Ascent_G_Gnd_16_5_7.img`) |

Офіційний manifest зараз лише **17.5.15**; для diff 16.5.7 → 17.5.15 треба вручну завантажити старий `.img` (Walksnail CDN у `download.sh`).

---

## Розбір у нашому репо (RE / протоколи / інструменти)

### 1. USB exploit (земний VRX, не повітря)

| Шлях | Що всередині |
|------|----------------|
| `fpv-library/repos/Walksnail-Ascent-FPV-VRX-Rooting-Exploit-.../` | PoC: OTRA USB `0x72–0x75`, `ar_fpv_upgrade` → `popen("md5sum %s")` |
| [HackMD](https://hackmd.io/@umeow0716/ryu63HDeGg) | Партиції, boot chain, RTSP-патчі, повний ланцюжок |

**Висновок RE:** RCE через **command injection** при USB-оновленні; **не** RSA bypass; **не** OTA на літаючий VTX.

### 2. Розпаковка OTRA

| Шлях | Що робить |
|------|-----------|
| `fpv-library/repos/extract-ascent-otra/` | `extract_ascent_otra.py` — партиції, LZO, UBI, SquashFS |

Типові партиції (з RE 16.5.7):

- `userapp0` — rootfs (SquashFS)
- `usr_data0`, `fpv_data` — дані / FPV
- `kernel`, `uboot0`

### 3. OTRA tools (fpv-wtf)

| Джерело | Примітка |
|---------|----------|
| [fpv-wtf/ar-firmware-tools](https://github.com/fpv-wtf/ar-firmware-tools) | Формат OTRA (Artosyn / сімейство DJI/Walksnail) — у каталозі, mirror опційно |

### 4. Протокол керування VRX (LAN, не 5.8 GHz air link)

| Шлях | Що всередині |
|------|----------------|
| `fpv-library/repos/Caddx_vrx_udp_protocol-.../` | Офіційний UDP клієнт + UART spec |
| `fpv-library/repos/caddx_vrx_udp_protocol-.../` | Community mirror (JerryLamMV) |

- **Ethernet:** `192.168.1.100:9001`
- **USB-RNDIS:** `192.168.3.102:9001`
- Команди: keys (`pairing`, …), frequency, power, wireless status
- Захист: checksum у пакеті; **без auth** (ризик лише при доступі до LAN VRX)

### 5. Ground Configuration (Windows GCS)

| Шлях | Що всередині |
|------|----------------|
| `fpv-library/manifests/Caddx_Ground_Configuration_Release.json` | Релізи v0.3.3, SHA256 |
| `fpv-library/scripts/sync_caddx_ground_config.py` | Sync + download |
| `fpv-library/ground-config/` | Локальні бінарники (gitignored) |

З розбору бінарника: HID-пульт, RTSP/GStreamer, OSD (BF/iNav/Ardu), `AscentVrxProtocol`, UDP helper.

### 6. Інші офіційні Caddx

| Репо | Роль |
|------|------|
| `Caddx-PC-Tool-Release` | Прошивка через PC tool |
| `Caddx_Ground_Configuration_Release` | Конфіг наземної станції |

---

## Air link VTX ↔ VRX (що **не** в прошивкових репо)

У відкритих матеріалах Caddx + наш RE:

- Повітряний лінк — **пропрієтарний цифровий 5.8 GHz**, pair/link між VTX і VRX.
- **Немає** публічного опису OTA-команди «disconnect» для стороннього передавача.
- USB/OTRA exploit і UDP — лише **земний VRX** / LAN.
- Перервати відео в польоті без доступу до заліза → переважно **RF-завади** на 5.8 GHz, не «команда VTX».

---

## Швидкі команди

```bash
# Офіційна прошивка VRX
python3 fpv-library/scripts/download_caddx_firmware.py Ascent_G_Gnd

# Розпакувати OTRA (після завантаження .img)
cd fpv-library/repos/extract-ascent-otra
./download.sh   # або свій .img з 17.5.15
uv run python extract_ascent_otra.py Ascent_G_Gnd_17_5_15.img -o extracted/

# UDP статус VRX (коли VRX у мережі)
python fpv-library/repos/Caddx_vrx_udp_protocol-.../udp_vrx_client.py status
```

## Див. також

- [THEMED.md § Caddx Ascent](../THEMED.md)
- [REPOS.md](../../REPOS.md) — повний каталог

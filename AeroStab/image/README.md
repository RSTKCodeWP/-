# AeroStab SD Image для Raspberry Pi Zero 2W

Готовий **bundle** для швидкого розгортання без ручного клонування репозиторію на Pi.

## Збірка bundle (на ПК)

```bash
cd AeroStab
bash image/build_sd_bundle.sh
```

Результат: `dist/aerostab-sd-bundle.tar.gz`

## Запис на SD

### 1. OS

Raspberry Pi Imager → **Pi Zero 2 W** → **Raspberry Pi OS Lite (64-bit)**.

У **Edit Settings**:
- Hostname: `aerostab`
- SSH: увімкнено
- Wi-Fi: ваші дані

### 2. Bundle на boot-розділ

Після запису OS (SD ще в ПК):

```bash
# Linux — шлях може бути bootfs або boot
sudo mkdir -p /mnt/bootfs
sudo mount /dev/sdX1 /mnt/bootfs   # замініть sdX1
sudo tar -xzf dist/aerostab-sd-bundle.tar.gz -C /mnt/bootfs/
sudo umount /mnt/bootfs
```

На boot-розділі з'явиться `/aerostab/` з проєктом і скриптами.

### 3. Перше завантаження

**Варіант A — вручну (надійніше):**

```bash
ssh pi@aerostab.local
sudo bash /boot/firmware/aerostab/install-on-first-boot.sh
sudo reboot
```

**Варіант B — автоматично:**

```bash
sudo cp /boot/firmware/aerostab/aerostab-firstboot.service /etc/systemd/system/
sudo systemctl enable --now aerostab-firstboot.service
```

### 4. Готово

Відкрийте http://aerostab.local:8080 → вкладки **Інструкція** та **Політ**.

## Структура bundle

```
aerostab/
├── project/              # повний AeroStab (без .venv)
├── install-on-first-boot.sh
├── aerostab-firstboot.service
├── README-FIRSTBOOT.txt
└── ENABLE_FIRSTBOOT
```

## Cloud-init (опційно)

Для автоматизації через Pi Imager cloud-init:

```yaml
#cloud-config
runcmd:
  - [ bash, -c, "test -f /boot/firmware/aerostab/install-on-first-boot.sh && bash /boot/firmware/aerostab/install-on-first-boot.sh" ]
```

Додайте як `user-data` на boot-розділ (розширена конфігурація Imager).

## Примітки

- Повний custom `.img` з pi-gen не входить у репозиторій — bundle + Pi OS Lite дає той самий результат з меншим розміром.
- Перше встановлення займає 5–15 хв (apt + pip).
- Після встановлення маркер `/var/lib/aerostab/firstboot.done` блокує повторний запуск.

Детальніше: [docs/FLASH.md](../docs/FLASH.md)

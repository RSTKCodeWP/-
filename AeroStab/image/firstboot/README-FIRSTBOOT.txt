AeroStab SD Bundle — First Boot
==============================

1. Flash Raspberry Pi OS Lite 64-bit with Pi Imager (hostname: aerostab, SSH on).
2. Extract aerostab-sd-bundle.tar.gz to the boot partition (/boot/firmware/ or /boot/).
3. Boot the Pi. On first login via SSH:

   sudo bash /boot/firmware/aerostab/install-on-first-boot.sh

   Or enable unattended install:

   sudo cp /boot/firmware/aerostab/aerostab-firstboot.service /etc/systemd/system/
   sudo systemctl enable --now aerostab-firstboot.service

4. After reboot: http://aerostab.local:8080

See docs/FLASH.md for full instructions.

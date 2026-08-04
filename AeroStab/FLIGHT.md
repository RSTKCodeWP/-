# AeroStab — картка польоту (ламінуй / тримай на телефоні)

## Залив → увімкнув → злетів → PosHold → завис

1. SD: Raspberry Pi OS Lite 64-bit, hostname `aerostab`, SSH on  
2. `sudo bash deploy/install_pi.sh && sudo reboot`  
3. Відкрий http://aerostab.local:8080 → вкладка **Політ**  
4. Проводка: Pi GPIO14 TX → FC RX, GPIO15 RX → FC TX, GND, 5V  
5. Mission Planner: `deploy/ardupilot_aerostab.param` (SERIAL2 TELEM2 @ 230400)  
6. Маска: закрий ніжки/кабелі в кадрі  
7. FOV: сітка 1 м на висоті ~1 м (Frank-S01 ≈ 72.4°)  
8. Чекай **FLIGHT OK** (усі кроки зелені)  
9. Arm **PosHold**, тримай стіки в центрі  
10. Якщо **HOLD LAST** — не панікуй; AltHold якщо довго немає текстури  

## НЕ армити якщо

- банер **НЕ АРМИТИ**
- NAV WAIT / немає heartbeat
- якість < 0.25 або мало точок
- маска закриває >33% ROI

## Failsafe

- Втрата optical flow → HOLD LAST (позиція заморожена, остання поза в EKF)
- RC loss → RTL з `ardupilot_rtl_failsafe.param`
- EKF fail → FS_EKF (див. params)

## Після польоту

```bash
python3 /opt/aerostab/scripts/analyze_log.py -d /var/log/aerostab
```

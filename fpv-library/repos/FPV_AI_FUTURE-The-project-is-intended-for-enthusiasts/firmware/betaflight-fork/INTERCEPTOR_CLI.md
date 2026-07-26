# SpeedyBee F405 V4 — interceptor CLI config (MSP override + kill, from the stock dump)

This converts the **stock manual-quad** config (`hardware/.../Архангел1 …AUX4 инициация.txt`) into the
interceptor config the software expects. It is a **diff** — paste it into the Betaflight CLI (4.4.3) and it
changes only what is needed, then `save`. Nothing here arms anything; the safety model is unchanged except
where noted.

> **Doctrine invariants this config enforces** (`docs/CHECKPOINT.md` §3):
> - **The Pi never arms.** Arming stays on the RC switch; the MSP override mask covers only the 4 sticks,
>   never the ARM channel. If the Pi crashes or the MSP RC stream stops, Betaflight drops the override and
>   the pilot's sticks return automatically. Both properties come from Betaflight, not from our code.
> - **No payload.** The stock `USER1` "Гермес инициация" GPIO channel is removed (see §4). Body-to-body,
>   no warhead — there is nothing to initiate.

---

## AUX layout — CONFIRMED by the owner (2026-07-19/20)

| what | mapping | note |
|---|---|---|
| ARM switch | **AUX5**, 1400–2100 (unchanged) | confirmed; the Pi never touches this |
| MSP-override toggle | **AUX2**, 1600–2100 | confirmed — the switch you HOLD to hand the sticks to the seeker |
| ANGLE (self-level) | AUX1, 1400–2100 (unchanged) | your manual-flight self-level |
| stray ARM on AUX3 (900–950) | **REMOVED** | confirmed — it armed when AUX3 was LOW, a real hazard |
| USER1 initiation on AUX4 | **REMOVED** | confirmed — no payload in doctrine (restore in §4 if ever needed) |

The one thing still on your judgement is the failsafe behaviour (§3) — it depends on your field rules.

---

## 1. MSP override — the seeker takes the sticks only while you hold the toggle

```
# MSP_OVERRIDE mode (permanent boxId 50) on AUX2 (auxChannelIndex 1 = RC channel 6), active 1600-2100.
# Owner-confirmed: AUX2 is the toggle. The Pi reads it at MSP RC index 5 (matches flight_gimbal default).
aux 4 50 1 1600 2100 0 0

# Which channels the Pi may override while the mode is active. 15 = roll+pitch+throttle+yaw (the 4 sticks),
# and DELIBERATELY NOT the AUX channels -- so ARM can never be driven over MSP. This is the "Pi never arms"
# invariant in one number.
set msp_override_channels_mask = 15
```

MSP RC arrives over the USB VCP, which the stock dump already has as an MSP port (`serial 20 1`). No
`RX_MSP` feature is added: CRSF stays the primary receiver and MSP is only overlaid on the masked sticks
while the toggle is held. This is exactly the handover `msp_override_flight.py` drives.

## 2. Remove the hazardous stray ARM on AUX3

```
# Stock had:  aux 1 0 2 900 950 0 0   -> ARM (mode 0) on AUX3, active at LOW stick. Clear it.
aux 1 0 0 900 900 0 0
```

## 3. Failsafe — cut motors on link loss (pairs with the independent kill-MCU)

```
# You chose independent kill-MCU + failsafe. The MCU cuts motor POWER on its own logic; Betaflight's job is
# to stop commanding thrust the instant the RC link is lost. DROP is the conservative choice for a small
# interceptor with a pilot holding the backup. [CONFIRM] against your field rules.
set failsafe_procedure = DROP
set failsafe_delay = 4
set failsafe_off_delay = 10
```

The MSP-override timeout is separate and automatic: if the Pi's MSP RC stream stops, Betaflight falls back
to the receiver within a few hundred ms — the pilot's sticks — even before any RC-link failsafe triggers.

## 4. Remove the payload initiation channel (doctrine: no warhead)

```
# Stock had:  aux 3 40 3 1600 2100 0 0  -> USER1 (boxId 40) on AUX4 -> PINIO1 (pin B11) "Гермес инициация".
# There is no payload to initiate (body-to-body, no warhead). Clear the mode.
aux 3 0 0 900 900 0 0
```

> To RESTORE it (if you keep a non-warhead payload on that GPIO), re-apply the stock line
> `aux 3 40 3 1600 2100 0 0`. It sits OUTSIDE the software safety model — `arming.py`/`hwkill` govern motors
> only — so treat it as an independent, operator-radio-driven output and secure it yourself.

## 5. Save

```
save
```

After reboot, verify in the CLI:

```
diff                       # confirm aux 4 (MSP_OVERRIDE) present, mask=15, no stray ARM, no USER1
status                     # arming flags; must NOT be armable from the Pi
```

Then run the bench handover check from the Pi **with props OFF**:

```
python3 -m fpv_ai.msp_override_flight scan            # find the FC
python3 -m fpv_ai.msp_override_flight no-camera       # toggle -> override handover, no perception
```

You should see: toggle DOWN → the FC uses the receiver (your sticks); toggle UP → the FC accepts the Pi's
level/gentle MSP RC on the 4 sticks only; flip DOWN → instant manual reclaim.

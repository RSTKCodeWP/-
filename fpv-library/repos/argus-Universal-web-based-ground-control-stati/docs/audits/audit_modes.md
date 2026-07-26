# Argus GCS Flight Mode ID Audit

Audit of `backend/constants.py` against the
ArduPilot source tree.

Sources of truth:

- Copter: `ArduCopter/mode.h:80-110` (`enum class Number`)
- Plane:  `ArduPlane/mode.h:33-65`  (`enum Number`)
- Rover:  `Rover/mode.h:14-31`      (`enum class Number`)
- Sub:    `ArduSub/mode.h:42-54`    (`enum class Number`)
- `MAV_TYPE`: `modules/mavlink/message_definitions/v1.0/minimal.xml:71-221`

Argus dicts are at `backend/constants.py:1-51`.

---

## 1. Copter

### ArduPilot truth (`ArduCopter/mode.h:81-106`)

| ID | Name           | ID | Name        | ID | Name         |
|----|----------------|----|-------------|----|--------------|
| 0  | STABILIZE      | 11 | DRIFT       | 21 | SMART_RTL    |
| 1  | ACRO           | 13 | SPORT       | 22 | FLOWHOLD     |
| 2  | ALT_HOLD       | 14 | FLIP        | 23 | FOLLOW       |
| 3  | AUTO           | 15 | AUTOTUNE    | 24 | ZIGZAG       |
| 4  | GUIDED         | 16 | POSHOLD     | 25 | SYSTEMID     |
| 5  | LOITER         | 17 | BRAKE       | 26 | AUTOROTATE   |
| 6  | RTL            | 18 | THROW       | 27 | AUTO_RTL     |
| 7  | CIRCLE         | 19 | AVOID_ADSB  | 28 | TURTLE       |
| 9  | LAND           | 20 | GUIDED_NOGPS |   |              |

(No mode 8, 10, 12. Mode 127 reserved for Skybrush drone-show fork.)

### Argus value (`backend/constants.py:1-4, 27-30`)

`COPTER_MODES` / `COPTER_MODES_EN` contain only IDs:
`0, 1, 2, 3, 4, 5, 6, 7, 9, 16, 21` — eleven modes.

### Missing in Argus (15 modes)

All confirmed via `ArduCopter/mode.h:81-106`.

| ID | AP name      | AP location              | Recommended zh / en                 |
|----|--------------|--------------------------|-------------------------------------|
| 11 | DRIFT        | `mode.h:90`              | `漂移` / `Drift`                    |
| 13 | SPORT        | `mode.h:91`              | `运动` / `Sport`                    |
| 14 | FLIP         | `mode.h:92`              | `翻滚` / `Flip`                     |
| 15 | AUTOTUNE     | `mode.h:93`              | `自动调参` / `AutoTune`             |
| 17 | BRAKE        | `mode.h:95`              | `刹车` / `Brake`                    |
| 18 | THROW        | `mode.h:96`              | `抛飞` / `Throw`                    |
| 19 | AVOID_ADSB   | `mode.h:97`              | `ADSB避让` / `Avoid ADSB`           |
| 20 | GUIDED_NOGPS | `mode.h:98`              | `无GPS引导` / `Guided NoGPS`        |
| 22 | FLOWHOLD     | `mode.h:100`             | `光流悬停` / `FlowHold`             |
| 23 | FOLLOW       | `mode.h:101`             | `跟随` / `Follow`                   |
| 24 | ZIGZAG       | `mode.h:102`             | `Z字形` / `ZigZag`                  |
| 25 | SYSTEMID     | `mode.h:103`             | `系统识别` / `SystemID`             |
| 26 | AUTOROTATE   | `mode.h:104`             | `自旋着陆` / `AutoRotate`           |
| 27 | AUTO_RTL     | `mode.h:105`             | `自动返航` / `Auto RTL`             |
| 28 | TURTLE       | `mode.h:106`             | `翻身` / `Turtle`                   |

### Wrong IDs / wrong names

None. All eleven currently-listed Copter modes match AP values and names.

### Extra modes in Argus

None.

### Recommended fix

```python
COPTER_MODES = {
    0: '自稳', 1: '特技', 2: '定高', 3: '自动', 4: '引导',
    5: '悬停', 6: '返航', 7: '绕圈', 9: '降落', 11: '漂移',
    13: '运动', 14: '翻滚', 15: '自动调参', 16: '定点', 17: '刹车',
    18: '抛飞', 19: 'ADSB避让', 20: '无GPS引导', 21: '智能返航',
    22: '光流悬停', 23: '跟随', 24: 'Z字形', 25: '系统识别',
    26: '自旋着陆', 27: '自动返航', 28: '翻身',
}
COPTER_MODES_EN = {
    0: 'Stabilize', 1: 'Acro', 2: 'Alt Hold', 3: 'Auto', 4: 'Guided',
    5: 'Loiter', 6: 'RTL', 7: 'Circle', 9: 'Land', 11: 'Drift',
    13: 'Sport', 14: 'Flip', 15: 'AutoTune', 16: 'PosHold', 17: 'Brake',
    18: 'Throw', 19: 'Avoid ADSB', 20: 'Guided NoGPS', 21: 'Smart RTL',
    22: 'FlowHold', 23: 'Follow', 24: 'ZigZag', 25: 'SystemID',
    26: 'AutoRotate', 27: 'Auto RTL', 28: 'Turtle',
}
```

---

## 2. Plane

### ArduPilot truth (`ArduPlane/mode.h:33-65`)

| ID | Name          | ID | Name              |
|----|---------------|----|-------------------|
| 0  | MANUAL        | 13 | TAKEOFF           |
| 1  | CIRCLE        | 14 | AVOID_ADSB        |
| 2  | STABILIZE     | 15 | GUIDED            |
| 3  | TRAINING      | 16 | INITIALISING      |
| 4  | ACRO          | 17 | QSTABILIZE        |
| 5  | FLY_BY_WIRE_A | 18 | QHOVER            |
| 6  | FLY_BY_WIRE_B | 19 | QLOITER           |
| 7  | CRUISE        | 20 | QLAND             |
| 8  | AUTOTUNE      | 21 | QRTL              |
| 10 | AUTO          | 22 | QAUTOTUNE         |
| 11 | RTL           | 23 | QACRO             |
| 12 | LOITER        | 24 | THERMAL           |
|    |               | 25 | LOITER_ALT_QLAND  |

(No mode 9.)

### Argus value (`backend/constants.py:5-9, 31-35`)

`PLANE_MODES` / `PLANE_MODES_EN` contain IDs:
`0, 1, 2, 5, 6, 7, 10, 11, 12, 15, 17, 18, 19, 20, 21` — fifteen modes.

### Missing in Argus (11 modes)

| ID | AP name           | AP location          | Recommended zh / en                       |
|----|-------------------|----------------------|-------------------------------------------|
| 3  | TRAINING          | `mode.h:37`          | `训练` / `Training`                       |
| 4  | ACRO              | `mode.h:38`          | `特技` / `Acro`                           |
| 8  | AUTOTUNE          | `mode.h:42`          | `自动调参` / `AutoTune`                   |
| 13 | TAKEOFF           | `mode.h:46`          | `起飞` / `Takeoff`                        |
| 14 | AVOID_ADSB        | `mode.h:47`          | `ADSB避让` / `Avoid ADSB`                 |
| 16 | INITIALISING      | `mode.h:49`          | `初始化` / `Initialising`                 |
| 22 | QAUTOTUNE         | `mode.h:57`          | `旋翼自动调参` / `Q-AutoTune`             |
| 23 | QACRO             | `mode.h:59`          | `旋翼特技` / `Q-Acro`                     |
| 24 | THERMAL           | `mode.h:61`          | `热气流` / `Thermal`                      |
| 25 | LOITER_ALT_QLAND  | `mode.h:63`          | `盘旋后旋翼降落` / `Loiter to QLand`      |

### Wrong IDs / wrong names

None. All fifteen currently-listed Plane modes match AP IDs and the
shorthand names are reasonable (FBW-A/FBW-B are common GCS aliases for
`FLY_BY_WIRE_A`/`FLY_BY_WIRE_B`).

### Extra modes in Argus

None.

### Recommended fix

```python
PLANE_MODES = {
    0: '手动', 1: '绕圈', 2: '自稳', 3: '训练', 4: '特技',
    5: '辅助A', 6: '辅助B', 7: '巡航', 8: '自动调参',
    10: '自动', 11: '返航', 12: '盘旋', 13: '起飞',
    14: 'ADSB避让', 15: '引导', 16: '初始化',
    17: '旋翼自稳', 18: '旋翼悬停', 19: '旋翼定点',
    20: '旋翼降落', 21: '旋翼返航', 22: '旋翼自动调参',
    23: '旋翼特技', 24: '热气流', 25: '盘旋后旋翼降落',
}
PLANE_MODES_EN = {
    0: 'Manual', 1: 'Circle', 2: 'Stabilize', 3: 'Training', 4: 'Acro',
    5: 'FBW-A', 6: 'FBW-B', 7: 'Cruise', 8: 'AutoTune',
    10: 'Auto', 11: 'RTL', 12: 'Loiter', 13: 'Takeoff',
    14: 'Avoid ADSB', 15: 'Guided', 16: 'Initialising',
    17: 'Q-Stabilize', 18: 'Q-Hover', 19: 'Q-Loiter',
    20: 'Q-Land', 21: 'Q-RTL', 22: 'Q-AutoTune',
    23: 'Q-Acro', 24: 'Thermal', 25: 'Loiter to QLand',
}
```

---

## 3. Rover

### ArduPilot truth (`Rover/mode.h:14-31`)

| ID | Name         |
|----|--------------|
| 0  | MANUAL       |
| 1  | ACRO         |
| 3  | STEERING     |
| 4  | HOLD         |
| 5  | LOITER       |
| 6  | FOLLOW       |
| 7  | SIMPLE       |
| 8  | DOCK         (gated `MODE_DOCK_ENABLED`, default = `AC_PRECLAND_ENABLED`) |
| 9  | CIRCLE       |
| 10 | AUTO         |
| 11 | RTL          |
| 12 | SMART_RTL    |
| 15 | GUIDED       |
| 16 | INITIALISING |

### Argus value (`backend/constants.py:10-13, 36-39`)

IDs present: `0, 1, 3, 4, 5, 10, 11, 12, 15` — nine modes.

### Issues

**Wrong name (Rover ID 5)**
- AP `Rover/mode.h:19`: `LOITER = 5`
- Argus: `5: '跟随'` / `5: 'Follow'`
- Recommended fix: `5: '悬停' / 'Loiter'`. Rover ID 5 is **LOITER**, not Follow. Follow is ID 6.

**Missing in Argus (6 modes)**

| ID | AP name      | AP location  | Recommended zh / en                |
|----|--------------|--------------|------------------------------------|
| 6  | FOLLOW       | `mode.h:20`  | `跟随` / `Follow`                  |
| 7  | SIMPLE       | `mode.h:21`  | `简单` / `Simple`                  |
| 8  | DOCK         | `mode.h:23`  | `对接` / `Dock`                    |
| 9  | CIRCLE       | `mode.h:25`  | `绕圈` / `Circle`                  |
| 12 | SMART_RTL is already listed (id 12 OK) — note Rover SMART_RTL is 12, not 21 |
| 16 | INITIALISING | `mode.h:30`  | `初始化` / `Initialising`          |

### Recommended fix

```python
ROVER_MODES = {
    0: '手动', 1: '特技', 3: '转向', 4: '固定',
    5: '悬停', 6: '跟随', 7: '简单', 8: '对接', 9: '绕圈',
    10: '自动', 11: '返航', 12: '智能返航', 15: '引导', 16: '初始化',
}
ROVER_MODES_EN = {
    0: 'Manual', 1: 'Acro', 3: 'Steering', 4: 'Hold',
    5: 'Loiter', 6: 'Follow', 7: 'Simple', 8: 'Dock', 9: 'Circle',
    10: 'Auto', 11: 'RTL', 12: 'Smart RTL', 15: 'Guided', 16: 'Initialising',
}
```

---

## 4. Sub

### ArduPilot truth (`ArduSub/mode.h:42-54`)

| ID | Name         |
|----|--------------|
| 0  | STABILIZE    |
| 1  | ACRO         |
| 2  | ALT_HOLD     |
| 3  | AUTO         |
| 4  | GUIDED       |
| 7  | CIRCLE       |
| 9  | SURFACE      |
| 16 | POSHOLD      |
| 19 | MANUAL       |
| 20 | MOTOR_DETECT |
| 21 | SURFTRAK     |

### Argus value (`backend/constants.py:14-17, 40-43`)

IDs present: `0, 1, 2, 3, 4, 7, 9, 16, 19` — nine modes. Names match.

### Missing in Argus (2 modes)

| ID | AP name      | AP location  | Recommended zh / en             |
|----|--------------|--------------|---------------------------------|
| 20 | MOTOR_DETECT | `mode.h:52`  | `电机检测` / `Motor Detect`     |
| 21 | SURFTRAK     | `mode.h:53`  | `底跟踪` / `SurfTrak`           |

### Wrong IDs / extra modes

None. (Argus uses `定深` / `Depth Hold` for ALT_HOLD which is the
conventional ROV translation — acceptable.)

### Recommended fix

```python
SUB_MODES = {
    0: '自稳', 1: '特技', 2: '定深', 3: '自动', 4: '引导',
    7: '绕圈', 9: '水面', 16: '定点', 19: '手动',
    20: '电机检测', 21: '底跟踪',
}
SUB_MODES_EN = {
    0: 'Stabilize', 1: 'Acro', 2: 'Depth Hold', 3: 'Auto', 4: 'Guided',
    7: 'Circle', 9: 'Surface', 16: 'PosHold', 19: 'Manual',
    20: 'Motor Detect', 21: 'SurfTrak',
}
```

---

## 5. `*_BTNS` quick-switch button coverage

The button arrays expose what the operator can click directly. They do
not need to be exhaustive, but they should cover the modes that are most
commonly used for arming and routine use.

### `COPTER_BTNS` (`constants.py:18, 44`)
Current: `Stabilize, Alt Hold, Loiter, Auto, RTL, Land`.
**Verdict: OK.** Covers the canonical arming/landing modes. Reasonable
additions if desired: `Guided` (id 4, used by mission-start and offboard),
`PosHold` (id 16), `Smart RTL` (id 21). Not strictly required.

### `PLANE_BTNS` (`constants.py:19-22, 45-48`)
Current: `Q-Loiter, Q-Hover, Q-Stabilize, Auto, Q-RTL, Q-Land, Loiter, RTL`.
**Verdict: Acceptable but biased toward quadplane.** Missing `Manual` (id 0)
and `FBW-A` (id 5) — the most common fixed-wing arming modes. Recommend
adding at minimum `Manual` for true fixed-wing operators.

### `ROVER_BTNS` (`constants.py:23, 49`)
Current: `Manual, Hold, Auto, Guided, RTL`. **Verdict: OK.**

### `SUB_BTNS` (`constants.py:24, 50`)
Current: `Stabilize, Depth Hold, PosHold, Auto, Guided`. **Verdict: OK.**

---

## 6. zh / en parity

Compared keysets of every pair:

- `COPTER_MODES.keys() == COPTER_MODES_EN.keys()` — yes (both 11 entries).
- `PLANE_MODES.keys() == PLANE_MODES_EN.keys()` — yes (both 15 entries).
- `ROVER_MODES.keys() == ROVER_MODES_EN.keys()` — yes (both 9 entries).
- `SUB_MODES.keys() == SUB_MODES_EN.keys()` — yes (both 9 entries).
- `COPTER_BTNS` ↔ `COPTER_BTNS_EN`: same 6 IDs. OK.
- `PLANE_BTNS` ↔ `PLANE_BTNS_EN`: same 8 IDs. OK.
- `ROVER_BTNS` ↔ `ROVER_BTNS_EN`: same 5 IDs. OK.
- `SUB_BTNS` ↔ `SUB_BTNS_EN`: same 5 IDs. OK.
- `FIX_NAMES` ↔ `FIX_NAMES_EN`: same 7 IDs (0..6). OK.

**Verdict: zh and en variants are in sync.** Any new IDs added per
sections 1-4 must be added to both dicts.

---

## 7. `is_plane()` MAV_TYPE check

### Code (`backend/drone_link.py:127-131`)

```python
def is_plane(self) -> bool:
    v = self.vehicle
    if v.force_plane is not None:
        return v.force_plane
    return v.vtype_raw in (1, 19, 20, 21, 22, 23, 24, 25)
```

### Reference (`modules/mavlink/message_definitions/v1.0/minimal.xml:71-221`)

ArduPlane / quadplane MAV_TYPE values:

| Value | Name                       |
|-------|----------------------------|
| 1     | MAV_TYPE_FIXED_WING        |
| 19    | MAV_TYPE_VTOL_DUOROTOR (tailsitter)   |
| 20    | MAV_TYPE_VTOL_QUADROTOR (tailsitter)  |
| 21    | MAV_TYPE_VTOL_TILTROTOR    |
| 22    | MAV_TYPE_VTOL_RESERVED2    |
| 23    | MAV_TYPE_VTOL_RESERVED3    |
| 24    | MAV_TYPE_VTOL_RESERVED4    |
| 25    | MAV_TYPE_VTOL_RESERVED5    |
| 28    | MAV_TYPE_PARAFOIL          |
| 47    | MAV_TYPE_VTOL_GYRODYNE     |

### Issues

The current set `{1, 19, 20, 21, 22, 23, 24, 25}` covers fixed wing plus
the canonical VTOL block (values 19-25 reserved for VTOL airframes per
`minimal.xml:139`). Two additions worth considering:

- **47 `MAV_TYPE_VTOL_GYRODYNE`** (`minimal.xml:215`) — newer VTOL hybrid
  added after the 19-25 reserved block was filled. ArduPlane could send
  this for a gyrodyne airframe. Recommend adding.
- **28 `MAV_TYPE_PARAFOIL`** (`minimal.xml:158`) — steerable airfoil.
  Whether this should map to plane is judgement-call; it is not a
  quadplane and ArduPlane does not currently expose it as a default
  vehicle type. Leaving out is defensible.

### Recommended fix

```python
return v.vtype_raw in (1, 19, 20, 21, 22, 23, 24, 25, 47)
```

(`force_plane` override remains the user escape hatch for any edge case.)

---

## Summary

- **Copter**: 0 wrong IDs, 0 wrong names, **15 missing modes** (IDs 11, 13, 14, 15, 17, 18, 19, 20, 22, 23, 24, 25, 26, 27, 28).
- **Plane**: 0 wrong IDs, 0 wrong names, **10 missing modes** (IDs 3, 4, 8, 13, 14, 16, 22, 23, 24, 25).
- **Rover**: **1 wrong name** (ID 5 listed as Follow, AP says Loiter), 0 wrong IDs, **5 missing modes** (IDs 6, 7, 8, 9, 16).
- **Sub**: 0 wrong IDs, 0 wrong names, **2 missing modes** (IDs 20, 21).
- **Buttons (`*_BTNS`)**: acceptable; recommend adding `Manual` (id 0) to `PLANE_BTNS` for fixed-wing users.
- **zh/en parity**: in sync.
- **`is_plane()`**: works for canonical plane/VTOL types; recommend adding `47` (`MAV_TYPE_VTOL_GYRODYNE`).

Total: **32 missing modes**, **1 wrong name**, **0 wrong IDs**.

"""LiPo battery telemetry via an INA219 (voltage + current over I2C).

The Pi has no native ADC, so pack voltage/current come from an INA219 breakout
on the battery line (I2C: SDA=GPIO2/pin3, SCL=GPIO3/pin5, plus 3V3 + GND). This
module reads bus voltage and current and estimates state-of-charge from a LiPo
discharge curve.

Same self-contained, no-op-if-missing pattern as motor_control.py /
lights_control.py: importing this never breaks the server. Without the `ina219`
library or the sensor wired, `read()` returns all-None and the HUD simply shows
`--%` — nothing raises.

Config via env vars (all optional):
    BATTERY_CELLS     LiPo cell count in series (default 2 -> 2S)
    BATTERY_SHUNT_OHMS  INA219 shunt resistance (default 0.1, the common breakout)
    BATTERY_MAX_AMPS  expected max current, tunes the INA219 gain (optional)
    BATTERY_WARN_PCT  low-battery alert threshold, percent (default 25)

Bench test: `python3 battery_control.py` prints a few reads.
"""

import os

BATTERY_CELLS = int(os.environ.get("BATTERY_CELLS", "2"))
SHUNT_OHMS = float(os.environ.get("BATTERY_SHUNT_OHMS", "0.1"))
MAX_AMPS = os.environ.get("BATTERY_MAX_AMPS")  # None -> let the library auto-gain
WARN_PCT = int(os.environ.get("BATTERY_WARN_PCT", "25"))
# INA219 I2C address. Defaults to 0x40 — note the PCA9685 (pan/tilt) also defaults
# to 0x40, so if you run both, readdress one (env here or PAN_TILT_I2C_ADDR).
I2C_ADDR = int(os.environ.get("BATTERY_I2C_ADDR", "0x40"), 0)

# Approximate resting per-cell voltage -> state-of-charge, descending. LiPo
# discharge is nonlinear, so a straight line over/under-reads badly; this small
# table interpolated is close enough for a HUD gauge. Voltage sags under load,
# so treat the number as an estimate, not a fuel gauge.
_LIPO_CURVE = [
    (4.20, 100), (4.15, 95), (4.11, 90), (4.08, 85), (4.02, 80),
    (3.98, 75), (3.95, 70), (3.91, 65), (3.87, 60), (3.85, 55),
    (3.84, 50), (3.82, 45), (3.80, 40), (3.79, 35), (3.77, 30),
    (3.75, 25), (3.73, 20), (3.71, 15), (3.69, 10), (3.61, 5), (3.27, 0),
]


def percent_from_voltage(total_v, cells=BATTERY_CELLS):
    """Estimate LiPo charge % from pack voltage. Returns None on bad input."""
    if total_v is None or cells is None or cells <= 0:
        return None
    per_cell = total_v / cells
    if per_cell >= _LIPO_CURVE[0][0]:
        return 100
    if per_cell <= _LIPO_CURVE[-1][0]:
        return 0
    for (v_hi, p_hi), (v_lo, p_lo) in zip(_LIPO_CURVE, _LIPO_CURVE[1:]):
        if v_lo <= per_cell <= v_hi:
            frac = (per_cell - v_lo) / (v_hi - v_lo)
            return round(p_lo + frac * (p_hi - p_lo))
    return None


class BatteryMonitor:
    """read() -> {voltage, current_ma, percent, cells}; all-None without the sensor."""

    def __init__(self, cells=BATTERY_CELLS, shunt_ohms=SHUNT_OHMS):
        self.cells = cells
        self.warn_pct = WARN_PCT
        self._ina = None
        self.hardware = False
        try:
            from ina219 import INA219
            if MAX_AMPS is not None:
                self._ina = INA219(shunt_ohms, float(MAX_AMPS), address=I2C_ADDR)
            else:
                self._ina = INA219(shunt_ohms, address=I2C_ADDR)
            self._ina.configure()
            self.hardware = True
        except Exception as e:
            print(f"[battery] sensor disabled ({e}); telemetry will report null")

    def read(self):
        if not self.hardware:
            return {"voltage": None, "current_ma": None, "percent": None, "cells": self.cells}
        try:
            v = round(self._ina.voltage(), 2)          # bus voltage (V)
        except Exception:
            return {"voltage": None, "current_ma": None, "percent": None, "cells": self.cells}
        try:
            i = round(self._ina.current(), 1)          # mA (may raise on overflow)
        except Exception:
            i = None
        return {
            "voltage": v,
            "current_ma": i,
            "percent": percent_from_voltage(v, self.cells),
            "cells": self.cells,
        }


if __name__ == "__main__":
    import time

    batt = BatteryMonitor()
    print("hardware:", batt.hardware, "cells:", batt.cells)
    for _ in range(5):
        print(" ", batt.read())
        time.sleep(1)
    print("Done.")

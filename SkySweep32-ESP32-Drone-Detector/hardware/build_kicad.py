#!/usr/bin/env python3
"""
SkySweep32 Pro Tier - KiCad 6 PCB Generator
Generates a complete .kicad_pcb file with proper footprints, nets, and layout.
Board: 120mm x 80mm, 2-layer (F.Cu + B.Cu)
Tier: PRO — ESP32 + NRF24 + CC1101 + RX5808 + OLED + GPS + LoRa + SD
"""

import uuid
from datetime import datetime

# ─── NETS ──────────────────────────────────────────────────────────────────────
# Net index → net name
NETS = {
    0:  "",
    1:  "GND",
    2:  "VCC_5V",
    3:  "VCC_3V3",
    4:  "SPI_MOSI",      # GPIO23
    5:  "SPI_MISO",      # GPIO19
    6:  "SPI_SCK",       # GPIO18
    7:  "NRF_CS",        # GPIO15
    8:  "NRF_CE",        # GPIO2
    9:  "CC_CS",         # GPIO5
    10: "RX_CS",         # GPIO13
    11: "RX_RSSI",       # GPIO34 ADC
    12: "I2C_SDA",       # GPIO21
    13: "I2C_SCL",       # GPIO22
    14: "GPS_RX",        # GPIO16 (ESP RX ← GPS TX)
    15: "GPS_TX",        # GPIO17 (ESP TX → GPS RX)
    16: "LORA_CS",       # GPIO14
    17: "LORA_DIO0",     # GPIO33
    18: "LORA_DIO1",     # GPIO32
    19: "LORA_RST",      # GPIO12
    20: "SD_CS",         # GPIO27
    21: "BUZZER",        # GPIO4
    22: "BAT_ADC",       # GPIO36 (through voltage divider)
    23: "BAT_VRAW",      # Raw battery voltage (before divider)
}

def uid():
    return str(uuid.uuid4())

def net_str(idx):
    if idx == 0:
        return ""
    return f'(net {idx} "{NETS[idx]}")'

# ─── PRIMITIVE HELPERS ─────────────────────────────────────────────────────────

def line(x1, y1, x2, y2, layer, width=0.1):
    return f'  (gr_line (start {x1} {y1}) (end {x2} {y2}) (layer "{layer}") (width {width}) (tstamp {uid()}))'

def arc(cx, cy, sx, sy, angle, layer, width=0.1):
    return f'  (gr_arc (start {cx} {cy}) (end {sx} {sy}) (angle {angle}) (layer "{layer}") (width {width}) (tstamp {uid()}))'

def text(t, x, y, layer, size=1.0, thickness=0.15):
    return f'''  (gr_text "{t}" (at {x} {y}) (layer "{layer}")
    (effects (font (size {size} {size}) (thickness {thickness})))
    (tstamp {uid()}))'''

# ─── BOARD OUTLINE (120×80mm with rounded corners r=3mm) ──────────────────────

def board_outline(w=120, h=80, r=3):
    lines = []
    # Straight edges
    lines.append(line(r, 0,   w-r, 0,   "Edge.Cuts", 0.1))
    lines.append(line(w, r,   w,   h-r, "Edge.Cuts", 0.1))
    lines.append(line(r, h,   w-r, h,   "Edge.Cuts", 0.1))
    lines.append(line(0, r,   0,   h-r, "Edge.Cuts", 0.1))
    # Corner arcs
    lines.append(arc(r,   r,   r,   0,   -90, "Edge.Cuts", 0.1))
    lines.append(arc(w-r, r,   w-r, 0,    90, "Edge.Cuts", 0.1))
    lines.append(arc(w-r, h-r, w,   h-r, -90, "Edge.Cuts", 0.1))
    lines.append(arc(r,   h-r, r,   h,    90, "Edge.Cuts", 0.1))
    return "\n".join(lines)

# ─── MOUNTING HOLE M3 ──────────────────────────────────────────────────────────

def mounting_hole(x, y, ref):
    return f'''  (footprint "MountingHole:MountingHole_3.2mm_M3" (layer "F.Cu")
    (at {x} {y})
    (fp_text reference "{ref}" (at 0 -2.5) (layer "F.Fab")
      (effects (font (size 1 1) (thickness 0.15))) (tstamp {uid()}))
    (fp_text value "MH_M3" (at 0 2.5) (layer "F.Fab")
      (effects (font (size 1 1) (thickness 0.15))) (tstamp {uid()}))
    (fp_circle (center 0 0) (end 2.2 0) (layer "F.Courtyard") (width 0.05) (tstamp {uid()}))
    (fp_circle (center 0 0) (end 1.6 0) (layer "Edge.Cuts") (width 0.1) (tstamp {uid()}))
    (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers *.Cu *.Mask) (tstamp {uid()}))
  )'''

# ─── GENERIC PIN HEADER 1×N ───────────────────────────────────────────────────

def header_1xN(ref, value, x, y, n, net_map=None, angle=0):
    """
    1×N through-hole pin header, 2.54mm pitch.
    net_map: dict {pin_number(1-based): net_index}
    """
    if net_map is None:
        net_map = {}
    pitch = 2.54
    pad_size = 1.7
    drill = 1.0
    courtyard_h = n * pitch + 1.0
    courtyard_w = 2.54 + 1.0

    fp = f'''  (footprint "Connector_PinHeader_2.54mm:PinHeader_1x{n:02d}_P2.54mm_Vertical" (layer "F.Cu")
    (at {x} {y} {angle})
    (fp_text reference "{ref}" (at 0 {-(n*pitch/2 + 1.5)}) (layer "F.Silkscreen")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_text value "{value}" (at 0 {n*pitch/2 + 1.5}) (layer "F.Fab")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_rect (start {-courtyard_w/2} {-pitch/2-0.5}) (end {courtyard_w/2} {(n-1)*pitch+pitch/2+0.5}) (layer "F.Courtyard") (width 0.05) (tstamp {uid()}))
    (fp_rect (start {-1.0} {-pitch/2-0.3}) (end {1.0} {(n-1)*pitch+pitch/2+0.3}) (layer "F.Fab") (width 0.1) (tstamp {uid()}))
'''
    for i in range(1, n+1):
        net_idx = net_map.get(i, 0)
        py = (i-1) * pitch
        shape = "rect" if i == 1 else "oval"
        net_clause = f' {net_str(net_idx)}' if net_idx else ''
        fp += f'    (pad "{i}" thru_hole {shape} (at 0 {py}) (size {pad_size} {pad_size}) (drill {drill}) (layers "*.Cu" "*.Mask"){net_clause} (tstamp {uid()}))\n'
    fp += '  )'
    return fp

# ─── GENERIC PIN HEADER 2×N ───────────────────────────────────────────────────

def header_2xN(ref, value, x, y, n, net_map=None, angle=0):
    """
    2×N dual-row through-hole pin header, 2.54mm pitch.
    net_map: dict {pin_number(1-based): net_index}
    Pin numbering: odd=left column (col 0), even=right column (col 1)
    Rows go top-to-bottom.
    """
    if net_map is None:
        net_map = {}
    pitch = 2.54
    pad_size = 1.7
    drill = 1.0

    fp = f'''  (footprint "Connector_PinHeader_2.54mm:PinHeader_2x{n:02d}_P2.54mm_Vertical" (layer "F.Cu")
    (at {x} {y} {angle})
    (fp_text reference "{ref}" (at 0 {-(n*pitch/2 + 1.5)}) (layer "F.Silkscreen")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_text value "{value}" (at 0 {n*pitch/2 + 1.5}) (layer "F.Fab")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_rect (start {-pitch-0.5} {-pitch/2-0.5}) (end {pitch+0.5} {(n-1)*pitch+pitch/2+0.5}) (layer "F.Courtyard") (width 0.05) (tstamp {uid()}))
'''
    for row in range(n):
        # Left column: pin 2*row+1, at (-1.27, row*pitch)
        # Right column: pin 2*row+2, at (+1.27, row*pitch)
        for col, px_off in enumerate([-1.27, 1.27]):
            pin_num = 2 * row + col + 1
            net_idx = net_map.get(pin_num, 0)
            py = row * pitch
            shape = "rect" if pin_num == 1 else "oval"
            net_clause = f' {net_str(net_idx)}' if net_idx else ''
            fp += f'    (pad "{pin_num}" thru_hole {shape} (at {px_off} {py}) (size {pad_size} {pad_size}) (drill {drill}) (layers "*.Cu" "*.Mask"){net_clause} (tstamp {uid()}))\n'
    fp += '  )'
    return fp

# ─── ESP32 DevKit V1 30-pin socket (2×15) ─────────────────────────────────────
# Left row (L, col A, pin 1-15 top→bottom):
# 1=3V3, 2=EN, 3=GPIO36(VP), 4=GPIO39(VN), 5=GPIO34, 6=GPIO35,
# 7=GPIO32, 8=GPIO33, 9=GPIO25, 10=GPIO26, 11=GPIO27, 12=GPIO14,
# 13=GPIO12, 14=GND, 15=GPIO13
#
# Right row (R, col B, pin 16-30 top→bottom):
# 16=VIN(5V), 17=GND, 18=GPIO22, 19=GPIO21, 20=GPIO0, 21=TX0(1),
# 22=RX0(3), 23=GPIO19, 24=GPIO18, 25=GPIO5, 26=GPIO17, 27=GPIO16,
# 28=GPIO4, 29=GPIO2, 30=GPIO15

def esp32_socket(x, y):
    """
    Two separate 1×15 headers side by side (standard DevKit V1 socket approach).
    Row spacing: 25.4mm (1 inch) between columns.
    """
    pitch = 2.54
    # Left header net map (pin 1-15)
    left_nets = {
        1:  3,   # 3V3 → VCC_3V3
        2:  0,   # EN (no net, user controlled)
        3:  11,  # GPIO36 → RX_RSSI (also BAT_ADC on 22 but 36 is input-only)
        4:  0,   # GPIO39
        5:  11,  # GPIO34 → RX_RSSI
        6:  0,   # GPIO35
        7:  18,  # GPIO32 → LORA_DIO1
        8:  17,  # GPIO33 → LORA_DIO0
        9:  0,   # GPIO25 (DAC1, unused in Pro)
        10: 0,   # GPIO26 (DAC2, unused in Pro)
        11: 20,  # GPIO27 → SD_CS
        12: 16,  # GPIO14 → LORA_CS
        13: 19,  # GPIO12 → LORA_RST
        14: 1,   # GND
        15: 10,  # GPIO13 → RX_CS
    }
    # Right header net map (pin 1-15, maps to ESP32 pins R1-R15)
    right_nets = {
        1:  2,   # VIN → VCC_5V
        2:  1,   # GND
        3:  13,  # GPIO22 → I2C_SCL
        4:  12,  # GPIO21 → I2C_SDA
        5:  0,   # GPIO0
        6:  0,   # GPIO1 (TX0/UART0)
        7:  0,   # GPIO3 (RX0/UART0)
        8:  5,   # GPIO19 → SPI_MISO
        9:  6,   # GPIO18 → SPI_SCK
        10: 9,   # GPIO5  → CC_CS
        11: 15,  # GPIO17 → GPS_TX
        12: 14,  # GPIO16 → GPS_RX
        13: 21,  # GPIO4  → BUZZER
        14: 8,   # GPIO2  → NRF_CE
        15: 7,   # GPIO15 → NRF_CS
    }

    # Left header at (x, y), Right header at (x + 25.4, y)
    parts = []
    parts.append(header_1xN("J_ESP32_L", "ESP32 Left", x, y, 15, left_nets))
    parts.append(header_1xN("J_ESP32_R", "ESP32 Right", x + 25.4, y, 15, right_nets))

    # Pin 1 marker line in silkscreen
    # Silkscreen labels for key pins
    labels = [
        # (label_text, lx, ly) — near the pads
        ("3V3",  x - 4,  y,         "F.Silkscreen"),
        ("GND",  x - 4,  y + 13*2.54, "F.Silkscreen"),
        ("GPIO13", x - 7, y + 14*2.54, "F.Silkscreen"),
        ("VIN",  x + 25.4 + 4, y,  "F.Silkscreen"),
    ]

    return "\n".join(parts)

# ─── AMS1117-3.3V LDO (SOT-223) ───────────────────────────────────────────────

def ams1117(x, y):
    # SOT-223: pins: 1=ADJ/GND, 2=OUTPUT(tab), 3=INPUT, tab=OUTPUT
    # We use it as fixed 3.3V: pin1=GND, pin2/tab=3V3 out, pin3=5V in
    return f'''  (footprint "Package_TO_SOT_SMD:SOT-223-3_TabPin2" (layer "F.Cu")
    (at {x} {y})
    (fp_text reference "U1" (at 0 -4.5) (layer "F.Silkscreen")
      (effects (font (size 1 1) (thickness 0.15))) (tstamp {uid()}))
    (fp_text value "AMS1117-3.3" (at 0 4.5) (layer "F.Fab")
      (effects (font (size 1 1) (thickness 0.15))) (tstamp {uid()}))
    (fp_rect (start -4 -2.5) (end 4 4.5) (layer "F.Courtyard") (width 0.05) (tstamp {uid()}))
    (fp_rect (start -2.3 -1.5) (end 2.3 1.5) (layer "F.Fab") (width 0.1) (tstamp {uid()}))
    (fp_line (start -2.3 -1.5) (end -2.3 1.5) (layer "F.Fab") (width 0.1) (tstamp {uid()}))
    (pad "1" smd rect (at -2.3 1.8) (size 1.5 2.2) (layers "F.Cu" "F.Mask" "F.Paste") {net_str(1)} (tstamp {uid()}))
    (pad "2" smd rect (at 0 1.8) (size 1.5 2.2) (layers "F.Cu" "F.Mask" "F.Paste") {net_str(3)} (tstamp {uid()}))
    (pad "3" smd rect (at 2.3 1.8) (size 1.5 2.2) (layers "F.Cu" "F.Mask" "F.Paste") {net_str(2)} (tstamp {uid()}))
    (pad "4" smd rect (at 0 -1.5) (size 3.6 2.2) (layers "F.Cu" "F.Mask" "F.Paste") {net_str(3)} (tstamp {uid()}))
  )'''

# ─── CAPACITOR SMD 0805 ────────────────────────────────────────────────────────

_cap_count = [0]

def cap_smd(x, y, value, net_a, net_b, ref=None):
    _cap_count[0] += 1
    r = ref or f"C{_cap_count[0]}"
    return f'''  (footprint "Capacitor_SMD:C_0805_2012Metric" (layer "F.Cu")
    (at {x} {y})
    (fp_text reference "{r}" (at 0 -1.5) (layer "F.Silkscreen")
      (effects (font (size 0.6 0.6) (thickness 0.09))) (tstamp {uid()}))
    (fp_text value "{value}" (at 0 1.5) (layer "F.Fab")
      (effects (font (size 0.6 0.6) (thickness 0.09))) (tstamp {uid()}))
    (fp_rect (start -1.8 -1.0) (end 1.8 1.0) (layer "F.Courtyard") (width 0.05) (tstamp {uid()}))
    (pad "1" smd rect (at -1.5 0) (size 1.0 1.2) (layers "F.Cu" "F.Mask" "F.Paste") {net_str(net_a)} (tstamp {uid()}))
    (pad "2" smd rect (at  1.5 0) (size 1.0 1.2) (layers "F.Cu" "F.Mask" "F.Paste") {net_str(net_b)} (tstamp {uid()}))
  )'''

# ─── ELECTROLYTIC CAPACITOR TH ────────────────────────────────────────────────

_ecap_count = [0]

def cap_electrolytic_th(x, y, value, net_pos, net_neg, ref=None):
    _ecap_count[0] += 1
    r = ref or f"CE{_ecap_count[0]}"
    return f'''  (footprint "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm" (layer "F.Cu")
    (at {x} {y})
    (fp_text reference "{r}" (at 0 -4.5) (layer "F.Silkscreen")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_text value "{value}" (at 0 4.5) (layer "F.Fab")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_circle (center 0 0) (end 3.8 0) (layer "F.Courtyard") (width 0.05) (tstamp {uid()}))
    (fp_circle (center 0 0) (end 3.15 0) (layer "F.Fab") (width 0.1) (tstamp {uid()}))
    (fp_line (start -1 -3.15) (end 1 -3.15) (layer "F.Fab") (width 0.3) (tstamp {uid()}))
    (pad "1" thru_hole circle (at -1.25 0) (size 1.8 1.8) (drill 0.8) (layers "*.Cu" "*.Mask") {net_str(net_pos)} (tstamp {uid()}))
    (pad "2" thru_hole oval (at  1.25 0) (size 1.8 1.8) (drill 0.8) (layers "*.Cu" "*.Mask") {net_str(net_neg)} (tstamp {uid()}))
  )'''

# ─── RESISTOR SMD 0805 ────────────────────────────────────────────────────────

_res_count = [0]

def res_smd(x, y, value, net_a, net_b, ref=None):
    _res_count[0] += 1
    r = ref or f"R{_res_count[0]}"
    return f'''  (footprint "Resistor_SMD:R_0805_2012Metric" (layer "F.Cu")
    (at {x} {y})
    (fp_text reference "{r}" (at 0 -1.5) (layer "F.Silkscreen")
      (effects (font (size 0.6 0.6) (thickness 0.09))) (tstamp {uid()}))
    (fp_text value "{value}" (at 0 1.5) (layer "F.Fab")
      (effects (font (size 0.6 0.6) (thickness 0.09))) (tstamp {uid()}))
    (fp_rect (start -1.8 -1.0) (end 1.8 1.0) (layer "F.Courtyard") (width 0.05) (tstamp {uid()}))
    (pad "1" smd rect (at -1.5 0) (size 1.0 1.2) (layers "F.Cu" "F.Mask" "F.Paste") {net_str(net_a)} (tstamp {uid()}))
    (pad "2" smd rect (at  1.5 0) (size 1.0 1.2) (layers "F.Cu" "F.Mask" "F.Paste") {net_str(net_b)} (tstamp {uid()}))
  )'''

# ─── EDGE-MOUNT SMA CONNECTOR ─────────────────────────────────────────────────

_sma_count = [0]

def sma_edge(x, y, ref_label):
    _sma_count[0] += 1
    r = f"J_SMA{_sma_count[0]}"
    # Simplified SMA edge mount footprint
    return f'''  (footprint "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount" (layer "F.Cu")
    (at {x} {y} 90)
    (fp_text reference "{r}" (at 0 -5) (layer "F.Silkscreen")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_text value "{ref_label}" (at 0 5) (layer "F.Fab")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_rect (start -4 -3) (end 4 7) (layer "F.Courtyard") (width 0.05) (tstamp {uid()}))
    (fp_rect (start -2.3 -1.5) (end 2.3 5) (layer "F.Fab") (width 0.1) (tstamp {uid()}))
    (pad "1" thru_hole circle (at 0 0) (size 2.0 2.0) (drill 1.3) (layers "*.Cu" "*.Mask") (tstamp {uid()}))
    (pad "2" thru_hole oval (at -2.54 3.0) (size 2.0 2.0) (drill 1.3) (layers "*.Cu" "*.Mask") {net_str(1)} (tstamp {uid()}))
    (pad "3" thru_hole oval (at  2.54 3.0) (size 2.0 2.0) (drill 1.3) (layers "*.Cu" "*.Mask") {net_str(1)} (tstamp {uid()}))
  )'''

# ─── DC BARREL JACK (5V INPUT) ────────────────────────────────────────────────

def power_jack(x, y):
    return f'''  (footprint "Connector_BarrelJack:BarrelJack_CUI_PJ-102A_Horizontal" (layer "F.Cu")
    (at {x} {y})
    (fp_text reference "J_PWR" (at 0 -6) (layer "F.Silkscreen")
      (effects (font (size 1 1) (thickness 0.15))) (tstamp {uid()}))
    (fp_text value "5V DC IN" (at 0 6) (layer "F.Fab")
      (effects (font (size 1 1) (thickness 0.15))) (tstamp {uid()}))
    (fp_rect (start -5.5 -3.5) (end 5.5 6) (layer "F.Courtyard") (width 0.05) (tstamp {uid()}))
    (pad "1" thru_hole circle (at 0 0) (size 2.4 2.4) (drill 1.5) (layers "*.Cu" "*.Mask") {net_str(2)} (tstamp {uid()}))
    (pad "2" thru_hole oval (at -3.5 0) (size 2.4 2.4) (drill 1.5) (layers "*.Cu" "*.Mask") {net_str(1)} (tstamp {uid()}))
    (pad "3" thru_hole oval (at  3.5 0) (size 2.4 2.4) (drill 1.5) (layers "*.Cu" "*.Mask") {net_str(1)} (tstamp {uid()}))
  )'''

# ─── LED + RESISTOR 0805 ──────────────────────────────────────────────────────

def led_indicator(x, y):
    parts = []
    # Resistor 330Ω between GPIO2 and LED anode
    parts.append(res_smd(x, y, "330R", 8, 0, "R_LED"))  # NRF_CE net (GPIO2)
    # LED
    _led_ref = "LED1"
    parts.append(f'''  (footprint "LED_THT:LED_D3.0mm" (layer "F.Cu")
    (at {x+5} {y})
    (fp_text reference "{_led_ref}" (at 0 -3) (layer "F.Silkscreen")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_text value "LED_RED" (at 0 3) (layer "F.Fab")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_circle (center 0 0) (end 2.5 0) (layer "F.Courtyard") (width 0.05) (tstamp {uid()}))
    (pad "1" thru_hole circle (at -1.27 0) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") (tstamp {uid()}))
    (pad "2" thru_hole oval (at  1.27 0) (size 1.7 1.7) (drill 0.8) (layers "*.Cu" "*.Mask") {net_str(1)} (tstamp {uid()}))
  )''')
    return "\n".join(parts)

# ─── PASSIVE BUZZER ───────────────────────────────────────────────────────────

def buzzer(x, y):
    return f'''  (footprint "Buzzer_Beeper:BZ_12x9.5mm" (layer "F.Cu")
    (at {x} {y})
    (fp_text reference "BZ1" (at 0 -7) (layer "F.Silkscreen")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_text value "BUZZER" (at 0 7) (layer "F.Fab")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_circle (center 0 0) (end 7 0) (layer "F.Courtyard") (width 0.05) (tstamp {uid()}))
    (fp_circle (center 0 0) (end 6 0) (layer "F.Fab") (width 0.1) (tstamp {uid()}))
    (pad "1" thru_hole circle (at  2.54 0) (size 1.8 1.8) (drill 0.8) (layers "*.Cu" "*.Mask") {net_str(21)} (tstamp {uid()}))
    (pad "2" thru_hole oval  (at -2.54 0) (size 1.8 1.8) (drill 0.8) (layers "*.Cu" "*.Mask") {net_str(1)} (tstamp {uid()}))
  )'''

# ─── BATTERY CONNECTOR (JST-PH 2-pin) ────────────────────────────────────────

def bat_connector(x, y):
    return f'''  (footprint "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical" (layer "F.Cu")
    (at {x} {y})
    (fp_text reference "J_BAT" (at 0 -4) (layer "F.Silkscreen")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_text value "LIPO IN" (at 0 4) (layer "F.Fab")
      (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
    (fp_rect (start -2 -2) (end 2 3.5) (layer "F.Courtyard") (width 0.05) (tstamp {uid()}))
    (pad "1" thru_hole rect (at -1.0 0) (size 1.5 1.5) (drill 0.8) (layers "*.Cu" "*.Mask") {net_str(23)} (tstamp {uid()}))
    (pad "2" thru_hole oval (at  1.0 0) (size 1.5 1.5) (drill 0.8) (layers "*.Cu" "*.Mask") {net_str(1)} (tstamp {uid()}))
  )'''

# ─── BOARD TITLE BLOCK ────────────────────────────────────────────────────────

def title_block():
    now = datetime.now().strftime("%Y-%m-%d")
    return f'''  (gr_text "SkySweep32 — Pro Tier Carrier PCB" (at 60 2) (layer "F.Silkscreen")
    (effects (font (size 1.2 1.2) (thickness 0.18))) (tstamp {uid()}))
  (gr_text "v1.0  {now}  GPL-3.0" (at 60 4.5) (layer "F.Silkscreen")
    (effects (font (size 0.8 0.8) (thickness 0.12))) (tstamp {uid()}))
  (gr_text "github.com/bobberdolle1/SkySweep32" (at 60 78) (layer "B.Silkscreen")
    (effects (font (size 0.8 0.8) (thickness 0.12)) (justify mirror)) (tstamp {uid()}))'''

# ─── MASTER PCB ASSEMBLY ──────────────────────────────────────────────────────

def generate_pcb():

    components = []

    # ── Power Section (top-left) ──────────────────────────────────────────────
    # DC Jack at left edge
    components.append(power_jack(8, 15))

    # AMS1117-3.3V LDO (5V→3.3V)
    components.append(ams1117(8, 28))

    # C_IN: 100µF electrolytic on 5V rail (after jack, before LDO)
    components.append(cap_electrolytic_th(15, 22, "100uF/16V", 2, 1, "C_IN"))

    # C_OUT: 10µF after LDO on 3.3V rail
    components.append(cap_electrolytic_th(15, 30, "10uF/10V", 3, 1, "C_OUT"))

    # ── Battery connector ─────────────────────────────────────────────────────
    components.append(bat_connector(8, 38))
    # Voltage divider for battery ADC: 100kΩ from VBAT → middle node → 100kΩ → GND
    # Middle node goes to GPIO36 (BAT_ADC)
    # VRAW (23) → R_BAT1 → BAT_ADC (22) → R_BAT2 → GND (1)
    components.append(res_smd(14, 36, "100k", 23, 22, "R_BAT1"))
    components.append(res_smd(14, 39, "100k", 22, 1,  "R_BAT2"))

    # ── ESP32 DevKit V1 Socket (center) ──────────────────────────────────────
    # Left header at (25, 12), right header at (25+25.4=50.4, 12)
    components.append(esp32_socket(25, 12))

    # ── Decoupling caps for ESP32 3.3V and 5V ────────────────────────────────
    components.append(cap_smd(30, 8, "100nF", 3, 1, "C_ESP32_A"))
    components.append(cap_smd(37, 8, "100nF", 3, 1, "C_ESP32_B"))

    # ── OLED I2C Display Header (1×4) ────────────────────────────────────────
    # Pins: 1=GND, 2=VCC, 3=SCL, 4=SDA
    oled_nets = {1: 1, 2: 3, 3: 13, 4: 12}
    components.append(header_1xN("J_OLED", "OLED SSD1306", 20, 7, 4, oled_nets))
    components.append(cap_smd(20, 3.5, "100nF", 3, 1, "C_OLED"))

    # ── NRF24L01+ 2×4 Header ─────────────────────────────────────────────────
    # Standard pinout (2×4 right-angle or vertical):
    # Pin 1=GND, 2=VCC, 3=CE, 4=CSN, 5=SCK, 6=MOSI, 7=MISO, 8=IRQ(NC)
    nrf_nets = {1:1, 2:3, 3:8, 4:7, 5:6, 6:4, 7:5, 8:0}
    components.append(header_2xN("J_NRF24", "NRF24L01+", 75, 10, 4, nrf_nets))
    # 10µF decoupling cap (NRF24 is known to be sensitive)
    components.append(cap_electrolytic_th(68, 15, "10uF/10V", 3, 1, "C_NRF24_BIG"))
    components.append(cap_smd(68, 10, "100nF", 3, 1, "C_NRF24_100N"))

    # ── CC1101 2×4 Header ─────────────────────────────────────────────────────
    # Pin 1=VCC, 2=GND, 3=MOSI, 4=SCK, 5=MISO, 6=GDO2(NC), 7=GDO0(NC), 8=CS
    cc_nets = {1:3, 2:1, 3:4, 4:6, 5:5, 6:0, 7:0, 8:9}
    components.append(header_2xN("J_CC1101", "CC1101 900MHz", 75, 28, 4, cc_nets))
    components.append(cap_smd(68, 30, "100nF", 3, 1, "C_CC1101"))

    # ── RX5808 1×5 Header ─────────────────────────────────────────────────────
    # Pin 1=5V, 2=GND, 3=RSSI(analog), 4=SPI_DATA(MOSI), 5=SPI_CLK(SCK), 6=CS(SPI_SEL)
    # Note: RX5808 needs 5V!
    rx_nets = {1:2, 2:1, 3:11, 4:4, 5:6, 6:10}
    components.append(header_1xN("J_RX5808", "RX5808 5.8GHz", 75, 46, 6, rx_nets))
    # RX5808 needs a 100µF cap on its 5V line
    components.append(cap_electrolytic_th(68, 48, "100uF/10V", 2, 1, "C_RX5808"))

    # ── GPS NEO-6M 1×4 Header ────────────────────────────────────────────────
    # Pin 1=VCC, 2=RX(GPS), 3=TX(GPS), 4=GND
    # GPS TX → ESP GPIO16 (GPS_RX net), GPS RX ← ESP GPIO17 (GPS_TX net)
    gps_nets = {1:3, 2:15, 3:14, 4:1}
    components.append(header_1xN("J_GPS", "GPS NEO-6M", 25, 62, 4, gps_nets))
    components.append(cap_smd(25, 58, "100nF", 3, 1, "C_GPS"))

    # ── LoRa SX1276 2×5 Header ───────────────────────────────────────────────
    # Common SX1276 module pinout (2×5):
    # 1=GND, 2=GND, 3=VCC, 4=MISO, 5=MOSI, 6=SCK, 7=NSS(CS), 8=DIO0, 9=DIO1, 10=RST
    lora_nets = {1:1, 2:1, 3:3, 4:5, 5:4, 6:6, 7:16, 8:17, 9:18, 10:19}
    components.append(header_2xN("J_LORA", "LoRa SX1276", 42, 62, 5, lora_nets))
    components.append(cap_smd(42, 58, "100nF", 3, 1, "C_LORA"))

    # ── MicroSD Module 1×6 Header ────────────────────────────────────────────
    # Pin 1=VCC(3.3V), 2=GND, 3=CS, 4=MOSI, 5=SCK, 6=MISO
    sd_nets = {1:3, 2:1, 3:20, 4:4, 5:6, 6:5}
    components.append(header_1xN("J_SD", "MicroSD SPI", 62, 62, 6, sd_nets))
    components.append(cap_smd(62, 58, "100nF", 3, 1, "C_SD"))

    # ── Buzzer ────────────────────────────────────────────────────────────────
    components.append(buzzer(88, 62))

    # ── LED indicator ─────────────────────────────────────────────────────────
    components.append(led_indicator(100, 55))

    # ── SMA Connectors (edge-mount, right side of board) ─────────────────────
    # 4 antennas: CC1101 (900MHz), NRF24 (2.4GHz), RX5808 (5.8GHz), LoRa (915MHz)
    components.append(sma_edge(113, 15, "900MHz CC1101"))
    components.append(sma_edge(113, 30, "2.4GHz NRF24"))
    components.append(sma_edge(113, 45, "5.8GHz RX5808"))
    components.append(sma_edge(113, 60, "915MHz LoRa"))

    # ── Mounting Holes ────────────────────────────────────────────────────────
    components.append(mounting_hole(5,   5,  "H1"))
    components.append(mounting_hole(115, 5,  "H2"))
    components.append(mounting_hole(5,   75, "H3"))
    components.append(mounting_hole(115, 75, "H4"))

    # ── Title text ────────────────────────────────────────────────────────────
    components.append(title_block())

    # ── Net declarations ──────────────────────────────────────────────────────
    net_decls = "\n".join(f'  (net {k} "{v}")' for k, v in NETS.items())

    # ── Assemble the full PCB file ────────────────────────────────────────────
    body = "\n".join(components)

    pcb = f"""(kicad_pcb (version 20211014) (generator pcbnew)

  (general
    (thickness 1.6)
    (drawings 0)
    (tracks 0)
    (zones 0)
    (modules {len(components)})
    (nets {len(NETS)})
  )

  (paper "A3")

  (title_block
    (title "SkySweep32 Pro Tier Carrier PCB")
    (date "{datetime.now().strftime('%Y-%m-%d')}")
    (rev "1.0")
    (company "SkySweep32 Project")
    (comment_1 "GPL-3.0 License — Open Hardware")
    (comment_2 "2-Layer PCB, 120x80mm, 1.6mm FR4")
    (comment_3 "Pro Tier: ESP32 + NRF24 + CC1101 + RX5808 + OLED + GPS + LoRa + SD")
  )

  (layers
    (0  "F.Cu"          signal)
    (31 "B.Cu"          signal)
    (34 "B.Mask"        user)
    (35 "F.Mask"        user)
    (36 "B.Silkscreen"  user)
    (37 "F.Silkscreen"  user)
    (40 "B.Courtyard"   user)
    (41 "F.Courtyard"   user)
    (42 "B.Fab"         user)
    (43 "F.Fab"         user)
    (44 "Edge.Cuts"     user)
  )

  (setup
    (stackup
      (layer "F.SilkS" (type "Top Silk Screen"))
      (layer "F.Paste" (type "Top Solder Paste"))
      (layer "F.Mask"  (type "Top Solder Mask") (thickness 0.01))
      (layer "F.Cu"    (type "copper") (thickness 0.035))
      (layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
      (layer "B.Cu"    (type "copper") (thickness 0.035))
      (layer "B.Mask"  (type "Bottom Solder Mask") (thickness 0.01))
      (layer "B.Paste" (type "Bottom Solder Paste"))
      (layer "B.SilkS" (type "Bottom Silk Screen"))
    )
    (pad_to_mask_clearance 0.1)
    (solder_mask_min_width 0.05)
    (pcbplotparams
      (layerselection 0x00010fc_ffffffff)
      (usegerberextensions false)
      (usegerberattributes true)
      (usegerberadvancedattributes true)
      (creategerberjobfile true)
      (svgprecision 6)
      (excludeedgelayer true)
      (plotframeref false)
      (viasonmask false)
      (mode 1)
      (useauxorigin false)
      (hpglpennumber 1)
      (hpglpenspeed 20)
      (hpglpendiameter 15.0)
      (dxfpolygonmode true)
      (dxfimperialunits false)
      (dxfusepcbnewfont true)
      (psnegative false)
      (plotreference true)
      (plotvalue true)
      (plotinvisibletext false)
      (sketchpadsonfab false)
      (subtractmaskfromsilk false)
      (outputformat 1)
      (mirror false)
      (drillshape 1)
      (scaleselection 1)
      (outputdirectory "gerber/")
    )
  )

{net_decls}

{board_outline(120, 80, 3)}

{body}

)
"""
    out_path = "f:/Projects/skysweep32/hardware/skysweep32_pro.kicad_pcb"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(pcb)
    print(f"[OK] Written: {out_path}")
    print(f"     Components placed: {len([c for c in components if 'footprint' in c])}")
    print(f"     Nets defined: {len(NETS)}")
    print(f"     Board: 120mm x 80mm, 2-layer FR4 1.6mm")

if __name__ == "__main__":
    generate_pcb()

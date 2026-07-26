#!/usr/bin/env python3
"""
SkySweep32 Pro — PCB Layout Visualization
Renders a realistic PCB preview matching the .kicad_pcb layout.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.patheffects as pe
from matplotlib.patches import FancyArrowPatch
import numpy as np

# ── STYLE ──────────────────────────────────────────────────────────────────────
plt.rcParams['font.family'] = 'monospace'

fig, ax = plt.subplots(figsize=(18, 12))
fig.patch.set_facecolor('#1a1a1a')
ax.set_facecolor('#1a4a1a')  # PCB green
ax.set_aspect('equal')

W, H = 120, 80  # board dimensions mm

# ── BOARD OUTLINE ──────────────────────────────────────────────────────────────
board = patches.FancyBboxPatch((0, 0), W, H,
    boxstyle="round,pad=0,rounding_size=3",
    linewidth=2, edgecolor='#ffd700', facecolor='#1e5c1e')
ax.add_patch(board)

# Board edge highlight
board_edge = patches.FancyBboxPatch((0.5, 0.5), W-1, H-1,
    boxstyle="round,pad=0,rounding_size=2.5",
    linewidth=1, edgecolor='#2a7a2a', facecolor='none')
ax.add_patch(board_edge)

# ── HELPER FUNCTIONS ───────────────────────────────────────────────────────────

def pad(x, y, w=1.7, h=1.7, color='#c8a000', shape='circle'):
    if shape == 'circle':
        c = plt.Circle((x, y), w/2, color=color, zorder=5)
        ax.add_patch(c)
        # Drill hole
        c2 = plt.Circle((x, y), 0.5, color='#0a2a0a', zorder=6)
        ax.add_patch(c2)
    else:
        r = patches.Rectangle((x-w/2, y-h/2), w, h, color=color, zorder=5)
        ax.add_patch(r)
        c2 = plt.Circle((x, y), 0.5, color='#0a2a0a', zorder=6)
        ax.add_patch(c2)

def smd_pad(x, y, w=1.0, h=1.2, color='#c8a000'):
    r = patches.Rectangle((x-w/2, y-h/2), w, h, color=color, zorder=5)
    ax.add_patch(r)

def header_1xN(label, x, y, n, color='#3a3a3a', pitch=2.54, horiz=False):
    """Draw a 1×N pin header block."""
    if horiz:
        bw = n * pitch + 1
        bh = pitch + 1
        bx, by = x - 0.5, y - (bh/2)
    else:
        bw = pitch + 1
        bh = n * pitch + 1
        bx, by = x - (bw/2), y - 0.5

    rect = patches.FancyBboxPatch((bx, by), bw, bh,
        boxstyle="round,pad=0.2",
        facecolor=color, edgecolor='#888888', linewidth=0.8, zorder=3)
    ax.add_patch(rect)

    for i in range(n):
        if horiz:
            px, py = x + i * pitch, y
        else:
            px, py = x, y + i * pitch
        pad(px, py)

    # Label
    lx = bx + bw/2
    ly = by - 2.5
    ax.text(lx, ly, label, color='white', ha='center', va='top',
            fontsize=5.5, weight='bold',
            path_effects=[pe.withStroke(linewidth=1.5, foreground='black')])

def header_2xN(label, x, y, n, color='#3a3a3a', pitch=2.54):
    """Draw a 2×N pin header block."""
    bw = 2 * pitch + 1
    bh = n * pitch + 1
    bx, by = x - (bw/2), y - 0.5

    rect = patches.FancyBboxPatch((bx, by), bw, bh,
        boxstyle="round,pad=0.2",
        facecolor=color, edgecolor='#888888', linewidth=0.8, zorder=3)
    ax.add_patch(rect)

    for row in range(n):
        for col, ox in enumerate([-pitch/2, pitch/2]):
            # Offset from header center
            px = x + ox - pitch/2 + pitch/2
            py = y + row * pitch
            pad(px, py)

    lx = bx + bw/2
    ly = by - 2.5
    ax.text(lx, ly, label, color='white', ha='center', va='top',
            fontsize=5.5, weight='bold',
            path_effects=[pe.withStroke(linewidth=1.5, foreground='black')])

def comp_box(label, value, x, y, w, h, color='#2a2a6a', edge='#5555cc'):
    """Generic component block (IC, module placeholder)."""
    rect = patches.FancyBboxPatch((x, y), w, h,
        boxstyle="round,pad=0.3",
        facecolor=color, edgecolor=edge, linewidth=1.2, zorder=3)
    ax.add_patch(rect)
    ax.text(x + w/2, y + h/2 + 1, label, color='white', ha='center', va='center',
            fontsize=6, weight='bold')
    ax.text(x + w/2, y + h/2 - 2, value, color='#aaaaff', ha='center', va='center',
            fontsize=4.5)

def mounting_hole(x, y):
    c1 = plt.Circle((x, y), 3.2/2, color='#0a2a0a', zorder=4)
    c2 = plt.Circle((x, y), 3.2/2, color='none', linewidth=1.5,
                     linestyle='--', edgecolor='#ffd700', zorder=5)
    ax.add_patch(c1)
    # Courtyard ring
    c3 = plt.Circle((x, y), 3.5, color='none', linewidth=0.5,
                     linestyle='--', edgecolor='#ff8800', zorder=5)
    ax.add_patch(patches.Circle((x, y), 3.2/2,
                                 fill=False, edgecolor='#ffd700',
                                 linewidth=1, linestyle='--', zorder=6))

def power_trace(x1, y1, x2, y2, color='#ff4444', width=2):
    ax.plot([x1, x2], [y1, y2], color=color, linewidth=width,
            zorder=2, solid_capstyle='round')

def gnd_trace(x1, y1, x2, y2, width=1.5):
    ax.plot([x1, x2], [y1, y2], color='#4488ff', linewidth=width,
            zorder=2, solid_capstyle='round')

def spi_trace(x1, y1, x2, y2):
    ax.plot([x1, x2], [y1, y2], color='#ffaa00', linewidth=0.8,
            zorder=2, linestyle='--', alpha=0.7)

def silk_label(x, y, text, size=5, color='#ccffcc', angle=0):
    ax.text(x, y, text, color=color, ha='center', va='center',
            fontsize=size, rotation=angle, style='italic',
            path_effects=[pe.withStroke(linewidth=1, foreground='#0a2a0a')])

def sma_connector(x, y, label):
    """Edge-mount SMA connector."""
    rect = patches.Rectangle((x-4, y-3), 8, 6,
        facecolor='#888888', edgecolor='#dddddd', linewidth=1.5, zorder=4)
    ax.add_patch(rect)
    c = plt.Circle((x, y), 1.5, color='#c8a000', zorder=5)
    ax.add_patch(c)
    c2 = plt.Circle((x, y), 0.6, color='#cccccc', zorder=6)
    ax.add_patch(c2)
    ax.text(x - 6, y, label, color='#ffff88', ha='right', va='center',
            fontsize=4.5, weight='bold')

# ── MOUNTING HOLES ─────────────────────────────────────────────────────────────
for mx, my in [(5, 5), (115, 5), (5, 75), (115, 75)]:
    mounting_hole(mx, my)
    ax.text(mx, my - 5, 'M3', color='#ffaa00', ha='center', va='top', fontsize=4)

# ── POWER SECTION (top-left) ──────────────────────────────────────────────────
# DC Jack
comp_box('J_PWR', '5V DC IN', 3, 10, 10, 8, '#5a2a00', '#ff8800')
silk_label(8, 19.5, '5V IN', 4.5, '#ffcc88')

# AMS1117 LDO
comp_box('U1', 'AMS1117-3.3', 3, 24, 10, 6, '#2a2a5a', '#8888ff')
silk_label(8, 31.5, 'LDO 3.3V', 4.5, '#aaaaff')

# Electrolytic caps
for cx, cy, cv in [(16, 19, '100µF'), (16, 27, '10µF')]:
    c = plt.Circle((cx, cy), 2.5, color='#555500', edgecolor='#aaaa00', linewidth=1, zorder=3)
    ax.add_patch(c)
    ax.text(cx, cy - 4, cv, color='#ffff88', ha='center', va='top', fontsize=4)

# Battery connector
comp_box('J_BAT', 'JST-PH\nLiPo', 3, 34, 7, 6, '#5a1a00', '#ff6600')
# Voltage divider resistors
for rx, ry, rv in [(13, 33, '100k'), (13, 37, '100k')]:
    r = patches.Rectangle((rx-1.5, ry-0.6), 3, 1.2, color='#4a3a00', edgecolor='#aaaa00', linewidth=0.8, zorder=3)
    ax.add_patch(r)
    ax.text(rx, ry - 1.8, rv, color='#ffff88', ha='center', va='top', fontsize=4)
silk_label(10, 41, 'BAT DIV', 4, '#ffcc88')

# ── DECOUPLING CAPS (small SMD, near ESP32) ───────────────────────────────────
for cx, cy in [(30, 7.5), (37, 7.5)]:
    ax.add_patch(patches.Rectangle((cx-1, cy-0.6), 2, 1.2, facecolor='#554400', edgecolor='#aaaa00', linewidth=0.5, zorder=3))
    ax.text(cx, cy + 1.5, '100n', color='#ffff88', ha='center', va='bottom', fontsize=3.5)

# ── ESP32 DevKit V1 SOCKET (center) ───────────────────────────────────────────
# ESP32 module placeholder
comp_box('ESP32', 'DevKit V1\n240MHz dual-core\nWiFi + BLE',
         22, 9, 30, 42, '#1a2a5a', '#4488ff')
silk_label(37, 52.5, 'GPIO SOCKET', 5, '#88aaff')

# Left headers
header_1xN('L-ROW\n3V3..GPIO13', 25, 11, 15, color='#253a6a')
# Right headers
header_1xN('R-ROW\nVIN..GPIO15', 50, 11, 15, color='#253a6a')

# Pin labels for key ESP32 pins
for px, py, lbl in [(28, 11, '3V3'), (28, 11+13*2.54, 'GND'),
                     (53, 11, 'VIN'), (53, 11+2.54, 'GND'),
                     (53, 11+7*2.54, 'MISO'), (53, 11+8*2.54, 'SCK')]:
    ax.text(px, py, lbl, color='#aaddff', va='center', fontsize=3.5)

# ── NRF24L01+ 2×4 HEADER (top-right) ─────────────────────────────────────────
comp_box('', '', 71, 8.5, 10, 11, '#1a4a1a', '#44aa44')
header_2xN('J_NRF24\nNRF24L01+\n2.4 GHz', 76, 10, 4, '#1a4a1a')
ax.add_patch(patches.Circle((68, 13), 2, facecolor='#555500', edgecolor='#aaaa00', linewidth=0.8, zorder=3))
ax.add_patch(patches.Rectangle((66, 9), 2, 1.2, facecolor='#554400', edgecolor='#aaaa00', linewidth=0.5, zorder=3))
silk_label(76, 21, '10µF+100nF', 4, '#88ff88')

# ── CC1101 2×4 HEADER ─────────────────────────────────────────────────────────
comp_box('', '', 71, 26.5, 10, 11, '#4a1a1a', '#aa4444')
header_2xN('J_CC1101\nCC1101\n900 MHz', 76, 28, 4, '#4a1a1a')
ax.add_patch(patches.Rectangle((67, 30), 2, 1.2, facecolor='#554400', edgecolor='#aaaa00', linewidth=0.5, zorder=3))
silk_label(76, 39, '100nF', 4, '#ff8888')

# ── RX5808 1×6 HEADER ─────────────────────────────────────────────────────────
comp_box('', '', 71, 44, 10, 17, '#4a2a00', '#cc6600')
header_1xN('J_RX5808\nRX5808\n5.8 GHz', 76, 45, 6, color='#4a2a00')
ax.add_patch(patches.Circle((68, 49), 2.5, facecolor='#555500', edgecolor='#aaaa00', linewidth=0.8, zorder=3))
ax.text(68, 53, '100µF\n5V!', color='#ffaa44', ha='center', va='bottom', fontsize=3.5)

# ── GPS NEO-6M 1×4 HEADER (bottom-left) ──────────────────────────────────────
comp_box('', '', 21, 60, 10, 11, '#1a3a4a', '#44aacc')
header_1xN('J_GPS\nNEO-6M\nUART', 26, 62, 4, color='#1a3a4a')
ax.add_patch(patches.Rectangle((21, 59), 2, 1.2, facecolor='#554400', edgecolor='#aaaa00', linewidth=0.5, zorder=3))

# ── LoRa SX1276 2×5 HEADER (bottom-center) ────────────────────────────────────
comp_box('', '', 38, 60, 12, 15, '#3a1a4a', '#aa44cc')
header_2xN('J_LORA\nSX1276\n915 MHz', 44, 62, 5, '#3a1a4a')
ax.add_patch(patches.Rectangle((38, 59), 2, 1.2, facecolor='#554400', edgecolor='#aaaa00', linewidth=0.5, zorder=3))

# ── MicroSD 1×6 HEADER (bottom-right area) ────────────────────────────────────
comp_box('', '', 58, 60, 10, 17, '#2a3a2a', '#66aa66')
header_1xN('J_SD\nMicroSD\nSPI', 63, 62, 6, color='#2a3a2a')
ax.add_patch(patches.Rectangle((58, 59), 2, 1.2, facecolor='#554400', edgecolor='#aaaa00', linewidth=0.5, zorder=3))

# ── BUZZER ────────────────────────────────────────────────────────────────────
ax.add_patch(patches.Circle((88, 65), 4.5, facecolor='#2a2a2a', edgecolor='#888888', linewidth=1.5, zorder=3))
ax.text(88, 65, 'BZ1', color='white', ha='center', va='center', fontsize=5, weight='bold')
ax.text(88, 71, 'BUZZER\nGPIO4', color='#cccccc', ha='center', va='bottom', fontsize=4)
pad(86, 65); pad(90, 65)

# ── LED + RESISTOR ────────────────────────────────────────────────────────────
ax.add_patch(patches.Rectangle((97, 53), 3, 1.2, facecolor='#4a3a00', edgecolor='#aaaa00', linewidth=0.8, zorder=3))
ax.text(98.5, 52, '330Ω\nR_LED', color='#ffff88', ha='center', va='top', fontsize=4)
ax.add_patch(patches.Circle((103, 54), 1.5, facecolor='#cc2200', edgecolor='#ff4444', linewidth=1.5, zorder=3))
ax.text(103, 51.5, 'LED1\nGPIO2', color='#ff8888', ha='center', va='top', fontsize=4)
pad(101.5, 54); pad(104.5, 54)

# ── SMA EDGE-MOUNT CONNECTORS (right edge) ────────────────────────────────────
for sy, slabel in [(13, '900 MHz\n(CC1101)'), (28, '2.4 GHz\n(NRF24)'),
                   (46, '5.8 GHz\n(RX5808)'), (61, '915 MHz\n(LoRa)')]:
    sma_connector(116, sy, slabel)

# ── OLED HEADER 1×4 ────────────────────────────────────────────────────────────
header_1xN('J_OLED\n0.96" SSD1306 I2C', 20, 7, 4, color='#2a2a3a', horiz=True)

# ── POWER & GND TRACES ────────────────────────────────────────────────────────
# 5V rail: jack → LDO in
power_trace(8, 14, 8, 24, '#ff4444', 1.5)
# 3.3V rail: LDO out → right (horizontal bus)
power_trace(13, 27, 22, 27, '#ff8800', 1.5)
power_trace(22, 27, 22, 9, '#ff8800', 1.5)  # up to ESP32 area
# GND bus (horizontal, bottom area)
gnd_trace(3, 4, 117, 4, 1.5)

# SPI bus traces (orange dashed)
spi_trace(52, 25, 70, 12)   # MOSI to NRF24
spi_trace(52, 25, 70, 30)   # MOSI to CC1101
spi_trace(52, 25, 70, 48)   # MOSI to RX5808

# ── TITLE & LEGEND ────────────────────────────────────────────────────────────
ax.text(60, 78.5, 'SkySweep32  —  Pro Tier Carrier PCB  |  120×80mm  |  2-Layer FR4  |  v1.0',
        color='#ccffcc', ha='center', va='bottom', fontsize=7, weight='bold',
        path_effects=[pe.withStroke(linewidth=2, foreground='#0a2a0a')])

ax.text(60, 1.5, 'github.com/bobberdolle1/SkySweep32  |  GPL-3.0 Open Hardware',
        color='#88cc88', ha='center', va='bottom', fontsize=5, style='italic')

# Legend box
legend_items = [
    (patches.Patch(color='#1a2a5a', label='ESP32 DevKit V1')),
    (patches.Patch(color='#1a4a1a', label='NRF24L01+ 2.4GHz')),
    (patches.Patch(color='#4a1a1a', label='CC1101 900MHz')),
    (patches.Patch(color='#4a2a00', label='RX5808 5.8GHz')),
    (patches.Patch(color='#1a3a4a', label='GPS NEO-6M')),
    (patches.Patch(color='#3a1a4a', label='LoRa SX1276')),
    (patches.Patch(color='#2a3a2a', label='MicroSD SPI')),
    (patches.Patch(color='#5a2a00', label='Power Section')),
]
leg = ax.legend(handles=legend_items, loc='upper right',
                fontsize=5.5, framealpha=0.85,
                facecolor='#0a1a0a', labelcolor='white',
                edgecolor='#44aa44', title='Components',
                title_fontsize=6)
leg.get_title().set_color('#88ff88')

ax.set_xlim(-5, 130)
ax.set_ylim(-8, 85)
ax.axis('off')

# Grid ticks for scale reference
for gx in range(0, 121, 10):
    ax.axvline(gx, color='#2a5a2a', linewidth=0.3, alpha=0.4, zorder=0)
    ax.text(gx, -1, f'{gx}', color='#4a8a4a', ha='center', va='top', fontsize=3.5)
for gy in range(0, 81, 10):
    ax.axhline(gy, color='#2a5a2a', linewidth=0.3, alpha=0.4, zorder=0)
    ax.text(-1, gy, f'{gy}', color='#4a8a4a', ha='right', va='center', fontsize=3.5)

plt.tight_layout(pad=0.2)
plt.savefig('f:/Projects/skysweep32/hardware/pcb_layout_preview.png',
            dpi=180, bbox_inches='tight',
            facecolor='#1a1a1a', edgecolor='none')
print("Saved: pcb_layout_preview.png")

#!/usr/bin/env python3
"""Parse OSD element layout from a Betaflight CLI backup.

Betaflight 4.5 encodes each ``osd_<element>_pos`` as a 16-bit value:

  column  = (v & 0x1F) | ((v & 0x400) >> 5)   # 6-bit col; bit10 is the HD high bit
  row     = (v >> 5) & 0x1F                    # 5-bit row
  visible = (v & 0x3800) != 0                  # profile bits 11/12/13

An element is only drawn if at least one OSD profile bit is set, so elements
left at their default value (e.g. GPS on a drone with no GPS) are hidden.
"""
import re

OSD_PROFILE_MASK = 0x3800  # bits 11,12,13

# Elements whose on-screen value is a plain number (extract the numeric token).
NUMERIC_ELEMENTS = {
    'avg_cell_voltage', 'vbat', 'current', 'mah_drawn', 'throttle',
    'rssi_dbm', 'core_temp', 'sys_vtx_temp',
    'altitude', 'power', 'g_force', 'esc_tmp',
}

# Purely graphical elements — no textual value worth extracting to a column.
GRAPHIC_ELEMENTS = {
    'crosshairs', 'flip_arrow', 'ah', 'ah_sbar', 'camera_frame',
    'up_down_reference', 'compass_bar', 'home_dir', 'nvario',
    'stick_overlay_left', 'stick_overlay_right', 'nheading',
}

# Human-friendly labels for the common elements.
LABELS = {
    'avg_cell_voltage': 'cell_V',
    'vbat': 'vbat_V',
    'current': 'current_A',
    'mah_drawn': 'mah',
    'throttle': 'throttle',
    'rssi_dbm': 'rssi_dbm',
    'link_quality': 'link_quality',
    'core_temp': 'core_temp_C',
    'sys_vtx_temp': 'vtx_temp_C',
    'tim_1': 'timer1',
    'tim_2': 'timer2',
    'flymode': 'flight_mode',
    'warnings': 'warnings',
    'disarmed': 'disarmed',
    'rate_profile_name': 'rate_profile',
    'pid_profile_name': 'pid_profile',
    'craft_name': 'craft_name',
}

_POS_RE = re.compile(r'^set\s+osd_(\w+?)_pos\s*=\s*(\d+)', re.MULTILINE)


def decode_pos(value):
    """Return (col, row, visible) for a Betaflight OSD position value."""
    col = (value & 0x1F) | ((value & 0x400) >> 5)
    row = (value >> 5) & 0x1F
    visible = bool(value & OSD_PROFILE_MASK)
    return col, row, visible


class OsdElement:
    __slots__ = ('name', 'value', 'col', 'row', 'visible')

    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.col, self.row, self.visible = decode_pos(value)

    @property
    def label(self):
        return LABELS.get(self.name, self.name)

    @property
    def numeric(self):
        return self.name in NUMERIC_ELEMENTS

    @property
    def graphic(self):
        return self.name in GRAPHIC_ELEMENTS

    def __repr__(self):
        return 'OsdElement({!r}, col={}, row={}, visible={})'.format(
            self.name, self.col, self.row, self.visible)


def parse_config(path):
    """Read a CLI backup and return {name: OsdElement} for all osd_*_pos lines."""
    with open(path, 'r', encoding='utf-8', errors='replace') as fp:
        text = fp.read()
    elements = {}
    for name, raw in _POS_RE.findall(text):
        elements[name] = OsdElement(name, int(raw))
    if not elements:
        raise ValueError('{}: no "set osd_*_pos" lines found'.format(path))
    return elements


def visible_elements(elements):
    """Return visible elements sorted by (row, col)."""
    vis = [e for e in elements.values() if e.visible]
    return sorted(vis, key=lambda e: (e.row, e.col))


if __name__ == '__main__':
    import sys
    for e in visible_elements(parse_config(sys.argv[1])):
        print('{:>4} {:>4}  {:<18} (raw {})'.format(e.col, e.row, e.name, e.value))

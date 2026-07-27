#!/usr/bin/env python3
"""Decode Walksnail Avatar `.osd` recordings to plain text.

These files use the Walksnail Avatar goggle format (magic ``BTFL``), which is
different from the msp-osd / DJI ``MSPOSD`` format that pymsposd targets.

Layout (verified against the sample recordings):
  * 40-byte file header, starting with b"BTFL".
    - offset 36: grid width  (uint16, = 53)
    - offset 38: grid height (uint16, = 20)
  * A sequence of fixed-size frames, each:
    - uint32 little-endian timestamp in milliseconds
    - width*height uint16 little-endian glyph codes, row-major

Glyph codes in the printable ASCII range (0x20..0x7E) map directly to that
character; code 0 is an empty cell; anything else is a font-specific icon glyph
(satellite, home, antenna, etc.) with no ASCII equivalent.
"""
import argparse
import os
import re
import struct
import sys

import btfl_osd_config

_NUM_RE = re.compile(r'-?\d+(?:\.\d+)?')

MAGIC = b'BTFL'
HEADER_SIZE = 40
BLANK_CODE = 0
# Placeholder for icon glyphs that have no printable ASCII representation.
ICON_PLACEHOLDER = '·'  # middle dot, keeps column alignment intact


def glyph_char(code):
    """Map a glyph code to a printable character or None (blank/icon).

    Betaflight font pages are style variants sharing one character map, so the
    low byte holds the character regardless of page (e.g. 0x337 is a bold '7').
    """
    if code == BLANK_CODE:
        return None
    low = code & 0xFF
    return chr(low) if 0x20 <= low < 0x7f else None


class OsdFile:
    """Reader for a single Walksnail Avatar .osd recording."""

    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as fp:
            header = fp.read(HEADER_SIZE)
        if len(header) < HEADER_SIZE or header[:4] != MAGIC:
            raise ValueError(
                '{}: not a Walksnail Avatar OSD file (expected magic {!r}, got {!r})'.format(
                    path, MAGIC, header[:4]))
        self.width, self.height = struct.unpack_from('<HH', header, 36)
        if not (0 < self.width <= 120 and 0 < self.height <= 60):
            raise ValueError('{}: implausible grid {}x{}'.format(path, self.width, self.height))
        self.cells = self.width * self.height
        self.frame_size = 4 + self.cells * 2
        body = os.path.getsize(path) - HEADER_SIZE
        if body < 0 or body % self.frame_size != 0:
            raise ValueError(
                '{}: file body ({} bytes) is not a whole number of {}-byte frames'.format(
                    path, body, self.frame_size))
        self.frame_count = body // self.frame_size

    def frames(self):
        """Yield (timestamp_ms, glyph_tuple) for every frame in order."""
        cell_fmt = '<{}H'.format(self.cells)
        with open(self.path, 'rb') as fp:
            fp.seek(HEADER_SIZE)
            for _ in range(self.frame_count):
                raw = fp.read(self.frame_size)
                if len(raw) != self.frame_size:
                    break
                ts = struct.unpack_from('<I', raw, 0)[0]
                glyphs = struct.unpack_from(cell_fmt, raw, 4)
                yield ts, glyphs

    def _row_chars(self, glyphs, row):
        """Row as chars; blank cells (code 0) and icon glyphs become spaces."""
        base = row * self.width
        out = []
        for c in range(self.width):
            ch = glyph_char(glyphs[base + c])
            out.append(ch if ch is not None else ' ')
        return out

    def extract_at(self, glyphs, col, row, max_gap=1, window=9):
        """Read the text field an OSD element draws starting at (col, row).

        Values may be right-aligned a few cells past ``col`` and may contain a
        single internal space between an icon and its number, so we skip up to
        ``window`` leading blanks then read until ``max_gap+1`` blanks in a row.
        """
        if row >= self.height:
            return ''
        line = self._row_chars(glyphs, row)
        c = col
        while c < self.width and line[c] == ' ' and c - col < window:
            c += 1
        if c >= self.width or line[c] == ' ':
            return ''
        chars = []
        gap = 0
        while c < self.width:
            if line[c] == ' ':
                gap += 1
                if gap > max_gap:
                    break
                chars.append(' ')
            else:
                gap = 0
                chars.append(line[c])
            c += 1
        return ''.join(chars).strip()

    def extract_fields(self, glyphs, elements):
        """Return {label: value} for visible, non-graphic elements."""
        values = {}
        for e in elements:
            if e.graphic:
                continue
            text = self.extract_at(glyphs, e.col, e.row)
            if e.numeric:
                m = _NUM_RE.search(text)
                text = m.group(0) if m else ''
            values[e.label] = text
        return values

    def render(self, glyphs):
        """Render a glyph tuple to a list of text rows (trailing spaces stripped)."""
        rows = []
        for r in range(self.height):
            base = r * self.width
            chars = []
            for c in range(self.width):
                code = glyphs[base + c]
                if code == BLANK_CODE:
                    chars.append(' ')
                else:
                    ch = glyph_char(code)
                    chars.append(ch if ch is not None else ICON_PLACEHOLDER)
            rows.append(''.join(chars).rstrip())
        return rows


def fmt_time(ms):
    total = ms / 1000.0
    m, s = divmod(total, 60)
    h, m = divmod(int(m), 60)
    return '{:02d}:{:02d}:{:06.3f}'.format(h, int(m), s)


def export(osd_path, out_path, dedupe=True, keep_blank=False):
    osd = OsdFile(osd_path)
    written = 0
    prev_rows = None
    with open(out_path, 'w', encoding='utf-8') as out:
        out.write('# {}\n'.format(os.path.basename(osd_path)))
        out.write('# grid {}x{}, {} frames\n'.format(osd.width, osd.height, osd.frame_count))
        out.write('# columns: time is the on-screen timestamp of the frame\n\n')
        for ts, glyphs in osd.frames():
            rows = osd.render(glyphs)
            content = [r for r in rows if r] if not keep_blank else rows
            if dedupe and rows == prev_rows:
                continue
            prev_rows = rows
            out.write('===== t={} (t_ms={}) =====\n'.format(fmt_time(ts), ts))
            if content:
                out.write('\n'.join(content) + '\n')
            out.write('\n')
            written += 1
    return osd, written


def export_csv(osd_path, out_path, config_path, sep=','):
    """Extract labelled OSD telemetry to CSV using a Betaflight config layout."""
    osd = OsdFile(osd_path)
    elements = btfl_osd_config.visible_elements(btfl_osd_config.parse_config(config_path))
    cols = [e.label for e in elements if not e.graphic]
    with open(out_path, 'w', encoding='utf-8', newline='') as out:
        out.write(sep.join(['time', 't_ms'] + cols) + '\n')
        rows = 0
        for ts, glyphs in osd.frames():
            values = osd.extract_fields(glyphs, elements)
            fields = [fmt_time(ts), str(ts)] + [values.get(c, '') for c in cols]
            fields = [f.replace(sep, ' ') for f in fields]
            out.write(sep.join(fields) + '\n')
            rows += 1
    return osd, cols, rows


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Export Walksnail Avatar .osd recordings to plain text.')
    parser.add_argument('inputs', metavar='OSDFILE', nargs='+', help='input .osd file(s)')
    parser.add_argument('-o', dest='output', help='output .txt file (single input only)')
    parser.add_argument('--all-frames', action='store_true',
                        help='write every frame, even when the screen is unchanged')
    parser.add_argument('--keep-blank', action='store_true',
                        help='keep fully blank rows within each frame')
    parser.add_argument('--config', metavar='CLI_BACKUP',
                        help='Betaflight CLI backup .txt; enables labelled CSV export '
                             'of OSD telemetry instead of the raw text grid')
    args = parser.parse_args(argv)

    if args.output and len(args.inputs) > 1:
        parser.error('-o cannot be used with multiple input files')

    rc = 0
    for src in args.inputs:
        try:
            if args.config:
                dst = args.output or (os.path.splitext(src)[0] + '.csv')
                osd, cols, rows = export_csv(src, dst, args.config)
                print('{} -> {}  ({} frames, {} fields: {})'.format(
                    src, dst, rows, len(cols), ', '.join(cols)))
            else:
                dst = args.output or (os.path.splitext(src)[0] + '.txt')
                osd, written = export(src, dst, dedupe=not args.all_frames,
                                      keep_blank=args.keep_blank)
                print('{} -> {}  ({} frames, {} screens written)'.format(
                    src, dst, osd.frame_count, written))
        except (ValueError, OSError) as exc:
            print('ERROR: {}'.format(exc), file=sys.stderr)
            rc = 1
            continue
    return rc


if __name__ == '__main__':
    sys.exit(main())

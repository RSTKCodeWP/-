#!/usr/bin/env python3
"""Round-trip test for the Walksnail OSD decoder."""
import os
import struct
import tempfile

import walksnail_osd as w


def build_osd(frames, width=53, height=20):
    """frames: list of (ts_ms, {(row,col): code})."""
    header = bytearray(w.HEADER_SIZE)
    header[:4] = w.MAGIC
    struct.pack_into('<HH', header, 36, width, height)
    out = bytearray(header)
    for ts, cells in frames:
        glyphs = [0] * (width * height)
        for (r, c), code in cells.items():
            glyphs[r * width + c] = code
        out += struct.pack('<I', ts)
        out += struct.pack('<{}H'.format(width * height), *glyphs)
    return bytes(out)


def test_parse_and_render():
    text = {(0, i): ord(ch) for i, ch in enumerate('HELLO')}
    text[(1, 0)] = 0x301  # icon glyph (low byte 0x01) -> placeholder
    data = build_osd([(0, text), (1500, text)])
    with tempfile.NamedTemporaryFile('wb', suffix='.osd', delete=False) as fp:
        fp.write(data)
        path = fp.name
    try:
        osd = w.OsdFile(path)
        assert (osd.width, osd.height) == (53, 20)
        assert osd.frame_count == 2
        first_ts, glyphs = next(osd.frames())
        assert first_ts == 0
        rows = osd.render(glyphs)
        assert rows[0] == 'HELLO'
        assert rows[1] == w.ICON_PLACEHOLDER
    finally:
        os.unlink(path)


def test_rejects_wrong_magic():
    with tempfile.NamedTemporaryFile('wb', suffix='.osd', delete=False) as fp:
        fp.write(b'MSPOSD\x00' + b'\x00' * 60)
        path = fp.name
    try:
        raised = False
        try:
            w.OsdFile(path)
        except ValueError:
            raised = True
        assert raised, 'expected ValueError for non-Walksnail magic'
    finally:
        os.unlink(path)


def test_dedupe_collapses_identical_frames():
    cells = {(0, 0): ord('A')}
    data = build_osd([(0, cells), (100, cells), (200, {(0, 0): ord('B')})])
    with tempfile.NamedTemporaryFile('wb', suffix='.osd', delete=False) as fp:
        fp.write(data)
        src = fp.name
    dst = src + '.txt'
    try:
        _, written = w.export(src, dst, dedupe=True)
        assert written == 2, 'identical consecutive frames should collapse'
    finally:
        os.unlink(src)
        if os.path.exists(dst):
            os.unlink(dst)


def test_decode_pos():
    import btfl_osd_config as cfg
    # flymode = 3504 -> col 48, row 13, visible (verified against a real frame)
    assert cfg.decode_pos(3504) == (48, 13, True)
    # avg_cell_voltage = 2401 -> col 1, row 11, visible
    assert cfg.decode_pos(2401) == (1, 11, True)
    # default hidden value 234 -> no profile bit set
    assert cfg.decode_pos(234)[2] is False


def test_glyph_char_font_pages():
    # low byte carries the character across font pages
    assert w.glyph_char(ord('7')) == '7'
    assert w.glyph_char(0x337) == '7'   # bold-page '7'
    assert w.glyph_char(0x32D) == '-'   # bold-page '-'
    assert w.glyph_char(0) is None      # blank
    assert w.glyph_char(0x301) is None  # icon (low byte 0x01)


def test_numeric_extraction_skips_icon_and_space():
    # 'Cz 47' with an icon prefix -> numeric field yields 47
    W = 53
    glyphs = [0] * (W * 20)
    for i, ch in enumerate('Cz 47'):
        glyphs[3 * W + 47 + i] = ord(ch)
    import btfl_osd_config as cfg
    el = cfg.OsdElement('core_temp', 3183)  # col 47, row 3

    class Dummy(w.OsdFile):
        def __init__(self):
            self.width, self.height = W, 20

    d = Dummy()
    vals = d.extract_fields(tuple(glyphs), [el])
    assert vals['core_temp_C'] == '47'


if __name__ == '__main__':
    test_parse_and_render()
    test_rejects_wrong_magic()
    test_dedupe_collapses_identical_frames()
    test_decode_pos()
    test_glyph_char_font_pages()
    test_numeric_extraction_skips_icon_and_space()
    print('all tests passed')

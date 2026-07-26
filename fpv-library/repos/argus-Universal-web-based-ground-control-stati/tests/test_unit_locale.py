"""Tests for backend/locale_text.py — bilingual event text lookup."""

from backend.locale_text import _T, lt


class TestLt:
    def test_default_returns_chinese(self):
        assert lt("connected") == "已连接 (sysid=%d)"

    def test_english_locale(self):
        assert lt("connected", "en") == "Connected (sysid=%d)"

    def test_unknown_key_returns_key(self):
        assert lt("nonexistent_key_xyz") == "nonexistent_key_xyz"

    def test_unknown_key_with_en(self):
        assert lt("nonexistent_key_xyz", "en") == "nonexistent_key_xyz"


class TestTextTable:
    def test_all_entries_are_pairs(self):
        for key, pair in _T.items():
            assert isinstance(pair, tuple), f"{key}: expected tuple, got {type(pair)}"
            assert len(pair) == 2, f"{key}: expected 2-tuple, got {len(pair)}-tuple"

    def test_all_values_are_strings(self):
        for key, (zh, en) in _T.items():
            assert isinstance(zh, str), f"{key} zh: not a string"
            assert isinstance(en, str), f"{key} en: not a string"

    def test_no_empty_values(self):
        for key, (zh, en) in _T.items():
            assert len(zh) > 0, f"{key} zh: empty"
            assert len(en) > 0, f"{key} en: empty"

    def test_key_count(self):
        assert len(_T) >= 50


class TestSyncLocalesEscaping:
    """Tests for the _escape_ts helper in scripts/sync_locales.py."""

    def test_apostrophe_escaped(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from sync_locales import _escape_ts
        assert _escape_ts("it's here") == r"it\'s here"

    def test_backslash_escaped(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from sync_locales import _escape_ts
        assert _escape_ts("path\\to\\file") == r"path\\to\\file"

    def test_plain_string_unchanged(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from sync_locales import _escape_ts
        assert _escape_ts("Hello World") == "Hello World"

    def test_escape_unescape_round_trip(self):
        """Running --write twice must not double-escape — _unescape_ts inverts _escape_ts."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from sync_locales import _escape_ts, _unescape_ts
        for raw in ("it's here", "path\\to\\file", "Hello", "\\'", "'\\", "a\\b'c"):
            assert _unescape_ts(_escape_ts(raw)) == raw, f"round-trip failed for {raw!r}"


class TestLocaleFormatStrings:
    # Matches Python %-format conversions: optional %(name), flags, width, .precision, length, then conversion letter.
    # Doesn't match %% — that's a literal percent, not a real specifier.
    _CONVERSION = r'(?:\([^)]+\))?[-+#0 ]*\d*\.?\d*[hlL]?[diouxXeEfFgGcrsab]'

    def test_no_bare_double_percent_in_non_format_strings(self):
        """Strings with %% but no format specifier produce literal %% in the UI."""
        import re
        has_format = re.compile(r'%' + self._CONVERSION)
        for key, (zh, en) in _T.items():
            for locale_str in (zh, en):
                if '%%' in locale_str:
                    assert has_format.search(locale_str), (
                        f"Key '{key}' has '%%' but no format specifier — "
                        "use a single '%' instead, or add the matching specifier"
                    )

    def test_format_arg_counts_match_between_locales(self):
        """zh and en strings for the same key should require the same number of format args."""
        import re
        spec_re = re.compile(r'%(?:%|' + self._CONVERSION + ')')
        def count_args(s):
            return sum(1 for m in spec_re.finditer(s) if m.group() != '%%')
        for key, (zh, en) in _T.items():
            assert count_args(zh) == count_args(en), (
                f"Key '{key}': zh needs {count_args(zh)} args, en needs {count_args(en)}"
            )

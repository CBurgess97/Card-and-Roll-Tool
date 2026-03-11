"""Tests for clipboard and output capturing."""

import sys

from dice_cards.clipboard import strip_ansi, capture


class TestStripAnsi:
    """Tests for strip_ansi()."""

    def test_strips_bold(self):
        assert strip_ansi("\033[1mhello\033[0m") == "hello"

    def test_strips_color(self):
        assert strip_ansi("\033[31mred\033[0m") == "red"

    def test_no_ansi_passthrough(self):
        assert strip_ansi("plain text") == "plain text"

    def test_multiple_codes(self):
        text = "\033[1m\033[32mgreen bold\033[0m"
        assert strip_ansi(text) == "green bold"

    def test_dim_and_cyan(self):
        text = "\033[2mfaded\033[36mcyan\033[0m"
        assert strip_ansi(text) == "fadedcyan"


class TestCapture:
    """Tests for capture() context manager."""

    def test_no_clip_no_lonelog_passes_through(self, capsys):
        with capture(clip=False, lonelog=False):
            print("hello")
        out = capsys.readouterr().out
        assert "hello" in out

    def test_lonelog_prepends_arrow(self, capsys):
        with capture(clip=False, lonelog=True):
            print("result")
        out = capsys.readouterr().out
        assert out.startswith("-> ")
        assert "result" in out

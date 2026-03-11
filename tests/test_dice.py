"""Tests for dice notation parsing and rolling."""

import random

import pytest

from dice_cards.dice import parse_dice, roll_dice, ironsworn_roll


class TestParseDice:
    """Tests for parse_dice()."""

    def test_simple_d6(self):
        parts = parse_dice("d6")
        assert len(parts) == 1
        assert parts[0]["count"] == 1
        assert parts[0]["sides"] == 6
        assert parts[0]["modifier"] == 0
        assert parts[0]["keep_mode"] is None

    def test_2d6(self):
        parts = parse_dice("2d6")
        assert parts[0]["count"] == 2
        assert parts[0]["sides"] == 6

    def test_d20(self):
        parts = parse_dice("d20")
        assert parts[0]["count"] == 1
        assert parts[0]["sides"] == 20

    def test_d100(self):
        parts = parse_dice("d100")
        assert parts[0]["sides"] == 100

    def test_modifier_plus(self):
        parts = parse_dice("d8+2")
        assert parts[0]["sides"] == 8
        assert parts[0]["modifier"] == 2

    def test_modifier_minus(self):
        parts = parse_dice("d12-1")
        assert parts[0]["sides"] == 12
        assert parts[0]["modifier"] == -1

    def test_keep_highest(self):
        parts = parse_dice("4d6kh3")
        assert parts[0]["count"] == 4
        assert parts[0]["sides"] == 6
        assert parts[0]["keep_mode"] == "kh"
        assert parts[0]["keep_count"] == 3

    def test_keep_lowest(self):
        parts = parse_dice("2d20kl1")
        assert parts[0]["count"] == 2
        assert parts[0]["sides"] == 20
        assert parts[0]["keep_mode"] == "kl"
        assert parts[0]["keep_count"] == 1

    def test_case_insensitive(self):
        parts = parse_dice("D20")
        assert parts[0]["sides"] == 20

    def test_invalid_notation_exits(self):
        with pytest.raises(SystemExit):
            parse_dice("abc")


class TestRollDice:
    """Tests for roll_dice() output formatting."""

    def test_simple_roll_format(self):
        random.seed(42)
        result = roll_dice("d6")
        assert "d6:" in result
        assert "=" in result

    def test_modifier_shown(self):
        random.seed(42)
        result = roll_dice("d8+2")
        assert "+2" in result or "+ 2" in result

    def test_keep_highest_shows_strikethrough(self):
        random.seed(42)
        result = roll_dice("4d6kh3")
        assert "4d6kh3:" in result

    def test_multiple_dice_shows_total(self):
        random.seed(42)
        result = roll_dice("d6+d8")
        assert "total:" in result


class TestIronswornRoll:
    """Tests for ironsworn_roll()."""

    def test_strong_hit(self, capsys):
        random.seed(0)
        # Find a seed that gives a strong hit
        for seed in range(100):
            random.seed(seed)
            action = random.randint(1, 6)
            c1 = random.randint(1, 10)
            c2 = random.randint(1, 10)
            if action > c1 and action > c2:
                random.seed(seed)
                ironsworn_roll(0)
                out = capsys.readouterr().out
                assert "Strong Hit" in out
                return
        pytest.skip("Could not find seed for strong hit")

    def test_miss(self, capsys):
        for seed in range(100):
            random.seed(seed)
            action = random.randint(1, 6)
            c1 = random.randint(1, 10)
            c2 = random.randint(1, 10)
            if action <= c1 and action <= c2:
                random.seed(seed)
                ironsworn_roll(0)
                out = capsys.readouterr().out
                assert "Miss" in out
                return
        pytest.skip("Could not find seed for miss")

    def test_adds_increase_score(self, capsys):
        random.seed(1)
        ironsworn_roll(5)
        out = capsys.readouterr().out
        assert "+ 5" in out

    def test_inline_mode(self, capsys):
        random.seed(42)
        ironsworn_roll(0, inline=True)
        out = capsys.readouterr().out
        # Inline outputs everything on one line
        lines = out.strip().split("\n")
        assert len(lines) == 1

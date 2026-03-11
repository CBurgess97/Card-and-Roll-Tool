"""Tests for config management."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dice_cards.config import load_config, save_config, toggle, DEFAULTS


class TestLoadConfig:
    """Tests for load_config()."""

    def test_defaults_when_no_file(self, tmp_path):
        fake_path = tmp_path / "config.json"
        with patch("dice_cards.config.CONFIG_FILE", fake_path):
            config = load_config()
        assert config == DEFAULTS

    def test_merges_with_defaults(self, tmp_path):
        fake_path = tmp_path / "config.json"
        fake_path.write_text(json.dumps({"inline": True}))
        with patch("dice_cards.config.CONFIG_FILE", fake_path):
            config = load_config()
        assert config["inline"] is True
        assert config["lonelog"] is False  # from defaults


class TestSaveConfig:
    """Tests for save_config()."""

    def test_creates_file(self, tmp_path):
        fake_path = tmp_path / "subdir" / "config.json"
        with patch("dice_cards.config.CONFIG_FILE", fake_path):
            save_config({"inline": True, "lonelog": False})
        assert fake_path.exists()
        data = json.loads(fake_path.read_text())
        assert data["inline"] is True


class TestToggle:
    """Tests for toggle()."""

    def test_toggle_false_to_true(self, tmp_path):
        fake_path = tmp_path / "config.json"
        fake_path.write_text(json.dumps({"inline": False, "lonelog": False}))
        with patch("dice_cards.config.CONFIG_FILE", fake_path):
            result = toggle("inline")
        assert result is True

    def test_toggle_true_to_false(self, tmp_path):
        fake_path = tmp_path / "config.json"
        fake_path.write_text(json.dumps({"inline": True, "lonelog": False}))
        with patch("dice_cards.config.CONFIG_FILE", fake_path):
            result = toggle("inline")
        assert result is False

    def test_toggle_persists(self, tmp_path):
        fake_path = tmp_path / "config.json"
        fake_path.write_text(json.dumps({"inline": False, "lonelog": False}))
        with patch("dice_cards.config.CONFIG_FILE", fake_path):
            toggle("lonelog")
            config = load_config()
        assert config["lonelog"] is True

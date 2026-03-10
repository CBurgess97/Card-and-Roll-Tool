"""Persistent configuration for dice-cards."""

import json
from pathlib import Path

CONFIG_FILE = Path.home() / ".local" / "share" / "dice-cards" / "config.json"

DEFAULTS = {
    "inline": False,
    "lonelog": False,
}


def load_config() -> dict:
    """Load config from disk, filling in defaults for missing keys."""
    config = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        config.update(json.loads(CONFIG_FILE.read_text()))
    return config


def save_config(config: dict) -> None:
    """Persist config to disk."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")


def toggle(key: str) -> bool:
    """Toggle a boolean config key and return the new value."""
    config = load_config()
    config[key] = not config.get(key, DEFAULTS.get(key, False))
    save_config(config)
    return config[key]


def show_config() -> None:
    """Print all config settings and their status."""
    config = load_config()
    for key in DEFAULTS:
        state = "on" if config.get(key, False) else "off"
        print(f"  {key}: {state}")

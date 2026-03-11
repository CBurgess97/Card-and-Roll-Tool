"""YAML table file loading and table lookup."""

import sys
from pathlib import Path

import yaml

from dice_cards.tables.formatting import BOLD, DIM, RESET, _prompt_input


def load_table_file(filepath: str) -> dict:
    """Load and validate a table YAML file."""
    path = Path(filepath)
    if not path.exists():
        print(f"error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        print("error: invalid table file", file=sys.stderr)
        sys.exit(1)
    # Normalize singular 'table' key to 'tables' array
    if "table" in data and "tables" not in data:
        data["tables"] = [data.pop("table")]
    # Normalize 'dice'/'cards'/'weighted'/'lookup'/'split_dice' shorthand to 'roll' object
    for t in data.get("tables", []):
        if "roll" not in t:
            for key in ("dice", "split_dice", "cards", "weighted", "lookup"):
                if key in t:
                    t["roll"] = {key: t.pop(key)}
                    break
    if "tables" not in data:
        print("error: invalid table file — missing 'tables' key", file=sys.stderr)
        sys.exit(1)
    return data


def find_table(data: dict, table_id: str | None) -> dict:
    """Find a table by id, or prompt user to choose if multiple tables exist."""
    tables = data["tables"]
    if table_id:
        needle = table_id.lower()
        for t in tables:
            if t["id"].lower() == needle or t.get("name", "").lower() == needle:
                return t
        print(f"error: table '{table_id}' not found", file=sys.stderr)
        available = ", ".join(f"{t['id']} ({t.get('name', '')})" for t in tables)
        print(f"available tables: {available}", file=sys.stderr)
        sys.exit(1)
    if len(tables) == 1:
        return tables[0]
    # If all tables share the same combine group, return the first (they'll all be rolled together)
    groups = {t.get("combine", {}).get("group") for t in tables}
    if len(groups) == 1 and None not in groups:
        return tables[0]
    # Multiple tables — prompt user to choose
    print(f"{DIM}Multiple tables available:{RESET}", file=sys.stderr)
    for i, t in enumerate(tables, 1):
        name = t.get("name", t["id"])
        roll_config = t.get("roll", {})
        roll_type = next(iter(roll_config), "unknown")
        print(f"  {BOLD}{i}{RESET}. {name} {DIM}[{roll_type}]{RESET}", file=sys.stderr)
    while True:
        try:
            choice = _prompt_input(f"{DIM}>{RESET} ")
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        try:
            idx = int(choice)
            if 1 <= idx <= len(tables):
                return tables[idx - 1]
        except ValueError:
            pass
        print(f"  enter a number from 1 to {len(tables)}", file=sys.stderr)

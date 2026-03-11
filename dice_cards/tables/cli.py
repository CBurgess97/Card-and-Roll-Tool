"""CLI entry point for table rolling."""

import sys

from dice_cards.tables.loading import load_table_file, find_table
from dice_cards.tables.rolling import roll_on_table, roll_dice_total
from dice_cards.tables.combine import roll_combine_group


def parse_modifier(mod_str: str) -> int:
    """Parse a modifier string like '+2', '-1', or '1d6' into an integer."""
    mod_str = mod_str.strip()
    if "d" in mod_str.lower():
        return roll_dice_total(mod_str)
    return int(mod_str)


def table_main(args: list[str], clip: bool, inline: bool = False, lonelog: bool = False) -> None:
    """Entry point for 'roll table <file> [table_id] [-m modifier]'."""
    from dice_cards.clipboard import capture

    # Extract -m flag
    modifier = 0
    filtered = []
    i = 0
    while i < len(args):
        if args[i] == "-m" and i + 1 < len(args):
            try:
                modifier = parse_modifier(args[i + 1])
            except (ValueError, SystemExit):
                print(f"error: invalid modifier '{args[i + 1]}'", file=sys.stderr)
                sys.exit(1)
            i += 2
        else:
            filtered.append(args[i])
            i += 1

    if not filtered:
        print("usage: roll table <file> [table_id] [-m modifier]", file=sys.stderr)
        print("       modifier can be a number (+2, -1) or dice (1d6)", file=sys.stderr)
        sys.exit(1)

    filepath = filtered[0]
    table_id = filtered[1] if len(filtered) > 1 else None

    data = load_table_file(filepath)
    table = find_table(data, table_id)

    with capture(clip, lonelog):
        combine = table.get("combine")
        if combine:
            group = combine["group"]
            group_tables = [t for t in data["tables"] if t.get("combine", {}).get("group") == group]
            roll_combine_group(group_tables, data["tables"], inline=inline)
        else:
            roll_on_table(table, data["tables"], modifier=modifier, inline=inline)

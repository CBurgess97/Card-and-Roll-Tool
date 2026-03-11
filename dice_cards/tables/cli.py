"""CLI entry point for table rolling."""

import sys

from dice_cards.tables.loading import load_table_file, find_table
from dice_cards.tables.rolling import roll_on_table, roll_dice_total
from dice_cards.tables.combine import roll_combine_group
from dice_cards.tables.formatting import BOLD, DIM, CYAN, RESET


def parse_modifier(mod_str: str) -> int:
    """Parse a modifier string like '+2', '-1', or '1d6' into an integer."""
    mod_str = mod_str.strip()
    if "d" in mod_str.lower():
        return roll_dice_total(mod_str)
    return int(mod_str)


def table_main(args: list[str], clip: bool, inline: bool = False, lonelog: bool = False) -> None:
    """Entry point for 'roll table <file> [table_id] [-m modifier]'."""
    from dice_cards.clipboard import capture

    # Handle --check mode
    if "--check" in args:
        args_filtered = [a for a in args if a != "--check"]
        _run_check(args_filtered)
        return

    # Handle --metadata mode
    if "--metadata" in args:
        args_filtered = [a for a in args if a != "--metadata"]
        _run_metadata(args_filtered)
        return

    # Handle --print mode
    if "--print" in args:
        args_filtered = [a for a in args if a != "--print"]
        _run_print(args_filtered)
        return

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
        print("       roll table --check <file> [file ...]", file=sys.stderr)
        print("       roll table --metadata <file>", file=sys.stderr)
        print("       roll table --print <file> [table_id]", file=sys.stderr)
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


def _run_check(args: list[str]) -> None:
    """Validate one or more table files against the schema."""
    from dice_cards.tables.validation import check_table_file

    if not args:
        print("usage: roll table --check <file> [file ...]", file=sys.stderr)
        sys.exit(1)

    all_ok = True
    for filepath in args:
        data = load_table_file(filepath)
        errors = check_table_file(data)
        if errors:
            all_ok = False
            print(f"{BOLD}{filepath}{RESET}: {len(errors)} error(s)")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"{BOLD}{filepath}{RESET}: {CYAN}ok{RESET}")

    if not all_ok:
        sys.exit(1)


def _run_metadata(args: list[str]) -> None:
    """Display metadata for a table file."""
    if not args:
        print("usage: roll table --metadata <file>", file=sys.stderr)
        sys.exit(1)

    data = load_table_file(args[0])
    meta = data.get("metadata", {})
    sv = data.get("schema_version", "unknown")
    tables = data.get("tables", [])

    print(f"{BOLD}Schema version{RESET}: {sv}")

    if meta:
        for key in ("title", "author", "system", "source", "description", "license", "created", "modified"):
            val = meta.get(key)
            if val:
                print(f"{BOLD}{key.title()}{RESET}: {val}")
        tags = meta.get("tags")
        if tags:
            print(f"{BOLD}Tags{RESET}: {', '.join(str(t) for t in tags)}")

    print(f"\n{BOLD}Tables{RESET}: {len(tables)}")
    for t in tables:
        name = t.get("name", t.get("id", "?"))
        roll_config = t.get("roll", {})
        roll_type = next(iter(roll_config), "unknown")
        desc = t.get("description", "")
        entry_count = len(t.get("entries", []))
        if roll_type == "split_dice":
            axes = roll_config.get("split_dice", [])
            entry_count = sum(len(a.get("entries", [])) for a in axes)

        parts = [f"{DIM}[{roll_type}]{RESET}"]
        if t.get("column_mode"):
            parts.append(f"{DIM}column_mode={t['column_mode']}{RESET}")
        if t.get("combine"):
            c = t["combine"]
            parts.append(f"{DIM}combine={c['group']}:{c['role']}{RESET}")
        if entry_count:
            parts.append(f"{DIM}{entry_count} entries{RESET}")

        print(f"  {BOLD}{name}{RESET} ({t.get('id', '?')}) {' '.join(parts)}")
        if desc:
            # Collapse multi-line descriptions
            desc_line = " ".join(desc.split())
            if len(desc_line) > 80:
                desc_line = desc_line[:77] + "..."
            print(f"    {DIM}{desc_line}{RESET}")


def _run_print(args: list[str]) -> None:
    """Pretty-print a table's contents."""
    from dice_cards.tables.matching import get_on

    if not args:
        print("usage: roll table --print <file> [table_id]", file=sys.stderr)
        sys.exit(1)

    filepath = args[0]
    table_id = args[1] if len(args) > 1 else None

    data = load_table_file(filepath)
    table = find_table(data, table_id)

    _print_table(table)


def _print_table(table: dict) -> None:
    """Print a single table in a readable format."""
    from dice_cards.tables.matching import get_on

    name = table.get("name", table.get("id", "?"))
    roll_config = table.get("roll", {})
    roll_type = next(iter(roll_config), "unknown")
    columns = table.get("columns")
    column_mode = table.get("column_mode")

    # Header
    print(f"{BOLD}{name}{RESET} {DIM}[{roll_type}]{RESET}")
    desc = table.get("description")
    if desc:
        print(f"  {DIM}{' '.join(desc.split())}{RESET}")

    # Roll info
    if roll_type == "dice":
        print(f"  {DIM}Roll: {roll_config['dice']}{RESET}")
    elif roll_type == "cards":
        cc = roll_config["cards"]
        draw = cc.get("draw", 1)
        print(f"  {DIM}Deck: {cc['deck']}, draw {draw}{RESET}")

    # Columns
    if columns:
        col_names = ", ".join(c["name"] for c in columns)
        mode_str = f" ({column_mode})" if column_mode else ""
        print(f"  {DIM}Columns{mode_str}: {col_names}{RESET}")

    # Combine
    combine = table.get("combine")
    if combine:
        print(f"  {DIM}Combine: {combine['group']} ({combine['role']}){RESET}")

    print()

    # Entries
    if roll_type == "split_dice":
        axes = roll_config.get("split_dice", [])
        for axis in axes:
            axis_name = axis.get("name", axis.get("id", "?"))
            print(f"  {BOLD}{axis_name}{RESET} {DIM}[{axis.get('dice', '?')}]{RESET}")
            for entry in axis.get("entries", []):
                on = get_on(entry)
                result = entry.get("result", "")
                _print_entry_line(on, entry, columns, column_mode, indent=4)
        return

    entries = table.get("entries", [])
    for entry in entries:
        on = get_on(entry)
        _print_entry_line(on, entry, columns, column_mode, indent=2)


def _print_entry_line(on, entry: dict, columns: list[dict] | None,
                      column_mode: str | None, indent: int = 2) -> None:
    """Print a single entry line."""
    pad = " " * indent
    result = entry.get("result", "")
    reroll = entry.get("reroll")
    weight = entry.get("weight")

    # Format the 'on' value
    if on is not None:
        if isinstance(on, dict):
            # Card match
            if "card" in on:
                on_str = str(on["card"])
            elif "rank" in on:
                on_str = f"rank:{on['rank']}"
            elif "suit" in on:
                on_str = f"suit:{on['suit']}"
            else:
                on_str = str(on)
        else:
            on_str = str(on)
        label = f"{pad}{BOLD}{on_str}{RESET}"
    elif weight is not None:
        label = f"{pad}{DIM}w:{weight}{RESET}"
    else:
        label = f"{pad}{DIM}?{RESET}"

    if reroll:
        print(f"{label}: {DIM}(reroll){RESET}")
        return

    # Format result
    if column_mode == "choice" and isinstance(result, list):
        opts = " / ".join(str(r) for r in result)
        print(f"{label}: {opts}")
    elif isinstance(result, dict) and columns:
        parts = []
        for col in columns:
            val = result.get(col["id"], "")
            parts.append(f"{col['name']}: {val}")
        print(f"{label}: {', '.join(parts)}")
    else:
        print(f"{label}: {result}")

    # Show subtable/ref
    if "subtable" in entry:
        sub = entry["subtable"]
        sub_name = sub.get("name", "subtable")
        print(f"{pad}  {DIM}→ subtable: {sub_name}{RESET}")
    if "ref" in entry:
        print(f"{pad}  {DIM}→ ref: {entry['ref']}{RESET}")

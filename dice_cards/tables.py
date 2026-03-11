"""Roll on YAML-defined TTRPG tables."""

import random
import sys
from pathlib import Path

import yaml

from dice_cards.dice import parse_dice


BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
RESET = "\033[0m"


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
    print(f"{DIM}Multiple tables available:{RESET}")
    for i, t in enumerate(tables, 1):
        name = t.get("name", t["id"])
        roll_config = t.get("roll", {})
        roll_type = next(iter(roll_config), "unknown")
        print(f"  {BOLD}{i}{RESET}. {name} {DIM}[{roll_type}]{RESET}")
    while True:
        try:
            choice = input(f"{DIM}>{RESET} ")
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        try:
            idx = int(choice)
            if 1 <= idx <= len(tables):
                return tables[idx - 1]
        except ValueError:
            pass
        print(f"  enter a number from 1 to {len(tables)}")


def roll_fudge(count: int) -> int:
    """Roll Fudge/Fate dice. Each die is -1, 0, or +1."""
    return sum(random.choice([-1, 0, 1]) for _ in range(count))


def roll_dice_total(notation: str) -> int:
    """Roll dice and return the numeric total."""
    notation = notation.strip().lower()
    # Handle Fudge dice
    if "df" in notation:
        count_str = notation.replace("df", "")
        count = int(count_str) if count_str else 1
        return roll_fudge(count)
    parts = parse_dice(notation)
    total = 0
    for part in parts:
        rolls = sorted([random.randint(1, part["sides"]) for _ in range(part["count"])])
        kept = rolls[:]
        if part["keep_mode"] == "kh":
            kept = rolls[-part["keep_count"]:]
        elif part["keep_mode"] == "kl":
            kept = rolls[:part["keep_count"]]
        total += sum(kept) + part["modifier"]
    return total


def get_on(entry: dict):
    """Get the 'on' value from an entry, handling YAML's boolean 'on' key."""
    if "on" in entry:
        return entry["on"]
    # YAML parses 'on' as boolean True
    if True in entry:
        return entry[True]
    return None


def match_dice_entry(entries: list[dict], roll_result: int) -> dict | None:
    """Find the entry matching a dice roll result."""
    for entry in entries:
        on = get_on(entry)
        if on is None:
            continue
        if isinstance(on, int):
            if roll_result == on:
                return entry
        elif isinstance(on, str):
            on = on.strip()
            # Threshold: "6+" means 6 or higher
            if on.endswith("+"):
                if roll_result >= int(on[:-1]):
                    return entry
            # Threshold: "3-" means 3 or lower, "-1-" means -1 or lower
            elif on.endswith("-"):
                if roll_result <= int(on[:-1]):
                    return entry
            elif "-" in on:
                # Handle negative numbers in ranges (e.g. "-2--1", "-4")
                parts = on.split("-")
                # Reassemble considering negative signs
                nums = []
                i = 0
                while i < len(parts):
                    if parts[i] == "" and i + 1 < len(parts):
                        nums.append(-int(parts[i + 1]))
                        i += 2
                    elif parts[i] == "":
                        i += 1
                    else:
                        nums.append(int(parts[i]))
                        i += 1
                if len(nums) == 1:
                    if roll_result == nums[0]:
                        return entry
                elif len(nums) >= 2:
                    if nums[0] <= roll_result <= nums[1]:
                        return entry
            else:
                if roll_result == int(on):
                    return entry
    return None


STANDARD_52_SUITS = ["hearts", "diamonds", "clubs", "spades"]
STANDARD_52_RANKS = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king"]

TAROT_MAJOR = [
    "The Fool", "The Magician", "The High Priestess", "The Empress",
    "The Emperor", "The Hierophant", "The Lovers", "The Chariot",
    "Strength", "The Hermit", "Wheel of Fortune", "Justice",
    "The Hanged Man", "Death", "Temperance", "The Devil",
    "The Tower", "The Star", "The Moon", "The Sun", "Judgement", "The World",
]

TAROT_MINOR_SUITS = ["wands", "cups", "swords", "pentacles"]
TAROT_MINOR_RANKS = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "page", "knight", "queen", "king"]


def build_deck(cards_config: dict) -> list[str]:
    """Build a deck of card names from a cards config."""
    deck_type = cards_config["deck"]
    if deck_type == "standard52":
        return [f"{r.title()} of {s.title()}" for s in STANDARD_52_SUITS for r in STANDARD_52_RANKS]
    elif deck_type == "standard54":
        cards = [f"{r.title()} of {s.title()}" for s in STANDARD_52_SUITS for r in STANDARD_52_RANKS]
        cards += ["Joker", "Joker"]
        return cards
    elif deck_type == "tarot_major":
        return list(TAROT_MAJOR)
    elif deck_type == "tarot_full":
        cards = list(TAROT_MAJOR)
        for suit in TAROT_MINOR_SUITS:
            for rank in TAROT_MINOR_RANKS:
                cards.append(f"{rank.title()} of {suit.title()}")
        return cards
    elif deck_type == "custom":
        return list(cards_config.get("custom_cards", []))
    else:
        print(f"error: unknown deck type '{deck_type}'", file=sys.stderr)
        sys.exit(1)


def match_card_entry(entries: list[dict], card_name: str) -> dict | None:
    """Find the best matching entry for a drawn card, using precedence: card > rank > suit."""
    card_lower = card_name.lower()

    # Parse the card name into parts
    card_suit = None
    card_rank = None
    if " of " in card_lower:
        rank_part, suit_part = card_lower.rsplit(" of ", 1)
        card_suit = suit_part.strip()
        card_rank = rank_part.strip()

    best = None
    best_priority = -1

    for entry in entries:
        on = get_on(entry) or {}
        if not isinstance(on, dict):
            continue

        if "card" in on:
            if on["card"].lower() == card_lower:
                if best_priority < 3:
                    best = entry
                    best_priority = 3
        elif "rank" in on:
            if card_rank and str(on["rank"]).lower() == card_rank:
                if best_priority < 2:
                    best = entry
                    best_priority = 2
        elif "suit" in on:
            if card_suit and on["suit"].lower() == card_suit:
                if best_priority < 1:
                    best = entry
                    best_priority = 1

    return best


def prompt_column_select(columns: list[dict]) -> dict:
    """Prompt the user to select a column from a list."""
    print(f"{DIM}Select a column:{RESET}")
    for i, col in enumerate(columns, 1):
        print(f"  {BOLD}{i}{RESET}. {col['name']}")
    while True:
        try:
            choice = input(f"{DIM}>{RESET} ")
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        try:
            idx = int(choice)
            if 1 <= idx <= len(columns):
                return columns[idx - 1]
        except ValueError:
            pass
        print(f"  enter a number from 1 to {len(columns)}")


def format_result(entry: dict, columns: list[dict] | None, inline: bool = False,
                  selected_column: dict | None = None, column_mode: str | None = None) -> str:
    """Format an entry's result for display."""
    result = entry["result"]
    # Choice mode — result is an array of options
    if column_mode == "choice" and isinstance(result, list):
        if inline:
            return " / ".join(str(r) for r in result)
        parts = [f"  {BOLD}{i}{RESET}. {r}" for i, r in enumerate(result, 1)]
        return "\n".join(parts)
    # Select mode — show only the selected column's value
    if selected_column and isinstance(result, dict):
        return str(result.get(selected_column["id"], ""))
    if isinstance(result, dict) and columns:
        parts = []
        for col in columns:
            val = result.get(col["id"], "")
            if inline:
                parts.append(f"{col['name']}: {val}")
            else:
                parts.append(f"  {BOLD}{col['name']}{RESET}: {val}")
        sep = ", " if inline else "\n"
        return sep.join(parts)
    return str(result)


def entry_bounds(entries: list[dict]) -> tuple[int, int]:
    """Find the min and max values covered by dice table entries."""
    lo, hi = float("inf"), float("-inf")
    for entry in entries:
        on = get_on(entry)
        if on is None:
            continue
        if isinstance(on, int):
            lo, hi = min(lo, on), max(hi, on)
        elif isinstance(on, str):
            on_s = on.strip()
            # Strip threshold suffixes for bounds calculation
            if on_s.endswith("+"):
                n = int(on_s[:-1])
                lo, hi = min(lo, n), max(hi, n)
                continue
            if on_s.endswith("-"):
                n = int(on_s[:-1])
                lo, hi = min(lo, n), max(hi, n)
                continue
            parts = on_s.split("-")
            nums = []
            i = 0
            while i < len(parts):
                if parts[i] == "" and i + 1 < len(parts):
                    nums.append(-int(parts[i + 1]))
                    i += 2
                elif parts[i] == "":
                    i += 1
                else:
                    nums.append(int(parts[i]))
                    i += 1
            for n in nums:
                lo, hi = min(lo, n), max(hi, n)
    return int(lo), int(hi)


def roll_on_table(table: dict, all_tables: list[dict], depth: int = 0, modifier: int = 0,
                   inline: bool = False, selected_column: dict | None = None,
                   _return_result: bool = False) -> str | None:
    """Roll on a table and print the result. If _return_result is True, return the result string instead of printing."""
    indent = "  " * depth
    roll_config = table["roll"]
    columns = table.get("columns")
    column_mode = table.get("column_mode")
    entries = table.get("entries", [])
    name = table.get("name", "Unknown Table")

    # Prompt for column selection if needed and not already selected
    if column_mode == "select" and columns and not selected_column and not _return_result:
        selected_column = prompt_column_select(columns)

    if "dice" in roll_config:
        notation = roll_config["dice"]
        raw = roll_dice_total(notation)
        result = raw + modifier

        # Clamp to entry bounds
        if modifier:
            lo, hi = entry_bounds(entries)
            result = max(lo, min(hi, result))

        # Show fudge dice result with sign
        if "f" in notation.lower():
            result_display = f"+{result}" if result > 0 else str(result)
        else:
            result_display = str(result)

        mod_str = ""
        if modifier:
            sign = "+" if modifier > 0 else "-"
            mod_str = f" {sign} {abs(modifier)} = {result}"

        entry = match_dice_entry(entries, result)

        if _return_result:
            if not entry or entry.get("reroll"):
                if entry and entry.get("reroll"):
                    return roll_on_table(table, all_tables, depth, inline=inline,
                                         selected_column=selected_column, _return_result=True)
                return "(no match)"
            return format_result(entry, columns, inline=True,
                                 selected_column=selected_column, column_mode=column_mode)

        if inline:
            header = f"{name} [{notation}] → {result_display}{mod_str}"
            if not entry:
                print(f"{header}: (no match)")
                return
            if entry.get("reroll"):
                roll_on_table(table, all_tables, depth, inline=inline, selected_column=selected_column)
                return
            result_text = format_result(entry, columns, inline=True,
                                        selected_column=selected_column, column_mode=column_mode)
            print(f"{header}: {result_text}")
        else:
            print(f"{indent}{DIM}{name}{RESET} [{notation}] → {BOLD}{result_display}{mod_str}{RESET}")
            if not entry:
                print(f"{indent}  (no matching entry for {result})")
                return
            if entry.get("reroll"):
                print(f"{indent}  reroll!")
                roll_on_table(table, all_tables, depth, selected_column=selected_column)
                return
            print(f"{indent}  {format_result(entry, columns, selected_column=selected_column, column_mode=column_mode)}")

        if "subtable" in entry:
            roll_on_table(entry["subtable"], all_tables, depth + 1, inline=inline)
        if "ref" in entry:
            ref_id = entry["ref"]
            for t in all_tables:
                if t["id"] == ref_id:
                    roll_on_table(t, all_tables, depth + 1, inline=inline)
                    break
            else:
                if inline:
                    print(f"(ref '{ref_id}' not found)")
                else:
                    print(f"{indent}  {DIM}(ref '{ref_id}' not found){RESET}")

    elif "cards" in roll_config:
        cards_config = roll_config["cards"]
        deck = build_deck(cards_config)
        draw_count = cards_config.get("draw", 1)
        suit_domains = table.get("suit_domains", {})
        random.shuffle(deck)
        drawn = deck[:draw_count]

        for card_name in drawn:
            entry = match_card_entry(entries, card_name)

            if _return_result:
                if entry:
                    return format_result(entry, columns, inline=True,
                                         selected_column=selected_column, column_mode=column_mode)
                return "(no match)"

            if inline:
                header = f"{name} → {card_name}"
                if entry:
                    result_text = format_result(entry, columns, inline=True,
                                                selected_column=selected_column, column_mode=column_mode)
                    if suit_domains and " of " in card_name:
                        suit = card_name.rsplit(" of ", 1)[1].strip().lower()
                        domain = suit_domains.get(suit)
                        if domain:
                            print(f"{header}: {result_text} [{domain}]")
                        else:
                            print(f"{header}: {result_text}")
                    else:
                        print(f"{header}: {result_text}")
                else:
                    print(f"{header}: (no match)")
            else:
                print(f"{indent}{DIM}{name}{RESET} → {BOLD}{card_name}{RESET}")
                if entry:
                    result_text = format_result(entry, columns,
                                                selected_column=selected_column, column_mode=column_mode)
                    if suit_domains and " of " in card_name:
                        suit = card_name.rsplit(" of ", 1)[1].strip().lower()
                        domain = suit_domains.get(suit)
                        if domain:
                            print(f"{indent}  {result_text}  {DIM}[{domain}]{RESET}")
                        else:
                            print(f"{indent}  {result_text}")
                    else:
                        print(f"{indent}  {result_text}")
                else:
                    print(f"{indent}  {DIM}(no matching entry){RESET}")

    elif "weighted" in roll_config:
        weights = [e.get("weight", 1) for e in entries]
        entry = random.choices(entries, weights=weights, k=1)[0]

        if _return_result:
            return format_result(entry, columns, inline=True,
                                 selected_column=selected_column, column_mode=column_mode)

        result_text = format_result(entry, columns, inline=inline,
                                    selected_column=selected_column, column_mode=column_mode)
        if inline:
            print(f"{name} → {result_text}")
        else:
            print(f"{indent}{DIM}{name}{RESET} →")
            print(f"{indent}  {result_text}")

    elif "lookup" in roll_config:
        if inline:
            items = [f"{get_on(e)}: {e['result']}" for e in entries]
            print(f"{name} — {', '.join(items)}")
        else:
            print(f"{indent}{DIM}{name}{RESET} — lookup table (no roll)")
            for entry in entries:
                print(f"{indent}  {BOLD}{get_on(entry)}{RESET}: {entry['result']}")

    elif "split_dice" in roll_config:
        axes = roll_config["split_dice"]

        if inline:
            parts = []
            for axis in axes:
                axis_notation = axis["dice"]
                axis_entries = axis["entries"]
                axis_name = axis.get("name", axis.get("id", "?"))
                axis_columns = axis.get("columns")
                raw = roll_dice_total(axis_notation)

                entry = match_dice_entry(axis_entries, raw)
                if entry and entry.get("reroll"):
                    raw = roll_dice_total(axis_notation)
                    entry = match_dice_entry(axis_entries, raw)

                if entry:
                    result_text = format_result(entry, axis_columns, inline=True)
                    parts.append(f"{axis_name}: {result_text}")
                else:
                    parts.append(f"{axis_name}: (no match)")
            print(f"{name} → {', '.join(parts)}")
        else:
            dice_summary = " + ".join(a["dice"] for a in axes)
            print(f"{indent}{DIM}{name}{RESET} [{dice_summary} split]")
            for axis in axes:
                axis_notation = axis["dice"]
                axis_entries = axis["entries"]
                axis_name = axis.get("name", axis.get("id", "?"))
                axis_columns = axis.get("columns")
                raw = roll_dice_total(axis_notation)

                if "f" in axis_notation.lower():
                    result_display = f"+{raw}" if raw > 0 else str(raw)
                else:
                    result_display = str(raw)

                print(f"{indent}  {DIM}{axis_name}{RESET} [{axis_notation}] → {BOLD}{result_display}{RESET}")
                entry = match_dice_entry(axis_entries, raw)
                if not entry:
                    print(f"{indent}    (no matching entry for {result_display})")
                    continue

                if entry.get("reroll"):
                    print(f"{indent}    reroll!")
                    raw = roll_dice_total(axis_notation)
                    entry = match_dice_entry(axis_entries, raw)
                    if not entry:
                        print(f"{indent}    (no matching entry for {raw})")
                        continue

                print(f"{indent}    {format_result(entry, axis_columns)}")

                if "subtable" in entry:
                    roll_on_table(entry["subtable"], all_tables, depth + 2)
                if "ref" in entry:
                    ref_id = entry["ref"]
                    for t in all_tables:
                        if t["id"] == ref_id:
                            roll_on_table(t, all_tables, depth + 2)
                            break
                    else:
                        print(f"{indent}    {DIM}(ref '{ref_id}' not found){RESET}")

    else:
        print(f"error: unknown roll method in table '{name}'", file=sys.stderr)
        sys.exit(1)


def roll_combine_group(tables: list[dict], all_tables: list[dict], inline: bool = False) -> None:
    """Roll all tables in a combine group and join prefix + suffix."""
    # Sort into prefix and suffix
    prefix_table = None
    suffix_table = None
    for t in tables:
        role = t["combine"]["role"]
        if role == "prefix":
            prefix_table = t
        elif role == "suffix":
            suffix_table = t

    if not prefix_table or not suffix_table:
        print("error: combine group must have exactly one prefix and one suffix", file=sys.stderr)
        return

    join_str = prefix_table["combine"].get("join", " ")

    # Check if any tables use column_mode: select — prompt once and reuse
    selected_column = None
    for t in [prefix_table, suffix_table]:
        if t.get("column_mode") == "select" and t.get("columns") and not selected_column:
            selected_column = prompt_column_select(t["columns"])
            break

    # Roll each table and collect results
    prefix_result = roll_on_table(prefix_table, all_tables, inline=inline,
                                  selected_column=selected_column, _return_result=True)
    suffix_result = roll_on_table(suffix_table, all_tables, inline=inline,
                                  selected_column=selected_column, _return_result=True)

    # For choice mode, format arrays as pick-lists
    prefix_is_choice = prefix_table.get("column_mode") == "choice"
    suffix_is_choice = suffix_table.get("column_mode") == "choice"

    if prefix_is_choice or suffix_is_choice:
        # Show individual rolls then combined options
        group_name = prefix_table["combine"]["group"]
        if inline:
            pre = f"({prefix_result})" if prefix_is_choice else prefix_result
            suf = f"({suffix_result})" if suffix_is_choice else suffix_result
            print(f"{group_name} → {pre}{join_str}{suf}")
        else:
            print(f"{DIM}{group_name}{RESET}")
            print(f"  {DIM}{prefix_table['name']}{RESET}: {prefix_result}")
            print(f"  {DIM}{suffix_table['name']}{RESET}: {suffix_result}")
    else:
        combined = f"{prefix_result}{join_str}{suffix_result}"
        group_name = prefix_table["combine"]["group"]
        if inline:
            print(f"{group_name} → {combined}")
        else:
            print(f"{DIM}{group_name}{RESET} → {BOLD}{combined}{RESET}")


def parse_modifier(mod_str: str) -> int:
    """Parse a modifier string like '+2', '-1', or '1d6' into an integer."""
    mod_str = mod_str.strip()
    if "d" in mod_str.lower():
        # Dice notation modifier — roll it
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
        # Check if this table is part of a combine group
        combine = table.get("combine")
        if combine:
            group = combine["group"]
            group_tables = [t for t in data["tables"] if t.get("combine", {}).get("group") == group]
            roll_combine_group(group_tables, data["tables"], inline=inline)
        else:
            roll_on_table(table, data["tables"], modifier=modifier, inline=inline)

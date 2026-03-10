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
    """Find a table by id, or return the only table if there's just one."""
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
    return tables[0]


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
            if "-" in on:
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


def format_result(entry: dict, columns: list[dict] | None) -> str:
    """Format an entry's result for display."""
    result = entry["result"]
    if isinstance(result, dict) and columns:
        parts = []
        for col in columns:
            val = result.get(col["id"], "")
            parts.append(f"  {BOLD}{col['name']}{RESET}: {val}")
        return "\n".join(parts)
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
            parts = on.strip().split("-")
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


def roll_on_table(table: dict, all_tables: list[dict], depth: int = 0, modifier: int = 0) -> None:
    """Roll on a table and print the result."""
    indent = "  " * depth
    roll_config = table["roll"]
    columns = table.get("columns")
    entries = table.get("entries", [])
    name = table.get("name", "Unknown Table")

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
        print(f"{indent}{DIM}{name}{RESET} [{notation}] → {BOLD}{raw}{mod_str}{RESET}")

        entry = match_dice_entry(entries, result)
        if not entry:
            print(f"{indent}  (no matching entry for {result})")
            return

        if entry.get("reroll"):
            print(f"{indent}  reroll!")
            roll_on_table(table, all_tables, depth)
            return

        print(f"{indent}  {format_result(entry, columns)}")

        if "subtable" in entry:
            roll_on_table(entry["subtable"], all_tables, depth + 1)
        if "ref" in entry:
            ref_id = entry["ref"]
            for t in all_tables:
                if t["id"] == ref_id:
                    roll_on_table(t, all_tables, depth + 1)
                    break
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
            print(f"{indent}{DIM}{name}{RESET} → {BOLD}{card_name}{RESET}")
            entry = match_card_entry(entries, card_name)
            if entry:
                result_text = format_result(entry, columns)
                # Show suit domain context if defined
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
        print(f"{indent}{DIM}{name}{RESET} →")
        print(f"{indent}  {format_result(entry, columns)}")

    elif "lookup" in roll_config:
        print(f"{indent}{DIM}{name}{RESET} — lookup table (no roll)")
        for entry in entries:
            print(f"{indent}  {BOLD}{get_on(entry)}{RESET}: {entry['result']}")

    elif "split_dice" in roll_config:
        axes = roll_config["split_dice"]
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
                # Re-roll just this axis
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


def parse_modifier(mod_str: str) -> int:
    """Parse a modifier string like '+2', '-1', or '1d6' into an integer."""
    mod_str = mod_str.strip()
    if "d" in mod_str.lower():
        # Dice notation modifier — roll it
        return roll_dice_total(mod_str)
    return int(mod_str)


def table_main(args: list[str], clip: bool) -> None:
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

    with capture(clip):
        roll_on_table(table, data["tables"], modifier=modifier)

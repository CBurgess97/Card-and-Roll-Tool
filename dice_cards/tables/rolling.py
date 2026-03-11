"""Dice rolling helpers, roll handler registry, and the core roll dispatcher."""

import random
import sys
from collections.abc import Callable

from dice_cards.dice import parse_dice
from dice_cards.tables.cards_data import build_deck
from dice_cards.tables.matching import get_on, match_dice_entry, match_card_entry, entry_bounds
from dice_cards.tables.formatting import format_result, prompt_column_select, prompt_choice_select
from dice_cards.tables.result import RollResult


# ---------------------------------------------------------------------------
# Dice rolling helpers
# ---------------------------------------------------------------------------


def roll_fudge(count: int) -> int:
    """Roll Fudge/Fate dice. Each die is -1, 0, or +1."""
    return sum(random.choice([-1, 0, 1]) for _ in range(count))


def roll_dice_total(notation: str) -> int:
    """Roll dice and return the numeric total."""
    notation = notation.strip().lower()
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


# ---------------------------------------------------------------------------
# Roll handler registry
# ---------------------------------------------------------------------------

type RollHandler = Callable[[dict, list[dict], int, dict | None], RollResult]

ROLL_HANDLERS: dict[str, RollHandler] = {}


def register_roll(name: str):
    """Decorator to register a roll handler for a given roll type key."""
    def decorator(fn: RollHandler):
        ROLL_HANDLERS[name] = fn
        return fn
    return decorator


def _resolve_children(entry: dict, all_tables: list[dict]) -> list[RollResult]:
    """Resolve subtable and ref entries into child RollResults."""
    children = []
    if "subtable" in entry:
        children.append(resolve_roll(entry["subtable"], all_tables))
    if "ref" in entry:
        ref_id = entry["ref"]
        ref_table = next((t for t in all_tables if t["id"] == ref_id), None)
        if ref_table:
            children.append(resolve_roll(ref_table, all_tables))
        else:
            children.append(RollResult(
                table_name="", roll_type="ref",
                error=f"ref '{ref_id}' not found",
            ))
    return children


# ---------------------------------------------------------------------------
# Roll handlers
# ---------------------------------------------------------------------------


@register_roll("dice")
def _roll_dice(table: dict, all_tables: list[dict], modifier: int, selected_column: dict | None) -> RollResult:
    notation = table["roll"]["dice"]
    columns = table.get("columns")
    column_mode = table.get("column_mode")
    entries = table.get("entries", [])
    name = table.get("name", "Unknown Table")

    raw = roll_dice_total(notation)
    result_val = raw + modifier

    if modifier:
        lo, hi = entry_bounds(entries)
        result_val = max(lo, min(hi, result_val))

    if "f" in notation.lower():
        raw_display = f"+{result_val}" if result_val > 0 else str(result_val)
    else:
        raw_display = str(result_val)

    mod_str = ""
    if modifier:
        sign = "+" if modifier > 0 else "-"
        mod_str = f" {sign} {abs(modifier)} = {result_val}"

    entry = match_dice_entry(entries, result_val)

    # Handle reroll
    rerolled = False
    if entry and entry.get("reroll"):
        rerolled = True
        return resolve_roll(table, all_tables, modifier, selected_column)

    children = _resolve_children(entry, all_tables) if entry else []

    return RollResult(
        table_name=name, roll_type="dice",
        entry=entry, columns=columns, column_mode=column_mode,
        selected_column=selected_column,
        notation=notation, raw_value=raw_display, modifier_str=mod_str,
        children=children, rerolled=rerolled,
        error=None if entry else f"no matching entry for {result_val}",
    )


@register_roll("cards")
def _roll_cards(table: dict, all_tables: list[dict], modifier: int, selected_column: dict | None) -> RollResult:
    cards_config = table["roll"]["cards"]
    columns = table.get("columns")
    column_mode = table.get("column_mode")
    entries = table.get("entries", [])
    name = table.get("name", "Unknown Table")
    suit_domains = table.get("suit_domains", {})

    deck = build_deck(cards_config)
    draw_count = cards_config.get("draw", 1)
    random.shuffle(deck)
    drawn = deck[:draw_count]

    if draw_count == 1:
        card_name = drawn[0]
        entry = match_card_entry(entries, card_name)
        children = _resolve_children(entry, all_tables) if entry else []
        return RollResult(
            table_name=name, roll_type="cards",
            entry=entry, columns=columns, column_mode=column_mode,
            selected_column=selected_column,
            raw_value=card_name, children=children,
            extra={"suit_domains": suit_domains},
            error=None if entry else "no matching entry",
        )

    # Multiple draws — each card becomes a child result
    card_results = []
    for card_name in drawn:
        entry = match_card_entry(entries, card_name)
        card_results.append(RollResult(
            table_name=name, roll_type="cards",
            entry=entry, columns=columns, column_mode=column_mode,
            selected_column=selected_column,
            raw_value=card_name,
            extra={"suit_domains": suit_domains},
            error=None if entry else "no matching entry",
        ))
    return RollResult(
        table_name=name, roll_type="cards_multi",
        columns=columns, column_mode=column_mode,
        selected_column=selected_column,
        children=card_results,
        extra={"suit_domains": suit_domains},
    )


@register_roll("weighted")
def _roll_weighted(table: dict, all_tables: list[dict], modifier: int, selected_column: dict | None) -> RollResult:
    columns = table.get("columns")
    column_mode = table.get("column_mode")
    entries = table.get("entries", [])
    name = table.get("name", "Unknown Table")

    weights = [e.get("weight", 1) for e in entries]
    entry = random.choices(entries, weights=weights, k=1)[0]

    return RollResult(
        table_name=name, roll_type="weighted",
        entry=entry, columns=columns, column_mode=column_mode,
        selected_column=selected_column,
    )


@register_roll("lookup")
def _roll_lookup(table: dict, all_tables: list[dict], modifier: int, selected_column: dict | None) -> RollResult:
    entries = table.get("entries", [])
    name = table.get("name", "Unknown Table")

    return RollResult(
        table_name=name, roll_type="lookup",
        extra={"entries": entries},
    )


@register_roll("split_dice")
def _roll_split_dice(table: dict, all_tables: list[dict], modifier: int, selected_column: dict | None) -> RollResult:
    axes = table["roll"]["split_dice"]
    name = table.get("name", "Unknown Table")

    axis_results = []
    for axis in axes:
        axis_notation = axis["dice"]
        axis_entries = axis["entries"]
        axis_name = axis.get("name", axis.get("id", "?"))
        axis_columns = axis.get("columns")
        raw = roll_dice_total(axis_notation)

        if "f" in axis_notation.lower():
            raw_display = f"+{raw}" if raw > 0 else str(raw)
        else:
            raw_display = str(raw)

        entry = match_dice_entry(axis_entries, raw)

        rerolled = False
        if entry and entry.get("reroll"):
            rerolled = True
            raw = roll_dice_total(axis_notation)
            if "f" in axis_notation.lower():
                raw_display = f"+{raw}" if raw > 0 else str(raw)
            else:
                raw_display = str(raw)
            entry = match_dice_entry(axis_entries, raw)

        children = _resolve_children(entry, all_tables) if entry else []

        axis_results.append(RollResult(
            table_name=axis_name, roll_type="dice",
            entry=entry, columns=axis_columns,
            notation=axis_notation, raw_value=raw_display,
            children=children, rerolled=rerolled,
            error=None if entry else f"no matching entry for {raw_display}",
        ))

    dice_summary = " + ".join(a["dice"] for a in axes)
    return RollResult(
        table_name=name, roll_type="split_dice",
        notation=dice_summary,
        children=axis_results,
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def resolve_roll(table: dict, all_tables: list[dict],
                 modifier: int = 0, selected_column: dict | None = None) -> RollResult:
    """Roll on a table and return a RollResult (no printing)."""
    roll_config = table["roll"]
    for key, handler in ROLL_HANDLERS.items():
        if key in roll_config:
            return handler(table, all_tables, modifier, selected_column)
    name = table.get("name", "Unknown Table")
    print(f"error: unknown roll method in table '{name}'", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Backward-compatible wrapper
# ---------------------------------------------------------------------------


def roll_on_table(table: dict, all_tables: list[dict], depth: int = 0, modifier: int = 0,
                  inline: bool = False, selected_column: dict | None = None,
                  _return_result: bool = False) -> str | None:
    """Roll on a table and print the result. Backward-compatible entry point."""
    # Lazy import to avoid circular dependency
    from dice_cards.tables.output import format_roll_output

    columns = table.get("columns")
    column_mode = table.get("column_mode")

    # Prompt for column selection if needed and not already selected
    if column_mode == "select" and columns and not selected_column and not _return_result:
        selected_column = prompt_column_select(columns)

    result = resolve_roll(table, all_tables, modifier, selected_column)

    # Prompt for choice selection if needed
    if result.column_mode == "choice" and result.entry and isinstance(result.entry.get("result"), list):
        options = result.entry["result"]
        selected = prompt_choice_select(options, result.table_name)
        result.entry = dict(result.entry)
        result.entry["result"] = selected
        result.column_mode = None

    if _return_result:
        if result.entry:
            return format_result(result.entry, result.columns, inline=True,
                                 selected_column=result.selected_column,
                                 column_mode=result.column_mode)
        if result.error:
            return f"({result.error})"
        return "(no match)"

    mode = "inline" if inline else "multiline"
    output = format_roll_output(result, mode=mode, depth=depth)
    if output:
        print(output, end="")

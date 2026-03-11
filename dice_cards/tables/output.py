"""Output formatters for RollResult — registry-based, pluggable."""

from collections.abc import Callable

from dice_cards.tables.result import RollResult
from dice_cards.tables.matching import get_on
from dice_cards.tables.formatting import BOLD, DIM, RESET, format_result


# ---------------------------------------------------------------------------
# Formatter registry
# ---------------------------------------------------------------------------

type Formatter = Callable[[RollResult, int], str]

FORMATTERS: dict[str, Formatter] = {}


def register_formatter(name: str):
    """Decorator to register an output formatter."""
    def decorator(fn: Formatter):
        FORMATTERS[name] = fn
        return fn
    return decorator


def format_roll_output(result: RollResult, mode: str = "multiline", depth: int = 0) -> str:
    """Format a RollResult using the named formatter. Returns a string ending with newline."""
    formatter = FORMATTERS.get(mode)
    if not formatter:
        raise ValueError(f"Unknown output mode: {mode}")
    return formatter(result, depth)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _format_entry(result: RollResult, inline: bool) -> str:
    """Format the entry result text from a RollResult."""
    if not result.entry:
        return ""
    return format_result(
        result.entry, result.columns, inline=inline,
        selected_column=result.selected_column,
        column_mode=result.column_mode,
    )


def _suit_domain_suffix(result: RollResult, inline: bool) -> str:
    """Return the suit domain annotation if applicable."""
    suit_domains = result.extra.get("suit_domains", {})
    if not suit_domains or not result.raw_value or " of " not in result.raw_value:
        return ""
    suit = result.raw_value.rsplit(" of ", 1)[1].strip().lower()
    domain = suit_domains.get(suit)
    if not domain:
        return ""
    if inline:
        return f" [{domain}]"
    return f"  {DIM}[{domain}]{RESET}"


# ---------------------------------------------------------------------------
# Inline formatter
# ---------------------------------------------------------------------------


@register_formatter("inline")
def format_inline(result: RollResult, depth: int = 0) -> str:
    """Single-line compact output."""

    if result.roll_type == "dice":
        header = f"{result.table_name} [{result.notation}] → {result.raw_value}{result.modifier_str}"
        if result.error:
            return f"{header}: (no match)\n"
        text = _format_entry(result, inline=True)
        out = f"{header}: {text}\n"
        for child in result.children:
            out += format_inline(child, depth + 1)
        return out

    if result.roll_type == "cards":
        header = f"{result.table_name} → {result.raw_value}"
        if result.error and not result.entry:
            return f"{header}: (no match)\n"
        text = _format_entry(result, inline=True)
        suffix = _suit_domain_suffix(result, inline=True)
        return f"{header}: {text}{suffix}\n"

    if result.roll_type == "cards_multi":
        out = ""
        for child in result.children:
            out += format_inline(child, depth)
        return out

    if result.roll_type == "weighted":
        text = _format_entry(result, inline=True)
        return f"{result.table_name} → {text}\n"

    if result.roll_type == "lookup":
        entries = result.extra.get("entries", [])
        items = [f"{get_on(e)}: {e['result']}" for e in entries]
        return f"{result.table_name} — {', '.join(items)}\n"

    if result.roll_type == "split_dice":
        parts = []
        for axis in result.children:
            if axis.entry:
                text = _format_entry(axis, inline=True)
                parts.append(f"{axis.table_name}: {text}")
            else:
                parts.append(f"{axis.table_name}: (no match)")
        return f"{result.table_name} → {', '.join(parts)}\n"

    if result.roll_type == "ref" and result.error:
        return f"({result.error})\n"

    return ""


# ---------------------------------------------------------------------------
# Multiline formatter
# ---------------------------------------------------------------------------


@register_formatter("multiline")
def format_multiline(result: RollResult, depth: int = 0) -> str:
    """Multi-line verbose output with ANSI formatting."""
    indent = "  " * depth

    if result.roll_type == "dice":
        out = f"{indent}{DIM}{result.table_name}{RESET} [{result.notation}] → {BOLD}{result.raw_value}{result.modifier_str}{RESET}\n"
        if result.error:
            return out + f"{indent}  ({result.error})\n"
        text = _format_entry(result, inline=False)
        out += f"{indent}  {text}\n"
        for child in result.children:
            out += format_multiline(child, depth + 1)
        return out

    if result.roll_type == "cards":
        out = f"{indent}{DIM}{result.table_name}{RESET} → {BOLD}{result.raw_value}{RESET}\n"
        if result.error and not result.entry:
            return out + f"{indent}  {DIM}(no matching entry){RESET}\n"
        text = _format_entry(result, inline=False)
        suffix = _suit_domain_suffix(result, inline=False)
        if suffix:
            out += f"{indent}  {text}{suffix}\n"
        else:
            out += f"{indent}  {text}\n"
        return out

    if result.roll_type == "cards_multi":
        out = ""
        for child in result.children:
            out += format_multiline(child, depth)
        return out

    if result.roll_type == "weighted":
        text = _format_entry(result, inline=False)
        return f"{indent}{DIM}{result.table_name}{RESET} →\n{indent}  {text}\n"

    if result.roll_type == "lookup":
        entries = result.extra.get("entries", [])
        out = f"{indent}{DIM}{result.table_name}{RESET} — lookup table (no roll)\n"
        for entry in entries:
            out += f"{indent}  {BOLD}{get_on(entry)}{RESET}: {entry['result']}\n"
        return out

    if result.roll_type == "split_dice":
        out = f"{indent}{DIM}{result.table_name}{RESET} [{result.notation} split]\n"
        for axis in result.children:
            out += f"{indent}  {DIM}{axis.table_name}{RESET} [{axis.notation}] → {BOLD}{axis.raw_value}{RESET}\n"
            if axis.error:
                out += f"{indent}    ({axis.error})\n"
                continue
            if axis.rerolled:
                out += f"{indent}    reroll!\n"
            text = _format_entry(axis, inline=False)
            out += f"{indent}    {text}\n"
            for child in axis.children:
                out += format_multiline(child, depth + 2)
        return out

    if result.roll_type == "ref" and result.error:
        return f"{indent}  {DIM}({result.error}){RESET}\n"

    return ""

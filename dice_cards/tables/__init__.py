"""Roll on YAML-defined TTRPG tables — public API."""

from dice_cards.tables.loading import load_table_file, find_table
from dice_cards.tables.matching import get_on, match_dice_entry, match_card_entry, entry_bounds
from dice_cards.tables.cards_data import build_deck
from dice_cards.tables.rolling import (
    roll_on_table, roll_fudge, roll_dice_total,
    resolve_roll, register_roll, ROLL_HANDLERS,
)
from dice_cards.tables.result import RollResult
from dice_cards.tables.formatting import format_result, prompt_column_select, prompt_choice_select, BOLD, DIM, CYAN, RESET
from dice_cards.tables.output import format_roll_output, register_formatter, FORMATTERS
from dice_cards.tables.combine import roll_combine_group
from dice_cards.tables.cli import parse_modifier, table_main
from dice_cards.tables.validation import check_table_file

__all__ = [
    "load_table_file", "find_table",
    "get_on", "match_dice_entry", "match_card_entry", "entry_bounds",
    "build_deck",
    "roll_on_table", "roll_fudge", "roll_dice_total",
    "resolve_roll", "register_roll", "ROLL_HANDLERS",
    "RollResult",
    "format_result", "prompt_column_select", "prompt_choice_select",
    "format_roll_output", "register_formatter", "FORMATTERS",
    "roll_combine_group",
    "parse_modifier", "table_main",
    "check_table_file",
    "BOLD", "DIM", "CYAN", "RESET",
]

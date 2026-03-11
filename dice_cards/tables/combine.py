"""Prefix-suffix combine group rolling."""

import dice_cards.tables as tables_pkg
from dice_cards.tables.formatting import DIM, BOLD, RESET
from dice_cards.tables.rolling import roll_on_table


def roll_combine_group(tables: list[dict], all_tables: list[dict], inline: bool = False) -> None:
    """Roll all tables in a combine group and join prefix + suffix."""
    import sys

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
            selected_column = tables_pkg.prompt_column_select(t["columns"])
            break

    # Roll each table and collect results (choice prompting happens inside roll_on_table)
    prefix_result = roll_on_table(prefix_table, all_tables, inline=inline,
                                  selected_column=selected_column, _return_result=True)
    suffix_result = roll_on_table(suffix_table, all_tables, inline=inline,
                                  selected_column=selected_column, _return_result=True)

    combined = f"{prefix_result}{join_str}{suffix_result}"
    group_name = prefix_table["combine"]["group"]
    if inline:
        print(f"{group_name} → {combined}")
    else:
        print(f"{DIM}{group_name}{RESET} → {BOLD}{combined}{RESET}")

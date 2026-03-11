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

    # Roll each table and collect results
    prefix_result = roll_on_table(prefix_table, all_tables, inline=inline,
                                  selected_column=selected_column, _return_result=True)
    suffix_result = roll_on_table(suffix_table, all_tables, inline=inline,
                                  selected_column=selected_column, _return_result=True)

    prefix_is_choice = prefix_table.get("column_mode") == "choice"
    suffix_is_choice = suffix_table.get("column_mode") == "choice"

    if prefix_is_choice or suffix_is_choice:
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

"""Result formatting and ANSI constants."""

import sys


BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
RESET = "\033[0m"


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


def prompt_choice_select(options: list, table_name: str = "") -> str:
    """Prompt the user to select one option from a choice result."""
    label = f"Choose from {table_name}:" if table_name else "Choose a result:"
    print(f"{DIM}{label}{RESET}")
    for i, opt in enumerate(options, 1):
        print(f"  {BOLD}{i}{RESET}. {opt}")
    while True:
        try:
            choice = input(f"{DIM}>{RESET} ")
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        try:
            idx = int(choice)
            if 1 <= idx <= len(options):
                return str(options[idx - 1])
        except ValueError:
            pass
        print(f"  enter a number from 1 to {len(options)}")


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

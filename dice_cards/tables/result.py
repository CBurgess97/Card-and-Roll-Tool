"""RollResult dataclass — the contract between rolling and formatting."""

from dataclasses import dataclass, field


@dataclass
class RollResult:
    """The outcome of rolling on a table, before formatting."""
    table_name: str
    roll_type: str                          # "dice", "cards", "weighted", "lookup", "split_dice"
    entry: dict | None = None               # the matched entry (has "result", maybe "subtable"/"ref")
    columns: list[dict] | None = None
    column_mode: str | None = None
    selected_column: dict | None = None
    notation: str | None = None             # "d6", "2d6", etc.
    raw_value: str | None = None            # display-ready roll value ("4", "+2", "Ace of Hearts")
    modifier_str: str = ""                  # " + 2 = 6" or ""
    children: list["RollResult"] = field(default_factory=list)  # subtable/ref/axis results
    extra: dict = field(default_factory=dict)  # roll-type-specific data
    error: str | None = None                # "no match", "ref not found", etc.
    rerolled: bool = False                  # whether a reroll occurred

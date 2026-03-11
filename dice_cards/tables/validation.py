"""Schema validation for table YAML files."""

from dice_cards.tables.cards_data import (
    STANDARD_52_SUITS,
    STANDARD_52_RANKS,
    TAROT_MINOR_SUITS,
)
from dice_cards.tables.matching import get_on


VALID_DECK_TYPES = {"standard52", "standard54", "tarot_major", "tarot_full", "custom"}
VALID_ROLL_KEYS = {"dice", "split_dice", "cards", "lookup", "weighted"}
VALID_COLUMN_MODES = {"combined", "select", "choice"}

# Suits per deck type
DECK_SUITS = {
    "standard52": [s.lower() for s in STANDARD_52_SUITS],
    "standard54": [s.lower() for s in STANDARD_52_SUITS],
    "tarot_major": [],
    "tarot_full": [s.lower() for s in TAROT_MINOR_SUITS] + [s.lower() for s in STANDARD_52_SUITS],
}


def check_table_file(data: dict) -> list[str]:
    """Validate a loaded table file against the schema. Returns a list of error strings."""
    errors = []

    # Rule 1: schema_version present and recognised
    sv = data.get("schema_version")
    if sv is None:
        errors.append("missing required field: schema_version")
    elif sv != "1.0":
        errors.append(f"unrecognised schema_version: '{sv}' (expected '1.0')")

    # Rule 2: exactly one of tables/table (already normalised by load_table_file,
    # but check tables exists)
    if "tables" not in data:
        errors.append("missing required field: tables")
        return errors

    tables = data["tables"]
    if not isinstance(tables, list) or len(tables) == 0:
        errors.append("'tables' must be a non-empty array")
        return errors

    # Rule 3: unique IDs
    ids = [t.get("id") for t in tables]
    seen_ids = set()
    for tid in ids:
        if tid and tid in seen_ids:
            errors.append(f"duplicate table id: '{tid}'")
        if tid:
            seen_ids.add(tid)

    # Collect all table IDs for ref validation
    all_ids = {t.get("id") for t in tables if t.get("id")}

    # Validate each table
    for t in tables:
        tid = t.get("id", "<unknown>")
        prefix = f"table '{tid}'"
        errors.extend(_check_table(t, prefix, all_ids))

    # Rule 13: combine group validation
    errors.extend(_check_combine_groups(tables))

    return errors


def _check_table(table: dict, prefix: str, all_ids: set[str],
                 is_subtable: bool = False) -> list[str]:
    """Validate a single table definition."""
    errors = []

    # Rule 3: required fields (subtables don't require id)
    required = ("name", "roll") if is_subtable else ("id", "name", "roll")
    for field in required:
        if field not in table:
            errors.append(f"{prefix}: missing required field '{field}'")
    if "roll" not in table:
        return errors

    roll = table["roll"]

    # Rule 4: exactly one roll mechanism key
    roll_keys = [k for k in roll if k in VALID_ROLL_KEYS]
    if len(roll_keys) == 0:
        errors.append(f"{prefix}: roll must contain one of: {', '.join(VALID_ROLL_KEYS)}")
        return errors
    if len(roll_keys) > 1:
        errors.append(f"{prefix}: roll must contain exactly one mechanism, found: {', '.join(roll_keys)}")

    roll_type = roll_keys[0]

    # Rule 11: column_mode validation
    column_mode = table.get("column_mode")
    columns = table.get("columns")
    if column_mode and column_mode not in VALID_COLUMN_MODES:
        errors.append(f"{prefix}: invalid column_mode '{column_mode}' (must be {', '.join(VALID_COLUMN_MODES)})")
    if column_mode in ("combined", "select") and not columns:
        errors.append(f"{prefix}: column_mode '{column_mode}' requires 'columns' to be defined")
    if column_mode == "choice" and columns:
        errors.append(f"{prefix}: column_mode 'choice' must not have 'columns' defined")

    # Rule 12: suit_domains validation
    suit_domains = table.get("suit_domains")
    if suit_domains:
        if roll_type != "cards":
            errors.append(f"{prefix}: suit_domains is only valid on card-based tables")
        else:
            deck_type = roll.get("cards", {}).get("deck", "")
            valid_suits = DECK_SUITS.get(deck_type, [])
            if valid_suits:
                for suit in suit_domains:
                    if suit.lower() not in valid_suits:
                        errors.append(f"{prefix}: invalid suit_domains key '{suit}' for deck '{deck_type}'")

    # Roll-type-specific validation
    if roll_type == "split_dice":
        errors.extend(_check_split_dice(table, prefix, all_ids))
    else:
        # Rule 3: entries required for non-split_dice
        entries = table.get("entries")
        if not entries:
            errors.append(f"{prefix}: missing required field 'entries'")
            return errors

        if roll_type == "dice":
            errors.extend(_check_dice_entries(entries, prefix, columns, column_mode, all_ids))
        elif roll_type == "cards":
            errors.extend(_check_card_entries(entries, prefix, roll.get("cards", {})))
        elif roll_type == "weighted":
            errors.extend(_check_weighted_entries(entries, prefix))
        elif roll_type == "lookup":
            errors.extend(_check_entries_common(entries, prefix, columns, column_mode, all_ids))

        # Common entry checks for dice/cards/lookup (ref, columns)
        if roll_type in ("dice", "cards", "lookup"):
            pass  # already checked in type-specific functions

    return errors


def _check_entries_common(entries: list[dict], prefix: str,
                          columns: list[dict] | None, column_mode: str | None,
                          all_ids: set[str]) -> list[str]:
    """Common entry checks: result keys match columns, ref validation, subtable recursion."""
    errors = []
    col_ids = {c["id"] for c in columns} if columns else set()

    for i, entry in enumerate(entries):
        result = entry.get("result")
        entry_label = f"{prefix} entry {i + 1}"

        # Rule 10: multi-column result key validation
        if result is not None and columns and column_mode != "choice":
            if isinstance(result, dict):
                for key in result:
                    if key not in col_ids:
                        errors.append(f"{entry_label}: result key '{key}' not in columns")
                for cid in col_ids:
                    if cid not in result:
                        errors.append(f"{entry_label}: missing column '{cid}' in result")

        # Rule 11: choice mode result must be array
        if column_mode == "choice" and result is not None:
            if not isinstance(result, list):
                errors.append(f"{entry_label}: choice mode result must be an array")

        # Rule 9: ref validation
        ref = entry.get("ref")
        if ref and ref not in all_ids:
            errors.append(f"{entry_label}: ref '{ref}' does not match any table id")

        # Rule 14: subtable recursion
        subtable = entry.get("subtable")
        if subtable:
            sub_prefix = f"{entry_label} subtable"
            if "roll" not in subtable:
                for key in VALID_ROLL_KEYS:
                    if key in subtable:
                        subtable["roll"] = {key: subtable[key]}
                        break
            errors.extend(_check_table(subtable, sub_prefix, all_ids, is_subtable=True))

    return errors


def _check_dice_entries(entries: list[dict], prefix: str,
                        columns: list[dict] | None, column_mode: str | None,
                        all_ids: set[str]) -> list[str]:
    """Rule 5: dice entry coverage — no gaps, no overlaps."""
    errors = []
    errors.extend(_check_entries_common(entries, prefix, columns, column_mode, all_ids))

    # Parse all on values into (lo, hi) ranges
    ranges = []
    for i, entry in enumerate(entries):
        on = get_on(entry)
        if on is None:
            continue
        if entry.get("reroll"):
            continue
        lo, hi = _parse_on_range(on)
        if lo is not None:
            ranges.append((lo, hi, i + 1))

    if not ranges:
        return errors

    # Sort by lo
    ranges.sort()

    # Check for overlaps
    for j in range(1, len(ranges)):
        prev_lo, prev_hi, prev_idx = ranges[j - 1]
        cur_lo, cur_hi, cur_idx = ranges[j]
        if cur_lo <= prev_hi:
            errors.append(f"{prefix}: entries {prev_idx} and {cur_idx} overlap at value {cur_lo}")

    # Check for gaps
    for j in range(1, len(ranges)):
        prev_lo, prev_hi, prev_idx = ranges[j - 1]
        cur_lo, cur_hi, cur_idx = ranges[j]
        if cur_lo > prev_hi + 1:
            gap_start = prev_hi + 1
            gap_end = cur_lo - 1
            if gap_start == gap_end:
                errors.append(f"{prefix}: gap at value {gap_start} (between entries {prev_idx} and {cur_idx})")
            else:
                errors.append(f"{prefix}: gap at values {gap_start}-{gap_end} (between entries {prev_idx} and {cur_idx})")

    return errors


def _parse_on_range(on) -> tuple[int | None, int | None]:
    """Parse an 'on' value into (lo, hi) inclusive range. Returns (None, None) for unparseable."""
    if isinstance(on, int):
        return (on, on)
    if isinstance(on, bool):
        return (None, None)
    if not isinstance(on, str):
        return (None, None)

    on = on.strip()
    # Threshold "6+" — treat as single point for overlap, open-ended
    if on.endswith("+"):
        n = int(on[:-1])
        return (n, n + 1000)  # large upper bound
    if on.endswith("-"):
        n = int(on[:-1])
        return (n - 1000, n)  # large lower bound

    if "-" in on:
        parts = on.split("-")
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
            return (nums[0], nums[0])
        if len(nums) >= 2:
            return (nums[0], nums[1])

    try:
        n = int(on)
        return (n, n)
    except ValueError:
        return (None, None)


def _check_card_entries(entries: list[dict], prefix: str,
                        cards_config: dict) -> list[str]:
    """Rule 7: card table entry validation."""
    errors = []
    for i, entry in enumerate(entries):
        on = get_on(entry)
        if on is None:
            errors.append(f"{prefix} entry {i + 1}: missing 'on' field")
            continue
        if not isinstance(on, dict):
            errors.append(f"{prefix} entry {i + 1}: card entry 'on' must be an object with suit/rank/card")
            continue
        valid_keys = {"suit", "rank", "card"}
        on_keys = set(on.keys()) & valid_keys
        if not on_keys:
            errors.append(f"{prefix} entry {i + 1}: card entry 'on' must have one of: suit, rank, card")
    return errors


def _check_weighted_entries(entries: list[dict], prefix: str) -> list[str]:
    """Rule 8: weighted entry validation."""
    errors = []
    for i, entry in enumerate(entries):
        weight = entry.get("weight")
        if weight is None:
            errors.append(f"{prefix} entry {i + 1}: missing 'weight' field")
        elif not isinstance(weight, int) or weight <= 0:
            errors.append(f"{prefix} entry {i + 1}: weight must be a positive integer, got {weight!r}")
    return errors


def _check_split_dice(table: dict, prefix: str, all_ids: set[str]) -> list[str]:
    """Rule 6: split_dice validation."""
    errors = []

    # Table-level entries must be absent
    if table.get("entries"):
        errors.append(f"{prefix}: split_dice tables must not have table-level 'entries'")

    axes = table["roll"].get("split_dice", [])
    if not axes:
        errors.append(f"{prefix}: split_dice must have at least one axis")
        return errors

    axis_ids = set()
    for j, axis in enumerate(axes):
        axis_label = f"{prefix} axis {j + 1}"
        for field in ("id", "name", "dice"):
            if field not in axis:
                errors.append(f"{axis_label}: missing required field '{field}'")
        aid = axis.get("id")
        if aid:
            if aid in axis_ids:
                errors.append(f"{axis_label}: duplicate axis id '{aid}'")
            axis_ids.add(aid)
        if "entries" not in axis:
            errors.append(f"{axis_label}: missing required field 'entries'")
        else:
            # Validate axis entries like dice entries
            errors.extend(_check_dice_entries(axis["entries"], axis_label, None, None, all_ids))

    return errors


def _check_combine_groups(tables: list[dict]) -> list[str]:
    """Rule 13: combine group validation."""
    errors = []
    groups: dict[str, dict[str, list]] = {}

    for t in tables:
        combine = t.get("combine")
        if not combine:
            continue
        group = combine.get("group")
        role = combine.get("role")
        if not group:
            errors.append(f"table '{t.get('id', '?')}': combine missing 'group'")
            continue
        if role not in ("prefix", "suffix"):
            errors.append(f"table '{t.get('id', '?')}': combine role must be 'prefix' or 'suffix', got '{role}'")
            continue
        groups.setdefault(group, {"prefix": [], "suffix": []})
        groups[group][role].append(t.get("id", "?"))

    for group, roles in groups.items():
        if len(roles["prefix"]) == 0:
            errors.append(f"combine group '{group}': missing prefix table")
        elif len(roles["prefix"]) > 1:
            errors.append(f"combine group '{group}': multiple prefix tables: {roles['prefix']}")
        if len(roles["suffix"]) == 0:
            errors.append(f"combine group '{group}': missing suffix table")
        elif len(roles["suffix"]) > 1:
            errors.append(f"combine group '{group}': multiple suffix tables: {roles['suffix']}")

    return errors

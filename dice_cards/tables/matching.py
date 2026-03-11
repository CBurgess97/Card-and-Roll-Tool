"""Entry matching logic for dice and card tables."""


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


def match_card_entry(entries: list[dict], card_name: str) -> dict | None:
    """Find the best matching entry for a drawn card, using precedence: card > rank > suit."""
    card_lower = card_name.lower()

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

"""Dice roller with standard dice notation support."""

import random
import re
import sys


def parse_dice(notation: str) -> list[dict]:
    """Parse dice notation like 2d6, d20, 3d8+2, d6-1, 4d6kh3, 2d20kl1."""
    notation = notation.strip().lower()
    pattern = re.compile(
        r"(\d*)d(\d+)"
        r"(?:(kh|kl)(\d+))?"
        r"([+-]\d+)?"
    )
    parts = []
    pos = 0
    for match in pattern.finditer(notation):
        if match.start() != pos:
            gap = notation[pos:match.start()].strip()
            if gap and gap not in ("+", "-"):
                print(f"error: unexpected '{gap}' in notation", file=sys.stderr)
                sys.exit(1)
        count = int(match.group(1)) if match.group(1) else 1
        sides = int(match.group(2))
        keep_mode = match.group(3)
        keep_count = int(match.group(4)) if match.group(4) else None
        modifier = int(match.group(5)) if match.group(5) else 0
        parts.append({
            "count": count,
            "sides": sides,
            "keep_mode": keep_mode,
            "keep_count": keep_count,
            "modifier": modifier,
        })
        pos = match.end()
    if not parts:
        print(f"error: invalid dice notation '{notation}'", file=sys.stderr)
        sys.exit(1)
    return parts


def roll_dice(notation: str) -> None:
    """Roll dice and print results."""
    parts = parse_dice(notation)
    grand_total = 0

    for part in parts:
        count = part["count"]
        sides = part["sides"]
        rolls = sorted([random.randint(1, sides) for _ in range(count)])

        kept = rolls[:]
        dropped = []
        if part["keep_mode"] == "kh":
            k = part["keep_count"]
            dropped = rolls[:-k]
            kept = rolls[-k:]
        elif part["keep_mode"] == "kl":
            k = part["keep_count"]
            dropped = rolls[k:]
            kept = rolls[:k]

        total = sum(kept) + part["modifier"]
        grand_total += total

        # Format output
        label = f"{count}d{sides}"
        if part["keep_mode"]:
            label += f"{part['keep_mode']}{part['keep_count']}"
        if part["modifier"] > 0:
            label += f"+{part['modifier']}"
        elif part["modifier"] < 0:
            label += str(part["modifier"])

        roll_strs = []
        for r in rolls:
            if r in dropped and dropped:
                roll_strs.append(f"\033[9;2m{r}\033[0m")
                dropped.remove(r)
            else:
                roll_strs.append(str(r))

        detail = ", ".join(roll_strs)
        mod_str = ""
        if part["modifier"]:
            mod_str = f" {'+' if part['modifier'] > 0 else '-'} {abs(part['modifier'])}"

        print(f"{label}: [{detail}]{mod_str} = {total}")

    if len(parts) > 1:
        print(f"total: {grand_total}")


BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
DIM = "\033[2m"
RESET = "\033[0m"


def ironsworn_roll(adds: int) -> None:
    """Perform an Ironsworn move roll: 1d6 + adds vs 2d10."""
    action = random.randint(1, 6)
    challenge1 = random.randint(1, 10)
    challenge2 = random.randint(1, 10)
    score = action + adds

    beats = sum(1 for c in (challenge1, challenge2) if score > c)

    if beats == 2:
        outcome = f"{GREEN}{BOLD}Strong Hit{RESET}"
    elif beats == 1:
        outcome = f"{YELLOW}{BOLD}Weak Hit{RESET}"
    else:
        outcome = f"{RED}{BOLD}Miss{RESET}"

    twist = ""
    if challenge1 == challenge2:
        twist = f"  {CYAN}⟐ match — narrative twist{RESET}"

    adds_str = f" + {adds}" if adds else ""
    print(f"action: [{action}]{adds_str} = {score}  vs  challenge: [{challenge1}, {challenge2}]")
    print(f"→ {outcome}{twist}")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: roll <dice_notation> [dice_notation ...]", file=sys.stderr)
        print("       roll iron [+adds]   ironsworn move roll", file=sys.stderr)
        print("examples: roll 2d6  roll d20+5  roll 4d6kh3", file=sys.stderr)
        print("          roll iron  roll iron +3", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1].lower() == "iron":
        adds = 0
        if len(sys.argv) > 2:
            raw = sys.argv[2].lstrip("+")
            try:
                adds = int(raw)
            except ValueError:
                print(f"error: invalid adds '{sys.argv[2]}'", file=sys.stderr)
                sys.exit(1)
        ironsworn_roll(adds)
        return

    for notation in sys.argv[1:]:
        roll_dice(notation)


if __name__ == "__main__":
    main()

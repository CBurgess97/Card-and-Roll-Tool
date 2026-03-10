"""Playing card deck with terminal color support."""

import json
import random
import sys
from pathlib import Path

STATE_FILE = Path.home() / ".local" / "share" / "dice-cards" / "deck.json"

SUITS = {
    "hearts": ("Hearts", "\u2661", "\033[91m"),
    "diamonds": ("Diamonds", "\u2662", "\033[91m"),
    "clubs": ("Clubs", "\u2667", "\033[97m"),
    "spades": ("Spades", "\u2664", "\033[97m"),
}
RESET = "\033[0m"

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def full_deck() -> list[str]:
    """Return a shuffled standard 52-card deck."""
    deck = [f"{rank}{suit}" for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    return deck


def load_deck() -> list[str]:
    """Load deck state from disk, or create a new shuffled deck."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return full_deck()


def save_deck(deck: list[str]) -> None:
    """Persist deck state to disk."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(deck))


def format_card(card: str) -> str:
    """Format a card with terminal colors based on suit."""
    for suit_key, (name, symbol, color) in SUITS.items():
        if card.endswith(suit_key):
            rank = card[: -len(suit_key)]
            return f"{color}{rank}{symbol}{RESET}"
    return card


def draw_cards(n: int, inline: bool = False) -> None:
    """Draw n cards from the deck."""
    deck = load_deck()
    if not deck:
        print("deck is empty — use 'draw shuffle' to reshuffle", file=sys.stderr)
        sys.exit(1)

    n = min(n, len(deck))
    drawn = deck[:n]
    remaining = deck[n:]

    save_deck(remaining)

    formatted = [format_card(c) for c in drawn]
    if inline:
        print("  ".join(formatted))
    else:
        print("  ".join(formatted))
        print(f"({len(remaining)} cards remaining)")


def shuffle_deck() -> None:
    """Shuffle a fresh deck."""
    deck = full_deck()
    save_deck(deck)
    print("deck shuffled (52 cards)")


def main() -> None:
    from dice_cards.clipboard import capture

    from dice_cards.config import load_config

    flags = ("-c", "--inline", "--lonelog")
    args = [a for a in sys.argv[1:] if a not in flags]
    clip = "-c" in sys.argv
    config = load_config()
    inline = config.get("inline", False) ^ ("--inline" in sys.argv)
    lonelog = config.get("lonelog", False) ^ ("--lonelog" in sys.argv)

    if not args:
        print("usage: draw [-c] [--inline] [--lonelog] <count>", file=sys.stderr)
        print("       draw shuffle   shuffle a new deck", file=sys.stderr)
        print("       draw config    show config settings", file=sys.stderr)
        print("flags: -c        copy result to clipboard", file=sys.stderr)
        print("       --inline  compact single-line output", file=sys.stderr)
        print("       --lonelog prepend -> for lonelog notation", file=sys.stderr)
        sys.exit(1)

    arg = args[0].lower()

    if arg == "config":
        from dice_cards.config import show_config, toggle
        toggled = False
        for flag in ("--inline", "--lonelog"):
            if flag in sys.argv:
                key = flag.lstrip("-")
                new_val = toggle(key)
                state = "on" if new_val else "off"
                print(f"{key}: {state}")
                toggled = True
        if not toggled:
            show_config()
        return

    with capture(clip, lonelog):
        if arg == "shuffle":
            shuffle_deck()
        elif arg.isdigit():
            draw_cards(int(arg), inline)
        else:
            print(f"error: expected a number or 'shuffle', got '{arg}'", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

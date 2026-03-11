"""Card deck constants and deck building."""

import sys


STANDARD_52_SUITS = ["hearts", "diamonds", "clubs", "spades"]
STANDARD_52_RANKS = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king"]

TAROT_MAJOR = [
    "The Fool", "The Magician", "The High Priestess", "The Empress",
    "The Emperor", "The Hierophant", "The Lovers", "The Chariot",
    "Strength", "The Hermit", "Wheel of Fortune", "Justice",
    "The Hanged Man", "Death", "Temperance", "The Devil",
    "The Tower", "The Star", "The Moon", "The Sun", "Judgement", "The World",
]

TAROT_MINOR_SUITS = ["wands", "cups", "swords", "pentacles"]
TAROT_MINOR_RANKS = ["ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "page", "knight", "queen", "king"]


def build_deck(cards_config: dict) -> list[str]:
    """Build a deck of card names from a cards config."""
    deck_type = cards_config["deck"]
    if deck_type == "standard52":
        return [f"{r.title()} of {s.title()}" for s in STANDARD_52_SUITS for r in STANDARD_52_RANKS]
    elif deck_type == "standard54":
        cards = [f"{r.title()} of {s.title()}" for s in STANDARD_52_SUITS for r in STANDARD_52_RANKS]
        cards += ["Joker", "Joker"]
        return cards
    elif deck_type == "tarot_major":
        return list(TAROT_MAJOR)
    elif deck_type == "tarot_full":
        cards = list(TAROT_MAJOR)
        for suit in TAROT_MINOR_SUITS:
            for rank in TAROT_MINOR_RANKS:
                cards.append(f"{rank.title()} of {suit.title()}")
        return cards
    elif deck_type == "custom":
        return list(cards_config.get("custom_cards", []))
    else:
        print(f"error: unknown deck type '{deck_type}'", file=sys.stderr)
        sys.exit(1)

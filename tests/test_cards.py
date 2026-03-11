"""Tests for the card drawing module."""

import json
import random

import pytest

from dice_cards.cards import full_deck, format_card, SUITS, RANKS


class TestFullDeck:
    """Tests for full_deck()."""

    def test_has_52_cards(self):
        deck = full_deck()
        assert len(deck) == 52

    def test_all_suit_rank_combos(self):
        deck = full_deck()
        for suit in SUITS:
            for rank in RANKS:
                assert f"{rank}{suit}" in deck

    def test_shuffled(self):
        """Two decks should almost certainly differ in order."""
        random.seed(1)
        d1 = full_deck()
        random.seed(2)
        d2 = full_deck()
        assert d1 != d2


class TestFormatCard:
    """Tests for format_card()."""

    def test_hearts_colored(self):
        result = format_card("Ahearts")
        assert "\033[91m" in result  # red
        assert "♡" in result or "A" in result

    def test_spades_colored(self):
        result = format_card("Kspades")
        assert "\033[97m" in result  # white
        assert "K" in result

    def test_unknown_card(self):
        result = format_card("Joker")
        assert result == "Joker"

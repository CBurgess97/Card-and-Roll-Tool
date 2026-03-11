"""Tests for YAML table loading, matching, and rolling."""

import random
import sys
from unittest.mock import patch

import pytest

from dice_cards.tables import (
    load_table_file,
    find_table,
    get_on,
    match_dice_entry,
    match_card_entry,
    build_deck,
    format_result,
    entry_bounds,
    roll_dice_total,
    roll_fudge,
    roll_on_table,
    roll_combine_group,
    prompt_column_select,
    prompt_choice_select,
    parse_modifier,
    check_table_file,
)
from dice_cards.tables.cli import _run_check, _run_metadata, _run_print

from tests.conftest import example_path


# ---------------------------------------------------------------------------
# Loading & normalisation
# ---------------------------------------------------------------------------


class TestLoadTableFile:
    """Tests for load_table_file()."""

    def test_load_simple_d6(self):
        data = load_table_file(example_path("simple-d6.yml"))
        assert "tables" in data
        assert len(data["tables"]) == 1
        t = data["tables"][0]
        assert t["id"] == "wandering_mood"
        assert "roll" in t
        assert "dice" in t["roll"]

    def test_load_single_table_shorthand(self):
        """The `table:` singular key should be normalised to `tables:` array."""
        data = load_table_file(example_path("single-table.yml"))
        assert "tables" in data
        assert "table" not in data
        assert len(data["tables"]) == 1
        assert data["tables"][0]["id"] == "coin_flip"

    def test_load_multi_table_file(self):
        data = load_table_file(example_path("nested-subtable.yml"))
        assert len(data["tables"]) == 2
        ids = {t["id"] for t in data["tables"]}
        assert ids == {"treasure_hoard", "magic_weapons"}

    def test_load_nonexistent_exits(self):
        with pytest.raises(SystemExit):
            load_table_file("/nonexistent/path.yml")

    def test_roll_key_normalised(self):
        """Tables with shorthand roll keys get normalised to roll: {key: value}."""
        data = load_table_file(example_path("simple-d6.yml"))
        t = data["tables"][0]
        assert isinstance(t["roll"], dict)
        assert "dice" in t["roll"]

    def test_schema_version_present(self):
        data = load_table_file(example_path("simple-d6.yml"))
        assert data.get("schema_version") == "1.0"

    def test_metadata_loaded(self):
        data = load_table_file(example_path("simple-d6.yml"))
        assert "metadata" in data
        assert data["metadata"]["title"] == "Simple d6 Table Example"


class TestFindTable:
    """Tests for find_table()."""

    def test_single_table_no_id(self):
        data = load_table_file(example_path("simple-d6.yml"))
        t = find_table(data, None)
        assert t["id"] == "wandering_mood"

    def test_find_by_id(self):
        data = load_table_file(example_path("nested-subtable.yml"))
        t = find_table(data, "magic_weapons")
        assert t["id"] == "magic_weapons"

    def test_find_by_name_case_insensitive(self):
        data = load_table_file(example_path("nested-subtable.yml"))
        t = find_table(data, "magic weapons")
        assert t["id"] == "magic_weapons"

    def test_find_missing_exits(self):
        data = load_table_file(example_path("nested-subtable.yml"))
        with pytest.raises(SystemExit):
            find_table(data, "nonexistent_table")

    def test_combine_group_auto_selects(self):
        """When all tables share the same combine group, return first without prompting."""
        data = load_table_file(example_path("prefix-suffix.yml"))
        t = find_table(data, None)
        # Should return without prompting — all tables share group 'weapon_name'
        assert t["id"] == "weapon_adj"

    def test_multi_table_prompts(self):
        """Multiple tables without a combine group should prompt for selection."""
        data = load_table_file(example_path("nested-subtable.yml"))
        with patch("builtins.input", return_value="1"):
            t = find_table(data, None)
        assert t["id"] == "treasure_hoard"


# ---------------------------------------------------------------------------
# get_on helper
# ---------------------------------------------------------------------------


class TestGetOn:
    """Tests for get_on() YAML boolean key handling."""

    def test_normal_on_key(self):
        assert get_on({"on": 5}) == 5

    def test_yaml_boolean_on(self):
        """YAML parses bare `on:` as True key in some contexts."""
        assert get_on({True: 5}) == 5

    def test_missing_on(self):
        assert get_on({"result": "foo"}) is None

    def test_string_on(self):
        assert get_on({"on": "1-5"}) == "1-5"


# ---------------------------------------------------------------------------
# Dice entry matching
# ---------------------------------------------------------------------------


class TestMatchDiceEntry:
    """Tests for match_dice_entry()."""

    @pytest.fixture
    def simple_entries(self):
        return [
            {"on": 1, "result": "one"},
            {"on": 2, "result": "two"},
            {"on": 3, "result": "three"},
        ]

    @pytest.fixture
    def range_entries(self):
        return [
            {"on": "1-5", "result": "low"},
            {"on": "6-10", "result": "mid"},
            {"on": "11-20", "result": "high"},
        ]

    @pytest.fixture
    def threshold_entries(self):
        return [
            {"on": "3-", "result": "rout"},
            {"on": "4-5", "result": "retreat"},
            {"on": "6-8", "result": "waver"},
            {"on": "9-11", "result": "stand"},
            {"on": "12+", "result": "rally"},
        ]

    def test_exact_match(self, simple_entries):
        entry = match_dice_entry(simple_entries, 2)
        assert entry["result"] == "two"

    def test_no_match(self, simple_entries):
        assert match_dice_entry(simple_entries, 99) is None

    def test_range_match_low(self, range_entries):
        entry = match_dice_entry(range_entries, 1)
        assert entry["result"] == "low"

    def test_range_match_boundary(self, range_entries):
        entry = match_dice_entry(range_entries, 5)
        assert entry["result"] == "low"

    def test_range_match_mid(self, range_entries):
        entry = match_dice_entry(range_entries, 8)
        assert entry["result"] == "mid"

    def test_range_match_high(self, range_entries):
        entry = match_dice_entry(range_entries, 20)
        assert entry["result"] == "high"

    def test_threshold_low(self, threshold_entries):
        """3- should match 2 and 3."""
        assert match_dice_entry(threshold_entries, 2)["result"] == "rout"
        assert match_dice_entry(threshold_entries, 3)["result"] == "rout"

    def test_threshold_high(self, threshold_entries):
        """12+ should match 12."""
        assert match_dice_entry(threshold_entries, 12)["result"] == "rally"

    def test_negative_exact(self):
        entries = [
            {"on": "-4", "result": "catastrophic"},
            {"on": "-3", "result": "severe"},
            {"on": "0", "result": "no change"},
        ]
        assert match_dice_entry(entries, -4)["result"] == "catastrophic"
        assert match_dice_entry(entries, -3)["result"] == "severe"
        assert match_dice_entry(entries, 0)["result"] == "no change"

    def test_negative_range(self):
        entries = [{"on": "-2--1", "result": "bad"}]
        assert match_dice_entry(entries, -2)["result"] == "bad"
        assert match_dice_entry(entries, -1)["result"] == "bad"
        assert match_dice_entry(entries, 0) is None

    def test_single_integer_as_string(self):
        """on: "2" (string) should match roll of 2."""
        entries = [{"on": "2", "result": "two"}]
        assert match_dice_entry(entries, 2)["result"] == "two"


# ---------------------------------------------------------------------------
# Card matching
# ---------------------------------------------------------------------------


class TestMatchCardEntry:
    """Tests for match_card_entry()."""

    @pytest.fixture
    def card_entries(self):
        return [
            {"on": {"suit": "hearts"}, "result": "Love"},
            {"on": {"suit": "spades"}, "result": "Conflict"},
            {"on": {"rank": "ace"}, "result": "New beginning"},
            {"on": {"card": "Ace of Spades"}, "result": "Death/Transformation"},
        ]

    def test_suit_match(self, card_entries):
        entry = match_card_entry(card_entries, "5 of Hearts")
        assert entry["result"] == "Love"

    def test_rank_match_overrides_suit(self, card_entries):
        entry = match_card_entry(card_entries, "Ace of Hearts")
        assert entry["result"] == "New beginning"

    def test_exact_card_overrides_rank(self, card_entries):
        entry = match_card_entry(card_entries, "Ace of Spades")
        assert entry["result"] == "Death/Transformation"

    def test_no_match(self, card_entries):
        entry = match_card_entry(card_entries, "5 of Diamonds")
        assert entry is None

    def test_case_insensitive(self, card_entries):
        entry = match_card_entry(card_entries, "ace of spades")
        assert entry["result"] == "Death/Transformation"

    def test_numeric_rank(self):
        entries = [{"on": {"rank": "2"}, "result": "Seek"}]
        entry = match_card_entry(entries, "2 of Hearts")
        assert entry["result"] == "Seek"


# ---------------------------------------------------------------------------
# Deck building
# ---------------------------------------------------------------------------


class TestBuildDeck:
    """Tests for build_deck()."""

    def test_standard52(self):
        deck = build_deck({"deck": "standard52"})
        assert len(deck) == 52
        assert "Ace of Hearts" in deck
        assert "King of Spades" in deck

    def test_standard54(self):
        deck = build_deck({"deck": "standard54"})
        assert len(deck) == 54
        assert deck.count("Joker") == 2

    def test_tarot_major(self):
        deck = build_deck({"deck": "tarot_major"})
        assert len(deck) == 22
        assert "The Fool" in deck
        assert "The World" in deck

    def test_tarot_full(self):
        deck = build_deck({"deck": "tarot_full"})
        assert len(deck) == 78
        assert "The Fool" in deck
        assert "Ace of Wands" in deck

    def test_custom_deck(self):
        deck = build_deck({"deck": "custom", "custom_cards": ["A", "B", "C"]})
        assert deck == ["A", "B", "C"]

    def test_unknown_deck_exits(self):
        with pytest.raises(SystemExit):
            build_deck({"deck": "nonexistent"})


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------


class TestFormatResult:
    """Tests for format_result()."""

    def test_simple_string(self):
        assert format_result({"result": "hello"}, None) == "hello"

    def test_multi_column_inline(self):
        entry = {"result": {"name": "Aldric", "trait": "Grumpy"}}
        columns = [{"id": "name", "name": "Name"}, {"id": "trait", "name": "Trait"}]
        result = format_result(entry, columns, inline=True)
        assert "Name: Aldric" in result
        assert "Trait: Grumpy" in result

    def test_multi_column_multiline(self):
        entry = {"result": {"name": "Aldric", "trait": "Grumpy"}}
        columns = [{"id": "name", "name": "Name"}, {"id": "trait", "name": "Trait"}]
        result = format_result(entry, columns, inline=False)
        assert "\n" in result
        assert "Name" in result
        assert "Aldric" in result

    def test_select_column(self):
        entry = {"result": {"human": "Aldric", "elf": "Thalion"}}
        selected = {"id": "elf", "name": "Elf"}
        result = format_result(entry, None, selected_column=selected)
        assert result == "Thalion"

    def test_choice_mode_inline(self):
        entry = {"result": ["Aldric", "Aldwin"]}
        result = format_result(entry, None, inline=True, column_mode="choice")
        assert "Aldric / Aldwin" == result

    def test_choice_mode_multiline(self):
        entry = {"result": ["Aldric", "Aldwin"]}
        result = format_result(entry, None, inline=False, column_mode="choice")
        assert "1" in result
        assert "2" in result
        assert "Aldric" in result
        assert "Aldwin" in result


# ---------------------------------------------------------------------------
# Entry bounds
# ---------------------------------------------------------------------------


class TestEntryBounds:
    """Tests for entry_bounds()."""

    def test_integer_entries(self):
        entries = [{"on": 1}, {"on": 2}, {"on": 6}]
        assert entry_bounds(entries) == (1, 6)

    def test_range_entries(self):
        entries = [{"on": "1-5"}, {"on": "6-10"}]
        assert entry_bounds(entries) == (1, 10)

    def test_negative_entries(self):
        entries = [{"on": "-4"}, {"on": "-3"}, {"on": "0"}, {"on": "4"}]
        assert entry_bounds(entries) == (-4, 4)


# ---------------------------------------------------------------------------
# Dice rolling helpers
# ---------------------------------------------------------------------------


class TestRollDiceTotal:
    """Tests for roll_dice_total()."""

    def test_d6_in_range(self):
        random.seed(42)
        for _ in range(100):
            result = roll_dice_total("d6")
            assert 1 <= result <= 6

    def test_2d6_in_range(self):
        random.seed(42)
        for _ in range(100):
            result = roll_dice_total("2d6")
            assert 2 <= result <= 12

    def test_d100_in_range(self):
        random.seed(42)
        for _ in range(50):
            result = roll_dice_total("d100")
            assert 1 <= result <= 100

    def test_modifier_applied(self):
        random.seed(42)
        for _ in range(50):
            result = roll_dice_total("d8+2")
            assert 3 <= result <= 10

    def test_negative_modifier(self):
        random.seed(42)
        for _ in range(50):
            result = roll_dice_total("d12-1")
            assert 0 <= result <= 11


class TestRollFudge:
    """Tests for roll_fudge()."""

    def test_range(self):
        random.seed(42)
        results = {roll_fudge(4) for _ in range(1000)}
        assert min(results) >= -4
        assert max(results) <= 4

    def test_single_die_range(self):
        random.seed(42)
        results = {roll_fudge(1) for _ in range(100)}
        assert results.issubset({-1, 0, 1})

    def test_fudge_via_roll_dice_total(self):
        random.seed(42)
        for _ in range(100):
            result = roll_dice_total("4dF")
            assert -4 <= result <= 4


# ---------------------------------------------------------------------------
# Parse modifier
# ---------------------------------------------------------------------------


class TestParseModifier:
    """Tests for parse_modifier()."""

    def test_positive_int(self):
        assert parse_modifier("+2") == 2

    def test_negative_int(self):
        assert parse_modifier("-1") == -1

    def test_dice_notation(self):
        random.seed(42)
        result = parse_modifier("1d6")
        assert 1 <= result <= 6


# ---------------------------------------------------------------------------
# Prompt column select
# ---------------------------------------------------------------------------


class TestPromptColumnSelect:
    """Tests for prompt_column_select()."""

    def test_valid_selection(self, capsys):
        columns = [{"id": "human", "name": "Human"}, {"id": "elf", "name": "Elf"}]
        with patch("builtins.input", return_value="2"):
            result = prompt_column_select(columns)
        assert result["id"] == "elf"

    def test_invalid_then_valid(self, capsys):
        columns = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
        with patch("builtins.input", side_effect=["x", "0", "1"]):
            result = prompt_column_select(columns)
        assert result["id"] == "a"

    def test_eof_exits(self):
        columns = [{"id": "a", "name": "A"}]
        with patch("builtins.input", side_effect=EOFError):
            with pytest.raises(SystemExit):
                prompt_column_select(columns)


# ---------------------------------------------------------------------------
# Prompt choice select
# ---------------------------------------------------------------------------


class TestPromptChoiceSelect:
    """Tests for prompt_choice_select()."""

    def test_valid_selection(self, capsys):
        options = ["Aldric", "Aldwin"]
        with patch("builtins.input", return_value="1"):
            result = prompt_choice_select(options)
        assert result == "Aldric"

    def test_second_option(self, capsys):
        options = ["Bera", "Brynn"]
        with patch("builtins.input", return_value="2"):
            result = prompt_choice_select(options)
        assert result == "Brynn"

    def test_invalid_then_valid(self, capsys):
        options = ["A", "B", "C"]
        with patch("builtins.input", side_effect=["x", "0", "2"]):
            result = prompt_choice_select(options)
        assert result == "B"

    def test_eof_exits(self):
        with patch("builtins.input", side_effect=EOFError):
            with pytest.raises(SystemExit):
                prompt_choice_select(["A", "B"])

    def test_table_name_shown(self, capsys):
        with patch("builtins.input", return_value="1"):
            prompt_choice_select(["A"], table_name="Test Table")
        out = capsys.readouterr().out
        assert "Test Table" in out

    def test_choice_prompts_during_roll(self, capsys):
        """Choice mode should prompt user instead of just listing options."""
        random.seed(42)
        data = load_table_file(example_path("prefix-suffix-choice.yml"))
        table = data["tables"][0]
        with patch("dice_cards.tables.rolling.prompt_choice_select", return_value="Aldric") as mock:
            roll_on_table(table, data["tables"], inline=True)
            mock.assert_called_once()
        out = capsys.readouterr().out
        assert "Aldric" in out

    def test_choice_prompts_during_combine(self, capsys):
        """Prefix-suffix choice tables should prompt for both parts."""
        random.seed(42)
        data = load_table_file(example_path("prefix-suffix-choice.yml"))
        tables = data["tables"]
        group_tables = [t for t in tables if t.get("combine", {}).get("group") == "human_name"]
        with patch("dice_cards.tables.rolling.prompt_choice_select", return_value="X") as mock:
            roll_combine_group(group_tables, tables, inline=True)
            assert mock.call_count == 2  # once for prefix, once for suffix


# ---------------------------------------------------------------------------
# Full table rolling — each example file
# ---------------------------------------------------------------------------


class TestRollOnTableSimpleD6:
    """Tests using simple-d6.yml."""

    def test_all_results_valid(self, capsys):
        data = load_table_file(example_path("simple-d6.yml"))
        table = data["tables"][0]
        for seed in range(20):
            random.seed(seed)
            roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        lines = [l for l in out.strip().split("\n") if l]
        for line in lines:
            assert "Wandering NPC Mood" in line
            assert "[d6]" in line
            assert "(no match)" not in line

    def test_multiline_format(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("simple-d6.yml"))
        roll_on_table(data["tables"][0], data["tables"])
        out = capsys.readouterr().out
        assert "Wandering NPC Mood" in out
        assert "[d6]" in out


class TestRollOnTableRangeD100:
    """Tests using range-d100.yml."""

    def test_all_rolls_match(self, capsys):
        data = load_table_file(example_path("range-d100.yml"))
        table = data["tables"][0]
        for seed in range(50):
            random.seed(seed)
            roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "(no match)" not in out

    def test_range_coverage(self):
        """Every value 1-100 should have a matching entry."""
        data = load_table_file(example_path("range-d100.yml"))
        entries = data["tables"][0]["entries"]
        for i in range(1, 101):
            assert match_dice_entry(entries, i) is not None, f"No match for {i}"


class TestRollOnTableBellCurve2d6:
    """Tests using bell-curve-2d6.yml."""

    def test_all_rolls_match(self, capsys):
        data = load_table_file(example_path("bell-curve-2d6.yml"))
        table = data["tables"][0]
        for seed in range(30):
            random.seed(seed)
            roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "(no match)" not in out

    def test_full_range_coverage(self):
        """Every value 2-12 should match."""
        data = load_table_file(example_path("bell-curve-2d6.yml"))
        entries = data["tables"][0]["entries"]
        for i in range(2, 13):
            assert match_dice_entry(entries, i) is not None, f"No match for {i}"


class TestRollOnTableMultiColumn:
    """Tests using multi-column.yml."""

    def test_columns_loaded(self):
        data = load_table_file(example_path("multi-column.yml"))
        table = data["tables"][0]
        assert table.get("columns") is not None
        assert len(table["columns"]) == 3
        ids = [c["id"] for c in table["columns"]]
        assert ids == ["name", "occupation", "quirk"]

    def test_inline_output_has_all_columns(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("multi-column.yml"))
        table = data["tables"][0]
        roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "Name:" in out
        assert "Occupation:" in out
        assert "Quirk:" in out

    def test_multiline_output_has_all_columns(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("multi-column.yml"))
        table = data["tables"][0]
        roll_on_table(table, data["tables"])
        out = capsys.readouterr().out
        assert "Name" in out
        assert "Occupation" in out
        assert "Quirk" in out


class TestRollOnTableNestedSubtable:
    """Tests using nested-subtable.yml."""

    def test_subtable_triggered(self, capsys):
        """Roll values 3-4 trigger the gemstone subtable."""
        data = load_table_file(example_path("nested-subtable.yml"))
        table = find_table(data, "treasure_hoard")

        for seed in range(200):
            random.seed(seed)
            result = roll_dice_total("d6")
            if result in (3, 4):
                random.seed(seed)
                roll_on_table(table, data["tables"])
                out = capsys.readouterr().out
                assert "Gemstone Type" in out
                return
        pytest.skip("Could not find seed triggering subtable")

    def test_ref_triggered(self, capsys):
        """Roll value 5 triggers ref to magic_weapons."""
        data = load_table_file(example_path("nested-subtable.yml"))
        table = find_table(data, "treasure_hoard")

        for seed in range(200):
            random.seed(seed)
            result = roll_dice_total("d6")
            if result == 5:
                random.seed(seed)
                roll_on_table(table, data["tables"])
                out = capsys.readouterr().out
                assert "Magic Weapons" in out
                return
        pytest.skip("Could not find seed triggering ref")

    def test_magic_weapons_standalone(self, capsys):
        data = load_table_file(example_path("nested-subtable.yml"))
        table = find_table(data, "magic_weapons")
        random.seed(42)
        roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "Magic Weapons" in out
        assert "(no match)" not in out


class TestRollOnTableFudgeDice:
    """Tests using fudge-dice.yml."""

    def test_fudge_range(self, capsys):
        data = load_table_file(example_path("fudge-dice.yml"))
        table = data["tables"][0]
        for seed in range(50):
            random.seed(seed)
            roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "(no match)" not in out

    def test_full_range_coverage(self):
        """Every value -4 to +4 should match."""
        data = load_table_file(example_path("fudge-dice.yml"))
        entries = data["tables"][0]["entries"]
        for i in range(-4, 5):
            assert match_dice_entry(entries, i) is not None, f"No match for {i}"

    def test_positive_display_has_plus(self, capsys):
        """Positive fudge results should show + prefix."""
        data = load_table_file(example_path("fudge-dice.yml"))
        table = data["tables"][0]
        for seed in range(200):
            random.seed(seed)
            result = roll_fudge(4)
            if result > 0:
                random.seed(seed)
                roll_on_table(table, data["tables"])
                out = capsys.readouterr().out
                assert f"+{result}" in out
                return
        pytest.skip("Could not find positive fudge result")


class TestRollOnTableCardDraw:
    """Tests using card-draw.yml."""

    def test_card_drawn(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("card-draw.yml"))
        table = data["tables"][0]
        roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "Fortune Reading" in out
        assert "→" in out

    def test_multiple_seeds_produce_results(self, capsys):
        data = load_table_file(example_path("card-draw.yml"))
        table = data["tables"][0]
        for seed in range(20):
            random.seed(seed)
            roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        # Most draws should match something
        lines = [l for l in out.strip().split("\n") if l]
        matched = sum(1 for l in lines if "(no match)" not in l)
        assert matched >= 15  # at least 75% match rate


class TestRollOnTableSuitDomains:
    """Tests using suit-domains.yml."""

    def test_suit_domain_shown(self, capsys):
        data = load_table_file(example_path("suit-domains.yml"))
        table = data["tables"][0]
        domains = {"Emotional / Personal", "Physical / Material",
                    "Cerebral / Knowledge", "Social / Relational"}
        for seed in range(50):
            random.seed(seed)
            roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        # At least one domain should appear
        assert any(d in out for d in domains)


class TestRollOnTableTarotDraw:
    """Tests using tarot-draw.yml."""

    def test_tarot_draw(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("tarot-draw.yml"))
        table = data["tables"][0]
        roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "Tarot Omen" in out


class TestRollOnTableCustomDeck:
    """Tests using custom-deck.yml."""

    def test_custom_cards_loaded(self):
        data = load_table_file(example_path("custom-deck.yml"))
        table = data["tables"][0]
        cards_config = table["roll"]["cards"]
        assert cards_config["deck"] == "custom"
        assert len(cards_config["custom_cards"]) == 6

    def test_all_custom_cards_match(self, capsys):
        data = load_table_file(example_path("custom-deck.yml"))
        table = data["tables"][0]
        for seed in range(20):
            random.seed(seed)
            roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "(no match)" not in out


class TestRollOnTableDiceModifier:
    """Tests using dice-modifier.yml."""

    def test_d8_plus_2_range(self, capsys):
        data = load_table_file(example_path("dice-modifier.yml"))
        table = data["tables"][0]
        for seed in range(30):
            random.seed(seed)
            roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "(no match)" not in out

    def test_full_range_coverage(self):
        """Every value 3-10 should match."""
        data = load_table_file(example_path("dice-modifier.yml"))
        entries = data["tables"][0]["entries"]
        for i in range(3, 11):
            assert match_dice_entry(entries, i) is not None, f"No match for {i}"


class TestRollOnTableLookup:
    """Tests using lookup.yml."""

    def test_lookup_displays_all_entries(self, capsys):
        data = load_table_file(example_path("lookup.yml"))
        table = data["tables"][0]
        roll_on_table(table, data["tables"])
        out = capsys.readouterr().out
        assert "forest" in out
        assert "mountain" in out
        assert "swamp" in out
        assert "desert" in out
        assert "coast" in out
        assert "lookup table" in out

    def test_lookup_inline(self, capsys):
        data = load_table_file(example_path("lookup.yml"))
        table = data["tables"][0]
        roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "Terrain Types" in out
        lines = out.strip().split("\n")
        assert len(lines) == 1  # all on one line


class TestRollOnTableWeighted:
    """Tests using weighted.yml."""

    def test_weighted_produces_results(self, capsys):
        data = load_table_file(example_path("weighted.yml"))
        table = data["tables"][0]
        for seed in range(20):
            random.seed(seed)
            roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        lines = out.strip().split("\n")
        assert all("→" in l for l in lines)

    def test_weighted_distribution(self):
        """Higher weight items should appear more often."""
        random.seed(42)
        data = load_table_file(example_path("weighted.yml"))
        table = data["tables"][0]
        entries = table["entries"]
        weights = [e["weight"] for e in entries]
        results = []
        for _ in range(1000):
            entry = random.choices(entries, weights=weights, k=1)[0]
            results.append(entry["result"])
        # "Wandering deer" (weight 10) should be most common
        deer_count = results.count("Wandering deer (no threat)")
        treant_count = results.count("Ancient treant")
        assert deer_count > treant_count


class TestRollOnTableSplitDice:
    """Tests using split-dice.yml."""

    def test_split_dice_inline(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("split-dice.yml"))
        table = data["tables"][0]
        roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "Simple Oracle" in out
        assert "Action:" in out
        assert "Subject:" in out

    def test_split_dice_multiline(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("split-dice.yml"))
        table = data["tables"][0]
        roll_on_table(table, data["tables"])
        out = capsys.readouterr().out
        assert "split" in out
        assert "Action" in out
        assert "Subject" in out

    def test_no_table_level_entries(self):
        data = load_table_file(example_path("split-dice.yml"))
        table = data["tables"][0]
        # split_dice tables should have entries in axes, not at table level
        assert table.get("entries", []) == [] or "entries" not in table

    def test_all_rolls_match(self, capsys):
        data = load_table_file(example_path("split-dice.yml"))
        table = data["tables"][0]
        for seed in range(30):
            random.seed(seed)
            roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "(no match)" not in out


class TestRollOnTableThreshold:
    """Tests using threshold.yml."""

    def test_full_range_coverage(self):
        """Every 2d6 result (2-12) should match."""
        data = load_table_file(example_path("threshold.yml"))
        entries = data["tables"][0]["entries"]
        for i in range(2, 13):
            assert match_dice_entry(entries, i) is not None, f"No match for {i}"

    def test_threshold_low_end(self):
        data = load_table_file(example_path("threshold.yml"))
        entries = data["tables"][0]["entries"]
        entry = match_dice_entry(entries, 2)
        assert entry["result"] == "Rout — flee in panic"

    def test_threshold_high_end(self):
        data = load_table_file(example_path("threshold.yml"))
        entries = data["tables"][0]["entries"]
        entry = match_dice_entry(entries, 12)
        assert entry["result"] == "Rally — counterattack with fury"


class TestRollOnTableSingleTable:
    """Tests using single-table.yml."""

    def test_coin_flip(self, capsys):
        data = load_table_file(example_path("single-table.yml"))
        table = data["tables"][0]
        results = set()
        for seed in range(20):
            random.seed(seed)
            roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "Heads" in out or "Tails" in out

    def test_normalised_from_singular(self):
        data = load_table_file(example_path("single-table.yml"))
        assert "tables" in data
        assert len(data["tables"]) == 1


# ---------------------------------------------------------------------------
# Select column mode
# ---------------------------------------------------------------------------


class TestSelectColumnMode:
    """Tests using select-column.yml."""

    def test_select_column_structure(self):
        data = load_table_file(example_path("select-column.yml"))
        table = data["tables"][0]
        assert table.get("column_mode") == "select"
        assert len(table["columns"]) == 3

    def test_select_column_inline(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("select-column.yml"))
        table = data["tables"][0]
        selected = {"id": "elf", "name": "Elf"}
        roll_on_table(table, data["tables"], inline=True, selected_column=selected)
        out = capsys.readouterr().out
        assert "Fantasy Names by Race" in out
        # Should show only the elf name, not human/dwarf
        elf_names = {"Thalion", "Aelindra", "Faenor", "Isilmë", "Caladrel", "Nyriel", "Viressë", "Lórien"}
        assert any(name in out for name in elf_names)

    def test_select_column_prompts_when_no_selection(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("select-column.yml"))
        table = data["tables"][0]
        with patch("builtins.input", return_value="1"):
            roll_on_table(table, data["tables"], inline=True)
        out = capsys.readouterr().out
        assert "Select a column" in out
        human_names = {"Aldric", "Bera", "Cassius", "Duna", "Elowen", "Falk", "Grenna", "Henrik"}
        assert any(name in out for name in human_names)

    def test_select_column_multiline(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("select-column.yml"))
        table = data["tables"][0]
        selected = {"id": "dwarf", "name": "Dwarf"}
        roll_on_table(table, data["tables"], selected_column=selected)
        out = capsys.readouterr().out
        dwarf_names = {"Durin", "Gimra", "Thorek", "Bruna", "Haldrek", "Orla", "Balin", "Keldra"}
        assert any(name in out for name in dwarf_names)

    def test_all_columns_produce_valid_results(self, capsys):
        data = load_table_file(example_path("select-column.yml"))
        table = data["tables"][0]
        for col in table["columns"]:
            random.seed(42)
            roll_on_table(table, data["tables"], inline=True, selected_column=col)
        out = capsys.readouterr().out
        assert "(no match)" not in out


# ---------------------------------------------------------------------------
# Choice column mode
# ---------------------------------------------------------------------------


class TestChoiceColumnMode:
    """Tests using prefix-suffix-choice.yml (choice mode tables)."""

    def test_choice_mode_structure(self):
        data = load_table_file(example_path("prefix-suffix-choice.yml"))
        for table in data["tables"]:
            assert table.get("column_mode") == "choice"

    def test_choice_results_are_arrays(self):
        data = load_table_file(example_path("prefix-suffix-choice.yml"))
        for table in data["tables"]:
            for entry in table["entries"]:
                assert isinstance(entry["result"], list)
                assert len(entry["result"]) >= 2

    def test_choice_format_inline(self):
        entry = {"result": ["Aldric", "Aldwin"]}
        result = format_result(entry, None, inline=True, column_mode="choice")
        assert result == "Aldric / Aldwin"

    def test_choice_format_multiline(self):
        entry = {"result": ["Bera", "Brynn"]}
        result = format_result(entry, None, inline=False, column_mode="choice")
        assert "Bera" in result
        assert "Brynn" in result


# ---------------------------------------------------------------------------
# Prefix-suffix combine
# ---------------------------------------------------------------------------


class TestPrefixSuffix:
    """Tests using prefix-suffix.yml."""

    def test_combine_structure(self):
        data = load_table_file(example_path("prefix-suffix.yml"))
        tables = data["tables"]
        assert len(tables) == 2
        roles = {t["combine"]["role"] for t in tables}
        assert roles == {"prefix", "suffix"}
        groups = {t["combine"]["group"] for t in tables}
        assert len(groups) == 1  # same group

    def test_combine_inline(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("prefix-suffix.yml"))
        tables = data["tables"]
        group_tables = [t for t in tables if t.get("combine", {}).get("group") == "weapon_name"]
        roll_combine_group(group_tables, tables, inline=True)
        out = capsys.readouterr().out
        assert "weapon_name" in out
        assert "→" in out
        # Should be two words separated by space
        parts = out.strip().split("→")[1].strip().split(" ")
        assert len(parts) == 2

    def test_combine_multiline(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("prefix-suffix.yml"))
        tables = data["tables"]
        group_tables = [t for t in tables if t.get("combine", {}).get("group") == "weapon_name"]
        roll_combine_group(group_tables, tables, inline=False)
        out = capsys.readouterr().out
        assert "weapon_name" in out

    def test_combine_produces_valid_combinations(self, capsys):
        data = load_table_file(example_path("prefix-suffix.yml"))
        tables = data["tables"]
        group_tables = [t for t in tables if t.get("combine", {}).get("group") == "weapon_name"]
        adjs = {e["result"] for e in group_tables[0]["entries"]}
        nouns = {e["result"] for e in group_tables[1]["entries"]}
        for seed in range(20):
            random.seed(seed)
            roll_combine_group(group_tables, tables, inline=True)
        out = capsys.readouterr().out
        for line in out.strip().split("\n"):
            result = line.split("→")[1].strip()
            adj, noun = result.split(" ", 1)
            assert adj in adjs
            assert noun in nouns

    def test_auto_detected_via_find_table(self):
        data = load_table_file(example_path("prefix-suffix.yml"))
        t = find_table(data, None)
        assert t.get("combine") is not None


class TestPrefixSuffixColumns:
    """Tests using prefix-suffix-columns.yml."""

    def test_structure(self):
        data = load_table_file(example_path("prefix-suffix-columns.yml"))
        tables = data["tables"]
        assert len(tables) == 2
        for t in tables:
            assert t.get("column_mode") == "select"
            assert len(t["columns"]) == 3

    def test_combine_with_select(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("prefix-suffix-columns.yml"))
        tables = data["tables"]
        group_tables = [t for t in tables if t.get("combine", {}).get("group") == "full_name"]

        # Manually select elf column
        with patch("dice_cards.tables.prompt_column_select",
                    return_value={"id": "elf", "name": "Elf"}):
            roll_combine_group(group_tables, tables, inline=True)
        out = capsys.readouterr().out
        assert "full_name" in out
        # Result should be two elf names
        result = out.strip().split("→")[1].strip()
        parts = result.split(" ")
        assert len(parts) == 2

    def test_elf_names_only(self, capsys):
        """When elf column is selected, only elf names should appear."""
        data = load_table_file(example_path("prefix-suffix-columns.yml"))
        tables = data["tables"]
        group_tables = [t for t in tables if t.get("combine", {}).get("group") == "full_name"]

        elf_first = set()
        elf_last = set()
        for t in group_tables:
            for e in t["entries"]:
                if t["combine"]["role"] == "prefix":
                    elf_first.add(e["result"]["elf"])
                else:
                    elf_last.add(e["result"]["elf"])

        for seed in range(20):
            random.seed(seed)
            with patch("dice_cards.tables.prompt_column_select",
                        return_value={"id": "elf", "name": "Elf"}):
                roll_combine_group(group_tables, tables, inline=True)
        out = capsys.readouterr().out
        for line in out.strip().split("\n"):
            result = line.split("→")[1].strip()
            first, last = result.split(" ", 1)
            assert first in elf_first, f"'{first}' not an elf first name"
            assert last in elf_last, f"'{last}' not an elf surname"


class TestPrefixSuffixChoice:
    """Tests using prefix-suffix-choice.yml."""

    def test_structure(self):
        data = load_table_file(example_path("prefix-suffix-choice.yml"))
        tables = data["tables"]
        assert len(tables) == 2
        for t in tables:
            assert t.get("column_mode") == "choice"
            assert t.get("combine") is not None

    def test_combine_choice_inline(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("prefix-suffix-choice.yml"))
        tables = data["tables"]
        group_tables = [t for t in tables if t.get("combine", {}).get("group") == "human_name"]
        with patch("dice_cards.tables.rolling.prompt_choice_select", return_value="Aldric"):
            roll_combine_group(group_tables, tables, inline=True)
        out = capsys.readouterr().out
        assert "human_name" in out
        assert "Aldric" in out

    def test_combine_choice_multiline(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("prefix-suffix-choice.yml"))
        tables = data["tables"]
        group_tables = [t for t in tables if t.get("combine", {}).get("group") == "human_name"]
        with patch("dice_cards.tables.rolling.prompt_choice_select", return_value="Bera"):
            roll_combine_group(group_tables, tables, inline=False)
        out = capsys.readouterr().out
        assert "human_name" in out
        assert "Bera" in out


# ---------------------------------------------------------------------------
# Return-result mode (used internally by combine)
# ---------------------------------------------------------------------------


class TestReturnResultMode:
    """Tests for _return_result=True in roll_on_table."""

    def test_dice_return_result(self):
        random.seed(42)
        data = load_table_file(example_path("simple-d6.yml"))
        table = data["tables"][0]
        result = roll_on_table(table, data["tables"], _return_result=True)
        assert isinstance(result, str)
        assert result != ""
        assert result != "(no match)"

    def test_weighted_return_result(self):
        random.seed(42)
        data = load_table_file(example_path("weighted.yml"))
        table = data["tables"][0]
        result = roll_on_table(table, data["tables"], _return_result=True)
        assert isinstance(result, str)
        expected = {"Pack of wolves", "Wandering deer (no threat)", "Bandit ambush",
                    "Fey trickster", "Ancient treant"}
        assert result in expected

    def test_card_return_result(self):
        random.seed(42)
        data = load_table_file(example_path("card-draw.yml"))
        table = data["tables"][0]
        result = roll_on_table(table, data["tables"], _return_result=True)
        assert isinstance(result, str)

    def test_return_result_with_selected_column(self):
        random.seed(42)
        data = load_table_file(example_path("select-column.yml"))
        table = data["tables"][0]
        selected = {"id": "human", "name": "Human"}
        result = roll_on_table(table, data["tables"], _return_result=True,
                               selected_column=selected)
        human_names = {"Aldric", "Bera", "Cassius", "Duna", "Elowen", "Falk", "Grenna", "Henrik"}
        assert result in human_names

    def test_return_result_choice_mode(self):
        random.seed(42)
        data = load_table_file(example_path("prefix-suffix-choice.yml"))
        table = data["tables"][0]
        with patch("dice_cards.tables.rolling.prompt_choice_select", return_value="Aldric"):
            result = roll_on_table(table, data["tables"], _return_result=True)
        assert result == "Aldric"


# ---------------------------------------------------------------------------
# Modifier clamping with table roll
# ---------------------------------------------------------------------------


class TestModifierClamping:
    """Tests for -m modifier with table rolls."""

    def test_modifier_applied_and_clamped(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("simple-d6.yml"))
        table = data["tables"][0]
        # Apply a +10 modifier — should be clamped to max entry (6)
        roll_on_table(table, data["tables"], modifier=10, inline=True)
        out = capsys.readouterr().out
        assert "(no match)" not in out

    def test_negative_modifier_clamped(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("simple-d6.yml"))
        table = data["tables"][0]
        roll_on_table(table, data["tables"], modifier=-10, inline=True)
        out = capsys.readouterr().out
        assert "(no match)" not in out

    def test_modifier_shown_in_output(self, capsys):
        random.seed(42)
        data = load_table_file(example_path("simple-d6.yml"))
        table = data["tables"][0]
        roll_on_table(table, data["tables"], modifier=2, inline=True)
        out = capsys.readouterr().out
        assert "+ 2" in out


# ---------------------------------------------------------------------------
# All example files load successfully
# ---------------------------------------------------------------------------


class TestAllExamplesLoad:
    """Verify every example file loads without error."""

    EXAMPLE_FILES = [
        "simple-d6.yml",
        "range-d100.yml",
        "bell-curve-2d6.yml",
        "multi-column.yml",
        "nested-subtable.yml",
        "fudge-dice.yml",
        "card-draw.yml",
        "suit-domains.yml",
        "tarot-draw.yml",
        "custom-deck.yml",
        "dice-modifier.yml",
        "lookup.yml",
        "weighted.yml",
        "split-dice.yml",
        "threshold.yml",
        "single-table.yml",
        "select-column.yml",
        "prefix-suffix.yml",
        "prefix-suffix-columns.yml",
        "prefix-suffix-choice.yml",
    ]

    @pytest.mark.parametrize("filename", EXAMPLE_FILES)
    def test_loads_successfully(self, filename):
        data = load_table_file(example_path(filename))
        assert "tables" in data
        assert len(data["tables"]) >= 1

    @pytest.mark.parametrize("filename", EXAMPLE_FILES)
    def test_has_schema_version(self, filename):
        data = load_table_file(example_path(filename))
        assert data.get("schema_version") == "1.0"

    @pytest.mark.parametrize("filename", EXAMPLE_FILES)
    def test_tables_have_required_fields(self, filename):
        data = load_table_file(example_path(filename))
        for table in data["tables"]:
            assert "id" in table, f"Missing id in {filename}"
            assert "name" in table, f"Missing name in {filename}"
            assert "roll" in table, f"Missing roll in {filename}"


# ---------------------------------------------------------------------------
# Schema validation (--check)
# ---------------------------------------------------------------------------


class TestCheckTableFile:
    """Tests for check_table_file() schema validation."""

    EXAMPLE_FILES = TestAllExamplesLoad.EXAMPLE_FILES

    @pytest.mark.parametrize("filename", EXAMPLE_FILES)
    def test_all_examples_pass_validation(self, filename):
        """Every example file should pass validation with zero errors."""
        data = load_table_file(example_path(filename))
        errors = check_table_file(data)
        assert errors == [], f"{filename} had errors: {errors}"

    def test_missing_schema_version(self):
        data = {"tables": [{"id": "t", "name": "T", "roll": {"dice": "d6"},
                            "entries": [{"on": 1, "result": "a"}]}]}
        errors = check_table_file(data)
        assert any("schema_version" in e for e in errors)

    def test_wrong_schema_version(self):
        data = {"schema_version": "2.0",
                "tables": [{"id": "t", "name": "T", "roll": {"dice": "d6"},
                            "entries": [{"on": 1, "result": "a"}]}]}
        errors = check_table_file(data)
        assert any("2.0" in e for e in errors)

    def test_missing_tables(self):
        data = {"schema_version": "1.0"}
        errors = check_table_file(data)
        assert any("tables" in e for e in errors)

    def test_duplicate_table_id(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "dup", "name": "A", "roll": {"dice": "d6"},
             "entries": [{"on": 1, "result": "x"}]},
            {"id": "dup", "name": "B", "roll": {"dice": "d6"},
             "entries": [{"on": 1, "result": "y"}]},
        ]}
        errors = check_table_file(data)
        assert any("duplicate" in e for e in errors)

    def test_missing_required_fields(self):
        data = {"schema_version": "1.0", "tables": [{"roll": {"dice": "d6"}}]}
        errors = check_table_file(data)
        assert any("id" in e for e in errors)
        assert any("name" in e for e in errors)

    def test_multiple_roll_keys(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "t", "name": "T", "roll": {"dice": "d6", "weighted": True},
             "entries": [{"on": 1, "result": "x"}]}
        ]}
        errors = check_table_file(data)
        assert any("exactly one" in e for e in errors)

    def test_dice_gap_detected(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "t", "name": "T", "roll": {"dice": "d6"},
             "entries": [
                 {"on": 1, "result": "a"},
                 {"on": 3, "result": "c"},  # gap at 2
             ]}
        ]}
        errors = check_table_file(data)
        assert any("gap" in e for e in errors)

    def test_dice_overlap_detected(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "t", "name": "T", "roll": {"dice": "d6"},
             "entries": [
                 {"on": "1-3", "result": "a"},
                 {"on": "3-6", "result": "b"},  # overlap at 3
             ]}
        ]}
        errors = check_table_file(data)
        assert any("overlap" in e for e in errors)

    def test_weighted_missing_weight(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "t", "name": "T", "roll": {"weighted": True},
             "entries": [{"result": "x"}]}  # no weight
        ]}
        errors = check_table_file(data)
        assert any("weight" in e for e in errors)

    def test_weighted_zero_weight(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "t", "name": "T", "roll": {"weighted": True},
             "entries": [{"result": "x", "weight": 0}]}
        ]}
        errors = check_table_file(data)
        assert any("positive integer" in e for e in errors)

    def test_bad_ref(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "t", "name": "T", "roll": {"dice": "d6"},
             "entries": [{"on": 1, "result": "x", "ref": "nonexistent"}]}
        ]}
        errors = check_table_file(data)
        assert any("nonexistent" in e for e in errors)

    def test_column_mode_select_without_columns(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "t", "name": "T", "roll": {"dice": "d6"}, "column_mode": "select",
             "entries": [{"on": 1, "result": "x"}]}
        ]}
        errors = check_table_file(data)
        assert any("columns" in e for e in errors)

    def test_column_mode_choice_with_columns(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "t", "name": "T", "roll": {"dice": "d6"}, "column_mode": "choice",
             "columns": [{"id": "a", "name": "A"}],
             "entries": [{"on": 1, "result": ["x"]}]}
        ]}
        errors = check_table_file(data)
        assert any("choice" in e and "columns" in e for e in errors)

    def test_result_key_mismatch(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "t", "name": "T", "roll": {"dice": "d6"},
             "columns": [{"id": "a", "name": "A"}],
             "entries": [{"on": 1, "result": {"b": "x"}}]}
        ]}
        errors = check_table_file(data)
        assert any("not in columns" in e for e in errors)

    def test_suit_domains_on_non_card(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "t", "name": "T", "roll": {"dice": "d6"},
             "suit_domains": {"hearts": "Love"},
             "entries": [{"on": 1, "result": "x"}]}
        ]}
        errors = check_table_file(data)
        assert any("suit_domains" in e for e in errors)

    def test_combine_missing_suffix(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "a", "name": "A", "roll": {"dice": "d6"},
             "combine": {"group": "g", "role": "prefix"},
             "entries": [{"on": 1, "result": "x"}]}
        ]}
        errors = check_table_file(data)
        assert any("missing suffix" in e for e in errors)

    def test_split_dice_with_table_entries(self):
        data = {"schema_version": "1.0", "tables": [
            {"id": "t", "name": "T", "roll": {"split_dice": [
                {"id": "a", "name": "A", "dice": "d6",
                 "entries": [{"on": 1, "result": "x"}]}
            ]}, "entries": [{"on": 1, "result": "bad"}]}
        ]}
        errors = check_table_file(data)
        assert any("table-level" in e for e in errors)


class TestRunCheck:
    """Tests for the --check CLI command."""

    def test_valid_file(self, capsys):
        _run_check([example_path("simple-d6.yml")])
        out = capsys.readouterr().out
        assert "ok" in out

    def test_multiple_files(self, capsys):
        _run_check([example_path("simple-d6.yml"), example_path("weighted.yml")])
        out = capsys.readouterr().out
        assert out.count("ok") == 2

    def test_no_args_exits(self):
        with pytest.raises(SystemExit):
            _run_check([])


# ---------------------------------------------------------------------------
# Metadata display (--metadata)
# ---------------------------------------------------------------------------


class TestRunMetadata:
    """Tests for the --metadata CLI command."""

    def test_shows_metadata(self, capsys):
        _run_metadata([example_path("simple-d6.yml")])
        out = capsys.readouterr().out
        assert "1.0" in out
        assert "Simple d6 Table Example" in out
        assert "Table Schema Project" in out

    def test_shows_table_count(self, capsys):
        _run_metadata([example_path("prefix-suffix.yml")])
        out = capsys.readouterr().out
        assert "Tables" in out
        assert "2" in out

    def test_shows_table_names(self, capsys):
        _run_metadata([example_path("multi-column.yml")])
        out = capsys.readouterr().out
        assert "Random Tavern Patron" in out

    def test_no_args_exits(self):
        with pytest.raises(SystemExit):
            _run_metadata([])


# ---------------------------------------------------------------------------
# Table print (--print)
# ---------------------------------------------------------------------------


class TestRunPrint:
    """Tests for the --print CLI command."""

    def test_prints_simple_table(self, capsys):
        _run_print([example_path("simple-d6.yml")])
        out = capsys.readouterr().out
        assert "Wandering NPC Mood" in out
        assert "Hostile" in out
        assert "Generous" in out

    def test_prints_multi_column(self, capsys):
        _run_print([example_path("multi-column.yml")])
        out = capsys.readouterr().out
        assert "Name:" in out
        assert "Occupation:" in out
        assert "Aldric" in out

    def test_prints_weighted(self, capsys):
        _run_print([example_path("weighted.yml")])
        out = capsys.readouterr().out
        assert "Pack of wolves" in out
        assert "w:" in out

    def test_prints_card_table(self, capsys):
        _run_print([example_path("card-draw.yml")])
        out = capsys.readouterr().out
        assert "Fortune Reading" in out
        assert "suit:hearts" in out

    def test_prints_split_dice(self, capsys):
        _run_print([example_path("split-dice.yml")])
        out = capsys.readouterr().out
        assert "Action" in out
        assert "Subject" in out

    def test_prints_choice(self, capsys):
        _run_print([example_path("prefix-suffix-choice.yml")])
        out = capsys.readouterr().out
        assert "Aldric / Aldwin" in out

    def test_prints_select_column(self, capsys):
        _run_print([example_path("select-column.yml")])
        out = capsys.readouterr().out
        assert "Columns" in out
        assert "Human" in out

    def test_prints_subtable_ref(self, capsys):
        _run_print([example_path("nested-subtable.yml"), "treasure_hoard"])
        out = capsys.readouterr().out
        assert "subtable" in out
        assert "ref" in out

    def test_no_args_exits(self):
        with pytest.raises(SystemExit):
            _run_print([])

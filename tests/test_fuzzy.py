"""
Tests for fuzzy matching logic.

Covers the three match strategies in fuzzy_match_ted, Kompas matching,
and the change-detection helper.
"""
import pandas as pd
import pytest

from investment_monitor.matching.fuzzy import (
    fuzzy_match_ted,
    fuzzy_match_kompas,
    detect_changes,
    build_id_index,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_df(*rows):
    """Build a minimal DataFrame with the columns fuzzy matching needs."""
    cols = ["Inwestycja", "Miejscowość", "Inwestor", "Status inwestycji", "Linki"]
    data = []
    for r in rows:
        data.append({
            "Inwestycja":         r.get("name", ""),
            "Miejscowość":        r.get("city", ""),
            "Inwestor":           r.get("investor", ""),
            "Status inwestycji":  r.get("status", "Budowa"),
            "Linki":              r.get("link", ""),
        })
    return pd.DataFrame(data, columns=cols)


# ── fuzzy_match_ted ───────────────────────────────────────────────────────────

class TestFuzzyMatchTed:

    def test_name_and_city_match(self):
        df = make_df({"name": "Budowa drogi S7 Radom", "city": "Radom"})
        item = {"Inwestycja": "Budowa drogi S7 Radom", "Miejscowość": "Radom"}
        idx, score, mtype = fuzzy_match_ted(item, df)
        assert idx == 0
        assert score >= 0.90
        assert mtype == "name+city"

    def test_name_and_investor_match(self):
        df = make_df({"name": "Rozbudowa oczyszczalni ścieków", "investor": "Wodociągi Miejskie"})
        item = {"Inwestycja": "Rozbudowa oczyszczalni ścieków", "Inwestor": "Wodociągi Miejskie"}
        idx, score, mtype = fuzzy_match_ted(item, df)
        assert idx == 0
        assert score >= 0.85

    def test_name_only_high_similarity(self):
        df = make_df({"name": "Przebudowa mostu na rzece Wisła w Płocku"})
        item = {"Inwestycja": "Przebudowa mostu na rzece Wisła w Płocku"}
        idx, score, mtype = fuzzy_match_ted(item, df)
        assert idx == 0
        assert mtype == "name_only"

    def test_suffix_stripped_before_compare(self):
        """TED title with '- modernizacja' suffix should still match DB entry without it."""
        df = make_df({"name": "Linia kolejowa nr 9 Warszawa–Gdańsk", "city": "Warszawa"})
        item = {
            "Inwestycja": "Linia kolejowa nr 9 Warszawa–Gdańsk - modernizacja",
            "Miejscowość": "Warszawa",
        }
        idx, score, _ = fuzzy_match_ted(item, df)
        assert idx == 0

    def test_no_match_below_threshold(self):
        df = make_df({"name": "Budowa elektrowni słonecznej Kozia Góra"})
        item = {"Inwestycja": "Przebudowa oczyszczalni ścieków Poznań"}
        idx, score, mtype = fuzzy_match_ted(item, df)
        assert idx is None
        assert score == 0

    def test_skips_zakonczona_rows(self):
        df = make_df({"name": "Most Łazienkowski Warszawa", "status": "Inwestycja zakończona"})
        item = {"Inwestycja": "Most Łazienkowski Warszawa", "Miejscowość": "Warszawa"}
        idx, score, _ = fuzzy_match_ted(item, df)
        assert idx is None

    def test_empty_name_returns_none(self):
        df = make_df({"name": "Cokolwiek"})
        idx, score, mtype = fuzzy_match_ted({"Inwestycja": ""}, df)
        assert idx is None
        assert mtype is None

    def test_picks_best_of_multiple_candidates(self):
        df = make_df(
            {"name": "Budowa szkoły podstawowej Kraków", "city": "Kraków"},
            {"name": "Budowa szkoły podstawowej Nowa Huta", "city": "Nowa Huta"},
        )
        item = {"Inwestycja": "Budowa szkoły podstawowej Kraków", "Miejscowość": "Kraków"}
        idx, score, _ = fuzzy_match_ted(item, df)
        assert idx == 0


# ── fuzzy_match_kompas ────────────────────────────────────────────────────────

class TestFuzzyMatchKompas:

    def test_exact_name_match(self):
        df = make_df({"name": "Budowa obwodnicy Mszczonowa", "city": "Mszczonów"})
        data = {"Inwestycja": "Budowa obwodnicy Mszczonowa", "Miejscowość": "Mszczonów"}
        idx, score = fuzzy_match_kompas(data, df)
        assert idx == 0
        assert score >= 0.90

    def test_skips_rows_with_kompas_link(self):
        df = make_df({"name": "Budowa mostu", "link": "https://kompasinwestycji.pl/inwestycja-123"})
        data = {"Inwestycja": "Budowa mostu", "Miejscowość": ""}
        idx, score = fuzzy_match_kompas(data, df)
        assert idx is None

    def test_no_match_dissimilar_names(self):
        df = make_df({"name": "Rozbudowa lotniska Katowice"})
        data = {"Inwestycja": "Przebudowa drogi krajowej nr 1"}
        idx, score = fuzzy_match_kompas(data, df)
        assert idx is None


# ── detect_changes ────────────────────────────────────────────────────────────

class TestDetectChanges:

    def _row(self, **kwargs):
        return pd.Series(kwargs)

    def test_detects_etap_change(self):
        row  = self._row(**{"Etap kompas": "Planowanie"})
        new  = {"Etap kompas": "Budowa"}
        cols = ["Etap kompas"]
        assert "Etap kompas" in detect_changes(row, new, cols)

    def test_no_change_same_values(self):
        row  = self._row(**{"Etap kompas": "Budowa"})
        new  = {"Etap kompas": "Budowa"}
        cols = ["Etap kompas"]
        assert detect_changes(row, new, cols) == []

    def test_empty_kompas_value_ignored(self):
        row  = self._row(**{"Etap kompas": "Budowa"})
        new  = {"Etap kompas": ""}
        cols = ["Etap kompas"]
        assert detect_changes(row, new, cols) == []

    def test_ostatni_status_compares_date_prefix_only(self):
        row  = self._row(**{"Ostatni status": "2025-03-01 - Przetarg ogłoszony\nSzczegóły..."})
        same = {"Ostatni status": "2025-03-01 - Przetarg ogłoszony\nInna treść"}
        diff = {"Ostatni status": "2025-06-15 - Podpisano umowę\nNowe info"}
        assert detect_changes(row, same, ["Ostatni status"]) == []
        assert detect_changes(row, diff, ["Ostatni status"]) == ["Ostatni status"]


# ── build_id_index ────────────────────────────────────────────────────────────

class TestBuildIdIndex:

    def test_extracts_id_from_kompas_link(self):
        df = make_df({"link": "https://kompasinwestycji.pl/budowa-mostu-123"})
        index = build_id_index(df)
        assert "123" in index

    def test_ignores_non_kompas_links(self):
        df = make_df({"link": "https://ted.europa.eu/notice/12345"})
        index = build_id_index(df)
        assert index == {}

    def test_empty_dataframe(self):
        df = make_df()
        index = build_id_index(df)
        assert index == {}

"""
Tests for the TED name normaliser.

Each test case is taken from a real TED notice title that was handled
incorrectly at some point during development — these are regression tests,
not toy examples.
"""
import pytest
from investment_monitor.ted.normalizer import (
    normalize_ted_name,
    is_construction,
    _normalize_road,
    _normalize_rail,
    _normalize_tram,
)


# ── Road normalisation ─────────────────────────────────────────────────────────

class TestNormalizeRoad:

    def test_express_road_with_section(self):
        result, _ = normalize_ted_name(
            "Budowa drogi ekspresowej S8 Wrocław-Kłodzko, zad. 4 - odc. węzeł Łagiewniki Zachód - węzeł Niemcza"
        )
        assert result == "S8 Łagiewniki Zachód-Niemcza"

    def test_bypass_with_road_number(self):
        result, _ = normalize_ted_name(
            "Budowa obwodnicy Sidziny w ciągu drogi krajowej nr 46"
        )
        assert result == "DK46 Obwodnica Sidziny"

    def test_expressway_endpoints(self):
        result, _ = normalize_ted_name(
            "Rozbudowa drogi ekspresowej S7 Radom-Kielce"
        )
        assert "S7" in result
        assert "rozbudowa" in result.lower()

    def test_national_road(self):
        result, _ = normalize_ted_name(
            "Przebudowa drogi krajowej nr 75 Brzesko-Nowy Sącz"
        )
        assert "DK75" in result
        assert "przebudowa" in result.lower()

    def test_city_suffix_extracted(self):
        _, city = normalize_ted_name(
            "Budowa oczyszczalni ścieków w Krakowie"
        )
        assert city == "Krakowie" or "Krak" in city


# ── Rail normalisation ────────────────────────────────────────────────────────

class TestNormalizeRail:

    def test_rail_with_endpoints(self):
        result, _ = normalize_ted_name(
            "Modernizacja linii kolejowej nr 309 Kłodzko Nowe – Kudowa Zdrój"
        )
        assert result == "Linia nr 309 Kłodzko Nowe-Kudowa Zdrój - modernizacja"

    def test_rail_number_only(self):
        result, _ = normalize_ted_name(
            "Remont linii kolejowej nr 131"
        )
        assert result == "Linia nr 131 - remont"

    def test_lk_prefix_converted(self):
        # LK prefix should be normalised to "Linia nr" via normalize_inv_name
        result, _ = normalize_ted_name("Modernizacja LK65")
        assert "Linia nr 65" in result

    def test_rail_endpoint_dash_separator(self):
        result, _ = normalize_ted_name(
            "Budowa linii kolejowej nr 582 Warszawa Wschodnia - Warszawa Gdańska"
        )
        assert "Linia nr 582" in result
        assert "Warszawa Wschodnia" in result or "Warszawa Gdańska" in result


# ── Tram normalisation ────────────────────────────────────────────────────────

class TestNormalizeTram:

    def test_tram_two_streets(self):
        result, _ = normalize_ted_name(
            "Przebudowa torowiska tramwajowego w ul. Aleksandrowskiej i Limanowskiego"
        )
        assert "Linia tramwajowa" in result
        assert "Aleksandrowsk" in result
        assert "przebudowa" in result.lower()

    def test_tram_single_street(self):
        result, _ = normalize_ted_name(
            "Budowa trasy tramwajowej w ul. Nowej"
        )
        assert "Linia tramwajowa" in result or "tramwaj" in result.lower()


# ── Construction filter ───────────────────────────────────────────────────────

class TestIsConstruction:

    def test_construction_title_accepted(self):
        assert is_construction("Budowa drogi ekspresowej S8") is True

    def test_supply_rejected(self):
        assert is_construction("Dostawa sprzętu biurowego") is False

    def test_english_only_rejected(self):
        assert is_construction("Framework Contract for IT Services") is False

    def test_english_with_polish_keywords_accepted(self):
        # Contains Polish construction keyword despite Latin chars
        assert is_construction("Budowa S7 — road construction") is True

    def test_empty_string_rejected(self):
        assert is_construction("") is False

    def test_renovation_accepted(self):
        assert is_construction("Modernizacja linii kolejowej nr 65") is True

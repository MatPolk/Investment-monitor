"""
Tests for shared text utility functions.

These functions handle date conversion, value formatting, and name
normalisation that appears throughout both the Kompas and TED pipelines.
"""
import pytest
from investment_monitor.utils.text import (
    clean_company_name,
    quarter_to_date,
    format_wartosc,
    capitalize_woj,
    parse_city_woj,
    normalize_inv_name,
    parse_wartosc_netto,
)


# ── clean_company_name ────────────────────────────────────────────────────────

class TestCleanCompanyName:

    def test_removes_sa_suffix(self):
        assert clean_company_name("Budimex S.A.") == "Budimex"

    def test_removes_sp_z_oo(self):
        assert clean_company_name("Mota-Engil Sp. z o.o.") == "Mota-Engil"

    def test_removes_parenthetical_role(self):
        assert clean_company_name("Strabag S.A. (lider konsorcjum)") == "Strabag"

    def test_public_body_unchanged(self):
        # Public institutions have no legal-form suffix
        assert clean_company_name("Urząd Miasta Sosnowiec") == "Urząd Miasta Sosnowiec"

    def test_empty_string(self):
        assert clean_company_name("") == ""

    def test_none_returns_none(self):
        assert clean_company_name(None) is None


# ── quarter_to_date ───────────────────────────────────────────────────────────

class TestQuarterToDate:

    def test_q1(self):
        assert quarter_to_date("I kw. 2025") == "01.01.2025"

    def test_q2(self):
        assert quarter_to_date("II kw. 2025") == "01.04.2025"

    def test_q3(self):
        assert quarter_to_date("III kw. 2026") == "01.07.2026"

    def test_q4(self):
        assert quarter_to_date("IV kw. 2028") == "01.10.2028"

    def test_full_word_kwartał(self):
        assert quarter_to_date("II kwartał 2025") == "01.04.2025"

    def test_invalid_returns_none(self):
        assert quarter_to_date("nie wiadomo") is None

    def test_empty_returns_none(self):
        assert quarter_to_date("") is None


# ── format_wartosc ────────────────────────────────────────────────────────────

class TestFormatWartosc:

    def test_decimal(self):
        assert format_wartosc(469.3) == "469,3"

    def test_integer_as_float(self):
        assert format_wartosc(1200.0) == "1200"

    def test_none_returns_empty(self):
        assert format_wartosc(None) == ""

    def test_already_formatted_passthrough(self):
        assert format_wartosc("469,3") == "469,3"

    def test_large_value(self):
        result = format_wartosc(3500.0)
        assert result == "3500"


# ── capitalize_woj ────────────────────────────────────────────────────────────

class TestCapitalizeWoj:

    def test_lowercase_to_capitalized(self):
        assert capitalize_woj("podkarpackie") == "Podkarpackie"

    def test_hyphenated(self):
        assert capitalize_woj("kujawsko-pomorskie") == "Kujawsko-pomorskie"

    def test_already_correct(self):
        assert capitalize_woj("Małopolskie") == "Małopolskie"

    def test_empty(self):
        assert capitalize_woj("") == ""


# ── parse_city_woj ────────────────────────────────────────────────────────────

class TestParseCityWoj:

    def test_city_with_voivodeship(self):
        city, woj = parse_city_woj("Dobrzechów (woj. podkarpackie, powiat strzyżowski)")
        assert city == "Dobrzechów"
        assert woj == "Podkarpackie"

    def test_city_only(self):
        city, woj = parse_city_woj("Kraków")
        assert city == "Kraków"
        assert woj is None


# ── normalize_inv_name ────────────────────────────────────────────────────────

class TestNormalizeInvName:

    def test_lk_to_linia_nr(self):
        assert normalize_inv_name("LK309 Kłodzko Nowe-Kudowa Zdrój") == "Linia nr 309 Kłodzko Nowe-Kudowa Zdrój"

    def test_removes_trailing_comma_after_road(self):
        assert "DW988," not in normalize_inv_name("DW988, Bochnia-Nowy Sącz")

    def test_work_suffix_preserved(self):
        result = normalize_inv_name("S7 Radom-Kielce - modernizacja")
        assert result == "S7 Radom-Kielce - modernizacja"

    def test_work_type_appended_from_desc(self):
        result = normalize_inv_name("S7 Radom-Kielce", work_type_from_desc="modernizacja")
        assert result == "S7 Radom-Kielce - modernizacja"

    def test_en_dash_normalised(self):
        result = normalize_inv_name("Linia nr 309 Kłodzko Nowe – Kudowa Zdrój")
        assert "–" not in result
        assert "Kłodzko Nowe-Kudowa Zdrój" in result


# ── parse_wartosc_netto ───────────────────────────────────────────────────────

class TestParseWartoscNetto:

    def test_mln_string(self):
        result = parse_wartosc_netto("4000 mln")
        assert result == round(4000 / 1.23, 1)

    def test_full_amount_in_pln(self):
        result = parse_wartosc_netto("500 000 000")
        assert result == round(500 / 1.23, 1)

    def test_empty_returns_none(self):
        assert parse_wartosc_netto("") is None

    def test_none_returns_none(self):
        assert parse_wartosc_netto(None) is None

"""
Tests for the investment classifier.

Verifies that the keyword-based classification rules produce the correct
sector, segment, renovation, and military flags for representative cases.
The test cases mirror the actual distribution of investments in the database.
"""
import pytest
from investment_monitor.classify.classifier import classify_investment, kompas_sektor_to_baza


# ── Sector classification ─────────────────────────────────────────────────────

class TestSectorClassification:

    def test_expressway(self):
        r = classify_investment("S7 Radom-Kielce")
        assert r["sektor"] == "Drogi"

    def test_railway(self):
        r = classify_investment("Linia nr 65 Bydgoszcz-Tczew - modernizacja")
        assert r["sektor"] == "Koleje"

    def test_tram_goes_to_koleje(self):
        r = classify_investment("Linia tramwajowa Aleksandrowska-Limanowskiego - przebudowa")
        assert r["sektor"] == "Koleje"

    def test_metro_goes_to_mosty(self):
        # Metro lines are classified as bridges/tunnels, not railways
        r = classify_investment("II linia metra w Warszawie - rozbudowa")
        assert r["sektor"] == "Mosty i tunele"

    def test_viaduct(self):
        r = classify_investment("Wiadukt nad linią kolejową w Poznaniu")
        assert r["sektor"] == "Mosty i tunele"

    def test_wind_farm(self):
        r = classify_investment("Farma wiatrowa Przykładowo - budowa")
        assert r["sektor"] == "Budowle przemysł."

    def test_wastewater_treatment(self):
        r = classify_investment("Oczyszczalnia ścieków w Gdańsku - rozbudowa")
        assert r["sektor"] == "Sieci rozdzielcze"

    def test_hospital(self):
        r = classify_investment("Szpital Kliniczny w Krakowie - rozbudowa")
        assert r["sektor"] == "Użyteczności publicznej"

    def test_residential(self):
        r = classify_investment("Budynki mieszkalne TBS przy ul. Kwiatowej")
        assert r["sektor"] == "Wielomieszkaniowe"

    def test_airport_road(self):
        r = classify_investment("Pas startowy lotniska Warszawa-Okęcie - remont")
        assert r["sektor"] == "Drogi lotniskowe"


# ── Segment classification ────────────────────────────────────────────────────

class TestSegmentClassification:

    def test_nuclear_segment(self):
        r = classify_investment("Elektrownia jądrowa Lubiatowo - budowa reaktora")
        assert r["segment"] == "Elektrownie jądrowe"

    def test_offshore_wind(self):
        r = classify_investment("Morska farma wiatrowa Baltic Power")
        assert r["segment"] == "Morskie elektrownie wiatrowe"

    def test_data_center(self):
        r = classify_investment("Centrum danych w Poznaniu")
        assert r["segment"] == "Centra danych"

    def test_energy_grid(self):
        r = classify_investment("Stacja elektroenergetyczna 400/110 kV")
        assert r["segment"] == "Sieci energetyczne"


# ── Renovation flag ───────────────────────────────────────────────────────────

class TestRenovationFlag:

    def test_modernizacja_flagged(self):
        r = classify_investment("Linia nr 65 - modernizacja")
        assert r["remonty"] == "Remonty, modernizacje, rewitalizacje, przebudowy"

    def test_przebudowa_flagged(self):
        r = classify_investment("DK75 Brzesko-Nowy Sącz - przebudowa")
        assert r["remonty"] == "Remonty, modernizacje, rewitalizacje, przebudowy"

    def test_rozbudowa_not_flagged(self):
        # Expansion (rozbudowa) is NOT a renovation
        r = classify_investment("Szpital w Krakowie - rozbudowa")
        assert r["remonty"] is None

    def test_new_construction_not_flagged(self):
        r = classify_investment("S7 Radom-Kielce")
        assert r["remonty"] is None


# ── Military flag ─────────────────────────────────────────────────────────────

class TestMilitaryFlag:

    def test_rzi_investor(self):
        r = classify_investment("Budynek koszarowy", investor="RZI Wrocław")
        assert r["wojsko"] == "Inwestycje wojskowe"

    def test_military_name(self):
        r = classify_investment("Budynki koszarowe 12 Brygady Zmechanizowanej")
        assert r["wojsko"] == "Inwestycje wojskowe"

    def test_civilian_not_flagged(self):
        r = classify_investment("Szkoła Podstawowa nr 5 w Gdańsku", investor="Gmina Gdańsk")
        assert r["wojsko"] is None


# ── Kompas sector fallback ────────────────────────────────────────────────────

class TestKompasSektorFallback:

    def test_transport_szynowy(self):
        assert kompas_sektor_to_baza("inżynieryjne - transport szynowy") == "Koleje"

    def test_budowle_wodne(self):
        assert kompas_sektor_to_baza("inżynieryjne - budowle wodne") == "Budowle wodne"

    def test_unknown_returns_none(self):
        assert kompas_sektor_to_baza("coś nieznanego") is None

    def test_classify_uses_kompas_fallback(self):
        # Name doesn't trigger any keyword rule, but Kompas sector should classify it
        r = classify_investment(
            "Inwestycja bez słów kluczowych",
            kompas_sektor="inżynieryjne - autostrady"
        )
        assert r["sektor"] == "Drogi"

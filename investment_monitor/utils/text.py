"""
Text normalisation utilities shared across Kompas and TED modules.

All functions are pure (no I/O, no side effects) to make them easy to test.
"""
import re


# ── Generic helpers ───────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", text).strip()


# ── Company names ─────────────────────────────────────────────────────────────

_PAREN_ROLE_RE = re.compile(r"\s*\([^)]*\)\s*$")
_LEGAL_FORM_RE = re.compile(
    r"\s+("
    r"Sp[oó]łka\s+[Zz]\s+[Oo]graniczon[aą]\s+[Oo]dpowiedzialno[sś]ci[aą]"
    r"|Sp[oó]łka\s+[Aa]kcyjna"
    r"|Sp\.?\s*z\s*o\.?\s*o\.?(?:\s*Sp\.?\s*k\.?)?"
    r"|S\.?\s*A\.?"
    r"|Sp\.?\s*k\.?"
    r"|Sp\.?\s*j\.?"
    r"|s\.?\s*c\.?"
    r")\s*$",
    re.IGNORECASE,
)


def clean_company_name(name: str) -> str:
    """
    Strip parenthetical role suffixes and legal-form suffixes from company names.

    Examples:
      'Budimex S.A.'                        → 'Budimex'
      'Mostostal Zabrze S.A. (lider)'       → 'Mostostal Zabrze'
      'Urząd Miasta Sosnowiec'              → 'Urząd Miasta Sosnowiec'
    """
    if not name:
        return name
    name = _PAREN_ROLE_RE.sub("", name).strip()
    name = _LEGAL_FORM_RE.sub("", name).strip()
    return name


# ── Date / quarter helpers ────────────────────────────────────────────────────

def format_quarter_date(text: str) -> str | None:
    """Normalise a quarter string: 'II kwartał 2025' → 'II kw. 2025'."""
    if not text:
        return None
    return re.sub(r"\s+", " ", text.replace("kwartał", "kw.")).strip()


_QTR_MONTH = {"I": "01", "II": "04", "III": "07", "IV": "10"}
_QTR_RE    = re.compile(r"(I{1,3}V?)\s+(?:kw\.?|kwartał)\s+(\d{4})", re.IGNORECASE)


def quarter_to_date(q_str: str) -> str | None:
    """
    Convert a quarter string to the first day of that quarter.

    'II kw. 2025' → '01.04.2025'
    'IV kwartał 2028' → '01.10.2028'
    """
    m = _QTR_RE.search(str(q_str or ""))
    if not m:
        return None
    month = _QTR_MONTH.get(m.group(1).upper())
    if not month:
        return None
    return f"01.{month}.{m.group(2)}"


_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def reformat_date(val) -> str:
    """Convert ISO datetime string to DD.MM.YYYY: '2028-04-01 00:00:00' → '01.04.2028'."""
    if not val:
        return val
    m = _ISO_DATE_RE.match(str(val))
    if m:
        return f"{m.group(3)}.{m.group(2)}.{m.group(1)}"
    return val


def format_wartosc(val) -> str:
    """
    Format a numeric value as a Polish-style decimal string.

    469.3 → '469,3'   |   1200.0 → '1200'   |   None → ''
    Already-formatted strings like '469,3' pass through unchanged.
    """
    if val is None:
        return ""
    s = str(val).strip()
    if not s:
        return s
    try:
        f = float(s.replace(",", "."))
        return f"{f:g}".replace(".", ",")
    except ValueError:
        return s


# ── Location helpers ──────────────────────────────────────────────────────────

_WOJ_NORMALIZE = {
    "dolnośląskie":        "Dolnośląskie",
    "kujawsko-pomorskie":  "Kujawsko-pomorskie",
    "lubelskie":           "Lubelskie",
    "lubuskie":            "Lubuskie",
    "łódzkie":             "Łódzkie",
    "małopolskie":         "Małopolskie",
    "mazowieckie":         "Mazowieckie",
    "opolskie":            "Opolskie",
    "podkarpackie":        "Podkarpackie",
    "podlaskie":           "Podlaskie",
    "pomorskie":           "Pomorskie",
    "śląskie":             "Śląskie",
    "świętokrzyskie":      "Świętokrzyskie",
    "warmińsko-mazurskie": "Warmińsko-mazurskie",
    "wielkopolskie":       "Wielkopolskie",
    "zachodniopomorskie":  "Zachodniopomorskie",
}


def capitalize_woj(woj: str) -> str:
    """Normalise voivodeship name capitalisation: 'podkarpackie' → 'Podkarpackie'."""
    if not woj:
        return woj
    return _WOJ_NORMALIZE.get(woj.lower().strip(), woj.strip().capitalize())


def parse_city_woj(val: str) -> tuple[str, str | None]:
    """
    Extract city and optional voivodeship from a Kompas location string.

    'Dobrzechów (woj. podkarpackie, powiat strzyżowski)' → ('Dobrzechów', 'Podkarpackie')
    'Kraków'                                             → ('Kraków', None)
    """
    val = val.strip()
    city = re.sub(r"\s*\(.*$", "", val).strip() or val
    woj  = None
    m = re.search(r"\bwoj\.\s*([^,)\n]+)", val, re.IGNORECASE)
    if m:
        woj = capitalize_woj(m.group(1).strip())
    return city, woj


# ── Investment name normalisation ─────────────────────────────────────────────

_SUFFIX_START_RE = re.compile(
    r"^(rozbudowa|przebudowa|modernizacja|remont|rewitalizacja|budowa\b|"
    r"odbudowa|dobudowa|rekonstrukcja|przystosowanie|dostosowanie|"
    r"naprawa|termomodernizacja|adaptacja|nadbudowa|"
    r"etap\b|część\b|zadanie\b|faza\b)",
    re.IGNORECASE,
)
_SUFFIX_WORD_RE = re.compile(
    r"\b(rozbudowa|przebudowa|modernizacja|remont|rewitalizacja|budowa\b|"
    r"odbudowa|dobudowa|rekonstrukcja|przystosowanie|dostosowanie)\b",
    re.IGNORECASE,
)
_DASH_REPAIR_RE = re.compile(
    r"(?<!\s)-\s+(rozbudowa|przebudowa|modernizacja|remont|rewitalizacja|"
    r"budowa|odbudowa|dobudowa|rekonstrukcja|odcinek|etap)\b",
    re.IGNORECASE,
)


def normalize_inv_name(name: str, work_type_from_desc: str | None = None) -> str:
    """
    Normalise an investment name to match the naming convention used in the
    reference database:

    - 'LK315' → 'Linia nr 315'
    - Trailing comma after road number removed: 'DW988,' → 'DW988'
    - Location separators collapsed to '-' (no spaces)
    - Work-type suffix appended with ' - ' separator when missing
    - Missing suffix inferred from description when available

    Examples:
      'LK309 Kłodzko Nowe – Kudowa Zdrój'        → 'Linia nr 309 Kłodzko Nowe-Kudowa Zdrój'
      'Budowa obwodnicy Sidziny w ciągu DK46'     → 'DK46 Obwodnica Sidziny'  (via TED normaliser)
    """
    if not name:
        return name

    name = re.sub(r"\bLK(\d+)\b", r"Linia nr \1", name)
    name = re.sub(r"\b([A-Z]{1,3}\d[\d/]*),\s*", r"\1 ", name)
    name = name.replace("–", " - ")
    name = _DASH_REPAIR_RE.sub(r" - \1", name)
    name = re.sub(r"\s{2,}", " ", name).strip()

    parts          = re.split(r"\s+-\s+", name)
    location_parts = []
    suffix_parts   = []
    for part in parts:
        if suffix_parts or _SUFFIX_START_RE.match(part.strip()):
            suffix_parts.append(part)
        else:
            location_parts.append(part)

    if not location_parts and suffix_parts:
        location_parts = suffix_parts
        suffix_parts   = []

    base   = "-".join(location_parts)
    result = base
    if suffix_parts:
        result += " - " + " - ".join(suffix_parts)

    if work_type_from_desc and not _SUFFIX_WORD_RE.search(result):
        result += " - " + work_type_from_desc

    return re.sub(r"\s{2,}", " ", result).strip()


# ── Value parsing ─────────────────────────────────────────────────────────────

def parse_wartosc_netto(text: str) -> float | None:
    """
    Parse a Kompas 'Wartość szacunkowa' string to net PLN millions.

    Kompas reports gross values; this function divides by 1.23 to get net.
    Handles formats: '4000 mln', '500 000 000', '1 200'.
    """
    if not text:
        return None
    text_lower = text.lower()
    is_mln     = "mln" in text_lower
    digits     = re.sub(r"[^\d,.]", "", text.replace(",", "."))
    if not digits:
        return None
    try:
        val = float(digits)
    except ValueError:
        return None
    if not is_mln:
        val = val / 1_000_000
    return round(val / 1.23, 1)


def map_phase(phase_str: str) -> str | None:
    """Map a Kompas phase label to the status vocabulary used in the database."""
    if not phase_str:
        return None
    if "realizacja" in phase_str.lower():
        return "Budowa"
    mapping = {
        "Obiekt zakończony":          "Inwestycja zakończona",
        "Wybór Generalnego Wykonawcy":"Przetarg",
        "Wybór generalnego wykonawcy":"Przetarg",
        "Projektowanie":              "Planowanie",
        "Projektowanie zakończone":   "Planowanie",
        "Wizja":                      "Wstępna koncepcja",
        "Zapowiedź inwestycji":       "Wstępna koncepcja",
    }
    return mapping.get(phase_str, phase_str)

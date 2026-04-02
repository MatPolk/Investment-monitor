"""
TED EU notice name normaliser.

TED notice titles follow EU procurement language conventions and often
include verbose prefixes ("Budowa drogi ekspresowej S8 na odcinku...").
This module maps those titles to the compact naming convention used in
the reference database:

  'Budowa drogi ekspresowej S8 Wrocław-Kłodzko, zad. 4 - odc. węzeł Łagiewniki Zachód - węzeł Niemcza'
      → 'S8 Łagiewniki Zachód-Niemcza'

  'Modernizacja linii kolejowej nr 309 Kłodzko Nowe – Kudowa Zdrój'
      → 'Linia nr 309 Kłodzko Nowe-Kudowa Zdrój - modernizacja'

  'Przebudowa torowiska tramwajowego w ul. Aleksandrowskiej i Limanowskiego'
      → 'Linia tramwajowa Aleksandrowska-Limanowskiego - przebudowa'

Dispatch order: road → rail → tram → generic.
All functions are pure (no I/O) to keep them easy to unit-test.
"""
import re

from investment_monitor.utils.text import normalize_inv_name, clean_company_name


# ── Notice type → database status ─────────────────────────────────────────────

TED_NOTICE_STATUS = {
    "can":          "Przetarg",
    "can-social":   "Przetarg",
    "can-modif":    "Przetarg",
    "can-desg":     "Przetarg",
    "can-standard": "Przetarg",
    "qu-sy":        "Przetarg",
    "subco":        "Przetarg",
    "pin-buyer":    "Wstępna koncepcja",
    "pin-cfc-social":"Wstępna koncepcja",
    "pin-only":     "Wstępna koncepcja",
    "result":       "Wynik przetargu",
    "veat":         "Wynik przetargu",
}

# ── NUTS2/NUTS3 → voivodeship ─────────────────────────────────────────────────

_NUTS_TO_WOJ = {
    "PL21": "Małopolskie",       "PL22": "Śląskie",
    "PL41": "Wielkopolskie",     "PL42": "Zachodniopomorskie",
    "PL43": "Lubuskie",          "PL51": "Dolnośląskie",
    "PL52": "Opolskie",          "PL61": "Kujawsko-pomorskie",
    "PL62": "Warmińsko-mazurskie","PL63": "Pomorskie",
    "PL71": "Łódzkie",           "PL72": "Świętokrzyskie",
    "PL81": "Lubelskie",         "PL82": "Podkarpackie",
    "PL84": "Podlaskie",         "PL91": "Warszawski stołeczny",
    "PL92": "Mazowieckie",
    # NUTS3 subregions → voivodeship
    "PL213": "Małopolskie",  "PL214": "Małopolskie",  "PL217": "Małopolskie",
    "PL224": "Śląskie",      "PL225": "Śląskie",      "PL227": "Śląskie",
    "PL228": "Śląskie",      "PL229": "Śląskie",
    "PL411": "Wielkopolskie","PL414": "Wielkopolskie","PL415": "Wielkopolskie",
    "PL416": "Wielkopolskie","PL417": "Wielkopolskie","PL418": "Wielkopolskie",
    "PL421": "Zachodniopomorskie","PL422": "Zachodniopomorskie",
    "PL424": "Zachodniopomorskie","PL428": "Zachodniopomorskie",
    "PL431": "Lubuskie",     "PL432": "Lubuskie",
    "PL514": "Dolnośląskie", "PL515": "Dolnośląskie", "PL516": "Dolnośląskie",
    "PL517": "Dolnośląskie", "PL518": "Dolnośląskie",
    "PL521": "Opolskie",     "PL522": "Opolskie",     "PL523": "Opolskie",
    "PL524": "Opolskie",
    "PL613": "Kujawsko-pomorskie","PL616": "Kujawsko-pomorskie",
    "PL617": "Kujawsko-pomorskie","PL618": "Kujawsko-pomorskie",
    "PL619": "Kujawsko-pomorskie",
    "PL621": "Warmińsko-mazurskie","PL622": "Warmińsko-mazurskie",
    "PL633": "Pomorskie",    "PL634": "Pomorskie",    "PL636": "Pomorskie",
    "PL637": "Pomorskie",    "PL638": "Pomorskie",
    "PL711": "Łódzkie",      "PL712": "Łódzkie",      "PL713": "Łódzkie",
    "PL714": "Łódzkie",      "PL715": "Łódzkie",
    "PL721": "Świętokrzyskie","PL722": "Świętokrzyskie",
    "PL811": "Lubelskie",    "PL812": "Lubelskie",    "PL814": "Lubelskie",
    "PL815": "Lubelskie",
    "PL821": "Podkarpackie", "PL822": "Podkarpackie", "PL823": "Podkarpackie",
    "PL824": "Podkarpackie",
    "PL841": "Podlaskie",    "PL842": "Podlaskie",    "PL843": "Podlaskie",
    "PL911": "Warszawski stołeczny","PL912": "Warszawski stołeczny",
    "PL913": "Mazowieckie",  "PL914": "Mazowieckie",  "PL921": "Mazowieckie",
    "PL922": "Mazowieckie",  "PL923": "Mazowieckie",  "PL924": "Mazowieckie",
    "PL925": "Mazowieckie",  "PL926": "Mazowieckie",
}


def nuts_to_woj(nuts_code: str) -> str:
    """Map a NUTS2/NUTS3 code to a voivodeship name."""
    woj = _NUTS_TO_WOJ.get(nuts_code or "", "")
    return "Mazowieckie" if woj == "Warszawski stołeczny" else woj


# ── Construction filter ────────────────────────────────────────────────────────

_TED_REJECT_RE = re.compile(
    r"^(Dostawa\s+(?!.*robót\s+budowlan)|Doposażenie\b|Zakup\b|"
    r"Framework\s+Contract|Tender\s+for|Provision\s+of|Supply\s+of|Delivery\s+of|"
    r"Dostawa\s+i\s+monta[zż]\s+(?!.*(?:konstrukcj|instalacj|budow)))",
    re.IGNORECASE,
)
_PL_CHARS_RE = re.compile(
    r"[ĄĆĘŁŃÓŚŹŻąćęłńóśźż]"
)
_PL_WORD_RE = re.compile(
    r"\b(budowa|rozbudowa|przebudowa|modernizacja|remont|budynku|drogi|"
    r"ulicy|miasta|gminy|powiatu|centrum|szkoły|przedszkol|"
    r"sieci|stacji|mostu|obwodnicy|linii|tramwaj|kolejow|wodociąg|"
    r"kanalizac|oczyszczaln|uzdatniania)\b",
    re.IGNORECASE,
)


def is_construction(name: str) -> bool:
    """
    Return True if a TED notice title looks like a construction tender.

    Rejects: pure-English titles (no Polish characters or keywords),
    supply/delivery notices, and other non-construction procurement types.
    """
    if not name:
        return False
    if (
        not _PL_CHARS_RE.search(name)
        and re.match(r"^[A-Za-z\s,.:;()\-/&0-9]+$", name)
        and not _PL_WORD_RE.search(name)
    ):
        return False
    return not _TED_REJECT_RE.match(name)


# ── Work-type prefix regex ─────────────────────────────────────────────────────

_TED_WORK_PREFIX_RE = re.compile(
    r"^(zaprojektowanie\s+i\s+(?:wybudowanie|budow[ae])|"
    r"budowa\s+i\s+rozbudowa|modernizacja\s+i\s+rozbudowa|przebudowa\s+i\s+rozbudowa|"
    r"rozbudowa\s+i\s+modernizacja|rozbudowa\s+i\s+przebudowa|modernizacja\s+i\s+przebudowa|"
    r"budowa\s+i\s+przebudowa|remont\s+i\s+przebudowa|remont\s+i\s+modernizacja|"
    r"naprawa\s+g[łl]ówna|"
    r"budowa|rozbudowa|przebudowa|modernizacja|remont|rewitalizacja|"
    r"odbudowa|rekonstrukcja|nadbudowa|adaptacja|termomodernizacja|naprawa|"
    r"prace\s+na)"
    r"\s+",
    re.IGNORECASE,
)

_TED_LOC_SUFFIX_RE = re.compile(
    r"\s+(?:w|we)\s+"
    r"(?!ciągu\b|kierunku\b|ramach\b|zakresie\b|związku\b|obrębie\b|rejonie\b|ul\.\s|ulicy\s)"
    r"(?:m\.\s*)?(?:miejscowości\s+)?"
    r"([A-ZĄĆĘŁŃÓŚŹŻ][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż\s-]*?)\s*$",
    re.IGNORECASE,
)


# ── Road normaliser ────────────────────────────────────────────────────────────

_TED_ROAD_PREFIX_RE = re.compile(
    r"(?:drogi\s+ekspresowej|drodze\s+ekspresowej|droga\s+ekspresowa|drogą\s+ekspresową)\s+(S\d{1,3})"
    r"|(?:autostrady|autostradzie|autostrada|autostradą)\s+(A\d{1,2})"
    r"|(?:drogi\s+krajowej|drodze\s+krajowej|droga\s+krajowa|drogą\s+krajową)\s+(?:nr\s+)?(\d{1,3})"
    r"|(?:drogi\s+wojewódzkiej|drodze\s+wojewódzkiej|droga\s+wojewódzka)\s+(?:nr\s+)?(\d{2,3})",
    re.IGNORECASE,
)
_TED_BYPASS_RE = re.compile(
    r"obwodnic[ayię]\s+([\wĄĆĘŁŃÓŚŹŻąćęłńóśźż][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż\s-]*?)(?:\s*[-–,]|\s+w\s+ciągu|\s*$)",
    re.IGNORECASE,
)
_TED_BYPASS_ROAD_RE = re.compile(
    r"w\s+ciągu\s+(?:drogi\s+krajowej\s+(?:nr\s+)?(\d{1,3})"
    r"|drogi\s+wojewódzkiej\s+(?:nr\s+)?(\d{2,3})"
    r"|drogi\s+ekspresowej\s+(S\d{1,3}))",
    re.IGNORECASE,
)
_TED_ROAD_SECTION_RE = re.compile(
    r"(?:odc\.?\s*|odcinek\s+)"
    r"(?:węzła?\s+)?([\wĄĆĘŁŃÓŚŹŻąćęłńóśźż][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż\s]*?)"
    r"\s*(?:\([^)]*\)\s*)?[-–]\s*"
    r"(?:węzła?\s+)?([\wĄĆĘŁŃÓŚŹŻąćęłńóśźż][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż\s]*?)"
    r"(?:\s*\([^)]*\))?(?:\s*[,;]|\s*$)",
    re.IGNORECASE,
)
_TED_ROAD_ENDPOINTS_RE = re.compile(
    r"(?:na\s+odcinku\s+)?(?:od\s+|odc\.\s*)?(?:węzła?\s+)?"
    r"([\wĄĆĘŁŃÓŚŹŻąćęłńóśźż][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż\s]*?)"
    r"\s*(?:[-–]|do\s+)(?:węzła?\s+)?\s*"
    r"([\wĄĆĘŁŃÓŚŹŻąćęłńóśźż][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż\s]*?)(?:\s*[,;(]|\s*$)",
    re.IGNORECASE,
)


def _normalize_road(full_text: str) -> str | None:
    """
    Normalise a road-infrastructure TED title.

    'budowę drogi ekspresowej S8 Wrocław-Kłodzko, zad. 4 - odc. węzeł Łagiewniki Zachód - węzeł Niemcza'
        → 'S8 Łagiewniki Zachód-Niemcza'
    """
    m = _TED_ROAD_PREFIX_RE.search(full_text)
    prefix = None
    if m:
        if m.group(1):   prefix = m.group(1)
        elif m.group(2): prefix = m.group(2)
        elif m.group(3): prefix = f"DK{m.group(3)}"
        elif m.group(4): prefix = f"DW{m.group(4)}"

    bypass = _TED_BYPASS_RE.search(full_text)
    bypass_name = bypass.group(1).strip() if bypass else None

    if not prefix:
        br = _TED_BYPASS_ROAD_RE.search(full_text)
        if br:
            if br.group(1):   prefix = f"DK{br.group(1)}"
            elif br.group(2): prefix = f"DW{br.group(2)}"
            elif br.group(3): prefix = br.group(3)

    if not prefix and not bypass_name:
        return None

    section   = _TED_ROAD_SECTION_RE.search(full_text)
    after_pfx = full_text[m.end():] if m else full_text
    endpoints = _TED_ROAD_ENDPOINTS_RE.search(after_pfx)

    parts = []
    if prefix:
        parts.append(prefix)
    if bypass_name:
        parts.append(f"Obwodnica {bypass_name}")
    elif section:
        ep1 = re.sub(r"^w[eę]ze?ł\w*\s+", "", section.group(1).strip().rstrip(" -"), flags=re.IGNORECASE)
        ep2 = re.sub(r"^w[eę]ze?ł\w*\s+", "", section.group(2).strip().rstrip(" -"), flags=re.IGNORECASE)
        if ep1 and ep2:
            parts.append(f"{ep1}-{ep2}")
    elif endpoints:
        ep1 = re.sub(r"^w[eę]ze?ł\w*\s+", "", endpoints.group(1).strip().rstrip(" -"), flags=re.IGNORECASE)
        ep2 = re.sub(r"^w[eę]ze?ł\w*\s+", "", endpoints.group(2).strip().rstrip(" -"), flags=re.IGNORECASE)
        if ep1 and ep2:
            parts.append(f"{ep1}-{ep2}")
    elif m:
        rest = after_pfx.strip().rstrip(",;.")
        rest = re.sub(r",?\s*(?:zadanie|długości?|dl\.)\s+.*$", "", rest, flags=re.IGNORECASE)
        rest = rest.strip().rstrip(",;. -")
        if rest and len(rest) < 80:
            parts.append(rest)

    return " ".join(parts) if parts else None


# ── Rail normaliser ────────────────────────────────────────────────────────────

_TED_RAIL_RE = re.compile(
    r"lini[a-z]*\s+kolejow[a-z]*\s+(?:nr\s+)?(\d{1,3})"
    r"(?:\s+(?:na\s+odcinku\s+)?([\wĄĆĘŁŃÓŚŹŻąćęłńóśźż][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż\s.]*?)"
    r"\s*[-–]\s*([\wĄĆĘŁŃÓŚŹŻąćęłńóśźż][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż\s.]*?))?"
    r"(?:\s*[-–]\s*(?:naprawa|remont|modernizacja|prace)|(?:\s+(?:[wo]\s*km|od\s+km))|(?:\s*[,(])|$)",
    re.IGNORECASE,
)
_TED_RAIL_TRACK_RE = re.compile(
    r"tor(?:u|ów)?\s+.*?lini[a-z]*\s+(?:kolejow[a-z]*\s+)?(?:nr\s+)?(\d{1,3})",
    re.IGNORECASE,
)


def _normalize_rail(full_text: str, description: str = "") -> str | None:
    """
    Normalise a rail-infrastructure TED title.

    'modernizacji linii kolejowej nr 309 Kłodzko Nowe – Kudowa Zdrój'
        → 'Linia nr 309 Kłodzko Nowe-Kudowa Zdrój'
    """
    m = _TED_RAIL_RE.search(full_text)
    if not m:
        m2 = _TED_RAIL_TRACK_RE.search(full_text)
        if not m2 and description:
            m2 = _TED_RAIL_TRACK_RE.search(description)
            if not m2:
                m3 = re.search(r"lini[a-z]*\s+(?:kolejow[a-z]*\s+)?(?:nr\s+)?(\d{1,3})", description, re.IGNORECASE)
                if m3:
                    m2 = m3
        if m2:
            line_num = m2.group(1)
            for source in [description, full_text]:
                if not source:
                    continue
                ep = re.search(
                    rf"lini[a-z]*\s+(?:kolejow[a-z]*\s+)?(?:nr\s+)?{line_num}\s+"
                    r"(?:na\s+odcinku\s+)?([\wĄĆĘŁŃÓŚŹŻąćęłńóśźż][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż\s.]*?)\s*[-–]\s*([\wĄĆĘŁŃÓŚŹŻąćęłńóśźż][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż\s.]*?)"
                    r"(?:\s*[-–]\s*(?:naprawa|remont|modernizacja|prace)|(?:\s+(?:[wo]\s*km|od\s+km))|(?:\s*[,(])|$)",
                    source, re.IGNORECASE,
                )
                if ep:
                    ep1 = ep.group(1).strip().rstrip(",;. -")
                    ep2 = ep.group(2).strip().rstrip(",;. -")
                    return f"Linia nr {line_num} {ep1}-{ep2}"
            return f"Linia nr {line_num}"
        return None

    line_num = m.group(1)
    ep1 = re.sub(r"^na\s+odcinku\s+", "", (m.group(2) or "").strip().rstrip(",;. -"), flags=re.IGNORECASE)
    ep2 = (m.group(3) or "").strip().rstrip(",;. -")
    result = f"Linia nr {line_num}"
    if ep1 and ep2:
        result += f" {ep1}-{ep2}"
    elif ep1:
        result += f" {ep1}"
    return result


# ── Tram normaliser ────────────────────────────────────────────────────────────

_TED_TRAM_RE = re.compile(
    r"(?:lini[a-z]*\s+)?tramwajow[a-z]*\s+(?:w\s+)?(?:ul\.?\s*|ulicy\s+)?"
    r"([\wĄĆĘŁŃÓŚŹŻąćęłńóśźż][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż\s./-]*)",
    re.IGNORECASE,
)


def _normalize_tram(full_text: str) -> str | None:
    """
    Normalise a tram-infrastructure TED title.

    'tramwajowej w ul. Aleksandrowskiej i Limanowskiego'
        → 'Linia tramwajowa Aleksandrowska-Limanowskiego'
    """
    m = _TED_TRAM_RE.search(full_text)
    if not m:
        return None
    route = m.group(1).strip()
    od_do = re.search(
        r"od\s+(?:ul\.?\s*)?(\w[\wĄĆĘŁŃÓŚŹŻąćęłńóśźż]*)\s+(?:do\s+(?:(?:włączenia\s+w\s+)?(?:ul\.?\s*)?))?([\wĄĆĘŁŃÓŚŹŻąćęłńóśźż]+)",
        route, re.IGNORECASE,
    )
    if od_do:
        route = f"{od_do.group(1)}-{od_do.group(2)}"
    else:
        route = re.sub(r"\s+i\s+", "-", route)
    route = re.sub(r"\s+(?:na\s+odcinku|od\s+ronda|do\s+).*$", "", route, flags=re.IGNORECASE)
    route = route.strip().rstrip(",;. -")
    return f"Linia tramwajowa {route}" if route else None


# ── Main dispatcher ────────────────────────────────────────────────────────────

_GENITIVE_TO_NOM = [
    (r"^Oczyszczalni\b",                        "Oczyszczalnia"),
    (r"^Stacji\b",                              "Stacja"),
    (r"^Polderu\b",                             "Polder"),
    (r"^Filii\b",                               "Filia"),
    (r"^Szko[łl]y\b",                           "Szkoła"),
    (r"^Trasy\b",                               "Trasa"),
    (r"^Domu\b",                                "Dom"),
    (r"^Korytarzy\s+transportowych\s+dojazdowych\b", "Korytarze transportowe dojazdowe"),
    (r"^Korytarzy\b",                           "Korytarze"),
    (r"^Systemu\b",                             "System"),
    (r"^Cz[eę][sś]ci\s+mechanicznej\b",        "Część mechaniczna"),
    (r"^Cz[eę][sś]ci\b",                       "Część"),
    (r"^Jednostki\s+kogeneracji\b",             "Jednostka kogeneracji"),
    (r"^Zespo[łl]u\s+Szkolno-Przedszkolnego\b", "Zespół Szkolno-Przedszkolny"),
    (r"^Krytego\s+basenu\b",                    "Kryty basen"),
]


def normalize_ted_name(raw_name: str, existing_city: str = "", description: str = "") -> tuple[str, str]:
    """
    Normalise a TED notice title to match the naming convention of the database.

    Returns (normalised_name, extracted_city).
    City may be extracted from location suffixes like '... w Krakowie'.
    """
    if not raw_name:
        return raw_name, existing_city

    name = raw_name.strip()
    work_type = ""
    city = existing_city

    # 1. Extract trailing location suffix: "... w Krakowie"
    loc_match = _TED_LOC_SUFFIX_RE.search(name)
    if loc_match:
        if not city:
            city = loc_match.group(1).strip()
        name = name[:loc_match.start()].strip()

    # 2. Extract work-type prefix and decide whether to append it as suffix
    pfx = _TED_WORK_PREFIX_RE.match(name)
    if pfx:
        wt = pfx.group(1).strip().lower()
        if "zaprojektowanie" in wt or wt == "budowa":
            work_type = ""  # database does not use "- budowa" suffix
        elif wt == "budowa i rozbudowa":
            work_type = "rozbudowa"
        elif wt == "budowa i przebudowa":
            work_type = "przebudowa"
        elif "naprawa" in wt and "g" in wt:
            work_type = "naprawa"
        elif wt == "prace na":
            work_type = ""
        else:
            work_type = wt
        name = name[pfx.end():].strip()

    # 3. Dispatch: road → rail → tram → generic
    road = _normalize_road(raw_name)
    if road:
        result = f"{road} - {work_type}" if work_type else road
        return normalize_inv_name(result), city

    rail = _normalize_rail(raw_name, description)
    if rail:
        result = f"{rail} - {work_type}" if work_type else rail
        return normalize_inv_name(result), city

    tram = _normalize_tram(raw_name)
    if tram:
        result = f"{tram} - {work_type}" if work_type else tram
        return normalize_inv_name(result), city

    # 4. Generic: fix genitive → nominative, remove verbose prefixes
    for pat, repl in _GENITIVE_TO_NOM:
        new = re.sub(pat, repl, name, flags=re.IGNORECASE)
        if new != name:
            name = new
            break

    name = re.sub(
        r"^(budynku|obiektu|zespołu|kompleksu|sieci|odcinka|drogi|"
        r"nowej|nowego|istniejącej|istniejącego|"
        r"wysokosprawnej|wysokosprawnego)\s+",
        "", name, flags=re.IGNORECASE,
    )
    if name and name[0].islower():
        name = name[0].upper() + name[1:]

    if work_type and name:
        name = f"{name} - {work_type}"

    return normalize_inv_name(name), city

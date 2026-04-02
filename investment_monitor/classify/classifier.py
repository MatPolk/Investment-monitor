"""
Investment classifier.

Maps an investment name (and optionally investor name / Kompas sector string)
to the taxonomy used in the reference database:

  sector      — top-level category (e.g. 'Drogi', 'Koleje', 'Budowle przemysł.')
  sector_pkob — PKOB classification code label (1:1 with sector)
  segment     — thematic sub-category
  remonty     — renovation flag (full column header string or None)
  wojsko      — military flag ('Inwestycje wojskowe' or None)

Classification priority:
  1. Keyword rules on investment name + investor  (_SECTOR_RULES)
  2. Segment → sector mapping                    (_SEGMENT_TO_SECTOR)
  3. Kompas sector string fallback               (kompas_sektor_to_baza)
"""
import re


# ── Sector → PKOB (1:1) ───────────────────────────────────────────────────────

SEKTOR_PKOB = {
    "Drogi":                    "Autostrady, drogi ekspresowe, ulice i drogi pozostałe (PKOB 211)",
    "Koleje":                   "Drogi szynowe, drogi kolei napowietrznych lub podwieszanych (PKOB 212)",
    "Drogi lotniskowe":         "Drogi lotniskowe (PKOB 213)",
    "Mosty i tunele":           "Mosty, wiadukty i estakady, tunele i przejścia nadziemne i podziemne (PKOB 214)",
    "Budowle wodne":            "Budowle wodne (PKOB 215)",
    "Sieci przesyłowe":         "Rurociągi i linie telekomunikacyjne oraz linie elektroenergetyczne przesyłowe (PKOB 221)",
    "Sieci rozdzielcze":        "Rurociągi sieci rozdzielczej i linie kablowe rozdzielcze (PKOB 222)",
    "Budowle przemysł.":        "Kompleksowe budowle na terenach przemysłowych (PKOB 230)",
    "Budowle sport. i rekrea.": "Budowle sportowe i rekreacyjne (PKOB 241)",
    "Biurowe":                  "Budynki biurowe (PKOB 122)",
    "Transportu i łączności":   "Budynki transportu i łączności (PKOB 124)",
    "Przemysł. i magazyn.":     "Budynki przemysłowe i magazynowe (PKOB 125)",
    "Użyteczności publicznej":  "Budynki użyteczności publicznej (PKOB 126)",
    "Wielomieszkaniowe":        "Budynki o dwóch mieszkaniach i wielomieszkaniowe (PKOB 112)",
    "Zbiorowego zamieszkania":  "Budynki zbiorowego zamieszkania (PKOB 113)",
}

_SEGMENT_TO_SECTOR = {
    "Drogi tramwajowe":                                   "Koleje",
    "Mosty, wiadukty i estakady":                         "Mosty i tunele",
    "Tunele i przejścia podziemne":                       "Mosty i tunele",
    "Sieci energetyczne":                                 "Sieci przesyłowe",
    "Obiekty sieci gazowej":                              "Sieci przesyłowe",
    "Instalacje paliwowe":                                "Sieci przesyłowe",
    "Instalacje wodorowe":                                "Sieci przesyłowe",
    "Lądowe elektrownie wiatrowe":                        "Budowle przemysł.",
    "Morskie elektrownie wiatrowe":                       "Budowle przemysł.",
    "Elektrownie fotowoltaiczne":                         "Budowle przemysł.",
    "Elektrownie jądrowe":                                "Budowle przemysł.",
    "Elektrownie konwencjonalne":                         "Budowle przemysł.",
    "Magazyny energii":                                   "Budowle przemysł.",
    "Instalacje biogazowe":                               "Budowle przemysł.",
    "Instalacje biomasowe":                               "Budowle przemysł.",
    "Instalacje geotermalne":                             "Budowle przemysł.",
    "Obiekty składowania i utylizacji odpadów":           "Budowle przemysł.",
    "Obiekty przemysłowe":                                "Budowle przemysł.",
    "Budynki z mieszkaniami na wynajem":                  "Wielomieszkaniowe",
    "Akademiki":                                          "Zbiorowego zamieszkania",
    "Domy opieki dla osób starszych i niepełnosprawnych": "Zbiorowego zamieszkania",
    "Budynki szpitali i zakładów opieki medycznej":       "Użyteczności publicznej",
    "Budynki szkół i instytucji badawczych":              "Użyteczności publicznej",
    "Budynki kultury i rozrywki oraz muzea":              "Użyteczności publicznej",
    "Hale sportowe":                                      "Użyteczności publicznej",
    "Kryte baseny":                                       "Użyteczności publicznej",
    "Budynki biurowe administracji publicznej":           "Biurowe",
    "Budynki parkingowe i garażowe":                      "Transportu i łączności",
    "Centra danych":                                      "Przemysł. i magazyn.",
}

_KOMPAS_SEKTOR_MAP = [
    ("budownictwo wielorodzinne",          "Wielomieszkaniowe"),
    ("zamieszkania zbiorowego",            "Zbiorowego zamieszkania"),
    ("lofty",                              "Wielomieszkaniowe"),
    ("budynki transportu i łączności",     "Transportu i łączności"),
    ("zakłady produkcyjne",                "Przemysł. i magazyn."),
    ("administracji publicznej",           "Użyteczności publicznej"),
    ("służby zdrowia",                     "Użyteczności publicznej"),
    ("kultury i rozrywki",                 "Użyteczności publicznej"),
    ("szkolnictwa",                        "Użyteczności publicznej"),
    ("sportowe i rekreacyjne",             "Budowle sport. i rekrea."),
    ("budynki magazynowe",                 "Przemysł. i magazyn."),
    ("centra logistyczne",                 "Przemysł. i magazyn."),
    ("budynki biurowe",                    "Biurowe"),
    ("infrastruktura lotniskowa",          "Drogi lotniskowe"),
    ("autostrady",                         "Drogi"),
    ("obwodnice",                          "Drogi"),
    ("pozostałe drogi",                    "Drogi"),
    ("mosty, wiadukty",                    "Mosty i tunele"),
    ("budowle wodne",                      "Budowle wodne"),
    ("uzbrojenie i przygotowanie terenu",  "Sieci rozdzielcze"),
    ("przestrzeni miejskiej",              "Użyteczności publicznej"),
    ("place, skwery",                      "Użyteczności publicznej"),
    ("otwarte obiekty sportowe",           "Budowle sport. i rekrea."),
    ("utylizacja odpadów",                 "Budowle przemysł."),
    ("wodno",                              "Sieci rozdzielcze"),
    ("transport szynowy",                  "Koleje"),
    ("rafinerii i elektrowni",             "Budowle przemysł."),
]

# Ordered sector rules — more specific patterns first.
# Tested against: name.lower() + " " + investor.lower()
_SECTOR_RULES = [
    ("Drogi lotniskowe", [
        "airside", "landside", "pas startowy", "droga startowa",
        "drogi kołowania", "płyta postoj", "płyta lotnisk", "nawierzchnia lotnisk",
    ]),
    ("Mosty i tunele", [
        "linia metra", "metro rondo", "metro bródno", "metro nowy",
        r"\bmost\b", "most nad", "most przez", "2 mosty", "3 mosty", "mosty ",
        r"\btunel\b", "tunel drogowy", "tunel kolejowy", "tunel tramwajowy",
        "2 tunele", "3 tunele",
        r"\bwiadukt\b", "wiadukty ", r"\bestakada\b", "estakady ",
        r"\bkładka\b", "przejście podziemne", "przejścia podziemne",
    ]),
    ("Budowle wodne", [
        "port gdańsk", "port gdynia", "port świnoujście", "port szczecin",
        "port morski", "port rzeczny", "nabrzeże", "falochron", "pirs ", "basen portowy",
        r"\bpolder\b", "stopień wodny", "stopień na rzece",
        "kanał żeglugowy", "kanał śląski", "droga wodna",
        "zbiornik retencyjny", "suchy zbiornik", "zbiornik wodny na",
        "ochrona przeciwpowodziowa", "wały przeciwpowodziowe", "wał przeciwpowodziowy",
        r"\bśluza\b", r"\bjaz\b", "bulwary nad", "przystań",
    ]),
    ("Sieci przesyłowe", [
        r"\bgazociąg\b", "gazociągu ", "gazociągiem ",
        "tłocznia gazu", "PMG ", "podziemny magazyn gazu",
        "terminal lng", "terminal gaz",
        "linia 400 kv", "linia 220 kv", "linia 110 kv",
        "400/110", "400/220", "220/110", "stacja 400", "stacja 220",
        "stacja 110", "rozdzielnia 400", "rozdzielnia 220", r"\bGPZ\b",
        "kse ", "krajowy system elektroenergetyczny",
        "rurociąg nato", "ropociąg", "naftociąg", "rurociąg produktowy",
        "most energetyczny", "harmony link", "nordycko-bałtycki korytarz",
        "interkonekt", "stacja elektroenergetyczna", "linia przesyłowa",
        "podstacja trakcyjna",
    ]),
    ("Sieci rozdzielcze", [
        "oczyszczalnia ścieków", "oczyszczalnia odpadów",
        "gospodarka wodno-ściekowa", "gospodarka ściekowa",
        "uporządkowanie gospodarki",
        "kolektor ściek", "kolektor sanitarny", "kolektor deszczowy",
        "kanalizacja sanitarna", "kanalizacja deszczowa",
        "zaopatrzenie w wodę", "stacja uzdatniania wody",
        "sieć wod-kan", "sieć wodociągowa", "sieć kanalizacyjna",
        "rozbudowa sieci ciepłowniczej", "sieć ciepłownicza",
        "węzeł cieplny", "przepompownia ścieków",
    ]),
    ("Budowle przemysł.", [
        "farma wiatrowa", "farmy wiatrowej", "park wiatrowy",
        "morska farma wiatrowa", "morskie farmy wiatrowe", "offshore",
        "farma fotowoltaiczna", "elektrownia fotowoltaiczna",
        "elektrownia jądrowa", "reaktor jądrowy", r"\bSMR\b",
        "elektrownia szczytowo-pompowa", "elektrownia gazowa", "elektrownia węglowa",
        "blok gazowo-parowy", "blok węglowy", "blok energetyczny",
        "elektrociepłown", "ciepłownia ",
        "kotłownia biomasowa", "kotłownia gazowa",
        "biogazownia", "biometanownia", "biomasa", "kotłownia na biomasę",
        r"\bBESS\b", "magazyn energii",
        "spalarnia odpadów", "spalarni odpadów",
        "instalacja termicznego przekształcania", "instalacja termicznego przetwarzania",
        "zakład termicznego przekształcania", "zakład unieszkodliwiania",
        "kopalnia węgla", "kopalnia ropy", "kopalnia miedzi",
        "szyb ", "huta miedzi", "rafineria", "zakłady azotow",
        "instalacja do produkcji wodoru", "hydrogen eagle", "rfnbo",
        "instalacja kogeneracyjn", "składy mps", "baza paliw nr",
    ]),
    ("Koleje", [
        "linia nr ", "linie nr ", "linia kolejowa nr",
        r"\bE20\b", r"\bE30\b", r"\bE59\b", r"\bE65\b", r"\bE75\b", r"\bLK\d",
        r"\bC-E\d", "linia y ", "linia cpe",
        "tramwaj", "torowisko", "trasa tramwajowa",
        "bocznica kolejowa", "stacja kolejowa", "przejazd kolejowy",
        "via carpathia",
    ]),
    ("Drogi", [
        r"\bS\d{1,2}\b", r"\bA\d\b", r"\bDK\d{1,3}\b", r"\bDW\d{3}\b",
        "obwodnic", "droga ekspresowa", "droga krajowa",
        "droga powiatowa", "droga gminna", "droga lokalna", "droga wojewódzka",
        "układ drogowy", "trasa łącząca", "trasa n-s", "trasa w-z",
        "via pomerania", "korytarz transportowy",
    ]),
    ("Transportu i łączności", [
        "dworzec kolejowy", "dworzec autobusowy", "dworzec pkp",
        "port lotniczy", "katowice airport", "lotnisko chopina",
        "zajezdnia tramwajowa", "zajezdnia autobusowa",
        "węzeł przesiadkowy", "centrum przesiadkowe",
        "parking wielopoziomowy", "parking podziemny",
        "terminal pasażerski", r"\bdworzec\b",
    ]),
    ("Budowle sport. i rekrea.", [
        r"\bstadion\b", "stadion miejski", "stadion żużlowy", "stadion piłkarski",
        "stadion lekkoatletyczny", "park rozrywki", "park wodny",
        r"\baquapark\b", "tor wyścigowy", "tor kartingowy",
        "kolej linowa", "ośrodek rekreacyjny",
    ]),
    ("Zbiorowego zamieszkania", [
        "zakład karny", "areszt śledczy", "areszt tymczasowy",
        "dom poprawczy", "zakład poprawczy",
        "budynek koszarowy", "budynki koszarowe", "budynki sztabowo-koszarowe",
        "koszary ", "miejsce stacjonowania",
        r"\bakademik\b", "dom studencki", "domy studenckie",
        r"\binternat\b", "dom pomocy społecznej", r"\bDPS\b",
        "dom seniora", "miasteczko seniora", "zakład opiekuńczo",
    ]),
    ("Wielomieszkaniowe", [
        "mieszkanie dla rozwoju", "mieszkanie plus",
        r"\bSIM\b", r"\bTBS\b", r"\bPTBS\b",
        "najem komunalny", "najem społeczny",
        r"\bmieszkani\b", "lokale mieszkalne", "budynek mieszkalny",
        r"\bwielorodzinn\w*\b", "osiedle ", "budynki mieszkalne",
    ]),
    ("Przemysł. i magazyn.", [
        "centrum logistyczne", "centrum dystrybucji", "centrum fulfilment",
        "hala magazynowa", "hala produkcyjna", "magazyn wielobranżowy",
        "centrum danych", r"\bserwerowni\b",
        "fabryka amunicji", "fabryka broni",
        "terminal przeładunkowy", "hurtownia farmaceutyczna",
    ]),
    ("Biurowe", [
        r"\bsiedziba\b", "siedziba komendy", "siedziba prokuratury",
        "siedziba agencji", "siedziba urzędu", "siedziba zarządu",
        r"\bsąd\b", r"\barchiwum\b", "komisariat policji",
        r"\bbiurowiec\b", "park biurowy", "campus biurowy",
        "centrum biurowe", "inkubator przedsiębiorczości",
        "budynek administracyjno-biurowy",
    ]),
    ("Użyteczności publicznej", [
        r"\bszpital\b", "centrum medyczne", "centrum onkologiczne",
        "szpital kliniczny", "szpital uniwersytecki", r"\bSP ZOZ\b",
        "szkoła podstawowa", "szkoła średnia", "szkoła specjalna",
        "szkoła zawodowa", "szkoła branżowa",
        r"\bliceum\b", r"\btechnikum\b",
        "uczelnia wyższa", r"\buniwersytet\b", r"\bpolitechnika\b",
        "wydział ", "kampus uczelni", "centrum nauki", "centrum badań",
        r"\binstytut\b", r"\bmuzeum\b", r"\bteatr\b", r"\bopera\b",
        r"\bfilharmonia\b", "centrum kultury", "dom kultury", r"\bbibliotek\b",
        "hala widowiskowo-sportowa", "hala sportowa", r"\bbasen\b",
        "kryty basen", "pływalnia kryta",
    ]),
]

_SEGMENT_RULES = [
    (["elektrownia jądrowa", "elektrownię jądrową", "reaktor jądrowy", r"\bSMR\b"], "Elektrownie jądrowe"),
    (["morska farma wiatrowa", "morskie farmy wiatrowe", "offshore",
      "bałtyk 1", "bałtyk 2", "bałtyk 3", "baltica", "baltic power"], "Morskie elektrownie wiatrowe"),
    (["farma wiatrowa", "farmy wiatrowej", "park wiatrowy",
      "elektrownia wiatrowa", "kompleks farm wiatrowych"], "Lądowe elektrownie wiatrowe"),
    (["farma fotowoltaiczna", "elektrownia fotowoltaiczna",
      "elektrownia słoneczna", "farma pv"], "Elektrownie fotowoltaiczne"),
    (["elektrociepłown", "blok gazowo-parowy", "blok węglowy", "blok energetyczny",
      "elektrownia gazowa", "elektrownia węglowa", "elektrownia szczytowo-pompowa",
      "blok biomasowy", "blok kogeneracyjny", "układ kogeneracyjn"], "Elektrownie konwencjonalne"),
    (["magazyn energii", "bess ", "bateria energetyczna", "system magazynowania energii"], "Magazyny energii"),
    (["biogazownia", "instalacja biogazowa", "biometanownia"], "Instalacje biogazowe"),
    (["biomasa", "kotłownia biomasowa", "instalacja biomasowa", "bioelektrownia"], "Instalacje biomasowe"),
    (["geotermalna", "geotermaln", "instalacja geotermalna"], "Instalacje geotermalne"),
    (["naftociąg", "ropociąg", "rurociąg produktowy", "baza paliw nr",
      "terminal naftowy", "terminal paliwowy", "składy mps"], "Instalacje paliwowe"),
    (["stacja wodorowa", "instalacja wodorowa", "elektrolizer",
      "rfnbo", "hydrogen eagle", "instalacja do produkcji wodoru"], "Instalacje wodorowe"),
    (["linia 400 kv", "linia 220 kv", "linia 110 kv",
      "400/110", "400/220", "220/110", "stacja 400", "stacja 220",
      r"\bgpz\b", "most energetyczny", "harmony link",
      "linia przesyłowa", "stacja elektroenergetyczna", "kse "], "Sieci energetyczne"),
    (["gazociąg", "tłocznia gazu", "terminal lng", "pmg ",
      "podziemny magazyn gazu", "regazyfikacja"], "Obiekty sieci gazowej"),
    (["spalarnia odpadów", "instalacja termicznego przekształcania",
      "zakład termicznego przekształcania", "zakład unieszkodliwiania",
      "składowisko odpadów", "sortownia odpadów", "kompostownia"], "Obiekty składowania i utylizacji odpadów"),
    (["tramwaj", "linia tramwajowa", "trasa tramwajowa",
      "torowisko tramwajowe", "torowisko w ulicy"], "Drogi tramwajowe"),
    (["most nad", "most przez", "most w ciągu", "most drogowy",
      r"\bwiadukt\b", "wiadukty ", r"\bestakada\b", r"\bkładka\b",
      "mosty i wiadukty"], "Mosty, wiadukty i estakady"),
    (["tunel drogowy", "tunel kolejowy", "tunel tramwajowy",
      "przejście podziemne", "przejścia podziemne"], "Tunele i przejścia podziemne"),
    (["centrum danych", "data center", "datacenter", r"\bserwerowni\b"], "Centra danych"),
    (["szpital", "centrum onkologiczne", "szpital kliniczny",
      "szpital uniwersytecki", "samodzielny publiczny", "sp zoz",
      "zakład opiekuńczo-leczniczy"], "Budynki szpitali i zakładów opieki medycznej"),
    (["szkoła podstawowa", "szkoła średnia", "szkoła zawodowa", "szkoła branżowa",
      "liceum", "technikum", "uczelnia ", "wydział ", "kampus", "campus",
      "centrum badawcz", "instytut badawcz", "budynek dydaktyczny"], "Budynki szkół i instytucji badawczych"),
    (["hala widowiskowo-sportowa", "hala sportowo-widowisk", "hala sportowa",
      "hala lekkoatletyczna", "arena sportowa"], "Hale sportowe"),
    (["kryty basen", "pływalnia kryta", "hala basenowa", "aquapark",
      "centrum aqua", "park wodny"], "Kryte baseny"),
    (["muzeum", "teatr ", "opera ", "filharmonia", "centrum kultury",
      "dom kultury", "bibliotek", "galeria sztuki", "planetarium"], "Budynki kultury i rozrywki oraz muzea"),
    (["archiwum państwowe", "archiwum narodowe",
      "sąd rejonowy", "sąd okręgowy", "sąd apelacyjny",
      "prokuratura", "urząd marszałkowski", "urząd skarbowy",
      "budynek administracyjno-biurowy"], "Budynki biurowe administracji publicznej"),
    (["parking wielopoziomowy", "parking podziemny",
      "garaż wielopoziomowy", "budynek parkingowy"], "Budynki parkingowe i garażowe"),
    (["akademik", "dom studencki", "domy studenckie", "bursa szkolna"], "Akademiki"),
    (["dom pomocy społecznej", "dom seniora", "miasteczko seniora",
      "zakład opiekuńczo", r"\bdps\b"], "Domy opieki dla osób starszych i niepełnosprawnych"),
    (["mieszkanie dla rozwoju", "mieszkanie plus", r"\bsim\b", r"\btbs\b", r"\bptbs\b",
      "najem komunalny", "mieszkania na wynajem"], "Budynki z mieszkaniami na wynajem"),
    (["fabryka amunicji", "fabryka broni", "huta miedzi", "stalownia"], "Obiekty przemysłowe"),
]

_MILITARY_INVESTOR_KW = [
    r"\bRZI\b", r"\bTOL\b", r"\bSZI\b", r"\bWAT\b", r"\bAMW\b",
    r"\bZIOTP\b", r"\bMON\b", r"\bPGZ\b",
    "wojskowy zarząd infrastruktury", "stołeczny zarząd infrastruktury",
    "zarząd infrastruktury sił powietrznych",
    "akademia wojsk lądowych", "lotnicza akademia wojskowa",
    "wojskowy instytut medyczny", "szpital wojskowy",
    "rejonowy zarząd infrastruktury", r"\bWOG\b",
]
_MILITARY_NAME_KW = [
    "wojskow", "koszarowy", "koszarowe", "koszar",
    "garnizon", "poligon wojsk", "miejsce stacjonowania",
    "baza wojskowa", "budynki sztabowo-koszarowe",
    "fabryka amunicji", "fabryka broni", "zbrojeniow",
    "składy mps", "centrum wsparcia logistycznego",
]
_RENOVATION_KW = [
    "modernizacja", "przebudowa", "rewitalizacja", "remont",
    "dobudowa", "odbudowa", "renowacja", "rekonstrukcja",
    "przystosowanie do", "dostosowanie do",
]


def kompas_sektor_to_baza(kompas_sektor_str: str) -> str | None:
    """Map a Kompas 'sector - subsector' string to a database sector name."""
    s = (kompas_sektor_str or "").lower()
    for key, sektor in _KOMPAS_SEKTOR_MAP:
        if key in s:
            return sektor
    return None


def classify_investment(
    name: str,
    investor: str = "",
    kompas_sektor: str | None = None,
) -> dict:
    """
    Classify an investment by sector, segment, renovation type, and military flag.

    Returns a dict with keys: segment, sektor, sektor_pkob, remonty, wojsko.
    All values are strings or None.
    """
    name_l    = (name or "").lower()
    inv_l     = (investor or "").lower()
    combined  = name_l + " " + inv_l

    result = {"segment": None, "sektor": None, "sektor_pkob": None, "remonty": None, "wojsko": None}

    # 1. Sector — keyword rules (order matters)
    for sektor_name, patterns in _SECTOR_RULES:
        for pat in patterns:
            try:
                matched = re.search(pat, combined, re.IGNORECASE)
            except re.error:
                matched = pat.lower() in combined
            if matched:
                result["sektor"]      = sektor_name
                result["sektor_pkob"] = SEKTOR_PKOB.get(sektor_name, "")
                break
        if result["sektor"]:
            break

    # 2. Segment — keyword rules
    for keywords, segment_name in _SEGMENT_RULES:
        for kw in keywords:
            try:
                matched = re.search(kw, name_l, re.IGNORECASE)
            except re.error:
                matched = kw.lower() in name_l
            if matched:
                result["segment"] = segment_name
                if not result["sektor"]:
                    seg_sektor = _SEGMENT_TO_SECTOR.get(segment_name)
                    if seg_sektor:
                        result["sektor"]      = seg_sektor
                        result["sektor_pkob"] = SEKTOR_PKOB.get(seg_sektor, "")
                break
        if result["segment"]:
            break

    # 2.5 Fallback — Kompas sector string
    if not result["sektor"] and kompas_sektor:
        hint = kompas_sektor_to_baza(kompas_sektor)
        if hint:
            result["sektor"]      = hint
            result["sektor_pkob"] = SEKTOR_PKOB.get(hint, "")

    # 3. Renovation flag
    for kw in _RENOVATION_KW:
        if kw in name_l:
            result["remonty"] = "Remonty, modernizacje, rewitalizacje, przebudowy"
            break

    # 4. Military flag — investor first, then name
    for pat in _MILITARY_INVESTOR_KW:
        try:
            matched = re.search(pat, inv_l, re.IGNORECASE)
        except re.error:
            matched = pat.lower() in inv_l
        if matched:
            result["wojsko"] = "Inwestycje wojskowe"
            break
    if not result["wojsko"]:
        for pat in _MILITARY_NAME_KW:
            try:
                matched = re.search(pat, name_l, re.IGNORECASE)
            except re.error:
                matched = pat.lower() in name_l
            if matched:
                result["wojsko"] = "Inwestycje wojskowe"
                break

    return result

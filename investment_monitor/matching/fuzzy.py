"""
Fuzzy matching helpers.

Three use cases:
  1. Kompas → database  (fuzzy_match_kompas)
  2. TED → database     (fuzzy_match_ted)
  3. Build ID index for fast exact-match lookups (build_id_index)
  4. Detect field-level changes between a database row and new Kompas data (detect_changes)
"""
import re
import difflib

from investment_monitor.config import FUZZY_THRESHOLD, COMPARE_COLS


# ── ID index ──────────────────────────────────────────────────────────────────

def build_id_index(df) -> dict:
    """
    Build a {kompas_id: row_index} lookup from all link columns.

    Used for O(1) exact matching before falling back to fuzzy search.
    """
    link_cols = [c for c in df.columns if "Linki" in c or c.startswith("Unnamed")]
    id_to_row = {}
    for idx, row in df.iterrows():
        for col in link_cols:
            val = str(row.get(col, ""))
            if "kompasinwestycji.pl" in val:
                inv_id = _extract_id(val)
                if inv_id:
                    id_to_row[inv_id] = idx
    return id_to_row


def _extract_id(url: str) -> str | None:
    m = re.search(r"-(\d+)/?$", str(url))
    return m.group(1) if m else None


# ── Kompas fuzzy match ────────────────────────────────────────────────────────

def fuzzy_match_kompas(kompas_data: dict, df, threshold: float = FUZZY_THRESHOLD):
    """
    Find the best-matching row in the database for a Kompas investment.

    Skips rows that already have a Kompas link (different URL = different investment).
    Combines name similarity (70%) and location similarity (30%).

    Returns (row_index, score) or (None, 0).
    """
    k_name = kompas_data.get("Inwestycja", "").lower()
    k_loc  = kompas_data.get("Miejscowość", "").lower()
    if not k_name:
        return None, 0

    link_cols = [c for c in df.columns if "Linki" in c or c.startswith("Unnamed")]
    best_idx, best_score = None, 0

    for idx, row in df.iterrows():
        if any("kompasinwestycji.pl" in str(row.get(c, "")) for c in link_cols):
            continue
        b_name = str(row.get("Inwestycja", "")).lower()
        b_loc  = str(row.get("Miejscowość", "")).lower()

        score_name = difflib.SequenceMatcher(None, k_name, b_name).ratio()
        if score_name < 0.70:
            continue
        score_loc  = difflib.SequenceMatcher(None, k_loc, b_loc).ratio() if k_loc and b_loc else 0
        score      = score_name * 0.7 + score_loc * 0.3

        if score > best_score:
            best_score, best_idx = score, idx

    return (best_idx, best_score) if best_score >= threshold else (None, 0)


# ── TED fuzzy match ───────────────────────────────────────────────────────────

_WORK_SUFFIX_RE = re.compile(
    r"\s+-\s+(?:rozbudowa|przebudowa|modernizacja|remont|rewitalizacja|naprawa|"
    r"budowa|odbudowa|nadbudowa|termomodernizacja|adaptacja|rekonstrukcja).*$",
    re.IGNORECASE,
)


def fuzzy_match_ted(item: dict, df, threshold: float = 0.70):
    """
    Find the best-matching database row for a TED notice.

    Tries three strategies and picks the best score:
      1. name + city   (weights: 0.65 / 0.35)
      2. name + investor (weights: 0.60 / 0.40)
      3. name only     (threshold: 0.78)

    Names are compared both with and without work-type suffixes
    ("- rozbudowa", "- modernizacja" etc.) to avoid false negatives
    when the database entry lacks such a suffix.

    Returns (row_index, score, match_type) or (None, 0, None).
    """
    t_name     = item.get("Inwestycja", "").lower()
    t_city     = item.get("Miejscowość", "").lower()
    t_investor = item.get("Inwestor", "").lower()
    if not t_name:
        return None, 0, None

    t_name_base = _WORK_SUFFIX_RE.sub("", t_name)
    best_idx, best_score, best_type = None, 0, None

    for idx, row in df.iterrows():
        if row.get("Status inwestycji", "") == "Inwestycja zakończona":
            continue
        b_name     = str(row.get("Inwestycja", "")).lower()
        b_city     = str(row.get("Miejscowość", "")).lower()
        b_investor = str(row.get("Inwestor", "")).lower()
        b_name_base = _WORK_SUFFIX_RE.sub("", b_name)

        score_name = max(
            difflib.SequenceMatcher(None, t_name, b_name).ratio(),
            difflib.SequenceMatcher(None, t_name_base, b_name_base).ratio(),
        )
        if score_name < 0.55:
            continue

        if t_city and b_city:
            score_city = difflib.SequenceMatcher(None, t_city, b_city).ratio()
            score = score_name * 0.65 + score_city * 0.35
            if score > best_score:
                best_score, best_idx, best_type = score, idx, "name+city"

        if t_investor and b_investor:
            score_inv = difflib.SequenceMatcher(None, t_investor, b_investor).ratio()
            score = score_name * 0.60 + score_inv * 0.40
            if score > best_score:
                best_score, best_idx, best_type = score, idx, "name+investor"

        if score_name > 0.78 and score_name > best_score:
            best_score, best_idx, best_type = score_name, idx, "name_only"

    return (best_idx, best_score, best_type) if best_score >= threshold else (None, 0, None)


# ── Change detection ──────────────────────────────────────────────────────────

def detect_changes(baza_row, kompas_data: dict, cols_in_baza: list) -> list[str]:
    """
    Return the list of column names where the Kompas value differs from the database.

    For 'Ostatni status' only the date prefix (first 10 characters) is compared,
    since the full text changes frequently with minor edits.
    """
    changed = []
    for col in COMPARE_COLS:
        if col not in cols_in_baza:
            continue
        baza_val   = str(baza_row.get(col, "")).strip()
        kompas_val = str(kompas_data.get(col, "") or "").strip()
        if not kompas_val:
            continue
        if col == "Ostatni status":
            if baza_val[:10] and kompas_val[:10] and baza_val[:10] != kompas_val[:10]:
                changed.append(col)
        else:
            if baza_val != kompas_val:
                changed.append(col)
    return changed

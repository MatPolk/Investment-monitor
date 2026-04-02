"""
Kompas Inwestycji — investment detail-page parser.

Takes raw HTML of an individual investment page and extracts all
structured fields into a dict that mirrors the column layout of the
reference database.
"""
import re
import logging

from bs4 import BeautifulSoup

from investment_monitor.utils.text import (
    clean_text,
    clean_company_name,
    capitalize_woj,
    parse_city_woj,
    format_quarter_date,
    quarter_to_date,
    normalize_inv_name,
    parse_wartosc_netto,
    map_phase,
)


# ── Company extraction ────────────────────────────────────────────────────────

def _extract_companies(vd) -> str:
    """
    Extract company names from a value <div>.

    Kompas inserts an analytics link ("Sprawdź firmy...") next to the real
    company link — we only keep links whose href contains '/firma/'.
    Falls back to the full text of the div if no company links are found.
    """
    links = vd.find_all("a", href=re.compile(r"firma/"))
    if links:
        names = [
            clean_company_name(clean_text(a.get_text()))
            for a in links if a.get_text(strip=True)
        ]
        return "; ".join(n for n in names if n)
    return clean_company_name(clean_text(vd.get_text(strip=True)))


# ── Aktualności section ───────────────────────────────────────────────────────

def extract_last_status(soup: BeautifulSoup) -> str | None:
    """
    Extract the most recent news entry from the Aktualności section.

    Returns a string in the format: 'YYYY-MM-DD Title\nDescription'
    """
    blok = soup.find("div", id="blok-aktualnosci")
    if not blok:
        return None
    content_div = blok.find("div", class_=re.compile(r"col-.*sm-9"))
    if not content_div:
        return None

    children = list(content_div.children)
    for i, child in enumerate(children):
        if not hasattr(child, "name") or child.name != "div":
            continue
        classes = child.get("class", [])
        if "collapse" in classes:
            break
        if "m-b-1" in classes:
            continue
        date_span = child.find("span", class_="cl--brand")
        if not date_span:
            continue
        date_text = date_span.get_text(strip=True)
        if not re.match(r"\d{4}-\d{2}-\d{2}", date_text):
            continue
        strong = child.find("strong")
        title  = clean_text(strong.get_text(strip=True)) if strong else ""
        desc   = ""
        for j in range(i + 1, min(i + 4, len(children))):
            sib = children[j]
            if hasattr(sib, "name") and sib.name == "div" and "m-b-1" in sib.get("class", []):
                desc = sib.get_text(separator="\n", strip=True)
                break
        result = f"{date_text} {title}"
        if desc:
            result += f"\n{desc}"
        return result
    return None


# ── GW / contract value from Aktualności ─────────────────────────────────────

_DESIGN_RE = re.compile(
    r"dokumentac\w*|projektant\w*|ste[sś]\b|nadzor\w*\s+autor\w*|koncepcj\w*",
    re.IGNORECASE,
)


def extract_gw_value_from_aktualizacje(
    soup: BeautifulSoup, confirmed_gw: str = ""
) -> tuple[str | None, float | None]:
    """
    Extract the winning contractor and contract value from an 'wybór oferty' news entry.

    Returns (contractor_string, value_netto_mln) or (None, None) when:
    - No 'wybór oferty' entry exists
    - The entry is about a design contract (not construction)
    - The winning firm cannot be confirmed by cross-referencing the Firms section
      or a subsequent 'works in progress' entry
    """
    content_div = None
    blok = soup.find("div", id="blok-aktualnosci")
    if blok:
        content_div = blok.find("div", class_=re.compile(r"col-.*sm-9"))
    if not content_div:
        for strong in soup.find_all("strong"):
            if "aktualności" in clean_text(strong.get_text()).lower():
                row = strong.find_parent("div", class_=re.compile(r"\brow\b"))
                if row:
                    content_div = row.find("div", class_=re.compile(r"col-.*sm-9"))
                if content_div:
                    break
    if not content_div:
        return None, None

    full_text = content_div.get_text(separator="\n", strip=True)

    if "wybór oferty" not in full_text.lower() and "wybor oferty" not in full_text.lower():
        return None, None

    # Skip entries about design contracts
    for line in full_text.split("\n"):
        if "wybor oferty" in line.lower() or "wybór oferty" in line.lower():
            if _DESIGN_RE.search(line):
                return None, None
            break

    m_firma = re.search(
        r"jako najkorzystniejsz\w+ uznano ofert\w+ (?:firmy|konsorcjum):\s*(.+)",
        full_text, re.IGNORECASE,
    )
    if not m_firma:
        return None, None

    firms_raw  = re.split(r"\s+-\s+(?:wartość|termin)", m_firma.group(1).strip(), flags=re.IGNORECASE)[0].strip()
    firm_list  = [clean_company_name(f.strip()) for f in re.split(r"\s+oraz\s+", firms_raw, flags=re.IGNORECASE)]
    firm_list  = [f for f in firm_list if f]
    if not firm_list:
        return None, None
    gw_str = "; ".join(firm_list)

    # Contract value
    m_val = re.search(
        r"warto\w+\s+z\w+onej\s+oferty\s+wynosi:\s*([\d\s]+(?:[,.][\d]+)?)\s*PLN\s+brutto",
        full_text, re.IGNORECASE,
    )
    value_netto = None
    if m_val:
        val_str = re.sub(r"\s+", "", m_val.group(1)).replace(",", ".")
        try:
            value_netto = round(float(val_str) / 1_000_000 / 1.23, 1)
        except ValueError:
            pass

    # Confirm the contractor
    confirmed = False
    if confirmed_gw:
        gw_lower = confirmed_gw.lower()
        for firm in firm_list:
            f_lower = firm.lower()
            if f_lower and (
                f_lower in gw_lower or gw_lower in f_lower
                or any(w in gw_lower for w in f_lower.split() if len(w) > 4)
            ):
                confirmed = True
                break

    if not confirmed:
        wybor_pos = -1
        for marker in ("wybór oferty", "wybor oferty"):
            p = full_text.lower().find(marker)
            if p > 0:
                wybor_pos = p
                break
        if wybor_pos > 0:
            newer_text = full_text[:wybor_pos]
            if re.search(
                r"trwaj\w+\s+(?:prace|roboty|budow\w*)"
                r"|umow\w+\s+(?:podpisano|zawarto|podpisana|zawarta)"
                r"|podpisano\s+umow"
                r"|(?:wykonawca|przedstawiciel)\s+(?:poinformowa\w+|przekaza\w+|potwierdzi\w+)",
                newer_text, re.IGNORECASE,
            ):
                confirmed = True

    if not confirmed:
        return None, None

    return gw_str or None, value_netto


# ── Main detail-page parser ───────────────────────────────────────────────────

def extract_investment_data(html_content: str) -> dict:
    """
    Parse a Kompas investment detail page and return a field dict.

    The returned keys match the column names of the reference database.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    data: dict = {}

    for row in soup.find_all("div", class_="row"):
        label_divs = row.find_all("div", class_=re.compile(r"col-.*sm-[34]"))
        for ld in label_divs:
            strong = ld.find("strong")
            if not strong:
                continue
            label = clean_text(strong.get_text(strip=True)).lower()

            vd = None
            for sib in ld.find_next_siblings("div"):
                if any(re.search(r"sm-[89]", c) for c in (sib.get("class") or [])):
                    vd = sib
                    break
            if not vd:
                vd = row.find("div", class_=re.compile(r"col-.*sm-[89]"))
            if not vd:
                continue

            val = clean_text(vd.get_text(strip=True))

            if "nazwa inwestycji" in label:
                data["Inwestycja"] = val
            elif label == "województwo":
                data["Województwo"] = capitalize_woj(val)
            elif "miasto początkowe" in label:
                city, woj = parse_city_woj(val)
                data["_city_start"] = city
                if woj and not data.get("_woj_from_city"):
                    data["_woj_from_city"] = woj
            elif "miasto końcowe" in label:
                city, woj = parse_city_woj(val)
                data["_city_end"] = city
                if woj and not data.get("_woj_end"):
                    data["_woj_end"] = woj
            elif label == "miasto":
                city, woj = parse_city_woj(val)
                data["Miejscowość"] = city
                if woj and not data.get("_woj_from_city"):
                    data["_woj_from_city"] = woj
            elif "ogólne informacje" in label or "informacje ogólne" in label:
                data["_opis"] = val
            elif "data rozpoczęcia" in label and "Start kompas" not in data:
                data["Start kompas"] = format_quarter_date(val)
            elif "data zakończenia" in label and "Koniec kompas" not in data:
                data["Koniec kompas"] = format_quarter_date(val)
            elif label == "etap":
                raw = re.sub(r"^[^a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]*", "", val).strip()
                data["Etap kompas"] = map_phase(raw)
            elif "inwestor" in label or "zamawiający" in label:
                company = _extract_companies(vd)
                if company:
                    existing = data.get("Inwestor", "")
                    data["Inwestor"] = (existing + "; " + company).strip("; ") if existing else company
            elif any(kw in label for kw in ["gw kubaturowy", "gw inżynieryjny",
                                             "gw inżynieryjny / kubaturowy",
                                             "generalny wykonawca", "gw:"]):
                company = _extract_companies(vd)
                if company:
                    existing = data.get("Generalny wykonawca", "")
                    data["Generalny wykonawca"] = (existing + "; " + company).strip("; ") if existing else company
            elif "sektor" in label and "podsektor" in label:
                data["_kompas_sektor"] = val.lower().strip()
            elif "wartość" in label and not data.get("Wartość (mln zł)"):
                netto = parse_wartosc_netto(val)
                if netto:
                    data["Wartość (mln zł)"] = netto

    # ── Post-processing ───────────────────────────────────────────────────────

    if "_city_start" in data:
        city_end = data.get("_city_end", "")
        data["Miejscowość"] = (
            f"{data['_city_start']}-{city_end}" if city_end and city_end != data["_city_start"]
            else data["_city_start"]
        )

    if "Województwo" not in data:
        ws, we = data.get("_woj_from_city"), data.get("_woj_end")
        if ws and we and ws != we:
            data["Województwo"] = f"{ws}; {we}"
        elif ws:
            data["Województwo"] = ws
        elif we:
            data["Województwo"] = we

    for _k in ["_city_start", "_city_end", "_woj_from_city", "_woj_end"]:
        data.pop(_k, None)

    opis = data.pop("_opis", None)
    work_type_from_desc = None
    if opis:
        _m = re.search(
            r"\b(rozbudowa|przebudowa|modernizacja|remont|rewitalizacja|"
            r"odbudowa|dobudowa|rekonstrukcja)\b",
            opis, re.IGNORECASE,
        )
        if _m:
            work_type_from_desc = _m.group(1).lower()

    if data.get("Inwestycja"):
        data["Inwestycja"] = normalize_inv_name(data["Inwestycja"], work_type_from_desc)

    data["Ostatni status"] = extract_last_status(soup)

    gw_from_akt, val_from_akt = extract_gw_value_from_aktualizacje(
        soup, data.get("Generalny wykonawca", "")
    )
    if gw_from_akt and not data.get("Generalny wykonawca"):
        data["Generalny wykonawca"] = gw_from_akt
    if val_from_akt and not data.get("Wartość (mln zł)"):
        data["Wartość (mln zł)"] = val_from_akt

    if data.get("Etap kompas"):
        data["Status inwestycji"] = data["Etap kompas"]

    if data.get("Start kompas"):
        data["Start budowy.1"] = data["Start kompas"]
        data["Start budowy"]   = quarter_to_date(data["Start kompas"])
    if data.get("Koniec kompas"):
        data["Koniec budowy.1"] = data["Koniec kompas"]
        data["Koniec budowy"]   = quarter_to_date(data["Koniec kompas"])

    return data

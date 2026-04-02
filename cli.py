"""
Command-line entry point.

Usage:
  python cli.py                   # incremental Kompas scan
  python cli.py --pages 10        # full scan of 10 pages (ignores last_id)
  python cli.py --ted             # include TED notices (incremental)
  python cli.py --ted --days-back 180  # TED with explicit date range
"""
import sys
import logging
import difflib
import argparse
from datetime import date
from time import sleep

import pandas as pd

from investment_monitor.config import (
    DATABASE_FILE, OUTPUT_FILE, IGNORED_FILE, LOG_FILE,
    REQUEST_DELAY, COMPARE_COLS,
)
from investment_monitor.state import load_last_id, save_last_id
from investment_monitor.kompas.session import create_session
from investment_monitor.kompas.scraper import fetch_page, build_page_url, parse_listing, extract_id
from investment_monitor.kompas.parser import extract_investment_data
from investment_monitor.matching.fuzzy import build_id_index, fuzzy_match_kompas, detect_changes
from investment_monitor.classify.classifier import classify_investment
from investment_monitor.output.excel import generate_output, load_baza_formatting


# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


# ── Database helpers ──────────────────────────────────────────────────────────

def load_baza():
    logging.info(f"Loading database: {DATABASE_FILE}")
    df = pd.read_excel(DATABASE_FILE, sheet_name=0, dtype=str)
    return df.fillna("")


def load_ignorowane() -> set:
    import csv, os
    ignored = set()
    if os.path.exists(IGNORED_FILE):
        with open(IGNORED_FILE, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ignored.add(row.get("id", "").strip())
    return ignored


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="Infrastructure investment monitor")
    parser.add_argument(
        "--pages", type=int, default=0,
        help="Full-scan mode: fetch N pages (ignores last_id). Default 0 = incremental.",
    )
    parser.add_argument(
        "--ted", action="store_true",
        help="Include TED EU notices (construction, Poland, ≥ 40M PLN net).",
    )
    parser.add_argument(
        "--days-back", type=int, default=None,
        help="TED date-range override: fetch the last N days. "
             "Default: auto (from ted_last_date.txt; 365 days on first run).",
    )
    return parser.parse_args()


# ── Pipeline stages ───────────────────────────────────────────────────────────

def run_kompas(session, args):
    """
    Fetch Kompas pages until last_id is seen (incremental) or N pages (full scan).

    Returns (investments_to_process, new_last_id).
    """
    last_id   = load_last_id()
    full_scan = args.pages > 0
    max_pages = args.pages if full_scan else 10_000

    all_investments = []
    for page_num in range(1, max_pages + 1):
        url  = build_page_url(page_num)
        mode = f"{page_num}/{args.pages}" if full_scan else str(page_num)
        logging.info(f"Fetching page {mode}: {url}")
        html = fetch_page(session, url)
        if not html:
            if page_num == 1:
                logging.error("Could not fetch page 1 — aborting")
                sys.exit(1)
            break
        page_invs = parse_listing(html)
        logging.info(f"  Page {page_num}: {len(page_invs)} investments")
        if not page_invs:
            break
        all_investments.extend(page_invs)

        if not full_scan and last_id:
            if last_id in {inv["id"] for inv in page_invs}:
                logging.info(f"  Found last_id={last_id} — stopping pagination")
                break
        if page_num < max_pages:
            sleep(REQUEST_DELAY)

    if not all_investments:
        logging.error("No investments found — check session / parsing")
        sys.exit(1)

    seen, investments = set(), []
    for inv in all_investments:
        if inv["id"] not in seen:
            seen.add(inv["id"])
            investments.append(inv)
    logging.info(f"Unique investments: {len(investments)}")

    new_last_id = investments[0]["id"]

    if full_scan:
        to_process = investments
    elif last_id:
        to_process = [inv for inv in investments if inv["id"] != last_id]
        to_process = to_process[:next(
            (i for i, inv in enumerate(investments) if inv["id"] == last_id),
            len(investments),
        )]
    else:
        to_process = investments

    return to_process, new_last_id


def process_kompas_investments(session, to_process, df_baza, df_active, id_to_row, ignored_ids):
    """
    Fetch detail pages, classify or match each investment.

    Returns (nowe, aktualizacje, stats).
    """
    baza_cols  = list(df_baza.columns)
    status_col = "Status inwestycji"
    nowe, aktualizacje = [], []
    stats = {"ok": 0, "new": 0, "updated": 0, "unchanged": 0, "errors": 0}

    for inv in to_process:
        sleep(REQUEST_DELAY)
        stats["ok"] += 1
        logging.info(f"[{stats['ok']}/{len(to_process)}] {inv['id']} {inv['name'][:60]}")
        html_page = fetch_page(session, inv["url"])
        if not html_page:
            stats["errors"] += 1
            continue

        kompas_data          = extract_investment_data(html_page)
        kompas_data["Linki"] = inv["url"]

        match_idx   = id_to_row.get(inv["id"])
        match_type  = "ID"
        fuzzy_score = None

        if match_idx is None:
            match_idx, fuzzy_score = fuzzy_match_kompas(kompas_data, df_active)
            if match_idx is not None:
                match_type = "FUZZY"
                logging.info(f"  Fuzzy match {fuzzy_score:.0%} → {df_baza.loc[match_idx]['Inwestycja'][:60]}")

        if match_idx is not None:
            baza_row = df_baza.loc[match_idx]
            if baza_row.get(status_col, "") == "Inwestycja zakończona":
                continue
            if inv["id"] in ignored_ids:
                continue
            changed = detect_changes(baza_row, kompas_data, baza_cols)
            if match_type == "FUZZY" and "Linki" not in changed:
                if not str(baza_row.get("Linki", "")).strip():
                    changed.append("Linki")
            if changed:
                aktualizacje.append({
                    "baza_row": baza_row, "baza_row_idx": match_idx,
                    "kompas_data": kompas_data, "changed_cols": changed,
                    "match_type": match_type, "fuzzy_score": fuzzy_score,
                    "inv_id": inv["id"],
                })
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1
        else:
            cls = classify_investment(
                kompas_data.get("Inwestycja", ""),
                investor=kompas_data.get("Inwestor", ""),
                kompas_sektor=kompas_data.get("_kompas_sektor"),
            )
            for key, field in [("segment", "Znaczące segmenty"), ("sektor", "Sektor"),
                                ("sektor_pkob", "Sektor.1")]:
                if cls[key]:
                    kompas_data.setdefault(field, cls[key])
            if cls["remonty"]:
                kompas_data["Remonty, modernizacje, rewitalizacje, przebudowy"] = cls["remonty"]
            if cls["wojsko"]:
                kompas_data["Inwestycje wojskowe"] = cls["wojsko"]
            nowe.append({"kompas_data": kompas_data, "url": inv["url"]})
            stats["new"] += 1

    return nowe, aktualizacje, stats


def run_ted(df_baza, days_back):
    """Fetch and match TED EU notices. Returns (ted_nowe, ted_dopasowane)."""
    from investment_monitor.ted.client import fetch_ted
    return fetch_ted(df_baza, days_back=days_back)


def cross_match_ted_kompas(nowe, ted_nowe):
    """
    Merge TED items into Kompas new-investments list where names are similar.

    Returns updated (nowe, ted_remaining).
    Modifies nowe in-place (adds TED link and value where missing).
    """
    ted_remaining, merged = [], 0
    for ted_item in ted_nowe:
        ted_name = ted_item.get("Inwestycja", "").lower()
        ted_city = ted_item.get("Miejscowość", "").lower()
        best_score, best_idx = 0, None
        for i, k_item in enumerate(nowe):
            kd    = k_item["kompas_data"]
            n_sim = difflib.SequenceMatcher(None, ted_name, kd.get("Inwestycja", "").lower()).ratio()
            c_sim = difflib.SequenceMatcher(None, ted_city, kd.get("Miejscowość", "").lower()).ratio() if ted_city else 0
            score = n_sim * 0.7 + c_sim * 0.3
            if score > best_score:
                best_score, best_idx = score, i
        if best_score >= 0.55 and best_idx is not None:
            kd = nowe[best_idx]["kompas_data"]
            ted_link = ted_item.get("Linki", "")
            if ted_link:
                for lc in ["Unnamed: 25", "Unnamed: 26", "Unnamed: 27", "Unnamed: 28"]:
                    if not kd.get(lc):
                        kd[lc] = ted_link
                        break
            if ted_item.get("Wartość (mln zł)") and not kd.get("Wartość (mln zł)"):
                kd["Wartość (mln zł)"] = ted_item["Wartość (mln zł)"]
            merged += 1
        else:
            ted_remaining.append(ted_item)
    if merged:
        logging.info(f"Cross-match: {merged} TED merged into Kompas new")
    return ted_remaining


def generate_report(nowe, df_baza, row_fonts, col_widths,
                    ted_nowe, ted_dopasowane, kompas_dopasowane, stats):
    """Write the output Excel file and log a summary."""
    if nowe or ted_nowe or ted_dopasowane or kompas_dopasowane:
        generate_output(nowe, df_baza, row_fonts, col_widths,
                        ted_nowe=ted_nowe, ted_dopasowane=ted_dopasowane,
                        kompas_dopasowane=kompas_dopasowane)
    else:
        logging.info("No new investments — output file not generated")

    logging.info(
        f"\n{'='*60}\n"
        f"DONE\n"
        f"Processed (Kompas): {stats['ok']}\n"
        f"New: {stats['new']} Kompas + {len(ted_nowe)} TED\n"
        f"Matched: {len(ted_dopasowane)} TED + {len(kompas_dopasowane)} Kompas\n"
        f"Errors: {stats['errors']}\n"
        f"{'='*60}"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args    = parse_args()
    session = create_session()

    to_process, new_last_id = run_kompas(session, args)

    if not to_process and not args.ted:
        logging.info("No changes since last run")
        save_last_id(new_last_id)
        return

    df_baza     = load_baza()
    id_to_row   = build_id_index(df_baza)
    status_col  = "Status inwestycji"
    df_active   = df_baza[df_baza[status_col] != "Inwestycja zakończona"] if status_col in df_baza.columns else df_baza
    ignored_ids = load_ignorowane()
    row_fonts, col_widths = load_baza_formatting()

    nowe, aktualizacje, stats = process_kompas_investments(
        session, to_process, df_baza, df_active, id_to_row, ignored_ids
    )

    ted_nowe, ted_dopasowane = [], []
    if args.ted:
        ted_nowe, ted_dopasowane = run_ted(df_baza, args.days_back)

    if nowe and ted_nowe:
        ted_nowe = cross_match_ted_kompas(nowe, ted_nowe)

    kompas_dopasowane = [
        a for a in aktualizacje
        if a["match_type"] == "FUZZY" and not str(df_baza.loc[a["baza_row_idx"]].get("Linki", "")).strip()
    ]

    generate_report(nowe, df_baza, row_fonts, col_widths,
                    ted_nowe, ted_dopasowane, kompas_dopasowane, stats)
    save_last_id(new_last_id)


if __name__ == "__main__":
    main()

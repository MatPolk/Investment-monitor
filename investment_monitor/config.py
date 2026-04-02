"""
Central configuration loader.

Reads config.yaml from the project root and exposes typed constants
used across all modules. Keeps every configurable value in one place.
"""
import os
import yaml

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_FILE = os.path.join(_BASE_DIR, "config.yaml")

with open(_CONFIG_FILE, encoding="utf-8") as _f:
    _cfg = yaml.safe_load(_f)

# ── File paths ────────────────────────────────────────────────────────────────
BASE_DIR        = _BASE_DIR
DATABASE_FILE   = os.path.join(_BASE_DIR, _cfg["database_file"])
OUTPUT_FILE     = os.path.join(_BASE_DIR, _cfg["output_file"])
IGNORED_FILE    = os.path.join(_BASE_DIR, _cfg["ignored_file"])
LAST_ID_FILE    = os.path.join(_BASE_DIR, "last_id.txt")
TED_LAST_DATE_FILE = os.path.join(_BASE_DIR, "ted_last_date.txt")
LOG_FILE        = os.path.join(_BASE_DIR, "monitor.log")

# ── Kompas ────────────────────────────────────────────────────────────────────
KOMPAS_BASE_URL     = _cfg["kompas"]["base_url"]
KOMPAS_LISTING_PATH = _cfg["kompas"]["listing_path"].replace("\n", "").strip()
KOMPAS_MONITOR_URL  = KOMPAS_BASE_URL + KOMPAS_LISTING_PATH
REQUEST_DELAY       = float(_cfg["kompas"]["request_delay"])
REQUEST_TIMEOUT     = int(_cfg["kompas"]["request_timeout"])

# ── TED ───────────────────────────────────────────────────────────────────────
TED_API_URL        = _cfg["ted"]["api_url"]
TED_MIN_VALUE_NETTO = float(_cfg["ted"]["min_value_netto_mln"])   # mln PLN netto
TED_MIN_VALUE_PLN   = int(TED_MIN_VALUE_NETTO * 1_000_000)        # PLN (for API filter)

# ── Matching ──────────────────────────────────────────────────────────────────
FUZZY_THRESHOLD = float(_cfg["matching"]["fuzzy_threshold"])

# ── Column groups ─────────────────────────────────────────────────────────────
# Columns compared between Kompas data and the local database on each run
COMPARE_COLS = ["Start kompas", "Koniec kompas", "Etap kompas", "Ostatni status"]

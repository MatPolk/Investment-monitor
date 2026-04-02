# Investment Monitor

Automated monitoring pipeline for large infrastructure tenders in Poland
(construction value ≥ 40M PLN net).

Combines two data sources and cross-references them against a reference
database of ~4 200 tracked investments.

---

## What it does

```
┌─────────────────────┐     ┌───────────────────────────────┐
│  Kompas Inwestycji  │     │  TED EU (api.ted.europa.eu)   │
│  (Polish investment │     │  Construction notices, CPV 45*│
│   portal, scraped)  │     │  Poland, ≥ 40M PLN net        │
└────────┬────────────┘     └────────────────┬──────────────┘
         │                                   │
         ▼                                   ▼
┌────────────────────────────────────────────────────────────┐
│              Fuzzy matching & cross-deduplication          │
│  • Kompas: exact ID match → fuzzy name+location fallback   │
│  • TED: 3-strategy fuzzy (name+city / name+investor / name)│
│  • Cross-match: same investment in both sources → merged   │
└────────────────────────────┬───────────────────────────────┘
                             │
                             ▼
                 ┌───────────────────────┐
                 │  do_zatwierdzenia.xlsx│
                 │  "Nowe"    — new      │
                 │  "Dopasowane" — diffs │
                 └───────────────────────┘
```

**Sheet "Nowe"** — investments not yet in the reference database (from both sources).  
**Sheet "Dopasowane"** — existing database rows with proposed field updates highlighted in green.

---

## Architecture

```
investment-monitor/
├── config.yaml                  ← all configurable parameters
├── investment_monitor/
│   ├── config.py                ← loads config.yaml, exposes typed constants
│   ├── state.py                 ← run-state persistence (last_id.txt, ted_last_date.txt)
│   ├── kompas/
│   │   ├── session.py           ← Firefox-cookie authentication
│   │   ├── scraper.py           ← HTTP fetching, listing-page parsing
│   │   └── parser.py            ← investment detail-page parser
│   ├── ted/
│   │   ├── normalizer.py        ← TED title → database naming convention
│   │   └── client.py            ← TED API client, pagination, deduplication
│   ├── matching/
│   │   └── fuzzy.py             ← fuzzy matching + change detection
│   ├── classify/
│   │   └── classifier.py        ← sector / segment / military / renovation flags
│   └── output/
│       └── excel.py             ← Excel file generation with formatting
├── cli.py                       ← entry point
└── tests/
    ├── test_ted_normalizer.py
    ├── test_classifier.py
    └── test_text_utils.py
```

---

## Interesting technical problems

### TED name normalisation (`ted/normalizer.py`)

TED notice titles follow EU procurement conventions and are verbose:

> *"Zaprojektowanie i wybudowanie drogi ekspresowej S8 na odcinku Wrocław-Kłodzko, zadanie 4 — odc. węzeł Łagiewniki Zachód — węzeł Niemcza"*

The normaliser dispatches to one of four sub-routines (road → rail → tram → generic)
and compresses the title to the compact database format:

> `S8 Łagiewniki Zachód-Niemcza`

Work-type prefixes are moved to a suffix (or dropped for plain "budowa"):

> `Modernizacja linii kolejowej nr 309 Kłodzko Nowe – Kudowa Zdrój`  
> → `Linia nr 309 Kłodzko Nowe-Kudowa Zdrój - modernizacja`

### Fuzzy matching (`matching/fuzzy.py`)

Names are compared both with and without work-type suffixes so that
`"S7 Radom-Kielce"` (database) matches `"S7 Radom-Kielce - rozbudowa"` (TED).

Three weighted strategies are tried per row:

| Strategy | name weight | context weight | threshold |
|---|---|---|---|
| name + city | 0.65 | 0.35 (city) | 0.70 |
| name + investor | 0.60 | 0.40 (investor) | 0.70 |
| name only | — | — | 0.78 |

### Incremental pagination (stateful runs)

Both sources track "where the last run ended" in plain text files:

- `last_id.txt` — most-recently processed Kompas listing ID
- `ted_last_date.txt` — publication date of the newest TED notice seen

Subsequent runs fetch only new data.  
`--pages N` (Kompas) and `--days-back N` (TED) override for manual backfills.

---

## Installation

```bash
pip install -r requirements.txt
```

**Authentication:** Kompas Inwestycji requires a paid account. The scraper
reads cookies from an active Firefox session via `browser-cookie3`.
Log in to the portal in Firefox before running.

---

## Usage

```bash
# Kompas only — incremental (since last run)
python cli.py

# Full scan of last 10 pages (Kompas)
python cli.py --pages 10

# Include TED notices (incremental)
python cli.py --ted

# Include TED — manual date range override
python cli.py --ted --days-back 180
```

Output file: `do_zatwierdzenia.xlsx`

---

## Tests

```bash
pytest tests/
```

Tests cover:
- TED name normalisation (road, rail, tram, construction filter) — `test_ted_normalizer.py`
- Investment classification (sector, segment, military, renovation) — `test_classifier.py`
- Text utility functions (dates, values, name normalisation) — `test_text_utils.py`

---

## Configuration

Edit `config.yaml` to change value thresholds, file paths, or matching sensitivity:

```yaml
ted:
  min_value_netto_mln: 40   # minimum net contract value in PLN millions

matching:
  fuzzy_threshold: 0.72     # similarity threshold for Kompas → database matching
```

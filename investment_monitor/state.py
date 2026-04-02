"""
Persistent run-state helpers.

Both Kompas and TED track "where we left off" so each run fetches only
new data, not the full history.  State is stored in plain text files
next to config.yaml.

  Kompas: last_id.txt      — ID of the most-recently processed listing entry
  TED:    ted_last_date.txt — ISO date (YYYY-MM-DD) of the newest notice seen
"""
import os
from investment_monitor.config import LAST_ID_FILE, TED_LAST_DATE_FILE


# ── Kompas ────────────────────────────────────────────────────────────────────

def load_last_id() -> str | None:
    """Return the Kompas ID saved from the previous run, or None on first run."""
    if os.path.exists(LAST_ID_FILE):
        val = open(LAST_ID_FILE).read().strip()
        return val or None
    return None


def save_last_id(inv_id: str) -> None:
    """Persist the ID of the newest Kompas investment processed this run."""
    with open(LAST_ID_FILE, "w") as f:
        f.write(str(inv_id))


# ── TED ───────────────────────────────────────────────────────────────────────

def load_ted_last_date() -> str | None:
    """
    Return the publication date (YYYY-MM-DD) of the newest TED notice seen,
    or None on first run.
    """
    if os.path.exists(TED_LAST_DATE_FILE):
        val = open(TED_LAST_DATE_FILE).read().strip()
        return val or None
    return None


def save_ted_last_date(date_str: str) -> None:
    """Persist the publication date of the newest TED notice processed this run."""
    with open(TED_LAST_DATE_FILE, "w") as f:
        f.write(str(date_str))

"""
Kompas Inwestycji — HTTP fetching and listing-page parsing.

Responsible for:
  - Building paginated listing URLs
  - Fetching pages with retry logic
  - Extracting the list of {id, name, url} from a listing page
"""
import re
import logging
from time import sleep

import requests
from bs4 import BeautifulSoup

from investment_monitor.config import (
    KOMPAS_BASE_URL,
    KOMPAS_MONITOR_URL,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
)


def build_page_url(page_num: int) -> str:
    """Return the URL for listing page N. Page 1 returns the base monitoring URL."""
    if page_num <= 1:
        return KOMPAS_MONITOR_URL
    return re.sub(r"(/wyswietl/\d+)$", f"/strona/{page_num}\\1", KOMPAS_MONITOR_URL)


def fetch_page(session: requests.Session, url: str, retries: int = 3) -> str | None:
    """
    GET a URL and return the response text.

    Retries up to `retries` times with exponential back-off on failure.
    Returns None if all attempts fail.
    """
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1}/{retries} failed for {url}: {e}")
            if attempt < retries - 1:
                sleep(3 * (attempt + 1))
    logging.error(f"Failed to fetch: {url}")
    return None


def extract_id(url: str) -> str | None:
    """Extract the numeric investment ID from a Kompas URL."""
    m = re.search(r"-(\d+)/?$", str(url))
    return m.group(1) if m else None


def parse_listing(html: str) -> list[dict]:
    """
    Parse a listing page and return investments ordered top-to-bottom (newest first).

    Each item: {'id': str, 'name': str, 'url': str}
    """
    soup = BeautifulSoup(html, "html.parser")
    seen, investments = set(), []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "obserwuj" in href or "mapa" in href:
            continue
        if href.startswith("/"):
            full_url = KOMPAS_BASE_URL + href
        elif "kompasinwestycji.pl" in href:
            full_url = href
        else:
            continue

        inv_id = extract_id(full_url)
        if inv_id and inv_id not in seen:
            seen.add(inv_id)
            investments.append({
                "id":   inv_id,
                "name": a.get_text(strip=True),
                "url":  full_url,
            })

    return investments

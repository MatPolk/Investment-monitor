"""
Kompas Inwestycji — authenticated HTTP session.

Authentication relies on cookies from an active Firefox session.
The portal requires a paid account; browser_cookie3 reads cookies
from the local Firefox profile without any credential storage in code.

If the portal ever exposes a token-based API, this module is the only
place that would need to change.
"""
import sys
import logging

import requests
import browser_cookie3

from investment_monitor.config import KOMPAS_BASE_URL, REQUEST_TIMEOUT


def create_session() -> requests.Session:
    """
    Build an authenticated requests.Session using Firefox cookies.

    Exits the process if authentication fails — there is no point
    continuing without a valid session.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pl,en-US;q=0.7,en;q=0.3",
    })

    try:
        cookies = browser_cookie3.firefox(domain_name="kompasinwestycji.pl")
        session.cookies = cookies
        logging.info("Loaded cookies from Firefox")
    except Exception as e:
        logging.error(f"Could not read Firefox cookies: {e}")
        sys.exit(1)

    try:
        test = session.get(KOMPAS_BASE_URL + "/", timeout=REQUEST_TIMEOUT)
        if "login" in test.url.lower() and "auth" in test.url.lower():
            logging.error("Session not active — log in to Kompas in Firefox first")
            sys.exit(1)
        logging.info("Session active")
    except Exception as e:
        logging.error(f"Connection error: {e}")
        sys.exit(1)

    return session

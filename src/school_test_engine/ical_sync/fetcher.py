"""HTTP layer for fetching iCal feeds. Translates urllib errors into FeedFetchError."""
from __future__ import annotations

import urllib.error
import urllib.request


class FeedFetchError(Exception):
    """Raised for any failure during feed download — network, HTTP status, timeout."""


def fetch_feed(url: str, timeout: float = 10.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "LearningBuddy/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                raise FeedFetchError(f"HTTP {resp.status}")
            return resp.read()
    except urllib.error.URLError as e:
        raise FeedFetchError(f"Netzwerk-Fehler: {e.reason}") from e
    except TimeoutError as e:
        raise FeedFetchError("Timeout — keine Antwort vom Server") from e

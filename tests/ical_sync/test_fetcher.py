"""Phase 15: fetcher wraps urllib with FeedFetchError translation."""
from __future__ import annotations

import urllib.error

import pytest

from school_test_engine.ical_sync import fetcher


def test_fetch_feed_returns_bytes(monkeypatch):
    class _FakeResponse:
        status = 200
        def read(self):
            return b"BEGIN:VCALENDAR\nEND:VCALENDAR\n"
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    def _fake_urlopen(req, timeout):
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    result = fetcher.fetch_feed("https://x.example/feed")
    assert result.startswith(b"BEGIN:VCALENDAR")


def test_fetch_feed_raises_on_non_200(monkeypatch):
    class _FakeResponse:
        status = 401
        def read(self):
            return b""
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda r, timeout: _FakeResponse())
    with pytest.raises(fetcher.FeedFetchError) as e:
        fetcher.fetch_feed("https://x.example/feed")
    assert "401" in str(e.value)


def test_fetch_feed_translates_urlerror(monkeypatch):
    def _raise(req, timeout):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    with pytest.raises(fetcher.FeedFetchError) as e:
        fetcher.fetch_feed("https://x.example/feed")
    assert "Netzwerk-Fehler" in str(e.value)


def test_fetch_feed_translates_timeout(monkeypatch):
    """Real urllib timeouts arrive wrapped: URLError(reason=TimeoutError(...))."""
    import socket
    def _raise(req, timeout):
        raise urllib.error.URLError(reason=socket.timeout("timed out"))

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    with pytest.raises(fetcher.FeedFetchError) as e:
        fetcher.fetch_feed("https://x.example/feed")
    assert "Timeout" in str(e.value)


def test_fetch_feed_translates_bare_timeout_error(monkeypatch):
    """Defensive: bare TimeoutError (rare SSL-layer leak) also produces timeout msg."""
    def _raise(req, timeout):
        raise TimeoutError()

    monkeypatch.setattr("urllib.request.urlopen", _raise)
    with pytest.raises(fetcher.FeedFetchError) as e:
        fetcher.fetch_feed("https://x.example/feed")
    assert "Timeout" in str(e.value)

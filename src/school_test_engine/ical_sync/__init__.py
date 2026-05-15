"""iCal-Sync domain package — public API."""
from .fetcher import FeedFetchError
from .service import SyncResult, sync_feed

__all__ = ["FeedFetchError", "SyncResult", "sync_feed"]

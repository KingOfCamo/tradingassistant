"""Typed exceptions for the data feed layer."""


class DataFeedError(Exception):
    """Raised when a data feed call fails and no fallback is available."""


class CreditExhaustedError(DataFeedError):
    """Raised when a provider's daily quota is exhausted."""


class FeedUnavailableError(DataFeedError):
    """Raised when a feed is misconfigured or cannot be reached."""

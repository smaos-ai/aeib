"""Error taxonomy for transport calls."""


class TransportError(Exception):
    """Base class for transport failures."""


class TransientError(TransportError):
    """A failure that may succeed on retry (timeouts, 503)."""


class PermanentError(TransportError):
    """A failure that will not succeed on retry (400, 404)."""

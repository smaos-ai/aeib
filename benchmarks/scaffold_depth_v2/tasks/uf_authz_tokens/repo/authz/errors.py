"""Exceptions raised by token handling."""


class InvalidToken(Exception):
    """The token must not be trusted."""


class ExpiredToken(InvalidToken):
    """The token was valid but its 'exp' time has passed."""


class Forbidden(Exception):
    """The token is valid but lacks the required scope."""

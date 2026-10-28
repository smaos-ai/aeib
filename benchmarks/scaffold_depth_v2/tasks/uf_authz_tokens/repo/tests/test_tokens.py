import pytest

from authz.errors import ExpiredToken
from authz.policy import authorise
from authz.signing import sign
from authz.verify import verify_token

KEY = b"k" * 32


def test_token_shape():
    assert sign({"sub": "u1", "exp": 100}, KEY).count(".") == 2


def test_roundtrip():
    claims = {"sub": "u1", "exp": 2_000, "scope": "read"}
    assert verify_token(sign(claims, KEY), KEY, now=1_000) == claims


def test_expired():
    with pytest.raises(ExpiredToken):
        verify_token(sign({"sub": "u1", "exp": 10}, KEY), KEY, now=1_000)


def test_authorise_scope():
    tok = sign({"sub": "u1", "exp": 2_000, "scope": "read write"}, KEY)
    assert authorise(tok, KEY, 1_000, "write")["sub"] == "u1"

import pytest

from authz.keyring import KeyRing


def test_rotation_uses_newest_key():
    ring = KeyRing()
    ring.add("k1", b"a" * 16)
    ring.add("k2", b"b" * 16)
    assert ring.current() == b"b" * 16
    ring.retire("k2")
    assert ring.current() == b"a" * 16
    with pytest.raises(ValueError):
        ring.add("k3", b"short")

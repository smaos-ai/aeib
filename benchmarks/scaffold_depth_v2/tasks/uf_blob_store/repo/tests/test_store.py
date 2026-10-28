from blobs.paths import name_parts, normalize_name
from blobs.store import BlobStore


def test_normalize():
    assert normalize_name(" a\\b.txt ") == "a/b.txt"
    assert name_parts("a/b/c") == ("a", "b", "c")


def test_put_get_roundtrip(tmp_path):
    store = BlobStore(tmp_path / "root")
    path = store.put("reports/2026/q1.csv", b"x,y\n")
    assert path.read_bytes() == b"x,y\n"
    assert store.get("reports/2026/q1.csv") == b"x,y\n"
    assert store.names() == ["reports/2026/q1.csv"]

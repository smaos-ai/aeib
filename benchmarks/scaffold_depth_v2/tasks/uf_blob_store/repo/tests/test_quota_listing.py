import pytest

from blobs.index import Index
from blobs.listing import total_size, tree, with_prefix
from blobs.quota import Quota, QuotaExceeded


def test_quota_counts_replacements(tmp_path):
    idx = Index(tmp_path)
    idx.add("a.bin", 60)
    q = Quota(idx, 100)
    q.check("a.bin", 90)
    with pytest.raises(QuotaExceeded):
        q.check("b.bin", 50)
    assert q.remaining() == 40


def test_listing(tmp_path):
    idx = Index(tmp_path)
    idx.add("r/1.csv", 3)
    idx.add("r/2.csv", 4)
    idx.add("top.txt", 1)
    assert with_prefix(idx, "r/") == ["r/1.csv", "r/2.csv"]
    assert tree(idx) == {"r": ["r/1.csv", "r/2.csv"], "": ["top.txt"]}
    assert total_size(idx, "r/") == 7

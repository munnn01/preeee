"""V4 source ranking must be deterministic and independent of labels."""
from __future__ import annotations

import hashlib

from ops.prepare_v4_holdout import SALT, rank_source_ids


def test_rank_source_ids_uses_locked_salt_and_exclusions():
    ids = ["AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC"]
    expected = sorted(ids[1:], key=lambda key: (
        hashlib.sha256(f"{SALT}\0{key}".encode()).hexdigest(), key))
    assert rank_source_ids(ids + [ids[0]], {ids[0]}) == expected

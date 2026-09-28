"""The next confirmation sample must exclude both prior holdouts."""
import hashlib

from ops.prepare_v6_holdout import SALT, rank_source_ids


def test_v6_rank_excludes_v2_and_v4_ids_before_hashing():
    official = ["AAAAAAAAAAA", "BBBBBBBBBBB", "CCCCCCCCCCC",
                "DDDDDDDDDDD"]
    exclusions = {official[0], official[1]}
    expected = sorted(official[2:], key=lambda key: (
        hashlib.sha256(f"{SALT}\0{key}".encode()).hexdigest(), key))
    assert SALT == "v6-h265-holdout-20260928"
    assert rank_source_ids(official + [official[2]], exclusions) == expected

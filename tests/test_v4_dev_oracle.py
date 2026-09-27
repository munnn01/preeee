"""The DEV oracle is an explicitly label-aware optimistic reference."""

from ops.v4_dev_oracle import oracle_choice


def test_oracle_preserves_each_correct_anchor_prediction():
    measurement = {"candidates": [
        {"name": "identity128", "bpp": 1.0, "correct": True, "cross_correct": True},
        {"name": "area112", "bpp": .8, "correct": True, "cross_correct": True},
        {"name": "area96", "bpp": .6, "correct": True, "cross_correct": False},
    ]}
    assert oracle_choice(measurement) == (1, True, True)


def test_oracle_can_improve_a_wrong_anchor_without_harming_the_other():
    measurement = {"candidates": [
        {"name": "identity128", "bpp": 1.0, "correct": False, "cross_correct": True},
        {"name": "area112", "bpp": .8, "correct": True, "cross_correct": True},
        {"name": "area96", "bpp": .6, "correct": True, "cross_correct": False},
    ]}
    assert oracle_choice(measurement) == (1, True, True)


def test_nonidentity_can_be_feasible_without_saving_rate():
    measurement = {"candidates": [
        {"name": "identity128", "bpp": 1.0, "correct": True, "cross_correct": True},
        {"name": "area112", "bpp": 1.1, "correct": True, "cross_correct": True},
    ]}
    assert oracle_choice(measurement) == (0, True, False)

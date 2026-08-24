#!/usr/bin/env python3
"""Regression checks for fixed-horizon expert-rank normalization."""

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("build_composite_board.py")
SPEC = importlib.util.spec_from_file_location("build_composite_board", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def main():
    score_100_from_150 = MODULE.fixed_rank_score(100, horizon=200)
    score_100_from_400 = MODULE.fixed_rank_score(100, horizon=200)
    assert score_100_from_150 == score_100_from_400 == 0.505
    assert MODULE.fixed_rank_score(1, horizon=200) == 1.0
    assert MODULE.fixed_rank_score(200, horizon=200) == 0.005
    assert MODULE.fixed_rank_score(201, horizon=200) == 0.0
    assert MODULE.fixed_rank_score(400, horizon=200) == 0.0
    print("Fixed-horizon composite-rank normalization: PASS")


if __name__ == "__main__":
    main()

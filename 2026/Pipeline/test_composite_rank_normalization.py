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

    supplemental_only = MODULE.combine_quality_scores([], [(0.05, 0.805)])
    assert supplemental_only["score"] == 0
    assert supplemental_only["source_count"] == 0
    assert supplemental_only["supplemental_source_count"] == 1
    assert supplemental_only["supplemental_applied_count"] == 0
    assert supplemental_only["supplemental_only"] is True

    primary_only = MODULE.combine_quality_scores([(0.4, 0.505)], [])
    assert primary_only["score"] == 0.505
    assert primary_only["source_count"] == 1

    primary_plus_supplemental = MODULE.combine_quality_scores(
        [(0.4, 0.505)], [(0.05, 0.805)]
    )
    expected = ((0.4 * 0.505) + (0.05 * 0.805)) / 0.45
    assert abs(primary_plus_supplemental["score"] - expected) < 1e-12
    assert primary_plus_supplemental["source_count"] == 2
    assert primary_plus_supplemental["supplemental_applied_count"] == 1
    print("Composite rank normalization and source-role gating: PASS")


if __name__ == "__main__":
    main()

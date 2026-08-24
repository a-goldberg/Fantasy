#!/usr/bin/env python3
"""Regression tests for Ourlads player-name and identifier parsing."""

from ourlads_names import parse_ourlads_name


CASES = {
    "RODGERS, AARON CC/NYJ": ("Aaron Rodgers", "CC/NYJ"),
    "Murray, Kyler CC/Arz": ("Kyler Murray", "CC/Arz"),
    "Harrison Jr., Marvin 24/1": ("Marvin Harrison Jr.", "24/1"),
    "BOURNE, KENDRICK U/SF": ("Kendrick Bourne", "U/SF"),
    "Smith-Marsette, Ihmir SF26": ("Ihmir Smith-Marsette", "SF26"),
    "Vakalahi, Laekin SF26*": ("Laekin Vakalahi", "SF26*"),
    "Jackson, Lamar 18/1": ("Lamar Jackson", "18/1"),
}

for raw_name, expected in CASES.items():
    parsed = parse_ourlads_name(raw_name)
    actual = (parsed["player"], parsed["identifier"])
    assert actual == expected, f"{raw_name!r}: expected {expected!r}, got {actual!r}"

print("Ourlads name-normalization scenarios: PASS")

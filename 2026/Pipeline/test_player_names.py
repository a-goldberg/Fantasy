#!/usr/bin/env python3
"""Regression checks for explicit player identity aliases."""

from player_names import normalize_player_name


def main():
    assert normalize_player_name("Kenny Gainwell") == "kennethgainwell"
    assert normalize_player_name("Kenneth Gainwell") == "kennethgainwell"
    assert normalize_player_name("Kyle Pitts Sr.") == "kylepitts"
    assert normalize_player_name("Amon-Ra St. Brown") == "amonrastbrown"
    print("Player-name alias normalization: PASS")


if __name__ == "__main__":
    main()

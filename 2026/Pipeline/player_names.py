#!/usr/bin/env python3
"""Canonical fantasy-player name keys and explicit cross-source aliases."""

from __future__ import annotations

import re
import unicodedata


PLAYER_NAME_ALIASES = {
    "kennygainwell": "kennethgainwell",
}


def normalize_player_name(value: str) -> str:
    """Return a stable identity key without guessing at unlisted nicknames."""
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", text)
    key = re.sub(r"[^a-z0-9]+", "", text)
    return PLAYER_NAME_ALIASES.get(key, key)

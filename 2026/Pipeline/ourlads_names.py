#!/usr/bin/env python3
"""Parse Ourlads display names without discarding its trailing roster identifier."""

from __future__ import annotations

import re


OURLADS_IDENTIFIER = re.compile(
    r"^(?:\d{2}/\d{1,2}|[A-Z]{1,3}/[A-Z]{2,3}|(?:CF|SF)\d{2})\*?$",
    re.IGNORECASE,
)


def parse_ourlads_name(raw_name: str) -> dict[str, str | None]:
    """Return a clean first-last name and preserve Ourlads' final metadata token."""
    value = " ".join(str(raw_name or "").split()).strip()
    identifier = None
    if value:
        candidate = value.rsplit(" ", 1)[-1]
        if OURLADS_IDENTIFIER.fullmatch(candidate):
            identifier = candidate
            value = value[: -(len(candidate))].rstrip()
    if "," in value:
        surname, given = (part.strip() for part in value.split(",", 1))
        value = f"{given} {surname}"
    return {"player": value.title(), "identifier": identifier}


def ourlads_player_name(raw_name: str) -> str:
    return str(parse_ourlads_name(raw_name)["player"] or "")

"""Academic terms (spec 05). Pure logic: no clock, no I/O.

A term code is the year plus a season: ``2026FA``, ``2027SP``, ``2027SU`` (same as ``data/*/terms.csv``).
Within a calendar year the order is Spring, Summer, Fall.
"""
from __future__ import annotations

from dataclasses import dataclass

SEASONS = ("SP", "SU", "FA")  # calendar order inside one year
SEASON_NAMES = {"SP": "Spring", "SU": "Summer", "FA": "Fall"}


@dataclass(frozen=True, order=True)
class Term:
    year: int
    index: int  # position in SEASONS, so dataclass ordering == calendar ordering

    @property
    def season(self) -> str:
        return SEASONS[self.index]

    @property
    def code(self) -> str:
        return f"{self.year}{self.season}"

    @property
    def name(self) -> str:
        return f"{SEASON_NAMES[self.season]} {self.year}"


@dataclass(frozen=True)
class Offering:
    """When a course usually runs: a season, every year or only even/odd calendar years."""
    season: str  # SP / SU / FA
    years: str = "every"  # every / even / odd


def parse_term(code: str) -> Term:
    code = code.strip().upper()
    year, season = code[:4], code[4:]
    if not year.isdigit() or season not in SEASONS:
        raise ValueError(f"term code must look like 2027SP, got {code!r}")
    return Term(int(year), SEASONS.index(season))


def next_term(t: Term, include_summer: bool = False) -> Term:
    """The next term a student would enroll in. Summer is skipped unless asked for."""
    if t.season == "FA":
        return Term(t.year + 1, SEASONS.index("SP"))
    if t.season == "SP":
        return Term(t.year, SEASONS.index("SU" if include_summer else "FA"))
    return Term(t.year, SEASONS.index("FA"))


def is_offered(offerings: tuple[Offering, ...], t: Term) -> bool:
    """True if any offering runs in term ``t`` (season matches and the year has the right parity)."""
    for o in offerings:
        if o.season != t.season:
            continue
        if o.years == "every" or (o.years == "even") == (t.year % 2 == 0):
            return True
    return False


def describe_offerings(offerings: tuple[Offering, ...]) -> str:
    """Human text like 'Spring only' or 'Fall of odd years'."""
    if not offerings:
        return "no regular term"
    parts = []
    for o in sorted(offerings, key=lambda o: SEASONS.index(o.season)):
        part = SEASON_NAMES[o.season]
        if o.years != "every":
            part += f" of {o.years} years"
        parts.append(part)
    return parts[0] + " only" if len(parts) == 1 else " and ".join(parts)

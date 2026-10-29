"""Letter grades (spec 05). Pure logic.

``None`` means the course is still in progress. Transfer credit usually arrives without a letter
grade (``TR``); spec 04 says it counts as passing at the SIS minimum, which is a C.
"""
from __future__ import annotations

GRADES = ("A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F")
PASSING = "D-"
# Non-letter grades that count as a pass, and the letter they are treated as.
EQUIVALENT = {"TR": "C", "P": "C", "CR": "C"}


def normalize(grade: str | None) -> str | None:
    if grade is None:
        return None
    g = str(grade).strip().upper()
    return EQUIVALENT.get(g, g) if g else None


def meets(grade: str | None, minimum: str | None) -> bool:
    """Does a finished course's grade meet ``minimum`` (default: any passing grade)?

    In-progress (``None``) and unknown grades (``W``, ``I``) never meet a minimum here; callers decide
    whether in-progress work counts as "expected to pass".
    """
    g = normalize(grade)
    floor = normalize(minimum) or PASSING
    if g not in GRADES or floor not in GRADES:
        return False
    return GRADES.index(g) <= GRADES.index(floor)

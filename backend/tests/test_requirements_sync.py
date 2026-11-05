"""The Vercel function installs the root requirements.txt, not backend/requirements.txt.

A package missing from the root file only shows up as a crash on the deployed site, so check here.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER_ONLY = {"gunicorn"}  # runs the app locally; Vercel doesn't need it


def _names(path: Path) -> set[str]:
    lines = (line.split("#")[0].strip() for line in path.read_text().splitlines())
    return {re.split(r"[=<>\[ ]", line)[0].lower() for line in lines if line}


def test_vercel_requirements_cover_the_backend():
    missing = _names(ROOT / "backend" / "requirements.txt") - _names(ROOT / "requirements.txt") - SERVER_ONLY
    assert not missing, f"add to the root requirements.txt for Vercel: {sorted(missing)}"

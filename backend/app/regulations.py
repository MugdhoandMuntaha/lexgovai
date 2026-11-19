"""Loads the before/after regulation texts and computes a deterministic line diff and version hash."""

from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path

REGULATION_ID = "nbr-vat-sro-4.2"
BEFORE_FILE = "regulation_before.txt"
AFTER_FILE = "regulation_after.txt"


@dataclass(frozen=True)
class RegulationPair:
    regulation_id: str
    before_text: str
    after_text: str
    before_title: str
    after_title: str
    version_hash: str
    diff: list[dict]

    @property
    def changed_lines_text(self) -> str:
        """Compact unified-style diff for prompts: '-' removed lines, '+' added lines."""
        prefix = {"removed": "- ", "added": "+ "}
        return "\n".join(prefix[d["op"]] + d["text"] for d in self.diff if d["op"] != "equal")


def _first_line(text: str) -> str:
    return next((line.strip().rstrip(":") for line in text.splitlines() if line.strip()), "Regulation")


def line_diff(before: str, after: str) -> list[dict]:
    a, b = before.splitlines(), after.splitlines()
    out: list[dict] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            out.extend({"op": "equal", "text": line} for line in a[i1:i2])
            continue
        out.extend({"op": "removed", "text": line} for line in a[i1:i2])
        out.extend({"op": "added", "text": line} for line in b[j1:j2])
    return out


def make_regulation_pair(
    regulation_id: str,
    before_text: str,
    after_text: str,
    before_title: str | None = None,
    after_title: str | None = None,
) -> RegulationPair:
    before = before_text.strip()
    after = after_text.strip()
    digest = hashlib.sha256(f"{before}\n---\n{after}".encode("utf-8")).hexdigest()
    return RegulationPair(
        regulation_id=regulation_id,
        before_text=before,
        after_text=after,
        before_title=before_title or _first_line(before),
        after_title=after_title or _first_line(after),
        version_hash=digest[:16],
        diff=line_diff(before, after),
    )


def load_regulation_pair(regulation_dir: Path) -> RegulationPair:
    before = (regulation_dir / BEFORE_FILE).read_text(encoding="utf-8").strip()
    after = (regulation_dir / AFTER_FILE).read_text(encoding="utf-8").strip()
    return make_regulation_pair(
        regulation_id=REGULATION_ID,
        before_text=before,
        after_text=after,
    )


def load_regulation_pair_by_id(
    db: Any = None,
    regulation_id: str | None = None,
    regulation_dir: Path | None = None,
) -> RegulationPair:
    if db is not None and regulation_id:
        try:
            db_pair = db.get_latest_published_pair(regulation_id)
            if db_pair:
                before_row, after_row = db_pair
                return make_regulation_pair(
                    regulation_id=regulation_id,
                    before_text=before_row["text"],
                    after_text=after_row["text"],
                    before_title=before_row.get("version_label"),
                    after_title=after_row.get("version_label"),
                )
        except Exception:
            pass
    if regulation_dir is not None:
        return load_regulation_pair(regulation_dir)
    from .config import get_settings
    return load_regulation_pair(get_settings().regulation_dir)



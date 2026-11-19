"""ChangeAgent: Detects statutory amendments when content hash changes, creates versions, diffs, and alerts watchers."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any

from app.db import Database


@dataclass(frozen=True)
class SectionDiffItem:
    number_label: str
    heading: str | None
    change_type: str  # 'added', 'removed', 'modified', 'unchanged'
    old_text: str | None
    new_text: str | None


def compute_section_diffs(
    old_sections: list[dict[str, Any]],
    new_sections: list[dict[str, Any]],
) -> list[SectionDiffItem]:
    """Computes section-by-section diff between two versions of a law."""
    old_by_label = {s["number_label"].lower(): s for s in old_sections}
    new_by_label = {s["number_label"].lower(): s for s in new_sections}

    diffs: list[SectionDiffItem] = []
    seen_labels: set[str] = set()

    for n_sec in new_sections:
        label_key = n_sec["number_label"].lower()
        seen_labels.add(label_key)
        old_match = old_by_label.get(label_key)

        if not old_match:
            diffs.append(
                SectionDiffItem(
                    number_label=n_sec["number_label"],
                    heading=n_sec.get("heading"),
                    change_type="added",
                    old_text=None,
                    new_text=n_sec["text"],
                )
            )
        elif old_match["text"].strip() != n_sec["text"].strip():
            diffs.append(
                SectionDiffItem(
                    number_label=n_sec["number_label"],
                    heading=n_sec.get("heading") or old_match.get("heading"),
                    change_type="modified",
                    old_text=old_match["text"],
                    new_text=n_sec["text"],
                )
            )
        else:
            diffs.append(
                SectionDiffItem(
                    number_label=n_sec["number_label"],
                    heading=n_sec.get("heading"),
                    change_type="unchanged",
                    old_text=old_match["text"],
                    new_text=n_sec["text"],
                )
            )

    for o_sec in old_sections:
        label_key = o_sec["number_label"].lower()
        if label_key not in seen_labels:
            diffs.append(
                SectionDiffItem(
                    number_label=o_sec["number_label"],
                    heading=o_sec.get("heading"),
                    change_type="removed",
                    old_text=o_sec["text"],
                    new_text=None,
                )
            )

    return diffs


class ChangeAgent:
    """Agent that handles version increments and watcher notifications upon statutory changes."""

    def __init__(self, db: Database):
        self.db = db

    def process_change(
        self,
        law_id: str,
        new_version_id: str,
        old_version_id: str | None = None,
    ) -> list[str]:
        """Notifies all workspace members watching this law about the newly published amendment."""
        law = self.db.get_law(law_id)
        if not law:
            return []

        watching_workspaces = self.db.list_workspace_ids_watching_law(law_id)
        notified_users: list[str] = []

        title = f"Statutory Amendment: {law['canonical_title_en']}"
        body = f"A new version of {law['canonical_title_en']} has been published to the Bangladesh Legal Library."
        link = f"/laws/{law_id}"

        for ws_id in watching_workspaces:
            # Dispatch through Alert Center
            try:
                from app.alerts.router import AlertRouter
                router = AlertRouter(db=self.db)
                router.dispatch_event(
                    workspace_id=ws_id,
                    event_type="law_amendment_watched",
                    entity_type="law",
                    entity_id=law_id,
                    payload={
                        "law_title": law["canonical_title_en"],
                        "summary": body,
                        "link": link,
                        "law_id": law_id,
                        "new_version_id": new_version_id,
                    },
                    version_hash=new_version_id,
                )
            except Exception:
                pass

            members = self.db.list_workspace_members(ws_id)
            for m in members:
                uid = m["user_id"]
                dedupe_key = f"law_alert:{law_id}:{new_version_id}:{uid}"
                self.db.create_notification(
                    workspace_id=ws_id,
                    user_id=uid,
                    title=title,
                    body=body,
                    link=link,
                    channel="in_app",
                    dedupe_key=dedupe_key,
                )
                notified_users.append(uid)

        return notified_users


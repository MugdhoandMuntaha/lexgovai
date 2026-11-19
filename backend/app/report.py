"""Markdown export of an action plan."""

from __future__ import annotations


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" for line in text.splitlines() or [""])


def render_markdown(plan: dict, level: str = "advanced") -> str:
    lines = [
        f"# Compliance Action Plan: {plan['regulation']}",
        "",
        f"- **Organization:** {plan['company']}",
        f"- **SOP document:** {plan['document_name']}",
        f"- **Impact risk score:** {plan['impact_score']}/100",
        f"- **Urgency:** {plan['urgency'].upper()}",
        f"- **Regulation version hash:** `{plan['regulation_version_hash']}`",
        f"- **Generated:** {plan['created_at']} (model: {plan['model']})",
        "",
        "## Regulatory change summary",
        "",
        plan["change_summary"],
        "",
        "## 1. Findings",
        "",
    ]
    if not plan["findings"]:
        lines += ["No compliance gaps were identified.", ""]
    for i, f in enumerate(plan["findings"], 1):
        status = "NEEDS HUMAN REVIEW" if f.get("flagged_for_review") else "citation verified"
        c = f["citation"]
        lines += [
            f"### {i}. {f['issue']}",
            "",
            f"- **Type:** {f['issue_type']}  |  **Severity:** {f['severity']}  |  "
            f"**Confidence:** {round(f['confidence'] * 100)}% ({status})",
            "",
            f["explanation"],
            "",
            f"**Citation:** {c['source']} ({c['section']})",
            "",
            _quote(c["text_snippet"]),
            "",
        ]

    # Basic tier stops after findings and score summary
    if level == "basic":
        lines += ["", "---", "", f"*{plan['disclaimer']}*", ""]
        return "\n".join(lines)

    lines += ["## 2. Policy draft amendments", ""]
    lines += [f"{i}. {d}" for i, d in enumerate(plan.get("policy_draft", []), 1)] or ["None required."]

    if level in ("on", "advanced"):
        lines += ["", "## 3. Technical and operational fixes", ""]
        lines += [f"- [ ] {fix}" for fix in plan.get("technical_fixes", [])] or ["None required."]

    lines += ["", "---", "", f"*{plan['disclaimer']}*", ""]
    return "\n".join(lines)


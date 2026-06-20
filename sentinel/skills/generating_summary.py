"""
sentinel/skills/generating_summary.py
──────────────────────────────────────────────────────────────────────────────
SKILL: generating-summary  (Skill 4 of 4)

PURPOSE:
    Produce a clean, scannable, ~30-second clinician handoff document.
    The summary captures everything gathered during intake and the triage
    outcome, formatted for fast clinical review.

TRIGGER:
    Called after the triage tool (classify_triage) assigns a label -
    i.e., only on the non-red-flag path. Never called after escalation.

WHEN NOT TO USE:
    - To include any advice, diagnosis, or treatment suggestion.
    - To include any content NOT gathered during the interview.
    - After a red-flag escalation (the HITL gate handles that path).

DESIGN INTENT:
    The summary is a structured handoff to a human clinician, not a report
    for the patient. It contains only facts the patient stated, plus the
    AI-assigned triage label with its rationale. The disclaimer at the
    bottom is non-negotiable: it must appear on every summary to make clear
    that this is an AI-assisted tool, not a clinical decision.

    Keeping summary generation as a separate tool (rather than letting the
    LLM free-form it) ensures consistent structure - a clinician scanning
    10 summaries per day sees the same layout every time.
──────────────────────────────────────────────────────────────────────────────
"""

import datetime


def generating_summary(
    chief_complaint: str,
    duration: str,
    severity: int,
    triage_label: str,
    triage_rationale: str,
    history: str = "None reported",
    red_flag_status: str = "CLEAR",
    prior_visit_note: str = "First visit",
) -> str:
    """
    Generate the structured clinician pre-visit handoff summary.

    Produces a fixed-format, scannable document that a clinician can read
    in approximately 30 seconds. Fields are drawn exclusively from patient-
    reported intake data and the rule-based triage result.

    IMPORTANT: This function never adds advice, diagnosis, or interpretation.
    The only inference it adds is the triage label produced by classify_triage.

    Args:
        chief_complaint:  Patient's primary complaint in their own words.
        duration:         How long the symptom has been present.
        severity:         Self-reported severity 1–10.
        triage_label:     One of: "self-care" | "see-a-doctor" | "urgent"
        triage_rationale: Plain-English reason the label was assigned.
        history:          Relevant history / medications (or "None reported").
        red_flag_status:  Result of the red-flag screen ("CLEAR" on this path).
        prior_visit_note: Note from a prior Sentinel session, if any.

    Returns:
        A formatted multi-line string - the clinician handoff document.
    """
    # ── Timestamp ────────────────────────────────────────────────────────────
    # UTC timestamp makes the record auditable across time zones.
    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # ── Format the triage label for display ─────────────────────────────────
    # Map internal labels to display strings with visual weight
    label_display = {
        "self-care":    "✅  SELF-CARE",
        "see-a-doctor": "⚠️  SEE A DOCTOR",
        "urgent":       "🔴  URGENT",
    }.get(triage_label.lower(), f"❓  {triage_label.upper()}")

    # ── Build the summary document ──────────────────────────────────────────
    # Fixed-width separators create scannable visual boundaries.
    lines = [
        "═" * 62,
        "  SENTINEL - PRE-VISIT SUMMARY",
        f"  Generated : {generated_at}",
        "═" * 62,
        "",
        f"  Chief Complaint  : {chief_complaint}",
        f"  Duration         : {duration}",
        f"  Severity (1–10)  : {severity}/10",
        f"  Relevant History : {history}",
        "",
        "─" * 62,
        f"  Red-Flag Screen  : {red_flag_status}",
        f"  Triage Label     : {label_display}",
        f"  Rationale        : {triage_rationale}",
        "",
        "─" * 62,
        f"  Prior Visit Note : {prior_visit_note}",
        "",
        "─" * 62,
        "  ⚠  DISCLAIMER",
        "  This summary was produced by an AI tool (Sentinel) for",
        "  informational and workflow purposes only. It is NOT a",
        "  diagnosis and does NOT constitute medical advice.",
        "  For use by a licensed clinician only.",
        "═" * 62,
    ]

    return "\n".join(lines)

"""
sentinel/skills/conducting_intake.py
──────────────────────────────────────────────────────────────────────────────
SKILL: conducting-intake  (Skill 1 of 4)

PURPOSE:
    Record and structure the patient's pre-visit information that the Sentinel
    agent has gathered through conversation. This tool does NOT conduct the
    conversation itself - the LLM does that. This tool is called once the agent
    has collected all required fields, to commit them into a structured intake
    record stored in session state.

TRIGGER:
    Called by the agent once it has gathered: chief complaint, duration,
    severity (1–10), and optionally relevant history.

WHEN NOT TO USE:
    - To give advice, reassurance, or diagnosis of any kind.
    - To interpret or evaluate the clinical significance of the complaint.
    - Before red-flag screening has passed on all patient messages.

DESIGN INTENT:
    Separates data-collection (the LLM's job) from data-structuring (this
    tool's job). The structured record is the canonical source of truth for
    subsequent steps (triage, summary). Storing it in session state means
    later tools (generating_summary) can access it without the agent having
    to re-state everything in the prompt.
──────────────────────────────────────────────────────────────────────────────
"""

from typing import Any
from google.adk.agents.context import Context


def conducting_intake(
    tool_context: Context,
    chief_complaint: str,
    duration: str,
    severity: int,
    history: str = "",
) -> dict[str, Any]:
    """
    Record the structured intake data for a patient pre-visit.

    This tool is the commitment point: once called, the intake phase is
    considered complete and the session moves to triage.

    Args:
        chief_complaint: The patient's primary complaint in their own words
                         (e.g. "sore throat that started two days ago").
        duration:        How long the symptom has been present
                         (e.g. "2 days", "about a week", "since yesterday").
        severity:        Self-reported severity on a 1–10 scale where
                         1 = barely noticeable, 10 = worst imaginable.
        history:         Relevant medical history, current medications, known
                         allergies, or prior episodes of this complaint.
                         Empty string if none reported.

    Returns:
        A dict confirming the recorded intake fields and signalling that
        intake is complete. The agent uses this confirmation to proceed to
        the triage step.
    """
    # ── Input validation ────────────────────────────────────────────────────
    # Clamp severity to 1–10 to guard against model hallucinating out-of-range
    # values (e.g., "0" or "11"). This is a data-integrity control.
    severity_clamped = max(1, min(10, int(severity)))

    # Strip whitespace from text fields - patient input can be messy
    intake_record = {
        "status": "intake_complete",
        "chief_complaint": chief_complaint.strip(),
        "duration": duration.strip(),
        "severity": severity_clamped,
        "history": history.strip() if history else "None reported",
    }
    
    # Save complaint to cross-session memory for returning patients (Scenario 3)
    from sentinel.memory import session_service
    app = tool_context.session.app_name
    uid = tool_context.session.user_id
    if app not in session_service.user_state:
        session_service.user_state[app] = {}
    if uid not in session_service.user_state[app]:
        session_service.user_state[app][uid] = {}
    
    # Store the most recent complaint for next time
    session_service.user_state[app][uid]["past_complaint"] = intake_record["chief_complaint"]

    return intake_record

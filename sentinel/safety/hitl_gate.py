"""
sentinel/safety/hitl_gate.py
──────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Human-in-the-Loop (HITL) gate - Sentinel's escalation endpoint.

    When a red-flag symptom is detected (by either the screening skill or the
    before_tool_callback), control is routed here. This module:
      1. Produces the calm, clear escalation message the patient sees.
      2. Marks the session outcome as ESCALATED (not triaged by AI).
      3. The before_tool_callback (red_flag_callback.py) sets the ADK 2.0
         native interrupt signal: tool_context.actions.escalate = True.
         This is the framework-level HITL pause that signals the runner to
         pause agent flow for human review.

STATUS (Phase 2): ✅ COMPLETE
    - Escalation message: implemented and tested.
    - Session state flags: set by screening_red_flags (Layer 1) and callback.
    - ADK 2.0 native HITL: tool_context.actions.escalate = True wired in
      red_flag_callback.py (Layer 2).

DESIGN INTENT (spec §5.3):
    - Use ADK 2.0's native HITL pause - do NOT catch BaseException, which
      would trap the ADK interrupt signal and break the mechanism.
    - Output is calm and non-diagnostic: Sentinel flags the case, recommends
      seeking care promptly, and explicitly does NOT diagnose or advise.
    - Outcome is unambiguous: "ESCALATED TO HUMAN - not triaged by AI"

WHY escalate IS SET IN THE CALLBACK, NOT THE SKILL:
    Setting actions.escalate = True ends the current agent turn. If set in
    the screening skill, the agent would not get to output the escalation
    message to the patient. The correct sequence is:
      1. Screening skill detects red flag → writes state, returns red_flag dict.
      2. Agent reads result, follows system instruction → outputs ESCALATION_MESSAGE.
      3. If agent ignores instruction and calls classify_triage → callback fires,
         sets escalate = True, blocks tool, returns escalation dict.
    The escalate signal is the defense-in-depth layer, not the primary path.
──────────────────────────────────────────────────────────────────────────────
"""

import datetime

# ── Escalation message template ──────────────────────────────────────────────
# This exact wording satisfies the spec requirement (§5.3):
#   "a clear, calm message … recommends seeking care promptly …
#    explicitly does NOT diagnose or advise …
#    Mark the outcome clearly: ESCALATED TO HUMAN - not triaged by AI"
#
# The message is a module-level constant so it can be imported by the
# before_tool_callback without creating a circular dependency.

ESCALATION_MESSAGE: str = (
    "I need to flag something important.\n\n"
    "Based on what you've described, I'm pausing this intake and connecting "
    "you to a human clinician right away. Please seek care promptly - "
    "go to your nearest emergency department or call emergency services "
    "if you feel your symptoms are severe.\n\n"
    "I am not able to advise you on what your symptoms mean or what to do "
    "medically - that is for a qualified clinician to assess.\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "  STATUS: ESCALATED TO HUMAN - not triaged by AI\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
)

# ── Unique status string used as a test-checkable sentinel value ─────────────
# Tests can assert this exact string appears in Sentinel's output.
ESCALATION_STATUS: str = "ESCALATED TO HUMAN - not triaged by AI"


def build_escalation_result(matched_term: str | None = None) -> dict:
    """
    Build the structured escalation result dict returned by the safety callback.

    This dict is returned from before_tool_callback to replace the triage
    tool's output, ensuring no triage label or advice is ever produced.

    The before_tool_callback also sets tool_context.actions.escalate = True
    (ADK 2.0 native HITL signal) before returning this dict.

    Args:
        matched_term: The red-flag term that triggered escalation (for logging).

    Returns:
        dict with escalation status, timestamp, and the patient-facing message.
        The agent will see this as the triage tool's "result" and should relay
        the message to the patient verbatim.
    """
    return {
        "status": ESCALATION_STATUS,
        "triage_label": None,           # Explicitly None - no label is produced
        "advice": None,                 # Explicitly None - no advice is produced
        "matched_red_flag": matched_term,
        "escalated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "message_to_patient": ESCALATION_MESSAGE,
    }

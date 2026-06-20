"""
sentinel/skills/screening_red_flags.py
──────────────────────────────────────────────────────────────────────────────
SKILL: screening-red-flags  (Skill 3 of 4) ← SAFETY-CRITICAL

PURPOSE:
    Screen every patient message for danger ("red-flag") symptoms. This is
    the agent-visible layer of Sentinel's two-layer safety system:

        Layer 1 - THIS SKILL (agent-visible):
            Called by the LLM agent after every patient message.
            Returns a structured signal the agent acts on.
            Also writes to session state so Layer 2 can verify independently.

        Layer 2 - before_tool_callback (hard chokepoint):
            Runs deterministically before triage, outside the model's judgment.
            Cannot be bypassed by the model or by adversarial patient input.
            Reads the state flags set here.
            Sets tool_context.actions.escalate = True (ADK 2.0 native HITL).
            (See sentinel/safety/red_flag_callback.py)

TRIGGER:
    Called by the agent after EVERY patient response during intake - no
    exceptions. This is enforced in the system instruction.

WHEN NOT TO USE:
    - To diagnose what the red-flag might indicate.
    - To reassure the patient ("that's probably fine").
    - To continue normal intake flow after a red flag is detected.
    On a match, the agent MUST halt and escalate - nothing else.

DESIGN INTENT:
    Deterministic keyword matching (not ML) makes the screen auditable and
    impossible for patient input to manipulate. A safety screen that says
    "I don't think that counts as a red flag" is not a safety screen.

STATE WRITES (Phase 2):
    "latest_patient_input" - always written, for Layer 2's independent scan.
    "red_flag_detected"    - True on match, for Layer 2's fast-path check.
    "red_flag_term"        - the matched term, for audit logging.
──────────────────────────────────────────────────────────────────────────────
"""

from google.adk.tools.tool_context import ToolContext

from sentinel.data.red_flags import RED_FLAG_TERMS


def screening_red_flags(patient_text: str, tool_context: ToolContext) -> dict:
    """
    Screen the patient's latest message for danger symptoms.

    Performs a case-insensitive substring match against the RED_FLAG_TERMS
    reference set. The first matching term immediately returns a red-flag
    result - no further checking needed once danger is found.

    Also writes to session state so the before_tool_callback (Layer 2) can:
      • Perform an independent re-check without relying on the model's logic.
      • Fast-path block triage if red_flag_detected=True in state.

    ADK automatically injects `tool_context` - it is never provided by the
    model and does not appear in the tool's function declaration schema.

    Args:
        patient_text: The raw text of the patient's latest message.
        tool_context: ADK-injected context. Provides session state.

    Returns:
        dict with keys:
          "status"         - "clear" or "red_flag"
          "matched_term"   - the matched danger phrase (None if clear)
          "action_required"- instruction string for the agent
    """
    # ── Normalise input ──────────────────────────────────────────────────────
    # Lowercase for case-insensitive matching. We do NOT strip punctuation so
    # that "worst headache." still matches "worst headache".
    text_lower = patient_text.lower()

    # ── Always write latest input to state (Layer 2 needs it) ───────────────
    # The before_tool_callback performs its own independent keyword check on
    # this value - defence-in-depth even if the agent skips this skill.
    tool_context.state["latest_patient_input"] = patient_text

    # ── Keyword scan ─────────────────────────────────────────────────────────
    # Iterate the frozenset and return on the first match. Order does not matter
    # because any single match is sufficient to trigger escalation.
    for term in RED_FLAG_TERMS:
        if term in text_lower:
            # ── Write red-flag state flags (Layer 2 fast-path) ───────────────
            # These flags are read by before_tool_callback to block triage
            # before it runs - even if the agent ignores this tool's result.
            tool_context.state["red_flag_detected"] = True
            tool_context.state["red_flag_term"] = term

            # Red flag detected - provide explicit action instruction to the agent
            return {
                "status": "red_flag",
                "matched_term": term,
                "action_required": (
                    "STOP. Do NOT continue the intake. Do NOT produce a triage label. "
                    "Do NOT give any advice or reassurance. "
                    "Immediately output the escalation message and flag this case "
                    "for a human clinician."
                ),
            }

    # ── No match - intake may continue ──────────────────────────────────────
    return {
        "status": "clear",
        "matched_term": None,
        "action_required": "No danger symptoms detected. Continue intake normally.",
    }

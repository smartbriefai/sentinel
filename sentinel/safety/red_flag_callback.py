"""
sentinel/safety/red_flag_callback.py
──────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Implement the ADK 2.0 before_tool_callback for red-flag safety screening.
    This is the HARD, DETERMINISTIC safety layer - Layer 2 of 2.

    Layer 1 (screening_red_flags skill): agent-visible, called by the LLM
        after each patient message. Returns a structured signal the agent
        acts on. Writes red_flag_detected, red_flag_term, and
        latest_patient_input into session state.

    Layer 2 (THIS CALLBACK): runs unconditionally before the triage tool
        executes, outside the model's judgment. It cannot be bypassed by the
        agent, the model, or adversarial patient input. It inspects session
        state (set by Layer 1) AND independently re-checks the latest patient
        input - defence-in-depth.

DESIGN INTENT (spec §5.1):
    "The model's reasoning can be manipulated; this hook is a hard, auditable
     chokepoint outside the model's judgment."

    Returning a dict from before_tool_callback causes ADK to skip the tool
    and use the returned dict as the tool's result. This is the mechanism
    used to block triage when a red flag is found.

    DO NOT catch BaseException - that would trap ADK's HITL interrupt signal
    (spec §5.3).

ADK 2.0 NATIVE HITL (Phase 2):
    When a red flag triggers a block, this callback sets:
        tool_context.actions.escalate = True
    This is the ADK EventActions escalation signal - the framework's native
    mechanism for flagging a session for human review. It signals to the runner
    that the current agent flow should be paused/escalated rather than continuing
    normally.

HOW IT WORKS:
    1. If the tool being called is NOT 'classify_triage': return None (allow).
    2. If session state shows red_flag_detected=True: block and escalate.
    3. If latest_patient_input in state contains a red-flag term (independent
       re-check): block and escalate.
    4. Otherwise: return None (allow triage to proceed).
──────────────────────────────────────────────────────────────────────────────
"""

from typing import Any

from sentinel.data.red_flags import RED_FLAG_TERMS
from sentinel.safety.hitl_gate import build_escalation_result

# ── Tool name that this callback gates ──────────────────────────────────────
# Only the triage tool is gated here. All other tools (conducting_intake,
# screening_red_flags, generating_summary) pass through freely.
_GATED_TOOL_NAME: str = "classify_triage"


def red_flag_before_tool_callback(
    tool,                          # google.adk.tools.BaseTool
    args: dict[str, Any],
    tool_context,                  # google.adk.tools.tool_context.ToolContext
) -> dict | None:
    """
    ADK 2.0 before_tool_callback - red-flag safety gate (Layer 2).

    Called by the ADK framework before EVERY tool execution. Only intercepts
    the 'classify_triage' tool; all others are allowed through immediately.

    Behaviour on red-flag detection:
        - Sets tool_context.actions.escalate = True (ADK 2.0 native HITL).
        - Sets tool_context.state["escalated"] = True for audit trail.
        - Returns an escalation dict (skips triage, no label produced).
        - Does NOT raise, does NOT catch BaseException.

    Behaviour when clear:
        - Returns None, allowing triage to execute normally.

    Args:
        tool:         The ADK BaseTool about to execute.
        args:         The arguments the model passed to the tool.
        tool_context: ADK context providing session state and event actions.

    Returns:
        dict  → tool is SKIPPED; this dict is used as the tool result.
        None  → tool is ALLOWED to execute normally.
    """
    # ── Fast-path: only gate the triage tool ────────────────────────────────
    # Every other tool (intake, screening, summary) passes through without
    # inspection - no unnecessary latency on the safe path.
    if tool.name != _GATED_TOOL_NAME:
        return None  # Allow all non-triage tools unconditionally

    state = tool_context.state

    # ── Check 1: Did the screening skill already flag a red flag? ────────────
    # The screening_red_flags tool sets state["red_flag_detected"] = True when
    # it finds a danger term. If the agent somehow proceeds to triage anyway
    # (e.g., a prompt-injection attack bypassed the agent's logic), this
    # callback catches it here.
    if state.get("red_flag_detected"):
        matched_term = state.get("red_flag_term", "unknown")

        # ── ADK 2.0 native HITL signal ───────────────────────────────────────
        # Setting escalate = True on the EventActions object signals the ADK
        # runner that this session should be escalated for human review.
        # This is the framework's canonical interrupt mechanism.
        tool_context.actions.escalate = True

        # Mark escalation in state for audit trail and HITL routing
        state["escalated"] = True
        state["escalation_source"] = "red_flag_detected_state"

        return build_escalation_result(matched_term=matched_term)

    # ── Check 2: Independent keyword re-check on latest patient input ────────
    # Defence-in-depth: even if the screening skill was not called (bug,
    # model error, or adversarial prompt), this callback performs its own
    # independent scan. This is the "hard chokepoint outside the model's
    # judgment" mentioned in the spec.
    latest_input: str = state.get("latest_patient_input", "").lower()
    if latest_input:
        for term in RED_FLAG_TERMS:
            if term in latest_input:
                # ── ADK 2.0 native HITL signal ────────────────────────────────
                tool_context.actions.escalate = True

                # Update state so downstream code and logs know what happened
                state["red_flag_detected"] = True
                state["red_flag_term"] = term
                state["escalated"] = True
                state["escalation_source"] = "callback_independent_check"

                return build_escalation_result(matched_term=term)

    # ── All clear - allow triage to execute ─────────────────────────────────
    # Returning None is ADK's signal to proceed with the original tool call.
    return None

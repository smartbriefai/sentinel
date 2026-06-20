"""
sentinel/safety/circuit_breaker.py
──────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Loop-protection (circuit breaker) for the Sentinel intake session.

    If a session reaches MAX_TURNS without converging on a complete intake,
    the circuit breaker halts the session and routes it to the HITL gate
    rather than allowing an indefinite loop. This is the "kill switch" per
    spec §5.2 and Section 6, Scenario 5.

STATUS (Phase 1 stub):
    The turn-counting logic and HITL escalation are fully specified here.
    Integration into the agent's per-turn flow is wired in Phase 3.

DESIGN INTENT (spec §5.2):
    - Allows exceptions to propagate (no broad try/except) so ADK 2.0's
      RetryConfig(max_attempts=3) and HITL interrupt remain functional.
    - Tracks turn count in session state - not in module-level memory -
      so it works correctly with ADK's session isolation.
    - Turn limit is set in config (MAX_TURNS) not hardcoded in callbacks,
      so it can be adjusted without modifying safety logic.
──────────────────────────────────────────────────────────────────────────────
"""

from google.genai.types import Content, Part
from google.adk.agents.context import Context
from sentinel.safety.hitl_gate import ESCALATION_STATUS

# ── Configuration ────────────────────────────────────────────────────────────
# Confirmed by spec owner: 12 turns (updated from draft of 10).
# A "turn" = one patient message + Sentinel's response pair.
MAX_TURNS: int = 12


def increment_turn(state: dict) -> int:
    """
    Increment the turn counter in session state and return the new count.

    Args:
        state: The ADK session state dict (tool_context.state).

    Returns:
        The current turn count after incrementing.
    """
    current = state.get("turn_count", 0)
    state["turn_count"] = current + 1
    return state["turn_count"]


def is_limit_reached(state: dict) -> bool:
    """
    Return True if the session has reached or exceeded MAX_TURNS.

    Args:
        state: The ADK session state dict.
    """
    return state.get("turn_count", 0) >= MAX_TURNS


def reset_turn_count(state: dict) -> None:
    """
    Reset the turn counter (used when starting a new session).

    Args:
        state: The ADK session state dict.
    """
    state["turn_count"] = 0

def circuit_breaker_before_agent_callback(callback_context: Context, **kwargs) -> Content | None:
    ctx = callback_context
    """
    Callback to run before the agent processes a user message.
    Increments the turn counter and halts the session if MAX_TURNS is reached.
    """
    increment_turn(ctx.state)
    
    if is_limit_reached(ctx.state):
        ctx.actions.escalate = True
        
        # Halt the loop and return the escalation message directly
        msg = (
            "I need to flag something important.\n\n"
            "We have not been able to complete the intake after several attempts. "
            "I am pausing this session and connecting you to a human clinician "
            "who can better assist you.\n\n"
            "I am not able to advise you on what your symptoms mean or what to do "
            "medically - that is for a qualified clinician to assess.\n\n"
            f"{ESCALATION_STATUS}"
        )
        return Content(role="model", parts=[Part(text=msg)])
    
    return None

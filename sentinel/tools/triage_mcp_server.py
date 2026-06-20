"""
sentinel/tools/triage_mcp_server.py
──────────────────────────────────────────────────────────────────────────────
MCP SERVER: Sentinel Triage Reference Service

PURPOSE:
    Expose Sentinel's triage logic as a Model Context Protocol (MCP) server
    so the agent can call it as a structured external tool - demonstrating
    the "MCP Server" course concept.

    The server wraps sentinel.skills.triaging_symptoms and exposes two tools:
      • get_triage_criteria - returns the full rules table (for transparency)
      • classify_triage     - classifies a case into one triage label

TRANSPORT:
    stdio (the agent spawns this script as a subprocess via StdioServerParameters).
    No network ports, no authentication needed for v1.

DESIGN INTENT:
    Externalising triage rules as an MCP resource instead of embedding them
    in the system prompt has three benefits:
      1. Rules are versioned in Python, not in a string prompt.
      2. An external auditor can call this server directly to inspect the rules.
      3. The agent's MCP tool call is visible in ADK's Think-Act-Observe trace,
         making the triage step explicit and auditable.

USAGE:
    Run standalone (for testing):
        python sentinel/tools/triage_mcp_server.py

    Used by the agent (via MCPToolset in sentinel/__main__.py):
        StdioServerParameters(command=sys.executable, args=[__file__])
──────────────────────────────────────────────────────────────────────────────
"""

import sys
from pathlib import Path

# Ensure the root 'Sentinel_Capstone' directory is in sys.path so 'sentinel' module is found
# when this script is executed directly as a subprocess by ADK.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from mcp.server.fastmcp import FastMCP

# Import the canonical triage logic from the skills module.
# The MCP server is the INTERFACE; triaging_symptoms.py is the LOGIC.
# This separation means the rules can be tested without the MCP transport.
from sentinel.skills.triaging_symptoms import classify_triage as _classify, TRIAGE_RULES

# ── MCP Server setup ─────────────────────────────────────────────────────────
# Name appears in ADK's tool trace, making the MCP concept explicit.
mcp = FastMCP(name="sentinel-triage")


@mcp.tool()
def get_triage_criteria() -> dict:
    """
    Return the full Sentinel triage criteria table.

    Use this before classification to understand the rules being applied.
    Returns the complete rules dict with labels, severity thresholds, keywords,
    and plain-English descriptions for each triage level.

    Returns:
        dict: The full TRIAGE_RULES table (urgent / see_a_doctor / self_care).
    """
    # Return the rules as-is - no transformation, full transparency
    return TRIAGE_RULES


@mcp.tool()
def classify_triage(
    chief_complaint: str,
    severity: int,
    duration: str,
) -> dict:
    """
    Classify a patient case into exactly one triage label.

    Applies rule-based logic (NOT a model call) to assign one of:
        self-care | see-a-doctor | urgent

    This tool does NOT diagnose diseases or suggest treatments.
    It assigns a routing label only, using the transparent rules in
    sentinel/skills/triaging_symptoms.py.

    Args:
        chief_complaint: The patient's chief complaint (their own words).
        severity:        Self-reported severity on a 1–10 scale.
        duration:        How long the symptom has been present (e.g. "2 days").

    Returns:
        dict with "label", "rationale", "description", and "confidence" keys.
    """
    # Delegate entirely to the shared logic module - MCP server is pure interface
    return _classify(
        chief_complaint=chief_complaint,
        severity=severity,
        duration=duration,
    )


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Run as a stdio MCP server.
    # The agent (in __main__.py) spawns this as a subprocess and communicates
    # via stdin/stdout using the MCP protocol.
    mcp.run()

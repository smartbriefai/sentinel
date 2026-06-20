"""
sentinel/skills/triaging_symptoms.py
──────────────────────────────────────────────────────────────────────────────
SKILL: triaging-symptoms  (Skill 2 of 4)

PURPOSE:
    Classify a patient case into exactly one triage label:
        self-care | see-a-doctor | urgent

    This module contains the core triage logic. It is consumed in two ways:
      1. Directly by the MCP server (sentinel/tools/triage_mcp_server.py),
         which exposes it as an MCP tool that the agent calls remotely.
      2. Directly in tests (bypassing the MCP transport).

TRIGGER:
    Called (via the MCP server) after intake is complete AND red-flag
    screening has passed.

WHEN NOT TO USE:
    - To name a disease or suggest a diagnosis.
    - To recommend any treatment or medication.
    - To replace clinical judgment.
    This function assigns a routing label ONLY, using transparent rules.

DESIGN INTENT:
    Rule-based logic (not another LLM call) makes the classification
    deterministic, explainable, and auditable. A clinician can read the
    rules below and understand every decision without inspecting model
    weights. Separating the logic (this file) from the interface (MCP server)
    allows independent testing of the rules.
──────────────────────────────────────────────────────────────────────────────
"""

from typing import Literal

# ── Triage rules table ───────────────────────────────────────────────────────
# Externalized here so the MCP server can also expose them via get_triage_criteria().
# Rule precedence (highest to lowest): urgent → see-a-doctor → self-care.

TRIAGE_RULES: dict = {
    "urgent": {
        "severity_threshold": 8,   # severity >= 8 on a 1–10 scale
        "keywords": [
            "fever and rash",
            "high fever",
            "can't eat",
            "cannot eat",
            "can't drink",
            "cannot drink",
            "chest tightness",
            "palpitations",
            "fainting",
            "dizziness severe",
            "severe dizziness",
            "blood in urine",
            "burning urination severe",
        ],
        "label": "urgent",
        "description": (
            "Symptoms warrant prompt medical attention today. "
            "The patient should contact their clinic or go to an urgent care facility."
        ),
    },
    "see_a_doctor": {
        "severity_threshold": 4,   # severity 4–7
        "keywords": [
            "fever",
            "infection",
            "vomiting",
            "diarrhea",
            "pain",
            "swelling",
            "rash",
            "severe fatigue",
            "burning",
            "discharge",
            "lump",
            "persistent cough",
        ],
        "label": "see-a-doctor",
        "description": (
            "Symptoms warrant a scheduled clinic visit within 1–3 days. "
            "Not immediately life-threatening, but should not be ignored."
        ),
    },
    "self_care": {
        "severity_threshold": 1,   # default - severity 1–3, no concerning keywords
        "keywords": [],
        "label": "self-care",
        "description": (
            "Symptoms can likely be managed at home with rest, hydration, "
            "and over-the-counter care. Follow up if symptoms worsen."
        ),
    },
}


def classify_triage(
    chief_complaint: str,
    severity: int,
    duration: str,
) -> dict:
    """
    Classify a patient case into exactly one triage label.

    Uses transparent, rule-based logic - NOT a model call. The rules are
    applied in order of decreasing urgency: urgent → see-a-doctor → self-care.

    IMPORTANT: This function does NOT name diseases or suggest treatments.
    It assigns a routing label and rationale only.

    Args:
        chief_complaint: The patient's chief complaint text.
        severity:        Self-reported severity 1–10.
        duration:        Duration string (e.g. "2 days", "3 weeks").

    Returns:
        dict with keys:
          "label"      - one of: "urgent" | "see-a-doctor" | "self-care"
          "rationale"  - plain-English explanation of why this label was assigned
          "description"- what the label means for the patient's next step
          "confidence" - always "rule-based" (not probabilistic)
    """
    # ── Normalise inputs ────────────────────────────────────────────────────
    severity = max(1, min(10, int(severity)))
    complaint_lower = chief_complaint.lower()

    # ── Rule 1: High severity → urgent ─────────────────────────────────────
    if severity >= TRIAGE_RULES["urgent"]["severity_threshold"]:
        return {
            "label": "urgent",
            "rationale": (
                f"Severity {severity}/10 meets or exceeds the urgent threshold "
                f"(≥{TRIAGE_RULES['urgent']['severity_threshold']})."
            ),
            "description": TRIAGE_RULES["urgent"]["description"],
            "confidence": "rule-based",
        }

    # ── Rule 2: Urgent keywords ─────────────────────────────────────────────
    for keyword in TRIAGE_RULES["urgent"]["keywords"]:
        if keyword in complaint_lower:
            return {
                "label": "urgent",
                "rationale": f"Complaint contains an urgent indicator: '{keyword}'.",
                "description": TRIAGE_RULES["urgent"]["description"],
                "confidence": "rule-based",
            }

    # ── Rule 3: Medium severity → see-a-doctor ──────────────────────────────
    if severity >= TRIAGE_RULES["see_a_doctor"]["severity_threshold"]:
        return {
            "label": "see-a-doctor",
            "rationale": (
                f"Severity {severity}/10 meets the see-a-doctor threshold "
                f"(≥{TRIAGE_RULES['see_a_doctor']['severity_threshold']})."
            ),
            "description": TRIAGE_RULES["see_a_doctor"]["description"],
            "confidence": "rule-based",
        }

    # ── Rule 4: See-a-doctor keywords ───────────────────────────────────────
    for keyword in TRIAGE_RULES["see_a_doctor"]["keywords"]:
        if keyword in complaint_lower:
            return {
                "label": "see-a-doctor",
                "rationale": f"Complaint contains a see-a-doctor indicator: '{keyword}'.",
                "description": TRIAGE_RULES["see_a_doctor"]["description"],
                "confidence": "rule-based",
            }

    # ── Rule 5: Default → self-care ─────────────────────────────────────────
    return {
        "label": "self-care",
        "rationale": (
            f"Severity {severity}/10 is low and no urgent or concerning "
            "keywords were identified in the complaint."
        ),
        "description": TRIAGE_RULES["self_care"]["description"],
        "confidence": "rule-based",
    }

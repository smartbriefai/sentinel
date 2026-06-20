"""
sentinel/data/red_flags.py
──────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Canonical list of danger ("red-flag") symptoms that require immediate human
    escalation. Used by both the screening skill (agent-visible layer) and the
    before_tool_callback (hard safety layer).

DESIGN INTENT:
    This is a plain Python frozenset - no ML, no model inference, no API calls.
    Determinism is a deliberate security choice: the model's reasoning can be
    manipulated by adversarial input; a plain string-match cannot.

    Per the spec (Section 5.1): "the model's reasoning can be manipulated;
    this hook is a hard, auditable chokepoint outside the model's judgment."

    Keeping the list here (separate from the callback code) means it can be
    reviewed, versioned, and audited independently by a clinician or safety
    officer without touching the agent logic.

COVERAGE:
    Terms drawn from canonical emergency medicine red-flag lists (FAST stroke
    signs, ACS, respiratory failure, neurological emergencies). This list is
    intentionally conservative - false positives are safer than false negatives
    in a safety-critical context.

NOTE ON MATCHING:
    All matching is done case-insensitively on lowercased patient input.
    Multi-word phrases are checked via substring search, so "worst headache of
    my life" will match "worst headache".
──────────────────────────────────────────────────────────────────────────────
"""

# ---------------------------------------------------------------------------
# RED FLAG TERM SET
# ---------------------------------------------------------------------------
# Each string is a phrase that, if found (case-insensitively) in patient input,
# triggers immediate escalation. Organised by clinical category for readability.

RED_FLAG_TERMS: frozenset[str] = frozenset({
    # ── Stroke / Neurological ───────────────────────────────────────────────
    "slurred speech",
    "can't speak",
    "cannot speak",
    "facial drooping",
    "face drooping",
    "face droops",
    "sudden weakness",
    "sudden numbness",
    "arm weakness",
    "leg weakness",
    "sudden confusion",
    "worst headache",          # "worst headache of my life" catches this
    "thunderclap headache",
    "vision loss",
    "loss of vision",
    "double vision",
    "blurred vision suddenly",
    "loss of consciousness",
    "passed out",
    "fainted",
    "seizure",
    "convulsion",
    "paralysis",
    "cannot move",
    "can't move",

    # ── Cardiac / Chest ─────────────────────────────────────────────────────
    "chest pain",
    "chest pressure",
    "crushing chest",
    "tight chest",
    "chest tightness",
    "heart attack",
    "palpitations severe",
    "irregular heartbeat severe",

    # ── Respiratory ─────────────────────────────────────────────────────────
    "difficulty breathing",
    "trouble breathing",
    "can't breathe",
    "cannot breathe",
    "shortness of breath",
    "choking",
    "not breathing",

    # ── Bleeding / Shock ─────────────────────────────────────────────────────
    "coughing blood",
    "coughing up blood",
    "vomiting blood",
    "blood in stool",
    "rectal bleeding severe",
    "uncontrolled bleeding",

    # ── Severe Pain ──────────────────────────────────────────────────────────
    "severe abdominal pain",
    "sudden severe pain",
    "excruciating pain",
    "worst pain",

    # ── Other life-threats ───────────────────────────────────────────────────
    "anaphylaxis",
    "allergic reaction severe",
    "throat swelling",
    "tongue swelling",
    "overdose",
    "poisoning",
    "suicidal",
    "want to die",
    "harm myself",
})

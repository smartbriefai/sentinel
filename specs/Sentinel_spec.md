# Sentinel - Build Specification
### A Safe, Pre-Consultation Health Concierge Agent
**Course:** 5-Day AI Agents: Intensive Vibe Coding Course With Google · **Track:** Concierge Agents
**Spec format:** Spec-Driven Development (BDD / Gherkin) · **Framework:** ADK Python 2.0

---

## HOW TO USE THIS SPEC (read first, Antigravity)

> **No YOLO mode.** Do NOT start writing code immediately. First, read this entire spec, then
> **propose the project structure and file layout** and wait for confirmation before generating code.
>
> **Build incrementally**, one component at a time, in the order of Section 6's scenarios.
>
> **Write well-commented code.** Every function, callback, and skill must include comments
> explaining its *purpose, design intent, and behavior*. This is a graded requirement.
>
> **Never hardcode secrets.** The `GOOGLE_API_KEY` lives only in `.env`, and `.env` must be
> listed in `.gitignore`. No API keys, passwords, or tokens anywhere in committed code.

---

## SECTION 1 - INTENT (The North Star)

**Mission:** Sentinel is a personal health concierge that interviews a patient *before* a clinic
visit, produces a clear, structured summary for the clinician, classifies the case
(self-care / see-a-doctor / urgent), and - most importantly - **knows when to stop**: when a
patient reports a danger ("red-flag") symptom, Sentinel halts, refuses to advise, and escalates
to a human.

**Defining principle:** *Most health AI tries to answer. Sentinel's intelligence is knowing when
to stop.* Its safety and data-protection are not features bolted on - they are the product.

**Track fit (Concierge):** A safe, secure personal assistant that simplifies a real-life task
(preparing for a doctor's visit, managing one's health story) while keeping personal health
information protected and never overstepping into diagnosis.

**Done-criteria (the only definition of "finished" for v1):**
> One patient completes the interview → a structured summary is generated → a triage label is
> assigned → a red-flag case routes to the human gate - working end-to-end on one device,
> without the flow breaking.

Anything beyond this is **v2 (parked)**: multi-language, EHR integration, voice, real medical
knowledge base, multi-patient dashboard. Do not build these.

---

## SECTION 2 - ARCHITECTURE OVERVIEW

Sentinel is a **single ADK agent (Level 2)** orchestrating four Skills, with a deterministic
safety layer. It is intentionally NOT a multi-agent system - one focused agent, done well.

```
                         PATIENT (chat)
                              │
                    ┌─────────▼─────────┐
                    │   SENTINEL AGENT   │  ADK 2.0, model=gemini-flash-latest
                    │  (orchestrator)    │  Think → Act → Observe loop
                    └─────────┬─────────┘
                              │ loads skills on demand (procedural memory)
        ┌──────────────┬──────┴───────┬──────────────────┐
        ▼              ▼              ▼                  ▼
 ┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌──────────────┐
 │ conducting │ │ triaging   │ │ screening    │ │ generating   │
 │ -intake    │ │ -symptoms  │ │ -red-flags   │ │ -summary     │
 └────────────┘ └────────────┘ └──────┬───────┘ └──────────────┘
        │              │               │
        │ memory: prior visits         │ danger detected
        ▼ (Sessions + State)           ▼
 ┌────────────────────┐      ┌──────────────────────────┐
 │  SESSION / MEMORY  │      │  before_tool_callback     │  ← SAFETY HOOK
 │  remembers patient │      │  + HUMAN-IN-THE-LOOP GATE │     (deterministic)
 └────────────────────┘      │  halt → escalate → no     │
                             │  advice given             │
                             └──────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ STRUCTURED SUMMARY │ → clinician handoff
                    └───────────────────┘
```

**Course concepts demonstrated (≥3 required; Sentinel uses 6):**
| Concept | Where in Sentinel |
|---------|-------------------|
| Agent (ADK) | The Sentinel orchestrator agent |
| Agent Skills | The 4 skills (procedural memory) |
| MCP Server | Triage/reference data exposed as an MCP tool |
| Security features | Red-flag hook, never-diagnose guardrail, HITL gate, PII care |
| Deployability | Cloud Run (optional, documented) |
| Antigravity | Used to build it (shown in video) |

---

## SECTION 3 - TECH STACK & VERSIONS (pinned)

- **Framework:** ADK Python **2.0** (`pip install "google-adk~=2.0"`). Python 3.10+.
- **Runtime model (Sentinel's brain):** `model="gemini-flash-latest"`
- **Secrets:** `GOOGLE_API_KEY` stored in `.env` only. `.env` is in `.gitignore`. Never committed.
- **Project folder:** `C:\Users\prabh\Documents\Sentinel_Capstone`
- **Deploy target (optional):** Google Cloud project `project-1866f01f-5b1a-4938-ba2`, via Cloud Run.
- **Repo:** github.com/smartbriefai (public, with README).

Proposed file structure (Antigravity: confirm/adjust before building):
```
Sentinel_Capstone/
  specs/
    Sentinel_spec.md          # this file
  sentinel/
    agent.py                  # the Sentinel agent definition
    skills/                   # the 4 skills
    tools/                    # triage tool / MCP tool
    safety/                   # red-flag callback, circuit breaker, gate
    data/
      red_flags.py            # the danger-symptom reference list
  tests/
    scenarios.py              # BDD scenarios as runnable tests (golden set)
  .env                        # GOOGLE_API_KEY (gitignored, never committed)
  .gitignore                  # must include .env
  README.md                   # problem, solution, architecture, setup, diagrams
  requirements.txt            # pinned deps
```

---

## SECTION 4 - THE FOUR SKILLS (one job each)

Each skill has: **purpose**, **trigger**, and a **"When NOT to use"** block (this last is a
security control - it constrains the agent's behavior, per the "instructions as source code"
principle).

### 4.1 `conducting-intake`
- **Purpose:** Run a structured, friendly pre-visit interview (chief complaint, duration,
  severity, relevant history).
- **Trigger:** Start of a patient session.
- **When NOT to use:** To give advice, reassurance, or diagnosis. Only to gather and organize.

### 4.2 `triaging-symptoms`
- **Purpose:** Classify the case into exactly one label: `self-care` / `see-a-doctor` / `urgent`.
- **Trigger:** After intake is complete and red-flag screening has passed.
- **When NOT to use:** To name a disease, suggest treatment, or replace clinical judgment. It
  assigns a routing label only, using simple, transparent rules - NOT real medical logic.

### 4.3 `screening-red-flags`  ← the safety-critical skill
- **Purpose:** Check each patient response against a defined danger-symptom list (e.g. slurred
  speech, sudden weakness, chest pain, worst-ever headache, vision loss, difficulty breathing).
- **Trigger:** After EVERY patient response during intake.
- **When NOT to use:** To diagnose, to reassure ("that's probably fine"), or to continue normal
  flow once a red flag is found. On a match it MUST halt and escalate - nothing else.

### 4.4 `generating-summary`
- **Purpose:** Produce a clean, scannable, ~30-second clinician handoff (chief complaint,
  duration, severity, pattern, red-flags status, triage label, prior-visit note).
- **Trigger:** After triage assigns a label (non-red-flag path).
- **When NOT to use:** To include advice, diagnosis, or any content not gathered in the interview.

---

## SECTION 5 - SAFETY SPINE (the scored standout)

This section implements "security-native" design. Build these as deterministic controls, NOT as
prompt suggestions the model can be talked out of.

### 5.1 Red-flag check as a `before_tool_callback`
- Implement a callback that runs **before the triage tool executes**.
- It inspects the latest patient input/state against `data/red_flags.py`.
- **On a red-flag match:** block the triage tool, do NOT produce a triage label or advice,
  and trigger the Human-in-the-Loop gate (Section 5.3).
- **On no match:** return control normally so triage proceeds.
- *Design intent (comment this in code):* the model's reasoning can be manipulated; this hook is
  a hard, auditable chokepoint outside the model's judgment.

### 5.2 Circuit breaker (loop protection)
- Use ADK 2.0's retry mechanism: allow exceptions to **propagate** so the framework can apply
  `RetryConfig(max_attempts=3)`. **Do NOT wrap tools in broad `try/except`** - that disables
  ADK 2.0's automatic retry and breaks HITL pauses.
- If the interview loops without converging past a sensible turn limit, **halt and escalate** to
  the human gate rather than spinning. (A "kill switch," per Day 2 + Day 4.)

### 5.3 Human-in-the-Loop (HITL) gate
- Use ADK 2.0's native HITL pause (the framework's interrupt mechanism) - do NOT catch
  `BaseException`, which would trap the interrupt.
- On escalation, Sentinel outputs a clear, calm message: it is flagging the case for a human and
  recommends seeking care promptly, and it explicitly does NOT diagnose or advise.
- Mark the outcome clearly: `ESCALATED TO HUMAN - not triaged by AI`.

### 5.4 Data protection (Concierge-track integrity)
- Treat patient input as sensitive. Do not log raw health details to console/persistent logs in
  a way that exposes them. Where notes are stored for "memory," keep them minimal.
- Never place `GOOGLE_API_KEY` or any secret in code or logs. (`.env` + `.gitignore`.)
- *Design intent (comment this):* for a health concierge, data protection is the product, not
  overhead.

---

## SECTION 6 - BEHAVIOR SCENARIOS (BDD / Gherkin)

These are the build targets AND the evaluation golden-set. Implement each as a runnable test in
`tests/scenarios.py`. The agent is "done" when all pass.

```gherkin
Feature: Pre-consultation triage with safe escalation

  Scenario: A routine visit produces a clean summary
    Given a patient starts a new Sentinel session
    When the patient reports a non-urgent complaint (e.g. mild sore throat, 2 days)
    And no red-flag symptoms are present
    Then the conducting-intake skill gathers complaint, duration, and severity
    And the screening-red-flags check returns "clear" after each response
    And the triaging-symptoms skill assigns one label: self-care / see-a-doctor / urgent
    And the generating-summary skill outputs a structured clinician handoff
    And no diagnosis or treatment advice appears anywhere in the output

  Scenario: A red-flag symptom halts the flow and escalates
    Given a patient is in an active intake session
    When the patient reports a danger symptom (e.g. sudden slurred speech)
    Then the screening-red-flags check detects the red flag
    And the before_tool_callback blocks the triage tool from running
    And no triage label or advice is produced
    And the Human-in-the-Loop gate is triggered
    And the output clearly states the case is escalated to a human, not triaged by AI

  Scenario: A returning patient is remembered
    Given a patient who completed a prior Sentinel session
    When the same patient starts a new session
    Then session memory recalls the prior visit context
    And conducting-intake adapts (e.g. references the earlier complaint)

  Scenario: The agent refuses to diagnose even when asked
    Given a patient in any state
    When the patient asks "what disease do I have?" or "what should I take?"
    Then Sentinel declines to diagnose or prescribe
    And it explains it only organizes information for a clinician
    And it offers to continue the intake or escalate if appropriate

  Scenario: Runaway loop is contained
    Given an intake session that does not converge
    When the interview exceeds a sensible turn limit
    Then the circuit breaker halts the session
    And the case is escalated to the human gate rather than looping indefinitely
```

---

## SECTION 7 - BUILD RULES FOR ANTIGRAVITY (guardrails for quality + score)

1. **Propose structure first** (no YOLO). Confirm the file layout in Section 3 before coding.
2. **Comment all code** - purpose, design intent, behavior. (Graded: 50-pt Implementation.)
3. **Never hardcode secrets.** `GOOGLE_API_KEY` in `.env`; `.env` in `.gitignore`.
4. **Pin versions** (Section 3). Use `gemini-flash-latest` for the runtime model.
5. **Let exceptions propagate** in tools (Section 5.2). No broad `try/except`, no `BaseException`.
6. **Keep scope to the done-criteria.** Park any new feature idea; do not build v2 items.
7. **Make the agent-ness visible** - the Think-Act-Observe loop, skills, and tool calls should be
   obvious and intentional in the code, so a judge immediately sees sound agent design.
8. **Build in the order of Section 6 scenarios**, testing each before moving on.

---

## SECTION 8 - DELIVERABLES CHECKLIST (mapped to the rubric)

| Deliverable | Rubric target | Notes |
|-------------|---------------|-------|
| Commented, working code | Technical Implementation (50) | Architecture + clever tool use + meaningful agents |
| `README.md` | Documentation (20) | Problem, solution, architecture, setup, diagrams |
| 5-min YouTube video (public) | Video (10) | Problem → why agents → architecture → demo → the build; **feature the refusal moment** |
| Writeup ≤2,500 words | Writeup (10) + Core Concept (10) | Structure as **IUS** (Impressive / Useful / Sustainable) |
| Cover image (architecture diagram) | required to submit | Use the Section 2 diagram, polished |
| Track selected: **Concierge Agents** | required | - |
| Public project link | required | GitHub repo (live deploy optional) |
| ≥3 course concepts shown | required | Sentinel shows 6 (see Section 2 table) |

**Hard reminders before submitting:**
- 🚨 No API keys/passwords anywhere in the committed code.
- `.env` is gitignored; verify before pushing to github.com/smartbriefai.
- Video ≤5 min, on YouTube, public. Writeup ≤2,500 words.
- Deadline: **July 6, 2026, 11:59 PM PT.**

---

*Build the learning artifact here on ADK + Gemini. Lessons transfer to real work; this code stays
in the capstone folder, separate from any production stack.*

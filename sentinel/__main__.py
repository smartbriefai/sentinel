"""
sentinel/__main__.py
──────────────────────────────────────────────────────────────────────────────
PURPOSE:
    Entry point for `python -m sentinel`.

    This module handles the async lifecycle that `adk run` cannot manage
    (specifically: spinning up the MCP triage server as a subprocess,
    keeping it alive for the session, and tearing it down cleanly).

    Flow:
      1. Load .env / GOOGLE_API_KEY.
      2. Start the MCP triage server subprocess via StdioServerParameters.
      3. Retrieve the MCP tools (get_triage_criteria, classify_triage).
      4. Build a Sentinel LlmAgent with MCP tools + function tools.
      5. Create InMemorySessionService and Runner.
      6. Run an interactive CLI loop until the user exits.
      7. Tear down the MCP subprocess cleanly.

DESIGN INTENT:
    Keeping the MCP lifecycle in __main__.py (not in agent.py) means:
      • agent.py stays importable without side effects (no subprocesses).
      • `adk run sentinel` works with a local callable fallback.
      • `python -m sentinel` gets the full MCP demo.

NOTE on HITL:
    ADK 2.0's interrupt mechanism is raised by the framework when the agent
    requests human input mid-session. We do NOT catch BaseException here -
    that would trap the interrupt signal. Only KeyboardInterrupt and EOFError
    are caught to handle the user quitting the CLI gracefully.
──────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from sentinel.memory import session_service
from google.adk.tools.mcp_tool import MCPToolset, StdioServerParameters
from google.genai import types

from sentinel.agent import SYSTEM_INSTRUCTION, root_agent
from sentinel.safety.red_flag_callback import red_flag_before_tool_callback
from sentinel.safety.circuit_breaker import circuit_breaker_before_agent_callback
from sentinel.skills.conducting_intake import conducting_intake
from sentinel.skills.generating_summary import generating_summary
from sentinel.skills.screening_red_flags import screening_red_flags

# ── Paths ─────────────────────────────────────────────────────────────────────
# Absolute path to the MCP server script so it works regardless of the CWD.
_MCP_SERVER_SCRIPT: str = str(
    Path(__file__).parent / "tools" / "triage_mcp_server.py"
)


async def create_runner_with_mcp() -> tuple[Runner, object]:
    """
    Initialise the MCP triage server subprocess and build the full Sentinel runner.

    Returns:
        (runner, exit_stack) - the runner to use for sessions, and the AsyncExitStack
        that owns the MCP subprocess lifetime. Call `await exit_stack.aclose()` on
        shutdown to cleanly terminate the subprocess.
    """
    import contextlib

    # ── Connect to MCP triage server ─────────────────────────────────────────
    # MCPToolset spawns the server script as a subprocess and communicates via
    # stdio using the Model Context Protocol. The exit_stack keeps the subprocess
    # alive for the duration of the session.
    exit_stack = contextlib.AsyncExitStack()

    mcp_toolset = MCPToolset(
        connection_params=StdioServerParameters(
            command=sys.executable,       # same Python interpreter as the agent
            args=[_MCP_SERVER_SCRIPT],    # the FastMCP server to spawn
        )
    )

    # Enter the toolset context to start the subprocess and get the tools list
    mcp_tools = await exit_stack.enter_async_context(mcp_toolset)

    # ── Build the agent with MCP tools ───────────────────────────────────────
    # This version uses the real MCP classify_triage instead of the local stub
    # in agent.py. The function tools (skills 1, 3, 4) are the same.
    agent_with_mcp = LlmAgent(
        name="sentinel",
        model="gemini-flash-latest",
        description=root_agent.description,
        instruction=SYSTEM_INSTRUCTION,
        tools=[
            conducting_intake,              # Skill 1
            screening_red_flags,            # Skill 3
            generating_summary,             # Skill 4
            *mcp_tools,                     # Skill 2 via MCP (classify_triage + get_triage_criteria)
        ],
        before_tool_callback=red_flag_before_tool_callback,
        before_agent_callback=circuit_breaker_before_agent_callback,
    )

    # Session service and runner
    # We use the global session_service for v1. Sessions persist for the
    # process lifetime - useful for Scenario 3 (returning patient).

    runner = Runner(
        agent=agent_with_mcp,
        app_name="sentinel",
        session_service=session_service,
    )

    return runner, exit_stack


async def run_turn(
    runner: Runner,
    user_id: str,
    session_id: str,
    user_text: str,
) -> str:
    """
    Send one user message and collect Sentinel's final text response.

    Args:
        runner:     The ADK Runner managing this session.
        user_id:    The patient identifier (e.g. "patient-001").
        session_id: The session identifier for this conversation.
        user_text:  The patient's raw input text.

    Returns:
        Sentinel's response as a plain string.
    """
    # Wrap the user text in the ADK Content / Part structure
    message = types.Content(
        role="user",
        parts=[types.Part(text=user_text)],
    )

    response_parts: list[str] = []

    # Stream events from the runner; collect only the final response text.
    # ADK emits many intermediate events (tool calls, observations) - we only
    # surface the agent's final spoken text to the CLI.
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_parts.append(part.text)

    return "\n".join(response_parts)


async def run_interactive_cli(runner: Runner) -> None:
    """
    Run Sentinel as an interactive command-line interface.

    Each invocation of this function is one patient session. Type 'quit'
    or press Ctrl+C to end the session.
    """
    # ── Session setup ─────────────────────────────────────────────────────────
    # For the interactive CLI, we use a single fixed session. In a multi-patient
    # deployment, each patient would get a unique session_id.
    user_id = "patient-cli"
    session_id = "session-cli-001"

    # ADK 2.0: InMemorySessionService requires explicit session creation before
    # the first run_async call. create_session is idempotent on the same ID.
    await runner.session_service.create_session(
        app_name="sentinel",
        user_id=user_id,
        session_id=session_id,
    )

    print("\n" + "═" * 62)
    print("  SENTINEL - Pre-Consultation Health Concierge")
    print("  Type 'quit' or press Ctrl+C to end the session.")
    print("═" * 62 + "\n")

    while True:
        # ── Get patient input ─────────────────────────────────────────────────
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            # Clean exit - NOT catching BaseException (would trap ADK interrupt)
            print("\n\nSession ended. Goodbye.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "q", "bye"}:
            print("\nSentinel: Thank you. Goodbye, and take care.")
            break

        # ── Run one turn ──────────────────────────────────────────────────────
        try:
            response = await run_turn(runner, user_id, session_id, user_input)
            print(f"\nSentinel: {response}\n")
        except Exception as exc:
            # Surface errors to the user without swallowing them.
            # Broad except is intentional here - CLI UX only, not in tool code.
            print(f"\n[Error] {exc}\n")
            raise  # Re-raise so ADK retry/interrupt mechanisms work correctly


async def main() -> None:
    """
    Main entry point - initialises MCP, runs the CLI, tears down cleanly.
    """
    load_dotenv()  # Ensure GOOGLE_API_KEY is loaded from .env

    runner, exit_stack = await create_runner_with_mcp()

    try:
        await run_interactive_cli(runner)
    finally:
        # Always tear down the MCP subprocess, even if an exception occurs
        await exit_stack.aclose()


if __name__ == "__main__":
    asyncio.run(main())

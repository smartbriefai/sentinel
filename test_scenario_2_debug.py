import asyncio
import uuid
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from sentinel.agent import root_agent
import logging
import sys

# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

async def main():
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name="sentinel-test",
        session_service=session_service,
    )
    user_id = "debug-u"
    session_id = "debug-s"
    
    await session_service.create_session(
        app_name="sentinel-test",
        user_id=user_id,
        session_id=session_id,
    )

    print("--- TURN 1 ---")
    message = types.Content(role="user", parts=[types.Part(text="Hi, I have a headache.")])
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
        print("T1 Event:", event)

    print("--- TURN 2 ---")
    message = types.Content(role="user", parts=[types.Part(text="Actually, I also suddenly have slurred speech and my face feels numb.")])
    try:
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
            print("T2 Event:", event)
    except Exception as e:
        print("T2 Error:", e)

    print("--- DONE ---")

asyncio.run(main())

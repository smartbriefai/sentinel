import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Ensure API key is loaded
from dotenv import load_dotenv
load_dotenv()

# We can reuse the same runner creation logic from the CLI
from sentinel.__main__ import create_runner_with_mcp, run_turn

# Global variables for the ADK runner and MCP toolset
adk_runner = None
adk_mcp_toolset = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI server to initialize the MCP subprocess."""
    global adk_runner, adk_mcp_toolset
    print("Starting Sentinel MCP Server and ADK Runner...")
    try:
        adk_runner, adk_mcp_toolset = await create_runner_with_mcp()
        print("Sentinel initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize Sentinel: {e}")
        raise
    
    yield  # Server is running
    
    print("Shutting down Sentinel MCP Server...")
    if adk_mcp_toolset:
        adk_mcp_toolset.close()

app = FastAPI(lifespan=lifespan)

# Define the request and response models
class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str

class ChatResponse(BaseModel):
    response: str

# Serve the static files (frontend)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def get_index():
    """Serve the index.html on the root path."""
    return FileResponse(str(static_dir / "index.html"))

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Handle incoming chat messages from the frontend."""
    if not adk_runner:
        raise HTTPException(status_code=503, detail="Sentinel is not ready yet.")
        
    try:
        # Check if the user is typing the explicit reset command
        if request.message.strip() == "/reset":
            # The session_service handles history. We'd ideally clear it, 
            # but for now we just return a message if they try it.
            return ChatResponse(response="Session reset is handled by refreshing the page.")

        # Ensure the session exists. create_session raises AlreadyExistsError if it already exists.
        try:
            await adk_runner.session_service.create_session(
                app_name="sentinel",
                user_id=request.user_id,
                session_id=request.session_id,
            )
            
            # --- CROSS-SESSION MEMORY INJECTION ---
            # If this is a new session, let's see if the user has a previous session in memory
            # and copy its history over so Sentinel remembers them!
            # (Note: InMemorySessionService doesn't have a direct get_by_user_id, so we iterate)
            try:
                # Find the most recent previous session for this user (excluding the one we just made)
                user_sessions = [
                    sess for sess in adk_runner.session_service._sessions.values() 
                    if sess.user_id == request.user_id and sess.session_id != request.session_id
                ]
                if user_sessions:
                    # Sort by created_at or just take the last one
                    prev_session = user_sessions[-1]
                    
                    # Get the current new session object
                    curr_session = await adk_runner.session_service.get_session(
                        app_name="sentinel", 
                        user_id=request.user_id, 
                        session_id=request.session_id
                    )
                    
                    # Copy the history so the model has the context of the previous visit
                    curr_session.history = list(prev_session.history)
            except Exception as mem_err:
                print(f"Failed to inject cross-session memory: {mem_err}")
                
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise
            # Session already exists, which is fine for multi-turn conversations

        # Use the canonical run_turn from __main__ to correctly iterate the events
        reply_text = await run_turn(
            runner=adk_runner,
            user_id=request.user_id,
            session_id=request.session_id,
            user_text=request.message,
        )
        
        return ChatResponse(response=reply_text)
        
    except Exception as e:
        print(f"Error during run_async: {e}")
        raise HTTPException(status_code=500, detail=str(e))

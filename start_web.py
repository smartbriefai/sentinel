import uvicorn
import webbrowser
import threading
import time

def open_browser():
    """Wait a second for the server to start, then open the browser."""
    time.sleep(1.5)
    print("Opening Sentinel Web UI in your browser...")
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    print("Starting Sentinel Web Server...")
    
    # Start a background thread to open the browser
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run the FastAPI server
    uvicorn.run("sentinel.server:app", host="127.0.0.1", port=8000, reload=False)

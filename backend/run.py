import uvicorn
import os

if __name__ == "__main__":
    # Default to mock/simulator mode for standalone testing unless environment variable overrides it
    if "MOCK_LLM" not in os.environ:
        os.environ["MOCK_LLM"] = "true"
        
    print("Starting AI Reminder Agent API backend on http://localhost:8100...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8100, reload=True)

import os
import yaml
import json
import sys

# Ensure backend directory is in the Python path for local app imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Reconfigure stdout to use UTF-8 to support printing emojis in Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.agent import run_reminder_agent
from app.agent.execution_context import get_logs

def main():
    # Load reminders.yaml
    yaml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reminders.yaml")
    if not os.path.exists(yaml_path):
        print(f"Error: YAML configuration file not found at {yaml_path}")
        sys.exit(1)
        
    print(f"Loading configurations from {yaml_path}...")
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
    except Exception as e:
        print(f"Error parsing reminders.yaml: {str(e)}")
        sys.exit(1)
        
    reminders = config_data.get("reminders", [])
    if not reminders:
        print("No reminders found in the configurations.")
        sys.exit(0)
        
    print(f"Loaded {len(reminders)} configuration(s).")
    print("-" * 60)
    
    # Run the agent in simulator mode by default for testing
    os.environ["MOCK_LLM"] = "true"
    
    # Trigger the agent run
    result = run_reminder_agent(reminders)
    
    print("\n--- Agent Execution Logs ---")
    for log in get_logs():
        print(f"> {log}")
        
    print("\n--- Generated Consolidated Messages ---")
    messages = result.get("consolidated_messages", {})
    if not messages:
        print("No consolidated messages were generated.")
    else:
        for assignee, msg in messages.items():
            print(f"\n" + "=" * 50)
            print(f"Assignee: {assignee}")
            print("=" * 50)
            print(msg)
            print("=" * 50)

if __name__ == "__main__":
    main()

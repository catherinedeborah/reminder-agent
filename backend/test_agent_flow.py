import os
import sys
import argparse
import yaml
import json

# Ensure backend directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Reconfigure stdout to use UTF-8 to support printing emojis in Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.agent import run_reminder_agent
from app.agent.execution_context import get_logs

def parse_args():
    parser = argparse.ArgumentParser(description="Test Agent Flow and Sprint Day Reminders")
    parser.add_argument(
        "--user", 
        type=str, 
        help="Run and generate reminder only for a specific assignee (e.g. 'alice', 'bob', 'arunj', 'charlie', 'david')"
    )
    parser.add_argument(
        "--all", 
        action="store_true", 
        help="Run and generate alerts for all assignees in reminders.yaml"
    )
    parser.add_argument(
        "--sprint-day", 
        type=str, 
        choices=["start", "mid", "end", "near_end"], 
        default="mid",
        help="Force a specific sprint day state for testing"
    )
    parser.add_argument(
        "--real", 
        action="store_true", 
        help="Use real vLLM (OpenAI-compatible) endpoint instead of simulated fallback"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 1. Load reminders.yaml config
    yaml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reminders.yaml")
    if not os.path.exists(yaml_path):
        print(f"Error: reminders.yaml not found at {yaml_path}")
        sys.exit(1)
        
    with open(yaml_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
        
    reminders = config_data.get("reminders", [])
    if not reminders:
        print("Error: No reminder configurations found in reminders.yaml")
        sys.exit(1)
        
    # Get the sprint board config
    sprint_configs = [c for c in reminders if c.get("type") == "SPRINT_BOARD_ALERTS"]
    if not sprint_configs:
        print("Error: No SPRINT_BOARD_ALERTS configuration found in reminders.yaml")
        sys.exit(1)
        
    config = sprint_configs[0]
    
    # 2. Filter recipients if --user is specified
    if args.user:
        user_lower = args.user.lower()
        print(f"Filtering recipients list to user: '{user_lower}'")
        config["recipients"] = {
            "users": [user_lower],
            "groups": []
        }
    elif not args.all:
        print("Notice: Running for all users. You can target a single assignee using: --user [username]")

    # 3. Configure environment settings
    os.environ["FORCE_SPRINT_DAY"] = args.sprint_day
    if args.real:
        os.environ["MOCK_LLM"] = "false"
        print("Running in REAL Agent mode (using configured LLM / vLLM endpoint)...")
    else:
        os.environ["MOCK_LLM"] = "true"
        print("Running in simulated high-fidelity Agent mode...")
        
    print(f"Forced Sprint Day state: {args.sprint_day.upper()}")
    print("-" * 65)
    
    # 4. Trigger the agent
    result = run_reminder_agent([config])
    
    # 5. Output results
    print("\n" + "=" * 25 + " AGENT LOGS " + "=" * 25)
    for log in get_logs():
        print(f"> {log}")
        
    print("\n" + "=" * 20 + " GENERATED MESSAGES " + "=" * 20)
    messages = result.get("consolidated_messages", {})
    if not messages:
        print("No consolidated notifications were generated for the target recipients.")
    else:
        for assignee, msg in messages.items():
            print(f"\nTarget Assignee: {assignee.upper()}")
            print("-" * 50)
            print(msg)
            print("-" * 50)
            
    print("\n" + "=" * 62)

if __name__ == "__main__":
    main()

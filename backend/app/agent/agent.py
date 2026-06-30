import os
import json
import datetime
import traceback
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.config import settings
from app.agent.tools import get_all_tools, jira_tool, github_tool, plm_tool, kpi_tool, consolidation_tool, slack_notification_tool, email_notification_tool, knox_notification_tool
from app.agent.execution_context import add_log, init_context, get_logs, get_deliveries

# Try loading LangChain components, fallback to mock state if not present
try:
    from langchain_openai import ChatOpenAI
    from langchain.agents import AgentExecutor, create_openai_tools_agent
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    LANGCHAIN_AVAILABLE = True
except ImportError:
    try:
        from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        LANGCHAIN_AVAILABLE = True
    except ImportError:
        ChatOpenAI = None
        AgentExecutor = None
        create_openai_tools_agent = None
        ChatPromptTemplate = None
        MessagesPlaceholder = None
        LANGCHAIN_AVAILABLE = False

# Determine if we should mock the LLM agent or use the real vLLM endpoint
USE_MOCK_LLM = os.getenv("MOCK_LLM", "true").lower() == "true"

def read_prompt_file(file_name: str) -> str:
    """Reads a prompt configuration file from the prompts directory."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_dir, "prompts", file_name)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        print(f"Error reading prompt file {file_name}: {str(e)}")
    return ""

def calculate_sprint_days(start_date_str: str, end_date_str: str) -> dict:
    """
    Calculates sprint day state, current day number, and days left.
    Returns:
    {
      "state": "start" | "mid" | "end",
      "current_day": int,
      "days_left": int
    }
    """
    # Parse dates
    try:
        start_clean = start_date_str.replace("Z", "+00:00")
        end_clean = end_date_str.replace("Z", "+00:00")
        start_date = datetime.datetime.fromisoformat(start_clean)
        end_date = datetime.datetime.fromisoformat(end_clean)
    except Exception:
        try:
            start_date = datetime.datetime.strptime(start_date_str[:19], "%Y-%m-%dT%H:%M:%S")
            end_date = datetime.datetime.strptime(end_date_str[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            _now = datetime.datetime.now()
            start_date = _now - datetime.timedelta(days=5)
            end_date = _now + datetime.timedelta(days=9)

    # Check for manual test overrides
    force_day = os.getenv("FORCE_SPRINT_DAY", "").lower()
    today = datetime.datetime.now(start_date.tzinfo) if start_date.tzinfo else datetime.datetime.now()
    
    if force_day == "start":
        total_len = (end_date.date() - start_date.date()).days
        return {"state": "start", "current_day": 1, "days_left": total_len}
    elif force_day == "end":
        total_len = (end_date.date() - start_date.date()).days
        return {"state": "end", "current_day": total_len + 1, "days_left": 0}
    elif force_day == "mid":
        return {"state": "mid", "current_day": 5, "days_left": 9}
    elif force_day == "near_end":
        return {"state": "mid", "current_day": 12, "days_left": 2}
        
    # Normal calculations
    days_left = (end_date.date() - today.date()).days
    
    if today.date() <= start_date.date():
        total_len = (end_date.date() - start_date.date()).days
        return {"state": "start", "current_day": 1, "days_left": total_len}
    elif today.date() >= end_date.date():
        total_len = (end_date.date() - start_date.date()).days
        return {"state": "end", "current_day": total_len + 1, "days_left": 0}
    else:
        current_day = (today.date() - start_date.date()).days + 1
        return {"state": "mid", "current_day": current_day, "days_left": days_left}

def run_agent_simulation(configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    High-fidelity simulator that runs the Reminder Agent reasoning loop offline.
    """
    add_log("Starting high-fidelity Reminder Agent Simulation...")
    
    collected_alerts = []
    active_sprint_info = MOCK_ACTIVE_SPRINT
    
    # 1. Fetch Sprint Info from Jira if board_id is provided
    # Standardize sprint dates for simulation
    sprint_state = calculate_sprint_days(active_sprint_info["startDate"], active_sprint_info["endDate"])
    add_log(f"Sprint Day State calculated: '{sprint_state['state'].upper()}' (Day: {sprint_state['current_day']}, Days left: {sprint_state['days_left']})")
    
    for config in configs:
        name = config.get("name", "Unnamed")
        alert_type = config.get("type")
        tool_hints = config.get("tool_hints", [])
        board_id = config.get("board_id")
        
        add_log(f"Processing config: '{name}' (Type: {alert_type})")
        
        # Verify if it is a sprint Board alerts config
        if alert_type == "SPRINT_BOARD_ALERTS" or board_id is not None:
            # Check toggles for enabled categories
            start_enabled = config.get("sprint_start_enabled", True)
            mid_enabled = config.get("sprint_mid_enabled", True)
            end_enabled = config.get("sprint_end_enabled", True)
            
            # Filter based on sprint day state
            if sprint_state["state"] == "start" and not start_enabled:
                add_log(f"Config '{name}': Sprint start day reminders are disabled. Skipping.")
                continue
            elif sprint_state["state"] == "mid" and not mid_enabled:
                add_log(f"Config '{name}': Sprint mid day reminders are disabled. Skipping.")
                continue
            elif sprint_state["state"] == "end" and not end_enabled:
                add_log(f"Config '{name}': Sprint closure end day reminders are disabled. Skipping.")
                continue
                
            # Fetch Jira Board sprint issues
            jql = f"board_id = {board_id or 123}"
            raw_out = jira_tool.invoke({"jql": jql})
            issues = json.loads(raw_out)
            
            # Map into collected alerts format
            for issue in issues:
                collected_alerts.append({
                    "raw_item": issue,
                    "source_type": "jira",
                    "alert_type": alert_type,
                    "category": "sprint_task"
                })
                
            # Include a dummy task for DAVID (David has no sprint tasks, triggers missing stories check)
            # Find recipients list to see if david is included
            recipients = config.get("recipients", {})
            users = recipients.get("users", [])
            if "david" in users:
                # david will be processed via aggregation (has zero tasks)
                # We register a placeholder for David in the normalizer to ensure David's key is grouped
                collected_alerts.append({
                    "raw_item": {"assignee": "david", "key": "", "status": "None", "project": ""},
                    "source_type": "jira",
                    "alert_type": alert_type,
                    "category": "sprint_task"
                })
                
        # Handle other individual alert types
        else:
            if "JiraTool" in tool_hints:
                # Basic mock check
                raw_out = jira_tool.invoke({"jql": "status = 'In Progress'"})
                issues = json.loads(raw_out)
                for issue in issues:
                    collected_alerts.append({
                        "raw_item": issue,
                        "source_type": "jira",
                        "alert_type": alert_type,
                        "category": "other"
                    })
            if "PLMTool" in tool_hints or alert_type == "PLM_TAT_BREACH":
                raw_out = plm_tool.invoke({"tat_breached": True})
                items = json.loads(raw_out)
                for item in items:
                    collected_alerts.append({
                        "raw_item": item,
                        "source_type": "plm",
                        "alert_type": alert_type,
                        "category": "stale_status"
                    })
                    
    if not collected_alerts:
        add_log("No active alerts collected during simulation data fetch.")
        return {"status": "SUCCESS", "message": "No notifications generated."}
        
    add_log(f"Fetched {len(collected_alerts)} items. Consolidating output alerts...")
    
    # Resolve target templates dynamically based on sprint state
    all_channels = set()
    for config in configs:
        all_channels.update(config.get("channels", ["slack"]))
        
    consolidated_results = {}
    
    for channel in all_channels:
        # Determine correct Jinja2 template file to load
        # If it's a sprint board configuration, select start, mid, or end template
        sprint_template_map = {
            "start": "sprint_start",
            "mid": "sprint_mid_consolidated",
            "end": "sprint_closure"
        }
        
        # Default template name mapping
        target_template_name = sprint_template_map.get(sprint_state["state"], "sprint_mid_consolidated")
        
        # If we have a single non-sprint alert (e.g. PLM), map template
        if len(configs) == 1 and configs[0].get("type") == "PLM_TAT_BREACH":
            target_template_name = "plm_tat_breach"
            
        raw_data_str = json.dumps(collected_alerts)
        consol_out = consolidation_tool.invoke({
            "raw_data_json": raw_data_str,
            "template_string": target_template_name,
            "channel": channel,
            "days_left": str(sprint_state["days_left"])
        })
        
        channel_results = json.loads(consol_out)
        if "error" in channel_results:
            add_log(f"Consolidation Tool Error: {channel_results['error']}")
            continue
            
        consolidated_results[channel] = channel_results
        
        # Deliver notifications
        for assignee, msg in channel_results.items():
            # Check if this recipient was configured in the configs
            # (Allows test runs to run per assignee)
            if channel == "slack":
                slack_notification_tool.invoke({"recipient": f"@{assignee}", "message": msg})
            elif channel == "email":
                email_notification_tool.invoke({"recipient": f"{assignee}@company.com", "message": msg})
            elif channel == "knox":
                knox_notification_tool.invoke({"recipient": assignee, "message": msg})
                
    add_log("Agent simulation complete!")
    return {
        "status": "SUCCESS",
        "message": "Orchestrated configurations consolidated successfully.",
        "consolidated_messages": consolidated_results.get("slack", consolidated_results.get("email", {}))
    }

def run_reminder_agent(configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Executes the Reminder Agent loop. Falls back to simulator if vLLM is not available
    or if MOCK_LLM is enabled.
    """
    init_context()
    
    if USE_MOCK_LLM or not LANGCHAIN_AVAILABLE:
        if not LANGCHAIN_AVAILABLE:
            add_log("LangChain library imports are not fully available. Running in high-fidelity simulator mode.")
        return run_agent_simulation(configs)
        
    try:
        # 1. Load external system and user prompt templates
        system_prompt = read_prompt_file("system_prompt.txt")
        user_prompt_template = read_prompt_file("user_prompt.txt")
        
        if not system_prompt or not user_prompt_template:
            add_log("Error loading system or user prompt files from disk. Falling back to simulator.")
            return run_agent_simulation(configs)
            
        # 2. Query Active Sprint day status (check first config with board ID)
        sprint_days_context = "Standard execution day"
        days_remaining = 14
        
        sprint_configs = [c for c in configs if c.get("board_id") is not None]
        if sprint_configs:
            board_id = sprint_configs[0]["board_id"]
            # Call jira tool mock/real to get agile board active sprint dates
            raw_sprints = jira_tool.invoke({"jql": f"board_id = {board_id}"})
            try:
                # We can mock calculate sprint day from first result
                issues_list = json.loads(raw_sprints)
                # Find sprint ID and start/end dates
                # To simulate correctly, calculate relative to Mock active dates
                active_sprint_info = MOCK_ACTIVE_SPRINT
                sprint_state = calculate_sprint_days(active_sprint_info["startDate"], active_sprint_info["endDate"])
                days_remaining = sprint_state["days_left"]
                sprint_days_context = f"Sprint State: {sprint_state['state'].upper()}, Day Number: {sprint_state['current_day']}, Days left: {sprint_state['days_left']}"
            except Exception:
                pass
                
        # 3. Create OpenAI client pointing to vLLM
        llm = ChatOpenAI(
            openai_api_base=settings.VLLM_API_BASE,
            openai_api_key=settings.VLLM_API_KEY,
            model_name=settings.MODEL_NAME,
            temperature=0.0,
            max_retries=1
        )
        
        tools = get_all_tools()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", user_prompt_template),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_openai_tools_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        
        # Inject context variables into user prompt
        formatted_user_prompt = user_prompt_template.format(
            current_date=datetime.datetime.now().isoformat(),
            sprint_day_context=sprint_days_context,
            configurations=json.dumps(configs, indent=2)
        )
        
        add_log("Starting LangChain Deep Agent Executor...")
        response = agent_executor.invoke({
            "current_date": datetime.datetime.now().isoformat(),
            "sprint_day_context": sprint_days_context,
            "configurations": json.dumps(configs, indent=2),
            "agent_scratchpad": []
        })
        add_log("Agent Executor execution finished.")
        
        deliveries = get_deliveries()
        consolidated_messages = {}
        for d in deliveries:
            consolidated_messages[d["recipient"]] = d["message"]
            
        return {
            "status": "SUCCESS",
            "message": response.get("output", "Agent ran successfully."),
            "consolidated_messages": consolidated_messages
        }
        
    except Exception as e:
        add_log(f"LangChain Deep Agent Execution failed: {str(e)}")
        add_log(traceback.format_exc())
        add_log("Falling back to high-fidelity agent simulation...")
        return run_agent_simulation(configs)

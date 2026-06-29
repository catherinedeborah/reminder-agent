import os
import json
import traceback
from typing import List, Dict, Any
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
from app.config import settings
from app.agent.tools import get_all_tools, jira_tool, github_tool, plm_tool, kpi_tool, consolidation_tool, slack_notification_tool, email_notification_tool, knox_notification_tool
from app.agent.execution_context import add_log, init_context, get_logs, get_deliveries

# Determine if we should mock the LLM agent or use the real vLLM endpoint
USE_MOCK_LLM = os.getenv("MOCK_LLM", "true").lower() == "true"

def run_agent_simulation(configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    High-fidelity simulator that runs the exact Agent reasoning loop:
    1. For each active config, run the appropriate data tools.
    2. Collect and structure the raw items into the standard array.
    3. Invoke ConsolidationTool to group, normalize, deduplicate, and render templates.
    4. Invoke notification tools to deliver messages.
    """
    add_log("Starting high-fidelity Reminder Agent Simulation...")
    
    collected_alerts = []
    
    for config in configs:
        name = config.get("name", "Unnamed")
        alert_type = config.get("type")
        tool_hints = config.get("tool_hints", [])
        metadata = config.get("metadata_json", {})
        project_keys = metadata.get("project_keys", ["ABC", "XYZ", "DEF"])
        
        add_log(f"Processing config: '{name}' (Type: {alert_type})")
        
        # Determine JQL queries or tool parameters based on alert type
        if "JiraTool" in tool_hints or alert_type in ["SPRINT_MID_PROGRESS_CHECK", "TASK_CREATION_REMINDER", "SUBTASK_CREATION_REMINDER", "STATUS_UPDATE_REMINDER"]:
            # Perform queries for each project key
            for proj in project_keys:
                if alert_type == "SUBTASK_CREATION_REMINDER":
                    jql = f"project = '{proj}' AND status = 'In Progress' AND subtasks is empty"
                    raw_out = jira_tool.invoke({"jql": jql})
                    issues = json.loads(raw_out)
                    for issue in issues:
                        collected_alerts.append({
                            "raw_item": issue,
                            "source_type": "jira",
                            "alert_type": alert_type,
                            "category": "missing_subtasks"
                        })
                elif alert_type == "STATUS_UPDATE_REMINDER":
                    jql = f"project = '{proj}' AND status = 'In Progress' AND updated <= -7d"
                    raw_out = jira_tool.invoke({"jql": jql})
                    issues = json.loads(raw_out)
                    for issue in issues:
                        collected_alerts.append({
                            "raw_item": issue,
                            "source_type": "jira",
                            "alert_type": alert_type,
                            "category": "stale_status"
                        })
                elif alert_type == "SPRINT_MID_PROGRESS_CHECK":
                    jql = f"project = '{proj}' AND status = 'To Do'"
                    raw_out = jira_tool.invoke({"jql": jql})
                    issues = json.loads(raw_out)
                    for issue in issues:
                        collected_alerts.append({
                            "raw_item": issue,
                            "source_type": "jira",
                            "alert_type": alert_type,
                            "category": "mid_progress_issues"
                        })
                elif alert_type == "TASK_CREATION_REMINDER":
                    # Simulating checking if assignee has no tasks in a project
                    # In mock data, let's trigger it for users who have no tasks in DEF project
                    jql = f"project = '{proj}'"
                    raw_out = jira_tool.invoke({"jql": jql})
                    issues = json.loads(raw_out)
                    # Let's say if we get fewer than 2 issues for project DEF, we create a missing task alert
                    if proj == "DEF" and len(issues) < 2:
                        collected_alerts.append({
                            "raw_item": {"key": "DEF-NEW", "summary": "Setup Project Backlog", "status": "Not Created", "assignee": "bob", "project": "DEF", "updated_at": "", "sprint_id": "Sprint-1"},
                            "source_type": "jira",
                            "alert_type": alert_type,
                            "category": "missing_tasks"
                        })
        
        if "GitHubTool" in tool_hints or alert_type in ["KPI_COMMITS", "KPI_CODE_REVIEWS"]:
            # Query github commits or reviews
            q_type = "commits" if alert_type == "KPI_COMMITS" else "pull_requests"
            raw_out = github_tool.invoke({"query_type": q_type})
            commits = json.loads(raw_out)
            for item in commits:
                collected_alerts.append({
                    "raw_item": item,
                    "source_type": "github",
                    "alert_type": alert_type,
                    "category": "other"
                })
                
        if "PLMTool" in tool_hints or alert_type in ["PLM_ASSIGNED_ITEMS", "PLM_TAT_BREACH"]:
            # Query PLM tool
            tat = True if alert_type == "PLM_TAT_BREACH" else None
            raw_out = plm_tool.invoke({"tat_breached": tat})
            items = json.loads(raw_out)
            for item in items:
                collected_alerts.append({
                    "raw_item": item,
                    "source_type": "plm",
                    "alert_type": alert_type,
                    "category": "stale_status" if item.get("tat_breach") else "other"
                })

        if "KPITool" in tool_hints or alert_type in ["KPI_JIRA_CLOSURES"]:
            raw_out = kpi_tool.invoke({"metric": "jira_closures"})
            items = json.loads(raw_out)
            for item in items:
                collected_alerts.append({
                    "raw_item": item,
                    "source_type": "kpi",
                    "alert_type": alert_type,
                    "category": "other"
                })
                
    if not collected_alerts:
        add_log("No alerts collected during data fetch stage.")
        return {"status": "SUCCESS", "message": "No alerts found to deliver."}

    add_log(f"Fetched {len(collected_alerts)} raw issues. Consolidating alerts...")
    
    # We consolidate the alerts per channel.
    # Typically, the active configs define which channels are used.
    # Let's inspect the channels configured.
    all_channels = set()
    for config in configs:
        all_channels.update(config.get("channels", ["slack"]))
    
    # Use the template from the first combinable config (or a fallback)
    template_str = configs[0].get("template_string") if configs else ""
    if not template_str:
        # Fallback template
        template_str = """Hi {{ assignee }},
Here's your consolidated sprint update:
🔴 Tasks Missing Subtasks:
{% for item in missing_subtasks -%}
- {{ make_link(item.system, item.issue_key) }}: {{ item.summary }}
{% else -%}
- None
{% endfor %}
🟡 Tasks Without Recent Updates:
{% for item in stale_status -%}
- {{ make_link(item.system, item.issue_key) }}: {{ item.summary }}
{% else -%}
- None
{% endfor %}
🔵 Mid Sprint Attention Needed:
{% for item in mid_progress_issues -%}
- {{ make_link(item.system, item.issue_key) }}: {{ item.summary }}
{% else -%}
- None
{% endfor %}
⚪ Tasks Not Created:
{% for item in missing_tasks -%}
- {{ make_link(item.system, item.issue_key) }}: {{ item.summary }}
{% else -%}
- None
{% endfor %}
Summary:
- Total Issues: {{ total_issues }}
- Action Required: {{ action_required }}
Please take action.
"""

    consolidated_results = {}
    
    for channel in all_channels:
        # Invoke consolidation tool for this channel
        raw_data_str = json.dumps(collected_alerts)
        consol_out = consolidation_tool.invoke({
            "raw_data_json": raw_data_str,
            "template_string": template_str,
            "channel": channel
        })
        
        channel_results = json.loads(consol_out)
        if "error" in channel_results:
            add_log(f"Consolidation error: {channel_results['error']}")
            continue
            
        consolidated_results[channel] = channel_results
        
        # Deliver notifications for this channel
        for assignee, msg in channel_results.items():
            if channel == "slack":
                slack_notification_tool.invoke({"recipient": f"@{assignee}", "message": msg})
            elif channel == "email":
                email_notification_tool.invoke({"recipient": f"{assignee}@company.com", "message": msg})
            elif channel == "knox":
                knox_notification_tool.invoke({"recipient": assignee, "message": msg})

    add_log("Agent simulation complete!")
    return {
        "status": "SUCCESS",
        "message": f"Processed {len(configs)} configs, consolidated notifications sent successfully.",
        "consolidated_messages": consolidated_results.get("slack", consolidated_results.get("email", {}))
    }

def run_reminder_agent(configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Executes the Reminder Agent loop. Falls back to simulator if vLLM is not available.
    """
    init_context()
    
    if USE_MOCK_LLM or not LANGCHAIN_AVAILABLE:
        if not LANGCHAIN_AVAILABLE:
            add_log("LangChain library imports are not fully available. Running in high-fidelity simulator mode.")
        return run_agent_simulation(configs)
        
    try:
        # Create OpenAI client pointing to vLLM
        llm = ChatOpenAI(
            openai_api_base=settings.VLLM_API_BASE,
            openai_api_key=settings.VLLM_API_KEY,
            model_name=settings.MODEL_NAME,
            temperature=0.0,
            max_retries=1
        )
        
        tools = get_all_tools()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a highly efficient autonomous Reminder Agent.
Your goal is to inspect the active reminder configurations, determine which tools to run, retrieve data, consolidate the alerts to avoid alert fatigue, and send the final consolidated messages.

You must follow these rules:
1. Inspect the configuration details provided in the input.
2. For each configuration, run the appropriate data tools (jira_tool, github_tool, plm_tool, kpi_tool) with relevant filters. You may need to run multiple queries or multiple tools.
3. Once all data is retrieved, format it into a list of alerts where each item is:
   {"raw_item": <item_dict>, "source_type": "jira"|"github"|"plm", "alert_type": "<CONFIG_TYPE>", "category": "<optional_category>"}
4. Pass this complete list, the config template string, and the target channel to the consolidation_tool.
5. The consolidation_tool will return a JSON dictionary mapping assignees to their formatted messages.
6. For each assignee and message in that dictionary, invoke the appropriate notification tool(s) (slack_notification_tool, email_notification_tool, knox_notification_tool) based on the channels configured in the reminder configurations.
7. Return a summary of your actions and the number of notifications sent.
"""),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_openai_tools_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        
        input_payload = f"Configurations: {json.dumps(configs, indent=2)}"
        add_log("Starting LangChain Deep Agent Executor...")
        
        response = agent_executor.invoke({"input": input_payload})
        add_log("Agent Executor execution finished.")
        
        # Extract consolidated messages from execution context
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

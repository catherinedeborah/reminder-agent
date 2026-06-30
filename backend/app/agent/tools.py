import json
import re
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from app.config import settings
from app.mock_data import MOCK_JIRA_ISSUES, MOCK_GITHUB_DATA, MOCK_PLM_ITEMS, MOCK_ACTIVE_SPRINT
from app.services.aggregation import run_aggregation_pipeline
from app.agent.execution_context import add_log, add_delivery

# Try loading tool decorator from langchain_core, fallback to dummy if not present
try:
    from langchain_core.tools import tool
except ImportError:
    def tool(func):
        """Fallback mock tool decorator when langchain_core is not installed."""
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper.invoke = lambda args: func(**args) if isinstance(args, dict) else func(args)
        wrapper.name = func.__name__
        wrapper.description = func.__doc__
        return wrapper

@tool
def jira_tool(jql: str) -> str:
    """
    Queries Jira Agile REST API (or falls back to mock issues if no PAT token is set).
    Supported operations:
    - If JQL contains 'board_id = <id>', fetches all issues in the active sprint of the agile board.
    - If JQL contains standard status or assignee filters, filters matches accordingly.
    """
    add_log(f"JiraTool invoked. JQL query: '{jql}'")
    
    # Check if real credentials are set
    has_jira_creds = bool(settings.JIRA_BASE_URL and settings.JIRA_PAT_TOKEN and "your_jira" not in settings.JIRA_PAT_TOKEN)
    
    board_id_match = re.search(r"board_id\s*=\s*(\d+)", jql, re.IGNORECASE)
    
    if has_jira_creds:
        base_url = settings.JIRA_BASE_URL.rstrip("/")
        headers = {
            "Authorization": f"Bearer {settings.JIRA_PAT_TOKEN}",
            "Accept": "application/json"
        }
        
        try:
            if board_id_match:
                board_id = board_id_match.group(1)
                add_log(f"JiraTool: Fetching active sprint for board {board_id} from API...")
                
                # 1. Fetch active sprint on the agile board
                sprint_url = f"{base_url}/rest/agile/1.0/board/{board_id}/sprint?state=active"
                sprint_res = requests.get(sprint_url, headers=headers, timeout=10)
                sprint_res.raise_for_status()
                sprint_data = sprint_res.json()
                
                sprints = sprint_data.get("values", [])
                if not sprints:
                    add_log(f"JiraTool warning: No active sprints found on board {board_id}")
                    return json.dumps([])
                    
                active_sprint = sprints[0]
                sprint_id = active_sprint["id"]
                add_log(f"JiraTool: Found active sprint '{active_sprint['name']}' (ID: {sprint_id})")
                
                # 2. Fetch all issues in the active sprint, with required fields (subtasks, worklog, timespent)
                issues_url = f"{base_url}/rest/agile/1.0/sprint/{sprint_id}/issue?fields=summary,status,assignee,subtasks,worklog,timespent,updated,created,issuetype"
                issues_res = requests.get(issues_url, headers=headers, timeout=10)
                issues_res.raise_for_status()
                issues_data = issues_res.json()
                
                raw_issues = issues_data.get("issues", [])
                add_log(f"JiraTool: Retreived {len(raw_issues)} issues from active sprint via agile API.")
                
                # 3. Parse/Normalize into standard structure
                parsed_issues = []
                for issue in raw_issues:
                    fields = issue.get("fields", {})
                    
                    # Resolve assignee
                    assignee_obj = fields.get("assignee")
                    assignee_name = assignee_obj.get("name", assignee_obj.get("displayName", "unassigned")) if assignee_obj else "unassigned"
                    
                    # Resolve subtasks list
                    subtasks_raw = fields.get("subtasks", [])
                    subtasks_list = []
                    for sub in subtasks_raw:
                        sub_fields = sub.get("fields", {})
                        subtasks_list.append({
                            "key": sub.get("key"),
                            "summary": sub_fields.get("summary", ""),
                            "status": sub_fields.get("status", {}).get("name", "To Do")
                        })
                        
                    # Resolve worklogs list
                    worklog_raw = fields.get("worklog", {}).get("worklogs", [])
                    worklogs_list = []
                    for wl in worklog_raw:
                        worklogs_list.append({
                            "timeSpentSeconds": wl.get("timeSpentSeconds", 0),
                            "created": wl.get("created", "")
                        })
                        
                    issue_type = fields.get("issuetype", {}).get("name", "Story")
                    is_subtask = fields.get("issuetype", {}).get("subtask", False)
                    
                    parsed_issues.append({
                        "key": issue.get("key"),
                        "summary": fields.get("summary", ""),
                        "status": fields.get("status", {}).get("name", "To Do"),
                        "assignee": assignee_name,
                        "updated_at": fields.get("updated", ""),
                        "has_subtasks": len(subtasks_list) > 0,
                        "subtasks": subtasks_list,
                        "worklogs": worklogs_list,
                        "timespent": fields.get("timespent", 0),
                        "project": issue.get("key", "").split("-")[0],
                        "created_at": fields.get("created", ""),
                        "sprint_id": str(sprint_id),
                        "board_id": int(board_id),
                        "is_subtask": is_subtask,
                        "issuetype": issue_type
                    })
                return json.dumps(parsed_issues, indent=2)
            else:
                # Fallback to JQL search if JQL does not specify board_id
                add_log(f"JiraTool: Running JQL search: {jql}")
                search_url = f"{base_url}/rest/api/2/search"
                payload = {
                    "jql": jql,
                    "fields": ["summary", "status", "assignee", "subtasks", "worklog", "timespent", "updated"]
                }
                res = requests.post(search_url, json=payload, headers=headers, timeout=10)
                res.raise_for_status()
                data = res.json()
                # Parse search results
                parsed_issues = []
                for issue in data.get("issues", []):
                    # (Standard JQL parser - similar parsing logic)
                    fields = issue.get("fields", {})
                    assignee_obj = fields.get("assignee")
                    assignee_name = assignee_obj.get("name", "unassigned") if assignee_obj else "unassigned"
                    parsed_issues.append({
                        "key": issue.get("key"),
                        "summary": fields.get("summary", ""),
                        "status": fields.get("status", {}).get("name", "To Do"),
                        "assignee": assignee_name,
                        "updated_at": fields.get("updated", ""),
                        "has_subtasks": len(fields.get("subtasks", [])) > 0,
                        "subtasks": fields.get("subtasks", []),
                        "worklogs": fields.get("worklog", {}).get("worklogs", []),
                        "timespent": fields.get("timespent", 0),
                        "project": issue.get("key", "").split("-")[0]
                    })
                return json.dumps(parsed_issues, indent=2)
        except Exception as e:
            add_log(f"JiraTool API Error: {str(e)}. Falling back to mock database.")
            
    # Mock data fallback:
    results = MOCK_JIRA_ISSUES.copy()
    
    if board_id_match:
        board_id = int(board_id_match.group(1))
        results = [x for x in results if x.get("board_id") == board_id]
        add_log(f"JiraTool (Mock): Filtered by board_id={board_id}. Results: {len(results)}")
        return json.dumps(results, indent=2)
        
    # Standard filter evaluations
    assignee_match = re.search(r"assignee\s*=\s*['\"]?([a-zA-Z0-9_\-]+)['\"]?", jql, re.IGNORECASE)
    if assignee_match:
        assignee = assignee_match.group(1).lower()
        results = [x for x in results if x["assignee"].lower() == assignee]
        
    status_match = re.search(r"status\s*=\s*['\"]?([a-zA-Z0-9_\-\s]+)['\"]?", jql, re.IGNORECASE)
    if status_match:
        status = status_match.group(1).lower().strip()
        results = [x for x in results if x["status"].lower() == status]

    project_match = re.search(r"project\s*=\s*['\"]?([a-zA-Z0-9_\-]+)['\"]?", jql, re.IGNORECASE)
    if project_match:
        project = project_match.group(1).lower()
        results = [x for x in results if x["project"].lower() == project]

    return json.dumps(results, indent=2)

@tool
def github_tool(query_type: str, author: Optional[str] = None) -> str:
    """
    Queries GitHub repository metadata.
    Parameters:
    - query_type: 'commits' (list commits) or 'pull_requests' (list pull requests)
    - author: filter results by author username (optional)
    """
    add_log(f"GitHubTool invoked with query_type: {query_type}, author: {author}")
    results = MOCK_GITHUB_DATA.copy()
    if author:
        results = [x for x in results if x["author"].lower() == author.lower()]
    
    if query_type == "pull_requests":
        results = [x for x in results if "pr_id" in x and x.get("status") == "Open"]
    elif query_type == "commits":
        results = [x for x in results if "commit_hash" in x]
        
    return json.dumps(results, indent=2)

@tool
def plm_tool(assignee: Optional[str] = None, status: Optional[str] = None, tat_breached: Optional[bool] = None) -> str:
    """
    Queries PLM database for part approvals and TAT breaches.
    """
    add_log(f"PLMTool invoked with assignee: {assignee}, status: {status}, tat_breached: {tat_breached}")
    results = MOCK_PLM_ITEMS.copy()
    if assignee:
        results = [x for x in results if x["assignee"].lower() == assignee.lower()]
    if status:
        results = [x for x in results if x["status"].lower() == status.lower()]
    if tat_breached is not None:
        breached_val = True if str(tat_breached).lower() in ("true", "1") else False
        results = [x for x in results if x["tat_bre_ach" if "tat_bre_ach" in x else "tat_breach"] == breached_val]
        
    return json.dumps(results, indent=2)

@tool
def kpi_tool(metric: str, assignee: Optional[str] = None) -> str:
    """
    Retrieves performance KPI metrics.
    """
    add_log(f"KPITool invoked with metric: {metric}, assignee: {assignee}")
    kpis = []
    
    if metric == "jira_closures":
        closures = {}
        for issue in MOCK_JIRA_ISSUES:
            if issue["status"].lower() == "done":
                ass = issue["assignee"]
                closures[ass] = closures.get(ass, 0) + 1
        for ass, count in closures.items():
            if not assignee or ass.lower() == assignee.lower():
                kpis.append({"assignee": ass, "metric": "jira_closures", "value": count})
                
    elif metric == "commits":
        commit_counts = {}
        for commit in MOCK_GITHUB_DATA:
            ass = commit["author"]
            commit_counts[ass] = commit_counts.get(ass, 0) + 1
        for ass, count in commit_counts.items():
            if not assignee or ass.lower() == assignee.lower():
                kpis.append({"assignee": ass, "metric": "commits", "value": count})
                
    return json.dumps(kpis, indent=2)

@tool
def consolidation_tool(raw_data_json: str, template_string: str, channel: str, days_left: Optional[int] = None) -> str:
    """
    Aggregates, normalizes, deduplicates, groups, and renders alerts.
    Parameters:
    - raw_data_json: A JSON-string list of alerts.
    - template_string: Jinja2 template content or file name.
    - channel: 'slack', 'email', or 'knox'.
    - days_left: sprint days remaining.
    """
    add_log(f"ConsolidationTool: Consolidating items for channel: {channel}. Days remaining: {days_left}")
    try:
        data = json.loads(raw_data_json)
        # Parse days_left into integer if supplied
        dl_val = int(days_left) if days_left is not None else None
        results = run_aggregation_pipeline(data, template_string, channel, days_left=dl_val)
        return json.dumps(results, indent=2)
    except Exception as e:
        add_log(f"Error in ConsolidationTool: {str(e)}")
        return json.dumps({"error": str(e)})

@tool
def slack_notification_tool(recipient: str, message: str) -> str:
    """
    Sends a consolidated reminder message to a user or channel via Slack.
    """
    add_log(f"SlackNotificationTool: Post requested for recipient '{recipient}'")
    
    has_slack_creds = bool(settings.SLACK_BOT_TOKEN and "your-slack" not in settings.SLACK_BOT_TOKEN)
    
    if has_slack_creds:
        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Clean user handle if formatted as '@username'
        channel_target = recipient
        if channel_target.startswith("@"):
            # Can be matched to user IDs in production. For now, post directly to handle or look up
            pass
            
        payload = {
            "channel": channel_target,
            "text": message
        }
        
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            res.raise_for_status()
            res_data = res.json()
            if not res_data.get("ok"):
                add_log(f"SlackNotificationTool Warning: Slack API rejected message: {res_data.get('error')}")
                return f"FAILED: {res_data.get('error')}"
            add_log(f"SlackNotificationTool: Successfully posted message to Slack recipient '{recipient}'")
            add_delivery("slack", recipient, message)
            return "SUCCESS"
        except Exception as e:
            add_log(f"SlackNotificationTool: Network error: {str(e)}")
            return f"FAILED: {str(e)}"
            
    # Mock fallback
    add_delivery("slack", recipient, message)
    return "SUCCESS"

@tool
def email_notification_tool(recipient: str, message: str) -> str:
    """
    Sends a consolidated reminder message to a user via Email SMTP.
    """
    add_log(f"EmailNotificationTool: Mail requested for recipient '{recipient}'")
    
    has_smtp_creds = bool(settings.SMTP_HOST and "your-email" not in settings.SMTP_USER)
    
    if has_smtp_creds:
        msg = MIMEMultipart()
        msg['From'] = settings.SMTP_FROM or settings.SMTP_USER
        msg['To'] = recipient
        msg['Subject'] = "Sprint Agile Status Alert Notification"
        
        # If html is inside message, attach as html, else plaintext
        msg_type = 'html' if "<a href=" in message or "<div" in message or "<html" in message else 'plain'
        msg.attach(MIMEText(message, msg_type, 'utf-8'))
        
        try:
            add_log(f"EmailNotificationTool: Connecting to SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT}...")
            server = smtplib.SMTP(settings.SMTP_HOST, int(settings.SMTP_PORT))
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
            server.close()
            
            add_log(f"EmailNotificationTool: Successfully sent email to '{recipient}'")
            add_delivery("email", recipient, message)
            return "SUCCESS"
        except Exception as e:
            add_log(f"EmailNotificationTool Error: SMTP failure: {str(e)}")
            return f"FAILED: {str(e)}"
            
    # Mock fallback
    add_delivery("email", recipient, message)
    return "SUCCESS"

@tool
def knox_notification_tool(recipient: str, message: str) -> str:
    """
    Sends a consolidated reminder push notification to a user via Knox.
    """
    add_log(f"KnoxNotificationTool invoked for recipient: {recipient}")
    add_delivery("knox", recipient, message)
    return "SUCCESS"

def get_all_tools() -> List[Any]:
    return [
        jira_tool,
        github_tool,
        plm_tool,
        kpi_tool,
        consolidation_tool,
        slack_notification_tool,
        email_notification_tool,
        knox_notification_tool
    ]

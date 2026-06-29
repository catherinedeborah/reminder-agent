import json
import re
from typing import List, Dict, Any, Optional

try:
    from langchain_core.tools import tool
except ImportError:
    def tool(func):
        """Fallback mock tool decorator when langchain_core is not installed."""
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        # Mock .invoke behavior for compatibility
        wrapper.invoke = lambda args: func(**args) if isinstance(args, dict) else func(args)
        wrapper.name = func.__name__
        wrapper.description = func.__doc__
        return wrapper
        
from app.mock_data import MOCK_JIRA_ISSUES, MOCK_GITHUB_DATA, MOCK_PLM_ITEMS
from app.services.aggregation import run_aggregation_pipeline
from app.agent.execution_context import add_log, add_delivery

@tool
def jira_tool(jql: str) -> str:
    """
    Executes a JQL (Jira Query Language) query against the Jira database and returns matching issues.
    Use this for sprinting progress, task, subtask, and status update checks.
    Supported JQL clauses:
    - assignee = 'username'
    - status = 'status_name' (e.g. 'In Progress', 'To Do', 'Done')
    - project = 'project_key'
    - subtasks is empty / has_subtasks = false (finds issues missing subtasks)
    - updated <= -7d / updatedDate < '-7d' (finds stale issues not updated in 7 days)
    """
    add_log(f"JiraTool invoked with JQL: {jql}")
    results = MOCK_JIRA_ISSUES.copy()
    
    # Check assignee
    assignee_match = re.search(r"assignee\s*=\s*['\"]?([a-zA-Z0-9_\-]+)['\"]?", jql, re.IGNORECASE)
    if assignee_match:
        assignee = assignee_match.group(1).lower()
        results = [x for x in results if x["assignee"].lower() == assignee]
        add_log(f"Filtered by assignee={assignee}. Remaining: {len(results)}")
        
    # Check status
    status_match = re.search(r"status\s*=\s*['\"]?([a-zA-Z0-9_\-\s]+)['\"]?", jql, re.IGNORECASE)
    if status_match:
        status = status_match.group(1).lower().strip()
        results = [x for x in results if x["status"].lower() == status]
        add_log(f"Filtered by status={status}. Remaining: {len(results)}")

    # Check project
    project_match = re.search(r"project\s*=\s*['\"]?([a-zA-Z0-9_\-]+)['\"]?", jql, re.IGNORECASE)
    if project_match:
        project = project_match.group(1).lower()
        results = [x for x in results if x["project"].lower() == project]
        add_log(f"Filtered by project={project}. Remaining: {len(results)}")

    # Check for missing subtasks (has_subtasks = False)
    if "subtasks" in jql.lower() and ("empty" in jql.lower() or "false" in jql.lower() or "no" in jql.lower() or "count = 0" in jql.lower() or "count = 0" in jql.replace(" ", "")):
        results = [x for x in results if not x.get("has_subtasks", True)]
        add_log(f"Filtered for missing subtasks. Remaining: {len(results)}")

    # Check for stale issues (updated_at <= 7 days ago)
    if "updated" in jql.lower() and ("7d" in jql.lower() or "7" in jql.lower()):
        import datetime
        seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        results = [x for x in results if datetime.datetime.fromisoformat(x["updated_at"]) < seven_days_ago]
        add_log(f"Filtered for stale issues (>7d). Remaining: {len(results)}")
        
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
    Queries Product Lifecycle Management (PLM) database for part approvals and Turnaround Time (TAT) breaches.
    Parameters:
    - assignee: username to filter by (optional)
    - status: PLM item status to filter by (optional)
    - tat_breached: True/False to filter by TAT breach status (optional)
    """
    add_log(f"PLMTool invoked with assignee: {assignee}, status: {status}, tat_breached: {tat_breached}")
    results = MOCK_PLM_ITEMS.copy()
    if assignee:
        results = [x for x in results if x["assignee"].lower() == assignee.lower()]
    if status:
        results = [x for x in results if x["status"].lower() == status.lower()]
    if tat_breached is not None:
        # Support string or boolean comparison
        breached_val = True if str(tat_breached).lower() in ("true", "1") else False
        results = [x for x in results if x["tat_breach"] == breached_val]
        
    return json.dumps(results, indent=2)

@tool
def kpi_tool(metric: str, assignee: Optional[str] = None) -> str:
    """
    Retrieves performance KPI metrics.
    Parameters:
    - metric: 'commits', 'jira_closures', or 'code_reviews'
    - assignee: username to filter by (optional)
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
                
    elif metric == "code_reviews":
        reviews = {}
        for pr in MOCK_GITHUB_DATA:
            ass = pr["author"]
            reviews[ass] = reviews.get(ass, 0) + pr.get("reviews_count", 0)
        for ass, count in reviews.items():
            if not assignee or ass.lower() == assignee.lower():
                kpis.append({"assignee": ass, "metric": "code_reviews", "value": count})
                
    return json.dumps(kpis, indent=2)

@tool
def consolidation_tool(raw_data_json: str, template_string: str, channel: str) -> str:
    """
    Aggregates, normalizes, deduplicates, groups, and renders alerts into a consolidated message per assignee.
    Parameters:
    - raw_data_json: A JSON-string representing a list of dicts.
      Format: [{"raw_item": {...}, "source_type": "jira|github|plm", "alert_type": "STATUS_UPDATE_REMINDER", "category": "stale_status"}]
    - template_string: Jinja2 template string to render
    - channel: 'slack', 'email', or 'knox'
    Returns:
    JSON string mapping assignee -> rendered consolidated message.
    """
    add_log(f"ConsolidationTool invoked. Channel: {channel}. Data items count: {len(raw_data_json)}")
    try:
        data = json.loads(raw_data_json)
        results = run_aggregation_pipeline(data, template_string, channel)
        return json.dumps(results, indent=2)
    except Exception as e:
        add_log(f"Error in ConsolidationTool: {str(e)}")
        return json.dumps({"error": str(e)})

@tool
def slack_notification_tool(recipient: str, message: str) -> str:
    """
    Sends a consolidated reminder message to a user or channel via Slack.
    - recipient: Slack username or channel ID (e.g. '@alice' or '#dev-team')
    - message: The formatted message body to send.
    """
    add_log(f"SlackNotificationTool invoked for recipient: {recipient}")
    add_delivery("slack", recipient, message)
    return "SUCCESS"

@tool
def email_notification_tool(recipient: str, message: str) -> str:
    """
    Sends a consolidated reminder message to a user via Email.
    - recipient: Email address (e.g. 'alice@company.com')
    - message: The HTML/plain-text formatted email body to send.
    """
    add_log(f"EmailNotificationTool invoked for recipient: {recipient}")
    add_delivery("email", recipient, message)
    return "SUCCESS"

@tool
def knox_notification_tool(recipient: str, message: str) -> str:
    """
    Sends a consolidated reminder push notification to a user via Knox.
    - recipient: Knox username
    - message: The text message.
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

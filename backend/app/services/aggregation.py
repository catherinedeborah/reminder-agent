import os
import re
from typing import List, Dict, Any, Optional
from jinja2 import Environment, BaseLoader

def make_link(system: str, key: str, channel: str) -> str:
    """
    Helper function to generate links for Jira or PLM based on the channel.
    - Slack: Markdown link [KEY](URL)
    - Email: HTML anchor tag <a href="URL">KEY</a>
    - Default (Knox): Plain URL link KEY (URL)
    """
    base_url = "https://jira.mycompany.com/browse" if system.lower() == "jira" else "https://plm.mycompany.com/item"
    url = f"{base_url}/{key}"
    
    if channel.lower() == "slack":
        return f"[{key}]({url})"
    elif channel.lower() == "email":
        return f'<a href="{url}">{key}</a>'
    else:
        return f"{key} ({url})"

def load_template_file(template_name: str) -> Optional[str]:
    """Loads a Jinja2 template file from the app/templates directory."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        templates_dir = os.path.join(base_dir, "templates")
        
        # Clean name and ensure extension
        clean_name = template_name.replace(".jinja2", "").strip()
        file_path = os.path.join(templates_dir, f"{clean_name}.jinja2")
        
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        print(f"Error loading template file {template_name}: {str(e)}")
    return None

def normalize_data(raw_item: Dict[str, Any], source_type: str, alert_type: str, category: str = None) -> Dict[str, Any]:
    """
    Normalize tool output (Jira, GitHub, PLM) to the standard format.
    """
    assignee = raw_item.get("assignee", "unassigned")
    
    # Handle GitHub data where assignee could be 'author'
    if source_type.lower() == "github":
        assignee = raw_item.get("author", assignee)
        issue_key = raw_item.get("commit_hash", "")[:8]
        summary = raw_item.get("message", "")
        status = raw_item.get("status", "")
        last_updated = raw_item.get("date", "")
        system = "github"
    elif source_type.lower() == "plm":
        issue_key = raw_item.get("item_id", "")
        summary = raw_item.get("name", "")
        status = raw_item.get("status", "")
        last_updated = raw_item.get("last_updated", "")
        system = "plm"
    else: # jira
        issue_key = raw_item.get("key", "")
        summary = raw_item.get("summary", "")
        status = raw_item.get("status", "")
        last_updated = raw_item.get("updated_at", "")
        system = "jira"

    # Default category mapping if not provided
    if not category:
        if alert_type == "SUBTASK_CREATION_REMINDER" or not raw_item.get("has_subtasks", True):
            category = "missing_subtasks"
        elif alert_type in ["STATUS_UPDATE_REMINDER", "PLM_TAT_BREACH"]:
            category = "stale_status"
        elif alert_type == "SPRINT_MID_PROGRESS_CHECK":
            category = "mid_progress_issues"
        elif alert_type == "TASK_CREATION_REMINDER":
            category = "missing_tasks"
        else:
            category = "other"

    return {
        "assignee": assignee,
        "issue_key": issue_key,
        "summary": summary,
        "status": status,
        "alert_type": alert_type,
        "category": category,
        "last_updated": last_updated,
        "system": system,
        "raw_item": raw_item,  # Keep full payload reference
        "metadata": {
            "project": raw_item.get("project"),
            "sprint_id": raw_item.get("sprint_id")
        }
    }

def deduplicate_alerts(alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped = []
    for item in alerts:
        key = (item["issue_key"], item["alert_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped

def group_by_assignee(alerts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped = {}
    for item in alerts:
        assignee = item["assignee"]
        if assignee not in grouped:
            grouped[assignee] = []
        grouped[assignee].append(item)
    return grouped

def categorize_sprint_issues(user_alerts: List[Dict[str, Any]], days_left: Optional[int] = None) -> Dict[str, Any]:
    """
    Sorts a developer's issues into structured lists based on sprint alert rules:
    - active_tasks: all sprint tasks assigned to user
    - incomplete_tasks: tasks not in Done status
    - missing_subtasks: tasks missing subtasks (no subtasks list or has_subtasks=False)
    - not_in_progress: has subtasks, but none are In Progress, and story is not In Progress
    - missing_efforts: task is In Progress but timespent is 0 or worklogs list is empty
    - near_end_unstarted: status is To Do and days_left <= 3
    - is_perfect_state: True if developer has active tasks and passes all hygiene checks
    """
    active_tasks = []
    incomplete_tasks = []
    missing_subtasks = []
    not_in_progress = []
    missing_efforts = []
    near_end_unstarted = []
    
    for alert in user_alerts:
        raw = alert.get("raw_item", {})
        key = alert["issue_key"]
        summary = alert["summary"]
        status = alert["status"]
        system = alert["system"]
        
        item_data = {
            "issue_key": key,
            "summary": summary,
            "status": status,
            "system": system,
            "raw_item": raw
        }
        
        # Skip items that are not agile tasks/stories (e.g. general commits or PLM items in composite runs)
        if system not in ("jira", "github") or not key:
            continue
            
        active_tasks.append(item_data)
        
        if status.lower() != "done":
            incomplete_tasks.append(item_data)
            
        # 1. Missing subtasks check (ignore subtask issues themselves)
        is_subtask = raw.get("is_subtask", False)
        subtasks_list = raw.get("subtasks", [])
        if not is_subtask and (not raw.get("has_subtasks", True) or len(subtasks_list) == 0):
            missing_subtasks.append(item_data)
            
        # 2. Not in progress check (has subtasks, but none are active)
        elif not is_subtask and raw.get("has_subtasks", True) and len(subtasks_list) > 0:
            any_sub_in_progress = any(sub.get("status", "").lower() == "in progress" for sub in subtasks_list)
            if status.lower() != "in progress" and not any_sub_in_progress:
                not_in_progress.append(item_data)
                
        # 3. Missing efforts check (In Progress but no logged hours)
        if status.lower() == "in progress":
            timespent = raw.get("timespent", 0)
            worklogs = raw.get("worklogs", [])
            if timespent == 0 or len(worklogs) == 0:
                missing_efforts.append(item_data)
                
        # 4. Near end unstarted check (To Do and sprint ending in <= 3 days)
        if status.lower() == "to do" and days_left is not None and days_left <= 3:
            near_end_unstarted.append(item_data)
            
    is_perfect_state = (
        len(active_tasks) > 0 and
        len(missing_subtasks) == 0 and
        len(not_in_progress) == 0 and
        len(missing_efforts) == 0 and
        len(near_end_unstarted) == 0
    )
    
    action_required = (
        len(missing_subtasks) + 
        len(not_in_progress) + 
        len(missing_efforts) + 
        len(near_end_unstarted)
    )
    
    return {
        "active_tasks": active_tasks,
        "incomplete_tasks": incomplete_tasks,
        "missing_subtasks": missing_subtasks,
        "not_in_progress": not_in_progress,
        "missing_efforts": missing_efforts,
        "near_end_unstarted": near_end_unstarted,
        "is_perfect_state": is_perfect_state,
        "total_issues": len(active_tasks),
        "action_required": action_required
    }

def render_template(assignee: str, categorized: Dict[str, Any], template_str: str, channel: str, days_left: Optional[int] = None) -> str:
    """
    Render Jinja2 template using the categorized items for the assignee.
    """
    rtemplate = Environment(loader=BaseLoader()).from_string(template_str)
    
    # Calculate fallback totals if not present
    total_issues = categorized.get("total_issues", len(categorized.get("active_tasks", [])))
    action_required = categorized.get("action_required", total_issues)
    
    # Add helper function and variables to context
    context = {
        "assignee": assignee,
        "active_tasks": categorized.get("active_tasks", []),
        "incomplete_tasks": categorized.get("incomplete_tasks", []),
        "missing_subtasks": categorized.get("missing_subtasks", []),
        "not_in_progress": categorized.get("not_in_progress", []),
        "missing_efforts": categorized.get("missing_efforts", []),
        "near_end_unstarted": categorized.get("near_end_unstarted", []),
        "is_perfect_state": categorized.get("is_perfect_state", False),
        "total_issues": total_issues,
        "action_required": action_required,
        "days_left": days_left,
        "make_link": lambda system, key: make_link(system, key, channel)
    }
    
    return rtemplate.render(context)

def run_aggregation_pipeline(
    raw_items_with_meta: List[Dict[str, Any]], 
    template_name_or_str: str, 
    channel: str, 
    days_left: Optional[int] = None
) -> Dict[str, str]:
    """
    Runs the complete aggregation pipeline on raw items:
    1. Normalize
    2. Deduplicate
    3. Group by Assignee
    4. Categorize per Assignee (Sprint Day Logic check)
    5. Dynamically load Template file
    6. Render template per Assignee
    """
    normalized_list = []
    for item in raw_items_with_meta:
        normalized = normalize_data(
            raw_item=item["raw_item"],
            source_type=item["source_type"],
            alert_type=item["alert_type"],
            category=item.get("category")
        )
        normalized_list.append(normalized)
        
    deduped = deduplicate_alerts(normalized_list)
    grouped = group_by_assignee(deduped)
    
    # Resolve the Jinja2 template content
    template_content = load_template_file(template_name_or_str)
    if not template_content:
        template_content = template_name_or_str # Treat as raw string fallback
        
    results = {}
    for assignee, user_alerts in grouped.items():
        categorized = categorize_sprint_issues(user_alerts, days_left=days_left)
        message = render_template(assignee, categorized, template_content, channel, days_left=days_left)
        results[assignee] = message
        
    return results

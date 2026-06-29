import re
from typing import List, Dict, Any
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

def normalize_data(raw_item: Dict[str, Any], source_type: str, alert_type: str, category: str = None) -> Dict[str, Any]:
    """
    Normalize any tool output (Jira, GitHub, PLM) to the standard format.
    Schema:
    {
      "assignee": str,
      "issue_key": str,
      "summary": str,
      "status": str,
      "alert_type": str,
      "category": str,
      "last_updated": str,
      "metadata": dict
    }
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
        "metadata": {
            "project": raw_item.get("project"),
            "sprint_id": raw_item.get("sprint_id")
        }
    }

def deduplicate_alerts(alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate issues. An issue is a duplicate if it has the same issue_key and alert_type.
    """
    seen = set()
    deduped = []
    for item in alerts:
        key = (item["issue_key"], item["alert_type"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped

def group_by_assignee(alerts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group standard alerts by assignee.
    """
    grouped = {}
    for item in alerts:
        assignee = item["assignee"]
        if assignee not in grouped:
            grouped[assignee] = []
        grouped[assignee].append(item)
    return grouped

def categorize_for_assignee(alerts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Categorize alerts into categories for template rendering.
    """
    categories = {
        "missing_subtasks": [],
        "stale_status": [],
        "mid_progress_issues": [],
        "missing_tasks": [],
        "other": []
    }
    for item in alerts:
        cat = item["category"]
        if cat in categories:
            categories[cat].append(item)
        else:
            categories["other"].append(item)
    return categories

def render_template(assignee: str, categorized: Dict[str, List[Dict[str, Any]]], template_str: str, channel: str) -> str:
    """
    Render Jinja2 template using the categorized items for the assignee.
    """
    # Create Jinja2 environment from string
    rtemplate = Environment(loader=BaseLoader()).from_string(template_str)
    
    # Calculate totals
    total_issues = sum(len(items) for items in categorized.values())
    action_required = total_issues # By default, all consolidated alerts require action
    
    # Add helper function and variables to context
    context = {
        "assignee": assignee,
        "missing_subtasks": categorized["missing_subtasks"],
        "stale_status": categorized["stale_status"],
        "mid_progress_issues": categorized["mid_progress_issues"],
        "missing_tasks": categorized["missing_tasks"],
        "other_alerts": categorized["other"],
        "total_issues": total_issues,
        "action_required": action_required,
        "make_link": lambda system, key: make_link(system, key, channel)
    }
    
    return rtemplate.render(context)

def run_aggregation_pipeline(raw_items_with_meta: List[Dict[str, Any]], template_str: str, channel: str) -> Dict[str, str]:
    """
    Runs the complete aggregation pipeline on raw items:
    1. Normalize
    2. Deduplicate
    3. Group by Assignee
    4. Categorize per Assignee
    5. Render template per Assignee
    Returns a dict mapping assignee -> consolidated message.
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
    
    results = {}
    for assignee, user_alerts in grouped.items():
        categorized = categorize_for_assignee(user_alerts)
        message = render_template(assignee, categorized, template_str, channel)
        results[assignee] = message
        
    return results

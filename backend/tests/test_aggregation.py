import pytest
from app.services.aggregation import (
    normalize_data,
    deduplicate_alerts,
    group_by_assignee,
    categorize_sprint_issues,
    render_template,
    make_link
)

def test_make_link():
    # Test slack Markdown link format
    link_slack = make_link("jira", "ABC-123", "slack")
    assert link_slack == "[ABC-123](https://jira.mycompany.com/browse/ABC-123)"

    # Test email HTML format
    link_email = make_link("plm", "PLM-101", "email")
    assert link_email == '<a href="https://plm.mycompany.com/item/PLM-101">PLM-101</a>'

    # Test Knox / default plain text format
    link_knox = make_link("jira", "ABC-123", "knox")
    assert "https://jira.mycompany.com/browse/ABC-123" in link_knox

def test_normalize_data():
    # Jira issue normalization
    jira_item = {
        "key": "ABC-123",
        "summary": "Implement Login",
        "status": "In Progress",
        "assignee": "alice",
        "updated_at": "2026-06-26T12:00:00",
        "has_subtasks": False
    }
    norm = normalize_data(jira_item, source_type="jira", alert_type="SUBTASK_CREATION_REMINDER")
    assert norm["assignee"] == "alice"
    assert norm["issue_key"] == "ABC-123"
    assert norm["summary"] == "Implement Login"
    assert norm["category"] == "missing_subtasks"
    assert norm["system"] == "jira"

    # PLM normalization
    plm_item = {
        "item_id": "PLM-101",
        "name": "Valve Assembly",
        "status": "In Review",
        "last_updated": "2026-06-25T10:00:00",
        "assignee": "bob",
        "tat_breach": True
    }
    norm_plm = normalize_data(plm_item, source_type="plm", alert_type="PLM_TAT_BREACH")
    assert norm_plm["assignee"] == "bob"
    assert norm_plm["issue_key"] == "PLM-101"
    assert norm_plm["category"] == "stale_status"
    assert norm_plm["system"] == "plm"

def test_deduplicate_alerts():
    alerts = [
        {"issue_key": "ABC-123", "alert_type": "STATUS_UPDATE_REMINDER", "assignee": "alice"},
        {"issue_key": "ABC-123", "alert_type": "STATUS_UPDATE_REMINDER", "assignee": "alice"}, # Duplicate
        {"issue_key": "ABC-456", "alert_type": "STATUS_UPDATE_REMINDER", "assignee": "alice"},
        {"issue_key": "ABC-123", "alert_type": "SUBTASK_CREATION_REMINDER", "assignee": "alice"}, # Different type
    ]
    deduped = deduplicate_alerts(alerts)
    assert len(deduped) == 3
    assert deduped[0]["issue_key"] == "ABC-123"
    assert deduped[1]["issue_key"] == "ABC-456"
    assert deduped[2]["issue_key"] == "ABC-123"

def test_group_by_assignee():
    alerts = [
        {"assignee": "alice", "issue_key": "ABC-123"},
        {"assignee": "bob", "issue_key": "XYZ-789"},
        {"assignee": "alice", "issue_key": "ABC-456"},
    ]
    grouped = group_by_assignee(alerts)
    assert len(grouped) == 2
    assert len(grouped["alice"]) == 2
    assert len(grouped["bob"]) == 1

def test_categorize_sprint_issues():
    alerts = [
        {
            "issue_key": "ABC-123",
            "summary": "Design Database Schema",
            "status": "In Progress",
            "system": "jira",
            "raw_item": {"has_subtasks": False, "is_subtask": False, "subtasks": [], "timespent": 0}
        },
        {
            "issue_key": "XYZ-789",
            "summary": "Create React Components",
            "status": "To Do",
            "system": "jira",
            "raw_item": {"has_subtasks": True, "is_subtask": False, "subtasks": [{"status": "To Do"}]}
        },
        {
            "issue_key": "ABC-222",
            "summary": "Fix Navbar alignment",
            "status": "In Progress",
            "system": "jira",
            "raw_item": {"has_subtasks": True, "is_subtask": False, "subtasks": [{"status": "In Progress"}], "timespent": 0, "worklogs": []}
        }
    ]
    
    cats = categorize_sprint_issues(alerts, days_left=5)
    assert len(cats["missing_subtasks"]) == 1
    assert len(cats["not_in_progress"]) == 1
    assert len(cats["missing_efforts"]) == 1
    assert cats["is_perfect_state"] is False
    
    cats_near_end = categorize_sprint_issues(alerts, days_left=2)
    assert len(cats_near_end["near_end_unstarted"]) == 1

def test_template_rendering():
    categorized = {
        "active_tasks": [
            {"issue_key": "ABC-123", "summary": "Subtask task", "system": "jira"},
            {"issue_key": "XYZ-789", "summary": "Stale task", "system": "jira"}
        ],
        "missing_subtasks": [{"issue_key": "ABC-123", "summary": "Subtask task", "system": "jira"}],
        "not_in_progress": [{"issue_key": "XYZ-789", "summary": "Stale task", "system": "jira"}],
        "missing_efforts": [],
        "near_end_unstarted": [],
        "is_perfect_state": False,
        "total_issues": 2,
        "action_required": 2
    }
    
    template = """Hi {{ assignee }},
🔴 Tasks Missing Subtasks:
{% for item in missing_subtasks -%}
- {{ make_link(item.system, item.issue_key) }}: {{ item.summary }}
{% endfor %}
🟡 Tasks Not in Progress:
{% for item in not_in_progress -%}
- {{ make_link(item.system, item.issue_key) }}: {{ item.summary }}
{% endfor %}
Summary:
- Total Issues: {{ total_issues }}
"""
    
    # Test for Slack channel
    rendered_slack = render_template("alice", categorized, template, "slack")
    assert "Hi alice" in rendered_slack
    assert "🔴 Tasks Missing Subtasks:\n- [ABC-123](https://jira.mycompany.com/browse/ABC-123): Subtask task" in rendered_slack
    assert "🟡 Tasks Not in Progress:\n- [XYZ-789](https://jira.mycompany.com/browse/XYZ-789): Stale task" in rendered_slack
    assert "Summary:\n- Total Issues: 2" in rendered_slack

    # Test for Email channel
    rendered_email = render_template("alice", categorized, template, "email")
    assert '<a href="https://jira.mycompany.com/browse/ABC-123">ABC-123</a>' in rendered_email

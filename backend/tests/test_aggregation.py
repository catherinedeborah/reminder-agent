import pytest
from app.services.aggregation import (
    normalize_data,
    deduplicate_alerts,
    group_by_assignee,
    categorize_for_assignee,
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

def test_categorize_for_assignee():
    alerts = [
        {"category": "missing_subtasks", "issue_key": "ABC-123"},
        {"category": "stale_status", "issue_key": "XYZ-789"},
        {"category": "mid_progress_issues", "issue_key": "DEF-111"},
        {"category": "missing_tasks", "issue_key": "GHI-222"},
        {"category": "other", "issue_key": "JKL-333"},
    ]
    cats = categorize_for_assignee(alerts)
    assert len(cats["missing_subtasks"]) == 1
    assert len(cats["stale_status"]) == 1
    assert len(cats["mid_progress_issues"]) == 1
    assert len(cats["missing_tasks"]) == 1
    assert len(cats["other"]) == 1

def test_template_rendering():
    categorized = {
        "missing_subtasks": [{"issue_key": "ABC-123", "summary": "Subtask task", "system": "jira"}],
        "stale_status": [{"issue_key": "XYZ-789", "summary": "Stale task", "system": "jira"}],
        "mid_progress_issues": [],
        "missing_tasks": [],
        "other": []
    }
    
    template = """Hi {{ assignee }},
🔴 Tasks Missing Subtasks:
{% for item in missing_subtasks -%}
- {{ make_link(item.system, item.issue_key) }}: {{ item.summary }}
{% endfor %}
🟡 Tasks Without Recent Updates:
{% for item in stale_status -%}
- {{ make_link(item.system, item.issue_key) }}: {{ item.summary }}
{% endfor %}
Summary:
- Total Issues: {{ total_issues }}
"""
    
    # Test for Slack channel
    rendered_slack = render_template("alice", categorized, template, "slack")
    assert "Hi alice" in rendered_slack
    assert "🔴 Tasks Missing Subtasks:\n- [ABC-123](https://jira.mycompany.com/browse/ABC-123): Subtask task" in rendered_slack
    assert "🟡 Tasks Without Recent Updates:\n- [XYZ-789](https://jira.mycompany.com/browse/XYZ-789): Stale task" in rendered_slack
    assert "Summary:\n- Total Issues: 2" in rendered_slack

    # Test for Email channel
    rendered_email = render_template("alice", categorized, template, "email")
    assert '<a href="https://jira.mycompany.com/browse/ABC-123">ABC-123</a>' in rendered_email

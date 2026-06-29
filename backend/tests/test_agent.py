import pytest
import json
from app.agent.tools import jira_tool, github_tool, plm_tool, kpi_tool
from app.agent.agent import run_reminder_agent
from app.agent.execution_context import get_deliveries, get_logs

def test_jira_tool():
    # Test assignee filter
    out = jira_tool.invoke({"jql": "assignee = 'alice'"})
    issues = json.loads(out)
    assert len(issues) > 0
    assert all(x["assignee"] == "alice" for x in issues)

    # Test status filter
    out = jira_tool.invoke({"jql": "status = 'In Progress'"})
    issues = json.loads(out)
    assert len(issues) > 0
    assert all(x["status"] == "In Progress" for x in issues)

    # Test subtasks check filter
    out = jira_tool.invoke({"jql": "status = 'In Progress' AND subtasks is empty"})
    issues = json.loads(out)
    assert len(issues) > 0
    assert all(not x.get("has_subtasks", True) for x in issues)

def test_github_tool():
    out = github_tool.invoke({"query_type": "commits"})
    commits = json.loads(out)
    assert len(commits) > 0
    assert "commit_hash" in commits[0]

def test_plm_tool():
    out = plm_tool.invoke({"tat_breached": True})
    items = json.loads(out)
    assert len(items) > 0
    assert all(x["tat_breach"] is True for x in items)

def test_kpi_tool():
    out = kpi_tool.invoke({"metric": "jira_closures"})
    kpis = json.loads(out)
    assert len(kpis) > 0
    assert all(x["metric"] == "jira_closures" for x in kpis)

def test_run_reminder_agent_simulation():
    # Mock configuration for testing
    configs = [
        {
            "id": "test-1",
            "name": "Subtask Reminder Config",
            "type": "SUBTASK_CREATION_REMINDER",
            "category": "hygiene",
            "schedule": "0 9 * * 1-5",
            "channels": ["slack"],
            "tool_hints": ["JiraTool"],
            "metadata_json": {"project_keys": ["ABC"]},
            "template_string": "Hi {{ assignee }},\n🔴 Tasks Missing Subtasks:\n{% for item in missing_subtasks -%}- {{ make_link('jira', item.issue_key) }}: {{ item.summary }}\n{% endfor %}"
        },
        {
            "id": "test-2",
            "name": "Stale Progress Config",
            "type": "STATUS_UPDATE_REMINDER",
            "category": "hygiene",
            "schedule": "0 9 * * 1-5",
            "channels": ["slack"],
            "tool_hints": ["JiraTool"],
            "metadata_json": {"project_keys": ["ABC"]},
            "template_string": "Hi {{ assignee }},\n🔴 Tasks Missing Subtasks:\n{% for item in missing_subtasks -%}- {{ make_link('jira', item.issue_key) }}: {{ item.summary }}\n{% endfor %}"
        }
    ]
    
    result = run_reminder_agent(configs)
    
    assert result["status"] == "SUCCESS"
    assert "consolidated_messages" in result
    
    # Make sure deliveries were logged in execution context
    deliveries = get_deliveries()
    assert len(deliveries) > 0
    assert any(d["channel"] == "slack" for d in deliveries)
    
    # Verify consolidated message contents for 'alice' (who has missing subtasks in mock data)
    assert "alice" in result["consolidated_messages"]
    alice_msg = result["consolidated_messages"]["alice"]
    assert "Tasks Missing Subtasks" in alice_msg
    assert "ABC-123" in alice_msg or "ABC-456" in alice_msg

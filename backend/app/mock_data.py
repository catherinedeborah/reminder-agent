import datetime

# Mock Jira Issues
# Includes issues with missing subtasks, stale in-progress status, and mid-sprint tasks
MOCK_JIRA_ISSUES = [
    {
        "key": "ABC-123",
        "summary": "Design Database Schema",
        "status": "In Progress",
        "assignee": "alice",
        "updated_at": (datetime.datetime.now() - datetime.timedelta(days=8)).isoformat(), # Stale
        "has_subtasks": False, # Missing subtask
        "project": "ABC",
        "created_at": (datetime.datetime.now() - datetime.timedelta(days=10)).isoformat(),
        "sprint_id": "Sprint-1"
    },
    {
        "key": "ABC-456",
        "summary": "Setup OAuth Authentication",
        "status": "In Progress",
        "assignee": "alice",
        "updated_at": (datetime.datetime.now() - datetime.timedelta(days=2)).isoformat(),
        "has_subtasks": False, # Missing subtask
        "project": "ABC",
        "created_at": (datetime.datetime.now() - datetime.timedelta(days=3)).isoformat(),
        "sprint_id": "Sprint-1"
    },
    {
        "key": "XYZ-789",
        "summary": "Create React Components",
        "status": "In Progress",
        "assignee": "bob",
        "updated_at": (datetime.datetime.now() - datetime.timedelta(days=12)).isoformat(), # Stale
        "has_subtasks": True,
        "project": "XYZ",
        "created_at": (datetime.datetime.now() - datetime.timedelta(days=15)).isoformat(),
        "sprint_id": "Sprint-1"
    },
    {
        "key": "DEF-111",
        "summary": "Write Integration Tests",
        "status": "To Do",
        "assignee": "bob",
        "updated_at": (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(),
        "has_subtasks": False,
        "project": "DEF",
        "created_at": (datetime.datetime.now() - datetime.timedelta(days=5)).isoformat(),
        "sprint_id": "Sprint-1"  # Needs attention (not started mid sprint)
    },
    {
        "key": "ABC-222",
        "summary": "Fix Navbar alignment",
        "status": "In Progress",
        "assignee": "arunj",
        "updated_at": (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat(), # Stale
        "has_subtasks": False, # Missing subtasks
        "project": "ABC",
        "created_at": (datetime.datetime.now() - datetime.timedelta(days=8)).isoformat(),
        "sprint_id": "Sprint-1"
    },
    {
        "key": "ABC-333",
        "summary": "Configure Production CI Pipeline",
        "status": "Done",
        "assignee": "arunj",
        "updated_at": (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(),
        "has_subtasks": True,
        "project": "ABC",
        "created_at": (datetime.datetime.now() - datetime.timedelta(days=6)).isoformat(),
        "sprint_id": "Sprint-1"
    }
]

# Mock GitHub Commits & PRs
MOCK_GITHUB_DATA = [
    {
        "repo": "reminder-agent-system",
        "author": "alice",
        "commit_hash": "a1b2c3d4",
        "message": "feat: init db module",
        "date": (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(),
        "pr_id": 101,
        "reviews_count": 0,
        "status": "Open"
    },
    {
        "repo": "reminder-agent-system",
        "author": "bob",
        "commit_hash": "e5f6g7h8",
        "message": "fix: update configurations",
        "date": (datetime.datetime.now() - datetime.timedelta(days=2)).isoformat(),
        "pr_id": 102,
        "reviews_count": 2,
        "status": "Merged"
    },
    {
        "repo": "reminder-agent-system",
        "author": "arunj",
        "commit_hash": "i9j0k1l2",
        "message": "docs: update API plan",
        "date": (datetime.datetime.now() - datetime.timedelta(days=3)).isoformat(),
        "pr_id": 103,
        "reviews_count": 1,
        "status": "Open"
    }
]

# Mock PLM Items
MOCK_PLM_ITEMS = [
    {
        "item_id": "PLM-101",
        "name": "Battery Thermal Enclosure Approval",
        "assignee": "alice",
        "status": "Awaiting Approval",
        "tat_breach": True,
        "last_updated": (datetime.datetime.now() - datetime.timedelta(days=15)).isoformat()
    },
    {
        "item_id": "PLM-102",
        "name": "Chassis Weldment Structural Analysis",
        "assignee": "bob",
        "status": "In Review",
        "tat_breach": False,
        "last_updated": (datetime.datetime.now() - datetime.timedelta(days=3)).isoformat()
    },
    {
        "item_id": "PLM-103",
        "name": "PDU Connectors BOM Release",
        "assignee": "arunj",
        "status": "Draft",
        "tat_breach": True,
        "last_updated": (datetime.datetime.now() - datetime.timedelta(days=10)).isoformat()
    }
]

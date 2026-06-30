import datetime

# Mock Active Sprint Details
# Dynamic dates relative to today's date for flexible testing
_now = datetime.datetime.now()
MOCK_ACTIVE_SPRINT = {
    "id": 1,
    "name": "Sprint 1",
    "startDate": (_now - datetime.timedelta(days=5)).isoformat(), # Started 5 days ago
    "endDate": (_now + datetime.timedelta(days=9)).isoformat(),   # Ends in 9 days (14 days total)
    "boardId": 123,
    "state": "active"
}

# Mock Jira Issues
MOCK_JIRA_ISSUES = [
    # ALICE: In Progress tasks, but has_subtasks is False (Missing Subtasks warning)
    {
        "key": "ABC-123",
        "summary": "Design Database Schema",
        "status": "In Progress",
        "assignee": "alice",
        "updated_at": (_now - datetime.timedelta(days=2)).isoformat(),
        "has_subtasks": False,
        "subtasks": [],
        "worklogs": [],
        "timespent": 0,
        "project": "ABC",
        "created_at": (_now - datetime.timedelta(days=10)).isoformat(),
        "sprint_id": "Sprint-1",
        "board_id": 123
    },
    {
        "key": "ABC-456",
        "summary": "Setup OAuth Authentication",
        "status": "In Progress",
        "assignee": "alice",
        "updated_at": (_now - datetime.timedelta(days=1)).isoformat(),
        "has_subtasks": False,
        "subtasks": [],
        "worklogs": [],
        "timespent": 0,
        "project": "ABC",
        "created_at": (_now - datetime.timedelta(days=3)).isoformat(),
        "sprint_id": "Sprint-1",
        "board_id": 123
    },

    # BOB: Has subtasks, but all items are in To Do status (Not In Progress warning)
    {
        "key": "XYZ-789",
        "summary": "Create React Components",
        "status": "To Do",
        "assignee": "bob",
        "updated_at": (_now - datetime.timedelta(days=5)).isoformat(),
        "has_subtasks": True,
        "subtasks": [
            {"key": "XYZ-790", "summary": "Implement Navbar Component", "status": "To Do"},
            {"key": "XYZ-791", "summary": "Implement Sidebar Component", "status": "To Do"}
        ],
        "worklogs": [],
        "timespent": 0,
        "project": "XYZ",
        "created_at": (_now - datetime.timedelta(days=15)).isoformat(),
        "sprint_id": "Sprint-1",
        "board_id": 123
    },

    # ARUNJ: In Progress with subtasks, but timespent is 0 (Missing Effort Logs warning)
    {
        "key": "ABC-222",
        "summary": "Fix Navbar alignment",
        "status": "In Progress",
        "assignee": "arunj",
        "updated_at": (_now - datetime.timedelta(days=1)).isoformat(),
        "has_subtasks": True,
        "subtasks": [
            {"key": "ABC-223", "summary": "Adjust CSS margins", "status": "In Progress"}
        ],
        "worklogs": [], # No effort logged
        "timespent": 0,
        "project": "ABC",
        "created_at": (_now - datetime.timedelta(days=8)).isoformat(),
        "sprint_id": "Sprint-1",
        "board_id": 123
    },

    # CHARLIE: In Progress with subtasks, and has logged efforts today (Appreciation trigger)
    {
        "key": "ABC-333",
        "summary": "Configure Production CI Pipeline",
        "status": "In Progress",
        "assignee": "charlie",
        "updated_at": _now.isoformat(),
        "has_subtasks": True,
        "subtasks": [
            {"key": "ABC-334", "summary": "Write Github Actions YAML", "status": "In Progress"}
        ],
        "worklogs": [
            {"timeSpentSeconds": 14400, "created": _now.isoformat()} # Effort logged today
        ],
        "timespent": 14400,
        "project": "ABC",
        "created_at": (_now - datetime.timedelta(days=6)).isoformat(),
        "sprint_id": "Sprint-1",
        "board_id": 123
    }
]

# Note: DAVID has no tasks assigned in MOCK_JIRA_ISSUES.
# When the agent runs, if david is configured as a recipient, they will trigger
# the "no tasks assigned" warning and be asked to create stories.

# Mock GitHub Commits & PRs
MOCK_GITHUB_DATA = [
    {
        "repo": "reminder-agent-system",
        "author": "alice",
        "commit_hash": "a1b2c3d4",
        "message": "feat: init db module",
        "date": (_now - datetime.timedelta(days=1)).isoformat(),
        "pr_id": 101,
        "reviews_count": 0,
        "status": "Open"
    },
    {
        "repo": "reminder-agent-system",
        "author": "bob",
        "commit_hash": "e5f6g7h8",
        "message": "fix: update configurations",
        "date": (_now - datetime.timedelta(days=2)).isoformat(),
        "pr_id": 102,
        "reviews_count": 2,
        "status": "Merged"
    },
    {
        "repo": "reminder-agent-system",
        "author": "arunj",
        "commit_hash": "i9j0k1l2",
        "message": "docs: update API plan",
        "date": (_now - datetime.timedelta(days=3)).isoformat(),
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
        "last_updated": (_now - datetime.timedelta(days=15)).isoformat()
    },
    {
        "item_id": "PLM-102",
        "name": "Chassis Weldment Structural Analysis",
        "assignee": "bob",
        "status": "In Review",
        "tat_breach": False,
        "last_updated": (_now - datetime.timedelta(days=3)).isoformat()
    },
    {
        "item_id": "PLM-103",
        "name": "PDU Connectors BOM Release",
        "assignee": "arunj",
        "status": "Draft",
        "tat_breach": True,
        "last_updated": (_now - datetime.timedelta(days=10)).isoformat()
    }
]

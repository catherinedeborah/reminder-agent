# AI-powered Reminder Agent System

A production-grade, configuration-driven, consolidated alert aggregation system built with **FastAPI**, **SQLAlchemy (SQLite/Postgres)**, **APScheduler**, **LangChain**, and a responsive **React (CDN-based) Single Page App**.

---

## 🚀 Key Features

- **YAML-driven Configs**: Configure all reminder alert rules offline in [reminders.yaml](file:///C:/Users/arunj/.gemini/antigravity/scratch/reminder_agent_system/backend/reminders.yaml). On startup, the backend automatically imports these configurations into the database.
- **CLI Manual Trigger**: Execute alerts locally using [trigger_yaml.py](file:///C:/Users/arunj/.gemini/antigravity/scratch/reminder_agent_system/backend/trigger_yaml.py) to parse configurations, run simulator loops, and verify the consolidated output without launching the server or using the UI.
- **Cross-Alert Consolidation**: Merges multiple check alerts (`SPRINT_MID_PROGRESS_CHECK`, `TASK_CREATION_REMINDER`, `SUBTASK_CREATION_REMINDER`, `STATUS_UPDATE_REMINDER`) into a **single, organized notification per assignee**.
- **Context-Aware Link Generation**: Generates channel-specific links (standard Markdown for Slack like `[KEY](URL)`, HTML anchor tags `<a href="...">` for Email, and raw URL strings for Knox push alerts).
- **Interactive Dashboard**: A glassmorphic admin panel for configuring reminders, schedules (cron), target recipients, and editing message templates with a direct manual execution logs viewer.
- **Python 3.13 Ready & Self-Contained**: Hashing logic is built directly on native `bcrypt` (avoiding legacy `passlib` version conflicts). An intelligent LangChain fallback simulator ensures the application runs perfectly out-of-the-box even without active LLM connections.

---

## ⚙️ Quick Start

### 1. Prerequisites
- **Python 3.10+** (Python 3.13 fully supported)

### 2. Setup Dependencies
From your shell, navigate to the `backend` directory and install the requirements:
```bash
cd backend
pip install -r requirements.txt
```

### 3. Run Automated Tests
Verify that all core normalization, grouping, API, and agent loop components pass their tests:
```bash
# Run from the root folder
python -m pytest backend/tests
```

### 4. Start the Application
Launch the FastAPI development server:
```bash
python run.py
```
This runs the application on **`http://localhost:8100`**.

---

## 🧪 Testing Manual Alerts via YAML (CLI Mode)

You can write and test configurations entirely in a local YAML file.

### 1. Edit Configurations
Open [backend/reminders.yaml](file:///C:/Users/arunj/.gemini/antigravity/scratch/reminder_agent_system/backend/reminders.yaml) and declare your configurations. For example:
```yaml
reminders:
  - name: "Sprint Hygiene Alert"
    type: "SUBTASK_CREATION_REMINDER"
    category: "hygiene"
    schedule: "0 9 * * 1-5"
    enabled: true
    recipients:
      users: ["alice", "bob", "arunj"]
    channels: ["slack", "email"]
    template_string: |
      Hi {{ assignee }},
      
      Here’s your consolidated sprint hygiene check:
      
      🔴 Tasks Missing Subtasks:
      {% for item in missing_subtasks -%}
      - {{ make_link(item.system, item.issue_key) }} : {{ item.summary }}
      {% else -%}
      - None
      {% endfor %}
      
      Summary:
      - Total Issues: {{ total_issues }}
```

### 2. Run the Trigger Script
Execute the YAML configuration trigger script:
```bash
python backend/trigger_yaml.py
```

### 3. Verify Output
The script prints the execution traces and shows the final consolidated message for each assignee directly on your console:
```text
==================================================
Assignee: alice
==================================================
Hi alice,

Here’s your consolidated sprint hygiene check:

🔴 Tasks Missing Subtasks:
- [ABC-123](https://jira.mycompany.com/browse/ABC-123) : Design Database Schema
- [ABC-456](https://jira.mycompany.com/browse/ABC-456) : Setup OAuth Authentication

Summary:
- Total Issues: 4
- Action Required: 4
==================================================
```

---

## 🖥️ Seeding the Database (UI Mode)

When you run `python run.py` to start the backend server, the server automatically reads [backend/reminders.yaml](file:///C:/Users/arunj/.gemini/antigravity/scratch/reminder_agent_system/backend/reminders.yaml) and seeds the SQL database with any missing configurations.

1. **Access the Dashboard**: Open your browser and navigate to `http://localhost:8100/`.
2. **Log In**: Authenticate using the auto-seeded admin credentials:
   - **Username**: `admin`
   - **Password**: `admin123`
3. **Trigger via UI**: You will see your YAML-configured alerts displayed on the dashboard. Click **Trigger Agent** to run them and inspect the log consoles.

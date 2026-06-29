import uuid
from sqlalchemy import Column, String, Boolean, Text, JSON, Integer
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

class ReminderConfig(Base):
    __tablename__ = "reminder_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # SPRINT_MID_PROGRESS_CHECK, etc.
    category = Column(String, nullable=True)
    schedule = Column(String, nullable=False)  # cron expression
    enabled = Column(Boolean, default=True)
    
    # JSON Fields for configurations
    recipients = Column(JSON, default=dict)  # {"users": [], "groups": [], "dynamic": {}}
    channels = Column(JSON, default=list)    # ["slack", "email", "knox"]
    template_string = Column(Text, nullable=False)
    tool_hints = Column(JSON, default=list)  # ["JiraTool", "GitHubTool"]
    data_requirements = Column(JSON, default=dict)
    aggregation = Column(JSON, default=dict)  # {"group_by": ["assignee"], "combine_alerts": true}
    execution = Column(JSON, default=dict)    # {"allow_multi_tool": true, "allow_multi_query": true}
    metadata_json = Column(JSON, default=dict) # {"project_keys": [], "sprint_id": ""}
    retry_policy = Column(JSON, default=dict)
    notification_rules = Column(JSON, default=dict)

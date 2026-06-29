from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# --- Auth Schemas ---
class UserCreate(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# --- Reminder Config Schemas ---
class ReminderConfigBase(BaseModel):
    name: str
    type: str  # SPRINT_MID_PROGRESS_CHECK, etc.
    category: Optional[str] = None
    schedule: str
    enabled: bool = True
    recipients: Dict[str, Any] = Field(default_factory=dict)
    channels: List[str] = Field(default_factory=list)
    template_string: str
    tool_hints: List[str] = Field(default_factory=list)
    data_requirements: Dict[str, Any] = Field(default_factory=dict)
    aggregation: Dict[str, Any] = Field(default_factory=lambda: {"group_by": ["assignee"], "combine_alerts": True})
    execution: Dict[str, Any] = Field(default_factory=lambda: {"allow_multi_tool": True, "allow_multi_query": True})
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    retry_policy: Dict[str, Any] = Field(default_factory=dict)
    notification_rules: Dict[str, Any] = Field(default_factory=dict)

class ReminderConfigCreate(ReminderConfigBase):
    pass

class ReminderConfigUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    category: Optional[str] = None
    schedule: Optional[str] = None
    enabled: Optional[bool] = None
    recipients: Optional[Dict[str, Any]] = None
    channels: Optional[List[str]] = None
    template_string: Optional[str] = None
    tool_hints: Optional[List[str]] = None
    data_requirements: Optional[Dict[str, Any]] = None
    aggregation: Optional[Dict[str, Any]] = None
    execution: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    retry_policy: Optional[Dict[str, Any]] = None
    notification_rules: Optional[Dict[str, Any]] = None

class ReminderConfigResponse(ReminderConfigBase):
    id: str

    class Config:
        from_attributes = True

class TriggerResponse(BaseModel):
    status: str
    message: str
    logs: Optional[List[str]] = None
    consolidated_messages: Optional[Dict[str, str]] = None

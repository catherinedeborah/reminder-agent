import logging
import os
import yaml
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List

from app.database import engine, Base, get_db
from app.models import User, ReminderConfig
from app.schemas import (
    UserCreate, UserResponse, Token,
    ReminderConfigCreate, ReminderConfigUpdate, ReminderConfigResponse,
    TriggerResponse
)
from app.auth import get_password_hash, verify_password, create_access_token, get_current_user
from app.scheduler import start_scheduler, shutdown_scheduler, sync_scheduler_jobs
from app.agent.agent import run_reminder_agent
from app.agent.execution_context import get_logs, init_context, add_log

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Reminder Agent API",
    description="Backend service for configuring and executing AI-driven reminder agents",
    version="1.0.0"
)

# CORS configurations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify the actual domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_dashboard():
    """Serves the configuration dashboard UI."""
    static_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(static_dir, "static", "index.html")
    return FileResponse(html_path)

# Startup and shutdown handlers
@app.on_event("startup")
def startup_event():
    db = next(get_db())
    try:
        # Seed default user if none exists
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            logger.info("Seeding default user: admin / admin123")
            hashed_pwd = get_password_hash("admin123")
            default_user = User(username="admin", hashed_password=hashed_pwd)
            db.add(default_user)
            db.commit()

        # Seed configurations from reminders.yaml
        yaml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reminders.yaml")
        if os.path.exists(yaml_path):
            logger.info(f"Seeding database from YAML file: {yaml_path}")
            try:
                with open(yaml_path, "r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f)
                
                reminders_seed = config_data.get("reminders", [])
                for r_data in reminders_seed:
                    # Check if config exists by name
                    existing = db.query(ReminderConfig).filter(ReminderConfig.name == r_data["name"]).first()
                    if not existing:
                        new_config = ReminderConfig(
                            name=r_data["name"],
                            type=r_data["type"],
                            category=r_data.get("category", "other"),
                            schedule=r_data["schedule"],
                            enabled=r_data.get("enabled", True),
                            recipients=r_data.get("recipients", {}),
                            channels=r_data.get("channels", ["slack"]),
                            template_string=r_data.get("template_string"),
                            tool_hints=r_data.get("tool_hints", []),
                            data_requirements=r_data.get("data_requirements", {}),
                            aggregation=r_data.get("aggregation", {"combine_alerts": True}),
                            execution=r_data.get("execution", {}),
                            metadata_json=r_data.get("metadata_json", {}),
                            retry_policy=r_data.get("retry_policy", {}),
                            notification_rules=r_data.get("notification_rules", {}),
                            board_id=r_data.get("board_id"),
                            sprint_start_enabled=r_data.get("sprint_start_enabled", False),
                            sprint_mid_enabled=r_data.get("sprint_mid_enabled", False),
                            sprint_end_enabled=r_data.get("sprint_end_enabled", False)
                        )
                        db.add(new_config)
                        logger.info(f"Seeding: Added reminder configuration '{r_data['name']}' from reminders.yaml")
                db.commit()
            except Exception as yaml_err:
                logger.error(f"Error seeding configs from YAML: {str(yaml_err)}")
        else:
            logger.warning(f"Seeding: reminders.yaml not found at {yaml_path}. Skipping database seeding.")
    except Exception as e:
        logger.error(f"Error seeding default user: {str(e)}")
    finally:
        db.close()
        
    start_scheduler()

@app.on_event("shutdown")
def shutdown_event():
    shutdown_scheduler()

# --- Auth Endpoints ---

@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user_data.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pwd = get_password_hash(user_data.password)
    new_user = User(username=user_data.username, hashed_password=hashed_pwd)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/login", response_model=Token)
def login_oauth2(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Standard OAuth2 form-compatible login endpoint."""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/login", response_model=Token)
def login_json(user_data: UserCreate, db: Session = Depends(get_db)):
    """JSON-compatible login endpoint for standard REST APIs."""
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# --- Reminder Configuration Endpoints ---

@app.get("/reminders", response_model=List[ReminderConfigResponse])
def get_reminders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(ReminderConfig).all()

@app.post("/reminders", response_model=ReminderConfigResponse, status_code=status.HTTP_201_CREATED)
def create_reminder(
    reminder_data: ReminderConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_config = ReminderConfig(
        **reminder_data.model_dump()
    )
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    sync_scheduler_jobs()
    return new_config

@app.put("/reminders/{id}", response_model=ReminderConfigResponse)
def update_reminder(
    id: str,
    reminder_data: ReminderConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    config = db.query(ReminderConfig).filter(ReminderConfig.id == id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Reminder config not found")
        
    # Update provided fields
    for field, value in reminder_data.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
        
    db.commit()
    db.refresh(config)
    sync_scheduler_jobs()
    return config

@app.delete("/reminders/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reminder(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    config = db.query(ReminderConfig).filter(ReminderConfig.id == id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Reminder config not found")
        
    db.delete(config)
    db.commit()
    sync_scheduler_jobs()
    return None

# --- Agent Execution Endpoints ---

@app.post("/reminders/{id}/trigger", response_model=TriggerResponse)
def trigger_reminder(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually triggers the execution of a single reminder config.
    Runs the LangChain Agent loop in the current thread and returns the execution details.
    """
    config = db.query(ReminderConfig).filter(ReminderConfig.id == id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Reminder config not found")
        
    config_dict = {
        "id": config.id,
        "name": config.name,
        "type": config.type,
        "category": config.category,
        "schedule": config.schedule,
        "channels": config.channels,
        "template_string": config.template_string,
        "tool_hints": config.tool_hints,
        "metadata_json": config.metadata_json,
        "aggregation": config.aggregation
    }
    
    # Run agent loop
    result = run_reminder_agent([config_dict])
    logs = get_logs()
    
    return TriggerResponse(
        status=result["status"],
        message=result["message"],
        logs=logs,
        consolidated_messages=result.get("consolidated_messages", {})
    )

@app.post("/reminders/trigger-batch", response_model=TriggerResponse)
def trigger_batch(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually triggers the consolidated batch execution of all active combinable configurations.
    """
    combinable_types = {
        "SPRINT_MID_PROGRESS_CHECK",
        "TASK_CREATION_REMINDER",
        "SUBTASK_CREATION_REMINDER",
        "STATUS_UPDATE_REMINDER"
    }
    
    configs = db.query(ReminderConfig).filter(
        ReminderConfig.enabled == True,
        ReminderConfig.type.in_(list(combinable_types))
    ).all()
    
    if not configs:
        return TriggerResponse(
            status="SUCCESS",
            message="No enabled combinable configs found to trigger.",
            logs=["Batch process completed: 0 configs executed."],
            consolidated_messages={}
        )
        
    configs_dict = []
    for c in configs:
        c_dict = {
            "id": c.id,
            "name": c.name,
            "type": c.type,
            "category": c.category,
            "schedule": c.schedule,
            "channels": c.channels,
            "template_string": c.template_string,
            "tool_hints": c.tool_hints,
            "metadata_json": c.metadata_json,
            "aggregation": c.aggregation
        }
        configs_dict.append(c_dict)
        
    result = run_reminder_agent(configs_dict)
    logs = get_logs()
    
    return TriggerResponse(
        status=result["status"],
        message=result["message"],
        logs=logs,
        consolidated_messages=result.get("consolidated_messages", {})
    )

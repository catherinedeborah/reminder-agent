from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import ReminderConfig
from app.agent.agent import run_reminder_agent
from app.agent.execution_context import add_log
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

# Combinable alert types defined in requirement
COMBINABLE_TYPES = {
    "SPRINT_MID_PROGRESS_CHECK",
    "TASK_CREATION_REMINDER",
    "SUBTASK_CREATION_REMINDER",
    "STATUS_UPDATE_REMINDER"
}

def get_db_session():
    return SessionLocal()

def execute_consolidated_batch():
    """Runs all combinable configs together in a single agent batch."""
    logger.info("Scheduler: Triggering consolidated batch run.")
    db = get_db_session()
    try:
        # Load all enabled combinable configs
        configs = db.query(ReminderConfig).filter(
            ReminderConfig.enabled == True,
            ReminderConfig.type.in_(list(COMBINABLE_TYPES))
        ).all()
        
        if not configs:
            logger.info("Scheduler: No active combinable configs found for batch.")
            return
            
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
            
        logger.info(f"Scheduler: Batch running with {len(configs_dict)} configs.")
        run_reminder_agent(configs_dict)
    except Exception as e:
        logger.error(f"Scheduler: Error in batch run: {str(e)}")
    finally:
        db.close()

def execute_single_reminder(config_id: str):
    """Runs a single non-consolidated configuration."""
    logger.info(f"Scheduler: Triggering single config run for {config_id}.")
    db = get_db_session()
    try:
        c = db.query(ReminderConfig).filter(ReminderConfig.id == config_id).first()
        if not c or not c.enabled:
            logger.info(f"Scheduler: Config {config_id} not found or disabled.")
            return
            
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
        
        run_reminder_agent([c_dict])
    except Exception as e:
        logger.error(f"Scheduler: Error running single config {config_id}: {str(e)}")
    finally:
        db.close()

def sync_scheduler_jobs():
    """
    Synchronizes the database configs with APScheduler jobs.
    Called on startup and whenever a config is added, updated, or deleted.
    """
    logger.info("Scheduler: Syncing scheduler jobs with database...")
    db = get_db_session()
    try:
        # Fetch all enabled configs
        configs = db.query(ReminderConfig).filter(ReminderConfig.enabled == True).all()
        
        # Remove all existing jobs to rebuild
        scheduler.remove_all_jobs()
        
        combinable_jobs_registered = False
        
        for c in configs:
            # Check if this config is combinable and has consolidation mode enabled
            is_combinable = c.type in COMBINABLE_TYPES
            combine_alerts = c.aggregation.get("combine_alerts", True)
            
            if is_combinable and combine_alerts:
                # Grouped batch. Register a single consolidated job running on the schedule
                # of the combinable configurations. For safety, we can run it at their specified schedules.
                # To prevent registering the exact same job multiple times, we tag a combined scheduler job.
                job_id = f"consolidated_batch_{c.schedule.replace(' ', '_')}"
                if not scheduler.get_job(job_id):
                    try:
                        # Add cron trigger
                        # e.g., "0 9 * * 1-5" (min, hour, day, month, day_of_week)
                        cron_parts = c.schedule.split()
                        if len(cron_parts) >= 5:
                            trigger = CronTrigger(
                                minute=cron_parts[0],
                                hour=cron_parts[1],
                                day=cron_parts[2],
                                month=cron_parts[3],
                                day_of_week=cron_parts[4]
                            )
                            scheduler.add_job(
                                execute_consolidated_batch,
                                trigger=trigger,
                                id=job_id,
                                replace_existing=True
                            )
                            logger.info(f"Scheduler: Added consolidated batch job with schedule: '{c.schedule}'")
                    except Exception as cron_err:
                        logger.error(f"Scheduler: Invalid cron schedule '{c.schedule}' for config '{c.name}': {str(cron_err)}")
            else:
                # Individual job
                job_id = f"single_job_{c.id}"
                try:
                    cron_parts = c.schedule.split()
                    if len(cron_parts) >= 5:
                        trigger = CronTrigger(
                            minute=cron_parts[0],
                            hour=cron_parts[1],
                            day=cron_parts[2],
                            month=cron_parts[3],
                            day_of_week=cron_parts[4]
                        )
                        scheduler.add_job(
                            execute_single_reminder,
                            trigger=trigger,
                            args=[c.id],
                            id=job_id,
                            replace_existing=True
                        )
                        logger.info(f"Scheduler: Added individual job '{c.name}' with schedule: '{c.schedule}'")
                except Exception as cron_err:
                    logger.error(f"Scheduler: Invalid cron schedule '{c.schedule}' for config '{c.name}': {str(cron_err)}")
                    
        logger.info(f"Scheduler: Sync complete. Active job count: {len(scheduler.get_jobs())}")
    except Exception as e:
        logger.error(f"Scheduler: Sync failed: {str(e)}")
    finally:
        db.close()

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started.")
        sync_scheduler_jobs()

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped.")

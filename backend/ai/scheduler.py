"""
Scheduler — QMS AI Module
Weekly automatic retraining using APScheduler.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_scheduler = None


def start_scheduler(app):
    """Initialize and start background scheduler within Flask app context."""
    global _scheduler

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("[Scheduler] apscheduler not installed. Weekly retraining disabled.")
        return

    _scheduler = BackgroundScheduler(
        job_defaults={"max_instances": 1, "coalesce": True},
        timezone="UTC"
    )

    def retrain_all_factories():
        """Retrain models for all active factories."""
        with app.app_context():
            try:
                from models import db
                from sqlalchemy import text
                from services.ai_service import AIService

                rows = db.session.execute(
                    text("SELECT id FROM factories WHERE is_active = TRUE")
                ).fetchall()

                logger.info(f"[Scheduler] Weekly retrain for {len(rows)} factories")

                for row in rows:
                    factory_id = row[0]
                    try:
                        result = AIService.train_defect_model(factory_id)
                        acc = result.get("metrics", {}).get("accuracy", "N/A")
                        logger.info(f"[Scheduler] Factory {factory_id} retrained — accuracy: {acc}")
                    except Exception as e:
                        logger.error(f"[Scheduler] Factory {factory_id} retrain failed: {e}")

            except Exception as e:
                logger.error(f"[Scheduler] Retrain job error: {e}")

    # Run every Sunday at 02:00 UTC
    _scheduler.add_job(
        func=retrain_all_factories,
        trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="weekly_retrain",
        name="Weekly AI Model Retraining",
        replace_existing=True,
    )

    # Also schedule daily anomaly detection at 06:00 UTC
    def daily_anomaly_scan():
        with app.app_context():
            try:
                from models import db
                from sqlalchemy import text
                from services.ai_service import AIService

                rows = db.session.execute(
                    text("SELECT id FROM factories WHERE is_active = TRUE")
                ).fetchall()

                for row in rows:
                    try:
                        AIService.detect_anomaly(row[0], days=1)
                    except Exception as e:
                        logger.error(f"[Scheduler] Anomaly scan factory {row[0]}: {e}")
            except Exception as e:
                logger.error(f"[Scheduler] Daily anomaly error: {e}")

    _scheduler.add_job(
        func=daily_anomaly_scan,
        trigger=CronTrigger(hour=6, minute=0),
        id="daily_anomaly",
        name="Daily Anomaly Detection",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("[Scheduler] Started — weekly retrain (Sun 02:00) + daily anomaly (06:00)")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Stopped")

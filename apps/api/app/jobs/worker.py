from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.jobs.reminders import send_due_reminders

settings = get_settings()


class WorkerSettings:
    """Entry point for `arq app.jobs.worker.WorkerSettings` (see the `worker`
    service in docker-compose.yml). No regular queued jobs yet — just the
    reminders cron — but functions=[] is where those would be listed."""

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    cron_jobs = [cron(send_due_reminders, second=0)]

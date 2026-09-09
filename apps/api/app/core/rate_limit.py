from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()

# Backed by Redis (not in-memory) so limits hold across the multiple worker
# processes/replicas a real deployment would run, not just per-process.
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)

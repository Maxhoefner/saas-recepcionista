from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.rate_limit import limiter

settings = get_settings()

app = FastAPI(
    title="AI Receptionist API",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
)

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,  # type: ignore[arg-type]  # slowapi's handler is typed
    # narrower (RateLimitExceeded) than Starlette's generic Exception — correct at runtime.
)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

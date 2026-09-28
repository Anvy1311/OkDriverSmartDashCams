import asyncio
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .api.routes import alerts, auth, cameras, dashboard, events, system, watchlist
from .api.routes import realtime as realtime_routes
from .config import settings
from .database import SessionLocal, engine, init_db
from .realtime import realtime
from .seed import seed_demo_data
from .services.analytics_service import alert_to_dict, event_to_dict
from .services.background import run_heartbeat_cycle, run_simulator_cycle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("okdriver")
rate_state: dict[str, deque[float]] = defaultdict(deque)
rate_lock = asyncio.Lock()


async def heartbeat_loop() -> None:
    while True:
        await asyncio.sleep(settings.heartbeat_interval_seconds)
        try:
            with SessionLocal() as db:
                changes = run_heartbeat_cycle(db)
            for change in changes:
                await realtime.broadcast({"type": "camera.health", "camera": change})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Camera heartbeat cycle failed")


async def simulator_loop() -> None:
    while True:
        await asyncio.sleep(settings.simulator_interval_seconds)
        try:
            with SessionLocal() as db:
                event, alert = run_simulator_cycle(db)
            await realtime.broadcast(
                {
                    "type": "detection",
                    "event": event_to_dict(event, alert),
                    "alert": alert_to_dict(alert) if alert else None,
                }
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Simulator cycle failed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed_demo_data(db)
    tasks: list[asyncio.Task] = []
    if settings.heartbeat_enabled:
        tasks.append(asyncio.create_task(heartbeat_loop()))
    if settings.simulator_enabled:
        tasks.append(asyncio.create_task(simulator_loop()))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Unified CCTV registry, simulated multi-source video, analytics events, "
        "watchlist correlation, and real-time alerting."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Analytics-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    started = time.perf_counter()
    if request.url.path.startswith("/api/"):
        now = time.monotonic()
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{request.url.path}"
        limit = 12 if request.url.path.endswith("/auth/login") else settings.rate_limit_per_minute
        async with rate_lock:
            history = rate_state[key]
            while history and now - history[0] > 60:
                history.popleft()
            if len(history) >= limit:
                return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
            history.append(now)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.environment.lower() in {"production", "prod"}:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Request-Duration-ms"] = f"{(time.perf_counter() - started) * 1000:.2f}"
    return response


app.include_router(system.router)
app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(watchlist.router)
app.include_router(events.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)
app.include_router(realtime_routes.router)

static_directory = Path(__file__).resolve().parent.parent / "static"
delivery_directory = Path(__file__).resolve().parent.parent / "docs"
app.mount("/delivery", StaticFiles(directory=delivery_directory, html=True), name="delivery")
app.mount("/", StaticFiles(directory=static_directory, html=True), name="static")

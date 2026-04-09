import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.config import settings
from backend.api.auth.rate_limiter import limiter
from backend.api.auth.router import router as auth_router
from backend.api.routes.ideas import router as ideas_router
from backend.api.routes.confluence import router as confluence_router
from backend.api.routes.watchlist import router as watchlist_router
from backend.api.routes.portfolio import router as portfolio_router
from backend.api.routes.risk import router as risk_router
from backend.api.routes.journal import router as journal_router
from backend.api.routes.alerts import router as alerts_router
from backend.api.routes.analysis import router as analysis_router
from backend.api.routes.screener import router as screener_router
from backend.api.routes.performance import router as performance_router
from backend.api.routes.style import router as style_router
from backend.api.routes.data import router as data_router_api

logger = logging.getLogger(__name__)

# Silence yfinance's chatty 429 warnings — it's now a fallback path and
# rate-blocks are expected. The strategy layer handles empty results.
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("peewee").setLevel(logging.ERROR)

# Frontend build directory (built by Vite into frontend/dist/)
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    # 1. DB tables (Railway can't run alembic manually)
    try:
        from backend.db.database import create_all_tables
        await create_all_tables()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error("Failed to create database tables: %s", e)

    # 2. Warn on missing feed keys
    missing = settings.warn_if_feeds_missing()
    if missing:
        logger.error(
            "Missing required feed keys: %s — data layer will degrade",
            ", ".join(missing),
        )

    # 3. Initialise data layer
    try:
        from backend.data.feeds.data_router import init_data_router
        router_instance = init_data_router(
            twelve_api_key=settings.twelve_data_api_key,
            fred_api_key=settings.fred_api_key,
            finnhub_api_key=settings.finnhub_api_key,
        )
        logger.info("DataRouter ready")
    except Exception as e:
        logger.error("DataRouter init failed: %s", e)
        router_instance = None

    # 4. Start scheduler
    try:
        from backend.scheduler.jobs import start_scheduler
        n = start_scheduler()
        logger.info("Scheduler started — %d jobs registered", n)
    except Exception as e:
        logger.error("Scheduler start failed: %s", e)

    # 5. Warm cache (don't block startup on failure)
    if router_instance is not None:
        try:
            import asyncio as _asyncio
            from backend.data.initializer import initialise_data

            async def _bg_init():
                try:
                    await initialise_data(router_instance)
                except Exception as e:
                    logger.warning("Background data init failed: %s", e)

            _asyncio.create_task(_bg_init())
        except Exception as e:
            logger.warning("Could not schedule background init: %s", e)

    yield

    # Shutdown
    try:
        from backend.scheduler.jobs import stop_scheduler
        stop_scheduler()
    except Exception:
        pass
    try:
        from backend.db.redis import close_redis
        await close_redis()
    except Exception:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading Assistant",
        description="AI-powered trading intelligence system",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS — allow Railway domain, Cloudflare domain, and localhost for dev
    allowed_origins = ["http://localhost:3000", "http://localhost:5173"]
    if settings.railway_public_domain:
        allowed_origins.append(f"https://{settings.railway_public_domain}")
    if settings.cloudflare_domain:
        allowed_origins.append(f"https://{settings.cloudflare_domain}")
    if settings.log_level == "DEBUG":
        allowed_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(auth_router, tags=["auth"])
    app.include_router(ideas_router, prefix="/api", tags=["ideas"])
    app.include_router(confluence_router, prefix="/api", tags=["confluence"])
    app.include_router(watchlist_router, prefix="/api", tags=["watchlist"])
    app.include_router(portfolio_router, prefix="/api", tags=["portfolio"])
    app.include_router(risk_router, prefix="/api", tags=["risk"])
    app.include_router(journal_router, prefix="/api", tags=["journal"])
    app.include_router(alerts_router, prefix="/api", tags=["alerts"])
    app.include_router(analysis_router, prefix="/api", tags=["analysis"])
    app.include_router(screener_router, prefix="/api", tags=["screener"])
    app.include_router(performance_router, prefix="/api", tags=["performance"])
    app.include_router(style_router, prefix="/api", tags=["style"])
    app.include_router(data_router_api, prefix="/api", tags=["data"])

    # Serve frontend static files (Vite build output)
    if FRONTEND_DIR.exists():
        # Mount static assets (JS, CSS, images)
        assets_dir = FRONTEND_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # Serve other static files at root (favicon, etc.)
        @app.get("/favicon.svg")
        async def favicon():
            favicon_path = FRONTEND_DIR / "favicon.svg"
            if favicon_path.exists():
                return FileResponse(str(favicon_path))

        # SPA catch-all: serve index.html for all non-API routes
        @app.get("/{path:path}")
        async def serve_spa(request: Request, path: str):
            # Don't catch API or WebSocket routes
            if path.startswith("api/") or path.startswith("ws"):
                return
            # Try to serve the exact file first
            file_path = FRONTEND_DIR / path
            if file_path.is_file():
                return FileResponse(str(file_path))
            # Otherwise serve index.html for client-side routing
            index_path = FRONTEND_DIR / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))

    return app


app = create_app()

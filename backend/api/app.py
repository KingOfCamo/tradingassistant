from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading Assistant",
        description="AI-powered trading intelligence system",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.log_level == "DEBUG" else [f"https://{settings.cloudflare_domain}"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    return app


app = create_app()

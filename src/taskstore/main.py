import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from taskstore.api.errors import register_exception_handlers
from taskstore.api.middleware import register_middleware
from taskstore.logging_config import configure_logging

# Configure logging before any app imports do getLogger(__name__) to
# ensure their logs route through our handler. Reading env directly
# (not via pydantic settings) since we need this at import time.
configure_logging(
    level=os.environ.get("LOG_LEVEL", "info"),
    fmt=os.environ.get("LOG_FORMAT", "plain"),
)
logger = logging.getLogger("taskstore")

# Routers imported after logging config so any getLogger(__name__)
# calls at import time resolve through our handler.
from taskstore.api.audit import router as audit_router
from taskstore.api.comments import router as comments_router
from taskstore.api.fragment_links import router as fragment_links_router
from taskstore.api.fragments import router as fragments_router
from taskstore.api.health import router as health_router
from taskstore.api.issues import router as issues_router
from taskstore.api.labels import router as labels_router
from taskstore.api.notifications import router as notifications_router
from taskstore.api.projects import router as projects_router
from taskstore.api.rules import router as rules_router
from taskstore.api.sessions import router as sessions_router
from taskstore.api.setup import router as setup_router
from taskstore.api.states import router as states_router
from taskstore.api.summary import router as summary_router
from taskstore.api.teams import router as teams_router
from taskstore.api.users import router as users_router


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("adhed_startup", extra={"version": app.version})
    yield
    logger.info("adhed_shutdown")


app = FastAPI(
    title="ADHED",
    version="0.2.0",
    description="Headless task management for agents and claws",
    lifespan=_lifespan,
)

register_exception_handlers(app)
register_middleware(app)

app.include_router(health_router)
app.include_router(setup_router)
app.include_router(teams_router)
app.include_router(states_router)
app.include_router(users_router)
app.include_router(labels_router)
app.include_router(issues_router)
app.include_router(audit_router)
app.include_router(rules_router)
app.include_router(projects_router)
app.include_router(comments_router)
app.include_router(notifications_router)
app.include_router(summary_router)
app.include_router(fragments_router)
app.include_router(fragment_links_router)
app.include_router(sessions_router)

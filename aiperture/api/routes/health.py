"""Health check endpoint — database connectivity probe."""

import logging

from fastapi import APIRouter
from sqlalchemy import text
from sqlmodel import Session

from aiperture import plugins
from aiperture.db import get_engine

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
def health_check():
    """Check service health including database connectivity.

    Returns:
        200 with {"status": "healthy", "database": "connected"} when DB is reachable.
        200 with {"status": "degraded", "database": "error", "detail": "..."} when DB is unreachable.

    Always returns 200 so load balancers can distinguish between
    "service is up but degraded" vs "service is down".
    """
    result = {
        "service": "aiperture",
        "version": "0.2.0",
    }

    try:
        with Session(get_engine()) as session:
            session.execute(text("SELECT 1"))
        result["status"] = "healthy"
        result["database"] = "connected"
    except Exception as exc:
        detail = str(exc)
        logger.warning("Health check: database unreachable — %s", detail)
        result["status"] = "degraded"
        result["database"] = "error"
        result["detail"] = detail

    # Run plugin health checkers
    health_checker = plugins.get("health_checker")
    if health_checker is not None:
        try:
            plugin_result = health_checker.check()
            result[health_checker.name] = plugin_result
            if plugin_result.get("status") != "healthy":
                result["status"] = "degraded"
        except Exception as exc:
            result[health_checker.name] = {"status": "error", "detail": str(exc)}
            result["status"] = "degraded"

    return result

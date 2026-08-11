import time
from typing import Optional

from fastapi import APIRouter, Query

from baixar_social_media.core.config import settings
from baixar_social_media.services.log_buffer_service import log_buffer_service

router = APIRouter(prefix="/api/system", tags=["System"])

START_TIME = time.time()


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": "Baixar Social Media",
        "uptime_seconds": round(time.time() - START_TIME, 2),
    }


@router.get("/metrics")
def get_metrics():
    return {
        "uptime": round(time.time() - START_TIME, 2),
        "app_name": "Baixar Social Media",
        "debug_mode": settings.DEBUG,
        "host": settings.HOST,
        "port": settings.PORT,
    }


@router.get("/logs")
def get_system_logs(
    limit: int = Query(50, ge=1, le=500),
    level: Optional[str] = None,
    search: Optional[str] = None,
):
    return {
        "logs": log_buffer_service.get_logs(limit=limit, level=level, search=search)
    }


@router.post("/logs/clear")
def clear_system_logs():
    log_buffer_service.clear()
    return {"status": "ok", "message": "Logs limpos com sucesso"}

import os
import unicodedata
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

from app.services.downloader import DownloadError, downloader
from app.core.logger import get_logger

logger = get_logger()
router = APIRouter()

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))


def _safe_filename(title: str) -> str:
    """Normaliza o título para uso seguro como nome de arquivo."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = "".join(c for c in normalized if not unicodedata.combining(c))
    safe = "".join(c if (c.isalnum() or c in " ._-") else "_" for c in ascii_only)
    return safe.strip()[:120] or "video"


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.post("/download")
async def download_video(url: str = Form(...)):
    try:
        filename, title = await downloader.download_async(url)
    except DownloadError as e:
        logger.warning(f"Falha no download: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Erro inesperado no download: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao processar o vídeo.")

    safe_title = _safe_filename(title)
    return FileResponse(
        path=filename,
        filename=f"{safe_title}.mp4",
        media_type="video/mp4",
        background=BackgroundTask(os.unlink, filename),
    )

import shutil
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

from baixar_social_media.services.downloader import DownloadError, UnsafeURLError, downloader
from baixar_social_media.core.logger import get_logger

logger = get_logger()
router = APIRouter()

_BASE_DIR = Path(__file__).resolve().parent.parent
frontend = Jinja2Templates(directory=str(_BASE_DIR / "frontend"))



@router.get("/")
async def index(request: Request):
    return frontend.TemplateResponse(request, "index.html")


@router.post("/download")
async def download_media(
    url: str = Form(...),
    mode: str = Form("video"),
    audio_format: str = Form("opus"),
    playlist: bool = Form(False),
):
    try:
        result = await downloader.download_async(
            url, mode=mode, audio_format=audio_format, playlist=playlist
        )
    except UnsafeURLError as e:
        logger.warning(f"URL bloqueada por proteção anti-SSRF: {e}")
        raise HTTPException(status_code=400, detail="URL não permitida.")
    except DownloadError as e:
        logger.warning(f"Falha no download: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Erro inesperado no download: {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao processar a mídia.")

    return FileResponse(
        path=result.path,
        filename=result.filename,
        media_type=result.media_type,
        background=BackgroundTask(shutil.rmtree, result.workdir, ignore_errors=True),
    )

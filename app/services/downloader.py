import asyncio
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import yt_dlp

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger()

_executor = ThreadPoolExecutor(max_workers=settings.DOWNLOAD_MAX_WORKERS)


class DownloadError(Exception):
    pass


class UniversalDownloaderService:
    """Gerencia downloads de plataformas variadas usando a flexibilidade do yt-dlp."""

    def __init__(self) -> None:
        self.output_dir = tempfile.gettempdir()

    def download_video(self, url: str) -> tuple[str, str]:
        """Extrai e baixa a mídia de qualquer URL suportada pelo yt-dlp.

        Returns:
            tuple[str, str]: Caminho do arquivo local e o título original do vídeo.

        Raises:
            DownloadError: Se o yt-dlp falhar ao processar a URL.
        """
        output_template = os.path.join(self.output_dir, "%(id)s.%(ext)s")
        has_ffmpeg = shutil.which("ffmpeg") is not None

        ydl_opts: dict[str, Any] = {
            "outtmpl": output_template,
            "format": "bestvideo+bestaudio/best" if has_ffmpeg else "best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
        }
        if has_ffmpeg:
            ydl_opts["merge_output_format"] = "mp4"

        if not has_ffmpeg:
            logger.warning("ffmpeg não encontrado — usando qualidade pré-mesclada (instale ffmpeg para melhor qualidade).")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
                info = ydl.extract_info(url, download=True)
                title: str = info.get("title") or "video_baixado"
                filename = ydl.prepare_filename(info)
                if has_ffmpeg and not filename.endswith(".mp4"):
                    filename = os.path.splitext(filename)[0] + ".mp4"
        except Exception as e:
            raise DownloadError(f"Não foi possível baixar o vídeo: {e}") from e

        return filename, title

    async def download_async(self, url: str) -> tuple[str, str]:
        logger.info(f"Recebida solicitação de download: {url}")
        loop = asyncio.get_running_loop()
        filename, title = await loop.run_in_executor(_executor, self.download_video, url)
        logger.info(f"Download concluído: {title!r}")
        return filename, title


downloader = UniversalDownloaderService()

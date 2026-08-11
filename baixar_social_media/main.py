import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from baixar_social_media.core.config import settings
from baixar_social_media.routers.download import router
from baixar_social_media.routers.system import router as system_router
from baixar_social_media.core.logger import get_logger
from baixar_social_media.services.log_buffer_service import log_buffer_service

logger = get_logger()
frontend_dir = Path(__file__).resolve().parent / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(f"Servidor iniciado em http://{settings.HOST}:{settings.PORT}")
    yield
    logger.info("Servidor encerrado.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Downloader Universal de Vídeos",
        description="Servidor local para baixar vídeos de redes sociais via yt-dlp.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Captura logging padrão (logging.getLogger(__name__), incluindo o logger
    # nomeado de core/logger.py que propaga pro raiz) no buffer de logs da UI
    logging.getLogger().addHandler(log_buffer_service.get_handler())

    app.include_router(router)
    app.include_router(system_router)

    # Nota: a rota GET "/" já é servida pelo router de download (via Jinja2,
    # ver routers/download.py), então esse mount só disponibiliza os
    # arquivos da pasta frontend/ em /static — não há uma segunda rota "/"
    # aqui (existia uma antes, mas era inalcançável: o router acima já a
    # intercepta primeiro por ter sido registrado antes).
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Exceção não tratada em {request.url}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno do servidor."},
        )

    return app


app = create_app()


def start():
    import uvicorn
    uvicorn.run(
        "baixar_social_media.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    start()

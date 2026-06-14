from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routes.download import router
from app.core.logger import get_logger

logger = get_logger()


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

    app.include_router(router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Exceção não tratada em {request.url}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno do servidor."},
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

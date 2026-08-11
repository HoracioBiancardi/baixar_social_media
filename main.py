"""
Entrypoint principal do baixar_social_media.
Re-exporta a aplicação FastAPI de baixar_social_media.main para padronização de inicialização.
"""
from baixar_social_media.main import app

__all__ = ["app"]

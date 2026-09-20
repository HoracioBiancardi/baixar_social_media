from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = False
    DOWNLOAD_MAX_WORKERS: int = 4
    # Teto de tamanho de arquivo (bytes) aceito pelo yt-dlp por download. Default: 2GB.
    DOWNLOAD_MAX_FILESIZE_BYTES: int = 2 * 1024 * 1024 * 1024
    # Teto de duração (segundos) do vídeo/mídia a ser baixado. Default: 3h.
    DOWNLOAD_MAX_DURATION_SECONDS: int = 3 * 60 * 60
    # Máximo de itens baixados por playlist. Default: 100.
    DOWNLOAD_MAX_PLAYLIST_ITEMS: int = 100
    # Runtime JS usado pelo yt-dlp para resolver os desafios do YouTube
    # (node, deno, bun...). Precisa estar no PATH do processo do servidor.
    YTDLP_JS_RUNTIME: str = "node"
    # Clientes de player do YouTube, em ordem. Com o servidor bgutil (PO Token)
    # ativo, estes baixam sem 403 (o cliente padrão android_vr é bloqueado).
    YTDLP_YOUTUBE_CLIENTS: str = "mweb,web_music,web_embedded"


settings = Settings()

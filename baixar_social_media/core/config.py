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


settings = Settings()

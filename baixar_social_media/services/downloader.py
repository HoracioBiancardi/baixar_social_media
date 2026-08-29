import asyncio
import ipaddress
import os
import shutil
import socket
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse

import yt_dlp

from baixar_social_media.core.config import settings
from baixar_social_media.core.logger import get_logger

logger = get_logger()

_executor = ThreadPoolExecutor(max_workers=settings.DOWNLOAD_MAX_WORKERS)

_ALLOWED_SCHEMES = {"http", "https"}


class DownloadError(Exception):
    pass


class UnsafeURLError(ValueError):
    """URL rejeitada por apontar (direta ou indiretamente, via DNS) para um
    destino de rede não permitido — ex.: localhost, IP privado/link-local
    ou o endpoint de metadados de nuvem (169.254.169.254)."""


def _validate_public_url(url: str) -> tuple[str, str]:
    """Bloqueia SSRF: exige esquema http(s) e resolve o host para garantir
    que nenhum IP retornado seja privado, loopback, link-local ou reservado.

    Resolve via socket.getaddrinfo (não apenas compara a string do host),
    pois um hostname atacante-controlado pode resolver para um IP interno.

    Returns:
        tuple[str, str]: o hostname original da URL e o primeiro IP validado
        (público) para o qual ele resolveu — usados por `_pin_dns` para fixar
        a resolução DNS no momento do download real e evitar TOCTOU/DNS
        rebinding (host resolve pra IP público na validação e pra IP interno
        na conexão de fato, minutos/segundos depois).
    """
    parsed = urlparse(url)

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UnsafeURLError("Esquema de URL não permitido.")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL sem host válido.")

    try:
        addr_infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise UnsafeURLError(f"Não foi possível resolver o host: {e}") from e

    if not addr_infos:
        raise UnsafeURLError("Não foi possível resolver o host.")

    pinned_ip: str | None = None
    for info in addr_infos:
        raw_addr = info[4][0]
        # IPv6 pode vir com escopo (ex.: "fe80::1%eth0"); ipaddress não aceita isso.
        ip_str = raw_addr.split("%", 1)[0]
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise UnsafeURLError("URL aponta para um destino de rede não permitido.")
        if pinned_ip is None:
            pinned_ip = ip_str

    assert pinned_ip is not None  # addr_infos não está vazia (checado acima)
    return host, pinned_ip


# --- DNS pinning: evita TOCTOU/DNS rebinding entre _validate_public_url e o
# download real feito pelo yt-dlp (que resolve o host de novo internamente).
#
# O patch em socket.getaddrinfo é instalado uma única vez, de forma idempotente,
# no import do módulo. Cada thread do _executor mantém seu próprio mapeamento
# de pins (via threading.local), então downloads concorrentes para hosts
# diferentes não colidem nem restauram o patch um do outro.
_pin_state = threading.local()
_original_getaddrinfo = socket.getaddrinfo


def _pinned_getaddrinfo(host, *args, **kwargs):
    pins = getattr(_pin_state, "map", None)
    if pins and host in pins:
        host = pins[host]
    return _original_getaddrinfo(host, *args, **kwargs)


if socket.getaddrinfo is not _pinned_getaddrinfo:
    socket.getaddrinfo = _pinned_getaddrinfo


@contextmanager
def _pin_dns(hostname: str, resolved_ip: str):
    """Dentro do escopo, qualquer socket.getaddrinfo(hostname, ...) chamado
    NESTA thread retorna o mesmo IP já validado por _validate_public_url,
    em vez de disparar uma nova resolução DNS (que um atacante com DNS
    autoritativo próprio poderia responder com um IP interno)."""
    pins = getattr(_pin_state, "map", None)
    if pins is None:
        pins = {}
        _pin_state.map = pins

    previous = pins.get(hostname)
    pins[hostname] = resolved_ip
    try:
        yield
    finally:
        if previous is None:
            pins.pop(hostname, None)
        else:
            pins[hostname] = previous


class UniversalDownloaderService:
    """Gerencia downloads de plataformas variadas usando a flexibilidade do yt-dlp."""

    def __init__(self) -> None:
        self.output_dir = tempfile.gettempdir()

    def download_video(self, url: str) -> tuple[str, str]:
        """Extrai e baixa a mídia de qualquer URL suportada pelo yt-dlp.

        Returns:
            tuple[str, str]: Caminho do arquivo local e o título original do vídeo.

        Raises:
            UnsafeURLError: Se a URL não passar na validação anti-SSRF.
            DownloadError: Se o yt-dlp falhar ao processar a URL.
        """
        host, pinned_ip = _validate_public_url(url)

        output_template = os.path.join(self.output_dir, "%(id)s.%(ext)s")
        has_ffmpeg = shutil.which("ffmpeg") is not None

        ydl_opts: dict[str, Any] = {
            "outtmpl": output_template,
            "format": "bestvideo+bestaudio/best" if has_ffmpeg else "best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "max_filesize": settings.DOWNLOAD_MAX_FILESIZE_BYTES,
        }
        if has_ffmpeg:
            ydl_opts["merge_output_format"] = "mp4"

        if not has_ffmpeg:
            logger.warning("ffmpeg não encontrado — usando qualidade pré-mesclada (instale ffmpeg para melhor qualidade).")

        # Fixa a resolução DNS no IP já validado por _validate_public_url para
        # toda a duração da extração/download (ver _pin_dns): impede que uma
        # segunda resolução (feita internamente pelo yt-dlp no momento da
        # conexão real) responda um IP interno diferente do que foi validado
        # (DNS rebinding / TOCTOU).
        try:
            with _pin_dns(host, pinned_ip):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
                    probe_info = ydl.extract_info(url, download=False)
                    duration = (probe_info or {}).get("duration")
                    if duration is not None and duration > settings.DOWNLOAD_MAX_DURATION_SECONDS:
                        raise DownloadError(
                            f"Vídeo excede a duração máxima permitida "
                            f"({settings.DOWNLOAD_MAX_DURATION_SECONDS}s)."
                        )

                    info = ydl.extract_info(url, download=True)
                    title: str = info.get("title") or "video_baixado"
                    filename = ydl.prepare_filename(info)
                    if has_ffmpeg and not filename.endswith(".mp4"):
                        filename = os.path.splitext(filename)[0] + ".mp4"
        except DownloadError:
            raise
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

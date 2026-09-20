import asyncio
import ipaddress
import os
import re
import shutil
import socket
import tempfile
import threading
import unicodedata
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
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


@dataclass
class DownloadResult:
    """Arquivo pronto para envio. `workdir` é o diretório temporário da
    requisição — o chamador deve removê-lo após enviar o arquivo."""

    path: str
    filename: str
    media_type: str
    workdir: str


_AUDIO_CODECS = {"mp3", "m4a", "opus", "flac", "wav"}
_MEDIA_TYPES = {
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "opus": "audio/ogg",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "mp4": "video/mp4",
    "webm": "audio/webm",
    "zip": "application/zip",
}


_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')


def _safe_name(title: str) -> str:
    """Mantém o título original (acentos, emojis, etc.), removendo apenas o
    que é inválido em nomes de arquivo ou permitiria path traversal."""
    safe = _INVALID_FILENAME_CHARS.sub("_", unicodedata.normalize("NFC", title))
    safe = safe.strip().strip(".")  # evita nomes ocultos/".."
    return safe[:120].strip() or "midia"


class _ErrorCollector:
    """Logger do yt-dlp que guarda as mensagens de erro — com ignoreerrors
    (playlist) o yt-dlp não levanta exceção, e sem isso a causa se perderia."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def debug(self, msg: str) -> None:
        pass

    warning = debug

    def error(self, msg: str) -> None:
        self.errors.append(msg)


class UniversalDownloaderService:
    """Gerencia downloads de plataformas variadas usando a flexibilidade do yt-dlp."""

    def download_media(
        self,
        url: str,
        mode: str = "video",
        audio_format: str = "opus",
        playlist: bool = False,
    ) -> DownloadResult:
        """Baixa vídeo ou áudio (melhor qualidade disponível) de uma URL.

        Com `playlist=True` baixa todos os itens (até DOWNLOAD_MAX_PLAYLIST_ITEMS)
        e devolve um .zip; caso contrário, apenas o item da URL.

        Raises:
            UnsafeURLError: Se a URL não passar na validação anti-SSRF.
            DownloadError: Se o yt-dlp falhar ou algum limite for excedido.
        """
        if mode not in ("video", "audio"):
            raise DownloadError("Modo inválido.")
        if audio_format not in _AUDIO_CODECS:
            raise DownloadError("Formato de áudio inválido.")

        host, pinned_ip = _validate_public_url(url)

        workdir = tempfile.mkdtemp(prefix="bsm_")
        try:
            return self._run(url, host, pinned_ip, workdir, mode, audio_format, playlist)
        except DownloadError:
            shutil.rmtree(workdir, ignore_errors=True)
            raise
        except Exception as e:
            shutil.rmtree(workdir, ignore_errors=True)
            raise DownloadError(f"Não foi possível baixar a mídia: {e}") from e

    def _run(
        self,
        url: str,
        host: str,
        pinned_ip: str,
        workdir: str,
        mode: str,
        audio_format: str,
        playlist: bool,
    ) -> DownloadResult:
        has_ffmpeg = shutil.which("ffmpeg") is not None
        max_duration = settings.DOWNLOAD_MAX_DURATION_SECONDS

        def _match_filter(info: dict[str, Any], *, incomplete: bool = False) -> str | None:
            duration = info.get("duration")
            if duration is not None and duration > max_duration:
                return f"Mídia excede a duração máxima permitida ({max_duration}s)."
            return None

        collector = _ErrorCollector()
        ydl_opts: dict[str, Any] = {
            "outtmpl": os.path.join(workdir, "%(playlist_index&{} - |)s%(title).100B [%(id)s].%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "logger": collector,
            "windowsfilenames": True,
            "noplaylist": not playlist,
            "max_filesize": settings.DOWNLOAD_MAX_FILESIZE_BYTES,
            "match_filter": _match_filter,
            "js_runtimes": {settings.YTDLP_JS_RUNTIME: {}},
            "extractor_args": {"youtube": {"player_client": settings.YTDLP_YOUTUBE_CLIENTS.split(",")}},
            "ignoreerrors": "only_download" if playlist else False,
        }
        if playlist:
            ydl_opts["playlistend"] = settings.DOWNLOAD_MAX_PLAYLIST_ITEMS

        out_ext = "mp4"
        if mode == "audio":
            ydl_opts["format"] = "bestaudio/best"
            if has_ffmpeg:
                out_ext = audio_format
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": audio_format,
                        # 0 = melhor qualidade VBR; ignorado por codecs sem perda.
                        "preferredquality": "0" if audio_format != "mp3" else "320",
                    }
                ]
            else:
                out_ext = ""  # mantém o formato nativo (m4a/webm) sem conversão
                logger.warning("ffmpeg não encontrado — áudio entregue no formato original, sem conversão.")
        else:
            ydl_opts["format"] = "bestvideo+bestaudio/best" if has_ffmpeg else "best[ext=mp4]/best"
            if has_ffmpeg:
                ydl_opts["merge_output_format"] = "mp4"
            else:
                logger.warning("ffmpeg não encontrado — usando qualidade pré-mesclada.")

        # Fixa a resolução DNS no IP já validado (ver _pin_dns): impede DNS
        # rebinding entre a validação e a conexão real feita pelo yt-dlp.
        with _pin_dns(host, pinned_ip):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[arg-type]
                info = ydl.extract_info(url, download=True)

        if not info:
            raise DownloadError("Nenhuma informação retornada para a URL.")

        files = sorted(
            os.path.join(workdir, f) for f in os.listdir(workdir) if not f.endswith((".part", ".ytdl"))
        )
        if not files:
            detail = collector.errors[-1] if collector.errors else "verifique limites de tamanho/duração."
            raise DownloadError(f"Nenhum arquivo foi baixado: {detail}")

        if collector.errors:
            logger.warning(f"{len(collector.errors)} item(ns) falharam: {collector.errors[-1]}")

        title = info.get("title") or "midia_baixada"

        if playlist and info.get("_type") == "playlist" and len(files) > 1:
            zip_path = os.path.join(workdir, "playlist.zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
                for f in files:
                    zf.write(f, arcname=os.path.basename(f))
            return DownloadResult(zip_path, f"{_safe_name(title)}.zip", _MEDIA_TYPES["zip"], workdir)

        path = files[0]
        ext = os.path.splitext(path)[1].lstrip(".").lower()
        return DownloadResult(
            path,
            f"{_safe_name(title)}.{ext or out_ext}",
            _MEDIA_TYPES.get(ext, "application/octet-stream"),
            workdir,
        )

    async def download_async(self, url: str, **kwargs: Any) -> DownloadResult:
        logger.info(f"Recebida solicitação de download: {url} {kwargs}")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(_executor, partial(self.download_media, url, **kwargs))
        logger.info(f"Download concluído: {result.filename!r}")
        return result


downloader = UniversalDownloaderService()

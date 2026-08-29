import socket

import pytest

from baixar_social_media.services import downloader as downloader_module
from baixar_social_media.services.downloader import UnsafeURLError, _validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/secret",
        "http://127.0.0.1:8000/",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",  # metadados de nuvem (AWS/GCP/Azure)
        "http://0.0.0.0/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]/",
    ],
)
def test_rejects_private_and_loopback_urls(url):
    with pytest.raises(UnsafeURLError):
        _validate_public_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/video.mp4",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "",
    ],
)
def test_rejects_disallowed_schemes(url):
    with pytest.raises(UnsafeURLError):
        _validate_public_url(url)


def test_accepts_public_https_url():
    # 8.8.8.8 é um endereço público (Google DNS) usado só para validar que a
    # checagem de IP público não bloqueia destinos legítimos.
    _validate_public_url("https://8.8.8.8/video")


def test_validate_public_url_returns_host_and_pinned_ip():
    host, pinned_ip = _validate_public_url("https://8.8.8.8/video")
    assert host == "8.8.8.8"
    assert pinned_ip == "8.8.8.8"


def test_dns_pinning_prevents_rebinding(monkeypatch):
    """Simula DNS rebinding: um host malicioso responde um IP público na
    validação (1ª consulta) e um IP interno (metadados de nuvem) numa
    resolução DNS subsequente — o cenário que burlaria _validate_public_url
    se a URL original (não o IP já validado) fosse repassada pro yt-dlp.

    Prova que, dentro do escopo de `_pin_dns`, uma resolução para o mesmo
    hostname não dispara uma nova consulta DNS (que o atacante poderia
    responder com o IP interno) — em vez disso, retorna o IP já validado.
    """
    hostname = "attacker-controlled.example.test"
    public_ip = "93.184.216.34"
    rebind_ip = "169.254.169.254"  # endpoint de metadados de nuvem

    call_count = {"n": 0}

    def fake_getaddrinfo(host, *args, **kwargs):
        if host == hostname:
            call_count["n"] += 1
            ip = public_ip if call_count["n"] == 1 else rebind_ip
        else:
            # host já é um IP literal (pin aplicado) — getaddrinfo real não
            # faz consulta DNS nesse caso, só "reformata" o próprio literal.
            ip = host
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    monkeypatch.setattr(downloader_module, "_original_getaddrinfo", fake_getaddrinfo)

    # 1ª resolução (validação): host malicioso responde IP público -> passa.
    host, pinned_ip = downloader_module._validate_public_url(f"https://{hostname}/video")
    assert host == hostname
    assert pinned_ip == public_ip

    # Sem proteção: uma 2ª resolução "real" pro mesmo host (como o yt-dlp
    # faria internamente) já viria com o IP interno — a vulnerabilidade
    # TOCTOU que o pinning existe para fechar.
    unprotected = socket.getaddrinfo(hostname, None)
    assert unprotected[0][4][0] == rebind_ip
    assert call_count["n"] == 2

    # Com o pin ativo, uma nova resolução para o MESMO host não dispara mais
    # consulta DNS nenhuma (call_count não avança) e retorna o IP já validado.
    with downloader_module._pin_dns(host, pinned_ip):
        pinned_result = socket.getaddrinfo(hostname, None)

    assert pinned_result[0][4][0] == pinned_ip
    assert pinned_result[0][4][0] != rebind_ip
    assert call_count["n"] == 2  # nenhuma nova consulta DNS ocorreu

    # Fora do escopo do pin, o comportamento (vulnerável, sem a defesa) volta:
    # prova que _pin_dns restaura o estado anterior ao sair.
    after_scope = socket.getaddrinfo(hostname, None)
    assert after_scope[0][4][0] == rebind_ip
    assert call_count["n"] == 3

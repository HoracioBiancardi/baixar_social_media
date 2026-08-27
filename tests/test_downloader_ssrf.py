import pytest

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

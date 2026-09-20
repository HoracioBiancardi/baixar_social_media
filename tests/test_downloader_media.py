import os
import shutil
import zipfile

import pytest

from baixar_social_media.services import downloader as dm
from baixar_social_media.services.downloader import DownloadError, downloader


class FakeYDL:
    captured: dict = {}
    files: list[str] = []
    info: dict = {}

    def __init__(self, opts):
        FakeYDL.captured = opts
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=True):
        workdir = os.path.dirname(self.opts["outtmpl"])
        for name in FakeYDL.files:
            with open(os.path.join(workdir, name), "wb") as f:
                f.write(b"x")
        return FakeYDL.info


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(dm, "_validate_public_url", lambda url: ("example.com", "93.184.216.34"))
    monkeypatch.setattr(dm.yt_dlp, "YoutubeDL", FakeYDL)


def test_audio_with_ffmpeg_extracts_best_quality(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/ffmpeg")
    FakeYDL.files, FakeYDL.info = ["a.mp3"], {"title": "Música Ç"}
    r = downloader.download_media("https://x", mode="audio", audio_format="mp3")
    try:
        assert FakeYDL.captured["format"] == "bestaudio/best"
        assert FakeYDL.captured["postprocessors"][0]["preferredcodec"] == "mp3"
        assert FakeYDL.captured["noplaylist"] is True
        assert r.filename == "Música Ç.mp3" and r.media_type == "audio/mpeg"
    finally:
        shutil.rmtree(r.workdir)


def test_playlist_returns_zip(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/ffmpeg")
    FakeYDL.files = ["1 - a.mp3", "2 - b.mp3"]
    FakeYDL.info = {"title": "Minha Playlist", "_type": "playlist"}
    r = downloader.download_media("https://x", mode="audio", playlist=True)
    try:
        assert FakeYDL.captured["noplaylist"] is False
        assert r.filename == "Minha Playlist.zip"
        assert sorted(zipfile.ZipFile(r.path).namelist()) == ["1 - a.mp3", "2 - b.mp3"]
    finally:
        shutil.rmtree(r.workdir)


def test_invalid_mode_and_codec():
    with pytest.raises(DownloadError):
        downloader.download_media("https://x", mode="foo")
    with pytest.raises(DownloadError):
        downloader.download_media("https://x", mode="audio", audio_format="exe")


def test_no_files_raises_and_cleans_workdir(monkeypatch):
    FakeYDL.files, FakeYDL.info = [], {"title": "t"}
    with pytest.raises(DownloadError):
        downloader.download_media("https://x")


def test_safe_name_keeps_unicode_and_strips_invalid_chars():
    assert dm._safe_name("A Vida É Um Game") == "A Vida É Um Game"
    assert dm._safe_name('AC/DC: "Back" in Black?') == "AC_DC_ _Back_ in Black_"
    assert dm._safe_name("../../etc/passwd") == "_.._etc_passwd"
    assert dm._safe_name("...") == "midia"

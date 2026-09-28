"""Whisper model cache inspection and progress-aware, atomic downloads."""

import hashlib
import os
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def cache_root():
    base = os.getenv("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "whisper"


def model_specs():
    import whisper

    return whisper._MODELS


def model_path(name):
    url = model_specs().get(name)
    if url is None:
        raise ValueError(f"Whisper 不支持模型 {name}")
    return cache_root() / Path(urlparse(url).path).name


def inventory():
    return [(name, model_path(name), model_path(name).is_file())
            for name in model_specs()]


def ensure_model(name, progress=None, cancelled=None):
    """Return a SHA-verified model file; leave existing cache intact on failure."""
    url = model_specs().get(name)
    if url is None:
        raise ValueError(f"Whisper 不支持模型 {name}")
    target = model_path(name)
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = url.split("/")[-2]

    def report(phase, done=0, total=0):
        if progress:
            progress(phase, done, total)

    def check_cancel():
        if cancelled and cancelled():
            raise RuntimeError("Whisper 初始化已取消")

    if target.is_file():
        report("verify", 0, target.stat().st_size)
        digest = hashlib.sha256()
        with target.open("rb") as existing:
            while chunk := existing.read(1024 * 1024):
                check_cancel()
                digest.update(chunk)
        if digest.hexdigest() == expected:
            report("ready", target.stat().st_size, target.stat().st_size)
            return target

    part = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    downloaded = 0
    last_report = 0.0
    try:
        check_cancel()
        with urllib.request.urlopen(url, timeout=30) as source, part.open("wb") as output:
            total = int(source.headers.get("Content-Length") or 0)
            report("download", 0, total)
            while chunk := source.read(256 * 1024):
                check_cancel()
                output.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if now - last_report >= .15:
                    report("download", downloaded, total)
                    last_report = now
        if digest.hexdigest() != expected:
            raise RuntimeError("Whisper 模型校验失败，请检查网络后重试")
        part.replace(target)
        report("ready", downloaded, downloaded)
        return target
    finally:
        part.unlink(missing_ok=True)

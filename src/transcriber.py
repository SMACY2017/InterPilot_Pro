"""Lazy ASR: no model import or download on GUI startup."""
import threading
from dataclasses import replace
from pathlib import Path
from src.llm_client import create_openai_client
from src.settings import Settings
from src.whisper_models import cache_root, ensure_model


class SpeechTranscriber:
    _models = {}
    _locks = {}
    _guard = threading.Lock()

    def __init__(self, model_size=None, settings=None):
        self.settings = settings or Settings()
        self.model_size = model_size or self.settings.whisper_model

    def preload(self, progress=None, cancelled=None):
        if self.settings.asr_backend == "local":
            self._local_model(self.model_size, progress, cancelled)

    @classmethod
    def _local_model(cls, model_size, progress=None, cancelled=None):
        with cls._guard:
            lock = cls._locks.setdefault(model_size, threading.Lock())
        with lock:
            if model_size not in cls._models:
                import whisper
                ensure_model(model_size, progress, cancelled)
                if progress:
                    progress("load", 0, 0)
                cls._models[model_size] = whisper.load_model(
                    model_size, download_root=str(cache_root()))
                if progress:
                    progress("ready", 1, 1)
            return cls._models[model_size], lock

    def transcribe(self, audio_path):
        if Path(audio_path).stat().st_size <= 44:
            return ""
        if self.settings.asr_backend == "cloud":
            with create_openai_client(cloud_settings(self.settings)) as client:
                with open(audio_path, "rb") as source:
                    result = client.audio.transcriptions.create(
                        model=self.settings.asr_model, file=source)
                return result.text.strip()
        model, lock = self._local_model(self.model_size)
        options = {"fp16": str(model.device).startswith("cuda"),
                   "condition_on_previous_text": False}
        if self.settings.language != "auto":
            options["language"] = self.settings.language
        with lock:
            return model.transcribe(str(audio_path), **options)["text"].strip()


def cloud_settings(settings):
    """Use a separate ASR provider when configured; otherwise share the LLM API."""
    if not settings.asr_api_url.strip():
        return settings
    return replace(settings, api_url=settings.asr_api_url.strip(),
                   api_key=settings.asr_api_key,
                   endpoint_type=settings.asr_endpoint_type)

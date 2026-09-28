"""On-demand checks for the capture, transcription, and answer paths."""

import math
import tempfile
import time
import wave
from array import array
from dataclasses import replace
from pathlib import Path

from src.llm_client import LLMClient, safe_error
from src.transcriber import SpeechTranscriber


def check_capture(settings):
    import pyaudiowpatch as pa

    sources = []
    if settings.mic_enabled:
        sources.append(("麦克风", settings.mic_device, False))
    if settings.system_enabled:
        sources.append(("系统声音", settings.system_device, True))
    if not sources:
        raise ValueError("没有启用任何音频通道")
    with pa.PyAudio() as audio:
        for name, index, loopback in sources:
            info = (audio.get_default_wasapi_loopback() if loopback else
                    audio.get_default_input_device_info()) if index < 0 else audio.get_device_info_by_index(index)
            if bool(info.get("isLoopbackDevice", False)) != loopback:
                raise ValueError(f"{name}选中的设备类型不匹配，请刷新设备")
            channels = int(info["maxInputChannels"])
            if channels < 1:
                raise ValueError(f"{name}设备没有输入通道")
            stream = audio.open(format=pa.paInt16, channels=channels,
                                rate=int(info["defaultSampleRate"]), input=True,
                                input_device_index=int(info["index"]),
                                frames_per_buffer=1024)
            try:
                time.sleep(.15)
                if not stream.is_active():
                    raise RuntimeError(f"{name}设备打开后未保持活动")
            finally:
                stream.stop_stream()
                stream.close()
    return "、".join(name for name, _, _ in sources) + "设备可打开"


def test_audio_file(path):
    rate = 16000
    samples = array("h", (int(1800 * math.sin(2 * math.pi * 440 * n / rate))
                          for n in range(rate * 2)))
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(samples.tobytes())


def check_transcription(settings, progress=None):
    transcriber = SpeechTranscriber(settings=settings)
    if settings.asr_backend == "local":
        transcriber.preload(progress=progress)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "interpilot-check.wav"
        test_audio_file(path)
        transcriber.transcribe(path)
    return (f"Whisper {settings.whisper_model} 已加载并完成一次本地推理" if
            settings.asr_backend == "local" else
            f"云端音频模型 {settings.asr_model} 已接受测试音频")


def check_answer(settings):
    test_settings = replace(settings, max_tokens=min(settings.max_tokens, 64),
                            enable_thinking=False)
    with LLMClient(settings=test_settings) as client:
        response = client.get_response("请只回复 OK。", system_prompt="你是连接测试助手，简短回答。")
    if not response.strip():
        raise RuntimeError("回答模型没有返回正文")
    return f"回答模型 {settings.model} 已返回流式正文"


def run_diagnostics(settings, report, progress=None):
    """Run independent checks, reporting each failure and a final summary."""
    checks = [("音频设备", check_capture), ("语音转写", check_transcription),
              ("回答模型", check_answer)]
    failed = 0
    for label, check in checks:
        report(f"正在检查{label}…")
        try:
            detail = check(settings, progress) if label == "语音转写" else check(settings)
            report(f"✓ {label}：{detail}")
        except Exception as exc:
            failed += 1
            report(f"✕ {label}：{safe_error(exc, (settings.api_key, settings.asr_api_key))}")
    report("检查完成：全部通过。" if not failed else
           f"检查完成：{failed} 项未通过，请按上方提示调整设置后重试。")
    return failed == 0

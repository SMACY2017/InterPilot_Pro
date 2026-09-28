"""Text and image requests with isolated, cancellable streams."""
import base64
import ipaddress
import threading
from urllib.parse import urlparse

import httpx
from openai import OpenAI
from src.settings import load_settings


def safe_error(exc, secret=""):
    status = getattr(exc, "status_code", None)
    if status == 504:
        return ("API 请求失败（HTTP 504）。若目标是本地或内网模型，请在设置中把服务位置改为"
                "“本地 / 内网自建”，以绕过公司 HTTP 代理。")
    if status == 404:
        return "API 请求失败（HTTP 404），请检查 API 地址是否包含正确的 /v1 路径以及模型 ID。"
    if status in (401, 403):
        return f"API 请求失败（HTTP {status}），请检查密钥和模型访问权限。"
    if status:
        return f"API 请求失败（HTTP {status}），请检查密钥、模型权限、额度和请求大小。"
    message = str(exc).replace(secret, "[已隐藏]") if secret else str(exc)
    if type(exc).__module__.startswith(("openai", "httpx", "httpcore")):
        return f"连接失败：{type(exc).__name__}，请检查网络或超时设置。"
    return message[:400]


def image_content(data, mime="image/png"):
    return {"type": "image_url", "image_url": {
        "url": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}",
        "detail": "high"}}


def is_self_hosted_endpoint(api_url, endpoint_type="auto"):
    """Return whether requests should ignore environment proxy variables."""
    if endpoint_type == "self_hosted":
        return True
    if endpoint_type == "hosted":
        return False
    host = (urlparse(api_url).hostname or "").lower().rstrip(".")
    if not host:
        return False
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(host)
        return bool(address.is_loopback or address.is_private or
                    address.is_link_local or address.is_reserved)
    except ValueError:
        # Single-label hosts and these suffixes are normally resolved only on
        # the local network. Other private DNS zones can use the manual mode.
        return "." not in host or host.endswith(
            (".local", ".lan", ".internal", ".corp", ".home.arpa")
        )


def resolved_compatibility(settings, model=None, api_url=None):
    mode = settings.api_compatibility
    if mode != "auto":
        return mode
    url = api_url or settings.api_url
    if "siliconflow" in url.lower():
        return "siliconflow"
    if (is_self_hosted_endpoint(url, settings.endpoint_type) and
            "qwen" in (model or settings.model).lower()):
        return "sglang"
    return "generic"


def create_openai_client(settings, api_url=None, api_key=None):
    """Build one SDK client, bypassing corporate proxies for self-hosted APIs."""
    url = api_url or settings.api_url
    kwargs = {
        "api_key": ((api_key if api_key is not None else settings.api_key) or
                    "not-required"),
        "base_url": url,
        "timeout": settings.timeout,
        "max_retries": 0,
    }
    transport = None
    if is_self_hosted_endpoint(url, settings.endpoint_type):
        transport = httpx.Client(
            trust_env=False,
            timeout=settings.timeout,
            follow_redirects=True,
        )
        kwargs["http_client"] = transport
    try:
        return OpenAI(**kwargs)
    except Exception:
        if transport is not None:
            transport.close()
        raise


def thinking_request_options(settings, model=None, api_url=None):
    mode = resolved_compatibility(settings, model, api_url)
    if mode == "siliconflow":
        body = {"enable_thinking": settings.enable_thinking}
        if settings.enable_thinking:
            body["thinking_budget"] = settings.thinking_budget
        return {"extra_body": body}
    if mode == "sglang":
        return {"extra_body": {"chat_template_kwargs": {
            "enable_thinking": settings.enable_thinking,
        }}}
    return {}


class LLMClient:
    def __init__(self, api_url=None, api_key=None, model=None, settings=None, client=None):
        self.settings = settings or load_settings()
        self.model = model or self.settings.model
        self.api_url = api_url or self.settings.api_url
        self.client = client or create_openai_client(self.settings, self.api_url, api_key)

    def close(self):
        self.client.close()

    def list_models(self):
        return sorted(item.id for item in self.client.models.list().data)

    def get_response(self, prompt, callback=None, *, image=None, cancel=None,
                     system_prompt=None, activity_callback=None):
        cancel = cancel or threading.Event()
        if cancel.is_set():
            return ""
        content = prompt
        if image:
            content = [image_content(image), {"type": "text", "text": prompt}]
        messages = [
            {"role": "system", "content": self.settings.system_prompt if system_prompt is None else system_prompt},
            {"role": "user", "content": content},
        ]
        parts = []
        reasoning_seen = False
        finish_reason = None
        request_options = thinking_request_options(
            self.settings, self.model, self.api_url
        )
        stream = self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True,
            max_tokens=self.settings.max_tokens,
            **request_options,
        )
        try:
            for chunk in stream:
                if cancel.is_set():
                    break
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                finish_reason = getattr(choice, "finish_reason", None) or finish_reason
                delta = choice.delta
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    reasoning_seen = True
                    if activity_callback:
                        activity_callback()
                text = getattr(delta, "content", None)
                if text:
                    parts.append(text)
                    if callback:
                        callback(text)
        finally:
            close = getattr(stream, "close", None)
            if close:
                close()
        if not parts and not cancel.is_set():
            if reasoning_seen:
                suffix = "且达到 token 上限" if finish_reason == "length" else ""
                raise RuntimeError(
                    f"模型只返回了推理内容{suffix}，没有最终回答。请关闭深度思考，"
                    "SGLang/vLLM 请选择对应兼容模式；确需思考时请提高回答 token 上限。"
                )
            raise RuntimeError(
                "模型没有返回可显示的正文。请检查接口兼容模式、模型 ID 和流式输出支持。"
            )
        return "".join(parts)

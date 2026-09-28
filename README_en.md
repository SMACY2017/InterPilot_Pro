# InterPilot Pro

English | [中文](README.md)

InterPilot Pro is a Windows desktop assistant for paper presentations, meetings, and Q&A. It captures microphone and system-loopback audio as separate sources, transcribes the discussion, and combines recent speech with a slide screenshot and paper excerpts to produce concise, source-aware speaking notes.

Users are responsible for ensuring that recording, transcription, and data upload comply with meeting rules, participant consent requirements, and local law. Use headphones and keep unrelated notifications and media off the selected output device.

## Features

- Independent microphone and WASAPI loopback selection, enable switches, and level meters.
- Local Whisper or any compatible cloud audio transcription API with silence-aware chunking; local mode shows rolling drafts and corrects them after a pause.
- The local model list shows cache state and paths, and first-use download progress appears in the UI before capture begins.
- Cloud ASR can use its own endpoint, key, and model ID; one-click diagnostics check capture, transcription, and streamed answers separately.
- Semi-automatic mode: keep transcribing and request a hint with a button or global hotkey.
- Automatic mode: check new discussion for questions or objections and stay quiet when no useful hint is needed.
- Local PDF text extraction and page-level excerpts with physical PDF page references.
- A preselected monitor can be captured directly by hotkey, with manual region selection available as an option.
- One Settings window covers the API, model, prompts, audio devices, paper, initial image, screenshot strategy, and hotkeys. Both SiliconFlow and local OpenAI-compatible endpoints are supported.
- Available models can be fetched, searched, and selected from a dropdown. Thinking is disabled by default for low first-token latency, with an optional token budget.
- The API key is optional for local services. Remote keys can be stored with Windows DPAPI and are never written to JSON or Git.
- Localhost, loopback, and common private-network endpoints automatically bypass `HTTP_PROXY`; service location and SiliconFlow, SGLang/vLLM, or generic OpenAI compatibility can also be selected manually.
- Streaming output, connection reuse, first-token/total latency display, cancellation, session export, and page pinning.
- The answer pane receives most of the window by default; Focus mode hides the sidebar and transcript when needed.
- Focus mode can keep the transcript visible, while rolling ASR text remains at a fixed UI height.
- Optional always-on-top mode for reading hints above the presentation window.

The default answer/vision model is `Qwen/Qwen3.8-27B`. Actual model access depends on the account. Use Settings to test the connection, refresh the model list, or enter a model ID directly.

If you do not have an API key, you can register through the [SiliconFlow invitation link](https://cloud.siliconflow.cn/i/TzKmtDJH) with invite code `TzKmtDJH`. The original promotion offered invited new users CNY 14 in credits; check the platform for the current offer. After registering, open **API Keys** in the SiliconFlow console, create a key, and enter it in InterPilot Pro Settings. Available model IDs are listed in the [SiliconFlow model catalog](https://cloud.siliconflow.cn/models). Other OpenAI-compatible providers and keyless local endpoints are supported as well.

![InterPilot Pro presentation console](doc_pic/GUI.png)

## Presentation workflow

1. Wear headphones, silence notifications, and make sure the chosen output device mainly carries the online meeting.
2. In Settings, select the paper PDF, microphone, and loopback device for the headphones in use.
3. Select the monitor that will share the slides and use full-screen capture.
4. Start in semi-automatic mode and press `Ctrl+Alt+Enter` when you want a hint.
5. After changing slides, press `Ctrl+Alt+S` to capture the configured monitor and request a hint.
6. Enable automatic mode after the device and prompt behavior have been validated.

A clear screenshot is enough to test the visual Q&A path. It remains fixed until the capture hotkey replaces it.

## Default global hotkeys

| Action | Hotkey |
| --- | --- |
| Start / pause listening | `Ctrl+Alt+R` |
| Request a hint | `Ctrl+Alt+Enter` |
| Capture the configured monitor and request | `Ctrl+Alt+S` |
| Show / hide the window | `Ctrl+Alt+H` |

## Install and run

### Windows portable release

The Windows ZIP contains `InterPilot_Pro.exe` and its `_internal` folder. Extract the **whole archive to a writable directory** and run the exe. Python and a separate FFmpeg installation are not required. The first use of a local Whisper model still downloads its weights. Settings, encrypted keys, and exported sessions are stored beside the exe, so avoid placing the bundle under `Program Files`.

Before your first session, open **Settings → Audio & transcription**. The local Whisper list shows which models are cached and where. You can initialize the selected model there, or click Start Listening: the main window then shows download, verification, and loading progress **before audio capture starts**. The default cache is `~/.cache/whisper` for the current Windows user; `XDG_CACHE_HOME` overrides its parent directory. Download errors appear in the UI, so a release build needs no console.

For cloud transcription, select the OpenAI-compatible audio API. By default it shares the answer model's API URL and key. An independent audio URL can have its own key; leaving that key empty does not forward the answer model's key to the independent service. The default `FunAudioLLM/SenseVoiceSmall` is only a SiliconFlow example. The service's `/models` list may include non-audio models, so verify the chosen ID with the connection check. The separate audio key is stored using Windows DPAPI.

The one-click check briefly opens selected input devices, sends a generated two-second test audio through ASR, and asks the answer model for a short streamed response. Cloud calls may incur a small charge. This checks basic connectivity and execution, not meeting sound quality, recognition accuracy, or image understanding; try real speech and a screenshot before a live session.

To build the release yourself on Windows:

```powershell
python -m pip install -r requirements-build.txt
python packaging/build_windows.py
```

The ZIP and its SHA-256 checksum appear in `dist/`. Before publishing, verify launch, audio capture, transcription, and model requests on a Windows machine without Python installed.

### Run from source

Python 3.10 is recommended:

```powershell
conda create -n interpilot python=3.10
conda activate interpilot
pip install -r requirements.txt
python main.py
```

Local Whisper also requires FFmpeg. On Windows with Scoop:

```powershell
scoop install ffmpeg
```

Open Settings on first launch, enter the API URL and model ID, and add an API key only when the service requires one. Fetch the model list to test the connection, then select the transcription mode and models. Settings are stored in the Git-ignored `config.local.json`; an optionally remembered key is encrypted for the current Windows account in `config.key`. Do not place a real key in `config.ini`.

### Local OpenAI-compatible endpoints

Any local server that implements an OpenAI-compatible Chat Completions endpoint can be used without a key:

```text
API URL:  http://localhost:8100/v1
API key:  leave blank
Model ID: use the name exposed by the local server
```

Include the `/v1` path expected by the server. The model dropdown depends on `GET /models`; if the server does not implement it, enter the model ID manually. Screenshot requests also require a model and server that accept OpenAI-style image input. Clear the initial reference image and avoid “Capture & Ask” when using a text-only model.

On company-managed computers, HTTPX normally reads environment variables such as `HTTP_PROXY`. This can route localhost and intranet requests through a corporate proxy and cause a 504. With Service Location set to Auto, InterPilot Pro detects localhost, loopback and private IP addresses, single-label hosts, and common intranet suffixes, then disables environment proxies for that connection. Select Self-hosted manually for a private DNS suffix that cannot be detected. Hosted endpoints continue to use the system proxy.

For local Qwen deployments on SGLang or vLLM, keep API Compatibility on Auto or choose SGLang/vLLM explicitly. Disabling thinking sends `chat_template_kwargs.enable_thinking=false`, as required by SGLang's Qwen templates. SiliconFlow continues to receive its top-level `enable_thinking` and `thinking_budget` fields, while Generic OpenAI sends no vendor extension. When thinking is enabled on SGLang/vLLM, reasoning consumes the `max_tokens` allowance, so raise the total generation-token limit accordingly. See the [SGLang Qwen documentation](https://github.com/sgl-project/sglang/blob/main/docs_new/cookbook/autoregressive/Qwen/Qwen3.6.mdx).

## Data handling

- Local Whisper keeps transcription on the computer and deletes temporary WAV chunks after processing.
- Cloud ASR uploads audio chunks to the configured service.
- Hint requests send recent discussion, selected paper excerpts, and the current screenshot to the answer model.
- The PDF is parsed locally; only selected excerpts are included in requests.
- Exported sessions may contain meeting content and should be stored appropriately.

Source labels describe capture channels rather than verified speaker identities.

## Diagnostics and tests

```powershell
python main_cmd.py --list-devices
python main_cmd.py --audio output/test_record.wav --transcribe-only
pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q main.py main_cmd.py src
python -m ruff check main.py main_cmd.py src tests
```

Example paper/slide request:

```powershell
python main_cmd.py --paper pre/paper.pdf --image pre/slide.png --question "Explain the roles of the two stages on this slide"
```

Hardware capture still requires one manual test with the actual headset and microphone.

## Current limitations

- Local lexical page retrieval is designed for short papers; longer corpora would benefit from a vector index.
- References use physical PDF pages, which can differ from printed journal page numbers.
- Scanned PDFs need OCR first.
- Automatic hints can still false-trigger and should be calibrated before a live presentation.
- Screenshots do not update automatically when slides change.
- Rolling transcription drafts reduce visible latency but may change; only corrected final segments trigger automatic hint checks.
- The first version relies on the user to keep unrelated system sounds off the selected output device.

## License

Licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) for non-commercial use only.

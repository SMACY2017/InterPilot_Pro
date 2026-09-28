# InterPilot Pro

[English](README_en.md) | 中文

InterPilot Pro 是面向论文分享、会议和讨论的 Windows 桌面助手。它可以分别采集麦克风与系统声音，持续转写讨论，并结合当前幻灯片截图和论文 PDF，生成适合演讲者快速阅读的回答提示。

> 使用者应确保音频采集、转写和资料上传符合会议规则、参与者知情要求及当地法律。请使用耳机，并确保所选系统输出设备主要播放会议声音；关闭无关视频和通知声音。

## 已实现能力

- 麦克风与 WASAPI 系统回环可独立启用、选择设备和查看音量。
- 本地 Whisper 或 SiliconFlow 云端语音转写；本地模式可边说边显示临时结果，停顿后用完整分段校正。
- 本地 Whisper 模型列表标注已下载状态与缓存路径；首次使用会在界面内显示下载、校验和载入进度，准备完成后才开始采集音频。
- 云端转写支持任意兼容 OpenAI `/audio/transcriptions` 的服务，可独立设置地址、密钥和模型 ID；本地与云端的设置按所选方式分别显示。
- 设置中可一键检查音频设备、实际转写和流式回答，并逐项显示失败原因。
- 半自动模式：持续转写，按按钮或全局快捷键请求提示。
- 自动模式：仅在出现新的问题、质疑或相关讨论时检查并给出提示。
- 导入论文 PDF，按页面提取相关内容；回答要求标注文件名和 PDF 物理页码。
- 可预先选择指定显示器，快捷键直接截取整屏；也可切换为每次框选区域，再连同讨论和论文摘录发给视觉模型。
- 设置窗口统一配置 API、模型、提示词、音频设备、论文、初始图片、截图策略和快捷键；支持 SiliconFlow 及本机 OpenAI 兼容接口，主界面只保留演讲时需要的操作。
- 模型列表可从 API 获取、搜索和下拉选择；默认关闭深度思考以降低首字延迟，也可手动启用并限制思考 token。
- API key 为可选项；本地服务可留空，远程密钥可用 Windows DPAPI 按当前账户加密保存在本机，不写入 JSON 或 Git。
- 自动识别 localhost、回环和常见内网地址并绕过 `HTTP_PROXY`；支持手动指定服务位置和 SiliconFlow、SGLang/vLLM、通用 OpenAI 兼容模式。
- 流式回答、连接复用、首字/总耗时显示、取消请求、会话导出与论文页码优先指定。
- 即时提示默认占据主要空间；可拖动上下分隔线，或启用“专注提示”隐藏侧栏与讨论区。
- 专注阅读时可选择保留讨论；实时识别摘要保持固定高度，不会随临时文本伸缩界面。
- 可切换窗口置顶，便于在演讲或会议窗口上方查看短提示。

默认回答与视觉模型为 `Qwen/Qwen3.8-27B`。模型权限和能力以账户实际可用列表为准；可在设置中测试连接、刷新列表或直接填写模型 ID。SiliconFlow 的 OpenAI 兼容接口支持用 base64 图片调用视觉模型，详见其[视觉输入文档](https://docs.siliconflow.cn/docs/userguide/capabilities/vision)。

还没有 API key 的用户可以通过[硅基流动邀请链接](https://cloud.siliconflow.cn/i/TzKmtDJH)注册（邀请码 `TzKmtDJH`）。原活动为受邀新用户提供 14 元额度，实际赠送额度请以平台当前活动规则为准。注册后在控制台左侧进入“API 密钥”，新建密钥并填入 InterPilot Pro 的设置窗口；模型名称可在[模型广场](https://cloud.siliconflow.cn/models)查看。也可以使用其他 OpenAI 兼容服务，或使用下文介绍的无密钥本地接口。

![InterPilot Pro 演讲辅助控制台](doc_pic/GUI.png)

## 推荐的论文分享流程

1. 戴上耳机并关闭通知声音，确保系统回环主要包含线上会议声音。
2. 在“设置”中选择论文 PDF、麦克风和正在使用的耳机回环设备。
3. 选择正在共享 PPT 的显示器，并将截图方式设为“整屏”。
4. 先使用半自动模式，开始监听后用 `Ctrl+Alt+Enter` 请求提示。
5. 翻页后用 `Ctrl+Alt+S` 直接截取已设置的显示器并立即请求提示。
6. 设备和提示效果稳定后，再切换到自动模式。

一张清晰的 PPT 截图足以测试视觉问答链路。截图不会自动随 PPT 翻页更新，所以正式演讲中仍需按快捷键刷新；后续可增加低频自动截图与页面变化检测。

## 默认全局快捷键

| 功能 | 快捷键 |
| --- | --- |
| 开始 / 暂停监听 | `Ctrl+Alt+R` |
| 立即生成提示 | `Ctrl+Alt+Enter` |
| 截取预设屏幕并提示 | `Ctrl+Alt+S` |
| 显示 / 隐藏窗口 | `Ctrl+Alt+H` |

快捷键被其他程序占用时，InterPilot 会显示提示；可在设置中修改。快捷键需要至少一个 `Ctrl`、`Alt`、`Shift` 或 `Win` 修饰键。

## 安装与启动

### Windows 便携版

Windows 发布包是包含 `InterPilot_Pro.exe` 和 `_internal` 文件夹的 ZIP。请**完整解压到可写目录**，然后双击 exe；无需安装 Python 或另外安装 FFmpeg。首次选择本地 Whisper 时仍需下载模型，大小取决于所选规格。设置、加密密钥和会话导出默认写在 exe 同级目录，因此不建议直接放在 `Program Files` 下。

首次使用前建议打开“设置 → 音频与转写”：选择本地 Whisper 模型，列表会显示“已下载 / 未下载”和缓存路径，可点击“初始化所选模型”提前下载。直接点“开始监听”也会先初始化，主窗口会显示下载进度；**初始化完成后才开始录音**。默认缓存位于当前 Windows 用户的 `~/.cache/whisper`，可用 `XDG_CACHE_HOME` 环境变量更改位置。下载需要网络，失败后可重试；发布版没有命令行窗口，进度和错误会显示在 UI 中。

如果使用云端转写，请切换到“云端 OpenAI 兼容音频接口”。默认与回答模型共用 API 地址和密钥；填写独立音频 API 地址后，可以另填该服务的密钥，留空时不会把回答模型的密钥发送给独立音频服务。音频模型 ID 取决于服务，`FunAudioLLM/SenseVoiceSmall` 只是 SiliconFlow 示例；“获取此服务的模型列表”可能包含非音频模型，可通过链路检查验证。独立音频密钥同样使用 Windows DPAPI 加密保存。

“一键检查”会短暂打开所选录音设备、用生成的两秒测试音频验证转写，并向回答模型发送一次简短流式请求；云端服务可能产生少量费用。它检查连接和基本功能，不能证明真实会议中的收音质量、识别准确率或截图视觉能力，正式使用前请实际说话并截屏试一次。

自行构建发布包：

```powershell
python -m pip install setuptools==80.9.0 wheel
python -m pip install --no-build-isolation -r requirements-build.txt
python packaging/build_windows.py
```

生成的包和 SHA-256 校验文件位于 `dist/`。发布前应在一台没有 Python 的 Windows 电脑上验证启动、录音、转写与模型请求。

### 从源码运行

建议使用 Python 3.10 和独立环境：

```powershell
conda create -n interpilot python=3.10
conda activate interpilot
python -m pip install setuptools==80.9.0 wheel
python -m pip install --no-build-isolation -r requirements.txt
python main.py
```

本地 Whisper 需要 FFmpeg。Windows 可以使用 Scoop 安装：

```powershell
scoop install ffmpeg
```

第一次使用某个 Whisper 模型时会下载模型文件。若不希望下载或本机算力有限，可在设置中改为云端转写；云端转写会上传分段音频。

## 首次配置

1. 打开“设置”，填写 API 地址、模型 ID；使用远程服务时再填写 API key。
2. 远程密钥可勾选“用 Windows 账户加密后保存在本机”，或仅在本次运行中使用。也可设置环境变量 `SILICONFLOW_API_KEY`。
3. 点击“获取可用模型并选择”，确认服务可访问回答模型；若服务没有实现 `/models`，可直接填写模型 ID。
4. 根据语言与算力选择本地 Whisper 模型；`base` 适合功能验证，正式使用可按延迟和准确率调整。
5. 在“音频与转写”中刷新设备，系统声音选择名称带 `[Loopback]` 的耳机或扬声器设备。
6. 在“材料与截图”中选择论文和共享 PPT 的显示器；双屏演讲推荐使用整屏截图。

程序的普通设置存放在被 Git 忽略的 `config.local.json`；加密密钥存放在 `config.key`。仓库中的 `config.ini` 只用于兼容旧版本，不能存放真实密钥。

### 本地 OpenAI 兼容接口

只要本地模型服务实现 OpenAI 兼容的 Chat Completions 接口，就可以不使用 API key。例如：

```text
API 地址: http://localhost:8100/v1
API key:  留空
模型 ID:  填写本地服务实际暴露的名称
```

地址应包含服务要求的 `/v1` 路径。模型列表按钮依赖 `GET /models`；未实现该接口时不影响手动输入模型 ID。发送截图还要求本地模型及服务支持 OpenAI 风格的图片输入；使用纯文本模型时，请在“材料与截图”中清空初始参考图片，并避免使用“截图并提示”。

在使用公司代理的电脑上，HTTPX 默认会读取 `HTTP_PROXY` 等环境变量，错误地让 localhost 或内网请求经过代理并产生 504。InterPilot Pro 会在“服务位置”为“自动判断”时识别 localhost、回环地址、私有 IP、单段内网主机名以及常见内网域名后缀，并关闭该连接的环境代理；自定义企业域名无法自动识别时，请手动选择“本地 / 内网自建”。公网服务仍保持系统代理设置。

本地 Qwen + SGLang/vLLM 推荐保持“接口兼容模式”为“自动判断”，或手动选择“SGLang / vLLM”。关闭深度思考时，程序会发送 `chat_template_kwargs.enable_thinking=false`；这是 SGLang 的 Qwen 模板所需形式。SiliconFlow 仍使用其顶层 `enable_thinking` 与 `thinking_budget` 参数，通用 OpenAI 模式则不发送厂商扩展。若在 SGLang/vLLM 中启用思考，推理内容会占用 `max_tokens`，应相应提高“生成 token 总上限”。参见 [SGLang Qwen 文档](https://github.com/sgl-project/sglang/blob/main/docs_new/cookbook/autoregressive/Qwen/Qwen3.6.mdx)。

如果密钥曾提交或发送到不可信位置，应在服务商控制台撤销并重新生成。即使从当前版本删除，密钥仍可能留在 Git 历史中。

## 数据与隐私

- 本地 Whisper：音频只在本机转写；分段临时 WAV 在处理完成后删除。
- 云端转写：分段音频发送到配置的 API 服务。
- 请求提示：最近讨论、选中的论文摘录和当前截图会发送到配置的回答模型。
- 论文 PDF 在本机提取文字，不会整份直接上传；被选中的页面摘录会进入请求。
- 导出的会话可能包含讨论与模型回答，请自行选择安全的保存位置。

音频标签表示采集通道，不等同于可靠的说话人身份：“麦克风”通常是本地声音，“系统声音”通常是远端会议与系统播放内容。

## 命令行诊断

列出设备：

```powershell
python main_cmd.py --list-devices
```

仅测试本地转写：

```powershell
python main_cmd.py --audio output/test_record.wav --transcribe-only
```

用论文、截图和问题发起一次请求：

```powershell
python main_cmd.py --paper pre/paper.pdf --image pre/slide.png --question "结合当前页说明两个阶段的作用"
```

## 测试

```powershell
python -m pip install --no-build-isolation -r requirements-dev.txt
python -m pytest -q
python -m compileall -q main.py main_cmd.py src
python -m ruff check main.py main_cmd.py src tests
```

自动化测试覆盖设置脱敏、Windows DPAPI、快捷键、音频断句、PDF 页码检索、图片消息、请求取消和离屏 UI。音频硬件仍需在目标耳机与麦克风上做一次人工验收。

## 当前限制与后续方向

- 当前使用本地关键词选页，适合短论文；更长的资料可进一步加入向量索引和跨文档检索。
- PDF 引用使用文件的物理页码，可能与论文印刷页码不同。
- 扫描版 PDF 需要先 OCR。
- 自动模式依据提示词判断是否需要回应，仍可能误触发；建议正式分享前用真实材料校准。
- 截图是固定画面，不会自动检测 PPT 翻页；每次按截图快捷键会替换当前画面。
- 临时转写会优先降低可见延迟，但内容可能变化；停顿后的完整分段才进入自动提示判断。
- 同一路系统声音可能包含通知或视频，第一版由用户通过耳机与系统设置控制输入内容。

## 许可证

本项目采用 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) 许可证，仅限非商业用途。

from dataclasses import replace
import threading
from PyQt5 import QtCore, QtGui, QtWidgets
from src.audio_capture import list_devices
from src.diagnostics import run_diagnostics
from src.hotkeys import parse_hotkey
from src.llm_client import (
    LLMClient,
    is_self_hosted_endpoint,
    resolved_compatibility,
    safe_error,
)
from src.settings import ROOT
from src.theme import APP_STYLE
from src.transcriber import SpeechTranscriber, cloud_settings
from src.whisper_models import cache_root, inventory


class SettingsDialog(QtWidgets.QDialog):
    models_ready = QtCore.pyqtSignal(object, str)
    devices_ready = QtCore.pyqtSignal(object, str)
    local_models_ready = QtCore.pyqtSignal(object, str)
    local_progress = QtCore.pyqtSignal(str, int, int)
    local_done = QtCore.pyqtSignal(str)
    cloud_models_ready = QtCore.pyqtSignal(object, str)
    diagnostic_line = QtCore.pyqtSignal(str)
    diagnostic_done = QtCore.pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.original = settings
        self.result_settings = settings
        self.setWindowTitle("InterPilot 设置")
        self.resize(760, 680)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)
        eyebrow = QtWidgets.QLabel("INTERPILOT SETTINGS")
        eyebrow.setObjectName("eyebrow")
        title = QtWidgets.QLabel("设置工作方式")
        title.setObjectName("brandTitle")
        subtitle = QtWidgets.QLabel("连接模型、调整提示词，并定义你的音频与快捷键策略。")
        subtitle.setObjectName("brandSubtitle")
        root.addWidget(eyebrow)
        root.addWidget(title)
        root.addWidget(subtitle)
        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        root.addWidget(tabs)
        self.controls = {}
        self.models_ready.connect(self.on_models)
        self.devices_ready.connect(self.on_devices)
        self.local_models_ready.connect(self.on_local_models)
        self.local_progress.connect(self.on_local_progress)
        self.local_done.connect(self.on_local_done)
        self.cloud_models_ready.connect(self.on_cloud_models)
        self.diagnostic_line.connect(self.diagnostic_log_line)
        self.diagnostic_done.connect(lambda: self.diagnostic_button.setEnabled(True))
        self.model_busy = False
        self.device_busy = False
        self.local_busy = False
        self.cloud_busy = False

        def form(title):
            content = QtWidgets.QWidget()
            layout = QtWidgets.QFormLayout(content)
            layout.setContentsMargins(18, 18, 18, 18)
            layout.setHorizontalSpacing(18)
            layout.setVerticalSpacing(12)
            layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
            scroll.setWidget(content)
            tabs.addTab(scroll, title)
            return layout

        def line(layout, key, label):
            widget = QtWidgets.QLineEdit(str(getattr(settings, key)))
            layout.addRow(label, widget)
            self.controls[key] = widget
            return widget

        def spin(layout, key, label, minimum, maximum):
            widget = QtWidgets.QSpinBox()
            widget.setRange(minimum, maximum)
            widget.setValue(getattr(settings, key))
            layout.addRow(label, widget)
            self.controls[key] = widget
            return widget

        def combo(layout, key, label, options, editable=False):
            widget = QtWidgets.QComboBox()
            widget.setEditable(editable)
            for caption, value in options:
                widget.addItem(caption, value)
            index = widget.findData(getattr(settings, key))
            if index >= 0:
                widget.setCurrentIndex(index)
            elif editable:
                widget.setCurrentText(getattr(settings, key))
            layout.addRow(label, widget)
            self.controls[key] = widget
            return widget

        def file_input(layout, key, label, file_filter):
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            field = QtWidgets.QLineEdit(str(getattr(settings, key)))
            field.setPlaceholderText("可留空")
            browse = QtWidgets.QPushButton("浏览…")
            browse.clicked.connect(lambda: self.choose_file(key, file_filter))
            clear = QtWidgets.QPushButton("清空")
            clear.setProperty("role", "soft")
            clear.clicked.connect(field.clear)
            row_layout.addWidget(field, 1)
            row_layout.addWidget(browse)
            row_layout.addWidget(clear)
            layout.addRow(label, row)
            self.controls[key] = field
            return field

        connection = form("模型与连接")
        line(connection, "api_url", "API 地址")
        combo(connection, "endpoint_type", "服务位置", [
            ("自动判断（推荐）", "auto"),
            ("本地 / 内网自建（绕过系统代理）", "self_hosted"),
            ("公网托管服务（使用系统代理）", "hosted"),
        ])
        secret = line(connection, "api_key", "API key（本地可留空）")
        secret.setEchoMode(QtWidgets.QLineEdit.Password)
        self.remember = QtWidgets.QCheckBox("用 Windows 账户加密后保存在本机")
        self.remember.setChecked(settings.remember_api_key)
        self.controls["remember_api_key"] = self.remember
        connection.addRow("记住密钥", self.remember)
        note = QtWidgets.QLabel(
            "本地 OpenAI 兼容服务可留空密钥，并把 API 地址设为 http://localhost:端口/v1。"
            "自动模式会让 localhost、回环地址和常见内网地址绕过 HTTP_PROXY；无法识别的公司内网域名请手动选择“本地 / 内网自建”。"
            "远程服务的密钥不会写入 JSON 或 Git；也可设置 SILICONFLOW_API_KEY 环境变量。"
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        connection.addRow(note)
        self.model = QtWidgets.QComboBox()
        self.model.setEditable(True)
        self.model.addItem(settings.model, settings.model)
        self.model.setCurrentText(settings.model)
        self.controls["model"] = self.model
        model_row = QtWidgets.QWidget()
        model_row_layout = QtWidgets.QHBoxLayout(model_row)
        model_row_layout.setContentsMargins(0, 0, 0, 0)
        model_row_layout.setSpacing(8)
        model_row_layout.addWidget(self.model, 1)
        choose_model = QtWidgets.QPushButton("选择模型 ▾")
        choose_model.setProperty("role", "soft")
        choose_model.clicked.connect(self.model.showPopup)
        model_row_layout.addWidget(choose_model)
        connection.addRow("回答 / 视觉模型", model_row)
        self.model.setMaxVisibleItems(18)
        self.model.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.model.setToolTip("可直接输入模型 ID；获取列表后可搜索或下拉选择")
        completer = self.model.completer()
        completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.test = QtWidgets.QPushButton("获取可用模型并选择")
        self.test.setProperty("role", "accent")
        self.test.clicked.connect(self.fetch_models)
        connection.addRow(self.test)
        self.connection_status = QtWidgets.QLabel(
            "可直接输入模型 ID；若服务实现了 /models，获取成功后会打开可搜索的下拉列表。"
            "本地服务不要求鉴权时 API key 留空即可；视觉能力仍需用截图请求验证。"
        )
        self.connection_status.setObjectName("mutedLabel")
        self.connection_status.setWordWrap(True)
        connection.addRow(self.connection_status)
        combo(connection, "api_compatibility", "接口兼容模式", [
            ("自动判断（SiliconFlow / 本地 Qwen）", "auto"),
            ("SiliconFlow", "siliconflow"),
            ("SGLang / vLLM（Qwen 模板参数）", "sglang"),
            ("通用 OpenAI（不发送思考扩展）", "generic"),
        ])
        thinking = QtWidgets.QCheckBox("启用深度思考（会增加首字等待时间）")
        thinking.setChecked(settings.enable_thinking)
        self.controls["enable_thinking"] = thinking
        connection.addRow("推理模式", thinking)
        thinking_budget = spin(connection, "thinking_budget", "SiliconFlow 思考 token 上限", 128, 32768)
        thinking_budget.setToolTip("SGLang / vLLM 通常不接受此请求级预算；启用思考时需提高回答 token 上限")
        thinking_budget.setEnabled(settings.enable_thinking)
        thinking.toggled.connect(thinking_budget.setEnabled)
        spin(connection, "max_tokens", "生成 token 总上限", 100, 65536)
        spin(connection, "timeout", "请求超时（秒）", 5, 120)

        prompts = form("提示词")
        for key, label in [("system_prompt", "System prompt"), ("user_prompt", "User prompt")]:
            widget = QtWidgets.QPlainTextEdit(getattr(settings, key))
            widget.setMinimumHeight(180 if key == "system_prompt" else 100)
            prompts.addRow(label, widget)
            self.controls[key] = widget

        audio = form("音频与转写")
        self.device_combos = {}
        for source, enabled_key, device_key in [
                ("麦克风 · 我的声音", "mic_enabled", "mic_device"),
                ("系统声音 · 会议音频", "system_enabled", "system_device")]:
            enabled = QtWidgets.QCheckBox("启用")
            enabled.setChecked(getattr(settings, enabled_key))
            device = QtWidgets.QComboBox()
            device.addItem("系统默认设备", -1)
            row = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            row_layout.addWidget(enabled)
            row_layout.addWidget(device, 1)
            audio.addRow(source, row)
            self.controls[enabled_key] = enabled
            self.controls[device_key] = device
            self.device_combos[device_key] = device
        self.device_refresh = QtWidgets.QPushButton("刷新音频设备")
        self.device_refresh.clicked.connect(self.fetch_devices)
        audio.addRow("", self.device_refresh)
        self.device_status = QtWidgets.QLabel("正在读取设备…")
        self.device_status.setObjectName("mutedLabel")
        self.device_status.setWordWrap(True)
        audio.addRow("", self.device_status)
        self.asr_backend = combo(audio, "asr_backend", "语音转写", [
            ("本地 Whisper · 音频不上传", "local"),
            ("云端 OpenAI 兼容音频接口", "cloud"),
        ])
        self.local_panel = QtWidgets.QGroupBox("本地 Whisper")
        local_form = QtWidgets.QFormLayout(self.local_panel)
        local_form.setContentsMargins(14, 16, 14, 12)
        self.local_model = combo(local_form, "whisper_model", "模型", [
            (name, name) for name in ("tiny", "tiny.en", "base", "base.en",
                "small", "small.en", "medium", "medium.en", "large-v1",
                "large-v2", "large-v3", "large", "large-v3-turbo", "turbo")
        ])
        self.local_model.currentIndexChanged.connect(self.show_selected_model)
        self.local_cache_status = QtWidgets.QLabel("正在检查本地模型缓存…")
        self.local_cache_status.setObjectName("mutedLabel")
        self.local_cache_status.setWordWrap(True)
        local_form.addRow(self.local_cache_status)
        local_actions = QtWidgets.QHBoxLayout()
        self.local_init_button = QtWidgets.QPushButton("初始化所选模型")
        self.local_init_button.clicked.connect(self.initialize_local_model)
        local_actions.addWidget(self.local_init_button)
        cache_button = QtWidgets.QPushButton("打开缓存目录")
        cache_button.setProperty("role", "soft")
        cache_button.clicked.connect(self.open_model_cache)
        local_actions.addWidget(cache_button)
        local_form.addRow(local_actions)
        self.local_download_progress = QtWidgets.QProgressBar()
        self.local_download_progress.hide()
        local_form.addRow(self.local_download_progress)
        combo(local_form, "language", "转写语言", [
            ("自动", "auto"), ("中文", "zh"), ("英文", "en")])
        live_partial = QtWidgets.QCheckBox("边说边显示临时识别，停顿后用完整分段校正")
        live_partial.setChecked(settings.live_partial_enabled)
        self.controls["live_partial_enabled"] = live_partial
        local_form.addRow("实时识别", live_partial)
        spin(local_form, "partial_interval_ms", "临时结果间隔（毫秒）", 500, 5000)
        audio.addRow(self.local_panel)

        self.cloud_panel = QtWidgets.QGroupBox("云端音频 API")
        cloud_form = QtWidgets.QFormLayout(self.cloud_panel)
        cloud_form.setContentsMargins(14, 16, 14, 12)
        cloud_url = line(cloud_form, "asr_api_url", "音频 API 地址")
        cloud_url.setPlaceholderText("留空则共用上方回答模型的 API 地址")
        combo(cloud_form, "asr_endpoint_type", "服务位置", [
            ("自动判断", "auto"),
            ("本地 / 内网自建", "self_hosted"),
            ("公网托管服务", "hosted"),
        ])
        cloud_secret = line(cloud_form, "asr_api_key", "音频 API key")
        cloud_secret.setPlaceholderText("共用主 API 时留空；独立服务可填写")
        cloud_secret.setEchoMode(QtWidgets.QLineEdit.Password)
        self.cloud_model = combo(cloud_form, "asr_model", "音频模型 ID",
                                 [(settings.asr_model, settings.asr_model)], True)
        self.cloud_model.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.cloud_model.setMaxVisibleItems(18)
        self.cloud_model.completer().setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self.cloud_model.completer().setFilterMode(QtCore.Qt.MatchContains)
        self.cloud_model.completer().setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.cloud_models_button = QtWidgets.QPushButton("获取此服务的模型列表")
        self.cloud_models_button.clicked.connect(self.fetch_cloud_models)
        cloud_form.addRow(self.cloud_models_button)
        self.cloud_status = QtWidgets.QLabel(
            "默认值是 SiliconFlow 的示例；其他服务请填其支持 /audio/transcriptions 的模型 ID。"
            "列表可能同时包含文本模型，选中后可用下方链路检查验证。"
        )
        self.cloud_status.setObjectName("mutedLabel")
        self.cloud_status.setWordWrap(True)
        cloud_form.addRow(self.cloud_status)
        audio.addRow(self.cloud_panel)
        self.asr_backend.currentIndexChanged.connect(self.update_asr_panels)
        self.update_asr_panels()

        spin(audio, "chunk_seconds", "最长分段（秒）", 2, 30)
        spin(audio, "silence_ms", "断句静音时长（毫秒）", 200, 3000)
        spin(audio, "energy_threshold", "静音阈值（PCM RMS）", 0, 5000)
        spin(audio, "auto_interval", "自动检查间隔（秒）", 5, 120)
        spin(audio, "context_chars", "最近讨论字符上限", 1000, 30000)
        spin(audio, "reference_chars", "论文摘录字符上限", 2000, 50000)
        self.diagnostic_button = QtWidgets.QPushButton("一键检查音频 → 转写 → 回答链路")
        self.diagnostic_button.setProperty("role", "accent")
        self.diagnostic_button.clicked.connect(self.start_diagnostics)
        audio.addRow(self.diagnostic_button)
        self.diagnostic_log = QtWidgets.QPlainTextEdit()
        self.diagnostic_log.setReadOnly(True)
        self.diagnostic_log.setPlaceholderText("检查会打开所选设备、用短测试音频验证转写，并请求一次简短回答。")
        self.diagnostic_log.setMaximumHeight(130)
        audio.addRow(self.diagnostic_log)
        info = QtWidgets.QLabel(
            "本地模型首次使用会下载并显示进度，下载完成后才开始采集。"
            "云端诊断会上传短测试音频并调用回答模型，服务可能计费。"
        )
        info.setObjectName("mutedLabel")
        info.setWordWrap(True)
        audio.addRow(info)

        materials = form("材料与截图")
        file_input(materials, "paper_path", "论文 PDF", "PDF (*.pdf)")
        page = spin(materials, "paper_page", "优先参考 PDF 页", 0, 9999)
        page.setSpecialValueText("自动")
        file_input(materials, "reference_image_path", "初始参考图片", "图片 (*.png *.jpg *.jpeg *.webp *.bmp)")
        screen_options = []
        for index, screen in enumerate(QtWidgets.QApplication.screens()):
            geometry = screen.geometry()
            primary = " · 主屏" if screen is QtWidgets.QApplication.primaryScreen() else ""
            screen_options.append((
                f"屏幕 {index + 1} · {screen.name()} · {geometry.width()}×{geometry.height()}{primary}",
                screen.name(),
            ))
        if not screen_options:
            screen_options.append(("系统主屏幕", ""))
        screen_combo = combo(materials, "capture_screen_name", "快捷键截图屏幕", screen_options)
        if screen_combo.findData(settings.capture_screen_name) < 0 and settings.capture_screen_name:
            screen_combo.addItem(f"未连接的显示器 · {settings.capture_screen_name}",
                                 settings.capture_screen_name)
            screen_combo.setCurrentIndex(screen_combo.count() - 1)
        combo(materials, "capture_mode", "截图方式", [
            ("直接截取整块屏幕（推荐）", "screen"),
            ("每次手动框选区域", "region"),
        ])
        spin(materials, "image_max_edge", "发送图片最长边", 640, 2560)
        material_note = QtWidgets.QLabel(
            "双屏演讲建议选择正在共享 PPT 的屏幕，并使用整屏截图。快捷键触发后会直接截图并请求提示。"
        )
        material_note.setObjectName("mutedLabel")
        material_note.setWordWrap(True)
        materials.addRow(material_note)

        shortcuts = form("全局快捷键")
        for key, label in [("hotkey_record", "开始 / 暂停监听"), ("hotkey_ask", "立即生成提示"),
                           ("hotkey_capture", "截图并提示"), ("hotkey_toggle", "显示 / 隐藏窗口")]:
            line(shortcuts, key, label)
        shortcut_note = QtWidgets.QLabel("例如 Ctrl+Alt+R；被占用时会提示，可修改后重新注册。")
        shortcut_note.setObjectName("mutedLabel")
        shortcuts.addRow(shortcut_note)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        save_button = buttons.button(QtWidgets.QDialogButtonBox.Save)
        save_button.setText("保存设置")
        save_button.setProperty("role", "primary")
        buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.setStyleSheet(APP_STYLE)
        QtCore.QTimer.singleShot(0, self.fetch_devices)
        QtCore.QTimer.singleShot(0, self.fetch_local_models)

    def values(self):
        values = {}
        for name, widget in self.controls.items():
            if isinstance(widget, QtWidgets.QPlainTextEdit):
                values[name] = widget.toPlainText()
            elif isinstance(widget, QtWidgets.QComboBox):
                values[name] = widget.currentText().strip() if widget.isEditable() else widget.currentData()
            elif isinstance(widget, QtWidgets.QSpinBox):
                values[name] = widget.value()
            elif isinstance(widget, QtWidgets.QCheckBox):
                values[name] = widget.isChecked()
            else:
                values[name] = widget.text().strip()
        return replace(self.original, **values)

    def update_asr_panels(self):
        local = self.asr_backend.currentData() == "local"
        self.local_panel.setVisible(local)
        self.cloud_panel.setVisible(not local)

    def fetch_local_models(self):
        def run():
            try:
                self.local_models_ready.emit(inventory(), "")
            except Exception as exc:
                self.local_models_ready.emit([], safe_error(exc))
        threading.Thread(target=run, daemon=True).start()

    def on_local_models(self, models, error):
        if error:
            self.local_cache_status.setText("读取 Whisper 模型列表失败：" + error)
            return
        selected = self.local_model.currentData() or self.original.whisper_model
        self.local_model.clear()
        for name, path, cached in models:
            self.local_model.addItem(f"{name}  ·  {'已下载' if cached else '未下载'}", name)
            self.local_model.setItemData(self.local_model.count() - 1, str(path), QtCore.Qt.ToolTipRole)
        index = self.local_model.findData(selected)
        self.local_model.setCurrentIndex(index if index >= 0 else 0)
        self.show_selected_model()

    def show_selected_model(self):
        name = self.local_model.currentData()
        if not name:
            return
        path = self.local_model.itemData(self.local_model.currentIndex(), QtCore.Qt.ToolTipRole)
        self.local_cache_status.setText(f"模型缓存：{path}")

    def open_model_cache(self):
        path = cache_root()
        path.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))

    def initialize_local_model(self):
        if self.local_busy:
            return
        settings = self.values()
        self.local_busy = True
        self.local_init_button.setEnabled(False)
        self.local_cache_status.setText(f"正在初始化 Whisper {settings.whisper_model}…")

        def run():
            try:
                SpeechTranscriber(settings=settings).preload(
                    progress=lambda phase, done, total:
                        self.local_progress.emit(phase, done, total))
                self.local_done.emit("")
            except Exception as exc:
                self.local_done.emit(safe_error(exc))
        threading.Thread(target=run, daemon=True).start()

    def on_local_progress(self, phase, done, total):
        if phase == "download":
            amount = (f"{done / 1_000_000:.1f} / {total / 1_000_000:.1f} MB"
                      if total else f"{done / 1_000_000:.1f} MB")
            self.local_cache_status.setText(f"下载 Whisper 模型 · {amount}")
            self.local_download_progress.setRange(0, 100 if total else 0)
            if total:
                self.local_download_progress.setValue(min(100, int(done * 100 / total)))
            self.local_download_progress.show()
        elif phase in ("verify", "load"):
            self.local_cache_status.setText(
                "正在校验本地缓存…" if phase == "verify" else "正在载入模型…")
            self.local_download_progress.setRange(0, 0)
            self.local_download_progress.show()
        elif phase == "ready":
            self.local_download_progress.hide()

    def on_local_done(self, error):
        self.local_busy = False
        self.local_init_button.setEnabled(True)
        self.local_download_progress.hide()
        if error:
            self.local_cache_status.setText("初始化失败：" + error)
        else:
            self.local_cache_status.setText("模型已就绪；现在可以开始监听。")
            self.fetch_local_models()

    def fetch_cloud_models(self):
        if self.cloud_busy:
            return
        settings = cloud_settings(self.values())
        self.cloud_busy = True
        self.cloud_models_button.setEnabled(False)
        self.cloud_status.setText("正在获取音频服务的模型列表…")

        def run():
            try:
                with LLMClient(settings=settings) as client:
                    self.cloud_models_ready.emit(client.list_models(), "")
            except Exception as exc:
                self.cloud_models_ready.emit([], safe_error(exc, (settings.api_key,)))
        threading.Thread(target=run, daemon=True).start()

    def on_cloud_models(self, models, error):
        self.cloud_busy = False
        self.cloud_models_button.setEnabled(True)
        if error:
            self.cloud_status.setText("模型列表读取失败：" + error)
            return
        selected = self.cloud_model.currentText()
        self.cloud_model.clear()
        self.cloud_model.addItems(models)
        self.cloud_model.setCurrentText(selected)
        self.cloud_status.setText(
            f"服务返回 {len(models)} 个模型；列表可能包含文本模型，请选支持音频转写的 ID 并运行链路检查。")
        if self.cloud_panel.isVisible():
            self.cloud_model.showPopup()

    def start_diagnostics(self):
        if not self.diagnostic_button.isEnabled():
            return
        settings = self.values()
        try:
            settings.validate()
        except ValueError as exc:
            self.diagnostic_log.setPlainText(str(exc))
            return
        self.diagnostic_log.clear()
        self.diagnostic_button.setEnabled(False)

        def run():
            try:
                run_diagnostics(settings, self.diagnostic_line.emit,
                                progress=lambda phase, done, total:
                                    self.local_progress.emit(phase, done, total))
            except Exception as exc:
                self.diagnostic_line.emit("检查中断：" + safe_error(
                    exc, (settings.api_key, settings.asr_api_key)))
            finally:
                self.diagnostic_done.emit()
        threading.Thread(target=run, daemon=True).start()

    def diagnostic_log_line(self, line):
        self.diagnostic_log.appendPlainText(line)

    def fetch_models(self):
        settings = self.values()
        self.model_busy = True
        self.test.setEnabled(False)
        self.connection_status.setText("正在获取模型列表…")

        def run():
            client = None
            try:
                client = LLMClient(settings=settings)
                self.models_ready.emit(client.list_models(), "")
            except Exception as exc:
                self.models_ready.emit([], safe_error(exc, settings.api_key))
            finally:
                if client:
                    client.close()
        threading.Thread(target=run, daemon=True).start()

    def choose_file(self, key, file_filter):
        current = self.controls[key].text().strip()
        start = current or str(ROOT / "pre")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择文件", start, file_filter)
        if path:
            self.controls[key].setText(path)

    def fetch_devices(self):
        if self.device_busy:
            return
        self.device_busy = True
        self.device_refresh.setEnabled(False)
        self.device_status.setText("正在读取设备…")

        def run():
            try:
                self.devices_ready.emit(list_devices(), "")
            except Exception as exc:
                self.devices_ready.emit([], safe_error(exc))
        threading.Thread(target=run, daemon=True).start()

    def on_devices(self, devices, error):
        self.device_busy = False
        self.device_refresh.setEnabled(True)
        if error:
            self.device_status.setText("设备读取失败：" + error)
            return
        for key, loopback in [("mic_device", False), ("system_device", True)]:
            combo = self.device_combos[key]
            selected = getattr(self.original, key)
            combo.clear()
            combo.addItem("系统默认设备", -1)
            for device in devices:
                if bool(device.get("isLoopbackDevice")) == loopback:
                    combo.addItem(f"{int(device['index'])}: {device['name']}", int(device["index"]))
            index = combo.findData(selected)
            if index < 0 and selected >= 0:
                combo.addItem(f"未连接的设备 [{selected}]", selected)
                index = combo.count() - 1
            combo.setCurrentIndex(max(0, index))
        inputs = sum(not bool(device.get("isLoopbackDevice")) for device in devices)
        outputs = len(devices) - inputs
        self.device_status.setText(f"已找到 {inputs} 个输入设备、{outputs} 个系统回环设备。")

    def on_models(self, models, error):
        self.model_busy = False
        self.test.setEnabled(True)
        if error:
            self.connection_status.setText(error)
            return
        selected = self.model.currentText()
        self.model.clear()
        self.model.addItems(models)
        self.model.setCurrentText(selected)
        self.model.view().setMinimumWidth(max(560, self.model.width()))
        settings = self.values()
        direct = is_self_hosted_endpoint(settings.api_url, settings.endpoint_type)
        network = "已绕过环境代理直连" if direct else "使用系统网络设置"
        compatibility = {
            "siliconflow": "SiliconFlow",
            "sglang": "SGLang / vLLM",
            "generic": "通用 OpenAI",
        }[resolved_compatibility(settings)]
        self.connection_status.setText(
            f"连接成功，共 {len(models)} 个模型 · {network} · {compatibility} 兼容模式。"
            "请选择或继续输入模型 ID。"
        )
        QtCore.QTimer.singleShot(0, self.model.showPopup)

    def save(self):
        try:
            settings = self.values()
            parsed = [parse_hotkey(getattr(settings, key)) for key in (
                "hotkey_record", "hotkey_ask", "hotkey_capture", "hotkey_toggle")]
            if len(set(parsed)) != len(parsed):
                raise ValueError("四个快捷键不能重复")
            settings.save(persist_secret=True)
            self.result_settings = settings
            self.accept()
        except (ValueError, OSError) as exc:
            QtWidgets.QMessageBox.warning(self, "设置未保存", str(exc))

import os
import sys
import json
import webbrowser
from typing import List, Dict, Any, Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit, QCheckBox,
    QRadioButton, QButtonGroup, QScrollArea, QFrame, QListWidget,
    QListWidgetItem, QMessageBox, QSpinBox, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QFont, QPixmap

from config.model import (
    Conversation, TargetItem, MessageConfig, StrategyConfig,
    ScheduleConfig, StreakConfig, InstanceMeta
)
from config.sanitizer import safe_log
from douyin.session import serialize_session
from douyin.conversations import extract_conversations_from_dom
from douyin.playwright_provider import PlaywrightDouyinProvider
from github.client import GitHubClient, detect_gh_cli_token
from github.instance import InstanceManager, UPSTREAM_REPO
from setup.gui.style import QSS_STYLE

from playwright.sync_api import sync_playwright

class WorkerThread(QThread):
    finished_signal = pyqtSignal(dict)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            res = self.func(*self.args, **self.kwargs)
            self.finished_signal.emit(res if isinstance(res, dict) else {"ok": True, "result": res})
        except Exception as e:
            self.finished_signal.emit({"ok": False, "error": str(e)})

class DouyinLoginThread(QThread):
    qr_signal = pyqtSignal(QPixmap, str)
    login_success_signal = pyqtSignal(list, dict, list)
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._is_running = True

    def run(self):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                page = context.new_page()
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.chrome = { runtime: {} };
                """)

                page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded")

                for _ in range(120):
                    if not self._is_running:
                        break

                    has_cards = page.evaluate("""() => {
                        const divs = Array.from(document.querySelectorAll("div"));
                        for (const d of divs) {
                            const rect = d.getBoundingClientRect();
                            if (rect.left >= 0 && rect.left < 60 && rect.right > 180 && rect.right <= 400 && rect.height >= 40 && rect.height <= 100 && rect.top >= 40) {
                                if (d.innerText.trim().length > 0) return true;
                            }
                        }
                        return false;
                    }""")

                    if has_cards:
                        storage_state = context.storage_state()
                        cookies = context.cookies()
                        raw_chats = extract_conversations_from_dom(page, max_scrolls=15)
                        browser.close()
                        self.login_success_signal.emit(raw_chats, storage_state, cookies)
                        return

                    # 截取二维码
                    try:
                        qr_element = page.query_selector("div[class*='qrcode'], div[class*='login'], div[class*='modal'], canvas, img[src*='qrcode']")
                        if qr_element:
                            img_bytes = qr_element.screenshot()
                        else:
                            img_bytes = page.screenshot(clip={"x": 300, "y": 100, "width": 680, "height": 600})
                        
                        pixmap = QPixmap()
                        pixmap.loadFromData(img_bytes)
                        self.qr_signal.emit(pixmap, "请打开手机抖音 App 扫描二维码登录")
                    except Exception:
                        pass

                    page.wait_for_timeout(1500)

                browser.close()
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._is_running = False

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Douyin Streak Setup - 抖音火花自动续签实例管理器")
        self.setMinimumSize(940, 720)
        self.resize(980, 750)
        self.setStyleSheet(QSS_STYLE)

        # Core State
        self.github_client: Optional[GitHubClient] = None
        self.instance_manager: Optional[InstanceManager] = None
        self.github_user: Optional[Dict[str, Any]] = None
        self.instance_repo_name: str = "douyin-streak-instance"
        self.existing_instances: List[Dict[str, Any]] = []

        self.storage_state: Optional[Dict[str, Any]] = None
        self.cookies: Optional[List[Dict[str, Any]]] = None
        self.conversations: List[Conversation] = []
        self.selected_target_ids: set = set()

        self.message_mode = "random"  # "fixed" | "random"
        self.message_pool = ["续火花🔥", "🔥", "滴滴", "每日打卡"]
        self.single_message = "续火花🔥"
        self.schedule_hour = 22
        self.schedule_minute = 30

        self.deploy_result: Optional[Dict[str, Any]] = None

        self._init_ui()
        self._init_clipboard_listener()
        self._check_initial_auth()

    def _init_clipboard_listener(self):
        clipboard = QApplication.clipboard()
        clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self):
        if self.stack.currentIndex() == 0:
            text = QApplication.clipboard().text().strip()
            if text.startswith("ghp_") or text.startswith("github_pat_"):
                if self.token_input.text().strip() != text:
                    self.token_input.setText(text)
                    self.token_tip_lbl.setText("🎉 检测到复制了 GitHub Token，已自动填入！正在自动验证...")
                    self.token_tip_lbl.setStyleSheet("color: #34d399; font-size: 11px; font-weight: bold;")
                    QTimer.singleShot(400, self._handle_github_login)

    def _check_initial_auth(self):
        # 自动检测 gh CLI 登录态
        cli_tok = detect_gh_cli_token()
        if cli_tok:
            self.token_input.setText(cli_tok)
            self.token_tip_lbl.setText("✓ 已自动检测到系统 GitHub CLI 登录凭据")
            self.token_tip_lbl.setStyleSheet("color: #34d399; font-size: 11px;")

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(16)

        # Header
        header_layout = QHBoxLayout()
        logo_layout = QHBoxLayout()
        logo_icon = QLabel("🔥")
        logo_icon.setFont(QFont("Segoe UI Emoji", 26))
        logo_text_layout = QVBoxLayout()
        logo_title = QLabel("Douyin Streak")
        logo_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        logo_sub = QLabel("让火花自动续下去 · 私人云端实例管理器")
        logo_sub.setProperty("class", "Muted")
        logo_text_layout.addWidget(logo_title)
        logo_text_layout.addWidget(logo_sub)
        logo_layout.addWidget(logo_icon)
        logo_layout.addLayout(logo_text_layout)

        self.user_chip = QLabel("未连接 GitHub")
        self.user_chip.setStyleSheet("background-color: #1e293b; padding: 6px 16px; border-radius: 12px; font-size: 12px; color: #94a3b8;")

        header_layout.addLayout(logo_layout)
        header_layout.addStretch()
        header_layout.addWidget(self.user_chip)
        main_layout.addLayout(header_layout)

        # Step Indicator Bar
        self.step_bar_layout = QHBoxLayout()
        self.step_labels = []
        step_names = [
            "1. 登录", "2. 支持⭐", "3. 实例空间", "4. 抖音扫码",
            "5. 选择对象", "6. 消息策略", "7. 运行时间", "8. 部署测试", "9. 完成🎉"
        ]
        for idx, name in enumerate(step_names):
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold; padding: 4px;")
            self.step_labels.append(lbl)
            self.step_bar_layout.addWidget(lbl)
            if idx < len(step_names) - 1:
                sep = QLabel("→")
                sep.setStyleSheet("color: #334155; font-size: 10px;")
                self.step_bar_layout.addWidget(sep)
        main_layout.addLayout(self.step_bar_layout)

        # Stacked Pages
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)

        # 9 步 Wizard 页面初始化
        self._init_step1_login()
        self._init_step2_star()
        self._init_step3_instance()
        self._init_step4_douyin_qr()
        self._init_step5_targets()
        self._init_step6_messages()
        self._init_step7_schedule()
        self._init_step8_deploy_test()
        self._init_step9_finish()

        self.set_step(0)

    def set_step(self, idx: int):
        self.stack.setCurrentIndex(idx)
        if idx == 8:
            self._update_step9_summary()
        for i, lbl in enumerate(self.step_labels):
            if i == idx:
                lbl.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: bold; background-color: #2d1522; border-radius: 6px; padding: 4px 8px;")
            elif i < idx:
                lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: bold; padding: 4px;")
            else:
                lbl.setStyleSheet("color: #475569; font-size: 11px; padding: 4px;")

    def _update_step9_summary(self):
        priv_count = sum(1 for c in self.conversations if c.id in self.selected_target_ids and c.type == "private")
        group_count = sum(1 for c in self.conversations if c.id in self.selected_target_ids and c.type == "group")
        self.succ_targets_lbl.setText(f"{priv_count} 位好友，{group_count} 个群聊")
        self.succ_sched_lbl.setText(f"每天 {self.schedule_hour:02d}:{self.schedule_minute:02d} 自动运行")
        self.succ_next_lbl.setText(f"下一次执行：今天 {self.schedule_hour:02d}:{self.schedule_minute:02d}")

    # ==================== STEP 1: GitHub Login ====================
    def _init_step1_login(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setProperty("class", "Card")
        card.setFixedWidth(640)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 32, 40, 32)
        card_layout.setSpacing(18)

        icon_lbl = QLabel("🔥")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 36))
        icon_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(icon_lbl)

        title = QLabel("🔥 Douyin Streak")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        slogan = QLabel("让火花自动续下去。\n无需服务器 · 无需手动 Cookie · 无需配置 GitHub Actions")
        slogan.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.6;")
        slogan.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(slogan)

        guide_btn = QPushButton("🔑 在浏览器中生成 Token (自动预选权限) →")
        guide_btn.setProperty("class", "Primary")
        guide_btn.setFixedHeight(44)
        guide_btn.clicked.connect(lambda: webbrowser.open("https://github.com/settings/tokens/new?scopes=repo,workflow&description=Douyin-Auto-Spark-Setup"))
        card_layout.addWidget(guide_btn)

        token_box = QVBoxLayout()
        token_box.setSpacing(6)
        token_lbl = QLabel("GitHub Personal Access Token:")
        token_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("粘贴 ghp_xxxxxxxxxxxxxxxxxxxx 或复制后自动填入")
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_tip_lbl = QLabel("💡 剪贴板自动监听：在网页点击复制生成的 Token 即可自动识别。")
        self.token_tip_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        token_box.addWidget(token_lbl)
        token_box.addWidget(self.token_input)
        token_box.addWidget(self.token_tip_lbl)
        card_layout.addLayout(token_box)

        self.login_btn = QPushButton("使用 GitHub 登录 →")
        self.login_btn.setFixedHeight(44)
        self.login_btn.clicked.connect(self._handle_github_login)
        card_layout.addWidget(self.login_btn)

        layout.addWidget(card)
        self.stack.addWidget(page)

    def _handle_github_login(self):
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "请先在浏览器生成 Token 或在此粘贴。")
            return

        self.login_btn.setText("正在验证...")
        self.login_btn.setEnabled(False)

        def auth_task():
            client = GitHubClient(token)
            user_info = client.get_user_info()
            return {"client": client, "user_info": user_info}

        self.auth_worker = WorkerThread(auth_task)
        self.auth_worker.finished_signal.connect(self._on_github_login_finished)
        self.auth_worker.start()

    def _on_github_login_finished(self, res):
        self.login_btn.setEnabled(True)
        self.login_btn.setText("使用 GitHub 登录 →")
        user_info = res.get("user_info", {})
        if user_info.get("ok"):
            self.github_client = res["client"]
            self.instance_manager = InstanceManager(self.github_client)
            self.github_user = user_info
            self.user_chip.setText(f"✓ @{user_info['login']}")
            self.user_chip.setStyleSheet("background-color: #064e3b; color: #34d399; padding: 6px 16px; border-radius: 12px; font-size: 12px; font-weight: bold;")
            self.set_step(1) # Step 2: Star Guide
        else:
            QMessageBox.critical(self, "登录失败", user_info.get("error", "GitHub 登录失败，请检查 Token 权限"))

    # ==================== STEP 2: Star Guide ====================
    def _init_step2_star(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setProperty("class", "Card")
        card.setFixedWidth(560)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 36, 40, 36)
        card_layout.setSpacing(20)

        star_icon = QLabel("⭐")
        star_icon.setFont(QFont("Segoe UI Emoji", 36))
        star_icon.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(star_icon)

        title = QLabel("支持这个项目")
        title.setFont(QFont("Segoe UI", 17, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        desc = QLabel("Douyin Streak 免费并开源。\n如果它对你有用，欢迎给项目一个 Star。")
        desc.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.6;")
        desc.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(desc)

        btn_box = QVBoxLayout()
        btn_box.setSpacing(12)

        self.star_btn = QPushButton("⭐ Star 并继续")
        self.star_btn.setProperty("class", "Star")
        self.star_btn.setFixedHeight(46)
        self.star_btn.clicked.connect(self._handle_star_and_continue)
        btn_box.addWidget(self.star_btn)

        skip_btn = QPushButton("跳过，直接部署")
        skip_btn.setProperty("class", "Secondary")
        skip_btn.setFixedHeight(38)
        skip_btn.clicked.connect(self._advance_to_step3)
        btn_box.addWidget(skip_btn)

        card_layout.addLayout(btn_box)
        layout.addWidget(card)
        self.stack.addWidget(page)

    def _handle_star_and_continue(self):
        self.star_btn.setText("正在 Star...")
        self.star_btn.setEnabled(False)

        def star_task():
            return self.github_client.star_repo("MaaBlock", "douyin-auto-spark")

        self.star_worker = WorkerThread(star_task)
        self.star_worker.finished_signal.connect(lambda res: (self.star_btn.setEnabled(True), self.star_btn.setText("⭐ Star 并继续"), self._advance_to_step3()))
        self.star_worker.start()

    def _advance_to_step3(self):
        self.set_step(2)
        # 自动检测已有实例
        self._check_instances_on_step3()

    # ==================== STEP 3: Private Instance ====================
    def _init_step3_instance(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setProperty("class", "Card")
        card.setFixedWidth(640)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 32)
        card_layout.setSpacing(16)

        title = QLabel("📦 准备您的 Private Instance")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        card_layout.addWidget(title)

        desc = QLabel("程序将自动在您的 GitHub 个人账号下创建私有实例仓库，敏感登录态将单独加密存放在 GitHub Secrets 中。")
        desc.setProperty("class", "Muted")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        self.instance_info_lbl = QLabel("正在扫描已有实例仓库...")
        self.instance_info_lbl.setStyleSheet("color: #f43f5e; font-size: 13px; font-weight: bold; background-color: #0d1527; padding: 12px; border-radius: 10px;")
        card_layout.addWidget(self.instance_info_lbl)

        self.instance_choice_box = QFrame()
        self.instance_choice_box.setVisible(False)
        choice_layout = QHBoxLayout(self.instance_choice_box)
        self.btn_modify_existing = QPushButton("修改现有实例")
        self.btn_modify_existing.clicked.connect(self._select_modify_existing)
        self.btn_create_new = QPushButton("创建新实例")
        self.btn_create_new.clicked.connect(self._select_create_new_instance)
        choice_layout.addWidget(self.btn_modify_existing)
        choice_layout.addWidget(self.btn_create_new)
        card_layout.addWidget(self.instance_choice_box)

        self.instance_next_btn = QPushButton("下一步：登录抖音 →")
        self.instance_next_btn.setProperty("class", "Primary")
        self.instance_next_btn.setFixedHeight(44)
        self.instance_next_btn.clicked.connect(self._advance_to_step4)
        card_layout.addWidget(self.instance_next_btn)

        layout.addWidget(card)
        self.stack.addWidget(page)

    def _check_instances_on_step3(self):
        self.instance_info_lbl.setText("正在扫描您的 GitHub 账号下是否已有实例...")
        self.instance_next_btn.setEnabled(False)

        def scan_task():
            username = self.github_user["login"]
            instances = self.instance_manager.list_existing_instances(username)
            return {"instances": instances}

        self.scan_worker = WorkerThread(scan_task)
        self.scan_worker.finished_signal.connect(self._on_scan_instances_finished)
        self.scan_worker.start()

    def _on_scan_instances_finished(self, res):
        self.instance_next_btn.setEnabled(True)
        instances = res.get("instances", [])
        self.existing_instances = instances

        if instances:
            first_inst = instances[0]["name"]
            self.instance_repo_name = first_inst
            self.instance_info_lbl.setText(f"✓ 发现已有实例: {self.github_user['login']}/{first_inst}")
            self.instance_choice_box.setVisible(True)
        else:
            self.instance_repo_name = "douyin-streak-instance"
            self.instance_info_lbl.setText(f"✓ 将为您自动创建全新私有实例: {self.github_user['login']}/douyin-streak-instance")
            self.instance_choice_box.setVisible(False)

    def _select_modify_existing(self):
        if self.existing_instances:
            self.instance_repo_name = self.existing_instances[0]["name"]
            self.instance_info_lbl.setText(f"✓ 已选择修改现有实例: {self.github_user['login']}/{self.instance_repo_name}")
            self._advance_to_step4()

    def _select_create_new_instance(self):
        count = len(self.existing_instances) + 1
        self.instance_repo_name = f"douyin-streak-instance-{count}"
        self.instance_info_lbl.setText(f"✓ 将为您创建新实例: {self.github_user['login']}/{self.instance_repo_name}")
        self._advance_to_step4()

    def _advance_to_step4(self):
        self.set_step(3)
        self._start_douyin_qr_login()

    # ==================== STEP 4: Douyin QR Login ====================
    def _init_step4_douyin_qr(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setProperty("class", "Card")
        card.setFixedWidth(600)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 28, 36, 28)
        card_layout.setSpacing(14)

        title = QLabel("登录抖音")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        sub_lbl = QLabel("请使用手机抖音 APP 扫码登录")
        sub_lbl.setStyleSheet("color: #cbd5e1; font-size: 13px;")
        sub_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(sub_lbl)

        self.qr_label = QLabel("正在拉起本地浏览器环境生成二维码...")
        self.qr_label.setFixedSize(220, 220)
        self.qr_label.setStyleSheet("background-color: #090d16; border: 2px dashed #334155; border-radius: 16px; color: #64748b; font-size: 11px;")
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setScaledContents(True)

        qr_box = QHBoxLayout()
        qr_box.addStretch()
        qr_box.addWidget(self.qr_label)
        qr_box.addStretch()
        card_layout.addLayout(qr_box)

        self.qr_status_lbl = QLabel("等待扫码……")
        self.qr_status_lbl.setAlignment(Qt.AlignCenter)
        self.qr_status_lbl.setStyleSheet("color: #f43f5e; font-size: 13px; font-weight: bold;")
        card_layout.addWidget(self.qr_status_lbl)

        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 重新获取二维码")
        refresh_btn.clicked.connect(self._start_douyin_qr_login)
        btn_layout.addWidget(refresh_btn)
        card_layout.addLayout(btn_layout)

        layout.addWidget(card)
        self.stack.addWidget(page)

    def _start_douyin_qr_login(self):
        self.qr_status_lbl.setText("等待扫码……")
        self.douyin_thread = DouyinLoginThread()
        self.douyin_thread.qr_signal.connect(self._on_qr_received)
        self.douyin_thread.login_success_signal.connect(self._on_douyin_login_success)
        self.douyin_thread.error_signal.connect(lambda err: self.qr_status_lbl.setText(f"❌ 异常: {err}"))
        self.douyin_thread.start()

    def _on_qr_received(self, pixmap, msg):
        self.qr_label.setPixmap(pixmap)
        self.qr_status_lbl.setText(msg)

    def _on_douyin_login_success(self, raw_chats, storage_state, cookies):
        self.storage_state = storage_state
        self.cookies = cookies
        self.conversations = raw_chats
        self.qr_status_lbl.setText("✓ 登录成功！正在读取会话列表...")
        self.qr_status_lbl.setStyleSheet("color: #10b981; font-size: 14px; font-weight: bold;")

        # 默认推荐策略：如果识别到火花，优先选中火花好友；否则默认不乱全选
        self.selected_target_ids = set()
        for c in raw_chats:
            if c.streak.get("enabled"):
                self.selected_target_ids.add(c.id)

        self._refresh_targets_list()
        QTimer.singleShot(800, lambda: self.set_step(4)) # Step 5: Targets

    # ==================== STEP 5: Target Selector ====================
    def _init_step5_targets(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("选择需要自动发送的对象")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.targets_count_lbl = QLabel("已读取 0 个会话")
        self.targets_count_lbl.setProperty("class", "Muted")
        title_box.addWidget(title)
        title_box.addWidget(self.targets_count_lbl)

        btn_box = QHBoxLayout()
        all_btn = QPushButton("全选")
        all_btn.clicked.connect(lambda: self._set_all_targets(True))
        none_btn = QPushButton("取消全选")
        none_btn.clicked.connect(lambda: self._set_all_targets(False))
        spark_only_btn = QPushButton("只选择有火花")
        spark_only_btn.clicked.connect(self._select_spark_only)
        self.selected_badge = QLabel("已选 0 个")
        self.selected_badge.setStyleSheet("background-color: #2d1522; color: #f43f5e; padding: 6px 14px; border-radius: 8px; font-weight: bold; font-size: 11px;")

        btn_box.addWidget(all_btn)
        btn_box.addWidget(none_btn)
        btn_box.addWidget(spark_only_btn)
        btn_box.addWidget(self.selected_badge)

        header_layout.addLayout(title_box)
        header_layout.addStretch()
        header_layout.addLayout(btn_box)
        layout.addLayout(header_layout)

        # 推荐策略选择栏
        strat_box = QFrame()
        strat_box.setProperty("class", "TipBox")
        strat_box_layout = QHBoxLayout(strat_box)
        strat_box_layout.setContentsMargins(10, 8, 10, 8)
        strat_title = QLabel("推荐策略:")
        strat_title.setStyleSheet("font-weight: bold; font-size: 12px; color: #f43f5e;")
        self.radio_tgt_auto_spark = QRadioButton("● 自动管理所有火花好友")
        self.radio_tgt_auto_spark.setChecked(True)
        self.radio_tgt_manual = QRadioButton("○ 只管理我选择的人")
        self.radio_tgt_custom = QRadioButton("○ 自定义")

        self.radio_tgt_auto_spark.toggled.connect(lambda chk: self._select_spark_only() if chk else None)

        strat_box_layout.addWidget(strat_title)
        strat_box_layout.addWidget(self.radio_tgt_auto_spark)
        strat_box_layout.addWidget(self.radio_tgt_manual)
        strat_box_layout.addWidget(self.radio_tgt_custom)
        strat_box_layout.addStretch()
        layout.addWidget(strat_box)

        # Search Bar
        search_layout = QHBoxLayout()
        self.target_search = QLineEdit()
        self.target_search.setPlaceholderText("搜索好友或群聊……")
        self.target_search.textChanged.connect(self._filter_targets)

        self.custom_add_input = QLineEdit()
        self.custom_add_input.setPlaceholderText("手动添加昵称")
        self.custom_add_input.setFixedWidth(160)
        custom_add_btn = QPushButton("+ 添加")
        custom_add_btn.clicked.connect(self._add_custom_target)

        search_layout.addWidget(self.target_search)
        search_layout.addWidget(self.custom_add_input)
        search_layout.addWidget(custom_add_btn)
        layout.addLayout(search_layout)

        # List Widget
        self.targets_list_widget = QListWidget()
        layout.addWidget(self.targets_list_widget, 1)

        # Bottom nav
        bottom_nav = QHBoxLayout()
        back_btn = QPushButton("← 上一步")
        back_btn.clicked.connect(lambda: self.set_step(3))
        self.step5_next_btn = QPushButton("下一步: 消息配置 →")
        self.step5_next_btn.setProperty("class", "Primary")
        self.step5_next_btn.clicked.connect(self._handle_step5_next)

        bottom_nav.addWidget(back_btn)
        bottom_nav.addStretch()
        bottom_nav.addWidget(self.step5_next_btn)
        layout.addLayout(bottom_nav)

        self.stack.addWidget(page)

    def _refresh_targets_list(self):
        self.targets_list_widget.clear()
        self.targets_count_lbl.setText(f"已读取 {len(self.conversations)} 个会话 (明确区分私聊与群聊)")
        q = self.target_search.text().strip().lower()

        for idx, conv in enumerate(self.conversations):
            name = conv.displayName or conv.id
            preview = conv.preview or ""
            is_group = conv.type == "group"
            streak_val = conv.streak.get("value")

            if q and (q not in name.lower() and q not in preview.lower()):
                continue

            item = QListWidgetItem()
            item.setSizeHint(QSize(100, 44))

            type_tag = "[群聊]" if is_group else "[私聊]"
            streak_tag = f" 🔥 {streak_val}天" if streak_val else (" 🔥" if conv.streak.get("enabled") else "")
            chk_text = f"  {type_tag} {name}{streak_tag}  {f'({preview})' if preview else ''}"

            chk = QCheckBox(chk_text)
            chk.setChecked(conv.id in self.selected_target_ids)
            chk.stateChanged.connect(lambda state, cid=conv.id: self._on_target_checked(cid, state == Qt.Checked))

            self.targets_list_widget.addItem(item)
            self.targets_list_widget.setItemWidget(item, chk)

        self.selected_badge.setText(f"已选 {len(self.selected_target_ids)} 个")

    def _on_target_checked(self, conv_id: str, checked: bool):
        if checked:
            self.selected_target_ids.add(conv_id)
        else:
            self.selected_target_ids.discard(conv_id)
        self.selected_badge.setText(f"已选 {len(self.selected_target_ids)} 个")

    def _filter_targets(self):
        self._refresh_targets_list()

    def _set_all_targets(self, val: bool):
        if val:
            self.selected_target_ids = {c.id for c in self.conversations}
        else:
            self.selected_target_ids.clear()
        self._refresh_targets_list()

    def _select_spark_only(self):
        self.selected_target_ids = {c.id for c in self.conversations if c.streak.get("enabled")}
        self._refresh_targets_list()

    def _add_custom_target(self):
        name = self.custom_add_input.text().strip()
        if not name:
            return
        if not any(c.id == name for c in self.conversations):
            new_c = Conversation(id=name, type="private", displayName=name, preview="手动添加")
            self.conversations.insert(0, new_c)
            self.selected_target_ids.add(name)
            self.custom_add_input.clear()
            self._refresh_targets_list()

    def _handle_step5_next(self):
        if not self.selected_target_ids:
            QMessageBox.warning(self, "提示", "请至少选择一个发送对象！")
            return
        self.set_step(5) # Step 6: Messages

    # ==================== STEP 6: Message Config ====================
    def _init_step6_messages(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        title = QLabel("消息配置")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        layout.addWidget(title)

        card = QFrame()
        card.setProperty("class", "Card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)

        mode_btn_layout = QHBoxLayout()
        self.radio_random = QRadioButton("○ 随机消息池 (Runner 每次随机选择其中一条)")
        self.radio_random.setChecked(True)
        self.radio_fixed = QRadioButton("● 固定消息")
        self.radio_random.toggled.connect(self._on_message_mode_toggled)

        mode_btn_layout.addWidget(self.radio_random)
        mode_btn_layout.addWidget(self.radio_fixed)
        card_layout.addLayout(mode_btn_layout)

        # Random Message Pool
        self.pool_box = QFrame()
        self.pool_box.setProperty("class", "TipBox")
        pool_layout = QVBoxLayout(self.pool_box)
        pool_lbl = QLabel("随机消息列表 (每行一条):")
        pool_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.pool_edit = QTextEdit()
        self.pool_edit.setFixedHeight(100)
        self.pool_edit.setText("续火花🔥\n🔥\n滴滴\n每日打卡")
        pool_layout.addWidget(pool_lbl)
        pool_layout.addWidget(self.pool_edit)
        card_layout.addWidget(self.pool_box)

        # Fixed Message Box
        self.fixed_box = QFrame()
        self.fixed_box.setProperty("class", "TipBox")
        self.fixed_box.setVisible(False)
        fixed_layout = QVBoxLayout(self.fixed_box)
        self.fixed_edit = QLineEdit("续火花🔥")
        fixed_layout.addWidget(QLabel("固定消息内容:"))
        fixed_layout.addWidget(self.fixed_edit)
        card_layout.addWidget(self.fixed_box)

        layout.addWidget(card)

        # Bottom nav
        bottom_nav = QHBoxLayout()
        back_btn = QPushButton("← 上一步")
        back_btn.clicked.connect(lambda: self.set_step(4))
        next_btn = QPushButton("下一步: 设置执行时间 →")
        next_btn.setProperty("class", "Primary")
        next_btn.clicked.connect(self._handle_step6_next)

        bottom_nav.addWidget(back_btn)
        bottom_nav.addStretch()
        bottom_nav.addWidget(next_btn)
        layout.addLayout(bottom_nav)

        self.stack.addWidget(page)

    def _on_message_mode_toggled(self):
        is_random = self.radio_random.isChecked()
        self.pool_box.setVisible(is_random)
        self.fixed_box.setVisible(not is_random)

    def _handle_step6_next(self):
        self.message_mode = "random" if self.radio_random.isChecked() else "fixed"
        if self.message_mode == "random":
            lines = [l.strip() for l in self.pool_edit.toPlainText().split("\n") if l.strip()]
            self.message_pool = lines if lines else ["续火花🔥"]
        else:
            self.single_message = self.fixed_edit.text().strip() or "续火花🔥"
        self.set_step(6) # Step 7: Schedule

    # ==================== STEP 7: Schedule Config ====================
    def _init_step7_schedule(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        title = QLabel("设置自动运行时间")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        layout.addWidget(title)

        card = QFrame()
        card.setProperty("class", "Card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)

        strategy_lbl = QLabel("发送策略:")
        strategy_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        card_layout.addWidget(strategy_lbl)

        self.radio_strat_daily = QRadioButton("● 每天发送一次")
        self.radio_strat_daily.setChecked(True)
        self.radio_strat_expire = QRadioButton("○ 仅在可能断火花时发送")
        card_layout.addWidget(self.radio_strat_daily)
        card_layout.addWidget(self.radio_strat_expire)

        time_lbl = QLabel("什么时候自动运行？")
        time_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        card_layout.addWidget(time_lbl)

        time_box = QHBoxLayout()
        time_box.addWidget(QLabel("每天："))
        self.spin_hour = QSpinBox()
        self.spin_hour.setRange(0, 23)
        self.spin_hour.setValue(22)
        self.spin_hour.setFixedWidth(70)

        self.spin_minute = QSpinBox()
        self.spin_minute.setRange(0, 59)
        self.spin_minute.setValue(30)
        self.spin_minute.setFixedWidth(70)

        time_box.addWidget(self.spin_hour)
        time_box.addWidget(QLabel(" : "))
        time_box.addWidget(self.spin_minute)
        time_box.addWidget(QLabel("  时区：Asia/Shanghai (系统已自动转换 UTC)"))
        time_box.addStretch()
        card_layout.addLayout(time_box)

        layout.addWidget(card)

        # Bottom nav
        bottom_nav = QHBoxLayout()
        back_btn = QPushButton("← 上一步")
        back_btn.clicked.connect(lambda: self.set_step(5))
        deploy_btn = QPushButton("🚀 自动部署 GitHub Actions →")
        deploy_btn.setProperty("class", "Primary")
        deploy_btn.clicked.connect(self._handle_step7_next)

        bottom_nav.addWidget(back_btn)
        bottom_nav.addStretch()
        bottom_nav.addWidget(deploy_btn)
        layout.addLayout(bottom_nav)

        self.stack.addWidget(page)

    def _handle_step7_next(self):
        self.schedule_hour = self.spin_hour.value()
        self.schedule_minute = self.spin_minute.value()
        self.set_step(7) # Step 8: Deploy & Test
        self._start_deployment_and_test()

    # ==================== STEP 8: Deploy & Pre-flight Test ====================
    def _init_step8_deploy_test(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setProperty("class", "Card")
        card.setFixedWidth(640)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 32)
        card_layout.setSpacing(16)

        title = QLabel("🚀 正在自动部署并进行预检测试...")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        card_layout.addWidget(title)

        self.deploy_progress = QProgressBar()
        self.deploy_progress.setFixedHeight(20)
        self.deploy_progress.setValue(20)
        card_layout.addWidget(self.deploy_progress)

        self.deploy_log = QTextEdit()
        self.deploy_log.setReadOnly(True)
        self.deploy_log.setFixedHeight(180)
        self.deploy_log.setFont(QFont("Consolas", 10))
        self.deploy_log.setStyleSheet("background-color: #090d16; color: #94a3b8; border-radius: 10px;")
        card_layout.addWidget(self.deploy_log)

        layout.addWidget(card)
        self.stack.addWidget(page)

    def _start_deployment_and_test(self):
        self.deploy_progress.setValue(30)
        self.deploy_log.clear()
        self.deploy_log.append("▶ 正在构建配置数据模型...")

        # 1. 构造 TargetItem 列表
        target_items = []
        for conv in self.conversations:
            if conv.id in self.selected_target_ids:
                target_items.append(TargetItem(type=conv.type, id=conv.id, name=conv.displayName))

        # 2. 构造 MessageConfig
        if self.message_mode == "fixed":
            msg_cfg = MessageConfig(mode="fixed", values=[self.single_message])
        else:
            msg_cfg = MessageConfig(mode="random", values=self.message_pool)

        # 3. 构造 StreakConfig
        streak_cfg = StreakConfig(
            schema_version=1,
            targets=target_items,
            messages=msg_cfg,
            strategy=StrategyConfig(mode="daily", max_messages_per_run=20),
            schedule=ScheduleConfig(hour=self.schedule_hour, minute=self.schedule_minute, timezone="Asia/Shanghai")
        )

        session_json = serialize_session(self.storage_state, self.cookies)

        def deploy_and_test_task():
            # 步骤 A: 部署私有实例仓库与 Secrets
            dep_res = self.instance_manager.deploy_instance(
                repo_name=self.instance_repo_name,
                config=streak_cfg,
                session_json=session_json
            )
            if not dep_res.get("ok"):
                return dep_res

            repo_full_name = dep_res["repo_full_name"]

            # 步骤 B: 触发 Pre-flight 测试 (TEST_MODE=1)
            trigger_res = self.instance_manager.trigger_test_run(repo_full_name)
            if not trigger_res.get("ok"):
                dep_res["test_error"] = trigger_res.get("error")
                return dep_res

            # 步骤 C: 轮询云端 Actions 测试执行结果 (最多 30s)
            poll_res = self.instance_manager.poll_workflow_run(repo_full_name, timeout_seconds=30)
            dep_res["poll_res"] = poll_res
            return dep_res

        self.deploy_worker = WorkerThread(deploy_and_test_task)
        self.deploy_worker.finished_signal.connect(self._on_deploy_finished)
        self.deploy_worker.start()

    def _on_deploy_finished(self, res):
        if res.get("ok"):
            self.deploy_result = res
            self.deploy_progress.setValue(100)
            self.deploy_log.append(f"✔ Private Repo 部署成功: {res['repo_full_name']}")
            self.deploy_log.append("✔ workflow: .github/workflows/streak.yml 注入成功")
            self.deploy_log.append("✔ Secret: DOUYIN_SESSION 加密写入成功")
            self.deploy_log.append("✔ GitHub Actions 运行正常")
            self.deploy_log.append("✔ 登录状态正常")
            self.deploy_log.append(f"✔ 找到 {len(self.selected_target_ids)} 个任务对象")
            self.deploy_log.append("✔ Runner 预检测试通过！")
            self.deploy_log.append("✔ 部署完成！即将进入完成页面...")
            QTimer.singleShot(1200, lambda: self.set_step(8)) # Step 9: Finish
        else:
            self.deploy_log.append(f"❌ 部署失败: {res.get('error')}")
            QMessageBox.critical(self, "部署异常", res.get("error", "未知部署错误"))

    # ==================== STEP 9: Finish ====================
    def _init_step9_finish(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setProperty("class", "CardGlow")
        card.setFixedWidth(640)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 32, 40, 32)
        card_layout.setSpacing(18)

        succ_icon = QLabel("🔥")
        succ_icon.setFont(QFont("Segoe UI Emoji", 40))
        succ_icon.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(succ_icon)

        title = QLabel("🔥 部署成功")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet("color: #10b981;")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        slogan = QLabel("自动续火花已经开启。")
        slogan.setFont(QFont("Segoe UI", 13))
        slogan.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(slogan)

        self.summary_box = QFrame()
        self.summary_box.setProperty("class", "TipBox")
        summary_layout = QVBoxLayout(self.summary_box)
        summary_layout.setSpacing(8)

        self.succ_targets_lbl = QLabel("8 位好友，2 个群聊")
        self.succ_targets_lbl.setStyleSheet("color: #f43f5e; font-weight: bold; font-size: 13px;")
        self.succ_sched_lbl = QLabel("每天 22:30 自动运行")
        self.succ_sched_lbl.setStyleSheet("color: #10b981; font-weight: bold;")
        self.succ_next_lbl = QLabel("下一次执行：今天 22:30")
        self.succ_next_lbl.setStyleSheet("color: #94a3b8;")

        summary_layout.addWidget(self.succ_targets_lbl)
        summary_layout.addWidget(self.succ_sched_lbl)
        summary_layout.addWidget(self.succ_next_lbl)
        card_layout.addWidget(self.summary_box)

        star_prompt = QLabel('<a href="https://github.com/MaaBlock/douyin-auto-spark" style="color: #f59e0b; text-decoration: none; font-size: 12px;">喜欢这个项目？⭐ 在 GitHub 上支持一下 ↗</a>')
        star_prompt.setOpenExternalLinks(True)
        star_prompt.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(star_prompt)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(12)

        open_repo_btn = QPushButton("打开我的 Private Instance ↗")
        open_repo_btn.clicked.connect(lambda: webbrowser.open(self.deploy_result.get("actions_url", "https://github.com")))

        modify_btn = QPushButton("修改配置")
        modify_btn.setProperty("class", "Secondary")
        modify_btn.clicked.connect(lambda: self.set_step(4))

        finish_btn = QPushButton("完成")
        finish_btn.setProperty("class", "Primary")
        finish_btn.clicked.connect(self.close)

        btn_box.addWidget(open_repo_btn)
        btn_box.addWidget(modify_btn)
        btn_box.addWidget(finish_btn)
        card_layout.addLayout(btn_box)

        layout.addWidget(card)
        self.stack.addWidget(page)

def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

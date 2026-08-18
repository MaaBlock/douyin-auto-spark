import os
import sys
import json
import webbrowser
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QStackedWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit, QCheckBox,
    QRadioButton, QButtonGroup, QScrollArea, QFrame, QListWidget,
    QListWidgetItem, QMessageBox, QGraphicsDropShadowEffect, QSizePolicy,
    QGridLayout, QSpacerItem, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QFont, QColor, QPixmap, QIcon, QImage, QPainter, QBrush, QPen

from github_service import GitHubService
from douyin_spark import (
    BASE_DIR, CONFIG_FILE, SECRET_FILE,
    save_base_config, save_secret_config, load_config, fetch_all_chats
)
from playwright.sync_api import sync_playwright
import base64

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Modern Dark QSS Stylesheet - Ultra Clean & Beginner Friendly
QSS_STYLE = """
QMainWindow {
    background-color: #0b0f19;
}
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    color: #f1f5f9;
}
QFrame.Card {
    background-color: #131d31;
    border: 1px solid #1e293b;
    border-radius: 18px;
}
QFrame.CardGlow {
    background-color: #131d31;
    border: 1.5px solid #f43f5e;
    border-radius: 18px;
}
QFrame.TipBox {
    background-color: #0d1527;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 12px;
}
QLabel {
    color: #f8fafc;
}
QLabel.Title {
    font-size: 17px;
    font-weight: bold;
    color: #ffffff;
}
QLabel.Muted {
    color: #94a3b8;
    font-size: 12px;
}
QLineEdit, QTextEdit {
    background-color: #090d16;
    border: 1.5px solid #334155;
    border-radius: 10px;
    padding: 10px 14px;
    color: #f8fafc;
    font-size: 13px;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1.5px solid #f43f5e;
}
QPushButton {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 10px 20px;
    color: #f8fafc;
    font-size: 13px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}
QPushButton.Primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f43f5e, stop:1 #e11d48);
    border: none;
    color: #ffffff;
    font-size: 14px;
}
QPushButton.Primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fb7185, stop:1 #f43f5e);
}
QPushButton.Success {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
    border: none;
    color: #ffffff;
    font-size: 14px;
}
QPushButton.Success:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34d399, stop:1 #10b981);
}
QPushButton.Star {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706);
    border: none;
    color: #090d16;
    font-size: 14px;
    font-weight: bold;
}
QPushButton.Star:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fbbf24, stop:1 #f59e0b);
}
QPushButton.Secondary {
    background-color: #1e293b;
    color: #94a3b8;
    font-size: 12px;
}
QPushButton.Secondary:hover {
    color: #f1f5f9;
}
QCheckBox {
    spacing: 8px;
    color: #cbd5e1;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1.5px solid #475569;
    background-color: #090d16;
}
QCheckBox::indicator:checked {
    background-color: #f43f5e;
    border-color: #f43f5e;
}
QRadioButton {
    spacing: 8px;
    color: #cbd5e1;
    font-size: 13px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 1.5px solid #475569;
    background-color: #090d16;
}
QRadioButton::indicator:checked {
    background-color: #f43f5e;
    border-color: #f43f5e;
}
QListWidget {
    background-color: #090d16;
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 6px;
}
QListWidget::item {
    background-color: #131d31;
    border: 1px solid #1e293b;
    border-radius: 10px;
    margin: 3px 0px;
    padding: 8px 12px;
}
QListWidget::item:selected {
    background-color: #1e1b4b;
    border: 1.5px solid #6366f1;
}
QProgressBar {
    border: 1px solid #1e293b;
    border-radius: 8px;
    background-color: #090d16;
    text-align: center;
    color: #f8fafc;
    font-size: 11px;
}
QProgressBar::chunk {
    background-color: #f43f5e;
    border-radius: 7px;
}
QScrollBar:vertical {
    border: none;
    background: #090d16;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 4px;
}
"""

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

    def __init__(self, reuse_existing=False):
        super().__init__()
        self.reuse_existing = reuse_existing
        self._is_running = True

    def run(self):
        try:
            cfg = load_config()
            existing_state = cfg.get("storage_state") if self.reuse_existing else None

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"]
                )
                context_kwargs = {
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "viewport": {"width": 1280, "height": 800}
                }
                if existing_state:
                    context_kwargs["storage_state"] = existing_state

                context = browser.new_context(**context_kwargs)
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
                        raw_chats = fetch_all_chats(page, max_scrolls=15)
                        browser.close()
                        self.login_success_signal.emit(raw_chats, storage_state, cookies)
                        return

                    # 截取登录二维码
                    try:
                        qr_element = page.query_selector("div[class*='qrcode'], div[class*='login'], div[class*='modal'], canvas, img[src*='qrcode']")
                        if qr_element:
                            img_bytes = qr_element.screenshot()
                        else:
                            img_bytes = page.screenshot(clip={"x": 300, "y": 100, "width": 680, "height": 600})
                        
                        pixmap = QPixmap()
                        pixmap.loadFromData(img_bytes)
                        self.qr_signal.emit(pixmap, "请打开手机抖音 App 扫码登录")
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
        self.setWindowTitle("Douyin Streak Setup - 抖音自动续火花一键部署")
        self.setMinimumSize(900, 680)
        self.resize(940, 720)
        self.setStyleSheet(QSS_STYLE)

        # App state
        self.github_token = ""
        self.github_user = None
        self.repo_name = "douyin-auto-spark"
        self.repo_full_name = ""
        self.contacts = []
        self.storage_state = None
        self.cookies = None
        self.deploy_result = None

        self._init_ui()
        self._init_clipboard_listener()

    def _init_clipboard_listener(self):
        # 自动监听剪贴板：小白用户在网页点击复制 Token 后，客户端秒级自动感知并填入！
        clipboard = QApplication.clipboard()
        clipboard.dataChanged.connect(self._on_clipboard_changed)

    def _on_clipboard_changed(self):
        if self.stack.currentIndex() != 0:
            return
        text = QApplication.clipboard().text().strip()
        if text.startswith("ghp_") or text.startswith("github_pat_"):
            if self.token_input.text().strip() != text:
                self.token_input.setText(text)
                self.token_tip_lbl.setText("🎉 检测到您复制了 GitHub Token，已自动填入！正在自动验证...")
                self.token_tip_lbl.setStyleSheet("color: #34d399; font-size: 11px; font-weight: bold;")
                QTimer.singleShot(500, self._handle_github_login)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(28, 20, 28, 20)
        main_layout.setSpacing(16)

        # Top Header
        header_layout = QHBoxLayout()
        logo_layout = QHBoxLayout()
        logo_icon = QLabel("🔥")
        logo_icon.setFont(QFont("Segoe UI Emoji", 24))
        logo_text_layout = QVBoxLayout()
        logo_title = QLabel("Douyin Streak Setup")
        logo_title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        logo_sub = QLabel("抖音火花全自动云端托管 · 小白一键部署向导")
        logo_sub.setProperty("class", "Muted")
        logo_text_layout.addWidget(logo_title)
        logo_text_layout.addWidget(logo_sub)
        logo_layout.addWidget(logo_icon)
        logo_layout.addLayout(logo_text_layout)

        self.user_chip = QLabel("未连接云端账号")
        self.user_chip.setStyleSheet("background-color: #1e293b; padding: 6px 14px; border-radius: 12px; font-size: 11px; color: #94a3b8;")

        header_layout.addLayout(logo_layout)
        header_layout.addStretch()
        header_layout.addWidget(self.user_chip)
        main_layout.addLayout(header_layout)

        # Step Indicator Bar
        self.step_bar_layout = QHBoxLayout()
        self.step_labels = []
        step_names = ["1. 连接云端", "2. 支持项目⭐", "3. 准备环境", "4. 扫码抖音", "5. 勾选好友", "6. 发送策略", "7. 开启成功🎉"]
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

        # Initialize all 7 pages
        self._init_step1_github_login()
        self._init_step2_star_project()
        self._init_step3_create_repo()
        self._init_step4_douyin_qr()
        self._init_step5_select_contacts()
        self._init_step6_message_strategy()
        self._init_step7_deploy_success()

        self.set_step(0)

    def set_step(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, lbl in enumerate(self.step_labels):
            if i == idx:
                lbl.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: bold; background-color: #2d1522; border-radius: 6px; padding: 4px 8px;")
            elif i < idx:
                lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: bold; padding: 4px;")
            else:
                lbl.setStyleSheet("color: #475569; font-size: 11px; padding: 4px;")

    # ==================== STEP 1: GitHub Login (Beginner Friendly) ====================
    def _init_step1_github_login(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setProperty("class", "Card")
        card.setFixedWidth(620)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 28, 36, 28)
        card_layout.setSpacing(16)

        icon_lbl = QLabel("☁️")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 32))
        icon_lbl.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(icon_lbl)

        title = QLabel("第一步：连接 GitHub 免费云端账号")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        desc = QLabel("💡 为什么需要这一步？\n通过 GitHub 提供的免费云端服务器，每天早晚会自动帮您续火花，您完全不用开电脑或手机！")
        desc.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.6; background-color: #0d1527; padding: 12px; border-radius: 10px; border: 1px solid #1e293b;")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        # 3 步傻瓜操作说明
        guide_box = QFrame()
        guide_box.setProperty("class", "TipBox")
        guide_layout = QVBoxLayout(guide_box)
        guide_layout.setSpacing(6)
        guide_title = QLabel("👇 3 步傻瓜式获取 Token（仅需 10 秒）:")
        guide_title.setStyleSheet("color: #f43f5e; font-weight: bold; font-size: 12px;")
        guide_1 = QLabel("1. 点击下方按钮，将在浏览器中自动打开 GitHub 授权页面")
        guide_2 = QLabel("2. 页面已为您自动勾选好所有权限，直接滑到底部点击绿色按钮【Generate token】")
        guide_3 = QLabel("3. 点击复制生成的代码，本软件会自动识别并自动填入！")
        for g in (guide_1, guide_2, guide_3):
            g.setStyleSheet("color: #94a3b8; font-size: 11px;")
        guide_layout.addWidget(guide_title)
        guide_layout.addWidget(guide_1)
        guide_layout.addWidget(guide_2)
        guide_layout.addWidget(guide_3)
        card_layout.addWidget(guide_box)

        open_browser_btn = QPushButton("🔑 点击一键在浏览器打开 GitHub 生成页面 →")
        open_browser_btn.setProperty("class", "Primary")
        open_browser_btn.setFixedHeight(40)
        open_browser_btn.clicked.connect(lambda: webbrowser.open("https://github.com/settings/tokens/new?scopes=repo,workflow&description=Douyin-Auto-Spark-Setup"))
        card_layout.addWidget(open_browser_btn)

        # Input & Auto-detect status
        token_input_layout = QVBoxLayout()
        token_input_layout.setSpacing(4)
        token_lbl = QLabel("或者在此手动粘贴 Token (以 ghp_ 开头):")
        token_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx (复制后会自动填入)")
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_tip_lbl = QLabel("💡 支持剪贴板自动监听：在网页上点击复制即可，无需手动粘贴。")
        self.token_tip_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        token_input_layout.addWidget(token_lbl)
        token_input_layout.addWidget(self.token_input)
        token_input_layout.addWidget(self.token_tip_lbl)
        card_layout.addLayout(token_input_layout)

        self.login_btn = QPushButton("验证并连接云端 →")
        self.login_btn.setFixedHeight(42)
        self.login_btn.clicked.connect(self._handle_github_login)
        card_layout.addWidget(self.login_btn)

        layout.addWidget(card)
        self.stack.addWidget(page)

    def _handle_github_login(self):
        token = self.token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "提示", "请先在浏览器生成并复制 GitHub Token，或在此粘贴。")
            return

        self.login_btn.setText("正在连接并验证云端账号...")
        self.login_btn.setEnabled(False)

        def verify():
            gh = GitHubService(token)
            return gh.get_user_info()

        self.login_worker = WorkerThread(verify)
        self.login_worker.finished_signal.connect(self._on_github_login_finished)
        self.login_worker.start()

    def _on_github_login_finished(self, res):
        self.login_btn.setEnabled(True)
        self.login_btn.setText("验证并连接云端 →")
        if res.get("ok"):
            self.github_token = self.token_input.text().strip()
            self.github_user = res
            self.user_chip.setText(f"👤 已连接: {res['login']}")
            self.user_chip.setStyleSheet("background-color: #064e3b; color: #34d399; padding: 6px 14px; border-radius: 12px; font-size: 11px; font-weight: bold;")
            self.set_step(1)
        else:
            QMessageBox.critical(self, "连接失败", "未能连接到 GitHub 账号，请检查 Token 是否复制完整或检查网络。")

    # ==================== STEP 2: Star Project ====================
    def _init_step2_star_project(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setProperty("class", "Card")
        card.setFixedWidth(560)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 32)
        card_layout.setSpacing(20)

        star_icon = QLabel("⭐")
        star_icon.setFont(QFont("Segoe UI Emoji", 36))
        star_icon.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(star_icon)

        title = QLabel("支持这个项目")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        desc = QLabel("这个工具完全免费且开源。如果觉得对您有帮助，不妨给项目点个 Star 吧！您的支持是我们持续免费维护的最大动力 ❤️")
        desc.setStyleSheet("color: #cbd5e1; font-size: 13px; line-height: 1.6;")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(desc)

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(12)

        self.star_btn = QPushButton("⭐ Star 并继续")
        self.star_btn.setProperty("class", "Star")
        self.star_btn.setFixedHeight(46)
        self.star_btn.clicked.connect(self._handle_star_and_continue)
        btn_layout.addWidget(self.star_btn)

        skip_btn = QPushButton("跳过，直接部署")
        skip_btn.setProperty("class", "Secondary")
        skip_btn.setFixedHeight(38)
        skip_btn.clicked.connect(self._advance_to_step3)
        btn_layout.addWidget(skip_btn)

        card_layout.addLayout(btn_layout)
        layout.addWidget(card)
        self.stack.addWidget(page)

    def _handle_star_and_continue(self):
        self.star_btn.setText("正在 Star MaaBlock/douyin-auto-spark...")
        self.star_btn.setEnabled(False)

        def star():
            gh = GitHubService(self.github_token)
            return gh.star_upstream()

        self.star_worker = WorkerThread(star)
        self.star_worker.finished_signal.connect(lambda res: (self.star_btn.setEnabled(True), self.star_btn.setText("⭐ Star 并继续"), self._advance_to_step3()))
        self.star_worker.start()

    def _advance_to_step3(self):
        self.set_step(2)
        # 小白用户无需手动点按钮，进入步骤 3 自动开始准备云端空间！
        QTimer.singleShot(400, self._handle_create_repo)

    # ==================== STEP 3: Automatic Environment Setup ====================
    def _init_step3_create_repo(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setProperty("class", "Card")
        card.setFixedWidth(580)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 32)
        card_layout.setSpacing(16)

        title = QLabel("📦 正在全自动准备您的专属云端空间")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        card_layout.addWidget(title)

        desc = QLabel("系统正在为您自动创建私有代码空间，并配置好每日定时自动续火花脚本。无需任何手动操作，请稍候...")
        desc.setProperty("class", "Muted")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        self.step3_progress = QProgressBar()
        self.step3_progress.setFixedHeight(22)
        self.step3_progress.setValue(30)
        card_layout.addWidget(self.step3_progress)

        self.create_repo_log = QTextEdit()
        self.create_repo_log.setReadOnly(True)
        self.create_repo_log.setFixedHeight(120)
        self.create_repo_log.setFont(QFont("Consolas", 10))
        self.create_repo_log.setStyleSheet("background-color: #090d16; color: #94a3b8; border-radius: 10px;")
        card_layout.addWidget(self.create_repo_log)

        layout.addWidget(card)
        self.stack.addWidget(page)

    def _handle_create_repo(self):
        self.step3_progress.setValue(40)
        self.create_repo_log.append("▶ 正在连接云端并创建私有空间...")

        def create_and_deploy():
            gh = GitHubService(self.github_token)
            repo_res = gh.ensure_private_repo(self.repo_name)
            if not repo_res.get("ok"):
                return repo_res

            repo_full_name = repo_res["full_name"]
            if repo_res.get("from_template"):
                # 通过公共模板库直接一键实例化成功，无需逐个文件上传
                return {"ok": True, "repo": repo_res, "deploy": {"ok": True}}

            files_to_deploy = {}
            file_list = [
                "douyin_spark.py",
                "requirements.txt",
                "config.example.json",
                "README.md",
                os.path.join(".github", "workflows", "douyin_spark.yml")
            ]
            for rel_path in file_list:
                full_path = os.path.join(BASE_DIR, rel_path)
                if os.path.exists(full_path):
                    with open(full_path, "rb") as f:
                        posix_path = rel_path.replace("\\", "/")
                        files_to_deploy[posix_path] = f.read()

            deploy_res = gh.deploy_files(repo_full_name, files_to_deploy)
            return {"ok": True, "repo": repo_res, "deploy": deploy_res}

        self.create_worker = WorkerThread(create_and_deploy)
        self.create_worker.finished_signal.connect(self._on_create_repo_finished)
        self.create_worker.start()

    def _on_create_repo_finished(self, res):
        if res.get("ok"):
            self.repo_full_name = res["repo"]["full_name"]
            self.step3_progress.setValue(100)
            self.create_repo_log.append(f"✔ 专属私有空间已就绪: {self.repo_full_name}")
            self.create_repo_log.append("✔ 自动续火花脚本已配置完毕！即将进入扫码步骤...")
            QTimer.singleShot(900, lambda: (self.set_step(3), self._start_douyin_qr_login()))
        else:
            self.create_repo_log.append(f"❌ 失败: {res.get('error')}")
            QMessageBox.critical(self, "配置失败", res.get("error", "未知错误"))

    # ==================== STEP 4: Douyin QR Code Login (Crystal Clear Guidance) ====================
    def _init_step4_douyin_qr(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setProperty("class", "Card")
        card.setFixedWidth(600)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 24, 36, 24)
        card_layout.setSpacing(14)

        title = QLabel("📱 扫码登录抖音")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        # 3步手机操作指引
        step_tip = QLabel("1. 打开手机【抖音】App  👉  2. 点击右上角【扫一扫】  👉  3. 扫描下方二维码并点击确认")
        step_tip.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: bold; background-color: #2d1522; padding: 8px; border-radius: 8px;")
        step_tip.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(step_tip)

        self.qr_label = QLabel("正在启动浏览器并生成二维码...")
        self.qr_label.setFixedSize(220, 220)
        self.qr_label.setStyleSheet("background-color: #090d16; border: 2px dashed #334155; border-radius: 16px; color: #64748b; font-size: 11px;")
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setScaledContents(True)

        qr_center_layout = QHBoxLayout()
        qr_center_layout.addStretch()
        qr_center_layout.addWidget(self.qr_label)
        qr_center_layout.addStretch()
        card_layout.addLayout(qr_center_layout)

        self.qr_status_lbl = QLabel("⏳ 正在拉起登录引擎...")
        self.qr_status_lbl.setAlignment(Qt.AlignCenter)
        self.qr_status_lbl.setStyleSheet("color: #f43f5e; font-size: 12px; font-weight: bold;")
        card_layout.addWidget(self.qr_status_lbl)

        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 刷新二维码")
        refresh_btn.clicked.connect(self._start_douyin_qr_login)
        use_local_btn = QPushButton("⚡ 使用本地已有凭据 (跳过扫码)")
        use_local_btn.setProperty("class", "Secondary")
        use_local_btn.clicked.connect(self._use_local_credentials)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addWidget(use_local_btn)
        card_layout.addLayout(btn_layout)

        layout.addWidget(card)
        self.stack.addWidget(page)

    def _start_douyin_qr_login(self):
        self.qr_status_lbl.setText("⏳ 正在获取最新登录二维码...")
        self.douyin_thread = DouyinLoginThread(reuse_existing=False)
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
        self.qr_status_lbl.setText("🎉 扫码成功！正在自动读取好友列表...")
        save_secret_config(storage_state, cookies=cookies)

        cfg = load_config()
        current_targets = cfg.get("targets", [])
        current_names = [t.get("name") if isinstance(t, dict) else str(t) for t in current_targets]

        self.contacts = []
        for c in raw_chats:
            name = c["name"]
            is_sel = any(cur == name or (cur and (cur in name or name in cur)) for cur in current_names)
            self.contacts.append({
                "name": name,
                "preview": c.get("preview", ""),
                "selected": is_sel
            })

        self._refresh_contacts_list()
        QTimer.singleShot(800, lambda: self.set_step(4))

    def _use_local_credentials(self):
        cfg = load_config()
        if cfg.get("storage_state"):
            self.storage_state = cfg["storage_state"]
            self.cookies = cfg.get("cookies", [])
            targets = cfg.get("targets", [])
            self.contacts = [{"name": (t.get("name") if isinstance(t, dict) else str(t)), "preview": "已选好友", "selected": True} for t in targets]
            self._refresh_contacts_list()
            self.set_step(4)
        else:
            QMessageBox.warning(self, "提示", "本地未检测到登录凭据，请扫码登录。")

    # ==================== STEP 5: Select Contacts ====================
    def _init_step5_select_contacts(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("👥 勾选想要每天自动续火花的好友")
        title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        self.contacts_count_lbl = QLabel("已从您的账号中读取到 0 个好友/群聊")
        self.contacts_count_lbl.setProperty("class", "Muted")
        title_box.addWidget(title)
        title_box.addWidget(self.contacts_count_lbl)

        btn_box = QHBoxLayout()
        all_btn = QPushButton("全选")
        all_btn.clicked.connect(lambda: self._set_all_contacts(True))
        none_btn = QPushButton("清空")
        none_btn.clicked.connect(lambda: self._set_all_contacts(False))
        self.selected_badge = QLabel("已选择 0 位好友")
        self.selected_badge.setStyleSheet("background-color: #2d1522; color: #f43f5e; padding: 6px 14px; border-radius: 8px; font-weight: bold; font-size: 11px;")
        btn_box.addWidget(all_btn)
        btn_box.addWidget(none_btn)
        btn_box.addWidget(self.selected_badge)

        header_layout.addLayout(title_box)
        header_layout.addStretch()
        header_layout.addLayout(btn_box)
        layout.addLayout(header_layout)

        # Search Bar & Add Custom
        search_layout = QHBoxLayout()
        self.contact_search = QLineEdit()
        self.contact_search.setPlaceholderText("🔍 快速搜索好友昵称...")
        self.contact_search.textChanged.connect(self._filter_contacts)

        self.custom_friend_input = QLineEdit()
        self.custom_friend_input.setPlaceholderText("手动添加昵称")
        self.custom_friend_input.setFixedWidth(160)
        add_friend_btn = QPushButton("+ 添加")
        add_friend_btn.clicked.connect(self._add_custom_friend)

        search_layout.addWidget(self.contact_search)
        search_layout.addWidget(self.custom_friend_input)
        search_layout.addWidget(add_friend_btn)
        layout.addLayout(search_layout)

        # Contacts List Widget
        self.contacts_list_widget = QListWidget()
        layout.addWidget(self.contacts_list_widget, 1)

        # Bottom nav
        bottom_nav = QHBoxLayout()
        back_btn = QPushButton("← 上一步")
        back_btn.clicked.connect(lambda: self.set_step(3))
        self.step5_next_btn = QPushButton("下一步: 设置文案与策略 →")
        self.step5_next_btn.setProperty("class", "Primary")
        self.step5_next_btn.clicked.connect(self._handle_step5_next)

        bottom_nav.addWidget(back_btn)
        bottom_nav.addStretch()
        bottom_nav.addWidget(self.step5_next_btn)
        layout.addLayout(bottom_nav)

        self.stack.addWidget(page)

    def _refresh_contacts_list(self):
        self.contacts_list_widget.clear()
        self.contacts_count_lbl.setText(f"已从您的账号中读取到 {len(self.contacts)} 个好友/群聊")
        q = self.contact_search.text().strip().lower()

        sel_count = 0
        for idx, c in enumerate(self.contacts):
            name = c["name"]
            preview = c.get("preview", "")
            is_sel = c.get("selected", False)
            if is_sel:
                sel_count += 1

            if q and (q not in name.lower() and q not in preview.lower()):
                continue

            item = QListWidgetItem()
            item.setSizeHint(QSize(100, 44))

            chk = QCheckBox(f"  {name}  {f'({preview})' if preview else ''}")
            chk.setChecked(is_sel)
            chk.stateChanged.connect(lambda state, index=idx: self._on_contact_check_changed(index, state == Qt.Checked))

            self.contacts_list_widget.addItem(item)
            self.contacts_list_widget.setItemWidget(item, chk)

        self.selected_badge.setText(f"已选择 {sel_count} 位好友")

    def _on_contact_check_changed(self, index, checked):
        if 0 <= index < len(self.contacts):
            self.contacts[index]["selected"] = checked
        sel_count = sum(1 for c in self.contacts if c.get("selected"))
        self.selected_badge.setText(f"已选择 {sel_count} 位好友")

    def _filter_contacts(self):
        self._refresh_contacts_list()

    def _set_all_contacts(self, val):
        for c in self.contacts:
            c["selected"] = val
        self._refresh_contacts_list()

    def _add_custom_friend(self):
        name = self.custom_friend_input.text().strip()
        if not name:
            return
        if not any(c["name"] == name for c in self.contacts):
            self.contacts.insert(0, {"name": name, "preview": "手动添加", "selected": True})
            self.custom_friend_input.clear()
            self._refresh_contacts_list()

    def _handle_step5_next(self):
        selected = [c["name"] for c in self.contacts if c.get("selected")]
        if not selected:
            QMessageBox.warning(self, "提示", "请至少勾选一位想要续火花的好友！")
            return
        self.set_step(5)

    # ==================== STEP 6: Message & Strategy (Beginner Friendly Default) ====================
    def _init_step6_message_strategy(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        title = QLabel("💬 选择续火花发送文案与策略")
        title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        layout.addWidget(title)

        card = QFrame()
        card.setProperty("class", "Card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)

        mode_lbl = QLabel("文案发送风格 (默认已为您选择最佳防封推荐):")
        mode_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        card_layout.addWidget(mode_lbl)

        mode_btn_layout = QHBoxLayout()
        self.radio_pool = QRadioButton("🎲 推荐智能随机文案库 (每天换一句，真实自然、不当复读机)")
        self.radio_pool.setChecked(True)
        self.radio_single = QRadioButton("💬 统一固定一条文案")
        self.radio_pool.toggled.connect(self._on_message_mode_changed)

        mode_btn_layout.addWidget(self.radio_pool)
        mode_btn_layout.addWidget(self.radio_single)
        card_layout.addLayout(mode_btn_layout)

        # Random Pool Editor
        self.pool_box = QFrame()
        self.pool_box.setProperty("class", "TipBox")
        pool_layout = QVBoxLayout(self.pool_box)
        pool_title = QLabel("文案库内容 (系统每天自动随机抽一条发送):")
        pool_title.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.pool_text_edit = QTextEdit()
        self.pool_text_edit.setFixedHeight(90)
        self.pool_text_edit.setText("续火花 🔥\n🔥\n滴滴续火花~\n今日火花打卡✨\n{greeting}，{name}，续火花啦☀️")
        pool_layout.addWidget(pool_title)
        pool_layout.addWidget(self.pool_text_edit)
        card_layout.addWidget(self.pool_box)

        # Single Message Editor
        self.single_box = QFrame()
        self.single_box.setProperty("class", "TipBox")
        self.single_box.setVisible(False)
        single_layout = QVBoxLayout(self.single_box)
        self.single_msg_input = QLineEdit("续火花 🔥")
        single_layout.addWidget(QLabel("固定发送的内容:"))
        single_layout.addWidget(self.single_msg_input)
        card_layout.addWidget(self.single_box)

        # Schedule notice
        sched_box = QFrame()
        sched_box.setStyleSheet("background-color: #090d16; border-radius: 10px; padding: 10px;")
        sched_layout = QVBoxLayout(sched_box)
        sched_lbl = QLabel("⏰ 云端执行计划: 每天早上 08:30 和 晚上 20:30 自动发送（双重保险，防遗漏）")
        sched_lbl.setStyleSheet("color: #34d399; font-size: 11px; font-weight: bold;")
        sched_layout.addWidget(sched_lbl)
        card_layout.addWidget(sched_box)

        self.trigger_now_chk = QCheckBox("部署完成后立即在云端触发一次测试运行 (验证是否能正常发送)")
        self.trigger_now_chk.setChecked(True)
        card_layout.addWidget(self.trigger_now_chk)

        layout.addWidget(card)

        # Bottom nav
        bottom_nav = QHBoxLayout()
        back_btn = QPushButton("← 上一步")
        back_btn.clicked.connect(lambda: self.set_step(4))
        self.deploy_btn = QPushButton("🚀 立即开启全自动云端托管")
        self.deploy_btn.setProperty("class", "Primary")
        self.deploy_btn.setFixedHeight(44)
        self.deploy_btn.clicked.connect(self._handle_final_deploy)

        bottom_nav.addWidget(back_btn)
        bottom_nav.addStretch()
        bottom_nav.addWidget(self.deploy_btn)
        layout.addLayout(bottom_nav)

        self.stack.addWidget(page)

    def _on_message_mode_changed(self):
        is_pool = self.radio_pool.isChecked()
        self.pool_box.setVisible(is_pool)
        self.single_box.setVisible(not is_pool)

    def _handle_final_deploy(self):
        self.deploy_btn.setEnabled(False)
        self.deploy_btn.setText("正在加密配置并开启云端工作流...")

        selected_targets = [c["name"] for c in self.contacts if c.get("selected")]
        is_pool = self.radio_pool.isChecked()
        if is_pool:
            pool_lines = [l.strip() for l in self.pool_text_edit.toPlainText().split("\n") if l.strip()]
            message = pool_lines[0] if pool_lines else "续火花 🔥"
            messages = pool_lines
        else:
            message = self.single_msg_input.text().strip() or "续火花 🔥"
            messages = None

        trigger_now = self.trigger_now_chk.isChecked()

        def deploy_task():
            save_base_config(
                targets=selected_targets,
                message=message,
                send_time="08:30",
                headless=False,
                messages=messages
            )
            secret_json = save_secret_config(
                storage_state=self.storage_state,
                targets=selected_targets,
                message=message,
                messages=messages,
                cookies=self.cookies
            )

            gh = GitHubService(self.github_token)
            secret_res = gh.set_secret(self.repo_full_name, "DOUYIN_CONFIG", secret_json)
            if not secret_res.get("ok"):
                return secret_res

            if trigger_now:
                gh.trigger_workflow(self.repo_full_name)

            return {
                "ok": True,
                "repo_url": f"https://github.com/{self.repo_full_name}",
                "actions_url": f"https://github.com/{self.repo_full_name}/actions",
                "targets_count": len(selected_targets)
            }

        self.deploy_worker = WorkerThread(deploy_task)
        self.deploy_worker.finished_signal.connect(self._on_deploy_finished)
        self.deploy_worker.start()

    def _on_deploy_finished(self, res):
        self.deploy_btn.setEnabled(True)
        self.deploy_btn.setText("🚀 立即开启全自动云端托管")
        if res.get("ok"):
            self.deploy_result = res
            self._update_step7_ui()
            self.set_step(6)
        else:
            QMessageBox.critical(self, "开启失败", res.get("error", "云端凭证加密失败，请检查网络。"))

    # ==================== STEP 7: Deploy Success + Beginner FAQ ====================
    def _init_step7_deploy_success(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setProperty("class", "CardGlow")
        card.setFixedWidth(640)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 28, 36, 28)
        card_layout.setSpacing(16)

        succ_icon = QLabel("🎉")
        succ_icon.setFont(QFont("Segoe UI Emoji", 36))
        succ_icon.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(succ_icon)

        title = QLabel("恭喜！全自动云端续火花已开启！")
        title.setFont(QFont("Segoe UI", 17, QFont.Bold))
        title.setStyleSheet("color: #10b981;")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        desc = QLabel("从现在起，每天早晚云端会自动替您向好友发送续火花消息，您无需打开电脑或手机！")
        desc.setProperty("class", "Muted")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(desc)

        self.summary_box = QFrame()
        self.summary_box.setProperty("class", "TipBox")
        summary_layout = QVBoxLayout(self.summary_box)
        summary_layout.setSpacing(8)

        self.succ_repo_lbl = QLabel("📦 专属私有空间: (已就绪)")
        self.succ_repo_lbl.setStyleSheet("color: #f43f5e; font-family: Consolas;")
        self.succ_targets_lbl = QLabel("👥 续火花目标: 0 位好友")
        self.succ_sched_lbl = QLabel("⏰ 每日定时运行: 每天 08:30 与 20:30 (北京时间)")
        self.succ_sched_lbl.setStyleSheet("color: #10b981; font-weight: bold;")
        self.succ_shot_lbl = QLabel("📸 运行截图保存: 每次发送完毕自动在 GitHub 保存现场截图")
        self.succ_shot_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")

        summary_layout.addWidget(self.succ_repo_lbl)
        summary_layout.addWidget(self.succ_targets_lbl)
        summary_layout.addWidget(self.succ_sched_lbl)
        summary_layout.addWidget(self.succ_shot_lbl)
        card_layout.addWidget(self.summary_box)

        # 小白常见疑问解答 FAQ
        faq_box = QFrame()
        faq_box.setStyleSheet("background-color: #090d16; border-radius: 10px; padding: 10px;")
        faq_layout = QVBoxLayout(faq_box)
        faq_layout.setSpacing(6)
        faq_t = QLabel("💡 常见小白疑问解答:")
        faq_t.setStyleSheet("color: #f43f5e; font-weight: bold; font-size: 11px;")
        faq_1 = QLabel("Q: 电脑关机了还会自动续吗？\n A: 会！任务在 GitHub 云端执行，电脑关机断网丝毫不影响。")
        faq_2 = QLabel("Q: 以后想换好友或改文案怎么办？\n A: 随时重新打开这个小软件，勾选新好友并点确定即可更新。")
        for f in (faq_1, faq_2):
            f.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        faq_layout.addWidget(faq_t)
        faq_layout.addWidget(faq_1)
        faq_layout.addWidget(faq_2)
        card_layout.addWidget(faq_box)

        action_btn_layout = QHBoxLayout()
        action_btn_layout.setSpacing(10)

        self.open_actions_btn = QPushButton("🔍 查看云端运行记录 ↗")
        self.open_actions_btn.setProperty("class", "Success")
        self.open_actions_btn.setFixedHeight(42)
        self.open_actions_btn.clicked.connect(lambda: webbrowser.open(self.deploy_result.get("actions_url", "https://github.com")))

        retrigger_btn = QPushButton("🧪 立即测试发送一次")
        retrigger_btn.setFixedHeight(42)
        retrigger_btn.clicked.connect(self._retrigger_workflow)

        action_btn_layout.addWidget(self.open_actions_btn)
        action_btn_layout.addWidget(retrigger_btn)
        card_layout.addLayout(action_btn_layout)

        layout.addWidget(card)
        self.stack.addWidget(page)

    def _update_step7_ui(self):
        if self.deploy_result:
            self.succ_repo_lbl.setText(f"📦 专属私有空间: {self.repo_full_name}")
            self.succ_targets_lbl.setText(f"👥 续火花目标: {self.deploy_result.get('targets_count', 0)} 位好友/群聊")

    def _retrigger_workflow(self):
        def trigger():
            gh = GitHubService(self.github_token)
            return gh.trigger_workflow(self.repo_full_name)

        worker = WorkerThread(trigger)
        worker.finished_signal.connect(lambda res: QMessageBox.information(self, "提示", "🎉 成功触发云端运行！稍等 1-2 分钟即可在 GitHub 看到发送截图。" if res.get("ok") else f"触发失败: {res.get('error')}"))
        worker.start()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

import os
import sys
import time
import json
import base64
import threading
from playwright.sync_api import sync_playwright
from douyin_spark import (
    load_config,
    save_base_config,
    save_secret_config,
    fetch_all_chats,
    SECRET_FILE,
    CONFIG_FILE
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

class DouyinWebSessionManager:
    """
    负责在后台运行 Playwright，提供实时截屏/二维码、登录状态检测与好友列表抓取
    """
    def __init__(self):
        self.status = "idle"  # idle | launching | waiting_scan | scanned | logged_in | ready | error
        self.message = "未启动"
        self.qrcode_b64 = None
        self.storage_state = None
        self.cookies = None
        self.contacts = []
        self.error = None
        self._thread = None
        self._stop_event = threading.Event()

    def get_state(self):
        return {
            "status": self.status,
            "message": self.message,
            "qrcode": self.qrcode_b64,
            "contacts": self.contacts,
            "error": self.error,
            "has_credentials": self.storage_state is not None
        }

    def start_login(self, reuse_existing=False):
        if self._thread and self._thread.is_alive():
            return {"ok": True, "message": "登录会话已在运行中"}

        self.status = "launching"
        self.message = "正在启动 Chromium 浏览器..."
        self.qrcode_b64 = None
        self.error = None
        self._stop_event.clear()

        self._thread = threading.Thread(target=self._run_browser_session, args=(reuse_existing,), daemon=True)
        self._thread.start()
        return {"ok": True, "message": "启动成功"}

    def use_existing_config(self):
        cfg = load_config()
        if cfg.get("storage_state"):
            self.storage_state = cfg["storage_state"]
            self.cookies = cfg.get("cookies", [])
            self.status = "ready"
            self.message = "已加载本地现有登录凭证"
            # 尝试把当前 targets 转换为 contacts 格式
            targets = cfg.get("targets", [])
            contacts = []
            for t in targets:
                if isinstance(t, dict):
                    contacts.append({"name": t.get("name", ""), "preview": "已配置专属文案", "selected": True, "custom_message": t.get("message")})
                else:
                    contacts.append({"name": str(t), "preview": "", "selected": True})
            self.contacts = contacts
            return {"ok": True, "contacts": contacts}
        return {"ok": False, "error": "未找到本地现有凭证，请使用扫码登录"}

    def _run_browser_session(self, reuse_existing=False):
        try:
            cfg = load_config()
            existing_state = cfg.get("storage_state") if reuse_existing else None

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage"
                    ]
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

                self.status = "waiting_scan"
                self.message = "正在加载抖音登录页面..."
                page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded")

                # 循环监测登录或捕获二维码
                max_checks = 120  # 最多等待 120 * 1.5s = 180 秒
                for check in range(max_checks):
                    if self._stop_event.is_set():
                        break

                    # 检查是否已登录成功
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
                        self.status = "logged_in"
                        self.message = "扫码成功！正在抓取全部好友与会话列表..."
                        self.storage_state = context.storage_state()
                        self.cookies = context.cookies()

                        # 抓取全部会话
                        raw_chats = fetch_all_chats(page, max_scrolls=15)
                        contacts = []
                        current_targets = cfg.get("targets", [])
                        current_names = [t.get("name") if isinstance(t, dict) else str(t) for t in current_targets]

                        for c in raw_chats:
                            name = c["name"]
                            is_sel = any(cur == name or (cur and (cur in name or name in cur)) for cur in current_names)
                            contacts.append({
                                "name": name,
                                "preview": c.get("preview", ""),
                                "selected": is_sel
                            })

                        self.contacts = contacts
                        self.status = "ready"
                        self.message = f"成功获取 {len(contacts)} 个好友/群聊"

                        # 自动持久化本地凭据
                        save_secret_config(self.storage_state, cookies=self.cookies)
                        break

                    # 截取登录二维码
                    try:
                        qr_element = page.query_selector("div[class*='qrcode'], div[class*='login'], div[class*='modal'], canvas, img[src*='qrcode']")
                        if qr_element:
                            img_bytes = qr_element.screenshot()
                        else:
                            # 截取中心区域
                            img_bytes = page.screenshot(clip={"x": 300, "y": 100, "width": 680, "height": 600})
                        
                        self.qrcode_b64 = f"data:image/png;base64,{base64.b64encode(img_bytes).decode('utf-8')}"
                        self.message = "请使用手机抖音 App 扫描下方二维码登录"
                    except Exception:
                        pass

                    page.wait_for_timeout(1500)

                browser.close()

        except Exception as e:
            self.status = "error"
            self.error = str(e)
            self.message = f"运行发生异常: {e}"

    def stop(self):
        self._stop_event.set()

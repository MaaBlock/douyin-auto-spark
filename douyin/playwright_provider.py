import os
import time
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

from config.model import Conversation
from douyin.provider import DouyinProvider, SendResult
from douyin.conversations import extract_conversations_from_dom
from douyin.sender import send_message_to_conversation

class PlaywrightDouyinProvider(DouyinProvider):
    def __init__(self, headless: bool = True, screenshots_dir: Optional[str] = None):
        self.headless = headless
        self.screenshots_dir = screenshots_dir
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def _ensure_browser(self, storage_state: Optional[Dict[str, Any]] = None, cookies: Optional[list] = None):
        if self._browser and self._context and self._page:
            return

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1920,1080"
            ]
        )

        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1920, "height": 1080},
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai"
        }
        if storage_state:
            context_kwargs["storage_state"] = storage_state

        self._context = self._browser.new_context(**context_kwargs)
        if cookies and not storage_state:
            self._context.add_cookies(cookies)

        self._page = self._context.new_page()
        self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        """)

    def start_login_session(self):
        self.headless = False
        self._ensure_browser()
        self._page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded")
        return self._page, self._context

    def restore_session(self, session_data: Dict[str, Any]) -> bool:
        storage_state = session_data.get("storage_state")
        cookies = session_data.get("cookies", [])
        self._ensure_browser(storage_state=storage_state, cookies=cookies)
        self._page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded", timeout=60000)
        return self.is_logged_in()

    def is_logged_in(self, max_retries: int = 15) -> bool:
        if not self._page:
            return False

        for attempt in range(1, max_retries + 1):
            if "login" in self._page.url.lower() or self._page.query_selector("div[class*='login'], div:has-text('扫码登录')"):
                return False

            has_cards = self._page.evaluate("""() => {
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
                return True
            self._page.wait_for_timeout(1500)

        return False

    def list_conversations(self) -> List[Conversation]:
        if not self._page:
            return []
        return extract_conversations_from_dom(self._page)

    def send_message(self, target_id: str, message: str, dry_run: bool = False) -> SendResult:
        if not self._page:
            return SendResult(ok=False, conversation_id=target_id, error="页面未初始化")
        return send_message_to_conversation(
            self._page,
            target_id=target_id,
            message=message,
            dry_run=dry_run,
            screenshots_dir=self.screenshots_dir
        )

    def close(self):
        try:
            if self._page:
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

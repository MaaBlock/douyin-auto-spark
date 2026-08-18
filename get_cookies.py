import os
import sys
import json
import subprocess
from playwright.sync_api import sync_playwright
from douyin_spark import (
    load_config,
    save_base_config,
    save_secret_config,
    fetch_all_chats,
    interactive_target_and_message_wizard,
    wait_for_chat_ready,
    SECRET_FILE
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def export_and_sync():
    print("==================================================")
    print("        抖音自动续火花 - 凭证导出与配置工具        ")
    print("==================================================")
    print("步骤说明:")
    print(" 1. 程序将自动拉起 Chromium 浏览器。")
    print(" 2. 请使用手机抖音 App 扫描二维码登录。")
    print(" 3. 成功登录并进入聊天页面后，返回本窗口按【Enter 回车键】。")
    print(" 4. 程序将自动扫描您的好友列表，并支持交互式选择目标和自定义文案。\n")

    current_cfg = load_config()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
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

        input("👉 扫码登录成功进入聊天页面后，在此处按下【回车键 (Enter)】继续...")

        storage_state = context.storage_state()
        cookies = context.cookies()

        ready, _ = wait_for_chat_ready(page, max_retries=10)
        if ready:
            scanned = fetch_all_chats(page)
            targets, msg, msgs = interactive_target_and_message_wizard(scanned, current_cfg)
        else:
            print("⚠️ 未能完全加载会话列表，将使用现有配置。")
            targets = current_cfg.get("targets", [])
            msg = current_cfg.get("message", "续火花")
            msgs = current_cfg.get("messages", None)

        save_base_config(targets=targets, message=msg, messages=msgs)
        save_secret_config(storage_state=storage_state, targets=targets, message=msg, messages=msgs, cookies=cookies)

        browser.close()

        print("\n==================================================")
        print("💡 若需手动更新 GitHub Actions Secret:")
        print(" 1. 打开 GitHub 仓库 -> Settings -> Secrets and variables -> Actions")
        print(" 2. 新建或更新 Secret 名称为: DOUYIN_CONFIG")
        print(f" 3. 将文件 {SECRET_FILE} 中的全部内容复制粘贴进 Secret Value 即可。")
        print("==================================================\n")

if __name__ == "__main__":
    export_and_sync()

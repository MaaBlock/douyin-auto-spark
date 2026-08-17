import os
import sys
import json
import subprocess
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
SECRET_FILE = os.path.join(BASE_DIR, "config_secret.json")

def load_defaults():
    targets = ["好友1", "好友2", "好友3", "好友4", "好友5", "好友6"]
    message = "续火花"
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                targets = data.get("targets", targets)
                message = data.get("message", message)
        except Exception:
            pass
    return targets, message

def export_and_sync():
    targets, message = load_defaults()

    print("==================================================")
    print("        抖音自动续火花 - 凭证导出与同步工具        ")
    print("==================================================")
    print(f"当前配置的目标好友/群聊 ({len(targets)} 个): {', '.join(targets)}")
    print(f"当前配置的发送消息: \"{message}\"")
    print("\n步骤说明:")
    print(" 1. 程序将自动拉起 Chromium 浏览器。")
    print(" 2. 请使用手机抖音 App 扫描二维码登录。")
    print(" 3. 成功登录并进入聊天页面后，返回本窗口按【Enter 回车键】。\n")

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
        page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded")

        input("👉 扫码登录成功进入聊天页面后，在此处按下【回车键 (Enter)】开始导出...")

        cookies = context.cookies()
        storage_state = context.storage_state()

        secret_data = {
            "targets": targets,
            "message": message,
            "storage_state": storage_state,
            "cookies": cookies
        }

        compact_json = json.dumps(secret_data, ensure_ascii=False, separators=(',', ':'))

        with open(SECRET_FILE, "w", encoding="utf-8") as f:
            f.write(compact_json)

        print("\n✅ 本地凭证文件保存成功: " + SECRET_FILE)
        browser.close()

        # 尝试使用 GitHub CLI 自动同步 Secret
        print("\n正在检测 GitHub CLI (gh) 状态...")
        try:
            res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
            if res.returncode == 0:
                print("检测到 GitHub CLI 已登录！正在自动同步 Secret 到 GitHub 仓库...")
                sync_res = subprocess.run(
                    ["gh", "secret", "set", "DOUYIN_CONFIG", "-b", compact_json],
                    capture_output=True,
                    text=True
                )
                if sync_res.returncode == 0:
                    print("🎉 成功自动将 DOUYIN_CONFIG Secret 同步至 GitHub 仓库！")
                else:
                    print(f"⚠️ 自动同步 Secret 提示: {sync_res.stderr.strip() or sync_res.stdout.strip()}")
            else:
                print("未检测到 gh 登录状态，可手动前往 GitHub 仓库设置 Secret。")
        except Exception:
            print("未找到 gh 命令行，可手动前往 GitHub 仓库设置 Secret。")

        print("\n==================================================")
        print("💡 若需手动更新 GitHub Actions Secret:")
        print(" 1. 打开 GitHub 仓库 -> Settings -> Secrets and variables -> Actions")
        print(" 2. 新建或更新 Secret 名称为: DOUYIN_CONFIG")
        print(f" 3. 将文件 {SECRET_FILE} 中的全部内容复制粘贴进 Secret Value 即可。")
        print("==================================================\n")

if __name__ == "__main__":
    export_and_sync()

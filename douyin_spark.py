import os
import sys
import json
import time
import random
import datetime
import argparse
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
SECRET_FILE = os.path.join(BASE_DIR, "config_secret.json")
LOG_FILE = os.path.join(BASE_DIR, "spark_log.txt")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def log(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {msg}"
    print(log_line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception:
        pass

def load_config(is_actions=False):
    cfg = {}
    
    # 1. 尝试从 GitHub Actions 环境变量读取
    env_config = os.environ.get("DOUYIN_CONFIG", "").strip()
    if env_config:
        try:
            cfg = json.loads(env_config)
            log("✅ 已从环境变量 DOUYIN_CONFIG 成功加载配置")
            return cfg
        except Exception as e:
            log(f"⚠️ 解析环境变量 DOUYIN_CONFIG 失败: {e}")

    # 2. 从本地 config_secret.json 读取凭证与配置
    if os.path.exists(SECRET_FILE):
        try:
            with open(SECRET_FILE, "r", encoding="utf-8") as sf:
                cfg = json.load(sf)
                log("✅ 已从本地 config_secret.json 加载凭证配置")
        except Exception as e:
            log(f"⚠️ 读取 config_secret.json 失败: {e}")

    # 3. 补充 config.json 默认配置
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                base_cfg = json.load(f)
                for k, v in base_cfg.items():
                    if k not in cfg or not cfg[k]:
                        cfg[k] = v
        except Exception as e:
            log(f"⚠️ 读取 config.json 失败: {e}")

    if not cfg:
        cfg = {
            "targets": ["好友1", "好友2", "好友3", "好友4", "好友5", "好友6"],
            "message": "续火花",
            "send_time": "08:30",
            "headless": False
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

    return cfg

def save_secret_config(storage_state, targets=None, message=None):
    current_cfg = load_config()
    # 过滤超大营销缓存（确保适配 GitHub Secret 64KB 大小限制）
    if isinstance(storage_state, dict):
        for orig in storage_state.get("origins", []):
            orig["localStorage"] = [
                item for item in orig.get("localStorage", [])
                if item.get("name") not in ("LoginGuidingStrategy", "rawData")
            ]

    secret_data = {
        "targets": targets if targets is not None else current_cfg.get("targets", []),
        "message": message if message is not None else current_cfg.get("message", "续火花"),
        "storage_state": storage_state
    }

    json_str = json.dumps(secret_data, ensure_ascii=False, separators=(',', ':'))
    with open(SECRET_FILE, "w", encoding="utf-8") as f:
        f.write(json_str)

    log(f"🎉 凭据已成功持久化至: {SECRET_FILE} (大小: {len(json_str.encode('utf-8'))} 字节)")
    return json_str

def wait_for_chat_ready(page, max_retries=20):
    log("⏳ 正在等待抖音聊天页面加载与会话列表渲染...")
    for attempt in range(1, max_retries + 1):
        if "login" in page.url.lower() or page.query_selector("div[class*='login'], div:has-text('扫码登录')"):
            return False, "login_required"

        has_cards = page.evaluate("""() => {
            const divs = Array.from(document.querySelectorAll("div"));
            for (const d of divs) {
                const rect = d.getBoundingClientRect();
                if (rect.left >= 0 && rect.left < 50 && rect.right > 200 && rect.right <= 350 && rect.height >= 45 && rect.height <= 95 && rect.top >= 40) {
                    if (d.innerText.trim().length > 0) return true;
                }
            }
            return false;
        }""")

        if has_cards:
            log(f"✅ 会话列表渲染完毕 (耗时 ~{attempt * 1.5:.1f} 秒)")
            return True, "ready"

        page.wait_for_timeout(1500)

    return False, "timeout"

def find_target_card(page, target_name):
    clean_target = target_name.strip()
    
    # 尝试当前视图查找
    for scroll_idx in range(4):
        card_info = page.evaluate("""(target) => {
            const divs = Array.from(document.querySelectorAll("div"));
            const candidates = [];
            for (const d of divs) {
                const rect = d.getBoundingClientRect();
                if (rect.left >= 0 && rect.left < 50 && rect.right > 200 && rect.right <= 350 && rect.height >= 45 && rect.height <= 95 && rect.top >= 40) {
                    const text = d.innerText.trim();
                    const firstLine = text.split('\\n')[0].trim();
                    if (firstLine) {
                        candidates.push({
                            name: firstLine,
                            x: rect.x + rect.width / 2,
                            y: rect.y + rect.height / 2,
                            text: text
                        });
                    }
                }
            }

            // 1. 完全精确匹配
            for (const c of candidates) {
                if (c.name === target) {
                    return { x: c.x, y: c.y, name: c.name, match: 'exact' };
                }
            }

            // 2. 包含匹配（处理带 emoji 或标签，如 好友2 -> 好友2🏸）
            for (const c of candidates) {
                if (c.name.includes(target) || target.includes(c.name)) {
                    return { x: c.x, y: c.y, name: c.name, match: 'contains' };
                }
            }

            return null;
        }""", clean_target)

        if card_info:
            return card_info

        # 如果未找到，向下滑动左侧列表查找
        if scroll_idx < 3:
            page.mouse.move(150, 300)
            page.mouse.wheel(0, 350)
            page.wait_for_timeout(1000)

    return None

def execute_spark_send(config, is_actions=False):
    targets = config.get("targets", [])
    message = config.get("message", "续火花").strip()
    headless = True if is_actions else config.get("headless", False)
    storage_state = config.get("storage_state", None)
    cookies = config.get("cookies", [])

    if not targets:
        log("❌ 错误: 未配置任何目标 (targets 为空)！")
        return False

    mode_name = "GitHub Actions" if is_actions else "本地"
    log(f"=== [{mode_name}] 开始执行抖音自动续火花 (共 {len(targets)} 个目标) ===")

    success_count = 0
    fail_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
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

        context = browser.new_context(**context_kwargs)

        if cookies and not storage_state:
            context.add_cookies(cookies)

        page = context.new_page()

        # 反爬注入
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        """)

        try:
            log("🌐 正在导航至抖音消息页面...")
            page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded", timeout=60000)
            
            ready, status = wait_for_chat_ready(page)
            if not ready:
                err_shot = os.path.join(SCREENSHOTS_DIR, "login_failed.png")
                page.screenshot(path=err_shot)
                if status == "login_required":
                    log("❌ Cookie 凭证失效或需要扫码登录！请运行 `python get_cookies.py` 重新生成凭据并更新 GitHub Secret！")
                else:
                    log(f"❌ 页面加载超时或会话列表未渲染 (已截图保存至 {err_shot})")
                browser.close()
                return False

            log("✅ 登录凭据有效，进入消息主面板！")
            page.wait_for_timeout(2000)

            for idx, target in enumerate(targets, 1):
                target_name = target.strip()
                if not target_name:
                    continue

                log(f"\n👉 [{idx}/{len(targets)}] 正在定位目标: 【{target_name}】...")

                # 1. 查找并点击会话卡片
                card = find_target_card(page, target_name)
                if not card:
                    log(f"⚠️ 聊天列表中未检索到【{target_name}】，跳过此目标。")
                    fail_count += 1
                    continue

                log(f"🎯 命中会话卡片: 【{card['name']}】 (匹配模式: {card['match']})，正在点击进入...")
                page.mouse.click(card["x"], card["y"])
                page.wait_for_timeout(1500)

                # 2. 定位输入框
                input_box = page.query_selector(
                    "div.zone-container, div[class*='messageEditorinputArea'], div[class*='editor-kit-container'], div[class*='messageEditorimChatEditorContainer'], div[contenteditable='true'], textarea"
                )

                if not input_box:
                    log(f"❌ 未能定位到【{target_name}】的聊天输入框！")
                    fail_count += 1
                    continue

                # 3. 聚焦并输入消息
                input_box.click()
                page.wait_for_timeout(300)

                log(f"💬 正在向【{target_name}】键入消息: \"{message}\"")
                for char in message:
                    page.keyboard.type(char)
                    time.sleep(random.uniform(0.04, 0.09))

                page.wait_for_timeout(300)

                # 4. 回车发送
                page.keyboard.press("Enter")
                page.wait_for_timeout(800)

                # 截图留存（GitHub Actions 可作为 Artifact 查看）
                safe_name = "".join(c for c in target_name if c.isalnum() or c in ("_", "-")) or f"target_{idx}"
                shot_path = os.path.join(SCREENSHOTS_DIR, f"{safe_name}.png")
                page.screenshot(path=shot_path)
                log(f"🎉 成功向【{target_name}】发送续火花消息！(截图已记录: {safe_name}.png)")

                success_count += 1

                # 随机停顿，平稳发送下一个
                time.sleep(random.uniform(2.0, 3.5))

            log(f"\n=== 续火花任务执行总结: 成功 {success_count} 个, 失败/跳过 {fail_count} 个 ===")
            browser.close()
            return success_count > 0

        except Exception as e:
            err_shot = os.path.join(SCREENSHOTS_DIR, "exception.png")
            try:
                page.screenshot(path=err_shot)
            except Exception:
                pass
            log(f"❌ 执行过程发生异常: {e} (已保存截图: {err_shot})")
            browser.close()
            return False

def run_login():
    log("=== 正在启动本地浏览器进行抖音扫码登录 ===")
    log("提示：请在弹出的浏览器窗口中使用手机抖音 App 扫描二维码。")
    log("登录成功进入聊天界面后，返回此终端按【回车键 (Enter)】完成保存！\n")

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

        input("👉 请完成扫码登录，并在进入聊天界面后在此处按【回车键 (Enter)】以保存凭据...")

        storage_state = context.storage_state()
        cookies = context.cookies()

        save_secret_config(storage_state, cookies=cookies)
        browser.close()
        log("✅ 登录凭据配置已保存！")

def list_chats():
    config = load_config()
    storage_state = config.get("storage_state")
    if not storage_state:
        log("❌ 未检测到登录凭据，请先运行 `python douyin_spark.py --login` 扫码登录！")
        return

    log("=== 正在扫描当前账号的会话列表... ===")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=storage_state,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded")
        ready, _ = wait_for_chat_ready(page)
        if not ready:
            log("❌ 会话列表加载失败或登录凭证已过期")
            browser.close()
            return

        chat_names = page.evaluate("""() => {
            const divs = Array.from(document.querySelectorAll("div"));
            const names = [];
            for (const d of divs) {
                const rect = d.getBoundingClientRect();
                if (rect.left >= 0 && rect.left < 50 && rect.right > 200 && rect.right <= 350 && rect.height >= 45 && rect.height <= 95 && rect.top >= 40) {
                    const text = d.innerText.trim();
                    const firstLine = text.split('\\n')[0].trim();
                    if (firstLine && !names.includes(firstLine)) {
                        names.push(firstLine);
                    }
                }
            }
            return names;
        }""")

        log(f"\n📋 检索到 {len(chat_names)} 个会话目标:")
        log("----------------------------------------")
        for i, name in enumerate(chat_names, 1):
            log(f"  {i}. {name}")
        log("----------------------------------------\n")
        browser.close()

def start_scheduler():
    import schedule
    config = load_config()
    send_time = config.get("send_time", "08:30")
    log(f"=== 已启动本地定时挂机服务 ===")
    log(f"⏰ 每日自动发送时间: {send_time}")
    log("提示：保持本终端运行即可，按 Ctrl+C 退出。\n")

    schedule.every().day.at(send_time).do(lambda: execute_spark_send(load_config()))

    while True:
        schedule.run_pending()
        time.sleep(30)

def main():
    parser = argparse.ArgumentParser(description="抖音自动续火花脚本 (本地 & GitHub Actions 通用)")
    parser.add_argument("--send", action="store_true", help="立即执行一次续火花任务")
    parser.add_argument("--actions", action="store_true", help="以 GitHub Actions 模式执行")
    parser.add_argument("--login", action="store_true", help="打开浏览器扫码登录以获取凭据")
    parser.add_argument("--list", action="store_true", help="列出当前所有会话列表")
    parser.add_argument("--schedule", action="store_true", help="启动本地定时任务")

    args = parser.parse_args()

    if args.login:
        run_login()
    elif args.actions:
        cfg = load_config(is_actions=True)
        success = execute_spark_send(cfg, is_actions=True)
        sys.exit(0 if success else 1)
    elif args.send:
        cfg = load_config()
        execute_spark_send(cfg, is_actions=False)
    elif args.list:
        list_chats()
    elif args.schedule:
        start_scheduler()
    else:
        cfg = load_config()
        execute_spark_send(cfg, is_actions=False)

if __name__ == "__main__":
    main()

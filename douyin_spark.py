import os
import sys
import json
import time
import random
import datetime
import argparse
import subprocess
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

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

    # 2. 本地模式：优先读取 config.json 的业务配置 (targets, message, messages, send_time, headless)
    local_cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                local_cfg = json.load(f)
        except Exception as e:
            log(f"⚠️ 读取 config.json 失败: {e}")

    # 3. 读取 config_secret.json 中的凭证数据 (storage_state, cookies) 及兜底配置
    secret_cfg = {}
    if os.path.exists(SECRET_FILE):
        try:
            with open(SECRET_FILE, "r", encoding="utf-8") as sf:
                secret_cfg = json.load(sf)
                log("✅ 已从本地 config_secret.json 加载凭证配置")
        except Exception as e:
            log(f"⚠️ 读取 config_secret.json 失败: {e}")

    # 合并凭证
    cfg["storage_state"] = secret_cfg.get("storage_state")
    cfg["cookies"] = secret_cfg.get("cookies", [])

    # targets 优先取 config.json，其次 secret_cfg
    if "targets" in local_cfg and local_cfg["targets"]:
        cfg["targets"] = local_cfg["targets"]
    elif "targets" in secret_cfg and secret_cfg["targets"]:
        cfg["targets"] = secret_cfg["targets"]
    else:
        cfg["targets"] = []

    # message 优先取 config.json，其次 secret_cfg，最后默认 "续火花"
    if "message" in local_cfg and local_cfg["message"]:
        cfg["message"] = local_cfg["message"]
    elif "message" in secret_cfg and secret_cfg["message"]:
        cfg["message"] = secret_cfg["message"]
    else:
        cfg["message"] = "续火花"

    # messages (随机文案池)
    if "messages" in local_cfg and local_cfg["messages"]:
        cfg["messages"] = local_cfg["messages"]
    elif "messages" in secret_cfg and secret_cfg["messages"]:
        cfg["messages"] = secret_cfg["messages"]

    # send_time & headless
    cfg["send_time"] = local_cfg.get("send_time", secret_cfg.get("send_time", "08:30"))
    cfg["headless"] = local_cfg.get("headless", secret_cfg.get("headless", False))

    if not os.path.exists(CONFIG_FILE):
        save_base_config(
            targets=cfg.get("targets", []),
            message=cfg.get("message", "续火花"),
            send_time=cfg.get("send_time", "08:30"),
            headless=cfg.get("headless", False),
            messages=cfg.get("messages")
        )

    return cfg

def save_base_config(targets, message, send_time="08:30", headless=False, messages=None):
    base_data = {
        "targets": targets,
        "message": message,
        "send_time": send_time,
        "headless": headless
    }
    if messages:
        base_data["messages"] = messages

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(base_data, f, ensure_ascii=False, indent=2)
    log(f"💾 基础配置已保存至: {CONFIG_FILE}")

def save_secret_config(storage_state, targets=None, message=None, messages=None, cookies=None):
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
    if messages is not None:
        secret_data["messages"] = messages
    elif "messages" in current_cfg:
        secret_data["messages"] = current_cfg["messages"]

    if cookies is not None:
        secret_data["cookies"] = cookies

    compact_json = json.dumps(secret_data, ensure_ascii=False, separators=(',', ':'))
    with open(SECRET_FILE, "w", encoding="utf-8") as f:
        f.write(compact_json)

    log(f"🎉 凭据已成功持久化至: {SECRET_FILE} (大小: {len(compact_json.encode('utf-8'))} 字节)")

    # 自动尝试同步 GitHub Secrets
    sync_to_github_secret(compact_json)
    return compact_json

def sync_to_github_secret(compact_json):
    try:
        res = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        if res.returncode == 0:
            log("🚀 检测到 GitHub CLI (gh) 已登录，正在自动同步 Secret 到 GitHub 仓库...")
            sync_res = subprocess.run(
                ["gh", "secret", "set", "DOUYIN_CONFIG", "-b", compact_json],
                capture_output=True,
                text=True
            )
            if sync_res.returncode == 0:
                log("🎉 成功自动将 DOUYIN_CONFIG Secret 同步至 GitHub 仓库！")
            else:
                log(f"⚠️ 自动同步 Secret 提示: {sync_res.stderr.strip() or sync_res.stdout.strip()}")
        else:
            log("ℹ️ 未检测到 gh CLI 登录，若使用 GitHub Actions 可手动将 config_secret.json 内容粘贴至 GitHub Secrets。")
    except Exception:
        pass

def wait_for_chat_ready(page, max_retries=20):
    log("⏳ 正在等待抖音聊天页面加载与会话列表渲染...")
    for attempt in range(1, max_retries + 1):
        if "login" in page.url.lower() or page.query_selector("div[class*='login'], div:has-text('扫码登录')"):
            return False, "login_required"

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
            log(f"✅ 会话列表渲染完毕 (耗时 ~{attempt * 1.5:.1f} 秒)")
            return True, "ready"

        page.wait_for_timeout(1500)

    return False, "timeout"

def fetch_all_chats(page, max_scrolls=15):
    log("🔍 正在扫描左侧会话列表以获取所有好友与群聊...")
    chat_candidates = {}
    no_new_count = 0
    last_count = 0

    for scroll_idx in range(max_scrolls):
        cards = page.evaluate("""() => {
            const divs = Array.from(document.querySelectorAll("div"));
            const items = [];
            for (const d of divs) {
                const rect = d.getBoundingClientRect();
                if (rect.left >= 0 && rect.left < 60 && rect.right > 180 && rect.right <= 400 && rect.height >= 40 && rect.height <= 100 && rect.top >= 40) {
                    const text = d.innerText.trim();
                    if (!text) continue;
                    const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);
                    if (lines.length > 0) {
                        const name = lines[0];
                        const preview = lines.length > 1 ? lines[1] : "";
                        items.push({ name, preview });
                    }
                }
            }
            return items;
        }""")

        for card in cards:
            name = card["name"]
            if name and name not in chat_candidates:
                chat_candidates[name] = card.get("preview", "")

        current_count = len(chat_candidates)
        if current_count == last_count:
            no_new_count += 1
            if no_new_count >= 2:
                break
        else:
            no_new_count = 0
            last_count = current_count

        page.mouse.move(150, 300)
        page.mouse.wheel(0, 450)
        page.wait_for_timeout(600)

    # 滚回顶部
    page.mouse.wheel(0, -10000)
    page.wait_for_timeout(400)

    results = [{"name": k, "preview": v} for k, v in chat_candidates.items()]
    log(f"📋 共扫描到 {len(results)} 个会话目标。")
    return results

def find_target_card(page, target_name):
    clean_target = target_name.strip()
    
    # 尝试当前视图查找及向下滚动查找
    for scroll_idx in range(6):
        card_info = page.evaluate("""(target) => {
            const divs = Array.from(document.querySelectorAll("div"));
            const candidates = [];
            for (const d of divs) {
                const rect = d.getBoundingClientRect();
                if (rect.left >= 0 && rect.left < 60 && rect.right > 180 && rect.right <= 400 && rect.height >= 40 && rect.height <= 100 && rect.top >= 40) {
                    const text = d.innerText.trim();
                    const lines = text.split('\\n').map(s => s.trim()).filter(Boolean);
                    if (lines.length > 0) {
                        candidates.push({
                            name: lines[0],
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

            // 2. 包含匹配（处理带 emoji 或标签，如 好友昵称 -> 好友昵称🏸）
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
        if scroll_idx < 5:
            page.mouse.move(150, 300)
            page.mouse.wheel(0, 350)
            page.wait_for_timeout(800)

    return None

def generate_spark_text(target_name, target_custom_msg=None, default_message="续火花", message_pool=None):
    if target_custom_msg:
        template = target_custom_msg
    elif message_pool and isinstance(message_pool, list) and len(message_pool) > 0:
        template = random.choice(message_pool)
    elif isinstance(default_message, list) and len(default_message) > 0:
        template = random.choice(default_message)
    elif default_message:
        template = default_message
    else:
        template = "续火花"

    hour = datetime.datetime.now().hour
    if 5 <= hour < 11:
        greeting = "早安"
    elif 11 <= hour < 14:
        greeting = "午安"
    elif 14 <= hour < 19:
        greeting = "下午好"
    else:
        greeting = "晚上好"

    now = datetime.datetime.now()
    text = str(template)
    text = text.replace("{name}", target_name)
    text = text.replace("{date}", now.strftime("%m月%d日"))
    text = text.replace("{time}", now.strftime("%H:%M"))
    text = text.replace("{greeting}", greeting)
    return text

def parse_selection_indices(input_str, total_count):
    input_str = input_str.strip().lower()
    if not input_str:
        return None
    if input_str in ("all", "全选", "a"):
        return list(range(total_count))
    if input_str in ("none", "清空", "0"):
        return []

    selected = set()
    cleaned = input_str.replace("，", ",").replace("、", ",").replace(" ", ",")
    parts = [p.strip() for p in cleaned.split(",") if p.strip()]

    for part in parts:
        if "-" in part or "~" in part:
            sep = "-" if "-" in part else "~"
            subparts = part.split(sep)
            if len(subparts) == 2 and subparts[0].isdigit() and subparts[1].isdigit():
                start = int(subparts[0])
                end = int(subparts[1])
                for idx in range(min(start, end), max(start, end) + 1):
                    if 1 <= idx <= total_count:
                        selected.add(idx - 1)
        elif part.isdigit():
            idx = int(part)
            if 1 <= idx <= total_count:
                selected.add(idx - 1)

    return sorted(list(selected))

def interactive_target_and_message_wizard(scanned_chats, current_cfg=None):
    if current_cfg is None:
        current_cfg = {}

    current_targets = current_cfg.get("targets", [])
    current_target_names = [t.get("name", "") if isinstance(t, dict) else str(t) for t in current_targets]
    target_custom_map = {t["name"]: t.get("message") for t in current_targets if isinstance(t, dict)}
    
    current_message = current_cfg.get("message", "续火花")
    current_messages = current_cfg.get("messages", None)

    print("\n" + "=" * 68)
    print(f"       📋 抖音会话好友/群聊列表 (共扫描到 {len(scanned_chats)} 个目标)")
    print("=" * 68)

    scanned_names = []
    for i, chat in enumerate(scanned_chats, 1):
        name = chat["name"]
        scanned_names.append(name)
        preview = f" (最新: \"{chat['preview']}\")" if chat.get("preview") else ""
        
        is_selected = False
        for cur in current_target_names:
            if cur == name or (cur and (cur in name or name in cur)):
                is_selected = True
                break
        
        tag = "[✅ 已选]" if is_selected else "[      ]"
        print(f"  {i:2d}. {tag} {name}{preview}")

    print("=" * 68)
    print("💡 选择提示:")
    print("  • 输入序号多选，例如: 1, 2, 5 或 1-4, 7")
    print("  • 输入 all 或 全选 选择扫描到的全部目标")
    print("  • 输入 none 或 清空 清空所有选择")
    print(f"  • 直接按【Enter 回车键】保持当前已选配置 ({len(current_target_names)} 个目标)")
    print("-" * 68)

    while True:
        user_sel = input("👉 请输入序号选择续火花目标: ").strip()
        parsed_indices = parse_selection_indices(user_sel, len(scanned_names))
        if parsed_indices is None:
            selected_names = current_target_names.copy()
            break
        else:
            selected_names = [scanned_names[idx] for idx in parsed_indices]
            break

    print("-" * 68)
    extra_input = input("➕ 是否需要手动追加其他好友昵称？(多个用逗号隔开，直接回车跳过): ").strip()
    if extra_input:
        cleaned_extra = extra_input.replace("，", ",").replace("、", ",")
        for item in cleaned_extra.split(","):
            name = item.strip()
            if name and name not in selected_names:
                selected_names.append(name)

    print(f"\n✅ 当前已选择 {len(selected_names)} 个续火花目标: {', '.join(selected_names) if selected_names else '(无)'}\n")

    final_targets = []
    for name in selected_names:
        if name in target_custom_map and target_custom_map[name]:
            final_targets.append({"name": name, "message": target_custom_map[name]})
        else:
            final_targets.append(name)

    # 步骤二：自定义续火花文字
    print("=" * 68)
    print("                    💬 自定义续火花发送文案")
    print("=" * 68)
    if current_messages:
        curr_msg_display = f"随机文案池 ({len(current_messages)} 条: {', '.join(current_messages)})"
    else:
        curr_msg_display = f"\"{current_message}\""
    print(f"当前配置文案: {curr_msg_display}")
    print("支持动态变量: {greeting}=时段问候(早安/午安/晚上好), {name}=对方昵称, {date}=日期, {time}=时间\n")

    print("请选择续火花文案模式:")
    print(f"  [1] 保持当前配置 ({curr_msg_display})")
    print("  [2] 经典火花: \"续火花 🔥\"")
    print("  [3] 精简火花: \"🔥\"")
    print("  [4] 趣味打卡: \"滴滴，今日续火花打卡✨\"")
    print("  [5] 智能问候: \"{greeting}！今天也要续火花呀🔥\"")
    print("  [6] 推荐随机文案池 (更真实自然，每次随机挑选一条):")
    print("      [\"续火花 🔥\", \"🔥\", \"滴滴续火花~\", \"今日火花打卡✨\", \"{greeting}，续火花啦☀️\"]")
    print("  [7] 自定义输入单个文案")
    print("  [8] 自定义输入多条随机文案池 (用逗号或分号分隔)")
    print("-" * 68)

    final_message = current_message
    final_messages = current_messages

    choice = input("👉 请输入选项 (1-8) 或直接输入自定义文案 (回车默认[1]): ").strip()

    if not choice or choice == "1":
        pass
    elif choice == "2":
        final_message = "续火花 🔥"
        final_messages = None
    elif choice == "3":
        final_message = "🔥"
        final_messages = None
    elif choice == "4":
        final_message = "滴滴，今日续火花打卡✨"
        final_messages = None
    elif choice == "5":
        final_message = "{greeting}！今天也要续火花呀🔥"
        final_messages = None
    elif choice == "6":
        final_message = "续火花 🔥"
        final_messages = ["续火花 🔥", "🔥", "滴滴续火花~", "今日火花打卡✨", "{greeting}，续火花啦☀️"]
    elif choice == "7":
        custom_txt = input("请输入自定义文案 (可包含 {name} / {greeting} / {date} / {time}): ").strip()
        if custom_txt:
            final_message = custom_txt
            final_messages = None
    elif choice == "8":
        custom_pool_input = input("请输入多条文案 (用逗号或分号分隔): ").strip()
        if custom_pool_input:
            pool = [p.strip() for p in custom_pool_input.replace("；", ";").replace("，", ",").replace(";", ",").split(",") if p.strip()]
            if pool:
                final_messages = pool
                final_message = pool[0]
    else:
        final_message = choice
        final_messages = None

    print("\n" + "=" * 68)
    print("                      🎉 配置更新完成")
    print("=" * 68)
    print(f"🎯 选中的续火花目标 ({len(final_targets)} 个): {json.dumps(final_targets, ensure_ascii=False)}")
    if final_messages:
        print(f"💬 随机文案池 ({len(final_messages)} 条): {json.dumps(final_messages, ensure_ascii=False)}")
    else:
        print(f"💬 续火花文案: \"{final_message}\"")
    print("=" * 68 + "\n")

    return final_targets, final_message, final_messages

def execute_spark_send(config, is_actions=False):
    raw_targets = config.get("targets", [])
    default_message = config.get("message", "续火花")
    message_pool = config.get("messages", None)
    headless = True if is_actions else config.get("headless", False)
    storage_state = config.get("storage_state", None)
    cookies = config.get("cookies", [])

    if not raw_targets:
        log("❌ 错误: 未配置任何目标 (targets 为空)！请先运行 `python douyin_spark.py --config` 选择目标。")
        return False

    targets = []
    for item in raw_targets:
        if isinstance(item, dict):
            name = item.get("name", "").strip()
            if name:
                targets.append({"name": name, "message": item.get("message")})
        elif isinstance(item, str) and item.strip():
            targets.append({"name": item.strip(), "message": None})

    if not targets:
        log("❌ 错误: 配置的目标列表有效项为空！")
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
                try:
                    page.screenshot(path=err_shot)
                except Exception:
                    pass
                if status == "login_required":
                    log("❌ Cookie 凭证失效或需要扫码登录！请运行 `python get_cookies.py` 或 `python douyin_spark.py --login` 重新生成凭据！")
                else:
                    log(f"❌ 页面加载超时或会话列表未渲染 (已截图保存至 {err_shot})")
                browser.close()
                return False

            log("✅ 登录凭据有效，进入消息主面板！")
            page.wait_for_timeout(2000)

            for idx, target_item in enumerate(targets, 1):
                target_name = target_item["name"]
                custom_msg = target_item.get("message")
                send_text = generate_spark_text(target_name, custom_msg, default_message, message_pool)

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

                log(f"💬 正在向【{target_name}】键入消息: \"{send_text}\"")
                for char in send_text:
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

def run_config_wizard():
    print("==================================================")
    print("        抖音自动续火花 - 目标选择与文案配置向导        ")
    print("==================================================")
    cfg = load_config()
    storage_state = cfg.get("storage_state")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context_kwargs = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1280, "height": 800}
        }
        if storage_state:
            context_kwargs["storage_state"] = storage_state

        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        page.goto("https://www.douyin.com/chat", wait_until="domcontentloaded")

        ready, status = wait_for_chat_ready(page, max_retries=6)
        if not ready or status == "login_required":
            print("\n⚠️ 当前未登录或登录凭据已失效，请在弹出的浏览器中扫码登录...")
            input("👉 扫码登录成功进入聊天界面后，在此处按【Enter 回车键】继续...")
            storage_state = context.storage_state()
            ready, _ = wait_for_chat_ready(page, max_retries=10)

        if not ready:
            print("❌ 无法加载会话界面，请检查网络或重新扫码登录。")
            browser.close()
            return

        # 扫描全部会话
        scanned_chats = fetch_all_chats(page)
        if not scanned_chats:
            print("⚠️ 未扫描到任何会话，请确保抖音消息面板中有联系人。")
            browser.close()
            return

        # 运行交互式选择与文案配置
        new_targets, new_message, new_messages = interactive_target_and_message_wizard(scanned_chats, cfg)

        # 获取最新 storage_state 与 cookies
        storage_state = context.storage_state()
        cookies = context.cookies()

        # 保存到 config.json 与 config_secret.json
        save_base_config(
            targets=new_targets,
            message=new_message,
            send_time=cfg.get("send_time", "08:30"),
            headless=cfg.get("headless", False),
            messages=new_messages
        )
        save_secret_config(
            storage_state=storage_state,
            targets=new_targets,
            message=new_message,
            messages=new_messages,
            cookies=cookies
        )

        browser.close()
        print("🎉 配置保存完毕！本地运行与 GitHub Actions 均已更新。")

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

        scanned = fetch_all_chats(page)
        current_cfg = load_config()
        targets, msg, msgs = interactive_target_and_message_wizard(scanned, current_cfg)

        save_base_config(targets=targets, message=msg, messages=msgs)
        save_secret_config(storage_state=storage_state, targets=targets, message=msg, messages=msgs, cookies=cookies)
        browser.close()
        log("✅ 登录凭据与续火花配置已全部保存！")

def list_chats():
    config = load_config()
    storage_state = config.get("storage_state")
    if not storage_state:
        log("❌ 未检测到登录凭据，请先运行 `python douyin_spark.py --login` 扫码登录！")
        return

    log("=== 正在扫描当前账号的全部会话列表... ===")
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
            log("❌ 会话列表加载失败或登录凭证已过期，请重新登录。")
            browser.close()
            return

        all_chats = fetch_all_chats(page)
        cur_targets = config.get("targets", [])
        cur_names = [t.get("name") if isinstance(t, dict) else str(t) for t in cur_targets]

        print("\n" + "=" * 60)
        print(f"📋 检索到 {len(all_chats)} 个会话好友/群聊:")
        print("=" * 60)
        for i, chat in enumerate(all_chats, 1):
            name = chat["name"]
            is_target = any(cur == name or (cur and (cur in name or name in cur)) for cur in cur_names)
            tag = "[✅ 续火花目标]" if is_target else "[             ]"
            preview = f" (最新: \"{chat['preview']}\")" if chat.get("preview") else ""
            print(f"  {i:2d}. {tag} {name}{preview}")
        print("=" * 60)
        print("💡 提示: 运行 `python douyin_spark.py --config` 可交互式选择目标与设置自定义文案。\n")
        browser.close()

def sync_config_only():
    log("=== 正在同步本地 config.json 到 config_secret.json 与 GitHub Secrets ===")
    cfg = load_config()
    storage_state = cfg.get("storage_state")
    if not storage_state:
        log("❌ 未找到 storage_state 凭据，请先扫码登录！")
        return
    save_secret_config(
        storage_state=storage_state,
        targets=cfg.get("targets", []),
        message=cfg.get("message", "续火花"),
        messages=cfg.get("messages"),
        cookies=cfg.get("cookies", [])
    )
    log("✅ 本地配置与凭证同步完成！")

def start_scheduler():
    import schedule
    config = load_config()
    send_time = config.get("send_time", "08:30")
    log("=== 已启动本地定时挂机服务 ===")
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
    parser.add_argument("--config", "--select", action="store_true", help="扫描会话并交互式选择续火花目标与自定义文案")
    parser.add_argument("--gui", action="store_true", help="启动 Douyin Streak Setup 桌面原生图形界面向导")
    parser.add_argument("--web", action="store_true", help="启动 Douyin Streak Setup 网页一键部署向导")
    parser.add_argument("--login", action="store_true", help="打开浏览器扫码登录以获取凭据")
    parser.add_argument("--list", action="store_true", help="列出当前所有会话列表")
    parser.add_argument("--sync", action="store_true", help="将 config.json 的设置同步至 config_secret.json 并同步至 GitHub")
    parser.add_argument("--schedule", action="store_true", help="启动本地定时任务")

    args = parser.parse_args()

    if args.gui:
        import setup.main
        setup.main.main()
    elif args.web:
        import web_setup
        web_setup.run_server()
    elif args.config:
        run_config_wizard()
    elif args.login:
        run_login()
    elif args.sync:
        sync_config_only()
    elif args.actions:
        import runner.main
        runner.main.main()
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

import time
import random
import os
from typing import Optional
from douyin.provider import SendResult

def find_target_element(page, target_name: str):
    clean_target = target_name.strip()
    
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

            // 2. 包含匹配 (支持 Emoji / 标签扩展)
            for (const c of candidates) {
                if (c.name.includes(target) || target.includes(c.name)) {
                    return { x: c.x, y: c.y, name: c.name, match: 'contains' };
                }
            }

            return null;
        }""", clean_target)

        if card_info:
            return card_info

        if scroll_idx < 5:
            page.mouse.move(150, 300)
            page.mouse.wheel(0, 350)
            page.wait_for_timeout(700)

    return None

def send_message_to_conversation(
    page,
    target_id: str,
    message: str,
    dry_run: bool = False,
    screenshots_dir: Optional[str] = None
) -> SendResult:
    """
    单会话节流发送消息或预检
    """
    card = find_target_element(page, target_id)
    if not card:
        return SendResult(ok=False, conversation_id=target_id, error="未在会话列表中检索到该目标")

    # 点击进入会话
    page.mouse.click(card["x"], card["y"])
    page.wait_for_timeout(1200)

    # 寻找输入框
    input_box = page.query_selector(
        "div.zone-container, div[class*='messageEditorinputArea'], div[class*='editor-kit-container'], div[class*='messageEditorimChatEditorContainer'], div[contenteditable='true'], textarea"
    )
    if not input_box:
        return SendResult(ok=False, conversation_id=target_id, error="未定位到聊天输入框")

    if dry_run:
        # TEST_MODE 只验证页面可访问性与输入框定位能力，不发送
        return SendResult(ok=True, conversation_id=target_id, message="[TEST_MODE] 页面与输入框验证通过，未发送实际消息")

    input_box.click()
    page.wait_for_timeout(300)

    # 真人打字延迟
    for char in message:
        page.keyboard.type(char)
        time.sleep(random.uniform(0.04, 0.08))

    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    page.wait_for_timeout(800)

    # 保存截图
    if screenshots_dir:
        os.makedirs(screenshots_dir, exist_ok=True)
        safe_name = "".join(c for c in target_id if c.isalnum() or c in ("_", "-")) or "target"
        shot_path = os.path.join(screenshots_dir, f"{safe_name}.png")
        try:
            page.screenshot(path=shot_path)
        except Exception:
            pass

    # 发送间随机等待 (节流防竞争)
    time.sleep(random.uniform(2.0, 3.5))
    return SendResult(ok=True, conversation_id=target_id, message=message)

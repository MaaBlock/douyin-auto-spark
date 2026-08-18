import re
from typing import List, Dict, Any, Set
from config.model import Conversation

def extract_conversations_from_dom(page, max_scrolls: int = 15) -> List[Conversation]:
    """
    通过滑动左侧边栏并结构化解析会话列表，提取私聊、群聊与火花状态
    """
    results: List[Conversation] = []
    seen_ids: Set[str] = set()
    no_new_count = 0
    last_count = 0

    for scroll_idx in range(max_scrolls):
        cards_raw = page.evaluate("""() => {
            const divs = Array.from(document.querySelectorAll("div"));
            const items = [];
            for (const d of divs) {
                const rect = d.getBoundingClientRect();
                if (rect.left >= 0 && rect.left < 60 && rect.right > 180 && rect.right <= 400 && rect.height >= 40 && rect.height <= 100 && rect.top >= 40) {
                    const fullText = d.innerText.trim();
                    if (!fullText) continue;
                    const lines = fullText.split('\\n').map(s => s.trim()).filter(Boolean);
                    if (lines.length > 0) {
                        const title = lines[0];
                        const preview = lines.length > 1 ? lines[1] : "";
                        // 判断是否包含群聊特征
                        const isGroup = title.includes("群聊") || /\\(\\d+人?\\)/.test(title) || /\\d+人$/.test(title);
                        
                        // 判断火花标识
                        let streakValue = null;
                        const match = fullText.match(/🔥\\s*(\\d+)/);
                        if (match) {
                            streakValue = parseInt(match[1], 10);
                        } else if (fullText.includes("🔥") || fullText.includes("火花")) {
                            streakValue = 1;
                        }

                        items.push({
                            title: title,
                            preview: preview,
                            isGroup: isGroup,
                            streakValue: streakValue,
                            fullText: fullText
                        });
                    }
                }
            }
            return items;
        }""")

        for card in cards_raw:
            title = card["title"].strip()
            if not title:
                continue

            conv_id = title
            if conv_id in seen_ids:
                continue
            seen_ids.add(conv_id)

            is_group = card.get("isGroup", False)
            streak_val = card.get("streakValue")
            has_streak = streak_val is not None

            conv = Conversation(
                id=conv_id,
                type="group" if is_group else "private",
                displayName=title,
                preview=card.get("preview", ""),
                streak_enabled=has_streak,
                streak_value=streak_val
            )
            results.append(conv)

        current_count = len(results)
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
    page.wait_for_timeout(300)
    return results

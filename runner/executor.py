import os
import random
import datetime
from typing import Dict, Any, Optional

from config.model import StreakConfig
from config.sanitizer import safe_log
from douyin.playwright_provider import PlaywrightDouyinProvider

class StreakExecutor:
    def __init__(
        self,
        config: StreakConfig,
        session_data: Dict[str, Any],
        test_mode: bool = False,
        headless: bool = True,
        screenshots_dir: str = "screenshots",
        log_file: Optional[str] = "spark_log.txt"
    ):
        self.config = config
        self.session_data = session_data
        self.test_mode = test_mode
        self.headless = headless
        self.screenshots_dir = screenshots_dir
        self.log_file = log_file

    def _log(self, msg: str):
        safe_log(msg, self.log_file)

    def resolve_message_for_target(self, target_name: str) -> str:
        msg_cfg = self.config.messages
        if msg_cfg.mode == "fixed" and msg_cfg.values:
            template = msg_cfg.values[0]
        elif msg_cfg.values:
            template = random.choice(msg_cfg.values)
        else:
            template = "续火花🔥"

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

    def run(self) -> Dict[str, Any]:
        targets = self.config.targets
        if not targets:
            self._log("❌ CONFIG_INVALID: 未配置任何续火花目标！")
            return {"ok": False, "code": "CONFIG_INVALID", "error": "未配置目标"}

        self._log(f"=== {'[TEST_MODE] ' if self.test_mode else ''}开始执行火花任务 (共 {len(targets)} 个目标) ===")

        provider = PlaywrightDouyinProvider(
            headless=self.headless,
            screenshots_dir=self.screenshots_dir
        )

        try:
            self._log("⏳ 正在加载登录凭据并验证会话...")
            logged_in = provider.restore_session(self.session_data)
            if not logged_in:
                self._log("❌ LOGIN_EXPIRED: 登录状态已失效，请重新扫码登录！")
                provider.close()
                return {
                    "ok": False,
                    "code": "LOGIN_EXPIRED",
                    "error": "登录状态已失效，请重新打开 Douyin Streak Setup 扫码登录。"
                }

            self._log("✓ 登录状态正常")

            if self.test_mode:
                # 测试模式：只验证第一个已选目标的可访问性与输入框定位能力，不发送真实消息
                first_target = targets[0]
                test_msg = self.resolve_message_for_target(first_target.name or first_target.id)
                self._log(f"🔍 [TEST_MODE] 正在测试目标页面定位: 【{first_target.name or first_target.id}】...")
                res = provider.send_message(first_target.id, test_msg, dry_run=True)
                provider.close()

                if res.ok:
                    self._log(f"✓ GitHub Actions 运行正常")
                    self._log(f"✓ 登录状态正常")
                    self._log(f"✓ 发现 {len(targets)} 个任务对象")
                    self._log(f"✓ Runner 运行正常")
                    return {
                        "ok": True,
                        "code": "TEST_SUCCESS",
                        "targets_count": len(targets)
                    }
                else:
                    self._log(f"❌ 测试失败: {res.error}")
                    return {
                        "ok": False,
                        "code": "TEST_FAILED",
                        "error": res.error
                    }

            # 正常执行模式
            max_msgs = self.config.strategy.max_messages_per_run
            planned_targets = targets[:max_msgs]
            if len(targets) > max_msgs:
                self._log(f"⚠️ 目标数超过本次运行上限 ({max_msgs} 个)，本次将发送前 {max_msgs} 个")

            success_count = 0
            fail_count = 0

            for idx, target in enumerate(planned_targets, 1):
                target_display = target.name or target.id
                msg_to_send = self.resolve_message_for_target(target_display)
                self._log(f"\n👉 [{idx}/{len(planned_targets)}] 正在定位: 【{target_display}】({target.type})...")

                res = provider.send_message(target.id, msg_to_send, dry_run=False)
                if res.ok:
                    self._log(f"🎉 成功向【{target_display}】发送消息！")
                    success_count += 1
                else:
                    self._log(f"⚠️ 向【{target_display}】发送失败: {res.error}")
                    fail_count += 1

            self._log("\n========================================")
            self._log("任务执行总结:")
            self._log(f"  发现 {len(targets)} 个任务对象")
            self._log(f"  成功发送 {success_count} 个")
            self._log(f"  跳过/失败 {fail_count + max(0, len(targets) - len(planned_targets))} 个")
            self._log("========================================\n")

            provider.close()
            return {
                "ok": success_count > 0,
                "code": "SUCCESS" if success_count > 0 else "SEND_FAILED",
                "success_count": success_count,
                "fail_count": fail_count
            }

        except Exception as e:
            self._log(f"❌ 运行异常: {e}")
            provider.close()
            return {
                "ok": False,
                "code": "RUN_EXCEPTION",
                "error": str(e)
            }

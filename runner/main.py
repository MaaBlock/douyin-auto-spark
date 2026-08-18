import os
import sys
import json
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from config.model import StreakConfig
from config.sanitizer import safe_log
from douyin.session import deserialize_session
from runner.executor import StreakExecutor

def main():
    parser = argparse.ArgumentParser(description="Douyin Streak Runner")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--session", default=None, help="Path to session.json or raw session string")
    parser.add_argument("--test", action="store_true", help="Run in TEST_MODE (verification only, no messages sent)")
    parser.add_argument("--actions", action="store_true", help="Running in GitHub Actions environment")

    args = parser.parse_args()

    # 1. 检查 TEST_MODE (可通过参数或环境变量 TEST_MODE=1)
    test_mode = args.test or os.environ.get("TEST_MODE", "0").strip() in ("1", "true", "True")

    # 2. 加载 config.json
    config_path = args.config
    if not os.path.exists(config_path):
        # 兼容当前目录没有 config.json 时的 fallback
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")

    if not os.path.exists(config_path):
        safe_log(f"❌ CONFIG_INVALID: 找不到配置文件 {args.config}")
        sys.exit(1)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            config = StreakConfig.from_dict(config_data)
    except Exception as e:
        safe_log(f"❌ CONFIG_INVALID: 读取配置文件失败: {e}")
        sys.exit(1)

    # 3. 加载 Session 凭据 (优先从环境变量 DOUYIN_SESSION / DOUYIN_CONFIG 读取)
    session_data = {}
    env_session = os.environ.get("DOUYIN_SESSION", "").strip() or os.environ.get("DOUYIN_CONFIG", "").strip()
    if env_session:
        session_data = deserialize_session(env_session)

    if not session_data and args.session:
        if os.path.exists(args.session):
            with open(args.session, "r", encoding="utf-8") as sf:
                session_data = deserialize_session(sf.read())
        else:
            session_data = deserialize_session(args.session)

    if not session_data:
        # 尝试从本地 config_secret.json 读取兜底
        secret_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config_secret.json")
        if os.path.exists(secret_file):
            with open(secret_file, "r", encoding="utf-8") as sf:
                session_data = deserialize_session(sf.read())

    if not session_data:
        safe_log("❌ LOGIN_EXPIRED: 未检测到有效的 DOUYIN_SESSION 环境变量或凭据文件！")
        sys.exit(1)

    # 兼容处理：若环境变量或凭据中自带 targets/message 且 config 未配置，自动合并
    if ("targets" in session_data or "message" in session_data) and not config.targets:
        legacy_cfg = StreakConfig.from_dict(session_data)
        if legacy_cfg.targets:
            config.targets = legacy_cfg.targets
        if session_data.get("message"):
            config.messages.values = [session_data["message"]]

    # 4. 执行任务
    executor = StreakExecutor(
        config=config,
        session_data=session_data,
        test_mode=test_mode,
        headless=True if args.actions else True,
        screenshots_dir="screenshots"
    )

    result = executor.run()
    if not result.get("ok"):
        sys.exit(1)

if __name__ == "__main__":
    main()

import os
import sys
import json
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from github_service import GitHubService
from douyin_web_manager import DouyinWebSessionManager
from douyin_spark import (
    BASE_DIR,
    CONFIG_FILE,
    SECRET_FILE,
    save_base_config,
    save_secret_config,
    load_config
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

session_manager = DouyinWebSessionManager()

class SetupRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 简化请求日志
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            html_path = os.path.join(BASE_DIR, "web", "index.html")
            if os.path.exists(html_path):
                with open(html_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self._send_json({"error": "web/index.html not found"}, 404)
        elif path == "/api/douyin/status":
            self._send_json(session_manager.get_state())
        else:
            self._send_json({"error": "Endpoint not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            body = self._read_json()
        except Exception as e:
            self._send_json({"ok": False, "error": f"Invalid JSON payload: {e}"}, 400)
            return

        if path == "/api/github/login":
            token = body.get("token", "")
            gh = GitHubService(token)
            user_info = gh.get_user_info()
            self._send_json(user_info)

        elif path == "/api/github/star":
            token = body.get("token", "")
            gh = GitHubService(token)
            res = gh.star_upstream()
            self._send_json(res)

        elif path == "/api/github/create_repo":
            token = body.get("token", "")
            repo_name = body.get("repo_name", "douyin-auto-spark")
            gh = GitHubService(token)
            repo_res = gh.ensure_private_repo(repo_name)
            if not repo_res.get("ok"):
                self._send_json(repo_res, 400)
                return

            repo_full_name = repo_res["full_name"]

            if repo_res.get("from_template"):
                self._send_json({
                    "ok": True,
                    "repo": repo_res,
                    "deploy_files": {"ok": True}
                })
                return

            # 备用：读取需要上传的代码文件
            files_to_deploy = {}
            file_list = [
                "douyin_spark.py",
                "requirements.txt",
                "config.example.json",
                "README.md",
                os.path.join(".github", "workflows", "douyin_spark.yml")
            ]

            for rel_path in file_list:
                full_path = os.path.join(BASE_DIR, rel_path)
                if os.path.exists(full_path):
                    with open(full_path, "rb") as f:
                        # 转换成 posix 风格路径
                        posix_path = rel_path.replace("\\", "/")
                        files_to_deploy[posix_path] = f.read()

            deploy_res = gh.deploy_files(repo_full_name, files_to_deploy)
            self._send_json({
                "ok": True,
                "repo": repo_res,
                "deploy_files": deploy_res
            })

        elif path == "/api/douyin/start_login":
            res = session_manager.start_login()
            self._send_json(res)

        elif path == "/api/douyin/use_existing":
            res = session_manager.use_existing_config()
            self._send_json(res)

        elif path == "/api/deploy":
            token = body.get("token", "")
            repo_full_name = body.get("repo_full_name", "")
            targets = body.get("targets", [])
            message = body.get("message", "续火花 🔥")
            messages = body.get("messages", None)
            send_time = body.get("send_time", "08:30")
            trigger_now = body.get("trigger_now", True)

            # 获取当前凭证
            storage_state = session_manager.storage_state
            cookies = session_manager.cookies

            if not storage_state:
                # 尝试从本地 secret 文件读取兜底
                cfg = load_config()
                storage_state = cfg.get("storage_state")
                cookies = cfg.get("cookies", [])

            if not storage_state:
                self._send_json({"ok": False, "error": "未检测到有效的抖音登录凭据，请先完成扫码！"}, 400)
                return

            # 保存本地
            save_base_config(
                targets=targets,
                message=message,
                send_time=send_time,
                headless=False,
                messages=messages
            )
            secret_json = save_secret_config(
                storage_state=storage_state,
                targets=targets,
                message=message,
                messages=messages,
                cookies=cookies
            )

            # 上传并加密至 GitHub Secret
            gh = GitHubService(token)
            secret_res = gh.set_secret(repo_full_name, "DOUYIN_CONFIG", secret_json)
            if not secret_res.get("ok"):
                self._send_json(secret_res, 400)
                return

            # 触发 Actions 运行
            if trigger_now:
                gh.trigger_workflow(repo_full_name)

            repo_url = f"https://github.com/{repo_full_name}"
            actions_url = f"https://github.com/{repo_full_name}/actions"

            self._send_json({
                "ok": True,
                "repo_url": repo_url,
                "actions_url": actions_url,
                "targets_count": len(targets)
            })

        elif path == "/api/trigger_workflow":
            token = body.get("token", "")
            repo_full_name = body.get("repo_full_name", "")
            gh = GitHubService(token)
            res = gh.trigger_workflow(repo_full_name)
            self._send_json(res)

        else:
            self._send_json({"error": "Endpoint not found"}, 404)

def run_server(port=5000, open_browser=True):
    server = HTTPServer(("127.0.0.1", port), SetupRequestHandler)
    url = f"http://127.0.0.1:{port}"
    print("=" * 65)
    print("      🚀 Douyin Streak Setup - 抖音自动续火花一键部署向导")
    print("=" * 65)
    print(f"👉 网页向导服务已启动: {url}")
    print("提示: 请在打开的浏览器网页中按步骤完成一键云端部署。按 Ctrl+C 停止服务。\n")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 正在停止 Web 向导服务...")
        session_manager.stop()
        server.server_close()
        print("✅ 服务已关闭。")

if __name__ == "__main__":
    port = 5000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port=port, open_browser=True)

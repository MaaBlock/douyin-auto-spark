import time
import base64
import requests
from typing import List, Dict, Any, Optional, Callable

from config.model import StreakConfig, InstanceMeta
from github.client import GitHubClient
from github.secrets import write_github_secret

UPSTREAM_REPO = "MaaBlock/douyin-auto-spark"

def generate_workflow_yaml(cron_expr: str = "30 14 * * *") -> str:
    return f"""name: Douyin Streak Auto Renew

on:
  schedule:
    - cron: '{cron_expr}'
  workflow_dispatch:
    inputs:
      test_mode:
        description: 'Run in test mode (1: test only, 0: normal send)'
        required: false
        default: '0'

jobs:
  streak:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Instance Configuration
        uses: actions/checkout@v4

      - name: Clone Latest Official Runner
        run: |
          git clone --depth 1 https://github.com/{UPSTREAM_REPO}.git _runner

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r _runner/requirements.txt
          playwright install --with-deps chromium

      - name: Run Douyin Streak Task
        env:
          DOUYIN_SESSION: ${{{{ secrets.DOUYIN_SESSION }}}}
          TEST_MODE: ${{{{ inputs.test_mode || '0' }}}}
          PYTHONPATH: _runner
        run: |
          python -m runner.main --config config.json --actions

      - name: Upload Run Screenshots
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: spark-run-screenshots
          path: screenshots/
          retention-days: 7
"""

class InstanceManager:
    def __init__(self, client: GitHubClient):
        self.client = client

    def list_existing_instances(self, username: str) -> List[Dict[str, Any]]:
        """检查用户账号下现有的 Douyin Streak 实例仓库"""
        instances = []
        url = "https://api.github.com/user/repos?per_page=100&type=owner"
        try:
            res = requests.get(url, headers=self.client.headers, timeout=15)
            if res.status_code == 200:
                repos = res.json()
                for r in repos:
                    name = r.get("name", "")
                    if name.startswith("douyin-streak-instance") or name == "douyin-auto-spark":
                        instances.append({
                            "name": name,
                            "full_name": r["full_name"],
                            "html_url": r["html_url"],
                            "updated_at": r.get("updated_at")
                        })
        except Exception:
            pass
        return instances

    def update_session_only(self, repo_full_name: str, session_json: str) -> Dict[str, Any]:
        """仅更新已有实例的 DOUYIN_SESSION 凭据"""
        return write_github_secret(
            headers=self.client.headers,
            repo_full_name=repo_full_name,
            secret_name="DOUYIN_SESSION",
            secret_value=session_json
        )

    def deploy_instance(
        self,
        repo_name: str,
        config: StreakConfig,
        session_json: str
    ) -> Dict[str, Any]:
        user_info = self.client.get_user_info()
        if not user_info["ok"]:
            return user_info

        owner = user_info["login"]
        repo_full_name = f"{owner}/{repo_name}"

        # 1. 确保私有仓库存在
        repo_url = f"https://api.github.com/repos/{repo_full_name}"
        check_res = requests.get(repo_url, headers=self.client.headers, timeout=15)
        
        if check_res.status_code == 404:
            create_url = "https://api.github.com/user/repos"
            payload = {
                "name": repo_name,
                "private": True,
                "description": "🔥 Douyin Streak Private Instance",
                "auto_init": True
            }
            create_res = requests.post(create_url, headers=self.client.headers, json=payload, timeout=20)
            if create_res.status_code not in (200, 201):
                return {"ok": False, "error": f"创建私有仓库失败: {create_res.text}"}

        # 2. 准备文件 map
        meta = InstanceMeta(
            schema_version=1,
            upstream=UPSTREAM_REPO,
            runner_channel="stable",
            created_by="Douyin Streak Setup"
        )
        cron_expr = config.schedule.to_utc_cron()
        workflow_yaml = generate_workflow_yaml(cron_expr)

        files = {
            ".github/workflows/streak.yml": workflow_yaml.encode("utf-8"),
            "config.json": config.to_json().encode("utf-8"),
            "instance.json": meta.to_json().encode("utf-8")
        }

        # 3. 写入文件至仓库
        for file_path, content_bytes in files.items():
            content_b64 = base64.b64encode(content_bytes).decode("utf-8")
            url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}"
            
            sha = None
            try:
                chk = requests.get(url, headers=self.client.headers, timeout=15)
                if chk.status_code == 200:
                    sha = chk.json().get("sha")
            except Exception:
                pass

            put_payload = {
                "message": f"Update {file_path}",
                "content": content_b64,
                "branch": "main"
            }
            if sha:
                put_payload["sha"] = sha

            put_res = requests.put(url, headers=self.client.headers, json=put_payload, timeout=20)
            if put_res.status_code not in (200, 201):
                return {"ok": False, "error": f"写入 {file_path} 失败: {put_res.text}"}

        # 4. 写入 DOUYIN_SESSION Secret
        secret_res = write_github_secret(
            headers=self.client.headers,
            repo_full_name=repo_full_name,
            secret_name="DOUYIN_SESSION",
            secret_value=session_json
        )
        if not secret_res.get("ok"):
            return {"ok": False, "error": f"写入 Secret 失败: {secret_res.get('error')}"}

        return {
            "ok": True,
            "repo_full_name": repo_full_name,
            "repo_url": f"https://github.com/{repo_full_name}",
            "actions_url": f"https://github.com/{repo_full_name}/actions"
        }

    def trigger_test_run(self, repo_full_name: str) -> Dict[str, Any]:
        """触发 TEST_MODE=1 预检测试"""
        url = f"https://api.github.com/repos/{repo_full_name}/actions/workflows/streak.yml/dispatches"
        payload = {
            "ref": "main",
            "inputs": {
                "test_mode": "1"
            }
        }
        try:
            res = requests.post(url, headers=self.client.headers, json=payload, timeout=15)
            if res.status_code in (200, 204):
                return {"ok": True}
            return {"ok": False, "error": f"触发测试失败 ({res.status_code}): {res.text}"}
        except Exception as e:
            return {"ok": False, "error": f"触发测试异常: {e}"}

    def poll_workflow_run(
        self,
        repo_full_name: str,
        timeout_seconds: int = 60,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """轮询最近一次 workflow dispatch 的执行结果"""
        runs_url = f"https://api.github.com/repos/{repo_full_name}/actions/runs?event=workflow_dispatch&per_page=3"
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            try:
                res = requests.get(runs_url, headers=self.client.headers, timeout=10)
                if res.status_code == 200:
                    runs = res.json().get("workflow_runs", [])
                    if runs:
                        latest_run = runs[0]
                        status = latest_run.get("status")  # queued | in_progress | completed
                        conclusion = latest_run.get("conclusion")  # success | failure | cancelled

                        if progress_callback:
                            progress_callback(f"云端 Actions 状态: {status}...")

                        if status == "completed":
                            if conclusion == "success":
                                return {
                                    "ok": True,
                                    "status": "success",
                                    "run_id": latest_run.get("id"),
                                    "html_url": latest_run.get("html_url")
                                }
                            else:
                                return {
                                    "ok": False,
                                    "status": conclusion or "failed",
                                    "error": f"云端 Actions 运行返回状态: {conclusion}"
                                }
            except Exception:
                pass
            time.sleep(3)

        return {"ok": True, "status": "queued_or_running", "message": "云端测试已触发并在排队执行中"}

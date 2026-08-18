import os
import sys
import subprocess
import requests
from typing import Dict, Any, Optional

def detect_gh_cli_token() -> Optional[str]:
    """尝试自动从已登录的 GitHub CLI 获取 Token"""
    try:
        res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return None

class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        cli_token = detect_gh_cli_token()
        self.token = (token or cli_token or "").strip()
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Douyin-Streak-Setup-Client"
        }

    def get_user_info(self) -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "未提供 GitHub Token"}
        url = "https://api.github.com/user"
        try:
            res = requests.get(url, headers=self.headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                scopes = res.headers.get("X-OAuth-Scopes", "")
                return {
                    "ok": True,
                    "login": data.get("login"),
                    "name": data.get("name") or data.get("login"),
                    "avatar_url": data.get("avatar_url"),
                    "html_url": data.get("html_url"),
                    "scopes": [s.strip() for s in scopes.split(",") if s.strip()]
                }
            return {"ok": False, "error": f"身份验证失败 ({res.status_code}): {res.text}"}
        except Exception as e:
            return {"ok": False, "error": f"网络异常: {e}"}

    def star_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        自愿 Star 上游项目 (容错设计：如果失败不阻断任何后续流程)
        """
        user_info = self.get_user_info()
        if user_info.get("ok") and user_info.get("login") == owner:
            return {"ok": True, "message": "作者本人账号无需 Star"}

        # 1. 尝试 gh CLI
        try:
            res = subprocess.run(["gh", "api", "-X", "PUT", f"user/starred/{owner}/{repo}"], capture_output=True, text=True)
            if res.returncode == 0:
                return {"ok": True}
        except Exception:
            pass

        # 2. 尝试 REST API
        url = f"https://api.github.com/user/starred/{owner}/{repo}"
        try:
            res = requests.put(url, headers=self.headers, timeout=15)
            return {"ok": res.status_code in (204, 200), "status": res.status_code}
        except Exception as e:
            return {"ok": False, "error": str(e)}

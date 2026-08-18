import os
import sys
import json
import base64
import struct
import hashlib
import subprocess
import requests
from cryptography.hazmat.primitives.asymmetric import x25519

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Pure Python / Cryptography NaCl crypto_box_seal implementation for GitHub Actions Secrets

def _salsa20_core(state):
    x = list(state)
    for _ in range(10):
        x[ 4] = (x[ 4] ^ (((x[ 0] + x[12]) & 0xFFFFFFFF) << 7 | ((x[ 0] + x[12]) & 0xFFFFFFFF) >> 25)) & 0xFFFFFFFF
        x[ 8] = (x[ 8] ^ (((x[ 4] + x[ 0]) & 0xFFFFFFFF) << 9 | ((x[ 4] + x[ 0]) & 0xFFFFFFFF) >> 23)) & 0xFFFFFFFF
        x[12] = (x[12] ^ (((x[ 8] + x[ 4]) & 0xFFFFFFFF) << 13 | ((x[ 8] + x[ 4]) & 0xFFFFFFFF) >> 19)) & 0xFFFFFFFF
        x[ 0] = (x[ 0] ^ (((x[12] + x[ 8]) & 0xFFFFFFFF) << 18 | ((x[12] + x[ 8]) & 0xFFFFFFFF) >> 14)) & 0xFFFFFFFF
        x[ 9] = (x[ 9] ^ (((x[ 5] + x[ 1]) & 0xFFFFFFFF) << 7 | ((x[ 5] + x[ 1]) & 0xFFFFFFFF) >> 25)) & 0xFFFFFFFF
        x[13] = (x[13] ^ (((x[ 9] + x[ 5]) & 0xFFFFFFFF) << 9 | ((x[ 9] + x[ 5]) & 0xFFFFFFFF) >> 23)) & 0xFFFFFFFF
        x[ 1] = (x[ 1] ^ (((x[13] + x[ 9]) & 0xFFFFFFFF) << 13 | ((x[13] + x[ 9]) & 0xFFFFFFFF) >> 19)) & 0xFFFFFFFF
        x[ 5] = (x[ 5] ^ (((x[ 1] + x[13]) & 0xFFFFFFFF) << 18 | ((x[ 1] + x[13]) & 0xFFFFFFFF) >> 14)) & 0xFFFFFFFF
        x[14] = (x[14] ^ (((x[10] + x[ 6]) & 0xFFFFFFFF) << 7 | ((x[10] + x[ 6]) & 0xFFFFFFFF) >> 25)) & 0xFFFFFFFF
        x[ 2] = (x[ 2] ^ (((x[14] + x[10]) & 0xFFFFFFFF) << 9 | ((x[14] + x[10]) & 0xFFFFFFFF) >> 23)) & 0xFFFFFFFF
        x[ 6] = (x[ 6] ^ (((x[ 2] + x[14]) & 0xFFFFFFFF) << 13 | ((x[ 2] + x[14]) & 0xFFFFFFFF) >> 19)) & 0xFFFFFFFF
        x[10] = (x[10] ^ (((x[ 6] + x[ 2]) & 0xFFFFFFFF) << 18 | ((x[ 6] + x[ 2]) & 0xFFFFFFFF) >> 14)) & 0xFFFFFFFF
        x[ 3] = (x[ 3] ^ (((x[15] + x[11]) & 0xFFFFFFFF) << 7 | ((x[15] + x[11]) & 0xFFFFFFFF) >> 25)) & 0xFFFFFFFF
        x[ 7] = (x[ 7] ^ (((x[ 3] + x[15]) & 0xFFFFFFFF) << 9 | ((x[ 3] + x[15]) & 0xFFFFFFFF) >> 23)) & 0xFFFFFFFF
        x[11] = (x[11] ^ (((x[ 7] + x[ 3]) & 0xFFFFFFFF) << 13 | ((x[ 7] + x[ 3]) & 0xFFFFFFFF) >> 19)) & 0xFFFFFFFF
        x[15] = (x[15] ^ (((x[11] + x[ 7]) & 0xFFFFFFFF) << 18 | ((x[11] + x[ 7]) & 0xFFFFFFFF) >> 14)) & 0xFFFFFFFF
        # row round
        x[ 1] = (x[ 1] ^ (((x[ 0] + x[ 3]) & 0xFFFFFFFF) << 7 | ((x[ 0] + x[ 3]) & 0xFFFFFFFF) >> 25)) & 0xFFFFFFFF
        x[ 2] = (x[ 2] ^ (((x[ 1] + x[ 0]) & 0xFFFFFFFF) << 9 | ((x[ 1] + x[ 0]) & 0xFFFFFFFF) >> 23)) & 0xFFFFFFFF
        x[ 3] = (x[ 3] ^ (((x[ 2] + x[ 1]) & 0xFFFFFFFF) << 13 | ((x[ 2] + x[ 1]) & 0xFFFFFFFF) >> 19)) & 0xFFFFFFFF
        x[ 0] = (x[ 0] ^ (((x[ 3] + x[ 2]) & 0xFFFFFFFF) << 18 | ((x[ 3] + x[ 2]) & 0xFFFFFFFF) >> 14)) & 0xFFFFFFFF
        x[ 6] = (x[ 6] ^ (((x[ 5] + x[ 4]) & 0xFFFFFFFF) << 7 | ((x[ 5] + x[ 4]) & 0xFFFFFFFF) >> 25)) & 0xFFFFFFFF
        x[ 7] = (x[ 7] ^ (((x[ 6] + x[ 5]) & 0xFFFFFFFF) << 9 | ((x[ 6] + x[ 5]) & 0xFFFFFFFF) >> 23)) & 0xFFFFFFFF
        x[ 4] = (x[ 4] ^ (((x[ 7] + x[ 6]) & 0xFFFFFFFF) << 13 | ((x[ 7] + x[ 6]) & 0xFFFFFFFF) >> 19)) & 0xFFFFFFFF
        x[ 5] = (x[ 5] ^ (((x[ 4] + x[ 7]) & 0xFFFFFFFF) << 18 | ((x[ 4] + x[ 7]) & 0xFFFFFFFF) >> 14)) & 0xFFFFFFFF
        x[11] = (x[11] ^ (((x[10] + x[ 9]) & 0xFFFFFFFF) << 7 | ((x[10] + x[ 9]) & 0xFFFFFFFF) >> 25)) & 0xFFFFFFFF
        x[ 8] = (x[ 8] ^ (((x[11] + x[10]) & 0xFFFFFFFF) << 9 | ((x[11] + x[10]) & 0xFFFFFFFF) >> 23)) & 0xFFFFFFFF
        x[ 9] = (x[ 9] ^ (((x[ 8] + x[11]) & 0xFFFFFFFF) << 13 | ((x[ 8] + x[11]) & 0xFFFFFFFF) >> 19)) & 0xFFFFFFFF
        x[10] = (x[10] ^ (((x[ 9] + x[ 8]) & 0xFFFFFFFF) << 18 | ((x[ 9] + x[ 8]) & 0xFFFFFFFF) >> 14)) & 0xFFFFFFFF
        x[12] = (x[12] ^ (((x[15] + x[14]) & 0xFFFFFFFF) << 7 | ((x[15] + x[14]) & 0xFFFFFFFF) >> 25)) & 0xFFFFFFFF
        x[13] = (x[13] ^ (((x[12] + x[15]) & 0xFFFFFFFF) << 9 | ((x[12] + x[15]) & 0xFFFFFFFF) >> 23)) & 0xFFFFFFFF
        x[14] = (x[14] ^ (((x[13] + x[12]) & 0xFFFFFFFF) << 13 | ((x[13] + x[12]) & 0xFFFFFFFF) >> 19)) & 0xFFFFFFFF
        x[15] = (x[15] ^ (((x[14] + x[13]) & 0xFFFFFFFF) << 18 | ((x[14] + x[13]) & 0xFFFFFFFF) >> 14)) & 0xFFFFFFFF
    return [(a + b) & 0xFFFFFFFF for a, b in zip(x, state)], x

def hsalsa20(k, n):
    c = b'expand 32-byte k'
    state = struct.unpack('<16I', c[:4] + k[:16] + c[4:8] + n[:16] + c[8:12] + k[16:] + c[12:])
    _, x = _salsa20_core(state)
    return struct.pack('<8I', x[0], x[5], x[10], x[15], x[6], x[7], x[8], x[9])

def salsa20_stream(length, nonce, key):
    c = b'expand 32-byte k'
    out = bytearray()
    counter = 0
    while len(out) < length:
        n_cnt = nonce + struct.pack('<Q', counter)
        state = struct.unpack('<16I', c[:4] + key[:16] + c[4:8] + n_cnt + c[8:12] + key[16:] + c[12:])
        block, _ = _salsa20_core(state)
        out.extend(struct.pack('<16I', *block))
        counter += 1
    return bytes(out[:length])

def poly1305_mac(msg, key):
    r = int.from_bytes(key[:16], 'little') & 0x0ffffffc0ffffffc0ffffffc0fffffff
    s = int.from_bytes(key[16:32], 'little')
    p = (1 << 130) - 5
    acc = 0
    for i in range(0, len(msg), 16):
        chunk = msg[i:i+16]
        n = int.from_bytes(chunk + b'\x01', 'little')
        acc = (acc + n) * r % p
    acc = (acc + s) % (1 << 128)
    return acc.to_bytes(16, 'little')

def crypto_box_seal(message: bytes, recipient_pk_bytes: bytes) -> bytes:
    esk = x25519.X25519PrivateKey.generate()
    epk_bytes = esk.public_key().public_bytes_raw()
    recipient_pk = x25519.X25519PublicKey.from_public_bytes(recipient_pk_bytes)
    shared_key = esk.exchange(recipient_pk)
    k = hsalsa20(shared_key, b'\x00' * 16)
    nonce = hashlib.blake2b(epk_bytes + recipient_pk_bytes, digest_size=24).digest()
    subkey = hsalsa20(k, nonce[:16])
    subnonce = nonce[16:24]
    stream = salsa20_stream(len(message) + 32, subnonce, subkey)
    poly_key = stream[:32]
    cipher_stream = stream[32:]
    ciphertext = bytes(a ^ b for a, b in zip(message, cipher_stream))
    mac = poly1305_mac(ciphertext, poly_key)
    return epk_bytes + mac + ciphertext

def get_gh_cli_token():
    try:
        res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return None

class GitHubService:
    UPSTREAM_OWNER = "MaaBlock"
    UPSTREAM_REPO = "douyin-auto-spark"

    def __init__(self, token: str = None):
        cli_tok = get_gh_cli_token()
        self.token = (token or cli_tok or "").strip()
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Douyin-Auto-Spark-Setup-Wizard"
        }

    def get_user_info(self):
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
            return {"ok": False, "error": f"GitHub 身份验证失败 ({res.status_code}): {res.text}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def star_upstream(self):
        # 如果是作者本人，无需 Star 自己的仓库
        user_info = self.get_user_info()
        if user_info.get("ok") and user_info.get("login") == self.UPSTREAM_OWNER:
            return {"ok": True, "self_owned": True, "message": "作者本人账号无需 Star"}

        # 1. 优先使用 gh CLI 执行 Star
        try:
            gh_res = subprocess.run(["gh", "api", "-X", "PUT", f"user/starred/{self.UPSTREAM_OWNER}/{self.UPSTREAM_REPO}"], capture_output=True, text=True)
            if gh_res.returncode == 0:
                return {"ok": True, "method": "gh_cli"}
        except Exception:
            pass

        # 2. 使用 REST API 执行 Star
        url = f"https://api.github.com/user/starred/{self.UPSTREAM_OWNER}/{self.UPSTREAM_REPO}"
        try:
            res = requests.put(url, headers=self.headers, timeout=15)
            return {"ok": res.status_code in (204, 200), "status": res.status_code, "method": "rest_api"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def ensure_private_repo(self, repo_name="douyin-auto-spark"):
        user_info = self.get_user_info()
        if not user_info["ok"]:
            return user_info

        owner = user_info["login"]
        repo_url = f"https://api.github.com/repos/{owner}/{repo_name}"
        try:
            res = requests.get(repo_url, headers=self.headers, timeout=15)
            if res.status_code == 200:
                repo_data = res.json()
                # 部署/更新 runner workflow
                self._deploy_runner_workflow(repo_data["full_name"])
                return {
                    "ok": True,
                    "created": False,
                    "full_name": repo_data["full_name"],
                    "html_url": repo_data["html_url"],
                    "default_branch": repo_data.get("default_branch", "main"),
                    "private": repo_data.get("private", True)
                }
            elif res.status_code == 404:
                # 创建私有仓库
                create_url = "https://api.github.com/user/repos"
                payload = {
                    "name": repo_name,
                    "private": True,
                    "description": "🔥 抖音自动续火花 (私有云端托管)",
                    "auto_init": True
                }
                create_res = requests.post(create_url, headers=self.headers, json=payload, timeout=20)
                if create_res.status_code in (201, 200):
                    repo_data = create_res.json()
                    repo_full_name = repo_data["full_name"]
                    self._deploy_runner_workflow(repo_full_name)
                    return {
                        "ok": True,
                        "created": True,
                        "full_name": repo_full_name,
                        "html_url": repo_data["html_url"],
                        "default_branch": repo_data.get("default_branch", "main"),
                        "private": True
                    }
                return {"ok": False, "error": f"创建私有仓库失败: {create_res.text}"}
            return {"ok": False, "error": f"检测仓库异常: {res.text}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _deploy_runner_workflow(self, repo_full_name: str):
        workflow_content = f"""name: Douyin Spark Auto Renew

on:
  schedule:
    # 每天 UTC 00:30 (北京时间 08:30)
    - cron: '30 0 * * *'
    # 每天 UTC 12:30 补发一次 (北京时间 20:30，双重保险)
    - cron: '30 12 * * *'
  workflow_dispatch:

jobs:
  renew_spark:
    runs-on: ubuntu-latest

    steps:
      - name: Clone Douyin Spark Upstream Code
        run: |
          git clone https://github.com/{self.UPSTREAM_OWNER}/{self.UPSTREAM_REPO}.git .

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          playwright install --with-deps chromium

      - name: Run Douyin Spark
        env:
          DOUYIN_CONFIG: ${{{{ secrets.DOUYIN_CONFIG }}}}
        run: |
          python douyin_spark.py --actions

      - name: Upload Run Screenshots
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: spark-run-screenshots
          path: screenshots/
          retention-days: 7
"""
        return self.deploy_files(repo_full_name, {
            ".github/workflows/douyin_spark.yml": workflow_content.encode("utf-8")
        })

    def deploy_files(self, repo_full_name: str, files_dict: dict, branch="main"):
        results = {}
        for file_path, content_bytes in files_dict.items():
            content_b64 = base64.b64encode(content_bytes).decode("utf-8")
            url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}"
            
            sha = None
            try:
                check_res = requests.get(f"{url}?ref={branch}", headers=self.headers, timeout=15)
                if check_res.status_code == 200:
                    sha = check_res.json().get("sha")
            except Exception:
                pass

            payload = {
                "message": f"Deploy {file_path} via Douyin Streak Setup Wizard",
                "content": content_b64,
                "branch": branch
            }
            if sha:
                payload["sha"] = sha

            try:
                put_res = requests.put(url, headers=self.headers, json=payload, timeout=20)
                results[file_path] = put_res.status_code in (200, 201)
            except Exception:
                results[file_path] = False

        all_ok = all(results.values())
        return {"ok": all_ok, "details": results}

    def set_secret(self, repo_full_name: str, secret_name: str, secret_value: str):
        # 1. 优先尝试使用 gh CLI 写入 Secret (无需网络计算)
        try:
            gh_res = subprocess.run(
                ["gh", "secret", "set", secret_name, "-b", secret_value, "--repo", repo_full_name],
                capture_output=True,
                text=True
            )
            if gh_res.returncode == 0:
                return {"ok": True, "secret_name": secret_name, "method": "gh_cli"}
        except Exception:
            pass

        # 2. 使用 REST API + NaCl 公钥加密写入 Secret
        pk_url = f"https://api.github.com/repos/{repo_full_name}/actions/secrets/public-key"
        pk_res = requests.get(pk_url, headers=self.headers, timeout=15)
        if pk_res.status_code != 200:
            return {"ok": False, "error": f"获取仓库公钥失败: {pk_res.text}"}

        pk_data = pk_res.json()
        key_id = pk_data["key_id"]
        public_key_b64 = pk_data["key"]
        public_key_bytes = base64.b64decode(public_key_b64)

        try:
            sealed_bytes = crypto_box_seal(secret_value.encode("utf-8"), public_key_bytes)
            encrypted_b64 = base64.b64encode(sealed_bytes).decode("utf-8")
        except Exception as e:
            return {"ok": False, "error": f"凭证加密失败: {e}"}

        set_url = f"https://api.github.com/repos/{repo_full_name}/actions/secrets/{secret_name}"
        payload = {
            "encrypted_value": encrypted_b64,
            "key_id": key_id
        }
        set_res = requests.put(set_url, headers=self.headers, json=payload, timeout=20)
        if set_res.status_code in (201, 204):
            return {"ok": True, "secret_name": secret_name, "method": "rest_api"}
        return {"ok": False, "error": f"写入 Secret 失败 ({set_res.status_code}): {set_res.text}"}

    def trigger_workflow(self, repo_full_name: str, workflow_name="douyin_spark.yml", branch="main"):
        # 1. 优先尝试使用 gh CLI
        try:
            gh_res = subprocess.run(["gh", "workflow", "run", workflow_name, "--repo", repo_full_name, "--ref", branch], capture_output=True, text=True)
            if gh_res.returncode == 0:
                return {"ok": True, "method": "gh_cli"}
        except Exception:
            pass

        # 2. 使用 REST API
        url = f"https://api.github.com/repos/{repo_full_name}/actions/workflows/{workflow_name}/dispatches"
        payload = {"ref": branch}
        try:
            res = requests.post(url, headers=self.headers, json=payload, timeout=15)
            if res.status_code in (204, 200):
                return {"ok": True, "method": "rest_api"}
            return {"ok": False, "error": f"触发 Actions 失败 ({res.status_code}): {res.text}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

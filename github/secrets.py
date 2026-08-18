import base64
import struct
import hashlib
import subprocess
import requests
from typing import Dict, Any
from cryptography.hazmat.primitives.asymmetric import x25519

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
        x[ 9] = (x[ 9] ^ (((x[ 8] + x[11]) & 0xFFFFFFFF) << 13 | ((x[ 8] + x[ 1]) & 0xFFFFFFFF) >> 19)) & 0xFFFFFFFF
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

def write_github_secret(headers: dict, repo_full_name: str, secret_name: str, secret_value: str) -> Dict[str, Any]:
    # 1. 优先尝试使用 gh CLI 写入 Secret
    try:
        gh_res = subprocess.run(
            ["gh", "secret", "set", secret_name, "-b", secret_value, "--repo", repo_full_name],
            capture_output=True,
            text=True
        )
        if gh_res.returncode == 0:
            return {"ok": True, "secret_name": secret_name}
    except Exception:
        pass

    # 2. REST API + NaCl 公钥加密
    pk_url = f"https://api.github.com/repos/{repo_full_name}/actions/secrets/public-key"
    try:
        pk_res = requests.get(pk_url, headers=headers, timeout=15)
        if pk_res.status_code != 200:
            return {"ok": False, "error": f"获取仓库公钥失败: {pk_res.text}"}

        pk_data = pk_res.json()
        key_id = pk_data["key_id"]
        public_key_b64 = pk_data["key"]
        public_key_bytes = base64.b64decode(public_key_b64)

        sealed_bytes = crypto_box_seal(secret_value.encode("utf-8"), public_key_bytes)
        encrypted_b64 = base64.b64encode(sealed_bytes).decode("utf-8")

        set_url = f"https://api.github.com/repos/{repo_full_name}/actions/secrets/{secret_name}"
        payload = {
            "encrypted_value": encrypted_b64,
            "key_id": key_id
        }
        set_res = requests.put(set_url, headers=headers, json=payload, timeout=20)
        if set_res.status_code in (201, 204):
            return {"ok": True, "secret_name": secret_name}
        return {"ok": False, "error": f"写入 Secret 失败 ({set_res.status_code}): {set_res.text}"}
    except Exception as e:
        return {"ok": False, "error": f"Secret 写入异常: {e}"}

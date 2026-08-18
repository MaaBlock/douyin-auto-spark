import re
import datetime

SENSITIVE_PATTERNS = [
    re.compile(r'(ghp_[a-zA-Z0-9]{30,})', re.IGNORECASE),
    re.compile(r'(github_pat_[a-zA-Z0-9_]{30,})', re.IGNORECASE),
    re.compile(r'(gho_[a-zA-Z0-9]{30,})', re.IGNORECASE),
    re.compile(r'(token["\s:=]+)([a-zA-Z0-9_\-\.]{10,})', re.IGNORECASE),
    re.compile(r'(sessionid["\s:=]+)([a-zA-Z0-9%_\-]{10,})', re.IGNORECASE),
    re.compile(r'(passport_csrf_token["\s:=]+)([a-zA-Z0-9%_\-]{10,})', re.IGNORECASE),
    re.compile(r'(cookie["\s:=]+)([^\r\n",]{15,})', re.IGNORECASE),
    re.compile(r'(storage_state["\s:=]+)({.*?})', re.IGNORECASE | re.DOTALL),
    re.compile(r'(DOUYIN_SESSION["\s:=]+)([^\r\n"]{15,})', re.IGNORECASE),
]

def sanitize_text(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)
    
    sanitized = text
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(r'\1[*** REDACTED ***]', sanitized)
    return sanitized

def safe_log(msg: str, log_file: str = None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_msg = sanitize_text(str(msg))
    line = f"[{timestamp}] {clean_msg}"
    print(line)
    
    if log_file:
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

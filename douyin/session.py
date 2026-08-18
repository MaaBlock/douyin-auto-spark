import json
from typing import Dict, Any, Optional

def clean_storage_state(storage_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    过滤超大营销、广告与非必要缓存 (确保适配 GitHub Secret 64KB 限制)
    """
    if not isinstance(storage_state, dict):
        return {}

    cleaned = dict(storage_state)
    origins = cleaned.get("origins", [])
    for orig in origins:
        orig["localStorage"] = [
            item for item in orig.get("localStorage", [])
            if item.get("name") not in ("LoginGuidingStrategy", "rawData", "byted_acrawler_token", "webmssdk_data")
        ]
    return cleaned

def serialize_session(storage_state: Dict[str, Any], cookies: Optional[list] = None) -> str:
    cleaned_state = clean_storage_state(storage_state)
    data = {
        "storage_state": cleaned_state
    }
    if cookies:
        data["cookies"] = cookies
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))

def deserialize_session(session_str: str) -> Dict[str, Any]:
    if not session_str or not isinstance(session_str, str):
        return {}
    try:
        return json.loads(session_str.strip())
    except Exception:
        return {}

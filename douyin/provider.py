from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from config.model import Conversation

class SendResult:
    def __init__(self, ok: bool, conversation_id: str, message: str = "", error: Optional[str] = None):
        self.ok = ok
        self.conversation_id = conversation_id
        self.message = message
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "conversation_id": self.conversation_id,
            "message": self.message,
            "error": self.error
        }

class DouyinProvider(ABC):
    @abstractmethod
    def start_login_session(self) -> Any:
        """启动扫码登录环境"""
        pass

    @abstractmethod
    def restore_session(self, session_data: Dict[str, Any]) -> bool:
        """从 Session 数据中恢复登录态"""
        pass

    @abstractmethod
    def is_logged_in(self) -> bool:
        """检测当前是否处于有效登录态"""
        pass

    @abstractmethod
    def list_conversations(self) -> List[Conversation]:
        """读取所有会话列表 (私聊/群聊/火花状态)"""
        pass

    @abstractmethod
    def send_message(self, target_id: str, message: str, dry_run: bool = False) -> SendResult:
        """向指定会话发送消息 (支持 dry_run 测试模式)"""
        pass

    @abstractmethod
    def close(self):
        """关闭浏览器与释放资源"""
        pass

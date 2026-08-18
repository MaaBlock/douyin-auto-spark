import json
from typing import List, Optional, Dict, Any

class Conversation:
    def __init__(
        self,
        id: str,
        type: str = "private",
        displayName: str = "",
        avatar: Optional[str] = None,
        preview: str = "",
        streak_enabled: bool = False,
        streak_value: Optional[int] = None,
        streak_expires_in: Optional[int] = None
    ):
        self.id = id
        self.type = type  # "private" | "group"
        self.displayName = displayName
        self.avatar = avatar
        self.preview = preview
        self.streak = {
            "enabled": streak_enabled,
            "value": streak_value,
            "expiresIn": streak_expires_in
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "displayName": self.displayName,
            "avatar": self.avatar,
            "preview": self.preview,
            "streak": self.streak
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conversation":
        streak_info = data.get("streak", {})
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "private"),
            displayName=data.get("displayName", ""),
            avatar=data.get("avatar"),
            preview=data.get("preview", ""),
            streak_enabled=streak_info.get("enabled", False),
            streak_value=streak_info.get("value"),
            streak_expires_in=streak_info.get("expiresIn")
        )

class TargetItem:
    def __init__(self, type: str, id: str, name: str = ""):
        self.type = type  # "private" | "group"
        self.id = id
        self.name = name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "name": self.name
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TargetItem":
        if isinstance(data, str):
            return cls(type="private", id=data, name=data)
        return cls(
            type=data.get("type", "private"),
            id=str(data.get("id", data.get("name", ""))),
            name=str(data.get("name", data.get("id", "")))
        )

class MessageConfig:
    def __init__(self, mode: str = "random", values: Optional[List[str]] = None):
        self.mode = mode  # "fixed" | "random"
        self.values = values if values is not None else ["续火花🔥", "🔥", "滴滴", "每日打卡"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "values": self.values
        }

    @classmethod
    def from_dict(cls, data: Any) -> "MessageConfig":
        if isinstance(data, str):
            return cls(mode="fixed", values=[data])
        if isinstance(data, list):
            return cls(mode="random", values=data)
        if isinstance(data, dict):
            return cls(
                mode=data.get("mode", "random"),
                values=data.get("values", ["续火花🔥"])
            )
        return cls()

class StrategyConfig:
    def __init__(self, mode: str = "daily", max_messages_per_run: int = 20):
        self.mode = mode  # "daily"
        self.max_messages_per_run = max_messages_per_run

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "max_messages_per_run": self.max_messages_per_run
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyConfig":
        if not isinstance(data, dict):
            return cls()
        return cls(
            mode=data.get("mode", "daily"),
            max_messages_per_run=int(data.get("max_messages_per_run", 20))
        )

class ScheduleConfig:
    def __init__(self, hour: int = 22, minute: int = 30, timezone: str = "Asia/Shanghai"):
        self.hour = hour
        self.minute = minute
        self.timezone = timezone

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hour": self.hour,
            "minute": self.minute,
            "timezone": self.timezone
        }

    def to_utc_cron(self) -> str:
        """
        根据当前设置的时区计算对应的 UTC cron 表达式 (北京时间 UTC+8)
        例如 22:30 CST -> 14:30 UTC -> '30 14 * * *'
        """
        offset_hours = 8 if self.timezone == "Asia/Shanghai" else 0
        utc_hour = (self.hour - offset_hours) % 24
        return f"{self.minute} {utc_hour} * * *"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduleConfig":
        if not isinstance(data, dict):
            return cls()
        return cls(
            hour=int(data.get("hour", 22)),
            minute=int(data.get("minute", 30)),
            timezone=data.get("timezone", "Asia/Shanghai")
        )

class StreakConfig:
    def __init__(
        self,
        schema_version: int = 1,
        targets: Optional[List[TargetItem]] = None,
        messages: Optional[MessageConfig] = None,
        strategy: Optional[StrategyConfig] = None,
        schedule: Optional[ScheduleConfig] = None
    ):
        self.schema_version = schema_version
        self.targets = targets or []
        self.messages = messages or MessageConfig()
        self.strategy = strategy or StrategyConfig()
        self.schedule = schedule or ScheduleConfig()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "targets": [t.to_dict() for t in self.targets],
            "messages": self.messages.to_dict(),
            "strategy": self.strategy.to_dict(),
            "schedule": self.schedule.to_dict()
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StreakConfig":
        raw_targets = data.get("targets", [])
        targets = [TargetItem.from_dict(t) for t in raw_targets]
        messages = MessageConfig.from_dict(data.get("messages", {}))
        strategy = StrategyConfig.from_dict(data.get("strategy", {}))
        schedule = ScheduleConfig.from_dict(data.get("schedule", {}))
        return cls(
            schema_version=data.get("schema_version", 1),
            targets=targets,
            messages=messages,
            strategy=strategy,
            schedule=schedule
        )

class InstanceMeta:
    def __init__(
        self,
        schema_version: int = 1,
        upstream: str = "MaaBlock/douyin-auto-spark",
        runner_channel: str = "stable",
        created_by: str = "Douyin Streak Setup"
    ):
        self.schema_version = schema_version
        self.upstream = upstream
        self.runner_channel = runner_channel
        self.created_by = created_by

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "upstream": self.upstream,
            "runner_channel": self.runner_channel,
            "created_by": self.created_by
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InstanceMeta":
        return cls(
            schema_version=data.get("schema_version", 1),
            upstream=data.get("upstream", "MaaBlock/douyin-auto-spark"),
            runner_channel=data.get("runner_channel", "stable"),
            created_by=data.get("created_by", "Douyin Streak Setup")
        )

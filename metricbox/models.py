"""Persistent script metadata. Adding fields here does not affect execution adapters."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import uuid


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ScriptEntry:
    name: str
    path: str
    category: str = "其他"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    interpreter: str = ""
    arguments: list[str] = field(default_factory=list)
    working_dir: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ScriptEntry":
        if not isinstance(data, dict):
            raise ValueError("脚本记录必须是对象")
        required = ("id", "name", "path")
        for key in required:
            if not isinstance(data.get(key), str) or not data[key].strip():
                raise ValueError(f"脚本记录缺少有效的 {key}")
        for key in ("category", "description", "interpreter", "working_dir", "created_at", "updated_at"):
            if key in data and not isinstance(data[key], str):
                raise ValueError(f"脚本记录中的 {key} 必须是文本")
        for key in ("tags", "arguments"):
            value = data.get(key, [])
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"脚本记录中的 {key} 必须是文本列表")
        known = cls.__dataclass_fields__
        return cls(**{key: value for key, value in data.items() if key in known})

    @property
    def available(self) -> bool:
        return Path(self.path).is_file()


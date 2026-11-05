"""Versioned, atomic JSON registry. Never imports or copies a registered script."""

import json
import os
from pathlib import Path
import tempfile

from .models import ScriptEntry


class StorageError(Exception):
    pass


class ScriptStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: list[ScriptEntry] = []

    def load(self) -> list[ScriptEntry]:
        if not self.path.exists():
            self.entries = []
            return self.entries
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or document.get("version") != 1:
                raise ValueError("不支持的脚本库版本")
            records = document.get("scripts")
            if not isinstance(records, list):
                raise ValueError("脚本库 scripts 必须是列表")
            entries = [ScriptEntry.from_dict(row) for row in records]
            if len({entry.id for entry in entries}) != len(entries):
                raise ValueError("脚本库存在重复 ID")
            self.entries = entries
            return entries
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"无法读取脚本库 {self.path}\n{exc}") from exc

    def _commit(self, entries: list[ScriptEntry]) -> None:
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            document = {"version": 1, "scripts": [entry.to_dict() for entry in entries]}
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(document, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except OSError as exc:
            raise StorageError(f"无法保存脚本库：{exc}") from exc
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
        self.entries = entries

    def save(self, entry: ScriptEntry) -> None:
        candidate = Path(entry.path).resolve()
        if not candidate.is_file():
            raise ValueError("脚本文件不存在，请重新选择")
        for other in self.entries:
            if other.id != entry.id and Path(other.path).resolve() == candidate:
                raise ValueError("这个脚本已经添加到工具箱，请编辑已有记录")
        entries = [entry if item.id == entry.id else item for item in self.entries]
        if all(item.id != entry.id for item in self.entries):
            entries.append(entry)
        self._commit(entries)

    def remove(self, entry_id: str) -> None:
        self._commit([item for item in self.entries if item.id != entry_id])

    def add_missing(self, entries: list[ScriptEntry]) -> int:
        """Atomically import a catalog without changing existing user configuration."""
        paths = {Path(item.path).resolve() for item in self.entries}
        additions = []
        for entry in entries:
            path = Path(entry.path).resolve()
            if path in paths:
                continue
            if not path.is_file():
                raise ValueError(f"内置脚本缺失：{path}")
            additions.append(entry)
            paths.add(path)
        if additions:
            self._commit([*self.entries, *additions])
        return len(additions)


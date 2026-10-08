"""Background execution with an adapter registry and UI-safe event queue."""

from dataclasses import dataclass
import codecs
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
from typing import Protocol

from .models import ScriptEntry


def parse_arguments(text: str) -> list[str]:
    """JSON keeps Windows paths, spaces and quotes unambiguous."""
    if not text.strip():
        return []
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError('参数需为 JSON 数组，例如 ["--input", "E:/dataset"]') from exc
    if not isinstance(result, list) or not all(isinstance(value, str) for value in result):
        raise ValueError('参数需为字符串数组，例如 ["--batch-size", "8"]')
    return result


class ExecutionAdapter(Protocol):
    def build_command(self, entry: ScriptEntry) -> list[str]: ...


class PythonAdapter:
    def build_command(self, entry: ScriptEntry) -> list[str]:
        interpreter = entry.interpreter.strip() or sys.executable
        executable = shutil.which(interpreter)
        if not executable:
            raise ValueError("找不到 Python 解释器，请选择有效的 python.exe")
        return [executable, "-u", str(Path(entry.path).resolve()), *entry.arguments]


ADAPTERS: dict[str, ExecutionAdapter] = {".py": PythonAdapter(), ".pyw": PythonAdapter()}


@dataclass
class RunEvent:
    kind: str
    text: str = ""
    returncode: int | None = None


class ScriptRunner:
    def __init__(self):
        self.events: queue.Queue[RunEvent] = queue.Queue(maxsize=512)
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None
        self._cancel = threading.Event()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def prepare(self, entry: ScriptEntry) -> tuple[list[str], str]:
        script = Path(entry.path).resolve()
        if not script.is_file():
            raise ValueError("脚本文件不存在，请编辑脚本路径")
        adapter = ADAPTERS.get(script.suffix.lower())
        if not adapter:
            raise ValueError(f"已收录此文件；当前运行器尚不支持 {script.suffix or '无扩展名'}，可添加执行适配器")
        working_dir = Path(entry.working_dir).resolve() if entry.working_dir else script.parent
        if not working_dir.is_dir():
            raise ValueError("工作目录不存在，请编辑配置")
        return adapter.build_command(entry), str(working_dir)

    def start(self, entry: ScriptEntry) -> None:
        if self.running:
            raise ValueError("已有脚本运行中，请等待完成或先停止")
        command, working_dir = self.prepare(entry)
        self._cancel.clear()
        self._thread = threading.Thread(target=self._execute, args=(command, working_dir), daemon=True)
        self._thread.start()

    def _execute(self, command: list[str], working_dir: str) -> None:
        outcome = RunEvent("finished", returncode=-1)
        try:
            self.events.put(RunEvent("output", f"命令：{subprocess.list2cmdline(command)}\n工作目录：{working_dir}\n\n"))
            environment = os.environ.copy()
            environment["PYTHONIOENCODING"] = "utf-8"
            environment["PYTHONUNBUFFERED"] = "1"
            self._process = subprocess.Popen(
                command, cwd=working_dir, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if self._cancel.is_set():
                self._terminate_process()
            assert self._process.stdout is not None
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            with self._process.stdout:
                # Read chunks so progress bars without newlines also appear in the UI.
                while chunk := os.read(self._process.stdout.fileno(), 4096):
                    self.events.put(RunEvent("output", decoder.decode(chunk)))
                tail = decoder.decode(b"", final=True)
                if tail:
                    self.events.put(RunEvent("output", tail))
            returncode = self._process.wait()
            if self._cancel.is_set():
                outcome = RunEvent("stopped", "运行已停止", returncode)
            else:
                outcome = RunEvent("finished", "运行成功" if returncode == 0 else "运行失败", returncode)
        except OSError as exc:
            outcome = RunEvent("failed", str(exc), -1)
        finally:
            self._process = None
            self.events.put(outcome)

    def _terminate_process(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
                if process.poll() is None:
                    process.kill()
            else:
                process.terminate()
        except (OSError, subprocess.TimeoutExpired):
            if process.poll() is None:
                process.kill()

    def stop(self) -> None:
        self._cancel.set()
        threading.Thread(target=self._terminate_process, daemon=True).start()


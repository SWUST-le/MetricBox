import json
from pathlib import Path
import queue
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from metricbox.models import ScriptEntry
from metricbox.runner import ScriptRunner, parse_arguments
from metricbox.storage import ScriptStore, StorageError


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.script = self.base / "指标.py"
        self.script.write_text("print('ok')", encoding="utf-8")
        self.store = ScriptStore(self.base / "data" / "scripts.json")

    def test_add_reload_edit_remove_preserves_source(self):
        entry = ScriptEntry(name="融合质量", path=str(self.script), tags=["PSNR", "SSIM"])
        self.store.save(entry)
        restored = ScriptStore(self.store.path)
        restored.load()
        self.assertEqual(restored.entries[0].to_dict(), entry.to_dict())
        entry.name = "新名称"
        restored.save(entry)
        self.assertEqual(len(restored.entries), 1)
        self.assertIn("新名称", restored.path.read_text(encoding="utf-8"))
        restored.remove(entry.id)
        self.assertEqual(ScriptStore(restored.path).load(), [])
        self.assertTrue(self.script.exists())

    def test_duplicate_path_and_missing_file_rejected(self):
        self.store.save(ScriptEntry(name="第一份", path=str(self.script)))
        with self.assertRaisesRegex(ValueError, "已经添加"):
            self.store.save(ScriptEntry(name="重复", path=str(self.script.parent / "." / self.script.name)))
        with self.assertRaisesRegex(ValueError, "不存在"):
            self.store.save(ScriptEntry(name="缺失", path=str(self.base / "missing.py")))
        self.assertEqual(len(self.store.entries), 1)

    def test_failed_atomic_save_preserves_registry_and_memory(self):
        self.store.save(ScriptEntry(name="原有", path=str(self.script)))
        original = self.store.path.read_bytes()
        other = self.base / "other.py"
        other.write_text("", encoding="utf-8")
        with patch("metricbox.storage.os.replace", side_effect=PermissionError("locked")):
            with self.assertRaises(StorageError):
                self.store.save(ScriptEntry(name="新增", path=str(other)))
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertEqual(len(self.store.entries), 1)
        self.assertFalse(list(self.store.path.parent.glob("*.tmp")))

    def test_corrupt_and_unsupported_registry_not_replaced(self):
        self.store.path.parent.mkdir()
        for value in ('{broken', '{"version": 9, "scripts": []}', '{"version":1,"scripts":[{"name":3}]}'):
            self.store.path.write_text(value, encoding="utf-8")
            with self.assertRaises(StorageError):
                self.store.load()
            self.assertEqual(self.store.path.read_text(encoding="utf-8"), value)

    def test_missing_script_can_still_be_loaded(self):
        self.store.save(ScriptEntry(name="指标", path=str(self.script)))
        self.script.unlink()
        self.assertFalse(ScriptStore(self.store.path).load()[0].available)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="MetricBox test ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.runner = ScriptRunner()

    def script(self, content, **kwargs):
        path = self.base / "中文 指标.py"
        path.write_text(content, encoding="utf-8")
        return ScriptEntry(name="真实测试", path=str(path), interpreter=sys.executable, **kwargs)

    def events_until_done(self, timeout=12):
        events = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                event = self.runner.events.get(timeout=0.1)
                events.append(event)
                if event.kind != "output":
                    self.runner._thread.join(timeout=2)
                    self.assertFalse(self.runner.running)
                    return events
            except queue.Empty:
                pass
        self.runner.stop()
        self.fail("进程未在预期时间内完成")

    def test_real_process_unicode_arguments_working_directory(self):
        entry = self.script("import json, os, sys\nprint('中文输出')\nprint(json.dumps(sys.argv[1:], ensure_ascii=False))\nprint(os.getcwd())\n",
                            arguments=["含 空格", 'a"b', "E:/数据集"], working_dir=str(self.base))
        self.runner.start(entry)
        events = self.events_until_done()
        output = "".join(event.text for event in events if event.kind == "output")
        self.assertIn("中文输出", output)
        self.assertIn(json.dumps(entry.arguments, ensure_ascii=False), output)
        self.assertIn(str(self.base), output)
        self.assertEqual(events[-1].returncode, 0)

    def test_stderr_and_failed_exit_are_visible(self):
        self.runner.start(self.script("import sys\nprint('test failure', file=sys.stderr)\nsys.exit(7)"))
        events = self.events_until_done()
        self.assertIn("test failure", "".join(event.text for event in events))
        self.assertEqual(events[-1].returncode, 7)

    def test_output_without_newline_arrives_before_exit_and_stop_works(self):
        self.runner.start(self.script("import time\nprint('READY', end='', flush=True)\ntime.sleep(30)"))
        deadline = time.monotonic() + 8
        output = ""
        while "READY" not in output and time.monotonic() < deadline:
            try:
                output += self.runner.events.get(timeout=0.1).text
            except queue.Empty:
                pass
        self.assertIn("READY", output)
        with self.assertRaisesRegex(ValueError, "已有脚本"):
            self.runner.start(self.script("print('another')"))
        self.runner.stop()
        events = self.events_until_done()
        self.assertEqual(events[-1].kind, "stopped")

    def test_invalid_interpreter_directory_and_adapter(self):
        entry = self.script("print('ok')", working_dir=str(self.base / "missing"))
        with self.assertRaisesRegex(ValueError, "工作目录"):
            self.runner.prepare(entry)
        entry.working_dir = ""
        entry.interpreter = str(self.base / "missing-python.exe")
        with self.assertRaisesRegex(ValueError, "解释器"):
            self.runner.prepare(entry)
        other = self.base / "metric.m"
        other.write_text("", encoding="utf-8")
        entry.path = str(other)
        with self.assertRaisesRegex(ValueError, "适配器"):
            self.runner.prepare(entry)

    def test_argument_json_preserves_paths_and_rejects_wrong_types(self):
        args = '["--input", "E:/数据/含 空格", "--name", "a\\\"b"]'
        self.assertEqual(parse_arguments(args), ["--input", "E:/数据/含 空格", "--name", 'a"b'])
        for value in ("--input data", "{}", "[1]", '"text"'):
            with self.assertRaises(ValueError):
                parse_arguments(value)


if __name__ == "__main__":
    unittest.main()


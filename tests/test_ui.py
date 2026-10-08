"""Desktop integration tests with real Tk widgets and isolated storage."""

from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from metricbox.app import MetricBoxApp
from metricbox.storage import ScriptStore
from metricbox.ui.script_dialog import ScriptDialog


class DesktopFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = MetricBoxApp(self.root, self.base / "registry.json")
        self.root.update()

    def tearDown(self):
        if self.app.runner.running:
            self.app.runner.stop()
            deadline = time.monotonic() + 12
            while self.app.runner.running and time.monotonic() < deadline:
                self.root.update()
                time.sleep(0.02)
        self.app.close()

    def dialog(self):
        return next(child for child in self.root.winfo_children() if isinstance(child, ScriptDialog))

    def test_add_via_file_chooser_edit_search_run_and_remove(self):
        script = self.base / "已有 指标.py"
        script.write_text("print('MAE = 0.125，运行成功')", encoding="utf-8")
        self.app.add_button.invoke()
        dialog = self.dialog()
        with patch("metricbox.ui.script_dialog.filedialog.askopenfilename", return_value=str(script)):
            dialog.browse_script()
        self.assertEqual(dialog.values["name"].get(), script.stem)
        dialog.values["name"].set("指标示例")
        dialog.values["category"].set("自定义任务")
        dialog.values["tags"].set("MAE， MSE, MAE")
        dialog.save_button.invoke()
        self.root.update()
        self.assertEqual(len(self.app.tree.get_children()), 1)
        self.assertEqual(self.app.selected_entry().tags, ["MAE", "MSE"])
        self.assertEqual(ScriptStore(self.app.store.path).load()[0].name, "指标示例")

        self.app.edit_button.invoke()
        dialog = self.dialog()
        dialog.description.insert("1.0", "用于误差测试")
        dialog.save_button.invoke()
        self.root.update()
        self.assertIn("用于误差测试", self.app.details.get("1.0", "end"))
        self.app.search_var.set("nothing-matches")
        self.assertEqual(self.app.tree.get_children(), ())
        self.app.search_var.set("mae")
        self.root.update()
        self.assertEqual(len(self.app.tree.get_children()), 1)
        self.app.set_category("自定义任务")
        self.assertEqual(len(self.app.tree.get_children()), 1)

        self.app.run_button.invoke()
        deadline = time.monotonic() + 12
        while self.app.active_entry is not None and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.02)
        self.assertIsNone(self.app.active_entry)
        self.assertIn("MAE = 0.125", self.app.log.get("1.0", "end"))
        self.assertIn("退出码 0", self.app.run_status.get())
        saved_log = self.base / "日志.log"
        with patch("metricbox.app.filedialog.asksaveasfilename", return_value=str(saved_log)):
            self.app.save_log()
        self.assertIn("MAE = 0.125", saved_log.read_text(encoding="utf-8"))
        with patch("metricbox.app.messagebox.askyesno", return_value=True):
            self.app.remove_button.invoke()
        self.assertTrue(script.is_file())
        self.assertEqual(ScriptStore(self.app.store.path).load(), [])

    def test_invalid_form_remains_open_and_does_not_write(self):
        self.app.add_button.invoke()
        dialog = self.dialog()
        with patch("metricbox.ui.script_dialog.messagebox.showerror") as error:
            dialog.save_button.invoke()
        error.assert_called_once()
        self.assertTrue(dialog.winfo_exists())
        self.assertFalse(self.app.store.path.exists())
        dialog.destroy()

    def test_reload_and_missing_file_status(self):
        script = self.base / "metric.py"
        script.write_text("print('ok')", encoding="utf-8")
        from metricbox.models import ScriptEntry
        entry = ScriptEntry(name="测试", path=str(script))
        self.app.save_entry(entry)
        script.unlink()
        self.app.refresh()
        self.assertEqual(self.app.tree.item(entry.id, "values")[-1], "文件缺失")
        self.assertEqual(self.app.stat_vars[2].get(), "0")
        reopened = tk.Toplevel(self.root)
        reopened.withdraw()
        restored = MetricBoxApp(reopened, self.app.store.path)
        self.root.update()
        try:
            self.assertEqual(restored.selected_entry().id, entry.id)
            self.assertEqual(restored.tree.item(entry.id, "values")[-1], "文件缺失")
        finally:
            restored.close()

    def test_corrupt_registry_opens_read_only_without_overwriting(self):
        broken = self.base / "broken.json"
        broken.write_text("{broken", encoding="utf-8")
        window = tk.Toplevel(self.root)
        window.withdraw()
        with patch("metricbox.app.messagebox.showerror") as error:
            app = MetricBoxApp(window, broken)
        try:
            error.assert_called_once()
            self.assertTrue(app._read_only)
            self.assertEqual(str(app.add_button.cget("state")), "disabled")
            app.add_script()
            self.assertFalse(any(isinstance(child, ScriptDialog) for child in window.winfo_children()))
            self.assertEqual(broken.read_text(encoding="utf-8"), "{broken")
        finally:
            app.close()


if __name__ == "__main__":
    unittest.main()


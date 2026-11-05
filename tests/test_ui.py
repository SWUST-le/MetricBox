"""Desktop integration tests with real Tk widgets and isolated storage."""

from pathlib import Path
import json
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

    def finish_image_job(self):
        deadline = time.monotonic() + 20
        while self.app.active_entry is not None and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.02)
        self.assertIsNone(self.app.active_entry)
        self.assertIn("退出码 0", self.app.run_status.get())
        self.assertEqual(self.app.tabs.select(), str(self.app.image_results.master.master))

    def test_image_form_choosers_drive_real_quality_calculation_and_auto_export(self):
        import numpy as np
        from PIL import Image
        original, processed = self.base / "原图 空格.png", self.base / "处理后.png"
        Image.fromarray(np.zeros((16, 16), dtype=np.uint8)).save(original)
        Image.fromarray(np.full((16, 16), 4, dtype=np.uint8)).save(processed)
        panel = self.app.image_panel
        with patch("metricbox.ui.image_panel.filedialog.askopenfilename", side_effect=[str(original), str(processed)]):
            panel.browse_image(panel.original)
            panel.browse_image(panel.processed)
        panel.run_button.invoke()
        output = self.app._image_output
        excel_output = self.app._image_xlsx
        self.assertIsNotNone(output)
        self.assertNotIn("--demo", self.app.active_entry.arguments)
        self.finish_image_job()
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertFalse(result["demo"])
        self.assertEqual(result["results"][0]["metrics"]["MAE"], 4)
        self.assertEqual(result["results"][0]["metrics"]["MSE"], 16)
        self.assertIn("MAE: 4.0", self.app.image_results.get("1.0", "end"))
        from openpyxl import load_workbook
        from io import BytesIO
        book = load_workbook(BytesIO(excel_output.read_bytes()))
        self.assertEqual(book["逐图明细"]["C2"].value, 16)
        book.close()
        self.assertIn(str(excel_output), self.app.image_results.get("1.0", "end"))
        self.assertEqual(self.app.store.entries, [])
        self.assertFalse(self.app.store.path.exists())

    def test_image_form_directories_and_selected_output(self):
        import numpy as np
        from PIL import Image
        original, processed = self.base / "原图目录", self.base / "处理目录"
        original.mkdir()
        processed.mkdir()
        for index in range(2):
            Image.fromarray(np.zeros((16, 16), dtype=np.uint8)).save(original / f"{index}.png")
            Image.fromarray(np.full((16, 16), index * 10, dtype=np.uint8)).save(processed / f"{index}.png")
        panel = self.app.image_panel
        with patch("metricbox.ui.image_panel.filedialog.askdirectory", side_effect=[str(original), str(processed)]):
            panel.browse_directory(panel.original)
            panel.browse_directory(panel.processed)
        output = self.base / "导出" / "指标.json"
        with patch("metricbox.ui.image_panel.filedialog.asksaveasfilename", return_value=str(output)):
            panel.browse_output()
        panel.run_button.invoke()
        self.finish_image_job()
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["mean_per_image"]["MSE"], 50)

    def test_image_form_validation_and_task_specific_controls(self):
        panel = self.app.image_panel
        with patch("metricbox.app.messagebox.showerror") as error:
            panel.run_button.invoke()
        error.assert_called_once()
        self.assertIsNone(self.app.active_entry)
        panel.task.set("融合图像统计（EN / SD / SF）")
        self.assertEqual(str(panel.original_controls[1].cget("state")), "disabled")
        self.assertEqual(str(panel.range_input.cget("state")), "disabled")
        panel.task.set("二值分割（真值与预测掩膜）")
        self.assertEqual(str(panel.threshold_input.cget("state")), "normal")
        self.assertEqual(str(panel.original_controls[1].cget("state")), "normal")

    def test_image_form_executes_segmentation_and_fusion_from_paths(self):
        import numpy as np
        from PIL import Image
        mask = self.base / "掩膜.png"
        Image.fromarray(np.array([[0, 1], [1, 0]], dtype=np.uint8)).save(mask)
        panel = self.app.image_panel
        panel.original.set(str(mask))
        panel.processed.set(str(mask))
        panel.task.set("二值分割（真值与预测掩膜）")
        panel.threshold.set("0.5")
        panel.run_button.invoke()
        output = self.app._image_output
        self.finish_image_job()
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["results"][0]["metrics"]["TP"], 2)
        panel.task.set("融合图像统计（EN / SD / SF）")
        panel.original.set("此路径不参与融合统计")
        panel.run_button.invoke()
        output = self.app._image_output
        self.finish_image_job()
        self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["results"][0]["metrics"]["EN"], 1)

    def test_failed_image_job_does_not_display_a_successful_result(self):
        import numpy as np
        from PIL import Image
        image = self.base / "too_small.png"
        Image.fromarray(np.zeros((2, 2), dtype=np.uint8)).save(image)
        panel = self.app.image_panel
        panel.original.set(str(image))
        panel.processed.set(str(image))
        panel.run_button.invoke()
        output = self.app._image_output
        deadline = time.monotonic() + 15
        while self.app.active_entry is not None and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.02)
        self.assertIsNone(self.app.active_entry)
        self.assertFalse(output.exists())
        self.assertIn("未生成本次有效结果", self.app.image_results.get("1.0", "end"))
        self.assertIn("11", self.app.log.get("1.0", "end"))
        self.assertIn("退出码 2", self.app.run_status.get())

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

    def test_import_builtins_preserves_edits_and_runs_demo(self):
        self.app.builtin_button.invoke()
        self.root.update()
        self.assertEqual(len(self.app.store.entries), 4)
        entry = next(item for item in self.app.store.entries if "PSNR" in item.tags)
        entry.description = "用户的配置说明"
        self.app.save_entry(entry)
        self.app.builtin_button.invoke()
        self.assertEqual(len(self.app.store.entries), 4)
        self.assertEqual(self.app.selected_entry().description, "用户的配置说明")
        self.assertEqual(len(ScriptStore(self.app.store.path).load()), 4)
        self.app.run_button.invoke()
        deadline = time.monotonic() + 15
        while self.app.active_entry is not None and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.02)
        self.assertIsNone(self.app.active_entry)
        self.assertIn('"SSIM"', self.app.log.get("1.0", "end"))
        self.assertIn("退出码 0", self.app.run_status.get())

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
            self.assertEqual(str(app.builtin_button.cget("state")), "disabled")
            app.add_script()
            self.assertFalse(any(isinstance(child, ScriptDialog) for child in window.winfo_children()))
            self.assertEqual(broken.read_text(encoding="utf-8"), "{broken")
        finally:
            app.close()


if __name__ == "__main__":
    unittest.main()


import json
from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from openpyxl import load_workbook

from metricbox.image_jobs import prepare_image_job
from metricbox.metrics.excel import write_xlsx
import test_metrics


class ExcelExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_typed_numeric_results_infinity_and_literal_filenames(self):
        result = {"task": "quality", "demo": False, "count": 2,
                  "mean_per_image": {"MSE": 2.0, "PSNR": "Infinity"},
                  "results": [{"name": "=1+1.png", "metrics": {"MSE": 0, "PSNR": "Infinity"}},
                              {"name": "中文图.png", "metrics": {"MSE": 4.0, "PSNR": 42.0}}],
                  "inputs": {"pred": "E:/含 空格/预测"}, "settings": {"data_range": 255}}
        output = self.base / "结果" / "指标.xlsx"
        write_xlsx(result, output)
        book = load_workbook(BytesIO(output.read_bytes()))
        try:
            self.assertEqual(book.sheetnames, ["汇总", "逐图明细"])
            page = book["逐图明细"]
            self.assertEqual(page["A2"].value, "=1+1.png")
            self.assertEqual(page["A2"].data_type, "s")
            self.assertEqual(page["B2"].value, 0)
            self.assertEqual(page["B3"].value, 4)
            self.assertEqual(page["B3"].data_type, "n")
            self.assertEqual(page["C2"].value, "Infinity")
            self.assertEqual(page.freeze_panes, "B2")
            self.assertEqual(page.auto_filter.ref, "A1:C3")
            self.assertFalse(page.sheet_view.showGridLines)
            values = list(book["汇总"].values)
            self.assertIn(("计算参数", "data_range", 255), values)
            self.assertIn(("输入", "pred", "E:/含 空格/预测"), values)
        finally:
            book.close()

    def test_prepare_excel_job_reserves_both_paths(self):
        image = self.base / "image.png"
        image.touch()
        def prepare(output="", fmt="xlsx"):
            return prepare_image_job("quality", str(image), str(image), output, "127", "255", self.base,
                                     output_format=fmt)
        job = prepare()
        self.assertEqual(job.xlsx_output.suffix, ".xlsx")
        self.assertEqual(job.output, job.xlsx_output.with_suffix(".json"))
        self.assertIn("--xlsx", job.entry.arguments)
        (self.base / "existing.json").write_text("old")
        with self.assertRaises(ValueError):
            prepare(str(self.base / "existing.xlsx"))
        json_job = prepare(str(self.base / "only.json"))
        self.assertIsNone(json_job.xlsx_output)


class ExcelCLITests(unittest.TestCase):
    setUp = test_metrics.MetricCLITests.setUp
    run_script = test_metrics.MetricCLITests.run_script
    def test_excel_cli_all_tasks_and_classification_matrix(self):
        for kind in ("quality", "segmentation", "fusion", "classification"):
            output = self.base / f"{kind}.xlsx"
            json_path = output.with_suffix(".json")
            result = self.run_script(kind, "--demo", "--output", json_path, "--xlsx", output)
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), result)
            book = load_workbook(BytesIO(output.read_bytes()), data_only=True)
            try:
                if kind == "classification":
                    self.assertEqual(book.sheetnames, ["汇总", "逐类指标", "混淆矩阵"])
                    self.assertEqual(book["混淆矩阵"]["C4"].value, 1)
                    self.assertEqual(book["逐类指标"]["E4"].value, 2)
                else:
                    page = book["逐图明细"]
                    self.assertEqual(page.max_row, 2)
                    for i, value in enumerate(result["results"][0]["metrics"].values(), 2):
                        self.assertAlmostEqual(page.cell(2, i).value, value)
            finally:
                book.close()

    def test_output_xlsx_extension_is_supported(self):
        output = self.base / "direct.xlsx"
        self.run_script("quality", "--demo", "--output", output)
        book = load_workbook(BytesIO(output.read_bytes()))
        book.close()
        self.run_script("quality", "--demo", "--xlsx", self.base / "bad.txt", success=False)


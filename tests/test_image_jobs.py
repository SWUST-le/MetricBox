from pathlib import Path
import tempfile
import unittest

from metricbox.builtin_catalog import builtin_entries
from metricbox.image_jobs import prepare_image_job


class ImageJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.original = self.base / "原始 图像.png"
        self.processed = self.base / "处理后 图像.png"
        self.original.touch()
        self.processed.touch()

    def job(self, **overrides):
        values = dict(kind="quality", original=str(self.original), processed=str(self.processed), output="",
                      threshold="127", data_range="255", result_dir=self.base / "results")
        values.update(overrides)
        return prepare_image_job(**values)

    def test_maps_reference_and_prediction_without_changing_saved_config(self):
        template = next(item for item in builtin_entries() if "PSNR" in item.tags)
        template.interpreter = "my-python"
        job = self.job(template=template)
        args = job.entry.arguments
        self.assertEqual(args[args.index("--pred") + 1], str(self.processed))
        self.assertEqual(args[args.index("--target") + 1], str(self.original))
        self.assertNotIn("--demo", args)
        self.assertEqual(template.arguments, ["--demo"])
        self.assertEqual(job.entry.interpreter, "my-python")
        self.assertEqual(job.output.parent, self.base / "results")
        self.assertNotEqual(job.output, self.job().output)

    def test_fusion_ignores_unused_original_and_segmentation_uses_threshold(self):
        fusion = self.job(kind="fusion", original="missing.png", threshold="bad", data_range="bad")
        self.assertEqual(fusion.entry.arguments[:2], ["--image", str(self.processed)])
        segmentation = self.job(kind="segmentation", threshold="0.5", data_range="bad")
        self.assertIn("0.5", segmentation.entry.arguments)
        self.assertNotIn("--data-range", segmentation.entry.arguments)

    def test_invalid_paths_mismatched_modes_and_numeric_fields_rejected(self):
        for overrides in ({"processed": ""}, {"original": "relative.png"},
                          {"processed": str(self.base / "missing.png")}, {"original": str(self.base)},
                          {"data_range": "nan"}, {"data_range": "0"}, {"data_range": "abc"},
                          {"kind": "segmentation", "threshold": "inf"}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.job(**overrides)

    def test_output_extension_and_existing_file_protection(self):
        existing = self.base / "history.json"
        existing.write_text("old", encoding="utf-8")
        for output in (str(existing), str(self.original), "relative.json"):
            with self.assertRaises(ValueError):
                self.job(output=output)
        self.assertEqual(existing.read_text(), "old")

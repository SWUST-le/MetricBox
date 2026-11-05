import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

from metricbox.config import APP_DIR
from metricbox.metrics.core import (quality_metrics, segmentation_metrics,
                                    classification_metrics, fusion_metrics)


class MetricFormulaTests(unittest.TestCase):
    def test_quality_known_constant_difference(self):
        result = quality_metrics(np.zeros((16, 16)), np.full((16, 16), 10))
        self.assertEqual(result["MAE"], 10)
        self.assertEqual(result["MSE"], 100)
        self.assertEqual(result["RMSE"], 10)
        self.assertAlmostEqual(result["PSNR"], 28.1308036086791)
        self.assertAlmostEqual(result["SSIM"], 2.55 ** 2 / (100 + 2.55 ** 2))

    def test_identical_rgb_and_normalized_range(self):
        image = np.random.default_rng(42).random((17, 18, 3))
        result = quality_metrics(image, image, data_range=1)
        self.assertEqual(result["SSIM"], 1)
        self.assertTrue(math.isinf(result["PSNR"]))
        self.assertEqual(result["MSE"], 0)
        with self.assertRaises(ValueError):
            quality_metrics(image[:5], image[:5], data_range=1)
        with self.assertRaises(ValueError):
            quality_metrics(image, image[:16], data_range=1)
        with self.assertRaises(ValueError):
            quality_metrics(image * 255, image, data_range=1)

    def test_binary_confusion_and_empty_conventions(self):
        result = segmentation_metrics([[1, 1], [0, 0]], [[1, 0], [1, 0]], 0.5)
        self.assertAlmostEqual(result["IoU"], 1 / 3)
        for key in ("Dice", "Precision", "Recall", "F1", "Specificity", "Accuracy"):
            self.assertEqual(result[key], 0.5)
        self.assertEqual([result[k] for k in ("TP", "FP", "FN", "TN")], [1, 1, 1, 1])
        empty = segmentation_metrics(np.zeros((2, 2)), np.zeros((2, 2)))
        self.assertEqual(empty["IoU"], 1)
        self.assertEqual(empty["Dice"], 1)
        self.assertEqual(empty["Precision"], 0)
        self.assertEqual(empty["F1"], 0)

    def test_multiclass_averages_and_confusion_orientation(self):
        result = classification_metrics([0, 1, 1, 2], [0, 1, 2, 2])
        self.assertEqual(result["Accuracy"], 0.75)
        self.assertEqual(result["confusion_matrix"], [[1, 0, 0], [0, 1, 0], [0, 1, 1]])
        self.assertAlmostEqual(result["macro"]["F1"], 7 / 9)
        self.assertAlmostEqual(result["weighted"]["F1"], 0.75)
        self.assertEqual(result["micro"]["F1"], 0.75)
        result = classification_metrics(["a", "a"], ["b", "b"])
        self.assertEqual(result["macro"]["F1"], 0)
        for pred, target in (([], []), ([1], ["1"]), ([[1]], [[1]]), ([0.5], [0.5])):
            with self.assertRaises(ValueError):
                classification_metrics(pred, target)

    def test_fusion_known_histogram_and_differences(self):
        result = fusion_metrics([[0, 255], [255, 0]])
        self.assertEqual(result["EN"], 1)
        self.assertEqual(result["SD"], 127.5)
        self.assertAlmostEqual(result["SF"], 255 * math.sqrt(2))
        self.assertEqual(fusion_metrics(np.full((3, 3), 128)), {"EN": 0, "SD": 0, "SF": 0})


class MetricCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="指标 CLI ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def run_script(self, kind, *args, success=True):
        result = subprocess.run([sys.executable, str(APP_DIR / "builtin_scripts" / f"{kind}.py"), *map(str, args)],
                                cwd=self.base, capture_output=True, encoding="utf-8", errors="replace",
                                env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}, timeout=30)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        return result

    def test_all_demos_real_subprocess_from_other_directory(self):
        for kind in ("quality", "segmentation", "classification", "fusion"):
            with self.subTest(kind=kind):
                result = self.run_script(kind, "--demo")
                self.assertTrue(result["demo"])
                self.assertEqual(result["count"], 1)

    def test_real_images_directory_pairing_and_json_export(self):
        pred, target = self.base / "预测", self.base / "真值"
        pred.mkdir()
        target.mkdir()
        for index in range(2):
            Image.fromarray(np.full((16, 16), 10 * index, dtype=np.uint8)).save(pred / f"{index}.png")
            Image.fromarray(np.zeros((16, 16), dtype=np.uint8)).save(target / f"{index}.png")
        output = self.base / "结果" / "指标.json"
        result = self.run_script("quality", "--pred", pred, "--target", target, "--output", output)
        self.assertFalse(result["demo"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["mean_per_image"]["MSE"], 50)
        self.assertEqual(result["results"][0]["metrics"]["PSNR"], "Infinity")
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)
        (target / "1.png").rename(target / "unmatched.png")
        failed = self.run_script("quality", "--pred", pred, "--target", target, success=False)
        self.assertIn("不匹配", failed.stderr)

    def test_real_classification_and_input_protection(self):
        pred, target = self.base / "pred.json", self.base / "target.json"
        pred.write_text('["cat", "dog", "cat"]', encoding="utf-8")
        target.write_text('["cat", "dog", "dog"]', encoding="utf-8")
        result = self.run_script("classification", "--pred", pred, "--target", target)
        self.assertAlmostEqual(result["results"][0]["metrics"]["Accuracy"], 2 / 3)
        self.run_script("classification", "--pred", pred, "--target", target, "--output", pred, success=False)
        self.assertEqual(json.loads(pred.read_text()), ["cat", "dog", "cat"])
        self.run_script("classification", "--demo", "--pred", pred, "--target", target, success=False)
        self.run_script("classification", success=False)

    def test_real_mask_threshold_and_fusion_image(self):
        path = self.base / "mask.png"
        Image.fromarray(np.array([[0, 1], [1, 0]], dtype=np.uint8)).save(path)
        result = self.run_script("segmentation", "--pred", path, "--target", path, "--threshold", "0.5")
        self.assertEqual(result["results"][0]["metrics"]["TP"], 2)
        result = self.run_script("fusion", "--image", path)
        self.assertEqual(result["results"][0]["metrics"]["EN"], 1)


if __name__ == "__main__":
    unittest.main()

"""Application defaults; no machine-specific paths are stored in source."""

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("METRICBOX_DATA_DIR", str(APP_DIR / "data")))
REGISTRY_PATH = DATA_DIR / "scripts.json"
DEFAULT_CATEGORIES = ("图像融合", "目标检测", "图像分割", "图像质量", "分类评估", "其他")


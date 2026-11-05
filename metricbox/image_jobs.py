"""Translate image form values into an isolated, real-data metric job."""

from dataclasses import dataclass, replace
from datetime import datetime
import math
from pathlib import Path
import uuid

from .builtin_catalog import builtin_entries
from .models import ScriptEntry


@dataclass
class ImageJob:
    entry: ScriptEntry
    output: Path


def prepare_image_job(kind, original, processed, output, threshold, data_range,
                      result_dir, template=None):
    if kind not in ("quality", "segmentation", "fusion"):
        raise ValueError("请选择支持的图像指标")

    def input_path(value, label):
        if not value.strip():
            raise ValueError(f"请选择或填写{label}路径")
        path = Path(value.strip()).expanduser()
        if not path.is_absolute():
            raise ValueError(f"{label}请填写绝对路径，或使用选择按钮")
        path = path.resolve()
        if not path.is_file() and not path.is_dir():
            raise ValueError(f"{label}不存在：{path}")
        return path

    prediction = input_path(processed, "处理后图像")
    reference = None if kind == "fusion" else input_path(original, "原始图像 / 真值")
    if reference and prediction.is_dir() != reference.is_dir():
        raise ValueError("原始图像与处理后图像必须同时选择单张图片，或同时选择目录")
    if output.strip():
        destination = Path(output.strip()).expanduser()
        if not destination.is_absolute():
            raise ValueError("结果文件请填写绝对路径，或使用选择按钮")
        if destination.suffix.lower() != ".json":
            raise ValueError("结果文件须使用 .json 扩展名")
        destination = destination.resolve()
    else:
        name = f"{kind}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.json"
        destination = Path(result_dir).resolve() / name
    if destination in (prediction, reference) or destination.is_dir():
        raise ValueError("结果文件不能覆盖输入文件或目录")
    if destination.exists():
        raise ValueError("结果文件已存在，请选择新文件名，避免覆盖历史结果")
    arguments = ["--image", str(prediction)] if kind == "fusion" else [
        "--pred", str(prediction), "--target", str(reference)]
    if kind in ("quality", "segmentation"):
        label, value = ("动态范围", data_range) if kind == "quality" else ("掩膜阈值", threshold)
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label}须为有效数值") from exc
        if not math.isfinite(number) or (kind == "quality" and number <= 0):
            raise ValueError(f"{label}须为有限数值，且动态范围须大于零")
        arguments += ["--data-range" if kind == "quality" else "--threshold", str(number)]
    arguments += ["--output", str(destination)]
    default = next(entry for entry in builtin_entries() if Path(entry.path).stem == kind)
    return ImageJob(replace(template or default, arguments=arguments), destination)

"""Shared CLI for bundled metric scripts; single-file or strict folder pairing."""

import argparse
import json
import math
from pathlib import Path


def json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def image_files(path):
    if not path.exists():
        raise ValueError(f"输入不存在：{path}")
    if path.is_file():
        return {path.name: path}
    files = {str(item.relative_to(path)): item for item in sorted(path.rglob("*"))
             if item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}}
    if not files:
        raise ValueError(f"目录中没有支持的图像：{path}")
    return files


def main(kind, argv=None):
    parser = argparse.ArgumentParser(description=f"MetricBox 内置指标：{kind}（默认不运行演示，须显式 --demo）")
    parser.add_argument("--demo", action="store_true", help="使用内存中的演示数据，不代表真实评估")
    parser.add_argument("--output", type=Path, help="保存 JSON 结果")
    if kind == "fusion":
        parser.add_argument("--image", type=Path, help="8 位灰度融合图或目录")
    else:
        parser.add_argument("--pred", type=Path, help="预测图/目录，分类时为 JSON 标签文件")
        parser.add_argument("--target", type=Path, help="真值图/目录，分类时为 JSON 标签文件")
    if kind == "quality":
        parser.add_argument("--data-range", type=float, default=255.0, help="像素动态范围，默认 255，不自动归一化")
    if kind == "segmentation":
        parser.add_argument("--threshold", type=float, default=127.0, help="像素值严格大于阈值为前景；0/1 掩膜请设为 0.5")
    args = parser.parse_args(argv)
    inputs = [getattr(args, key, None) for key in ("pred", "target", "image")]
    if args.demo and any(inputs):
        parser.error("--demo 不能与真实数据输入同时使用，请移除 --demo")
    if not args.demo and (not args.image if kind == "fusion" else not args.pred or not args.target):
        parser.error("请选择输入文件，或显式使用 --demo 运行演示")
    try:
        import numpy as np
        from PIL import Image
        from .core import quality_metrics, segmentation_metrics, classification_metrics, fusion_metrics

        def load(path):
            with Image.open(path) as image:
                if image.mode not in ("L", "RGB"):
                    raise ValueError(f"仅接受 8 位 L/RGB 图像，请先显式转换：{path}（{image.mode}）")
                return np.array(image)

        records = []
        used_paths = []
        if kind == "classification":
            if args.demo:
                pred, target = [0, 1, 1, 2], [0, 1, 2, 2]
            else:
                used_paths = [args.pred, args.target]
                pred = json.loads(args.pred.read_text(encoding="utf-8-sig"))
                target = json.loads(args.target.read_text(encoding="utf-8-sig"))
            metrics = classification_metrics(pred, target)
            records.append({"name": "labels", "metrics": metrics})
        else:
            if args.demo:
                target = np.arange(256, dtype=np.uint8).reshape(16, 16)
                pred = np.clip(target.astype(float) + 5, 0, 255).astype(np.uint8)
                pairs = [("演示数据", pred, target)]
            elif kind == "fusion":
                images = image_files(args.image)
                used_paths = list(images.values())
                pairs = ((name, load(path), None) for name, path in images.items())
            else:
                predictions, targets = image_files(args.pred), image_files(args.target)
                if args.pred.is_file() and args.target.is_file():
                    paired_paths = [(args.pred.name, args.pred, args.target)]
                elif args.pred.is_dir() and args.target.is_dir():
                    if predictions.keys() != targets.keys():
                        missing = sorted(predictions.keys() ^ targets.keys())
                        raise ValueError(f"目录须按相同相对文件名严格配对；不匹配：{missing[:5]}")
                    paired_paths = [(name, path, targets[name]) for name, path in predictions.items()]
                else:
                    raise ValueError("预测与真值必须同时为文件，或同时为目录")
                used_paths = [path for _, p, t in paired_paths for path in (p, t)]
                pairs = ((name, load(p), load(t)) for name, p, t in paired_paths)
            for name, pred, target in pairs:
                if kind == "quality":
                    metrics = quality_metrics(pred, target, args.data_range)
                elif kind == "segmentation":
                    metrics = segmentation_metrics(pred, target, args.threshold)
                else:
                    metrics = fusion_metrics(pred)
                records.append({"name": name, "metrics": metrics})
        result = {"task": kind, "demo": args.demo, "count": len(records), "results": records}
        if kind != "classification":
            keys = [key for key in records[0]["metrics"] if key not in ("TP", "FP", "FN", "TN")]
            result["mean_per_image"] = {key: float(np.mean([row["metrics"][key] for row in records])) for key in keys}
        result["settings"] = {key: getattr(args, key) for key in ("data_range", "threshold") if hasattr(args, key)}
        text = json.dumps(json_safe(result), ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            if args.output.resolve() in {path.resolve() for path in used_paths}:
                raise ValueError("结果文件不能覆盖输入文件")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
        print(text, flush=True)
    except ImportError as exc:
        parser.error(f"缺少指标依赖，请在所选 Python 环境安装：python -m pip install -r requirements-metrics.txt（{exc}）")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

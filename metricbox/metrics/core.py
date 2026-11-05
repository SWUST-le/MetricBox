"""Explicit metric conventions; float64 arithmetic, no implicit rescaling."""

import math
import numpy as np


def image_array(image):
    result = np.asarray(image, dtype=np.float64)
    if result.ndim not in (2, 3) or result.size == 0 or not np.isfinite(result).all():
        raise ValueError("图像必须是非空、有限值的 H×W 或 H×W×C 数组")
    return result


def paired(pred, target):
    pred, target = image_array(pred), image_array(target)
    if pred.shape != target.shape:
        raise ValueError(f"预测与真值尺寸不同：{pred.shape} / {target.shape}，请先对齐数据")
    return pred, target


def quality_metrics(pred, target, data_range=255.0):
    pred, target = paired(pred, target)
    if not math.isfinite(data_range) or data_range <= 0:
        raise ValueError("data_range 必须是有限正数")
    if min(pred.min(), target.min()) < 0 or max(pred.max(), target.max()) > data_range:
        raise ValueError("像素值超出 [0, data_range]，请检查动态范围")
    if min(pred.shape[:2]) < 11:
        raise ValueError("SSIM 使用 11×11 窗口，图像的高和宽至少为 11")
    difference = pred - target
    mse = float(np.mean(difference ** 2))
    kernel = np.exp(-np.arange(-5, 6, dtype=float) ** 2 / (2 * 1.5 ** 2))
    kernel /= kernel.sum()

    def smooth(array):
        for axis in (0, 1):
            array = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode="valid"), axis, array)
        return array

    mu_x, mu_y = smooth(pred), smooth(target)
    var_x = np.maximum(smooth(pred * pred) - mu_x ** 2, 0)
    var_y = np.maximum(smooth(target * target) - mu_y ** 2, 0)
    covariance = smooth(pred * target) - mu_x * mu_y
    c1, c2 = (0.01 * data_range) ** 2, (0.03 * data_range) ** 2
    ssim = ((2 * mu_x * mu_y + c1) * (2 * covariance + c2)
            / ((mu_x ** 2 + mu_y ** 2 + c1) * (var_x + var_y + c2)))
    return {"MAE": float(np.mean(np.abs(difference))), "MSE": mse, "RMSE": math.sqrt(mse),
            "PSNR": math.inf if mse == 0 else 10 * math.log10(data_range ** 2 / mse),
            "SSIM": float(ssim.mean())}


def segmentation_metrics(pred, target, threshold=127.0):
    pred, target = paired(pred, target)
    if pred.ndim != 2:
        raise ValueError("二值分割需要单通道掩膜")
    if not math.isfinite(threshold):
        raise ValueError("阈值必须是有限数值")
    pred, target = pred > threshold, target > threshold
    tp = int(np.count_nonzero(pred & target))
    fp = int(np.count_nonzero(pred & ~target))
    fn = int(np.count_nonzero(~pred & target))
    tn = int(np.count_nonzero(~pred & ~target))
    divide = lambda numerator, denominator: numerator / denominator if denominator else 0.0
    return {"IoU": divide(tp, tp + fp + fn) if tp + fp + fn else 1.0,
            "Dice": divide(2 * tp, 2 * tp + fp + fn) if tp + fp + fn else 1.0,
            "Precision": divide(tp, tp + fp), "Recall": divide(tp, tp + fn),
            "F1": divide(2 * tp, 2 * tp + fp + fn), "Specificity": divide(tn, tn + fp),
            "Accuracy": (tp + tn) / pred.size, "TP": tp, "FP": fp, "FN": fn, "TN": tn}


def classification_metrics(pred, target):
    if not isinstance(pred, list) or not isinstance(target, list) or not pred or len(pred) != len(target):
        raise ValueError("预测与真值必须是等长、非空的 JSON 标签列表")
    values = pred + target
    if not (all(type(value) is int for value in values) or all(type(value) is str for value in values)):
        raise ValueError("分类标签须全部为整数，或全部为字符串；不接受概率、嵌套数组或混合类型")
    labels = sorted(set(values))
    indexes = {label: index for index, label in enumerate(labels)}
    confusion = np.zeros((len(labels), len(labels)), dtype=np.int64)
    for p, t in zip(pred, target):
        confusion[indexes[t], indexes[p]] += 1
    tp = np.diag(confusion).astype(float)
    support, predicted = confusion.sum(axis=1), confusion.sum(axis=0)
    precision = np.divide(tp, predicted, out=np.zeros_like(tp), where=predicted != 0)
    recall = np.divide(tp, support, out=np.zeros_like(tp), where=support != 0)
    f1 = np.divide(2 * tp, support + predicted, out=np.zeros_like(tp), where=support + predicted != 0)
    accuracy = float(tp.sum() / len(pred))
    return {"Accuracy": accuracy, "labels": labels, "confusion_matrix": confusion.tolist(),
            "per_class": [{"label": label, "Precision": float(precision[i]), "Recall": float(recall[i]),
                           "F1": float(f1[i]), "support": int(support[i])} for i, label in enumerate(labels)],
            "macro": {"Precision": float(precision.mean()), "Recall": float(recall.mean()), "F1": float(f1.mean())},
            "weighted": {"Precision": float(precision @ support / len(pred)),
                         "Recall": float(recall @ support / len(pred)), "F1": float(f1 @ support / len(pred))},
            "micro": {"Precision": accuracy, "Recall": accuracy, "F1": accuracy}}


def fusion_metrics(image):
    image = image_array(image)
    if image.ndim != 2 or min(image.shape) < 2:
        raise ValueError("EN、SD、SF 需要至少 2×2 的灰度图")
    if image.min() < 0 or image.max() > 255 or not np.equal(image, np.floor(image)).all():
        raise ValueError("融合指标使用 0–255 的 8 位灰度值")
    counts = np.bincount(image.astype(np.uint8).ravel(), minlength=256)
    probabilities = counts[counts > 0] / image.size
    rf = float(np.mean(np.diff(image, axis=1) ** 2))
    cf = float(np.mean(np.diff(image, axis=0) ** 2))
    return {"EN": float(-np.sum(probabilities * np.log2(probabilities))),
            "SD": float(np.std(image, ddof=0)), "SF": math.sqrt(rf + cf)}

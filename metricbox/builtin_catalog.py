"""Catalog metadata stays independent of NumPy/Pillow and the Tk UI."""

from .config import APP_DIR
from .models import ScriptEntry


def builtin_entries():
    definitions = [
        ("quality", "图像质量：MAE / MSE / RMSE / PSNR / SSIM", "图像质量", ["MAE", "MSE", "RMSE", "PSNR", "SSIM"],
         '配对图像或目录。真实数据参数：["--pred", "预测路径", "--target", "真值路径"]。SSIM 使用 11×11 高斯窗口，RGB 按通道平均；默认动态范围 255。'),
        ("segmentation", "二值分割：IoU / Dice / Precision / Recall", "图像分割", ["IoU", "Dice", "Precision", "Recall", "F1", "Specificity", "Accuracy"],
         '灰度掩膜或配对目录。参数：["--pred", "预测路径", "--target", "真值路径", "--threshold", "127"]。0/1 掩膜改用阈值 0.5；仅评估前景类。'),
        ("classification", "分类评估：Accuracy / Precision / Recall / F1", "分类评估", ["Accuracy", "Precision", "Recall", "F1", "混淆矩阵"],
         'JSON 标签列表（如 [0, 1, 2]），支持多类。参数：["--pred", "pred.json", "--target", "target.json"]。输出逐类、macro、micro、weighted 指标。'),
        ("fusion", "融合图像：EN / SD / SF", "图像融合", ["EN", "SD", "SF"],
         '单张或目录中的 8 位灰度融合图。参数：["--image", "融合结果路径"]。EN 使用 256 bins，SD 使用总体标准差，SF 使用相邻差分均方。'),
    ]
    return [ScriptEntry(name=name, path=str(APP_DIR / "builtin_scripts" / f"{key}.py"), category=category,
                        tags=tags, description=description + '\n初始参数 --demo 仅演示。评估真实数据时须替换全部参数；可加 --output 保存 JSON。需要 NumPy、Pillow。',
                        arguments=["--demo"], working_dir=str(APP_DIR))
            for key, name, category, tags, description in definitions]

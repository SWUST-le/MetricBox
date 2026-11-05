"""Portable application XLSX exporter. Loaded only when Excel output is requested."""

import math
import os
from pathlib import Path
import tempfile


def write_xlsx(result, destination):
    from openpyxl import Workbook
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    book = Workbook()
    book.remove(book.active)

    def sheet(name, rows, header_row=1):
        page = book.create_sheet(name)
        page.sheet_view.showGridLines = False
        for row in rows:
            for value in row:
                if isinstance(value, str) and (len(value) > 32767 or ILLEGAL_CHARACTERS_RE.search(value)):
                    raise ValueError("表格文本超出 Excel 限制或包含不支持的控制字符")
            page.append(row)
        for row in page:
            for cell in row:
                value = cell.value
                if isinstance(value, float) and not math.isfinite(value):
                    cell.value = "Infinity" if value > 0 else "-Infinity"
                if isinstance(cell.value, str):
                    if len(cell.value) > 32767 or ILLEGAL_CHARACTERS_RE.search(cell.value):
                        raise ValueError("表格文本超出 Excel 限制或包含不支持的控制字符")
                    # Labels and filenames are always data, even if they start with '='.
                    cell.data_type = "s"
                cell.font = Font(name="Microsoft YaHei", size=10, color="1B2940")
                cell.alignment = Alignment(vertical="center", horizontal="right" if cell.data_type == "n" else "left", wrap_text=True)
                if isinstance(cell.value, float):
                    cell.number_format = "0.000000"
                elif isinstance(cell.value, int) and not isinstance(cell.value, bool):
                    cell.number_format = "#,##0"
        for cell in page[header_row]:
            cell.fill = PatternFill("solid", fgColor="294477")
            cell.font = Font(name="Microsoft YaHei", size=10, bold=True, color="FFFFFF")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        page.row_dimensions[header_row].height = 26
        for column in range(1, page.max_column + 1):
            width = max((sum(2 if ord(ch) > 127 else 1 for ch in str(page.cell(row, column).value or ""))
                         for row in range(header_row, page.max_row + 1)), default=12)
            page.column_dimensions[get_column_letter(column)].width = min(65, max(16, width + 3))
        for row in range(header_row + 1, page.max_row + 1):
            line_count = max((math.ceil(sum(2 if ord(ch) > 127 else 1 for ch in str(cell.value or "")) /
                                        page.column_dimensions[cell.column_letter].width) for cell in page[row]), default=1)
            page.row_dimensions[row].height = max(23, min(120, 17 * line_count))
        if name != "汇总":
            page.freeze_panes = "B2"
            page.auto_filter.ref = page.dimensions
        return page

    summary = [["类别", "项目", "值"], ["任务", "task", result["task"]],
               ["任务", "演示数据", result["demo"]], ["任务", "记录数", result["count"]]]
    if "mean_per_image" in result:
        summary += [["逐图等权平均", key, value] for key, value in result["mean_per_image"].items()]
    else:
        metrics = result["results"][0]["metrics"]
        summary.append(["分类汇总", "Accuracy", metrics["Accuracy"]])
        for method in ("macro", "weighted", "micro"):
            summary += [[method, key, value] for key, value in metrics[method].items()]
    summary += [["输入", key, value] for key, value in result.get("inputs", {}).items()]
    summary += [["计算参数", key, value] for key, value in result.get("settings", {}).items()]
    summary += [["说明", "汇总口径", "图像指标为逐图等权平均；不是合并全部像素后的全局指标。"],
                ["说明", "Infinity", "正无穷，例如相同图像的 PSNR；按文本保留，不替换成零。"],
                ["说明", "结果类型", "本次计算的静态数值，不含随单元格变化而重新计算的公式。"]]
    sheet("汇总", summary)
    if result["task"] == "classification":
        metrics = result["results"][0]["metrics"]
        sheet("逐类指标", [["类别", "Precision", "Recall", "F1", "support"]] +
              [[row[key] for key in ("label", "Precision", "Recall", "F1", "support")] for row in metrics["per_class"]])
        sheet("混淆矩阵", [["真值 / 预测", *metrics["labels"]]] +
              [[label, *values] for label, values in zip(metrics["labels"], metrics["confusion_matrix"])])
    else:
        keys = list(result["results"][0]["metrics"])
        sheet("逐图明细", [["图像文件", *keys]] +
              [[record["name"], *[record["metrics"][key] for key in keys]] for record in result["results"]])
    destination = Path(destination)
    temporary = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".xlsx", delete=False) as handle:
            temporary = Path(handle.name)
        book.save(temporary)
        os.replace(temporary, destination)
    finally:
        book.close()
        if temporary and temporary.exists():
            temporary.unlink()

"""Scrollable image input form, independent of persistence and execution."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from .theme import PANEL, MUTED


class ImageInputPanel(ttk.Frame):
    TASKS = {"图像质量（原图与处理图对比）": "quality",
             "二值分割（真值与预测掩膜）": "segmentation",
             "融合图像统计（EN / SD / SF）": "fusion"}

    def __init__(self, parent, on_run):
        super().__init__(parent, style="Panel.TFrame")
        self.task = tk.StringVar(value=next(iter(self.TASKS)))
        self.original = tk.StringVar()
        self.processed = tk.StringVar()
        self.output = tk.StringVar()
        self.output_format = tk.StringVar(value="xlsx")
        self.threshold = tk.StringVar(value="127")
        self.data_range = tk.StringVar(value="255")
        self.hint = tk.StringVar()
        canvas = tk.Canvas(self, background=PANEL, highlightthickness=0)
        scroll = ttk.Scrollbar(self, command=canvas.yview)
        scroll.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(fill="both", expand=True)
        form = ttk.Frame(canvas, style="Panel.TFrame", padding=(12, 10))
        form.columnconfigure(1, weight=1)
        window = canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        form.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))

        ttk.Label(form, text="计算指标", style="Panel.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12))
        task_box = ttk.Combobox(form, textvariable=self.task, values=list(self.TASKS), state="readonly")
        task_box.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        self.run_button = ttk.Button(form, text="开始计算", style="Primary.TButton", command=on_run)
        self.run_button.grid(row=0, column=2, columnspan=2, sticky="ew", padx=(6, 0), pady=(0, 6))
        self.original_controls = self._input_row(form, 1, "原始图像 / 参考图", self.original)
        self.original_label = self.original_controls[0]
        self._input_row(form, 2, "处理后图像", self.processed)
        ttk.Label(form, text="结果文件（可选）", style="Panel.TLabel").grid(row=3, column=0, sticky="w", padx=(0, 12))
        ttk.Entry(form, textvariable=self.output).grid(row=3, column=1, sticky="ew", pady=3)
        ttk.Button(form, text="保存到…", command=self.browse_output).grid(row=3, column=2, columnspan=2, sticky="ew", padx=(6, 0))
        options = ttk.Frame(form, style="Panel.TFrame")
        options.grid(row=4, column=0, columnspan=4, sticky="ew", pady=5)
        ttk.Label(options, text="动态范围", style="Panel.TLabel").pack(side="left")
        self.range_input = ttk.Entry(options, textvariable=self.data_range, width=8)
        self.range_input.pack(side="left", padx=(8, 18))
        ttk.Label(options, text="掩膜阈值", style="Panel.TLabel").pack(side="left")
        self.threshold_input = ttk.Entry(options, textvariable=self.threshold, width=8)
        self.threshold_input.pack(side="left", padx=8)
        ttk.Label(options, text="输出格式", style="Panel.TLabel").pack(side="left", padx=(12, 0))
        format_box = ttk.Combobox(options, textvariable=self.output_format, values=["xlsx", "json"], width=7, state="readonly")
        format_box.pack(side="left", padx=8)
        format_box.bind("<<ComboboxSelected>>", self.change_output_format)
        self.output.trace_add("write", lambda *args: self.sync_output_format())
        hint = ttk.Label(form, textvariable=self.hint, background=PANEL, foreground=MUTED, wraplength=650)
        hint.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(2, 0))
        canvas.bind("<Configure>", lambda event: (canvas.itemconfigure(window, width=event.width),
                                                   hint.configure(wraplength=max(200, event.width - 35))))
        self.task.trace_add("write", lambda *args: self.update_task())
        self.update_task()

    @property
    def kind(self):
        return self.TASKS[self.task.get()]

    def _input_row(self, parent, row, label, variable):
        title = ttk.Label(parent, text=label, style="Panel.TLabel")
        title.grid(row=row, column=0, sticky="w", padx=(0, 12))
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=3)
        file_button = ttk.Button(parent, text="图片…", command=lambda: self.browse_image(variable))
        file_button.grid(row=row, column=2, padx=(6, 0))
        directory_button = ttk.Button(parent, text="目录…", command=lambda: self.browse_directory(variable))
        directory_button.grid(row=row, column=3, padx=(6, 0))
        return title, entry, file_button, directory_button

    def browse_image(self, variable):
        path = filedialog.askopenfilename(parent=self, title="选择图像", filetypes=[
            ("图像文件", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"), ("所有文件", "*.*")])
        if path:
            variable.set(path)

    def browse_directory(self, variable):
        path = filedialog.askdirectory(parent=self, title="选择图像目录")
        if path:
            variable.set(path)

    def browse_output(self):
        types = [("Excel 工作簿", "*.xlsx"), ("JSON 结果", "*.json")]
        if self.output_format.get() == "json":
            types.reverse()
        path = filedialog.asksaveasfilename(parent=self, title="选择结果文件路径", defaultextension="." + self.output_format.get(),
                                            filetypes=types)
        if path:
            self.output.set(path)

    def sync_output_format(self):
        suffix = Path(self.output.get()).suffix.lower()
        if suffix in (".xlsx", ".json"):
            self.output_format.set(suffix[1:])

    def change_output_format(self, event=None):
        if self.output.get().strip():
            self.output.set(str(Path(self.output.get()).with_suffix("." + self.output_format.get())))

    def update_task(self):
        kind = self.kind
        for widget in self.original_controls[1:]:
            widget.configure(state="disabled" if kind == "fusion" else "normal")
        self.original_label.configure(text="原始图像（无需填写）" if kind == "fusion" else
                                      "原始图像 / 真值掩膜" if kind == "segmentation" else "原始图像 / 参考图")
        self.range_input.configure(state="normal" if kind == "quality" else "disabled")
        self.threshold_input.configure(state="normal" if kind == "segmentation" else "disabled")
        self.hint.set({
            "quality": "选择单张图或配对目录。原图作为参考，处理图作为预测；尺寸需一致，SSIM 至少 11×11。结果路径留空时自动保存到 data/results。",
            "segmentation": "原始输入应为真值掩膜，处理后输入为预测掩膜，均需灰度图。0/255 掩膜阈值用 127；0/1 掩膜用 0.5。",
            "fusion": "仅使用处理后的 8 位灰度融合图或目录，计算 EN、SD、SF；原始图像路径不参与该计算。",
        }[kind])

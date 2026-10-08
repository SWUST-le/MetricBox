"""Modal editor for a script registration; browsing never executes a file."""

from dataclasses import replace
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..config import DEFAULT_CATEGORIES
from ..models import ScriptEntry, now_iso
from ..runner import parse_arguments
from .theme import BG, MUTED, TEXT


class ScriptDialog(tk.Toplevel):
    def __init__(self, parent, on_save, entry: ScriptEntry | None = None, categories=()):
        super().__init__(parent)
        self.entry = entry
        self.on_save = on_save
        self.title("编辑脚本" if entry else "添加已有脚本")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.geometry("720x740")
        self.minsize(620, 630)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.values = {key: tk.StringVar(value=value) for key, value in {
            "name": entry.name if entry else "",
            "path": entry.path if entry else "",
            "category": entry.category if entry else "其他",
            "tags": ", ".join(entry.tags) if entry else "",
            "interpreter": entry.interpreter if entry else "",
            "working_dir": entry.working_dir if entry else "",
        }.items()}

        outer = ttk.Frame(self, padding=24)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="编辑脚本配置" if entry else "把已有脚本加入工具箱",
                  font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
        ttk.Label(outer, text="保留原文件位置；保存配置后，可在脚本库中统一管理。",
                  style="Muted.TLabel").pack(anchor="w", pady=(6, 18))

        # A scrollable form also fits smaller laptop displays.
        canvas = tk.Canvas(outer, background=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        footer = ttk.Frame(outer)
        footer.pack(side="bottom", fill="x", pady=(18, 0))
        ttk.Button(footer, text="取消", command=self.destroy).pack(side="right")
        self.save_button = ttk.Button(footer, text="保存脚本", style="Primary.TButton", command=self.save)
        self.save_button.pack(side="right", padx=(0, 10))
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        form = ttk.Frame(canvas, padding=(0, 0, 12, 0))
        window_id = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        form.columnconfigure(0, weight=1)

        self._field(form, 0, "脚本文件 *", "path", self.browse_script, "选择文件")
        self.name_input = self._field(form, 1, "显示名称 *", "name")
        row = ttk.Frame(form)
        row.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)
        for col, label in enumerate(("分类（可直接输入新分类）", "指标 / 标签（逗号分隔）")):
            ttk.Label(row, text=label).grid(row=0, column=col, sticky="w", pady=(0, 6))
        categories = sorted(set(DEFAULT_CATEGORIES) | set(categories))
        ttk.Combobox(row, textvariable=self.values["category"], values=categories).grid(
            row=1, column=0, sticky="ew", padx=(0, 12))
        ttk.Entry(row, textvariable=self.values["tags"]).grid(row=1, column=1, sticky="ew")

        ttk.Label(form, text="用途说明").grid(row=3, column=0, sticky="w", pady=(0, 6))
        self.description = tk.Text(form, height=3, wrap="word", relief="solid", borderwidth=1,
                                   background="white", foreground=TEXT, highlightthickness=0)
        self.description.grid(row=4, column=0, sticky="ew", pady=(0, 16))
        if entry:
            self.description.insert("1.0", entry.description)
        ttk.Separator(form).grid(row=5, column=0, sticky="ew", pady=(0, 14))
        ttk.Label(form, text="运行配置", font=("Microsoft YaHei UI", 12, "bold")).grid(
            row=6, column=0, sticky="w", pady=(0, 12))
        self._field(form, 7, "Python 解释器（留空使用当前环境）", "interpreter", self.browse_interpreter, "选择")
        ttk.Label(form, text=f"当前环境：{sys.executable}", foreground=MUTED, wraplength=570).grid(
            row=8, column=0, sticky="w", pady=(0, 12))
        self._field(form, 9, "工作目录（留空使用脚本所在目录）", "working_dir", self.browse_directory, "选择")
        ttk.Label(form, text="命令行参数（JSON 字符串数组）").grid(row=10, column=0, sticky="w", pady=(0, 6))
        self.arguments = tk.Text(form, height=3, wrap="word", relief="solid", borderwidth=1,
                                 background="white", foreground=TEXT, highlightthickness=0)
        self.arguments.grid(row=11, column=0, sticky="ew")
        self.arguments.insert("1.0", json.dumps(entry.arguments if entry else [], ensure_ascii=False))
        ttk.Label(form, text='示例：["--input", "E:/数据集", "--batch-size", "8"]',
                  foreground=MUTED).grid(row=12, column=0, sticky="w", pady=(6, 0))
        self.bind("<Escape>", lambda event: self.destroy())
        self.bind("<Control-Return>", lambda event: self.save())
        self.update_idletasks()
        x = max(0, parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2)
        y = max(0, parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.name_input.focus_set()

    def _field(self, parent, row, label, key, browse=None, browse_label="浏览"):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text=label).grid(row=0, column=0, sticky="w", pady=(0, 6))
        widget = ttk.Entry(frame, textvariable=self.values[key])
        widget.grid(row=1, column=0, sticky="ew")
        if browse:
            ttk.Button(frame, text=browse_label, command=browse).grid(row=1, column=1, padx=(8, 0))
        return widget

    def browse_script(self):
        path = filedialog.askopenfilename(parent=self, title="选择已有指标脚本", filetypes=[
            ("Python 脚本", "*.py *.pyw"), ("脚本文件", "*.py *.pyw *.m *.sh *.bat *.ps1"), ("所有文件", "*.*")])
        if path:
            self.values["path"].set(path)
            if not self.values["name"].get().strip():
                self.values["name"].set(Path(path).stem)

    def browse_interpreter(self):
        path = filedialog.askopenfilename(parent=self, title="选择 Python 解释器",
                                           filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")])
        if path:
            self.values["interpreter"].set(path)

    def browse_directory(self):
        path = filedialog.askdirectory(parent=self, title="选择脚本工作目录")
        if path:
            self.values["working_dir"].set(path)

    def save(self):
        try:
            values = {key: value.get().strip() for key, value in self.values.items()}
            if not values["name"] or not values["path"]:
                raise ValueError("请填写显示名称并选择脚本文件")
            script = Path(values["path"]).expanduser().resolve()
            if not script.is_file():
                raise ValueError("所选脚本文件不存在")
            if values["working_dir"] and not Path(values["working_dir"]).is_dir():
                raise ValueError("工作目录不存在")
            values["path"] = str(script)
            values["category"] = values["category"] or "其他"
            values["tags"] = list(dict.fromkeys(tag.strip() for tag in values["tags"].replace("，", ",").split(",") if tag.strip()))
            values["arguments"] = parse_arguments(self.arguments.get("1.0", "end-1c"))
            values["description"] = self.description.get("1.0", "end-1c").strip()
            values["updated_at"] = now_iso()
            entry = replace(self.entry, **values) if self.entry else ScriptEntry(**values)
            self.on_save(entry)
        except (ValueError, OSError) as exc:
            messagebox.showerror("无法保存", str(exc), parent=self)
            return
        self.destroy()


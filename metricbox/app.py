"""Desktop shell. UI delegates persistence and execution to separate services."""

import json
import os
from pathlib import Path
import queue
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .builtin_catalog import builtin_entries
from .config import REGISTRY_PATH
from .image_jobs import prepare_image_job
from .models import ScriptEntry
from .runner import ScriptRunner
from .storage import ScriptStore, StorageError
from .ui.script_dialog import ScriptDialog
from .ui.image_panel import ImageInputPanel
from .ui import theme


class MetricBoxApp:
    def __init__(self, root: tk.Tk, registry_path: Path = REGISTRY_PATH):
        self.root = root
        self.store = ScriptStore(registry_path)
        self.runner = ScriptRunner()
        self.selected_id: str | None = None
        self.active_entry: ScriptEntry | None = None
        self.category = "全部脚本"
        self._read_only = False
        self._closing = False
        self._terminal_event = None
        self._poll_id = None
        self._image_output = None
        root.title("MetricBox · 深度学习指标工具箱")
        root.geometry("1240x850")
        root.minsize(1000, 720)
        theme.configure(root)
        try:
            self.store.load()
        except StorageError as exc:
            # A corrupt registry must never be silently overwritten by an empty list.
            self._read_only = True
            messagebox.showerror("脚本库读取失败", f"{exc}\n\n本次以只读模式打开，请修复脚本库后重新启动。", parent=root)
        self._build()
        self.refresh()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Control-n>", lambda event: self.add_script())
        root.bind("<Control-f>", lambda event: self.search_input.focus_set())
        self._poll_id = root.after(100, self.poll_runner)

    def _build(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.sidebar = tk.Frame(self.root, bg=theme.NAV, width=204)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        tk.Label(self.sidebar, text="M  MetricBox", bg=theme.NAV, fg="white",
                 font=("Segoe UI", 21, "bold")).pack(anchor="w", padx=22, pady=(30, 5))
        tk.Label(self.sidebar, text="深度学习指标工具箱", bg=theme.NAV, fg="#98A9C6",
                 font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=24, pady=(0, 30))
        tk.Label(self.sidebar, text="工作空间", bg=theme.NAV, fg="#8394B2",
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=24, pady=(0, 10))
        self.all_button = self._nav_button("全部脚本", lambda: self.set_category("全部脚本"))
        tk.Label(self.sidebar, text="按任务分类", bg=theme.NAV, fg="#8394B2",
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=24, pady=(24, 8))
        self.category_frame = tk.Frame(self.sidebar, bg=theme.NAV)
        self.category_frame.pack(fill="both", expand=True)
        tk.Label(self.sidebar, text=f"本地工作空间  /  v{__version__}", bg=theme.NAV, fg="#8394B2",
                 font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=22, pady=24)

        main = ttk.Frame(self.root, padding=(28, 24))
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)
        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew")
        title = ttk.Frame(header)
        title.pack(side="left")
        ttk.Label(title, text="指标脚本库", font=("Microsoft YaHei UI", 23, "bold")).pack(anchor="w")
        ttk.Label(title, text="让常用指标脚本有序可查，随时可用。", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        self.add_button = ttk.Button(header, text="＋ 添加已有脚本", style="Primary.TButton", command=self.add_script)
        self.add_button.pack(side="right")

        stats = ttk.Frame(main)
        stats.grid(row=1, column=0, sticky="ew", pady=(22, 18))
        self.stat_vars = [tk.StringVar(value="0"), tk.StringVar(value="0"), tk.StringVar(value="0")]
        for index, (label, subtitle) in enumerate((("已收录脚本", "统一管理你的计算入口"),
                                                  ("任务分类", "按研究任务组织脚本"),
                                                  ("文件可访问", "脚本路径实时检查"))):
            stats.columnconfigure(index, weight=1, uniform="stats")
            card = tk.Frame(stats, bg=theme.PANEL, highlightbackground=theme.LINE, highlightthickness=1)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 6, 0 if index == 2 else 6))
            tk.Label(card, text=label, bg=theme.PANEL, fg=theme.MUTED).pack(anchor="w", padx=18, pady=(12, 0))
            tk.Label(card, textvariable=self.stat_vars[index], bg=theme.PANEL, fg=theme.TEXT,
                     font=("Segoe UI", 25, "bold")).pack(anchor="w", padx=18)
            tk.Label(card, text=subtitle, bg=theme.PANEL, fg=theme.MUTED,
                     font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=18, pady=(0, 12))

        search = ttk.Frame(main)
        search.grid(row=2, column=0, sticky="ew")
        self.search_var = tk.StringVar()
        self.search_input = ttk.Entry(search, textvariable=self.search_var)
        self.search_input.pack(side="left", fill="x", expand=True)
        self.search_var.trace_add("write", lambda *args: self.refresh_table())
        ttk.Button(search, text="刷新", command=self.refresh).pack(side="left", padx=(10, 0))
        self.builtin_button = ttk.Button(search, text="添加常用指标", command=self.add_builtins)
        self.builtin_button.pack(side="left", padx=(10, 0))
        self.filter_var = tk.StringVar(value="全部脚本 · 搜索名称、说明、标签或路径")
        ttk.Label(main, textvariable=self.filter_var, style="Muted.TLabel").grid(
            row=3, column=0, sticky="w", pady=(8, 12))

        split = ttk.Panedwindow(main, orient="vertical")
        split.grid(row=4, column=0, sticky="nsew")
        library = ttk.Frame(split, style="Panel.TFrame")
        library.rowconfigure(0, weight=1)
        library.columnconfigure(0, weight=1)
        split.add(library, weight=3)
        self.tree = ttk.Treeview(library, columns=("name", "category", "tags", "status"), show="headings",
                                 selectmode="browse", height=5)
        for key, title, width in (("name", "脚本名称", 250), ("category", "任务分类", 110),
                                  ("tags", "指标 / 标签", 190), ("status", "文件状态", 100)):
            self.tree.heading(key, text=title, anchor="w")
            self.tree.column(key, width=width, minwidth=80, anchor="w", stretch=key in ("name", "tags"))
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(library, command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", lambda event: self.edit_script())
        self.empty_label = tk.Label(library, text="还没有脚本\n点击右上角“添加已有脚本”开始整理你的指标库",
                                    bg=theme.PANEL, fg=theme.MUTED, justify="center")

        bottom = ttk.Frame(split, padding=(0, 14, 0, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(1, weight=1)
        split.add(bottom, weight=4)
        toolbar = ttk.Frame(bottom)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.detail_title = tk.StringVar(value="脚本详情")
        ttk.Label(toolbar, textvariable=self.detail_title, font=("Microsoft YaHei UI", 12, "bold")).pack(side="left")
        self.run_button = ttk.Button(toolbar, text="运行脚本", style="Primary.TButton", command=self.run_script)
        self.run_button.pack(side="right")
        self.edit_button = ttk.Button(toolbar, text="编辑", command=self.edit_script)
        self.edit_button.pack(side="right", padx=(0, 8))
        self.remove_button = ttk.Button(toolbar, text="移除", style="Danger.TButton", command=self.remove_script)
        self.remove_button.pack(side="right", padx=(0, 8))

        self.tabs = ttk.Notebook(bottom)
        self.tabs.grid(row=1, column=0, sticky="nsew")
        self.image_panel = ImageInputPanel(self.tabs, self.run_image_metrics)
        self.tabs.add(self.image_panel, text="图像输入与计算")
        detail_frame = ttk.Frame(self.tabs, style="Panel.TFrame")
        self.tabs.add(detail_frame, text="脚本信息")
        self.details = self._text_area(detail_frame, "white", theme.TEXT)
        log_frame = ttk.Frame(self.tabs, style="Panel.TFrame")
        self.tabs.add(log_frame, text="运行日志")
        log_tools = ttk.Frame(log_frame, padding=6, style="Panel.TFrame")
        log_tools.pack(fill="x")
        self.run_status = tk.StringVar(value="尚未运行脚本")
        ttk.Label(log_tools, textvariable=self.run_status, style="Panel.TLabel").pack(side="left")
        self.stop_button = ttk.Button(log_tools, text="停止运行", command=self.stop_script, state="disabled")
        self.stop_button.pack(side="right")
        ttk.Button(log_tools, text="保存日志", command=self.save_log).pack(side="right", padx=6)
        self.log = self._text_area(log_frame, "#182338", "#DDE6F7", font=("Consolas", 10))
        result_frame = ttk.Frame(self.tabs, style="Panel.TFrame")
        self.tabs.add(result_frame, text="计算结果")
        self.image_results = self._text_area(result_frame, "white", theme.TEXT)
        self.set_text(self.image_results, "选择原始图像和处理后图像，点击“开始计算”。结果将自动保存为 JSON 文件。")
        self.status_var = tk.StringVar(value=f"就绪  ·  脚本库：{self.store.path}")
        ttk.Label(main, textvariable=self.status_var, style="Muted.TLabel", wraplength=900).grid(
            row=5, column=0, sticky="w", pady=(14, 0))

    def _text_area(self, parent, background, foreground, font=("Microsoft YaHei UI", 10)):
        frame = tk.Frame(parent, bg=background)
        frame.pack(fill="both", expand=True)
        area = tk.Text(frame, wrap="word", height=7, relief="flat", padx=16, pady=12,
                       background=background, foreground=foreground, font=font, state="disabled")
        scroll = ttk.Scrollbar(frame, command=area.yview)
        scroll.pack(side="right", fill="y")
        area.configure(yscrollcommand=scroll.set)
        area.pack(fill="both", expand=True)
        return area

    def _nav_button(self, label, command, parent=None, active=False):
        button = tk.Button(parent or self.sidebar, text=label, command=command, anchor="w", relief="flat",
                           bg="#2A3C5B" if active else theme.NAV, fg="#FFFFFF" if active else "#BAC7DC",
                           activebackground="#30466A", activeforeground="white", padx=16, pady=10,
                           borderwidth=0, cursor="hand2")
        button.pack(fill="x", padx=12, pady=2)
        return button

    def set_category(self, category):
        self.category = category
        self.refresh()

    def refresh(self):
        entries = self.store.entries
        self.stat_vars[0].set(str(len(entries)))
        categories = sorted({item.category for item in entries})
        self.stat_vars[1].set(str(len(categories)))
        self.stat_vars[2].set(str(sum(item.available for item in entries)))
        if self.category != "全部脚本" and self.category not in categories:
            self.category = "全部脚本"
        self.all_button.configure(bg="#2A3C5B" if self.category == "全部脚本" else theme.NAV)
        for child in self.category_frame.winfo_children():
            child.destroy()
        for category in categories:
            count = sum(item.category == category for item in entries)
            self._nav_button(f"{category}   {count}", lambda value=category: self.set_category(value),
                             parent=self.category_frame, active=self.category == category)
        if not categories:
            tk.Label(self.category_frame, text="添加脚本后自动生成分类", fg="#8394B2", bg=theme.NAV,
                     font=("Microsoft YaHei UI", 9)).pack(anchor="w", padx=24, pady=8)
        self.refresh_table()

    def refresh_table(self):
        query = self.search_var.get().strip().casefold()
        entries = [entry for entry in self.store.entries
                   if (self.category == "全部脚本" or entry.category == self.category)
                   and query in " ".join((entry.name, entry.description, entry.category, entry.path, *entry.tags)).casefold()]
        for row in self.tree.get_children():
            self.tree.delete(row)
        for entry in sorted(entries, key=lambda item: item.name.casefold()):
            self.tree.insert("", "end", iid=entry.id, values=(entry.name, entry.category,
                             " / ".join(entry.tags) or "—", "可访问" if entry.available else "文件缺失"))
        self.filter_var.set(f"{self.category}  ·  {len(entries)} 个脚本  ·  搜索名称、说明、标签或路径")
        if entries:
            self.empty_label.place_forget()
            ids = {entry.id for entry in entries}
            self.selected_id = self.selected_id if self.selected_id in ids else entries[0].id
            self.tree.selection_set(self.selected_id)
        else:
            self.selected_id = None
            self.empty_label.configure(text="还没有脚本\n点击右上角“添加已有脚本”开始整理你的指标库" if not self.store.entries
                                       else "没有匹配的脚本\n尝试其他关键词或切换分类")
            self.empty_label.place(relx=0.5, rely=0.58, anchor="center")
        self.show_details()

    def selected_entry(self) -> ScriptEntry | None:
        return next((entry for entry in self.store.entries if entry.id == self.selected_id), None)

    def on_select(self, event=None):
        selection = self.tree.selection()
        if selection:
            self.selected_id = selection[0]
            self.show_details()

    @staticmethod
    def set_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", text)
        widget.configure(state="disabled")

    def show_details(self):
        entry = self.selected_entry()
        self.detail_title.set(entry.name if entry else "脚本详情")
        if entry:
            text = (f"用途说明    {entry.description or '暂无说明，可通过“编辑”补充'}\n\n"
                    f"脚本路径    {entry.path}\n"
                    f"任务分类    {entry.category}\n"
                    f"指标标签    {' / '.join(entry.tags) or '—'}\n"
                    f"解释器        {entry.interpreter or sys.executable}\n"
                    f"工作目录    {entry.working_dir or str(Path(entry.path).parent)}\n"
                    f"运行参数    {json.dumps(entry.arguments, ensure_ascii=False)}\n\n"
                    "提示：添加脚本只登记文件路径，运行时才会启动独立进程。当前支持直接运行 Python 脚本。")
        else:
            text = "选择一个脚本，查看说明和运行配置。\n\n开始使用：添加已有脚本 → 填写分类与标签 → 保存。"
        self.set_text(self.details, text)
        self.update_buttons()

    def update_buttons(self):
        selected = self.selected_entry() is not None
        busy = self.runner.running or self.active_entry is not None
        self.add_button.configure(state="disabled" if self._read_only else "normal")
        self.builtin_button.configure(state="disabled" if self._read_only else "normal")
        for button in (self.edit_button, self.remove_button):
            button.configure(state="normal" if selected and not self._read_only else "disabled")
        self.run_button.configure(state="normal" if selected and not busy else "disabled")
        self.stop_button.configure(state="normal" if busy else "disabled")
        self.image_panel.run_button.configure(state="disabled" if busy else "normal")

    def add_script(self):
        if not self._read_only:
            ScriptDialog(self.root, self.save_entry, categories=[entry.category for entry in self.store.entries])

    def add_builtins(self):
        if self._read_only:
            return
        try:
            count = self.store.add_missing(builtin_entries())
        except (StorageError, ValueError) as exc:
            messagebox.showerror("添加失败", str(exc), parent=self.root)
            return
        self.category = "全部脚本"
        self.search_var.set("")
        self.refresh()
        self.status_var.set(f"已添加 {count} 组常用指标（已有配置保持不变）。默认 --demo 为演示，真实评估请先编辑输入参数。")

    def edit_script(self):
        entry = self.selected_entry()
        if entry and not self._read_only:
            ScriptDialog(self.root, self.save_entry, entry, [item.category for item in self.store.entries])

    def save_entry(self, entry):
        try:
            self.store.save(entry)
        except StorageError as exc:
            raise ValueError(str(exc)) from exc
        self.selected_id = entry.id
        self.category = "全部脚本"
        self.search_var.set("")
        self.refresh()
        self.status_var.set(f"已保存：{entry.name}")

    def remove_script(self):
        entry = self.selected_entry()
        if not entry or self._read_only:
            return
        if not messagebox.askyesno("从工具箱移除", f"移除“{entry.name}”的登记记录？\n原始脚本文件会保留。", parent=self.root):
            return
        try:
            self.store.remove(entry.id)
        except StorageError as exc:
            messagebox.showerror("移除失败", str(exc), parent=self.root)
            return
        self.refresh()
        self.status_var.set(f"已移除登记：{entry.name}")

    def run_script(self):
        entry = self.selected_entry()
        if not entry or self.active_entry is not None:
            return
        self.start_entry(entry)

    def run_image_metrics(self):
        if self.active_entry is not None or self.runner.running:
            return
        panel = self.image_panel
        default = next(item for item in builtin_entries() if Path(item.path).stem == panel.kind)
        template = next((item for item in self.store.entries if Path(item.path).resolve() == Path(default.path).resolve()), default)
        try:
            job = prepare_image_job(panel.kind, panel.original.get(), panel.processed.get(), panel.output.get(),
                                    panel.threshold.get(), panel.data_range.get(), self.store.path.parent / "results", template)
        except ValueError as exc:
            messagebox.showerror("无法计算", str(exc), parent=self.root)
            return
        if self.start_entry(job.entry, job.output):
            self.set_text(self.image_results, f"计算中…\n本次结果路径：{job.output}")

    def start_entry(self, entry, image_output=None):
        try:
            self.runner.start(entry)
        except ValueError as exc:
            messagebox.showerror("无法运行", str(exc), parent=self.root)
            return False
        self._image_output = image_output
        self.active_entry = entry
        self.set_text(self.log, "")
        self.run_status.set(f"运行中：{entry.name}")
        self.tabs.select(self.log.master.master)
        self.status_var.set(f"正在运行：{entry.name}")
        self.update_buttons()
        return True

    def stop_script(self):
        if self.active_entry is not None:
            self.run_status.set(f"正在停止：{self.active_entry.name}")
            self.runner.stop()

    def poll_runner(self):
        chunks = []
        # Bound each poll so very noisy scripts cannot freeze the event loop.
        for _ in range(300):
            try:
                event = self.runner.events.get_nowait()
            except queue.Empty:
                break
            if event.kind == "output":
                chunks.append(event.text)
            else:
                self._terminal_event = event
                chunks.append(f"\n\n{event.text} · 退出码 {event.returncode}\n")
        if chunks:
            self.log.configure(state="normal")
            self.log.insert("end", "".join(chunks))
            # Keep memory bounded; full logs may be written by the script itself.
            lines = int(self.log.index("end-1c").split(".")[0])
            if lines > 5000:
                self.log.delete("1.0", f"{lines - 5000}.0")
            chars = int(self.log.count("1.0", "end-1c", "chars")[0])
            if chars > 500_000:
                self.log.delete("1.0", f"1.0+{chars - 500_000}c")
            self.log.configure(state="disabled")
            self.log.see("end")
        if self._terminal_event and not self.runner.running:
            event = self._terminal_event
            name = self.active_entry.name if self.active_entry else "脚本"
            self.run_status.set(f"{name} · {event.text} · 退出码 {event.returncode}")
            self.status_var.set(self.run_status.get())
            if self._image_output is not None:
                if event.kind == "finished" and event.returncode == 0:
                    try:
                        result = json.loads(self._image_output.read_text(encoding="utf-8"))
                        summary = "\n".join(f"{key}: {value}" for key, value in result.get("mean_per_image", {}).items())
                        self.set_text(self.image_results, f"计算完成，共 {result['count']} 张图像\n结果文件：{self._image_output}\n\n"
                                      f"逐图指标平均值\n{summary}\n\n详细结果\n{json.dumps(result, ensure_ascii=False, indent=2)}")
                        self.tabs.select(self.image_results.master.master)
                        self.status_var.set(f"计算完成，结果已保存：{self._image_output}")
                    except (OSError, ValueError, KeyError) as exc:
                        self.set_text(self.image_results, f"脚本已结束，但读取结果失败：{exc}\n请查看运行日志。")
                else:
                    self.set_text(self.image_results, f"{event.text}，未生成本次有效结果。请查看运行日志。")
                self._image_output = None
            self.active_entry = None
            self._terminal_event = None
            self.update_buttons()
        if self._closing and not self.runner.running:
            self.root.destroy()
            return
        self._poll_id = self.root.after(100, self.poll_runner)

    def save_log(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="保存当前显示的日志", defaultextension=".log",
                                            filetypes=[("日志文件", "*.log"), ("文本文件", "*.txt")])
        if path:
            try:
                Path(path).write_text(self.log.get("1.0", "end-1c"), encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("保存失败", str(exc), parent=self.root)
            else:
                self.status_var.set(f"日志已保存：{path}")

    def close(self):
        if self.runner.running:
            if not messagebox.askyesno("关闭工具箱", "脚本仍在运行。停止脚本并关闭工具箱？", parent=self.root):
                return
            self._closing = True
            self.runner.stop()
            self.run_status.set("正在停止脚本并关闭…")
        else:
            if self._poll_id:
                self.root.after_cancel(self._poll_id)
            self.root.destroy()


def main():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    MetricBoxApp(root)
    root.mainloop()


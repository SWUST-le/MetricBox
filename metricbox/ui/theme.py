"""Centralized colors and widget styles."""

from tkinter import ttk

BG = "#F4F6FA"
PANEL = "#FFFFFF"
NAV = "#172338"
TEXT = "#1B2940"
MUTED = "#6B7890"
ACCENT = "#4068E8"
LINE = "#E2E7F0"


def configure(root) -> None:
    root.option_add("*Font", ("Microsoft YaHei UI", 10))
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("TButton", padding=(12, 8), background=PANEL, foreground=TEXT,
                    bordercolor=LINE, focuscolor=LINE, font=("Microsoft YaHei UI", 10))
    style.map("TButton", background=[("active", "#EBEFFB"), ("disabled", "#EDF0F5")],
              foreground=[("disabled", "#A1AABA")])
    style.configure("Primary.TButton", background=ACCENT, foreground="white", bordercolor=ACCENT)
    style.map("Primary.TButton", background=[("active", "#3158CF"), ("disabled", "#9AACE7")],
              foreground=[("disabled", "#FFFFFF")])
    style.configure("Danger.TButton", foreground="#BD4253")
    style.configure("TEntry", padding=8, fieldbackground=PANEL, bordercolor=LINE)
    style.configure("TCombobox", padding=7, fieldbackground=PANEL, bordercolor=LINE)
    style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                    rowheight=48, borderwidth=0, font=("Microsoft YaHei UI", 10))
    style.configure("Treeview.Heading", background="#F0F3F9", foreground=MUTED,
                    padding=(10, 12), font=("Microsoft YaHei UI", 10), relief="flat")
    style.map("Treeview", background=[("selected", "#EAF0FF")], foreground=[("selected", ACCENT)])
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(18, 10), background="#E9EDF5", foreground=MUTED)
    style.map("TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", TEXT)])


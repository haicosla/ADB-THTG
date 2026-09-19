"""
dashboard_progress.py — Theo dõi tiến độ chạy của từng Hoạt Động (đang chờ/đang chạy/xong/lỗi/đã dừng) và khung 'Lỗi / Chưa Xong' liệt kê các Hoạt Động bị lỗi trong phiên chạy gần nhất.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import tkinter as tk

import task_registry
from dashboard_theme import *
from dashboard_widgets import _bind_esc_close
import window_geometry as wg


class ProgressMixin:
    def _bump_task_progress(self, task_id, kind):
        self.root.after(0, lambda: self._apply_task_progress(task_id, kind))

    def _apply_task_progress(self, task_id, kind):
        prog = self.task_progress.get(task_id)
        if prog is None:
            return
        if kind == "running":
            prog["running"] += 1
        elif kind == "done":
            prog["done"] += 1
            prog["running"] = max(0, prog["running"] - 1)
        elif kind == "error":
            prog["error"] += 1
            prog["running"] = max(0, prog["running"] - 1)
        elif kind == "stopped":
            prog["stopped"] += 1
            prog["running"] = max(0, prog["running"] - 1)

        lbl = self.task_status_lbl.get(task_id)
        if lbl:
            total = prog["total"]
            if prog["error"] > 0:
                lbl.config(text=f"⚠ Lỗi {prog['error']}/{total}", fg=COL_RED)
            elif total > 0 and prog["done"] == total:
                lbl.config(text=f"✅ Hoàn thành ({total}/{total})", fg=COL_GREEN)
            elif prog["running"] > 0:
                lbl.config(text=f"▶ Đang chạy ({prog['done']}/{total})", fg=COL_TEAL)
            elif prog["stopped"] > 0:
                lbl.config(text=f"⏹ Đã dừng ({prog['done']}/{total})", fg=COL_ORANGE)
            else:
                lbl.config(text="⏳ Đang chờ", fg=COL_TEXT_MUTED)

        self._refresh_error_badge()

    def _refresh_error_badge(self):
        n = sum(1 for p in self.task_progress.values() if p["error"] > 0)
        self.btn_view_errors.set_text(f"⚠ Xem Lỗi / Chưa Xong ({n})")

    def show_error_panel(self):
        win = tk.Toplevel(self.root)
        win.title("Lỗi / Chưa Xong")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "progress_errors", default="440x420")
        wg.autosave(win, "progress_errors")
        _bind_esc_close(win)

        problems = [(tid, p) for tid, p in self.task_progress.items() if p["error"] > 0]
        if not problems:
            tk.Label(win, text="Không có tác vụ nào bị lỗi trong phiên chạy gần nhất. ✅",
                     bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 10)).pack(pady=30, padx=20)
            return

        name_by_id = {}
        for t in self.tasks:
            tid = t.get("id") or task_registry.make_task_id(t.get("file_json", ""))
            name_by_id[tid] = t.get("ten_hien_thi", tid)

        tk.Label(win, text="Các Hoạt Động bị lỗi trong phiên chạy gần nhất:", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

        for tid, p in problems:
            row = tk.Frame(win, bg=COL_PANEL_ALT)
            row.pack(fill="x", padx=12, pady=3)
            tk.Label(row, text=name_by_id.get(tid, tid), bg=COL_PANEL_ALT, fg=COL_TEXT,
                     font=("Segoe UI", 9)).pack(side="left", padx=8, pady=6)
            tk.Label(row, text=f"Lỗi {p['error']}/{p['total']}", bg=COL_PANEL_ALT, fg=COL_RED,
                     font=("Segoe UI", 9, "bold")).pack(side="right", padx=8)

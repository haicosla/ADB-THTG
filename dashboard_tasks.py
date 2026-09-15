"""
dashboard_tasks.py — Nạp/hiển thị danh mục Hoạt Động (task_registry.json) theo từng MỤC, theo dõi file để tự nạp lại khi có Hoạt Động mới đăng ký, mở lại chương trình soạn kịch bản cũ (LD Macro Studio), các nút chức năng nhanh, và popup 'Chọn Hành Động Để Chạy'.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import os
import sys
import json
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

import task_registry
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, CategorySection, _bind_esc_close


class TaskMixin:
    # ================= NẠP DANH MỤC TÁC VỤ =================
    def reload_tasks(self):
        self.tasks = task_registry.load_registry()
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.task_vars = {}
        self.task_status_lbl = {}
        self.task_progress = {}

        if not self.tasks:
            tk.Label(
                self.list_frame,
                text="Chưa có tác vụ nào được đăng ký.\n\n"
                     "Bấm '➕ Tạo Hoạt Động' để mở LD Macro Studio,\n"
                     "soạn kịch bản rồi bấm '📋 Đăng Ký Tác Vụ'.",
                bg=COL_BG, fg=COL_TEXT_MUTED, font=("Segoe UI", 11), justify="center"
            ).pack(pady=40)
            self._log("info", "Danh mục tác vụ trống (task_registry.json chưa có hoặc rỗng).")
            return

        groups = {}
        order_keys = []
        for t in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0))):
            muc = t.get("muc") or "Chưa phân loại"
            if muc not in groups:
                groups[muc] = []
                order_keys.append(muc)
            groups[muc].append(t)

        for idx, muc in enumerate(order_keys):
            self._build_category_section(muc, groups[muc], show_shop_button=(idx == 0))

        self._log("info", f"Đã nạp {len(self.tasks)} tác vụ trong {len(groups)} mục.")

    def _build_category_section(self, muc, entries, show_shop_button=False):
        section = CategorySection(
            self.list_frame, title=muc, count=len(entries),
            show_shop_button=show_shop_button,
            on_shop_click=lambda m=muc: self._open_shop_settings(m)
        )
        section.pack(fill="x", padx=8, pady=6, anchor="n")

        for i, entry in enumerate(entries):
            task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", str(i)))
            var = tk.BooleanVar(value=bool(entry.get("mac_dinh_bat", True)))
            self.task_vars[task_id] = var
            self.task_progress[task_id] = {"total": 0, "done": 0, "error": 0, "running": 0, "stopped": 0}

            row = tk.Frame(section.body, bg=COL_PANEL)
            row.grid(row=i // 3, column=i % 3, sticky="w", padx=10, pady=5)

            DarkCheck(row, entry.get("ten_hien_thi", task_id), var, bg=COL_PANEL).pack(side="left")
            status_lbl = tk.Label(row, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"))
            status_lbl.pack(side="left", padx=6)
            self.task_status_lbl[task_id] = status_lbl

        for col in range(3):
            section.body.grid_columnconfigure(col, weight=1, uniform="task_col")

        section.set_select_all_command(lambda v, es=entries: self._set_category_checks(es, v))

    def _set_category_checks(self, entries, value):
        for e in entries:
            task_id = e.get("id") or task_registry.make_task_id(e.get("file_json", ""))
            var = self.task_vars.get(task_id)
            if var:
                var.set(value)

    def _set_all_checks(self, value):
        for var in self.task_vars.values():
            var.set(value)

    # ================= NÚT CHỨC NĂNG NHANH =================
    def _quick_action(self, action_id):
        if action_id == "mo_bang_gia_lap":
            self._open_emulator_panel()
            return
        if action_id == "huong_dan":
            self._open_help_panel()
            return

        entry = task_registry.find_task(self.tasks, action_id)
        if not entry:
            messagebox.showinfo(
                "Chưa cấu hình",
                "Chức năng này chưa có Hoạt Động tương ứng.\n\n"
                "Cách kích hoạt: bấm '➕ Tạo Hoạt Động', soạn kịch bản, LƯU FILE "
                f"với tên đúng quy ước:\n\n    tasks/{action_id}.json\n\n"
                "rồi bấm '📋 Đăng Ký Tác Vụ' như bình thường. ID sẽ tự nhận đúng "
                "tên file, và nút này sẽ chạy thẳng kịch bản đó (xem thêm ở '📖 Hướng Dẫn')."
            )
            return

        selected_emulators = self._get_selected_emulators()
        if not selected_emulators:
            messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào để chạy!")
            return

        self._start_run([entry], selected_emulators, login_entry=None)

    # ================= TẠO HOẠT ĐỘNG (mở chương trình cũ) =================
    def open_creator_tool(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            main_py = os.path.join(script_dir, "main.py")
            subprocess.Popen([sys.executable, main_py], cwd=script_dir)
            self._log("info", "Đã mở LD Macro Studio (chương trình tạo Hoạt Động) ở cửa sổ riêng.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không mở được chương trình tạo Hoạt Động:\n{e}")

    def _watch_registry(self):
        """Tự động phát hiện task_registry.json thay đổi (do chương trình
        Tạo Hoạt Động ghi ra) để nạp lại danh mục MÀ KHÔNG CẦN người dùng tự
        bấm '🔄 Quét Lại Danh Mục'."""
        try:
            mtime = os.path.getmtime(task_registry.REGISTRY_PATH) if os.path.exists(task_registry.REGISTRY_PATH) else None
        except Exception:
            mtime = None

        if mtime != self._last_registry_mtime:
            if not self._first_watch_tick:
                self.reload_tasks()
                self._log("info", "Đã tự động nạp lại danh mục do phát hiện thay đổi mới.")
            self._last_registry_mtime = mtime

        self._first_watch_tick = False
        self.root.after(2000, self._watch_registry)

    # ================= CHỌN HÀNH ĐỘNG ĐỂ CHẠY (chạy nhanh 1 tác vụ) =================
    def _open_task_picker(self):
        win = tk.Toplevel(self.root)
        win.title("Chọn Hành Động Để Chạy")
        win.configure(bg=COL_PANEL)
        win.geometry("440x500")
        _bind_esc_close(win)

        tk.Label(win, text="Chọn 1 Hoạt Động để chạy ngay:", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=6)
        vbar.pack(side="right", fill="y", padx=(0, 6))

        if not self.tasks:
            tk.Label(inner, text="Chưa có Hoạt Động nào được đăng ký.", bg=COL_PANEL,
                     fg=COL_TEXT_MUTED).pack(pady=20)

        for entry in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0))):
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=3, padx=4)
            tk.Label(row, text=entry.get("ten_hien_thi", "?"), bg=COL_PANEL_ALT, fg=COL_TEXT,
                     font=("Segoe UI", 9)).pack(side="left", padx=8, pady=6)
            tk.Label(row, text=entry.get("muc", ""), bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                     font=("Segoe UI", 8)).pack(side="left", padx=4)

            def _run(e=entry):
                win.destroy()
                selected_emulators = self._get_selected_emulators()
                if not selected_emulators:
                    messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào để chạy!")
                    return
                self._start_run([e], selected_emulators, login_entry=None)

            RoundedButton(row, "▶ Chạy", command=_run, bg=COL_GREEN, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="right", padx=8, pady=4)

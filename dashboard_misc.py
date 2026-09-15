"""
dashboard_misc.py — Các tính năng phụ trợ lặt vặt: popup thông báo ĐÈ LÊN giả lập (dùng cho bước 'popup' trong kịch bản), cửa sổ Hướng Dẫn, Cài Đặt Mua Shop theo từng Mục, và Reset Bộ Nhớ Task Hôm Nay.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from window_finder import WindowFinder
import run_state
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, _bind_esc_close


class MiscMixin:
    # ================= POPUP (dùng cho bước 'popup' trong kịch bản) =================
    def _show_ingame_popup(self, wf, message, duration=0):
        """Giống LD Macro Studio: hiện overlay đè lên đúng khung LDPlayer
        TƯƠNG ỨNG với luồng đang chạy (nhận wf = WindowFinder riêng của
        luồng đó), tránh hiện nhầm sang cửa sổ giả lập khác khi đa luồng."""
        done_event = threading.Event() if not duration else None

        def _do():
            rect = wf.get_render_screen_rect()
            top = tk.Toplevel(self.root)
            top.overrideredirect(True)
            try:
                top.attributes("-topmost", True)
                top.attributes("-alpha", 0.93)
            except Exception:
                pass

            if rect:
                sx, sy, sw, sh = rect
                top.geometry(f"{max(sw, 220)}x64+{sx}+{max(0, sy)}")
                wrap = max(150, sw - 90)
            else:
                top.geometry("420x64+300+300")
                wrap = 330

            frame = tk.Frame(top, bg="#212121", highlightbackground="#FFEB3B", highlightthickness=2)
            frame.pack(fill="both", expand=True)
            tk.Label(frame, text=message or "(không có nội dung)", bg="#212121", fg="#FFEB3B",
                     font=("Segoe UI", 12, "bold"), wraplength=wrap, justify="left").pack(
                side="left", expand=True, fill="both", padx=12, pady=6)

            def _close():
                try:
                    top.destroy()
                except Exception:
                    pass
                if done_event:
                    done_event.set()

            if duration and duration > 0:
                top.after(int(duration * 1000), _close)
            else:
                ttk.Button(frame, text="✔ Đóng", command=_close).pack(side="right", padx=10)

        self.root.after(0, _do)
        if done_event:
            done_event.wait()

    def _open_help_panel(self):
        win = tk.Toplevel(self.root)
        win.title("Hướng Dẫn")
        win.configure(bg=COL_PANEL)
        win.geometry("580x540")
        _bind_esc_close(win)

        txt = tk.Text(win, bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 10), wrap="word",
                      relief="flat", padx=14, pady=14)
        txt.pack(fill="both", expand=True)
        txt.insert("end", HELP_TEXT)
        txt.config(state="disabled")

    def _open_shop_settings(self, muc):
        win = tk.Toplevel(self.root)
        win.title(f"Cài Đặt Mua Shop - {muc}")
        win.configure(bg=COL_PANEL)
        win.geometry("400x190")
        _bind_esc_close(win)

        var = tk.BooleanVar(value=bool(self.shop_settings.get(muc, False)))
        tk.Label(win, text=f"Mục: {muc}", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(14, 8))
        DarkCheck(win, "Tự động mua Shop khi chạy các tác vụ trong mục này", var, bg=COL_PANEL,
                  wraplength=340).pack(anchor="w", padx=14)

        def _save():
            self.shop_settings[muc] = var.get()
            self._save_settings()
            self._log("info", f"Đã lưu cài đặt Mua Shop cho mục '{muc}': {'BẬT' if var.get() else 'TẮT'}.")
            win.destroy()

        RoundedButton(win, "💾 Lưu", command=_save, bg=COL_GREEN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9, "bold")).pack(pady=16)

    # ================= RESET BỘ NHỚ TASK =================
    def reset_daily_memory(self):
        if not messagebox.askyesno("Xác nhận", "Xóa toàn bộ ghi nhớ 'đã chạy hôm nay' của mọi Hoạt Động/giả lập?"):
            return
        run_state.reset_today()
        self._log("info", "Đã reset bộ nhớ task hôm nay.")

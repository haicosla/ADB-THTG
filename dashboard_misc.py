"""
dashboard_misc.py — Các tính năng phụ trợ lặt vặt: popup thông báo ĐÈ LÊN giả lập (dùng cho bước 'popup' trong kịch bản), cửa sổ Hướng Dẫn, Cài Đặt Mua Shop theo từng Mục, và Reset Bộ Nhớ Task Hôm Nay.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import threading
import tkinter as tk
from tkinter import messagebox

from window_finder import WindowFinder
from popup_widget import show_ingame_popup
import window_geometry as wg
import run_state
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, _bind_esc_close


class MiscMixin:
    # ================= POPUP (dùng cho bước 'popup' trong kịch bản) =================
    def _show_ingame_popup(self, wf, message, duration=0, bg=None, fg=None, alpha=None, pos_box=None):
        """Hiện popup thông báo ĐÈ LÊN cửa sổ LDPlayer - phần dựng popup
        thật sự nằm chung trong popup_widget.py (dùng chung với Macro
        Studio, xem gui_run.py) để khỏi lặp code 2 nơi.

        wf: WindowFinder RIÊNG của luồng đang chạy (đa luồng nhiều giả lập
        cùng lúc, mỗi luồng phải tự biết đúng cửa sổ LDPlayer của mình).
        bg/fg/alpha: tuỳ chỉnh màu nền/chữ/độ mờ theo từng bước popup, mặc
        định nền trắng/chữ đen/mờ 50%. pos_box: vị trí/kích thước tự chọn
        (xem gui_canvas.py) - để trống thì dùng dải ngang mặc định phía
        trên khung game. Mọi lỗi bất ngờ được ghi vào Nhật Ký (self._log)
        thay vì im lặng biến mất, để còn biết đường debug tiếp nếu vẫn có
        vấn đề."""
        done_event = threading.Event() if not duration else None

        def _log_err(where, e):
            try:
                self._log("error", f"Popup lỗi ({where}): {e}")
            except Exception:
                pass

        def _do():
            show_ingame_popup(
                self.root, wf.get_render_screen_rect, message, duration,
                bg=bg, fg=fg, alpha=alpha, pos_box=pos_box,
                log_fn=_log_err, done_event=done_event,
            )

        try:
            self.root.after(0, _do)
        except Exception as e:
            _log_err("schedule _do", e)
        if done_event:
            done_event.wait()

    def _open_help_panel(self):
        win = tk.Toplevel(self.root)
        win.title("Hướng Dẫn")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "misc_help", default="580x540")
        wg.autosave(win, "misc_help")
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
        wg.restore_geometry(win, "misc_shop_settings", default="400x190")
        wg.autosave(win, "misc_shop_settings")
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

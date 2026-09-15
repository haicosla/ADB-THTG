"""
dashboard_log.py — Ghi/hiển thị/lọc Nhật Ký chạy theo từng giả lập (hoặc xem tổng hợp tất cả), đếm số dòng đang hiển thị, xoá/sao chép Nhật Ký.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import time
from tkinter import messagebox


class LogMixin:
    # ================= LOG =================
    def _log(self, level, message, emulator_name=None):
        """logger(level, message) - có thể được LogicEngine gọi từ thread
        nền nên luôn điều phối qua root.after()."""
        self.root.after(0, lambda: self._append_log(level, message, emulator_name))

    def _append_log(self, level, message, emulator_name):
        ts = time.strftime("%H:%M:%S")
        self.log_entries.append((ts, level, emulator_name, message))
        if self._log_passes_filter(emulator_name):
            self._write_log_line(ts, level, emulator_name, message)
        self._update_log_count()

    def _log_passes_filter(self, emulator_name):
        filt = self.log_filter_var.get()
        if not filt or filt == self.LOG_FILTER_ALL:
            return True
        return emulator_name == filt

    def _write_log_line(self, ts, level, emulator_name, message):
        tag = level if level in ("info", "success", "warn", "error") else "info"
        prefix = f"[{emulator_name}] " if emulator_name else ""
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", f"[{ts}] {prefix}{message}\n", (tag,))
        if self.var_log_autoscroll.get():
            self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    def _update_log_count(self):
        visible = sum(1 for e in self.log_entries if self._log_passes_filter(e[2]))
        self.lbl_log_count.config(text=f"{visible} dòng")

    def _on_log_filter_changed(self, _evt=None):
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        for ts, level, emu, msg in self.log_entries:
            if self._log_passes_filter(emu):
                tag = level if level in ("info", "success", "warn", "error") else "info"
                prefix = f"[{emu}] " if emu else ""
                self.txt_log.insert("end", f"[{ts}] {prefix}{msg}\n", (tag,))
        self.txt_log.config(state="disabled")
        self._update_log_count()

    def _refresh_log_filter_options(self):
        names = [self.LOG_FILTER_ALL] + [e.name for e in self.emulators]
        current = self.log_filter_var.get()
        self.cbo_log_filter["values"] = names
        if current not in names:
            self.log_filter_var.set(self.LOG_FILTER_ALL)

    def _clear_log(self):
        self.log_entries = []
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.config(state="disabled")
        self._update_log_count()

    def _copy_log(self):
        content = self.txt_log.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("Đã sao chép", "Đã sao chép nhật ký hiện đang hiển thị vào clipboard.")

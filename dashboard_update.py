"""
dashboard_update.py - UpdateMixin: nút '🔄 Cập Nhật' + tự báo 'có bản mới' khi mở Dashboard.

Phần logic (tải/kiểm tra/ghi đè an toàn) nằm hết ở updater.py (không dùng tkinter, đã test riêng).
File này chỉ lo giao diện + luồng nền:
  - 8 giây sau khi mở app: kiểm tra GIM LẶNG 1 lần ở thread nền. Có bản mới -> nút đổi thành
    '🔄 Có bản mới vX - Cập Nhật' (màu cam) + 1 dòng log. Không hiện popup chặn (tránh đè lên hộp
    'chạy tiếp phiên dở' / 'Tự bật giả lập'). Không có mạng/không có bản mới -> không báo gì.
  - Bấm nút: kiểm tra lại -> hỏi xác nhận (kèm ghi chú Release) -> tải + áp dụng có thanh tiến độ ->
    cài thư viện nếu requirements.txt đổi -> hỏi 'Khởi động lại ngay?'.
  - ĐANG CHẠY tác vụ (self.is_running) thì từ chối cập nhật, tránh đổi code giữa lượt chạy.
  - Máy dev (có .git VÀ data/may_phat_trien.flag) không tự cập nhật; máy chỉ có .git vẫn cập nhật bình thường.
KHÔNG ghi gì vào dashboard_settings.json.
"""
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import updater
from dashboard_theme import *
from dashboard_widgets import RoundedButton, ThemedToplevel

_STARTUP_CHECK_DELAY_MS = 8000
_POLL_MS = 150


class UpdateMixin:

    # ------------------------------------------------------------ khởi tạo / nút
    def _init_update(self):
        """Gọi 1 lần ở cuối DashboardApp.__init__ (sau khi UI dựng xong)."""
        self._update_busy = False
        self._update_available = None        # dict 'latest' của updater.check_for_update khi có bản mới
        if not updater.is_dev_checkout():
            self.root.after(_STARTUP_CHECK_DELAY_MS, self._update_startup_check)

    def _update_button_set(self, available_tag=None):
        btn = getattr(self, "btn_update", None)
        if btn is None:
            return
        try:
            if available_tag:
                btn.set_text(f"🔄 Có bản mới {available_tag} - Cập Nhật")
                btn.bg_color = COL_ORANGE
                btn.fg_color = "#241a00"
            else:
                btn.set_text("🔄 Cập Nhật")
                btn.bg_color = COL_BLUE
                btn.fg_color = "white"
            btn._redraw()
        except Exception:
            pass   # nút chỉ là trang trí - lỗi vẽ không được làm hỏng app

    # ------------------------------------------------------------ chạy việc nặng ở thread nền
    def _update_run_bg(self, work, done):
        """work() chạy ở thread nền (KHÔNG đụng Tk); done(kết_quả, lỗi) chạy lại ở thread giao diện."""
        box = {}

        def _target():
            try:
                box["res"] = work()
            except Exception as e:   # mọi lỗi đều quay về giao diện, không để thread chết lặng
                box["err"] = e

        def _poll():
            if "res" in box or "err" in box:
                done(box.get("res"), box.get("err"))
            else:
                self.root.after(_POLL_MS, _poll)

        threading.Thread(target=_target, daemon=True).start()
        self.root.after(_POLL_MS, _poll)

    # ------------------------------------------------------------ kiểm tra khi mở app
    def _update_startup_check(self):
        def _done(res, err):
            if err or not res or res.get("status") != "available":
                return
            self._update_available = res["latest"]
            self._update_button_set(res["latest"]["tag"])
            self._log("info", f"🔄 Có bản cập nhật mới {res['latest']['tag']} (đang dùng "
                              f"{res['installed'] or 'chưa ghi phiên bản'}) - bấm '🔄 Cập Nhật' ở góc trên để cập nhật.")
        self._update_run_bg(updater.check_for_update, _done)

    # ------------------------------------------------------------ bấm nút
    def _update_clicked(self):
        if self._update_busy:
            return
        if updater.is_dev_checkout():
            messagebox.showinfo("Cập Nhật", "Máy này được đánh dấu là máy phát triển (có data/may_phat_trien.flag).\n\n"
                                            "Cập nhật bằng lệnh 'git pull' - không dùng tự cập nhật để khỏi ghi đè "
                                            "thay đổi đang làm dở.", parent=self.root)
            return
        if getattr(self, "is_running", False):
            messagebox.showwarning("Cập Nhật", "Đang chạy tác vụ. Hãy DỪNG hoặc chờ chạy xong rồi mới cập nhật "
                                               "(cập nhật đổi file code của chương trình).", parent=self.root)
            return
        self._update_busy = True
        self._update_button_set_checking(True)

        def _done(res, err):
            self._update_busy = False
            self._update_button_set_checking(False)
            if err or res is None:
                messagebox.showerror("Cập Nhật", f"Lỗi khi kiểm tra bản mới:\n{err}", parent=self.root)
                return
            st = res["status"]
            if st == "error":
                messagebox.showerror("Cập Nhật", res["message"], parent=self.root)
            elif st in ("none", "up_to_date"):
                self._update_available = None
                self._update_button_set(None)
                messagebox.showinfo("Cập Nhật", res["message"], parent=self.root)
            elif st == "available":
                self._update_available = res["latest"]
                self._update_button_set(res["latest"]["tag"])
                self._update_confirm_and_run(res)
            else:   # 'dev'
                messagebox.showinfo("Cập Nhật", res["message"], parent=self.root)

        self._update_run_bg(updater.check_for_update, _done)

    def _update_button_set_checking(self, checking):
        btn = getattr(self, "btn_update", None)
        if btn is None:
            return
        try:
            if checking:
                btn.set_text("🔄 Đang kiểm tra...")
                btn.set_state("disabled")
            else:
                btn.set_state("normal")
                self._update_button_set((self._update_available or {}).get("tag"))
        except Exception:
            pass

    # ------------------------------------------------------------ xác nhận + áp dụng
    def _update_confirm_and_run(self, res):
        latest = res["latest"]
        notes = (latest.get("notes") or "").strip()
        msg = (f"Có bản mới: {latest['tag']}\nĐang dùng: {res['installed'] or '(chưa ghi phiên bản)'}\n\n"
               + (f"Ghi chú:\n{notes[:600]}\n\n" if notes else "")
               + "Sẽ cập nhật: file code (.py), requirements.txt, tasks/, groups/, templates/ và (nếu bản này có) "
                 "một số file dữ liệu dùng chung trong data/ như Tuỳ chỉnh Hoạt Động, Biến, Lịch hẹn giờ "
                 "(chỉ ghi đè/thêm, không xoá file riêng của máy này).\n"
                 "KHÔNG BAO GIỜ đụng: tài khoản, cài đặt Dashboard, token Telegram.\n"
                 "File cũ bị đổi được sao lưu vào thư mục backup_cap_nhat/.\n")
        dirty = updater.git_dirty_files()
        if dirty:
            msg += ("\n⚠ Máy có git và đang có file sửa chưa commit: " + ", ".join(dirty[:5]) +
                    ". Nếu bản mới cũng có các file này, thay đổi của bạn sẽ bị ghi đè (có sao lưu).\n")
        msg += "\nCập nhật ngay?"
        if not messagebox.askyesno("Cập Nhật", msg, parent=self.root):
            return
        self._update_apply(latest)

    def _update_apply(self, latest):
        self._update_busy = True
        win = ThemedToplevel(self.root)
        win.title("Đang cập nhật...")
        win.geometry("420x130")
        win.resizable(False, False)
        win.transient(self.root)
        win.protocol("WM_DELETE_WINDOW", lambda: None)   # không cho đóng giữa chừng
        lbl = tk.Label(win, text=f"Đang tải {latest['tag']}...", bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 10))
        lbl.pack(padx=16, pady=(18, 8))
        bar = ttk.Progressbar(win, mode="indeterminate", length=380)
        bar.pack(padx=16, pady=4)
        bar.start(12)
        prog = {"done": 0, "total": 0}

        def _tick():
            if not win.winfo_exists():
                return
            if prog["total"]:
                if str(bar.cget("mode")) != "determinate":
                    bar.stop()
                    bar.config(mode="determinate", maximum=prog["total"])
                bar["value"] = prog["done"]
                lbl.config(text=f"Đang tải {latest['tag']}... {prog['done'] // 1024} / {prog['total'] // 1024} KB")
            self.root.after(200, _tick)
        self.root.after(200, _tick)

        def _work():
            def _progress(done, total):
                prog["done"], prog["total"] = done, total
            r = updater.update_to_latest(latest, progress=_progress)
            if r.get("needs_pip"):
                r["pip"] = updater.install_requirements()
            return r

        def _done(res, err):
            self._update_busy = False
            try:
                win.destroy()
            except Exception:
                pass
            if err is not None:
                msg = str(err) if isinstance(err, updater.UpdateError) else f"Lỗi không mong đợi: {err}"
                messagebox.showerror("Cập Nhật thất bại", msg + "\n\nChương trình vẫn ở bản cũ.", parent=self.root)
                return
            self._update_available = None
            self._update_button_set(None)
            n = len(res["changed"])
            extra = ""
            if "pip" in res and not res["pip"][0]:
                extra = ("\n\n⚠ requirements.txt có đổi nhưng cài thư viện chưa xong: " + res["pip"][1] +
                         "\nNếu app báo thiếu thư viện sau khi mở lại, chạy Tai_Them_Thanh_Phan.bat.")
            self._log("info", f"🔄 Đã cập nhật lên {latest['tag']} ({n} file). "
                              + (f"Bản cũ lưu ở {res['backup_dir']}." if res.get("backup_dir") else ""))
            if messagebox.askyesno("Cập Nhật", f"Đã cập nhật lên {latest['tag']} ({n} file đổi).{extra}\n\n"
                                               "Khởi động lại Dashboard ngay để dùng bản mới?", parent=self.root):
                try:
                    updater.spawn_restart()
                except Exception as e:
                    messagebox.showerror("Cập Nhật", f"Không tự mở lại được ({e}).\nHãy tự mở lại Dashboard.",
                                         parent=self.root)
                    return
                self._on_close()

        self._update_run_bg(_work, _done)

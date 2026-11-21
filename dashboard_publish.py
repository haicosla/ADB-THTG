"""
dashboard_publish.py - PublishMixin: nút '🚀 Phát Hành' (máy chủ/máy chính đẩy bản cập nhật cho các máy khác).

Bấm nút -> hộp chọn các mục cần phát hành (Code, Kịch bản, Ảnh mẫu, Hoạt động...) -> xác nhận ->
tự đóng gói + tạo Release trên GitHub. Các máy khác thấy 'Có bản mới' ở nút '🔄 Cập Nhật'.
Logic nằm hết ở publisher.py (không dùng tkinter, đã test với GitHub giả). File này chỉ lo giao diện + thread nền.
Tài khoản / Cài đặt Dashboard bị KHOÁ (hiện 🔒 kèm lý do), không thể tick.
Token GitHub lưu ở data/publish_config.json (thư mục data/ không bao giờ vào gói phát hành).
"""
import threading
import tkinter as tk
from tkinter import messagebox

import publisher
from dashboard_theme import *
from dashboard_widgets import RoundedButton, ThemedToplevel, DarkCheck

_POLL_MS = 150


def _fmt_size(n):
    return f"{n / 1048576:.1f} MB" if n >= 1048576 else f"{max(1, n // 1024) if n else 0} KB"


class PublishMixin:

    def _init_publish(self):
        self._publish_busy = False

    # ------------------------------------------------------------ thread nền
    def _publish_run_bg(self, work, done):
        box = {}

        def _target():
            try:
                box["res"] = work()
            except Exception as e:
                box["err"] = e

        def _poll():
            if "res" in box or "err" in box:
                done(box.get("res"), box.get("err"))
            else:
                self.root.after(_POLL_MS, _poll)

        threading.Thread(target=_target, daemon=True).start()
        self.root.after(_POLL_MS, _poll)

    # ------------------------------------------------------------ hộp chọn mục
    def _publish_clicked(self):
        if self._publish_busy:
            return
        if getattr(self, "is_running", False):
            messagebox.showwarning("Phát Hành", "Đang chạy tác vụ. Hãy DỪNG hoặc chờ chạy xong rồi phát hành.",
                                   parent=self.root)
            return
        try:
            scan = publisher.scan()
        except Exception as e:
            messagebox.showerror("Phát Hành", f"Không quét được dữ liệu:\n{e}", parent=self.root)
            return
        cfg = publisher.load_config()
        win = ThemedToplevel(self.root)
        win.title("🚀 Phát Hành Bản Cập Nhật")
        win.transient(self.root)
        win.configure(padx=14, pady=12)
        tk.Label(win, text="Chọn các mục đẩy cho các máy khác:", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        vars_ = {}
        for c in publisher.CATEGORIES:
            row = tk.Frame(win, bg=COL_PANEL)
            row.pack(fill="x", pady=2)
            if c["locked"]:
                tk.Label(row, text=f"🔒 {c['label']}", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                         font=("Segoe UI", 9)).pack(anchor="w")
                tk.Label(row, text=c["locked"], bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8),
                         wraplength=560, justify="left").pack(anchor="w", padx=22)
                continue
            info = scan.get(c["key"], {"count": 0, "bytes": 0})
            v = tk.BooleanVar(value=bool(c["default"] and info["count"]))
            vars_[c["key"]] = v
            DarkCheck(row, f"{c['label']}  —  {info['count']} file, {_fmt_size(info['bytes'])}", v,
                      bg=COL_PANEL, font=("Segoe UI", 9)).pack(anchor="w")
            if c["hint"]:
                tk.Label(row, text=c["hint"], bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8),
                         wraplength=560, justify="left").pack(anchor="w", padx=22)

        tk.Label(win, text="Ghi chú phiên bản (hiện cho các máy khi cập nhật):", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 2))
        notes = tk.Text(win, height=3, width=70, bg=COL_ENTRY, fg=COL_TEXT, insertbackground=COL_TEXT,
                        relief="flat", font=("Segoe UI", 9))
        notes.pack(fill="x")

        tk.Label(win, text="Token GitHub (fine-grained, quyền Contents: Read and write cho repo này):",
                 bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 2))
        tok = tk.StringVar(value=cfg.get("token", ""))
        tk.Entry(win, textvariable=tok, show="•", bg=COL_ENTRY, fg=COL_TEXT, insertbackground=COL_TEXT,
                 relief="flat", font=("Segoe UI", 9)).pack(fill="x", ipady=3)
        tk.Label(win, text="Tạo tại github.com → Settings → Developer settings → Fine-grained tokens. "
                           "Token chỉ lưu trên máy này (data/publish_config.json).",
                 bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=560, justify="left").pack(anchor="w")

        btns = tk.Frame(win, bg=COL_PANEL)
        btns.pack(fill="x", pady=(12, 0))

        def _go():
            keys = [k for k, v in vars_.items() if v.get()]
            token = tok.get().strip()
            if not keys:
                messagebox.showwarning("Phát Hành", "Hãy tick ít nhất 1 mục.", parent=win)
                return
            if not token:
                messagebox.showwarning("Phát Hành", "Chưa nhập token GitHub.", parent=win)
                return
            note_txt = notes.get("1.0", "end").strip()
            try:
                publisher.save_config(None, token=token)
            except OSError:
                pass
            win.destroy()
            self._publish_check_then_confirm(keys, note_txt, token, scan)

        RoundedButton(btns, "🚀 Phát Hành", command=_go, bg=COL_GREEN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9), pady=7).pack(side="right", padx=4)
        RoundedButton(btns, "Huỷ", command=win.destroy, bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9), pady=7).pack(side="right", padx=4)

    # ------------------------------------------------------------ kiểm quyền -> xác nhận -> phát hành
    def _publish_check_then_confirm(self, keys, notes, token, scan):
        self._publish_busy = True
        self._log("info", "🚀 Đang kiểm tra token GitHub...")

        def _done(info, err):
            self._publish_busy = False
            if err is not None:
                messagebox.showerror("Phát Hành", str(err) if isinstance(err, publisher.PublishError)
                                     else f"Lỗi không mong đợi: {err}", parent=self.root)
                return
            files = sum(scan[k]["count"] for k in keys)
            size = sum(scan[k]["bytes"] for k in keys)
            names = ", ".join(publisher.CATEGORY_BY_KEY[k]["label"] for k in keys)
            msg = (f"Sẽ phát hành lên: {info['full_name']}\nMục: {names}\nTổng: {files} file, {_fmt_size(size)}\n\n")
            if not info["private"]:
                msg += ("⚠ Repo này CÔNG KHAI: ai cũng tải được nội dung gói (kịch bản, ảnh mẫu, dữ liệu đã tick).\n\n")
            msg += ("Các mục dữ liệu (data/*.json) sẽ GHI ĐÈ nguyên file trên máy nhận (có sao lưu).\n"
                    "Tài khoản và cài đặt KHÔNG được gửi.\n\nPhát hành ngay?")
            if not messagebox.askyesno("Xác nhận phát hành", msg, parent=self.root):
                return
            self._publish_apply(keys, notes, token)

        self._publish_run_bg(lambda: publisher.check_access(token, publisher.load_config().get("repo") or None), _done)

    def _publish_apply(self, keys, notes, token):
        self._publish_busy = True
        btn = getattr(self, "btn_publish", None)
        try:
            if btn:
                btn.set_text("🚀 Đang phát hành...")
                btn.set_state("disabled")
        except Exception:
            pass
        msgs = []

        def _tick():
            while msgs:
                self._log("info", "🚀 " + msgs.pop(0))
            if self._publish_busy:
                self.root.after(300, _tick)
        self.root.after(300, _tick)

        def _done(res, err):
            self._publish_busy = False
            while msgs:
                self._log("info", "🚀 " + msgs.pop(0))
            try:
                if btn:
                    btn.set_text("🚀 Phát Hành")
                    btn.set_state("normal")
            except Exception:
                pass
            if err is not None:
                m = str(err) if isinstance(err, publisher.PublishError) else f"Lỗi không mong đợi: {err}"
                self._log("error", "🚀 Phát hành thất bại: " + m)
                messagebox.showerror("Phát hành thất bại", m + "\n\nKhông có bản nào được công bố.", parent=self.root)
                return
            self._log("info", f"🚀 Đã phát hành {res['tag']} ({res['files']} file). Các máy khác bấm '🔄 Cập Nhật'.")
            messagebox.showinfo("Phát Hành", f"Đã phát hành {res['tag']} ({res['files']} file, "
                                             f"{_fmt_size(res['zip_bytes'])}).\nCác máy khác sẽ thấy 'Có bản mới'.",
                                parent=self.root)

        self._publish_run_bg(lambda: publisher.publish(None, keys, notes, token, progress=msgs.append), _done)

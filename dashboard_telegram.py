"""
dashboard_telegram.py — Cửa sổ "📨 Telegram": nhập Bot Token/Chat ID, chọn loại
sự kiện được gửi về điện thoại, bấm "Gửi thử". Logic gửi nằm ở notifier.py.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành 1
Mixin theo chức năng - mọi "self." trỏ vào cùng 1 instance DashboardApp.
"""

import threading
import tkinter as tk
from tkinter import messagebox

from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, _bind_esc_close, ThemedToplevel
import window_geometry as wg
import notifier


class TelegramMixin:
    def open_telegram_settings(self):
        win = ThemedToplevel(self.root)
        win.title("📨 Thông báo Telegram")
        win.configure(bg=COL_PANEL)
        _geo_name = wg.slug_name("telegram", "settings")
        wg.restore_geometry(win, _geo_name, default="520x560")
        win.minsize(460, 500)
        wg.autosave(win, _geo_name)
        win.transient(self.root)
        win.focus_set()
        _bind_esc_close(win)

        cfg = notifier.load_config()

        tk.Label(win, text="📨 Thông báo qua Telegram", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        tk.Label(win, text="Tạo bot bằng @BotFather để lấy Token; nhắn bot 1 tin rồi lấy Chat ID "
                           "(vd qua @userinfobot). Token là BÍ MẬT - chỉ lưu trên máy này "
                           "(data/telegram_config.json, đã loại khỏi Git).",
                 bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=480,
                 justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        enabled_var = tk.BooleanVar(value=bool(cfg["enabled"]))
        DarkCheck(win, "Bật thông báo Telegram", enabled_var, bg=COL_PANEL,
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(0, 6))

        form = tk.Frame(win, bg=COL_PANEL)
        form.pack(fill="x", padx=14)
        token_var = tk.StringVar(value=cfg["token"])
        chat_var = tk.StringVar(value=cfg["chat_id"])
        interval_var = tk.StringVar(value=str(cfg["min_interval_sec"]))
        shot_var = tk.BooleanVar(value=bool(cfg["send_screenshot"]))

        def _row(r, label, var, show=None, width=38):
            tk.Label(form, text=label, bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 9)
                     ).grid(row=r, column=0, sticky="w", pady=3, padx=(0, 8))
            e = tk.Entry(form, textvariable=var, font=("Segoe UI", 9), width=width, show=show)
            e.grid(row=r, column=1, sticky="we", pady=3)
            return e
        form.columnconfigure(1, weight=1)
        _row(0, "Bot Token:", token_var, show="•")
        _row(1, "Chat ID:", chat_var)
        _row(2, "Gộp tin trùng (giây):", interval_var, width=8)

        DarkCheck(win, "Gửi kèm ảnh chụp màn hình khi tác vụ lỗi", shot_var, bg=COL_PANEL
                  ).pack(anchor="w", padx=14, pady=(6, 4))

        tk.Label(win, text="Gửi khi có sự kiện:", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(8, 2))
        event_vars = {}
        for key, (label, _default) in notifier.EVENTS.items():
            v = tk.BooleanVar(value=bool(cfg["events"].get(key, False)))
            event_vars[key] = v
            DarkCheck(win, label, v, bg=COL_PANEL).pack(anchor="w", padx=26, pady=1)

        status = tk.Label(win, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8),
                          wraplength=480, justify="left")
        status.pack(anchor="w", padx=14, pady=(10, 0))

        def _collect():
            try:
                interval = max(0, int(interval_var.get().strip() or "0"))
            except ValueError:
                interval = notifier.DEFAULT_CONFIG["min_interval_sec"]
            return {
                "enabled": bool(enabled_var.get()),
                "token": token_var.get().strip(),
                "chat_id": chat_var.get().strip(),
                "send_screenshot": bool(shot_var.get()),
                "min_interval_sec": interval,
                "events": {k: bool(v.get()) for k, v in event_vars.items()},
            }

        def _test():
            data = _collect()
            status.config(text="⏳ Đang gửi tin thử...", fg=COL_TEXT_MUTED)

            def _run():
                ok, msg = notifier.send_test(data["token"], data["chat_id"])

                def _show():
                    try:
                        status.config(text=("✅ Gửi thử thành công - kiểm tra Telegram." if ok
                                            else f"❌ Gửi thử thất bại: {msg}"),
                                      fg=COL_TEXT if ok else "#ff6b6b")
                    except tk.TclError:
                        pass  # cửa sổ đã đóng
                self.root.after(0, _show)
            threading.Thread(target=_run, daemon=True).start()

        def _save():
            data = _collect()
            if data["enabled"] and (not data["token"] or not data["chat_id"]):
                messagebox.showwarning("Thiếu thông tin", "Cần nhập cả Bot Token và Chat ID để bật thông báo.",
                                       parent=win)
                return
            try:
                notifier.save_config(data)
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không lưu được cài đặt: {e}", parent=win)
                return
            self._log("info", "Đã lưu cài đặt thông báo Telegram ("
                      + ("BẬT" if data["enabled"] else "tắt") + ").")
            win.destroy()

        btns = tk.Frame(win, bg=COL_PANEL)
        btns.pack(fill="x", padx=14, pady=14, side="bottom")
        RoundedButton(btns, "📨 Gửi thử", command=_test, bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9, "bold"), padx=14, pady=6).pack(side="left")
        RoundedButton(btns, "💾 Lưu", command=_save, bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9, "bold"), padx=18, pady=6).pack(side="right")
        RoundedButton(btns, "Đóng", command=win.destroy, bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9), padx=14, pady=6).pack(side="right", padx=8)

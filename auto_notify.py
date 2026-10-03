"""
auto_notify.py — Thay các hộp thoại tkinter.messagebox mặc định bằng bản:
  1) THÔNG BÁO (showinfo / showwarning / showerror) TỰ TẮT sau
     AUTO_CLOSE_SECONDS giây nếu người dùng không bấm gì - và KHÔNG chờ:
     hàm trả về "ok" ngay, cửa sổ tự sống + tự đóng bằng timer riêng.
  2) CÂU HỎI (askyesno / askokcancel / askretrycancel / askyesnocancel /
     askquestion) KHÔNG tự tắt (phải có người quyết định, tự chọn hộ dễ
     nguy hiểm - vd xác nhận xoá) nhưng KHÔNG CHẶN (không grab) các cửa sổ
     khác của chương trình - hộp thoại gốc của Windows chặn cả cửa sổ cha.
  3) simpledialog.askstring/askfloat/askinteger: bỏ grab_set() để cũng
     không chặn cửa sổ khác.

LỖI CŨ: messagebox gốc là hộp thoại HỆ ĐIỀU HÀNH - vừa chặn cửa sổ cha,
vừa không có cách nào đặt timeout để tự tắt, nên 1 thông báo lỡ hiện ra
(nhất là lúc chạy tự động/hẹn giờ) sẽ nằm đó tới khi có người bấm OK, chặn
luôn thao tác ở cửa sổ khác.

CÁCH DÙNG: chỉ cần gọi auto_notify.install() 1 lần lúc khởi động (đã gọi
sẵn ở dashboard.py và gui.py). Code cũ vẫn viết `messagebox.showinfo(...)`
như trước, không cần sửa từng chỗ gọi (install() thay thẳng các hàm trong
module tkinter.messagebox nên mọi nơi đã import đều được áp dụng).

AN TOÀN: gọi từ thread khác (không phải main thread) -> thông báo được xếp
lịch hiện ở main thread (root.after) và trả về "ok" ngay; câu hỏi từ thread
khác hoặc bất kỳ lỗi nào khi dựng hộp thoại tuỳ biến -> tự rơi về hộp thoại
gốc, không bao giờ làm mất thông báo/câu hỏi.
"""
import threading
import tkinter as tk
from tkinter import messagebox as _mb
from tkinter import simpledialog as _sd

AUTO_CLOSE_SECONDS = 5
_MAX_OPEN_NOTICES = 6

from dashboard_theme import (
    COL_PANEL as _BG, COL_TEXT as _FG, COL_TEXT_MUTED as _MUTED, COL_HEADER as _BAR_BG,
    COL_BORDER as _BORDER, COL_TEAL, COL_ORANGE, COL_RED, COL_BLUE, COL_GREEN, COL_GRAY_BTN,
    COL_SHADOW,
)
from dashboard_widgets import ThemedToplevel, RoundedButton, _mix

# kind -> (ký hiệu vẽ trong huy hiệu tròn 3D, màu chủ đạo)
_ICONS = {
    "info": ("i", COL_TEAL),
    "warning": ("!", COL_ORANGE),
    "error": ("×", COL_RED),
    "question": ("?", COL_BLUE),
}

_ORIG = {n: getattr(_mb, n) for n in (
    "showinfo", "showwarning", "showerror", "askyesno", "askokcancel",
    "askretrycancel", "askyesnocancel", "askquestion")}
_ORIG_SD_GRAB = _sd.Dialog.grab_set

_open_notices = []   # [{"win", "key", "reset"}] các thông báo đang mở
_installed = False


def _default_root():
    return getattr(tk, "_default_root", None)


def _parent_toplevel(parent):
    try:
        if parent is not None:
            return parent.winfo_toplevel()
    except Exception:
        pass
    return _default_root()


def _build(kind, title, message, buttons, default_key, cancel_value, parent, auto_close):
    """Dựng 1 hộp thoại KHÔNG grab. `buttons`: list (nhãn, giá_trị, khoá).
    Trả về (top, res) - res["v"] là giá trị người dùng chọn."""
    parent_top = _parent_toplevel(parent)
    top = ThemedToplevel(parent_top)
    top.withdraw()
    top.title(title or "Thông báo")
    top.resizable(False, False)
    top.configure(bg=_BG)
    try:
        if parent_top is not None and parent_top.winfo_viewable():
            top.transient(parent_top)
    except Exception:
        pass

    res = {"v": cancel_value}
    icon, color = _ICONS.get(kind, _ICONS["info"])

    tk.Frame(top, bg=color, height=4).pack(fill="x")     # dải màu theo loại thông báo
    body = tk.Frame(top, bg=_BG)
    body.pack(fill="both", expand=True, padx=18, pady=(16, 8))
    badge = tk.Canvas(body, width=46, height=46, bg=_BG, highlightthickness=0)
    badge.pack(side="left", anchor="n", padx=(0, 14))
    badge.create_oval(4, 6, 44, 46, fill=COL_SHADOW, outline=COL_SHADOW)          # bóng
    badge.create_oval(3, 3, 43, 43, fill=color, outline=_mix(color, "#000000", 0.35), width=2)
    badge.create_oval(9, 6, 37, 22, fill=_mix(color, "#ffffff", 0.22), outline="")  # ánh sáng
    badge.create_text(23, 23, text=icon, fill="#ffffff", font=("Segoe UI", 18, "bold"))
    tk.Label(body, text=str(message if message is not None else ""), bg=_BG, fg=_FG,
             font=("Segoe UI", 10), justify="left", wraplength=440).pack(side="left", anchor="w")

    tk.Frame(top, bg=_BORDER, height=1).pack(fill="x", pady=(6, 0))
    bar = tk.Frame(top, bg=_BAR_BG)
    bar.pack(fill="x")
    lbl_cd = tk.Label(bar, text="", bg=_BAR_BG, fg=_MUTED, font=("Segoe UI", 8))
    lbl_cd.pack(side="left", padx=(14, 0))

    def _choose(value):
        res["v"] = value
        try:
            top.destroy()
        except Exception:
            pass

    default_btn = None
    for label, value, key in reversed(buttons):
        _is_primary = key in ("ok", "yes", "retry")
        b = RoundedButton(bar, label, command=lambda v=value: _choose(v),
                          bg=(COL_GREEN if _is_primary else COL_GRAY_BTN), container_bg=_BAR_BG,
                          font=("Segoe UI", 9, "bold"), padx=18, pady=6, width=84)
        b.pack(side="right", padx=(0, 10), pady=10)
        if key == default_key or (default_btn is None and key is None):
            default_btn = b
    if default_btn is None and buttons:
        default_btn = bar.winfo_children()[-1]

    top.protocol("WM_DELETE_WINDOW", lambda: _choose(cancel_value))
    top.bind("<Escape>", lambda e: _choose(cancel_value))
    default_value = next((v for _l, v, k in buttons if k == default_key), buttons[0][1])
    top.bind("<Return>", lambda e: _choose(default_value))

    remaining = [AUTO_CLOSE_SECONDS]

    def _tick():
        try:
            if not top.winfo_exists():
                return
            if remaining[0] <= 0:
                _choose(default_value if kind != "question" else cancel_value)
                return
            lbl_cd.config(text=f"Tự đóng sau {remaining[0]}s")
            remaining[0] -= 1
            top.after(1000, _tick)
        except Exception:
            pass

    if auto_close:
        _tick()

    # Vị trí: giữa cửa sổ cha, xếp lệch nhẹ nếu đang có nhiều thông báo cùng lúc.
    top.update_idletasks()
    w, h = top.winfo_reqwidth(), top.winfo_reqheight()
    try:
        if parent_top is not None and parent_top.winfo_viewable():
            px, py = parent_top.winfo_rootx(), parent_top.winfo_rooty()
            pw, ph = parent_top.winfo_width(), parent_top.winfo_height()
        else:
            px, py, pw, ph = 0, 0, top.winfo_screenwidth(), top.winfo_screenheight()
    except Exception:
        px, py, pw, ph = 0, 0, top.winfo_screenwidth(), top.winfo_screenheight()
    shift = 26 * (len(_open_notices) % 5)
    x = max(0, px + (pw - w) // 2 + shift)
    y = max(0, py + (ph - h) // 2 + shift)
    top.geometry(f"+{x}+{y}")
    top.deiconify()
    try:
        top.lift()
        top.focus_force()
        if default_btn is not None:
            default_btn.focus_set()
    except Exception:
        pass

    top._auto_notify_reset = lambda: remaining.__setitem__(0, AUTO_CLOSE_SECONDS)
    return top, res


def _notify_main(kind, title, message, options):
    key = (kind, title, str(message))
    for item in list(_open_notices):
        try:
            alive = item["win"].winfo_exists()
        except Exception:
            alive = False
        if not alive:
            _open_notices.remove(item)
        elif item["key"] == key:      # trùng y hệt -> chỉ gia hạn, không mở thêm
            item["win"]._auto_notify_reset()
            return "ok"
    while len(_open_notices) >= _MAX_OPEN_NOTICES:
        old = _open_notices.pop(0)
        try:
            old["win"].destroy()
        except Exception:
            pass
    top, _res = _build(kind, title, message, [("OK", "ok", "ok")], "ok", "ok",
                       options.get("parent"), auto_close=True)
    _open_notices.append({"win": top, "key": key})
    return "ok"


def _make_notify(kind, orig_name):
    def _fn(title=None, message=None, **options):
        orig = _ORIG[orig_name]
        if threading.current_thread() is not threading.main_thread():
            root = _default_root()
            if root is not None:
                try:
                    root.after(0, lambda: _safe_notify_main(kind, title, message, options, orig))
                    return "ok"
                except Exception:
                    pass
            try:
                return orig(title, message, **options)
            except Exception:      # mainloop chưa chạy/đang tắt: bỏ qua, không văng lỗi vào thread gọi
                return "ok"
        return _safe_notify_main(kind, title, message, options, orig)
    _fn.__name__ = orig_name
    return _fn


def _safe_notify_main(kind, title, message, options, orig):
    try:
        return _notify_main(kind, title, message, options)
    except Exception:
        try:
            return orig(title, message, **options)
        except Exception:
            return "ok"


def _make_ask(orig_name, buttons, default_key, cancel_value, as_string=False):
    def _fn(title=None, message=None, **options):
        orig = _ORIG[orig_name]
        if threading.current_thread() is not threading.main_thread() or _default_root() is None:
            return orig(title, message, **options)
        try:
            dkey = options.get("default") or default_key
            top, res = _build("question", title, message, buttons, dkey, cancel_value,
                              options.get("parent"), auto_close=False)
            top.wait_window()     # vòng lặp con, KHÔNG grab -> cửa sổ khác vẫn thao tác được
            return res["v"]
        except Exception:
            return orig(title, message, **options)
    _fn.__name__ = orig_name
    return _fn


def install():
    """Thay các hàm của tkinter.messagebox/simpledialog (idempotent)."""
    global _installed
    if _installed:
        return
    _installed = True
    _mb.showinfo = _make_notify("info", "showinfo")
    _mb.showwarning = _make_notify("warning", "showwarning")
    _mb.showerror = _make_notify("error", "showerror")
    _mb.askyesno = _make_ask(
        "askyesno", [("Có", True, "yes"), ("Không", False, "no")], "yes", False)
    _mb.askokcancel = _make_ask(
        "askokcancel", [("OK", True, "ok"), ("Hủy", False, "cancel")], "ok", False)
    _mb.askretrycancel = _make_ask(
        "askretrycancel", [("Thử lại", True, "retry"), ("Hủy", False, "cancel")], "retry", False)
    _mb.askyesnocancel = _make_ask(
        "askyesnocancel",
        [("Có", True, "yes"), ("Không", False, "no"), ("Hủy", None, "cancel")], "yes", None)
    _mb.askquestion = _make_ask(
        "askquestion", [("Có", "yes", "yes"), ("Không", "no", "no")], "yes", "no")
    # simpledialog.askstring/askfloat/askinteger: bỏ grab -> không chặn cửa sổ khác.
    _sd.Dialog.grab_set = lambda self, *a, **k: None

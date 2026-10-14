"""
dashboard_widgets.py — Các widget Tkinter tự vẽ dùng chung trong toàn bộ
Dashboard (nút 3D bo tròn, checkbox tối màu, thanh tự xuống dòng, khối MỤC,
khối nhóm nút ToolGroup, cửa sổ popup ThemedToplevel), cùng các hàm tiện ích
(_set_dpi_awareness, _bind_esc_close, apply_global_theme,
install_themed_simpledialog). Tách riêng khỏi dashboard.py để bất kỳ file
dashboard_*.py nào cũng import được mà không phải phụ thuộc vào toàn bộ
DashboardApp.

ĐỒNG BỘ THEME (đợt giao diện 3D):
- apply_global_theme(root): gọi 1 LẦN duy nhất ở DashboardApp.__init__ - đặt
  style ttk (Scrollbar, Combobox, Spinbox, Treeview...) + giá trị mặc định
  (option_add) cho tk.Entry/Text/Listbox/Menu/... -> mọi cửa sổ, popup, ô
  nhập liệu dù chưa tự đặt màu vẫn ra đúng tông tối của Dashboard.
- ThemedToplevel: thay cho tk.Toplevel ở mọi popup - nền/viền đồng bộ + thanh
  tiêu đề tối (Windows 10/11).
- Btn3D: nút 3D thay thẳng cho ttk.Button/tk.Button (dùng ở LD Macro Studio).
- install_themed_simpledialog(): thay simpledialog.askstring/askinteger/askfloat
  bằng hộp nhập cùng theme (không grab, giống auto_notify.py).
- Hộp thoại thông báo/xác nhận (messagebox) do auto_notify.py đảm nhận - file
  đó tự dùng ThemedToplevel + RoundedButton của module này.
"""
import tkinter as tk
from tkinter import ttk
import ctypes
import math
import threading

from dashboard_theme import (
    COL_BG, COL_PANEL, COL_PANEL_ALT, COL_HEADER, COL_BORDER, COL_TEXT,
    COL_TEXT_MUTED, COL_BLUE, COL_TEAL, COL_GRAY_BTN, COL_CHECK_ON,
    COL_CHECK_OFF, COL_GREEN, COL_RED, COL_ENTRY, COL_SHADOW,
    COL_HIGHLIGHT, COL_SELECT,
)


def _set_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _bind_esc_close(win):
    """Cho phép bấm phím ESC để đóng nhanh 1 cửa sổ popup (Toplevel), thay
    vì bắt buộc phải rê chuột tới nút X/Đóng - áp dụng cho mọi popup cài
    đặt/chọn lựa trong Dashboard."""
    win.bind("<Escape>", lambda e: win.destroy())


# ======================= TIỆN ÍCH MÀU =======================
def _to_rgb(color, widget=None):
    """'#rrggbb' hoặc tên màu Tk ('white'...) -> (r, g, b) 0..255."""
    try:
        c = color.lstrip("#")
        if color.startswith("#") and len(c) == 6:
            return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        pass
    try:
        w = widget or tk._default_root
        r, g, b = w.winfo_rgb(color)
        return (r // 257, g // 257, b // 257)
    except Exception:
        return (128, 128, 128)


def _rgb_hex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))


def _mix(c1, c2, t):
    """Trộn màu c1 -> c2 theo tỉ lệ t (0 = c1, 1 = c2)."""
    a = _to_rgb(c1)
    b = _to_rgb(c2)
    return _rgb_hex(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _round_rect_points(x1, y1, x2, y2, r):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1
    ]


# ======================= CỬA SỔ / TITLE BAR =======================
def _apply_dark_titlebar(win):
    """Thanh tiêu đề tối + màu viền/chữ đồng bộ theme (Windows 10 1809+ /
    Windows 11). Hệ điều hành/phiên bản không hỗ trợ thì âm thầm bỏ qua -
    cửa sổ vẫn dùng bình thường với thanh tiêu đề mặc định."""
    try:
        win.update_idletasks()
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        dwm = ctypes.windll.dwmapi
        one = ctypes.c_int(1)
        for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (20; bản cũ 19)
            if dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(one), ctypes.sizeof(one)) == 0:
                break
        for attr, col in ((35, COL_HEADER), (34, COL_BORDER), (36, COL_TEXT)):
            r, g, b = _to_rgb(col)
            c = ctypes.c_int(r | (g << 8) | (b << 16))  # COLORREF 0x00BBGGRR (Windows 11)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(c), ctypes.sizeof(c))
    except Exception:
        pass


class ThemedToplevel(tk.Toplevel):
    """Thay thế tk.Toplevel cho MỌI popup của Dashboard: nền + viền mảnh
    đúng tông theme, thanh tiêu đề tối. API y hệt tk.Toplevel (mọi lệnh
    .title()/.geometry()/.transient()/.configure(bg=...) đều dùng như cũ)."""

    def __init__(self, master=None, **kw):
        kw.setdefault("bg", COL_PANEL)
        kw.setdefault("highlightthickness", 1)
        kw.setdefault("highlightbackground", COL_BORDER)
        super().__init__(master, **kw)
        self._titlebar_done = False
        self.bind("<Map>", self._on_map_theme, add="+")
        self.after(20, lambda: _apply_dark_titlebar(self))

    def _on_map_theme(self, event=None):
        if event is not None and event.widget is not self:
            return
        if not self._titlebar_done:
            self._titlebar_done = True
            _apply_dark_titlebar(self)


# ======================= THEME TOÀN CỤC =======================
def apply_global_theme(root):
    """Gọi 1 lần (trước khi dựng giao diện) - đồng bộ theme tối cho MỌI
    widget tiêu chuẩn kể cả popup/ô nhập chưa tự đặt màu."""
    # ----- ttk -----
    try:
        style = ttk.Style(root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", background=COL_PANEL, foreground=COL_TEXT,
                        fieldbackground=COL_ENTRY, bordercolor=COL_BORDER,
                        troughcolor=COL_BG, focuscolor=COL_BLUE)
        style.configure("TFrame", background=COL_PANEL)
        style.configure("TLabel", background=COL_PANEL, foreground=COL_TEXT)
        style.configure("TLabelframe", background=COL_PANEL, bordercolor=COL_BORDER,
                        lightcolor=COL_BORDER, darkcolor=COL_BORDER, relief="solid")
        style.configure("TLabelframe.Label", background=COL_PANEL, foreground=COL_TEXT_MUTED)

        for orient in ("Vertical", "Horizontal", ""):
            name = f"{orient}.TScrollbar" if orient else "TScrollbar"
            style.configure(name, gripcount=0, background=COL_GRAY_BTN,
                            darkcolor=COL_GRAY_BTN, lightcolor=COL_HIGHLIGHT,
                            troughcolor=COL_BG, bordercolor=COL_BG,
                            arrowcolor=COL_TEXT_MUTED, relief="flat", arrowsize=13)
            style.map(name, background=[("pressed", COL_BLUE), ("active", COL_HIGHLIGHT)],
                      arrowcolor=[("active", COL_TEXT)])

        for name in ("TCombobox", "TSpinbox", "TEntry"):
            style.configure(name, fieldbackground=COL_ENTRY, background=COL_HEADER,
                            foreground=COL_TEXT, insertcolor=COL_TEXT,
                            bordercolor=COL_BORDER, lightcolor=COL_BORDER,
                            darkcolor=COL_BORDER, arrowcolor=COL_TEXT_MUTED,
                            selectbackground=COL_SELECT, selectforeground="#ffffff",
                            padding=3)
            style.map(name,
                      fieldbackground=[("readonly", COL_ENTRY), ("disabled", COL_PANEL_ALT)],
                      foreground=[("disabled", COL_TEXT_MUTED)],
                      bordercolor=[("focus", COL_BLUE)],
                      lightcolor=[("focus", COL_BLUE)],
                      darkcolor=[("focus", COL_BLUE)],
                      background=[("active", COL_HIGHLIGHT)],
                      selectbackground=[("readonly", COL_ENTRY)],
                      selectforeground=[("readonly", COL_TEXT)],
                      arrowcolor=[("active", COL_TEXT)])

        style.configure("Treeview", background=COL_PANEL_ALT, fieldbackground=COL_PANEL_ALT,
                        foreground=COL_TEXT, rowheight=26, bordercolor=COL_BORDER,
                        lightcolor=COL_BORDER, darkcolor=COL_BORDER, relief="flat")
        style.configure("Treeview.Heading", background=COL_HEADER, foreground=COL_TEXT,
                        bordercolor=COL_BORDER, lightcolor=COL_HIGHLIGHT, darkcolor=COL_BORDER,
                        relief="raised", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", COL_SELECT)],
                  foreground=[("selected", "#ffffff")])
        style.map("Treeview.Heading", background=[("active", COL_HIGHLIGHT)])

        style.configure("TButton", background=COL_GRAY_BTN, foreground=COL_TEXT,
                        bordercolor=COL_BORDER, lightcolor=COL_HIGHLIGHT, darkcolor=COL_SHADOW,
                        focuscolor=COL_GRAY_BTN, padding=(10, 4), relief="raised")
        style.map("TButton", background=[("pressed", COL_SHADOW), ("active", COL_HIGHLIGHT)])
        for name in ("TCheckbutton", "TRadiobutton"):
            style.configure(name, background=COL_PANEL, foreground=COL_TEXT,
                            indicatorbackground=COL_ENTRY, indicatorforeground="#ffffff",
                            upperbordercolor=COL_BORDER, lowerbordercolor=COL_BORDER,
                            bordercolor=COL_BORDER, focuscolor=COL_PANEL)
            style.map(name, background=[("active", COL_PANEL)],
                      indicatorcolor=[("selected", COL_CHECK_ON), ("pressed", COL_HIGHLIGHT),
                                      ("!selected", COL_ENTRY)],
                      indicatorbackground=[("selected", COL_CHECK_ON), ("!selected", COL_ENTRY)],
                      foreground=[("disabled", COL_TEXT_MUTED)])
        style.configure("TPanedwindow", background=COL_BG)
        style.configure("Sash", sashthickness=6, gripcount=0, background=COL_HIGHLIGHT,
                        bordercolor=COL_BORDER, lightcolor=COL_HIGHLIGHT, darkcolor=COL_HIGHLIGHT)
        style.configure("TScale", background=COL_PANEL, troughcolor=COL_ENTRY,
                        bordercolor=COL_BORDER, lightcolor=COL_HIGHLIGHT, darkcolor=COL_GRAY_BTN)
        style.configure("TSizegrip", background=COL_PANEL)
        style.configure("TNotebook", background=COL_PANEL, bordercolor=COL_BORDER)
        style.configure("TNotebook.Tab", background=COL_HEADER, foreground=COL_TEXT_MUTED, padding=(12, 5))
        style.map("TNotebook.Tab", background=[("selected", COL_PANEL)],
                  foreground=[("selected", COL_TEXT)])
        style.configure("TProgressbar", background=COL_GREEN, troughcolor=COL_PANEL_ALT,
                        bordercolor=COL_BORDER, lightcolor=COL_GREEN, darkcolor=COL_GREEN)
        style.configure("TSeparator", background=COL_BORDER)
    except Exception:
        pass

    # ----- widget tk thuần: giá trị MẶC ĐỊNH (widget nào tự đặt màu thì vẫn ưu tiên màu tự đặt) -----
    def _opt(pattern, value):
        try:
            root.option_add(pattern, value)
        except Exception:
            pass

    for cls in ("Entry", "Spinbox"):
        _opt(f"*{cls}.background", COL_ENTRY)
        _opt(f"*{cls}.foreground", COL_TEXT)
        _opt(f"*{cls}.insertBackground", COL_TEXT)
        _opt(f"*{cls}.selectBackground", COL_SELECT)
        _opt(f"*{cls}.selectForeground", "#ffffff")
        _opt(f"*{cls}.disabledBackground", COL_PANEL_ALT)
        _opt(f"*{cls}.disabledForeground", COL_TEXT_MUTED)
        _opt(f"*{cls}.readonlyBackground", COL_PANEL_ALT)
        _opt(f"*{cls}.relief", "flat")
        _opt(f"*{cls}.highlightThickness", 1)
        _opt(f"*{cls}.highlightBackground", COL_BORDER)
        _opt(f"*{cls}.highlightColor", COL_BLUE)
    for cls in ("Text", "Listbox"):
        _opt(f"*{cls}.background", COL_ENTRY)
        _opt(f"*{cls}.foreground", COL_TEXT)
        _opt(f"*{cls}.selectBackground", COL_SELECT)
        _opt(f"*{cls}.selectForeground", "#ffffff")
        _opt(f"*{cls}.relief", "flat")
        _opt(f"*{cls}.highlightThickness", 1)
        _opt(f"*{cls}.highlightBackground", COL_BORDER)
        _opt(f"*{cls}.highlightColor", COL_BLUE)
    _opt("*Text.insertBackground", COL_TEXT)
    _opt("*Toplevel.background", COL_PANEL)
    _opt("*Frame.background", COL_PANEL)
    _opt("*Label.background", COL_PANEL)
    _opt("*Label.foreground", COL_TEXT)
    _opt("*LabelFrame.background", COL_PANEL)
    _opt("*LabelFrame.foreground", COL_TEXT_MUTED)
    for cls in ("Checkbutton", "Radiobutton"):
        _opt(f"*{cls}.background", COL_PANEL)
        _opt(f"*{cls}.foreground", COL_TEXT)
        _opt(f"*{cls}.activeBackground", COL_PANEL)
        _opt(f"*{cls}.activeForeground", COL_TEXT)
        _opt(f"*{cls}.selectColor", COL_PANEL_ALT)
    _opt("*Button.background", COL_GRAY_BTN)
    _opt("*Button.foreground", COL_TEXT)
    _opt("*Button.activeBackground", COL_HIGHLIGHT)
    _opt("*Button.activeForeground", "#ffffff")
    _opt("*Button.relief", "flat")
    _opt("*Button.borderWidth", 0)
    _opt("*PanedWindow.background", COL_BG)
    _opt("*Scale.background", COL_PANEL)
    _opt("*Scale.foreground", COL_TEXT)
    _opt("*Scale.troughColor", COL_ENTRY)
    _opt("*Scale.highlightThickness", 0)
    _opt("*Canvas.highlightThickness", 0)
    _opt("*Menu.background", COL_HEADER)
    _opt("*Menu.foreground", COL_TEXT)
    _opt("*Menu.activeBackground", COL_SELECT)
    _opt("*Menu.activeForeground", "#ffffff")
    _opt("*Menu.relief", "flat")
    _opt("*Menu.borderWidth", 0)
    # Danh sách xổ xuống của ttk.Combobox là 1 tk.Listbox bên trong
    _opt("*TCombobox*Listbox.background", COL_ENTRY)
    _opt("*TCombobox*Listbox.foreground", COL_TEXT)
    _opt("*TCombobox*Listbox.selectBackground", COL_SELECT)
    _opt("*TCombobox*Listbox.selectForeground", "#ffffff")
    _opt("*TCombobox*Listbox.font", ("Segoe UI", 9))

    # Cửa sổ chính cũng dùng thanh tiêu đề tối cho đồng bộ với popup
    try:
        root.after(30, lambda: _apply_dark_titlebar(root))
    except Exception:
        pass

    # Lăn chuột giữa cho MỌI cửa sổ/popup (xem wheel_scroll.py) - cài 1 lần ở mức lớp widget
    # nên không bị bind_all/unbind_all của từng cửa sổ đè mất.
    try:
        from wheel_scroll import install_wheel_scroll
        install_wheel_scroll(root)
    except Exception:
        pass


class Tooltip:
    """Chú thích nhỏ hiện khi RÊ CHUỘT vào 1 widget (không cần bấm) - dùng
    cho các nút/nhãn hiển thị DẠNG RÚT GỌN (vd đếm số lượng, chữ bị cắt
    bớt) để xem được ĐẦY ĐỦ nội dung mà không cần bấm mở popup con (vd
    nút '🔗 Gán GL/TK' trong '⏰ Hẹn Giờ' chỉ hiện số lượng giả lập/tài
    khoản trên dòng lịch - rê chuột vào để xem ĐÚNG TÊN từng giả lập/tài
    khoản đã gán, xem dashboard_schedule.py).

    Cách dùng: `Tooltip(widget, lambda: "nội dung...")` - truyền 1 HÀM
    (không phải chuỗi cố định) để nội dung LUÔN LẤY MỚI NHẤT ngay lúc rê
    chuột vào (vd sau khi vừa đổi lựa chọn ở popup con), không bị đứng
    hình theo giá trị lúc khởi tạo. Tự ẩn nếu hàm trả về chuỗi rỗng."""

    def __init__(self, widget, text_fn, delay_ms=350):
        self.widget = widget
        self.text_fn = text_fn
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<Button-1>", self._on_leave, add="+")

    def _on_enter(self, _event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, _event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        text = ""
        try:
            text = self.text_fn() or ""
        except Exception:
            text = ""
        if not text:
            return
        self._hide()
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        try:
            self._tip.wm_attributes("-topmost", True)
        except Exception:
            pass
        self._tip.wm_geometry(f"+{x}+{y}")
        self._tip.configure(bg=COL_SHADOW)
        tk.Label(self._tip, text=text, bg=COL_HEADER, fg=COL_TEXT, font=("Segoe UI", 8),
                 justify="left", anchor="w", padx=10, pady=6,
                 highlightbackground=COL_BLUE, highlightthickness=1).pack(padx=(0, 2), pady=(0, 2))

    def _hide(self):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


class RoundedButton(tk.Canvas):
    """Nút bấm 3D bo tròn tự vẽ bằng Canvas: chuyển màu sáng -> tối theo
    chiều dọc, viền, vệt sáng phía trên, 'gờ' bóng phía dưới; rê chuột thì
    sáng hơn, GIỮ chuột thì nút lún xuống. Lệnh (command) chạy khi NHẢ chuột
    ngay trên nút (kéo chuột ra ngoài rồi nhả = huỷ, đúng như nút chuẩn).

    Giữ NGUYÊN toàn bộ API cũ (text_str, bg_color, fg_color, set_text(),
    set_state(), _redraw()...) - nơi nào đang đổi `btn.bg_color = ...` rồi
    gọi `btn._redraw()` vẫn chạy đúng."""

    DEPTH = 3  # độ dày 'gờ' 3D phía dưới (px)

    def __init__(self, parent, text, command=None, bg=COL_BLUE, fg="white",
                 container_bg=COL_BG, font=("Segoe UI", 9, "bold"),
                 padx=16, pady=8, radius=14, disabled_bg="#2a3244", width=None):
        super().__init__(parent, highlightthickness=0, bg=container_bg, bd=0, cursor="hand2")
        self.command = command
        self.text_str = text
        self.bg_color = bg
        self.disabled_bg = disabled_bg
        self.fg_color = fg
        self.font = font
        self.padx = padx
        self.pady = pady
        self.radius = radius
        self._state = "normal"
        self._min_width = width
        self._hover = False
        self._pressed = False

        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", self._on_leave)
        self.bind("<Configure>", lambda e: self._redraw(), add="+")

        self._compute_size()
        self._redraw()

    def _compute_size(self):
        tmp = tk.Label(self, text=self.text_str, font=self.font)
        tmp.update_idletasks()
        tw = tmp.winfo_reqwidth()
        th = tmp.winfo_reqheight()
        tmp.destroy()
        w = max(tw + self.padx * 2, self._min_width or 0)
        h = th + self.pady * 2 + self.DEPTH
        self.config(width=w, height=h)

    @staticmethod
    def _round_rect_points(x1, y1, x2, y2, r):
        return _round_rect_points(x1, y1, x2, y2, r)

    @staticmethod
    def _shade(hex_color, factor):
        r, g, b = _to_rgb(hex_color)
        return _rgb_hex(min(255, r * factor), min(255, g * factor), min(255, b * factor))

    def _redraw(self):
        self.delete("all")
        w = int(float(self["width"]))
        h = int(float(self["height"]))
        # Nút bị kéo giãn (pack fill / grid sticky) -> vẽ theo kích thước THẬT
        try:
            aw, ah = self.winfo_width(), self.winfo_height()
            if aw > 1 and ah > 1:
                w, h = aw, ah
        except tk.TclError:
            pass
        if w <= 1 or h <= 1:
            return
        d = self.DEPTH
        disabled = self._state == "disabled"
        base = self.disabled_bg if disabled else self.bg_color
        if self._hover and not disabled:
            base = _mix(base, "#ffffff", 0.13)
        pressed = self._pressed and not disabled
        off = (d - 1) if pressed else 0
        top = 1 + off
        bot = h - d - 1 + off
        face_h = max(2, bot - top)
        r = max(2, min(self.radius, face_h / 2.0))

        # 'Gờ' bóng phía dưới (tạo độ dày 3D) - lộ ra khi nút chưa bị nhấn
        lip = _mix(base, "#000000", 0.62)
        self.create_polygon(_round_rect_points(1, 1 + d, w - 1, h - 1, r),
                            smooth=True, fill=lip, outline=lip)

        # Thân nút: chuyển màu dọc (sáng ở trên -> tối ở dưới)
        if disabled:
            self.create_polygon(_round_rect_points(1, top, w - 1, bot, r),
                                smooth=True, fill=base, outline=base)
        else:
            light = _mix(base, "#ffffff", 0.26)
            dark = _mix(base, "#000000", 0.16)
            if pressed:
                light, dark = _mix(base, "#ffffff", 0.04), _mix(base, "#000000", 0.24)
            self.create_polygon(_round_rect_points(1, top, w - 1, bot, r),
                                smooth=True, fill=_mix(light, dark, 0.5), outline="")
            steps = int(face_h)
            for i in range(steps + 1):
                y = top + i
                t = i / float(steps or 1)
                dy = min(i, steps - i)
                inset = 0.0
                if dy < r:
                    inset = r - math.sqrt(max(0.0, r * r - (r - dy) ** 2))
                x1 = 1 + inset + 1
                x2 = w - 1 - inset - 1
                if x2 > x1:
                    self.create_line(x1, y, x2, y, fill=_mix(light, dark, t))
            # Vệt sáng mảnh ngay dưới mép trên (cảm giác bóng nhựa/kính)
            if not pressed:
                self.create_line(1 + r * 0.7, top + 1, w - 1 - r * 0.7, top + 1,
                                 fill=_mix(base, "#ffffff", 0.5))

        # Viền thân nút
        edge = _mix(base, "#000000", 0.35)
        self.create_polygon(_round_rect_points(1, top, w - 1, bot, r),
                            smooth=True, fill="", outline=edge)

        cx = w / 2
        cy = (top + bot) / 2 + 0.5
        if disabled:
            self.create_text(cx, cy, text=self.text_str, fill="#6b7488", font=self.font)
        else:
            self.create_text(cx + 1, cy + 1, text=self.text_str,
                             fill=_mix(base, "#000000", 0.55), font=self.font)
            self.create_text(cx, cy, text=self.text_str, fill=self.fg_color, font=self.font)

    def _set_hover(self, on):
        if self._state == "disabled":
            return
        self._hover = on
        self._redraw()

    def _on_leave(self, _event=None):
        self._pressed = False
        self._set_hover(False)

    def _on_press(self, _event=None):
        if self._state == "disabled":
            return
        self._pressed = True
        self._redraw()

    def _on_release(self, event=None):
        was_pressed = self._pressed
        self._pressed = False
        if self._state == "disabled":
            return
        inside = True
        if event is not None:
            inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        try:
            self._redraw()
        except tk.TclError:
            return
        if was_pressed and inside:
            self._on_click()

    def _on_click(self, _event=None):
        if self._state == "disabled":
            return
        if self.command:
            self.command()

    def set_text(self, text):
        self.text_str = text
        self._compute_size()
        self._redraw()

    def set_state(self, state):
        self._state = state
        try:
            self.config(cursor=("arrow" if state == "disabled" else "hand2"))
        except tk.TclError:
            pass
        self._redraw()


def _widget_bg(widget, default=COL_PANEL):
    """Màu nền của widget cha (tk hoặc ttk) - để nút 3D hoà vào nền."""
    try:
        return widget.cget("bg")
    except Exception:
        pass
    try:
        cls = widget.winfo_class()
        v = ttk.Style(widget).lookup(cls, "background")
        if v:
            return v
    except Exception:
        pass
    return default


# Màu nút tự chọn theo NỘI DUNG nhãn (chỉ dùng khi nơi gọi không truyền bg=)
_BTN_RED_WORDS = ("xóa", "xoá", "dừng", "⏹", "🗑", "gỡ")
_BTN_GREEN_WORDS = ("chạy", "bắt đầu", "▶", "ghi ")
_BTN_BLUE_WORDS = ("lưu", "ok", "áp dụng", "thêm", "đăng ký", "xác nhận", "đồng ý", "tạo",
                   "chọn", "mở", "quét", "chụp", "cắt", "nhập", "xuất", "tìm", "test", "🧪", "💾", "📂")


def _auto_button_color(text):
    t = (text or "").lower()
    if any(w in t for w in _BTN_RED_WORDS):
        return COL_RED
    if any(w in t for w in _BTN_GREEN_WORDS):
        return COL_GREEN
    if any(w in t for w in _BTN_BLUE_WORDS):
        return COL_BLUE
    return COL_GRAY_BTN


class Btn3D(RoundedButton):
    """Nút 3D dùng THAY THẾ trực tiếp cho ttk.Button / tk.Button (cùng cách
    dùng: Btn3D(parent, text=..., command=..., width=..., state=...), rồi
    .pack/.grid/.config(text=/state=/command=/bg=/fg=)). Màu nút tự chọn
    theo nhãn (Xoá/Dừng = đỏ, Chạy = xanh lá, Lưu/Thêm/Chọn... = xanh dương,
    còn lại = xám) trừ khi truyền bg=... riêng."""

    def __init__(self, parent, text="", command=None, width=None, state="normal",
                 bg=None, fg=None, font=None, padx=12, pady=4, style=None,
                 takefocus=None, cursor=None, **ignored):
        color = bg or _auto_button_color(text)
        fnt = font or ("Segoe UI", 9, "bold")
        min_px = None
        if width:
            try:
                import tkinter.font as tkfont
                min_px = int(tkfont.Font(font=fnt).measure("0") * int(width)) + padx * 2
            except Exception:
                min_px = None
        super().__init__(parent, text, command=command, bg=color, fg=fg or "white",
                         container_bg=_widget_bg(parent), font=fnt, padx=padx, pady=pady,
                         radius=10, width=min_px)
        self._custom_color = bg is not None
        if state == "disabled":
            self.set_state("disabled")

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = {**cnf, **kw}
        redraw = False
        if "text" in kw:
            self.text_str = kw.pop("text")
            if not self._custom_color:
                self.bg_color = _auto_button_color(self.text_str)
            self._compute_size()
            redraw = True
        for k in ("bg", "background"):
            if k in kw:
                self.bg_color = kw.pop(k)
                self._custom_color = True
                redraw = True
        for k in ("fg", "foreground"):
            if k in kw:
                self.fg_color = kw.pop(k)
                redraw = True
        if "command" in kw:
            self.command = kw.pop("command")
        if "state" in kw:
            self.set_state("disabled" if kw.pop("state") == "disabled" else "normal")
        for k in ("activebackground", "activeforeground", "relief", "bd", "borderwidth",
                  "highlightthickness", "highlightbackground", "highlightcolor", "style",
                  "takefocus", "padding", "underline", "image", "compound"):
            kw.pop(k, None)
        if kw:
            return super().configure(**kw)
        if redraw:
            self._redraw()
        return None

    config = configure

    def cget(self, key):
        if key == "text":
            return self.text_str
        if key in ("bg", "background"):
            return self.bg_color
        if key in ("fg", "foreground"):
            return self.fg_color
        if key == "state":
            return self._state
        if key == "command":
            return self.command
        return super().cget(key)

    __getitem__ = cget

    def __setitem__(self, key, value):
        self.configure(**{key: value})

    def invoke(self):
        self._on_click()

    def state(self, spec=None):
        """API kiểu ttk: btn.state(['disabled']) / btn.state(['!disabled'])."""
        if spec:
            for st in spec:
                if st == "disabled":
                    self.set_state("disabled")
                elif st == "!disabled":
                    self.set_state("normal")
        return ("disabled",) if self._state == "disabled" else ()

    def instate(self, spec, callback=None):
        return (("disabled" in spec) == (self._state == "disabled"))


# ======================= simpledialog CÙNG THEME =======================
def _themed_ask_value(kind, title, prompt, **kw):
    parent = kw.get("parent") or getattr(tk, "_default_root", None)
    if parent is None:
        raise RuntimeError("no parent")
    try:
        parent = parent.winfo_toplevel()
    except Exception:
        pass
    initial = kw.get("initialvalue")
    show = kw.get("show")
    minv, maxv = kw.get("minvalue"), kw.get("maxvalue")

    result = {"v": None}
    win = ThemedToplevel(parent)
    win.withdraw()
    win.title(title or "")
    win.resizable(False, False)

    tk.Frame(win, bg=COL_BLUE, height=4).pack(fill="x")
    body = tk.Frame(win, bg=COL_PANEL)
    body.pack(fill="both", expand=True, padx=18, pady=(14, 6))
    tk.Label(body, text=str(prompt or ""), bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 10),
             wraplength=420, justify="left", anchor="w").pack(fill="x")
    var = tk.StringVar(value="" if initial is None else str(initial))
    ent = tk.Entry(body, textvariable=var, font=("Segoe UI", 10), width=44,
                   **({"show": show} if show else {}))
    ent.pack(fill="x", pady=(8, 2), ipady=4)
    err = tk.Label(body, text="", bg=COL_PANEL, fg=COL_RED, font=("Segoe UI", 8), anchor="w")
    err.pack(fill="x")

    tk.Frame(win, bg=COL_BORDER, height=1).pack(fill="x", pady=(6, 0))
    row = tk.Frame(win, bg=COL_HEADER)
    row.pack(fill="x")

    def _ok(_e=None):
        raw = var.get()
        if kind == "string":
            result["v"] = raw
        else:
            try:
                val = int(raw) if kind == "integer" else float(raw)
            except ValueError:
                err.config(text="Vui lòng nhập một số nguyên." if kind == "integer"
                           else "Vui lòng nhập một số.")
                return
            if minv is not None and val < minv:
                err.config(text=f"Giá trị phải >= {minv}.")
                return
            if maxv is not None and val > maxv:
                err.config(text=f"Giá trị phải <= {maxv}.")
                return
            result["v"] = val
        win.destroy()

    def _cancel(_e=None):
        result["v"] = None
        try:
            win.destroy()
        except Exception:
            pass

    RoundedButton(row, "Huỷ", command=_cancel, bg=COL_GRAY_BTN, container_bg=COL_HEADER,
                  font=("Segoe UI", 9, "bold"), padx=18, pady=6, width=84
                  ).pack(side="right", padx=(0, 10), pady=10)
    RoundedButton(row, "OK", command=_ok, bg=COL_GREEN, container_bg=COL_HEADER,
                  font=("Segoe UI", 9, "bold"), padx=18, pady=6, width=84
                  ).pack(side="right", padx=(0, 6), pady=10)
    win.bind("<Return>", _ok)
    win.bind("<Escape>", _cancel)
    win.protocol("WM_DELETE_WINDOW", _cancel)

    win.update_idletasks()
    ww, wh = max(win.winfo_reqwidth(), 380), win.winfo_reqheight()
    try:
        if parent.winfo_viewable():
            x = parent.winfo_rootx() + (parent.winfo_width() - ww) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - wh) // 3
        else:
            raise RuntimeError
    except Exception:
        x = (win.winfo_screenwidth() - ww) // 2
        y = (win.winfo_screenheight() - wh) // 3
    win.geometry(f"{ww}x{wh}+{max(0, x)}+{max(0, y)}")
    try:
        if parent.winfo_viewable():
            win.transient(parent)
    except Exception:
        pass
    win.deiconify()
    return win, ent, result


def install_themed_simpledialog():
    """Thay simpledialog.askstring/askinteger/askfloat bằng hộp nhập cùng
    theme (cùng chữ ký + giá trị trả về: giá trị đã nhập, hoặc None nếu
    Huỷ/ESC). Số sai/ngoài khoảng min-max báo NGAY DƯỚI ô nhập thay vì bật
    hộp thoại lỗi. Gọi từ luồng nền/gặp lỗi -> dùng lại hàm gốc."""
    from tkinter import simpledialog as _sd
    if getattr(_sd, "_dashboard_themed", False):
        return
    kinds = {"askstring": "string", "askinteger": "integer", "askfloat": "float"}

    def _make(fn_name, kind):
        orig = getattr(_sd, fn_name)

        def _fn(title, prompt, **kw):
            if threading.current_thread() is not threading.main_thread():
                return orig(title, prompt, **kw)
            try:
                win, ent, result = _themed_ask_value(kind, title, prompt, **kw)
            except Exception:
                return orig(title, prompt, **kw)
            try:
                win.update_idletasks()
                # KHÔNG grab_set(): giống auto_notify.py - không chặn cửa sổ khác.
                win.focus_force()
                ent.focus_set()
                ent.select_range(0, "end")
            except Exception:
                pass
            try:
                win.wait_window()
            except Exception:
                pass
            return result["v"]
        _fn.__name__ = fn_name
        return _fn

    for fn_name, kind in kinds.items():
        setattr(_sd, fn_name, _make(fn_name, kind))
    _sd._dashboard_themed = True


class FlowBar(tk.Frame):
    """Thanh chứa nhiều nút nhỏ (RoundedButton, nhãn...) TỰ ĐỘNG XUỐNG DÒNG
    khi không đủ bề ngang, thay vì bị cắt/khuất mất (vd nút '💾 Lưu' ở cuối
    1 popup không hiện ra cho tới khi người dùng tự kéo rộng cửa sổ) - dùng
    cho các hàng nút 'chọn nhanh theo Nhóm', hàng nút Lưu/Huỷ ở popup... để
    mọi popup vẫn hiển thị ĐẦY ĐỦ nút kể cả trên màn hình/cửa sổ nhỏ.

    Cách dùng: tạo FlowBar(parent, ...) rồi PACK NÓ NHƯ 1 FRAME BÌNH THƯỜNG
    (fill='x'), sau đó với mỗi nút con, tạo widget với parent=flowbar rồi
    gọi flowbar.add(widget) THAY VÌ widget.pack(...) - Flowbar tự tính lại
    layout (đặt bằng place()) mỗi khi bề ngang đổi (vd cửa sổ được kéo dãn)
    hoặc mỗi khi có thêm nút mới."""

    def __init__(self, master, bg=None, hgap=6, vgap=6, **kw):
        super().__init__(master, bg=(bg if bg is not None else COL_PANEL), **kw)
        self._hgap = hgap
        self._vgap = vgap
        self._widgets = []
        self.bind("<Configure>", self._reflow)

    def add(self, widget):
        self._widgets.append(widget)
        self.after_idle(self._reflow)
        return widget

    def clear(self):
        for w in self._widgets:
            try:
                w.destroy()
            except Exception:
                pass
        self._widgets = []
        self._reflow()

    def _reflow(self, _event=None):
        width = self.winfo_width()
        if width <= 1:
            width = self.winfo_reqwidth() or 1
        x = 0
        y = 0
        row_h = 0
        for w in self._widgets:
            try:
                w.update_idletasks()
                ww = w.winfo_reqwidth()
                wh = w.winfo_reqheight()
            except tk.TclError:
                continue
            if x > 0 and x + ww > width:
                x = 0
                y += row_h + self._vgap
                row_h = 0
            w.place(x=x, y=y, width=ww, height=wh)
            x += ww + self._hgap
            row_h = max(row_h, wh)
        total_h = max(y + row_h, 1)
        if abs(self.winfo_reqheight() - total_h) > 1:
            self.config(height=total_h)


class DarkCheck(tk.Frame):
    """Checkbox tự vẽ (không dùng ttk.Checkbutton): ô bo góc có viền sáng/
    tối nhẹ + dấu tick trắng, đồng bộ theme tối trên mọi máy Windows (ttk
    mặc định không cho phép đổi màu nền tuỳ ý)."""

    def __init__(self, parent, text, variable, command=None, bg=COL_PANEL,
                 fg=COL_TEXT, font=("Segoe UI", 9), box_size=16, wraplength=0):
        super().__init__(parent, bg=bg)
        self.var = variable
        self.command = command
        self.box_size = box_size

        self.canvas = tk.Canvas(self, width=box_size, height=box_size,
                                 highlightthickness=0, bg=bg)
        self.canvas.pack(side="left", padx=(0, 6))
        self.lbl = tk.Label(self, text=text, bg=bg, fg=fg, font=font,
                             anchor="w", justify="left", cursor="hand2")
        if wraplength:
            self.lbl.config(wraplength=wraplength)
        self.lbl.pack(side="left", fill="x", expand=True)

        for w in (self.canvas, self.lbl, self):
            w.bind("<Button-1>", self.toggle)

        self._draw()
        try:
            self.var.trace_add("write", lambda *_: self._draw())
        except Exception:
            pass

    def toggle(self, _event=None):
        self.var.set(not self.var.get())
        self._draw()
        if self.command:
            self.command()

    def _draw(self):
        try:
            self.canvas.delete("all")
        except tk.TclError:
            return
        s = self.box_size
        pts = _round_rect_points(1, 1, s - 1, s - 1, 4)
        if self.var.get():
            self.canvas.create_polygon(pts, smooth=True, fill=COL_CHECK_ON,
                                       outline=_mix(COL_CHECK_ON, "#000000", 0.35), width=1)
            self.canvas.create_line(3, 2, s - 3, 2, fill=_mix(COL_CHECK_ON, "#ffffff", 0.45))
            self.canvas.create_line(4, s * 0.55, s * 0.42, s - 5, fill="white", width=2)
            self.canvas.create_line(s * 0.42, s - 5, s - 4, 4, fill="white", width=2)
        else:
            self.canvas.create_polygon(pts, smooth=True, fill=COL_ENTRY,
                                       outline=COL_CHECK_OFF, width=2)


class ToolGroup(tk.Frame):
    """Khối NHÓM NÚT có tiêu đề nhỏ + viền mảnh + bóng đổ phía dưới (nổi 3D
    nhẹ) - dùng để gom các nút CÙNG CHỨC NĂNG lại với nhau cho dễ nhìn.

    Cách dùng:
        g = ToolGroup(flowbar, "🚀 TÁC VỤ NHANH", accent=COL_BLUE)
        row = g.new_row()                      # mỗi hàng là 1 tk.Frame
        RoundedButton(row, "...", command=..., container_bg=g.card_bg
                      ).pack(side="left", padx=3, pady=2)
        flowbar.add(g)                         # (hoặc g.pack(...))
    """

    def __init__(self, parent, title="", accent=COL_BLUE, container_bg=COL_BG, bg=COL_PANEL):
        super().__init__(parent, bg=container_bg)
        self.card_bg = bg
        self.card = tk.Frame(self, bg=bg, highlightbackground=COL_BORDER, highlightthickness=1)
        self.card.pack(fill="both", expand=True)
        tk.Frame(self, bg=COL_SHADOW, height=3).pack(fill="x", padx=3)

        if title:
            head = tk.Frame(self.card, bg=bg)
            head.pack(fill="x", padx=8, pady=(6, 2))
            tk.Frame(head, bg=accent, width=3, height=11).pack(side="left", padx=(0, 6))
            tk.Label(head, text=title, bg=bg, fg=accent,
                     font=("Segoe UI", 8, "bold")).pack(side="left")
        self.body = tk.Frame(self.card, bg=bg)
        self.body.pack(fill="x", padx=8, pady=(2 if title else 8, 8))

    def new_row(self, pady=(0, 0)):
        row = tk.Frame(self.body, bg=self.card_bg)
        row.pack(fill="x", pady=pady, anchor="w")
        return row


def make_separator(parent, bg=COL_BORDER, height=24):
    """Vạch đứng mảnh ngăn cách các nhóm nút trong 1 hàng (dùng được với
    FlowBar.add() vì có kích thước cố định)."""
    return tk.Frame(parent, bg=bg, width=1, height=height)


class CategorySection(tk.Frame):
    """1 khối 'MỤC' trong danh sách - checkbox chọn tất cả + tiêu đề + số
    lượng tác vụ + nút thu gọn/mở rộng, và tuỳ chọn nút "Cài Đặt Mua Shop"
    (chỉ MỤC đầu tiên có, đúng như ảnh mẫu)."""

    def __init__(self, parent, title, count, show_shop_button=False, on_shop_click=None):
        super().__init__(parent, bg=COL_HEADER, highlightbackground=COL_BORDER, highlightthickness=1)
        self.collapsed = False
        self._select_all_cmd = None

        header = tk.Frame(self, bg=COL_HEADER)
        header.pack(fill="x")

        # Dải màu nhấn bên trái tiêu đề MỤC
        tk.Frame(header, bg=COL_BLUE, width=4).pack(side="left", fill="y")

        self.select_all_var = tk.BooleanVar(value=True)
        DarkCheck(header, "", self.select_all_var, bg=COL_HEADER,
                  command=self._on_select_all).pack(side="left", padx=(10, 2), pady=8)

        tk.Label(header, text=f"📁 {title}  ({count} Tác Vụ)", bg=COL_HEADER, fg=COL_TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=4)

        self.btn_collapse = RoundedButton(
            header, "▼ Thu Gọn", command=self._toggle_collapse,
            bg=COL_GRAY_BTN, container_bg=COL_HEADER,
            font=("Segoe UI", 8, "bold"), padx=10, pady=4)
        self.btn_collapse.pack(side="right", padx=8, pady=6)

        if show_shop_button:
            RoundedButton(
                header, "🛒 Cài Đặt Mua Shop", command=on_shop_click,
                bg=COL_TEAL, container_bg=COL_HEADER,
                font=("Segoe UI", 8, "bold"), padx=10, pady=4
            ).pack(side="right", padx=4, pady=6)

        self.body = tk.Frame(self, bg=COL_PANEL)
        self.body.pack(fill="x", padx=4, pady=(0, 8))

    def _on_select_all(self):
        if self._select_all_cmd:
            self._select_all_cmd(self.select_all_var.get())

    def set_select_all_command(self, cmd):
        self._select_all_cmd = cmd

    def _toggle_collapse(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.body.pack_forget()
            self.btn_collapse.set_text("▶ Mở Rộng")
        else:
            self.body.pack(fill="x", padx=4, pady=(0, 8))
            self.btn_collapse.set_text("▼ Thu Gọn")

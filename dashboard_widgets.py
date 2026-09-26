"""
dashboard_widgets.py — Các widget Tkinter tự vẽ dùng chung trong toàn bộ
Dashboard (nút bo tròn, checkbox tối màu, thanh tự xuống dòng, khối MỤC),
cùng 2 hàm tiện ích nhỏ (_set_dpi_awareness, _bind_esc_close). Tách riêng
khỏi dashboard.py để bất kỳ file dashboard_*.py nào cũng import được mà
không phải phụ thuộc vào toàn bộ DashboardApp.
"""
import tkinter as tk
import ctypes

from dashboard_theme import (
    COL_BG, COL_PANEL, COL_HEADER, COL_BORDER, COL_TEXT, COL_BLUE,
    COL_TEAL, COL_GRAY_BTN, COL_CHECK_ON, COL_CHECK_OFF,
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
        tk.Label(self._tip, text=text, bg="#000000", fg="#ffffff", font=("Segoe UI", 8),
                 justify="left", anchor="w", padx=8, pady=5,
                 highlightbackground=COL_BORDER, highlightthickness=1).pack()

    def _hide(self):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None



class RoundedButton(tk.Canvas):
    """Nút bấm bo tròn (pill-shaped) tự vẽ bằng Canvas - ttk.Button không
    cho phép bo góc + đổi màu nền tuỳ ý trên mọi theme Windows, nên tự vẽ
    để bám sát đúng màu sắc trong ảnh mẫu."""

    def __init__(self, parent, text, command=None, bg=COL_BLUE, fg="white",
                 container_bg=COL_BG, font=("Segoe UI", 9, "bold"),
                 padx=16, pady=8, radius=14, disabled_bg="#2a3244", width=None):
        super().__init__(parent, highlightthickness=0, bg=container_bg, bd=0)
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

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))

        self._compute_size()
        self._redraw()

    def _compute_size(self):
        tmp = tk.Label(self, text=self.text_str, font=self.font)
        tmp.update_idletasks()
        tw = tmp.winfo_reqwidth()
        th = tmp.winfo_reqheight()
        tmp.destroy()
        w = max(tw + self.padx * 2, self._min_width or 0)
        h = th + self.pady * 2
        self.config(width=w, height=h)

    @staticmethod
    def _round_rect_points(x1, y1, x2, y2, r):
        r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
        return [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1
        ]

    @staticmethod
    def _shade(hex_color, factor):
        hex_color = hex_color.lstrip("#")
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _redraw(self):
        self.delete("all")
        w = int(self["width"])
        h = int(self["height"])
        if w <= 1 or h <= 1:
            return
        color = self.disabled_bg if self._state == "disabled" else self.bg_color
        if self._hover and self._state != "disabled":
            color = self._shade(color, 1.12)
        pts = self._round_rect_points(1, 1, w - 1, h - 1, self.radius)
        self.create_polygon(pts, smooth=True, fill=color, outline=color)
        fg = self.fg_color if self._state != "disabled" else "#6b7488"
        self.create_text(w / 2, h / 2, text=self.text_str, fill=fg, font=self.font)

    def _set_hover(self, on):
        if self._state == "disabled":
            return
        self._hover = on
        self._redraw()

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
        self._redraw()


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
    """Checkbox tự vẽ (không dùng ttk.Checkbutton) để tô đúng màu nền/chữ/
    ô vuông + dấu tick xanh lá giống ảnh mẫu, đồng bộ theme tối trên mọi
    máy Windows (ttk mặc định không cho phép đổi màu nền tuỳ ý)."""

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
                             anchor="w", justify="left")
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
        self.canvas.delete("all")
        s = self.box_size
        if self.var.get():
            self.canvas.create_rectangle(1, 1, s - 1, s - 1, fill=COL_CHECK_ON, outline=COL_CHECK_ON)
            self.canvas.create_line(3, s * 0.55, s * 0.42, s - 4, fill="white", width=2)
            self.canvas.create_line(s * 0.42, s - 4, s - 3, 3, fill="white", width=2)
        else:
            self.canvas.create_rectangle(1, 1, s - 1, s - 1, fill="", outline=COL_CHECK_OFF, width=2)


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


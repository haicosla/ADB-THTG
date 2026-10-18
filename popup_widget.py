"""
popup_widget.py — Vẽ popup thông báo ĐÈ LÊN cửa sổ LDPlayer (dùng chung cho
cả Dashboard nhiều giả lập lẫn Macro Studio "Chạy Thử", tránh lặp lại 2 lần
2 nơi y hệt nhau dễ sửa chỗ này quên chỗ kia).

LỊCH SỬ SỬA LỖI (để hiểu vì sao làm theo cách này):
- Bản đầu dùng win32 SetParent() để "nhúng thật" popup làm cửa sổ CON của
  LDPlayer. Cách đó vỡ với các bản LDPlayer render bằng GPU/DirectX - khung
  hình game tự vẽ đè (flip/blit) lên toàn bộ client area BẤT KỂ Z-order cửa
  sổ con, nên popup "tồn tại" nhưng chữ bị vẽ đè mất ngay -> nhìn như "không
  hoạt động"/không thấy chữ (đúng report thực tế của người dùng).
- Đổi sang cửa sổ NỔI "topmost" bình thường (Windows/DWM compositing đè lên
  MỌI cửa sổ khác, kể cả cửa sổ vẽ bằng GPU) - CHẮC CHẮN hiện được chữ. Để
  vẫn bám theo LDPlayer khi cửa sổ đó di chuyển/đổi kích thước, tự canh lại
  vị trí mỗi 300ms bằng vòng lặp top.after() thay vì nhúng làm con thật.
"""

import tkinter as tk

DEFAULT_BG = "#FFFFFF"
DEFAULT_FG = "#000000"
DEFAULT_ALPHA = 0.5
_RADIUS = 14


def _rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Vẽ 1 hình chữ nhật BO GÓC trên Canvas bằng 1 polygon mượt (dùng
    smooth=True để Tk tự bo các điểm góc thành đường cong) - Tkinter không
    có sẵn hình chữ nhật bo góc, đây là cách vẽ phổ biến để giả lập."""
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


def show_ingame_popup(root, get_rect_fn, message, duration=0, bg=None, fg=None,
                       alpha=None, pos_box=None, log_fn=None, done_event=None):
    """Tạo + hiện 1 popup. PHẢI được gọi từ main thread (root.after) - hàm
    này KHÔNG tự điều phối thread, nơi gọi (dashboard_misc.py/gui_run.py) lo
    việc đó vì mỗi nơi có cách xác định main thread hơi khác nhau 1 chút.

    - get_rect_fn(): trả về (screen_x, screen_y, w, h) của khung game hiện
      tại trên MÀN HÌNH THẬT, hoặc None nếu chưa tìm thấy cửa sổ.
    - pos_box: [nx1, ny1, nx2, ny2] toạ độ TỈ LỆ (0..1) do người dùng tự kéo
      chọn trên Preview (xem gui_canvas.py) - nếu có, hiện ĐÚNG vùng này
      thay vì dải ngang mặc định phía trên khung game.
    - alpha: độ đục 0..1 (mặc định 0.5 = mờ 50% theo yêu cầu người dùng).
    - log_fn(where, exc): gọi khi có lỗi bất ngờ, để nơi gọi ghi vào Nhật Ký
      thay vì lỗi âm thầm biến mất (rất khó debug nếu không có dòng này)."""
    def _log_err(where, e):
        if log_fn:
            try:
                log_fn(where, e)
            except Exception:
                pass

    bg = bg or DEFAULT_BG
    fg = fg or DEFAULT_FG
    alpha = DEFAULT_ALPHA if alpha is None else max(0.1, min(1.0, alpha))

    try:
        rect = get_rect_fn()
    except Exception as e:
        rect = None
        _log_err("get_render_screen_rect", e)

    def _geometry_for(rect):
        """Tính (bw, bh, sx, sy, wrap) theo rect hiện tại + pos_box (nếu
        có) - dùng chung lúc tạo popup VÀ mỗi lần _follow() canh lại vị trí."""
        if not rect:
            return 420, 64, 300, 300, 330
        sx, sy, sw, sh = rect
        if pos_box:
            nx1, ny1, nx2, ny2 = pos_box
            bx = sx + nx1 * sw
            by = sy + ny1 * sh
            bw = max(120, (nx2 - nx1) * sw)
            bh = max(40, (ny2 - ny1) * sh)
            return int(bw), int(bh), int(bx), int(max(0, by)), max(100, int(bw) - 60)
        bw = max(sw, 220)
        bh = 64
        return int(bw), bh, int(sx), int(max(0, sy)), max(150, int(bw) - 90)

    top = tk.Toplevel(root)
    top.overrideredirect(True)
    try:
        top.attributes("-topmost", True)
    except Exception as e:
        _log_err("attributes -topmost", e)
    try:
        top.attributes("-alpha", alpha)
    except Exception:
        pass

    bw, bh, sx, sy, wrap = _geometry_for(rect)
    top.geometry(f"{bw}x{bh}+{sx}+{sy}")

    canvas = tk.Canvas(top, width=bw, height=bh, bg=bg, highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)
    _rounded_rect(canvas, 1, 1, bw - 1, bh - 1, _RADIUS, fill=bg, outline="#FFC107", width=2)
    canvas.create_text(16, bh / 2, text="🔔", anchor="w", font=("Segoe UI Emoji", 14))
    text_id = canvas.create_text(44, bh / 2, text=message or "(không có nội dung)", anchor="w",
                                  fill=fg, font=("Segoe UI", 11, "bold"), width=wrap)

    close_btn = None
    if not (duration and duration > 0):
        close_btn = tk.Label(canvas, text="✖", bg=bg, fg=fg, font=("Segoe UI", 11, "bold"), cursor="hand2")
        canvas.create_window(bw - 20, bh / 2, window=close_btn)

    def _close():
        try:
            top.destroy()
        except Exception as e:
            _log_err("destroy", e)
        if done_event:
            done_event.set()

    if close_btn is not None:
        close_btn.bind("<Button-1>", lambda e: _close())

    if duration and duration > 0:
        top.after(int(duration * 1000), _close)

    def _follow():
        # Bám theo LDPlayer nếu cửa sổ di chuyển/đổi kích thước trong lúc
        # popup đang hiện - tự dừng khi popup đã bị đóng (destroy()).
        if not top.winfo_exists():
            return
        try:
            r2 = get_rect_fn()
            if r2:
                bw2, bh2, sx2, sy2, _wrap2 = _geometry_for(r2)
                top.geometry(f"{bw2}x{bh2}+{sx2}+{sy2}")
        except Exception:
            pass
        top.after(300, _follow)

    top.after(300, _follow)
    try:
        top.lift()
        top.update_idletasks()
    except Exception as e:
        _log_err("lift/update", e)

"""
wheel_scroll.py - Lăn chuột giữa (MouseWheel) cho MỌI cửa sổ/popup, cài 1 LẦN.

Vấn đề cũ: từng cửa sổ tự `canvas.bind_all("<MouseWheel>", ...)` rồi khi đóng gọi
`canvas.unbind_all("<MouseWheel>")`. bind_all chỉ giữ ĐƯỢC 1 hàm duy nhất cho cả
chương trình, nên mở cửa sổ B là đè mất của A, đóng B là gỡ luôn của cả cửa sổ
chính/A. Nhiều cửa sổ (Quản Lý Biến, Quản Lý Tài Khoản, Quản Lý Ảnh Trong Nhóm...)
còn không bind gì cả -> lăn chuột không chạy. Thêm nữa, trên Windows Tk 8.6 gửi sự
kiện lăn chuột tới widget đang có FOCUS chứ không phải widget dưới con trỏ.

Cách làm: `install_wheel_scroll(root)` đăng ký handler ở mức LỚP widget
(bind_class, add="+") nên không đè/không bị gỡ bởi bind_all/unbind_all của cửa sổ nào.
Handler lấy widget DƯỚI CON TRỎ, đi ngược lên cha tới widget cuộn được gần nhất
(Canvas/Listbox/Text/Treeview có thanh cuộn dọc và còn nội dung để cuộn) rồi cuộn nó,
trả "break" để các handler bind_all cũ không cuộn thêm lần nữa (tránh cuộn đôi).

Không can thiệp khi: giữ Shift/Ctrl (dành cho zoom/cuộn ngang của nơi khác); widget
nhận sự kiện đã tự có binding <MouseWheel> riêng (nó đã tự xử lý rồi); không tìm
thấy widget nào cuộn được (để handler cũ chạy như trước).
"""

_BIND_CLASSES = (
    "Tk", "Toplevel", "Frame", "Labelframe", "Label", "Canvas", "Button",
    "Checkbutton", "Radiobutton", "Entry",
    "TFrame", "TLabelframe", "TLabel", "TButton", "TCheckbutton", "TRadiobutton",
    "TEntry", "TNotebook",
)
# Widget có thể là ĐÍCH cuộn (có yview/yview_scroll + tuỳ chọn yscrollcommand).
_SCROLL_CLASSES = ("Canvas", "Listbox", "Text", "Treeview")
_SKIP_MODS = 0x0001 | 0x0004  # Shift | Control


def _is_scrollable(w):
    """True nếu w có thanh cuộn dọc gắn vào VÀ nội dung dài hơn vùng nhìn."""
    try:
        if w.winfo_class() not in _SCROLL_CLASSES:
            return False
        if not str(w.cget("yscrollcommand")):
            return False
        top, bottom = w.yview()
        return not (top <= 0.0 and bottom >= 1.0)
    except Exception:
        return False


def find_scroll_target(widget):
    """Đi từ `widget` ngược lên các widget cha, trả về widget cuộn được đầu tiên (hoặc None)."""
    w = widget
    while w is not None:
        if _is_scrollable(w):
            return w
        try:
            parent = w.winfo_parent()
            if not parent:
                return None
            w = w.nametowidget(parent)
        except Exception:
            return None
    return None


def _wheel_steps(event):
    try:
        d = int(event.delta)
    except Exception:
        return 0
    if d == 0:
        return 0
    steps = -int(d / 120)
    return steps if steps != 0 else (-1 if d > 0 else 1)


def _on_wheel(event):
    try:
        if int(getattr(event, "state", 0)) & _SKIP_MODS:
            return None
        src = event.widget
        # Widget nhận sự kiện đã tự có binding <MouseWheel> riêng -> nó đã xử lý rồi.
        try:
            if str(src.bind("<MouseWheel>")):
                return None
        except Exception:
            pass
        steps = _wheel_steps(event)
        if not steps:
            return None
        try:
            under = src.winfo_containing(event.x_root, event.y_root) or src
        except Exception:
            under = src
        target = find_scroll_target(under)
        if target is None and under is not src:
            target = find_scroll_target(src)
        if target is None:
            return None
        target.yview_scroll(steps, "units")
        return "break"
    except Exception:
        return None


def install_wheel_scroll(root):
    """Gọi 1 lần cho mỗi chương trình (đã được gọi trong apply_global_theme)."""
    if getattr(root, "_wheel_scroll_installed", False):
        return
    try:
        for cls in _BIND_CLASSES:
            root.bind_class(cls, "<MouseWheel>", _on_wheel, add="+")
        root._wheel_scroll_installed = True
    except Exception:
        pass

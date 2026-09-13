"""
dashboard.py — GIAO DIỆN CHÍNH của LD Macro Studio (Auto Runner Dashboard).

Đây là chương trình người dùng NÊN MỞ HÀNG NGÀY để chạy các tác vụ đã soạn
sẵn. Việc SOẠN kịch bản mới (ghi F7, kéo-thả bước, chỉnh IF/ELSE, cắt ảnh
mẫu...) vẫn nằm ở "LD Macro Studio" cũ (main.py + gui.py) - bấm nút
"➕ TẠO HOẠT ĐỘNG" ở góc trên để mở chương trình đó dưới dạng CỬA SỔ RIÊNG
(tiến trình con độc lập), không làm gián đoạn Dashboard đang chạy.

SO VỚI BẢN KHUNG (dashboard.py) TRƯỚC ĐÂY, BẢN NÀY THÊM:
  - Giao diện TỐI (dark mode) + nút bo tròn nhiều màu, bám theo ảnh mẫu.
  - Chạy ĐA LUỒNG: tick chọn NHIỀU giả lập LDPlayer cùng lúc, mỗi giả lập
    chạy trên 1 luồng riêng với ADBHelper / LogicEngine / WindowFinder
    độc lập hoàn toàn (không đụng chạm nhau).
  - Target theo TÊN GIẢ LẬP THẬT (qua ldconsole.exe list2 - xem
    emulator_manager.py) thay vì chỉ theo serial ADB vô nghĩa như
    "127.0.0.1:5556".
  - Log gắn kèm tên giả lập, lọc xem theo từng giả lập hoặc xem tổng hợp.
  - Nút "➕ Tạo Hoạt Động" mở lại chương trình tạo kịch bản cũ; Dashboard
    tự phát hiện khi có tác vụ mới được đăng ký và tự nạp lại danh mục.
  - Các nút tắt (Mở Bảng Giả Lập, Setup Người Mới, Quét Xe, UID Like, Cài
    Đặt Shop...) chạy thẳng 1 Hoạt Động cụ thể theo quy ước ID - xem
    HELP_TEXT / nút "📖 Hướng Dẫn" trong app để biết cách gắn kịch bản vào
    từng nút.

CHẠY CHƯƠNG TRÌNH NÀY: `python dashboard.py` (thay cho main.py khi dùng
hàng ngày; main.py vẫn giữ nguyên vai trò mở LD Macro Studio để tạo/sửa
kịch bản, và được chính Dashboard này gọi tới khi bấm "➕ Tạo Hoạt Động").
"""
import os
import sys
import json
import time
import ctypes
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import cv2

from adb_helper import ADBHelper
from logic_engine import LogicEngine, BreakGroupSignal, ContinueGroupSignal
from window_finder import WindowFinder
from emulator_manager import EmulatorManager
import task_registry
import run_state

SETTINGS_PATH = "dashboard_settings.json"

# ============================= BẢNG MÀU (theo ảnh mẫu) =============================
COL_BG = "#0c1220"          # nền tổng thể
COL_PANEL = "#141c2c"       # nền các khối/panel
COL_PANEL_ALT = "#101827"   # nền dòng trong danh sách con (popup, log filter...)
COL_HEADER = "#19233a"      # nền tiêu đề mục (MỤC 1, Sự kiện...)
COL_BORDER = "#232e46"      # viền mảnh quanh khối
COL_TEXT = "#e7ebf3"
COL_TEXT_MUTED = "#8b96ad"
COL_GREEN = "#27ae60"
COL_GREEN_DARK = "#1e8449"
COL_BLUE = "#2f6fed"
COL_TEAL = "#2d9cdb"
COL_ORANGE = "#f2994a"
COL_PURPLE = "#9b6ef3"
COL_RED = "#eb5757"
COL_GRAY_BTN = "#3a4560"
COL_ACCENT = "#ffb020"      # màu nổi bật riêng cho "➕ Tạo Hoạt Động"
COL_CHECK_ON = "#2ecc71"
COL_CHECK_OFF = "#4a5570"

HELP_TEXT = """HƯỚNG DẪN SỬ DỤNG DASHBOARD

1) TẠO HOẠT ĐỘNG MỚI
   Bấm '➕ Tạo Hoạt Động' ở góc trên bên phải để mở lại chương trình soạn
   kịch bản cũ (LD Macro Studio). Ghi thao tác bằng F7 hoặc soạn tay, lưu
   file, xong bấm '📋 Đăng Ký Tác Vụ' để nó xuất hiện ngay tại Dashboard
   này - Dashboard tự phát hiện thay đổi và tự nạp lại danh mục, không cần
   khởi động lại chương trình.

2) CHẠY ĐA LUỒNG NHIỀU GIẢ LẬP
   Ở thanh 'Giả lập', tick chọn 1 hoặc nhiều giả lập LDPlayer đang mở (mỗi
   ô tick là 1 giả lập, hiển thị đúng TÊN bạn đặt trong LDMultiPlayer, lấy
   qua ldconsole.exe). Tick nhiều giả lập rồi bấm
   '▶ CHẠY TẤT CẢ TÁC VỤ ĐANG CHỌN' sẽ chạy CÙNG LÚC trên từng giả lập,
   mỗi giả lập 1 luồng riêng, không ảnh hưởng lẫn nhau.

3) CÁC NÚT CHỨC NĂNG NHANH
   (Mở Bảng Giả Lập, Setup Người Mới, Quét Xe, UID Like, Cài Đặt Shop...)
   là các phím tắt chạy THẲNG 1 Hoạt Động cụ thể mà không cần tick trong
   danh sách. ID của 1 Hoạt Động được TỰ SINH từ TÊN FILE kịch bản (lưu
   trong thư mục tasks/), nên để gắn kịch bản vào 1 nút tắt, hãy lưu file
   kịch bản đúng tên quy ước rồi Đăng Ký Tác Vụ như bình thường:
       tasks/mo_bang_gia_lap.json   -> nút "Mở Bảng Giả Lập"
       tasks/setup_nguoi_moi.json   -> nút "Setup Người Mới"
       tasks/quet_xe.json           -> nút "Quét Xe"
       tasks/uid_like.json          -> nút "UID Like"
       tasks/cai_dat_shop.json      -> nút "Cài Đặt Shop"
       tasks/auto_login.json        -> chạy TRƯỚC MỌI phiên khi bật 'Tự Login'
   Nếu chưa có file tương ứng, nút sẽ báo "Chưa cấu hình" và hướng dẫn lại
   đúng như trên.

4) NHẬT KÝ & LỌC THEO GIẢ LẬP
   Mỗi dòng log được gắn kèm tên giả lập tương ứng. Dùng ô 'Xem Log Giả
   Lập' để chỉ xem log của 1 giả lập cụ thể, hoặc chọn 'Tất cả giả lập
   (Tổng hợp)' để xem chung tất cả.

5) RESET BỘ NHỚ TASK HÔM NAY
   Xoá toàn bộ ghi nhớ "đã chạy hôm nay" (run_state.py) - dùng khi cần bắt
   đầu lại từ đầu trong ngày, hoặc phục vụ các tính năng mở rộng sau này
   dựa trên dữ liệu này (vd tự động bỏ qua tác vụ đã hoàn thành).
"""


def _set_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ============================= WIDGET DÙNG CHUNG =============================
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


# ============================= APP CHÍNH =============================
class DashboardApp:
    LOG_FILTER_ALL = "Tất cả giả lập (Tổng hợp)"

    def __init__(self, root):
        self.root = root
        self.root.title("LD Macro Studio - Auto Runner Dashboard")
        self.root.geometry("1320x880")
        self.root.minsize(1020, 640)
        self.root.configure(bg=COL_BG)

        self._settings = self._load_settings()
        self.shop_settings = self._settings.get("shop_settings", {})

        self.adb = ADBHelper()
        self.emu_manager = EmulatorManager(self.adb)
        self.emulators = []
        self.emu_vars = {}
        self.emu_all_var = tk.BooleanVar(value=True)

        self.stop_flag = False
        self.is_running = False
        self.active_threads = 0

        self.tasks = []
        self.task_vars = {}
        self.task_status_lbl = {}
        self.task_progress = {}

        self.log_entries = []
        self.log_filter_var = tk.StringVar(value=self.LOG_FILTER_ALL)

        self._last_registry_mtime = None
        self._first_watch_tick = True

        self._build_ui()
        self.reload_tasks()
        self.refresh_emulators()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(2000, self._watch_registry)

    # ================= CÀI ĐẶT (persist) =================
    def _load_settings(self):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_settings(self):
        data = {
            "auto_login": bool(self.auto_login_var.get()) if hasattr(self, "auto_login_var") else False,
            "shop_settings": self.shop_settings,
        }
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _on_close(self):
        self._save_settings()
        self.root.destroy()

    # ================= GIAO DIỆN =================
    def _build_ui(self):
        self._build_top_toolbar()
        self._build_emulator_bar()
        self._build_task_scroll_area()
        self._build_bottom_controls()
        self._build_log_panel()

    def _build_top_toolbar(self):
        top = tk.Frame(self.root, bg=COL_BG)
        top.pack(fill="x", padx=10, pady=(10, 6))

        tk.Label(top, text="📋 DANH SÁCH TÁC VỤ AUTO", bg=COL_BG, fg=COL_TEXT,
                 font=("Segoe UI", 14, "bold")).pack(side="left")

        self.btn_create_activity = RoundedButton(
            top, "➕ Tạo Hoạt Động", command=self.open_creator_tool,
            bg=COL_ACCENT, fg="#241a00", container_bg=COL_BG,
            font=("Segoe UI", 10, "bold"), padx=16, pady=8
        )
        self.btn_create_activity.pack(side="right", padx=4)

        actions_bar = tk.Frame(self.root, bg=COL_BG)
        actions_bar.pack(fill="x", padx=10, pady=(0, 8))

        RoundedButton(actions_bar, "📱 Mở Bảng Giả Lập", command=lambda: self._quick_action("mo_bang_gia_lap"),
                      bg=COL_BLUE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)
        RoundedButton(actions_bar, "🆕 Setup Người Mới", command=lambda: self._quick_action("setup_nguoi_moi"),
                      bg=COL_ORANGE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)
        RoundedButton(actions_bar, "📖 Hướng Dẫn", command=lambda: self._quick_action("huong_dan"),
                      bg=COL_PURPLE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)

        self.auto_login_var = tk.BooleanVar(value=bool(self._settings.get("auto_login", False)))
        DarkCheck(actions_bar, "Tự Login", self.auto_login_var, bg=COL_BG).pack(side="left", padx=10)

        RoundedButton(actions_bar, "🚗 Quét Xe", command=lambda: self._quick_action("quet_xe"),
                      bg=COL_ORANGE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)
        RoundedButton(actions_bar, "🆔 UID Like", command=lambda: self._quick_action("uid_like"),
                      bg=COL_BLUE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)

        self.btn_view_errors = RoundedButton(
            actions_bar, "⚠ Xem Lỗi / Chưa Xong (0)", command=self.show_error_panel,
            bg=COL_RED, container_bg=COL_BG, font=("Segoe UI", 9, "bold"))
        self.btn_view_errors.pack(side="left", padx=3)

        RoundedButton(actions_bar, "🛍 Cài Đặt Shop", command=lambda: self._quick_action("cai_dat_shop"),
                      bg=COL_GREEN, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)

    def _build_emulator_bar(self):
        bar = tk.Frame(self.root, bg=COL_PANEL, highlightbackground=COL_BORDER, highlightthickness=1)
        bar.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(bar, text="🖥 Giả lập:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(10, 6), pady=8)

        self.emu_chip_frame = tk.Frame(bar, bg=COL_PANEL)
        self.emu_chip_frame.pack(side="left", fill="x", expand=True)

        RoundedButton(bar, "🔄 Quét Lại Danh Mục", command=self.reload_tasks,
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=3, pady=6)
        RoundedButton(bar, "☐ Bỏ Chọn", command=lambda: self._set_all_checks(False),
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=3, pady=6)
        RoundedButton(bar, "☑ Chọn Tất Cả", command=lambda: self._set_all_checks(True),
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=3, pady=6)
        RoundedButton(bar, "🔄 Quét Giả Lập", command=self.refresh_emulators,
                      bg=COL_TEAL, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=6, pady=6)

    def _build_task_scroll_area(self):
        outer = tk.Frame(self.root, bg=COL_BG)
        outer.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        self.canvas = tk.Canvas(outer, highlightthickness=0, bg=COL_BG)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.list_frame = tk.Frame(self.canvas, bg=COL_BG)

        self._list_frame_id = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._list_frame_id, width=e.width))
        self.canvas.configure(yscrollcommand=vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _build_bottom_controls(self):
        bar = tk.Frame(self.root, bg=COL_BG)
        bar.pack(fill="x", padx=10, pady=6)

        self.btn_run = RoundedButton(
            bar, "▶ CHẠY TẤT CẢ TÁC VỤ ĐANG CHỌN", command=self.run_selected_tasks,
            bg=COL_GREEN, container_bg=COL_BG, font=("Segoe UI", 10, "bold"), padx=14, pady=9)
        self.btn_run.pack(side="left", padx=4)

        RoundedButton(
            bar, "🔀 Chọn Hành Động Để Chạy", command=self._open_task_picker,
            bg=COL_BLUE, container_bg=COL_BG, font=("Segoe UI", 10, "bold"), padx=14, pady=9
        ).pack(side="left", padx=4)

        self.btn_stop = RoundedButton(
            bar, "⏹ DỪNG LẠI (STOP)", command=self.stop_run,
            bg=COL_RED, container_bg=COL_BG, font=("Segoe UI", 10, "bold"), padx=14, pady=9)
        self.btn_stop.set_state("disabled")
        self.btn_stop.pack(side="left", padx=4)

        RoundedButton(
            bar, "♻ Reset Bộ Nhớ Task Hôm Nay", command=self.reset_daily_memory,
            bg=COL_GRAY_BTN, container_bg=COL_BG, font=("Segoe UI", 9, "bold"), padx=12, pady=9
        ).pack(side="left", padx=4)

        self.lbl_status = tk.Label(bar, text="Trạng thái: Sẵn sàng", bg=COL_BG, fg=COL_TEXT,
                                    font=("Segoe UI", 9, "bold"))
        self.lbl_status.pack(side="right", padx=8)

    def _build_log_panel(self):
        frame = tk.Frame(self.root, bg=COL_PANEL, highlightbackground=COL_BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=False, padx=10, pady=(0, 10))

        header = tk.Frame(frame, bg=COL_PANEL)
        header.pack(fill="x", padx=8, pady=(8, 0))
        tk.Label(header, text="📜 NHẬT KÝ THỰC THI THỜI GIAN THỰC", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 9, "bold")).pack(side="left")

        tk.Label(header, text="Xem Log Giả Lập:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8)).pack(side="left", padx=(20, 4))
        self.cbo_log_filter = ttk.Combobox(header, state="readonly", width=26,
                                            textvariable=self.log_filter_var,
                                            values=[self.LOG_FILTER_ALL])
        self.cbo_log_filter.pack(side="left")
        self.cbo_log_filter.bind("<<ComboboxSelected>>", self._on_log_filter_changed)

        RoundedButton(header, "🗑 Xóa Log", command=self._clear_log, bg=COL_GRAY_BTN,
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="left", padx=6)
        RoundedButton(header, "📋 Sao Chép", command=self._copy_log, bg=COL_BLUE,
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="left", padx=4)

        self.var_log_autoscroll = tk.BooleanVar(value=True)
        DarkCheck(header, "Tự cuộn xuống", self.var_log_autoscroll, bg=COL_PANEL).pack(side="left", padx=12)

        self.lbl_log_count = tk.Label(header, text="0 dòng", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8))
        self.lbl_log_count.pack(side="right", padx=4)

        body = tk.Frame(frame, bg=COL_PANEL)
        body.pack(fill="both", expand=True, padx=8, pady=8)

        log_scroll = ttk.Scrollbar(body, orient="vertical")
        self.txt_log = tk.Text(
            body, height=10, wrap="none", state="disabled",
            bg="#0b0f18", fg="#dfe4ee", font=("Consolas", 9), relief="flat",
            yscrollcommand=log_scroll.set
        )
        log_scroll.config(command=self.txt_log.yview)
        log_scroll.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)
        self.txt_log.tag_configure("info", foreground="#9aa5bd")
        self.txt_log.tag_configure("success", foreground="#3ddc84")
        self.txt_log.tag_configure("warn", foreground="#ffb020")
        self.txt_log.tag_configure("error", foreground="#ff5c5c")

    # ================= GIẢ LẬP =================
    def refresh_emulators(self):
        self.emulators = self.emu_manager.refresh()
        for w in self.emu_chip_frame.winfo_children():
            w.destroy()
        self.emu_vars = {}

        if not self.emulators:
            tk.Label(self.emu_chip_frame, text="Không tìm thấy giả lập nào đang chạy. Hãy mở LDPlayer rồi bấm 'Quét Giả Lập'.",
                     bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9)).pack(side="left", padx=6)
            self._refresh_log_filter_options()
            return

        DarkCheck(self.emu_chip_frame, "Tất cả giả lập", self.emu_all_var, bg=COL_PANEL,
                  command=self._on_toggle_all_emulators).pack(side="left", padx=8)

        for e in self.emulators:
            var = tk.BooleanVar(value=self.emu_all_var.get())
            self.emu_vars[e.name] = var
            DarkCheck(self.emu_chip_frame, e.name, var, bg=COL_PANEL).pack(side="left", padx=6)

        if not self.emu_manager.has_ldconsole():
            self._log("warn", "Không tìm thấy ldconsole.exe - chỉ hiển thị được serial ADB, "
                               "không có tên giả lập thật. Tính năng target theo TÊN sẽ hạn chế.")

        self._refresh_log_filter_options()
        self._log("info", f"Đã quét thấy {len(self.emulators)} giả lập đang chạy.")

    def _on_toggle_all_emulators(self):
        val = self.emu_all_var.get()
        for var in self.emu_vars.values():
            var.set(val)

    def _get_selected_emulators(self):
        return [e for e in self.emulators if self.emu_vars.get(e.name, tk.BooleanVar(value=False)).get()]

    # ================= NẠP DANH MỤC TÁC VỤ =================
    def reload_tasks(self):
        self.tasks = task_registry.load_registry()
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.task_vars = {}
        self.task_status_lbl = {}
        self.task_progress = {}

        if not self.tasks:
            tk.Label(
                self.list_frame,
                text="Chưa có tác vụ nào được đăng ký.\n\n"
                     "Bấm '➕ Tạo Hoạt Động' để mở LD Macro Studio,\n"
                     "soạn kịch bản rồi bấm '📋 Đăng Ký Tác Vụ'.",
                bg=COL_BG, fg=COL_TEXT_MUTED, font=("Segoe UI", 11), justify="center"
            ).pack(pady=40)
            self._log("info", "Danh mục tác vụ trống (task_registry.json chưa có hoặc rỗng).")
            return

        groups = {}
        order_keys = []
        for t in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0))):
            muc = t.get("muc") or "Chưa phân loại"
            if muc not in groups:
                groups[muc] = []
                order_keys.append(muc)
            groups[muc].append(t)

        for idx, muc in enumerate(order_keys):
            self._build_category_section(muc, groups[muc], show_shop_button=(idx == 0))

        self._log("info", f"Đã nạp {len(self.tasks)} tác vụ trong {len(groups)} mục.")

    def _build_category_section(self, muc, entries, show_shop_button=False):
        section = CategorySection(
            self.list_frame, title=muc, count=len(entries),
            show_shop_button=show_shop_button,
            on_shop_click=lambda m=muc: self._open_shop_settings(m)
        )
        section.pack(fill="x", padx=8, pady=6, anchor="n")

        for i, entry in enumerate(entries):
            task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", str(i)))
            var = tk.BooleanVar(value=bool(entry.get("mac_dinh_bat", True)))
            self.task_vars[task_id] = var
            self.task_progress[task_id] = {"total": 0, "done": 0, "error": 0, "running": 0, "stopped": 0}

            row = tk.Frame(section.body, bg=COL_PANEL)
            row.grid(row=i // 3, column=i % 3, sticky="w", padx=10, pady=5)

            DarkCheck(row, entry.get("ten_hien_thi", task_id), var, bg=COL_PANEL).pack(side="left")
            status_lbl = tk.Label(row, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"))
            status_lbl.pack(side="left", padx=6)
            self.task_status_lbl[task_id] = status_lbl

        for col in range(3):
            section.body.grid_columnconfigure(col, weight=1, uniform="task_col")

        section.set_select_all_command(lambda v, es=entries: self._set_category_checks(es, v))

    def _set_category_checks(self, entries, value):
        for e in entries:
            task_id = e.get("id") or task_registry.make_task_id(e.get("file_json", ""))
            var = self.task_vars.get(task_id)
            if var:
                var.set(value)

    def _set_all_checks(self, value):
        for var in self.task_vars.values():
            var.set(value)

    # ================= NÚT CHỨC NĂNG NHANH =================
    def _quick_action(self, action_id):
        if action_id == "mo_bang_gia_lap":
            self._open_emulator_panel()
            return
        if action_id == "huong_dan":
            self._open_help_panel()
            return

        entry = task_registry.find_task(self.tasks, action_id)
        if not entry:
            messagebox.showinfo(
                "Chưa cấu hình",
                "Chức năng này chưa có Hoạt Động tương ứng.\n\n"
                "Cách kích hoạt: bấm '➕ Tạo Hoạt Động', soạn kịch bản, LƯU FILE "
                f"với tên đúng quy ước:\n\n    tasks/{action_id}.json\n\n"
                "rồi bấm '📋 Đăng Ký Tác Vụ' như bình thường. ID sẽ tự nhận đúng "
                "tên file, và nút này sẽ chạy thẳng kịch bản đó (xem thêm ở '📖 Hướng Dẫn')."
            )
            return

        selected_emulators = self._get_selected_emulators()
        if not selected_emulators:
            messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào để chạy!")
            return

        self._start_run([entry], selected_emulators, login_entry=None)

    # ================= TẠO HOẠT ĐỘNG (mở chương trình cũ) =================
    def open_creator_tool(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            main_py = os.path.join(script_dir, "main.py")
            subprocess.Popen([sys.executable, main_py], cwd=script_dir)
            self._log("info", "Đã mở LD Macro Studio (chương trình tạo Hoạt Động) ở cửa sổ riêng.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không mở được chương trình tạo Hoạt Động:\n{e}")

    def _watch_registry(self):
        """Tự động phát hiện task_registry.json thay đổi (do chương trình
        Tạo Hoạt Động ghi ra) để nạp lại danh mục MÀ KHÔNG CẦN người dùng tự
        bấm '🔄 Quét Lại Danh Mục'."""
        try:
            mtime = os.path.getmtime(task_registry.REGISTRY_PATH) if os.path.exists(task_registry.REGISTRY_PATH) else None
        except Exception:
            mtime = None

        if mtime != self._last_registry_mtime:
            if not self._first_watch_tick:
                self.reload_tasks()
                self._log("info", "Đã tự động nạp lại danh mục do phát hiện thay đổi mới.")
            self._last_registry_mtime = mtime

        self._first_watch_tick = False
        self.root.after(2000, self._watch_registry)

    # ================= CHỌN HÀNH ĐỘNG ĐỂ CHẠY (chạy nhanh 1 tác vụ) =================
    def _open_task_picker(self):
        win = tk.Toplevel(self.root)
        win.title("Chọn Hành Động Để Chạy")
        win.configure(bg=COL_PANEL)
        win.geometry("440x500")

        tk.Label(win, text="Chọn 1 Hoạt Động để chạy ngay:", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=6)
        vbar.pack(side="right", fill="y", padx=(0, 6))

        if not self.tasks:
            tk.Label(inner, text="Chưa có Hoạt Động nào được đăng ký.", bg=COL_PANEL,
                     fg=COL_TEXT_MUTED).pack(pady=20)

        for entry in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0))):
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=3, padx=4)
            tk.Label(row, text=entry.get("ten_hien_thi", "?"), bg=COL_PANEL_ALT, fg=COL_TEXT,
                     font=("Segoe UI", 9)).pack(side="left", padx=8, pady=6)
            tk.Label(row, text=entry.get("muc", ""), bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                     font=("Segoe UI", 8)).pack(side="left", padx=4)

            def _run(e=entry):
                win.destroy()
                selected_emulators = self._get_selected_emulators()
                if not selected_emulators:
                    messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào để chạy!")
                    return
                self._start_run([e], selected_emulators, login_entry=None)

            RoundedButton(row, "▶ Chạy", command=_run, bg=COL_GREEN, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="right", padx=8, pady=4)

    # ================= CHẠY TÁC VỤ (ĐA LUỒNG THEO GIẢ LẬP) =================
    def run_selected_tasks(self):
        if self.is_running:
            return

        selected = [
            t for t in self.tasks
            if self.task_vars.get(t.get("id") or task_registry.make_task_id(t.get("file_json", "")), tk.BooleanVar(value=False)).get()
        ]
        if not selected:
            messagebox.showwarning("Lưu ý", "Chưa chọn tác vụ nào để chạy!")
            return

        selected_emulators = self._get_selected_emulators()
        if not selected_emulators:
            messagebox.showwarning(
                "Lưu ý",
                "Chưa chọn giả lập nào để chạy!\nBấm '🔄 Quét Giả Lập' rồi tick chọn ít nhất 1 giả lập."
            )
            return

        selected = sorted(selected, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0)))

        login_entry = None
        if self.auto_login_var.get():
            login_entry = task_registry.find_task(self.tasks, "auto_login")
            if not login_entry:
                self._log("warn", "Đã bật 'Tự Login' nhưng chưa có Hoạt Động với id 'auto_login' (xem '📖 Hướng Dẫn').")

        self._start_run(selected, selected_emulators, login_entry)

    def _start_run(self, selected, selected_emulators, login_entry):
        self.is_running = True
        self.stop_flag = False
        self.active_threads = len(selected_emulators)
        self.btn_run.set_state("disabled")
        self.btn_stop.set_state("normal")

        for entry in selected:
            task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
            self.task_progress[task_id] = {"total": len(selected_emulators), "done": 0, "error": 0, "running": 0, "stopped": 0}
            lbl = self.task_status_lbl.get(task_id)
            if lbl:
                lbl.config(text="⏳ Đang chờ", fg=COL_TEXT_MUTED)

        self._update_status_label()
        names = ", ".join(e.name for e in selected_emulators)
        self._log("info", f"══════ Bắt đầu phiên chạy: {len(selected)} tác vụ trên [{names}] ══════")

        for emulator in selected_emulators:
            threading.Thread(target=self._worker_run_emulator, args=(emulator, selected, login_entry), daemon=True).start()

    def stop_run(self):
        self.stop_flag = True
        self._log("warn", "Người dùng bấm DỪNG - đang chờ các luồng hiện tại kết thúc...")

    def _worker_run_emulator(self, emulator, selected, login_entry):
        if not self.emu_manager.ensure_adb_connected(emulator):
            self._log("error", f"Không thấy giả lập trong 'adb devices' (serial: {emulator.adb_serial}). "
                                f"Bỏ qua giả lập này - hãy bấm 'Quét Giả Lập' hoặc 'Kết nối lại ADB' rồi thử lại.",
                       emulator_name=emulator.name)
            self.root.after(0, self._on_emulator_thread_done)
            return

        adb = ADBHelper()
        adb.device_id = emulator.adb_serial
        adb.update_resolution()
        self._log("info", f"Độ phân giải nhận diện: {adb.screen_w}x{adb.screen_h}px", emulator_name=emulator.name)

        wf = WindowFinder(adb)
        attached = wf.attach_hwnd(emulator.hwnd) if emulator.hwnd else False
        if not attached:
            wf.find_ld_windows()

        if wf.ensure_window_visible():
            self._log("warn", f"Cửa sổ LDPlayer '{emulator.name}' đang bị THU NHỎ - đã tự khôi phục lại "
                               f"(cửa sổ thu nhỏ thường khiến ADB gửi được lệnh nhưng KHÔNG có tác dụng chạm/vuốt).",
                       emulator_name=emulator.name)
            time.sleep(0.5)

        engine = LogicEngine(
            adb,
            stop_checker=lambda: self.stop_flag,
            popup_notifier=lambda msg, dur=0, _wf=wf: self._show_ingame_popup(_wf, msg, dur),
            logger=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )

        run_queue = ([login_entry] if login_entry is not None else []) + list(selected)

        for entry in run_queue:
            if self.stop_flag:
                break

            task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
            name = entry.get("ten_hien_thi", task_id)
            file_path = entry.get("file_json")
            is_tracked = entry is not login_entry

            if is_tracked:
                self._bump_task_progress(task_id, "running")
            self._log("info", f"── Bắt đầu tác vụ: {name} ──", emulator_name=emulator.name)

            if not file_path or not os.path.exists(file_path):
                self._log("error", f"Không tìm thấy file kịch bản: {file_path}", emulator_name=emulator.name)
                if is_tracked:
                    self._bump_task_progress(task_id, "error")
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    steps = json.load(f)
                engine.reset_variables()
                engine.execute_steps(steps, is_root=True)

                if self.stop_flag:
                    if is_tracked:
                        self._bump_task_progress(task_id, "stopped")
                    self._log("warn", f"Tác vụ '{name}' bị dừng giữa chừng.", emulator_name=emulator.name)
                    break

                if is_tracked:
                    self._bump_task_progress(task_id, "done")
                    run_state.mark_done(task_id, emulator.name)
                self._log("success", f"Hoàn thành tác vụ: {name}", emulator_name=emulator.name)

            except (BreakGroupSignal, ContinueGroupSignal):
                if is_tracked:
                    self._bump_task_progress(task_id, "done")
                    run_state.mark_done(task_id, emulator.name)
                self._log("warn", f"Tác vụ '{name}' kết thúc sớm do break/continue nằm ngoài GROUP.", emulator_name=emulator.name)
            except Exception as e:
                if is_tracked:
                    self._bump_task_progress(task_id, "error")
                self._log("error", f"Lỗi khi chạy '{name}': {e}", emulator_name=emulator.name)

        self.root.after(0, self._on_emulator_thread_done)

    def _on_emulator_thread_done(self):
        self.active_threads = max(0, self.active_threads - 1)
        if self.active_threads == 0:
            self._on_finish_all()
        else:
            self._update_status_label()

    def _update_status_label(self):
        if self.active_threads > 1:
            self.lbl_status.config(text=f"Trạng thái: Đang chạy đa luồng ({self.active_threads} luồng)")
        elif self.active_threads == 1:
            self.lbl_status.config(text="Trạng thái: Đang chạy...")
        else:
            self.lbl_status.config(text="Trạng thái: Sẵn sàng")

    def _on_finish_all(self):
        self.is_running = False
        self.btn_run.set_state("normal")
        self.btn_stop.set_state("disabled")
        self._update_status_label()
        self._log("info", "══════ Kết thúc phiên chạy ══════")

    def _bump_task_progress(self, task_id, kind):
        self.root.after(0, lambda: self._apply_task_progress(task_id, kind))

    def _apply_task_progress(self, task_id, kind):
        prog = self.task_progress.get(task_id)
        if prog is None:
            return
        if kind == "running":
            prog["running"] += 1
        elif kind == "done":
            prog["done"] += 1
            prog["running"] = max(0, prog["running"] - 1)
        elif kind == "error":
            prog["error"] += 1
            prog["running"] = max(0, prog["running"] - 1)
        elif kind == "stopped":
            prog["stopped"] += 1
            prog["running"] = max(0, prog["running"] - 1)

        lbl = self.task_status_lbl.get(task_id)
        if lbl:
            total = prog["total"]
            if prog["error"] > 0:
                lbl.config(text=f"⚠ Lỗi {prog['error']}/{total}", fg=COL_RED)
            elif total > 0 and prog["done"] == total:
                lbl.config(text=f"✅ Hoàn thành ({total}/{total})", fg=COL_GREEN)
            elif prog["running"] > 0:
                lbl.config(text=f"▶ Đang chạy ({prog['done']}/{total})", fg=COL_TEAL)
            elif prog["stopped"] > 0:
                lbl.config(text=f"⏹ Đã dừng ({prog['done']}/{total})", fg=COL_ORANGE)
            else:
                lbl.config(text="⏳ Đang chờ", fg=COL_TEXT_MUTED)

        self._refresh_error_badge()

    def _refresh_error_badge(self):
        n = sum(1 for p in self.task_progress.values() if p["error"] > 0)
        self.btn_view_errors.set_text(f"⚠ Xem Lỗi / Chưa Xong ({n})")

    def show_error_panel(self):
        win = tk.Toplevel(self.root)
        win.title("Lỗi / Chưa Xong")
        win.configure(bg=COL_PANEL)
        win.geometry("440x420")

        problems = [(tid, p) for tid, p in self.task_progress.items() if p["error"] > 0]
        if not problems:
            tk.Label(win, text="Không có tác vụ nào bị lỗi trong phiên chạy gần nhất. ✅",
                     bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 10)).pack(pady=30, padx=20)
            return

        name_by_id = {}
        for t in self.tasks:
            tid = t.get("id") or task_registry.make_task_id(t.get("file_json", ""))
            name_by_id[tid] = t.get("ten_hien_thi", tid)

        tk.Label(win, text="Các Hoạt Động bị lỗi trong phiên chạy gần nhất:", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

        for tid, p in problems:
            row = tk.Frame(win, bg=COL_PANEL_ALT)
            row.pack(fill="x", padx=12, pady=3)
            tk.Label(row, text=name_by_id.get(tid, tid), bg=COL_PANEL_ALT, fg=COL_TEXT,
                     font=("Segoe UI", 9)).pack(side="left", padx=8, pady=6)
            tk.Label(row, text=f"Lỗi {p['error']}/{p['total']}", bg=COL_PANEL_ALT, fg=COL_RED,
                     font=("Segoe UI", 9, "bold")).pack(side="right", padx=8)

    # ================= POPUP (dùng cho bước 'popup' trong kịch bản) =================
    def _show_ingame_popup(self, wf, message, duration=0):
        """Giống LD Macro Studio: hiện overlay đè lên đúng khung LDPlayer
        TƯƠNG ỨNG với luồng đang chạy (nhận wf = WindowFinder riêng của
        luồng đó), tránh hiện nhầm sang cửa sổ giả lập khác khi đa luồng."""
        done_event = threading.Event() if not duration else None

        def _do():
            rect = wf.get_render_screen_rect()
            top = tk.Toplevel(self.root)
            top.overrideredirect(True)
            try:
                top.attributes("-topmost", True)
                top.attributes("-alpha", 0.93)
            except Exception:
                pass

            if rect:
                sx, sy, sw, sh = rect
                top.geometry(f"{max(sw, 220)}x64+{sx}+{max(0, sy)}")
                wrap = max(150, sw - 90)
            else:
                top.geometry("420x64+300+300")
                wrap = 330

            frame = tk.Frame(top, bg="#212121", highlightbackground="#FFEB3B", highlightthickness=2)
            frame.pack(fill="both", expand=True)
            tk.Label(frame, text=message or "(không có nội dung)", bg="#212121", fg="#FFEB3B",
                     font=("Segoe UI", 12, "bold"), wraplength=wrap, justify="left").pack(
                side="left", expand=True, fill="both", padx=12, pady=6)

            def _close():
                try:
                    top.destroy()
                except Exception:
                    pass
                if done_event:
                    done_event.set()

            if duration and duration > 0:
                top.after(int(duration * 1000), _close)
            else:
                ttk.Button(frame, text="✔ Đóng", command=_close).pack(side="right", padx=10)

        self.root.after(0, _do)
        if done_event:
            done_event.wait()

    # ================= BẢNG GIẢ LẬP / HƯỚNG DẪN / CÀI ĐẶT SHOP =================
    def _debug_capture_emulator(self, emulator, parent_win):
        """Chụp màn hình bằng ĐÚNG serial mà Dashboard sẽ dùng để chạy tác vụ
        trên giả lập này, lưu ra file rồi mở lên - để người dùng TỰ MẮT so
        sánh với cửa sổ LDPlayer thật, xác nhận serial có đang trỏ đúng giả
        lập hay không (thay vì chỉ tin 'adb connect' báo thành công - lệnh
        đó chỉ xác nhận CÓ kết nối, không xác nhận kết nối tới ĐÚNG cửa sổ)."""
        connected = self.emu_manager.ensure_adb_connected(emulator)
        if not connected:
            messagebox.showerror(
                "Chụp thử thất bại",
                f"Không kết nối được tới serial: {emulator.adb_serial}", parent=parent_win)
            return

        test_adb = ADBHelper()
        test_adb.device_id = emulator.adb_serial
        img = test_adb.screencap_fast()
        if img is None:
            messagebox.showerror(
                "Chụp thử thất bại",
                f"Serial '{emulator.adb_serial}' kết nối được nhưng KHÔNG chụp được màn hình.\n"
                "Có thể serial này không thật sự tương ứng với giả lập đang hiển thị.",
                parent=parent_win)
            return

        try:
            os.makedirs("logs", exist_ok=True)
            safe_name = "".join(c if c.isalnum() else "_" for c in emulator.name)
            out_path = os.path.abspath(os.path.join("logs", f"debug_capture_{safe_name}.png"))
            cv2.imwrite(out_path, img)
            os.startfile(out_path)
            messagebox.showinfo(
                "Đã chụp",
                f"Đã chụp màn hình qua serial '{emulator.adb_serial}' và mở ảnh lên.\n\n"
                f"So sánh ảnh vừa mở với cửa sổ LDPlayer '{emulator.name}' thật trên màn hình bạn:\n"
                "- Nếu KHỚP -> serial đúng, vấn đề nằm ở nơi khác (vd sai vùng ảnh mẫu, thư mục templates).\n"
                "- Nếu KHÔNG khớp (ảnh khác hẳn, hoặc là màn hình 1 giả lập/app khác) -> serial đang bị "
                "gán NHẦM cho giả lập này.",
                parent=parent_win)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không lưu/mở được ảnh chụp thử:\n{e}", parent=parent_win)

    def _open_emulator_panel(self):
        win = tk.Toplevel(self.root)
        win.title("Bảng Giả Lập")
        win.configure(bg=COL_PANEL)
        win.geometry("480x440")

        tk.Label(win, text="🖥 Giả Lập LDPlayer Đang Chạy", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 4))

        if not self.emu_manager.has_ldconsole():
            tk.Label(win, text="⚠ Không tìm thấy ldconsole.exe - chỉ hiển thị serial ADB thô.",
                     bg=COL_PANEL, fg=COL_ORANGE, font=("Segoe UI", 9), wraplength=440, justify="left").pack(
                anchor="w", padx=14, pady=(0, 8))

        body = tk.Frame(win, bg=COL_PANEL)
        body.pack(fill="both", expand=True, padx=10, pady=4)

        if not self.emulators:
            tk.Label(body, text="Chưa quét thấy giả lập nào. Bấm 'Quét Lại' bên dưới.",
                     bg=COL_PANEL, fg=COL_TEXT_MUTED).pack(pady=20)
        else:
            for e in self.emulators:
                row = tk.Frame(body, bg=COL_PANEL_ALT)
                row.pack(fill="x", pady=3)
                status = "🟢 Đã khởi động" if e.android_started else "🟡 Đang khởi động"
                tk.Label(row, text=e.name, bg=COL_PANEL_ALT, fg=COL_TEXT,
                         font=("Segoe UI", 9, "bold")).pack(side="left", padx=8, pady=6)
                tk.Label(row, text=f"{status}  •  ADB: {e.adb_serial}", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                         font=("Segoe UI", 8)).pack(side="left", padx=6)

                def _reconnect(em=e):
                    ok = self.emu_manager.ensure_adb_connected(em)
                    messagebox.showinfo("Kết nối ADB", f"{'Thành công' if ok else 'Thất bại'}: {em.adb_serial}", parent=win)

                def _test_capture(em=e):
                    self._debug_capture_emulator(em, win)

                RoundedButton(row, "📸 Chụp Thử", command=_test_capture, bg=COL_PURPLE,
                              container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(side="right", padx=4, pady=4)
                RoundedButton(row, "🔌 Kết nối lại", command=_reconnect, bg=COL_TEAL,
                              container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(side="right", padx=6, pady=4)

        def _rescan():
            self.refresh_emulators()
            win.destroy()
            self._open_emulator_panel()

        RoundedButton(win, "🔄 Quét Lại", command=_rescan,
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")).pack(pady=10)

    def _open_help_panel(self):
        win = tk.Toplevel(self.root)
        win.title("Hướng Dẫn")
        win.configure(bg=COL_PANEL)
        win.geometry("580x540")

        txt = tk.Text(win, bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 10), wrap="word",
                      relief="flat", padx=14, pady=14)
        txt.pack(fill="both", expand=True)
        txt.insert("end", HELP_TEXT)
        txt.config(state="disabled")

    def _open_shop_settings(self, muc):
        win = tk.Toplevel(self.root)
        win.title(f"Cài Đặt Mua Shop - {muc}")
        win.configure(bg=COL_PANEL)
        win.geometry("400x190")

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


if __name__ == "__main__":
    _set_dpi_awareness()
    root = tk.Tk()
    app = DashboardApp(root)
    root.mainloop()
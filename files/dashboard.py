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
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import cv2

from adb_helper import ADBHelper
from logic_engine import LogicEngine, BreakGroupSignal, ContinueGroupSignal
from window_finder import WindowFinder
from emulator_manager import EmulatorManager
import task_registry
import run_state
import account_manager
import scheduler

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

6) XOAY VÒNG TÀI KHOẢN (nhiều tài khoản trên CÙNG 1 giả lập)
   a) Soạn 2 kịch bản bắt buộc bằng '➕ Tạo Hoạt Động' (ghi F7 như bình
      thường), rồi Đăng Ký Tác Vụ với đúng tên file:
        tasks/account_login.json   -> id "account_login"  (các bước ĐĂNG
             NHẬP). Ở bước 'Gõ Chữ', gõ đúng {tk_user} và {tk_pass} thay vì
             gõ tay - Dashboard sẽ tự điền đúng tài khoản đang xoay tới.
        tasks/account_logout.json  -> id "account_logout" (các bước ĐĂNG
             XUẤT tài khoản đang đăng nhập).
   b) Bấm '👥 Quản Lý Tài Khoản', thêm từng tài khoản: tên hiển thị,
      username, password, và GÁN cho 1 giả lập cụ thể (theo index - vẫn
      đúng dù bạn đổi tên giả lập sau này). Bấm '💾 Lưu Tất Cả'.
   c) Tick 'Xoay Vòng Tài Khoản' ở thanh trên, tick chọn tác vụ + giả lập
      như bình thường rồi bấm '▶ CHẠY TẤT CẢ TÁC VỤ ĐANG CHỌN'.
   d) Với MỖI giả lập đã tick: Dashboard tự kiểm tra đang bật hay tắt - nếu
      TẮT thì tự khởi động (qua ldconsole) và chờ tới khi sẵn sàng, rồi lần
      lượt: Đăng Xuất -> Đăng Nhập tài khoản kế tiếp -> chạy các tác vụ đã
      tick -> sang tài khoản tiếp theo, cho tới hết danh sách tài khoản đã
      gán cho giả lập đó (chỉ tính tài khoản đang BẬT trong danh sách).

7) HẸN GIỜ TỰ ĐỘNG (chạy 1 Hoạt Động cho 1 nhóm tài khoản vào giờ cố định,
   hoặc lặp lại mỗi N giờ - KHÔNG cần bấm CHẠY thủ công)
   a) Bấm '⏰ Hẹn Giờ' ở góc trên, bấm '➕ Thêm Lịch Mới'.
   b) Đặt tên lịch, chọn Loại:
        - "Hằng ngày": nhập giờ chạy dạng hh:mm (vd 07:00) - chạy 1 lần
          mỗi ngày đúng giờ đó.
        - "Mỗi N giờ": nhập số giờ ở ô "Mỗi (giờ)" (vd 4) - chạy lặp lại
          cách nhau đúng N giờ, tính từ lần chạy gần nhất (chạy ngay lần
          đầu khi vừa Lưu, các lần sau tự cách đều).
   c) Bấm '🎯 HĐ (...)' chọn các Hoạt Động sẽ chạy, '👤 TK (...)' chọn các
      Tài khoản áp dụng lịch này (mỗi tài khoản phải đã được GÁN giả lập ở
      '👥 Quản Lý Tài Khoản' thì mới chạy được). Bấm 💾 ở cuối dòng để lưu.
   d) Khi tới giờ: Dashboard tự nhóm các tài khoản theo giả lập được gán,
      tự BẬT giả lập nếu đang tắt, rồi Đăng Xuất -> Đăng Nhập từng tài
      khoản -> chạy đúng các Hoạt Động đã chọn cho lịch đó - y hệt cơ chế
      Xoay Vòng Tài Khoản ở mục 6, nhưng do THỜI GIAN kích hoạt tự động.
   e) Dashboard PHẢI ĐANG MỞ (có thể thu nhỏ, không cần thao tác gì) để
      lịch tự kích hoạt đúng giờ - đóng chương trình thì lịch sẽ không
      chạy. Nếu 1 giả lập đang bận (đang chạy tay hoặc 1 lịch khác), lượt
      chạy đó sẽ bị bỏ qua và ghi rõ trong Nhật Ký - không xếp hàng chờ.
      Nút DỪNG LẠI / Tạm Dừng ở dưới áp dụng luôn cho các lịch đang chạy.
"""


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
        # Nếu người dùng đã từng tự chỉ đường dẫn ldconsole.exe thủ công (xem
        # choose_ldconsole_path) - áp dụng lại luôn, không cần tự dò lại mỗi
        # lần mở app (tự dò có thể thất bại nếu chưa có giả lập nào đang bật).
        custom_ldconsole = self._settings.get("ldconsole_path")
        if custom_ldconsole and os.path.exists(custom_ldconsole):
            self.emu_manager.ldconsole_path = custom_ldconsole
        self.emulators = []
        self.emu_vars = {}
        self.emu_all_var = tk.BooleanVar(value=True)

        self.stop_flag = False
        self.pause_flag = False
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

        self.accounts = account_manager.load_accounts()

        # ================= HẸN GIỜ TỰ ĐỘNG =================
        self.schedules = scheduler.load_schedules()
        self._active_schedule_count = 0
        self._disabled_schedule_notified = {}  # {schedule_id: "YYYY-MM-DD"} - chống spam cảnh báo lịch đang TẮT
        # Các index giả lập đang bận (đang chạy tay HOẶC đang được 1 lịch hẹn
        # giờ dùng) - dùng để tránh chạy tay và lịch tự động cùng điều khiển
        # 1 giả lập cùng lúc (đá nhau/chạm chuột chồng chéo).
        self._busy_emulator_indexes = set()
        # Hàng chờ THEO TỪNG GIẢ LẬP (key = emulator.index): list các
        # start_fn (hàm không tham số) đã bị hoãn vì giả lập đang bận lúc
        # yêu cầu tới. Khi giả lập đó XONG việc hiện tại, _release_emulator()
        # sẽ tự lấy ĐÚNG start_fn đầu hàng ra chạy ngay - giữ nguyên THỨ TỰ
        # các yêu cầu (chạy tay / xoay vòng tài khoản / lịch hẹn giờ) đã gửi
        # tới giả lập đó, thay vì bỏ qua (im lặng) như trước đây.
        self._emulator_queues = {}

        self._build_ui()
        self.reload_tasks()
        self.refresh_emulators()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(2000, self._watch_registry)
        self.root.after(20000, self._check_schedules)

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
            "account_rotate": bool(self.account_rotate_var.get()) if hasattr(self, "account_rotate_var") else False,
            "shop_settings": self.shop_settings,
            "ldconsole_path": getattr(self.emu_manager, "ldconsole_path", None),
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

        self.account_rotate_var = tk.BooleanVar(value=bool(self._settings.get("account_rotate", False)))
        DarkCheck(actions_bar, "Xoay Vòng Tài Khoản", self.account_rotate_var, bg=COL_BG).pack(side="left", padx=10)

        RoundedButton(actions_bar, "👥 Quản Lý Tài Khoản", command=self._open_account_manager,
                      bg=COL_PURPLE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)

        RoundedButton(actions_bar, "⏰ Hẹn Giờ", command=self._open_schedule_manager,
                      bg=COL_TEAL, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)

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
        RoundedButton(bar, "🔴 Tắt Đã Chọn", command=self.quit_selected_emulators,
                      bg=COL_RED, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=3, pady=6)
        RoundedButton(bar, "🟢 Bật Đã Chọn", command=self.launch_selected_emulators,
                      bg=COL_GREEN, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=3, pady=6)
        RoundedButton(bar, "📁 Chọn ldconsole.exe", command=self.choose_ldconsole_path,
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=3, pady=6)

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

        self.btn_pause = RoundedButton(
            bar, "⏸ Tạm Dừng", command=self.toggle_pause,
            bg=COL_ORANGE, container_bg=COL_BG, font=("Segoe UI", 10, "bold"), padx=14, pady=9)
        self.btn_pause.set_state("disabled")
        self.btn_pause.pack(side="left", padx=4)

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
        """Quét TOÀN BỘ giả lập đã cấu hình trong LDPlayer, KỂ CẢ những giả
        lập đang TẮT (dùng list_configured() thay vì refresh() vốn chỉ thấy
        giả lập đang chạy) - để người dùng vẫn tick chọn và bấm '🟢 Bật Đã
        Chọn' được ngay cả khi chưa mở sẵn giả lập nào."""
        self.emulators = self.emu_manager.list_configured()
        for w in self.emu_chip_frame.winfo_children():
            w.destroy()
        self.emu_vars = {}

        if not self.emulators:
            tk.Label(self.emu_chip_frame,
                     text="Không tìm thấy giả lập nào. Kiểm tra đường dẫn ldconsole.exe "
                          "(bấm '📁 Chọn ldconsole.exe') rồi bấm '🔄 Quét Giả Lập' lại.",
                     bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9)).pack(side="left", padx=6)
            self._refresh_log_filter_options()
            return

        DarkCheck(self.emu_chip_frame, "Tất cả giả lập", self.emu_all_var, bg=COL_PANEL,
                  command=self._on_toggle_all_emulators).pack(side="left", padx=8)

        for e in self.emulators:
            # Mặc định KHÔNG tự tick giả lập đang TẮT dù "Tất cả giả lập"
            # đang bật, tránh bấm CHẠY xong ăn lỗi "không thấy trong adb
            # devices" ngay lập tức - người dùng có thể tự tick tay nếu
            # muốn (vd để dùng chung với '🟢 Bật Đã Chọn').
            default_checked = bool(self.emu_all_var.get() and e.running)
            var = tk.BooleanVar(value=default_checked)
            self.emu_vars[e.name] = var
            label = f"🟢 {e.name}" if e.running else f"⚪ {e.name} (đang tắt)"
            fg = COL_TEXT if e.running else COL_TEXT_MUTED
            DarkCheck(self.emu_chip_frame, label, var, bg=COL_PANEL, fg=fg).pack(side="left", padx=6)

        if not self.emu_manager.has_ldconsole():
            self._log("warn", "Không tìm thấy ldconsole.exe - chỉ hiển thị được serial ADB, không có tên "
                               "giả lập thật và KHÔNG quét được giả lập đang TẮT. Bấm '📁 Chọn ldconsole.exe' "
                               "để chỉ đường dẫn thủ công (file ldconsole.exe nằm trong thư mục cài LDPlayer).")

        running_count = sum(1 for e in self.emulators if e.running)
        off_count = len(self.emulators) - running_count
        self._refresh_log_filter_options()
        self._log("info", f"Đã quét thấy {len(self.emulators)} giả lập ({running_count} đang chạy, {off_count} đang tắt).")

    def _on_toggle_all_emulators(self):
        val = self.emu_all_var.get()
        for var in self.emu_vars.values():
            var.set(val)

    def _get_selected_emulators(self):
        return [e for e in self.emulators if self.emu_vars.get(e.name, tk.BooleanVar(value=False)).get()]

    # ================= CHỌN ĐƯỜNG DẪN ldconsole.exe THỦ CÔNG =================
    def choose_ldconsole_path(self):
        """Cho phép người dùng tự trỏ tới file ldconsole.exe khi tự động dò
        không thành công (vd ldconsole.exe không nằm cùng thư mục adb.exe,
        không có tiến trình dnplayer.exe nào đang chạy để dò theo, và không
        cài ở 2 đường dẫn mặc định C:/D:\\leidian\\LDPlayer9). Lưu lại vào
        dashboard_settings.json để lần mở app sau không phải chọn lại."""
        path = filedialog.askopenfilename(
            title="Chọn file ldconsole.exe (trong thư mục cài LDPlayer)",
            filetypes=[("ldconsole.exe", "ldconsole.exe"), ("Tệp thực thi", "*.exe"), ("Tất cả file", "*.*")]
        )
        if not path:
            return
        self.emu_manager.ldconsole_path = path
        self._save_settings()
        self._log("success", f"Đã đặt đường dẫn ldconsole.exe: {path}")
        self.refresh_emulators()

    # ================= BẬT / TẮT GIẢ LẬP ĐÃ CHỌN =================
    def launch_selected_emulators(self):
        selected = self._get_selected_emulators()
        if not selected:
            messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào để khởi động!\nTick chọn ở thanh 'Giả lập' trước.")
            return
        if not self.emu_manager.has_ldconsole():
            messagebox.showwarning("Lưu ý", "Chưa tìm thấy ldconsole.exe.\n"
                                             "Bấm '📁 Chọn ldconsole.exe' để chỉ đường dẫn thủ công.")
            return
        threading.Thread(target=self._worker_launch_emulators, args=(list(selected),), daemon=True).start()

    def _worker_launch_emulators(self, selected):
        for e in selected:
            self._log("info", f"Đang khởi động giả lập '{e.name}' (#{e.index})...", emulator_name=e.name)
            ok, msg = self.emu_manager.launch(e.index)
            if ok:
                self._log("success", f"Đã gửi lệnh khởi động giả lập '{e.name}' (#{e.index}). "
                                      f"Chờ khoảng 30-60s cho Android khởi động xong rồi bấm '🔄 Quét Giả Lập' "
                                      f"lại để cập nhật trạng thái.", emulator_name=e.name)
            else:
                self._log("error", f"Không khởi động được giả lập '{e.name}' (#{e.index}): {msg}", emulator_name=e.name)
        self.root.after(1500, self.refresh_emulators)

    def quit_selected_emulators(self):
        selected = self._get_selected_emulators()
        if not selected:
            messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào để tắt!\nTick chọn ở thanh 'Giả lập' trước.")
            return
        if not self.emu_manager.has_ldconsole():
            messagebox.showwarning("Lưu ý", "Chưa tìm thấy ldconsole.exe.\n"
                                             "Bấm '📁 Chọn ldconsole.exe' để chỉ đường dẫn thủ công.")
            return
        if not messagebox.askyesno("Xác nhận", f"Tắt {len(selected)} giả lập đã chọn?"):
            return
        threading.Thread(target=self._worker_quit_emulators, args=(list(selected),), daemon=True).start()

    def _worker_quit_emulators(self, selected):
        for e in selected:
            self._log("info", f"Đang tắt giả lập '{e.name}' (#{e.index})...", emulator_name=e.name)
            ok, msg = self.emu_manager.quit_emulator(e.index)
            if ok:
                self._log("success", f"Đã gửi lệnh tắt giả lập '{e.name}' (#{e.index}).", emulator_name=e.name)
            else:
                self._log("error", f"Không tắt được giả lập '{e.name}' (#{e.index}): {msg}", emulator_name=e.name)
        self.root.after(1500, self.refresh_emulators)

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
        _bind_esc_close(win)

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

        if self.account_rotate_var.get():
            self._start_run_with_accounts(selected, selected_emulators)
            return

        login_entry = None
        if self.auto_login_var.get():
            login_entry = task_registry.find_task(self.tasks, "auto_login")
            if not login_entry:
                self._log("warn", "Đã bật 'Tự Login' nhưng chưa có Hoạt Động với id 'auto_login' (xem '📖 Hướng Dẫn').")

        self._start_run(selected, selected_emulators, login_entry)

    def _queue_or_start(self, emulator_index, start_fn, context_label, display_name):
        """Nếu giả lập ĐANG RẢNH: đánh dấu bận rồi chạy `start_fn()` ngay.
        Nếu ĐANG BẬN (có 1 phiên chạy tay / xoay vòng / lịch hẹn giờ khác
        đang dùng giả lập này): xếp `start_fn` vào HÀNG CHỜ riêng của giả
        lập đó (FIFO - vào trước chạy trước) thay vì bỏ qua. Ngay khi việc
        đang chạy hiện tại trên giả lập đó KẾT THÚC, `_release_emulator()`
        sẽ tự lấy đúng việc đầu hàng chờ ra chạy tiếp, đảm bảo các hành
        động luôn được thực hiện ĐÚNG THEO THỨ TỰ đã yêu cầu, không chồng
        chéo lên nhau (tránh 2 luồng cùng đá chuột/gõ phím vào 1 cửa sổ)."""
        if emulator_index in self._busy_emulator_indexes:
            queue = self._emulator_queues.setdefault(emulator_index, [])
            queue.append(start_fn)
            self._log("info", f"'{display_name}' đang bận - đã XẾP VÀO HÀNG CHỜ ({context_label}), vị trí "
                               f"#{len(queue)}. Sẽ tự chạy ngay khi xong việc hiện tại, đúng thứ tự đã yêu cầu.")
            return False
        self._busy_emulator_indexes.add(emulator_index)
        start_fn()
        return True

    def _release_emulator(self, emulator_index):
        """Gọi khi giả lập VỪA XONG 1 việc (chạy tay / xoay vòng / lịch hẹn
        giờ). Bỏ đánh dấu BẬN, rồi nếu có việc đang XẾP HÀNG CHỜ cho đúng
        giả lập này thì lấy việc ĐẦU HÀNG (FIFO) ra chạy NGAY LẬP TỨC, giữ
        đúng thứ tự các yêu cầu đã gửi tới - đây chính là cách "hết việc
        này thì tự chạy tiếp việc kế tiếp" mà không cần người dùng bấm lại."""
        self._busy_emulator_indexes.discard(emulator_index)
        queue = self._emulator_queues.get(emulator_index)
        if queue:
            next_fn = queue.pop(0)
            if not queue:
                self._emulator_queues.pop(emulator_index, None)
            self._busy_emulator_indexes.add(emulator_index)
            self._log("info", f"Giả lập #{emulator_index} đã rảnh - tự chạy tiếp việc kế tiếp trong hàng chờ "
                               f"({len(queue)} việc còn lại phía sau).")
            next_fn()

    def _start_run(self, selected, selected_emulators, login_entry):
        self.is_running = True
        self.stop_flag = False
        self.pause_flag = False
        self.btn_pause.set_text("⏸ Tạm Dừng")
        self.active_threads = len(selected_emulators)
        self.btn_run.set_state("disabled")
        self._refresh_run_control_buttons()

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
            def _start(emulator=emulator):
                threading.Thread(target=self._worker_run_emulator, args=(emulator, selected, login_entry), daemon=True).start()
            self._queue_or_start(emulator.index, _start, "chạy tác vụ", emulator.name)

    def stop_run(self):
        self.stop_flag = True
        self.pause_flag = False
        self.btn_pause.set_text("⏸ Tạm Dừng")
        self._log("warn", "Người dùng bấm DỪNG - đang chờ các luồng/lịch hiện tại kết thúc...")

    def _any_active_work(self):
        """True nếu có BẤT KỲ việc gì đang chạy - phiên CHẠY thủ công (tick
        chọn tác vụ) HOẶC 1 lịch hẹn giờ đang thực thi. Dùng để bật/tắt nút
        DỪNG + Tạm Dừng đúng lúc kể cả khi việc đang chạy là do lịch tự kích
        hoạt (người dùng không hề bấm nút CHẠY)."""
        return self.is_running or self._active_schedule_count > 0

    def _refresh_run_control_buttons(self):
        active = self._any_active_work()
        self.btn_stop.set_state("normal" if active else "disabled")
        self.btn_pause.set_state("normal" if active else "disabled")
        if not active:
            # Không còn gì chạy -> RESET stop_flag để LẦN TRIGGER TIẾP THEO
            # của 1 lịch hẹn giờ (không đi qua _start_run - nơi duy nhất
            # trước đây reset cờ này) không bị coi là "đã bị dừng" ngay từ
            # đầu và im lặng không chạy gì cả.
            self.stop_flag = False
            self.pause_flag = False
            self.btn_pause.set_text("⏸ Tạm Dừng")

    def toggle_pause(self):
        """Bật/tắt tạm dừng phiên chạy hiện tại (thủ công hoặc lịch hẹn
        giờ). Không dừng hẳn luồng - chỉ chặn LogicEngine lại NGAY TRƯỚC
        lần kiểm tra dừng kế tiếp (xem _make_stop_checker), nên độ trễ tạm
        dừng chỉ trong vòng 1 bước/1 vòng lặp chờ ảnh, không phải chờ hết
        cả tác vụ."""
        if not self._any_active_work():
            return
        self.pause_flag = not self.pause_flag
        if self.pause_flag:
            self.btn_pause.set_text("▶ Tiếp Tục")
            self._log("warn", "Người dùng bấm TẠM DỪNG - các giả lập sẽ dừng lại giữa bước hiện tại, "
                               "bấm '▶ Tiếp Tục' để chạy tiếp.")
        else:
            self.btn_pause.set_text("⏸ Tạm Dừng")
            self._log("info", "Đã bấm TIẾP TỤC - các giả lập chạy lại bình thường.")

    def _make_stop_checker(self):
        """Trả về hàm stop_checker() cho LogicEngine của 1 luồng giả lập.
        LogicEngine gọi hàm này liên tục ở MỌI điểm dừng an toàn (giữa mỗi
        bước, trong vòng lặp chờ ảnh...) để biết có nên dừng hẳn không - tận
        dụng luôn các điểm gọi đó làm điểm TẠM DỪNG: khi self.pause_flag
        đang bật, hàm sẽ 'đứng chờ' tại đây (vẫn kiểm tra stop_flag để nút
        DỪNG luôn hoạt động ngay cả khi đang tạm dừng) thay vì trả về ngay,
        nên KHÔNG cần sửa gì trong logic_engine.py."""
        def checker():
            while self.pause_flag and not self.stop_flag:
                time.sleep(0.15)
            return self.stop_flag
        return checker

    def _worker_run_emulator(self, emulator, selected, login_entry):
        if not self.emu_manager.ensure_adb_connected(emulator):
            self._log("error", f"Không thấy giả lập trong 'adb devices' (serial: {emulator.adb_serial}). "
                                f"Bỏ qua giả lập này - hãy bấm 'Quét Giả Lập' hoặc 'Kết nối lại ADB' rồi thử lại.",
                       emulator_name=emulator.name)
            self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
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
            stop_checker=self._make_stop_checker(),
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

        self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))

    # ================= CHẠY XOAY VÒNG TÀI KHOẢN (tự bật giả lập + đổi tài khoản) =================
    def _start_run_with_accounts(self, selected, selected_emulators):
        self.accounts = account_manager.load_accounts()

        self.is_running = True
        self.stop_flag = False
        self.pause_flag = False
        self.btn_pause.set_text("⏸ Tạm Dừng")
        self.active_threads = len(selected_emulators)
        self.btn_run.set_state("disabled")
        self._refresh_run_control_buttons()

        for entry in selected:
            task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
            self.task_progress[task_id] = {"total": len(selected_emulators), "done": 0, "error": 0, "running": 0, "stopped": 0}
            lbl = self.task_status_lbl.get(task_id)
            if lbl:
                lbl.config(text="⏳ Đang chờ", fg=COL_TEXT_MUTED)

        self._update_status_label()
        names = ", ".join(e.name for e in selected_emulators)
        self._log("info", f"══════ Bắt đầu phiên CHẠY XOAY VÒNG TÀI KHOẢN: {len(selected)} tác vụ trên [{names}] ══════")

        for emulator in selected_emulators:
            def _start(emulator=emulator):
                threading.Thread(target=self._worker_run_emulator_with_accounts, args=(emulator, selected), daemon=True).start()
            self._queue_or_start(emulator.index, _start, "xoay vòng tài khoản", emulator.name)

    def _worker_run_emulator_with_accounts(self, emulator, selected):
        # 1) Đảm bảo giả lập ĐANG BẬT VÀ SẴN SÀNG - tự khởi động qua
        # ldconsole nếu đang tắt (đây chính là "tự nhận diện bật/tắt, nếu
        # tắt thì khởi động" mà tính năng xoay vòng tài khoản cần).
        ready_info, _auto_started = self.emu_manager.ensure_running(
            emulator.index, timeout=120,
            on_log=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )
        if not ready_info:
            self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
            return
        emulator = ready_info  # dùng thông tin MỚI NHẤT (hwnd/serial có thể đổi sau khi vừa bật lại)

        if not self.emu_manager.ensure_adb_connected(emulator):
            self._log("error", f"Không thấy giả lập trong 'adb devices' (serial: {emulator.adb_serial}) sau khi "
                                f"khởi động. Bỏ qua giả lập này.", emulator_name=emulator.name)
            self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
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
            self._log("warn", f"Cửa sổ LDPlayer '{emulator.name}' đang bị THU NHỎ - đã tự khôi phục lại.",
                       emulator_name=emulator.name)
            time.sleep(0.5)

        engine = LogicEngine(
            adb,
            stop_checker=self._make_stop_checker(),
            popup_notifier=lambda msg, dur=0, _wf=wf: self._show_ingame_popup(_wf, msg, dur),
            logger=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )

        # 2) Danh sách tài khoản đã gán cho giả lập này (theo INDEX, xem
        # account_manager.py). Không có tài khoản nào -> chạy tác vụ 1 lần
        # bình thường (không xoay vòng) thay vì bỏ trắng cả phiên chạy.
        accounts = account_manager.accounts_for_emulator(self.accounts, emulator.index)
        if not accounts:
            self._log("warn", f"Giả lập '{emulator.name}' (#{emulator.index}) chưa được gán tài khoản nào đang BẬT "
                               f"trong '👥 Quản Lý Tài Khoản' - chạy các tác vụ đã chọn 1 lần, không xoay vòng.",
                       emulator_name=emulator.name)
            for entry in selected:
                if self.stop_flag:
                    break
                self._exec_entry(engine, emulator, entry, preset_vars=None, tracked=True)
            self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
            return

        login_entry = task_registry.find_task(self.tasks, "account_login")
        logout_entry = task_registry.find_task(self.tasks, "account_logout")
        if not login_entry:
            self._log("error", "Chưa có Hoạt Động với id 'account_login' - hãy soạn kịch bản đăng nhập (dùng "
                                "{tk_user} / {tk_pass} ở bước Gõ Chữ) rồi Đăng Ký Tác Vụ với tên file "
                                "tasks/account_login.json. Đã bỏ qua xoay vòng cho giả lập này.",
                       emulator_name=emulator.name)
            self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
            return
        if not logout_entry:
            self._log("warn", "Chưa có Hoạt Động với id 'account_logout' - sẽ đăng nhập tài khoản mới mà KHÔNG "
                               "đăng xuất tài khoản trước đó (nên soạn thêm tasks/account_logout.json để tránh "
                               "đăng nhập chồng).", emulator_name=emulator.name)

        # 3) Lần lượt từng tài khoản: đăng xuất (nếu có) -> đăng nhập (điền
        # {tk_user}/{tk_pass}) -> chạy các tác vụ đã tick -> tài khoản kế tiếp.
        for acc in accounts:
            if self.stop_flag:
                break

            ten = acc.get("ten_hien_thi") or acc.get("username") or acc.get("id")
            self._log("info", f"═══ Tài khoản: {ten} ═══", emulator_name=emulator.name)

            if logout_entry:
                self._exec_entry(engine, emulator, logout_entry, preset_vars=None, tracked=False)
                if self.stop_flag:
                    break

            preset_vars = {"tk_user": acc.get("username", ""), "tk_pass": acc.get("password", "")}
            ok_login = self._exec_entry(engine, emulator, login_entry, preset_vars=preset_vars, tracked=False)
            if not ok_login:
                self._log("error", f"Đăng nhập thất bại cho tài khoản '{ten}' - bỏ qua tài khoản này, chuyển "
                                    f"tiếp tài khoản kế tiếp.", emulator_name=emulator.name)
                continue

            for entry in selected:
                if self.stop_flag:
                    break
                self._exec_entry(engine, emulator, entry, preset_vars=preset_vars, tracked=True)

            if not self.stop_flag:
                account_manager.mark_run(self.accounts, acc.get("id"))
                self._log("success", f"Hoàn thành tài khoản '{ten}' trên giả lập '{emulator.name}'.",
                           emulator_name=emulator.name)

        self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))

    def _exec_entry(self, engine, emulator, entry, preset_vars, tracked):
        """Chạy 1 Hoạt Động (Tác Vụ) đơn lẻ bằng `engine` đã dựng sẵn cho
        giả lập này. `preset_vars` (dict hoặc None) được nạp vào biến của
        engine SAU khi reset - dùng để bơm {tk_user}/{tk_pass} của tài khoản
        đang xoay tới vào bước 'Gõ Chữ' của kịch bản đăng nhập/đăng xuất.
        `tracked=True` thì mới cập nhật tiến độ/nhãn trên danh sách tác vụ
        chính (đăng nhập/đăng xuất không tính là 1 'tác vụ' của người dùng
        nên tracked=False, giống cách login_entry cũ không được đếm tiến độ).
        Trả về True nếu chạy xong không lỗi, False nếu lỗi/bị dừng."""
        task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
        name = entry.get("ten_hien_thi", task_id)
        file_path = entry.get("file_json")

        if tracked:
            self._bump_task_progress(task_id, "running")
        self._log("info", f"── Bắt đầu tác vụ: {name} ──", emulator_name=emulator.name)

        if not file_path or not os.path.exists(file_path):
            self._log("error", f"Không tìm thấy file kịch bản: {file_path}", emulator_name=emulator.name)
            if tracked:
                self._bump_task_progress(task_id, "error")
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                steps = json.load(f)
            engine.reset_variables()
            if preset_vars:
                engine.variables.update(preset_vars)
            engine.execute_steps(steps, is_root=True)

            if self.stop_flag:
                if tracked:
                    self._bump_task_progress(task_id, "stopped")
                self._log("warn", f"Tác vụ '{name}' bị dừng giữa chừng.", emulator_name=emulator.name)
                return False

            if tracked:
                self._bump_task_progress(task_id, "done")
                run_state.mark_done(task_id, emulator.name)
            self._log("success", f"Hoàn thành tác vụ: {name}", emulator_name=emulator.name)
            return True

        except (BreakGroupSignal, ContinueGroupSignal):
            if tracked:
                self._bump_task_progress(task_id, "done")
                run_state.mark_done(task_id, emulator.name)
            self._log("warn", f"Tác vụ '{name}' kết thúc sớm do break/continue nằm ngoài GROUP.", emulator_name=emulator.name)
            return True
        except Exception as e:
            if tracked:
                self._bump_task_progress(task_id, "error")
            self._log("error", f"Lỗi khi chạy '{name}': {e}", emulator_name=emulator.name)
            return False

    def _on_emulator_thread_done(self, emulator_index=None):
        if emulator_index is not None:
            self._release_emulator(emulator_index)
        self.active_threads = max(0, self.active_threads - 1)
        if self.active_threads == 0:
            self._on_finish_all()
        else:
            self._update_status_label()

    def _update_status_label(self):
        parts = []
        if self.active_threads > 1:
            parts.append(f"Đang chạy đa luồng ({self.active_threads} luồng)")
        elif self.active_threads == 1:
            parts.append("Đang chạy...")
        if self._active_schedule_count:
            parts.append(f"⏰ {self._active_schedule_count} lịch hẹn giờ đang chạy nền")
        self.lbl_status.config(text="Trạng thái: " + (" | ".join(parts) if parts else "Sẵn sàng"))

    def _on_finish_all(self):
        self.is_running = False
        self.btn_run.set_state("normal")
        self._refresh_run_control_buttons()
        self._update_status_label()
        self._log("info", "══════ Kết thúc phiên chạy ══════")

    # ================= HẸN GIỜ TỰ ĐỘNG =================
    def _check_schedules(self):
        """Chạy mỗi 20s (xem __init__) - kiểm tra từng lịch trong
        schedules.json xem đã đến giờ chưa (scheduler.is_due), nếu có thì
        trigger ngay (scheduler.mark_triggered + lưu file TRƯỚC khi chạy
        xong, xem lý do trong scheduler.py)."""
        try:
            now = datetime.now()
            due_list = [e for e in self.schedules if scheduler.is_due(e, now)]
            if due_list:
                for entry in due_list:
                    scheduler.mark_triggered(entry, now)
                scheduler.save_schedules(self.schedules)
                for entry in due_list:
                    self._trigger_schedule(entry)

            # CẢNH BÁO 1 LẦN/NGÀY cho các lịch đang TẮT ('Bật' chưa tick)
            # nhưng lẽ ra đã tới giờ chạy - nếu không có dòng này, người
            # dùng quên tick 'Bật' sẽ thấy lịch "im lặng không chạy" mà
            # KHÔNG có bất kỳ log nào giải thích vì sao (is_due trả về
            # False ngay từ bước kiểm tra 'bat', không rớt vào due_list).
            today = now.strftime("%Y-%m-%d")
            for entry in self.schedules:
                if entry.get("bat", True):
                    continue
                if not scheduler.would_be_due_if_enabled(entry, now):
                    continue
                if self._disabled_schedule_notified.get(entry.get("id")) == today:
                    continue
                self._disabled_schedule_notified[entry.get("id")] = today
                self._log("warn", f"⏰ Lịch '{entry.get('ten', '?')}' đã tới giờ hẹn nhưng đang ở trạng thái "
                                   f"TẮT ('Bật' chưa tick) nên KHÔNG tự chạy - vào '⏰ Hẹn Giờ' tick 'Bật' "
                                   f"rồi bấm 💾 nếu muốn lịch này tự chạy.")
        except Exception as e:
            self._log("error", f"Lỗi kiểm tra lịch hẹn giờ: {e}")
        finally:
            self.root.after(20000, self._check_schedules)

    def _trigger_schedule(self, entry):
        """Tới giờ 1 lịch - dựng danh sách Hoạt Động tương ứng, rồi chọn 1
        trong 2 CHẾ ĐỘ chạy:
          - CÓ chọn Tài khoản (tai_khoan_ids không rỗng): nhóm tài khoản
            theo giả lập được GÁN CHO TÀI KHOẢN đó (account_manager), mỗi
            giả lập xoay vòng Đăng Xuất - Đăng Nhập - chạy Hoạt Động, y
            hệt trước đây.
          - KHÔNG chọn Tài khoản nào (tai_khoan_ids rỗng): dùng thẳng danh
            sách giả lập đã chọn TRỰC TIẾP ở lịch (may_ids) - chạy các Hoạt
            Động ngay trên giả lập đó, KHÔNG đăng xuất/đăng nhập đổi tài
            khoản (dùng đúng phiên đang đăng nhập sẵn). Đây là lựa chọn
            dành cho các lịch không cần xoay vòng tài khoản, chỉ cần chạy
            đúng giờ trên (các) giả lập chỉ định.
        Mỗi giả lập luôn chạy trên 1 luồng riêng (giống hệt cơ chế đa luồng
        của nút CHẠY thủ công)."""
        name = entry.get("ten", "Lịch không tên")
        hoat_dong_ids = set(entry.get("hoat_dong_ids", []))
        tai_khoan_ids = set(entry.get("tai_khoan_ids", []))
        may_ids = set(entry.get("may_ids", []))

        activities = [
            t for t in self.tasks
            if (t.get("id") or task_registry.make_task_id(t.get("file_json", ""))) in hoat_dong_ids
        ]
        if not activities:
            self._log("error", f"⏰ Lịch '{name}' đến giờ chạy nhưng không tìm thấy Hoạt Động nào khớp "
                                f"(có thể đã bị xoá khỏi Danh Mục) - bỏ qua lượt này.")
            return

        if not tai_khoan_ids and not may_ids:
            self._log("error", f"⏰ Lịch '{name}' đến giờ chạy nhưng chưa chọn Tài khoản LẪN Giả lập nào - "
                                f"bấm '👤 TK' (nếu muốn xoay vòng tài khoản) hoặc '🖥 GL' (nếu chỉ muốn chạy "
                                f"thẳng trên giả lập chỉ định) rồi lưu lại - bỏ qua lượt này.")
            return

        # ----- CHẾ ĐỘ 1: CÓ chọn Tài khoản -> xoay vòng như cũ -----
        if tai_khoan_ids:
            accounts_all = account_manager.load_accounts()
            accounts = [a for a in accounts_all if a.get("id") in tai_khoan_ids]
            if not accounts:
                self._log("error", f"⏰ Lịch '{name}' đến giờ chạy nhưng không tìm thấy Tài khoản nào khớp "
                                    f"(có thể đã bị xoá) - bỏ qua lượt này.")
                return

            self._log("info", f"⏰ Lịch '{name}' đến giờ chạy - {len(activities)} hoạt động × {len(accounts)} tài khoản.")

            by_emulator = {}
            for acc in accounts:
                idx = acc.get("emulator_index")
                if idx is None:
                    self._log("warn", f"⏰ Lịch '{name}': tài khoản "
                                       f"'{acc.get('ten_hien_thi') or acc.get('username') or acc.get('id')}' "
                                       f"chưa được gán giả lập nào - bỏ qua tài khoản này.")
                    continue
                by_emulator.setdefault(idx, []).append(acc)

            for idx, accs in by_emulator.items():
                emu_name = next((e.name for e in self.emulators if e.index == idx), f"#{idx}")

                def _start(idx=idx, accs=accs, emu_name=emu_name):
                    self._active_schedule_count += 1
                    self._refresh_run_control_buttons()
                    self._update_status_label()
                    threading.Thread(target=self._worker_run_schedule, args=(name, idx, accs, activities), daemon=True).start()

                self._queue_or_start(idx, _start, f"lịch '{name}'", emu_name)
            return

        # ----- CHẾ ĐỘ 2: KHÔNG chọn Tài khoản -> chạy thẳng trên (các) giả lập đã chọn -----
        self._log("info", f"⏰ Lịch '{name}' đến giờ chạy - {len(activities)} hoạt động, chạy thẳng trên "
                           f"{len(may_ids)} giả lập (không đổi tài khoản).")
        for idx in may_ids:
            emu_name = next((e.name for e in self.emulators if e.index == idx), f"#{idx}")

            def _start(idx=idx, emu_name=emu_name):
                self._active_schedule_count += 1
                self._refresh_run_control_buttons()
                self._update_status_label()
                threading.Thread(target=self._worker_run_schedule, args=(name, idx, [], activities), daemon=True).start()

            self._queue_or_start(idx, _start, f"lịch '{name}'", emu_name)

    def _worker_run_schedule(self, schedule_name, emulator_index, accounts, activities):
        """Chạy 1 lượt lịch hẹn giờ trên 1 giả lập (emulator_index): tự bật
        giả lập nếu đang tắt, rồi:
          - Nếu `accounts` KHÔNG rỗng: lần lượt từng tài khoản - Đăng Xuất
            (nếu có) -> Đăng Nhập -> chạy đúng các Hoạt Động của lịch này -
            giống hệt '👥 Xoay Vòng Tài Khoản' nhưng do THỜI GIAN kích hoạt
            thay vì người dùng bấm CHẠY.
          - Nếu `accounts` RỖNG (lịch không chọn Tài khoản, chỉ chọn thẳng
            Giả lập): chạy các Hoạt Động NGAY 1 lần trên giả lập này, KHÔNG
            đăng xuất/đăng nhập đổi tài khoản gì cả."""
        tag = f"⏰ {schedule_name}"
        try:
            ready_info, _auto_started = self.emu_manager.ensure_running(
                emulator_index, timeout=120,
                on_log=lambda lvl, msg: self._log(lvl, f"[{tag}] {msg}")
            )
            if not ready_info:
                self._log("error", f"[{tag}] Không bật được giả lập #{emulator_index} - bỏ qua lượt này.")
                return
            emulator = ready_info

            if not self.emu_manager.ensure_adb_connected(emulator):
                self._log("error", f"[{tag}] Không thấy giả lập '{emulator.name}' trong 'adb devices' sau khi "
                                    f"khởi động - bỏ qua lượt này.", emulator_name=emulator.name)
                return

            adb = ADBHelper()
            adb.device_id = emulator.adb_serial
            adb.update_resolution()

            wf = WindowFinder(adb)
            attached = wf.attach_hwnd(emulator.hwnd) if emulator.hwnd else False
            if not attached:
                wf.find_ld_windows()
            if wf.ensure_window_visible():
                self._log("warn", f"[{tag}] Cửa sổ LDPlayer '{emulator.name}' đang bị THU NHỎ - đã tự khôi phục lại.",
                           emulator_name=emulator.name)
                time.sleep(0.5)

            engine = LogicEngine(
                adb,
                stop_checker=self._make_stop_checker(),
                popup_notifier=lambda msg, dur=0, _wf=wf: self._show_ingame_popup(_wf, msg, dur),
                logger=lambda lvl, msg, _e=emulator: self._log(lvl, f"[{tag}] {msg}", emulator_name=_e.name)
            )

            # KHÔNG có tài khoản nào (lịch chọn thẳng Giả lập, không chọn
            # Tài khoản) -> chạy các Hoạt Động NGAY trên giả lập này, dùng
            # đúng phiên đang đăng nhập sẵn, KHÔNG đăng xuất/đăng nhập đổi
            # tài khoản gì cả.
            if not accounts:
                self._log("info", f"[{tag}] Chạy thẳng trên '{emulator.name}' (không chọn Tài khoản - "
                                   f"không đổi tài khoản).", emulator_name=emulator.name)
                for act_entry in activities:
                    if self.stop_flag:
                        break
                    self._exec_entry(engine, emulator, act_entry, preset_vars=None, tracked=False)
                if not self.stop_flag:
                    self._log("success", f"[{tag}] Hoàn thành trên '{emulator.name}'.", emulator_name=emulator.name)
                return

            login_entry = task_registry.find_task(self.tasks, "account_login")
            logout_entry = task_registry.find_task(self.tasks, "account_logout")
            if not login_entry:
                self._log("warn", f"[{tag}] Chưa có Hoạt Động 'account_login' - sẽ chạy thẳng các Hoạt Động đã "
                                   f"hẹn mà KHÔNG đăng nhập lại đúng tài khoản (dùng đúng phiên đang đăng nhập sẵn "
                                   f"trên giả lập).", emulator_name=emulator.name)

            for acc in accounts:
                if self.stop_flag:
                    break
                ten = acc.get("ten_hien_thi") or acc.get("username") or acc.get("id")
                self._log("info", f"[{tag}] ═══ Tài khoản: {ten} trên '{emulator.name}' ═══", emulator_name=emulator.name)

                preset_vars = None
                ok_login = True
                if login_entry:
                    if logout_entry:
                        self._exec_entry(engine, emulator, logout_entry, preset_vars=None, tracked=False)
                        if self.stop_flag:
                            break
                    preset_vars = {"tk_user": acc.get("username", ""), "tk_pass": acc.get("password", "")}
                    ok_login = self._exec_entry(engine, emulator, login_entry, preset_vars=preset_vars, tracked=False)

                if not ok_login:
                    self._log("error", f"[{tag}] Đăng nhập thất bại cho '{ten}' - bỏ qua tài khoản này.",
                               emulator_name=emulator.name)
                    continue

                for act_entry in activities:
                    if self.stop_flag:
                        break
                    self._exec_entry(engine, emulator, act_entry, preset_vars=preset_vars, tracked=False)

                if not self.stop_flag:
                    account_manager.mark_run(account_manager.load_accounts(), acc.get("id"))
                    self._log("success", f"[{tag}] Hoàn thành tài khoản '{ten}'.", emulator_name=emulator.name)

        except Exception as e:
            self._log("error", f"[{tag}] Lỗi khi chạy trên giả lập #{emulator_index}: {e}")
        finally:
            self.root.after(0, lambda: self._on_schedule_thread_done(emulator_index))

    def _on_schedule_thread_done(self, emulator_index):
        self._release_emulator(emulator_index)
        self._active_schedule_count = max(0, self._active_schedule_count - 1)
        self._refresh_run_control_buttons()
        self._update_status_label()

    def _open_multi_select_dialog(self, parent, title, items, selected_ids, on_save, group_of=None):
        """Popup chọn nhiều mục bằng checkbox (dùng chung cho chọn Hoạt Động
        / chọn Tài Khoản / chọn Giả Lập khi soạn 1 lịch hẹn giờ). `items`:
        list (id, nhãn). `on_save(list_id_đã_chọn)` được gọi khi bấm Lưu.

        `group_of` (tuỳ chọn): dict {item_id: tên_nhóm} - nếu có, hiển thị
        thêm 1 hàng nút "chọn nhanh theo nhóm" (vd Clone / Acc chính) ở đầu
        danh sách, bấm 1 nút là tick hết các mục cùng nhóm đó ngay lập tức
        thay vì phải tick tay từng mục - dùng cho việc chọn nhanh Tài khoản
        theo phân loại đã đặt ở '👥 Quản Lý Tài Khoản'."""
        win = tk.Toplevel(parent)
        win.title(title)
        win.configure(bg=COL_PANEL)
        win.geometry("380x460")
        win.transient(parent)
        win.grab_set()
        win.focus_set()
        _bind_esc_close(win)

        tk.Label(win, text=title, bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        count_lbl = tk.Label(win, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8))
        count_lbl.pack(anchor="w", padx=14, pady=(0, 6))

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 8))

        # Cuộn được bằng con lăn chuột khi trỏ nằm trên danh sách - trước
        # đây chỉ kéo được thanh cuộn bên phải, dễ khiến người dùng tưởng
        # nhầm là "không chọn được" các mục nằm khuất bên dưới.
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        inner.bind("<MouseWheel>", _on_mousewheel)

        vars_by_id = {}

        def _update_count():
            n = sum(1 for v in vars_by_id.values() if v.get())
            count_lbl.config(text=f"Đã chọn {n}/{len(vars_by_id)} mục")

        # ----- Hàng nút "chọn nhanh theo nhóm" (vd Clone / Acc chính) -----
        if group_of:
            groups_seen = []
            for item_id, _label in items:
                g = (group_of.get(item_id) or "Chưa phân nhóm").strip() or "Chưa phân nhóm"
                if g not in groups_seen:
                    groups_seen.append(g)
            if len(groups_seen) > 1 or (groups_seen and groups_seen[0] != "Chưa phân nhóm"):
                group_bar = tk.Frame(win, bg=COL_PANEL)
                group_bar.pack(fill="x", padx=14, pady=(0, 6))
                tk.Label(group_bar, text="Chọn nhanh theo nhóm:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                         font=("Segoe UI", 8)).pack(side="left", padx=(0, 6))

                def _select_group(g):
                    for iid, _lbl in items:
                        grp = (group_of.get(iid) or "Chưa phân nhóm").strip() or "Chưa phân nhóm"
                        if grp == g:
                            vars_by_id[iid].set(True)
                    _update_count()

                for g in groups_seen:
                    RoundedButton(group_bar, f"☑ {g}", command=lambda g=g: _select_group(g),
                                  bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"),
                                  padx=8, pady=3).pack(side="left", padx=2)

        if not items:
            tk.Label(inner, text="(Không có mục nào)", bg=COL_PANEL, fg=COL_TEXT_MUTED).pack(anchor="w", pady=10)
        for item_id, label in items:
            v = tk.BooleanVar(value=item_id in selected_ids)
            vars_by_id[item_id] = v
            chk = DarkCheck(inner, label, v, command=_update_count, bg=COL_PANEL, wraplength=300)
            chk.pack(anchor="w", pady=2, padx=2, fill="x")
            chk.bind("<MouseWheel>", _on_mousewheel)
        _update_count()

        def _save():
            chosen = [iid for iid, v in vars_by_id.items() if v.get()]
            on_save(chosen)
            win.destroy()
            messagebox.showinfo("Đã chọn", f"Đã chọn {len(chosen)} mục cho '{title}'.\n"
                                            f"Nhớ bấm 💾 ở dòng lịch để lưu lại toàn bộ.", parent=parent)

        btn_bar = tk.Frame(win, bg=COL_PANEL)
        btn_bar.pack(fill="x", padx=14, pady=10)
        RoundedButton(btn_bar, "☑ Tất cả", command=lambda: ([v.set(True) for v in vars_by_id.values()], _update_count()),
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="left", padx=2)
        RoundedButton(btn_bar, "☐ Bỏ chọn", command=lambda: ([v.set(False) for v in vars_by_id.values()], _update_count()),
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="left", padx=2)
        RoundedButton(btn_bar, "💾 Lưu", command=_save, bg=COL_GREEN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9, "bold"), padx=12, pady=6).pack(side="right")

    def _open_schedule_manager(self):
        self.schedules = scheduler.load_schedules()
        self.accounts = account_manager.load_accounts()
        configured_emus = self.emu_manager.list_configured()

        win = tk.Toplevel(self.root)
        win.title("Hẹn Giờ Tự Động")
        win.configure(bg=COL_PANEL)
        win.geometry("1150x620")
        win.minsize(760, 480)
        _bind_esc_close(win)

        tk.Label(win, text="⏰ Lịch Chạy Tự Động", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(
            win,
            text="Mỗi lịch: chọn Hoạt Động áp dụng, đặt Giờ hẹn (mốc chạy lần đầu) và Lặp lại (hh:mm) - muốn "
                 "hằng ngày thì để 24:00, muốn mỗi 4 tiếng thì để 04:00. Rồi chọn 1 trong 2 cách chạy: (a) bấm "
                 "'👤 TK' chọn Tài khoản áp dụng - mỗi tài khoản tự Đăng Xuất - Đăng Nhập - chạy Hoạt Động, giống "
                 "'👥 Xoay Vòng Tài Khoản'; hoặc (b) KHÔNG chọn Tài khoản nào, chỉ bấm '🖥 GL' chọn thẳng (các) "
                 "Giả lập cần chạy - lịch sẽ chạy NGAY các Hoạt Động trên giả lập đó mà KHÔNG đổi tài khoản (dùng "
                 "đúng phiên đang đăng nhập sẵn). Cả 2 cách đều TỰ BẬT giả lập nếu đang tắt. Có thể bấm '▶ Chạy "
                 "Ngay' để chạy thử ngay lập tức mà không cần chờ tới giờ. Dashboard cần MỞ SẴN (chạy nền) để lịch "
                 "tự kích hoạt - không cần tick chọn thủ công trong danh sách tác vụ. Nhớ bấm 💾 ở từng dòng sau "
                 "khi sửa để lưu lại.",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=1110, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        if not self.tasks:
            tk.Label(win, text="⚠ Chưa có Hoạt Động nào trong Danh Mục - hãy Tạo & Đăng Ký Hoạt Động trước.",
                     bg=COL_PANEL, fg=COL_ORANGE, wraplength=1110, justify="left").pack(anchor="w", padx=14, pady=(0, 4))
        if not self.accounts:
            tk.Label(win, text="⚠ Chưa có Tài Khoản nào - hãy thêm ở '👥 Quản Lý Tài Khoản' trước nếu muốn xoay "
                                "vòng tài khoản (không bắt buộc - có thể để trống Tài khoản và chỉ chọn Giả lập).",
                     bg=COL_PANEL, fg=COL_ORANGE, wraplength=1110, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        if not configured_emus:
            tk.Label(win, text="⚠ Không tìm thấy giả lập nào (kiểm tra đường dẫn ldconsole.exe) - chưa thể chọn "
                                "thẳng Giả lập cho lịch.",
                     bg=COL_PANEL, fg=COL_ORANGE, wraplength=1110, justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        header = tk.Frame(win, bg=COL_HEADER)
        header.pack(fill="x", padx=10)
        for text, w in [("Bật", 4), ("Tên lịch", 16), ("Giờ hẹn (hh:mm)", 13), ("Lặp lại (hh:mm)", 12)]:
            tk.Label(header, text=text, bg=COL_HEADER, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"),
                     width=w, anchor="w").pack(side="left", padx=2, pady=6)
        tk.Label(header, text="Hoạt Động / Tài khoản / Giả lập chọn ở dòng dưới mỗi lịch ↓", bg=COL_HEADER,
                 fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"), anchor="w").pack(side="left", padx=8, pady=6)
        tk.Label(
            win,
            text="💡 Giờ hẹn = mốc chạy LẦN ĐẦU, theo đúng giờ này VĨNH VIỄN (kể cả sau khi bấm 'Chạy Ngay' để "
                 "test). Lặp lại (hh:mm) = cách bao lâu chạy lại 1 lần - muốn chạy hằng ngày thì để 24:00, "
                 "muốn mỗi 4 tiếng thì để 04:00, muốn mỗi 30 phút (để test nhanh) thì để 00:30.",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=1040, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 6))

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 6))

        activity_items = [
            (t.get("id") or task_registry.make_task_id(t.get("file_json", "")), t.get("ten_hien_thi", "?"))
            for t in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0)))
        ]
        account_items = [
            (a.get("id"), (a.get("ten_hien_thi") or a.get("username") or a.get("id")) +
             (f"  (giả lập #{a['emulator_index']})" if a.get("emulator_index") is not None else "  (chưa gán giả lập)"))
            for a in self.accounts
        ]
        account_group_of = {a.get("id"): (a.get("nhom") or "") for a in self.accounts}
        emulator_items = [
            (e.index, f"#{e.index} - {e.name}" + ("" if e.running else "  (đang tắt)"))
            for e in configured_emus
        ]

        def _add_row(entry):
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=3)

            # ----- DÒNG 1: Bật / Tên / Giờ hẹn / Lặp lại / Chạy lần cuối -----
            line1 = tk.Frame(row, bg=COL_PANEL_ALT)
            line1.pack(fill="x")

            bat_var = tk.BooleanVar(value=bool(entry.get("bat", True)))
            DarkCheck(line1, "", bat_var, bg=COL_PANEL_ALT, box_size=14).pack(side="left", padx=(6, 2), pady=4)

            ten_var = tk.StringVar(value=entry.get("ten", ""))
            tk.Entry(line1, textvariable=ten_var, width=16, bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2, pady=4)

            gio_var = tk.StringVar(value=entry.get("gio_hen", "07:00"))
            tk.Entry(line1, textvariable=gio_var, width=10, bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2, pady=4)

            interval_var = tk.StringVar(value=scheduler.hours_to_hhmm(entry.get("interval_hours", 24)))
            tk.Entry(line1, textvariable=interval_var, width=8, bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2, pady=4)

            last_run_text = entry.get("lan_chay_luc") or "Chưa chạy lần nào"
            last_run_lbl = tk.Label(line1, text=f"Chạy cuối: {last_run_text}", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                                     font=("Segoe UI", 8), anchor="w")
            last_run_lbl.pack(side="left", padx=(10, 4), pady=4)

            # ----- DÒNG 2: chọn Hoạt Động / Tài khoản / Giả lập + hành động -----
            line2 = tk.Frame(row, bg=COL_PANEL_ALT)
            line2.pack(fill="x")

            chosen_activities = list(entry.get("hoat_dong_ids", []))
            chosen_accounts = list(entry.get("tai_khoan_ids", []))
            chosen_emulators = list(entry.get("may_ids", []))

            btn_act = RoundedButton(line2, f"🎯 HĐ ({len(chosen_activities)})", bg=COL_BLUE,
                                     container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=8, pady=3)
            btn_act.pack(side="left", padx=(6, 2), pady=(0, 6))

            btn_acc = RoundedButton(line2, f"👤 TK ({len(chosen_accounts)})", bg=COL_PURPLE,
                                     container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=8, pady=3)
            btn_acc.pack(side="left", padx=2, pady=(0, 6))

            btn_may = RoundedButton(line2, f"🖥 GL ({len(chosen_emulators)})", bg=COL_TEAL,
                                     container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=8, pady=3)
            btn_may.pack(side="left", padx=2, pady=(0, 6))

            mode_lbl = tk.Label(line2, text="", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "italic"))
            mode_lbl.pack(side="left", padx=(6, 2), pady=(0, 6))

            def _refresh_mode_label():
                if chosen_accounts:
                    mode_lbl.config(text="→ xoay vòng tài khoản")
                elif chosen_emulators:
                    mode_lbl.config(text="→ chạy thẳng, không đổi tài khoản")
                else:
                    mode_lbl.config(text="→ (chưa chọn Tài khoản hoặc Giả lập)")
            _refresh_mode_label()

            def _pick_activities():
                def _on_save(chosen):
                    chosen_activities[:] = chosen
                    btn_act.set_text(f"🎯 HĐ ({len(chosen_activities)})")
                self._open_multi_select_dialog(win, "Chọn Hoạt Động cho lịch này",
                                                activity_items, set(chosen_activities), _on_save)
            btn_act.command = _pick_activities

            def _pick_accounts():
                def _on_save(chosen):
                    chosen_accounts[:] = chosen
                    btn_acc.set_text(f"👤 TK ({len(chosen_accounts)})")
                    _refresh_mode_label()
                self._open_multi_select_dialog(win, "Chọn Tài Khoản áp dụng lịch này (để trống nếu muốn chạy "
                                                     "thẳng bằng Giả lập, không đổi tài khoản)",
                                                account_items, set(chosen_accounts), _on_save,
                                                group_of=account_group_of)
            btn_acc.command = _pick_accounts

            def _pick_emulators():
                def _on_save(chosen):
                    chosen_emulators[:] = chosen
                    btn_may.set_text(f"🖥 GL ({len(chosen_emulators)})")
                    _refresh_mode_label()
                self._open_multi_select_dialog(win, "Chọn Giả Lập chạy thẳng cho lịch này (chỉ dùng khi KHÔNG "
                                                     "chọn Tài khoản)",
                                                emulator_items, set(chosen_emulators), _on_save)
            btn_may.command = _pick_emulators

            def _save_row(silent=False):
                entry["bat"] = bool(bat_var.get())
                entry["ten"] = ten_var.get().strip() or "Lịch không tên"
                gio_text = gio_var.get().strip() or "07:00"
                try:
                    hh, mm = [int(x) for x in gio_text.split(":")]
                    assert 0 <= hh <= 23 and 0 <= mm <= 59
                    entry["gio_hen"] = f"{hh:02d}:{mm:02d}"
                except Exception:
                    messagebox.showerror("Giờ hẹn không hợp lệ",
                                          f"'{gio_text}' không phải giờ hợp lệ. Nhập theo dạng HH:MM, "
                                          f"vd 07:00 hoặc 22:30.", parent=win)
                    return False
                try:
                    entry["interval_hours"] = scheduler.hhmm_to_hours(interval_var.get())
                except Exception:
                    messagebox.showerror("Giờ lặp lại không hợp lệ",
                                          f"'{interval_var.get()}' không đúng định dạng hh:mm. Nhập vd 24:00 "
                                          f"(hằng ngày), 04:00 (mỗi 4 tiếng), 00:30 (mỗi 30 phút để test).",
                                          parent=win)
                    return False
                entry["hoat_dong_ids"] = list(chosen_activities)
                entry["tai_khoan_ids"] = list(chosen_accounts)
                entry["may_ids"] = list(chosen_emulators)
                self.schedules = scheduler.upsert_schedule(self.schedules, entry)
                scheduler.save_schedules(self.schedules)
                trang_thai = "🟢 ĐANG BẬT - sẽ tự chạy đúng giờ" if entry["bat"] else "🔴 ĐANG TẮT - sẽ KHÔNG tự chạy cho tới khi bạn tick lại 'Bật'"
                if not silent:
                    che_do = "xoay vòng tài khoản" if chosen_accounts else "chạy thẳng giả lập"
                    self._log("success", f"Đã lưu lịch '{entry['ten']}' ({scheduler.describe(entry)}, "
                                          f"{len(chosen_activities)} hoạt động, chế độ {che_do}) - {trang_thai}.")
                    messagebox.showinfo("Đã lưu", f"Đã lưu lịch '{entry['ten']}'.\n\n{trang_thai}.", parent=win)
                return True

            def _delete_row():
                if not messagebox.askyesno("Xác nhận", f"Xoá lịch '{entry.get('ten', '')}' này?", parent=win):
                    return
                self.schedules = scheduler.remove_schedule(self.schedules, entry.get("id"))
                scheduler.save_schedules(self.schedules)
                row.destroy()
                self._log("warn", f"Đã xoá lịch '{entry.get('ten', '')}'.")

            def _run_now():
                if not _save_row(silent=True):
                    return
                if not entry.get("hoat_dong_ids"):
                    messagebox.showwarning("Thiếu Hoạt Động",
                                            "Lịch này chưa chọn Hoạt Động nào - bấm '🎯 HĐ' để chọn trước.",
                                            parent=win)
                    return
                if not entry.get("tai_khoan_ids") and not entry.get("may_ids"):
                    messagebox.showwarning("Thiếu Tài Khoản hoặc Giả Lập",
                                            "Lịch này chưa chọn Tài Khoản (để xoay vòng) LẪN Giả Lập (để chạy "
                                            "thẳng) - bấm '👤 TK' hoặc '🖥 GL' để chọn ít nhất 1 trong 2 trước.",
                                            parent=win)
                    return
                if not entry.get("bat", True):
                    # "Chạy Ngay" vẫn cho chạy thử dù lịch đang TẮT (không tick
                    # 'Bật') - nhưng phải cảnh báo rõ, nếu không người dùng dễ
                    # hiểu nhầm là lịch "vẫn hoạt động bình thường, tự chạy
                    # được" trong khi thực ra _check_schedules() sẽ bỏ qua nó
                    # hoàn toàn (không ghi log gì cả) cho tới khi tick lại Bật.
                    messagebox.showwarning(
                        "Lịch đang TẮT",
                        f"Lịch '{entry.get('ten', '')}' đang ở trạng thái TẮT (cột 'Bật' chưa tick) - "
                        f"nó sẽ KHÔNG tự chạy khi đến giờ hẹn. Lượt chạy thử này vẫn tiếp tục vì bạn bấm "
                        f"'Chạy Ngay' thủ công. Hãy tick 'Bật' rồi bấm 💾 nếu muốn lịch tự chạy sau này.",
                        parent=win)
                scheduler.mark_triggered(entry)
                scheduler.save_schedules(self.schedules)
                last_run_lbl.config(text=f"Chạy cuối: {entry.get('lan_chay_luc') or 'Chưa chạy lần nào'}")
                self._log("info", f"▶ Chạy ngay lịch '{entry.get('ten', '')}' theo yêu cầu thủ công.")
                self._trigger_schedule(entry)

            RoundedButton(line2, "▶ Chạy Ngay", command=_run_now, bg=COL_TEAL, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(side="right", padx=2, pady=(0, 6))
            RoundedButton(line2, "💾", command=_save_row, bg=COL_GREEN, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 9, "bold"), padx=8, pady=3).pack(side="right", padx=4, pady=(0, 6))
            RoundedButton(line2, "🗑", command=_delete_row, bg=COL_RED, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 9, "bold"), padx=8, pady=3).pack(side="right", padx=2, pady=(0, 6))

            sep = tk.Frame(row, bg=COL_HEADER, height=1)
            sep.pack(fill="x", pady=(2, 0))

        for entry in self.schedules:
            _add_row(entry)

        def _add_new():
            entry = {
                "id": scheduler.new_schedule_id(),
                "ten": "Lịch mới",
                "gio_hen": "07:00",
                "interval_hours": 24,
                "hoat_dong_ids": [],
                "tai_khoan_ids": [],
                "may_ids": [],
                "bat": True,
                "lan_chay_ngay": None,
                "lan_chay_luc": None,
            }
            _add_row(entry)

        RoundedButton(win, "➕ Thêm Lịch Mới", command=_add_new, bg=COL_ACCENT, fg="#241a00",
                      container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")).pack(pady=10)

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
        _bind_esc_close(win)

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

    # ================= QUẢN LÝ TÀI KHOẢN (xoay vòng) =================
    def _open_account_manager(self):
        self.accounts = account_manager.load_accounts()
        configured = self.emu_manager.list_configured()
        emu_options = [f"#{e.index} - {e.name}" for e in configured]
        emu_index_by_label = {f"#{e.index} - {e.name}": e.index for e in configured}
        label_by_index = {e.index: f"#{e.index} - {e.name}" for e in configured}

        win = tk.Toplevel(self.root)
        win.title("Quản Lý Tài Khoản (Xoay Vòng)")
        win.configure(bg=COL_PANEL)
        win.geometry("1060x560")
        win.minsize(760, 460)
        _bind_esc_close(win)

        tk.Label(win, text="👥 Danh Sách Tài Khoản Xoay Vòng", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(
            win,
            text="Mỗi tài khoản gán cho 1 giả lập, và có thể gắn 1 Nhóm (vd 'Clone', 'Acc chính'...) để lọc/chọn "
                 "nhanh khi hẹn giờ hoặc xoay vòng. Khi tick 'Xoay Vòng Tài Khoản' rồi bấm CHẠY: Dashboard tự BẬT "
                 "giả lập nếu đang tắt, rồi lần lượt từng tài khoản: Đăng Xuất -> Đăng Nhập (điền {tk_user}/"
                 "{tk_pass}) -> chạy các tác vụ đang tick -> sang tài khoản kế tiếp. Cần soạn sẵn 2 Hoạt Động "
                 "'account_login' và 'account_logout' (xem '📖 Hướng Dẫn').",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=1020, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        if not configured:
            tk.Label(win, text="⚠ Không tìm thấy ldconsole.exe hoặc chưa có giả lập nào trong LDPlayer - "
                                "chưa thể gán tài khoản.", bg=COL_PANEL, fg=COL_ORANGE,
                     wraplength=1020, justify="left").pack(anchor="w", padx=14, pady=(0, 6))

        filter_bar = tk.Frame(win, bg=COL_PANEL)
        filter_bar.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(filter_bar, text="Lọc nhanh theo Nhóm:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8)).pack(side="left", padx=(0, 6))
        filter_btns_frame = tk.Frame(filter_bar, bg=COL_PANEL)
        filter_btns_frame.pack(side="left")

        header = tk.Frame(win, bg=COL_HEADER)
        header.pack(fill="x", padx=10)
        for text, w in [("Bật", 4), ("Tên hiển thị", 14), ("Username", 14), ("Password", 14),
                         ("Nhóm", 10), ("Gán giả lập", 18), ("Ghi chú", 12), ("Chạy cuối", 14)]:
            tk.Label(header, text=text, bg=COL_HEADER, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"),
                     width=w, anchor="w").pack(side="left", padx=2, pady=6)

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 6))

        row_widgets = []

        # Gợi ý Nhóm: nhóm đã có sẵn trong dữ liệu + vài nhóm phổ biến mặc
        # định (Acc chính / Clone) để người dùng chọn nhanh thay vì phải gõ
        # tay ngay từ đầu - vẫn gõ tay được tên nhóm khác tuỳ ý (combobox
        # KHÔNG readonly).
        existing_groups = sorted({(a.get("nhom") or "").strip() for a in self.accounts if (a.get("nhom") or "").strip()})
        group_suggestions = ["Acc chính", "Clone"] + [g for g in existing_groups if g not in ("Acc chính", "Clone")]

        def _add_row(acc):
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=2)

            bat_var = tk.BooleanVar(value=bool(acc.get("bat", True)))
            DarkCheck(row, "", bat_var, bg=COL_PANEL_ALT, box_size=14).pack(side="left", padx=(6, 2), pady=4)

            ten_var = tk.StringVar(value=acc.get("ten_hien_thi", ""))
            tk.Entry(row, textvariable=ten_var, width=14, bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2, pady=4)

            user_var = tk.StringVar(value=acc.get("username", ""))
            tk.Entry(row, textvariable=user_var, width=14, bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2)

            pass_var = tk.StringVar(value=acc.get("password", ""))
            tk.Entry(row, textvariable=pass_var, width=14, show="•", bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2)

            nhom_var = tk.StringVar(value=acc.get("nhom", ""))
            ttk.Combobox(row, textvariable=nhom_var, values=group_suggestions, width=10).pack(side="left", padx=2)

            cur_label = label_by_index.get(acc.get("emulator_index"), "")
            emu_var = tk.StringVar(value=cur_label if cur_label in emu_options else (emu_options[0] if emu_options else ""))
            ttk.Combobox(row, textvariable=emu_var, values=emu_options, width=16, state="readonly").pack(side="left", padx=2)

            ghichu_var = tk.StringVar(value=acc.get("ghi_chu", ""))
            tk.Entry(row, textvariable=ghichu_var, width=12, bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2)

            tk.Label(row, text=acc.get("lan_chay_cuoi") or "-", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                     font=("Segoe UI", 8), width=14, anchor="w").pack(side="left", padx=2)

            rid = acc.get("id") or account_manager.new_account_id()
            rw = {
                "id": rid, "bat_var": bat_var, "ten_var": ten_var, "user_var": user_var,
                "pass_var": pass_var, "nhom_var": nhom_var, "emu_var": emu_var, "ghichu_var": ghichu_var,
                "lan_chay_cuoi": acc.get("lan_chay_cuoi"), "row": row,
            }

            def _delete(rid=rid, row=row):
                row.destroy()
                row_widgets[:] = [x for x in row_widgets if x["id"] != rid]

            RoundedButton(row, "🗑", command=_delete, bg=COL_RED, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 8, "bold"), padx=8, pady=2).pack(side="left", padx=4)

            row_widgets.append(rw)

        for acc in self.accounts:
            _add_row(acc)

        def _rebuild_filter_buttons():
            """Vẽ lại hàng nút lọc nhanh theo Nhóm - gọi lại sau khi Lưu Tất
            Cả để nhóm MỚI người dùng vừa gõ (chưa từng có trước đó) cũng
            xuất hiện thành nút lọc ngay, không cần đóng mở lại cửa sổ."""
            for w in filter_btns_frame.winfo_children():
                w.destroy()
            groups_now = sorted({(rw["nhom_var"].get() or "").strip() for rw in row_widgets if (rw["nhom_var"].get() or "").strip()})

            def _apply_filter(g):
                for rw in row_widgets:
                    match = (g is None) or ((rw["nhom_var"].get() or "").strip() == g)
                    if match:
                        rw["row"].pack(fill="x", pady=2)
                    else:
                        rw["row"].pack_forget()

            RoundedButton(filter_btns_frame, "Tất cả", command=lambda: _apply_filter(None),
                          bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"),
                          padx=8, pady=3).pack(side="left", padx=2)
            for g in groups_now:
                RoundedButton(filter_btns_frame, g, command=lambda g=g: _apply_filter(g),
                              bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"),
                              padx=8, pady=3).pack(side="left", padx=2)

        _rebuild_filter_buttons()

        btn_bar = tk.Frame(win, bg=COL_PANEL)
        btn_bar.pack(fill="x", padx=10, pady=8)

        RoundedButton(btn_bar, "➕ Thêm Tài Khoản", command=lambda: _add_row({}),
                      bg=COL_BLUE, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)

        def _save_all():
            new_entries = []
            for rw in row_widgets:
                label = rw["emu_var"].get()
                new_entries.append({
                    "id": rw["id"],
                    "ten_hien_thi": rw["ten_var"].get().strip(),
                    "username": rw["user_var"].get(),
                    "password": rw["pass_var"].get(),
                    "nhom": rw["nhom_var"].get().strip(),
                    "ghi_chu": rw["ghichu_var"].get(),
                    "emulator_index": emu_index_by_label.get(label),
                    "bat": bool(rw["bat_var"].get()),
                    "lan_chay_cuoi": rw.get("lan_chay_cuoi"),
                })
            account_manager.save_accounts(new_entries)
            self.accounts = new_entries
            self._log("info", f"Đã lưu {len(new_entries)} tài khoản vào accounts.json.")
            _rebuild_filter_buttons()
            messagebox.showinfo("Đã lưu", f"Đã lưu {len(new_entries)} tài khoản.", parent=win)

        RoundedButton(btn_bar, "💾 Lưu Tất Cả", command=_save_all,
                      bg=COL_GREEN, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)

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
        _bind_esc_close(win)

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
        _bind_esc_close(win)

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
        _bind_esc_close(win)

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
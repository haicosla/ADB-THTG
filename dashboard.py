"""
dashboard.py — ĐIỂM VÀO của LD Macro Studio (Auto Runner Dashboard).

File này giờ CHỈ còn giữ:
  - Khởi tạo state (__init__) và load/save cài đặt (dashboard_settings.json).
  - Khai báo class DashboardApp, GHÉP LẠI từ nhiều Mixin theo chức năng
    (mỗi Mixin nằm ở 1 file dashboard_*.py riêng) - cách tổ chức này
    KHÔNG đổi hành vi so với bản gộp 1 file duy nhất trước đây: mọi
    phương thức vẫn thuộc về CÙNG 1 class/instance DashboardApp, chỉ khác
    là được ĐỊNH NGHĨA rải ở nhiều file cho dễ tìm/sửa từng mảng:

        dashboard_theme.py      -> bảng màu (COL_*) + HELP_TEXT
        dashboard_widgets.py    -> RoundedButton/FlowBar/DarkCheck/CategorySection
        dashboard_ui.py         -> UIBuildMixin      (dựng khung giao diện)
        dashboard_emulators.py  -> EmulatorMixin     (quét/bật/tắt giả lập)
        dashboard_tasks.py      -> TaskMixin         (danh mục Hoạt Động)
        dashboard_run.py        -> RunMixin          (CHẠY tay/tạm dừng/hậu kỳ)
        dashboard_accounts.py   -> AccountsMixin     (Xoay Vòng Tài Khoản)
        dashboard_schedule.py   -> ScheduleMixin     (Hẹn Giờ Tự Động)
        dashboard_dialogs.py    -> DialogsMixin      (popup multi-select dùng chung)
        dashboard_progress.py   -> ProgressMixin     (tiến độ + Lỗi/Chưa Xong)
        dashboard_misc.py       -> MiscMixin         (popup, Hướng Dẫn, Cài Đặt Shop)
        dashboard_log.py        -> LogMixin          (Nhật Ký)

  MUỐN SỬA 1 TÍNH NĂNG CỤ THỂ? Mở đúng file dashboard_*.py tương ứng ở
  trên - KHÔNG cần lục cả 1 file 3000 dòng như trước. Muốn thêm 1 Mixin
  MỚI: viết file dashboard_xxx.py với `class XxxMixin:` chứa các def liên
  quan (dùng `self.` như bình thường), rồi thêm XxxMixin vào danh sách kế
  thừa của DashboardApp bên dưới.

  Việc SOẠN kịch bản mới (ghi F7, kéo-thả bước, chỉnh IF/ELSE, cắt ảnh
  mẫu...) vẫn nằm ở "LD Macro Studio" cũ (main.py + gui.py) - bấm nút
  "➕ TẠO HOẠT ĐỘNG" ở góc trên để mở chương trình đó dưới dạng CỬA SỔ RIÊNG
  (tiến trình con độc lập), không làm gián đoạn Dashboard đang chạy.

CHẠY CHƯƠNG TRÌNH NÀY: `python dashboard.py` (thay cho main.py khi dùng
hàng ngày; main.py vẫn giữ nguyên vai trò mở LD Macro Studio để tạo/sửa
kịch bản, và được chính Dashboard này gọi tới khi bấm "➕ Tạo Hoạt Động").
"""
import os
import json

# QUAN TRỌNG: Dashboard là 1 TIẾN TRÌNH RIÊNG với LD Macro Studio (main.py),
# có "if __name__ == '__main__'" của chính nó - bản vá os.chdir ở main.py
# KHÔNG áp dụng cho tiến trình này. Toàn bộ đường dẫn dùng trong Dashboard
# (accounts.json, task_registry.json, dashboard_settings.json, schedules.json,
# tasks/, groups/...) đều là đường dẫn TƯƠNG ĐỐI, phụ thuộc thư mục làm việc
# hiện tại lúc chạy - ép cwd về đúng thư mục chứa dashboard.py ngay từ đầu để
# không bị lệch dù chạy bằng shortcut/.bat có "Start in" khác, hay trên máy
# nào khác, giống hệt lý do đã sửa ở main.py.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk

from emulator_manager import EmulatorManager
from adb_helper import ADBHelper
import account_manager
import scheduler

from dashboard_theme import COL_BG
from dashboard_widgets import _set_dpi_awareness
from dashboard_ui import UIBuildMixin
from dashboard_emulators import EmulatorMixin
from dashboard_tasks import TaskMixin
from dashboard_run import RunMixin
from dashboard_accounts import AccountsMixin
from dashboard_schedule import ScheduleMixin
from dashboard_dialogs import DialogsMixin
from dashboard_progress import ProgressMixin
from dashboard_misc import MiscMixin
from dashboard_log import LogMixin

SETTINGS_PATH = "dashboard_settings.json"


# ============================= APP CHÍNH =============================
class DashboardApp(
    UIBuildMixin,
    EmulatorMixin,
    TaskMixin,
    RunMixin,
    AccountsMixin,
    ScheduleMixin,
    DialogsMixin,
    ProgressMixin,
    MiscMixin,
    LogMixin,
):
    """Ghép từ nhiều Mixin (xem docstring đầu file) - mọi hành vi/thứ tự
    khởi tạo giữ NGUYÊN như bản gộp 1 file trước đây."""

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
        self.schedules = self._migrate_schedules_gan_may_tk(scheduler.load_schedules())
        self._active_schedule_count = 0
        self._disabled_schedule_notified = {}  # {schedule_id: "YYYY-MM-DD"} - chống spam cảnh báo lịch đang TẮT
        # Các index giả lập đang bận (đang chạy tay HOẶC đang được 1 lịch hẹn
        # giờ dùng) - dùng để tránh chạy tay và lịch tự động cùng điều khiển
        # 1 giả lập cùng lúc (đá nhau/chạm chuột chồng chéo).
        self._busy_emulator_indexes = set()
        # HÀNG CHỜ theo từng giả lập: {emulator_index: [job, job, ...]} - khi
        # 1 lịch đến giờ chạy HOẶC người dùng bấm CHẠY (tay/xoay vòng/Chạy
        # Ngay) nhưng giả lập đang bận (đang chạy Hoạt Động khác/tài khoản
        # khác dở dang), job được XẾP VÀO ĐÂY thay vì bị bỏ qua/bỏ dở - ngay
        # khi giả lập đó rảnh (_after_emulator_freed), job đầu hàng chờ sẽ
        # tự được chạy tiếp. Mỗi job là 1 dict có khoá "kind":
        #   "schedule"        -> lượt lịch hẹn giờ (xem _trigger_schedule)
        #   "manual_run"      -> lượt CHẠY tay/Tự Login (xem _start_run)
        #   "manual_accounts" -> lượt CHẠY Xoay Vòng Tài Khoản (xem
        #                        _launch_run_with_accounts)
        self._emulator_job_queue = {}

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
            "shutdown_after": bool(self.shutdown_after_var.get()) if hasattr(self, "shutdown_after_var") else False,
            "shutdown_after_by_emulator": getattr(self, "_shutdown_after_by_emulator", {}) or {},
            "post_login_after": bool(self.post_login_after_var.get()) if hasattr(self, "post_login_after_var") else False,
            # TK riêng theo từng giả lập (mới) - "post_login_account_id" (cũ, dùng
            # chung 1 TK cho mọi giả lập) không còn được GHI nữa nhưng vẫn được ĐỌC
            # làm giá trị dự phòng ở _get_post_run_account() nếu 1 giả lập chưa có
            # TK riêng, để không mất cấu hình của người dùng bản cũ.
            "post_login_account_by_emulator": getattr(self, "_post_login_account_by_emulator", {}) or {},
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



if __name__ == "__main__":
    _set_dpi_awareness()
    root = tk.Tk()
    app = DashboardApp(root)
    root.mainloop()

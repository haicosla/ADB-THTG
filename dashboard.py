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
        dashboard_event.py      -> EventActionMixin  (🎁 Hành Động Sự Kiện - chạy nền suốt ngày)
        dashboard_accounts.py   -> AccountsMixin     (Xoay Vòng Tài Khoản)
        dashboard_schedule.py   -> ScheduleMixin     (Hẹn Giờ Tự Động)
        dashboard_groups.py     -> GroupsMixin       (📦 Nhóm Hành Động)
        dashboard_queue.py      -> QueueMixin        (⏳ Hàng Chờ: xem/xoá/đổi thứ tự job chờ giả lập)
        dashboard_ld_setup.py   -> LdSetupMixin      (🛠 Setup LDPlayer: chọn ldconsole, màn hình 1280x720, bật gỡ lỗi ADB)
        dashboard_dialogs.py    -> DialogsMixin      (popup multi-select dùng chung)
        dashboard_progress.py   -> ProgressMixin     (tiến độ + Lỗi/Chưa Xong)
        dashboard_misc.py       -> MiscMixin         (popup, Hướng Dẫn, Cài Đặt Shop)
        dashboard_telegram.py   -> TelegramMixin     (📨 Cài đặt thông báo Telegram - xem notifier.py)
        dashboard_shop.py       -> ShopQtyMixin      (🛍 Cài Đặt Shop: số lượng mua theo từng biến/shop)
        dashboard_log.py        -> LogMixin          (Nhật Ký)
        dashboard_popup_ctl.py  -> RunControlPopupMixin (🪟 Popup nhỏ Dừng/Tạm Dừng theo từng giả lập)

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
import threading
from datetime import datetime

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
from tkinter import messagebox
import auto_notify
auto_notify.install()  # thông báo tự tắt sau 5s + hộp thoại không chặn cửa sổ khác

from emulator_manager import EmulatorManager
from adb_helper import ADBHelper
import paths
import account_manager
import scheduler

from dashboard_theme import COL_BG
from dashboard_widgets import _set_dpi_awareness, apply_global_theme, install_themed_simpledialog
import window_geometry as wg
from dashboard_ui import UIBuildMixin
from dashboard_emulators import EmulatorMixin
from dashboard_ld_setup import LdSetupMixin
from dashboard_tasks import TaskMixin
from dashboard_run import RunMixin
from dashboard_event import EventActionMixin
from dashboard_accounts import AccountsMixin
from dashboard_schedule import ScheduleMixin
from dashboard_groups import GroupsMixin
from dashboard_queue import QueueMixin
from dashboard_dialogs import DialogsMixin
from dashboard_progress import ProgressMixin
from dashboard_misc import MiscMixin
from dashboard_telegram import TelegramMixin
from dashboard_shop import ShopQtyMixin
from dashboard_log import LogMixin
from dashboard_popup_ctl import RunControlPopupMixin

SETTINGS_PATH = paths.resolve_data_path("dashboard_settings.json")
# Gom các file .bak kiểu cũ (nằm lẫn cạnh file gốc) vào thư mục con backup/.
paths.migrate_legacy_bak_files()


# ============================= APP CHÍNH =============================
class DashboardApp(
    UIBuildMixin,
    EmulatorMixin,
    LdSetupMixin,
    TaskMixin,
    RunMixin,
    EventActionMixin,
    AccountsMixin,
    ScheduleMixin,
    GroupsMixin,
    QueueMixin,
    DialogsMixin,
    ProgressMixin,
    MiscMixin,
    TelegramMixin,
    ShopQtyMixin,
    LogMixin,
    RunControlPopupMixin,
):
    """Ghép từ nhiều Mixin (xem docstring đầu file) - mọi hành vi/thứ tự
    khởi tạo giữ NGUYÊN như bản gộp 1 file trước đây."""

    LOG_FILTER_ALL = "Tất cả giả lập (Tổng hợp)"

    def __init__(self, root):
        self.root = root
        self.root.title("LD Macro Studio - Auto Runner Dashboard")
        # Khôi phục lại đúng vị trí + kích thước cửa sổ đã tự co kéo/sắp
        # xếp lần trước TRÊN MÁY NÀY (xem window_geometry.py) - máy nào
        # chưa có gì lưu (lần đầu mở) thì dùng kích thước mặc định cũ.
        wg.restore_geometry(self.root, "dashboard_main", default="1320x880")
        self.root.minsize(1020, 640)
        self.root.configure(bg=COL_BG)
        # Đồng bộ theme tối 3D cho TOÀN BỘ cửa sổ/popup/ô nhập (xem
        # dashboard_widgets.py::apply_global_theme) - gọi 1 lần, TRƯỚC khi
        # dựng giao diện. Hộp thoại thông báo/xác nhận do auto_notify.py
        # đảm nhận (tự tắt sau 5s, không chặn cửa sổ khác) và cũng đã theo theme.
        apply_global_theme(self.root)
        install_themed_simpledialog()

        self._settings = self._load_settings()
        self.shop_settings = self._settings.get("shop_settings", {})
        # Thứ tự các MỤC (danh mục Hoạt Động) do người dùng tự sắp xếp ở
        # '🔀 Sắp Xếp Hành Động' (xem dashboard_tasks.py::_open_arrange_tasks_dialog) -
        # rỗng = chưa từng sắp xếp, dùng lại thứ tự bảng chữ cái mặc định cũ.
        self._muc_order_override = list(self._settings.get("task_muc_order") or [])

        self.adb = ADBHelper()
        self.emu_manager = EmulatorManager(self.adb)
        # Nếu người dùng đã từng tự chỉ đường dẫn ldconsole.exe thủ công (xem
        # choose_ldconsole_path) - áp dụng lại luôn, không cần tự dò lại mỗi
        # lần mở app (tự dò có thể thất bại nếu chưa có giả lập nào đang bật).
        custom_ldconsole = self._settings.get("ldconsole_path")
        if custom_ldconsole and os.path.exists(custom_ldconsole):
            self.emu_manager.set_console_path(custom_ldconsole)
        self.emulators = []
        self.emu_vars = {}
        self.emu_all_var = tk.BooleanVar(value=True)

        self.stop_flag = False
        self.pause_flag = False
        # Cờ DỪNG/TẠM DỪNG RIÊNG theo từng giả lập ({emulator_index: True/False})
        # - dùng khi người dùng chọn 1 giả lập cụ thể ở ô "Áp dụng cho" thay vì
        # "🌐 Tất cả giả lập". self.stop_flag/self.pause_flag ở trên vẫn giữ
        # nguyên vai trò cũ: khi bật, áp dụng cho TẤT CẢ giả lập đang chạy
        # (xem _is_stop_requested/_is_pause_requested ở dashboard_run.py).
        self.stop_flags = {}
        self.pause_flags = {}
        # ===== 🎁 HÀNH ĐỘNG SỰ KIỆN (dashboard_event.py) =====
        # Cờ Dừng/Tạm Dừng RIÊNG của Sự Kiện (theo emulator_index) - HOÀN
        # TOÀN ĐỘC LẬP với stop_flag(s)/pause_flag(s) ở trên: bấm Dừng/Tạm
        # Dừng ở thanh CHẠY chính KHÔNG ảnh hưởng Sự Kiện và ngược lại.
        self._event_stop_flags = {}
        self._event_pause_flags = {}
        # Các emulator_index ĐANG CÓ 1 luồng nền Sự Kiện chạy (đã bấm '▶ Bắt
        # Đầu Sự Kiện' và chưa Dừng hẳn) - xem start_event_action/_worker_event_action.
        self._event_active_indexes = set()
        # Các emulator_index ĐANG chạy 1 lượt Sự Kiện (đang giữ giả lập) - popup
        # "🪟 Điều Khiển Nhanh" (dashboard_popup_ctl.py) dùng để biết dòng nào điều khiển
        # bằng cờ RIÊNG của Sự Kiện.
        self._event_cycle_indexes = set()
        self.is_running = False
        self.active_threads = 0

        self.tasks = []
        self.task_vars = {}
        self.task_status_lbl = {}
        self.task_progress = {}

        self.log_entries = []
        self.log_filter_var = tk.StringVar(value=self.LOG_FILTER_ALL)
        # Trạng thái tác vụ ĐANG CHẠY theo từng giả lập (tên giả lập ->
        # dòng mô tả ngắn), hiển thị CỐ ĐỊNH ở thanh 'NHẬT KÝ THỰC THI
        # THỜI GIAN THỰC' (self.lbl_current_task trong dashboard_ui.py) -
        # khác với các dòng log thường (cuộn mất khi có dòng mới), dòng
        # này LUÔN đứng yên tại chỗ để biết ngay đang chạy gì mà không
        # phải nhìn/lọc qua Nhật Ký. Xem _set_current_task_status trong
        # dashboard_log.py.
        self._current_task_by_emulator = {}

        self._last_registry_mtime = None
        self._first_watch_tick = True

        # Thu thập cảnh báo "vừa phải tự khôi phục từ .bak vì file lỗi
        # định dạng" (xem paths.load_json_with_recovery) - hiển thị cho
        # người dùng biết NGAY khi mở app thay vì âm thầm im lặng làm mất
        # dữ liệu nếu chẳng may file cấu hình bị hỏng (mất điện, đầy ổ
        # đĩa, phần mềm đồng bộ khoá file nửa chừng...).
        _load_warnings = []
        self.accounts = account_manager.load_accounts(warnings_out=_load_warnings)

        # ================= HẸN GIỜ TỰ ĐỘNG =================
        self.schedules = self._migrate_schedules_gan_may_tk(
            scheduler.load_schedules(warnings_out=_load_warnings))
        self._active_schedule_count = 0
        self._active_quicklogin_count = 0
        # Mốc lúc MỞ APP + cờ "đã xử lý lần kiểm tra lịch đầu tiên chưa" - để
        # _check_schedules() phân biệt lịch đã BỎ LỠ lúc app đang tắt (hiện
        # bảng cho người dùng chọn chạy bù, xem dashboard_missed.py) với lịch
        # vừa tới giờ khi app đang mở (tự chạy như cũ).
        self._app_start_time = datetime.now()
        self._missed_startup_checked = False
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
        #   "run_group"       -> lượt ▶ Chạy Nhóm (xem _start_run_group)
        #   "quick_login"     -> ⚡ Log Nhanh / 🔑 Đăng Nhập 1 Acc (xem
        #                        _start_quick_login)
        # THÊM job bằng self._enqueue_job() (dashboard_queue.py). Xem/xoá/đổi
        # thứ tự job ở nút '⏳ Hàng Chờ'. Khoá dưới đây bảo vệ hàng chờ khi
        # luồng nền (_after_emulator_freed) và cửa sổ Hàng Chờ cùng sửa.
        self._queue_lock = threading.RLock()
        self._emulator_job_queue = {}

        self._build_ui()
        self.reload_tasks()
        self.refresh_emulators()

        # Nếu accounts.json/schedules.json (hoặc task_registry.json, xem
        # reload_tasks() ở dashboard_tasks.py) vừa phải tự khôi phục từ
        # .bak vì file lỗi định dạng lúc mở app - báo NGAY cho người dùng
        # (log + 1 hộp thoại), đừng để họ vô tình bấm Lưu 1 thứ gì đó rồi
        # ghi đè mất luôn phần dữ liệu chưa kịp khôi phục mà không biết.
        for w in _load_warnings:
            self._log("error", f"⚠️ {w}")
        if _load_warnings:
            self.root.after(300, lambda: messagebox.showwarning(
                "Phát hiện file cấu hình bị lỗi - đã tự khôi phục",
                "Có " + str(len(_load_warnings)) + " file cấu hình bị lỗi định dạng khi mở app, "
                "đã tự khôi phục từ bản sao lưu gần nhất (.bak).\n\n"
                "Xem chi tiết ở Nhật Ký (dòng ⚠️ màu đỏ) - NÊN kiểm tra lại Tài Khoản/Lịch Hẹn Giờ/"
                "Hoạt Động xem có thiếu thay đổi nào gần đây không trước khi bấm Lưu bất cứ gì.",
                parent=self.root))

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # Tự lưu lại vị trí/kích thước cửa sổ chính mỗi khi đóng app (đè
        # lên self.root.destroy - _on_close() ở dưới vẫn gọi bình thường,
        # manage_close=False vì _on_close đã tự xử lý nút X riêng).
        wg.autosave(self.root, "dashboard_main", manage_close=False)
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
        # 'data' ở đây là dict cấu hình sắp lưu, KHÔNG liên quan tới thư mục
        # data/ (paths.DATA_DIR) - trùng tên biến cục bộ thuần tuý.
        data = {
            "auto_login": bool(self.auto_login_var.get()) if hasattr(self, "auto_login_var") else False,
            # 'session' = 1 lần mỗi phiên, 'each' = trước mỗi hành động (xem _auto_login_mode()).
            "auto_login_mode": self._auto_login_mode() if hasattr(self, "auto_login_mode_var") else "session",
            "account_rotate": bool(self.account_rotate_var.get()) if hasattr(self, "account_rotate_var") else False,
            # Số giây chờ sau khi giả lập khởi động xong rồi mới chạy Tự Login (ô 'Chờ boot (s)').
            "boot_wait_seconds": self._get_boot_wait_seconds() if hasattr(self, "boot_wait_var") else 10,
            # "Hành Động Cuối": mỗi giả lập 1 CHUỖI BƯỚC có thứ tự (Hoạt
            # Động + Hành động hệ thống: Bật/Tắt giả lập, Đăng Xuất, Đăng
            # Nhập 1 TK bất kỳ) - xem _pick_post_run_actions()/
            # _apply_post_run_options() ở dashboard_run.py.
            "post_run_steps_by_emulator": getattr(self, "_post_run_steps_by_emulator", {}) or {},
            # 🎁 Hành Động Sự Kiện: chuỗi bước riêng theo từng giả lập (xem
            # _pick_event_actions()/self._event_action_steps_by_emulator ở
            # dashboard_event.py) + khoảng nghỉ giữa các lượt (phút, ô cạnh
            # nút '▶ Bắt Đầu Sự Kiện'). KHÔNG lưu trạng thái ĐANG CHẠY/ĐANG
            # TẠM DỪNG (_event_active_indexes/_event_pause_flags) - mở lại
            # app luôn coi như Sự Kiện đang TẮT, người dùng tự bấm lại
            # '▶ Bắt Đầu Sự Kiện' nếu muốn tiếp tục (tránh tự ý chạy nền
            # ngay khi vừa mở app mà người dùng không hay biết).
            "event_action_steps_by_emulator": getattr(self, "_event_action_steps_by_emulator", {}) or {},
            "event_interval_minutes": int(self.event_interval_var.get()) if hasattr(self, "event_interval_var")
                                       else 5,
            # Nghỉ RIÊNG từng giả lập của Sự Kiện (phút) - ƯU TIÊN hơn ô nghỉ chung.
            "event_interval_by_emulator": getattr(self, "_event_interval_by_emulator", {}) or {},
            "shop_settings": self.shop_settings,
            "ldconsole_path": getattr(self.emu_manager, "ldconsole_path", None),
            # Thứ tự Mục do người dùng tự sắp xếp (xem '🔀 Sắp Xếp Hành Động').
            "task_muc_order": getattr(self, "_muc_order_override", []) or [],
            # Watchdog (health_watchdog.py): ngưỡng phát hiện đứng hình/văng game/ANR, package game.
            # PHẢI ghi lại ở đây - hàm này dựng lại toàn bộ dict nên khoá lạ sẽ bị mất.
            "watchdog": self._watchdog_cfg() if hasattr(self, "_watchdog_cfg") else {},
        }
        try:
            paths.save_json(SETTINGS_PATH, data)
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

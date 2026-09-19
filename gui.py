"""
gui.py — ĐIỂM VÀO của giao diện "LD Macro Studio" (soạn kịch bản: ghi F7,
kéo-thả bước, chỉnh IF/ELSE, cắt ảnh mẫu, chạy thử...).

File này giờ CHỈ còn giữ:
  - Khởi tạo state (__init__), load/save vị trí cửa sổ, và đóng cửa sổ.
  - Khai báo class MacroStudioApp, GHÉP LẠI từ nhiều Mixin theo chức năng
    (mỗi Mixin nằm ở 1 file gui_*.py riêng) - CÁCH TỔ CHỨC NÀY GIỐNG HỆT
    dashboard.py + dashboard_*.py, KHÔNG đổi hành vi so với bản gộp 1 file
    3500+ dòng trước đây: mọi phương thức vẫn thuộc về CÙNG 1 class/
    instance MacroStudioApp, chỉ khác là được ĐỊNH NGHĨA rải ở nhiều file
    cho dễ tìm/sửa từng mảng:

        gui_dialogs.py       -> SetVarDialog/IncVarDialog/IfVarDialog/
                                 ZoomStepDialog (hộp thoại sửa biến/zoom)
        gui_dialogs_data.py  -> DataGroupManagerDialog/NextDataItemDialog/
                                 RegisterTaskDialog (hộp thoại dữ liệu/tác vụ)
        gui_ui_build.py      -> UIBuildMixin       (dựng khung giao diện)
        gui_step_edit.py     -> StepEditMixin      (sửa 1 bước đã có)
        gui_manual_steps.py  -> ManualStepsMixin   (thêm bước thủ công)
        gui_inspector.py     -> InspectorMixin     (panel xem chi tiết bước)
        gui_capture.py       -> CaptureMixin       (kết nối giả lập, chụp
                                                     màn hình, xem trực tiếp)
        gui_canvas.py        -> CanvasMixin        (kéo/lăn chuột trên
                                                     khung xem trước, F7)
        gui_steplist_ops.py  -> StepListOpsMixin   (thao tác toàn danh sách
                                                     bước, lưu/mở file)
        gui_run.py           -> RunMixin           (chạy thử / dừng / log)

  MUỐN SỬA 1 TÍNH NĂNG CỤ THỂ? Mở đúng file gui_*.py tương ứng ở trên -
  KHÔNG cần lục cả 1 file 3500 dòng như trước. Muốn thêm 1 Mixin MỚI: viết
  file gui_xxx.py với `class XxxMixin:` chứa các def liên quan (dùng
  `self.` như bình thường), rồi thêm XxxMixin vào danh sách kế thừa của
  MacroStudioApp bên dưới.

CHẠY CHƯƠNG TRÌNH NÀY: `python main.py` (main.py chỉ khởi tạo cửa sổ
Tkinter rồi gọi MacroStudioApp ở đây).
"""

import os
import glob
import json
import time
import re
import math
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import cv2
from PIL import Image, ImageTk, ImageDraw
from pynput import keyboard

from adb_helper import ADBHelper
from emulator_manager import EmulatorManager
from logic_engine import LogicEngine, BreakGroupSignal, ContinueGroupSignal
from window_finder import WindowFinder
from recorder import LiveRecorder, parse_key_combo_text
from step_list_controls import StepListController
import paths
import capture_tools
import task_registry
import data_groups

from gui_ui_build import UIBuildMixin
from gui_step_edit import StepEditMixin
from gui_manual_steps import ManualStepsMixin
from gui_inspector import InspectorMixin
from gui_capture import CaptureMixin
from gui_canvas import CanvasMixin
from gui_steplist_ops import StepListOpsMixin
from gui_run import RunMixin
from gui_image_test import ImageTestMixin


class MacroStudioApp(
    UIBuildMixin,
    StepEditMixin,
    ManualStepsMixin,
    InspectorMixin,
    CaptureMixin,
    CanvasMixin,
    StepListOpsMixin,
    RunMixin,
    ImageTestMixin,
):
    """Ghép từ nhiều Mixin (xem docstring đầu file) - mọi hành vi/thứ tự
    khởi tạo giữ NGUYÊN như bản gộp 1 file duy nhất trước đây."""

    def __init__(self, root):
        self.root = root
        self.root.title("LD Macro Studio - Modular Edition")
        
        self.config_path = paths.resolve_data_path("config.json")
        cfg = self._load_config()
        self.root.geometry(cfg.get("geometry", "1440x920"))

        self.adb = ADBHelper()
        self.window_finder = WindowFinder(self.adb)
        # LỖI ĐÃ TÌM RA: đổi giả lập ở ô "Thiết bị" chỉ đổi được lệnh ADB
        # (nên Preview đổi đúng) nhưng KHÔNG hề đổi cửa sổ đang gắn để ghi F7
        # - window_finder.find_ld_windows() quét MÙ, luôn bắt cửa sổ LDPlayer
        # ĐẦU TIÊN tìm thấy trên toàn hệ thống bất kể đang chọn giả lập nào,
        # nên khi mở NHIỀU giả lập cùng lúc, F7 luôn ghi vào ĐÚNG 1 giả lập
        # cố định (thường là giả lập mở đầu tiên) dù đã đổi ô chọn - đúng
        # như hiện tượng người dùng phát hiện ra ("tên giả lập bên cạnh
        # không đổi"). Nay dùng EmulatorManager (qua ldconsole list2) để biết
        # CHÍNH XÁC hwnd cửa sổ ứng với TỪNG serial ADB, rồi gọi
        # window_finder.attach_hwnd() thẳng vào đúng cửa sổ đó mỗi khi đổi
        # giả lập - không còn đoán mò nữa.
        self.emulator_manager = EmulatorManager(self.adb)
        self._device_hwnd_map = {}  # serial ADB -> EmulatorInfo (có .hwnd, .name)

        self.steps = []
        self.current_screen_cv = None
        # Đường dẫn file JSON đã Lưu/Nạp gần nhất - dùng cho nút "Đăng Ký Tác
        # Vụ" (cần biết tác vụ hiện tại tương ứng file nào trong tasks/).
        self.current_macro_path = None

        self.is_streaming_active = False
        self.frame_lock = threading.Lock()
        self.new_frame_ready = False

        self.is_recording_live = False
        self.recorder = LiveRecorder(
            coord_mapper=self.window_finder.win_coords_to_norm,
            on_step_captured=self._on_recorder_step_captured,
            focus_checker=self.window_finder.is_ld_focused
        )

        self.preview_action_mode = tk.StringVar(value="crop_and_tap")
        self.drag_start = None
        self.rect_id = None
        self.pending_action = None
        self._ocr_edit_idx = None
        self._region_edit_idx = None
        self._popup_pos_edit_idx = None
        # Dùng khi bấm ESC hủy quét NGAY LÚC THÊM bước mới (thay vì quét
        # khung ảnh/tọa độ ngay) -> vẫn chèn 1 bước RỖNG (chưa chọn ảnh/tọa
        # độ), rồi có thể bấm đúp/menu chuột phải vào bước đó để CHỌN SAU.
        # Khác với _ocr_edit_idx/_region_edit_idx (đang SỬA 1 bước ĐÃ CÓ sẵn)
        # ở chỗ: 3 biến dưới đây cũng dùng để SỬA bước đã có (đổi ảnh/tọa độ
        # bằng cách quét lại trên Preview), nhưng khi None nghĩa là đang TẠO
        # MỚI - bấm ESC lúc đó sẽ tạo bước rỗng thay vì không làm gì cả.
        self._image_edit_idx = None
        self._tap_edit_idx = None
        self._swipe_edit_idx = None
        self._zoom_edit_idx = None
        # Vùng quét/điểm chạm/đường vuốt/tâm zoom của BƯỚC ĐANG ĐƯỢC CHỌN
        # trong danh sách - hiển thị đè lên Preview (xem render_preview) để
        # dễ hình dung bước đó tác động ở đâu trên màn hình mà không cần mở
        # lại chế độ chọn vùng/tọa độ. Dạng: {"type": "region"|"point"|
        # "swipe"|"zoom", ...}
        # - "region": {"type": "region", "box": [x1,y1,x2,y2]} (tỉ lệ 0..1)
        # - "point":  {"type": "point", "pos": [x,y]} (tỉ lệ 0..1) - bước Tap
        # - "swipe":  {"type": "swipe", "from": [x,y], "to": [x,y]}
        # - "zoom":   {"type": "zoom", "center": [x,y], "start_radius": px,
        #              "end_radius": px, "angle": độ} - bước Zoom (Pinch)
        self._step_action_overlay = None

        self.preview_scale = 1.0
        self.preview_w = 400
        self.preview_h = 600
        # Zoom Preview: 1.0 = vừa khít khung (fit mặc định). Giữ Ctrl + lăn
        # chuột trên Preview để phóng to/nhỏ quanh đúng vị trí con trỏ, y
        # hệt Photoshop/trình duyệt. Xem on_canvas_ctrl_wheel(). KHÔNG liên
        # quan tới bước "zoom" (Pinch gửi vào giả lập) - đây chỉ là phóng to
        # ảnh xem trước trên máy tính, không gửi gì cho giả lập cả.
        self.preview_zoom = 1.0
        self.preview_zoom_min = 0.2
        self.preview_zoom_max = 6.0

        self.is_playing = False
        self.stop_flag = False
        # Danh sách bước ĐANG CHẠY thật sự (toàn bộ self.steps khi bấm
        # "CHẠY THỬ", hoặc chỉ các bước đang bôi đen khi bấm "Chạy Đã
        # Chọn") + hàm step_notifier gốc để khôi phục lại sau khi chạy
        # xong 1 lượt "Chạy Đã Chọn" (xem run_selected_steps()).
        self._active_run_steps = None
        self._default_step_notifier = None

        os.makedirs("templates", exist_ok=True)
        os.makedirs("tasks", exist_ok=True)
        os.makedirs("groups", exist_ok=True)
        os.makedirs("logs", exist_ok=True)

        self._setup_styles()
        self._build_ui()
        
        sash_pos = cfg.get("sash_pos", None)
        sash_pos_v = cfg.get("sash_pos_v", None)
        if sash_pos or sash_pos_v:
            self.root.after(200, lambda: self._restore_sash(sash_pos, sash_pos_v))
        else:
            self.root.after(400, self._apply_default_preview_width)

        self.root.update()

        min_w = max(1100, self.root.winfo_reqwidth())
        min_h = max(700, self.root.winfo_reqheight())
        self.root.minsize(min_w, min_h)

        self.refresh_all()

        self.step_list_ctrl = StepListController(
            tree=self.tree,
            get_steps=lambda: self.steps,
            on_changed=self._on_step_list_changed,
            on_edit_step=self.open_step_edit_menu_at
        )

        self.engine = LogicEngine(
            self.adb,
            stop_checker=lambda: self.stop_flag,
            step_notifier=lambda idx: self.root.after(0, lambda: self.tree.selection_set(str(idx))),
            popup_notifier=self._show_ingame_popup,
            logger=self._log_run
        )
        # Lưu lại notifier "mặc định" (đánh dấu đúng theo index trong TOÀN
        # BỘ self.steps) để có thể khôi phục sau khi "Chạy Đã Chọn" tạm đổi
        # sang notifier ánh xạ index-trong-tập-con -> index-thật (xem
        # run_selected_steps()).
        self._default_step_notifier = self.engine.step_notifier

        self.stream_thread = threading.Thread(target=self._stream_capture_worker, daemon=True)
        self.stream_thread.start()
        self._render_poll_loop()
        self._start_global_hotkeys()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_config(self):
        try:
            cfg = {
                "geometry": self.root.geometry(),
                "sash_pos": self.paned.sashpos(0),
                "sash_pos_v": self.vpaned.sashpos(0)
            }
            paths.save_json(self.config_path, cfg)
        except Exception:
            pass

    def _restore_sash(self, pos, pos_v=None):
        try:
            self.root.update_idletasks()
            if pos:
                self.paned.sashpos(0, int(pos))
            if pos_v:
                self.vpaned.sashpos(0, int(pos_v))
        except Exception:
            pass

    def on_close(self):
        self._save_config()
        self.root.destroy()


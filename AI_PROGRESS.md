# AI Progress

## Current Task (2026-09-24, đợt 13)

Yêu cầu người dùng: (1) bước hệ thống "Đăng Xuất"/"Đăng Nhập" (trong "🏁 Hành
Động Cuối" hoặc Hẹn Giờ) phải chạy `auto_login` ngay trước bước đó - trước đây
xếp "Bật giả lập" rồi "Đăng Xuất" liền nhau thì Đăng Xuất chạy khi chưa vào game
nên hỏng; (2) mỗi khi giả lập được KHỞI ĐỘNG (ở bất kỳ đâu, kể cả tắt rồi bật lại
giữa chuỗi bước) phải chờ boot xong hẳn (+ tuỳ chọn thời gian chờ) rồi chạy
`auto_login`; bình thường vẫn chạy `auto_login` trước khi chạy thao tác.

### Đã làm (đợt 13)

- `dashboard_run.py`: thêm `_get_boot_wait_seconds`, `_wait_after_boot_for_autologin`,
  `_autologin_after_boot`, `_autologin_before_step`. `_exec_entry` xoá cờ
  `_prev_sys_loai[emulator.index]` (bước liền trước là Đăng Xuất). `_worker_run_emulator`:
  vừa tự bật -> chờ boot-wait rồi vòng lặp sẵn có chạy auto_login.
- `dashboard_schedule.py` `_exec_system_action`: `dang_xuat` chạy auto_login trước;
  `dang_nhap` chạy auto_login trước, TRỪ khi ngay sau 1 bước Đăng Xuất (tránh vào lại
  game bằng TK cũ); `bat_gia_lap` dùng `find_by_index` mới, nếu THẬT SỰ vừa khởi động
  (`ensure_running` trả True) -> chờ boot-wait + auto_login, cập nhật hwnd/serial;
  `tat_gia_lap` chờ tắt hẳn (`wait_until_stopped`, tối đa 30s) để "tắt rồi bật" không
  bị coi là đã bật sẵn. `_worker_run_schedule`: vừa tự bật -> chờ boot-wait.
- `dashboard_emulators.py`: nút Bật giả lập chờ boot-wait trước Tự Login.
- `dashboard_accounts.py`: Xoay Vòng + Log Nhanh chờ boot-wait khi vừa tự bật.
- `emulator_manager.py`: thêm `wait_until_stopped()`.
- `dashboard_ui.py` + `dashboard.py`: ô "Chờ boot (s)" cạnh "Tự Login", lưu
  `boot_wait_seconds` (mặc định 10, 0-600) trong dashboard_settings.json.

### Lưu ý (đợt 13)

- Chỉ chờ boot-wait khi "Tự Login" đang bật.
- Chưa test trên Windows/LDPlayer thật (chỉ test giả lập bằng mock trên Linux).
- WindowFinder (chỉ dùng cho popup trong game) không tự gắn lại hwnd mới sau khi tắt-bật.

## Current Task (2026-09-21, đợt 12)

Yêu cầu người dùng: khi tắt Dashboard rồi bật lại, nó tự chạy bù các lịch hẹn
giờ đã bỏ lỡ. Thêm BẢNG liệt kê các lịch đã bỏ lỡ + tuỳ chọn chạy hay không
(nhiều lịch thì tick chọn lịch nào chạy, vẫn theo thứ tự); nếu chọn không chạy
thì đặt hết thành "vừa chạy xong".

### Đã làm (đợt 12)

- `scheduler.py`: thêm `last_due_time()` (mốc lưới giờ gần nhất đã qua),
  `next_due_time()` (mốc kế tiếp, chỉ để ghi log) và `missed_count()` (đã lỡ
  bao nhiêu mốc kể từ `lan_chay_luc`). KHÔNG đổi `is_due()`/`mark_triggered()`.
- `dashboard_missed.py` (FILE MỚI): `MissedSchedulesDialog` - bảng tối màu, mỗi
  dòng 1 lịch bị lỡ (tick chạy, tên, mốc bị lỡ + "cách đây", Hoạt Động theo thứ
  tự chạy, giả lập gán). Tick sẵn TẤT CẢ (giữ hành vi cũ nếu chỉ bấm Chạy).
  Nút: Tick/Bỏ tick tất cả, "Không chạy gì (coi như vừa chạy xong)", "Chạy N lịch
  đã tick". Nút X và ESC = "Không chạy". Chỉ lo giao diện, trả `result` (list
  chỉ số dòng tick theo thứ tự bảng / [] / None nếu cửa sổ bị huỷ khi app tắt).
- `dashboard.py`: thêm `self._app_start_time` (mốc mở app) và
  `self._missed_startup_checked` (+ `from datetime import datetime`).
- `dashboard_schedule.py`: `_check_schedules` - Ở LẦN KIỂM TRA ĐẦU TIÊN sau khi
  mở app, lịch đến hạn mà `last_due_time` < lúc mở app = "bỏ lỡ" -> KHÔNG tự
  chạy nữa mà đưa vào `_handle_missed_schedules`; lịch vừa tới giờ khi app đang
  mở (và mọi lần kiểm tra sau) chạy y như cũ. `_handle_missed_schedules`: sắp
  theo mốc lỡ (sớm chạy trước, bằng nhau theo thứ tự file), mở bảng chờ chọn,
  rồi `mark_triggered` cho TẤT CẢ lịch trong bảng + lưu TRƯỚC khi chạy, sau đó
  `_trigger_schedule` lần lượt các lịch được tick (giả lập bận vẫn tự xếp hàng
  chờ như mọi lượt lịch). Lịch không tick chỉ ghi log + đặt "vừa chạy xong".
  Bảng lỗi không mở được -> chạy bù TẤT CẢ như cũ; cửa sổ bị đóng do app tắt ->
  không đánh dấu gì (lần mở sau hỏi lại).
- `dashboard_theme.py` HELP_TEXT: thêm mục 7f giải thích bảng lịch bỏ lỡ.

### Kiểm tra (đợt 12)

- Dựng DashboardApp thật dưới Xvfb (stub win32*): tick 1 phần (chỉ lịch được tick
  chạy, đúng thứ tự, lịch bỏ tick được `lan_chay_luc` mới và không còn `is_due`);
  chạy tất cả; "Không chạy gì"; ESC; kiểm tra lần 2 không chạy/hỏi lại; lịch
  vừa tới giờ khi app mở (sau `_app_start_time`) vẫn tự chạy không qua bảng;
  không có lịch bỏ lỡ -> không mở bảng; bảng lỗi -> chạy bù tất cả; huỷ không
  chọn -> giữ nguyên. Bảng 8 dòng: cuộn, wrap, nút Chạy khoá khi 0 tick.

### Lưu ý / hạn chế

- Bảng chờ người dùng bấm: máy chạy không người trông (tự bật khi khởi động)
  sẽ KHÔNG tự chạy bù cho tới khi có người chọn (trước đây tự chạy hết). Muốn
  có thể thêm đếm ngược tự chạy sau N giây.
- Chỉ áp cho lịch bỏ lỡ LÚC MỞ APP; lịch trễ do máy ngủ/treo khi app vẫn mở vẫn
  tự chạy bù như cũ.
- Lịch lặp lại lỡ nhiều mốc vẫn chỉ chạy bù 1 lượt (như cũ) - bảng chỉ hiện số mốc lỡ.
- Chưa test trên Windows thật (chỉ Linux + Xvfb).

## Current Task (2026-09-21, đợt 11)

Yêu cầu người dùng: `dong_goi_dong_bo.py` thêm TUỲ CHỌN ĐỒNG BỘ GÌ (vd chỉ cần
đồng bộ Hoạt Động + Kịch bản, không cần đồng bộ Giờ Hẹn và Tài khoản).

### Đã làm (đợt 11)

- `dong_goi_dong_bo.py`: chia dữ liệu thành 7 NHÓM chọn được (`NHOM_DONG_BO`):
  `kich_ban` (tasks/*.json), `hoat_dong` (task_registry.json), `anh_mau`
  (templates/), `nhom_du_lieu` (data_groups.json), `tai_khoan` (accounts +
  account_groups + quick_login_groups), `lich_hen_gio` (schedules.json),
  `cai_dat_dashboard` (dashboard_settings.json). Map file: `DATA_FILES_BY_NHOM`.
- Chạy không tham số -> hộp thoại Tkinter (`HopThoaiChon`) tick chọn + 3 nút
  chọn nhanh (`PRESETS`: `day_du`, `hoat_dong_kich_ban`, `chi_kich_ban`). Không
  mở được Tkinter/không có màn hình -> tự chuyển sang menu chữ
  (`_hoi_chon_console`). Dòng lệnh không hỏi: `--chon a,b,c`, `--preset x`,
  `--console`, `--liet-ke`.
- `build_package(chon=None)`: `chon=None` = ĐÚNG hành vi cũ (`NHOM_MAC_DINH`).
  Giữ nguyên tên `PROJECT_ROOT/TASKS_DIR/TEMPLATES_DIR/DATA_DIR/OUTPUT_DIR/
  DATA_FILES_TO_INCLUDE/INCLUDE_DASHBOARD_SETTINGS/IMAGE_EXTS/SKIP_*/
  _iter_files/_build_readme` (`_build_readme` thêm 2 tham số cuối tuỳ chọn).
- Gói chọn một phần đặt tên `dong_bo_mot_phan_<ngày_giờ>.zip` (gói đầy đủ vẫn
  `dong_bo_<ngày_giờ>.zip`). README trong gói liệt kê nhóm đã/không đồng bộ.
- `_canh_bao_chon()` nhắc khi chọn tổ hợp dễ sai (Tuỳ chỉnh Hoạt Động không kèm
  Kịch bản; Kịch bản không kèm Ảnh mẫu; có Cài đặt Dashboard).

### Kiểm tra (đợt 11)

- Preset `day_du` cho danh sách file trong .zip GIỐNG HỆT bản cũ (so sánh trên
  dự án giả có .bak/__pycache__/file lạ/window_geometry/run_state).
- Từng preset và `--chon` tuỳ ý cho đúng file; nhóm sai/rỗng báo lỗi, exit 1.
- Hộp thoại dựng thật dưới Xvfb: preset, tick tay, bỏ hết -> cảnh báo không
  đóng, Huỷ -> None. Menu chữ và fallback khi không có DISPLAY chạy đúng.

### Lưu ý

- `data_groups.json` (Nhóm Dữ Liệu, bước "Lấy Dữ Liệu (Nhóm)") TRƯỚC ĐÂY chưa
  từng được đóng gói; nay có nhóm riêng nhưng để KHÔNG tick sẵn (giữ nguyên
  hành vi gói đầy đủ cũ). Kịch bản dùng bước đó nên tick kèm.
- Chưa test trên Windows thật (chỉ Linux + Xvfb).

## Current Task (2026-09-20, đợt 10)

Yêu cầu người dùng: thêm TUỲ CHỌN KIỂU QUÉT ẢNH ở MỌI chỗ tìm ảnh (kể cả 🧪 Test
Quét Ảnh), mỗi ảnh/bước chọn được 1 kiểu phù hợp, MẶC ĐỊNH vẫn là `_to_gray`
như cũ. Nguyên nhân gốc: `TM_CCOEFF_NORMED` trên ảnh xám bỏ qua độ sáng/tương
phản nên 2 ảnh cùng hình chỉ khác sáng/màu vẫn ra ~0.998 (log `.2f` làm tròn
thành "1.00").

### Đã làm (đợt 10)

- `adb_helper.py`: thêm `DEFAULT_MATCH_MODE`, `MATCH_MODES` (5 kiểu: `gray`
  mặc định = cách cũ, `color`, `gray_sqdiff`, `color_sqdiff`, `edge`),
  `normalize_match_mode`, `match_mode_label/short/from_label`,
  `_prep_for_mode`, `_match_map` (module-level). Điểm LUÔN "càng cao càng
  khớp" 0..1 (kiểu SQDIFF đảo thành 1 - sai_khác). `find_image_on_screen`,
  `find_any_image_on_screen`, `find_all_images_on_screen`,
  `find_all_matches_on_screen` thêm tham số CUỐI `mode=` (và `modes=` dict
  tên_ảnh->kiểu cho hàm nhiều ảnh) - KHÔNG đổi tên/thứ tự tham số cũ. Thêm
  `find_image_all_modes()` (1 lần chụp, điểm của mọi kiểu - cho Test Quét Ảnh).
- Dữ liệu bước: `step["match_mode"]` (str) + `step["template_modes"]`
  ({tên_file: kiểu}, chỉ bước nhiều ảnh). KHÔNG có field = "gray" => kịch bản
  cũ chạy y hệt. Chọn lại mặc định thì XOÁ key cho file JSON gọn.
- `logic_engine.py`: `_poll_single_template`/`_poll_any_template` thêm tham số
  cuối `mode`/`modes` (mặc định None); `check_condition` (if_image), `wait_image`,
  `wait_vanish`, `multi_image` (cả click_all) đều đọc và truyền kiểu quét.
- GUI: `gui_dialogs.MatchModeDialog` (kiểu chung + kiểu riêng từng ảnh);
  `gui_step_edit` nhánh `_edit_step_field(..., "match_mode")`, `_panel_match_mode`,
  và `_insert_step` áp kiểu đang chọn ở panel cho bước ảnh MỚI;
  `gui_ui_build` menu chuột phải "🧠 Sửa Kiểu Quét Ảnh" (kể cả wait_vanish),
  dòng riêng "🧠 Kiểu quét ảnh" dưới khung hàng loạt (hàng trên đã kín 1440px),
  cột Độ khớp rộng 100 và hiện nhãn kiểu khi khác mặc định (`*` = có ảnh dùng
  kiểu riêng); `gui_steplist_ops` áp hàng loạt ("Giữ nguyên" KHÔNG đụng kiểu
  đã đặt); `gui_image_test` thêm ô Kiểu quét + tick "So sánh điểm của MỌI kiểu",
  điểm log đổi `.2f` -> `.3f`.

### Kiểm tra (đợt 10)

- Kiểu mặc định so với bản cũ: 25 trial ngẫu nhiên x 8 phép gọi (4 hàm find_*,
  có/không region, mode=None/lạ) cho kết quả GIỐNG HỆT (repr bằng nhau).
- Ảnh thật icon_78x86_73490/73510 (cùng hình, khác sáng): gray 0.998, color
  0.993 (nhận nhầm) - gray_sqdiff 0.764, color_sqdiff 0.704, edge 0.488 (phân biệt).
- E2E qua LogicEngine (màn hình giả): wait_image/if_image/multi_image click_all/
  wait_vanish đều dùng đúng kiểu; click_all gray = 4 click (nhận nhầm), color_sqdiff = 3.
- GUI dựng thật dưới Xvfb: dialog, menu, cột conf, áp hàng loạt, cửa sổ Test.

### Lưu ý / hạn chế

- SQDIFF chuẩn hoá có thể vẫn cho điểm cao khi ảnh mẫu và nền cùng rất sáng;
  `edge` cần hạ Độ khớp (~0.6-0.75). Nên dùng 🧪 Test + "So sánh mọi kiểu" để chọn.
- Áp hàng loạt với kiểu cụ thể sẽ xoá `template_modes` của các bước nhiều ảnh.

## Current Task (2026-09-15, đợt 9)

Yêu cầu người dùng: "file dashboard đang dài quá, chia nhỏ ra để dễ chỉnh
sửa và quản lý" (dashboard.py đã tới 3020 dòng, 1 class DashboardApp với
~90 phương thức).

### Đã làm (đợt 9)

- CHỈ tổ chức lại code, KHÔNG đổi bất kỳ hành vi/logic nào (đã kiểm tra kỹ
  - xem bên dưới). Tách `dashboard.py` (3020 dòng) thành 12 file nhỏ hơn,
  dùng mô hình MIXIN (nhiều class kế thừa cùng lúc) để mọi phương thức vẫn
  thuộc về ĐÚNG 1 class/instance `DashboardApp` như trước - chỉ khác là
  ĐỊNH NGHĨA rải ở nhiều file:
    - `dashboard_theme.py`      - bảng màu COL_* + HELP_TEXT
    - `dashboard_widgets.py`    - RoundedButton/FlowBar/DarkCheck/
      CategorySection + `_set_dpi_awareness`/`_bind_esc_close`
    - `dashboard_ui.py`         - `UIBuildMixin` (dựng khung giao diện)
    - `dashboard_emulators.py`  - `EmulatorMixin` (quét/bật/tắt giả lập,
      Bảng Giả Lập, Chụp Thử)
    - `dashboard_tasks.py`      - `TaskMixin` (danh mục Hoạt Động, nút
      chức năng nhanh, Chọn Hành Động Để Chạy)
    - `dashboard_run.py`        - `RunMixin` (CHẠY tay/hàng chờ/tạm dừng/
      `_exec_entry`/2 tuỳ chọn hậu kỳ)
    - `dashboard_accounts.py`   - `AccountsMixin` (Xoay Vòng Tài Khoản,
      Quản Lý Tài Khoản)
    - `dashboard_schedule.py`   - `ScheduleMixin` (Hẹn Giờ Tự Động, Gán
      GL/TK)
    - `dashboard_dialogs.py`    - `DialogsMixin` (popup multi-select dùng
      chung giữa Task/Run/Schedule)
    - `dashboard_progress.py`   - `ProgressMixin` (tiến độ + Lỗi/Chưa
      Xong)
    - `dashboard_misc.py`       - `MiscMixin` (popup trong-game, Hướng
      Dẫn, Cài Đặt Shop, Reset Bộ Nhớ Task)
    - `dashboard_log.py`        - `LogMixin` (Nhật Ký)
  `dashboard.py` giờ chỉ còn ~185 dòng: docstring giải thích cách tổ chức
  mới, imports, `SETTINGS_PATH`, và `class DashboardApp(UIBuildMixin,
  EmulatorMixin, TaskMixin, RunMixin, AccountsMixin, ScheduleMixin,
  DialogsMixin, ProgressMixin, MiscMixin, LogMixin)` chứa `__init__` +
  `_load_settings`/`_save_settings`/`_on_close` + khối `if __name__`.
- QUY TRÌNH KIỂM TRA KHÔNG MẤT/ĐỔI CODE (làm bằng script, không gõ tay
  từng dòng để tránh sai sót khi di chuyển ~2550 dòng):
  1. Dò toàn bộ ranh giới `def` bằng `grep -n` để xác định chính xác từng
     phương thức bắt đầu ở dòng nào.
  2. Cắt file gốc thành các đoạn theo đúng ranh giới đó (script Python),
     kiểm chứng bằng cách cộng dồn số dòng của mọi đoạn = đúng số dòng gốc
     và mỗi dòng gốc (469-3014, toàn bộ thân class) xuất hiện ĐÚNG 1 LẦN
     duy nhất trong tổng các đoạn (không trùng, không thiếu).
  3. Đếm tên từng `def` ở gốc vs. tổng các file mới - khớp 100/100 (kể cả
     các `__init__` trùng tên của nhiều class khác nhau).
  4. So sánh nội dung ở mức "mỗi dòng code sau khi bỏ dòng trắng" giữa bản
     gốc và tổng các file mới - phần khác biệt DUY NHẤT là docstring đầu
     file, các dòng import được viết lại (gộp/tách `from tkinter import
     ...`), các dòng comment phân cách, và khai báo `class DashboardApp:`
     đổi thành `class DashboardApp(...Mixin...):` - không có dòng logic
     nào bị mất/đổi.
  5. `ast.parse` + `py_compile` toàn bộ 13 file - không lỗi cú pháp.
  6. Kiểm tra tĩnh (tự viết bằng `ast`) mọi tên được dùng (Name-Load) ở
     từng file đều được import/định nghĩa/là tham số hàm - phát hiện đủ
     import còn thiếu (vd `ADBHelper`, `WindowFinder`, `LogicEngine`,
     `datetime`, `run_state`, `scheduler`...) và đã thêm đủ vào từng file
     theo đúng nhu cầu thực tế của file đó (không import thừa tràn lan).
  7. Riêng bảng màu COL_*/HELP_TEXT: dùng `from dashboard_theme import *`
     ở các file cần nhiều màu (đây là theme module nội bộ, star-import ở
     đây chấp nhận được) - đã đối chiếu mọi `COL_*`/`HELP_TEXT` được dùng
     ở bất kỳ file nào đều có định nghĩa trong `dashboard_theme.py`.
- CHƯA thể `import` thật với `tkinter` để chạy GUI thử (môi trường code
  hiện tại không có `tkinter`/Windows/LDPlayer) - đã kiểm tra tĩnh kỹ như
  trên nhưng người dùng NÊN tự mở thử `python dashboard.py` trên máy thật
  trước khi dùng để chạy các tác vụ quan trọng, phòng trường hợp hiếm gặp
  ngoài phạm vi kiểm tra tĩnh (vd lỗi thứ tự khởi tạo MRO - dù đã xem qua
  và không thấy phương thức nào bị gọi đè lẫn nhau giữa các Mixin).

### Cần người dùng tự kiểm tra trên máy thật

- Mở `python dashboard.py`, xác nhận giao diện hiện lên y hệt trước đây
  (không thiếu nút/khung nào), thử qua các tính năng chính 1 lượt: CHẠY
  tay, Xoay Vòng Tài Khoản, Hẹn Giờ, Bảng Giả Lập, Hướng Dẫn, Nhật Ký.
- Nếu về sau cần SỬA 1 tính năng cụ thể, chỉ cần mở đúng file
  `dashboard_xxx.py` tương ứng (xem bảng trong docstring đầu
  `dashboard.py`) - không cần mở lại `dashboard.py` gốc nữa.

---

## Current Task (2026-09-14, đợt 8)

Theo yêu cầu người dùng (4 ý):
1. "Chạy ngay" (chạy tay/Chạy Ngay/Xoay Vòng Tài Khoản) cũng phải XẾP HÀNG
   CHỜ khi giả lập bận, giống lịch hẹn giờ (đợt 7 mới chỉ làm cho lịch hẹn
   giờ, chưa áp dụng cho các lượt CHẠY do người dùng bấm tay).
2. Danh sách lịch trong '⏰ Hẹn Giờ' sắp xếp theo THỜI GIAN CHẠY (giờ hẹn).
3. Nút 'Tự Login' (Hoạt Động 'auto_login') phải là 1 hành động RIÊNG (khác
   'account_login') để đưa giả lập vào game (script tự kiểm tra đã vào
   game chưa) - CHỈ SAU KHI thành công mới bắt đầu chạy kịch bản đã chọn
   (trước đây chạy nối tiếp vô điều kiện, không gate theo kết quả).
4. Thêm 2 tuỳ chọn HẬU KỲ: (a) tự TẮT GIẢ LẬP sau khi chạy xong, (b) tự
   ĐĂNG NHẬP vào 1 TÀI KHOẢN CHỈ ĐỊNH sau khi chạy xong.

### Đã làm (đợt 8)

- `dashboard.py`:
  - Đổi tên `self._emulator_schedule_queue` -> `self._emulator_job_queue`
    (dict `{emulator_index: [job, ...]}`), mỗi job có khoá `"kind"`:
    `"schedule"` (như đợt 7), `"manual_run"` (CHẠY tay/Chạy Ngay 1 tác vụ/
    Tự Login), `"manual_accounts"` (Xoay Vòng Tài Khoản).
  - Thêm `_split_busy_emulators()` (tách available/busy) và `_queue_job()`
    (đẩy 1 job vào hàng chờ + log rõ vị trí) dùng chung - thay thế hẳn
    `_filter_busy_emulators()` cũ (đã xoá, trước đây chỉ log cảnh báo rồi
    BỎ QUA giả lập bận).
  - `_start_run()`: giả lập bận -> `_queue_job(kind="manual_run")` thay vì
    bỏ qua; giả lập rảnh chạy như cũ.
  - `_start_run_with_accounts()` / `_launch_run_with_accounts()`: KHÔNG
    lọc bận trước khi mở popup gán Tài khoản nữa (vẫn cho gán Tài khoản
    cho MỌI giả lập đã tick kể cả đang bận) - tách available/busy SAU khi
    đã có `assignment`, giả lập bận -> `_queue_job(kind="manual_accounts")`
    kèm đúng `account_ids` đã gán cho giả lập đó.
  - `_trigger_schedule()`: đẩy job qua `_queue_job`/`_emulator_job_queue`
    chung (job `kind="schedule"`) thay vì hàng chờ riêng như đợt 7 - nhờ
    vậy "▶ Chạy Ngay" của 1 lịch (vốn gọi thẳng `_trigger_schedule`) TỰ
    ĐỘNG được xếp hàng chờ đúng như lịch tự động, không cần sửa thêm gì ở
    nút "▶ Chạy Ngay".
  - `_after_emulator_freed()`: đọc `kind` của job đầu hàng để dispatch đúng
    chỗ - `"schedule"` -> `_start_schedule_worker()` (như cũ); `"manual_run"`
    -> `_run_queued_manual_job()` (mới); `"manual_accounts"` ->
    `_run_queued_manual_accounts_job()` (mới). 2 hàm mới lấy lại
    `EmulatorInfo` MỚI NHẤT qua `emu_manager.find_by_index()` (phòng
    trường hợp giả lập vừa khởi động lại đổi hwnd/serial), rồi tăng
    `self.active_threads` + `task_progress[...]["total"]` THEO KIỂU CỘNG
    DỒN (không reset) qua `_begin_queue_replay_session()` - tránh phá vỡ
    đếm luồng/tiến độ của các giả lập khác đang chạy song song.
  - `scheduler.py`: thêm `sort_key(entry)` (khoá sắp xếp theo `gio_hen`
    tăng dần trong ngày). `_open_schedule_manager()` giờ hiển thị danh
    sách lịch theo `sorted(self.schedules, key=scheduler.sort_key)` thay
    vì đúng thứ tự lưu trong file - KHÔNG đổi thứ tự lưu trong
    `schedules.json`, chỉ đổi thứ tự HIỂN THỊ.
  - `_worker_run_emulator()` (lượt CHẠY tay thường, không xoay vòng): viết
    lại để dùng `_exec_entry()` thay vì code lặp riêng (giảm trùng lặp,
    đồng bộ với 2 worker kia). Nếu có `login_entry` ('Tự Login'): chạy
    TRƯỚC, lấy kết quả `ok_login` - THẤT BẠI (không vào được game) thì BỎ
    QUA hẳn các tác vụ đã chọn trên giả lập đó (log lỗi rõ ràng), KHÔNG
    còn chạy tiếp vô điều kiện như trước. Không gate trong trường hợp bấm
    DỪNG giữa chừng (kiểm tra `self.stop_flag` riêng để không log nhầm
    "thất bại" khi thực ra là do người dùng dừng).
  - Thêm `_apply_post_run_options(engine, emulator)`: áp dụng 2 tuỳ chọn
    HẬU KỲ mới sau khi 1 giả lập chạy xong hết việc của lượt hiện tại,
    dùng chung cho cả 3 worker (`_worker_run_emulator`,
    `_worker_run_emulator_with_accounts`, `_worker_run_schedule`) - BỎ
    QUA nếu `self.stop_flag` (đang dừng dở dang). Nếu bật CẢ 2 tuỳ chọn,
    ưu tiên TẮT GIẢ LẬP (log cảnh báo, bỏ qua đăng nhập).
  - Thêm `self.shutdown_after_var` (checkbox "🔌 Tắt Giả Lập Sau Khi Chạy
    Xong") và `self.post_login_after_var` (checkbox "🔑 Đăng Nhập TK Chỉ
    Định Sau Khi Chạy Xong") ở dòng `actions_bar2` mới (bên dưới dòng nút
    cũ, tránh chật). Thêm `_pick_post_login_account()` (popup chọn ĐÚNG 1
    Tài khoản, khác popup multi-select cũ) + `_get_post_run_account()` +
    `_post_login_account_label_text()`. Lưu `shutdown_after`,
    `post_login_after`, `post_login_account_id` vào `dashboard_settings.json`
    qua `_save_settings()` (đã có sẵn cơ chế persist từ trước) - tự nạp
    lại đúng lựa chọn cũ mỗi khi mở lại app.
  - `HELP_TEXT`: thêm mục 8 (Tự Login là hành động riêng, có gate theo kết
    quả), mục 9 (Chạy tay/Chạy Ngay cũng xếp hàng chờ), mục 10 (2 tuỳ chọn
    hậu kỳ mới).
- Đã `py_compile` + `ast.parse` cả `dashboard.py` + `scheduler.py` - không
  lỗi cú pháp. CHƯA test thật trên Windows/LDPlayer (môi trường code hiện
  tại không có Windows/LDPlayer).

### Cần người dùng tự kiểm tra trên máy thật

- Cho 2 giả lập CÙNG chạy 1 lượt tay dài, trong lúc đó bấm CHẠY thêm cho
  1 trong 2 giả lập đó (hoặc bấm "▶ Chạy Ngay" 1 lịch gán đúng giả lập
  đó) - xác nhận lượt mới XẾP HÀNG CHỜ (có log rõ) thay vì bị bỏ qua, và
  tự chạy tiếp đúng lúc giả lập đó rảnh, KHÔNG làm rối tiến độ (%) của
  giả lập kia đang chạy song song.
- Test 'Tự Login' với 1 `tasks/auto_login.json` cố tình cho THẤT BẠI (vd
  chờ 1 ảnh không tồn tại) - xác nhận các tác vụ đã tick trên giả lập đó
  bị BỎ QUA hẳn (không chạy nhầm khi màn hình chưa đúng), có log lỗi rõ.
  Sau đó test lại với `auto_login.json` chạy THÀNH CÔNG - xác nhận các
  tác vụ đã tick chạy bình thường như trước.
- Mở '⏰ Hẹn Giờ' với nhiều lịch có `gio_hen` khác nhau - xác nhận danh
  sách hiển thị đúng thứ tự giờ tăng dần.
- Bật '🔌 Tắt Giả Lập Sau Khi Chạy Xong', chạy xong 1 lượt - xác nhận giả
  lập tự tắt. Tắt tuỳ chọn đó, bật '🔑 Đăng Nhập TK Chỉ Định Sau Khi Chạy
  Xong', bấm '🎯 Chọn TK' chọn 1 tài khoản, chạy xong 1 lượt - xác nhận tự
  đăng nhập đúng tài khoản đã chọn (cần có sẵn Hoạt Động 'account_login').
  Bật cả 2 cùng lúc - xác nhận chỉ tắt giả lập, có log cảnh báo bỏ qua
  đăng nhập.
- Đóng/mở lại app - xác nhận 2 tuỳ chọn hậu kỳ + tài khoản đã chọn vẫn giữ
  nguyên (đọc từ `dashboard_settings.json`).

---

## Current Task (2026-09-13, đợt 7)

Báo lỗi: Hoạt Động A đang chạy dở trên 1 giả lập, tới giờ Hoạt Động B (1
lịch khác, hoặc cùng lịch tới kỳ lặp tiếp theo) cần chạy trên CÙNG giả lập
đó thì bị BỎ QUA LUÔN (chỉ ghi log cảnh báo rồi thôi) thay vì chờ A chạy
xong rồi chạy tiếp B.

### Đã làm (đợt 7)

- `dashboard.py`:
  - Thêm `self._emulator_schedule_queue` (dict `{emulator_index: [job, ...]}`)
    trong `__init__`.
  - `_trigger_schedule()`: khi giả lập đích đang có trong
    `_busy_emulator_indexes`, KHÔNG còn bỏ qua nữa - đẩy job (tên lịch +
    danh sách tài khoản + danh sách Hoạt Động) vào hàng chờ của đúng giả
    lập đó, log rõ "đã XẾP HÀNG CHỜ (vị trí N)".
  - Tách phần khởi chạy luồng ra hàm riêng `_start_schedule_worker(name,
    idx, accs, activities)` - dùng chung cho cả lượt chạy NGAY (giả lập
    đang rảnh) và lượt LẤY TỪ HÀNG CHỜ.
  - Thêm `_after_emulator_freed(emulator_index)`: gọi ngay khi 1 giả lập
    vừa hết bận (dù do chạy tay xong hay 1 lượt lịch chạy xong) - nếu hàng
    chờ của giả lập đó còn job, lấy job ĐẦU HÀNG ra chạy tiếp ngay lập tức
    (không cần đợi chu kỳ `_check_schedules()` 20s kế tiếp).
  - Gọi `_after_emulator_freed()` ở CẢ 2 nơi giải phóng "bận":
    `_on_emulator_thread_done()` (chạy tay/xoay vòng tài khoản xong) và
    `_on_schedule_thread_done()` (1 lượt lịch hẹn giờ xong).
  - Nút "▶ Chạy Ngay" (test thủ công 1 lịch) gọi thẳng `_trigger_schedule()`
    nên tự động thừa hưởng cơ chế hàng chờ này, không cần sửa riêng.
  - Cập nhật HELP_TEXT mục 7.e mô tả đúng hành vi mới (xếp hàng chờ thay vì
    bỏ qua).
  - **Lưu ý phạm vi sửa**: hàng chờ chỉ áp dụng cho LỊCH HẸN GIỜ khi gặp
    giả lập bận (dù bận do chạy tay hay do lịch khác). Nút CHẠY thủ công
    ('▶ CHẠY TẤT CẢ TÁC VỤ ĐANG CHỌN' / xoay vòng tài khoản) vẫn giữ hành
    vi CŨ (bỏ qua giả lập đang bận + cảnh báo, không tự xếp hàng) vì đó là
    hành động người dùng chủ động bấm ngay lúc đó, xếp hàng ngầm có thể gây
    hiểu nhầm "đã bấm mà không thấy chạy gì".
- Đã kiểm tra cú pháp (`py_compile`) - không lỗi. CHƯA test thật trên
  Windows/LDPlayer.

### Cần người dùng tự kiểm tra trên máy thật

- Đặt 2 lịch trên CÙNG 1 giả lập, giờ hẹn gần nhau (vd cách 2-3 phút, Hoạt
  Động A cố tình dài) - xác nhận lịch B bị "XẾP HÀNG CHỜ" (log), rồi tự
  chạy ngay khi A xong (không cần đợi tới chu kỳ 20s kế tiếp).
  Chờ nhiều Hoạt Động B, C cùng xếp hàng cho 1 giả lập - xác nhận chạy
  đúng thứ tự (FIFO) từng cái một, không chạy chồng lên nhau.
- Bấm DỪNG LẠI trong lúc có job đang nằm trong hàng chờ (chưa tới lượt
  chạy) - xác nhận job đó có bị bỏ dở giữa chừng đúng không, hay vẫn tự
  chạy sau đó (hiện tại: `_worker_run_schedule` tự kiểm tra `stop_flag`
  qua từng bước nên vẫn sẽ CHẠY nhưng dừng giữa chừng ngay khi
  `stop_flag` bật - nếu người dùng muốn hàng chờ cũng bị HUỶ HẲN khi bấm
  DỪNG thì cần báo lại để bổ sung).

---

## Current Task (2026-09-13, đợt 6)

Người dùng báo cáo 3 việc:
1. Hẹn Giờ đang THIẾU cách chọn thẳng Giả lập để chạy - lịch chỉ chạy được
   khi có gán Tài khoản (vì giả lập được suy ra từ `emulator_index` của
   tài khoản). Yêu cầu: nếu KHÔNG chọn Tài khoản nào thì chạy thẳng kịch
   bản trên giả lập đã chọn, không cần đổi tài khoản.
2. Thêm phân loại Nhóm tài khoản (vd "Clone", "Acc chính") để lọc/chọn
   nhanh.
3. Ở cửa sổ Hẹn Giờ, các nút (Hoạt Động/Tài khoản/Chạy Ngay/💾/🗑) nằm
   ngoài vùng nhìn thấy, phải kéo rộng cửa sổ mới thấy được.

### Đã làm (đợt 6)

- `scheduler.py`: KHÔNG đổi cấu trúc bắt buộc - lịch giờ có thêm field tuỳ
  chọn mới `may_ids` (list index giả lập chọn THẲNG cho lịch, độc lập với
  tài khoản). Không cần migrate vì field cũ dùng `.get(..., [])`.
- `dashboard.py`:
  - `_trigger_schedule`: tách 2 CHẾ ĐỘ rõ ràng - (a) CÓ `tai_khoan_ids`:
    xoay vòng như cũ (nhóm theo `emulator_index` của tài khoản); (b)
    KHÔNG có `tai_khoan_ids` nhưng CÓ `may_ids`: chạy thẳng trên đúng các
    giả lập đó, không đăng xuất/đăng nhập. Thiếu cả 2 -> log lỗi rõ ràng,
    bỏ qua lượt đó (trước đây bị "im lặng" nếu tài khoản rỗng vì vòng lặp
    for không chạy).
  - `_worker_run_schedule`: thêm nhánh `if not accounts:` chạy thẳng các
    Hoạt Động 1 lần trên giả lập (dùng đúng phiên đăng nhập sẵn có), y hệt
    kiểu fallback đã có sẵn ở `_worker_run_emulator_with_accounts`.
  - `_open_schedule_manager`: thêm nút chọn "🖥 GL (n)" (giả lập trực tiếp,
    dùng lại `_open_multi_select_dialog`), nhãn chế độ tự động (
    "→ xoay vòng tài khoản" / "→ chạy thẳng, không đổi tài khoản" /
    "→ chưa chọn..."). Sửa layout: mỗi dòng lịch tách thành 2 dòng con
    (line1: Bật/Tên/Giờ hẹn/Lặp lại/Chạy cuối; line2: 🎯 HĐ / 👤 TK / 🖥 GL
    + Chạy Ngay/💾/🗑) thay vì nhồi hết vào 1 dòng ngang - khắc phục lỗi
    phải kéo rộng cửa sổ mới thấy hết nút (line 2 tự đủ chỗ ở khổ cửa sổ
    bình thường, không phụ thuộc độ rộng cửa sổ). Cũng tăng kích thước cửa
    sổ mặc định lên 1150x620 (trước 1080x580) và thêm `minsize` để tránh
    thu quá nhỏ làm vỡ layout lần nữa.
  - `_open_multi_select_dialog`: thêm tham số tuỳ chọn `group_of` (dict
    item_id -> tên nhóm) - nếu có, hiện thêm hàng nút "chọn nhanh theo
    nhóm" phía trên danh sách checkbox (bấm 1 nút là tick hết các mục cùng
    nhóm). Dùng khi mở dialog chọn Tài khoản cho 1 lịch (group theo `nhom`
    của account_manager); không ảnh hưởng dialog chọn Hoạt Động (không
    truyền `group_of`).
  - `_open_account_manager`: thêm cột "Nhóm" (combobox gõ tự do, gợi ý sẵn
    "Acc chính"/"Clone" + các nhóm đã có), lưu vào field `nhom`. Thêm hàng
    "Lọc nhanh theo Nhóm" phía trên bảng - bấm 1 nút ẩn/hiện các dòng tài
    khoản theo đúng nhóm đó (ẩn bằng `pack_forget`, không xoá dữ liệu).
    Tăng kích thước cửa sổ mặc định lên 1060x560 (trước 920x520) + thêm
    `minsize` cho cùng lý do layout ở trên.
- `account_manager.py`: thêm field tài liệu hoá `"nhom"` (chuỗi tự do,
  mặc định rỗng, KHÔNG ảnh hưởng logic xoay vòng) vào docstring đầu file,
  và hàm tiện ích `list_groups(entries)`.
- Đã kiểm tra `py_compile` + `ast.parse` trên `dashboard.py`,
  `account_manager.py`, `scheduler.py` - không lỗi cú pháp. CHƯA test thật
  trên Windows/LDPlayer (môi trường code hiện tại không có Tkinter thật
  chạy giao diện lẫn LDPlayer) - cần người dùng tự mở app và xác nhận:
  1) 1 lịch không chọn Tài khoản, chỉ chọn Giả lập, chạy đúng giờ không
     đăng xuất/đăng nhập gì.
  2) Cột "Nhóm" gõ/lưu/tải lại đúng, nút lọc nhanh hoạt động, và nút
     "chọn nhanh theo nhóm" trong dialog chọn Tài khoản khi soạn lịch tick
     đúng các tài khoản cùng nhóm.
  3) Cửa sổ "Hẹn Giờ Tự Động" và "Quản Lý Tài Khoản" mở ra ở kích thước
     mặc định đã thấy đủ hết các nút mà không cần kéo giãn cửa sổ.

### Cần người dùng tự kiểm tra trên máy thật

- Test đầy đủ như 3 mục ở trên trên máy Windows thật với LDPlayer.
- Nếu màn hình nhỏ hơn 1150px chiều ngang, xác nhận cửa sổ Hẹn Giờ vẫn co
  giãn hợp lý nhờ `minsize` + layout 2 dòng (không còn phụ thuộc độ rộng
  cửa sổ như trước).

---

## Current Task (2026-09-13, đợt 5)

Người dùng báo cáo: lịch đang Bật, "▶ Chạy Ngay" chạy được, nhưng đến đúng
giờ hẹn thì Hoạt Động không tự chạy và KHÔNG có bất kỳ dòng log nào giải
thích. Kèm yêu cầu đổi ô "Lặp lại" từ số giờ thập phân sang định dạng hh:mm.

### Nguyên nhân (đợt 5)

`is_due()` (viết lại ở đợt 4) chỉ neo theo `gio_hen` (giờ hẹn) cho tới
TRƯỚC lần trigger đầu tiên. Ngay khi lịch trigger LẦN ĐẦU - kể cả chỉ do
bấm "▶ Chạy Ngay" để test - `lan_chay_luc` được ghi lại đúng giờ:phút bấm
nút đó, và mọi lần tính "đến giờ chưa" SAU ĐÓ chuyển hẳn sang công thức
`lan_chay_luc + interval_hours`, không còn dùng `gio_hen` nữa. Hậu quả:
bấm "Chạy Ngay" thử lúc 14:00 khiến lịch "hằng ngày lúc 07:00" âm thầm trôi
thành "hằng ngày lúc 14:00" mãi mãi - đúng 07:00 hôm sau `is_due()` trả về
False (chưa 24h kể từ 14:00 hôm trước) nên không chạy, không có gì để log
vì đơn giản là "chưa đến hạn" theo cách tính (sai) đó.

### Đã làm (đợt 5)

- `scheduler.py`:
  - Viết lại `is_due()`/`would_be_due_if_enabled()` theo **lưới giờ cố
    định** neo tại `gio_hen`, dùng mốc gốc cố định 2020-01-01 (không phụ
    thuộc ngày hôm nay hay lần trigger gần nhất) + bội số của
    `interval_hours` - nhờ vậy giờ hẹn hh:mm luôn được tôn trọng vĩnh viễn,
    kể cả sau khi bấm "▶ Chạy Ngay" test ở bất kỳ giờ nào. `lan_chay_luc`
    giờ CHỈ dùng để biết mốc lưới gần nhất đã xử lý hay chưa (chống trigger
    lặp lại nhiều lần cho cùng 1 mốc do Dashboard kiểm tra mỗi ~20s), không
    còn dùng để TÍNH mốc kế tiếp.
  - Thêm `hours_to_hhmm()` / `hhmm_to_hours()` để ô "Lặp lại" nhập/hiển thị
    theo định dạng hh:mm (vd `04:00` = mỗi 4 tiếng, `00:30` = mỗi 30 phút)
    thay vì số giờ thập phân (`4`, `0.5`) - `interval_hours` vẫn lưu nội bộ
    dạng giờ float như cũ (không vỡ `schedules.json` đã lưu). `describe()`
    cập nhật hiển thị theo hh:mm.
- `dashboard.py` (`_open_schedule_manager`): đổi nhãn cột "Lặp lại (giờ)"
  -> "Lặp lại (hh:mm)", ô nhập dùng `scheduler.hours_to_hhmm`/`hhmm_to_hours`
  để đọc/ghi, thông báo lỗi khi nhập sai định dạng cập nhật theo hh:mm.
- Đã viết test thủ công mô phỏng đúng kịch bản báo lỗi (Chạy Ngay lúc 14:00
  ngày 1, kiểm tra 07:00 ngày 2) - xác nhận `is_due()` mới trả về True đúng
  giờ hẹn, không còn bị trôi theo giờ Chạy Ngay. Đã `ast.parse` cả 2 file -
  không lỗi cú pháp. CHƯA test thật trên Windows/LDPlayer.

### Cần người dùng tự kiểm tra trên máy thật

- Mở lại app với `schedules.json` cũ - các lịch đã lưu trước đó (đợt 4) vẫn
  đọc được bình thường (không cần migrate gì thêm, chỉ đổi cách TÍNH đến
  hạn, không đổi định dạng file). Ô "Lặp lại" nay hiển thị hh:mm (vd lịch cũ
  `interval_hours: 24` sẽ hiện `24:00`) - bấm 💾 lại 1 lần để chắc chắn.
- Bấm "▶ Chạy Ngay" thử ở 1 giờ bất kỳ khác xa `gio_hen`, sau đó xác nhận
  lịch VẪN tự chạy đúng vào đúng `gio_hen` đã đặt ở lần kế tiếp (không bị
  trôi theo giờ vừa bấm Chạy Ngay như trước).
- Nhập thử ô "Lặp lại" sai định dạng (vd `4` thay vì `04:00`) - xác nhận có
  `messagebox` báo lỗi rõ ràng thay vì âm thầm nhận giá trị sai.

---

## Current Task (2026-09-13, đợt 4)

Sửa 4 vấn đề người dùng báo cáo về tính năng HẸN GIỜ TỰ ĐỘNG (đợt 3):
1. Popup "Chọn Hoạt Động" / "Chọn Tài Khoản" chọn không được / không có
   xác nhận.
2. Chưa chỉnh được giờ tuỳ chọn - chỉ cần "giờ hẹn" + "giờ lặp lại"
   (hằng ngày = 24h).
3. Thêm nút "Chạy Ngay" để test lịch mà không cần chờ tới giờ.
4. Các popup cần bấm ESC để tắt nhanh.

### Đã làm (đợt 4)

- `scheduler.py`: **Gộp mô hình lịch** - bỏ 2 loại "daily"/"interval"
  riêng biệt, thay bằng 2 trường duy nhất: `gio_hen` (hh:mm - mốc chạy LẦN
  ĐẦU) + `interval_hours` (lặp lại mỗi N giờ; hằng ngày = 24, mỗi 4 tiếng =
  4, có thể để số lẻ như 0.5 để test nhanh). `is_due()` viết lại theo mô
  hình mới: nếu chưa từng trigger thì so với mốc `gio_hen` hôm nay; nếu đã
  từng trigger thì so `now - lan_chay_luc >= interval_hours`. Thêm
  `_migrate_entry()` tự động chuyển các lịch đã lưu ở định dạng CŨ
  (`loai`/`gio`) sang định dạng mới ngay khi `load_schedules()` - lịch cũ
  không bị mất khi mở lại app với bản này. `describe()` cập nhật theo mô
  hình mới.
- `dashboard.py` (`_open_schedule_manager`):
  - Bảng lịch đổi cột "Loại" + "Giờ (hh:mm)" + "Mỗi (giờ)" thành 2 cột
    "Giờ hẹn (hh:mm)" + "Lặp lại (giờ)", có validate rõ ràng (báo lỗi bằng
    `messagebox` nếu nhập sai định dạng giờ hoặc số giờ lặp <= 0) thay vì
    âm thầm dùng giá trị mặc định như trước.
  - Thêm nút "▶ Chạy Ngay" ở mỗi dòng lịch: tự lưu lịch trước, kiểm tra đã
    chọn đủ Hoạt Động + Tài khoản chưa (báo rõ nếu thiếu), rồi gọi thẳng
    `mark_triggered()` + `_trigger_schedule()` để chạy thử ngay không cần
    chờ đến giờ hẹn - tiện để test mà không phải chỉnh giờ hệ thống.
  - `_open_multi_select_dialog` (popup chọn Hoạt Động / Tài khoản): thêm
    cuộn bằng con lăn chuột (`<MouseWheel>`) - trước đây chỉ kéo được
    thanh cuộn hẹp bên phải, khiến các mục nằm khuất bên dưới trông như
    "không chọn được". Thêm nhãn đếm "Đã chọn X/Y mục" cập nhật realtime
    khi tick, và sau khi bấm "💾 Lưu" hiện `messagebox` xác nhận đã chọn
    bao nhiêu mục (kèm nhắc bấm 💾 ở dòng lịch để lưu hẳn) - trước đây bấm
    Lưu xong đóng popup im lặng, không rõ đã ăn hay chưa.
  - Thêm hàm dùng chung `_bind_esc_close(win)`: gán phím ESC để đóng ngay
    1 cửa sổ Toplevel. Áp dụng cho TẤT CẢ popup cài đặt/chọn lựa: Chọn
    Hành Động Để Chạy, Hẹn Giờ Tự Động, popup Chọn Hoạt Động/Tài Khoản,
    Lỗi/Chưa Xong, Quản Lý Tài Khoản, Bảng Giả Lập, Hướng Dẫn, Cài Đặt Mua
    Shop. KHÔNG áp dụng cho overlay thông báo trong game (`_show_ingame_popup`)
    vì đó là cửa sổ `overrideredirect` đè lên giả lập, không phải dialog
    cài đặt.
- `gui.py`: thêm cùng hàm `_bind_esc_close()` và áp dụng cho 2 popup thật
  sự là dialog ("Quản Lý Ảnh Trong Nhóm", xem ảnh phóng to) - bỏ qua popup
  overlay trong game (giống dashboard.py, lý do tương tự).
- Đã kiểm tra cú pháp (`py_compile`) trên cả 3 file - không lỗi. CHƯA test
  thật trên Windows/LDPlayer.

### Cần người dùng tự kiểm tra trên máy thật

- Mở lại app với `schedules.json` cũ (định dạng "loai"/"gio") - xác nhận
  các lịch cũ vẫn hiện đúng tên/hoạt động/tài khoản và tự chuyển sang hiện
  "Giờ hẹn"/"Lặp lại (giờ)" hợp lý (lịch "daily" cũ -> lặp lại 24; lịch
  "interval" cũ giữ nguyên số giờ lặp).
  Bấm 💾 lại 1 lần cho từng lịch cũ để chốt định dạng mới vào file.
- Bấm "▶ Chạy Ngay" thử với 1 lịch đã chọn đủ Hoạt Động + Tài khoản, xác
  nhận chạy đúng luồng (đăng xuất - đăng nhập - chạy Hoạt Động) giống hệt
  khi tự động đến giờ, và giờ hẹn/lặp lại được tính lại từ mốc vừa chạy
  (không bị lịch tự trigger lại ngay lập tức ở lần kiểm tra 20s kế tiếp).
- Test popup Chọn Hoạt Động / Chọn Tài khoản với danh sách dài (nhiều hơn
  1 màn hình) - xác nhận cuộn được bằng con lăn chuột và tick chọn được
  mọi mục kể cả mục nằm khuất bên dưới.
- Bấm ESC ở từng popup xem có đóng đúng không (đặc biệt popup chọn nhiều -
  ESC sẽ đóng mà KHÔNG lưu lựa chọn, đúng ý nghĩa "huỷ/đóng nhanh").

---

## Current Task (2026-09-13, đợt 3)

Thêm tính năng HẸN GIỜ TỰ ĐỘNG theo yêu cầu người dùng: hẹn chạy 1 (hoặc
nhiều) Hoạt Động cho 1 nhóm Tài Khoản vào giờ cố định hằng ngày, hoặc lặp
lại mỗi N giờ - không cần bấm CHẠY thủ công. Ví dụ đúng use-case người
dùng nêu: "7h hằng ngày chạy HĐ A cho tài khoản 1,2,3", "mỗi 4 tiếng chạy
HĐ B cho tài khoản 4,5,6", "8h hằng ngày chạy A,B,C cho tài khoản 6,7,8" -
đều là 3 lịch riêng biệt, mỗi lịch có danh sách Hoạt Động + danh sách Tài
Khoản + kiểu lặp riêng.

### Đã làm (đợt 3)

- `scheduler.py` (MỚI): lưu/đọc `schedules.json` (danh sách lịch), mỗi lịch
  gồm `loai` ("daily" giờ cố định `gio` hh:mm, hoặc "interval" lặp mỗi
  `interval_hours` giờ), `hoat_dong_ids` (list id Hoạt Động), `tai_khoan_ids`
  (list id Tài Khoản), `bat` (bật/tắt lịch). `is_due(entry, now)` tính đã
  đến giờ chưa; `mark_triggered()` ghi lại NGAY KHI quyết định trigger
  (không chờ chạy xong) để tránh bị kích hoạt lặp lại nhiều lần trong lúc
  1 lượt chạy còn đang dở (có thể mất vài phút - vài chục phút).
- `dashboard.py`:
  - Nút "⏰ Hẹn Giờ" mở dialog `_open_schedule_manager()`: mỗi dòng = 1
    lịch, sửa tên/loại/giờ/số giờ trực tiếp, bấm "🎯 HĐ (n)" / "👤 TK (n)"
    mở popup checkbox multi-select (`_open_multi_select_dialog`) để chọn
    Hoạt Động / Tài khoản áp dụng, bấm 💾 lưu từng dòng, 🗑 xoá, "➕ Thêm
    Lịch Mới" thêm dòng trống.
  - `self.root.after(20000, self._check_schedules)` (đặt trong `__init__`,
    tự lặp lại) - mỗi 20s kiểm tra `scheduler.is_due()` cho từng lịch, nếu
    đến giờ thì `mark_triggered()` + lưu file NGAY rồi mới `_trigger_schedule()`.
  - `_trigger_schedule()`: nhóm các Tài khoản của lịch theo `emulator_index`
    được gán (xem account_manager.py) - mỗi giả lập 1 luồng riêng
    (`_worker_run_schedule`), y hệt cơ chế đa luồng của nút CHẠY thủ công.
    Bỏ qua (log warn) nếu giả lập đó ĐANG BẬN.
  - `_worker_run_schedule()`: `ensure_running()` (tự bật giả lập nếu tắt,
    tái dùng từ đợt 1) -> với từng tài khoản: Đăng Xuất (nếu có
    `account_logout`) -> Đăng Nhập (`account_login`, bơm `{tk_user}`/
    `{tk_pass}`) -> chạy đúng các Hoạt Động đã hẹn của lịch này (dùng lại
    `_exec_entry()` có sẵn, `tracked=False` vì không phải tick trong danh
    sách tác vụ chính) - logic giống hệt `_worker_run_emulator_with_accounts`
    nhưng scope theo TỪNG LỊCH thay vì "mọi tài khoản gán cho giả lập".
  - **Chống xung đột thủ công/lịch trên CÙNG 1 giả lập**: thêm
    `self._busy_emulator_indexes` (set index đang bận) - CHẠY THỦ CÔNG
    (`_start_run`/`_start_run_with_accounts`) giờ cũng đánh dấu bận/gỡ bận
    qua `_filter_busy_emulators()` (bỏ qua + log warn nếu giả lập đã bận do
    1 lịch đang chạy) và `_on_emulator_thread_done(emulator_index)`.
  - **Nút DỪNG / Tạm Dừng dùng chung cho cả lịch tự động**: thêm
    `_any_active_work()` (đang chạy tay HOẶC có lịch đang chạy nền) +
    `_refresh_run_control_buttons()` để bật/tắt 2 nút này đúng lúc kể cả
    khi việc đang chạy là do lịch tự kích hoạt (người dùng không bấm CHẠY).
    **Sửa 1 lỗi tiềm ẩn**: trước đây `stop_flag` chỉ được reset về False ở
    đầu `_start_run`/`_start_run_with_accounts` - nếu người dùng bấm DỪNG
    trong lúc CHỈ có lịch hẹn giờ đang chạy (không bấm CHẠY tay lần nào),
    `stop_flag` sẽ bị kẹt ở True mãi mãi và MỌI lịch sau đó sẽ tự thoát
    ngay lập tức mà không chạy gì (im lặng, khó phát hiện). Đã sửa:
    `_refresh_run_control_buttons()` tự reset `stop_flag`/`pause_flag` về
    False ngay khi không còn việc gì đang chạy (`_any_active_work()` ==
    False) - đảm bảo lượt lịch tiếp theo luôn bắt đầu "sạch".
  - Trạng thái (`_update_status_label`) hiển thị thêm số lịch đang chạy
    nền. HELP_TEXT thêm mục 7 hướng dẫn Hẹn Giờ.
- Đã kiểm tra cú pháp (`py_compile`) trên `dashboard.py` + `scheduler.py` -
  không lỗi. CHƯA test thật trên Windows/LDPlayer.

### Cần người dùng tự kiểm tra trên máy thật

- Đặt 1 lịch "Mỗi N giờ" nhỏ (vd 0.05 giờ ~ 3 phút) để xem có tự trigger
  đúng hạn không, và log ra đúng như mô tả.
- Đặt 2 lịch có tài khoản CÙNG gán 1 giả lập nhưng khác giờ chạy gần nhau,
  kiểm tra 1 lịch có bị bỏ qua đúng (do giả lập bận) và có log rõ ràng.
- Bấm DỪNG trong lúc 1 lịch đang chạy (không có phiên chạy tay nào), sau
  đó chờ lịch tiếp theo (hoặc lịch khác) tự trigger - xác nhận KHÔNG bị
  kẹt (đây là lỗi tiềm ẩn đã fix ở bản này, cần xác nhận lại trên máy
  thật vì môi trường code hiện tại không mô phỏng được đa luồng thật với
  Tkinter mainloop).
- Đóng/mở lại Dashboard giữa chừng: lịch "Hằng ngày" đã lỡ giờ trong lúc
  tắt app sẽ tự chạy ngay khi mở lại (vì `is_due()` chỉ so `lan_chay_ngay
  != hôm nay`, không quan tâm đã trễ bao lâu) - xác nhận đây là hành vi
  mong muốn (chạy bù) chứ không phải bug.

---



Theo yêu cầu người dùng:
1. Thêm nút "⏸ Tạm Dừng" khi đang chạy (bên cạnh nút DỪNG).
2. Dashboard trước đây chỉ quét được giả lập ĐANG CHẠY (dùng
   emu_manager.refresh()) - không nhận diện được giả lập đã tắt. Cần: (a)
   nút tự chọn đường dẫn ldconsole.exe thủ công, (b) quét đầy đủ danh sách
   giả lập kể cả đang tắt, (c) nút khởi động/tắt các giả lập đang được tick
   chọn.

### Đã làm (đợt 2)

- `dashboard.py`:
  - Thêm `self.pause_flag`, nút `self.btn_pause` ("⏸ Tạm Dừng" / "▶ Tiếp
    Tục") cạnh nút DỪNG, chỉ bật khi `is_running`.
  - `toggle_pause()` bật/tắt `pause_flag`. `_make_stop_checker()` trả về 1
    hàm `stop_checker` RIÊNG cho mỗi luồng giả lập: hàm này BUSY-WAIT (sleep
    0.15s) khi `pause_flag` đang bật (vẫn thoát ngay nếu `stop_flag` bật, để
    nút DỪNG luôn hoạt động kể cả đang tạm dừng), rồi trả về `stop_flag` như
    cũ. Tận dụng LUÔN các điểm gọi `stop_checker()` có sẵn trong
    `logic_engine.py` (giữa mỗi bước, trong vòng lặp chờ ảnh...) làm điểm
    tạm dừng -> **KHÔNG cần sửa gì trong `logic_engine.py`**, không đổi
    hành vi cũ khi không tạm dừng.
  - `_start_run()` / `_start_run_with_accounts()` reset `pause_flag=False`,
    bật nút Tạm Dừng; `stop_run()` và `_on_finish_all()` reset lại
    `pause_flag`/text nút.
  - `refresh_emulators()` đổi từ `emu_manager.refresh()` (chỉ thấy giả lập
    ĐANG CHẠY) sang `emu_manager.list_configured()` (thấy TẤT CẢ giả lập đã
    tạo trong LDPlayer, kể cả đang tắt - hàm này đã có sẵn từ đợt 1, dùng
    cho "Quản Lý Tài Khoản"). Giả lập đang tắt hiển thị mờ + nhãn "(đang
    tắt)", KHÔNG tự tick khi bấm "Tất cả giả lập" (tránh chạy nhầm ngay khi
    chưa bật) nhưng vẫn tick tay được để dùng với nút Bật Đã Chọn.
  - Thêm nút "📁 Chọn ldconsole.exe" (`choose_ldconsole_path`): mở hộp
    thoại chọn file, gán thẳng `self.emu_manager.ldconsole_path`, lưu vào
    `dashboard_settings.json` (key `ldconsole_path`) để không phải chọn lại
    mỗi lần mở app - áp dụng lại ở `__init__`.
  - Thêm nút "🟢 Bật Đã Chọn" / "🔴 Tắt Đã Chọn" (`launch_selected_emulators`
    / `quit_selected_emulators`): chạy trên thread nền, gọi
    `emu_manager.launch(index)` / `quit_emulator(index)` (đã có sẵn từ đợt
    1) cho từng giả lập ĐANG ĐƯỢC TICK, log kết quả, rồi tự `refresh_emulators()`
    lại sau 1.5s (giả lập vừa bật cần thêm 30-60s mới thấy "đang chạy" -
    người dùng cần tự bấm Quét Giả Lập lại sau khi Android boot xong, có
    ghi rõ trong log).
  - `emulator_manager.py`: KHÔNG cần sửa - `list_configured()`, `launch()`,
    `quit_emulator()`, thuộc tính public `ldconsole_path` đã có sẵn từ đợt
    1, chỉ cần gọi/gán từ dashboard.py.
- Đã kiểm tra cú pháp (`py_compile`) trên `dashboard.py` - không lỗi. CHƯA
  test thật trên Windows/LDPlayer (môi trường code hiện tại không có
  Windows/LDPlayer).

### Cần người dùng tự kiểm tra trên máy thật

- Tạm dừng/tiếp tục giữa 1 bước wait_image / swipe thật.
- Chọn tay đường dẫn ldconsole.exe khi máy không có sẵn giả lập nào đang
  bật (test trường hợp tự dò thất bại).
- Bật/Tắt giả lập qua nút mới, đối chiếu với `ldconsole.exe list2` xem
  index có đúng không sau khi bật lại.

---

## Current Task (đợt 1)

Thêm tính năng: tự nhận diện giả lập bật/tắt (tự khởi động nếu tắt) +
xoay vòng nhiều tài khoản trên cùng 1 giả lập (đăng xuất - đổi - đăng
nhập), theo yêu cầu người dùng ngày 2026-09-13.

## Completed

- Git repository initialized.
- `emulator_manager.py`: thêm `EmulatorInfo.running`, `list_configured()`
  (liệt kê TẤT CẢ giả lập kể cả đang tắt), `find_by_index()`, `launch()`,
  `quit_emulator()`, `reboot()`, `_boot_completed()`, `wait_until_ready()`,
  `ensure_running()` (tự kiểm tra bật/tắt, tự khởi động nếu tắt, chờ tới
  khi Android boot xong mới coi là sẵn sàng). Không đổi hành vi cũ của
  `refresh()`.
- `account_manager.py` (MỚI): quản lý `accounts.json` - danh sách tài
  khoản (username/password/ghi_chú), gán theo `emulator_index`, bật/tắt,
  `accounts_for_emulator()` để lấy hàng chờ xoay vòng của 1 giả lập.
- `dashboard.py`:
  - Nút "👥 Quản Lý Tài Khoản" (thêm/sửa/xoá tài khoản, gán giả lập, lưu
    vào accounts.json).
  - Tick "Xoay Vòng Tài Khoản" cạnh "Tự Login".
  - Khi bật tick này và bấm CHẠY: mỗi giả lập chạy trên 1 luồng riêng như
    cũ, nhưng qua `_worker_run_emulator_with_accounts()`: tự
    `ensure_running()` giả lập, rồi lặp qua từng tài khoản đã gán (đang
    bật): chạy Hoạt Động id `account_logout` (nếu có) -> `account_login`
    (bơm biến `{tk_user}`/`{tk_pass}`) -> các tác vụ đã tick -> tài khoản
    kế tiếp. Không có tài khoản nào gán cho giả lập -> fallback chạy 1 lần
    bình thường (không vỡ luồng chạy cũ).
  - Cập nhật HELP_TEXT (mục 6) hướng dẫn quy ước 2 Hoạt Động bắt buộc
    `account_login` / `account_logout`.
- Đã kiểm tra cú pháp (`py_compile`) và `pyflakes` trên cả 3 file - không
  lỗi. CHƯA kiểm thử thật trên Windows/LDPlayer thật (môi trường code hiện
  tại không có Windows/LDPlayer) - cần người dùng tự test lại trên máy
  thật, đặc biệt bước `ldconsole launch` + thời gian chờ boot.

## In Progress

- Chờ người dùng tự soạn 2 kịch bản `tasks/account_login.json` và
  `tasks/account_logout.json` (dùng {tk_user}/{tk_pass}) rồi test thực tế
  trên LDPlayer.

## Problems

- Chưa xác nhận được thời gian LDPlayer thật sự cần để khởi động xong
  (mặc định timeout 120s trong `ensure_running`) - có thể cần chỉnh tuỳ
  cấu hình máy.

## Next Steps

- Test `ldconsole launch/quit/reboot` thật trên máy Windows của người
  dùng, tinh chỉnh timeout nếu cần.
- Soạn `tasks/account_login.json` / `tasks/account_logout.json` mẫu.
- Cân nhắc thêm: chạy song song NHIỀU tài khoản trên NHIỀU giả lập khác
  nhau đã hoạt động sẵn (đã có qua chạy đa luồng theo giả lập) - nếu người
  dùng cần mở rộng thêm, có thể thêm bảng "gán nhóm giả lập" cho xoay vòng
  hàng loạt.
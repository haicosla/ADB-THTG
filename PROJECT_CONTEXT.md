# LDPlayer Auto Project

## Environment

- Windows
- Python 3.10
- LDPlayer 9

## Main LDPlayer path

H:/LDPlayer/LDPlayer9/ldconsole.exe

## Important rule

Do not remove existing functionality unless explicitly requested.

Không tự ý đổi tên biến/hàm/tham số đã có sẵn khi sửa code, để tránh làm lỗi các chỗ khác (kể cả ở file khác) đang gọi/phụ thuộc vào đúng tên cũ đó.

Read AI_PROGRESS.md before starting work.

Update AI_PROGRESS.md before finishing a task.

## File Map

### Dashboard (chạy hàng ngày - `python dashboard.py`)
- `dashboard.py` - Điểm vào: khởi tạo state, load/save settings, ghép class DashboardApp từ các Mixin bên dưới.
- `dashboard_theme.py` - Bảng màu (COL_*) và văn bản Hướng Dẫn (HELP_TEXT) dùng chung toàn Dashboard.
- `dashboard_widgets.py` - Các widget tự vẽ dùng chung (RoundedButton, FlowBar, DarkCheck, CategorySection).
- `dashboard_ui.py` - UIBuildMixin: dựng khung giao diện chính (toolbar, thanh giả lập, vùng task, log...).
- `dashboard_emulators.py` - EmulatorMixin: quét/bật/tắt giả lập, chọn ldconsole.exe, Bảng Giả Lập.
- `dashboard_tasks.py` - TaskMixin: nạp/hiển thị danh mục Hoạt Động, mở LD Macro Studio, Chọn Hành Động Để Chạy.
- `dashboard_run.py` - RunMixin: chạy tay đa luồng, hàng chờ, tạm dừng/dừng, `_exec_entry`, tuỳ chọn hậu kỳ.
- `dashboard_accounts.py` - AccountsMixin: Xoay Vòng Tài Khoản, cửa sổ Quản Lý Tài Khoản.
- `dashboard_schedule.py` - ScheduleMixin: Hẹn Giờ Tự Động, gán Giả Lập ↔ Tài Khoản.
- `dashboard_missed.py` - Bảng "Lịch Hẹn Giờ Đã Bỏ Lỡ" hiện khi mở lại Dashboard (chọn lịch nào chạy bù, lịch không chạy = đặt là vừa chạy xong); chỉ giao diện, logic nằm ở `_handle_missed_schedules` trong dashboard_schedule.py.
- `dashboard_dialogs.py` - DialogsMixin: popup chọn nhiều mục dùng chung (task picker, tài khoản...).
- `dashboard_progress.py` - ProgressMixin: theo dõi tiến độ chạy từng Hoạt Động, khung Lỗi/Chưa Xong.
- `dashboard_misc.py` - MiscMixin: popup trong-game, cửa sổ Hướng Dẫn, Cài Đặt Shop, Reset Bộ Nhớ Task.
- `dashboard_log.py` - LogMixin: ghi/lọc/xoá/sao chép Nhật Ký chạy.
- `run_state.py` - Bộ nhớ task nào đã chạy xong hôm nay, trên giả lập nào (phục vụ nút Reset Bộ Nhớ).
- `scheduler.py` - Dữ liệu + tính toán lịch chạy tự động (không lo phần thực thi).
- `account_manager.py` - Quản lý danh sách tài khoản dùng cho Xoay Vòng Tài Khoản.

### LD Macro Studio (mở khi cần tạo/sửa kịch bản - `python main.py`)
- `main.py` - Điểm vào: chỉ tạo cửa sổ Tkinter và chạy MacroStudioApp.
- `gui.py` - MacroStudioApp: toàn bộ giao diện soạn kịch bản (thêm/sửa bước, IF/ELSE/GROUP, xem trước...).
- `recorder.py` - Ghi lại thao tác chuột (tap/swipe) và bàn phím trực tiếp trên cửa sổ LDPlayer (F7).
- `step_list_controls.py` - Kéo-thả sắp xếp và Ctrl+C/X/V trên bảng danh sách bước.
- `capture_tools.py` - Cắt ảnh mẫu từ màn hình preview để dùng cho bước wait_image/if_image.

### Dùng chung (cả 2 chương trình đều import - sửa cần cẩn thận)
- `adb_helper.py` - Giao tiếp ADB: tap/swipe/gõ phím/chụp màn hình giả lập.
- `logic_engine.py` - Chạy kịch bản: IF/ELSE/GROUP/lặp, BreakGroupSignal/ContinueGroupSignal.
- `window_finder.py` - Tìm cửa sổ LDPlayer và quy đổi tọa độ chuột thật sang tọa độ chuẩn hoá.
- `emulator_manager.py` - Quản lý danh sách giả lập qua ldconsole.exe (bật/tắt/liệt kê).
- `task_registry.py` - Cầu nối định dạng dữ liệu Hoạt Động giữa LD Macro Studio và Dashboard.

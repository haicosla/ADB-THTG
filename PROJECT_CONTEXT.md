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

Chỉ đọc những file LIÊN QUAN đến yêu cầu/câu hỏi hiện tại, không đọc toàn bộ dự án: dùng mục "File Map" bên dưới để xác định file cần đọc (và file mà chúng import/gọi tới nếu cần), bỏ qua các file không liên quan. Với AI_PROGRESS.md (rất dài) chỉ cần đọc phần đầu file (các đợt gần nhất) và những đợt có nhắc tới file/chức năng đang sửa (tìm bằng grep theo tên file/hàm), không cần đọc hết từ đầu tới cuối.

Update AI_PROGRESS.md before finishing a task.

Quy tắc gửi kết quả sau khi sửa code (BẮT BUỘC, áp dụng cho mọi AI):
- KHÔNG gửi file code đầy đủ, KHÔNG nén zip, KHÔNG dán toàn bộ nội dung file vào câu trả lời, trừ khi người dùng yêu cầu rõ ràng (vd "gửi file X", "gửi zip").
- Chỉ trả lời bằng: (1)gửi file patch để dùng git + tên các file .py đã thay đổi, mỗi file kèm 1 dòng nói đã sửa gì; (2) các file .md đã cập nhật (AI_PROGRESS.md, và PROJECT_CONTEXT.md nếu có sửa).
- File không thay đổi thì không nhắc tới, không gửi.
- PATCH THEO THỨ TỰ (BẮT BUỘC): trong cùng 1 cuộc trò chuyện, người dùng áp dụng các patch lần lượt theo thứ tự đã gửi. Mỗi patch mới CHỈ chứa thay đổi so với bản code SAU patch gần nhất đã gửi, KHÔNG tính từ bản gốc trên repo và KHÔNG gộp lại các patch cũ (gộp lại sẽ báo "patch does not apply" vì người dùng đã áp dụng phần đó rồi). Chỉ tính từ bản gốc repo khi đây là patch đầu tiên của cuộc trò chuyện, hoặc khi người dùng nói rõ là chưa áp dụng patch nào / đã làm mới repo.
- Trước khi gửi patch phải tự kiểm tra: áp patch mới lên đúng bản code sau patch trước, phải ra đúng bản code cuối (`git apply --check`, rồi so file). Tên file patch đặt theo tính năng (vd `thtg_update.patch`), không ghi đè tên gây nhầm với patch cũ nếu nội dung khác.
- Với AI_PROGRESS.md và PROJECT_CONTEXT.md: file này rất dài và hay lệch dòng giữa các lần sửa, nên KHÔNG gửi patch cho 2 file này.Chỉ cần gửi thẳng file .md
- Nếu người dùng báo patch không áp dụng được: không gửi lại cả bản từ gốc. Hỏi hoặc tự xác định patch nào đã áp dụng, rồi gửi lại đúng phần còn thiếu.
- Nếu người dùng yêu cầu gửi file, chỉ gửi đúng file được yêu cầu, không gửi kèm file khác.

## File Map

> Tổng cộng 67 file `.py` + 3 file `.md` ở thư mục gốc. Dữ liệu người dùng (accounts, lịch, biến, nhóm...) nằm trong `data/*.json` (đường dẫn do `paths.py` quản lý), ảnh mẫu trong `templates/`, kịch bản trong `tasks/`, Nhóm Ngoài trong `groups/`, log trong `logs/`.
> Cách tách code: cả Dashboard và LD Macro Studio đều là 1 class ghép từ nhiều **Mixin** (mỗi Mixin 1 file) - `self.` trong mọi Mixin trỏ vào CÙNG 1 instance (`DashboardApp` / `MacroStudioApp`). Tìm tính năng theo tên file, đừng lục file khác.

### Tài liệu (.md)
- `PROJECT_CONTEXT.md` - File này: môi trường, quy tắc làm việc, File Map.
- `AI_PROGRESS.md` - Nhật ký từng đợt sửa (mới nhất ở ĐẦU file). Đọc phần đầu + grep theo tên file/hàm; cập nhật trước khi kết thúc task.
- `CHANGELOG_dot_nay.md` - Ghi chú thay đổi của 1 đợt sửa cũ (Hẹn Giờ nhiều mốc/ngày, hiển thị giả lập/tài khoản đang chạy...), chỉ tham khảo.

### Dashboard (chạy hàng ngày - `python dashboard.py`)
Class `DashboardApp` = `UIBuildMixin, EmulatorMixin, TaskMixin, RunMixin, EventActionMixin, AccountsMixin, ScheduleMixin, GroupsMixin, QueueMixin, DialogsMixin, ProgressMixin, MiscMixin, LogMixin, RunControlPopupMixin`.
- `dashboard.py` - Điểm vào: khởi tạo state, load/save settings, ghép class DashboardApp từ các Mixin bên dưới.
- `dashboard_theme.py` - Bảng màu (COL_*) và văn bản Hướng Dẫn (HELP_TEXT) dùng chung toàn Dashboard.
- `dashboard_widgets.py` - Widget tự vẽ dùng chung cho CẢ 2 chương trình: RoundedButton/Btn3D (nút 3D), FlowBar, DarkCheck, CategorySection, ToolGroup, Tooltip, ThemedToplevel (thay `tk.Toplevel`), `apply_global_theme()`, `install_themed_simpledialog()`.
- `dashboard_ui.py` - UIBuildMixin: dựng khung giao diện chính (toolbar theo nhóm, thanh giả lập, vùng task, thanh điều khiển, log...).
- `dashboard_emulators.py` - EmulatorMixin: quét/bật/tắt giả lập, chọn ldconsole.exe, Bảng Giả Lập.
- `dashboard_ld_setup.py` - LdSetupMixin: cửa sổ "🛠 Setup LDPlayer" cho máy mới - chọn/dò ldconsole.exe, đặt màn hình 1280x720 + bật Gỡ lỗi ADB cho các giả lập đã tick (logic ở `ld_setup.py`).
- `dashboard_tasks.py` - TaskMixin: nạp/hiển thị danh mục Hoạt Động, mở LD Macro Studio (`subprocess ... main.py`), Chọn Hành Động Để Chạy.
- `dashboard_run.py` - RunMixin: chạy tay đa luồng, hàng chờ, tạm dừng/dừng, `_exec_entry`, tuỳ chọn hậu kỳ (Hành Động Cuối), `_open_steps_editor`, `_start_run_group`.
- `dashboard_event.py` - EventActionMixin: "🎁 Hành Động Sự Kiện" - chuỗi bước soạn riêng theo giả lập (giống Hành Động Cuối), chạy LẶP LẠI SUỐT NGÀY, tự nhường ưu tiên ngay cho Chạy tay/Hẹn Giờ/Nhóm Hành Động rồi tự chạy tiếp khi rảnh; Dừng/Tạm Dừng riêng; có ô nghỉ chung + nghỉ RIÊNG từng giả lập (`event_interval_by_emulator`, riêng ưu tiên hơn chung).
- `dashboard_popup_ctl.py` - RunControlPopupMixin: popup nhỏ "🪟 Popup Dừng/Tạm Dừng" - mỗi giả lập đang bận 1 dòng (tên + Tạm dừng/Tiếp tục + Dừng), ô tích "📌 Luôn trên cùng"; dùng lại cờ `stop_flags`/`pause_flags` (dòng 🎁 Sự Kiện dùng `_event_*_flags`, nhận biết qua `_event_cycle_indexes`).
- `dashboard_accounts.py` - AccountsMixin: Xoay Vòng Tài Khoản, cửa sổ Quản Lý Tài Khoản, Log Nhanh/Đăng Nhập 1 Acc (`_start_quick_login`).
- `dashboard_schedule.py` - ScheduleMixin: Hẹn Giờ Tự Động (nhiều mốc/ngày), gán Giả Lập ↔ Tài Khoản, `_build_activity_steps` (bung Nhóm Hành Động thành bước), `_handle_missed_schedules`.
- `dashboard_groups.py` - GroupsMixin: "📦 Nhóm Hành Động" - cửa sổ tạo/đổi tên/xoá Nhóm, soạn chuỗi bước, bấm ▶ chạy thẳng Nhóm (dữ liệu ở `activity_groups.py`).
- `dashboard_queue.py` - QueueMixin: HÀNG CHỜ theo giả lập - `_enqueue_job()` (cách DUY NHẤT thêm job vào `_emulator_job_queue`, có khoá luồng `_queue_lock`), nút "⏳ Hàng Chờ (N)" + cửa sổ xem/xoá/đổi thứ tự job đang chờ, chạy job `quick_login` (⚡ Log Nhanh / 🔑 Đăng Nhập 1 Acc xếp hàng khi giả lập bận).
- `dashboard_missed.py` - Bảng "Lịch Hẹn Giờ Đã Bỏ Lỡ" hiện khi mở lại Dashboard (chọn lịch nào chạy bù, lịch không chạy = đặt là vừa chạy xong); chỉ giao diện, logic nằm ở `_handle_missed_schedules` trong dashboard_schedule.py.
- `dashboard_dialogs.py` - DialogsMixin: popup chọn nhiều mục dùng chung (task picker, tài khoản...).
- `dashboard_progress.py` - ProgressMixin: theo dõi tiến độ chạy từng Hoạt Động, khung Lỗi/Chưa Xong.
- `dashboard_misc.py` - MiscMixin: popup trong-game, cửa sổ Hướng Dẫn, Cài Đặt Shop, Quản Lý Biến (`_get_registry_preset_vars`, `_scan_variable_usage_by_task`), Reset Bộ Nhớ Task.
- `dashboard_telegram.py` - TelegramMixin: cửa sổ "📨 Telegram" (Bot Token/Chat ID, chọn loại sự kiện, Gửi thử); logic gửi nằm ở `notifier.py`.
- `dashboard_log.py` - LogMixin: ghi/lọc/xoá/sao chép Nhật Ký chạy (đồng thời ghi ra file qua `file_logger.py`).
- `run_state.py` - Bộ nhớ task nào đã chạy xong hôm nay, trên giả lập nào (phục vụ nút Reset Bộ Nhớ).
- `scheduler.py` - Dữ liệu + tính toán lịch chạy tự động (không lo phần thực thi).
- `account_manager.py` - Quản lý danh sách tài khoản dùng cho Xoay Vòng Tài Khoản.
- `activity_groups.py` - Dữ liệu "Nhóm Hành Động" (gói đặt tên gồm nhiều Hoạt Động/hành động hệ thống theo thứ tự, có thể lồng nhóm - chống lặp vòng); dùng bởi dashboard_groups.py, dashboard_schedule.py, dashboard_run.py.
- `variables_registry.py` - "🧩 Quản Lý Biến": danh sách biến dùng CHUNG cho mọi kịch bản (`variables.json`), Dashboard áp thẳng giá trị `default` mỗi lần chạy (ưu tiên hơn bước `input_var` trong kịch bản).

### LD Macro Studio (mở khi cần tạo/sửa kịch bản - `python main.py`)
Class `MacroStudioApp` (trong `gui.py`) ghép từ các Mixin `gui_*.py`.
- `main.py` - Điểm vào: chỉ tạo cửa sổ Tkinter và chạy MacroStudioApp.
- `gui.py` - MacroStudioApp: khởi tạo state, load/save vị trí cửa sổ, ghép các Mixin (bảng phân chia file ở docstring đầu file).
- `gui_ui_build.py` - UIBuildMixin: dựng khung giao diện (thanh trên, panel danh sách bước, xem trước màn hình, log/inspector, menu chuột phải trên danh sách bước, màu loại bước `STEP_BTN_COLORS`, `_setup_styles`).
- `gui_step_edit.py` - StepEditMixin: sửa 1 bước đã có (`_edit_step_field`: ghi chú, lặp, delay, vuốt...), quản lý ảnh mẫu nhóm IF/ELSE, hàm chung khi chèn bước mới.
- `gui_manual_steps.py` - ManualStepsMixin: các nút "Thêm Bước Thủ Công" (gõ chữ, tổ hợp phím, popup, IF/ELSE, GROUP, SET_VAR, INC_VAR, IF_VAR, Dữ Liệu Kế Tiếp, BREAK/CONTINUE, Sleep, chờ nhiều ảnh...); parse ô nhập Lặp (`_parse_repeat_input`) và Delay (`_parse_delay_input`, `_format_delay_display`).
- `gui_steplist_ops.py` - StepListOpsMixin: thao tác toàn danh sách bước (chọn hết, áp dụng cài đặt ảnh hàng loạt, gộp/tách Nhóm đã lưu, xoá/di chuyển, `refresh_tree`, LƯU/MỞ kịch bản .json, đăng ký vào Danh Mục Tác Vụ).
- `gui_inspector.py` - InspectorMixin: panel xem chi tiết 1 bước (ảnh mẫu thu nhỏ/phóng to, thống kê ảnh mẫu đang dùng), đổi preset kích thước, đổi ảnh mẫu của bước.
- `gui_capture.py` - CaptureMixin: kết nối giả lập LDPlayer, tìm cửa sổ, chụp màn hình 1 lần hoặc xem trực tiếp (stream), vẽ khung xem trước.
- `gui_canvas.py` - CanvasMixin: chuột trên khung xem trước (kéo chọn vùng chụp mẫu, zoom/pan), phím tắt toàn cục (F7 ghi thao tác), nút chèn nhanh IF/ELSE/chờ nhiều ảnh, `_do_crop`/`_do_crop_custom`.
- `gui_run.py` - RunMixin: "Chạy Thử"/"Chạy Đã Chọn"/"Dừng" ngay trong Studio, Nhật Ký chạy (`_log_run`), popup "trong game" xem trước, "🔍 Kiểm Tra Kịch Bản" (`validate_current_task`).
- `gui_image_test.py` - ImageTestMixin: cửa sổ "🧪 Test Quét Ảnh" - chẩn đoán nhanh 1 ảnh mẫu (chụp liên tục, ghi độ khớp) mà không cần thêm bước vào kịch bản.
- `gui_dialogs.py` - Hộp thoại độc lập (không phải Mixin): SetVarDialog, IncVarDialog, IfVarDialog, IfOcrDialog, ZoomStepDialog, SwipePathParamsDialog, MatchModeDialog, InputVarDialog + hàm parse quick-type.
- `gui_dialogs_data.py` - DataGroupManagerDialog (quản lý Nhóm Dữ Liệu), NextDataItemDialog (bước Dữ Liệu Kế Tiếp), RegisterTaskDialog (đăng ký kịch bản vào Danh Mục Tác Vụ).
- `gui_dialogs_ifgroup.py` - IfGroupDialog: trình xây CÂY điều kiện AND/OR/NOT lồng nhau cho bước `if_group` (chỉ xây cây, việc đánh giá nằm ở `logic_engine.py::_eval_condition_node`).
- `recorder.py` - Ghi lại thao tác chuột (tap/swipe) và bàn phím trực tiếp trên cửa sổ LDPlayer (F7).
- `step_list_controls.py` - Kéo-thả sắp xếp và Ctrl+C/X/V trên bảng danh sách bước.
- `template_replace.py` - Tìm & thay 1 ảnh mẫu ở nhiều nơi (tasks/ + groups/ + kịch bản đang mở): `find_usages`, `apply_replace`; dùng bởi `gui_inspector.py::_offer_replace_image_everywhere` (hỏi có đổi hàng loạt khi đổi/chụp lại ảnh của 1 bước).
- `capture_tools.py` - Cắt ảnh mẫu từ màn hình preview để dùng cho bước wait_image/if_image.
- `data_groups.py` - Dữ liệu "Nhóm Dữ Liệu" (danh sách text làm biến lặp, `data_groups.json`) cho bước `next_data_item`.
- `script_validator.py` - Quét cả kịch bản (đệ quy vào Nhóm Ngoài) tìm ảnh mẫu/file nhóm/nhãn bị thiếu TRƯỚC khi chạy; dùng cho nút "Kiểm Tra Kịch Bản".

### Dùng chung (cả 2 chương trình đều import - sửa cần cẩn thận)
- `adb_helper.py` - Giao tiếp ADB: tap/swipe/gõ phím/chụp màn hình giả lập, OCR, các hàm Siêu Tốc (turbo). Mọi lệnh adb có timeout; thất bại liên tiếp đặt cờ `ADBHelper.hung` (xem hằng số `HUNG_*`) để Dashboard tự khởi động lại giả lập treo (`dashboard_run.py::_recover_hung_emulator`).
- `logic_engine.py` - Chạy kịch bản: IF/ELSE/GROUP/lặp, nhãn + `goto_label` (Nhảy Tới Nhãn, GotoLabelSignal), BreakGroupSignal/ContinueGroupSignal, biến `{tên}` + biến random `{rand:a-b}` (`_interpolate_vars`), delay cố định/ngẫu nhiên (`_get_step_delay`, field `delay`/`delay_max`).
- `health_watchdog.py` - Luồng giám sát nền (do `dashboard_run.py::_exec_entry` tạo): phát hiện màn hình ĐỨNG IM / văng ra màn hình chính LDPlayer / hộp thoại ANR rồi đặt cờ `adb.hung` (+ `hung_kind`) để Dashboard tự mở lại game hoặc khởi động lại giả lập; cấu hình ở `dashboard_settings.json` -> `watchdog`.
- `turbo_engine.py` - Động cơ "Chế Độ Siêu Tốc" (chụp raw framebuffer + quét song song); chỉ chạy khi bước bật `turbo`, do `adb_helper.py`/`logic_engine.py` gọi.
- `merge2048_bot.py` - Bot auto-play game merge 2048 lưới 4x4 qua ADB (bước `auto_merge2048`, gọi từ `logic_engine.py`; `max_moves: 0` = chỉ chụp/phân tích, lưu ảnh vào `debug_merge2048/`).
- `thtg_bot.py` - Bot auto "Thất Thánh - Phàn Đầu" (lưới 7x7, nối thú cùng loại 8 hướng, diệt quái to) qua ADB, bước `auto_thtg` (gọi từ `logic_engine.py`): nhận diện bàn cờ bằng màu + template (`templates/thtg_*.png`), bộ giải đường đi mỗi lượt (chính xác `thtg_solver.py` + beam search), bấm từng ô; điểm gồm diệt quái > số bước > thưởng kim cương mỗi 10 bước (kim cương dùng bị trừ điểm) và phạt bước cuối vào góc/mép/chỗ lượt sau bị kẹt (`_EndEval`); đọc "Hiệp còn lại" (`read_turns_left`, khớp mẫu `templates/thtg_turns_<số>.png`, lưu bằng `--add-turns-template`) - còn 1 hiệp thì bỏ thưởng kim cương/phạt vị trí cuối, chỉ lo diệt quái; đọc số bước ở nút Chiến để kiểm tra đã nối đủ ô (`verify_steps`); `test: true` = chỉ tính không bấm; `python thtg_bot.py anh.png` để kiểm nhận diện + đường đi.
- `thtg_solver.py` - Bộ giải CHÍNH XÁC (nhánh-cận, không import tkinter/thtg_bot) cho 1 lượt của `thtg_bot.py`: `solve_exact(grid, hero, w_step, w_diamond, count_step_first, node_limit, seed_path, seed_score, w_reward, reward_every, end_fn)`; dừng theo SỐ NÚT nên kết quả xác định. `solve()` trong `thtg_bot.py` gọi nó trước rồi mới tới beam (lỗi ở đây bị `except Exception` nuốt -> lặng lẽ chỉ còn beam, nên test bằng cách chạy riêng).
- `photo_bot.py` - Bot auto "Chụp Ảnh" (tiệm ảnh) qua ADB, bước `auto_photo` (gọi từ `logic_engine.py`): đọc vùng vàng/vạch trên thanh đo từ pixel, bấm thử từng Nền/Trang Trí để đo điểm rồi chọn tổ hợp vào vùng vàng và bấm "Chụp ảnh"; `shoot: false` = chế độ TEST; ghi `photo_scores_log.jsonl`; `python photo_bot.py anh.png` để kiểm nhận diện.
- `window_finder.py` - Tìm cửa sổ LDPlayer và quy đổi tọa độ chuột thật sang tọa độ chuẩn hoá.
- `window_geometry.py` - Tự lưu/khôi phục vị trí + kích thước mọi cửa sổ Tkinter theo từng máy (`data/window_geometry.json`, không nên đồng bộ giữa các máy).
- `wheel_scroll.py` - Lăn chuột giữa cho MỌI cửa sổ/popup: `install_wheel_scroll(root)` (gọi trong `apply_global_theme`) bind ở mức lớp widget, tự cuộn Canvas/Listbox/Text/Treeview gần nhất dưới con trỏ; cửa sổ mới có Canvas+Scrollbar KHÔNG cần tự bind `<MouseWheel>` nữa (đừng dùng `bind_all/unbind_all` cho lăn chuột - sẽ đè nhau).
- `popup_widget.py` - Vẽ popup thông báo nổi (topmost) đè lên cửa sổ LDPlayer, dùng chung cho Dashboard và "Chạy Thử" của Studio.
- `auto_notify.py` - Thay hộp thoại `messagebox`/`simpledialog` mặc định: thông báo TỰ TẮT sau 5s và không chặn, câu hỏi không grab; giao diện theme tối 3D.
- `notifier.py` - Thông báo Telegram ra NGOÀI máy (chỉ urllib): `notify(event, text, key, photo_jpeg)` chạy nền, có timeout, chống ngập chat, KHÔNG BAO GIỜ ném lỗi. Cấu hình ở `data/telegram_config.json` (chứa token - nằm trong `.gitignore`).
- `session_report.py` - Gom kết quả TỪNG lượt chạy Hoạt Động (giả lập, tài khoản, giờ bắt đầu/xong, trạng thái) trong `REPORT` rồi dựng tin Telegram "🏁 Xong toàn bộ phiên" (`format_report`); không import tkinter. `_exec_entry` ghi (`REPORT.add`), `_on_emulator_thread_done` đóng (`close`), Hẹn Giờ/Log Nhanh bỏ (`discard`), `_on_finish_all` gửi (`drain`).
- `ld_setup.py` - Ghi cấu hình LDPlayer cho máy mới (không import tkinter): `ldconsole modify --resolution` + khoá `basicSettings.adbDebug` trong `vms/config/leidianN.config`; chỉ áp dụng khi giả lập đang tắt.
- `emulator_manager.py` - Quản lý danh sách giả lập qua ldconsole.exe (bật/tắt/liệt kê).
- `safe_calc.py` - Tính biểu thức số học an toàn (+ - * / ( ), không dùng eval) cho ô số có biến, vd Sửa Lặp = `{sach}-1`; engine và giao diện soạn kịch bản cùng dùng.
- `task_registry.py` - Cầu nối định dạng dữ liệu Hoạt Động giữa LD Macro Studio và Dashboard.
- `paths.py` - Đường dẫn/lưu file dùng chung: `resolve_data_path()` (gom file cấu hình vào `data/`, tự di chuyển file cũ), `save_json()` (sao lưu `.bak` vào thư mục con `backup/` cạnh file gốc + ghi tạm rồi đổi tên), `load_json_with_recovery()` (tự khôi phục từ `backup/*.bak`), `bak_path_for()`, `migrate_legacy_bak_files()` (gom `.bak` kiểu cũ lúc khởi động).
- `file_logger.py` - Ghi Nhật Ký ra file `logs/YYYY-MM-DD.log` (flush từng dòng, an toàn đa luồng); dùng bởi `gui_run.py` và `dashboard_log.py`.

### Công cụ phụ (chạy riêng, không nằm trong luồng Dashboard/Studio)
- `dong_goi_dong_bo.py` - Đóng gói Hoạt Động (`tasks/`), Nhóm Ngoài (`groups/`), ảnh mẫu (`templates/`), cấu hình (`data/*.json`) thành 1 file .zip để đồng bộ sang máy khác; có hộp thoại tick chọn nhóm cần đồng bộ (nhóm không chọn thì máy kia giữ nguyên dữ liệu).
- `build_portable.py` - Dựng bản PORTABLE (mang theo Python + thư viện, chạy được trên máy chưa cài Python; cố ý KHÔNG dùng PyInstaller vì `dashboard_tasks.py` mở Studio bằng `sys.executable main.py`). `python build_portable.py [--zip]`.
- `patch_tool.py` - "Quick Patch Manager" (Tkinter): chọn thư mục mã nguồn + file patch để áp dụng bản vá nhanh.
- `turbo_selftest.py` - Đo thực tế tốc độ Chế Độ Siêu Tốc trên máy (PNG vs RAW, 1/2/3 luồng, thử tap sendevent); chỉ đọc/đo, không sửa gì.

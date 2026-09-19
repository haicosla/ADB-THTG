# Đã làm (đợt 2 - xong toàn bộ 9/9 file JSON cấu hình)

- `run_state.py` (`run_state_today.json`), `data_groups.py`
  (`data_groups.json`), `scheduler.py` (`schedules.json`), `dashboard.py`
  (`dashboard_settings.json`), `gui.py` (`config.json`) — cả 5 file còn
  lại giờ đều dùng `paths.resolve_data_path()` để lưu vào `data/` và
  `paths.save_json()` (có `.bak` + ghi nguyên tử) khi lưu.
- Vậy là ĐỦ 9/9 file JSON cấu hình gốc: `accounts.json`,
  `account_groups.json`, `quick_login_groups.json`, `task_registry.json`,
  `run_state_today.json`, `data_groups.json`, `schedules.json`,
  `dashboard_settings.json`, `config.json` — tất cả giờ nằm trong
  `data/`, và LẦN ĐẦU chạy code mới, mọi file cũ ở thư mục gốc (nếu có)
  sẽ TỰ ĐỘNG được chuyển vào `data/`, không cần tự tay dọn.
- Đã kiểm tra cú pháp (`py_compile`) toàn bộ 9 file đã sửa - không lỗi.

**Lưu ý:** `templates/`, `tasks/`, `groups/` (ảnh mẫu, kịch bản, nhóm
bước dùng chung) CHƯA đụng tới - vẫn nằm ở vị trí cũ như trước (xem giải
thích ở cuối file này).

---

# Đã làm (đợt 1)

Theo yêu cầu: "cho tất cả các file cấu hình/json (người dùng) vào thư mục
data" + "backup/auto-save khi Lưu JSON".

## File mới

- **`paths.py`**
  - `resolve_data_path(filename)`: trả về đường dẫn `data/<filename>`, tự
    tạo thư mục `data/` nếu chưa có, và nếu thấy file CÙNG TÊN còn ở thư
    mục gốc (bản cũ trước khi có thay đổi này) mà `data/` chưa có, TỰ ĐỘNG
    DI CHUYỂN file đó sang `data/` — chỉ 1 lần, không mất dữ liệu cũ khi
    cập nhật code.
  - `save_json(path, data, backup=True)`: lưu JSON có sao lưu `.bak` (đè
    lên `.bak` cũ) TRƯỚC khi ghi đè, và ghi NGUYÊN TỬ (ghi ra `.tmp` rồi
    `os.replace()` sang tên thật) — không bao giờ để lại file JSON dở
    dang nếu mất điện/crash đúng lúc đang lưu.
  - `backup_before_overwrite(path)`: dùng riêng cho những chỗ tự mở file
    bằng `open(path, "w")` (không qua `save_json`), ví dụ Lưu Kịch Bản
    `.json` chọn đường dẫn tuỳ ý qua hộp thoại.

- **`file_logger.py`**
  - `write(level, message, emulator_name=None, source="")`: ghi 1 dòng
    log ra `logs/YYYY-MM-DD.log`, **flush + fsync ngay lập tức** (không
    đợi buffer) — tắt máy/crash giữa chừng vẫn còn nguyên các dòng log đã
    ghi trước đó. Tự sang file mới khi qua ngày. An toàn khi nhiều luồng
    (nhiều giả lập) ghi log cùng lúc.
  - **CHƯA gắn vào `dashboard_log.py`/`gui_run.py`** (xem phần "Còn lại"
    bên dưới) — module đã sẵn sàng dùng ngay khi gắn.

## File đã sửa (chuyển sang `data/` + JSON có backup)

- **`account_manager.py`** — `accounts.json`, `account_groups.json`,
  `quick_login_groups.json` → `data/accounts.json`,
  `data/account_groups.json`, `data/quick_login_groups.json`. Cả 3 hàm
  `save_accounts`/`save_group_presets`/`save_quick_login_groups` giờ gọi
  `paths.save_json()` (có `.bak` + ghi nguyên tử).
- **`task_registry.py`** — `task_registry.json` → `data/task_registry.json`.
  `save_registry()` dùng `paths.save_json()`.

Đã kiểm tra cú pháp (`py_compile`) — không lỗi. Lần đầu chạy sau khi cập
nhật, các file `accounts.json`/`account_groups.json`/
`quick_login_groups.json`/`task_registry.json` cũ ở thư mục gốc (nếu có)
sẽ TỰ ĐỘNG chuyển vào `data/` — không cần tự tay di chuyển.

---

# Còn lại (chưa làm trong đợt này)

1. Chuyển nốt `run_state.py` (`run_state_today.json`), `data_groups.py`
   (`data_groups.json`), `scheduler.py` (`schedules.json`), `dashboard.py`
   (`dashboard_settings.json`), `gui.py` (`config.json`) sang `data/` +
   `paths.save_json()` — cùng 1 khuôn mẫu như 2 file đã làm ở trên.
2. Gắn `file_logger.write(...)` vào `dashboard_log.py::_append_log` và
   `gui_run.py::_log_run` để mọi dòng Nhật Ký cũng tự ghi ra
   `logs/YYYY-MM-DD.log`.
3. Backup `.bak` khi bấm "💾 Lưu JSON" trong
   `gui_steplist_ops.py::save_macro_file()` (gọi
   `paths.backup_before_overwrite(path)` trước khi ghi đè).
4. Nested Logical Group (AND/OR lồng nhau, có NOT) — thêm action mới
   `if_group` vào `logic_engine.py` với cây điều kiện đệ quy (mỗi nút là
   `and`/`or`/`not` + danh sách con, lá là điều kiện ảnh/biến/OCR), tái
   dùng cơ chế IF/ELSE/ENDIF (jump-table) đã có sẵn cho `if_image`/
   `if_var`. Cần thêm 1 dialog trong GUI để dựng cây điều kiện.
5. Swipe nhiều điểm (path phức tạp) — thêm `swipe_path_px()` vào
   `adb_helper.py` (DOWN → nội suy MOVE qua từng đoạn giữa các điểm liên
   tiếp → UP), action `swipe_path` trong `logic_engine.py`, và thao tác
   click-nhiều-điểm-rồi-Enter trên Preview trong `gui_canvas.py`.
6. OCR dùng làm điều kiện/click (`if_ocr`) — action mới trong
   `logic_engine.py`: quét lặp lại 1 vùng cho tới khi chữ khớp (chứa/khớp
   đúng/regex) hoặc hết timeout, có thể tick "Click" để chạm vào giữa
   vùng đó khi khớp — tận dụng lại `ocr_text_in_box()` đã có trong
   `adb_helper.py`. Tham gia được cả vào cây điều kiện của mục 4 (1 loại
   lá "ocr" trong `if_group`) lẫn dùng độc lập như `if_image`.

Mục 4/5/6 đã khảo sát kỹ vị trí cần nối vào code hiện tại (đúng file,
đúng hàm) nhưng chưa viết — đây là phần tốn thời gian nhất vì đụng tới cả
`logic_engine.py`, `adb_helper.py` lẫn nhiều file GUI (`gui_canvas.py`,
`gui_manual_steps.py`, `gui_ui_build.py`, `gui_step_edit.py`) cùng lúc.

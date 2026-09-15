# AI Progress

## Current Task (2026-09-13, đợt 7)

Người dùng yêu cầu: "sửa lại để xếp hàng chờ các hành động theo thứ tự.
xong thì chạy tiếp hành động tiếp" — tức là khi 1 giả lập đang BẬN (có
phiên chạy tay / xoay vòng tài khoản / lịch hẹn giờ khác đang dùng), các
yêu cầu chạy tiếp theo nhắm vào ĐÚNG giả lập đó (trước đây bị BỎ QUA im
lặng kèm 1 dòng log cảnh báo - xem `_filter_busy_emulators` cũ) cần được
XẾP VÀO HÀNG CHỜ và tự động chạy tiếp theo ĐÚNG THỨ TỰ ngay khi việc đang
chạy kết thúc, thay vì mất hẳn yêu cầu đó.

### Đã làm (đợt 7)

- `dashboard.py`:
  - Thêm `self._emulator_queues = {}` (dict `emulator_index -> list các
    start_fn đang chờ`, FIFO) cạnh `self._busy_emulator_indexes` đã có.
  - Thêm 2 hàm dùng chung:
    - `_queue_or_start(emulator_index, start_fn, context_label,
      display_name)`: nếu giả lập RẢNH -> đánh dấu bận + chạy `start_fn()`
      ngay; nếu BẬN -> đẩy `start_fn` vào cuối hàng chờ của đúng giả lập
      đó, log rõ vị trí trong hàng chờ.
    - `_release_emulator(emulator_index)`: bỏ đánh dấu bận, rồi nếu hàng
      chờ của giả lập đó còn việc -> lấy ĐÚNG việc đầu hàng (FIFO) ra chạy
      NGAY LẬP TỨC (đánh dấu bận lại), giữ nguyên thứ tự các yêu cầu.
  - Xoá `_filter_busy_emulators()` cũ (lọc bỏ + cảnh báo) - thay bằng
    `_queue_or_start()` ở **3 nơi phát sinh yêu cầu chạy** (đều bọc logic
    khởi thread thật sự vào 1 `start_fn` không tham số, chỉ được gọi khi
    THỰC SỰ đến lượt chạy - không tăng nhầm bộ đếm khi mới xếp hàng):
    1. `_start_run()` (nút CHẠY thường).
    2. `_start_run_with_accounts()` (Xoay Vòng Tài Khoản).
    3. `_trigger_schedule()` (cả 2 chế độ: có Tài khoản / chỉ chọn thẳng
       Giả lập) - phần tăng `_active_schedule_count` +
       `_refresh_run_control_buttons()` + `_update_status_label()` được
       chuyển VÀO BÊN TRONG `start_fn`, chỉ chạy khi thực sự dispatch (kể
       cả khi dispatch trễ từ hàng chờ), không còn tăng đếm ngay tại thời
       điểm trigger như cũ.
  - `_on_emulator_thread_done()` và `_on_schedule_thread_done()`: đổi từ
    `self._busy_emulator_indexes.discard(idx)` trực tiếp sang gọi
    `_release_emulator(idx)` - đây là ĐIỂM DUY NHẤT cả 2 luồng (chạy tay và
    lịch hẹn giờ) cùng dùng để "trả lại" giả lập, nên hàng chờ luôn được
    xử lý bất kể việc đang chạy trước đó thuộc loại nào (chạy tay, xoay
    vòng, hay lịch hẹn giờ) và việc TIẾP THEO trong hàng chờ thuộc loại
    nào - 3 loại việc có thể xen kẽ nhau trong cùng 1 hàng chờ của 1 giả
    lập, luôn theo đúng thứ tự đã yêu cầu.
  - KHÔNG cần sửa `logic_engine.py`, `emulator_manager.py`,
    `account_manager.py`, `scheduler.py` - đây thuần là vấn đề ĐIỀU PHỐI
    (scheduling) ở tầng dashboard.py, không liên quan tới cách 1 kịch bản
    được thực thi.
  - `active_threads` (đếm cho phiên CHẠY thường/xoay vòng) và
    `_active_schedule_count` (đếm cho lịch hẹn giờ) giữ nguyên ý nghĩa cũ -
    không đổi cách tính, chỉ đổi THỜI ĐIỂM `_active_schedule_count` được
    tăng (dời vào trong `start_fn`, tăng đúng lúc THỰC SỰ bắt đầu chạy thay
    vì lúc trigger).
- Đã kiểm tra `py_compile` + `ast.parse` + `pyflakes` trên `dashboard.py`
  (và các file liên quan: `account_manager.py`, `emulator_manager.py`,
  `scheduler.py`, `logic_engine.py`) - không lỗi. CHƯA test thật trên
  Windows/LDPlayer.

### Cần người dùng tự kiểm tra trên máy thật

- Bấm CHẠY tay trên giả lập A trong lúc 1 lịch hẹn giờ CŨNG vừa trigger
  đúng giả lập A - xác nhận lượt lịch bị XẾP HÀNG (thấy log "đã XẾP VÀO
  HÀNG CHỜ") thay vì mất, và tự chạy ngay khi lượt chạy tay xong.
- Đặt 2 lịch hẹn giờ trùng giờ, cùng nhắm 1 giả lập - xác nhận lịch chạy
  sau tự xếp hàng, chạy nối tiếp đúng thứ tự trigger (không chồng lên
  nhau, không bị mất lượt nào).
- Bấm DỪNG trong lúc có việc đang XẾP HÀNG CHỜ (chưa tới lượt) cho 1 giả
  lập - xác nhận việc đang xếp hàng đó KHÔNG tự chạy sau khi dừng (vì việc
  đang chạy hiện tại dừng giữa chừng vẫn gọi `_on_..._thread_done` như
  bình thường, dequeue việc kế tiếp - cần xác nhận có nên huỷ luôn hàng
  chờ khi bấm DỪNG hay để nó tự chạy tiếp; hiện tại code CHO chạy tiếp,
  nếu người dùng muốn bấm DỪNG là huỷ sạch cả hàng chờ thì cần báo lại để
  sửa thêm).

---



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
"""
dashboard_theme.py — Bảng màu (dark mode) + văn bản Hướng Dẫn dùng chung
cho toàn bộ Dashboard. Tách riêng khỏi dashboard.py để mọi module UI
(dashboard_widgets.py, các Mixin trong dashboard_*.py) import chung 1
nguồn màu sắc duy nhất, không lặp lại/lệch màu giữa các file.
"""

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
      username, password, và (tuỳ chọn) 1 Nhóm để lọc/chọn nhanh sau này -
      tài khoản KHÔNG gán cố định theo giả lập nào cả. Bấm '💾 Lưu Tất Cả'.
   c) Tick 'Xoay Vòng Tài Khoản' ở thanh trên, tick chọn tác vụ + giả lập
      như bình thường rồi bấm '▶ CHẠY TẤT CẢ TÁC VỤ ĐANG CHỌN' - 1 popup sẽ
      hiện ra để bạn CHỌN THỦ CÔNG tài khoản xoay vòng cho TỪNG giả lập đã
      tick (để trống 1 giả lập = chạy tác vụ 1 lần, không xoay vòng).
   d) Với MỖI giả lập đã tick: Dashboard tự kiểm tra đang bật hay tắt - nếu
      TẮT thì tự khởi động (qua ldconsole) và chờ tới khi sẵn sàng, rồi lần
      lượt: Đăng Xuất -> Đăng Nhập tài khoản kế tiếp -> chạy các tác vụ đã
      tick -> sang tài khoản tiếp theo, cho tới hết danh sách tài khoản vừa
      chọn cho giả lập đó ở bước (c).

7) HẸN GIỜ TỰ ĐỘNG (chạy 1 Hoạt Động cho 1 nhóm tài khoản vào giờ cố định,
   hoặc lặp lại mỗi N giờ - KHÔNG cần bấm CHẠY thủ công)
   a) Bấm '⏰ Hẹn Giờ' ở góc trên, bấm '➕ Thêm Lịch Mới'.
   b) Đặt tên lịch, chọn Loại:
        - "Hằng ngày": nhập giờ chạy dạng hh:mm (vd 07:00) - chạy 1 lần
          mỗi ngày đúng giờ đó.
        - "Mỗi N giờ": nhập số giờ ở ô "Mỗi (giờ)" (vd 4) - chạy lặp lại
          cách nhau đúng N giờ, tính từ lần chạy gần nhất (chạy ngay lần
          đầu khi vừa Lưu, các lần sau tự cách đều).
   c) Bấm '🎯 HĐ (...)' chọn các Hoạt Động sẽ chạy, rồi '🔗 Gán GL/TK' để
      CHỌN THỦ CÔNG: giả lập nào áp dụng, và trên mỗi giả lập đó chọn (các)
      Tài khoản để xoay vòng (để trống Tài khoản của 1 giả lập = chạy
      thẳng, không đổi tài khoản). Bấm 💾 ở cuối dòng để lưu.
   d) Khi tới giờ: Dashboard tự BẬT từng giả lập đã gán nếu đang tắt, rồi
      Đăng Xuất -> Đăng Nhập từng tài khoản -> chạy đúng các Hoạt Động đã
      chọn cho lịch đó - y hệt cơ chế Xoay Vòng Tài Khoản ở mục 6, nhưng do
      THỜI GIAN kích hoạt tự động.
   e) Dashboard PHẢI ĐANG MỞ (có thể thu nhỏ, không cần thao tác gì) để
      lịch tự kích hoạt đúng giờ - đóng chương trình thì lịch sẽ không
      chạy. Nếu 1 giả lập đang bận (đang chạy dở Hoạt Động khác do chạy
      tay hoặc do 1 lịch khác), lượt chạy đó sẽ tự XẾP HÀNG CHỜ (ghi rõ
      trong Nhật Ký) - KHÔNG bị bỏ qua - và tự chạy tiếp ngay khi giả lập
      đó rảnh, dù việc trước đó chạy lâu tới đâu.
      Nút DỪNG LẠI / Tạm Dừng ở dưới áp dụng luôn cho các lịch đang chạy.
   f) Lịch BỎ LỠ lúc chương trình đang tắt: khi mở lại Dashboard, nếu có
      lịch đã tới giờ trong lúc tắt máy/tắt chương trình, sẽ hiện bảng
      '⏰ Lịch Hẹn Giờ Đã Bỏ Lỡ' liệt kê từng lịch (kèm các Hoạt Động theo
      thứ tự chạy). Tick lịch nào muốn CHẠY BÙ rồi bấm '▶ Chạy' - các lịch
      tick chạy lần lượt theo thứ tự trong bảng. Lịch không tick, hoặc bấm
      '⏭ Không chạy gì' (cũng như nút X/ESC), sẽ KHÔNG chạy và được đặt thành
      'vừa chạy xong' - lần chạy kế tiếp là mốc giờ hẹn tiếp theo.

8) TỰ LOGIN LÀ 1 HÀNH ĐỘNG RIÊNG (KHÁC "account_login")
   tasks/auto_login.json (id "auto_login") KHÔNG phải kịch bản đăng nhập
   tài khoản (đó là "account_login" - dùng cho Xoay Vòng Tài Khoản) - đây
   là 1 kịch bản RIÊNG chỉ để ĐƯA GIẢ LẬP VÀO ĐÚNG MÀN HÌNH GAME (tự soạn
   các bước wait_image/if_image để TỰ KIỂM TRA đã vào game hay chưa, bấm
   vào game nếu đang ở màn hình chờ...). Khi tick 'Tự Login': Dashboard
   chạy 'auto_login' TRƯỚC, CHỈ chạy tiếp các tác vụ đã tick SAU KHI
   'auto_login' báo THÀNH CÔNG - nếu thất bại (không vào được game), các
   tác vụ đã tick trên giả lập đó sẽ bị BỎ QUA (ghi rõ lỗi trong Nhật Ký)
   thay vì cứ chạy tiếp như trước.
   Ngoài ra: mỗi khi giả lập VỪA ĐƯỢC KHỞI ĐỘNG (nút Bật, bước hệ thống
   'Bật giả lập' - kể cả Tắt rồi Bật lại, hay tự bật khi chạy/hẹn giờ),
   Dashboard chờ boot xong + thêm số giây ở ô 'Chờ boot (s)' (máy chậm thì
   tăng) rồi mới chạy 'auto_login'. Bước hệ thống 'Đăng Xuất'/'Đăng Nhập'
   cũng chạy 'auto_login' ngay trước (riêng 'Đăng Nhập' đứng liền sau 'Đăng
   Xuất' thì bỏ qua để không vào lại game bằng tài khoản cũ).

9) CHẠY NGAY / CHẠY TAY CŨNG XẾP HÀNG CHỜ KHI GIẢ LẬP BẬN
   '▶ CHẠY TẤT CẢ TÁC VỤ ĐANG CHỌN', '▶ Chạy' (1 tác vụ), '👥 Xoay Vòng Tài
   Khoản' và '▶ Chạy Ngay' (trong '⏰ Hẹn Giờ') đều dùng chung 1 cơ chế
   HÀNG CHỜ với lịch hẹn giờ: nếu 1 giả lập đã chọn đang bận (đang chạy dở
   việc khác), lượt vừa bấm sẽ tự XẾP HÀNG CHỜ cho đúng giả lập đó (ghi rõ
   trong Nhật Ký) thay vì bị bỏ qua âm thầm - tự chạy tiếp ngay khi giả lập
   đó rảnh, không cần bấm lại.

10) 2 TUỲ CHỌN HẬU KỲ (áp dụng SAU KHI 1 giả lập chạy xong hết các tác vụ
    của lượt hiện tại - CHẠY tay/Chạy Ngay/Xoay Vòng Tài Khoản/lịch hẹn
    giờ đều áp dụng như nhau):
      - '🔌 Tắt Giả Lập Sau Khi Chạy Xong': tự tắt (ldconsole quit) giả lập
        đó ngay khi chạy xong.
      - '🔑 Đăng Nhập TK Chỉ Định Sau Khi Chạy Xong': bấm '🎯 Chọn TK' để
        chọn 1 Tài khoản cố định, Dashboard sẽ tự chạy 'account_login' để
        đăng nhập đúng tài khoản đó ngay khi chạy xong (cần có Hoạt Động
        'account_login', xem mục 6a).
    Nếu bật CẢ 2, Dashboard ưu tiên TẮT GIẢ LẬP (bỏ qua đăng nhập, có ghi
    log cảnh báo) vì đăng nhập xong rồi tắt ngay là vô nghĩa. Cả 2 tuỳ chọn
    đều KHÔNG áp dụng nếu bạn bấm DỪNG giữa chừng.
"""

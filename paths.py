"""
paths.py — Tiện ích dùng CHUNG cho mọi module lưu file cấu hình/dữ liệu do
NGƯỜI DÙNG tạo ra (accounts.json, task_registry.json, data_groups.json,
schedules.json, dashboard_settings.json, config.json...).

TRƯỚC ĐÂY mỗi file này nằm rải rác ngay tại thư mục gốc của dự án, lẫn với
mã nguồn (.py) - nay gom hết vào 1 thư mục "data/" cho gọn, dễ backup/
.gitignore nguyên cụm, và không lẫn với code khi dọn dẹp/đóng gói.

Hàm resolve_data_path() vừa trả về đường dẫn MỚI trong data/, vừa TỰ ĐỘNG
DI CHUYỂN file cũ (nếu có) từ thư mục gốc sang data/ - để người dùng cập
nhật code không bị mất sạch tài khoản/lịch/nhóm dữ liệu đã lưu trước đây.

Hàm save_json() thay cho việc tự mở file + json.dump() rải rác ở nhiều
module: TRƯỚC KHI ghi đè, tự sao lưu bản cũ thành "<path>.bak" (1 bản backup
gần nhất, không phải Undo nhiều bước, nhưng đủ cứu khi lỡ tay lưu sai/ghi đè
nhầm); rồi ghi ra file tạm ".tmp" trước, sau đó os.replace() sang tên thật -
đảm bảo KHÔNG BAO GIỜ để lại 1 file JSON dở dang/hỏng nếu mất điện hay
chương trình bị tắt đột ngột đúng lúc đang ghi.
"""
import json
import os
import shutil

DATA_DIR = "data"


def resolve_data_path(filename):
    """Trả về đường dẫn 'data/<filename>'. Tạo thư mục data/ nếu chưa có.
    Nếu tìm thấy file CÙNG TÊN ở thư mục gốc (bản trước khi có thay đổi
    này) mà data/ CHƯA có, tự di chuyển (migrate) sang data/ - chỉ làm 1
    lần duy nhất, những lần gọi sau file đã nằm sẵn trong data/ rồi."""
    os.makedirs(DATA_DIR, exist_ok=True)
    new_path = os.path.join(DATA_DIR, filename)
    old_path = filename
    if not os.path.exists(new_path) and os.path.exists(old_path) and os.path.abspath(old_path) != os.path.abspath(new_path):
        try:
            shutil.move(old_path, new_path)
        except OSError:
            pass
    return new_path


def backup_before_overwrite(path):
    """Sao lưu file ĐANG TỒN TẠI ở `path` thành `path + '.bak'` (đè lên bản
    .bak cũ nếu có) TRƯỚC khi ghi đè - dùng ở những nơi tự mở file bằng
    open(path, 'w') thay vì gọi save_json() (vd Lưu Kịch Bản .json chọn
    đường dẫn tuỳ ý qua hộp thoại, không cố định trong data/)."""
    if os.path.exists(path):
        try:
            shutil.copy2(path, path + ".bak")
        except OSError:
            pass


def save_json(path, data, backup=True):
    """Lưu `data` ra file JSON tại `path`, có sao lưu .bak + ghi nguyên tử
    (xem docstring đầu file). Dùng thay cho open(path,'w') + json.dump()."""
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    if backup:
        backup_before_overwrite(path)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def _write_raw(path, data):
    """Ghi `data` đè lên `path` NGUYÊN TỬ nhưng KHÔNG tạo .bak - dùng nội
    bộ bởi load_json_with_recovery() khi tự "chữa lành" 1 file vừa đọc lỗi
    bằng dữ liệu phục hồi từ chính bản .bak của nó: nếu gọi save_json()
    (có backup=True) ở bước này, nó sẽ sao lưu file LỖI đang có ở `path`
    đè lên .bak - tức là XOÁ MẤT bản .bak TỐT vừa dùng để cứu dữ liệu."""
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, path)


def load_json_with_recovery(path, default):
    """Đọc JSON tại `path`. Nếu file KHÔNG TỒN TẠI (vd lần đầu chạy app),
    trả về `default` như bình thường - KHÔNG phải lỗi.

    Nếu file CÓ tồn tại nhưng ĐỌC LỖI (JSON hỏng do bị tắt máy/mất điện
    đúng lúc ghi, ổ đĩa đầy, phần mềm đồng bộ (OneDrive/Google Drive) khoá
    file nửa chừng, tự tay sửa file rồi gõ sai cú pháp...) - hàm này
    KHÔNG âm thầm trả về `default` như các bản load_*() cũ (rất nguy hiểm:
    nếu sau đó người dùng bấm Lưu bất cứ thứ gì, toàn bộ danh sách cũ - Tài
    Khoản/Lịch Hẹn Giờ/Hoạt Động... - sẽ bị GHI ĐÈ THÀNH RỖNG, mất trắng mà
    KHÔNG có bất kỳ cảnh báo nào). Thay vào đó:
      1. Sao 1 bản file lỗi sang "<path>.corrupted" để có thể xem lại/gửi
         báo lỗi sau này.
      2. Nếu có "<path>.bak" (save_json() tự tạo mỗi lần lưu bình thường)
         và đọc được -> PHỤC HỒI từ đó, đồng thời tự ghi đè lại `path`
         bằng đúng dữ liệu vừa phục hồi (KHÔNG qua save_json() để tránh
         xoá mất chính bản .bak tốt vừa cứu) - từ lần đọc sau, file đã
         "lành" trở lại, không cần bạn tự làm gì thêm.
      3. Nếu không có .bak hoặc .bak cũng lỗi -> đành trả về `default`.

    Trả về (data, warning): `warning` là None nếu đọc bình thường (kể cả
    trường hợp file chưa tồn tại); nếu khác None thì có sự cố vừa xảy ra -
    BÊN GỌI NÊN hiển thị cảnh báo này cho người dùng (log + messagebox),
    đừng âm thầm bỏ qua."""
    if not os.path.exists(path):
        return default, None

    def _try_load(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    try:
        return _try_load(path), None
    except Exception as e:
        corrupt_copy = path + ".corrupted"
        try:
            shutil.copy2(path, corrupt_copy)
        except OSError:
            corrupt_copy = None

        bak_path = path + ".bak"
        if os.path.exists(bak_path):
            try:
                data = _try_load(bak_path)
            except Exception:
                data = None
            if data is not None:
                try:
                    _write_raw(path, data)
                except OSError:
                    pass  # phục hồi trong bộ nhớ vẫn dùng được, chỉ là chưa ghi lại được ra đĩa
                warning = (f"File '{path}' bị lỗi định dạng ({e}) - ĐÃ TỰ ĐỘNG KHÔI PHỤC dữ liệu từ "
                           f"bản sao lưu gần nhất ('{bak_path}'). Vài thay đổi GẦN NHẤT ngay trước "
                           f"lúc file bị hỏng có thể KHÔNG có trong bản khôi phục này - kiểm tra lại "
                           f"cho chắc." + (f" File lỗi gốc được giữ lại tại '{corrupt_copy}' nếu cần "
                                           f"đối chiếu." if corrupt_copy else ""))
                return data, warning

        warning = (f"File '{path}' bị lỗi định dạng ({e}) và KHÔNG có bản sao lưu hợp lệ để khôi "
                   f"phục - ĐANG DÙNG DANH SÁCH RỖNG cho tới khi bạn tự sửa lại." +
                   (f" File lỗi gốc được giữ lại tại '{corrupt_copy}' để đối chiếu/khôi phục thủ "
                    f"công." if corrupt_copy else ""))
        return default, warning

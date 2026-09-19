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

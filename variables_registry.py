"""
variables_registry.py — "🧩 Quản Lý Biến": danh sách các BIẾN dùng CHUNG
cho MỌI kịch bản, khai báo 1 LẦN DUY NHẤT ở đây (tên biến, câu hỏi hiển
thị chỉ để ghi nhớ, kiểu dữ liệu, GIÁ TRỊ) - KHÔNG cần thêm bước SET_VAR/
INPUT_VAR thủ công bên trong từng kịch bản riêng lẻ nữa.

Cách dùng: sau khi khai báo 1 biến ở đây (vd tên "so_luong", giá trị 5),
chỉ cần gõ {so_luong} ở BẤT KỲ ô nào hỗ trợ biến trong LD Macro Studio
(Sửa Lặp, Gõ Chữ, Popup...) của BẤT KỲ kịch bản nào - giá trị "default"
lưu ở đây được Dashboard lấy ra và áp dụng THẲNG mỗi lần CHẠY (xem
_get_registry_preset_vars() trong dashboard_misc.py), KHÔNG còn hộp thoại
hỏi lúc bấm Chạy nữa - muốn đổi giá trị thì mở "🧩 Quản Lý Biến" sửa rồi
Lưu trước khi chạy. Cột "Dùng bởi" trong giao diện quản lý (tính bởi
_scan_variable_usage_by_task() trong dashboard_misc.py) cho biết Hoạt
Động nào đang tham chiếu từng biến, chỉ để tham khảo/tổ chức, không ảnh
hưởng logic.

Vẫn dùng SONG SONG được với bước 'input_var' khai báo ngay trong kịch bản
(xem logic_engine.py) - biến nào ĐÃ khai báo ở registry này thì giá trị ở
đây LUÔN được ưu tiên dùng (coi như "đã preset"); bước 'input_var' của
1 kịch bản chỉ còn tác dụng khi biến đó CHƯA có trong registry (dùng
'default' riêng của bước đó), hoặc lúc "Chạy Thử" ngay trong Macro Studio.

DỮ LIỆU LƯU TRONG variables.json (list các dict):
    {
        "id": "bien_a1b2c3d4",           # sinh tự động, ổn định để sửa/xoá đúng dòng
        "var": "so_luong",               # tên biến - dùng trong {so_luong}
        "label": "Số lượng mua Shop",     # ghi chú/nhãn gợi nhớ (không còn dùng để hỏi)
        "var_type": "int",                # "int" | "float" | "text"
        "default": 1,                     # GIÁ TRỊ THẬT SỰ áp dụng mỗi lần chạy
        "ghi_chu": ""                     # ghi chú tự do, không ảnh hưởng logic
    }
"""
import threading
import uuid

import paths

VARIABLES_PATH = paths.resolve_data_path("variables.json")

# Khoá dùng CHUNG cho mọi thao tác ghi variables.json - tránh 2 nơi cùng ghi
# đè lên nhau (giống accounts.json, xem account_manager.py).
_variables_file_lock = threading.RLock()


def load_variables(path=VARIABLES_PATH, warnings_out=None):
    """Đọc toàn bộ danh sách biến đã khai báo. Luôn trả về list (rỗng nếu
    CHƯA TỪNG có file). Nếu file CÓ nhưng bị lỗi định dạng, tự thử khôi
    phục từ bản sao lưu ".bak" (xem paths.load_json_with_recovery)."""
    data, warning = paths.load_json_with_recovery(path, [])
    if warning and warnings_out is not None:
        warnings_out.append(warning)
    return data if isinstance(data, list) else []


def save_variables(entries, path=VARIABLES_PATH):
    with _variables_file_lock:
        paths.save_json(path, entries)


def new_variable_id():
    return f"bien_{uuid.uuid4().hex[:8]}"


def upsert_variable(entries, entry):
    """Thêm mới nếu chưa có id trùng, ngược lại cập nhật tại chỗ. Trả về entries."""
    for i, e in enumerate(entries):
        if e.get("id") == entry.get("id"):
            entries[i] = entry
            return entries
    entries.append(entry)
    return entries


def remove_variable(entries, var_id):
    return [e for e in entries if e.get("id") != var_id]


def find_by_var_name(entries, var_name):
    """Tìm định nghĩa biến theo TÊN (không phải id). Trùng tên nhiều dòng
    thì lấy dòng ĐẦU TIÊN. Tiện ích chung, chưa có nơi nào gọi trực tiếp
    trong code hiện tại (Dashboard áp dụng toàn bộ registry qua
    _get_registry_preset_vars() thay vì tra theo từng tên)."""
    for e in entries:
        if e.get("var") == var_name:
            return e
    return None

"""
Danh mục Tác Vụ (Task Registry) - CẦU NỐI giữa 2 chương trình:

  1) LD Macro Studio (gui.py)  -> nơi TẠO từng tác vụ (ghi F7 hoặc soạn thủ
     công), lưu thành file JSON trong tasks/, rồi bấm "📋 Đăng Ký Tác Vụ" để
     ghi 1 dòng mô tả vào task_registry.json.

  2) Auto Runner Dashboard (dashboard.py) -> chỉ ĐỌC task_registry.json để
     dựng danh sách checklist theo từng Mục và chạy các tác vụ được chọn.

Vì cả 2 chương trình đều import module này, khi đổi định dạng file thì chỉ
cần sửa 1 chỗ duy nhất.
"""
import json
import os

REGISTRY_PATH = "task_registry.json"


def load_registry(path=REGISTRY_PATH):
    """Đọc toàn bộ danh mục tác vụ. Luôn trả về list (rỗng nếu chưa có file
    hoặc file bị lỗi định dạng) để nơi gọi không cần tự try/except."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def save_registry(entries, path=REGISTRY_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def make_task_id(file_json):
    """Sinh id ổn định từ đường dẫn file kịch bản, vd tasks/like_ng.json -> 'like_ng'.
    Dùng tên file làm id để 'Đăng ký lại' cùng 1 file sẽ CẬP NHẬT thay vì tạo trùng."""
    return os.path.splitext(os.path.basename(file_json))[0]


def find_task(entries, task_id):
    for e in entries:
        if e.get("id") == task_id:
            return e
    return None


def upsert_task(entries, entry):
    """Thêm mới nếu chưa có id trùng, ngược lại cập nhật tại chỗ. Trả về entries."""
    for i, e in enumerate(entries):
        if e.get("id") == entry.get("id"):
            entries[i] = entry
            return entries
    entries.append(entry)
    return entries


def remove_task(entries, task_id):
    return [e for e in entries if e.get("id") != task_id]


def list_categories(entries):
    """Danh sách các Mục đã tồn tại, giữ đúng thứ tự xuất hiện lần đầu
    (dùng để gợi ý trong ô combobox khi đăng ký tác vụ mới)."""
    seen = []
    for e in entries:
        muc = e.get("muc") or "Chưa phân loại"
        if muc not in seen:
            seen.append(muc)
    return seen


def next_order_in_category(entries, muc):
    """Số thứ tự gợi ý tiếp theo trong 1 Mục, để tác vụ mới đăng ký mặc định
    xếp xuống cuối danh sách của Mục đó thay vì lẫn lộn vị trí."""
    orders = [e.get("thu_tu", 0) for e in entries if (e.get("muc") or "Chưa phân loại") == muc]
    return (max(orders) + 1) if orders else 1

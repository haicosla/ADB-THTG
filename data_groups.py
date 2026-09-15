"""
data_groups.py — Quản lý "NHÓM DỮ LIỆU": các danh sách text do người dùng tự
đặt (vd danh sách ID tài khoản, tên phòng, số bàn, nội dung bình luận...),
dùng làm BIẾN LẶP khi soạn kịch bản trong gui.py.

Ý TƯỞNG: giống hệt cơ chế "Xoay Vòng Tài Khoản" (account_manager.py) nhưng
TỔNG QUÁT cho MỌI loại danh sách, không chỉ riêng tài khoản đăng nhập/đăng
xuất. Trong kịch bản, đặt 1 bước "➡️ Lấy Dữ Liệu (Nhóm)" (action
"next_data_item", xem logic_engine.py) BÊN TRONG 1 khối GROUP lặp N lần:
mỗi lượt lặp, biến chỉ định sẽ tự động đổi sang PHẦN TỬ TIẾP THEO trong
danh sách theo đúng thứ tự - dùng {tên_biến} ở các bước Gõ Chữ/Tap sau đó
như bình thường.

Ví dụ: Nhóm Dữ Liệu "id_acc" = ["1","2","3",...,"10"], đặt bước Lấy Dữ Liệu
vào biến "id" ở đầu 1 GROUP lặp 10 lần -> lượt 1 biến id="1", lượt 2
id="2", ... lượt 10 id="10" (giống hệt log đổi tài khoản 1->10).

DỮ LIỆU LƯU TRONG data_groups.json (list các dict):
    {
        "id": "dg_xxxxxxxx",       # sinh tự động, ổn định để sửa/xoá đúng dòng
        "ten": "ID tài khoản",     # tên gợi nhớ, hiển thị trong Dashboard/GUI
        "items": ["1", "2", "3"],  # danh sách text, THỨ TỰ chính là thứ tự lặp
        "ghi_chu": "",
    }
"""
import json
import os
import uuid

DATA_GROUPS_PATH = "data_groups.json"


def load_groups(path=DATA_GROUPS_PATH):
    """Đọc toàn bộ danh sách Nhóm Dữ Liệu. Luôn trả về list (rỗng nếu chưa
    có file hoặc file lỗi định dạng)."""
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


def save_groups(entries, path=DATA_GROUPS_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def new_group_id():
    return f"dg_{uuid.uuid4().hex[:8]}"


def upsert_group(entries, entry):
    """Thêm mới nếu chưa có id trùng, ngược lại cập nhật tại chỗ. Trả về
    entries."""
    for i, e in enumerate(entries):
        if e.get("id") == entry.get("id"):
            entries[i] = entry
            return entries
    entries.append(entry)
    return entries


def remove_group(entries, group_id):
    return [e for e in entries if e.get("id") != group_id]


def get_group(entries, group_id):
    for e in entries:
        if e.get("id") == group_id:
            return e
    return None


def find_group_by_name(entries, name):
    name = (name or "").strip().lower()
    for e in entries:
        if (e.get("ten") or "").strip().lower() == name:
            return e
    return None


def items_from_text(raw_text):
    """Chuyển nội dung ô nhập nhiều dòng (mỗi dòng 1 phần tử) thành list,
    bỏ dòng trống và khoảng trắng thừa đầu/cuối mỗi dòng."""
    if not raw_text:
        return []
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def items_to_text(items):
    """Chiều ngược lại items_from_text() - dùng để đổ dữ liệu ra ô nhập
    nhiều dòng khi mở lại 1 Nhóm Dữ Liệu để sửa."""
    return "\n".join(str(x) for x in (items or []))

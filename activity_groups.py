"""
activity_groups.py — Quản lý "Nhóm Hành Động": mỗi Nhóm là 1 gói ĐẶT TÊN,
gồm nhiều Hoạt Động (macro) và/hoặc Hành động hệ thống (Bật/Tắt giả lập,
Đăng Xuất, Đăng Nhập 1 tài khoản cụ thể) SẮP XẾP THEO THỨ TỰ, dùng để:
  - Bấm CHẠY THẲNG 1 Nhóm (mở từ '📦 Nhóm Hành Động' trên Dashboard) - chạy
    lần lượt đúng thứ tự các bước bên trong, y hệt 1 Hoạt Động đơn lẻ.
  - CHỌN 1 Nhóm làm 1 trong các "Hoạt Động" của 1 Lịch Hẹn Giờ, hoặc của
    'Hành Động Cuối' (theo giả lập/theo từng lịch) - xem GROUP_PREFIX +
    _build_activity_steps() ở dashboard_schedule.py (tự "bung" Nhóm ra
    thành đúng các bước con của nó tại vị trí đó, kể cả LỒNG NHÓM TRONG
    NHÓM - có chống lặp vòng tự tham chiếu).

Ví dụ đúng yêu cầu ban đầu: Nhóm 1 = [A, B, C], Nhóm 2 = [B, C, D], Nhóm 3 =
[A, G, H] - các Hoạt Động A/B/C... có thể xuất hiện lặp lại ở NHIỀU Nhóm
khác nhau, không ảnh hưởng lẫn nhau (chỉ là tham chiếu id, không sao chép).

DỮ LIỆU LƯU TRONG activity_groups.json (list các dict):
    {
        "id": "nhom_xxxxxxxx",      # sinh tự động, ổn định để sửa/xoá đúng dòng
        "ten": "Nhóm 1",            # tên gợi nhớ, hiển thị trong Dashboard
        "hoat_dong_ids": [...],     # danh sách id CÓ THỨ TỰ, CÓ THỂ LẶP -
                                     # cùng định dạng `hoat_dong_ids` của 1
                                     # Lịch Hẹn Giờ (id Hoạt Động thường /
                                     # hằng số SYS_* / "GROUP:<id>" của 1
                                     # Nhóm khác - xem dashboard_schedule.py).
        "ghi_chu": "",
    }
"""
import threading
import uuid

import paths

GROUPS_PATH = paths.resolve_data_path("activity_groups.json")

# Tiền tố đánh dấu 1 id trong `hoat_dong_ids` (của Lịch Hẹn Giờ/Hành Động
# Cuối/1 Nhóm khác) là THAM CHIẾU tới 1 Nhóm Hành Động khác, thay vì 1 id
# Hoạt Động thường hay hằng số SYS_* - xem cách dùng ở
# dashboard_schedule.py::_build_activity_steps().
GROUP_PREFIX = "GROUP:"

_groups_file_lock = threading.RLock()


def load_groups(path=GROUPS_PATH):
    """Đọc toàn bộ danh sách Nhóm Hành Động. Luôn trả về list (rỗng nếu
    CHƯA TỪNG có file). Tự khôi phục từ bản sao lưu ".bak" nếu file bị lỗi
    định dạng (xem paths.load_json_with_recovery)."""
    data, _warning = paths.load_json_with_recovery(path, [])
    return data if isinstance(data, list) else []


def save_groups(entries, path=GROUPS_PATH):
    with _groups_file_lock:
        paths.save_json(path, entries)


def new_group_id():
    return f"nhom_{uuid.uuid4().hex[:8]}"


def upsert_group(entries, entry):
    """Thêm mới nếu chưa có id trùng, ngược lại cập nhật tại chỗ. Trả về entries."""
    for i, e in enumerate(entries):
        if e.get("id") == entry.get("id"):
            entries[i] = entry
            return entries
    entries.append(entry)
    return entries


def remove_group(entries, group_id):
    return [e for e in entries if e.get("id") != group_id]


def groups_by_id(entries=None):
    """Dict {id: group_dict} tiện tra cứu nhanh - tự load nếu không truyền
    sẵn `entries`."""
    if entries is None:
        entries = load_groups()
    return {e.get("id"): e for e in entries if e.get("id")}

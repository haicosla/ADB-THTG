"""
account_manager.py — Quản lý danh sách TÀI KHOẢN dùng cho tính năng "Xoay
Vòng Tài Khoản": nhiều tài khoản chạy LẦN LƯỢT trên CÙNG 1 giả lập (đăng
xuất tài khoản cũ - đăng nhập tài khoản mới - chạy các Tác Vụ đã chọn -
sang tài khoản tiếp theo).

LƯU Ý QUAN TRỌNG (thay đổi so với bản trước): danh sách tài khoản ở đây
KHÔNG còn gán cố định theo 1 giả lập cụ thể nào nữa (đã bỏ hẳn field
"emulator_index"). Tài khoản nào chạy trên giả lập nào giờ được CHỌN THỦ
CÔNG ngay tại thời điểm bấm CHẠY ('👥 Xoay Vòng Tài Khoản') hoặc lúc soạn 1
lịch hẹn giờ (nút gán Giả Lập ↔ Tài Khoản trong '⏰ Hẹn Giờ' - xem
dashboard.py), thay vì phải "nhớ trước" 1 giả lập duy nhất cho từng tài
khoản như trước đây. Nhờ vậy: (1) cùng 1 danh sách tài khoản dùng lại được
cho nhiều giả lập/nhiều lịch khác nhau, và (2) không còn bị kẹt khi số
lượng/tên/index giả lập thay đổi qua thời gian.

DỮ LIỆU LƯU TRONG accounts.json (list các dict):
    {
        "id": "tk_1",                 # sinh tự động, ổn định để sửa/xoá đúng dòng
        "ten_hien_thi": "Nick 01",     # tên gợi nhớ, hiển thị trong Dashboard
        "username": "...",
        "password": "...",
        "ghi_chu": "",
        "nhom": "",                    # PHÂN LOẠI HOÀN TOÀN TỰ DO - gõ tay
                                        # tên nhóm bất kỳ (không giới hạn chỉ
                                        # "Clone" / "Acc chính" như gợi ý mặc
                                        # định trên giao diện) để LỌC/CHỌN
                                        # NHANH trong '👥 Quản Lý Tài Khoản'
                                        # và khi chọn Tài khoản cho 1 lịch
                                        # hẹn giờ. Không ảnh hưởng logic xoay
                                        # vòng. Để trống nếu không cần phân
                                        # loại.
        "bat": true,                   # bỏ tick = tạm ngưng, không đưa vào
                                        # hàng chờ xoay vòng.
        "lan_chay_cuoi": null          # ISO timestamp lần chạy xong gần nhất
                                        # (chỉ để hiển thị, KHÔNG dùng để lọc
                                        # "đã chạy hôm nay" - mỗi lần bấm
                                        # CHẠY sẽ xoay vòng lại từ đầu danh
                                        # sách các tài khoản đang BẬT).
    }

QUY ƯỚC 2 TÁC VỤ (Hoạt Động) BẮT BUỘC PHẢI TỰ SOẠN TRƯỚC (dùng LD Macro
Studio ghi F7 như soạn tác vụ bình thường), rồi Đăng Ký Tác Vụ với ID đúng
tên file:
    tasks/account_login.json   -> id "account_login": các bước ĐĂNG NHẬP.
        Ở bước "Gõ Chữ" (type_text), gõ đúng {tk_user} và {tk_pass} thay vì
        gõ tay email/mật khẩu thật - 2 biến này sẽ được điền tự động bằng
        đúng thông tin của tài khoản đang xoay tới.
    tasks/account_logout.json  -> id "account_logout": các bước ĐĂNG XUẤT
        tài khoản đang đăng nhập (mở menu, bấm Đăng Xuất...). Chạy TRƯỚC khi
        đăng nhập tài khoản tiếp theo, và sau khi xong tài khoản CUỐI CÙNG
        trong hàng chờ (để giả lập luôn kết thúc ở trạng thái đã đăng xuất).
Nếu chưa có 1 trong 2 file trên, Dashboard sẽ báo lỗi rõ ràng trong Nhật Ký
Chạy và bỏ qua bước đó (không dừng hẳn toàn bộ phiên chạy).
"""
import json
import os
import uuid
from datetime import datetime

ACCOUNTS_PATH = "accounts.json"


def load_accounts(path=ACCOUNTS_PATH):
    """Đọc toàn bộ danh sách tài khoản. Luôn trả về list (rỗng nếu chưa có
    file hoặc file lỗi định dạng)."""
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


def save_accounts(entries, path=ACCOUNTS_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def new_account_id():
    return f"tk_{uuid.uuid4().hex[:8]}"


def upsert_account(entries, entry):
    """Thêm mới nếu chưa có id trùng, ngược lại cập nhật tại chỗ. Trả về entries."""
    for i, e in enumerate(entries):
        if e.get("id") == entry.get("id"):
            entries[i] = entry
            return entries
    entries.append(entry)
    return entries


def remove_account(entries, account_id):
    return [e for e in entries if e.get("id") != account_id]


def active_accounts(entries):
    """Danh sách tài khoản ĐANG BẬT, giữ nguyên thứ tự trong file (thứ tự
    này chính là thứ tự xoay vòng mặc định khi chọn nhanh 'Tất cả' ở giao
    diện). Tài khoản không còn gán cố định theo giả lập nào - nơi gọi (xem
    dashboard.py) tự quyết định tài khoản nào chạy trên giả lập nào tại
    thời điểm bấm CHẠY / soạn lịch."""
    return [e for e in entries if bool(e.get("bat", True))]


def mark_run(entries, account_id, path=ACCOUNTS_PATH):
    """Ghi lại thời điểm vừa chạy xong 1 tài khoản (chỉ để hiển thị tham
    khảo trong Dashboard, không ảnh hưởng logic xoay vòng lần sau)."""
    for e in entries:
        if e.get("id") == account_id:
            e["lan_chay_cuoi"] = datetime.now().isoformat(timespec="seconds")
            break
    save_accounts(entries, path)
    return entries


GROUP_PRESETS_PATH = "account_groups.json"


def load_group_presets(path=GROUP_PRESETS_PATH):
    """Đọc danh sách tên Nhóm được LƯU SẴN làm gợi ý (hiện trong combobox
    'Nhóm' + nút lọc nhanh ở '👥 Quản Lý Tài Khoản') NGAY CẢ KHI chưa có
    tài khoản nào thuộc nhóm đó - khác với nhóm suy ra tự động từ
    accounts.json (chỉ thấy khi đã có >=1 tài khoản gắn nhóm đó, xem
    list_groups() ở trên). Nếu chưa từng lưu file này (lần đầu dùng), trả
    về đúng 2 gợi ý mặc định cũ ('Acc chính', 'Clone') để không đổi trải
    nghiệm người dùng đang dùng bản trước."""
    if not os.path.exists(path):
        return ["Acc chính", "Clone"]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            cleaned = [str(g).strip() for g in data if str(g).strip()]
            if cleaned:
                return cleaned
    except Exception:
        pass
    return ["Acc chính", "Clone"]


def save_group_presets(groups, path=GROUP_PRESETS_PATH):
    """Lưu danh sách tên Nhóm gợi ý (loại trùng - không phân biệt
    hoa/thường, giữ nguyên thứ tự xuất hiện đầu tiên). Trả về danh sách đã
    dọn dẹp."""
    seen = set()
    cleaned = []
    for g in groups:
        g = str(g).strip()
        key = g.lower()
        if g and key not in seen:
            seen.add(key)
            cleaned.append(g)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    return cleaned


def add_group_preset(name, path=GROUP_PRESETS_PATH):
    """Thêm 1 tên Nhóm MỚI vào danh sách gợi ý đã lưu (bỏ qua nếu tên
    trống hoặc đã có sẵn, không phân biệt hoa/thường). Trả về danh sách
    gợi ý sau khi thêm - dùng để cập nhật lại combobox/nút lọc ngay mà
    không cần đóng mở lại cửa sổ '👥 Quản Lý Tài Khoản'."""
    name = str(name).strip()
    presets = load_group_presets(path)
    if not name or name.lower() in {p.lower() for p in presets}:
        return presets
    presets.append(name)
    return save_group_presets(presets, path)


def list_groups(entries):
    """Danh sách các Nhóm tài khoản đã tồn tại (bỏ chuỗi rỗng), sắp xếp theo
    bảng chữ cái - dùng để gợi ý trong combobox 'Nhóm' và dựng các nút lọc
    nhanh theo nhóm."""
    return sorted({(e.get("nhom") or "").strip() for e in entries if (e.get("nhom") or "").strip()})

"""
dong_goi_dong_bo.py — Đóng gói TOÀN BỘ Hoạt Động (tasks/), ảnh mẫu
(templates/) và các file cấu hình cần thiết (data/*.json) thành ĐÚNG 1 file
.zip duy nhất, để chuyển sang máy khác và ĐỒNG BỘ lại y hệt danh mục Hoạt
Động/Tài khoản/Lịch hẹn giờ đang có trên máy này.

CÁCH DÙNG:
    1) Đặt file này (và Dong_Goi_Dong_Bo.bat đi kèm, nếu có) ngay cùng thư
       mục với dashboard.py/main.py (thư mục gốc của dự án).
    2) Bấm đúp Dong_Goi_Dong_Bo.bat (hoặc chạy `python dong_goi_dong_bo.py`
       trong terminal) - file .zip sẽ được tạo trong thư mục con
       "xuat_dong_bo/", tên có kèm ngày giờ để không đè lên gói đã xuất
       trước đó (dong_bo_2026-09-17_221530.zip chẳng hạn).
    3) Copy file .zip đó sang máy kia (USB/Zalo/Google Drive/...).
    4) Ở máy kia: bung nén file .zip ĐÈ THẲNG vào thư mục gốc của dự án
       (thư mục đã có sẵn dashboard.py/main.py/adb.exe/OCR...) - chọn "Có/
       Yes/Replace" nếu Windows hỏi có ghi đè file trùng tên không. XONG,
       KHÔNG cần chạy thêm script nào khác - mở dashboard.py lên là thấy
       đầy đủ Hoạt Động/Tài khoản/Lịch hẹn giờ giống hệt máy nguồn.

GÓI .zip GIỮ NGUYÊN CẤU TRÚC THƯ MỤC (tasks/..., templates/..., data/...)
nên bung nén đè vào đúng thư mục gốc là file rơi đúng chỗ, không cần đổi
tên/di chuyển gì thêm.

CHỦ Ý ĐÍCH THỊ KHÔNG ĐÓNG GÓI (để tránh phá cấu hình riêng của máy kia):
  - data/window_geometry.json  - vị trí/kích thước từng cửa sổ đã lưu
    riêng cho MÀN HÌNH của máy này (xem chú thích trong window_geometry.py:
    "file này KHÔNG nên đồng bộ/copy giữa các máy, vì mỗi máy có độ phân
    giải màn hình khác nhau").
  - data/dashboard_settings.json - có chứa "ldconsole_path" (đường dẫn cài
    LDPlayer, THƯỜNG KHÁC NHAU giữa 2 máy) và bảng "shutdown_after_by_
    emulator"/"post_login_account_by_emulator" (gán theo SỐ THỨ TỰ giả lập
    - số này ở máy kia có thể trỏ nhầm sang giả lập khác nếu 2 máy không
    set giả lập giống hệt nhau). 3 tuỳ chọn checkbox chung (Tự Login/Xoay
    Vòng Tài Khoản/...) cũng nằm trong file này nên sẽ cần tự tick lại 1
    lần trên máy kia - không đáng kể so với rủi ro nếu đồng bộ nhầm số thứ
    tự giả lập.
  - data/run_state_today.json - chỉ là "đã chạy xong tác vụ nào hôm nay",
    không phải cấu hình, tự sinh lại khi chạy.
  - Mọi file *.bak/*.tmp (bản sao lưu tạm của paths.save_json) và
    __pycache__/ (bytecode Python, máy nào tự sinh máy đó).

Nếu 2 máy đã set SỐ THỨ TỰ giả lập (index trong LDPlayer) giống hệt nhau và
muốn đồng bộ luôn cả gán giả lập/tài khoản của Lịch Hẹn Giờ + ldconsole_path,
xem ghi chú ở cuối file này (biến INCLUDE_DASHBOARD_SETTINGS).
"""

import os
import sys
import zipfile
from datetime import datetime

# Thư mục gốc của dự án = thư mục chứa chính file này (đặt file này ngay
# cạnh dashboard.py/main.py là dùng được ngay, không cần sửa gì).
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

TASKS_DIR = os.path.join(PROJECT_ROOT, "tasks")
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "xuat_dong_bo")

# Các file cấu hình trong data/ sẽ được đóng gói (an toàn để copy sang máy
# khác - không chứa gì gắn riêng với 1 máy cụ thể).
DATA_FILES_TO_INCLUDE = [
    "accounts.json",
    "account_groups.json",
    "quick_login_groups.json",
    "task_registry.json",
    "schedules.json",
]

# Đổi thành True nếu 2 máy đã set SỐ THỨ TỰ giả lập giống hệt nhau và muốn
# đồng bộ luôn cả đường dẫn ldconsole.exe + gán giả lập/tài khoản của Lịch
# Hẹn Giờ - MẶC ĐỊNH False vì đây là trường hợp không phổ biến (rủi ro gán
# nhầm giả lập nếu 2 máy set khác số thứ tự).
INCLUDE_DASHBOARD_SETTINGS = False
if INCLUDE_DASHBOARD_SETTINGS:
    DATA_FILES_TO_INCLUDE.append("dashboard_settings.json")

# Đuôi file ảnh mẫu hợp lệ (khớp với capture_tools.py - luôn lưu .png,
# nhưng có thể có người tự thêm ảnh .jpg thủ công nên quét luôn cho chắc).
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp")

SKIP_SUFFIXES = (".bak", ".tmp")
SKIP_DIR_NAMES = {"__pycache__"}


def _iter_files(root_dir, allowed_exts=None):
    """Duyệt toàn bộ file trong root_dir (kể cả thư mục con), bỏ qua
    __pycache__/ và các file .bak/.tmp - trả về (đường dẫn tuyệt đối,
    đường dẫn tương đối so với PROJECT_ROOT dùng làm tên trong .zip)."""
    if not os.path.isdir(root_dir):
        return
    for cur_root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_NAMES]
        for fname in sorted(files):
            if fname.endswith(SKIP_SUFFIXES):
                continue
            if allowed_exts and not fname.lower().endswith(allowed_exts):
                continue
            abs_path = os.path.join(cur_root, fname)
            rel_path = os.path.relpath(abs_path, PROJECT_ROOT)
            yield abs_path, rel_path


def build_package():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ten_file = f"dong_bo_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.zip"
    zip_path = os.path.join(OUTPUT_DIR, ten_file)

    so_luong = {"tasks": 0, "templates": 0, "data": 0}
    thieu_thu_muc = []

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1) Hoạt Động (tasks/*.json, kể cả thư mục con)
        if os.path.isdir(TASKS_DIR):
            for abs_path, rel_path in _iter_files(TASKS_DIR, allowed_exts=(".json",)):
                zf.write(abs_path, rel_path)
                so_luong["tasks"] += 1
        else:
            thieu_thu_muc.append("tasks/")

        # 2) Ảnh mẫu (templates/*, kể cả thư mục con)
        if os.path.isdir(TEMPLATES_DIR):
            for abs_path, rel_path in _iter_files(TEMPLATES_DIR, allowed_exts=IMAGE_EXTS):
                zf.write(abs_path, rel_path)
                so_luong["templates"] += 1
        else:
            thieu_thu_muc.append("templates/")

        # 3) File cấu hình được chọn trong data/ (xem DATA_FILES_TO_INCLUDE)
        for fname in DATA_FILES_TO_INCLUDE:
            abs_path = os.path.join(DATA_DIR, fname)
            if os.path.exists(abs_path):
                zf.write(abs_path, os.path.join("data", fname))
                so_luong["data"] += 1

        # 4) File HƯỚNG DẪN kèm trong gói - để người nhận (hoặc chính mình ở
        # máy kia) biết gói này chứa gì / thiếu gì mà không cần đọc code.
        readme = _build_readme(so_luong)
        zf.writestr("DOC_TRUOC_KHI_GIAI_NEN.txt", readme)

    print("=" * 60)
    print(f"✔ Đã tạo gói đồng bộ: {zip_path}")
    print(f"   - Hoạt Động (tasks/*.json): {so_luong['tasks']} file")
    print(f"   - Ảnh mẫu (templates/*): {so_luong['templates']} file")
    print(f"   - File cấu hình (data/*.json): {so_luong['data']} file")
    if thieu_thu_muc:
        print(f"   ⚠ Không thấy thư mục: {', '.join(thieu_thu_muc)} (bỏ qua, không phải lỗi "
              f"nếu bạn chưa có Hoạt Động/ảnh nào thuộc loại đó).")
    print("\nMang file .zip trên sang máy kia rồi GIẢI NÉN ĐÈ THẲNG vào thư mục")
    print("gốc của dự án (chọn Yes/Replace nếu được hỏi ghi đè) là xong.")
    print("=" * 60)
    return zip_path


def _build_readme(so_luong):
    return (
        "GÓI ĐỒNG BỘ DASHBOARD - ADB-THTG\n"
        f"Tạo lúc: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        "\n"
        "CÁCH DÙNG: Giải nén file .zip này ĐÈ THẲNG vào thư mục gốc của dự án\n"
        "ở máy kia (thư mục đã có sẵn dashboard.py/main.py/adb.exe/OCR...).\n"
        "Chọn Yes/Replace nếu Windows hỏi có ghi đè file trùng tên không.\n"
        "KHÔNG cần chạy thêm script nào khác sau khi giải nén.\n"
        "\n"
        f"Gói này gồm:\n"
        f"  - {so_luong['tasks']} file Hoạt Động trong tasks/\n"
        f"  - {so_luong['templates']} ảnh mẫu trong templates/\n"
        f"  - {so_luong['data']} file cấu hình trong data/ "
        f"({', '.join(DATA_FILES_TO_INCLUDE)})\n"
        "\n"
        "KHÔNG đóng gói (cố ý, để không phá cấu hình riêng của máy kia):\n"
        "  - data/dashboard_settings.json (đường dẫn ldconsole.exe + gán giả lập\n"
        "    theo số thứ tự - khác nhau giữa 2 máy). Sau khi đồng bộ, mở Dashboard\n"
        "    ở máy kia và tự tick lại vài checkbox tổng (Tự Login/Xoay Vòng Tài\n"
        "    Khoản...) và chỉ lại đường dẫn ldconsole.exe nếu cần.\n"
        "  - data/window_geometry.json (vị trí/cỡ cửa sổ riêng theo màn hình từng máy)\n"
        "  - data/run_state_today.json (chỉ là trạng thái 'đã chạy tác vụ nào hôm\n"
        "    nay', tự sinh lại, không phải cấu hình)\n"
    )


if __name__ == "__main__":
    try:
        build_package()
    except Exception as e:
        print(f"✖ Lỗi khi đóng gói: {e}")
        sys.exit(1)
    if os.name == "nt":
        input("\nBấm Enter để đóng cửa sổ này...")

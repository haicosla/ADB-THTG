"""
dong_goi_dong_bo.py — Đóng gói các Hoạt Động (tasks/), ảnh mẫu (templates/)
và các file cấu hình cần thiết (data/*.json) thành ĐÚNG 1 file .zip duy
nhất, để chuyển sang máy khác và ĐỒNG BỘ lại danh mục Hoạt Động/Tài khoản/
Lịch hẹn giờ đang có trên máy này.

MỚI: CHỌN ĐỒNG BỘ GÌ (không còn bắt buộc phải đóng gói tất cả)
    Mỗi lần chạy, một hộp thoại có tick chọn sẽ hiện ra để bạn chọn NHÓM nào
    đưa vào gói .zip. Ví dụ chỉ cần đồng bộ Hoạt Động + Kịch bản, KHÔNG cần
    đồng bộ Lịch Hẹn Giờ và Tài khoản -> bấm nút "Chỉ Hoạt Động + Kịch bản"
    rồi "Đóng Gói". Những nhóm KHÔNG chọn sẽ không nằm trong gói, nên khi
    giải nén ở máy kia, dữ liệu tương ứng của máy kia được GIỮ NGUYÊN.

    Các nhóm (khoá dùng cho dòng lệnh ghi trong ngoặc):
      (kich_ban)          Kịch bản    - tasks/*.json (nội dung các Hoạt Động)
      (hoat_dong)         Tuỳ chỉnh Hoạt Động - task_registry.json (Tên hiển
                          thị/Mục/Thứ tự/Bật mặc định)
      (anh_mau)           Ảnh mẫu     - templates/
      (nhom_du_lieu)      Nhóm Dữ Liệu - data_groups.json (mặc định KHÔNG tick)
      (tai_khoan)         Tài khoản   - accounts/account_groups/
                          quick_login_groups .json
      (lich_hen_gio)      Lịch Hẹn Giờ - schedules.json
      (cai_dat_dashboard) Cài đặt Dashboard - dashboard_settings.json
                          (mặc định KHÔNG tick, xem cảnh báo bên dưới)

    Chạy không tham số = hiện hộp thoại chọn. Dòng lệnh (không hỏi):
        python dong_goi_dong_bo.py --preset hoat_dong_kich_ban
        python dong_goi_dong_bo.py --chon kich_ban,hoat_dong,anh_mau
        python dong_goi_dong_bo.py --preset day_du       (giống bản cũ)
        python dong_goi_dong_bo.py --console             (menu chữ thay hộp thoại)
        python dong_goi_dong_bo.py --liet-ke             (xem các nhóm/preset)

CÁCH DÙNG:
    1) Đặt file này (và Dong_Goi_Dong_Bo.bat đi kèm, nếu có) ngay cùng thư
       mục với dashboard.py/main.py (thư mục gốc của dự án).
    2) Bấm đúp Dong_Goi_Dong_Bo.bat (hoặc chạy `python dong_goi_dong_bo.py`
       trong terminal), tick chọn nhóm cần đồng bộ rồi bấm "Đóng Gói" - file
       .zip được tạo trong thư mục con "xuat_dong_bo/", tên có kèm ngày giờ
       để không đè lên gói đã xuất trước đó (dong_bo_2026-09-17_221530.zip
       chẳng hạn). Gói CHỌN MỘT PHẦN có tên bắt đầu bằng "dong_bo_mot_phan_"
       để không nhầm với gói đầy đủ.
    3) Copy file .zip đó sang máy kia (USB/Zalo/Google Drive/...).
    4) Ở máy kia: bung nén file .zip ĐÈ THẲNG vào thư mục gốc của dự án
       (thư mục đã có sẵn dashboard.py/main.py/adb.exe/OCR...) - chọn "Có/
       Yes/Replace" nếu Windows hỏi có ghi đè file trùng tên không. XONG,
       KHÔNG cần chạy thêm script nào khác - mở dashboard.py lên là thấy
       đúng phần đã đồng bộ.

GÓI .zip GIỮ NGUYÊN CẤU TRÚC THƯ MỤC (tasks/..., templates/..., data/...)
nên bung nén đè vào đúng thư mục gốc là file rơi đúng chỗ, không cần đổi
tên/di chuyển gì thêm.

LƯU Ý KHI CHỌN MỘT PHẦN:
  - Chỉ tick "Kịch bản" (không tick "Tuỳ chỉnh Hoạt Động"): máy kia tự nhận
    kịch bản mới với tên hiển thị/Mục mặc định (lấy từ tên file/thư mục
    con); những Hoạt Động đã có sẵn ở máy kia giữ nguyên tên/Mục/thứ tự.
  - Chỉ tick "Tuỳ chỉnh Hoạt Động" mà không có "Kịch bản": máy kia sẽ hiện
    thêm các dòng Hoạt Động chưa có file kịch bản (báo lỗi "không tìm thấy
    file" nếu bấm chạy) - nên tick cả hai.
  - Kịch bản dùng bước tìm ảnh (wait_image/if_image) cần đủ "Ảnh mẫu" ở máy
    kia - nên tick kèm nếu có ảnh mẫu mới.
  - Kịch bản dùng bước "Lấy Dữ Liệu (Nhóm)" cần "Nhóm Dữ Liệu" ở máy kia.

CHỦ Ý ĐÍCH THỊ KHÔNG BAO GIỜ ĐÓNG GÓI (để tránh phá cấu hình riêng của máy kia):
  - data/window_geometry.json  - vị trí/kích thước từng cửa sổ đã lưu
    riêng cho MÀN HÌNH của máy này (xem chú thích trong window_geometry.py:
    "file này KHÔNG nên đồng bộ/copy giữa các máy, vì mỗi máy có độ phân
    giải màn hình khác nhau").
  - data/run_state_today.json - chỉ là "đã chạy xong tác vụ nào hôm nay",
    không phải cấu hình, tự sinh lại khi chạy.
  - Mọi file *.bak/*.tmp (bản sao lưu tạm của paths.save_json) và
    __pycache__/ (bytecode Python, máy nào tự sinh máy đó).

MẶC ĐỊNH KHÔNG TICK (nhưng có thể tick tay nếu cần):
  - data/dashboard_settings.json - có chứa "ldconsole_path" (đường dẫn cài
    LDPlayer, THƯỜNG KHÁC NHAU giữa 2 máy) và bảng "shutdown_after_by_
    emulator"/"post_login_account_by_emulator" (gán theo SỐ THỨ TỰ giả lập
    - số này ở máy kia có thể trỏ nhầm sang giả lập khác nếu 2 máy không
    set giả lập giống hệt nhau). 3 tuỳ chọn checkbox chung (Tự Login/Xoay
    Vòng Tài Khoản/...) cũng nằm trong file này. Chỉ nên tick khi 2 máy đã
    set SỐ THỨ TỰ giả lập (index trong LDPlayer) giống hệt nhau; hoặc đổi
    biến INCLUDE_DASHBOARD_SETTINGS bên dưới thành True để nó luôn được tick
    sẵn trong gói "đầy đủ".
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

# Đổi thành True nếu 2 máy đã set SỐ THỨ TỰ giả lập giống hệt nhau và
# muốn đồng bộ luôn cả đường dẫn ldconsole.exe + gán giả lập/tài khoản của
# Lịch Hẹn Giờ - MẶC ĐỊNH False vì đây là trường hợp không phổ biến (rủi ro
# gán nhầm giả lập nếu 2 máy set khác số thứ tự). Nếu để False, vẫn có thể
# tick tay nhóm "Cài đặt Dashboard" trong hộp thoại chọn mỗi lần đóng gói.
INCLUDE_DASHBOARD_SETTINGS = False

# ---------------------------------------------------------------------------
# CÁC NHÓM CÓ THỂ CHỌN ĐỒNG BỘ: (khoá, tên hiển thị, mô tả ngắn)
# ---------------------------------------------------------------------------
NHOM_DONG_BO = [
    ("kich_ban", "Kịch bản",
     "Toàn bộ file tasks/*.json (kể cả thư mục con) - chính là nội dung các Hoạt Động."),
    ("hoat_dong", "Tuỳ chỉnh Hoạt Động",
     "task_registry.json - Tên hiển thị / Mục / Thứ tự / Bật mặc định đã đặt cho từng Hoạt Động."),
    ("anh_mau", "Ảnh mẫu",
     "Thư mục templates/ - ảnh dùng cho các bước wait_image / if_image."),
    ("nhom_du_lieu", "Nhóm Dữ Liệu",
     "data_groups.json - danh sách dùng cho bước 'Lấy Dữ Liệu (Nhóm)' trong kịch bản."),
    ("tai_khoan", "Tài khoản",
     "accounts.json + account_groups.json + quick_login_groups.json."),
    ("lich_hen_gio", "Lịch Hẹn Giờ",
     "schedules.json - giờ hẹn, giờ lặp lại và Hoạt Động/Tài khoản gán cho từng lịch."),
    ("cai_dat_dashboard", "Cài đặt Dashboard",
     "CẨN THẬN: dashboard_settings.json - đường dẫn ldconsole.exe + gán theo SỐ THỨ TỰ "
     "giả lập. Chỉ tick khi 2 máy set giả lập giống hệt nhau."),
]
_NHOM_KEYS = [k for k, _, _ in NHOM_DONG_BO]
_NHOM_TEN = {k: ten for k, ten, _ in NHOM_DONG_BO}
_NHOM_MOTA = {k: mo_ta for k, _, mo_ta in NHOM_DONG_BO}

# File trong data/ thuộc từng nhóm (nhóm không có ở đây thì không có file
# data/ - vd kich_ban chỉ có tasks/, anh_mau chỉ có templates/).
DATA_FILES_BY_NHOM = {
    "hoat_dong": ["task_registry.json"],
    "nhom_du_lieu": ["data_groups.json"],
    "tai_khoan": ["accounts.json", "account_groups.json", "quick_login_groups.json"],
    "lich_hen_gio": ["schedules.json"],
    "cai_dat_dashboard": ["dashboard_settings.json"],
}

# Nhóm được tick sẵn = ĐÚNG như hành vi cũ của file này (đóng gói tất cả,
# trừ dashboard_settings.json trừ khi INCLUDE_DASHBOARD_SETTINGS = True;
# Nhóm Dữ Liệu trước đây chưa từng được đóng gói nên vẫn để không tick).
NHOM_MAC_DINH = ["kich_ban", "hoat_dong", "anh_mau", "tai_khoan", "lich_hen_gio"]
if INCLUDE_DASHBOARD_SETTINGS:
    NHOM_MAC_DINH.append("cai_dat_dashboard")


def _data_files_cua(chon):
    """Danh sách file data/*.json thuộc các nhóm trong `chon` (đã chuẩn hoá)."""
    ket_qua = []
    for k in _NHOM_KEYS:
        if k in chon:
            ket_qua.extend(DATA_FILES_BY_NHOM.get(k, []))
    return ket_qua


# Các file cấu hình trong data/ được đóng gói khi chọn MẶC ĐỊNH (giữ tên biến
# cũ cho ai import/đọc lại - giá trị = đúng danh sách của gói "đầy đủ").
DATA_FILES_TO_INCLUDE = _data_files_cua(NHOM_MAC_DINH)

# Các lựa chọn nhanh (preset): khoá -> (tên hiển thị, danh sách nhóm)
PRESETS = {
    "day_du": ("Đầy đủ (như bản cũ)", list(NHOM_MAC_DINH)),
    "hoat_dong_kich_ban": ("Chỉ Hoạt Động + Kịch bản", ["kich_ban", "hoat_dong", "anh_mau"]),
    "chi_kich_ban": ("Chỉ Kịch bản + ảnh mẫu", ["kich_ban", "anh_mau"]),
}

# Đuôi file ảnh mẫu hợp lệ (khớp với capture_tools.py - luôn lưu .png,
# nhưng có thể có người tự thêm ảnh .jpg thủ công nên quét luôn cho chắc).
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp")

SKIP_SUFFIXES = (".bak", ".tmp")
SKIP_DIR_NAMES = {"__pycache__"}


def _chuan_hoa_chon(chon):
    """Chuẩn hoá danh sách nhóm được chọn: None = mặc định (như bản cũ);
    kiểm tra khoá hợp lệ, không rỗng; trả về list theo đúng thứ tự chuẩn."""
    if chon is None:
        return list(NHOM_MAC_DINH)
    if isinstance(chon, str):
        chon = [chon]
    chon = set(chon)
    la = sorted(chon - set(_NHOM_KEYS))
    if la:
        raise ValueError(f"Nhóm không hợp lệ: {', '.join(la)}. "
                         f"Các nhóm có sẵn: {', '.join(_NHOM_KEYS)}.")
    if not chon:
        raise ValueError("Chưa chọn nhóm nào để đồng bộ.")
    return [k for k in _NHOM_KEYS if k in chon]


def _canh_bao_chon(chon):
    """Các cảnh báo (nếu có) về tổ hợp nhóm đang chọn - chỉ để nhắc, không
    chặn việc đóng gói."""
    chon = set(chon)
    ds = []
    if "hoat_dong" in chon and "kich_ban" not in chon:
        ds.append("Tick 'Tuỳ chỉnh Hoạt Động' mà không có 'Kịch bản': máy kia sẽ hiện "
                  "thêm Hoạt Động chưa có file kịch bản.")
    if "kich_ban" in chon and "anh_mau" not in chon:
        ds.append("Không tick 'Ảnh mẫu': kịch bản có bước tìm ảnh mới sẽ không chạy đúng "
                  "nếu máy kia chưa có ảnh đó.")
    if "cai_dat_dashboard" in chon:
        ds.append("'Cài đặt Dashboard' ghi đè đường dẫn ldconsole.exe và gán theo số thứ tự "
                  "giả lập của máy kia - chỉ nên dùng khi 2 máy set giống hệt.")
    return ds


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


def build_package(chon=None):
    """Đóng gói các nhóm trong `chon` (list khoá nhóm, xem NHOM_DONG_BO).
    `chon=None` = mặc định như bản cũ (đóng gói tất cả nhóm trong
    NHOM_MAC_DINH). Trả về đường dẫn file .zip vừa tạo."""
    chon = _chuan_hoa_chon(chon)
    la_day_du = (chon == _chuan_hoa_chon(None))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tien_to = "dong_bo_" if la_day_du else "dong_bo_mot_phan_"
    ten_file = f"{tien_to}{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.zip"
    zip_path = os.path.join(OUTPUT_DIR, ten_file)

    so_luong = {"tasks": 0, "templates": 0, "data": 0}
    thieu_thu_muc = []
    data_da_dong_goi = []
    data_thieu_file = []

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1) Kịch bản / Hoạt Động (tasks/*.json, kể cả thư mục con)
        if "kich_ban" in chon:
            if os.path.isdir(TASKS_DIR):
                for abs_path, rel_path in _iter_files(TASKS_DIR, allowed_exts=(".json",)):
                    zf.write(abs_path, rel_path)
                    so_luong["tasks"] += 1
            else:
                thieu_thu_muc.append("tasks/")

        # 2) Ảnh mẫu (templates/*, kể cả thư mục con)
        if "anh_mau" in chon:
            if os.path.isdir(TEMPLATES_DIR):
                for abs_path, rel_path in _iter_files(TEMPLATES_DIR, allowed_exts=IMAGE_EXTS):
                    zf.write(abs_path, rel_path)
                    so_luong["templates"] += 1
            else:
                thieu_thu_muc.append("templates/")

        # 3) File cấu hình thuộc các nhóm được chọn trong data/
        for fname in _data_files_cua(chon):
            abs_path = os.path.join(DATA_DIR, fname)
            if os.path.exists(abs_path):
                zf.write(abs_path, os.path.join("data", fname))
                so_luong["data"] += 1
                data_da_dong_goi.append(fname)
            else:
                data_thieu_file.append(fname)

        # 4) File HƯỚNG DẪN kèm trong gói - để người nhận (hoặc chính mình ở
        # máy kia) biết gói này chứa gì / thiếu gì mà không cần đọc code.
        readme = _build_readme(so_luong, chon, data_da_dong_goi)
        zf.writestr("DOC_TRUOC_KHI_GIAI_NEN.txt", readme)

    print("=" * 60)
    print(f"✔ Đã tạo gói đồng bộ: {zip_path}")
    print("   Các nhóm đã chọn: " + ", ".join(_NHOM_TEN[k] for k in chon))
    if "kich_ban" in chon:
        print(f"   - Kịch bản (tasks/*.json): {so_luong['tasks']} file")
    if "anh_mau" in chon:
        print(f"   - Ảnh mẫu (templates/*): {so_luong['templates']} file")
    if data_da_dong_goi or data_thieu_file or _data_files_cua(chon):
        print(f"   - File cấu hình (data/*.json): {so_luong['data']} file"
              + (f" ({', '.join(data_da_dong_goi)})" if data_da_dong_goi else ""))
    khong_chon = [k for k in _NHOM_KEYS if k not in chon]
    if khong_chon:
        print("   Không đồng bộ lần này (máy kia giữ nguyên): "
              + ", ".join(_NHOM_TEN[k] for k in khong_chon))
    if thieu_thu_muc:
        print(f"   ⚠ Không thấy thư mục: {', '.join(thieu_thu_muc)} (bỏ qua, không phải lỗi "
              f"nếu bạn chưa có Hoạt Động/ảnh nào thuộc loại đó).")
    if data_thieu_file:
        print(f"   ⚠ Chưa có file trong data/: {', '.join(data_thieu_file)} (bỏ qua, không "
              f"phải lỗi nếu máy này chưa tạo dữ liệu loại đó).")
    for cb in _canh_bao_chon(chon):
        print(f"   ⚠ Lưu ý: {cb}")
    print("\nMang file .zip trên sang máy kia rồi GIẢI NÉN ĐÈ THẲNG vào thư mục")
    print("gốc của dự án (chọn Yes/Replace nếu được hỏi ghi đè) là xong.")
    print("=" * 60)
    return zip_path


def _build_readme(so_luong, chon=None, data_files=None):
    if chon is None:
        chon = list(NHOM_MAC_DINH)
    if data_files is None:
        data_files = DATA_FILES_TO_INCLUDE
    # "Cài đặt Dashboard" nếu không chọn thì đã được giải thích ở khối
    # "KHÔNG đóng gói" bên dưới, không lặp lại ở đây.
    khong_chon = [k for k in _NHOM_KEYS if k not in chon and k != "cai_dat_dashboard"]

    dong = [
        "GÓI ĐỒNG BỘ DASHBOARD - ADB-THTG",
        f"Tạo lúc: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        "",
        "CÁCH DÙNG: Giải nén file .zip này ĐÈ THẲNG vào thư mục gốc của dự án",
        "ở máy kia (thư mục đã có sẵn dashboard.py/main.py/adb.exe/OCR...).",
        "Chọn Yes/Replace nếu Windows hỏi có ghi đè file trùng tên không.",
        "KHÔNG cần chạy thêm script nào khác sau khi giải nén.",
        "",
        "Gói này gồm:",
    ]
    if "kich_ban" in chon:
        dong.append(f"  - {so_luong['tasks']} file kịch bản Hoạt Động trong tasks/")
    if "anh_mau" in chon:
        dong.append(f"  - {so_luong['templates']} ảnh mẫu trong templates/")
    if _data_files_cua(chon):
        dong.append(f"  - {so_luong['data']} file cấu hình trong data/ ({', '.join(data_files)})")
    dong.append("  (Nhóm đã chọn: " + ", ".join(_NHOM_TEN[k] for k in chon) + ")")
    dong.append("")

    if khong_chon:
        dong.append("KHÔNG đồng bộ LẦN NÀY (không nằm trong gói -> máy kia GIỮ NGUYÊN dữ liệu của nó):")
        for k in khong_chon:
            dong.append(f"  - {_NHOM_TEN[k]}: {_NHOM_MOTA[k]}")
        dong.append("")

    dong += [
        "KHÔNG đóng gói (cố ý, để không phá cấu hình riêng của máy kia):",
        "  - data/window_geometry.json (vị trí/cỡ cửa sổ riêng theo màn hình từng máy)",
        "  - data/run_state_today.json (chỉ là trạng thái 'đã chạy tác vụ nào hôm",
        "    nay', tự sinh lại, không phải cấu hình)",
    ]
    if "cai_dat_dashboard" not in chon:
        dong += [
            "  - data/dashboard_settings.json (đường dẫn ldconsole.exe + gán giả lập",
            "    theo số thứ tự - khác nhau giữa 2 máy). Sau khi đồng bộ, mở Dashboard",
            "    ở máy kia và tự tick lại vài checkbox tổng (Tự Login/Xoay Vòng Tài",
            "    Khoản...) và chỉ lại đường dẫn ldconsole.exe nếu cần.",
        ]
    return "\n".join(dong) + "\n"


# ---------------------------------------------------------------------------
# CHỌN NHÓM ĐỒNG BỘ: hộp thoại (Tkinter) hoặc menu chữ (dự phòng)
# ---------------------------------------------------------------------------
class HopThoaiChon:
    """Hộp thoại tick chọn nhóm cần đồng bộ. Sau khi đóng, `ket_qua` là list
    khoá nhóm đã chọn (hoặc None nếu bấm Huỷ/đóng cửa sổ)."""

    def __init__(self, mac_dinh=None):
        import tkinter as tk
        from tkinter import ttk, messagebox
        self._tk, self._ttk, self._mb = tk, ttk, messagebox

        self.ket_qua = None
        self.win = tk.Tk()
        self.win.title("Đóng Gói Đồng Bộ - chọn đồng bộ gì")
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.huy)

        chon_ban_dau = set(_chuan_hoa_chon(mac_dinh))
        font_chuan = ("Segoe UI", 10)
        font_dam = ("Segoe UI", 10, "bold")

        khung = ttk.Frame(self.win, padding=14)
        khung.grid(row=0, column=0, sticky="nsew")

        ttk.Label(khung, text="Chọn những gì cần đưa vào gói đồng bộ:",
                  font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")

        # Hàng nút chọn nhanh
        f_preset = ttk.Frame(khung)
        f_preset.grid(row=1, column=0, sticky="w", pady=(8, 6))
        ttk.Label(f_preset, text="Chọn nhanh:", font=font_chuan).pack(side="left", padx=(0, 6))
        for khoa, (ten, _ds) in PRESETS.items():
            ttk.Button(f_preset, text=ten,
                       command=lambda k=khoa: self.chon_preset(k)).pack(side="left", padx=3)

        # Danh sách nhóm: mỗi nhóm 1 ô tick + dòng mô tả nhỏ bên dưới
        f_ds = ttk.LabelFrame(khung, text=" Nhóm dữ liệu ", padding=(10, 6))
        f_ds.grid(row=2, column=0, sticky="ew")
        self.bien = {}
        for i, (khoa, ten, mo_ta) in enumerate(NHOM_DONG_BO):
            var = tk.BooleanVar(value=(khoa in chon_ban_dau))
            self.bien[khoa] = var
            ttk.Checkbutton(f_ds, text=ten, variable=var,
                            command=self._cap_nhat_canh_bao).grid(
                row=i * 2, column=0, sticky="w", pady=(6, 0))
            ttk.Label(f_ds, text=mo_ta, wraplength=560, foreground="#666666",
                      font=("Segoe UI", 9)).grid(
                row=i * 2 + 1, column=0, sticky="w", padx=(24, 0))

        self.lbl_canh_bao = ttk.Label(khung, text="", wraplength=580, foreground="#b45f06",
                                      font=("Segoe UI", 9), justify="left")
        self.lbl_canh_bao.grid(row=3, column=0, sticky="w", pady=(8, 0))

        f_nut = ttk.Frame(khung)
        f_nut.grid(row=4, column=0, sticky="e", pady=(12, 0))
        ttk.Button(f_nut, text="Huỷ", command=self.huy).pack(side="right", padx=(6, 0))
        self.btn_ok = ttk.Button(f_nut, text="📦 Đóng Gói", command=self.dong_goi)
        self.btn_ok.pack(side="right")

        self._cap_nhat_canh_bao()
        self.win.bind("<Escape>", lambda _e: self.huy())
        # Đưa cửa sổ lên trên cùng (khi chạy từ .bat cửa sổ dễ bị nằm dưới)
        self.win.attributes("-topmost", True)
        self.win.after(300, lambda: self.win.attributes("-topmost", False))

    def _dang_chon(self):
        return [k for k in _NHOM_KEYS if self.bien[k].get()]

    def _cap_nhat_canh_bao(self):
        chon = self._dang_chon()
        self.lbl_canh_bao.config(
            text="\n".join("⚠ " + c for c in _canh_bao_chon(chon)) if chon else "")

    def chon_preset(self, khoa):
        ds = set(PRESETS[khoa][1])
        for k, var in self.bien.items():
            var.set(k in ds)
        self._cap_nhat_canh_bao()

    def dong_goi(self):
        chon = self._dang_chon()
        if not chon:
            self._mb.showwarning("Chưa chọn gì", "Hãy tick ít nhất 1 nhóm để đồng bộ.",
                                 parent=self.win)
            return
        self.ket_qua = chon
        self.win.destroy()

    def huy(self):
        self.ket_qua = None
        self.win.destroy()

    def chay(self):
        self.win.mainloop()
        return self.ket_qua


def _hoi_chon_console(mac_dinh=None):
    """Menu chữ dự phòng (khi không mở được hộp thoại hoặc dùng --console).
    Trả về list nhóm đã chọn, hoặc None nếu người dùng thoát."""
    chon = set(_chuan_hoa_chon(mac_dinh))
    preset_keys = list(PRESETS)
    while True:
        print("\n" + "=" * 60)
        print("CHỌN ĐỒNG BỘ GÌ  (gõ số để bật/tắt, có thể gõ nhiều số: vd 5 6)")
        for i, k in enumerate(_NHOM_KEYS, 1):
            print(f"  {i}. [{'x' if k in chon else ' '}] {_NHOM_TEN[k]}")
            print(f"         {_NHOM_MOTA[k]}")
        print("Chọn nhanh: " + " | ".join(f"p{i}={PRESETS[k][0]}"
                                          for i, k in enumerate(preset_keys, 1)))
        print("Enter = đóng gói   |   q = thoát")
        try:
            s = input("> ").strip().lower()
        except EOFError:
            return None
        if s in ("q", "quit", "thoat", "thoát"):
            return None
        if s == "":
            if chon:
                return [k for k in _NHOM_KEYS if k in chon]
            print("Chưa chọn nhóm nào.")
            continue
        for tok in s.replace(",", " ").split():
            if tok.startswith("p") and tok[1:].isdigit() and 1 <= int(tok[1:]) <= len(preset_keys):
                chon = set(PRESETS[preset_keys[int(tok[1:]) - 1]][1])
            elif tok.isdigit() and 1 <= int(tok) <= len(_NHOM_KEYS):
                k = _NHOM_KEYS[int(tok) - 1]
                chon.symmetric_difference_update({k})
            else:
                print(f"Không hiểu '{tok}', bỏ qua.")
        for cb in _canh_bao_chon(chon):
            print(f"⚠ {cb}")


def hoi_chon_nhom(mac_dinh=None, dung_console=False):
    """Hỏi người dùng chọn nhóm đồng bộ: hộp thoại nếu mở được, không thì
    menu chữ. Trả về list khoá nhóm hoặc None nếu huỷ."""
    if not dung_console:
        try:
            return HopThoaiChon(mac_dinh).chay()
        except Exception:  # không có tkinter / không có màn hình -> menu chữ
            pass
    return _hoi_chon_console(mac_dinh)


def _in_danh_sach_nhom():
    print("CÁC NHÓM (dùng với --chon, cách nhau dấu phẩy):")
    for k in _NHOM_KEYS:
        mac_dinh = " (tick sẵn)" if k in NHOM_MAC_DINH else ""
        print(f"  {k:<18} {_NHOM_TEN[k]}{mac_dinh}\n  {'':<18} {_NHOM_MOTA[k]}")
    print("\nCÁC PRESET (dùng với --preset):")
    for k, (ten, ds) in PRESETS.items():
        print(f"  {k:<20} {ten}: {', '.join(ds)}")


def _doc_tham_so(argv):
    import argparse
    p = argparse.ArgumentParser(
        description="Đóng gói dữ liệu Dashboard thành 1 file .zip để đồng bộ sang máy khác. "
                    "Không truyền --chon/--preset thì hiện hộp thoại để tick chọn.")
    p.add_argument("--chon", help="Các nhóm cần đóng gói, cách nhau bằng dấu phẩy "
                                  "(vd kich_ban,hoat_dong,anh_mau). Xem --liet-ke.")
    p.add_argument("--preset", choices=list(PRESETS), help="Chọn nhanh 1 bộ nhóm dựng sẵn.")
    p.add_argument("--console", action="store_true",
                   help="Dùng menu chữ thay cho hộp thoại tick chọn.")
    p.add_argument("--liet-ke", action="store_true", help="Liệt kê các nhóm/preset rồi thoát.")
    return p.parse_args(argv)


def main(argv=None):
    args = _doc_tham_so(sys.argv[1:] if argv is None else argv)
    if args.liet_ke:
        _in_danh_sach_nhom()
        return None
    if args.chon:
        chon = [x.strip() for x in args.chon.split(",") if x.strip()]
    elif args.preset:
        chon = PRESETS[args.preset][1]
    else:
        chon = hoi_chon_nhom(dung_console=args.console)
        if chon is None:
            print("Đã huỷ - không tạo gói nào.")
            return None
    return build_package(chon)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"✖ Lỗi khi đóng gói: {e}")
        sys.exit(1)
    if os.name == "nt":
        input("\nBấm Enter để đóng cửa sổ này...")

"""
Danh mục Tác Vụ (Task Registry) - CẦU NỐI giữa 2 chương trình:

  1) LD Macro Studio (gui.py)  -> nơi TẠO từng tác vụ (ghi F7 hoặc soạn thủ
     công), lưu thành file JSON trong tasks/.

  2) Auto Runner Dashboard (dashboard.py) -> tự QUÉT toàn bộ file .json
     trong tasks/ (kể cả thư mục con) để dựng danh sách checklist theo
     từng Mục và chạy các tác vụ được chọn.

TRƯỚC ĐÂY bắt buộc phải bấm "📋 Đăng Ký Tác Vụ" (mở RegisterTaskDialog ở
gui_dialogs_data.py) để ghi 1 dòng mô tả vào task_registry.json thì
Dashboard mới thấy được tác vụ đó. GIỜ KHÔNG CÒN BẮT BUỘC NỮA: chỉ cần
lưu file kịch bản .json vào tasks/ là Dashboard tự nhận làm 1 Hoạt Động
ngay từ lần quét kế tiếp (xem load_registry()/_scan_task_files() bên
dưới) - "Đăng Ký Tác Vụ" giờ chỉ còn là cách TUỲ CHỌN để đặt Tên hiển thị/
Mục/Thứ tự/Bật mặc định đẹp hơn tên file thô, không phải điều kiện để
tác vụ xuất hiện.

Vì cả 2 chương trình đều import module này, khi đổi định dạng file thì chỉ
cần sửa 1 chỗ duy nhất.
"""
import json
import os
import re

import paths

REGISTRY_PATH = paths.resolve_data_path("task_registry.json")

# Thư mục chứa các file kịch bản (.json) do LD Macro Studio tạo ra -
# _scan_task_files() quét TOÀN BỘ file .json ở đây (kể cả thư mục con) để
# tự dựng Hoạt Động, không cần đăng ký thủ công.
TASKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks")


def _prettify_name(stem):
    """Tên hiển thị GỢI Ý cho 1 Hoạt Động tự nhận từ tên file (chưa từng
    đăng ký/đổi tên thủ công) - vd 'dagacay_like' -> 'Dagacay Like'. Chỉ
    là mặc định ban đầu; đăng ký thủ công (RegisterTaskDialog) vẫn có thể
    đè lên bằng 1 Tên hiển thị đẹp hơn bất kỳ lúc nào."""
    ten = stem.replace("_", " ").replace("-", " ").strip()
    return ten.title() if ten else stem


def _scan_task_files(tasks_dir=TASKS_DIR):
    """Quét TOÀN BỘ file .json trong `tasks_dir` (kể cả thư mục con) và tự
    dựng 1 entry MẶC ĐỊNH cho MỖI file tìm thấy - trả về dict {id: entry}.

    - File nằm TRỰC TIẾP trong tasks/ -> Mục 'Chưa phân loại'.
    - File nằm trong 1 thư mục con của tasks/ -> lấy TÊN thư mục con làm
      Mục, để tự nhóm nhiều kịch bản theo Mục mà không cần đăng ký từng
      cái (vd tasks/da_ga/xxx.json -> Mục 'Da Ga').
    - ID vẫn sinh từ TÊN FILE giống hệt make_task_id() như trước đây, để
      KHÔNG đổi hành vi của các ID đặc biệt Dashboard tự tìm theo tên
      (auto_login/account_login/account_logout...).
    - 2 file trùng tên (id trùng) ở 2 thư mục khác nhau: giữ file gặp
      TRƯỚC theo thứ tự quét (bảng chữ cái), bỏ qua file trùng còn lại -
      nên đặt tên file duy nhất trong toàn bộ tasks/ để tránh nhầm lẫn."""
    found = {}
    if not os.path.isdir(tasks_dir):
        return found
    order_counters = {}
    for root, _dirs, files in sorted(os.walk(tasks_dir)):
        rel_dir = os.path.relpath(root, tasks_dir)
        muc = "Chưa phân loại" if rel_dir in (".", "") else _prettify_name(os.path.basename(rel_dir))
        for fname in sorted(files):
            if not fname.lower().endswith(".json"):
                continue
            file_json = os.path.join(root, fname)
            task_id = make_task_id(file_json)
            if task_id in found:
                continue
            order_counters[muc] = order_counters.get(muc, 0) + 1
            found[task_id] = {
                "id": task_id,
                "ten_hien_thi": _prettify_name(task_id),
                "muc": muc,
                "thu_tu": order_counters[muc],
                "mac_dinh_bat": True,
                "file_json": file_json,
            }
    return found


def _task_file_exists(file_json):
    """True nếu file kịch bản `file_json` (tuyệt đối HOẶC tương đối so với
    thư mục chương trình) còn tồn tại trên đĩa."""
    if not file_json:
        return False
    if os.path.isfile(file_json):
        return True
    if not os.path.isabs(file_json):
        return os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), file_json))
    return False


def manual_file_states(path=REGISTRY_PATH):
    """Trạng thái tồn tại file của các entry đã lưu trong task_registry.json
    (chỉ để Dashboard nhận ra khi 1 file NGOÀI tasks/ bị xoá/đổi tên - file
    trong tasks/ đã được theo dõi qua _scan_task_files). Không bao giờ ném lỗi."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ()
    if not isinstance(data, list):
        return ()
    return tuple(sorted(
        (str(m.get("id") or make_task_id(m.get("file_json", ""))), _task_file_exists(m.get("file_json")))
        for m in data if isinstance(m, dict)
    ))


def load_registry(path=REGISTRY_PATH, tasks_dir=TASKS_DIR, warnings_out=None):
    """Dựng Danh mục Tác Vụ TỰ ĐỘNG từ toàn bộ file .json trong tasks_dir/
    (xem _scan_task_files()), rồi ĐÈ (overlay) các tuỳ chỉnh (Tên hiển
    thị/Mục/Thứ tự/Bật mặc định) đã lưu trước đó trong task_registry.json
    lên trên - để những Hoạt Động đã đăng ký/đổi tên thủ công từ trước
    KHÔNG bị mất tuỳ chỉnh khi chuyển sang cơ chế tự quét này.

    KHÔNG CÒN bắt buộc phải bấm '📋 Đăng Ký Tác Vụ' nữa - chỉ cần lưu file
    kịch bản (.json) vào tasks/ (hoặc 1 thư mục con của tasks/) là
    Dashboard tự nhận làm 1 Hoạt Động ngay từ lần quét kế tiếp. Luôn trả
    về list (rỗng nếu tasks/ chưa có file .json nào)."""
    auto = _scan_task_files(tasks_dir)

    manual = []
    data, warning = paths.load_json_with_recovery(path, [])
    if warning and warnings_out is not None:
        warnings_out.append(warning)
    if isinstance(data, list):
        manual = data

    for m in manual:
        task_id = m.get("id") or make_task_id(m.get("file_json", ""))
        if task_id in auto:
            # File tương ứng vẫn còn trong tasks/ - giữ nguyên file_json
            # tự quét được (luôn đúng chỗ thật của file), chỉ đè các tuỳ
            # chỉnh hiển thị đã lưu trước đó lên entry tự động.
            entry = auto[task_id]
            for key in ("ten_hien_thi", "muc", "thu_tu", "mac_dinh_bat"):
                if key in m:
                    entry[key] = m[key]
        elif _task_file_exists(m.get("file_json")):
            # File nằm NGOÀI tasks/ nhưng vẫn còn trên đĩa (đăng ký thủ công
            # từ đường dẫn khác) - giữ lại như trước.
            auto[task_id] = m
        # else: entry đã đăng ký nhưng FILE KỊCH BẢN KHÔNG CÒN (bị xoá hoặc
        # đổi tên) -> BỎ, không hiện Hoạt Động "ma". Trước đây vẫn giữ lại
        # nên xoá/đổi tên file .json mà danh sách Dashboard không cập nhật
        # (đổi tên còn hiện cả tên cũ lẫn tên mới). Entry cũ vẫn nằm trong
        # task_registry.json; nếu file được khôi phục thì tuỳ chỉnh quay lại.

    return list(auto.values())


def save_registry(entries, path=REGISTRY_PATH):
    paths.save_json(path, entries)


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


# ================= ĐỔI TÊN FILE KỊCH BẢN (đồng bộ với Tên hiển thị) =================
# ID của 1 Hoạt Động = tên file (không đuôi) nên đổi tên file = đổi ID. Các ID
# dưới đây được code Dashboard TÌM THEO TÊN FILE (Tự Login, Xoay Vòng Tài
# Khoản, Cài Đặt Shop, các nút nhanh) - đổi tên file sẽ làm hỏng chức năng
# tương ứng nên '🔀 Sắp Xếp Hành Động' chỉ đổi Tên hiển thị cho các ID này.
RESERVED_TASK_IDS = frozenset({
    "auto_login", "account_login", "account_logout", "cai_dat_shop",
    "setup_nguoi_moi", "quet_xe", "uid_like",
})

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def slugify_task_stem(display_name):
    """Tên file (không đuôi) sinh từ Tên hiển thị người dùng gõ: bỏ ký tự
    Windows không cho phép, khoảng trắng -> '_', giữ nguyên chữ có dấu.
    Trả về '' nếu không còn gì dùng được. Không để tên bắt đầu bằng
    '__sys__' (tiền tố dành riêng của Hành động hệ thống; 'GROUP:' đã bị bỏ vì có dấu ':')."""
    ten = _INVALID_FILENAME_CHARS.sub(" ", str(display_name or ""))
    ten = re.sub(r"\s+", "_", ten.strip()).strip("._")
    if ten.lower().startswith("__sys__"):
        ten = ten.lstrip("_")
    return ten


def _resolve_task_path(file_json):
    if os.path.isabs(file_json) or os.path.isfile(file_json):
        return file_json
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), file_json)


def rename_task_file(file_json, new_stem):
    """Đổi tên file kịch bản `file_json` thành `<new_stem>.json` (cùng thư mục,
    giữ đuôi cũ). Trả về đường dẫn MỚI (cùng kiểu tuyệt đối/tương đối với
    `file_json`). Ném FileNotFoundError/FileExistsError/OSError nếu không đổi
    được - khi đó file cũ còn nguyên, không đổi gì."""
    real_old = _resolve_task_path(file_json)
    if not os.path.isfile(real_old):
        raise FileNotFoundError(f"Không thấy file kịch bản: {file_json}")
    ext = os.path.splitext(real_old)[1] or ".json"
    new_file_json = os.path.join(os.path.dirname(file_json), new_stem + ext)
    real_new = os.path.join(os.path.dirname(real_old), new_stem + ext)
    if os.path.normcase(os.path.abspath(real_new)) == os.path.normcase(os.path.abspath(real_old)):
        if os.path.basename(real_new) != os.path.basename(real_old):
            # Chỉ khác HOA/thường (Windows coi là cùng file) - đổi qua tên tạm.
            tmp = real_old + ".__rename_tmp__"
            os.replace(real_old, tmp)
            os.replace(tmp, real_new)
        return new_file_json
    if os.path.exists(real_new):
        raise FileExistsError(f"Đã có file {os.path.basename(real_new)} trong thư mục này.")
    os.rename(real_old, real_new)
    return new_file_json


def replace_ids(id_list, mapping):
    """Thay id cũ -> mới trong 1 list id (giữ nguyên thứ tự/lặp). Trả về
    (list mới, số phần tử đã đổi). Phần tử không phải chuỗi giữ nguyên."""
    if not isinstance(id_list, list):
        return id_list, 0
    out, n = [], 0
    for x in id_list:
        if isinstance(x, str) and x in mapping:
            out.append(mapping[x])
            n += 1
        else:
            out.append(x)
    return out, n

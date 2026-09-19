"""
scheduler.py — Lưu trữ & tính toán LỊCH CHẠY TỰ ĐỘNG (hẹn giờ) cho
Dashboard. Module này CHỈ lo phần "dữ liệu + tính đến giờ chưa" (giống
task_registry.py / account_manager.py) - phần THỰC THI (tự bật giả lập,
đăng nhập, chạy các Hoạt Động) nằm ở dashboard.py vì cần dùng chung
EmulatorManager / LogicEngine / ADBHelper / WindowFinder đã có sẵn ở đó.

MỖI LỊCH (1 phần tử trong schedules.json) LÀ 1 DICT:
    {
        "id": "lich_xxxx",
        "ten": "Ca sáng 7h",
        "bat": true,                  # bỏ tick = tạm ngưng, không tự chạy
        "gio_hen": "07:00",            # GIỜ HẸN (hh:mm) - mốc chạy LẦN ĐẦU
                                        # tiên. Các lần sau tính từ
                                        # lan_chay_luc + interval_hours (xem
                                        # bên dưới).
        "interval_hours": 24,          # GIỜ LẶP LẠI - cứ cách nhau bấy
                                        # nhiêu giờ lại chạy tiếp. Muốn
                                        # "hằng ngày" thì để 24 (24h sau vẫn
                                        # đúng giờ đó trong ngày). Muốn "mỗi
                                        # 4 tiếng" thì để 4. Có thể để số lẻ
                                        # (vd 0.5 = mỗi 30 phút) để test.
        "hoat_dong_ids": ["id1", ...], # danh sách id Hoạt Động (task_registry)
        "tai_khoan_ids": ["tk_1", ...],# danh sách id Tài Khoản (account_manager)
        "lan_chay_ngay": "2026-09-13", # ngày (YYYY-MM-DD) lần TRIGGER gần nhất
                                        # (chỉ để hiển thị/tương thích cũ)
        "lan_chay_luc": "2026-09-13T07:00:05"  # ISO timestamp lần TRIGGER
                                        # gần nhất - dùng để tính mốc kế
                                        # tiếp (lan_chay_luc + interval_hours)
    }

VÌ SAO GỘP "Hằng ngày" + "Mỗi N giờ" THÀNH 1 MÔ HÌNH DUY NHẤT
(giờ hẹn + giờ lặp lại):
Bản trước bắt chọn 1 trong 2 loại lịch riêng biệt ("daily" chỉ nhập được
giờ cố định, "interval" chỉ nhập được số giờ lặp mà KHÔNG neo theo giờ
nào) - không tạo được lịch kiểu "chạy lần đầu lúc 7h rồi cứ thế lặp lại
mỗi 6 tiếng". Theo yêu cầu người dùng: chỉ cần đúng 2 ô "giờ hẹn" (mốc
chạy lần đầu) và "giờ lặp lại" (khoảng cách giữa các lần chạy sau đó) -
lịch "hằng ngày" chỉ là trường hợp đặc biệt khi giờ lặp lại = 24.

VÌ SAO GHI lan_chay_* NGAY KHI TRIGGER (không chờ chạy xong):
1 lượt chạy (đăng xuất - đăng nhập - chạy Hoạt Động) có thể mất vài phút
tới vài chục phút. Dashboard kiểm tra lịch mỗi ~20s (xem
dashboard.py::_check_schedules) - nếu chờ tới lúc CHẠY XONG mới ghi nhận
thì trong lúc đang chạy dở, is_due() sẽ tiếp tục trả về True liên tục (vì
lan_chay_luc chưa cập nhật) -> bị trigger lại chồng chéo nhiều lần. Ghi
ngay khi quyết định trigger giải quyết dứt điểm việc này.
"""
import json
import os
import time
import uuid
from datetime import datetime, timedelta

import paths

SCHEDULES_PATH = paths.resolve_data_path("schedules.json")


def _migrate_entry(entry):
    """Chuyển 1 lịch định dạng CŨ (loai='daily' + 'gio', hoặc loai='interval'
    không có giờ neo) sang định dạng MỚI (gio_hen + interval_hours), để các
    lịch đã lưu từ bản trước không bị mất/vỡ khi mở lại app."""
    if not isinstance(entry, dict):
        return entry
    if "gio_hen" in entry and "interval_hours" in entry:
        entry.pop("loai", None)
        entry.pop("gio", None)
        return entry

    loai = entry.get("loai")
    if loai == "daily":
        entry["gio_hen"] = entry.get("gio", "07:00")
        entry["interval_hours"] = 24
    elif loai == "interval":
        # Lịch "Mỗi N giờ" bản cũ không có giờ neo - dùng giờ hiện tại lúc
        # mở app làm mốc hiển thị, không ảnh hưởng is_due() vì đã có
        # lan_chay_luc từ trước (nếu có) sẽ được is_due() ưu tiên dùng.
        entry["gio_hen"] = entry.get("gio") or time.strftime("%H:%M")
        entry["interval_hours"] = entry.get("interval_hours", 4)
    else:
        entry.setdefault("gio_hen", entry.get("gio", "07:00"))
        entry.setdefault("interval_hours", entry.get("interval_hours", 24))
    entry.pop("loai", None)
    entry.pop("gio", None)
    return entry


def load_schedules(path=SCHEDULES_PATH):
    """Đọc toàn bộ danh sách lịch. Luôn trả về list (rỗng nếu chưa có file
    hoặc file lỗi định dạng). Tự động chuyển các lịch định dạng cũ sang
    định dạng mới (xem _migrate_entry)."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [_migrate_entry(e) for e in data]
    except Exception:
        pass
    return []


def save_schedules(entries, path=SCHEDULES_PATH):
    paths.save_json(path, entries)


def new_schedule_id():
    return f"lich_{uuid.uuid4().hex[:8]}"


def upsert_schedule(entries, entry):
    """Thêm mới nếu chưa có id trùng, ngược lại cập nhật tại chỗ. Trả về entries."""
    for i, e in enumerate(entries):
        if e.get("id") == entry.get("id"):
            entries[i] = entry
            return entries
    entries.append(entry)
    return entries


def remove_schedule(entries, schedule_id):
    return [e for e in entries if e.get("id") != schedule_id]


def _today_key():
    return time.strftime("%Y-%m-%d")


def _parse_gio_hen(entry):
    try:
        hh, mm = [int(x) for x in entry.get("gio_hen", "07:00").strip().split(":")]
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError
        return hh, mm
    except Exception:
        return 7, 0


def _parse_interval_hours(entry):
    try:
        hours = float(entry.get("interval_hours", 24))
    except Exception:
        hours = 24
    return hours if hours > 0 else 24


def hours_to_hhmm(hours):
    """Chuyển số giờ (float, lưu nội bộ) sang chuỗi hh:mm để HIỂN THỊ/NHẬP
    trong ô 'Lặp lại', vd 4.5 -> '04:30', 0.5 -> '00:30'."""
    try:
        hours = float(hours)
    except Exception:
        hours = 24
    if hours < 0:
        hours = 0
    total_minutes = round(hours * 60)
    hh, mm = divmod(total_minutes, 60)
    return f"{hh:02d}:{mm:02d}"


def hhmm_to_hours(text):
    """Chuyển chuỗi hh:mm người dùng nhập ở ô 'Lặp lại' (vd '04:30') sang số
    giờ float để lưu nội bộ (vd 4.5). Ném ValueError với thông báo phù hợp
    nếu định dạng sai hoặc giá trị <= 0."""
    text = (text or "").strip()
    parts = text.split(":")
    if len(parts) != 2:
        raise ValueError(f"'{text}' không đúng định dạng hh:mm")
    try:
        hh, mm = int(parts[0]), int(parts[1])
    except Exception:
        raise ValueError(f"'{text}' không đúng định dạng hh:mm")
    if hh < 0 or mm < 0 or mm > 59:
        raise ValueError(f"'{text}' không đúng định dạng hh:mm")
    total_hours = hh + mm / 60.0
    if total_hours <= 0:
        raise ValueError("Giờ lặp lại phải lớn hơn 00:00")
    return total_hours


def is_due(entry, now=None):
    """True nếu lịch này ĐẾN GIỜ chạy tại thời điểm `now` (mặc định: bây
    giờ). Mô hình MỚI: "giờ hẹn" (gio_hen, hh:mm) là mốc chạy LẦN ĐẦU TIÊN;
    kể từ đó cứ cách interval_hours giờ lại đến hạn chạy tiếp (tính từ
    lan_chay_luc - lần TRIGGER gần nhất). interval_hours = 24 tự nhiên cho
    ra đúng nghĩa "hằng ngày" (24 giờ sau vẫn là cùng giờ đó trong ngày).
    KHÔNG tự sửa entry - nơi gọi tự quyết định rồi gọi mark_triggered()
    ngay khi bắt đầu chạy (xem lý do ở đầu file)."""
    if not entry.get("bat", True):
        return False
    return _is_due_ignoring_bat(entry, now)


def would_be_due_if_enabled(entry, now=None):
    """Giống is_due() nhưng BỎ QUA việc kiểm tra 'bat' - dùng để CẢNH BÁO
    người dùng khi 1 lịch đang TẮT nhưng đúng ra đã tới giờ chạy (nếu không
    thì việc quên tick 'Bật' sẽ khiến lịch im lặng không chạy mà không có
    bất kỳ dòng log nào giải thích vì sao)."""
    if entry.get("bat", True):
        return False  # đang BẬT thì dùng is_due() bình thường, không cần cảnh báo riêng
    return _is_due_ignoring_bat(entry, now)


def _grid_anchor_epoch(entry):
    """Mốc gốc CỐ ĐỊNH (không phụ thuộc ngày hôm nay) dùng để dựng "lưới giờ
    chạy" của 1 lịch: 2020-01-01 lúc đúng gio_hen (hh:mm). Lưới các mốc đến
    hạn là anchor_epoch + k*interval_hours (k = 0, 1, 2, ...) - CỐ ĐỊNH vĩnh
    viễn theo hh:mm đã đặt, bất kể lịch đã từng bị trigger lúc nào."""
    hh, mm = _parse_gio_hen(entry)
    return datetime(2020, 1, 1, hh, mm)


def _last_grid_due_at_or_before(entry, now):
    """Mốc GẦN NHẤT trong lưới giờ chạy mà đã <= now (None nếu now đứng
    trước mốc gốc, trường hợp gần như không xảy ra vì mốc gốc ở năm 2020)."""
    anchor = _grid_anchor_epoch(entry)
    if now < anchor:
        return None
    interval_hours = _parse_interval_hours(entry)
    interval = timedelta(hours=interval_hours)
    k = int((now - anchor) / interval)
    return anchor + k * interval


def _is_due_ignoring_bat(entry, now=None):
    """TRƯỚC ĐÂY: khi chưa từng chạy thì neo theo gio_hen của NGÀY HÔM NAY,
    nhưng kể từ lần TRIGGER đầu tiên (kể cả bấm '▶ Chạy Ngay' để thử) lại
    chuyển hẳn sang tính "lan_chay_luc + interval_hours" - nghĩa là mốc hh:mm
    người dùng đặt (gio_hen) bị BỎ QUÊN VĨNH VIỄN sau lần chạy đầu tiên, lịch
    trôi dần theo đúng giờ phút của lần chạy gần nhất (vd bấm 'Chạy Ngay' thử
    lúc 14:00 thì từ đó lịch "hằng ngày" sẽ luôn chờ tới 14:00 hôm sau, KHÔNG
    còn chạy đúng giờ hẹn 07:00 đã đặt nữa) - lịch trông như "đến giờ hẹn
    không chạy, không báo gì" dù đang Bật và Chạy Ngay vẫn hoạt động bình
    thường.

    BÂY GIỜ: lưới giờ chạy CỐ ĐỊNH vĩnh viễn theo gio_hen (xem
    _grid_anchor_epoch) - lan_chay_luc CHỈ dùng để biết mốc lưới gần nhất đã
    được xử lý hay chưa (tránh trigger lặp lại nhiều lần cho cùng 1 mốc khi
    Dashboard kiểm tra mỗi ~20s), KHÔNG còn dùng để tính mốc kế tiếp - nhờ
    vậy bấm 'Chạy Ngay' để thử không còn làm lịch tự động trôi khỏi giờ hẹn
    đã đặt."""
    now = now or datetime.now()

    last_grid_due = _last_grid_due_at_or_before(entry, now)
    if last_grid_due is None:
        return False

    last_at = entry.get("lan_chay_luc")
    if not last_at:
        return True

    try:
        last_dt = datetime.fromisoformat(last_at)
    except Exception:
        return True

    return last_dt < last_grid_due


def mark_triggered(entry, now=None):
    """Cập nhật entry NGAY KHI quyết định trigger (không chờ chạy xong)."""
    now = now or datetime.now()
    entry["lan_chay_ngay"] = _today_key()
    entry["lan_chay_luc"] = now.isoformat(timespec="seconds")
    return entry


def sort_key(entry):
    """Khoá sắp xếp theo GIỜ HẸN (hh:mm) tăng dần trong ngày - dùng để hiển
    thị danh sách lịch trong '⏰ Hẹn Giờ' theo đúng THỨ TỰ THỜI GIAN CHẠY
    (lịch chạy sớm nhất trong ngày lên đầu) thay vì thứ tự thêm vào file
    schedules.json như trước đây."""
    hh, mm = _parse_gio_hen(entry)
    return hh * 60 + mm


def describe(entry):
    """Chuỗi mô tả ngắn gọn để hiển thị, vd 'Hằng ngày lúc 07:00' (khi giờ
    lặp lại = 24) hoặc 'Từ 13:30, lặp lại mỗi 4 giờ'."""
    hh, mm = _parse_gio_hen(entry)
    gio_hen_txt = f"{hh:02d}:{mm:02d}"
    interval_hours = _parse_interval_hours(entry)

    if interval_hours == 24:
        return f"Hằng ngày lúc {gio_hen_txt}"

    return f"Từ {gio_hen_txt}, lặp lại mỗi {hours_to_hhmm(interval_hours)}"

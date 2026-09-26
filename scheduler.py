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
        "gio_hen": "07:00",            # (CÓ THỂ NHIỀU MỐC/NGÀY) GIỜ HẸN
                                        # (hh:mm) - mốc chạy LẦN ĐẦU trong
                                        # "lưới giờ" của lịch này. Nhập NHIỀU
                                        # mốc trong 1 ngày bằng cách cách
                                        # nhau dấu phẩy, vd "07:00, 09:00,
                                        # 14:00" -> lịch tự chạy ở CẢ 3 mốc
                                        # đó (với interval_hours=24, tức mỗi
                                        # mốc lặp lại hằng ngày - xem
                                        # parse_gio_hen_list/describe bên
                                        # dưới). Chỉ 1 mốc vẫn hoạt động y
                                        # hệt bản cũ (tương thích ngược hoàn
                                        # toàn, không cần migrate dữ liệu).
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

VÌ SAO "gio_hen" NHẬN ĐƯỢC NHIỀU MỐC/NGÀY (vd "07:00, 09:00, 14:00"):
Ban đầu 1 lịch chỉ có ĐÚNG 1 mốc neo/ngày - muốn 1 nhóm Hoạt Động chạy ở
3 mốc lệch giờ không đều nhau trong ngày (vd 7h-9h-14h, không phải cứ
cách đều N giờ) thì phải tạo HẲN 3 lịch riêng, trùng lặp Hoạt Động/Giả
lập/Tài khoản - dễ quên sửa đồng bộ cả 3 khi đổi Hoạt Động. Nay ô "gio_hen"
nhận 1 DANH SÁCH mốc (cách nhau dấu phẩy) dùng CHUNG interval_hours (mặc
định 24 = mỗi mốc lặp lại hằng ngày): is_due()/next_due_time()/
missed_count() coi mỗi mốc là 1 "lưới giờ" riêng (xem _grid_anchor_epochs)
rồi gộp lại - lịch đến hạn nếu BẤT KỲ mốc nào đến hạn. lan_chay_luc vẫn
CHỈ 1 giá trị dùng chung cho cả lịch (không tách riêng từng mốc) - đủ để
mỗi mốc chỉ trigger đúng 1 lần khi tới, vì is_due() so sánh với mốc ĐÃ QUA
GẦN NHẤT trong TẤT CẢ các lưới (_last_grid_due_at_or_before), không phải
mốc của riêng 1 lưới.

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
import re
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


def load_schedules(path=SCHEDULES_PATH, warnings_out=None):
    """Đọc toàn bộ danh sách lịch. Luôn trả về list (rỗng nếu CHƯA TỪNG có
    file). Tự động chuyển các lịch định dạng cũ sang định dạng mới (xem
    _migrate_entry). Nếu file CÓ nhưng bị lỗi định dạng, tự thử khôi phục
    từ bản sao lưu ".bak" thay vì âm thầm trả về rỗng (xem
    paths.load_json_with_recovery) - truyền `warnings_out` (1 list) nếu
    muốn biết có sự cố vừa xảy ra để báo cho người dùng."""
    data, warning = paths.load_json_with_recovery(path, [])
    if warning and warnings_out is not None:
        warnings_out.append(warning)
    if not isinstance(data, list):
        data = []
    return [_migrate_entry(e) for e in data]


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


def _parse_one_hhmm(text):
    """Phân tích 1 chuỗi 'HH:MM' đơn lẻ -> (hh, mm). Ném ValueError nếu sai
    định dạng hoặc ngoài phạm vi hợp lệ (00:00-23:59)."""
    text = (text or "").strip()
    bits = text.split(":")
    if len(bits) != 2:
        raise ValueError(f"'{text}' không đúng định dạng HH:MM")
    try:
        hh, mm = int(bits[0]), int(bits[1])
    except Exception:
        raise ValueError(f"'{text}' không đúng định dạng HH:MM")
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError(f"'{text}' không phải giờ hợp lệ (00:00-23:59)")
    return hh, mm


def parse_gio_hen_list(text):
    """Phân tích ô 'Giờ hẹn' người dùng nhập - CÓ THỂ NHIỀU MỐC/NGÀY cách
    nhau bởi dấu phẩy hoặc chấm phẩy (vd '07:00, 09:00, 14:00') - thành 1
    LIST (hh, mm) đã loại trùng + sắp xếp tăng dần trong ngày. Chỉ 1 mốc
    (không có dấu phẩy) vẫn hoạt động bình thường, trả về list 1 phần tử.
    Ném ValueError (kèm thông báo cụ thể mốc nào sai) nếu có mốc không
    đúng định dạng HH:MM, hoặc chuỗi rỗng."""
    parts = [p.strip() for p in re.split(r"[,;]", text or "") if p.strip()]
    if not parts:
        raise ValueError("Chưa nhập Giờ hẹn nào.")
    pairs = [_parse_one_hhmm(p) for p in parts]
    return sorted(set(pairs))


def format_gio_hen_list(pairs):
    """Ngược lại parse_gio_hen_list(): list (hh, mm) -> chuỗi hiển thị/lưu
    'HH:MM' hoặc 'HH:MM, HH:MM, ...' nếu nhiều mốc."""
    return ", ".join(f"{hh:02d}:{mm:02d}" for hh, mm in pairs)


def hhmm_multi_to_stored(text):
    """Dùng ở UI khi LƯU ô 'Giờ hẹn': validate + chuẩn hoá (loại trùng, sắp
    xếp, format lại 2 chữ số) chuỗi người dùng vừa nhập thành chuỗi lưu vào
    entry['gio_hen']. Ném ValueError với thông báo phù hợp nếu sai."""
    return format_gio_hen_list(parse_gio_hen_list(text))


def _entry_gio_hen_pairs(entry):
    """Giống parse_gio_hen_list() nhưng KHÔNG BAO GIỜ ném lỗi - dùng nội bộ
    cho is_due()/describe()/... (dữ liệu trong schedules.json coi như đã
    được validate lúc lưu; nếu vì lý do gì đó bị hỏng thì âm thầm rơi về
    mốc mặc định 07:00 thay vì làm crash cả app)."""
    try:
        pairs = parse_gio_hen_list(entry.get("gio_hen", "07:00"))
    except Exception:
        pairs = []
    return pairs or [(7, 0)]


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


def _grid_anchor_epochs(entry):
    """Danh sách mốc gốc CỐ ĐỊNH (không phụ thuộc ngày hôm nay), 1 mốc cho
    MỖI giờ hẹn trong entry['gio_hen'] (có thể nhiều mốc/ngày, xem
    parse_gio_hen_list): 2020-01-01 lúc đúng hh:mm đó. Mỗi mốc gốc dựng ra 1
    "lưới giờ chạy" riêng (anchor + k*interval_hours, k = 0, 1, 2, ...) -
    CỐ ĐỊNH vĩnh viễn theo hh:mm đã đặt, bất kể lịch đã từng bị trigger lúc
    nào."""
    return [datetime(2020, 1, 1, hh, mm) for hh, mm in _entry_gio_hen_pairs(entry)]


def _last_grid_due_at_or_before_single(anchor, interval, now):
    """Giống _last_grid_due_at_or_before() nhưng cho ĐÚNG 1 lưới (1 mốc
    gốc) - dùng làm khối xây dựng chung cho mọi hàm bên dưới khi 1 lịch có
    NHIỀU mốc/ngày."""
    if now < anchor:
        return None
    k = int((now - anchor) / interval)
    return anchor + k * interval


def _last_grid_due_at_or_before(entry, now):
    """Mốc GẦN NHẤT trong TẤT CẢ các lưới giờ chạy của lịch (1 lưới/mốc
    trong gio_hen) mà đã <= now (None nếu now đứng trước mọi mốc gốc,
    trường hợp gần như không xảy ra vì mốc gốc ở năm 2020). Lịch có nhiều
    mốc/ngày đến hạn nếu BẤT KỲ lưới nào đến hạn - lấy mốc MUỘN NHẤT trong
    số đó để so với lan_chay_luc (xem _is_due_ignoring_bat)."""
    interval = timedelta(hours=_parse_interval_hours(entry))
    candidates = [d for d in (_last_grid_due_at_or_before_single(a, interval, now)
                               for a in _grid_anchor_epochs(entry)) if d is not None]
    return max(candidates) if candidates else None


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


def last_due_time(entry, now=None):
    """Mốc GẦN NHẤT trong lưới giờ chạy của lịch mà đã qua tại thời điểm
    `now` (mặc định: bây giờ) - dùng để biết 1 lịch đang "đến hạn" (is_due)
    là do mốc nào. None nếu không có mốc nào (xem _last_grid_due_at_or_before).
    Dashboard dùng để phân biệt lịch bị BỎ LỠ lúc chương trình đang tắt (mốc
    này sớm hơn lúc mở app) với lịch vừa tới giờ trong lúc app đang mở."""
    return _last_grid_due_at_or_before(entry, now or datetime.now())


def next_due_time(entry, now=None):
    """Mốc chạy KẾ TIẾP (sau `now`) - chỉ để hiển thị/ghi log "lần chạy tiếp
    theo lúc ...". Với lịch NHIỀU mốc/ngày, đây là mốc SỚM NHẤT trong tất
    cả các lưới (vd lịch 7h-9h-14h, đang là 10h -> trả về 14h hôm nay; đang
    là 15h -> trả về 7h hôm sau)."""
    now = now or datetime.now()
    interval = timedelta(hours=_parse_interval_hours(entry))
    anchors = _grid_anchor_epochs(entry)
    candidates = []
    for a in anchors:
        last_due = _last_grid_due_at_or_before_single(a, interval, now)
        candidates.append(a if last_due is None else last_due + interval)
    return min(candidates) if candidates else anchors[0]


def missed_count(entry, now=None):
    """Tổng số mốc (cộng dồn trên TẤT CẢ các lưới/mốc trong ngày của lịch)
    đã trôi qua mà CHƯA được xử lý (kể từ lần TRIGGER gần nhất -
    lan_chay_luc). 0 nếu lịch không có gì bị lỡ. Lưu ý is_due()/Dashboard
    chỉ chạy bù 1 LẦN duy nhất cho dù đã lỡ nhiều mốc (vd lịch mỗi 4 giờ,
    tắt app 12 giờ = lỡ 3 mốc nhưng chỉ chạy bù 1 lượt) - con số này chỉ để
    cho người dùng biết đã lỡ bao nhiêu lần (vd lịch 7h-9h-14h mà tắt app
    từ 6h tới 15h thì đây trả về 3, dù chỉ chạy bù 1 lượt)."""
    now = now or datetime.now()
    interval = timedelta(hours=_parse_interval_hours(entry))
    anchors = _grid_anchor_epochs(entry)

    last_at = entry.get("lan_chay_luc")
    try:
        last_dt = datetime.fromisoformat(last_at) if last_at else None
    except Exception:
        last_dt = None
    if last_dt is None:
        return 1 if _last_grid_due_at_or_before(entry, now) is not None else 0

    total = 0
    for anchor in anchors:
        last_due = _last_grid_due_at_or_before_single(anchor, interval, now)
        if last_due is None or last_dt >= last_due:
            continue
        k_now = int((now - anchor) / interval)
        k_last = int((last_dt - anchor) / interval) if last_dt >= anchor else -1
        total += max(1, k_now - k_last)
    return total


def hhmm_to_hours_allow_zero(text):
    """Giống hhmm_to_hours(), nhưng CHO PHÉP giá trị 00:00 (nghĩa là 0 giờ) -
    dùng riêng cho ô 'Chu kỳ xoay tài khoản' (0 = TẮT, giữ hành vi CŨ: chạy
    hết cả danh sách tài khoản trong 1 lượt trigger, xem
    resolve_rotation_accounts() bên dưới)."""
    text = (text or "").strip()
    if not text:
        return 0.0
    parts = text.split(":")
    if len(parts) != 2:
        raise ValueError(f"'{text}' không đúng định dạng hh:mm")
    try:
        hh, mm = int(parts[0]), int(parts[1])
    except Exception:
        raise ValueError(f"'{text}' không đúng định dạng hh:mm")
    if hh < 0 or mm < 0 or mm > 59:
        raise ValueError(f"'{text}' không đúng định dạng hh:mm")
    return hh + mm / 60.0


def resolve_rotation_accounts(entry, gl_key, accs, now=None):
    """Áp dụng 'Chu kỳ xoay tài khoản' RIÊNG của lịch này (trường
    chu_ky_xoay_tk_gio, giờ) khi 1 giả lập (gl_key = str(emulator_index))
    tới lượt chạy Hoạt Động, cho DANH SÁCH ĐẦY ĐỦ tài khoản đã gán
    (`accs`):
        - chu_ky_xoay_tk_gio = 0 (mặc định, KHÔNG có trong entry cũ) ->
          trả về NGUYÊN `accs` - hành vi CŨ: chạy xoay vòng hết cả danh
          sách (đăng xuất - đăng nhập - chạy Hoạt Động cho TỪNG tài khoản)
          ngay trong 1 lượt trigger.
        - chu_ky_xoay_tk_gio > 0 -> CHỈ trả về 1 tài khoản DUY NHẤT (tài
          khoản đang tới lượt trong vòng xoay). Tài khoản chỉ CHUYỂN sang
          tài khoản KẾ TIẾP khi đã đủ số giờ đó kể từ lần đổi gần nhất -
          nếu CHƯA đủ giờ, lượt trigger này vẫn chạy lại ĐÚNG tài khoản
          hiện tại (không bị bỏ qua, không đổi). Trạng thái xoay vòng (vị
          trí hiện tại + lần đổi gần nhất) được lưu NGAY trong `entry`
          (khoá "tk_xoay_trang_thai") - hàm này chỉ MUTATE `entry`, nơi
          gọi tự chịu trách nhiệm save_schedules() lại sau khi gọi.
    accs rỗng hoặc chỉ có 1 tài khoản -> trả nguyên accs, không cần xoay gì."""
    try:
        chu_ky = float(entry.get("chu_ky_xoay_tk_gio", 0) or 0)
    except Exception:
        chu_ky = 0.0
    if chu_ky <= 0 or len(accs) <= 1:
        return list(accs)

    now = now or datetime.now()
    trang_thai = entry.setdefault("tk_xoay_trang_thai", {})
    st = trang_thai.get(gl_key) or {}
    idx = st.get("idx", 0)
    if not isinstance(idx, int) or not (0 <= idx < len(accs)):
        idx = 0
    luc_doi_raw = st.get("luc")

    can_doi = True
    if luc_doi_raw:
        try:
            last_dt = datetime.fromisoformat(luc_doi_raw)
            can_doi = (now - last_dt).total_seconds() >= chu_ky * 3600
        except Exception:
            can_doi = True

    if can_doi:
        if luc_doi_raw is not None:
            idx = (idx + 1) % len(accs)
        trang_thai[gl_key] = {"idx": idx, "luc": now.isoformat(timespec="seconds")}
    else:
        trang_thai[gl_key] = {"idx": idx, "luc": luc_doi_raw}

    return [accs[idx]]


def mark_triggered(entry, now=None):
    """Cập nhật entry NGAY KHI quyết định trigger (không chờ chạy xong)."""
    now = now or datetime.now()
    entry["lan_chay_ngay"] = _today_key()
    entry["lan_chay_luc"] = now.isoformat(timespec="seconds")
    return entry


def sort_key(entry):
    """Khoá sắp xếp theo GIỜ HẸN SỚM NHẤT (hh:mm) tăng dần trong ngày - dùng
    để hiển thị danh sách lịch trong '⏰ Hẹn Giờ' theo đúng THỨ TỰ THỜI GIAN
    CHẠY (lịch chạy sớm nhất trong ngày lên đầu) thay vì thứ tự thêm vào
    file schedules.json như trước đây. Lịch nhiều mốc/ngày xếp theo mốc SỚM
    NHẤT trong số đó."""
    hh, mm = _entry_gio_hen_pairs(entry)[0]
    return hh * 60 + mm


def describe(entry):
    """Chuỗi mô tả ngắn gọn để hiển thị, vd 'Hằng ngày lúc 07:00' (khi giờ
    lặp lại = 24, 1 mốc/ngày), 'Hằng ngày lúc 07:00, 09:00, 14:00' (nhiều
    mốc/ngày, vẫn lặp lại = 24) hoặc 'Từ 13:30, lặp lại mỗi 4 giờ' (1 mốc,
    lặp lại khác 24)."""
    pairs = _entry_gio_hen_pairs(entry)
    gio_hen_txt = format_gio_hen_list(pairs)
    interval_hours = _parse_interval_hours(entry)

    if interval_hours == 24:
        base = f"Hằng ngày lúc {gio_hen_txt}"
    elif len(pairs) == 1:
        base = f"Từ {gio_hen_txt}, lặp lại mỗi {hours_to_hhmm(interval_hours)}"
    else:
        base = f"Từ mỗi mốc ({gio_hen_txt}), lặp lại thêm mỗi {hours_to_hhmm(interval_hours)}"

    try:
        chu_ky_xoay = float(entry.get("chu_ky_xoay_tk_gio", 0) or 0)
    except Exception:
        chu_ky_xoay = 0.0
    if chu_ky_xoay > 0:
        base += f", đổi tài khoản mỗi {hours_to_hhmm(chu_ky_xoay)}"
    return base

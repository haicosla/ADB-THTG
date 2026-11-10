"""
file_logger.py — Ghi Nhật Ký ra FILE trên đĩa (ngoài panel GUI đang thấy),
dùng chung cho cả LD Macro Studio (gui_run.py::_log_run) và Auto Runner
Dashboard (dashboard_log.py::_append_log).

VÌ SAO CẦN: chạy 1 kịch bản/lịch lâu, nếu tắt máy/crash/mất điện giữa
chừng thì panel Nhật Ký trong GUI biến mất theo, không còn cách nào biết
lỗi đã xảy ra ở bước nào, lúc mấy giờ - rất khó debug lại. File log ghi
song song ra đĩa, FLUSH NGAY từng dòng (không đợi buffer đầy hay đóng file
mới ghi), nên kể cả tắt đột ngột, mọi dòng đã log TRƯỚC thời điểm đó vẫn
còn nguyên vẹn trong file để mở lại xem.

Mỗi ngày dùng 1 file riêng: logs/YYYY-MM-DD.log - tự động sang file mới khi
qua ngày, không cần dọn/xoay vòng thủ công. An toàn khi gọi từ NHIỀU LUỒNG
cùng lúc (Dashboard chạy song song nhiều giả lập, mỗi luồng có thể ghi log
đồng thời) nhờ khoá threading.Lock().
"""
import os
import time
import threading

LOG_DIR = "logs"

_lock = threading.Lock()
_state = {"date": None, "fh": None}


def _get_handle():
    today = time.strftime("%Y-%m-%d")
    if _state["date"] != today or _state["fh"] is None:
        if _state["fh"] is not None:
            try:
                _state["fh"].close()
            except OSError:
                pass
        os.makedirs(LOG_DIR, exist_ok=True)
        path = os.path.join(LOG_DIR, f"{today}.log")
        _state["fh"] = open(path, "a", encoding="utf-8")
        _state["date"] = today
    return _state["fh"]


def write(level, message, emulator_name=None, source=""):
    """Ghi 1 dòng log ra file, flush + fsync NGAY LẬP TỨC (không đợi hệ
    điều hành tự gom buffer) để đảm bảo còn nguyên trên đĩa kể cả khi
    chương trình bị tắt đột ngột ngay sau lệnh ghi này. Không bao giờ ném
    lỗi ra ngoài (nuốt OSError) - ghi log ra file là tiện ích PHỤ, không
    được phép làm gãy luồng chạy chính nếu đĩa gặp sự cố."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    prefix = f"[{emulator_name}] " if emulator_name else ""
    src = f"{source} " if source else ""
    line = f"[{ts}] {src}{prefix}[{str(level).upper()}] {message}\n"
    with _lock:
        try:
            fh = _get_handle()
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        except OSError:
            pass

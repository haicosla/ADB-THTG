"""
run_state.py — Bộ nhớ "task nào đã chạy XONG hôm nay, trên giả lập nào" để
phục vụ nút "♻ Reset Bộ Nhớ Task Hôm Nay" trên Dashboard.

Đây CHỈ là nguồn ghi nhớ mở rộng, KHÔNG bắt buộc để Dashboard chạy được -
Dashboard hiện tại vẫn chạy lại bình thường mọi tác vụ đã tick dù đã chạy
hôm nay hay chưa. Việc ghi nhớ này giúp:
  - Về sau dễ dàng thêm tính năng "tự động bỏ qua task đã hoàn thành hôm
    nay" nếu cần, mà không phải đổi cấu trúc dữ liệu.
  - Cho người dùng 1 cách "xoá sạch" trạng thái đó bằng 1 nút bấm, thay vì
    phải tự tay xoá file.
"""
import json
import os
import threading
import time

import paths

STATE_PATH = paths.resolve_data_path("run_state_today.json")

# Nhiều luồng giả lập có thể cùng gọi mark_done() gần như đồng thời (xem
# dashboard_run.py). mark_done()/reset_today() là "đọc cả file -> sửa -> ghi
# lại cả file", nên nếu 2 luồng chen nhau thì bản ghi của 1 luồng bị luồng
# kia ghi đè mất. RLock này bắt mọi thao tác đọc-sửa-ghi phải chạy lần lượt.
_state_lock = threading.RLock()


def _today_key():
    return time.strftime("%Y-%m-%d")


def _load_raw(path=STATE_PATH):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_raw(data, path=STATE_PATH):
    try:
        paths.save_json(path, data)
    except Exception:
        pass


def mark_done(task_id, emulator_name, path=STATE_PATH):
    """Đánh dấu task_id đã chạy XONG hôm nay trên giả lập emulator_name."""
    with _state_lock:
        data = _load_raw(path)
        day_bucket = data.setdefault(_today_key(), {})
        done_list = day_bucket.setdefault(task_id, [])
        if emulator_name not in done_list:
            done_list.append(emulator_name)
        _save_raw(data, path)


def is_done_today(task_id, emulator_name, path=STATE_PATH):
    data = _load_raw(path)
    day_bucket = data.get(_today_key(), {})
    return emulator_name in day_bucket.get(task_id, [])


def count_done_today(task_id, path=STATE_PATH):
    data = _load_raw(path)
    day_bucket = data.get(_today_key(), {})
    return len(day_bucket.get(task_id, []))


def reset_today(path=STATE_PATH):
    """Xoá sạch ghi nhớ của NGÀY HÔM NAY (giữ nguyên lịch sử các ngày khác,
    nếu về sau muốn xem lại)."""
    with _state_lock:
        data = _load_raw(path)
        data[_today_key()] = {}
        _save_raw(data, path)


def rename_task_ids(mapping, path=STATE_PATH):
    """Đổi khoá task_id cũ -> mới ở MỌI ngày (khi đổi tên file kịch bản) để
    bộ nhớ 'đã chạy hôm nay' không bị mồ côi. Trả về số khoá đã đổi."""
    if not mapping:
        return 0
    n = 0
    with _state_lock:
        data = _load_raw(path)
        for day_bucket in data.values():
            if not isinstance(day_bucket, dict):
                continue
            for old, new in mapping.items():
                if old in day_bucket:
                    moved = day_bucket.pop(old)
                    cur = day_bucket.setdefault(new, [])
                    for emu in (moved if isinstance(moved, list) else []):
                        if emu not in cur:
                            cur.append(emu)
                    n += 1
        if n:
            _save_raw(data, path)
    return n


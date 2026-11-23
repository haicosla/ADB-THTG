"""
session_journal.py — "Sổ tiến độ phiên đang chạy" để CHẠY TIẾP phần còn lại sau khi chương trình bị tắt
đột ngột / treo / mất điện giữa chừng.

Cách hoạt động:
  - Mỗi giả lập đang chạy 1 phiên (chạy tay hoặc lượt Hẹn Giờ) có đúng 1 bản ghi trong
    data/session_journal.json, ghi ngay lúc BẮT ĐẦU và cập nhật sau mỗi Hoạt Động xong.
  - Phiên kết thúc BÌNH THƯỜNG (xong, bấm Dừng, không bật được giả lập...) -> end() xoá bản ghi.
  - Còn sót bản ghi khi mở lại app = phiên đó bị gián đoạn -> Dashboard hiện hộp "Chạy tiếp?"
    (xem dashboard_resume.py).
Chỉ lưu id/vị trí (không lưu mật khẩu: tài khoản lưu theo id). Lỗi ghi file bị nuốt - không bao giờ
làm hỏng phiên đang chạy.
"""
import json
import os
import threading
from datetime import datetime

import paths
import task_registry

JOURNAL_PATH = paths.resolve_data_path("session_journal.json")
_lock = threading.RLock()
QUEUE_KEY = "__queue__"      # khoá đặc biệt: hàng chờ job (không phải bản ghi phiên)


def _load():
    try:
        with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d):
    try:
        if not d:
            if os.path.exists(JOURNAL_PATH):
                os.remove(JOURNAL_PATH)
            return
        paths.save_json(JOURNAL_PATH, json.loads(json.dumps(d, ensure_ascii=False, default=str)), backup=False)
    except Exception:
        pass


def _now():
    return datetime.now().isoformat(timespec="seconds")


def begin_manual(emu_index, emu_name, task_ids, login, preset_vars):
    with _lock:
        d = _load()
        d[str(emu_index)] = {"kind": "manual", "emu_index": emu_index, "emu_name": emu_name,
                             "started": _now(), "updated": _now(), "task_ids": list(task_ids),
                             "login": bool(login), "preset_vars": dict(preset_vars or {}),
                             "act_pos": 0, "phase": "run"}
        _save(d)


def begin_schedule(emu_index, emu_name, schedule_id, schedule_name, activity_ids, account_ids, final_ids,
                   schedule_vars, act_pos=0):
    with _lock:
        d = _load()
        d[str(emu_index)] = {"kind": "schedule", "emu_index": emu_index, "emu_name": emu_name,
                             "started": _now(), "updated": _now(), "schedule_id": schedule_id,
                             "schedule_name": schedule_name, "activity_ids": list(activity_ids or []),
                             "account_ids": list(account_ids or []), "final_ids": list(final_ids or []),
                             "schedule_vars": dict(schedule_vars or {}), "acc_pos": 0,
                             "act_pos": int(act_pos or 0), "phase": "run"}
        _save(d)


def progress(emu_index, **fields):
    """Cập nhật vị trí: act_pos (số Hoạt Động đã xong/bỏ qua của tài khoản hiện tại), acc_pos, phase."""
    with _lock:
        d = _load()
        rec = d.get(str(emu_index))
        if not rec:
            return
        rec.update(fields)
        rec["updated"] = _now()
        _save(d)


def end(emu_index):
    with _lock:
        d = _load()
        if d.pop(str(emu_index), None) is not None:
            _save(d)


def pending():
    """Các bản ghi phiên còn sót từ lần chạy trước (list dict)."""
    with _lock:
        return [r for k, r in _load().items() if k != QUEUE_KEY and isinstance(r, dict)]


def begin_rotation(emu_index, emu_name, specs, account_ids, preset_vars):
    """Phiên 👥 Xoay Vòng Tài Khoản: specs = các mục đã chọn (xem selected_to_specs)."""
    with _lock:
        d = _load()
        d[str(emu_index)] = {"kind": "rotation", "emu_index": emu_index, "emu_name": emu_name,
                             "started": _now(), "updated": _now(), "specs": list(specs),
                             "account_ids": list(account_ids or []), "preset_vars": dict(preset_vars or {}),
                             "acc_pos": 0, "act_pos": 0, "phase": "run"}
        _save(d)


def begin_group(emu_index, emu_name, group_ids, tag):
    """Phiên ▶ Chạy Nhóm Hành Động: act_pos = số bước (đã bung phẳng) đã xong."""
    with _lock:
        d = _load()
        d[str(emu_index)] = {"kind": "group", "emu_index": emu_index, "emu_name": emu_name,
                             "started": _now(), "updated": _now(), "group_ids": list(group_ids or []),
                             "tag": tag, "act_pos": 0, "phase": "run"}
        _save(d)


def selected_to_specs(selected):
    """Danh sách `selected` (Hoạt Động thường + entry ảo của Nhóm) -> list JSON gọn: {"id"} / {"group","name"}."""
    out = []
    for e in selected or []:
        if e.get("__group_ids__") is not None:
            out.append({"group": list(e.get("__group_ids__") or []), "name": e.get("ten_hien_thi", "")})
        else:
            out.append({"id": e.get("id") or task_registry.make_task_id(e.get("file_json", ""))})
    return out


# ---- HÀNG CHỜ (self._emulator_job_queue) lưu xuống đĩa để không mất khi app tắt/treo ----
def save_queue(queue_specs):
    """queue_specs: {"<emu_index>": [spec, ...]} (rỗng -> xoá khoá hàng chờ)."""
    with _lock:
        d = _load()
        if queue_specs:
            d[QUEUE_KEY] = queue_specs
        else:
            d.pop(QUEUE_KEY, None)
        _save(d)


def load_queue():
    with _lock:
        q = _load().get(QUEUE_KEY)
        return q if isinstance(q, dict) else {}

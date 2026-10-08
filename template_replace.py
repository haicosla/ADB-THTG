"""
template_replace.py - Tìm & thay 1 ảnh mẫu (templates/<tên>.png) ở NHIỀU NƠI cùng lúc.

Mỗi bước trong kịch bản chỉ lưu TÊN file ảnh (field "template", danh sách "templates",
hoặc lá "image" trong cây điều kiện `tree` của bước if_group), nên đổi ảnh ở 1 bước KHÔNG
làm các bước/task/nhóm khác đổi theo. Module này giúp: đếm xem ảnh cũ còn được dùng ở đâu
(tasks/*.json + groups/*.json + kịch bản đang mở trong Studio), rồi (khi người dùng đồng ý)
thay tên ảnh cũ -> ảnh mới ở tất cả các chỗ đó.

- Kịch bản ĐANG MỞ trong Studio chỉ được sửa TRONG BỘ NHỚ (không ghi đè file - tránh lưu luôn
  phần người dùng đang sửa dở); người dùng tự bấm Lưu như bình thường.
- Các file tasks/groups KHÁC được ghi ngay bằng paths.save_json (ghi nguyên tử + .bak).
- Không bao giờ ném lỗi ra ngoài khi QUÉT; khi GHI thì gom lỗi từng file vào kết quả.
"""
import os
import json
import glob

import paths

TASKS_DIR = "tasks"
GROUPS_DIR = "groups"


def _iter_tree_slots(node):
    """Các lá 'image' trong cây điều kiện if_group (đệ quy and/or/not)."""
    if not isinstance(node, dict):
        return
    t = node.get("type")
    if t in ("and", "or", "not"):
        for child in (node.get("children") or []):
            yield from _iter_tree_slots(child)
    elif t == "image" and isinstance(node.get("template"), str):
        yield node, "template"


def _iter_slots(steps):
    """Yield (container, key) cho MỌI chỗ lưu tên ảnh: container[key] = tên file."""
    if not isinstance(steps, list):
        return
    for s in steps:
        if not isinstance(s, dict):
            continue
        if isinstance(s.get("template"), str) and s["template"]:
            yield s, "template"
        tpls = s.get("templates")
        if isinstance(tpls, list):
            for i, t in enumerate(tpls):
                if isinstance(t, str) and t:
                    yield tpls, i
        if s.get("action") == "if_group" and s.get("tree"):
            yield from _iter_tree_slots(s["tree"])


def count_refs(steps, name):
    return sum(1 for c, k in _iter_slots(steps) if c[k] == name)


def replace_refs(steps, old, new):
    """Thay `old` -> `new` trong `steps` (tại chỗ). Trả về số tham chiếu đã đổi. Nếu comment
    của bước đúng dạng 'Ảnh: <old>' thì cập nhật theo luôn."""
    changed = 0
    for c, k in list(_iter_slots(steps)):
        if c[k] == old:
            c[k] = new
            changed += 1
            if isinstance(c, dict) and k == "template":
                if c.get("comment") == f"Ảnh: {old}":
                    c["comment"] = f"Ảnh: {new}"
    return changed


def _norm(p):
    try:
        return os.path.normcase(os.path.abspath(p))
    except Exception:
        return p


def _load_list(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else None
    except Exception:
        return None


def find_usages(old, current_steps=None, current_path=None):
    """Trả về list dict {kind: 'task'|'group'|'current', label, path, count, is_current}
    cho mọi nơi còn dùng ảnh `old`. Kịch bản đang mở dùng bản TRONG BỘ NHỚ (current_steps)."""
    out = []
    cur_norm = _norm(current_path) if current_path else None
    seen_current = False
    for kind, folder in (("task", TASKS_DIR), ("group", GROUPS_DIR)):
        for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
            label = os.path.splitext(os.path.basename(path))[0]
            if cur_norm and _norm(path) == cur_norm and current_steps is not None:
                seen_current = True
                n = count_refs(current_steps, old)
                if n:
                    out.append({"kind": kind, "label": label + " (đang mở)", "path": path,
                                "count": n, "is_current": True})
                continue
            data = _load_list(path)
            if data is None:
                continue
            n = count_refs(data, old)
            if n:
                out.append({"kind": kind, "label": label, "path": path, "count": n, "is_current": False})
    if current_steps is not None and not seen_current:
        n = count_refs(current_steps, old)
        if n:
            out.append({"kind": "current", "label": "kịch bản đang mở (chưa lưu)", "path": current_path,
                        "count": n, "is_current": True})
    return out


def apply_replace(old, new, usages, current_steps=None):
    """Thay `old` -> `new` ở mọi nơi trong `usages` (kết quả find_usages).
    Trả về {"changed": tổng số chỗ đã đổi, "files": [file đã ghi], "memory": số chỗ đổi trong
    kịch bản đang mở, "errors": [(label, lỗi)]}."""
    res = {"changed": 0, "files": [], "memory": 0, "errors": []}
    for u in usages:
        try:
            if u["is_current"]:
                n = replace_refs(current_steps, old, new) if current_steps is not None else 0
                res["memory"] += n
                res["changed"] += n
                continue
            data = _load_list(u["path"])
            if data is None:
                raise ValueError("không đọc được file JSON")
            n = replace_refs(data, old, new)
            if n:
                paths.save_json(u["path"], data)
                res["files"].append(u["path"])
                res["changed"] += n
        except Exception as e:
            res["errors"].append((u.get("label", "?"), str(e)))
    return res

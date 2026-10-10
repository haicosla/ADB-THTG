# -*- coding: utf-8 -*-
"""
pig_check_log.py - Đọc debug_pig/pig_log.jsonl để biết bot thả lệch vì ĐÂU:
  (A) con heo thật rơi KHÔNG đúng x bot định thả  -> lỗi điểm bấm / cách game nhận bấm (không phải thuật toán)
  (B) rơi đúng x nhưng chỗ nằm yên khác dự đoán      -> mô phỏng vật lý chưa khớp (tự hiệu chỉnh sẽ sửa dần)
  (C) bot không thấy heo cùng cấp đang nằm trên bàn   -> lỗi nhận diện (xem ảnh pig_NNNN.png)
Chạy:  python pig_check_log.py [pig_log.jsonl | thư mục phiên | debug_pig]   (bỏ trống = phiên mới nhất)
"""
import sys, json, math

import os


def _default_log(arg=None):
    """Không truyền gì = log của phiên MỚI NHẤT (debug_pig/last_session.txt); truyền thư mục phiên/debug_pig = log trong đó; truyền file = dùng luôn."""
    root = arg or "debug_pig"
    if arg and os.path.isfile(arg):
        return arg
    if os.path.isfile(os.path.join(root, "pig_log.jsonl")):
        return os.path.join(root, "pig_log.jsonl")
    try:
        with open(os.path.join(root, "last_session.txt"), encoding="utf-8") as f:
            p_ = os.path.join(f.read().strip(), "pig_log.jsonl")
        if os.path.isfile(p_):
            return p_
    except Exception:
        pass
    return os.path.join(root, "pig_log.jsonl")


path = _default_log(sys.argv[1] if len(sys.argv) > 1 else None)
rows = []
with open(path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            rows.append(json.loads(line))
print("Đọc %d lượt từ %s\n" % (len(rows), path))
modes = sorted(set(str(r.get("drop_mode", "tap(log cũ)")) for r in rows))
print("Cách thả trong log: %s  (log mới có x_act = x thật lúc nhả tay; cột 'x định thả' dưới đây dùng x_act nếu có)\n" % ", ".join(modes))
drag_dev = [abs(r["x_act"] - r["x"]) / r["W"] for r in rows if r.get("x_act") is not None]
if drag_dev:
    drag_dev.sort()
    print("Nhả tay lệch x định (trung vị): %.1f%% khung\n" % (100 * drag_dev[len(drag_dev) // 2]))
dx_int, dx_pred, miss_same = [], [], 0
print("lượt | cầm | x định thả | x thật của con mới | lệch so định thả | lệch so dự đoán | ghi chú")
for a, b in zip(rows, rows[1:]):
    W = a["W"]
    held = a["held"]
    xa = a["x_act"] if a.get("x_act") is not None else a["x"]       # x thật lúc nhả tay (drop_mode=drag) nếu có
    cur = [tuple(t) for t in a["before"]]
    nxt = [tuple(t) for t in b["before"]]
    # con mới = con của lượt sau không khớp con nào của lượt này (cùng cấp, gần < 3% rộng khung)
    new = [n for n in nxt if not any(c[0] == n[0] and math.hypot(c[1] - n[1], c[2] - n[2]) < 0.03 * W for c in cur)]
    fresh = [n for n in new if n[0] == held]
    note = ""
    same_before = [c for c in cur if c[0] == held and held < 10]
    if not fresh:
        note = "đã gộp/bị đẩy đi" if new else "không thấy con mới"
        print("%4d | L%-2d | %5.1f%%     |        -           |        -         |        -        | %s" % (a["turn"], held, 100 * xa / W, note))
        continue
    n = min(fresh, key=lambda t: abs(t[1] - xa))
    pr = [tuple(t) for t in a["pred"] if t[0] == held]
    e_int = abs(n[1] - xa) / W
    e_pred = min((math.hypot(p[1] - n[1], p[2] - n[2]) for p in pr), default=float("nan")) / W
    dx_int.append(e_int)
    dx_pred.append(e_pred)
    if same_before:
        near = min(abs(c[1] - n[1]) for c in same_before) / W
        if near > 0.2:
            miss_same += 1
            note = "có heo L%d trên bàn nhưng thả xa" % held
    print("%4d | L%-2d | %5.1f%%     |      %5.1f%%        |      %5.1f%%      |     %5.1f%%     | %s" %
          (a["turn"], held, 100 * xa / W, 100 * n[1] / W, 100 * e_int, 100 * e_pred, note))
if dx_int:
    dx_int.sort()
    med = dx_int[len(dx_int) // 2]
    print("\nTóm tắt (đơn vị: % chiều rộng khung):")
    print(" - lệch trung vị giữa x ĐỊNH THẢ và x THẬT của con mới: %.1f%%" % (100 * med))
    print(" - số lượt có heo cùng cấp trên bàn nhưng con mới rơi xa nó: %d" % miss_same)
    if med > 0.06:
        print(" => Nghi (A): heo KHÔNG rơi đúng chỗ bot định. Nếu log cũ là tap: đổi drop_mode=\"drag\" (mặc định mới); nếu đã drag mà vẫn lệch: gửi mình log này.")
    else:
        e2 = sorted(x for x in dx_pred if x == x)
        if e2 and e2[len(e2) // 2] > 0.08:
            print(" => Nghi (B): rơi đúng x nhưng lăn khác dự đoán -> mô phỏng vật lý chưa khớp (cần thêm lượt để tự hiệu chỉnh).")
        else:
            print(" => Rơi đúng x và khớp dự đoán: lệch nằm ở thuật toán chọn chỗ (hoặc nhận diện, xem ảnh pig_NNNN.png).")

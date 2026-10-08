# -*- coding: utf-8 -*-
"""Phân tích log auto_pig: dự đoán (mô phỏng) có khớp ảnh thật không, và sai ở đâu.

Cách dùng:   python pig_report.py [thư_mục_debug_pig]  [--fit]
  - Đọc pig_log.jsonl (mỗi dòng 1 lượt: before / pred / x thả). Ảnh THẬT sau lượt k = 'before' của lượt k+1.
  - In bảng từng lượt: sai số dự đoán, số heo lệch, con bị lệch nhiều nhất (cấp, lệch px, hướng lệch ngang).
  - Phân loại: 'ĐỌC' (số heo/cấp khác hẳn: đọc sớm / đọc nhầm popup) hay 'LĂN' (đúng heo nhưng vị trí lệch: mô phỏng lăn/nảy sai).
  - Thống kê hướng lệch TB của con vừa thả (dương = thật nằm bên PHẢI chỗ dự đoán) -> biết mô phỏng lăn thiếu/thừa.
  - --fit: chạy calibrate offline trên toàn bộ mẫu, in tham số vật lý tốt nhất + sai số trước/sau, ghi pig_params_fit.json.
"""
import json
import math
import os
import sys

import pig_bot as p


def load(d):
    rows = []
    with open(os.path.join(d, "pig_log.jsonl"), encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    return rows


def match(pred, obs):
    """Khớp từng heo dự đoán với heo thật cùng cấp, gần nhất. Trả (list (cấp, dx, dy, d), số thật không khớp)."""
    used, out = set(), []
    for lv, x, y, r in sorted(pred, key=lambda b: -b[0]):
        best = None
        for j, b in enumerate(obs):
            if j in used or b[0] != lv:
                continue
            d = math.hypot(b[1] - x, b[2] - y)
            if best is None or d < best[0]:
                best = (d, j)
        if best is None:
            out.append((lv, None, None, None))
        else:
            used.add(best[1])
            b = obs[best[1]]
            out.append((lv, b[1] - x, b[2] - y, best[0]))
    return out, len(obs) - len(used)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    d = args[0] if args else "debug_pig"
    rows = load(d)
    if len(rows) < 2:
        print("Cần >= 2 lượt trong", d)
        return
    W = rows[0]["W"]
    H = rows[0]["H"]
    print("%d lượt, khung %dx%d. Sai số = trung bình lệch / bề rộng khung (0.02 = lệch ~2%%).\n" % (len(rows), W, H))
    print("%-4s %-4s %-6s %-7s %-6s  %s" % ("lượt", "cầm", "x%", "sai số", "lệch", "chi tiết (con lệch nhiều nhất) / loại"))
    samples, dxs, kinds = [], [], {"tốt": 0, "LĂN": 0, "ĐỌC": 0}
    for i in range(len(rows) - 1):
        r, nx = rows[i], rows[i + 1]
        pred = [tuple(b) for b in r["pred"]]
        obs = [tuple(b) for b in nx["before"]]
        err, miss = p.pred_error(pred, obs, W)
        pairs, extra = match(pred, obs)
        unmatched = sum(1 for q in pairs if q[3] is None) + extra
        worst = max((q for q in pairs if q[3] is not None), key=lambda q: q[3], default=None)
        if err < 0.04 and unmatched == 0 and (worst is None or worst[3] < 0.06 * W):
            kind = "tốt"
        elif unmatched >= 1 and len(pred) != len(obs):
            kind = "ĐỌC"      # khác SỐ heo / cấp: gộp mà không dự đoán được, hoặc đọc sớm/nhầm popup/heo đang rơi
        else:
            kind = "LĂN"
        kinds[kind] += 1
        det = ""
        if worst:
            det = "L%d lệch %.0fpx (dx=%+.0f dy=%+.0f)" % (worst[0], worst[3], worst[1], worst[2])
        if unmatched:
            det += " | %d heo không khớp (dự đoán %d, thật %d)" % (unmatched, len(pred), len(obs))
        print("%-4d L%-3d %-6.0f %-7.3f %-6d  %s  [%s]" % (r["turn"], r["held"], 100.0 * r["x_act"] / W, err, miss, det, kind))
        if kind != "ĐỌC":
            # hướng lệch của con vừa thả (heo có cấp = cấp con thả, lệch nhiều nhất)
            c = [q for q in pairs if q[0] == r["held"] and q[3] is not None]
            if c:
                dxs.append(max(c, key=lambda q: q[3])[1])
        samples.append(([tuple(b) for b in r["before"]], (r["held"], 0), r["x_act"], obs))
    print("\nTổng kết: %d tốt, %d LĂN (đúng heo nhưng sai chỗ -> chỉnh vật lý), %d ĐỌC (sai số heo/cấp -> lỗi nhận diện/đọc sớm)" %
          (kinds["tốt"], kinds["LĂN"], kinds["ĐỌC"]))
    if dxs:
        m = sum(dxs) / len(dxs)
        print("Con vừa thả: lệch ngang TB %+.1fpx (%+.1f%% khung); dương = thật nằm bên PHẢI chỗ dự đoán. Nếu |TB| lớn: lệch hệ thống (vd tâm thả/tap bị lệch)." % (m, 100.0 * m / W))
    if "--fit" in sys.argv:
        # cần bán kính con thả: lấy từ r_for
        smp = []
        for (b, h, x, o), r in zip(samples, rows):
            smp.append((b, (h[0], p.r_for(h[0], W)), x, o))
        sp0 = p.SimParams()
        best, e0, eb, n = p.calibrate(smp, sp0, W, H, budget_s=20.0, seed=1)
        print("\nFit offline (%d thử): sai số %.4f -> %.4f" % (n, e0, eb))
        out = {k: getattr(best, k) for k in p.CAL_RANGE}
        print(json.dumps(out, indent=1))
        with open(os.path.join(d, "pig_params_fit.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
        print("Đã ghi pig_params_fit.json (đổi tên thành pig_params.json để bot dùng).")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Phân tích log auto_pig: dự đoán (mô phỏng) có khớp ảnh thật không, và sai ở đâu.

Cách dùng:   python pig_report.py [thư_mục_phiên | debug_pig | thư_mục_có_pig_log.jsonl]  [--fit]
  - Bỏ trống = phiên MỚI NHẤT trong debug_pig/sessions (xem debug_pig/last_session.txt). Đọc pig_log.jsonl (+ pig_cmp.jsonl): mỗi dòng 1 lượt.
    Ảnh THẬT sau lượt k = ảnh đo trong pig_cmp.jsonl (hoặc 'before' của lượt k+1 với log kiểu cũ).
  - In bảng từng lượt: sai số, con lệch nhiều nhất, quãng lăn dự đoán/thật, loại:
      tốt | LĂN (đúng heo nhưng vị trí lệch -> chỉnh ma sát/nảy) | GỘP (mô phỏng gộp khác thật -> chỉnh merge_eps/rad_scale) | ĐỌC (đọc thiếu/thừa/nhầm heo -> lỗi nhận diện)
  - Tóm tắt: tỉ lệ gộp đúng, thiên lệch lăn (thật lăn xa/ngắn hơn dự đoán), độ cao con vừa thả.
  - --fit: chạy calibrate (5 tham số gốc) offline, ghi pig_params_fit.json. Muốn chỉnh đủ lăn/nảy/gộp + ảnh quay + kiểm tra chéo: dùng pig_calib.py.
"""
import json
import os
import sys

import pig_bot as p
import pig_calib as pc


def load(d):
    """Đọc pig_log.jsonl trong thư mục d (giữ lại cho tương thích)."""
    return pc._read_jsonl(os.path.join(d, "pig_log.jsonl"))


def match(pred, obs):
    """Khớp từng heo dự đoán với heo thật cùng cấp, gần nhất. Trả (list (cấp, dx, dy, d), số thật không khớp)."""
    return p.match_balls(pred, obs)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    d = args[0] if args else "debug_pig"
    dirs = pc.find_sessions(d)
    if not dirs:
        print("Không thấy pig_log.jsonl trong", d)
        return
    sd = dirs[-1]
    ss = pc.load_session(sd)
    smp = ss["samples"]
    if not smp:
        print("Cần >= 1 lượt thả có ảnh thật sau đó trong", sd)
        return
    sp0 = pc.sp_from_dict(smp[0].get("sp"))
    ev = pc.evaluate_samples(smp, sp0)
    print("Phiên %s: %d lượt, khung %dx%d. Sai số = trung bình lệch / bề rộng khung (0.02 = lệch ~2%%)." % (ss["id"], len(smp), smp[0]["W"], smp[0]["H"]))
    print("Tham số vật lý bot đã dùng: " + pc._fmt_sp(sp0) + "\n")
    for ln in p.format_cmp_table(ev):
        print(ln)
    print()
    for ln in p.summarize_cmp(ev):
        print(ln)
    xs = [r["drop"]["x_obs"] - r["drop"]["x_pred"] for r in ev if r["kind"] != "ĐỌC" and r.get("drop") and r["drop"].get("x_obs") is not None]
    if xs:
        m = sum(xs) / len(xs)
        W = smp[0]["W"]
        print("Con vừa thả: lệch ngang TB %+.1fpx (%+.1f%% khung); dương = thật nằm bên PHẢI chỗ dự đoán. Nếu |TB| lớn: lệch hệ thống (vd tâm thả/tap bị lệch)." % (m, 100.0 * m / W))
    if "--fit" in sys.argv:
        samples = [(s["before"], (s["held"], s["hr"]), s["x"], s["obs"], s["y0"]) for s, r in zip(smp, ev) if r["kind"] != "ĐỌC"]
        if len(samples) < 3:
            print("\nQuá ít mẫu sạch để fit.")
            return
        best, e0, eb, n = p.calibrate(samples, sp0, smp[0]["W"], smp[0]["H"], budget_s=20.0, seed=1)
        print("\nFit offline (%d thử): sai số %.4f -> %.4f" % (n, e0, eb))
        out = {k: getattr(best, k) for k in p.CAL_RANGE}
        print(json.dumps(out, indent=1))
        with open(os.path.join(sd, "pig_params_fit.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
        print("Đã ghi pig_params_fit.json (đổi tên thành pig_params.json để bot dùng, hoặc dùng: python pig_calib.py --fit --apply).")


if __name__ == "__main__":
    main()

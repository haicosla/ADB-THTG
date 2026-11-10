# -*- coding: utf-8 -*-
"""
pig_calib.py - ĐỌC log các phiên auto_pig, so DỰ ĐOÁN với THỰC TẾ rồi HIỆU CHỈNH tham số vật lý (lăn / nảy / gộp cấp) cho khớp.

Quy trình lặp (mục tiêu: mô phỏng giống chơi thật nhất):
  1) Trong bước auto_pig bật  "calib_run": true  (chơi THẬT ~40 lượt, lưu đủ log + ảnh + ảnh quay lúc heo rơi/lăn). Phiên lưu ở debug_pig/sessions/<ngày_giờ>_calib/
  2) python pig_calib.py                     -> báo cáo phiên MỚI NHẤT: bao nhiêu lượt tốt/LĂN/GỘP/ĐỌC, sai số, thiên lệch lăn, tỉ lệ gộp đúng ...
  3) python pig_calib.py --fit               -> tìm tham số khớp hơn (in trước/sau, kiểm tra chéo), ghi pig_params_fit.json trong thư mục phiên
     python pig_calib.py --fit --apply       -> như trên + ghi thành debug_pig/pig_params.json (bản cũ sao lưu .bak) để bot dùng từ lượt sau
  4) chạy lại bước 1 (phiên mới dùng tham số mới) -> python pig_calib.py --history để xem sai số có giảm qua từng phiên không. Lặp tới khi hài lòng.

Các lệnh:
  python pig_calib.py [đường_dẫn ...] [tuỳ chọn]
    đường_dẫn : thư mục 1 phiên | thư mục debug_pig (dùng phiên mới nhất; --all = mọi phiên) | thư mục chứa pig_log.jsonl (log kiểu cũ)
    --all            dùng MỌI phiên trong debug_pig/sessions (nhiều dữ liệu -> hiệu chỉnh vững hơn)
    --history        bảng 1 dòng / phiên: tham số đang dùng, sai số TB, % gộp đúng, số lượt tốt/LĂN/GỘP/ĐỌC (để thấy xu hướng qua các lần chỉnh)
    --table          in bảng từng lượt
    --fit            tìm tham số khớp hơn          --aspect all|roll|bounce|merge  (chỉ chỉnh nhóm: roll = friction/damping/spin_damp; bounce = elasticity/gravity/damping;
                                                   merge = merge_eps/rad_scale)
    --budget S       giây tối đa cho --fit (mặc định 90)       --val F  tỉ lệ mẫu dành kiểm tra chéo (mặc định 0.25; 0 = dùng hết để chỉnh)
    --trace          dùng thêm ảnh quay trace/ (heo rơi/lăn theo thời gian) để chỉnh gravity/elasticity/damping + trễ bấm (tự bật nếu phiên có trace)
    --no-trace       không dùng trace         --trace-weight F  trọng số trace so với trạng thái cuối (mặc định 1.0)
    --start FILE     tham số bắt đầu (json); mặc định = tham số bot đã dùng trong log
    --read-tol N     lượt có khối lượng heo thật lệch > N so với (trước + con thả) mới bị loại là 'ĐỌC' (mặc định 8; 99999 = không loại lượt nào)
    --apply          ghi kết quả --fit vào <debug_pig>/pig_params.json          --seed N
Chỉ dùng mẫu không bị 'ĐỌC' (khối lượng heo thật lệch > ngưỡng so với trước + con thả: ảnh đọc thiếu/thừa/nhầm cấp to; lệch nhỏ do heo nhỏ bị che thì vẫn dùng).
"""
import glob
import json
import math
import os
import random
import sys
import time

import pig_bot as pb

DEFAULT_ROOT = "debug_pig"
FINAL_TRIM = 0.92


# ----------------------------------------------------------------------------------------------
# NẠP DỮ LIỆU
# ----------------------------------------------------------------------------------------------
def _read_jsonl(path):
    rows = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    try:
                        rows.append(json.loads(ln))
                    except Exception:
                        pass
    return rows


def find_sessions(path):
    """path -> list thư mục phiên. Nhận: thư mục phiên, debug_pig (-> phiên mới nhất), thư mục 'sessions', thư mục log kiểu cũ."""
    path = os.path.abspath(path)
    if os.path.exists(os.path.join(path, "pig_log.jsonl")):
        return [path]
    base = os.path.join(path, "sessions") if os.path.isdir(os.path.join(path, "sessions")) else path
    dirs = sorted(d for d in glob.glob(os.path.join(base, "*")) if os.path.exists(os.path.join(d, "pig_log.jsonl")))
    return dirs


def load_session(d):
    """Trả dict: dir, id, meta (session.json), samples (list dict mẫu), cmp_rows (đã tính lại bằng compare_turn không có -> lấy từ log)."""
    logs = _read_jsonl(os.path.join(d, "pig_log.jsonl"))
    cmps = {r["turn"]: r for r in _read_jsonl(os.path.join(d, "pig_cmp.jsonl"))}
    meta = {}
    try:
        with open(os.path.join(d, "session.json"), encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        pass
    samples = []
    for i, r in enumerate(logs):
        if r.get("drop_mode") == "test":
            continue                                             # chế độ TEST không bấm -> không có ảnh thật sau lượt
        tn = r["turn"]
        if tn in cmps:
            obs = [tuple(b) for b in cmps[tn]["obs"]]
        elif i + 1 < len(logs) and logs[i + 1]["W"] == r["W"]:
            obs = [tuple(b) for b in logs[i + 1]["before"]]          # log kiểu cũ: ảnh thật sau lượt k = 'before' của lượt k+1
        else:
            continue
        W = r["W"]
        before = [tuple(b) for b in r["before"]]
        hr = r.get("held_r")
        if hr is None:
            same = [b[3] for b in before if b[0] == r["held"]]
            hr = sum(same) / len(same) if same else pb.R_FRAC[r["held"] - 1] * W
        x = r["x_act"] if r.get("x_act") is not None else r["x"]
        samples.append({"before": before, "held": r["held"], "hr": hr, "x": x, "obs": obs, "y0": r.get("y0"), "W": W, "H": r["H"], "turn": tn,
                        "sess": os.path.basename(d), "sp": r.get("sp"), "explore": bool(r.get("explore"))})
    return {"dir": d, "id": os.path.basename(d), "meta": meta, "samples": samples, "logs": logs}


def _simulate_sample(smp, sp):
    y0 = smp.get("y0")
    pred, gain = pb.simulate(smp["before"], smp["W"], smp["H"], (smp["held"], smp["x"], smp["hr"], y0), sp)
    return pred, gain


def evaluate_samples(samples, sp):
    """Chạy lại mô phỏng với `sp` trên mọi mẫu, trả list dict compare_turn (kèm turn/held/x_drop/W/explore) để tóm tắt/in bảng."""
    out = []
    for smp in samples:
        pred, gain = _simulate_sample(smp, sp)
        cd = pb.compare_turn(smp["before"], smp["held"], smp["x"], pred, smp["obs"], smp["W"])
        cd.update({"turn": smp["turn"], "held": smp["held"], "x_drop": smp["x"], "W": smp["W"], "explore": smp["explore"], "sess": smp["sess"]})
        out.append(cd)
    return out


def sp_from_dict(d, base=None):
    sp = base or pb.SimParams()
    for k in pb.CAL_RANGE:
        if d and k in d:
            setattr(sp, k, float(d[k]))
    return sp


def _fmt_sp(sp):
    return ", ".join("%s=%.4g" % (k, getattr(sp, k)) for k in pb.CAL_RANGE)


# ----------------------------------------------------------------------------------------------
# TRACE (ảnh quay theo thời gian)
# ----------------------------------------------------------------------------------------------
def load_trace(sessions, log=print):
    """Với từng phiên có trace.jsonl: nhận diện heo trong từng ảnh quay (có cache trace_det.json). Trả list {before, held, hr, x, y0, W, H, frames:[(dt, balls)]}."""
    import cv2
    import numpy as np
    out = []
    for ss in sessions:
        d = ss["dir"]
        rows = _read_jsonl(os.path.join(d, "trace.jsonl"))
        if not rows:
            continue
        cache_p = os.path.join(d, "trace_det.json")
        try:
            with open(cache_p, encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}
        by_turn = {}
        for r in rows:
            by_turn.setdefault(r["turn"], []).append(r)
        smap = {s["turn"]: s for s in ss["samples"]}
        n_new = 0
        for tn, frs in by_turn.items():
            smp = smap.get(tn)
            if smp is None:
                continue
            frames = []
            for r in sorted(frs, key=lambda t: t["i"]):
                key = r["file"]
                if key not in cache:
                    im = cv2.imdecode(np.fromfile(os.path.join(d, key), dtype=np.uint8), cv2.IMREAD_COLOR)
                    if im is None:
                        continue
                    h, w = im.shape[:2]
                    try:
                        pigs = pb.detect_pigs(im, (0, 0, w, h))
                    except Exception:
                        pigs = []
                    cache[key] = [[lv, round(cx, 1), round(cy, 1), round(rr, 1)] for lv, cx, cy, rr, _s in pigs]
                    n_new += 1
                frames.append((r["dt"], [tuple(b) for b in cache[key]]))
            if frames:
                out.append({"before": smp["before"], "held": smp["held"], "hr": smp["hr"], "x": smp["x"], "y0": smp["y0"], "W": smp["W"], "H": smp["H"],
                            "turn": tn, "sess": ss["id"], "frames": frames})
        if n_new:
            try:
                with open(cache_p, "w", encoding="utf-8") as f:
                    json.dump(cache, f)
            except Exception:
                pass
            log("  trace %s: nhận diện %d ảnh mới (đã cache)" % (ss["id"], n_new))
    return out


def trace_error(tr, sp, lat, cap=0.25):
    """Sai số TB giữa mô phỏng (tại các mốc thời gian ảnh quay, trừ độ trễ bấm `lat`) và heo nhận diện được trong ảnh quay."""
    W = tr["W"]
    times = [dt - lat for dt, _ in tr["frames"] if dt - lat > 0]
    snaps = []
    if times:
        o = {"times": sorted(times)}
        pb.simulate(tr["before"], tr["W"], tr["H"], (tr["held"], tr["x"], tr["hr"], tr["y0"]), sp, trace_out=o)
        snaps = o["snaps"]
    errs, j = [], 0
    for dt, det in tr["frames"]:
        if dt - lat > 0:
            snap = snaps[j]
            j += 1
        else:
            snap = tr["before"]                                  # chưa kịp thả: chỉ có heo cũ
        pred = [b for b in snap if b[2] > 0.8 * b[3]]            # con có tâm sát/ngoài mép trên khung thì ảnh crop không thấy
        if not pred and not det:
            continue
        errs.append(pb.pred_error(pred, det, W, cap)[0])
    return errs


# ----------------------------------------------------------------------------------------------
# HIỆU CHỈNH
# ----------------------------------------------------------------------------------------------
_G = {}


def _init_worker(samples, traces, keys, w_trace):
    _G.update({"samples": samples, "traces": traces, "keys": keys, "w_trace": w_trace})


def _trim_mean(errs, frac=0.75):
    if not errs:
        return 0.0
    e = sorted(errs)
    k = max(1, int(math.ceil(len(e) * frac)))
    return sum(e[:k]) / k


def _objective(cand, samples=None, traces=None, w_trace=None, w_final=1.0):
    """cand = dict tham số (+ 'lat'). Trả (tổng, sai số trạng thái cuối, sai số trace). w_final = 0 -> chỉ tính trace (nhanh hơn)."""
    samples = _G["samples"] if samples is None else samples
    traces = _G["traces"] if traces is None else traces
    w_trace = _G["w_trace"] if w_trace is None else w_trace
    sp = sp_from_dict(cand)
    e_final = 0.0
    if w_final > 0 or not traces:
        errs = []
        for smp in samples:
            pred, _ = _simulate_sample(smp, sp)
            errs.append(pb.pred_error(pred, smp["obs"], smp["W"])[0])
        e_final = _trim_mean(errs, FINAL_TRIM)      # chỉ bỏ ~8% lượt sai nhất: lượt 'gộp rồi đẩy văng/lăn xa' chính là thứ cần học, bỏ nhiều sẽ bỏ luôn chúng
    e_tr = 0.0
    if traces:
        te = []
        for tr in traces:
            te += trace_error(tr, sp, cand.get("lat", 0.1))
        e_tr = _trim_mean(te, 0.85)
    return (w_final if (w_final > 0 or not traces) else 0.0) * e_final + (w_trace * e_tr if traces else 0.0), e_final, e_tr


def _eval_job(args):
    cand, wf = args
    return cand, _objective(cand, w_final=wf)


def _climb(best, sc, keys, lat_on, budget_s, stepf0, wf, rnd, pool, lam, samples, traces, w_trace):
    """Leo đồi (1+λ) trên keys (+ 'lat') trong budget_s giây, bước giảm dần từ stepf0. Trả (best, sc, số lần thử)."""
    t0, n, stepf, stall = time.time(), 0, stepf0, 0
    pk = list(keys) + (["lat"] if lat_on else [])
    if not pk:
        return best, sc, 0
    while time.time() - t0 < budget_s:
        cands = []
        for _ in range(lam):
            c = dict(best)
            for k in rnd.sample(pk, min(len(pk), rnd.choice((1, 2, 3)))):
                if k == "lat":
                    c["lat"] = min(0.6, max(0.0, c["lat"] + rnd.uniform(-1, 1) * 0.10 * (stepf / 0.3)))
                    continue
                lo, hi = pb.CAL_RANGE[k]
                if k in pb.CAL_ADD:
                    v = c[k] + rnd.uniform(-1.0, 1.0) * pb.CAL_ADD[k] * (stepf / 0.3)
                else:
                    v = c[k] * (1.0 + rnd.uniform(-stepf, stepf))
                c[k] = min(hi, max(lo, v))
            cands.append(c)
        res = list(pool.map(_eval_job, [(c, wf) for c in cands])) if pool else [(c, _objective(c, samples, traces, w_trace, wf)) for c in cands]
        n += len(cands)
        improved = False
        for c, s_ in res:
            if s_[0] < sc[0] - 1e-6:
                best, sc, improved = c, s_, True
        stall = 0 if improved else stall + 1
        if n % 16 < lam:
            stepf = max(0.03, stepf * 0.88)
        if stall > 80 and stepf <= 0.05:
            break
    return best, sc, n


def fit(samples, traces, start, keys, budget_s=90.0, w_trace=1.0, seed=1, workers=None, log=print):
    """Tìm tham số khớp hơn. start = dict tham số. Trả (dict tốt nhất kèm 'lat', (tổng, cuối, trace) sau, (tổng, cuối, trace) trước, số lần thử).
    Có ảnh quay (traces) thì tìm theo GIAI ĐOẠN vì độ trễ bấm `lat` đi cặp với gravity/damping (dễ kẹt ở điểm tối ưu cục bộ):
      0) quét lat  1) gravity/damping/lat theo ảnh quay  2) mọi tham số cùng lúc  3) tinh chỉnh bước nhỏ.  Không có trace: leo đồi 1 giai đoạn."""
    rnd = random.Random(seed)
    keys = list(keys)
    lat_on = bool(traces)
    best = {k: float(start[k]) for k in pb.CAL_RANGE}
    best["lat"] = float(start.get("lat", 0.12))
    workers = workers or max(1, (os.cpu_count() or 1))
    pool = None
    if workers > 1 and len(samples) >= 10:
        from concurrent.futures import ProcessPoolExecutor
        pool = ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(samples, traces, keys, w_trace))
    else:
        _init_worker(samples, traces, keys, w_trace)
    lam = workers * 2 if pool else 1
    try:
        sc = _objective(best, samples, traces, w_trace)
        s0 = sc
        total = 0
        full = set(keys) >= set(pb.CAL_RANGE)
        if not lat_on:
            if full:     # chỉnh TUẦN TỰ theo nhóm (gộp -> lăn -> nảy -> chung): 10 tham số cùng lúc hội tụ rất chậm
                for g, f, st in ((pb.CAL_ASPECTS["merge"], 0.30, 0.30), (pb.CAL_ASPECTS["roll"], 0.25, 0.30), (pb.CAL_ASPECTS["bounce"], 0.15, 0.30), (keys, 0.30, 0.12)):
                    best, sc, n = _climb(best, sc, g, False, budget_s * f, st, 1.0, rnd, pool, lam, samples, traces, w_trace)
                    total += n
                return best, sc, s0, total
            best, sc, n = _climb(best, sc, keys, False, budget_s, 0.30, 1.0, rnd, pool, lam, samples, traces, w_trace)
            return best, sc, s0, n
        # 0) quét độ trễ bấm
        tr_keys = [k for k in ("gravity", "damping") if k in keys]
        sub = traces[::max(1, len(traces) // 15)]               # quét lat trên ~15 lượt là đủ
        best_t = _objective(best, samples, sub, w_trace, 0.0)[2]
        for lat in [0.02 * i for i in range(0, 21)]:
            c = dict(best, lat=lat)
            t_ = _objective(c, samples, sub, w_trace, 0.0)[2]
            if t_ < best_t:
                best, best_t = c, t_
        sc = _objective(best, samples, traces, w_trace)
        # 1) theo ảnh quay: gravity/damping/lat
        if tr_keys:
            best, _s, n = _climb(best, sc, tr_keys, True, budget_s * 0.25, 0.30, 0.0, rnd, pool, lam, samples, traces, w_trace)
            total += n
            sc = _objective(best, samples, traces, w_trace)
        # 1b) (khi chỉnh đủ) nhóm gộp rồi nhóm lăn   2) chung   3) tinh chỉnh
        if full:
            for g in (pb.CAL_ASPECTS["merge"], pb.CAL_ASPECTS["roll"]):
                best, sc, n = _climb(best, sc, g, True, budget_s * 0.15, 0.30, 1.0, rnd, pool, lam, samples, traces, w_trace)
                total += n
        best, sc, n = _climb(best, sc, keys, True, budget_s * (0.30 if full else 0.45), 0.25, 1.0, rnd, pool, lam, samples, traces, w_trace)
        total += n
        best, sc, n = _climb(best, sc, keys, True, budget_s * (0.15 if full else 0.30), 0.10, 1.0, rnd, pool, lam, samples, traces, w_trace)
        total += n
        return best, sc, s0, total
    finally:
        if pool:
            pool.shutdown()


# ----------------------------------------------------------------------------------------------
# BÁO CÁO
# ----------------------------------------------------------------------------------------------
def session_line(ss, sp=None):
    """1 dòng tóm tắt phiên (dùng cho --history). sp=None: tham số bot đã dùng trong phiên."""
    smp = ss["samples"]
    sp0 = sp_from_dict(smp[0]["sp"]) if (sp is None and smp and smp[0].get("sp")) else (sp or pb.SimParams())
    ev = evaluate_samples(smp, sp0) if smp else []
    clean = [r for r in ev if r["kind"] != "ĐỌC"]
    kinds = {k: sum(1 for r in ev if r["kind"] == k) for k in ("tốt", "LĂN", "GỘP", "ĐỌC")}
    mrows = [r for r in ev if r["mass_ok"]]
    e = sum(r["err"] for r in clean) / len(clean) if clean else float("nan")
    mm = 100.0 * sum(1 for r in mrows if r["kind"] != "GỘP") / len(mrows) if mrows else float("nan")
    return "%-24s %-6s %4d lượt | sai số TB %.4f | gộp đúng %3.0f%% | tốt %d LĂN %d GỘP %d ĐỌC %d | %s" % (
        ss["id"], ss["meta"].get("mode", "?"), len(smp), e, mm, kinds["tốt"], kinds["LĂN"], kinds["GỘP"], kinds["ĐỌC"],
        ", ".join("%s=%.3g" % (k, getattr(sp0, k)) for k in ("gravity", "damping", "friction", "elasticity", "rad_scale", "merge_eps", "spin_damp")))


def _split(samples, val):
    """Chia train/val ổn định (không ngẫu nhiên): cứ mỗi 1/val mẫu lấy 1 mẫu cho kiểm tra chéo."""
    if val <= 0 or len(samples) < 12:
        return samples, []
    k = max(2, int(round(1.0 / val)))
    tr = [s for i, s in enumerate(samples) if i % k != k - 1]
    va = [s for i, s in enumerate(samples) if i % k == k - 1]
    return tr, va


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if "-h" in a or "--help" in a:
        print(__doc__)
        return 0

    def opt(name, default=None):
        if name in a:
            i = a.index(name)
            v = a[i + 1] if i + 1 < len(a) else default
            return v
        return default

    if opt("--read-tol") is not None:
        pb.READ_TOL = int(opt("--read-tol"))                       # ngưỡng lệch khối lượng để loại lượt 'ĐỌC' (mặc định 8)
    flags_with_val = {"--read-tol", "--aspect", "--budget", "--val", "--start", "--seed", "--trace-weight", "--workers"}
    paths, skip = [], False
    for i, t in enumerate(a):
        if skip:
            skip = False
            continue
        if t in flags_with_val:
            skip = True
            continue
        if not t.startswith("--"):
            paths.append(t)
    root = paths[0] if paths else DEFAULT_ROOT
    dirs = []
    for p in (paths or [DEFAULT_ROOT]):
        ds = find_sessions(p)
        if not ds:
            print("Không thấy log trong:", p, "(cần pig_log.jsonl; chạy bước auto_pig với calib_run=true trước)")
            continue
        dirs += ds if ("--all" in a or "--history" in a or len(paths) > 1 or os.path.exists(os.path.join(os.path.abspath(p), "pig_log.jsonl"))) else ds[-1:]
    if not dirs:
        return 1
    sessions = [load_session(d) for d in dirs]
    sessions = [s for s in sessions if s["samples"]]
    if not sessions:
        print("Các phiên chưa có lượt nào so sánh được (cần >= 1 lượt thả có ảnh thật sau đó).")
        return 1
    if "--history" in a:
        print("Lịch sử các phiên (cũ -> mới). Sai số TB tính lại bằng ĐÚNG tham số bot đã dùng trong phiên đó:")
        for s in sessions:
            print(" ", session_line(s))
        return 0
    samples = [x for s in sessions for x in s["samples"]]
    print("Đọc %d phiên, %d lượt có đối chiếu thật:" % (len(sessions), len(samples)))
    for s in sessions:
        print("  -", s["id"], "(%d lượt)" % len(s["samples"]))
    # tham số bắt đầu
    start_file = opt("--start")
    if start_file:
        with open(start_file, encoding="utf-8") as f:
            d0 = json.load(f)
        d0 = d0.get("params", d0)
    elif samples[0].get("sp"):
        d0 = samples[0]["sp"]
    else:
        d0 = {}
    sp0 = sp_from_dict(d0)
    print("\nTham số dùng để dự đoán (bot đã dùng trong log):\n  " + _fmt_sp(sp0))
    ev0 = evaluate_samples(samples, sp0)
    print("\n== KẾT QUẢ HIỆN TẠI ==")
    for ln in pb.summarize_cmp(ev0):
        print(" ", ln)
    if "--table" in a:
        print()
        for ln in pb.format_cmp_table(ev0):
            print(ln)
    n_read = sum(1 for r in ev0 if r["kind"] == "ĐỌC")
    if n_read:
        print("\n  Lưu ý: %d lượt loại 'ĐỌC' (khối lượng heo không khớp) bị bỏ khi chỉnh - xem ảnh pig_NNNN_cmp.png của các lượt đó để biết nhận diện sai chỗ nào." % n_read)
    if "--fit" not in a:
        print("\nĐể tìm tham số khớp hơn:  python pig_calib.py%s --fit   (thêm --apply để bot dùng ngay)" % ((" " + root) if paths else ""))
        return 0

    # ---- FIT
    clean = [s for s, r in zip(samples, ev0) if r["kind"] != "ĐỌC"]
    if len(clean) < 6:
        print("\nQuá ít mẫu sạch (%d) để chỉnh - chạy thêm lượt (khuyên >= 30 lượt; calib_run mặc định 40)." % len(clean))
        return 1
    aspect = opt("--aspect", "all")
    if aspect not in pb.CAL_ASPECTS:
        print("--aspect phải là một trong:", ", ".join(pb.CAL_ASPECTS))
        return 1
    keys = pb.CAL_ASPECTS[aspect]
    budget = float(opt("--budget", 90))
    val = float(opt("--val", 0.25))
    seed = int(opt("--seed", 1))
    w_trace = float(opt("--trace-weight", 1.0))
    traces = []
    if "--no-trace" not in a:
        print("\nĐọc ảnh quay (trace) ...")
        traces = load_trace(sessions)
        if traces:
            print("  %d lượt có ảnh quay (%d khung)" % (len(traces), sum(len(t["frames"]) for t in traces)))
        elif "--trace" in a:
            print("  Không có trace (chạy bước auto_pig với calib_run=true để có).")
    train, valid = _split(clean, val)
    tr_traces = [t for t in traces if any(s["turn"] == t["turn"] and s["sess"] == t["sess"] for s in train)] if traces else []
    print("Chỉnh nhóm '%s' (%s) trong %.0fs: %d mẫu chỉnh + %d mẫu kiểm tra chéo%s" % (
        aspect, ", ".join(keys), budget, len(train), len(valid), (", %d lượt trace" % len(tr_traces)) if tr_traces else ""))
    start = {k: getattr(sp0, k) for k in pb.CAL_RANGE}
    best, sc, s0, n = fit(train, tr_traces, start, keys, budget_s=budget, w_trace=w_trace, seed=seed, workers=int(opt("--workers", 0)) or None)
    spb = sp_from_dict(best)
    print("\n== KẾT QUẢ CHỈNH (%d lần thử) ==" % n)
    print("  Sai số trạng thái cuối (tập chỉnh): %.4f -> %.4f" % (s0[1], sc[1]))
    if tr_traces:
        print("  Sai số ảnh quay (trace):            %.4f -> %.4f   (độ trễ bấm ước lượng: %.2fs)" % (s0[2], sc[2], best["lat"]))
    if valid:
        v0 = _objective(dict(start), valid, [], 0.0)[1]
        v1 = _objective({k: getattr(spb, k) for k in pb.CAL_RANGE}, valid, [], 0.0)[1]
        print("  KIỂM TRA CHÉO (mẫu không dùng để chỉnh): %.4f -> %.4f  %s" % (
            v0, v1, "OK - tốt hơn thật" if v1 < v0 * 0.98 else "KHÔNG cải thiện: tham số mới có thể chỉ khớp riêng tập chỉnh (cần thêm dữ liệu)"))
    print("  Tham số cũ : " + _fmt_sp(sp0))
    print("  Tham số mới: " + _fmt_sp(spb))
    ev1 = evaluate_samples(samples, spb)
    print("\n  Nếu dùng tham số mới trên TOÀN BỘ log:")
    for ln in pb.summarize_cmp(ev1):
        print("   ", ln)
    out = {k: getattr(spb, k) for k in pb.CAL_RANGE}
    last = sessions[-1]["dir"]
    fp = os.path.join(last, "pig_params_fit.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    with open(os.path.join(last, "calib_fit.json"), "w", encoding="utf-8") as f:
        json.dump({"aspect": aspect, "keys": list(keys), "sessions": [s["id"] for s in sessions], "n_samples": len(clean), "n_train": len(train), "n_val": len(valid),
                   "err_before": s0[1], "err_after": sc[1], "trace_before": s0[2], "trace_after": sc[2], "lat": best["lat"], "params_before": start, "params_after": out},
                  f, indent=1)
    print("\nĐã ghi %s" % fp)
    if "--apply" in a:
        sess_root = os.path.dirname(os.path.dirname(last)) if os.path.basename(os.path.dirname(last)) == "sessions" else os.path.dirname(last)
        tgt = os.path.join(sess_root, "pig_params.json")
        if os.path.exists(tgt):
            bak = tgt + "." + time.strftime("%Y%m%d_%H%M%S") + ".bak"
            try:
                os.replace(tgt, bak)
                print("  sao lưu bản cũ ->", bak)
            except Exception:
                pass
        with open(tgt, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
        print("ĐÃ ÁP DỤNG: %s (bot nạp file này mỗi lần bắt đầu bước auto_pig; lưu ý reset_params=true sẽ xoá nó)" % tgt)
    else:
        print("Chưa áp dụng. Thêm --apply để ghi thành pig_params.json, hoặc tự copy pig_params_fit.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

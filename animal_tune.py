# -*- coding: utf-8 -*-
"""
animal_tune.py - SO SÁNH cấu hình bot + CHỈNH trọng số (Cross-Entropy) trên animal_sim.py. ĐA NHÂN, chạy được trên Windows.
KHÔNG sửa animal_bot.py: các đặc trưng thử nghiệm (phạt trâu theo độ dài^2, theo số hàng có trâu, thưởng khi rút trâu) được gắn tạm bằng "monkeypatch"
trong tiến trình thử; nếu cấu hình nào thắng thì mới đem vào animal_bot.py.

LỆNH
  python animal_tune.py presets                            # liệt kê cấu hình có sẵn
  python animal_tune.py compare --n 30 --presets base,bull24,bull40,sq3,shrink10,K,K_bear280
  python animal_tune.py compare --n 30 --cfg "bull_cell=24,bull_sq=2" --cfg "bull_cell=24,skill=K,bear_from=280,bear_bulls=8"
  python animal_tune.py tune --pop 16 --games 8 --gens 10 --depth 2 --beam 15      # CE: tự tìm trọng số tốt hơn, cuối cùng kiểm lại bằng ván mới
  python animal_tune.py compare --n 30 --bot D:\\cu\\animal_bot_v1.py --bot animal_bot.py        # so sánh các FILE BOT (mỗi file chạy với trọng số/mặc định của chính nó)
  python animal_tune.py compare --n 30 --bot a.py --bot b.py --presets base,bull24 --cross      # mỗi file bot x mỗi cấu hình
  (--engine file.py: file cung cấp LUẬT game cho mọi bot, mặc định animal_bot.py cùng thư mục; --bot-skill K: bật kỹ năng cho các file bot)
MẶC ĐỊNH CHUNG (áp lên MỌI cấu hình, lưu ở animal_defaults.json cạnh file này): test xong thấy bull_cell=24 tốt nhất thì chốt làm mặc định rồi test tiếp cái khác:
  python animal_tune.py defaults --set "bull_cell=24"        # chốt;   `defaults` = xem;   `defaults --clear` = về gốc
  python animal_tune.py compare --presets base,shrink10,sq3  # base = mặc định chung; các preset khác ĐÈ lên mặc định (vd shrink10 vẫn giữ bull_cell=24)
  (--no-defaults: bỏ qua mặc định chung;  --defaults-file f.json: dùng file khác;  --defaults-bots: áp cả lên các file bot;  --baseline: luôn có dòng mốc = mặc định chung)
Tùy chọn chung: --cap 500 --lens real|real-hard|easy --workers N --seed0 1000 --depth 2 --beam 20 --crowd-depth 6
  lịch trâu: --bull-early 20 --bull-late 4 --bull-from 300 [--bull-ramp-to 400]    bậc năng lượng: --ladder 1000,1500,2000,3000,4000,5000,6000,10000
Khóa trong --cfg:  tên trường Weights (bull_cell, row_fill, hole, height, danger, fit, points...), depth, beam, crowd_depth, crowd_row,
  bull_sq (phạt mỗi ô trâu^2 theo độ dài), bull_rows (phạt mỗi HÀNG có trâu), shrink (thưởng điểm mỗi ô trâu rút được trong 1 nước),
  skill (kinds: K, KYPB... rỗng = không dùng), bear_first (0/1), bear_from + bear_bulls (Gấu CHỦ ĐỘNG từ hiệp N khi ô trâu thừa >= M), label,
  bot (đường dẫn file bot .py, không chứa dấu phẩy; trống = animal_bot.py mặc định).

ĐỌC KẾT QUẢ: cột "Δ so với cấu hình đầu" là hiệu CÙNG SEED (ghép cặp) ± sai số chuẩn; chỉ tin khi |Δ| > 2×SE. Mỗi ván 500 hiệp ~10-30 giây/nhân.
MẸO: nếu hầu hết ván đều tới cap thì khó phân biệt -> tăng --cap 600, hoặc --bull-late 3, hoặc dùng cột "trâu thừa cuối".
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import statistics
import sys
import time
from dataclasses import fields, replace
from multiprocessing import Pool, TimeoutError as MpTimeout, cpu_count, freeze_support

import animal_bot as ab
import animal_sim as sim

_ORIGS = {id(ab): (getattr(ab, "evaluate_items", None), getattr(ab, "step_state", None))}    # hàm gốc của từng module bot (trước khi gắn thử nghiệm)
_MODS = [ab]


def load_module(path):
    """Nạp file bot (cache theo tiến trình) và ghi nhớ hàm gốc để hoàn tác sau khi gắn thử nghiệm."""
    mod = sim.load_bot(path)
    if id(mod) not in _ORIGS:
        _ORIGS[id(mod)] = (getattr(mod, "evaluate_items", None), getattr(mod, "step_state", None))
        _MODS.append(mod)
    return mod


def _restore_all():
    for m in _MODS:
        ev, st = _ORIGS[id(m)]
        if ev is not None:
            m.evaluate_items = ev
        if st is not None:
            m.step_state = st

LENS = {"real": [(1, 0.30), (2, 0.30), (3, 0.25), (4, 0.15)],
        "real-hard": [(1, 0.22), (2, 0.30), (3, 0.30), (4, 0.18)],
        "easy": [(1, 0.45), (2, 0.30), (3, 0.15), (4, 0.10)]}
W_FIELDS = {f.name for f in fields(ab.Weights)}
EXTRA = {"bull_sq": 0.0, "bull_rows": 0.0, "shrink": 0.0}
STR_KEYS = {"bot"}
INT_KEYS = {"depth", "beam", "crowd_depth", "crowd_row", "bear_from", "bear_bulls"}
DEFAULT_CFG = dict(label="", bot="", depth=None, beam=None, crowd_depth=None, crowd_row=4, w={}, bull_sq=0.0, bull_rows=0.0, shrink=0.0,
                   skill="", bear_first=True, bear_from=None, bear_bulls=8)

PRESETS = {
    "base": {},
    "bull12": {"w": {"bull_cell": 12.0}},
    "bull24": {"w": {"bull_cell": 24.0}},
    "bull40": {"w": {"bull_cell": 40.0}},
    "sq3": {"bull_sq": 3.0},
    "rows15": {"bull_rows": 15.0},
    "shrink10": {"shrink": 10.0},
    "shrink25": {"shrink": 25.0},
    "bull24_sq3": {"w": {"bull_cell": 24.0}, "bull_sq": 3.0},
    "KYPB": {"skill": "KYPB"},
    "K": {"skill": "K"},
    "K_bear280": {"skill": "K", "bear_from": 280, "bear_bulls": 8},
    "K_bear250": {"skill": "K", "bear_from": 250, "bear_bulls": 6},
    "bull24_K_bear280": {"w": {"bull_cell": 24.0}, "skill": "K", "bear_from": 280, "bear_bulls": 8},
    "d3": {"depth": 3},
    "crowd6": {"crowd_depth": 6},
}


# ---------------------------------------------------------------- cấu hình
def make_cfg(d=None, label=None):
    c = dict(DEFAULT_CFG)
    c["w"] = {}
    for k, v in (d or {}).items():
        if k == "_set":
            continue
        if k == "w":
            c["w"].update(v)
        else:
            c[k] = v
    c["_set"] = sorted(k for k in (d or {}) if k not in ("label", "_set", "w"))       # khóa được ĐẶT RÕ (để biết khóa nào đè lên mặc định chung)
    if label:
        c["label"] = label
    return c


def parse_cfg_string(s):
    d = {"w": {}}
    for part in s.split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise ValueError(f"cấu hình sai chỗ '{part.strip()}' (cần dạng khóa=giá_trị)")
        k, v = part.split("=", 1)
        k, v = k.strip(), v.strip()
        try:
            _ = float(v) if (k in W_FIELDS or k in EXTRA or k in INT_KEYS) else None
        except ValueError:
            raise ValueError(f"giá trị của '{k}' phải là số, không phải '{v}'")
        if k in W_FIELDS:
            d["w"][k] = float(v)
        elif k in INT_KEYS:
            d[k] = int(v)
        elif k in EXTRA:
            d[k] = float(v)
        elif k == "bear_first":
            d[k] = v not in ("0", "false", "False")
        elif k in STR_KEYS:
            d[k] = v
        elif k in ("skill", "label"):
            d[k] = v.upper() if k == "skill" else v
        else:
            raise ValueError(f"khóa lạ trong cấu hình: {k}")
    lab = d.pop("label", None)
    if not lab:
        lab = s
        if d.get("bot"):                                         # nhãn = tên file (+ các khóa còn lại)
            rest = ",".join(x for x in s.split(",") if x.strip() and not x.strip().startswith("bot="))
            lab = os.path.splitext(os.path.basename(d["bot"]))[0] + ("," + rest if rest else "")
    return make_cfg(d, lab)


def params_string(cfg):
    """Thông số THỰC TẾ đang chạy của 1 cấu hình (đã gồm mặc định chung): chỉ liệt kê những gì khác trọng số gốc của bot."""
    items = [f"{k}={v:.6g}" for k, v in cfg["w"].items()]
    items += [f"{k}={cfg[k]:.6g}" for k in EXTRA if cfg.get(k)]
    if cfg.get("skill"):
        items.append(f"skill={cfg['skill']}")
    if cfg.get("bear_from") is not None:
        items += [f"bear_from={cfg['bear_from']}", f"bear_bulls={cfg.get('bear_bulls', 8)}"]
    if cfg.get("bear_first") is False:
        items.append("bear_first=0")
    st = set(cfg.get("_set", []))
    for k in ("depth", "beam", "crowd_depth"):
        if cfg.get(k) and (k in st or k == "crowd_depth"):
            items.append(f"{k}={cfg[k]}")
    if cfg.get("bot"):
        items.insert(0, "bot=" + os.path.basename(cfg["bot"]))
    return ",".join(items) or "(trọng số gốc của bot)"


def cfg_string(cfg, names=None):
    items = []
    for k, v in cfg["w"].items():
        items.append(f"{k}={v:.3g}")
    for k in EXTRA:
        if cfg.get(k):
            items.append(f"{k}={cfg[k]:.3g}")
    for k in ("bot", "depth", "beam", "crowd_depth", "bear_from", "bear_bulls", "skill"):
        if cfg.get(k) not in (None, "", DEFAULT_CFG.get(k)):
            items.append(f"{k}={cfg[k]}")
    return ",".join(items) or "(mặc định)"


# ---------------------------------------------------------------- MẶC ĐỊNH CHUNG
DEFAULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "animal_defaults.json")
DEFAULT_KEYS = ("w", "bull_sq", "bull_rows", "shrink", "skill", "bear_first", "bear_from", "bear_bulls")


def load_defaults(path=None):
    """Đọc mặc định chung từ file JSON (thiếu/hỏng -> {})."""
    try:
        d = json.load(open(path or DEFAULTS_FILE, encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in d.items() if k in DEFAULT_KEYS and v not in (None, {}, "", 0, 0.0)} if isinstance(d, dict) else {}


def save_defaults(d, path=None):
    path = path or DEFAULTS_FILE
    if not d:
        if os.path.exists(path):
            os.remove(path)
        return
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def defaults_string(d):
    """{'w': {'bull_cell': 24}, ...} -> 'bull_cell=24,...' ('' nếu rỗng)."""
    if not d:
        return ""
    c = make_cfg(d)
    items = [f"{k}={v:.6g}" for k, v in c["w"].items()]
    items += [f"{k}={c[k]:.6g}" for k in EXTRA if c.get(k)]
    if c.get("skill"):
        items.append(f"skill={c['skill']}")
    if c.get("bear_from") is not None:
        items += [f"bear_from={c['bear_from']}", f"bear_bulls={c.get('bear_bulls', 8)}"]
    if c.get("bear_first") is False:
        items.append("bear_first=0")
    return ",".join(items)


def parse_defaults_string(text):
    """'bull_cell=24,skill=K' -> dict mặc định chung. Chỉ nhận trọng số, bull_sq/bull_rows/shrink, skill, bear_*; depth/beam/bot đặt ở chỗ khác."""
    text = (text or "").strip()
    if not text:
        return {}
    c = parse_cfg_string(text)
    bad = [k for k in c["_set"] if k not in DEFAULT_KEYS]
    if bad:
        raise ValueError(f"'{', '.join(bad)}' không đặt làm mặc định chung được (depth/beam/... ở Cài đặt chung; bot ở danh sách file bot)")
    return extract_defaults(c)


def extract_defaults(cfg):
    """Lấy phần 'thông số' (không có depth/beam/bot/label) của 1 cấu hình để làm mặc định chung."""
    d = {}
    if cfg["w"]:
        d["w"] = {k: float(v) for k, v in cfg["w"].items()}
    for k in EXTRA:
        if cfg.get(k):
            d[k] = float(cfg[k])
    if cfg.get("skill"):
        d["skill"] = cfg["skill"]
    if cfg.get("bear_from") is not None:
        d["bear_from"] = int(cfg["bear_from"])
        d["bear_bulls"] = int(cfg.get("bear_bulls", 8))
    if cfg.get("bear_first") is False:
        d["bear_first"] = False
    return d


def merge_defaults(cfg, defaults):
    """Cấu hình = mặc định chung, rồi ĐÈ bằng những khóa cấu hình tự đặt rõ."""
    if not defaults:
        return cfg
    out = dict(cfg)
    out["w"] = {**defaults.get("w", {}), **cfg["w"]}
    st = set(cfg.get("_set", []))
    for k in DEFAULT_KEYS:
        if k != "w" and k in defaults and k not in st:
            out[k] = defaults[k]
    return out


# ---------------------------------------------------------------- 1 ván (chạy trong tiến trình con)
def _apply_env(env):
    sim.LEN_W[:] = LENS[env["lens"]]
    sim.BULL_EARLY, sim.BULL_LATE = env["bull_early"], env["bull_late"]
    sim.BULL_LATE_FROM, sim.BULL_RAMP_TO = env["bull_from"], env["bull_ramp_to"]
    sim.SKILL_LADDER[:] = env["ladder"]


def _apply_cfg(cfg, bot):
    """Gắn thử nghiệm (đặc trưng phụ, thưởng rút trâu) VÀO MODULE BOT; luật game (engine) giữ nguyên."""
    _restore_all()
    bs, br, sh = cfg.get("bull_sq", 0.0), cfg.get("bull_rows", 0.0), cfg.get("shrink", 0.0)
    ev0, st0 = _ORIGS[id(bot)]
    if (bs or br) and ev0 is None:
        raise ValueError(f"{getattr(bot, '__file__', 'bot')}: không có evaluate_items nên không gắn được bull_sq/bull_rows")
    if sh and st0 is None:
        raise ValueError(f"{getattr(bot, '__file__', 'bot')}: không có step_state nên không gắn được shrink")
    if bs or br:
        def ev(items, w):
            v = ev0(items, w)
            bulls = [t for t in items if t[3] == "R"]
            if bulls:
                v -= bs * sum(t[2] ** 2 for t in bulls) + br * len({t[0] for t in bulls})
            return v
        bot.evaluate_items = ev
    if sh:
        def st(items, i, nc, preview, rules=None):
            nb, pts, dead, cl = st0(items, i, nc, preview, rules)
            b0 = sum(t[2] for t in items if t[3] == "R")
            b1 = sum(t[2] for t in nb if t[3] == "R")
            return nb, pts + sh * max(0, b0 - b1), dead, cl
        bot.step_state = st
    sim.SKILL_KINDS = cfg.get("skill") or "K"
    sim.BEAR_FIRST = bool(cfg.get("bear_first", True))


def play_task(task):
    ci, cfg, seed, env = task
    _apply_env(env)
    engine = load_module(env.get("engine", ""))
    sim.set_engine(engine, _ORIGS[id(engine)][1])
    bot = load_module(cfg.get("bot", ""))
    _apply_cfg(cfg, bot)
    info = {}
    w = replace(bot.Weights(), **cfg["w"]) if cfg["w"] else None
    turns, rows, score = sim.play(seed, cfg["depth"], cfg["beam"], weights=w, cap=env["cap"], skill=bool(cfg.get("skill")),
                                  crowd_depth=cfg.get("crowd_depth"), crowd_row=cfg.get("crowd_row", 4),
                                  bear_from=cfg.get("bear_from"), bear_bulls=cfg.get("bear_bulls", 8), info=info, bot=bot)
    return ci, seed, turns, rows, score, info


def make_env(a):
    lad = [int(x) for x in a.ladder.split(",") if x.strip()]
    return dict(cap=a.cap, lens=a.lens, bull_early=a.bull_early, bull_late=a.bull_late, bull_from=a.bull_from,
                bull_ramp_to=a.bull_ramp_to, ladder=lad, engine=getattr(a, "engine", "") or "")


# ---------------------------------------------------------------- so sánh
class Stopped(Exception):
    """Người dùng bấm Dừng (giao diện) - hủy giữa chừng."""


def evaluate(pool, cfgs, seeds, env, progress=None, stop=None):
    """-> res[ci][seed] = (turns, info). `progress(done, total)`; `stop()` trả True thì ném Stopped."""
    tasks = [(ci, c, s, env) for s in seeds for ci, c in enumerate(cfgs)]
    total = len(tasks)
    res = [dict() for _ in cfgs]
    it = pool.imap_unordered(play_task, tasks, chunksize=1)
    done = 0
    while done < total:
        if stop and stop():
            raise Stopped()
        try:
            ci, seed, turns, rows, score, info = it.next(timeout=0.25)
        except MpTimeout:
            continue
        res[ci][seed] = (turns, info)
        done += 1
        if progress:
            progress(done, total)
    return res


def mean_se(xs):
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    return m, statistics.stdev(xs) / math.sqrt(n)


def summarize(cfgs, res, seeds, cap):
    """-> list dict mỗi cấu hình (số liệu đã tính, dùng chung cho in ra dòng lệnh và bảng giao diện)."""
    n = len(seeds)
    base = [res[0][s][0] for s in seeds]
    rows = []
    for ci, c in enumerate(cfgs):
        t = [res[ci][s][0] for s in seeds]
        m, se = mean_se(t)
        row = dict(label=c["label"], params=params_string(c), mean=m, se=se, median=statistics.median(t), r300=sum(1 for x in t if x >= 300), rcap=sum(1 for x in t if x >= cap), n=n,
                   bull=sum(res[ci][s][1].get("bull_excess", 0) for s in seeds) / n, used=sum(res[ci][s][1].get("used", 0) for s in seeds) / n,
                   dm=None, dse=None, win=0, loss=0, sig=0)
        if ci > 0:
            d = [x - y for x, y in zip(t, base)]
            dm, dse = mean_se(d)
            row.update(dm=dm, dse=dse, win=sum(1 for x in d if x > 0), loss=sum(1 for x in d if x < 0),
                       sig=(1 if dm > 0 else -1) if (dse and abs(dm) > 2 * dse) else 0)
        rows.append(row)
    return rows


def report(cfgs, res, seeds, cap, log=print):
    rows = summarize(cfgs, res, seeds, cap)
    log(f"\n{'cấu hình':36s} {'hiệp TB±SE':>14s} {'trung vị':>8s} {'>=300':>6s} {'cap':>6s} {'trâu thừa':>9s} {'kỹ năng':>7s} | {'Δ so với cấu hình đầu (ghép cặp)':>34s}")
    for r in rows:
        if r["dm"] is None:
            dtxt = "-"
        else:
            dtxt = f"{r['dm']:+7.1f} ± {r['dse']:5.1f}  (thắng {r['win']} / thua {r['loss']})" + ("  **" if r["sig"] else "")
        log(f"{r['label'][:36]:36s} {r['mean']:7.1f}±{r['se']:5.1f} {r['median']:8.0f} {r['r300']:3d}/{r['n']:<2d} {r['rcap']:3d}/{r['n']:<2d} {r['bull']:9.1f} {r['used']:7.1f} | {dtxt}")
    log("(** = chênh lệch > 2 lần sai số chuẩn)")
    log("Thông số đang dùng của từng dòng:")
    for r in rows:
        log(f"  {r['label'][:30]:30s} {r['params']}")
    return rows


def bot_label(path, all_paths):
    stem = os.path.splitext(os.path.basename(path))[0]
    dup = [q for q in all_paths if os.path.splitext(os.path.basename(q))[0] == stem]
    return stem if len(dup) <= 1 else os.path.basename(os.path.dirname(os.path.abspath(path))) + "/" + stem


def build_cfgs(presets=(), cfg_strings=(), json_path=None, depth=2, beam=20, crowd_depth=0, bots=(), cross=False, bot_skill="",
               defaults=None, defaults_bots=False, add_baseline=False):
    """presets/cfg_strings/json -> các cấu hình trên bot mặc định; bots = list đường dẫn file bot.
    cross=False: mỗi file bot là 1 cấu hình riêng (trọng số mặc định của chính file đó); cross=True: mỗi file bot x mỗi cấu hình đã chọn.
    defaults: MẶC ĐỊNH CHUNG, áp lên mọi cấu hình (khóa tự đặt trong cấu hình thì đè lên). defaults_bots: áp cả lên các file bot (cross=False).
    add_baseline: luôn đặt ở đầu 1 dòng mốc = mặc định chung (nếu đã chọn preset 'base' thì đưa nó lên đầu)."""
    base = []
    for name in [x.strip() for x in presets if x.strip()]:
        if name not in PRESETS:
            raise ValueError(f"preset lạ: {name} (xem `presets`)")
        base.append(make_cfg(PRESETS[name], name))
    for s_ in cfg_strings:
        if s_.strip():
            base.append(parse_cfg_string(s_.strip()))
    if json_path:
        for d in json.load(open(json_path, encoding="utf-8")):
            base.append(make_cfg(d, d.get("label")))
    base = [merge_defaults(c, defaults) for c in base]
    bots = [b for b in bots if b]
    if add_baseline and not (cross and bots):
        i = next((k for k, c in enumerate(base) if c["label"] == "base"), None)
        if i is not None:
            base.insert(0, base.pop(i))
        else:
            base.insert(0, merge_defaults(make_cfg({}, "mặc định chung"), defaults))
    cfgs = list(base)
    if bots:
        if cross and base:
            cfgs = []
            for pth in bots:
                bl = bot_label(pth, bots)
                for c in base:
                    cc = make_cfg({k: v for k, v in c.items() if k not in ("w", "label")}, f"{bl}|{c['label']}")
                    cc["w"] = dict(c["w"])
                    cc["bot"] = pth
                    cfgs.append(cc)
        else:
            for pth in bots:
                d_ = {"bot": pth}
                if bot_skill:
                    d_["skill"] = bot_skill.upper()
                c_ = make_cfg(d_, bot_label(pth, bots))
                cfgs.append(merge_defaults(c_, defaults) if defaults_bots else c_)
    for c in cfgs:                         # độ sâu/beam chung nếu cấu hình không đặt riêng
        c["depth"] = c["depth"] or depth
        c["beam"] = c["beam"] or beam
        if c["crowd_depth"] is None and crowd_depth:
            c["crowd_depth"] = crowd_depth
    return cfgs


def validate(cfgs, env, log=print):
    """Nạp thử các file bot/engine ngay trong tiến trình hiện tại: báo lỗi rõ ràng TRƯỚC khi chạy đa nhân. -> list ghi chú."""
    notes = []
    eng = load_module(env.get("engine", ""))
    sim.check_engine(eng, os.path.basename(getattr(eng, "__file__", "") or "engine"))
    seen = set()
    for c in cfgs:
        pth = c.get("bot", "")
        mod = load_module(pth)
        key = (pth, bool(c.get("skill")))
        if key in seen:
            continue
        seen.add(key)
        lab = os.path.basename(pth) if pth else "animal_bot.py (mặc định)"
        notes += sim.check_bot(mod, lab, need_skill=bool(c.get("skill")))
        if c["w"]:
            bad = [k for k in c["w"] if not hasattr(mod.Weights(), k)]
            if bad:
                raise ValueError(f"{lab}: Weights không có trường {', '.join(bad)}")
    for n in notes:
        log("lưu ý: " + n)
    return notes


def write_csv(path, cfgs, res, seeds):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(["label", "seed", "turns", "bull_cells", "bull_excess", "skills_used", "dead"])
        for ci, c in enumerate(cfgs):
            for s in seeds:
                t, inf = res[ci][s]
                wr.writerow([c["label"], s, t, inf.get("bull_cells"), inf.get("bull_excess"), inf.get("used"), inf.get("dead")])


def run_compare(a, pool, cfgs, log=print, progress=None, stop=None):
    """a: có n, cap, lens, seed0, bull_*, ladder. -> (res, seeds, rows)."""
    env = make_env(a)
    validate(cfgs, env, log)
    seeds = [a.seed0 + k for k in range(a.n)]
    if env["engine"]:
        log(f"file LUẬT game (engine): {env['engine']}")
    log(f"{len(cfgs)} cấu hình x {a.n} ván = {len(cfgs) * a.n} ván, {a.workers} nhân, cap {a.cap}, lens {a.lens}, trâu {a.bull_early}->{a.bull_late} từ hiệp {a.bull_from}")
    t0 = time.time()
    res = evaluate(pool, cfgs, seeds, env, progress, stop)
    rows = report(cfgs, res, seeds, a.cap, log)
    log(f"xong sau {time.time() - t0:.0f}s")
    return res, seeds, rows


def cmd_compare(a, pool):
    names = [x for x in (a.presets or "").split(",") if x.strip()]
    args = (a.depth, a.beam, a.crowd_depth, a.bot or [], a.cross, a.bot_skill, a.defaults, a.defaults_bots, a.baseline)
    try:
        cfgs = build_cfgs(names, a.cfg or [], a.json, *args)
        if not cfgs:
            cfgs = build_cfgs(["base", "bull24", "sq3", "shrink10", "K", "K_bear280"], [], None, *args)
        print("mặc định chung:", defaults_string(a.defaults) or "(không - trọng số gốc của bot)")
        res, seeds, _rows = run_compare(a, pool, cfgs)
    except ValueError as e:
        raise SystemExit(f"LỖI: {e}")
    if a.csv:
        write_csv(a.csv, cfgs, res, seeds)
        print("đã ghi", a.csv)


def cmd_defaults(a):
    path = a.defaults_file or DEFAULTS_FILE
    if a.clear:
        save_defaults({}, path)
        print("đã xóa mặc định chung (về trọng số gốc của bot)")
    elif a.set is not None:
        try:
            d = parse_defaults_string(a.set)
        except ValueError as e:
            raise SystemExit(f"LỖI: {e}")
        save_defaults(d, path)
        print("đã lưu mặc định chung:", defaults_string(d) or "(rỗng)", "->", path)
    else:
        print("mặc định chung hiện tại:", defaults_string(load_defaults(path)) or "(không - trọng số gốc của bot)", f"[{path}]")


# ---------------------------------------------------------------- CE
def run_ce(a, pool, log=print, progress=None, stop=None, on_gen=None):
    """Cross-Entropy chỉnh trọng số. a: depth, beam, crowd_depth, cfg (list), params, pop, games, gens, elite, alpha, fit_bull, verify, seed0, out + trường env.
    -> dict(cands={tên: cfg}, rows=[bảng kiểm lại], hist=[...], stopped=bool)"""
    base = parse_cfg_string(a.cfg[0]) if a.cfg else make_cfg({}, "base")
    base = merge_defaults(base, getattr(a, "defaults", None))
    base["depth"], base["beam"] = base["depth"] or a.depth, base["beam"] or a.beam
    if a.crowd_depth:
        base["crowd_depth"] = a.crowd_depth
    names = [x.strip() for x in a.params.split(",") if x.strip()]
    if not names:
        raise ValueError("chưa chọn tham số nào để chỉnh")
    dw = ab.Weights()

    def get(cfg, k):
        return cfg["w"].get(k, getattr(dw, k)) if k in W_FIELDS else cfg.get(k, 0.0)

    def put(cfg, vec):
        c = make_cfg({k: v for k, v in cfg.items() if k not in ("w", "label")}, "")
        c["w"] = dict(cfg["w"])
        for k, v in zip(names, vec):
            if k in W_FIELDS:
                c["w"][k] = float(v)
            else:
                c[k] = float(v)
        return c

    mean = [float(get(base, k)) for k in names]
    std = [max(0.5 * abs(m), 5.0 if k in EXTRA else 1.0) for k, m in zip(names, mean)]
    env = make_env(a)
    validate([base], env, log)
    rng = random.Random(a.seed0)
    n_elite = max(2, int(round(a.elite * a.pop)))
    best = (-1e9, list(mean))
    hist = []
    stopped = False
    log(f"mặc định chung: {defaults_string(getattr(a, 'defaults', None)) or '(không)'}")
    log(f"CE: {len(names)} tham số {names}\n    quần thể {a.pop}, {a.games} ván/ứng viên (cùng seed trong 1 thế hệ), {a.gens} thế hệ, elite {n_elite}, {a.workers} nhân, cap {a.cap}")
    t0 = time.time()
    try:
        for g in range(a.gens):
            seeds = [a.seed0 + 100000 + 977 * g + k for k in range(a.games)]
            vecs = [list(mean)] + [[max(0.0, rng.gauss(m, s)) for m, s in zip(mean, std)] for _ in range(a.pop - 1)]
            cfgs = [put(base, v) for v in vecs]
            res = evaluate(pool, cfgs, seeds, env, (lambda d, t, g=g: progress(g * 1.0 + d / t, a.gens)) if progress else None, stop)
            fit = []
            for ci in range(len(cfgs)):
                ts = [res[ci][s][0] for s in seeds]
                bx = [res[ci][s][1].get("bull_excess", 0) for s in seeds]
                fit.append(sum(ts) / len(ts) - a.fit_bull * sum(bx) / len(bx))
            order = sorted(range(len(cfgs)), key=lambda i: -fit[i])
            elites = [vecs[i] for i in order[:n_elite]]
            nm = [sum(e[j] for e in elites) / len(elites) for j in range(len(names))]
            ns = [math.sqrt(sum((e[j] - nm[j]) ** 2 for e in elites) / len(elites)) + 0.02 * max(1.0, abs(nm[j])) for j in range(len(names))]
            mean = [a.alpha * x + (1 - a.alpha) * y for x, y in zip(nm, mean)]
            std = [a.alpha * x + (1 - a.alpha) * y for x, y in zip(ns, std)]
            if fit[order[0]] > best[0]:
                best = (fit[order[0]], list(vecs[order[0]]))
            hist.append({"gen": g, "best": fit[order[0]], "mean": sum(fit) / len(fit), "center_fit": fit[0], "mean_vec": list(mean)})
            log(f"gen {g + 1:2d}/{a.gens}  tốt nhất {fit[order[0]]:6.1f} | TB {sum(fit) / len(fit):6.1f} | tâm cũ {fit[0]:6.1f} | {time.time() - t0:5.0f}s | tâm = "
                + " ".join(f"{k}={v:.2f}" for k, v in zip(names, mean)))
            if on_gen:
                on_gen(hist[-1])
            if a.out:
                json.dump({"names": names, "hist": hist, "best_vec": best[1], "mean_vec": mean}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except (KeyboardInterrupt, Stopped):
        stopped = True
        log("(dừng sớm, dùng kết quả hiện có)")
    cand = {"tâm CE": put(base, mean), "ứng viên tốt nhất": put(base, best[1])}
    out = dict(cands=cand, rows=[], hist=hist, stopped=stopped, base=base)
    if a.verify > 0 and hist and not stopped:
        cfgs = [dict(base, label="base (xuất phát)")] + [dict(c, label=k) for k, c in cand.items()]
        seeds = [a.seed0 + 555000 + k for k in range(a.verify)]
        log(f"\nKIỂM LẠI trên {a.verify} ván MỚI (không dùng khi chỉnh):")
        try:
            res = evaluate(pool, cfgs, seeds, env, progress and (lambda d, t: progress(d, t)), stop)
            out["rows"] = report(cfgs, res, seeds, a.cap, log)
        except Stopped:
            out["stopped"] = True
    for k, c in cand.items():
        log(f"\n[{k}]  --cfg \"{cfg_string(c)}\"")
        wv = {kk: round(v, 3) for kk, v in c["w"].items()}
        extra = {kk: round(c[kk], 3) for kk in EXTRA if c.get(kk)}
        if wv:
            log("   Weights: replace(Weights(), " + ", ".join(f"{kk}={v}" for kk, v in wv.items()) + ")")
        if extra:
            log(f"   đặc trưng phụ (cần thêm vào evaluate_items/step_state của animal_bot.py nếu muốn dùng): {extra}")
    return out


def cmd_tune(a, pool):
    run_ce(a, pool)
    if a.out:
        print(f"\nlog: {a.out}")


def cmd_presets(a, pool=None):
    for k, v in PRESETS.items():
        print(f"{k:20s} {json.dumps(v, ensure_ascii=False)}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=["compare", "tune", "presets", "defaults"])
    p.add_argument("--n", type=int, default=24, help="số ván mỗi cấu hình (compare)")
    p.add_argument("--presets", default="")
    p.add_argument("--cfg", action="append")
    p.add_argument("--json")
    p.add_argument("--csv", default="")
    p.add_argument("--bot", action="append", help="file bot .py (lặp lại để so nhiều file)")
    p.add_argument("--cross", action="store_true", help="mỗi file bot x mỗi cấu hình đã chọn")
    p.add_argument("--bot-skill", default="", help="kỹ năng cho các file bot, vd K hoặc KYPB (trống = không dùng)")
    p.add_argument("--engine", default="", help="file cung cấp LUẬT game (mặc định animal_bot.py)")
    p.add_argument("--no-defaults", action="store_true", help="bỏ qua mặc định chung")
    p.add_argument("--defaults-file", default="", help="file JSON mặc định chung (mặc định: animal_defaults.json cạnh animal_tune.py)")
    p.add_argument("--defaults-bots", action="store_true", help="áp mặc định chung cả lên các file bot")
    p.add_argument("--baseline", action="store_true", help="luôn có dòng mốc = mặc định chung ở đầu bảng")
    p.add_argument("--set", default=None, help="(lệnh defaults) chốt mặc định chung, vd \"bull_cell=24,skill=K\"")
    p.add_argument("--clear", action="store_true", help="(lệnh defaults) xóa mặc định chung")
    p.add_argument("--cap", type=int, default=500)
    p.add_argument("--lens", choices=list(LENS), default="real")
    p.add_argument("--depth", type=int, default=2)
    p.add_argument("--beam", type=int, default=20)
    p.add_argument("--crowd-depth", type=int, default=0)
    p.add_argument("--workers", type=int, default=max(1, cpu_count() - 1))
    p.add_argument("--seed0", type=int, default=1000)
    p.add_argument("--bull-early", type=int, default=20)
    p.add_argument("--bull-late", type=int, default=4)
    p.add_argument("--bull-from", type=int, default=300)
    p.add_argument("--bull-ramp-to", type=int, default=None)
    p.add_argument("--ladder", default="1000,1500,2000,3000,4000,5000,6000,10000")
    # tune
    p.add_argument("--pop", type=int, default=16)
    p.add_argument("--games", type=int, default=8)
    p.add_argument("--gens", type=int, default=10)
    p.add_argument("--elite", type=float, default=0.25)
    p.add_argument("--alpha", type=float, default=0.7, help="làm mượt cập nhật CE (1 = thay hẳn)")
    p.add_argument("--fit-bull", type=float, default=0.3, help="trừ vào độ thích nghi: hệ số x số ô trâu thừa cuối ván (phân biệt khi mọi ván đều tới cap)")
    p.add_argument("--params", default="bull_cell,row_fill,hole,height,danger,fit,bull_sq,bull_rows,shrink")
    p.add_argument("--verify", type=int, default=24)
    p.add_argument("--out", default="tune_log.json")
    a = p.parse_args()
    if a.cmd == "presets":
        return cmd_presets(a)
    if a.cmd == "defaults":
        return cmd_defaults(a)
    a.defaults = {} if a.no_defaults else load_defaults(a.defaults_file or None)
    with Pool(a.workers) as pool:
        (cmd_compare if a.cmd == "compare" else cmd_tune)(a, pool)


if __name__ == "__main__":
    freeze_support()
    main()

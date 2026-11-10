# -*- coding: utf-8 -*-
"""
animal_sim.py - Game GIẢ "Thế Giới Động Vật" để chơi thử/chỉnh trọng số cho animal_bot.py (không cần LDPlayer, không import tkinter).

BẢN 2 (18/10, sát game thật hơn):
  - LỊCH TRÂU: `BULL_EARLY` hiệp/trâu đến hiệp `BULL_LATE_FROM`, sau đó `BULL_LATE` hiệp/trâu (mặc định 20 -> 4 từ hiệp 300; `BULL_RAMP_TO` != None thì giảm DẦN tới mốc đó).
    Bản 1 chỉ có 20 hiệp/trâu suốt ván nên QUÁ DỄ: bot depth 2-3 sống vượt 500 hiệp, còn game thật chết ở 300-480.
  - NĂNG LƯỢNG: bậc giá kỹ năng tăng dần sau mỗi lần dùng `SKILL_LADDER` = 1000-1500-2000-3000-4000-5000-6000-10000 (lần thứ 9 trở đi dùng giá cuối). Bản 1 cố định 3000.
  - GẤU CHỦ ĐỘNG (tùy chọn, chỉ để THỬ): `--bear-from=280 --bear-bulls=8` = từ hiệp 280, khi tổng ô trâu THỪA (độ dài - 1) >= 8, có Gấu trên bàn và đủ năng lượng thì dùng Gấu ngay,
    không đợi kẹt/thua. Nếu không đặt thì giữ đúng luật của bot (CHỈ khi kẹt/chắc chắn thua).
  - `--crowd=6`: như bot thật, đổi sang depth cao hơn khi khối chạm sát hàng `crowd_row` (mặc định 4).

Luật dùng đúng như mô phỏng của animal_bot.py (docstring mục 1; bản 3: trâu co lại, điểm theo thanh + Buff; loài sinh ngẫu nhiên theo độ dài, KHÔNG mô phỏng cú tấn công của trâu): bàn 9x11, kéo thanh ngang, rơi cứng, hàng đầy thì ăn (dây chuyền),
mỗi hiệp đẩy 1 hàng mới từ đáy lên, còn thú ở hàng 0 khi hàng mới tới = THUA. Hàng mới sinh NGẪU NHIÊN (phân bố độ dài/độ đầy đo
xấp xỉ từ 2 ảnh màn chơi: mỗi hàng mới khoảng 6/9 ô có thú), dải xem trước báo đúng hàng sắp tới.

Chạy:  python animal_sim.py [số_ván] [depth] [beam]      (mặc định 20 ván, depth 2, beam 30, cap 150; nên thêm --real --cap=500)
       python animal_sim.py --compare                  (so vài bộ trọng số)
       (thêm --real / --real-hard: độ dài thú sát game thật, xem AI_PROGRESS 18/10; mặc định mô phỏng quá dễ)
       python animal_sim.py --skill-compare [số_ván] [depth] [beam] [--kinds=KYPB] [--hard]   (so: không kỹ năng | Gấu luôn trước | kỹ năng giá trị cao nhất; in hiệp sống TB + điểm TB)
       python animal_sim.py --skill [số_ván] [depth] [beam]   (bật KỸ NĂNG: năng lượng = điểm ăn (tối đa 10000), giá theo `SKILL_LADDER`, CHỈ GẤU, khi KẸT/chắc chắn thua; cap 400)
       python animal_sim.py --bear-compare [số_ván] [depth] [beam]   (so: không kỹ năng | KYPB khi kẹt | K khi kẹt | K khi kẹt + Gấu chủ động; dùng --bear-from/--bear-bulls)
       python animal_sim.py 20 2 20 --real --cap=500 --bot=D:\\cu\\animal_bot_v2.py   (chạy 1 FILE BOT khác thay animal_bot.py; --engine=file.py: file cung cấp LUẬT game, mặc định animal_bot.py)
Cờ phụ:  --cap=500  --bull-early=20  --bull-late=4  --bull-from=300  --bull-ramp-to=400  --old-bull (= 20 hiệp/trâu cả ván)  --ladder=1000,1500,...  --bear-from=280  --bear-bulls=8  --crowd=6
Kết quả: số hiệp sống sót trung bình (tối đa `cap`), số hàng ăn, số lần dùng kỹ năng.
Mô phỏng kỹ năng: không tốn hiệp; Gấu đóng băng 3 hiệp + rút trâu còn 1 ô (cần có ÍT NHẤT 1 con Gấu trên bàn, như game thật).
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import os
import random
import sys
import time
from dataclasses import replace

import animal_bot as ab

_DEFAULT_BOT = ab                     # bot mặc định (quyết định nước đi); `ab` bên dưới là ENGINE (luật game), đổi được bằng set_engine()
_STEP = ab.step_state                 # bản gốc: animal_tune.py có thể thay `step_state` của bot (thưởng phụ khi tìm nước) nhưng ván thật vẫn dùng luật gốc
_LOADED = {}


def load_bot(path):
    """Nạp 1 file .py (bản animal_bot.py bất kỳ) thành module riêng (tên duy nhất, không đụng animal_bot đã nạp). '' = animal_bot.py mặc định."""
    if not path:
        return _DEFAULT_BOT
    p = os.path.abspath(path)
    if not os.path.isfile(p):
        raise ValueError(f"không thấy file bot: {p}")
    key = (p, os.path.getmtime(p))
    if key in _LOADED:
        return _LOADED[key]
    d = os.path.dirname(p)
    if d not in sys.path:
        sys.path.append(d)            # để file bot import được các module cạnh nó (ưu tiên thấp, không che module của repo)
    name = "_bot_%s_%d" % (hashlib.md5(p.encode("utf-8")).hexdigest()[:8], int(key[1]))
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod           # dataclass cần module có trong sys.modules
    try:
        spec.loader.exec_module(mod)
    except BaseException as e:
        sys.modules.pop(name, None)
        raise ValueError(f"không nạp được {os.path.basename(p)}: {type(e).__name__}: {e}")
    _LOADED[key] = mod
    return mod


def _accepts(fn, name):
    try:
        ps = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return True
    return name in ps or any(q.kind == q.VAR_KEYWORD for q in ps.values())


def check_bot(mod, label="bot", need_skill=False):
    """Kiểm tra module có đủ API để làm BOT. Ném ValueError nếu thiếu; trả list ghi chú (cảnh báo không chết)."""
    need = ["Bar", "Weights", "beam_search"] + (["choose_skill"] if need_skill else [])
    miss = [n for n in need if not hasattr(mod, n)]
    if miss:
        raise ValueError(f"{label}: thiếu {', '.join(miss)} - không phải bản animal_bot.py tương thích")
    notes = []
    if not _accepts(mod.beam_search, "preview"):
        notes.append(f"{label}: beam_search không nhận 'preview' -> bot này không dùng hàng xem trước")
    if not need_skill and not hasattr(mod, "choose_skill"):
        notes.append(f"{label}: không có choose_skill -> không dùng được kỹ năng")
    return notes


def check_engine(mod, label="engine"):
    need = ["step_state", "_settle_items", "_gen_moves_items", "skill_candidates", "ROWS", "COLS", "FREEZE_TURNS"]
    miss = [n for n in need if not hasattr(mod, n)]
    if miss:
        raise ValueError(f"{label}: thiếu {', '.join(miss)} - không dùng được làm file LUẬT game")


def set_engine(mod, step=None):
    """Chọn module làm LUẬT game (ăn hàng, đẩy hàng, trâu, hiệu ứng kỹ năng). Mọi bot đều chơi trên cùng luật này nên so sánh công bằng."""
    global ab, _STEP
    ab = mod
    _STEP = step or mod.step_state


def _call(fn, *args, **kw):
    """Gọi hàm của bot, bỏ các tham số mà bản bot cũ không có."""
    try:
        ps = inspect.signature(fn).parameters
        if not any(q.kind == q.VAR_KEYWORD for q in ps.values()):
            kw = {k: v for k, v in kw.items() if k in ps}
    except (TypeError, ValueError):
        pass
    return fn(*args, **kw)


def _engine_cand(items, cand):
    """Hiệu ứng kỹ năng do LUẬT game tính (không tin phần bot tự tính)."""
    try:
        for c in ab.skill_candidates(items, cand[1]):
            if c[0] == cand[0] and c[1] == cand[1]:
                return c
    except Exception:
        pass
    return cand

LEN_W = [(1, 0.45), (2, 0.30), (3, 0.15), (4, 0.10)]
SKILL_LADDER = [1000, 1500, 2000, 3000, 4000, 5000, 6000, 10000]     # giá lần dùng kỹ năng thứ 1, 2, 3...; sau mốc cuối giữ giá cuối
SKILL_KINDS = "K"                     # --kinds=KYPB
BEAR_FIRST = True                     # --best: chọn kỹ năng giá trị cao nhất, không ưu tiên Gấu
BULL_EARLY = 20                       # cứ N hiệp hiện THÊM 1 con trâu (đếm ngược 20 hiệp của game)
BULL_LATE = 4                         # sau hiệp BULL_LATE_FROM: cứ N hiệp 1 trâu (người dùng quan sát 18/10: ~4 hiệp/trâu sau hiệp ~300)
BULL_LATE_FROM = 300
BULL_RAMP_TO = None                   # None: đổi đột ngột ở BULL_LATE_FROM; số: giảm dần tuyến tính tới hiệp này
FILL_CHOICES = [5, 6, 6, 6, 7]       # --hard: hàng mới đầy hơn (7-8/9 ô) để thử sức chịu đựng


def skill_cost(used):
    return float(SKILL_LADDER[min(used, len(SKILL_LADDER) - 1)])


def bull_every(turn):
    """Số hiệp giữa 2 con trâu mới, tại hiệp `turn`."""
    if turn < BULL_LATE_FROM:
        return BULL_EARLY
    if BULL_RAMP_TO and turn < BULL_RAMP_TO:
        f = (turn - BULL_LATE_FROM) / max(1, BULL_RAMP_TO - BULL_LATE_FROM)
        return max(BULL_LATE, int(round(BULL_EARLY + (BULL_LATE - BULL_EARLY) * f)))
    return BULL_LATE


def bull_excess(items):
    """Tổng ô trâu THỪA (độ dài - 1): phần Gấu có thể rút được."""
    return sum(t[2] - 1 for t in items if t[3] == "R")


def rand_len(rng):
    x = rng.random()
    a = 0.0
    for ln, p in LEN_W:
        a += p
        if x <= a:
            return ln
    return 1


KIND_BY_LEN = {1: "OOP", 2: "PW", 3: "BY", 4: "KRR"}      # loài theo độ dài (đoán từ ảnh: đà điểu 1, hươu 1-2, ngựa vằn 2, voi/sư tử 3, gấu 4, trâu 4)


def rand_kind(rng, ln):
    return rng.choice(KIND_BY_LEN.get(ln, "O"))


def rand_row(rng, fill=None):
    """Hàng mới: list (cột, dài) với khoảng 6/9 ô có thú, luôn còn ít nhất 1 ô trống."""
    target = fill or rng.choice(FILL_CHOICES)
    for _ in range(50):
        bars = []
        col = 0
        used = 0
        # đặt thanh lần lượt từ trái sang phải với khe ngẫu nhiên
        free = ab.COLS - target
        while col < ab.COLS:
            if free > 0 and rng.random() < 0.35:
                col += 1
                free -= 1
                continue
            ln = min(rand_len(rng), ab.COLS - col)
            bars.append((col, ln))
            used += ln
            col += ln
            if col < ab.COLS and rng.random() < 0.25 and free > 0:
                col += 1
                free -= 1
        if 4 <= used <= ab.COLS - 1:
            return bars
    return [(0, 3), (4, 2)]


def new_game(rng, start_rows=8):
    items = []
    for _ in range(start_rows):
        items = [(t[0] - 1, t[1], t[2], t[3]) for t in items]
        for c, ln in rand_row(rng):
            items.append((ab.ROWS - 1, c, ln, rand_kind(rng, ln)))
        items, _, _, _, _ = ab._settle_items(items)
    return items


def play(seed, depth=2, beam=30, weights=None, cap=150, start_rows=8, policy="beam", skill=False, stats=None,
         crowd_depth=None, crowd_row=4, bear_from=None, bear_bulls=8, info=None, bot=None):
    """1 ván giả (bot = module quyết định nước đi, mặc định animal_bot.py; luật game theo engine `ab`). -> (số hiệp sống, số hàng ăn, điểm). `info` (dict, tùy chọn) nhận: used (số lần kỹ năng), bull_cells, bull_excess, dead, energy."""
    rng = random.Random(seed)
    energy = 0.0
    score = 0.0
    freeze = 0
    used = 0
    since_bull = 0
    dead = False
    items = new_game(rng, start_rows)
    preview = rand_row(rng)
    bot = bot if bot is not None else _DEFAULT_BOT
    w = weights or bot.Weights()
    can_skill = skill and hasattr(bot, "choose_skill")
    turns = rows = 0
    while turns < cap:
        bars = [bot.Bar(*t) for t in items]
        pv = [] if freeze > 0 else preview
        cost = skill_cost(used)
        if can_skill and energy >= cost and policy != "random":
            cand = None
            if bear_from is not None and turns >= bear_from and freeze == 0 and "K" in SKILL_KINDS and bull_excess(items) >= bear_bulls:
                cs = ab.skill_candidates(items, "K")             # Gấu CHỦ ĐỘNG (chỉ để thử): cần có Gấu trên bàn
                if cs:
                    cand = cs[0]
            if cand is None:
                ch = _call(bot.choose_skill, bars, pv, None, SKILL_KINDS, depth=depth, beam=beam, w=weights, bear_first=BEAR_FIRST)
                if ch is not None:
                    cand = _engine_cand(items, ch[1])
            if cand is not None:
                items = [(t[0], t[1], t[2], t[3]) for t in cand[2]]
                energy -= cost
                used += 1
                if cand[3]:
                    freeze = ab.FREEZE_TURNS
                energy += cand[4]
                score += cand[4]
                continue
        if policy == "random":
            mv = ab._gen_moves_items(items)
            if not mv:
                break
            i, nc = rng.choice(mv)
        else:
            d = depth
            if crowd_depth and items and min(t[0] for t in items) <= crowd_row:
                d = crowd_depth
            path, _ = _call(bot.beam_search, bars, d, beam, w=w, preview=pv)
            if not path:
                break
            r, c0, ln, nc = path[0]
            i = next(k for k, t in enumerate(items) if (t[0], t[1], t[2]) == (r, c0, ln))
        items, pts, dead, cl = _STEP(items, i, nc, pv)
        score += pts
        energy = min(energy + pts, 10000.0)
        if freeze > 0:
            freeze -= 1
        since_bull += 1
        us = [k for k, t in enumerate(items) if t[3] == "U"]
        bull_k = max(us, key=lambda k: items[k][2]) if (us and since_bull >= bull_every(turns + 1)) else None
        if bull_k is not None:                     # hết đếm ngược mà hàng mới bị ăn ngay (không có thanh 'U') -> trâu HOÃN sang hàng kế (bản cũ thì bỏ lượt đó)
            since_bull = 0
        items = [(t[0], t[1], t[2], "R" if k == bull_k else (rand_kind(rng, t[2]) if t[3] == "U" else t[3])) for k, t in enumerate(items)]     # hàng mới 'U' -> loài ngẫu nhiên
        rows += cl
        turns += 1
        if dead:
            break
        if not items:                              # dọn sạch bàn: thêm 2 hàng
            for _ in range(2):
                for c, ln in rand_row(rng):
                    items.append((ab.ROWS - 1, c, ln, rand_kind(rng, ln)))
        preview = rand_row(rng)
    if stats is not None:
        stats.append(used)
    if info is not None:
        info.update(used=used, bull_cells=sum(t[2] for t in items if t[3] == "R"), bull_excess=bull_excess(items), dead=bool(dead), energy=energy)
    return turns, rows, score


def run(n=20, depth=2, beam=30, weights=None, cap=150, label="", start_rows=8, policy="beam", seed0=1000, skill=False, **kw):
    t = time.time()
    used = []
    infos = []
    res = []
    for s in range(n):
        inf = {}
        res.append(play(seed0 + s, depth, beam, weights, cap, start_rows, policy, skill, used, info=inf, **kw))
        infos.append(inf)
    tu = sum(r[0] for r in res) / n
    ro = sum(r[1] for r in res) / n
    full = sum(1 for r in res if r[0] >= cap)
    r300 = sum(1 for r in res if r[0] >= 300)
    sc = sum(r[2] for r in res) / n
    bx = sum(i.get("bull_excess", 0) for i in infos) / n
    print(f"{label:34s} hiệp TB {tu:6.1f} | hàng ăn TB {ro:5.1f} | >=300: {r300}/{n} | tới cap {full}/{n} | điểm TB {sc:8.0f} | trâu thừa cuối TB {bx:4.1f} | kỹ năng TB {sum(used) / max(1, len(used)):.1f} | {time.time() - t:.0f}s", flush=True)
    return tu


def _flag(name, cast=int, default=None):
    for a_ in sys.argv:
        if a_.startswith(name + "="):
            return cast(a_.split("=", 1)[1])
    return default


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    n = int(args[0]) if args else 20
    depth = int(args[1]) if len(args) > 1 else 2
    beam = int(args[2]) if len(args) > 2 else 30
    cap_ = _flag("--cap", int, None)
    if "--hard" in sys.argv:
        FILL_CHOICES[:] = [7, 7, 8]
    if "--real" in sys.argv:             # độ dài thú sát bàn thật (18/10: bàn thật chỉ ~8% thú 1 ô, mặc định mô phỏng 45% nên QUÁ DỄ)
        LEN_W[:] = [(1, 0.30), (2, 0.30), (3, 0.25), (4, 0.15)]
    if "--real-hard" in sys.argv:        # khó hơn nữa (1 ô 22%): để phân biệt các bản bot với nhau
        LEN_W[:] = [(1, 0.22), (2, 0.30), (3, 0.30), (4, 0.18)]
    BULL_EARLY = _flag("--bull-early", int, BULL_EARLY)
    BULL_LATE = _flag("--bull-late", int, BULL_LATE)
    BULL_LATE_FROM = _flag("--bull-from", int, BULL_LATE_FROM)
    BULL_RAMP_TO = _flag("--bull-ramp-to", int, BULL_RAMP_TO)
    if "--old-bull" in sys.argv:         # luật cũ: 20 hiệp/trâu cả ván
        BULL_LATE = BULL_EARLY
    lad = _flag("--ladder", str, None)
    if lad:
        SKILL_LADDER[:] = [int(x) for x in lad.split(",") if x.strip()]
    for a_ in sys.argv:
        if a_.startswith("--kinds="):
            SKILL_KINDS = a_.split("=", 1)[1].upper()
    if "--best" in sys.argv:
        BEAR_FIRST = False
    if _flag("--engine", str, None):
        _eng = load_bot(_flag("--engine", str))
        check_engine(_eng)
        set_engine(_eng)
    kw = dict(crowd_depth=_flag("--crowd", int, None), bear_from=_flag("--bear-from", int, None), bear_bulls=_flag("--bear-bulls", int, 8))
    if _flag("--bot", str, None):
        _b = load_bot(_flag("--bot", str))
        for _n in check_bot(_b, os.path.basename(_flag("--bot", str)), need_skill=any(f in sys.argv for f in ("--skill", "--skill-compare", "--bear-compare"))):
            print("lưu ý:", _n)
        kw["bot"] = _b
    if "--skill-compare" in sys.argv:        # so: Gấu luôn trước  vs  chọn kỹ năng giá trị cao nhất (cùng seed)
        SKILL_KINDS = SKILL_KINDS if SKILL_KINDS != "K" else "KYPB"
        cp = cap_ or 400
        run(n, depth, beam, cap=cp, label="không kỹ năng", skill=False, **kw)
        BEAR_FIRST = True
        run(n, depth, beam, cap=cp, label=f"{SKILL_KINDS}: Gấu luôn trước", skill=True, **kw)
        BEAR_FIRST = False
        run(n, depth, beam, cap=cp, label=f"{SKILL_KINDS}: giá trị cao nhất", skill=True, **kw)
    elif "--bear-compare" in sys.argv:
        cp = cap_ or 500
        bf = kw["bear_from"] if kw["bear_from"] is not None else 280
        BEAR_FIRST = True
        k0 = dict(kw, bear_from=None)
        SKILL_KINDS = "KYPB"
        run(n, depth, beam, cap=cp, label="không kỹ năng", skill=False, **k0)
        run(n, depth, beam, cap=cp, label="KYPB khi kẹt/thua", skill=True, **k0)
        SKILL_KINDS = "K"
        run(n, depth, beam, cap=cp, label="chỉ K khi kẹt/thua", skill=True, **k0)
        run(n, depth, beam, cap=cp, label=f"chỉ K + chủ động từ {bf}, thừa>={kw['bear_bulls']}", skill=True, **dict(kw, bear_from=bf))
    elif "--skill" in sys.argv:
        cp = cap_ or 400
        run(n, depth, beam, cap=cp, label=f"không kỹ năng (cap {cp})", skill=False, **kw)
        run(n, depth, beam, cap=cp, label=f"kỹ năng khi cần (cap {cp})", skill=True, **kw)
    elif "--compare" in sys.argv:
        W = ab.Weights
        cp = cap_ or 150
        run(n, 1, beam, W(), cap=cp, label="ngẫu nhiên", policy="random", **kw)
        run(n, 1, beam, W(), cap=cp, label="depth1 mặc định", **kw)
        run(n, 2, beam, W(), cap=cp, label="depth2 mặc định", **kw)
        run(n, 2, beam, replace(W(), danger=0.0), cap=cp, label="depth2 danger=0", **kw)
        run(n, 2, beam, replace(W(), fit=0.0), cap=cp, label="depth2 fit=0", **kw)
        run(n, 2, beam, replace(W(), bull_cell=24.0), cap=cp, label="depth2 bull_cell=24", **kw)
    else:
        run(n, depth, beam, cap=cap_ or 150, label=f"depth{depth} beam{beam}", **kw)

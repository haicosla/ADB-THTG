# -*- coding: utf-8 -*-
"""
Bộ giải đường đi CHÍNH XÁC (nhánh-cận) cho bot Ngưu Ma Vương. Không import tkinter / thtg_bot.

Bài toán 1 lượt: từ ô nhân vật, đi 8 hướng, không lặp ô, chỉ nối thú CÙNG LOẠI; kim cương hoặc diệt quái to
(đủ N bước tích luỹ) thì được đổi loại; đá không đi qua được. Tối đa hoá
    điểm = Σ giá trị quái diệt được + w_step * số bước + w_diamond * số kim cương (w_diamond thường ÂM: dùng kim cương bị trừ)
           + w_reward * (số bước // reward_every)  (thưởng kim cương mỗi 10 bước)
           + end_fn(ô cuối, mask)                   (<= 0: phạt vị trí cuối dễ kẹt, tuỳ chọn).

Vì sao không chỉ dùng beam search: beam giữ K đường "trông có vẻ tốt" nên dễ bỏ sót đường dài/đường qua kim cương
(đổi màu) mà lúc đầu nhìn chưa tốt. Ở đây duyệt có CẬN TRÊN (cắt nhánh khi không thể hơn kết quả đã có) nên với
bàn 7x7 thường chứng minh được đường tối ưu; nếu bàn quá khó thì dừng theo SỐ NÚT (không theo thời gian) -> kết quả
xác định, không phụ thuộc máy nhanh/chậm.

Biểu diễn bàn cờ (độc lập với thtg_bot): grid[r][c] = (kind, color, n, value)
    kind: 'A' thú (color 0..), 'D' kim cương, 'M' quái to (n = số bước cần, value = điểm khi diệt),
          'L' ô lồng (như M: cần n bước, bị trừ n, nhưng KHÔNG đổi loại - giữ loại thú đang nối),
          'S' đá, 'H' nhân vật, 'E' trống/không rõ.
"""

from __future__ import annotations

ROWS = COLS = 7
_W = 8                                   # bit = r*8 + c (cột 7 là đệm)
_BOARD = sum(0x7F << (_W * r) for r in range(ROWS))
_DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _pc(x):
    try:
        return x.bit_count()
    except AttributeError:
        return bin(x).count("1")


def _dil(m):
    d = m | (m << 1) | (m >> 1)
    d |= (d << _W) | (d >> _W)
    return d & _BOARD


def _flood(seed, allowed):
    reg = _dil(seed) & allowed
    while True:
        n = _dil(reg) & allowed
        if n == reg:
            return reg
        reg = n


def solve_exact(grid, hero, w_step=10.0, w_diamond=0.0, count_step_first=False,
                node_limit=400_000, seed_path=None, seed_score=None,
                w_reward=0.0, reward_every=10, end_fn=None):
    """Trả (path, score, info). `seed_path` (vd kết quả beam) dùng làm cận dưới ban đầu để cắt nhánh sớm.
    info = {'nodes', 'complete' (True nếu duyệt hết = đã chứng minh tối ưu)}.
    `end_fn(tip, mask)` (tip = r*8+c) phải trả số <= 0 (phạt) và chỉ phụ thuộc (tip, mask) - khi đó cận trên (bỏ qua phạt)
    vẫn hợp lệ và bộ nhớ `seen` vẫn đúng. Mặc định w_reward=0, end_fn=None = hành vi cũ."""
    reward_every = max(1, int(reward_every))
    hr, hc = hero
    cc = [-1] * 64            # loại thú của ô (-1: không phải thú)
    kind = ["x"] * 64
    need = [0] * 64
    nreal = [0] * 64
    val = [0.0] * 64
    lcol = [-1] * 64          # màu của LỒNG (-1 = không rõ -> qua được mọi màu); lồng chỉ cho đi qua khi cùng màu với con đang nối
    colmask = {}
    dia_mask = mon_mask = stone_mask = 0
    walk = 0                   # ô đi vào được (thú/kim cương/quái)
    for r in range(ROWS):
        for c in range(COLS):
            k, col, n, v = grid[r][c]
            i = r * _W + c
            kind[i] = k
            b = 1 << i
            if k == "A":
                cc[i] = col
                colmask[col] = colmask.get(col, 0) | b
                walk |= b
            elif k == "D":
                dia_mask |= b
                walk |= b
            elif k in ("M", "L"):      # L (lồng) tính chung với M ở CẬN TRÊN (cho phép đổi loại = nới lỏng hơn, vẫn là cận hợp lệ)
                mon_mask |= b
                nreal[i] = n
                need[i] = n - (1 if count_step_first else 0)
                val[i] = float(v)
                if k == "L":
                    lcol[i] = col
                walk |= b
            elif k == "S":
                stone_mask |= b
    bridge = dia_mask | mon_mask
    colors = sorted(colmask)
    nb = [[] for _ in range(64)]
    for r in range(ROWS):
        for c in range(COLS):
            for dr, dc in _DIRS:
                a, b = r + dr, c + dc
                if 0 <= a < ROWS and 0 <= b < COLS and (walk >> (a * _W + b)) & 1:
                    nb[r * _W + c].append(a * _W + b)

    # --- thành phần tĩnh: các ô thú cùng loại nối liền (8 hướng). Mỗi đoạn đi (giữa 2 lần đổi loại) nằm trọn trong 1 thành phần.
    comp_of = [-1] * 64
    comp_mask = []
    for i in range(64):
        if kind[i] == "A" and comp_of[i] < 0:
            cid = len(comp_mask)
            stack, m = [i], 0
            comp_of[i] = cid
            while stack:
                x = stack.pop()
                m |= 1 << x
                for j in nb[x]:
                    if kind[j] == "A" and cc[j] == cc[i] and comp_of[j] < 0:
                        comp_of[j] = cid
                        stack.append(j)
            comp_mask.append(m)
    ncomp = len(comp_mask)
    comp_adj_bridges = [_dil(m) & bridge for m in comp_mask]          # cầu nối kề thành phần (mặt nạ ô)
    bridge_adj_comps = {}                                              # ô cầu nối -> mặt nạ bit các thành phần kề
    for i in range(64):
        if kind[i] in "DML":
            bm = 0
            for j in nb[i]:
                if kind[j] == "A":
                    bm |= 1 << comp_of[j]
            bridge_adj_comps[i] = bm

    start = hr * _W + hc
    best = [-1e18, []]         # điểm có thể ÂM (kim cương trừ điểm / phạt) nhưng vẫn phải chọn 1 đường nếu có
    if seed_path:
        sp = [p[0] * _W + p[1] for p in seed_path]
        best[0] = (seed_score if seed_score is not None else 0.0) - 1e-9
        best[1] = sp
    nodes = [0]
    aborted = [False]
    seen = set()
    path = []

    def bound(tip, mask, color, bal):
        """CẬN TRÊN HỢP LỆ (không bao giờ nhỏ hơn giá trị thật) của (số bước, điểm quái, số kim cương) còn lấy thêm được.
        Lý lẽ: mỗi đoạn đi nằm trong 1 thành phần cùng loại; giữa 2 đoạn phải đi qua 1 cầu nối (kim cương/quái).
        => số đoạn <= số cầu nối với tới được + 1, mỗi đoạn <= số ô còn trống của thành phần đó."""
        free = ~mask & walk
        tb = 1 << tip
        rc = 0
        extra_sizes = []
        if color >= 0 and comp_of[tip] >= 0:     # (tip là ô lồng giữ loại thú: comp_of = -1 -> dùng nhánh nới lỏng bên dưới, vẫn là cận hợp lệ)
            cur = comp_of[tip]
            reg = _flood(tb, free & comp_mask[cur])
            steps_cur = _pc(reg)
            todo = _dil(reg | tb) & bridge & free      # cầu nối kề đoạn đang đi (kể cả kề ngay ô tip)
            seg_allow = 0
            rest = _pc(comp_mask[cur] & free & ~reg)      # phần thành phần hiện tại bị cắt rời (vào lại sau khi qua cầu)
            if rest:
                extra_sizes.append(rest)
            curbit = 1 << cur
        else:
            cur = -1
            curbit = 0
            steps_cur = 0
            seg_allow = 1
            todo = _dil(tb) & bridge & free
            for j in nb[tip]:
                if kind[j] == "A" and (free >> j) & 1:
                    rc |= 1 << comp_of[j]
            m = rc
            while m:
                cl = m & -m
                m ^= cl
                todo |= comp_adj_bridges[cl.bit_length() - 1] & free
        rb = 0
        done = 0
        cur_seen = False
        todo &= ~tb
        while todo:
            low = todo & -todo
            todo ^= low
            done |= low
            rb |= low
            todo |= _dil(low) & bridge & free & ~done & ~tb      # cầu nối kề cầu nối (kim cương liền kim cương/quái)
            adjc = bridge_adj_comps.get(low.bit_length() - 1, 0)
            if adjc & curbit and not cur_seen:
                # quay lại thành phần đang đi ở phần bị cắt rời: các cầu nối kề phần đó cũng tới được
                cur_seen = True
                todo |= comp_adj_bridges[cur] & free & ~done & ~tb
            newc = adjc & ~rc & ~curbit
            while newc:
                cl = newc & -newc
                newc ^= cl
                rc |= cl
                todo |= comp_adj_bridges[cl.bit_length() - 1] & free & ~done & ~tb
        nbr = _pc(rb)
        sizes = list(extra_sizes) if nbr else []
        m = rc
        while m:
            cl = m & -m
            m ^= cl
            sizes.append(_pc(comp_mask[cl.bit_length() - 1] & free))
        sizes.sort(reverse=True)
        steps = steps_cur + nbr + sum(sizes[:nbr + seg_allow])
        mv = 0.0
        m = rb & mon_mask
        cap = bal + steps
        while m:
            low = m & -m
            m ^= low
            j = low.bit_length() - 1
            if need[j] <= cap:
                mv += val[j]
        dv = _pc(rb & dia_mask) if w_diamond > 0 else 0       # w_diamond <= 0: không dùng kim cương là cận trên tốt nhất
        return steps, mv, dv

    def dfs(tip, mask, color, bal, v, steps, dia):
        nodes[0] += 1
        if nodes[0] > node_limit:
            aborted[0] = True
            return
        score = v + w_step * steps + w_diamond * dia + w_reward * (steps // reward_every)
        if score > best[0] and steps > 0:
            if end_fn is not None:
                score += end_fn(tip, mask)          # <= 0; chỉ tính khi có thể vượt best (cắt bớt chi phí)
            if score > best[0]:
                best[0] = score
                best[1] = list(path)
        bs, bm, bd = bound(tip, mask, color, bal)
        if (v + bm + w_step * (steps + bs) + w_diamond * (dia + bd)
                + w_reward * ((steps + bs) // reward_every)) <= best[0]:
            return
        free = ~mask
        cand = []
        for j in nb[tip]:
            if not (free >> j) & 1:
                continue
            k = kind[j]
            if k == "A":
                if color != -1 and cc[j] != color:
                    continue
                pri = 1
            elif k == "D":
                pri = 0
            else:          # quái / lồng
                if bal < need[j]:
                    continue
                if k == "L" and color != -1 and lcol[j] != -1 and lcol[j] != color:
                    continue                      # lồng khác màu con đang nối -> không đi qua được
                pri = -1
            # Warnsdorff: ít đường đi tiếp thì đi trước (tránh bỏ lại ô cụt)
            deg = 0
            for q in nb[j]:
                if (free >> q) & 1 and q != j:
                    deg += 1
            cand.append((pri, deg, j))
        cand.sort()
        for _p, _d, j in cand:
            nm = mask | (1 << j)
            k = kind[j]
            key = (j, nm, color if k == "L" else -2)      # qua lồng giữ nguyên loại -> loại hiện tại phụ thuộc đường đi, phải nằm trong khoá
            if key in seen:
                continue
            seen.add(key)
            path.append(j)
            if k == "A":
                dfs(j, nm, cc[j], bal + 1, v, steps + 1, dia)
            elif k == "D":
                dfs(j, nm, -1, bal + 1, v, steps + 1, dia + 1)
            elif k == "L":
                dfs(j, nm, color, bal + 1 - nreal[j], v + val[j], steps + 1, dia)
            else:
                dfs(j, nm, -1, bal + 1 - nreal[j], v + val[j], steps + 1, dia)
            path.pop()
            if aborted[0]:
                return

    dfs(start, 1 << start, -1, 0, 0.0, 0, 0)
    out = [(i // _W, i % _W) for i in best[1]]
    return out, best[0], {"nodes": nodes[0], "complete": not aborted[0]}

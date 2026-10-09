# -*- coding: utf-8 -*-
"""
pig_bot.py - Bot auto game "Lợn giống" (kiểu Suika: thả heo, 2 con cùng cấp chạm nhau thì gộp thành cấp cao hơn).

Luồng 1 lượt (run_auto_pig_step):
  chụp màn hình -> nhận diện từng con heo (hình tròn viền màu, cấp suy ra từ bán kính + màu viền)
  -> đọc con đang cầm -> mô phỏng vật lý (Pymunk) thử nhiều vị trí thả (+ con kế ngẫu nhiên cấp 1-4)
  -> bấm vị trí tốt nhất -> chờ heo lăn yên -> lặp.

Luật đã biết: 10 cấp; heo đỏ (cấp 10) không gộp; 2 heo cùng cấp CHẠM THẬT mới gộp (sát nhau mà còn hở thì chưa gộp);
con thả ra ngẫu nhiên cấp 1-4; thể lực < min_stamina thì dừng.
Cần: pip install pymunk  (không có Pymunk thì bước báo lỗi rõ ràng và dừng).

Kiểm tra nhanh 1 ảnh:  python pig_bot.py anh.png [x1 y1 x2 y2]   (toạ độ pixel của khung nét đứt; bỏ trống = khung mặc định)

Cách thả: mặc định drop_mode="tap" - chạm đâu trong lồng thì heo rơi THẲNG tại x đó. drop_mode="drag" (nhấn giữ-kéo-đọc lại-nhả) chỉ là tuỳ chọn.
Khung bàn (khung nét đứt) CỐ ĐỊNH theo tỉ lệ ảnh giả lập 720x1280, không cần chọn tay (muốn tự đặt: board_custom=true + board_from/board_to).
"""
import os
import re
import sys
import json
import math
import time
import glob

import cv2
import numpy as np

try:
    import pymunk
except Exception:  # chưa cài
    pymunk = None

NLV = 10
# bán kính / chiều rộng khung bàn (ước lượng từ ảnh, đã đối chiếu 3 ảnh thật)
R_FRAC = [0.036, 0.057, 0.073, 0.090, 0.110, 0.127, 0.151, 0.178, 0.203, 0.270]
# nhóm màu viền: 0 ngọc, 1 xanh, 2 tím, 3 vàng, 4 đỏ, 5 xám (cấp 1)
GROUP = [5, 0, 0, 1, 1, 2, 2, 3, 3, 4]
# khung nét đứt theo tỉ lệ ảnh: giả lập chuẩn 720x1280 (đo từ ảnh thật) và máy thật 946x2048
BOARD_EMU = ([0.018, 0.2945], [0.979, 0.9086])
BOARD_PHONE = ([0.019, 0.401], [0.978, 0.906])
DEFAULT_BOARD = BOARD_EMU


def _default_board(fw, fh):
    asp = fw / float(fh)
    return BOARD_PHONE if abs(asp - 946 / 2048.0) < abs(asp - 720 / 1280.0) else BOARD_EMU

# ----------------------------------------------------------------------------------------------
# NHẬN DIỆN
# ----------------------------------------------------------------------------------------------
_THETA = np.linspace(0, 2 * np.pi, 120, endpoint=False)
_CT, _ST = np.cos(_THETA), np.sin(_THETA)


def _group_masks(hsv):
    H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    v = V > 80
    m = [
        v & (S > 55) & (H >= 77) & (H <= 93),                      # ngọc
        v & (S > 75) & (H >= 95) & (H <= 109),                     # xanh
        v & (S > 70) & (H >= 128) & (H <= 152),                    # tím
        v & (S > 110) & (H >= 13) & (H <= 25),                     # vàng
        v & (S > 110) & ((H <= 3) | (H >= 176)),                   # đỏ
        (S < 80) & (V > 60) & (V < 175),                           # xám (heo cấp 1)
    ]
    return [x.astype(np.uint8) for x in m]


def _ring_cover(mask, cx, cy, r):
    h, w = mask.shape
    px = (cx + r * 0.94 * _CT).astype(int)
    py = (cy + r * 0.94 * _ST).astype(int)
    ok = (px >= 0) & (px < w) & (py >= 0) & (py < h)
    if ok.sum() < 0.55 * len(_THETA):
        return 0.0
    return float(mask[py[ok], px[ok]].mean() * ok.mean())


def _hough(gray, r, lo=0.90, hi=1.10):
    p2 = 9 if r < 45 else (13 if r < 60 else 22)
    c = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1, minDist=max(5, r * 0.4), param1=90, param2=p2,
                         minRadius=max(8, int(r * lo)), maxRadius=int(r * hi) + 1)
    return [] if c is None else c[0]


def _refine(mask, cx, cy, rr):
    best = (0.0, cx, cy, rr)
    st = (-4, -2, 0, 2, 4) if rr < 45 else (-3, 0, 3)     # heo bé viền mỏng -> lưới mịn hơn
    for dr in (-3, 0, 3):
        for dx in st:
            for dy in st:
                s = _ring_cover(mask, cx + dx, cy + dy, rr + dr)
                if s > best[0]:
                    best = (s, cx + dx, cy + dy, rr + dr)
    return best


def find_popups(img, box):
    """Tìm các băng điểm nổi (\"+50\", \"+6\"... nền xám-nâu mờ, có icon tròn bên trái) hiện lên sau mỗi lần gộp.
    Icon/chữ đỏ trong băng rất dễ bị Hough nhận nhầm thành heo (đỏ/xám cấp 1). Trả [(x, y, w, h)] theo toạ độ TRONG khung."""
    x1, y1, x2, y2 = [int(v) for v in box]
    roi = img[y1:y2, x1:x2]
    if roi.size == 0:
        return []
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    Hh, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    m = ((V > 55) & (V < 150) & (S > 25) & (S < 110) & (Hh >= 10) & (Hh <= 32)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (31, 5)))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7)))
    n, _, st, _ = cv2.connectedComponentsWithStats(m)
    out = []
    for i in range(1, n):
        x, y, w, h, a = [int(v) for v in st[i]]
        # băng điểm: dẹt (w >= 2h), cao ~34px (có thể 2-3 băng xếp chồng), đặc
        if w >= 70 and 18 <= h <= 140 and w / float(h) >= 1.6 and a / float(w * h) > 0.45:
            out.append((x, y, w, h))
    return out


def _in_popup(cx, cy, r, popups, pad=8):
    """Tâm vòng tròn nằm trong băng điểm (nới pad px) -> không phải heo thật."""
    for x, y, w, h in popups:
        if x - pad <= cx <= x + w + pad and y - pad <= cy <= y + h + pad:
            return True
    return False


def detect_pigs(img, box, thr=0.62, popups=None):
    """box=(x1,y1,x2,y2) pixel khung nét đứt. Trả [(cấp, cx, cy, r, điểm)] theo toạ độ TRONG khung (gốc = góc trên-trái khung).
    popups: danh sách băng điểm cần bỏ qua (None = tự tìm bằng find_popups)."""
    x1, y1, x2, y2 = [int(v) for v in box]
    W = x2 - x1
    roi = img[y1:y2, x1:x2]
    if popups is None:
        popups = find_popups(img, box)
    gray = cv2.GaussianBlur(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gm = _group_masks(hsv)
    h, w = gray.shape
    acc = []
    for k in range(NLV - 1, -1, -1):          # từ cấp lớn xuống nhỏ: con nhỏ không thể nằm trong con lớn
        r = R_FRAC[k] * W
        m = gm[GROUP[k]]
        cands = []
        for cx, cy, rr in _hough(gray, r)[:45]:
            s, ax, ay, ar = _refine(m, cx, cy, rr)
            if s >= thr:
                if popups and _in_popup(ax, ay, ar, popups):
                    continue                               # icon/chữ trong băng điểm nổi, không phải heo
                if k == 0 and not _pink_inside(hsv, ax, ay, ar):
                    continue                               # cấp 1 viền xám: bắt buộc có thân hồng bên trong
                cands.append((s, ax, ay, ar))
        cands.sort(key=lambda t: -t[0])
        for s, cx, cy, rr in cands:
            if cx - rr < -0.04 * W or cx + rr > 1.04 * W or cy + rr > h * 1.04:
                continue                                   # lòi ra ngoài tường/sàn -> giả
            if any(math.hypot(cx - a[1], cy - a[2]) < max(a[3] * 0.98, (rr + a[3]) * 0.88) for a in acc):
                continue
            acc.append((k + 1, cx, cy, rr, s))
    # chốt cấp theo bán kính gần nhất TRONG CÙNG nhóm màu (Hough cho phép ±10% nên 2 cấp kề nhau có thể lẫn)
    out = []
    for lv, cx, cy, rr, s in acc:
        g = GROUP[lv - 1]
        same = [i for i in range(NLV) if GROUP[i] == g]
        best = min(same, key=lambda i: abs(rr - R_FRAC[i] * W))
        out.append((best + 1, float(cx), float(cy), float(rr), float(s)))
    return out


HELD_TOP = 0.233     # mép TRÊN con đang cầm cách mép trên khung bàn ~0.233 x chiều rộng khung (đo từ ảnh thật, mọi cấp)


def _pink_inside(hsv, cx, cy, r):
    """Thân heo hồng bên trong vòng tròn (dùng để chắc chắn đó là heo, nhất là heo cấp 1 viền xám)."""
    h, w = hsv.shape[:2]
    ok = tot = 0
    for fx in (-0.45, -0.2, 0.0, 0.2, 0.45):
        for fy in (-0.45, -0.2, 0.0, 0.2, 0.45):
            x, y = int(cx + fx * r), int(cy + fy * r)
            if 0 <= x < w and 0 <= y < h:
                H_, S_, V_ = (int(v) for v in hsv[y, x])
                tot += 1
                if (H_ <= 16 or H_ >= 168) and 30 <= S_ <= 170 and V_ > 170:
                    ok += 1
    return tot > 0 and ok / float(tot) >= 0.2


def _dark_body(hsv, cx, cy, r):
    """Thân heo tối (heo cấp 3 màu xanh đen) hay sáng (cấp 2 hồng-trắng)? Cấp 2 và 3 CÙNG màu viền (ngọc) nên chỉ phân biệt được bằng
    màu thân + bán kính. Lấy mẫu nửa dưới thân (tránh mắt/mũi). Trả tỉ lệ điểm tối (V < 120): L3 ~0.85-1.0, L2 ~0.05."""
    h, w = hsv.shape[:2]
    ok = tot = 0
    for fx in (-0.4, -0.2, 0.0, 0.2, 0.4):
        for fy in (-0.1, 0.1, 0.3, 0.5):
            x, y = int(cx + fx * r), int(cy + fy * r)
            if 0 <= x < w and 0 <= y < h:
                tot += 1
                if int(hsv[y, x, 2]) < 120:
                    ok += 1
    return ok / float(tot) if tot else 0.0


def detect_held(img, box, held_top=HELD_TOP, search=0.14):
    """Con đang cầm luôn nằm GIỮA màn hình, MÉP TRÊN cố định -> tâm = mép trên + bán kính.
    Khung bàn do người dùng kéo bằng tay có thể lệch vài chục px nên quét một vùng rộng quanh vị trí kỳ vọng
    (thô -> tinh), thử cấp 1-4, chọn cấp có vòng viền khớp nhất. Trả (cấp, cx, cy(âm), r) trong toạ độ khung, hoặc None."""
    x1, y1, x2, y2 = [int(v) for v in box]
    W = x2 - x1
    cx0 = (x1 + x2) / 2.0
    ytop0 = y1 - held_top * W
    r4 = R_FRAC[3] * W
    pad = int(0.06 * W)
    sy = int(search * W)
    xa, xb = max(0, int(cx0 - pad - r4 - 24)), int(cx0 + pad + r4 + 24)
    ya, yb = max(0, int(ytop0 - sy - 20)), int(ytop0 + sy + 2 * r4 + 20)
    band = img[ya:yb, xa:xb]
    if band.size == 0:
        return None
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    gm = _group_masks(hsv)
    best = None
    for k in range(4):
        r = R_FRAC[k] * W
        m = gm[GROUP[k]]
        cands = []
        stp = 3 if k == 0 else 6                      # heo cấp 1 bé, viền xám -> quét mịn hơn
        for dy in range(-sy, sy + 1, stp):
            for dx in range(-pad, pad + 1, stp):
                sc = _ring_cover(m, cx0 + dx - xa, ytop0 + r + dy - ya, r)
                if sc >= (0.3 if k == 0 else 0.4):
                    cands.append((sc, dx, dy))
        cands.sort(reverse=True)
        need = 0.6 if k == 0 else 0.62
        for _, dx0, dy0 in cands[:(6 if k == 0 else 3)]:
            for dr in (-3, 0, 3):
                for ddx in (-4, -2, 0, 2, 4):
                    for ddy in (-4, -2, 0, 2, 4):
                        cx, cy = cx0 + dx0 + ddx - xa, ytop0 + r + dy0 + ddy - ya
                        sc = _ring_cover(m, cx, cy, r + dr)
                        if sc < need:
                            continue
                        if k == 0 and not _pink_inside(hsv, cx, cy, r):
                            continue
                        v = sc + (0.15 if k else 0.0)          # ưu tiên viền có màu hơn viền xám
                        if best is None or v > best[0]:
                            best = (v, k, cx + xa, cy + ya, r + dr)
    if best is None:
        return None
    _, k, cx, cy, rr = best
    if k in (1, 2):
        # Con vừa hiện ra có hoạt ảnh phóng to: heo cấp 3 (đen) còn nhỏ bằng cỡ cấp 2 -> bị đọc nhầm L2. Chốt cấp theo MÀU THÂN,
        # bán kính + y tâm lấy theo cấp đã chốt (giữ nguyên mép trên của con cầm).
        dark = _dark_body(hsv, cx - xa, cy - ya, rr) >= 0.4
        k2 = 2 if dark else 1
        if k2 != k:
            r2 = R_FRAC[k2] * W
            cy, rr, k = cy - rr + r2, r2, k2
    return (k + 1, cx - x1, cy - y1, rr)


# ----------------------------------------------------------------------------------------------
# MÔ PHỎNG
# ----------------------------------------------------------------------------------------------
class SimParams:
    def __init__(self, **kw):
        self.gravity = 1.84         # x chiều rộng khung / giây^2 (khớp 233 lượt thật; trước đây 3.0)
        self.damping = 0.78         # phần vận tốc còn lại sau 1 giây
        self.friction = 0.81
        self.elasticity = 0.097
        self.rad_scale = 1.02       # bán kính va chạm = bán kính vòng viền * hệ số này (heo thật hơi to hơn vòng đo được)
        self.merge_eps = 0.0        # cộng thêm vào (r1+r2) khi xét chạm, tính theo chiều rộng khung
        self.dt = 1.0 / 60.0
        self.max_t = 4.5
        for k, v in kw.items():
            setattr(self, k, v)


def _merge_pass(balls, eps):
    """Gộp mọi cặp cùng cấp (<10) đang chạm. balls: list [lv,x,y,r,vx,vy]. Trả (balls mới, điểm gộp)."""
    gain = 0.0
    changed = True
    while changed:
        changed = False
        n = len(balls)
        for i in range(n):
            a = balls[i]
            if a[0] >= NLV:
                continue
            for j in range(i + 1, n):
                b = balls[j]
                if b[0] != a[0]:
                    continue
                if math.hypot(a[1] - b[1], a[2] - b[2]) <= a[3] + b[3] + eps:
                    lv = a[0] + 1
                    wa, wb = a[3] ** 2, b[3] ** 2
                    s = wa + wb
                    nb = [lv, (a[1] * wa + b[1] * wb) / s, (a[2] * wa + b[2] * wb) / s, None,
                          (a[4] * wa + b[4] * wb) / s, (a[5] * wa + b[5] * wb) / s]
                    nb[3] = a[3] * (R_NOM[lv - 1] / R_NOM[a[0] - 1])
                    balls = [x for t, x in enumerate(balls) if t not in (i, j)] + [nb]
                    gain += 2.0 ** lv
                    changed = True
                    break
            if changed:
                break
    return balls, gain


R_NOM = R_FRAC   # tỉ lệ bán kính các cấp (dùng để suy ra bán kính con mới)
LEVEL_PROB = {1: 0.31, 2: 0.28, 3: 0.28, 4: 0.14}   # tỉ lệ con thả theo cấp (đếm từ log thật) - trọng số khi nhìn trước con kế


def simulate(balls, W, H, drop=None, p=None):
    """balls: [(lv,x,y,r)]; drop=(lv,x,r[,y_tâm]) thả từ trên (y_tâm = tâm con rơi lúc nhả tay, toạ độ khung, âm = phía trên khung;
    bỏ trống = -1.1*r). Trả (balls [(lv,x,y,r)], điểm gộp)."""
    if pymunk is None:
        raise RuntimeError("Chưa cài Pymunk: chạy  pip install pymunk")
    p = p or SimParams()
    sp = pymunk.Space()
    sp.gravity = (0.0, p.gravity * W)
    sp.damping = p.damping
    sp.iterations = 14
    sb = sp.static_body
    for seg in (pymunk.Segment(sb, (-12, H + 12), (W + 12, H + 12), 12),
                pymunk.Segment(sb, (-12, -9 * H), (-12, H + 30), 12),
                pymunk.Segment(sb, (W + 12, -9 * H), (W + 12, H + 30), 12)):
        seg.friction = p.friction
        seg.elasticity = p.elasticity
        sp.add(seg)

    def add(lv, x, y, r, vx=0.0, vy=0.0):
        rr = r * p.rad_scale
        body = pymunk.Body(rr * rr * 0.01, pymunk.moment_for_circle(rr * rr * 0.01, 0, rr))
        body.position = (x, y)
        body.velocity = (vx, vy)
        sh = pymunk.Circle(body, rr)
        sh.friction = p.friction
        sh.elasticity = p.elasticity
        sp.add(body, sh)
        return body

    live = []   # [lv, body, r_ring]
    for lv, x, y, r in balls:
        live.append([lv, add(lv, x, y, r), r])
    if drop is not None:
        lv, x, r = drop[0], drop[1], drop[2]
        y0 = drop[3] if len(drop) > 3 and drop[3] is not None else -1.1 * r
        live.append([lv, add(lv, x, y0, r), r])
    gain = 0.0
    eps = p.merge_eps * W
    t, calm = 0.0, 0.0
    step = 0
    while t < p.max_t:
        sp.step(p.dt)
        t += p.dt
        step += 1
        if step % 2 == 0:
            arr = [[lv, b.position.x, b.position.y, r * p.rad_scale, b.velocity.x, b.velocity.y] for lv, b, r in live]
            merged, g = _merge_pass([a[:] for a in arr], eps)
            if g > 0:
                gain += g
                for lv, b, r in live:
                    sp.remove(b, *b.shapes)
                live = []
                for nb in merged:
                    ring_r = nb[3] / p.rad_scale
                    live.append([nb[0], add(nb[0], nb[1], nb[2], ring_r, nb[4], nb[5]), ring_r])
                calm = 0.0
                continue
            vmax = max((abs(a[4]) + abs(a[5]) for a in arr), default=0.0)
            calm = calm + p.dt * 2 if vmax < 0.02 * W else 0.0
            if calm > 0.25 and t > 0.4:
                break
    return [(lv, b.position.x, b.position.y, r) for lv, b, r in live], gain


class EvalParams:
    def __init__(self, **kw):
        self.w_gain = 1.0
        self.w_height = 900.0
        self.w_area = 500.0
        self.w_pair = 0.35        # thưởng cặp cùng cấp nằm sát nhau (chờ gộp)
        self.w_big_low = 4.0      # thưởng heo lớn nằm thấp
        self.w_trap = 6.0         # phạt heo nhỏ bị kẹp giữa heo lớn
        self.w_top_lv = 40.0      # thưởng cấp cao nhất đạt được
        self.w_grad = 6.0         # phạt 2 heo chạm nhau mà chênh >1 cấp (muốn dốc thoải: cấp kề nhau)
        self.w_order = 3.0        # phạt xếp lộn xộn: heo lớn nên dồn dần về MỘT phía (trái->phải giảm dần hoặc ngược lại)
        self.w_block = 2.0        # phạt heo nhỏ NẰM CHEN GIỮA 2 heo to cùng cấp (chặn không cho 2 con to chạm nhau để gộp)
        self.w_wedge = 4.0        # phạt heo nhỏ (cấp<=3) bị kẹp giữa heo to và tường (không còn đường gộp)
        self.w_direct = 2.0       # thưởng thả THẲNG vào tâm heo cùng cấp (chắc chắn chạm) thay vì thả lệch sang cạnh
        self.w_robust = 0.6       # phạt mất điểm khi vị trí thả lệch ±1.2% chiều rộng khung (sai số bấm/nhận diện)
        self.w_width = 0.8        # phạt nước đi MẤT điểm khi độ rộng heo lệch +-rad_jit (khe hở/chạm tiếp tuyến chỉ đúng trên giấy)
        self.w_width_gain = 1.5   # phạt thêm khi lần gộp dự đoán BIẾN MẤT lúc heo to/nhỏ hơn chút (x điểm gộp)
        self.rad_jit = 0.04       # +-4% bán kính (độ rộng) khi kiểm tra độ bền
        self.w_phys = 0.8         # phạt nước đi mất điểm khi vật lý khác chút (ma sát thấp/cao, nảy nhiều, trọng lực lớn): dễ bị nảy/lăn khác dự đoán
        self.w_phys_gain = 1.5    # phạt thêm khi lần gộp dự đoán biến mất ở bộ vật lý khác (x điểm gộp)
        self.w_graze = 0.6        # phạt nước đi trông có gộp nhưng đường rơi chạm VAI con khác trước (không phải con cùng cấp) -> bị nảy ra, x điểm gộp
        self.w_bigpair = 6.0      # thưởng 2 con CÙNG CẤP lớn (>= bigpair_min) sắp chạm nhau và KHÔNG có con khác chắn giữa: x 2^cấp x (1 - khe/(2r))
        self.w_blocker = 4.0      # phạt 2 con cùng cấp lớn nằm gần nhau (khe <= 2r) mà có con khác CHẮN GIỮA (không chạm nhau được): x 2^cấp
        self.bigpair_min = 5
        self.reserve = True       # True: tính cả việc heo bên dưới NỞ RA khi gộp sẽ đẩy heo phía trên lên (đỉnh hiệu dụng), thay vì chỉ nhìn đỉnh hiện tại
        self.w_safe = 30000.0     # phạt mềm (bình phương) khi đỉnh hiệu dụng còn cách vạch < safe_line*H ; 0 = tắt
        self.safe_line = 0.25
        self.w_flat = 800.0       # phạt bề mặt đống heo gồ ghề (cột cao hẹp sát tường): x độ lệch chuẩn chiều cao các cột / H
        self.w_l10 = 3000.0       # thưởng mỗi con cấp cao nhất (L10) đang nằm trên bàn
        self.w_count = 60.0       # phạt MỖI con heo còn trên bàn: mỗi lần gộp (kể cả L1+L1) bớt 1 con = +60 điểm -> gộp heo nhỏ thay vì để rải rác ; 0 = tắt
        self.w_corner = 0.0      # thưởng con TO NHẤT nằm sát góc (khe giữa nó và tường góc càng nhỏ càng tốt)
        self.w_inv = 0.0          # phạt "đảo thứ tự": con to hơn nằm XA góc hơn con nhỏ hơn (muốn dốc giảm dần từ góc ra), x chênh cấp
        self.w_buried = 0.0       # phạt heo nhỏ (cấp<=3) bị heo khác đè lên phía trên (thả từ trên xuống không còn tới được), x 2^cấp
        self.w_dup = 0.0          # phạt thừa heo cùng cấp không chạm nhau (>2 con) - chiếm chỗ, x 2^cấp
        self.corner_side = "auto"  # "left" / "right" / "auto" (auto = phía tường gần con to nhất)
        self.danger_line = 0.10   # mép trên heo cao hơn (tỉ lệ H) mà thấp hơn mức này thì phạt nặng
        # --- đợt 2026-10-09: ưu tiên SỐNG + dọn heo nhỏ cho gọn bàn ---
        self.w_lose = 1e6         # phạt THUA cứng: mép trên heo (sau khi gộp nở xong) cao hơn lose_margin*H -> coi như thua, gần như loại nước đó (0 = tắt)
        self.lose_margin = 0.02   # tỉ lệ H: mép trên thấp hơn mức này (tính từ đỉnh khung) là thua (chừa ~16px cho sai số nhận diện/mô phỏng)
        self.next_weighted = True # nhìn trước con kế: trung bình có TRỌNG SỐ theo tỉ lệ con thả thật (L1 31%, L2 28%, L3 28%, L4 14%), không phải trung bình đều
        self.w_small_cnt = 0.0    # phạt MỖI heo nhỏ (cấp <= small_max) còn trên bàn: ép gộp heo nhỏ (nhất là L1) thay vì để rải rác chiếm chỗ ; 0 = tắt
        self.small_max = 3
        self.w_tower = 0.0        # phạt cột heo CAO vọt so với mặt đống (trung vị các cột) - tránh dựng tháp sát tường ; 0 = tắt
        self.w_skyline = 3000.0   # phạt CHIỀU CAO TRUNG BÌNH của mặt đống (x tỉ lệ H): heo nhỏ chui vào chỗ trũng thay vì chất lên đỉnh -> bàn gọn, ít khe rỗng ; 0 = tắt
        for k, v in kw.items():
            setattr(self, k, v)


def _bigpair_score(balls, W, ep):
    """Thưởng/phạt theo cấp số nhân cho các cặp heo lớn cùng cấp: gần nhau không bị chắn = đáng giá (sắp ra cấp kế), bị con khác chắn giữa = phạt."""
    sc = 0.0
    n = len(balls)
    for i in range(n):
        li, xi, yi, ri = balls[i]
        if li < ep.bigpair_min or li >= NLV:
            continue
        for j in range(i + 1, n):
            lj, xj, yj, rj = balls[j]
            if lj != li:
                continue
            dx, dy = xj - xi, yj - yi
            dist = math.hypot(dx, dy)
            gap = dist - ri - rj
            if gap > 2.0 * ri:
                continue
            V = 2.0 ** li
            L2 = dist * dist + 1e-9
            blocked = False
            for k in range(n):
                if k == i or k == j:
                    continue
                lk, xk, yk, rk = balls[k]
                t = ((xk - xi) * dx + (yk - yi) * dy) / L2
                if t <= 0.05 or t >= 0.95:
                    continue
                if math.hypot(xk - (xi + t * dx), yk - (yi + t * dy)) < 0.9 * rk:
                    blocked = True
                    break
            if blocked:
                sc -= ep.w_blocker * V
            else:
                sc += ep.w_bigpair * V * max(0.0, 1.0 - max(0.0, gap) / (2.0 * ri))
    return sc


def effective_top(balls, W):
    """Đỉnh cao nhất tính cả 'đẩy lên do heo bên dưới nở ra khi gộp': heo k đỡ heo j mà k còn gộp được (có >=2 con cùng cấp trên bàn, hoặc cấp<=4
    vì con thả hay trùng) thì khi gộp bán kính tăng dr, mép trên của j bị đẩy lên ~2*dr (cộng dồn theo chuỗi đỡ). Cảnh báo: đây là ước lượng
    bảo thủ từ hình học, KHÔNG phải vật lý thật của game."""
    n = len(balls)
    if n == 0:
        return 1e9
    cnt = {}
    for b in balls:
        cnt[b[0]] = cnt.get(b[0], 0) + 1
    order = sorted(range(n), key=lambda i: -balls[i][2])      # từ dưới lên
    push = [0.0] * n
    worst = 1e9
    for j in order:
        lj, xj, yj, rj = balls[j]
        pj = 0.0
        for k in range(n):
            if k == j:
                continue
            lk, xk, yk, rk = balls[k]
            if yk <= yj + 1e-6 or math.hypot(xj - xk, yj - yk) > rj + rk + 4.0:
                continue
            g = 0.0
            if lk < NLV and (cnt.get(lk, 0) >= 2 or lk <= 4):
                g = 2.0 * (R_FRAC[lk] - R_FRAC[lk - 1]) * W
            pj = max(pj, g + push[k])
        push[j] = pj
        worst = min(worst, yj - rj - pj)
    return worst


def surface_roughness(balls, W, H, nb=12):
    """Độ lệch chuẩn (so với H) của chiều cao bề mặt đống heo trên nb cột đều nhau."""
    hs = []
    for c in range(nb):
        x = (c + 0.5) * W / nb
        top = H
        for _, xc, yc, r in balls:
            dx = abs(x - xc)
            if dx < r:
                top = min(top, yc - math.sqrt(r * r - dx * dx))
        hs.append(top)
    m = sum(hs) / nb
    return math.sqrt(sum((h - m) ** 2 for h in hs) / nb) / H


def _col_tops(balls, W, H, nb=12):
    """Mép trên của đống heo tại nb cột đều nhau (y nhỏ = cao; cột trống = H)."""
    hs = []
    for c in range(nb):
        x = (c + 0.5) * W / nb
        top = H
        for _, xc, yc, r in balls:
            dx = abs(x - xc)
            if dx < r:
                top = min(top, yc - math.sqrt(r * r - dx * dx))
        hs.append(top)
    return hs


def _tower_penalty(balls, W, H, ep, nb=12):
    """Phạt cột heo cao vọt so với mặt đống (trung vị chiều cao 12 cột): tháp dựng sát tường không còn chỗ để heo lăn xuống/gộp."""
    hs = _col_tops(balls, W, H, nb)
    med = sorted(hs)[nb // 2]
    return ep.w_tower * (max(0.0, med - min(hs)) / H) ** 2


def _valley_xs(balls, W, H, nb=48, max_n=4):
    """Tâm các chỗ TRŨNG của mặt đống (cột thấp hơn hẳn hai bên): vị trí thả ứng viên để heo nhỏ chui khe/lấp chỗ trống thay vì chất lên đỉnh."""
    hs = _col_tops(balls, W, H, nb)
    out = []
    for i in range(nb):
        lo_i, hi_i = max(0, i - 3), min(nb - 1, i + 3)
        left_peak = min(hs[lo_i:i + 1])
        right_peak = min(hs[i:hi_i + 1])
        # valley: thấp (y lớn) hơn cả hai phía ít nhất 0.02H và là cực đại cục bộ của y
        if hs[i] >= max(hs[max(0, i - 1)], hs[min(nb - 1, i + 1)]) and hs[i] - left_peak >= 0.02 * H and hs[i] - right_peak >= 0.02 * H and hs[i] < H - 1:
            out.append((hs[i], (i + 0.5) * W / nb))
    out.sort(key=lambda t: -t[0])
    return [x for _, x in out[:max_n]]


def evaluate(balls, gain, W, H, ep):
    sc = ep.w_gain * gain
    if not balls:
        return sc
    sc -= ep.w_count * len(balls)
    top = min(y - r for _, _, y, r in balls)
    height = max(0.0, (H - top) / H)
    sc -= ep.w_height * height ** 3
    if ep.w_lose > 0 and top < ep.lose_margin * H:
        sc -= ep.w_lose * (1.0 + (ep.lose_margin * H - top) / H)       # THUA thật: heo chạm vạch trên -> không bao giờ chọn nếu còn nước khác
    if ep.w_small_cnt > 0:
        sc -= ep.w_small_cnt * sum(1 for b in balls if b[0] <= ep.small_max)
    if ep.w_tower > 0:
        sc -= _tower_penalty(balls, W, H, ep)
    if ep.w_skyline > 0:
        hs24 = _col_tops(balls, W, H, 24)
        sc -= ep.w_skyline * sum(H - h for h in hs24) / (24.0 * H)
    if ep.reserve or ep.w_safe > 0:
        top = min(top, effective_top(balls, W))          # thua = heo chạm vạch trên: tính cả cú đẩy khi gộp nở ra
    if top < ep.danger_line * H:
        sc -= 1e5 * (ep.danger_line * H - top) / H + 5e3
    if ep.w_safe > 0 and top < ep.safe_line * H:
        sc -= ep.w_safe * ((ep.safe_line * H - top) / H) ** 2
    if ep.w_flat > 0:
        sc -= ep.w_flat * surface_roughness(balls, W, H)
    if ep.w_l10 > 0:
        sc += ep.w_l10 * sum(1 for b in balls if b[0] >= NLV)
    if ep.w_bigpair > 0 or ep.w_blocker > 0:
        sc += _bigpair_score(balls, W, ep)
    area = sum(math.pi * r * r for _, _, _, r in balls) / (W * H)
    sc -= ep.w_area * area
    n = len(balls)
    for i in range(n):
        li, xi, yi, ri = balls[i]
        sc += ep.w_big_low * (2 ** li) ** 0.5 * (yi / H) * 0.5
        bigger = 0
        for j in range(n):
            if i == j:
                continue
            lj, xj, yj, rj = balls[j]
            d = math.hypot(xi - xj, yi - yj) - ri - rj
            if lj == li and j > i and li < NLV and d < 0.35 * ri:
                sc += ep.w_pair * (2 ** li) * (1.0 - max(0.0, d) / (0.35 * ri + 1e-9))
            if lj > li and d < 0.1 * ri:
                bigger += 1
        if li <= 4 and bigger >= 2:
            sc -= ep.w_trap * (2 ** li)
    sc += ep.w_top_lv * max(lv for lv, _, _, _ in balls)
    if ep.w_grad > 0:
        pen = 0.0
        for i in range(n):
            li, xi, yi, ri = balls[i]
            for j in range(i + 1, n):
                lj, xj, yj, rj = balls[j]
                if abs(li - lj) > 1 and math.hypot(xi - xj, yi - yj) - ri - rj < 0.12 * min(ri, rj):
                    pen += (abs(li - lj) - 1) ** 2
        sc -= ep.w_grad * pen
    if ep.w_order > 0 and n >= 3:
        xs = sorted((b for b in balls if b[0] >= 3), key=lambda b: b[1])
        lr = rl = 0.0
        for i in range(len(xs)):
            for j in range(i + 1, len(xs)):
                d = xs[j][0] - xs[i][0]
                if d > 0:
                    lr += d
                elif d < 0:
                    rl -= d
        sc -= ep.w_order * min(lr, rl)
    sc -= _block_wedge_penalty(balls, W, ep)
    sc -= _structure_penalty(balls, W, ep)
    return sc


def _structure_penalty(balls, W, ep):
    """Cấu trúc kiểu '2048 dồn góc' cho game ghép heo: (1) con to nhất sát một góc; (2) từ góc ra xa, cấp giảm dần (dốc thoải) để một con
    thả cuối gây gộp dây chuyền; (3) heo nhỏ không bị chôn dưới con khác; (4) không thừa nhiều heo cùng cấp rời rạc."""
    n = len(balls)
    if n < 2:
        return 0.0
    pen = 0.0
    mb = max(balls, key=lambda b: (b[0], b[3]))
    side = ep.corner_side if ep.corner_side in ("left", "right") else ("left" if mb[1] < W / 2.0 else "right")

    def dist(b):                                   # khoảng cách ngang từ tâm tới tường góc
        return b[1] if side == "left" else W - b[1]
    if mb[0] >= 4:
        if ep.w_corner > 0:
            gap = max(0.0, dist(mb) - mb[3]) / W
            pen += ep.w_corner * (2 ** mb[0]) ** 0.5 * gap
        if ep.w_inv > 0:
            bigs = [b for b in balls if b[0] >= 3]
            for i in range(len(bigs)):
                for j in range(len(bigs)):
                    a, b = bigs[i], bigs[j]
                    if a[0] > b[0] and dist(a) > dist(b) + 0.3 * (a[3] + b[3]):
                        pen += ep.w_inv * (a[0] - b[0]) * min(1.0, (dist(a) - dist(b)) / (0.5 * W))
    if ep.w_buried > 0:
        for i in range(n):
            li, xi, yi, ri = balls[i]
            if li > 3:
                continue
            for j in range(n):
                if i == j:
                    continue
                lj, xj, yj, rj = balls[j]
                if lj != li and yj < yi - 0.4 * rj and abs(xi - xj) < 0.8 * (ri + rj):
                    pen += ep.w_buried * (2 ** li)
                    break
    if ep.w_dup > 0:
        cnt = {}
        for lv, _, _, _ in balls:
            if lv < NLV:
                cnt[lv] = cnt.get(lv, 0) + 1
        for lv, c in cnt.items():
            if c > 2:
                pen += ep.w_dup * (2 ** lv) * (c - 2)
    return pen


def _block_wedge_penalty(balls, W, ep):
    """Chống KẸT: (1) heo nhỏ nằm chen giữa 2 heo to cùng cấp (>=3) làm 2 con to không chạm nhau được;
    (2) heo nhỏ (cấp<=3) bị kẹp giữa heo to và tường/góc."""
    pen = 0.0
    n = len(balls)
    if ep.w_block > 0:
        for i in range(n):
            li, xi, yi, ri = balls[i]
            if li < 3 or li >= NLV:
                continue
            for j in range(i + 1, n):
                lj, xj, yj, rj = balls[j]
                if lj != li:
                    continue
                dx, dy = xj - xi, yj - yi
                L2 = dx * dx + dy * dy
                if L2 < 1e-6 or math.sqrt(L2) > 3.2 * (ri + rj):
                    continue                                   # 2 con quá xa nhau, chưa kể là cặp chờ gộp
                for k in range(n):
                    if k == i or k == j:
                        continue
                    lk, xk, yk, rk = balls[k]
                    t = ((xk - xi) * dx + (yk - yi) * dy) / L2
                    if t <= 0.05 or t >= 0.95:
                        continue
                    d = math.hypot(xk - (xi + t * dx), yk - (yi + t * dy))      # cách đường nối tâm 2 con to
                    if d < rk + 0.35 * min(ri, rj):
                        pen += ep.w_block * (2 ** li) * (1.0 if lk < li else 0.6)
    if ep.w_wedge > 0:
        for i in range(n):
            li, xi, yi, ri = balls[i]
            if li > 3:
                continue
            wall = xi - ri < 0.035 * W or xi + ri > W * 0.965
            if not wall:
                continue
            for j in range(n):
                if i == j:
                    continue
                lj, xj, yj, rj = balls[j]
                if lj > li + 1 and math.hypot(xi - xj, yi - yj) - ri - rj < 0.12 * ri:
                    pen += ep.w_wedge * (2 ** li)
                    break
    return pen


def choose_drop(balls, held, W, H, sp, ep, think_s=2.5, n_x=25, next_levels=(1, 2, 3, 4), topk=6, log=None, held_top=None, y0_fixed=None,
                valleys=True, refine=True):
    """Trả (x_trong_khung, thông tin). held=(lv,r). held_top: mép trên con cầm cách mép trên khung (x W) -> heo rơi từ ĐÚNG độ cao
    thật (mặc định HELD_TOP) thay vì ngay sát mép khung (rơi từ cao hơn thì chạm sàn/heo mạnh hơn, lăn xa hơn)."""
    t0 = time.time()
    ht = HELD_TOP if held_top is None else held_top

    def y0_for(r_):
        return y0_fixed if y0_fixed is not None else -ht * W + r_
    lv, r = held
    lo, hi = r * 1.0, W - r * 1.0

    def cand_x(lv_, r_, n):
        xs = list(np.linspace(r_, W - r_, n))
        for b in balls:
            if b[0] == lv_ and lv_ < NLV:
                for dx in (0.0, -(b[3] + r_) * 0.97, (b[3] + r_) * 0.97):
                    xs.append(min(max(b[1] + dx, r_), W - r_))
        if valleys and balls:
            xs.extend(min(max(vx, r_), W - r_) for vx in _valley_xs(balls, W, H))
        out = []
        for x in sorted(xs):
            if not out or abs(x - out[-1]) > 0.006 * W:
                out.append(x)
        return out

    res1 = []
    for x in cand_x(lv, r, n_x):
        nb, g = simulate(balls, W, H, (lv, x, r, y0_for(r)), sp)
        res1.append((evaluate(nb, g, W, H, ep), x, nb, g))
        if time.time() - t0 > think_s * 0.5 and len(res1) >= 8:
            break
    res1.sort(key=lambda t: -t[0])
    if refine and len(res1) >= 3 and time.time() - t0 < think_s * 0.5:
        # tinh chỉnh vị trí: thử thêm 2 điểm sát hai bên mỗi nước trong top 3 (lưới thô cách nhau ~(W-2r)/n_x px, heo nhỏ chui khe cần chính xác hơn)
        step_x = max(4.0, 0.3 * (W - 2 * r) / max(1, n_x))
        have = [t_[1] for t_ in res1]
        for s_, x_, _nb, _g in list(res1[:3]):
            for dx_ in (-step_x, step_x):
                xn = min(max(x_ + dx_, lo), hi)
                if any(abs(xn - h_) < 0.5 * step_x for h_ in have):
                    continue
                nb_, g_ = simulate(balls, W, H, (lv, xn, r, y0_for(r)), sp)
                res1.append((evaluate(nb_, g_, W, H, ep), xn, nb_, g_))
                have.append(xn)
        res1.sort(key=lambda t: -t[0])
    best = res1[0]
    final = []
    for s1, x, nb, g in res1[:topk]:
        tot, cnt = 0.0, 0.0
        for nl in next_levels:
            r2 = r_for(nl, W)
            bests = None
            for x2 in cand_x(nl, r2, 9):
                nb2, g2 = simulate(nb, W, H, (nl, x2, r2, y0_for(r2)), sp)
                e2 = evaluate(nb2, g2, W, H, ep)
                if bests is None or e2 > bests:
                    bests = e2
            wgt = LEVEL_PROB.get(nl, 0.25) if ep.next_weighted else 1.0
            tot += wgt * bests
            cnt += wgt
            if time.time() - t0 > think_s:
                break
        base = 0.4 * s1 + 0.6 * (tot / cnt) if cnt else s1
        # (a) thả THẲNG vào tâm heo cùng cấp (chắc chắn chạm) được thưởng nhẹ so với thả lệch sang cạnh
        if g > 0 and ep.w_direct > 0:
            _fb, _fdx, _ = first_contact(balls, x, r)
            if _fb is not None and _fb[0] == lv and lv < NLV and abs(_fdx) <= 0.2 * (_fb[3] + r):
                base += ep.w_direct * lv
        # (b) độ bền: lệch vị trí thả ±1.2% chiều rộng (sai số bấm/nhận diện) mà mất điểm nhiều = nước đi mong manh (vd chỉ vừa chạm tiếp tuyến)
        if ep.w_robust > 0 and time.time() - t0 <= think_s:
            dlt = 0.012 * W
            worst = s1
            for xe in (max(r, x - dlt), min(W - r, x + dlt)):
                nbe, ge = simulate(balls, W, H, (lv, xe, r, y0_for(r)), sp)
                worst = min(worst, evaluate(nbe, ge, W, H, ep))
            base -= ep.w_robust * max(0.0, s1 - worst)
        # (c) độ bền theo ĐỘ RỘNG: heo to/nhỏ hơn +-rad_jit (đo bán kính sai vài px) mà lần gộp biến mất / điểm tụt = nước đi chỉ đúng trên giấy
        #     (vd thả L1 xuống khe hẹp tưởng lọt xuống chạm L1 dưới, thực tế kẹt ở miệng khe; hoặc chạm tiếp tuyến không tới)
        if ep.w_width > 0 and ep.rad_jit > 0 and time.time() - t0 <= think_s:
            import copy
            worst_w, gain_min = s1, g
            for k in (1.0 - ep.rad_jit, 1.0 + ep.rad_jit):
                spk = copy.copy(sp)
                spk.rad_scale = sp.rad_scale * k
                nbw, gw = simulate(balls, W, H, (lv, x, r, y0_for(r)), spk)
                worst_w = min(worst_w, evaluate(nbw, gw, W, H, ep))
                gain_min = min(gain_min, gw)
            base -= ep.w_width * max(0.0, s1 - worst_w)
            if g > 0 and gain_min < g:
                base -= ep.w_width_gain * (g - gain_min)
        # (d) độ bền theo VẬT LÝ: thử vài bộ tham số khác (trơn/nhám, nảy nhiều, rơi mạnh). Trên 233 lượt thật, nhóm lượt mà các bộ này cho kết quả
        #     khác nhau nhiều thì dự đoán sai gấp ~2.5 lần (0.085 so với 0.034) -> nước đi nào "phụ thuộc may rủi nảy/lăn" bị trừ điểm.
        if ep.w_phys > 0 and time.time() - t0 <= think_s:
            import copy
            scs, gmin_p = [], g
            for ch in PHYS_VARIANTS:
                spv = copy.copy(sp)
                for k_, m_ in ch:
                    lo_, hi_ = CAL_RANGE.get(k_, (0.0, 1e9))
                    setattr(spv, k_, min(max(getattr(sp, k_) * m_, lo_ * 0.5), hi_ * 2.0 if k_ == "gravity" else hi_))
                nbv, gv = simulate(balls, W, H, (lv, x, r, y0_for(r)), spv)
                scs.append(evaluate(nbv, gv, W, H, ep))
                gmin_p = min(gmin_p, gv)
            if scs:
                base -= ep.w_phys * max(0.0, s1 - (sum(scs) / len(scs)))
                if g > 0 and gmin_p < g:
                    base -= ep.w_phys_gain * (g - gmin_p)
        # (e) đường rơi: dự đoán có gộp nhưng heo rơi chạm VAI một con KHÁC (không phải con cùng cấp sẽ gộp ngay) trước -> bị văng ra ("nảy")
        if g > 0 and ep.w_graze > 0:
            fb, fdx, _fy = first_contact(balls, x, r)
            if fb is not None and not (fb[0] == lv and lv < NLV):
                base -= ep.w_graze * g * min(1.0, 0.4 + abs(fdx) / max(1.0, r + fb[3]))
        final.append((base, x, s1))
        if time.time() - t0 > think_s:
            break
    final.sort(key=lambda t: -t[0])
    x = final[0][1] if final else best[1]
    info = {"x": float(x), "score1": float(best[0]), "n_eval": len(res1), "sec": round(time.time() - t0, 2),
            "top": [(round(float(f[1]), 1), round(float(f[0]), 1)) for f in final[:3]]}
    return x, info


def r_for(lv, W):
    return R_FRAC[lv - 1] * W


def first_contact(balls, x, r):
    """Heo rơi THẲNG xuống tại x (bán kính r): chạm con nào TRƯỚC? Trả (con_bị_chạm, dx, y_chạm) hoặc (None, 0, None) nếu rơi xuống sàn.
    Con chạm đầu tiên quyết định nảy/lăn: chạm đúng con cùng cấp thì gộp ngay (không cần vật lý), chạm vai con khác thì bị văng sang bên."""
    best = None
    for b in balls:
        dx = x - b[1]
        rr = r + b[3]
        if abs(dx) < rr:
            yc = b[2] - math.sqrt(rr * rr - dx * dx)
            if best is None or yc < best[2]:
                best = (b, dx, yc)
    return best if best else (None, 0.0, None)


# các biến thể vật lý để thử độ bền: (tên tham số, hệ số nhân)
PHYS_VARIANTS = (
    (("friction", 0.5),),                       # trơn hơn -> lăn xa hơn
    (("friction", 1.6),),                       # nhám hơn -> lăn ngắn
    (("elasticity", 3.5),),                     # nảy nhiều hơn
    (("gravity", 1.8), ("damping", 0.9)),       # rơi mạnh hơn
)


class RadiusBook:
    """Nhớ TỈ LỆ bán kính thật của từng cấp (đo từ vòng viền heo trên bàn, trung bình trượt) để mọi con CÙNG CẤP dùng ĐÚNG MỘT bán kính.
    Lỗi cũ: con đang cầm dùng bán kính danh nghĩa (R_FRAC) +-3px còn heo trên bàn dùng bán kính Hough đo được (heo cấp 1 thường nhỏ hơn
    ~8-10%) -> mô phỏng tưởng 2 con cùng cấp chạm nhau (hoặc lọt khe) trong khi ngoài đời thì không."""

    def __init__(self, alpha=0.35, lo=0.85, hi=1.12):
        self.ratio = {}
        self.alpha, self.lo, self.hi = alpha, lo, hi

    def update(self, pigs, W, min_score=0.7):
        for lv, cx, cy, r, s in pigs:
            q = r / (R_FRAC[lv - 1] * W)
            if s < min_score or not (self.lo <= q <= self.hi):
                continue
            old = self.ratio.get(lv)
            self.ratio[lv] = q if old is None else (1 - self.alpha) * old + self.alpha * q

    def ratio_for(self, lv):
        q = self.ratio.get(lv)
        if q is not None:
            return q
        if not self.ratio:
            return 1.0
        near = sorted(self.ratio, key=lambda k: abs(k - lv))[:2]      # cấp chưa thấy: lấy trung bình 2 cấp gần nhất
        return sum(self.ratio[k] for k in near) / len(near)

    def r(self, lv, W):
        return self.ratio_for(lv) * R_FRAC[lv - 1] * W

    def snap(self, pigs, W, tol=0.05):
        """[(cấp,cx,cy,r,điểm)] -> [(cấp,cx,cy,r_chuẩn)] ; r_chuẩn chỉ lệch tối đa +-tol so với r đo riêng của con đó."""
        out = []
        for lv, cx, cy, r, *_ in pigs:
            rs = self.r(lv, W)
            out.append((lv, cx, cy, min(max(rs, r * (1 - tol)), r * (1 + tol))))
        return out


# ----------------------------------------------------------------------------------------------
# KIỂM TRA DỰ ĐOÁN + TỰ HIỆU CHỈNH THAM SỐ VẬT LÝ
# ----------------------------------------------------------------------------------------------
CAL_RANGE = {"gravity": (0.8, 9.0), "damping": (0.3, 1.0), "friction": (0.05, 1.3),
             "elasticity": (0.0, 0.8), "rad_scale": (0.90, 1.08)}


def pred_error(pred, obs, W, cap=0.25):
    """Sai số dự đoán vs ảnh thật (theo chiều rộng khung): khớp từng con theo cấp + gần nhất; con không khớp bị phạt `cap`.
    Trả (sai số TB, số con lệch)."""
    used, tot, miss = set(), 0.0, 0
    for lv, x, y, r in sorted(pred, key=lambda b: -b[0]):
        best = None
        for j, b in enumerate(obs):
            if j in used or b[0] != lv:
                continue
            d = math.hypot(b[1] - x, b[2] - y) / W
            if best is None or d < best[0]:
                best = (d, j)
        if best is None:
            tot += cap
            miss += 1
        else:
            used.add(best[1])
            tot += min(cap, best[0])
    extra = len(obs) - len(used)
    tot += cap * extra
    miss += extra
    return tot / max(1, max(len(pred), len(obs))), miss


def calibrate(samples, sp, W, H, budget_s=2.0, seed=None):
    """Leo đồi ngẫu nhiên trên các tham số vật lý để mô phỏng khớp ảnh thật hơn.
    samples: [(before, (cấp,bán kính), x_thả, after_thật)]. Trả (SimParams mới, sai số trước, sau, số lần thử)."""
    import copy
    import random
    rnd = random.Random(seed)

    def total(p):
        # trung bình CÓ CẮT ĐUÔI: bỏ 25% mẫu sai nhiều nhất (đọc nhầm cấp con cầm, heo bị đẩy bởi hiệu ứng...) để không kéo tham số
        # vật lý về cực trị (vd friction ~1, rad_scale chạm trần) chỉ để chiều theo mẫu hỏng
        errs = []
        for smp in samples:
            before, held, x, after = smp[:4]
            y0 = smp[4] if len(smp) > 4 else None
            pr, _ = simulate(before, W, H, (held[0], x, held[1], y0), p)
            errs.append(pred_error(pr, after, W)[0])
        errs.sort()
        keep = max(1, int(math.ceil(len(errs) * 0.75)))
        return sum(errs[:keep]) / keep

    best = copy.copy(sp)
    e0 = eb = total(best)
    t0, n, stepf = time.time(), 0, 0.3
    keys = list(CAL_RANGE)
    while time.time() - t0 < budget_s:
        cand = copy.copy(best)
        for k in rnd.sample(keys, rnd.choice((1, 2))):
            lo, hi = CAL_RANGE[k]
            v = getattr(cand, k) * (1.0 + rnd.uniform(-stepf, stepf))
            setattr(cand, k, min(hi, max(lo, v)))
        e = total(cand)
        n += 1
        if e < eb:
            best, eb = cand, e
        if n % 15 == 0:
            stepf = max(0.06, stepf * 0.8)
    return best, e0, eb, n


def _params_path(step):
    return os.path.join(step.get("debug_dir", "debug_pig"), "pig_params.json")


def _load_params(step, log):
    sp = SimParams()
    if step.get("reset_params"):
        try:
            os.remove(_params_path(step))
            log("info", "🐷 reset_params: bỏ tham số vật lý đã lưu, dùng mặc định")
        except Exception:
            pass
    try:
        with open(_params_path(step), encoding="utf-8") as f:
            d = json.load(f)
        for k in CAL_RANGE:
            if k in d:
                setattr(sp, k, float(d[k]))
        log("info", "🐷 Nạp tham số vật lý đã hiệu chỉnh: " + ", ".join("%s=%.3f" % (k, getattr(sp, k)) for k in CAL_RANGE))
    except Exception:
        pass
    for k in ("gravity", "damping", "friction", "elasticity", "rad_scale", "merge_eps"):
        if k in step:
            setattr(sp, k, float(step[k]))
    return sp


def _save_params(step, sp):
    try:
        os.makedirs(step.get("debug_dir", "debug_pig"), exist_ok=True)
        with open(_params_path(step), "w", encoding="utf-8") as f:
            json.dump({k: getattr(sp, k) for k in CAL_RANGE}, f, indent=1)
    except Exception:
        pass


# ----------------------------------------------------------------------------------------------
# ĐIỀU KHIỂN
# ----------------------------------------------------------------------------------------------
def _board_px(step, fw, fh):
    """Khung bàn (khung nét đứt) -> pixel. MẶC ĐỊNH CỐ ĐỊNH theo tỉ lệ ảnh (BOARD_EMU/BOARD_PHONE), bỏ qua board_from/board_to đã lưu
    trong bước; muốn tự đặt thì bật `board_custom: true` (menu chuột phải của bước -> Chọn Lại Khung Bàn)."""
    d = _default_board(fw, fh)
    if step.get("board_custom"):
        p1 = step.get("board_from") or d[0]
        p2 = step.get("board_to") or d[1]
    else:
        p1, p2 = d[0], d[1]
    x1, x2 = sorted((int(p1[0] * fw), int(p2[0] * fw)))
    y1, y2 = sorted((int(p1[1] * fh), int(p2[1] * fh)))
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(fw, x2), min(fh, y2)           # khung kéo tay có thể lòi ra ngoài ảnh
    return (x1, y1, max(x1 + 50, x2), max(y1 + 50, y2))


# ----------------------------------------------------------------------------------------------
# THẢ HEO: nhấn giữ -> kéo -> ĐỌC lại vị trí thật -> chỉnh -> nhả
# ----------------------------------------------------------------------------------------------
def locate_held_x(img, box, lv, cy_abs, x_expect_abs, span=0.30):
    """Tìm x (pixel TUYỆT ĐỐI trên ảnh) của con đang cầm cấp `lv` khi nó đang bị kéo ngang. Con cầm có y cố định (cy_abs) nên chỉ quét
    theo x quanh x_expect_abs (+-span x W). Trả (x_abs, điểm) hoặc None."""
    x1, y1, x2, y2 = [int(v) for v in box]
    W = x2 - x1
    r = R_FRAC[lv - 1] * W
    ih, iw = img.shape[:2]
    ya, yb = max(0, int(cy_abs - r - 24)), min(ih, int(cy_abs + r + 24))
    xa, xb = max(0, int(x1 - 0.06 * W)), min(iw, int(x2 + 0.06 * W))
    band = img[ya:yb, xa:xb]
    if band.size == 0:
        return None
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    m = _group_masks(hsv)[GROUP[lv - 1]]
    lo, hi = int(x_expect_abs - span * W), int(x_expect_abs + span * W)
    cands = []
    for cx in range(lo, hi + 1, 4):
        for dy in (-6, -3, 0, 3, 6):
            sc = _ring_cover(m, cx - xa, cy_abs + dy - ya, r)
            if sc >= 0.35:
                cands.append((sc, cx, dy))
    cands.sort(reverse=True)
    best = None
    for _, cx0, dy0 in cands[:6]:
        for dr in (-3, 0, 3):
            for ddx in range(-4, 5, 2):
                for ddy in (-2, 0, 2):
                    cx, cy = cx0 + ddx - xa, cy_abs + dy0 + ddy - ya
                    sc = _ring_cover(m, cx, cy, r + dr)
                    if sc < 0.55:
                        continue
                    if lv == 1 and not _pink_inside(hsv, cx, cy, r):
                        continue
                    if best is None or sc > best[0]:
                        best = (sc, cx + xa)
    if best is None:
        return None
    return (float(best[1]), float(best[0]))


def _touch(adb, action, x, y):
    adb.run_cmd(["shell", "input", "touchscreen", "motionevent", action, str(int(round(x))), str(int(round(y)))])


def _drag_drop(adb, box, held, x_target, step, should_stop, log):
    """Thả heo đúng kiểu game: NHẤN lên con đang cầm -> KÉO ngang tới x_target (toạ độ trong khung) -> GIỮ yên -> chụp ảnh đọc x thật
    của con cầm -> chỉnh tay nếu lệch -> NHẢ. Trả x thật (toạ độ trong khung) lúc nhả; không đọc được thì trả x_target."""
    x1, y1 = box[0], box[1]
    W = box[2] - box[0]
    lv = int(held[0])
    hx0, hy = x1 + held[1], y1 + held[2]
    tx = x1 + x_target
    steps = max(2, int(step.get("drag_steps", 8)))
    move_s = float(step.get("drag_ms", 350)) / 1000.0
    settle = float(step.get("drag_settle", 0.15))
    fixes = int(step.get("drag_fix", 3))
    tol = float(step.get("drag_tol", 0.01)) * W
    fw_img = None
    fx = tx
    _touch(adb, "DOWN", hx0, hy)
    try:
        time.sleep(0.06)
        for i in range(1, steps + 1):
            _touch(adb, "MOVE", hx0 + (tx - hx0) * i / steps, hy)
            time.sleep(move_s / steps)
        x_real, prev, n_fix, waited = None, None, 0, 0
        while waited < fixes + 5:
            if should_stop():
                break
            _sleep(settle, should_stop)
            fr = adb.screencap_fast()
            if fr is None:
                break
            waited += 1
            loc = locate_held_x(fr, box, lv, hy, fx if prev is not None else tx)
            if loc is None:
                if prev is None:
                    log("warn", "🐷 Đang kéo mà không đọc được vị trí con cầm - nhả tại x dự kiến")
                break
            x_real = loc[0] - x1
            err = x_target - x_real
            if abs(err) <= tol:
                break                              # đã đúng chỗ
            if prev is None or (abs(x_real - prev) > 0.004 * W and waited < fixes + 5):
                prev = x_real                      # con cầm có thể còn đang trượt theo ngón tay -> đo lại, yên mới chỉnh
                continue
            prev = x_real
            if n_fix >= fixes:
                break
            n_fix += 1
            if fw_img is None:
                fw_img = fr.shape[1]
            fx = min(max(2.0, fx + err), fw_img - 3.0)
            _touch(adb, "MOVE", fx, hy)
            prev = None                            # đã chỉnh -> đo lại từ đầu
    finally:
        _touch(adb, "UP", fx, hy)
    return float(x_real if x_real is not None else x_target)


def _overlay(img, box, balls, held, x_drop, path):
    x1, y1, x2, y2 = box
    im = img.copy()
    for lv, cx, cy, r, *_ in balls:
        cv2.circle(im, (int(cx + x1), int(cy + y1)), int(r), (0, 255, 0), 3)
        cv2.putText(im, "L%d" % lv, (int(cx + x1 - 22), int(cy + y1 + 8)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
    if held:
        cv2.circle(im, (int(held[1] + x1), int(held[2] + y1)), int(held[3]), (255, 0, 0), 3)
        cv2.putText(im, "cam L%d" % held[0], (int(held[1] + x1 - 30), int(held[2] + y1 - held[3] - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 3)
    if x_drop is not None:
        cv2.line(im, (int(x_drop + x1), y1), (int(x_drop + x1), y2), (0, 165, 255), 3)
    cv2.rectangle(im, (x1, y1), (x2, y2), (255, 255, 0), 2)
    ok, buf = cv2.imencode(".png", im)
    if ok:
        buf.tofile(path)


def _cmp_overlay(img, box, pred, obs, x_drop, path, err_txt=""):
    """Ảnh SO SÁNH sau mỗi lượt thả: ảnh THẬT (sau khi heo nằm yên) + vòng XANH LÁ = heo thật đọc được,
    vòng TÍM = chỗ mô phỏng DỰ ĐOÁN, vạch cam = x đã thả. Vòng tím lệch vòng xanh nhiều = mô phỏng lăn/nảy chưa giống thật
    (kèm nhãn cấp + số px lệch của từng con khớp được)."""
    x1, y1, x2, y2 = box
    im = img.copy()
    used = set()
    for lv, cx, cy, r, *_ in obs:
        cv2.circle(im, (int(cx + x1), int(cy + y1)), int(r), (0, 255, 0), 3)
    for lv, cx, cy, r, *_ in sorted(pred, key=lambda b: -b[0]):
        best = None
        for j, b in enumerate(obs):
            if j in used or b[0] != lv:
                continue
            d = math.hypot(b[1] - cx, b[2] - cy)
            if best is None or d < best[0]:
                best = (d, j)
        col = (200, 0, 200)
        cv2.circle(im, (int(cx + x1), int(cy + y1)), int(r), col, 2)
        if best is not None:
            used.add(best[1])
            b = obs[best[1]]
            cv2.line(im, (int(cx + x1), int(cy + y1)), (int(b[1] + x1), int(b[2] + y1)), (0, 0, 255), 2)
            txt = "L%d d=%d" % (lv, round(best[0]))
        else:
            txt = "L%d ?" % lv
        cv2.putText(im, txt, (int(cx + x1 - 30), int(cy + y1 + 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    if x_drop is not None:
        cv2.line(im, (int(x_drop + x1), y1), (int(x_drop + x1), y2), (0, 165, 255), 3)
    cv2.rectangle(im, (x1, y1), (x2, y2), (255, 255, 0), 2)
    cv2.putText(im, "xanh=THAT  tim=DU DOAN  cam=x tha " + err_txt, (x1 + 6, y1 + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
    cv2.putText(im, "xanh=THAT  tim=DU DOAN  cam=x tha " + err_txt, (x1 + 6, y1 + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    ok, buf = cv2.imencode(".png", im)
    if ok:
        buf.tofile(path)


def _read_stamina(adb, frame, step):
    box_r = step.get("stamina_box") or [0.74, 0.932, 0.945, 0.962]
    fh, fw = frame.shape[:2]
    box = (int(box_r[0] * fw), int(box_r[1] * fh), int(box_r[2] * fw), int(box_r[3] * fh))
    try:
        txt = adb.ocr_text_in_box(frame, box, lang="eng", charset="all", extra_chars="/")
    except Exception:
        return None
    m = re.search(r"(\d+)\s*/\s*(\d+)", txt or "")
    return int(m.group(1)) if m else None


def _board_signature(img, box):
    x1, y1, x2, y2 = box
    g = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (64, 112), interpolation=cv2.INTER_AREA).astype(np.int16)


def _sleep(sec, should_stop):
    t0 = time.time()
    while time.time() - t0 < sec and not should_stop():
        time.sleep(min(0.1, max(0.0, sec - (time.time() - t0))))


def _wait_ready(adb, box, step, should_stop):
    """Sau khi thả: heo lăn/nảy thì game KHÔNG hiện con kế; con kế hiện ra trên đầu nhân vật = heo đã lăn xong.
    Chờ con cũ biến mất (tối đa gone_max) -> chờ con kế hiện (tối đa ready_max). Trả (frame ngay lúc con kế hiện, ready, t_ready).
    Khung hình này ĐÃ là trạng thái cuối nên tính luôn; chỉ việc bấm thì mới đợi đủ held_wait (xem vòng lặp chính)."""
    hu = float(step.get("held_top", HELD_TOP))
    gone_max = float(step.get("gone_max", 2.5))
    ready_max = float(step.get("ready_max", 25.0))
    _sleep(float(step.get("settle_min", 0.25)), should_stop)
    t0 = time.time()
    seen_gone, frame = False, None
    while time.time() - t0 < gone_max + ready_max and not should_stop():
        fr = adb.screencap_fast()
        if fr is None:
            time.sleep(0.2)
            continue
        frame = fr
        present = detect_held(fr, box, hu) is not None
        if not seen_gone:
            if (not present) or time.time() - t0 > gone_max:
                seen_gone = True
        elif present:
            return frame, True, time.time()
        time.sleep(0.15)
    return frame, False, time.time()


def _wait_stable(adb, box, step, should_stop, frame, log=None):
    """Chụp lặp tới khi bàn cờ THẬT SỰ yên rồi mới cho đọc: (1) băng điểm nổi (+50...) đã tắt, (2) ảnh vùng bàn gần như không đổi
    giữa 2 khung liên tiếp (heo hết lăn / hết hiệu ứng gộp), (3) con đang cầm đứng yên đúng chỗ (không còn đang trượt vào vị trí).
    Trả về khung hình yên (hoặc khung cuối nếu quá stable_max giây). Field: stable_need (2), stable_max (6.0), popup_max (3.0), stable_diff (0.7)."""
    need = int(step.get("stable_need", 2))
    t_max = float(step.get("stable_max", 6.0))
    popup_max = float(step.get("popup_max", 3.0))
    thr = float(step.get("stable_diff", 0.7))
    hu = float(step.get("held_top", HELD_TOP))
    t0 = time.time()
    prev_sig, prev_held, calm = None, None, 0
    cur, why = frame, ""
    while not should_stop():
        if cur is None:
            cur = adb.screencap_fast()
            if cur is None:
                time.sleep(0.15)
                continue
        pops = find_popups(cur, box)
        sig = _board_signature(cur, box)
        if pops:
            sg = sig.copy()
            sx, sy = sig.shape[1] / float(box[2] - box[0]), sig.shape[0] / float(box[3] - box[1])
            for px, py, pw, ph in pops:      # che băng điểm khi so sánh (băng trôi lên nên luôn làm ảnh đổi)
                sg[max(0, int((py - 6) * sy)):int((py + ph + 6) * sy) + 1, max(0, int((px - 6) * sx)):int((px + pw + 6) * sx) + 1] = 0
            sig_cmp = sg
        else:
            sig_cmp = sig
        held = detect_held(cur, box, hu)
        still = prev_sig is not None and float(np.abs(sig_cmp - prev_sig).mean()) < thr
        held_ok = held is not None and prev_held is not None and held[0] == prev_held[0] and \
            abs(held[1] - prev_held[1]) <= 3 and abs(held[2] - prev_held[2]) <= 3
        pop_ok = (not pops) or (time.time() - t0 > popup_max)
        if still and held_ok and pop_ok:
            calm += 1
        else:
            calm = 0
            why = "popup" if pops and not pop_ok else ("heo còn động" if not still else "con cầm chưa yên")
        if calm >= need:
            return cur
        if time.time() - t0 > t_max:
            if log:
                log("warn", "🐷 Chờ bàn cờ yên quá %.0fs (%s) - vẫn dùng ảnh hiện tại" % (t_max, why or "?"))
            return cur
        prev_sig, prev_held = sig_cmp, held
        time.sleep(0.12)
        cur = adb.screencap_fast()
    return cur


def run_auto_pig_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """
    Field của bước (đều tuỳ chọn):
      board_from / board_to  - 2 góc khung nét đứt theo tỉ lệ ảnh [x/w, y/h] (CHỈ dùng khi board_custom=true; mặc định khung cố định)
      test (false)           - true: chỉ nhận diện + tính, KHÔNG bấm; lưu ảnh kế hoạch
      max_turns (0)          - số lượt thả tối đa (0 = không giới hạn)
      max_seconds (0)        - thời gian tối đa (0 = không giới hạn)
      min_stamina (10)       - thể lực nhỏ hơn mức này thì dừng (đọc OCR 'n/150' ở góc phải dưới)
      stamina_box            - [x1,y1,x2,y2] tỉ lệ ảnh của chữ thể lực
      stamina_every (5)      - đọc OCR thể lực mỗi N lượt; tự trừ 1/lượt ở giữa; còn <= min_stamina+12 thì đọc mỗi lượt
      drop_mode ('tap')      - 'tap' (MẶC ĐỊNH): chạm 1 phát, heo thả THẲNG xuống tại điểm chạm (đã xác nhận trên game thật);
                               'drag': nhấn giữ -> kéo -> đọc lại x thật -> chỉnh -> nhả; 'swipe': kéo 1 mạch rồi nhả
      spawn_y ('held')       - 'held': mô phỏng cho heo rơi từ độ cao con đang cầm (trên hàng rào); 'click': heo xuất hiện ngay tại điểm chạm
                               (y = tap_y x H) rồi rơi - đổi nếu dự đoán lăn lệch hệ thống
      drag_steps (8) / drag_ms (350) / drag_settle (0.15) / drag_fix (3) / drag_tol (0.01) - số nấc kéo, thời gian kéo, chờ con cầm theo kịp,
                               số lần chỉnh tối đa, sai số cho phép (x W) khi drop_mode='drag'
      board_custom (false)   - false: khung bàn CỐ ĐỊNH theo tỉ lệ ảnh (bỏ qua board_from/board_to); true: dùng board_from/board_to tự chọn
      tap_y (0.08)           - độ cao điểm bấm trong khung (0 = mép trên, 1 = đáy) khi drop_mode='tap'
      think_s (tự động)      - thời gian suy nghĩ tối đa mỗi lượt; mặc định tính sao cho xong trong lúc đợi held_wait
      held_wait (2.0)        - chỉ bấm thả sau khi con kế hiện đủ ngần này giây (phòng lag); lúc đó bot đã chụp + tính xong
      auto_calib (true) / calib_every (6) / calib_s (2.0) - tự hiệu chỉnh gravity/damping/friction/elasticity/rad_scale từ ảnh thật, lưu debug_dir/pig_params.json
      n_x (25)               - số vị trí thả thử
      Chờ heo lăn yên: game chỉ hiện con kế tiếp khi heo đã lăn xong -> chờ con cũ biến mất (gone_max=2.5s) -> chờ con kế hiện (ready_max=25s)
                             -> chờ thêm held_wait (2.0s) rồi mới chụp để tính lượt tiếp; settle_min (0.25s) = nghỉ ngay sau khi bấm
      wait_stable (true)     - chờ bàn cờ yên hẳn (hết popup điểm, heo hết động, con cầm đứng yên) rồi mới chụp để tính; stable_need (2) khung yên liên tiếp,
                             stable_max (6.0s) chờ tối đa, popup_max (3.0s) chờ popup tắt tối đa, stable_diff (0.7) ngưỡng khác biệt ảnh
      held_level (0)         - ép cấp con đang cầm (0 = tự đọc); held_top (0.233) = mép trên con cầm cách mép trên khung bao nhiêu x chiều rộng (con cầm luôn ở GIỮA)
      assume_held (true) / held_default (1) - không đọc được con cầm 3 lần liền thì đoán cấp held_default (tối đa 3 lần, sau 6 lần dừng)
      reset_params (false)   - true: xoá debug_dir/pig_params.json (tham số vật lý đã hiệu chỉnh) và dùng mặc định
      gravity / damping / friction / elasticity / rad_scale / merge_eps - tham số mô phỏng
      w_*                    - trọng số hàm đánh giá (xem EvalParams); mới 2026-10-09: w_lose (phạt THUA cứng, 1e6), w_count (60: mỗi con heo còn trên bàn),
                               w_skyline (3000: chiều cao trung bình mặt đống), w_small_cnt / w_tower (mặc định 0 = tắt); lose_margin (0.02), next_weighted (true), small_max (3)
      valleys (true) / refine (true) - thêm vị trí thả ở chỗ trũng mặt đống / tinh chỉnh vị trí quanh 3 nước tốt nhất
      save_shots (true) / debug_dir ('debug_pig') / shots_keep (40) - ảnh kiểm tra mỗi lượt + nhật ký pig_log.jsonl
    """
    should_stop = should_stop or (lambda: False)
    log = log or (lambda level, msg: print("[%s] %s" % (level, msg)))
    if pymunk is None:
        log("error", "🐷 Auto Lợn Giống: chưa cài Pymunk - chạy:  pip install pymunk")
        return False
    test = bool(step.get("test", False))
    max_turns = int(step.get("max_turns", 0))
    max_sec = float(step.get("max_seconds", 0))
    min_st = int(step.get("min_stamina", 10))
    st_every = int(step.get("stamina_every", 5))
    drop_mode = step.get("drop_mode", "tap")
    tap_y = float(step.get("tap_y", 0.08))
    spawn_y = str(step.get("spawn_y", "held"))
    think_cfg = step.get("think_s")             # None = tự tính để xong trong lúc đợi held_wait
    held_wait = float(step.get("held_wait", 2.0))
    held_top = float(step.get("held_top", HELD_TOP))
    auto_calib = bool(step.get("auto_calib", True))
    calib_every = int(step.get("calib_every", 6))
    calib_s = float(step.get("calib_s", 2.0))
    n_x = int(step.get("n_x", 25))
    debug_dir = step.get("debug_dir", "debug_pig")
    save_shots = bool(step.get("save_shots", True))
    keep = int(step.get("shots_keep", 40))
    sp = _load_params(step, log)
    radius_fix = bool(step.get("radius_fix", True))      # đồng nhất bán kính từng cấp (heo bàn + con cầm); false = như cũ
    rbook = RadiusBook()
    ep = EvalParams(**{k: v for k, v in step.items() if k.startswith("w_") or k in ("danger_line", "lose_margin", "next_weighted", "small_max")})
    use_valleys = bool(step.get("valleys", True))        # thêm vị trí thả ứng viên ở chỗ trũng mặt đống
    use_refine = bool(step.get("refine", True))          # tinh chỉnh vị trí thả quanh 3 nước tốt nhất
    if save_shots or test:
        os.makedirs(debug_dir, exist_ok=True)
    t_start = time.time()

    frame = adb.screencap_fast()
    if frame is None:
        log("error", "🐷 Auto Lợn Giống: không chụp được màn hình")
        return False
    fh, fw = frame.shape[:2]
    log("info", "🐷 Khung bàn %s: %s (ảnh %dx%d), cách thả: %s" % (
        "TỰ CHỌN" if step.get("board_custom") else "CỐ ĐỊNH", _board_px(step, fw, fh), fw, fh, drop_mode))
    st = _read_stamina(adb, frame, step) if min_st > 0 else None
    st_est = st
    if st is not None:
        log("info", "🐷 Thể lực hiện tại: %d (dừng khi < %d)" % (st, min_st))
        if st < min_st:
            log("warn", "🐷 Thể lực %d < %d - không chơi" % (st, min_st))
            return False

    if not test and bool(step.get("wait_stable", True)):
        _fs = _wait_stable(adb, _board_px(step, fw, fh), step, should_stop, frame, log)
        if _fs is not None:
            frame = _fs
    turn, no_held, same_cnt, last_sig, err_cnt = 0, 0, 0, None, 0
    y0_last = None
    pending = None          # (before, held(lv,r), x, pred) của lượt trước
    samples = []            # mẫu (before, held, x, after_thật) để hiệu chỉnh
    t_ready = time.time() - held_wait   # lượt đầu: con đang cầm đã sẵn, không cần chờ thêm
    while not should_stop():
        if max_turns and turn >= max_turns:
            log("info", "🐷 Đủ %d lượt" % max_turns)
            break
        if max_sec and time.time() - t_start > max_sec:
            log("info", "🐷 Hết thời gian cho phép")
            break
        t_turn = time.time()
        box = _board_px(step, fw, fh)
        W, H = box[2] - box[0], box[3] - box[1]
        try:
            pigs = detect_pigs(frame, box)
            held = detect_held(frame, box, held_top)
        except Exception as e:
            err_cnt += 1
            import traceback
            tb = traceback.format_exc().strip().splitlines()
            log("warn", "🐷 Lỗi nhận diện (%d/3): %s | %s" % (err_cnt, repr(e), " / ".join(x.strip() for x in tb[-4:-1])))
            try:
                os.makedirs(debug_dir, exist_ok=True)
                cv2.imencode(".png", frame)[1].tofile(os.path.join(debug_dir, "pig_error.png"))
            except Exception:
                pass
            if err_cnt >= 3:
                log("error", "🐷 Lỗi nhận diện 3 lần liền, dừng")
                return False
            time.sleep(0.5)
            fr2 = adb.screencap_fast()
            frame = frame if fr2 is None else fr2
            continue
        err_cnt = 0
        if radius_fix:
            rbook.update(pigs, W)
        if step.get("held_level"):
            lv = int(step["held_level"])
            held = (lv, W / 2, -held_top * W + r_for(lv, W), r_for(lv, W))
        if held is None:
            no_held += 1
            if no_held == 1 and (save_shots or test):
                try:
                    os.makedirs(debug_dir, exist_ok=True)
                    _overlay(frame, box, pigs, None, None, os.path.join(debug_dir, "pig_noheld.png"))
                    log("warn", "🐷 Không thấy con đang cầm - đã lưu %s (khung xanh = khung bàn bot đang dùng, kiểm tra có khớp khung nét đứt không)" %
                        os.path.join(debug_dir, "pig_noheld.png"))
                except Exception:
                    pass
            if no_held >= 6:
                log("warn", "🐷 Không thấy con heo đang cầm %d lần liền - có thể ván đã kết thúc hoặc màn hình đã đổi, dừng" % no_held)
                break
            if no_held < 3 or not step.get("assume_held", True):
                time.sleep(0.5)
                fr2 = adb.screencap_fast()
                frame = frame if fr2 is None else fr2
                t_ready = time.time()
                continue
            lv_g = int(step.get("held_default", 1))
            held = (lv_g, W / 2, -held_top * W + r_for(lv_g, W), r_for(lv_g, W))
            log("warn", "🐷 Không đọc được con đang cầm (lần %d) - đoán cấp %d" % (no_held, lv_g))
        else:
            no_held = 0
        balls = rbook.snap(pigs, W) if radius_fix else [(lv, cx, cy, r) for lv, cx, cy, r, _ in pigs]
        if radius_fix:
            # con đang cầm CÙNG CẤP phải cùng bán kính với heo trên bàn (trước đây: danh nghĩa/+-3px vs Hough đo được)
            _nr = rbook.r(held[0], W)
            held = (held[0], held[1], held[2] + (_nr - held[3]), _nr)      # mép trên con cầm giữ nguyên -> tâm dời theo bán kính mới
        # so dự đoán lượt trước với ảnh thật (kiểm tra mô phỏng lăn đúng không) + thu mẫu hiệu chỉnh
        err_txt, err_val = "", None
        if pending is not None:
            b0, h0, x0, pr0 = pending
            err_val, miss = pred_error(pr0, balls, W)
            err_txt = " | dự đoán lượt trước: sai số %.3f x rộng khung, lệch %d heo" % (err_val, miss)
            samples.append((b0, h0, x0, balls, y0_last))
            samples = samples[-12:]
            if save_shots and not test:
                try:
                    os.makedirs(debug_dir, exist_ok=True)
                    _cmp_overlay(frame, box, pr0, pigs, x0, os.path.join(debug_dir, "pig_%04d_cmp.png" % turn),
                                 "sai so %.3f lech %d" % (err_val, miss))
                except Exception:
                    pass
        # tính nước đi NGAY (ảnh này đã là trạng thái cuối); trong lúc đó vẫn đang đợi held_wait
        if think_cfg is not None:
            think_s = float(think_cfg)
        else:
            think_s = max(float(step.get("think_min", 1.2)), held_wait - (time.time() - t_ready) - 0.1)
        y0_fix = tap_y * H if spawn_y == "click" else None
        x_drop, info = choose_drop(balls, (held[0], held[3]), W, H, sp, ep, think_s=think_s, n_x=n_x, log=log, held_top=held_top, y0_fixed=y0_fix,
                                   valleys=use_valleys, refine=use_refine)
        y0_held = y0_fix if y0_fix is not None else held[2]
        pred, _ = simulate(balls, W, H, (held[0], x_drop, held[3], y0_held), sp)
        turn += 1
        log("info", "🐷 Lượt %d: %d heo, cầm cấp %d -> thả x=%.0f%% (tính %.1fs)%s" %
            (turn, len(balls), held[0], 100.0 * x_drop / W, time.time() - t_turn, err_txt))

        def _write_log(x_act, pred_row, mode_txt):
            if not (save_shots or test):
                return
            try:
                with open(os.path.join(debug_dir, "pig_log.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps({"turn": turn, "W": W, "H": H, "held": held[0], "x": x_drop,
                                        "x_act": x_act, "drop_mode": mode_txt,
                                        "before": [[a, round(b, 1), round(c, 1), round(d, 1)] for a, b, c, d in balls],
                                        "pred": [[a, round(b, 1), round(c, 1), round(d, 1)] for a, b, c, d in pred_row],
                                        "pred_err": err_val, "info": info}, ensure_ascii=False) + "\n")
            except Exception:
                pass

        if save_shots or test:
            _overlay(frame, box, pigs, held, x_drop, os.path.join(debug_dir, "pig_%04d.png" % turn))
            if keep > 0:
                for pat in ("pig_[0-9][0-9][0-9][0-9].png", "pig_[0-9][0-9][0-9][0-9]_cmp.png"):
                    olds = sorted(glob.glob(os.path.join(debug_dir, pat)))
                    for p in olds[:-keep]:
                        try:
                            os.remove(p)
                        except Exception:
                            pass
        if test:
            _write_log(None, pred, "test")
            log("info", "🐷 TEST: không bấm. Ảnh kế hoạch: %s" % os.path.join(debug_dir, "pig_%04d.png" % turn))
            break
        # chỉ bấm khi đã đủ held_wait kể từ lúc con kế hiện (phòng lag); thời gian đó đã dùng để tính
        _sleep(held_wait - (time.time() - t_ready), should_stop)
        if should_stop():
            break
        # chụp LẠI ngay trước khi thả: khung dùng để tính được chụp lúc con cầm vừa hiện (còn đang phóng to / có thể đọc sai cấp)
        if not test:
            try:
                fr_chk = adb.screencap_fast()
                held2 = detect_held(fr_chk, box, held_top) if fr_chk is not None else None
            except Exception:
                held2 = None
            if held2 is not None and not step.get("held_level") and held2[0] != held[0]:
                log("warn", "🐷 Con cầm thật là cấp %d (lúc đầu đọc cấp %d) - tính lại nước đi" % (held2[0], held[0]))
                held = held2
                if radius_fix:
                    _nr = rbook.r(held[0], W)
                    held = (held[0], held[1], held[2] + (_nr - held[3]), _nr)
                y0_fix = tap_y * H if spawn_y == "click" else None
                x_drop, info = choose_drop(balls, (held[0], held[3]), W, H, sp, ep, think_s=1.2, n_x=n_x, log=log,
                                           held_top=held_top, y0_fixed=y0_fix)
                y0_held = y0_fix if y0_fix is not None else held[2]
                pred, _ = simulate(balls, W, H, (held[0], x_drop, held[3], y0_held), sp)
        sx = box[0] + x_drop
        x_act = x_drop
        if drop_mode == "swipe":
            hx, hy = box[0] + held[1], box[1] + held[2]
            adb.swipe_hold_px(hx, hy, sx, hy, move_duration_ms=250, hold_ms=80)
        elif drop_mode == "tap":
            adb.tap_px(sx, box[1] + tap_y * H)
        else:
            x_act = _drag_drop(adb, box, held, x_drop, step, should_stop, log)
            if abs(x_act - x_drop) > 0.02 * W:
                log("warn", "🐷 Nhả tay ở x=%.0f%% (định %.0f%%) - con cầm không theo kịp ngón tay; mô phỏng dùng x thật" %
                    (100.0 * x_act / W, 100.0 * x_drop / W))
        # mô phỏng lại với x THẬT lúc nhả (không phải x định) để so/hiệu chỉnh đúng
        pred_act = pred
        if abs(x_act - x_drop) > 1e-6:
            try:
                pred_act, _ = simulate(balls, W, H, (held[0], x_act, held[3], y0_held), sp)
            except Exception:
                pred_act = pred
        pending = (balls, (held[0], held[3]), x_act, pred_act)
        y0_last = y0_held
        _write_log(x_act, pred_act, drop_mode)
        # tận dụng lúc heo đang lăn (game chưa hiện con kế) để hiệu chỉnh tham số vật lý từ các mẫu thật
        if auto_calib and len(samples) >= 6 and turn % calib_every == 0 and not should_stop():
            try:
                sp2, e0, e1, nt = calibrate(samples, sp, W, H, budget_s=calib_s)
                if e1 < e0 * 0.97:
                    sp = sp2
                    _save_params(step, sp)
                log("info", "🐷 Hiệu chỉnh vật lý: sai số %.3f -> %.3f (%d lần thử) %s" %
                    (e0, e1, nt, ", ".join("%s=%.2f" % (k, getattr(sp, k)) for k in CAL_RANGE)))
            except Exception as e:
                log("warn", "🐷 Hiệu chỉnh vật lý lỗi: %s" % e)
        frame, ready, t_ready = _wait_ready(adb, box, step, should_stop)
        if not ready and not should_stop():
            log("warn", "🐷 Quá lâu không thấy con kế tiếp xuất hiện - vẫn tiếp tục với ảnh hiện tại")
        if frame is None:
            frame = adb.screencap_fast()
            if frame is None:
                log("error", "🐷 Mất ảnh màn hình, dừng")
                break
        if bool(step.get("wait_stable", True)) and not should_stop():
            # con kế vừa hiện chưa chắc heo đã yên (đang gộp/popup điểm/con cầm còn trượt) -> chờ yên hẳn rồi mới đọc
            _fs = _wait_stable(adb, _board_px(step, fw, fh), step, should_stop, frame, log)
            if _fs is not None:
                frame = _fs
        sig = _board_signature(frame, _board_px(step, fw, fh))
        if last_sig is not None and float(np.abs(sig - last_sig).mean()) < 0.6:
            same_cnt += 1
            if same_cnt >= 4:
                log("warn", "🐷 Màn hình không đổi sau 4 lần thả - có thể đã hết ván hoặc bấm không ăn, dừng")
                break
        else:
            same_cnt = 0
        last_sig = sig
        if min_st > 0:
            # mỗi lượt thả tốn 1 thể lực: tự trừ giữa 2 lần đọc; còn cách ngưỡng <= 12 thì đọc OCR MỖI lượt (trước đây 25 lượt/lần -> có thể tụt xa dưới ngưỡng)
            if st_est is not None:
                st_est -= 1
            near = st_est is not None and st_est <= min_st + 12
            if (near or (st_every > 0 and turn % st_every == 0) or st_est is None):
                st = _read_stamina(adb, frame, step)
                if st is not None:
                    st_est = st
            if st_est is not None and st_est < min_st:
                log("warn", "🐷 Thể lực %d < %d - dừng" % (st_est, min_st))
                break
    log("info", "🐷 Kết thúc sau %d lượt (%.0fs)" % (turn, time.time() - t_start))
    return True


# ----------------------------------------------------------------------------------------------
# CLI kiểm tra 1 ảnh
# ----------------------------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    im = cv2.imdecode(np.fromfile(sys.argv[1], dtype=np.uint8), cv2.IMREAD_COLOR)
    fh, fw = im.shape[:2]
    if len(sys.argv) >= 6:
        bx = tuple(int(v) for v in sys.argv[2:6])
    else:
        bx = _board_px({}, fw, fh)
    W, H = bx[2] - bx[0], bx[3] - bx[1]
    t0 = time.time()
    pigs = detect_pigs(im, bx)
    held = detect_held(im, bx)
    print("Nhận diện %d heo (%.2fs); cấp: %s; đang cầm: %s" % (len(pigs), time.time() - t0, sorted(p[0] for p in pigs), held and held[0]))
    xd = None
    if held and pymunk is not None:
        balls = [(lv, cx, cy, r) for lv, cx, cy, r, _ in pigs]
        xd, info = choose_drop(balls, (held[0], held[3]), W, H, SimParams(), EvalParams())
        print("Thả tại x=%.0f%% khung. %s" % (100 * xd / W, info))
    os.makedirs("debug_pig", exist_ok=True)
    _overlay(im, bx, pigs, held, xd, os.path.join("debug_pig", "test_cli.png"))
    print("Ảnh kiểm tra: debug_pig/test_cli.png")

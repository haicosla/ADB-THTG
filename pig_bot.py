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
import random

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
        self.damping = 0.63         # phần vận tốc còn lại sau 1 giây (hiệu chỉnh lại trên 681 lượt thật "sạch": 0.78 -> 0.63)
        self.friction = 1.05        # (cũ 0.81)
        self.elasticity = 0.083     # (cũ 0.097)
        self.rad_scale = 1.02       # bán kính va chạm = bán kính vòng viền * hệ số này (heo thật hơi to hơn vòng đo được)
        self.merge_eps = 0.0008     # cộng thêm vào (r1+r2) khi xét chạm, tính theo chiều rộng khung
        # --- mô hình gộp sát game thật hơn (đo từ log thật; đặt merge_cd=0, merge_keepv=1, merge_pos=0 để về hành vi cũ) ---
        self.merge_cd = 0.25        # giây: con vừa sinh ra do gộp CHƯA gộp tiếp ngay được -> game thật hay dừng chuỗi gộp sớm hơn mô phỏng cũ
        self.merge_keepv = 0.0      # phần vận tốc con mới thừa hưởng từ 2 con cũ (0 = đứng yên lúc sinh ra, 1 = bảo toàn động lượng như cũ)
        self.merge_hold = 1         # 1: cặp CÙNG CẤP đã nằm sát nhau trong ảnh thật thì CHƯA gộp (game thật đã không gộp chúng, mô phỏng phồng bán kính nên tưởng chạm -> gộp bậy, vd tự ra L10 ngay lượt đầu); chỉ gộp lại sau khi chúng tách ra rồi chạm lần nữa. 0 = tắt (cũ)
        self.hold_tol = 0.03        # cặp ban đầu có khoảng cách <= (r1+r2) x (1+hold_tol) bị giữ
        self.hold_gap = 0.01        # hết giữ khi 2 con cách nhau > (r1+r2) x (1+hold_gap)
        self.merge_pos = 2          # vị trí con mới: 0 = trung bình theo diện tích (cũ); 1 = trung điểm; 2 = trung điểm ngang, y của con nằm thấp hơn
        self.spin_damp = 0.0        # cản LĂN: tốc độ quay của heo giảm theo e^(-spin_damp*t) (0 = lăn tự do như Pymunk mặc định; lớn = lăn ngắn, dễ dừng)
        self.merge_push = 0.0       # con MỚI sinh ra do gộp (to hơn) đẩy văng heo hàng xóm đang bị nó đè lên: vận tốc thêm = merge_push x (độ chồng, px) hướng ra xa (1/giây; 0 = tắt)
        self.dt = 1.0 / 60.0
        self.max_t = 4.5
        for k, v in kw.items():
            setattr(self, k, v)


def _merge_pass(balls, eps, t=0.0, cd=0.0, keepv=1.0, pos=0, hold=None):
    """Gộp mọi cặp cùng cấp (<10) đang chạm. balls: list [lv,x,y,r,vx,vy(,born)]. Trả (balls mới, điểm gộp).
    cd: con sinh ra do gộp (born = giây lúc sinh) chưa được gộp tiếp trong cd giây; keepv/pos: xem SimParams.
    hold: tập {(uid nhỏ, uid lớn)} các cặp chưa được gộp (phần tử thứ 8 của bóng = uid)."""
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
                if cd > 0.0 and (t - (a[6] if len(a) > 6 else -99.0) < cd or t - (b[6] if len(b) > 6 else -99.0) < cd):
                    continue
                if hold and len(a) > 7 and len(b) > 7 and (min(a[7], b[7]), max(a[7], b[7])) in hold:
                    continue
                if math.hypot(a[1] - b[1], a[2] - b[2]) <= a[3] + b[3] + eps:
                    lv = a[0] + 1
                    wa, wb = a[3] ** 2, b[3] ** 2
                    s = wa + wb
                    if pos == 0:
                        nx, ny = (a[1] * wa + b[1] * wb) / s, (a[2] * wa + b[2] * wb) / s
                    elif pos == 1:
                        nx, ny = (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0
                    else:
                        nx, ny = (a[1] + b[1]) / 2.0, max(a[2], b[2])
                    nb = [lv, nx, ny, None,
                          keepv * (a[4] * wa + b[4] * wb) / s, keepv * (a[5] * wa + b[5] * wb) / s, t, -1]
                    nb[3] = a[3] * (R_NOM[lv - 1] / R_NOM[a[0] - 1])
                    balls = [x for t, x in enumerate(balls) if t not in (i, j)] + [nb]
                    gain += 2.0 ** lv
                    changed = True
                    break
            if changed:
                break
    return balls, gain


R_NOM = R_FRAC   # tỉ lệ bán kính các cấp (dùng để suy ra bán kính con mới)


def simulate(balls, W, H, drop=None, p=None, trace_out=None):
    """balls: [(lv,x,y,r)]; drop=(lv,x,r[,y_tâm]) thả từ trên (y_tâm = tâm con rơi lúc nhả tay, toạ độ khung, âm = phía trên khung;
    bỏ trống = -1.1*r). Trả (balls [(lv,x,y,r)], điểm gộp).
    trace_out (tuỳ chọn, dùng khi hiệu chỉnh offline bằng ảnh quay theo thời gian): dict {\"times\": [giây tăng dần]} -> hàm điền thêm
    trace_out[\"snaps\"] = [[(lv,x,y,r)...] tại từng mốc giây] (mô phỏng chạy ĐỦ tới mốc cuối, không dừng sớm khi heo đã yên)."""
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

    live = []   # [lv, body, r_ring, giây_sinh_ra, uid]
    uid_next = 0
    for lv, x, y, r in balls:
        live.append([lv, add(lv, x, y, r), r, -99.0, uid_next])
        uid_next += 1
    hold = set()
    if p.merge_hold:
        for i in range(len(live)):
            for j in range(i + 1, len(live)):
                a_, b_ = live[i], live[j]
                if a_[0] != b_[0] or a_[0] >= NLV:
                    continue
                if math.hypot(a_[1].position.x - b_[1].position.x, a_[1].position.y - b_[1].position.y) <= \
                        ((a_[2] + b_[2]) * p.rad_scale + p.merge_eps * W) * (1.0 + p.hold_tol):
                    hold.add((a_[4], b_[4]))
    if drop is not None:
        lv, x, r = drop[0], drop[1], drop[2]
        y0 = drop[3] if len(drop) > 3 and drop[3] is not None else -1.1 * r
        live.append([lv, add(lv, x, y0, r), r, -99.0, uid_next])
        uid_next += 1
    gain = 0.0
    eps = p.merge_eps * W
    t, calm = 0.0, 0.0
    step = 0
    push = float(getattr(p, "merge_push", 0.0))
    spin_k = math.exp(-float(getattr(p, "spin_damp", 0.0)) * p.dt * 2.0)      # cản quay mỗi 2 bước vật lý (xem SimParams.spin_damp)
    tr_times = list(trace_out.get("times") or []) if trace_out is not None else []
    tr_snaps, tr_i = [], 0
    t_end = max(p.max_t, (tr_times[-1] + 0.1) if tr_times else 0.0)
    while t < t_end:
        sp.step(p.dt)
        t += p.dt
        step += 1
        while tr_i < len(tr_times) and t >= tr_times[tr_i] - 1e-9:
            tr_snaps.append([(lv, b.position.x, b.position.y, r) for lv, b, r, born, uid in live])
            tr_i += 1
        if step % 2 == 0:
            if spin_k < 1.0:
                for _l in live:
                    _l[1].angular_velocity *= spin_k
            arr = [[lv, b.position.x, b.position.y, r * p.rad_scale, b.velocity.x, b.velocity.y, born, uid] for lv, b, r, born, uid in live]
            if hold:
                byu = {a[7]: a for a in arr}
                for key in list(hold):
                    a_, b_ = byu.get(key[0]), byu.get(key[1])
                    if a_ is None or b_ is None or math.hypot(a_[1] - b_[1], a_[2] - b_[2]) > (a_[3] + b_[3] + eps) * (1.0 + p.hold_gap):
                        hold.discard(key)   # đã tách ra (hoặc 1 con đã biến mất) -> lần chạm sau được gộp bình thường
            merged, g = _merge_pass([a[:] for a in arr], eps, t, p.merge_cd, p.merge_keepv, p.merge_pos, hold)
            if g > 0:
                gain += g
                if push > 0.0:
                    news = [nb for nb in merged if nb[7] < 0]
                    for nb in merged:
                        if nb[7] < 0:
                            continue
                        for nn in news:
                            ddx, ddy = nb[1] - nn[1], nb[2] - nn[2]
                            dd = math.hypot(ddx, ddy)
                            ov = nn[3] + nb[3] - dd
                            if ov > 0.0:
                                if dd < 1e-6:
                                    ddx, ddy, dd = 0.0, -1.0, 1.0
                                nb[4] += push * ov * ddx / dd
                                nb[5] += push * ov * ddy / dd
                for lv, b, r, born, uid in live:
                    sp.remove(b, *b.shapes)
                live = []
                for nb in merged:
                    ring_r = nb[3] / p.rad_scale
                    if nb[7] < 0:
                        nb[7] = uid_next
                        uid_next += 1
                    live.append([nb[0], add(nb[0], nb[1], nb[2], ring_r, nb[4], nb[5]), ring_r, nb[6], nb[7]])
                calm = 0.0
                continue
            vmax = max((abs(a[4]) + abs(a[5]) for a in arr), default=0.0)
            calm = calm + p.dt * 2 if vmax < 0.02 * W else 0.0
            if calm > 0.25 and t > 0.4 and tr_i >= len(tr_times):
                break
    if trace_out is not None:
        while len(tr_snaps) < len(tr_times):                       # mốc sau khi mô phỏng đã dừng: heo đứng yên ở trạng thái cuối
            tr_snaps.append([(lv, b.position.x, b.position.y, r) for lv, b, r, born, uid in live])
        trace_out["snaps"] = tr_snaps
    return [(lv, b.position.x, b.position.y, r) for lv, b, r, born, uid in live], gain


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
        self.w_corner = 0.0      # thưởng con TO NHẤT nằm sát góc (khe giữa nó và tường góc càng nhỏ càng tốt)
        self.w_inv = 0.0          # phạt "đảo thứ tự": con to hơn nằm XA góc hơn con nhỏ hơn (muốn dốc giảm dần từ góc ra), x chênh cấp
        self.w_buried = 0.0       # phạt heo nhỏ (cấp<=3) bị heo khác đè lên phía trên (thả từ trên xuống không còn tới được), x 2^cấp
        self.w_dup = 0.0          # phạt thừa heo cùng cấp không chạm nhau (>2 con) - chiếm chỗ, x 2^cấp
        self.corner_side = "auto"  # "left" / "right" / "auto" (auto = phía tường gần con to nhất)
        self.danger_line = 0.10   # mép trên heo cao hơn (tỉ lệ H) mà thấp hơn mức này thì phạt nặng
        for k, v in kw.items():
            setattr(self, k, v)


def evaluate(balls, gain, W, H, ep):
    sc = ep.w_gain * gain
    if not balls:
        return sc
    top = min(y - r for _, _, y, r in balls)
    height = max(0.0, (H - top) / H)
    sc -= ep.w_height * height ** 3
    if top < ep.danger_line * H:
        sc -= 1e5 * (ep.danger_line * H - top) / H + 5e3
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


def choose_drop(balls, held, W, H, sp, ep, think_s=2.5, n_x=25, next_levels=(1, 2, 3, 4), topk=6, log=None, held_top=None, y0_fixed=None):
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
    best = res1[0]
    final = []
    for s1, x, nb, g in res1[:topk]:
        tot, cnt = 0.0, 0
        for nl in next_levels:
            r2 = r_for(nl, W)
            bests = None
            for x2 in cand_x(nl, r2, 9):
                nb2, g2 = simulate(nb, W, H, (nl, x2, r2, y0_for(r2)), sp)
                e2 = evaluate(nb2, g2, W, H, ep)
                if bests is None or e2 > bests:
                    bests = e2
            tot += bests
            cnt += 1
            if time.time() - t0 > think_s:
                break
        base = 0.4 * s1 + 0.6 * (tot / max(1, cnt)) if cnt else s1
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
             "elasticity": (0.0, 0.8), "rad_scale": (0.90, 1.08),
             "merge_eps": (-0.015, 0.04), "spin_damp": (0.0, 10.0),
             "merge_cd": (0.0, 1.0), "merge_keepv": (0.0, 1.0), "merge_push": (0.0, 40.0)}
# tham số có thể bằng 0/âm -> bước thử CỘNG (không nhân): giá trị = cỡ bước lớn nhất (cùng đơn vị tham số)
CAL_ADD = {"merge_eps": 0.006, "spin_damp": 1.2, "merge_cd": 0.12, "merge_keepv": 0.15, "merge_push": 3.0}
# nhóm tham số theo hiện tượng cần chỉnh (dùng cho pig_calib.py --aspect): lăn / nảy / gộp cấp
CAL_ASPECTS = {
    "roll": ("friction", "damping", "spin_damp"),
    "bounce": ("elasticity", "gravity", "damping"),
    "merge": ("merge_eps", "rad_scale", "merge_cd", "merge_keepv", "merge_push"),
    "all": tuple(CAL_RANGE),
}


def pred_error(pred, obs, W, cap=0.25):
    """Sai số dự đoán vs ảnh thật (theo chiều rộng khung): ghép TỐI ƯU từng con theo cấp (assign_balls); con không khớp bị phạt `cap`.
    Trả (sai số TB, số con lệch)."""
    pairs, extra = assign_balls(pred, obs, W, cap)
    tot = sum(min(cap, d / W) for _, d in pairs.values())
    unmatched = (len(pred) - len(pairs)) + extra
    tot += cap * unmatched
    return tot / max(1, max(len(pred), len(obs))), unmatched


def calibrate(samples, sp, W, H, budget_s=2.0, seed=None, keys=None):
    """Leo đồi ngẫu nhiên trên các tham số vật lý để mô phỏng khớp ảnh thật hơn.
    samples: [(before, (cấp,bán kính), x_thả, after_thật)]. Trả (SimParams mới, sai số trước, sau, số lần thử).
    keys: chỉ chỉnh các tham số này (mặc định: online chỉ 5 tham số gốc; xem CAL_ASPECTS để chọn nhóm lăn/nảy/gộp)."""
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
    # online mặc định CHỈ chỉnh 5 tham số gốc (merge_eps/spin_damp cần nhiều mẫu hơn -> chỉnh offline bằng pig_calib.py)
    keys = list(keys) if keys else [k for k in CAL_RANGE if k not in CAL_ADD]
    while time.time() - t0 < budget_s:
        cand = copy.copy(best)
        for k in rnd.sample(keys, min(len(keys), rnd.choice((1, 2)))):
            lo, hi = CAL_RANGE[k]
            if k in CAL_ADD:
                v = getattr(cand, k) + rnd.uniform(-1.0, 1.0) * CAL_ADD[k] * (stepf / 0.3)
            else:
                v = getattr(cand, k) * (1.0 + rnd.uniform(-stepf, stepf))
            setattr(cand, k, min(hi, max(lo, v)))
        e = total(cand)
        n += 1
        if e < eb:
            best, eb = cand, e
        if n % 15 == 0:
            stepf = max(0.06, stepf * 0.8)
    return best, e0, eb, n


# ----------------------------------------------------------------------------------------------
# SO SÁNH DỰ ĐOÁN vs THẬT TỪNG LƯỢT (dùng chung: bot, pig_report.py, pig_calib.py)
# ----------------------------------------------------------------------------------------------
PIG_BOT_VERSION = "2026-10-10-session"
# Lệch khối lượng heo (thật so với trước + con thả) <= READ_TOL thì KHÔNG coi là lỗi đọc: bàn đông (~25 con) hay có 1-2 con nhỏ bị che/sát mép nên đọc thiếu,
# trong khi heo lớn đọc đúng. 8 = cỡ vài con cấp 1-3. pig_calib.py --read-tol N để đổi (N lớn = không bao giờ loại lượt vì đọc).
READ_TOL = 8


def level_mass(lv):
    """Khối lượng quy đổi của heo cấp lv: 2^(lv-1). BẤT BIẾN khi gộp (2 con cấp k = 1 con cấp k+1) -> dùng để biết ảnh đọc có đủ/đúng heo không."""
    return 2 ** (int(lv) - 1)


def _hungarian(cost):
    """Bài toán gán tối ưu (Kuhn-Munkres O(n^3)) cho ma trận vuông cost[i][j]; trả list cột được gán cho từng hàng."""
    n = len(cost)
    INF = float("inf")
    u, v, p, way = [0.0] * (n + 1), [0.0] * (n + 1), [0] * (n + 1), [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    res = [0] * n
    for j in range(1, n + 1):
        res[p[j] - 1] = j - 1
    return res


def assign_balls(pred, obs, W, cap=0.25):
    """Ghép heo dự đoán với heo thật CÙNG CẤP sao cho TỔNG khoảng cách nhỏ nhất (tối ưu theo từng cấp - không ghép tham lam: khi có nhiều con
    cùng cấp, vd mấy con cấp 1, ghép tham lam hay ghép nhầm con rồi báo lệch hàng trăm px). Trả ({chỉ_số_pred: (chỉ_số_obs, khoảng_cách_px)}, số thật không khớp)."""
    by_p, by_o = {}, {}
    for i, b in enumerate(pred):
        by_p.setdefault(b[0], []).append(i)
    for j, b in enumerate(obs):
        by_o.setdefault(b[0], []).append(j)
    pairs, used_o = {}, 0
    for lv, pi in by_p.items():
        oj = by_o.get(lv, [])
        if not oj:
            continue
        n = max(len(pi), len(oj))
        cost = [[cap] * n for _ in range(n)]                       # ô thừa (con không có đối tác) = phạt cap
        for a_, i in enumerate(pi):
            for b_, j in enumerate(oj):
                cost[a_][b_] = min(cap, math.hypot(obs[j][1] - pred[i][1], obs[j][2] - pred[i][2]) / W)
        col = _hungarian(cost)
        for a_, i in enumerate(pi):
            b_ = col[a_]
            if b_ < len(oj):
                j = oj[b_]
                pairs[i] = (j, math.hypot(obs[j][1] - pred[i][1], obs[j][2] - pred[i][2]))
                used_o += 1
    return pairs, len(obs) - used_o


def match_balls(pred, obs, W=None):
    """Ghép từng heo dự đoán với heo thật cùng cấp (tối ưu theo cấp, xem assign_balls). Trả ([(cấp, dx, dy, d)] theo thứ tự cấp lớn trước - dx/dy/d = None nếu không khớp, số heo thật thừa)."""
    W = W or 692.0
    pairs, extra = assign_balls(pred, obs, W)
    out = []
    for i in sorted(range(len(pred)), key=lambda k: -pred[k][0]):
        if i in pairs:
            j, d = pairs[i]
            out.append((pred[i][0], obs[j][1] - pred[i][1], obs[j][2] - pred[i][2], d))
        else:
            out.append((pred[i][0], None, None, None))
    return out, extra


def compare_turn(before, held_lv, x_drop, pred, obs, W):
    """So 1 lượt: dự đoán `pred` (sau khi thả con cấp held_lv tại x_drop vào bàn `before`) với ảnh thật `obs` (heo nằm yên). Các list [(cấp,x,y,r,...)].
    Trả dict:  kind = 'tốt' | 'LĂN' | 'GỘP' | 'ĐỌC'
      ĐỌC = tổng khối lượng heo thật != trước + con thả -> ảnh đọc thiếu/thừa/nhầm cấp heo (lỗi nhận diện hoặc đọc khi heo còn động), KHÔNG dùng để chỉnh vật lý;
      GỘP = đủ khối lượng nhưng tập cấp heo khác dự đoán -> mô phỏng gộp sai (merge_diff > 0: mô phỏng gộp ÍT hơn thật; < 0: gộp NHIỀU hơn thật);
      LĂN = cùng tập cấp nhưng vị trí lệch (>4% sai số TB hoặc có con lệch > 6% rộng khung) -> chỉnh lăn/nảy/ma sát;
      tốt = khớp.
    drop = thông tin con vừa thả (nếu còn nguyên, không bị gộp mất): roll_pred/roll_obs = quãng lăn ngang so với x thả (px, dương = sang phải)."""
    err, miss = pred_error(pred, obs, W)
    pairs, extra = match_balls(pred, obs, W)
    unmatched = sum(1 for q in pairs if q[3] is None) + extra
    worst = max((q for q in pairs if q[3] is not None), key=lambda q: q[3], default=None)
    mass_b = sum(level_mass(b[0]) for b in before)
    mass_h = level_mass(held_lv)
    mass_o = sum(level_mass(b[0]) for b in obs)
    lv_pred = sorted(b[0] for b in pred)
    lv_obs = sorted(b[0] for b in obs)
    mass_diff = mass_o - (mass_b + mass_h)
    mass_ok = None
    # cấp nào thật THIẾU / THỪA so với dự đoán (đa tập hợp) - để biết ảnh đọc sót/thừa con nào
    cp, co = {}, {}
    for v in lv_pred:
        cp[v] = cp.get(v, 0) + 1
    for v in lv_obs:
        co[v] = co.get(v, 0) + 1
    obs_missing = sorted(v for v in cp for _ in range(max(0, cp[v] - co.get(v, 0))))
    obs_extra = sorted(v for v in co for _ in range(max(0, co[v] - cp.get(v, 0))))
    # lệch khối lượng chỉ được bỏ qua khi nhỏ (<= READ_TOL) VÀ chỉ do heo NHỎ (cấp <= 3) thiếu/thừa; thiếu/thừa/nhầm heo to = lỗi nhận diện thật
    mass_ok = (mass_diff == 0) or (abs(mass_diff) <= READ_TOL and all(v <= 3 for v in obs_missing + obs_extra))
    if mass_diff == 0:
        lv_same = (lv_pred == lv_obs)
    else:                                           # lệch nhỏ (đọc sót/thừa heo nhỏ): chỉ xét heo cấp >= 4 để phân biệt GỘP thật
        lv_same = ([v for v in lv_pred if v >= 4] == [v for v in lv_obs if v >= 4])
    if not mass_ok:
        kind = "ĐỌC"
    elif not lv_same:
        kind = "GỘP"
    elif err < 0.04 and (worst is None or worst[3] < 0.06 * W):
        kind = "tốt"
    else:
        kind = "LĂN"
    # con vừa thả: heo cấp held_lv trong dự đoán KHÔNG trùng heo cũ cùng cấp ở `before` (nếu nhiều: lấy con gần x thả nhất)
    drop = None
    old = [b for b in before if b[0] == held_lv]
    cands = [b for b in pred if b[0] == held_lv and not any(math.hypot(b[1] - o[1], b[2] - o[2]) < 0.015 * W for o in old)]
    if cands:
        c = min(cands, key=lambda b: abs(b[1] - x_drop))
        om = [o for o in obs if o[0] == held_lv]
        o = min(om, key=lambda t: math.hypot(t[1] - c[1], t[2] - c[2])) if om else None
        drop = {"lv": held_lv, "x_drop": round(x_drop, 1), "x_pred": round(c[1], 1), "y_pred": round(c[2], 1),
                "x_obs": None if o is None else round(o[1], 1), "y_obs": None if o is None else round(o[2], 1),
                "roll_pred": round(c[1] - x_drop, 1), "roll_obs": None if o is None else round(o[1] - x_drop, 1),
                "d": None if o is None else round(math.hypot(o[1] - c[1], o[2] - c[2]), 1)}
    return {"kind": kind, "err": round(err, 4), "miss": miss, "unmatched": unmatched,
            "n_before": len(before), "n_pred": len(pred), "n_obs": len(obs),
            "mass_before": mass_b, "mass_held": mass_h, "mass_obs": mass_o, "mass_ok": mass_ok,
            "mass_diff": mass_diff, "obs_missing": obs_missing, "obs_extra": obs_extra,
            "lv_pred": lv_pred, "lv_obs": lv_obs,
            "merge_pred": len(before) + 1 - len(pred), "merge_obs": len(before) + 1 - len(obs),
            "merge_diff": len(obs) - len(pred),
            "worst": None if worst is None else {"lv": worst[0], "dx": round(worst[1], 1), "dy": round(worst[2], 1), "d": round(worst[3], 1)},
            "drop": drop}


def summarize_cmp(rows):
    """rows = các dict compare_turn (đã thêm 'turn'). Trả list dòng chữ tóm tắt: số lượt theo loại, sai số TB, thiên lệch lăn, thống kê gộp."""
    if not rows:
        return ["(chưa có lượt nào được so sánh)"]
    n = len(rows)
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    clean = [r for r in rows if r["kind"] != "ĐỌC"]
    out = ["%d lượt so sánh: %s" % (n, ", ".join("%d %s" % (kinds.get(k, 0), k) for k in ("tốt", "LĂN", "GỘP", "ĐỌC")))]
    if clean:
        errs = sorted(r["err"] for r in clean)
        out.append("Sai số vị trí (bỏ lượt ĐỌC): TB %.4f, trung vị %.4f, xấu nhất %.4f (x rộng khung)" % (sum(errs) / len(errs), errs[len(errs) // 2], errs[-1]))
    reads = [r for r in rows if r["kind"] == "ĐỌC"]
    if reads:
        miss, extra = {}, {}
        for r in reads:
            for v in r.get("obs_missing", []):
                miss[v] = miss.get(v, 0) + 1
            for v in r.get("obs_extra", []):
                extra[v] = extra.get(v, 0) + 1
        out.append("Lượt ĐỌC (lệch khối lượng > %d): ảnh thật THIẾU so với dự đoán %s; THỪA %s (cấp x số lần) - thiếu cấp nhỏ = heo bị che/sát mép, thừa/thiếu cấp to = nhận diện sai" % (
            READ_TOL, ", ".join("L%d x%d" % kv for kv in sorted(miss.items())) or "-", ", ".join("L%d x%d" % kv for kv in sorted(extra.items())) or "-"))
    mrows = [r for r in rows if r["mass_ok"]]
    if mrows:
        mp = sum(1 for r in mrows if r["kind"] != "GỘP")
        out.append("Gộp cấp: tập cấp dự đoán khớp thật %d/%d lượt (%.0f%%); mô phỏng gộp ÍT hơn thật %d lượt, NHIỀU hơn thật %d lượt" % (
            mp, len(mrows), 100.0 * mp / len(mrows),
            sum(1 for r in mrows if r["merge_diff"] > 0), sum(1 for r in mrows if r["merge_diff"] < 0)))
    rolls = [r["drop"] for r in clean if r.get("drop") and r["drop"].get("roll_obs") is not None and abs(r["drop"]["roll_pred"]) > 8]
    if rolls:
        # chiều dương = cùng hướng lăn dự đoán: >0 thật lăn XA hơn dự đoán (mô phỏng quá nhám/cản), <0 thật lăn NGẮN hơn (mô phỏng quá trơn)
        bias = [(d["roll_obs"] - d["roll_pred"]) * (1 if d["roll_pred"] > 0 else -1) for d in rolls]
        ratio = [d["roll_obs"] / d["roll_pred"] for d in rolls if abs(d["roll_pred"]) > 8]
        out.append("Lăn: %d lượt có lăn; thật - dự đoán (cùng hướng lăn) TB %+.1fpx; thật/dự đoán TB %.2f (>1 = thật lăn xa hơn)" % (
            len(rolls), sum(bias) / len(bias), sum(ratio) / len(ratio)))
    dys = [r["drop"]["y_obs"] - r["drop"]["y_pred"] for r in clean if r.get("drop") and r["drop"].get("y_obs") is not None]
    if dys:
        out.append("Độ cao nơi con vừa thả nằm yên: thật - dự đoán TB %+.1fpx (dương = thật nằm THẤP hơn; lệch lớn = chồng/nảy/rung khác nhau)" % (sum(dys) / len(dys)))
    return out


def format_cmp_table(rows):
    """Bảng từng lượt (text) từ các dict compare_turn: lượt, cấp cầm, x thả %, sai số, loại, chi tiết (con lệch nhiều nhất / gộp / lăn)."""
    out = ["%-4s %-4s %-5s %-7s %-5s  %s" % ("lượt", "cầm", "x%", "sai số", "loại", "chi tiết")]
    for r in rows:
        W = r.get("W") or 1
        det = []
        w = r.get("worst")
        if w:
            det.append("lệch nhất L%d %.0fpx (dx=%+.0f dy=%+.0f)" % (w["lv"], w["d"], w["dx"], w["dy"]))
        d = r.get("drop")
        if d and d.get("roll_obs") is not None:
            det.append("lăn dự đoán %+.0f / thật %+.0f px" % (d["roll_pred"], d["roll_obs"]))
        if r["kind"] == "GỘP":
            det.append("cấp dự đoán %s | thật %s" % (",".join(map(str, r["lv_pred"])), ",".join(map(str, r["lv_obs"]))))
        if r["kind"] == "ĐỌC":
            det.append("khối lượng thật %d != %d+%d (lệch %+d); thật thiếu %s thừa %s" % (
                r["mass_obs"], r["mass_before"], r["mass_held"], r.get("mass_diff", 0),
                ",".join("L%d" % v for v in r.get("obs_missing", [])) or "-", ",".join("L%d" % v for v in r.get("obs_extra", [])) or "-"))
        elif r.get("mass_diff"):
            det.append("(đọc lệch %+d: thật thiếu %s thừa %s - đã bỏ qua)" % (
                r["mass_diff"], ",".join("L%d" % v for v in r.get("obs_missing", [])) or "-", ",".join("L%d" % v for v in r.get("obs_extra", [])) or "-"))
        out.append("%-4d L%-3d %-5.0f %-7.3f %-5s  %s%s" % (r.get("turn", 0), r.get("held", 0), 100.0 * r.get("x_drop", 0) / W, r["err"], r["kind"],
                                                         " ".join("| " + t for t in det), "  [thả ngẫu nhiên]" if r.get("explore") else ""))
    return out


# ----------------------------------------------------------------------------------------------
# PHIÊN CHẠY: mỗi lần chạy 1 thư mục riêng (log, tham số, ảnh từng bước, ảnh so sánh)
# ----------------------------------------------------------------------------------------------
def _json_safe(o):
    try:
        return json.loads(json.dumps(o, ensure_ascii=False, default=str))
    except Exception:
        return {}


def _save_img(im, path):
    """Ghi ảnh theo đuôi file (png/jpg), chịu được đường dẫn tiếng Việt; không bao giờ ném lỗi."""
    try:
        ext = os.path.splitext(path)[1].lower() or ".png"
        if ext in (".jpg", ".jpeg"):
            ok, buf = cv2.imencode(".jpg", im, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        else:
            ok, buf = cv2.imencode(".png", im)
        if ok:
            buf.tofile(path)
        return bool(ok)
    except Exception:
        return False


class PigSession:
    """Thư mục của 1 phiên chạy:  <debug_dir>/sessions/<YYYYMMDD_HHMMSS>_<play|test|calib>/
        session.json          cấu hình bước, khung bàn, tham số bắt đầu/kết thúc, kết quả tóm tắt
        pig_log.jsonl         mỗi lượt 1 dòng: heo trước khi thả, con cầm, x thả, DỰ ĐOÁN (pred), tham số vật lý đang dùng...
        pig_cmp.jsonl         mỗi lượt 1 dòng: dự đoán vs ảnh THẬT sau khi heo yên (loại tốt/LĂN/GỘP/ĐỌC, sai số, quãng lăn, gộp...)
        pig_params_start.json / pig_params_end.json / calib_history.jsonl   tham số vật lý lúc đầu / cuối / từng lần tự hiệu chỉnh
        img/pig_NNNN.png      ảnh kế hoạch lượt N (vòng xanh = heo đọc được, vòng xanh dương = con cầm, vạch cam = x thả)
        img/pig_NNNN_cmp.png  ảnh THẬT sau lượt N: vòng XANH LÁ = thật, vòng TÍM = dự đoán, đường đỏ nối con khớp (kèm số px lệch)
        raw/ , trace/         (chế độ calib_run) ảnh gốc trước khi thả + ảnh quay theo thời gian lúc heo rơi/lăn (trace.jsonl)
        report.txt            tóm tắt tự sinh khi phiên kết thúc
    `debug_dir/pig_params.json` vẫn là tham số vật lý ĐANG DÙNG (mang sang phiên sau); `debug_dir/last_session.txt` trỏ tới phiên mới nhất.
    session_dir=false trong bước -> bố cục phẳng như bản cũ (mọi file nằm thẳng trong debug_dir)."""

    def __init__(self, step, calib_run=False):
        self.root = step.get("debug_dir", "debug_pig")
        self.flat = not bool(step.get("session_dir", True))
        tag = "calib" if calib_run else ("test" if step.get("test") else "play")
        self.id = time.strftime("%Y%m%d_%H%M%S") + "_" + tag
        self.created = False
        if self.flat:
            self.dir = self.img_dir = self.raw_dir = self.trace_dir = self.root
        else:
            base = os.path.join(self.root, "sessions", self.id)
            d, k = base, 1
            while os.path.exists(d):
                k += 1
                d = "%s_%d" % (base, k)
            self.dir = d
            self.id = os.path.basename(d)
            self.img_dir = os.path.join(d, "img")
            self.raw_dir = os.path.join(d, "raw")
            self.trace_dir = os.path.join(d, "trace")
        self.keep_sessions = int(step.get("sessions_keep", 15))

    def make(self, *subdirs):
        try:
            for d in (self.dir,) + tuple(subdirs):
                os.makedirs(d, exist_ok=True)
            if not self.created:
                self.created = True
                if not self.flat:
                    with open(os.path.join(self.root, "last_session.txt"), "w", encoding="utf-8") as f:
                        f.write(os.path.abspath(self.dir))
                    self._prune_sessions()
        except Exception:
            pass

    def path(self, name):
        return os.path.join(self.dir, name)

    def img(self, name):
        return os.path.join(self.img_dir, name)

    def write_json(self, name, obj):
        try:
            self.make()
            with open(self.path(name), "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
        except Exception:
            pass

    def append_jsonl(self, name, obj):
        try:
            self.make()
            with open(self.path(name), "a", encoding="utf-8") as f:
                f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

    def _prune_sessions(self):
        """Xoá các phiên CŨ nhất khi vượt sessions_keep (mặc định 15; 0 = giữ hết). Phiên có file KEEP bên trong không bị xoá."""
        if self.keep_sessions <= 0:
            return
        try:
            import shutil
            base = os.path.join(self.root, "sessions")
            dirs = sorted(d for d in os.listdir(base) if re.match(r"^\d{8}_\d{6}", d) and os.path.isdir(os.path.join(base, d)))
            cur = os.path.basename(self.dir)
            olds = [d for d in dirs if d != cur and not os.path.exists(os.path.join(base, d, "KEEP"))]
            for d in olds[:max(0, len(dirs) - self.keep_sessions)]:
                shutil.rmtree(os.path.join(base, d), ignore_errors=True)
        except Exception:
            pass

    def prune_images(self, keep):
        """Giữ `keep` ảnh kế hoạch + `keep` ảnh cmp mới nhất trong thư mục ảnh (keep <= 0: giữ hết)."""
        if keep <= 0:
            return
        for pat in ("pig_[0-9][0-9][0-9][0-9].*", "pig_[0-9][0-9][0-9][0-9]_cmp.*"):
            olds = sorted(glob.glob(os.path.join(self.img_dir, pat)))
            for p in olds[:-keep]:
                try:
                    os.remove(p)
                except Exception:
                    pass


def sim_dict(sp):
    return {k: round(float(getattr(sp, k, 0.0)), 5) for k in CAL_RANGE}


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
    for k in ("gravity", "damping", "friction", "elasticity", "rad_scale", "merge_eps", "merge_cd", "merge_keepv", "merge_pos", "merge_hold", "spin_damp", "merge_push"):
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
    _save_img(im, path)


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
    for k_, txt_ in enumerate(("xanh=THAT  tim=DU DOAN  cam=x tha", err_txt)):
        cv2.putText(im, txt_, (x1 + 6, y1 + 26 + 28 * k_), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
        cv2.putText(im, txt_, (x1 + 6, y1 + 26 + 28 * k_), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    _save_img(im, path)


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


def _wait_ready(adb, box, step, should_stop, on_frame=None, settle=None):
    """Sau khi thả: heo lăn/nảy thì game KHÔNG hiện con kế; con kế hiện ra trên đầu nhân vật = heo đã lăn xong.
    Chờ con cũ biến mất (tối đa gone_max) -> chờ con kế hiện (tối đa ready_max). Trả (frame ngay lúc con kế hiện, ready, t_ready).
    Khung hình này ĐÃ là trạng thái cuối nên tính luôn; chỉ việc bấm thì mới đợi đủ held_wait (xem vòng lặp chính).
    on_frame(frame, t_bắt_đầu_chụp, t_xong_chụp) (tuỳ chọn): gọi cho MỌI khung chụp được (ảnh quay heo rơi/lăn để hiệu chỉnh nảy/lăn); settle = nghỉ đầu (None = settle_min)."""
    hu = float(step.get("held_top", HELD_TOP))
    gone_max = float(step.get("gone_max", 2.5))
    ready_max = float(step.get("ready_max", 25.0))
    _sleep(float(step.get("settle_min", 0.25)) if settle is None else float(settle), should_stop)
    t0 = time.time()
    seen_gone, frame = False, None
    while time.time() - t0 < gone_max + ready_max and not should_stop():
        _tc0 = time.time()
        fr = adb.screencap_fast()
        _tc1 = time.time()
        if fr is None:
            time.sleep(0.2)
            continue
        frame = fr
        if on_frame is not None:
            try:
                on_frame(fr, _tc0, _tc1)
            except Exception:
                pass
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


def _run_auto_pig_impl(adb, step: dict, should_stop=None, log=None, ctx=None) -> bool:
    """
    (Gọi qua run_auto_pig_step - hàm đó lo kết thúc phiên: ghi tham số cuối + report.txt dù thoát bằng đường nào.)
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
      w_*                    - trọng số hàm đánh giá (xem EvalParams)
      save_shots (true) / debug_dir ('debug_pig') / shots_keep (40; 0 = giữ hết) - ảnh kiểm tra mỗi lượt + nhật ký pig_log.jsonl
      session_dir (true)     - MỖI lần chạy 1 thư mục riêng debug_dir/sessions/<ngày_giờ>_<play|test|calib>/ (log, tham số, ảnh từng bước, ảnh cmp...; xem PigSession);
                               false = bố cục phẳng như bản cũ. sessions_keep (15) = giữ tối đa N phiên gần nhất (0 = giữ hết; có file KEEP trong phiên thì không xoá)
      shot_ext ('png')       - 'jpg' để ảnh nhẹ hơn (ảnh kế hoạch + cmp)
      calib_run (false)      - CHẾ ĐỘ TEST HIỆU CHỈNH: CHƠI THẬT (có bấm) để đối chiếu dự đoán với thực tế. Mặc định bật: max_turns 40, giữ HẾT ảnh, lưu ảnh gốc (raw/),
                               quay ảnh lúc heo rơi/lăn (trace/), thả ngẫu nhiên một phần lượt (explore 0.25) để đủ tình huống lăn/nảy/gộp, TẮT auto_calib (đo ĐÚNG bộ
                               tham số đang dùng; muốn bật thì auto_calib: true). Xong chạy:  python pig_calib.py  (đọc phiên mới nhất, in báo cáo + tìm tham số khớp hơn)
      save_raw (calib_run) / trace (calib_run) / trace_max (40) / explore (0.25 khi calib_run, còn lại 0) / seed - tuỳ chỉnh riêng từng thứ ở trên
    """
    should_stop = should_stop or (lambda: False)
    log = log or (lambda level, msg: print("[%s] %s" % (level, msg)))
    if pymunk is None:
        log("error", "🐷 Auto Lợn Giống: chưa cài Pymunk - chạy:  pip install pymunk")
        return False
    ctx = ctx if ctx is not None else {}
    test = bool(step.get("test", False))
    calib_run = bool(step.get("calib_run", False))
    if calib_run and test:
        log("warn", "🐷 calib_run cần CHƠI THẬT để đối chiếu với thực tế - bỏ qua test=true")
        test = False
    max_turns = int(step.get("max_turns", 0))
    if calib_run and not max_turns:
        max_turns = 40
    max_sec = float(step.get("max_seconds", 0))
    min_st = int(step.get("min_stamina", 10))
    st_every = int(step.get("stamina_every", 5))
    drop_mode = step.get("drop_mode", "tap")
    tap_y = float(step.get("tap_y", 0.08))
    spawn_y = str(step.get("spawn_y", "held"))
    think_cfg = step.get("think_s")             # None = tự tính để xong trong lúc đợi held_wait
    held_wait = float(step.get("held_wait", 2.0))
    held_top = float(step.get("held_top", HELD_TOP))
    auto_calib = bool(step.get("auto_calib", not calib_run))      # calib_run: giữ cố định tham số để ĐO; hiệu chỉnh làm offline bằng pig_calib.py
    calib_every = int(step.get("calib_every", 6))
    calib_s = float(step.get("calib_s", 2.0))
    n_x = int(step.get("n_x", 25))
    debug_dir = step.get("debug_dir", "debug_pig")
    save_shots = bool(step.get("save_shots", True))
    keep = int(step.get("shots_keep", 0 if calib_run else 40))
    shot_ext = "." + str(step.get("shot_ext", "png")).lstrip(".").lower()
    save_raw = bool(step.get("save_raw", calib_run))
    trace_on = bool(step.get("trace", calib_run)) and not test
    trace_max = int(step.get("trace_max", 40))
    explore = float(step.get("explore", 0.25 if calib_run else 0.0))
    rnd = random.Random(step.get("seed"))
    sess = PigSession(step, calib_run)
    ctx.update({"sess": sess, "turn": 0, "cmp_rows": [], "reason": "", "started": time.time(), "mode": ("calib" if calib_run else ("test" if test else "play"))})
    sp = _load_params(step, log)
    ctx["sp"] = sp
    radius_fix = bool(step.get("radius_fix", True))      # đồng nhất bán kính từng cấp (heo bàn + con cầm); false = như cũ
    rbook = RadiusBook()
    ep = EvalParams(**{k: v for k, v in step.items() if k.startswith("w_") or k == "danger_line"})
    if save_shots or test or calib_run:
        sess.make(sess.img_dir)
        if save_raw:
            sess.make(sess.raw_dir)
        if trace_on:
            sess.make(sess.trace_dir)
        sess.write_json("pig_params_start.json", {"params": sim_dict(sp), "file_exists": os.path.exists(_params_path(step))})
    t_start = time.time()

    frame = adb.screencap_fast()
    if frame is None:
        log("error", "🐷 Auto Lợn Giống: không chụp được màn hình")
        return False
    fh, fw = frame.shape[:2]
    log("info", "🐷 Khung bàn %s: %s (ảnh %dx%d), cách thả: %s" % (
        "TỰ CHỌN" if step.get("board_custom") else "CỐ ĐỊNH", _board_px(step, fw, fh), fw, fh, drop_mode))
    if save_shots or test or calib_run:
        try:
            import platform
            sess.write_json("session.json", {
                "id": sess.id, "mode": ctx["mode"], "started": time.strftime("%Y-%m-%d %H:%M:%S"), "version": PIG_BOT_VERSION,
                "frame": [fw, fh], "box": list(_board_px(step, fw, fh)), "drop_mode": drop_mode, "tap_y": tap_y, "spawn_y": spawn_y,
                "sp_start": sim_dict(sp), "ep": _json_safe(getattr(ep, "__dict__", {})), "step": _json_safe(step),
                "options": {"calib_run": calib_run, "auto_calib": auto_calib, "save_raw": save_raw, "trace": trace_on, "explore": explore, "shot_ext": shot_ext},
                "pymunk": getattr(pymunk, "version", "?"), "python": platform.python_version(), "ended": None})
        except Exception:
            pass
        log("info", "🐷 Phiên %s (%s): %s" % (sess.id, ctx["mode"], os.path.abspath(sess.dir)))
    st = _read_stamina(adb, frame, step) if min_st > 0 else None
    st_est = st
    if st is not None:
        log("info", "🐷 Thể lực hiện tại: %d (dừng khi < %d)" % (st, min_st))
        if st < min_st:
            log("warn", "🐷 Thể lực %d < %d - không chơi" % (st, min_st))
            ctx["reason"] = "thể lực thấp ngay từ đầu"
            return False

    if not test and bool(step.get("wait_stable", True)):
        _fs = _wait_stable(adb, _board_px(step, fw, fh), step, should_stop, frame, log)
        if _fs is not None:
            frame = _fs
    turn, no_held, same_cnt, last_sig, err_cnt = 0, 0, 0, None, 0
    y0_last = None
    pending = None          # (before, held(lv,r), x, pred) của lượt trước
    pend_meta = {}          # thông tin thêm của lượt trước: turn, gain, y0, tap, t_tap...
    samples = []            # mẫu (before, held, x, after_thật) để hiệu chỉnh
    t_ready = time.time() - held_wait   # lượt đầu: con đang cầm đã sẵn, không cần chờ thêm
    _KIND_ASCII = {"tốt": "tot", "LĂN": "LAN", "GỘP": "GOP", "ĐỌC": "DOC"}

    def _compare_pending(frame_c, pigs_c, balls_c, W_c, H_c, box_c):
        """So dự đoán của lượt thả TRƯỚC với ảnh thật `frame_c` (heo đã yên): ghi pig_cmp.jsonl + ảnh cmp, thêm mẫu hiệu chỉnh.
        Trả (sai số, số heo lệch, dict compare_turn)."""
        nonlocal samples
        b0, h0, x0, pr0 = pending
        cd = compare_turn(b0, h0[0], x0, pr0, balls_c, W_c)
        if cd["kind"] != "ĐỌC":        # lượt ĐỌC (thiếu/thừa/nhầm heo) là lỗi nhận diện, không dùng để chỉnh vật lý
            samples.append((b0, h0, x0, balls_c, pend_meta.get("y0")))
            samples = samples[-12:]
        tn = pend_meta.get("turn", 0)
        row = dict(cd)
        row.update({"turn": tn, "t": round(time.time(), 2), "held": h0[0], "x_drop": round(x0, 1), "W": W_c, "H": H_c,
                    "pred_gain": pend_meta.get("gain"), "explore": pend_meta.get("explore", False), "sp": sim_dict(sp),
                    "obs": [[a, round(b, 1), round(c, 1), round(d, 1)] for a, b, c, d in balls_c],
                    "pred": [[a, round(b, 1), round(c, 1), round(d, 1)] for a, b, c, d in pr0]})
        ctx["cmp_rows"].append(row)
        if save_shots or calib_run:
            sess.append_jsonl("pig_cmp.jsonl", row)
            try:
                sess.make(sess.img_dir)
                _cmp_overlay(frame_c, box_c, pr0, pigs_c, x0, sess.img("pig_%04d_cmp%s" % (tn, shot_ext)),
                             "sai so %.3f lech %d %s" % (cd["err"], cd["miss"], _KIND_ASCII.get(cd["kind"], "")))
            except Exception:
                pass
        return cd["err"], cd["miss"], cd

    def _flush_trace(buf, turn_id, t_tap0, box_t):
        """Ghi ảnh quay (crop khung bàn) lúc heo rơi/lăn sau lượt thả turn_id + trace.jsonl (dt = giây kể từ lúc bắt đầu bấm)."""
        for i, (crop, ta, tb) in enumerate(buf):
            try:
                name = "tr_%04d_%02d.jpg" % (turn_id, i)
                _save_img(crop, os.path.join(sess.trace_dir, name))
                sess.append_jsonl("trace.jsonl", {"turn": turn_id, "i": i, "dt": round((ta + tb) / 2.0 - t_tap0, 3),
                                                  "dt0": round(ta - t_tap0, 3), "dt1": round(tb - t_tap0, 3),
                                                  "file": "trace/" + name if not sess.flat else name, "W": box_t[2] - box_t[0], "H": box_t[3] - box_t[1]})
            except Exception:
                pass

    while not should_stop():
        if max_turns and turn >= max_turns:
            log("info", "🐷 Đủ %d lượt" % max_turns)
            ctx["reason"] = "đủ %d lượt" % max_turns
            break
        if max_sec and time.time() - t_start > max_sec:
            log("info", "🐷 Hết thời gian cho phép")
            ctx["reason"] = "hết thời gian"
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
                sess.make()
                _save_img(frame, sess.path("pig_error.png"))
            except Exception:
                pass
            if err_cnt >= 3:
                log("error", "🐷 Lỗi nhận diện 3 lần liền, dừng")
                ctx["reason"] = "lỗi nhận diện 3 lần"
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
                    sess.make()
                    _overlay(frame, box, pigs, None, None, sess.path("pig_noheld.png"))
                    log("warn", "🐷 Không thấy con đang cầm - đã lưu %s (khung xanh = khung bàn bot đang dùng, kiểm tra có khớp khung nét đứt không)" %
                        sess.path("pig_noheld.png"))
                except Exception:
                    pass
            if no_held >= 6:
                log("warn", "🐷 Không thấy con heo đang cầm %d lần liền - có thể ván đã kết thúc hoặc màn hình đã đổi, dừng" % no_held)
                ctx["reason"] = "không thấy con cầm (hết ván/đổi màn hình)"
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
            err_val, miss, _cd = _compare_pending(frame, pigs, balls, W, H, box)
            err_txt = " | dự đoán lượt trước: sai số %.3f x rộng khung, lệch %d heo [%s]" % (err_val, miss, _cd["kind"])
            pending = None
        # tính nước đi NGAY (ảnh này đã là trạng thái cuối); trong lúc đó vẫn đang đợi held_wait
        if think_cfg is not None:
            think_s = float(think_cfg)
        else:
            think_s = max(float(step.get("think_min", 1.2)), held_wait - (time.time() - t_ready) - 0.1)
        y0_fix = tap_y * H if spawn_y == "click" else None
        x_drop, info = choose_drop(balls, (held[0], held[3]), W, H, sp, ep, think_s=think_s, n_x=n_x, log=log, held_top=held_top, y0_fixed=y0_fix)
        explore_flag = False
        if explore > 0 and rnd.random() < explore:
            # chế độ thu mẫu (calib_run): thả NGẪU NHIÊN một phần lượt để log có đủ tình huống lăn/nảy/gộp/sát tường, không chỉ nước "đẹp" nhất
            x_drop = rnd.uniform(held[3] * 1.02, W - held[3] * 1.02)
            explore_flag = True
            info = dict(info, explore=True)
        y0_held = y0_fix if y0_fix is not None else held[2]
        pred, pred_gain = simulate(balls, W, H, (held[0], x_drop, held[3], y0_held), sp)
        turn += 1
        ctx["turn"] = turn
        log("info", "🐷 Lượt %d: %d heo, cầm cấp %d -> thả x=%.0f%% (tính %.1fs)%s" %
            (turn, len(balls), held[0], 100.0 * x_drop / W, time.time() - t_turn, err_txt))

        def _write_log(x_act, pred_row, mode_txt, tap=None):
            if not (save_shots or test or calib_run):
                return
            sess.append_jsonl("pig_log.jsonl", {
                "turn": turn, "t": round(time.time(), 2), "session": sess.id, "W": W, "H": H, "held": held[0], "held_r": round(float(held[3]), 2), "x": x_drop,
                "x_act": x_act, "drop_mode": mode_txt, "tap": tap, "y0": round(float(y0_held), 1), "tap_y": tap_y, "spawn_y": spawn_y,
                "before": [[a, round(b, 1), round(c, 1), round(d, 1)] for a, b, c, d in balls],
                "pigs_raw": [[a, round(b, 1), round(c, 1), round(d, 1), round(e, 2)] for a, b, c, d, e in pigs],
                "pred": [[a, round(b, 1), round(c, 1), round(d, 1)] for a, b, c, d in pred_row],
                "pred_gain": pred_gain, "mass": sum(level_mass(b[0]) for b in balls), "explore": explore_flag,
                "sp": sim_dict(sp), "stamina": st_est, "pred_err": err_val, "info": info})

        if save_shots or test:
            sess.make(sess.img_dir)
            _overlay(frame, box, pigs, held, x_drop, sess.img("pig_%04d%s" % (turn, shot_ext)))
            sess.prune_images(keep)
        if save_raw and not test:
            sess.make(sess.raw_dir)
            _save_img(frame, os.path.join(sess.raw_dir, "pig_%04d_before.jpg" % turn))
        if test:
            _write_log(None, pred, "test")
            log("info", "🐷 TEST: không bấm. Ảnh kế hoạch: %s" % sess.img("pig_%04d%s" % (turn, shot_ext)))
            ctx["reason"] = "test (không bấm)"
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
                if explore_flag:
                    x_drop = rnd.uniform(held[3] * 1.02, W - held[3] * 1.02)
                    info = dict(info, explore=True)
                y0_held = y0_fix if y0_fix is not None else held[2]
                pred, pred_gain = simulate(balls, W, H, (held[0], x_drop, held[3], y0_held), sp)
        sx = box[0] + x_drop
        x_act = x_drop
        tap_xy = None
        t_tap0 = time.time()
        if drop_mode == "swipe":
            hx, hy = box[0] + held[1], box[1] + held[2]
            adb.swipe_hold_px(hx, hy, sx, hy, move_duration_ms=250, hold_ms=80)
            tap_xy = [round(hx, 1), round(hy, 1), round(sx, 1), round(hy, 1)]
        elif drop_mode == "tap":
            adb.tap_px(sx, box[1] + tap_y * H)
            tap_xy = [round(sx, 1), round(box[1] + tap_y * H, 1)]
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
        pend_meta = {"turn": turn, "gain": pred_gain, "y0": y0_held, "tap": tap_xy, "t_tap": t_tap0, "explore": explore_flag}
        y0_last = y0_held
        _write_log(x_act, pred_act, drop_mode, tap_xy)
        # tận dụng lúc heo đang lăn (game chưa hiện con kế) để hiệu chỉnh tham số vật lý từ các mẫu thật
        if auto_calib and len(samples) >= 6 and turn % calib_every == 0 and not should_stop():
            try:
                sp2, e0, e1, nt = calibrate(samples, sp, W, H, budget_s=calib_s)
                sess.append_jsonl("calib_history.jsonl", {"turn": turn, "e0": round(e0, 5), "e1": round(e1, 5), "tries": nt, "accepted": bool(e1 < e0 * 0.97),
                                                           "n_samples": len(samples), "params": sim_dict(sp2 if e1 < e0 * 0.97 else sp)})
                if e1 < e0 * 0.97:
                    sp = sp2
                    ctx["sp"] = sp
                    _save_params(step, sp)
                    sess.write_json("pig_params_end.json", {"params": sim_dict(sp), "turn": turn})
                log("info", "🐷 Hiệu chỉnh vật lý: sai số %.3f -> %.3f (%d lần thử) %s" %
                    (e0, e1, nt, ", ".join("%s=%.2f" % (k, getattr(sp, k)) for k in CAL_RANGE)))
            except Exception as e:
                log("warn", "🐷 Hiệu chỉnh vật lý lỗi: %s" % e)
        tr_buf = []

        def _trace_cb(fr, ta, tb, _b=box, _buf=tr_buf):
            if len(_buf) < trace_max:
                _buf.append((fr[_b[1]:_b[3], _b[0]:_b[2]].copy(), ta, tb))
        _on_frame = _trace_cb if trace_on else None
        frame, ready, t_ready = _wait_ready(adb, box, step, should_stop, on_frame=_on_frame, settle=(0.05 if trace_on else None))
        if trace_on and tr_buf:
            _flush_trace(tr_buf, turn, t_tap0, box)
        if not ready and not should_stop():
            log("warn", "🐷 Quá lâu không thấy con kế tiếp xuất hiện - vẫn tiếp tục với ảnh hiện tại")
        if frame is None:
            frame = adb.screencap_fast()
            if frame is None:
                log("error", "🐷 Mất ảnh màn hình, dừng")
                ctx["reason"] = "mất ảnh màn hình"
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
                ctx["reason"] = "màn hình không đổi sau 4 lần thả"
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
                ctx["reason"] = "hết thể lực (< %d)" % min_st
                break
    # lượt thả CUỐI chưa được so sánh với ảnh thật (vòng lặp thoát trước khi sang lượt kế): so nốt để log đủ
    if pending is not None and not test and frame is not None:
        try:
            box = _board_px(step, fw, fh)
            W, H = box[2] - box[0], box[3] - box[1]
            pigs = detect_pigs(frame, box)
            balls = rbook.snap(pigs, W) if radius_fix else [(lv, cx, cy, r) for lv, cx, cy, r, _ in pigs]
            e_l, m_l, cd_l = _compare_pending(frame, pigs, balls, W, H, box)
            pending = None
            log("info", "🐷 Lượt cuối: sai số dự đoán %.3f, lệch %d heo [%s]" % (e_l, m_l, cd_l["kind"]))
        except Exception as e:
            log("warn", "🐷 Không so được lượt cuối: %s" % e)
    if not ctx.get("reason") and should_stop():
        ctx["reason"] = "người dùng dừng"
    log("info", "🐷 Kết thúc sau %d lượt (%.0fs)" % (turn, time.time() - t_start))
    return True


def _finish_session(ctx, log):
    """Ghi kết quả cuối phiên: session.json (kết thúc/tóm tắt), pig_params_end.json, report.txt. Không bao giờ ném lỗi."""
    sess = ctx.get("sess")
    if sess is None or not sess.created:
        return
    try:
        rows = ctx.get("cmp_rows") or []
        sp = ctx.get("sp")
        lines = summarize_cmp(rows)
        meta = {}
        try:
            with open(sess.path("session.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            pass
        meta.update({"ended": time.strftime("%Y-%m-%d %H:%M:%S"), "turns": ctx.get("turn", 0), "reason": ctx.get("reason", ""),
                     "seconds": round(time.time() - ctx.get("started", time.time()), 1), "cmp_turns": len(rows), "summary": lines,
                     "sp_end": sim_dict(sp) if sp is not None else None})
        sess.write_json("session.json", meta)
        if sp is not None:
            sess.write_json("pig_params_end.json", {"params": sim_dict(sp), "turn": ctx.get("turn", 0)})
        head = ["Phiên %s (%s) - %d lượt thả, %.0fs, kết thúc: %s" % (sess.id, ctx.get("mode"), ctx.get("turn", 0), meta["seconds"], ctx.get("reason") or "?"), ""]
        txt = head + lines + [""] + format_cmp_table(rows) + [
            "", "Hiệu chỉnh lại bằng log của phiên này:  python pig_calib.py \"%s\"" % os.path.abspath(sess.dir),
            "Đọc báo cáo chi tiết:                     python pig_report.py \"%s\"" % os.path.abspath(sess.dir)]
        with open(sess.path("report.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(txt) + "\n")
        for ln in lines:
            log("info", "🐷 " + ln)
        log("info", "🐷 Đã lưu phiên: %s (report.txt, pig_log.jsonl, pig_cmp.jsonl, ảnh trong img/)" % os.path.abspath(sess.dir))
    except Exception as e:
        try:
            log("warn", "🐷 Không ghi được báo cáo phiên: %s" % e)
        except Exception:
            pass


def run_auto_pig_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy bước auto_pig (đủ các field xem docstring của _run_auto_pig_impl). Dù thoát bằng đường nào cũng ghi tóm tắt phiên
    (session.json, pig_params_end.json, report.txt) vào thư mục phiên - xem PigSession."""
    log = log or (lambda level, msg: print("[%s] %s" % (level, msg)))
    ctx = {}
    try:
        return _run_auto_pig_impl(adb, step, should_stop, log, ctx)
    except Exception as e:
        ctx["reason"] = "lỗi: %r" % (e,)
        raise
    finally:
        _finish_session(ctx, log)


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

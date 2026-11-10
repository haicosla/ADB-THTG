# -*- coding: utf-8 -*-
"""
Bot auto "Giao Hàng - Đại Chiến Giành Đơn" (chiếm ô đất trên bản đồ khu thương mại, 4 phe) - điều khiển qua ADB, bước `auto_delivery`.

>>> Bản 1 (08/11): CHƯA chạy thử trên LDPlayer thật. Đã kiểm trên 18 ảnh chụp thật (`python delivery_bot.py --check anh.png`)
>>> và bằng bộ lập kế hoạch/bản đồ giả (`python delivery_bot.py --selftest`). LẦN ĐẦU hãy chạy chế độ TEST (không bấm).

======================================================================================================
1) LUẬT GAME (người dùng mô tả) VÀ CÁCH BOT HIỂU
======================================================================================================
  - Phe của mình (mặc định MÀU XANH DƯƠNG = "Ăn No Chưa", field `my_color`). 14 ô: 8 ô Lv1 (300đ), 4 ô Lv2 (600đ), 2 ô Lv3 (1800đ).
  - Bấm vào ô trên bản đồ lớn là VÀO LUÔN (không popup). Đi vào mất ~3s (`enter_s`, bot tự đo lại và nhớ).
  - Trong ô: thanh "Số người" ở góc phải trên. Thanh đầy 1 màu = chưa ai đếm ngược. Có đếm ngược = thanh chỉ đầy 1 phần,
    chiếm đủ 20s (`capture_s`) là thắng: số giây còn lại = 20 * (1 - độ đầy). Màu thanh = phe đang được đếm (xanh = ta).
    Phe nào ĐÔNG hơn trong ô thì đồng hồ thuộc phe đó (đổi màu).
  - Số giây của từng ô CHỈ thấy khi đang ở trong ô -> bot GHI NHỚ (ô nào, còn bao nhiêu giây, lúc nào thấy) rồi tự trừ dần theo giờ.
  - Chết -> banner "Bị đánh lui" + nút "Đến hồi sinh" -> về phòng chờ -> phải bấm "Bản đồ lớn" để vào ô lại.
  - Bản đồ RỘNG hơn màn hình: bot kéo (vuốt) để tìm ô, đo độ dịch thật bằng so khớp pha (phaseCorrelate) giữa 2 ảnh liên tiếp,
    nhờ đó biết toạ độ "thế giới" của từng ô và kéo thẳng tới đúng ô cần vào.

======================================================================================================
2) CHIẾN THUẬT (hàm `plan`)
======================================================================================================
  Mỗi lần quyết định, bot xét các ô ứng viên:
    * ô đã có đồng hồ phe ta (đã ghi nhớ): sẽ XONG lúc `thấy_lúc + còn_lại`; bot phải ĐẾN KỊP (đến trước lúc xong `arrive_margin_s`).
    * ô chưa có đồng hồ: coi như phải chiếm mới = đứng đủ `capture_s`, nhân xác suất thắng theo số quân ta/địch (mũ bảo hiểm ở bản đồ).
    * ô vòng sáng đã XANH (đã của ta): điểm rất thấp (`hold_factor`).
  Thời gian đi từ ô A sang ô B = mở bản đồ (`open_map_s`) + kéo bản đồ (số lần vuốt * `swipe_s`) + vào ô (`enter_s`).
  Bot thử mọi thứ tự đi tối đa `seq_len` (3) ô trong `horizon_s` (60s), chọn chuỗi cho TỔNG ĐIỂM lớn nhất. Ví dụ 3 ô còn 20s/10s/4s:
  đi ô 4s trước, rồi ô 10s, rồi ô 20s nếu kịp. Đang ở ô nào thì chỉ rời khi chuỗi tốt nhất bắt đầu bằng ô khác và hơn chuỗi
  "ở lại" ít nhất `switch_gain` điểm (và đã ở >= `min_stay_s`). Còn vài giây thì tự động ở lại chờ xong (vì rời không kịp quay lại).

======================================================================================================
3) ẢNH MẪU (templates/delivery/, tên delivery_<loại>_<số>.png; mỗi loại nhiều file được)
======================================================================================================
  hud      chữ "Số người:" ở thanh góc phải trên (dấu hiệu đang ở TRONG khu chiếm đất).
  map      tiêu đề "Bản đồ khu thương mại".
  dead     banner "Bị đánh lui".          respawn  nút "Đến hồi sinh".
  bigmap   nút "Bản đồ lớn" góc trái dưới (không khớp thì vẫn bấm toạ độ cố định `bigmap_xy`).
  lobby    nút "Đại Chiến Giành Đơn" ở sảnh (bấm để vào).   done  dòng "Chờ nhận thưởng" ở sảnh = hết trận -> DỪNG.
  plot_<slug>  nhãn của từng ô trên bản đồ (14 mẫu: delivery_plot_lv3_toa_nha_ifc.png ...), xem PLOTS bên dưới.
  Cắt mẫu từ ảnh 720x1280:   python delivery_bot.py --add hud anh.png x1 y1 x2 y2
                             python delivery_bot.py --add plot:lv2_cang_so anh.png x1 y1 x2 y2
  Kiểm 1 ảnh:                python delivery_bot.py --check anh.png

======================================================================================================
4) FIELD CỦA BƯỚC `auto_delivery` (đều tuỳ chọn)
======================================================================================================
  test (False: chỉ đọc + log + lưu debug_delivery/, KHÔNG bấm/vuốt), max_seconds (0 = không giới hạn), my_color ("blue"),
  capture_s 20, enter_s 3.0, open_map_s 1.5, swipe_s 1.2, arrive_margin_s 1.0, seq_len 3, horizon_s 60, switch_gain 150,
  min_stay_s 5, hold_factor 0.05, tap_dy -90 (bấm cao hơn nhãn bao nhiêu px để trúng toà nhà), bigmap_xy [60,1115],
  thr 0.80 (ngưỡng nhãn ô), poll_s 0.4, unknown_max 25, tpl_dir, debug.
  Chi tiết nhớ tự đo: `enter_s` được cập nhật bằng trung bình trượt từ lần vào ô thật.
"""
import os
import sys
import json
import time
import itertools
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

REF_W, REF_H = 720, 1280

# (slug, tên hiển thị, cấp). Điểm theo cấp: Lv1 300, Lv2 600, Lv3 1800.
PLOTS = [
    ("lv1_cho_cu", "Lv1 Chợ Cũ", 1),
    ("lv1_pho_an_v", "Lv1 Phố Ăn V...", 1),
    ("lv1_trun", "Lv1 Trun... (tên đầy đủ chưa thấy)", 1),
    ("lv1_lang_trong_thanh_pho", "Lv1 Làng Trong Thành Phố", 1),
    ("lv1_lau_uyen_uong", "Lv1 Lầu Uyên Ương", 1),
    ("lv1_khu_dan_cu", "Lv1 Khu Dân Cư", 1),
    ("lv1_pho_di_bo", "Lv1 Phố Đi Bộ", 1),
    ("lv1_cho_ngoai_troi", "Lv1 Chợ Ngoài Trời", 1),
    ("lv2_thung_lung_thong_minh", "Lv2 Thung Lũng Thông Minh", 2),
    ("lv2_khu_sang_tao", "Lv2 Khu Sáng Tạo", 2),
    ("lv2_cang_so", "Lv2 Cảng Số", 2),
    ("lv2_toa_nha_thuong_mai", "Lv2 Tòa Nhà Thương Mại", 2),
    ("lv3_toa_nha_ifc", "Lv3 Tòa Nhà IFC", 3),
    ("lv3_trung_tam_tai_chinh", "Lv3 Trung Tâm Tài Chính", 3),
]
LEVEL_PTS = {1: 300, 2: 600, 3: 1800}
PLOT_LEVEL = {s: lv for s, _n, lv in PLOTS}
PLOT_NAME = {s: n for s, n, _lv in PLOTS}
KINDS = ("hud", "map", "dead", "respawn", "bigmap", "lobby", "done")

# vùng thanh "Số người" (toạ độ 720x1280)
BAR_X0, BAR_X1, BAR_Y = 415, 706, 314
CIRCLE_BOX = (505, 284, 640, 313)      # x0,y0,x1,y1 vùng các vòng tròn phe + số người


def _tpl_dir_default():
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "delivery")
    return here if os.path.isdir(here) else os.path.join("templates", "delivery")


def _imread(p):
    try:
        return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


def _imwrite(p, img):
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        ok, buf = cv2.imencode(os.path.splitext(p)[1] or ".png", img)
        if ok:
            buf.tofile(p)
        return ok
    except Exception:
        return False


def load_templates(tpl_dir: str) -> Dict[str, List[Tuple[str, np.ndarray]]]:
    """Nạp delivery_<loại>_N.png và delivery_plot_<slug>_N.png -> {loại hoặc 'plot:<slug>': [(tên, ảnh)]}."""
    out: Dict[str, list] = {k: [] for k in KINDS}
    for s, _n, _l in PLOTS:
        out["plot:" + s] = []
    if not os.path.isdir(tpl_dir):
        return out
    for fn in sorted(os.listdir(tpl_dir)):
        low = fn.lower()
        if not (low.startswith("delivery_") and low.endswith((".png", ".jpg", ".jpeg"))):
            continue
        stem = os.path.splitext(fn)[0][len("delivery_"):]
        key = None
        if stem.startswith("plot_"):
            body = stem[len("plot_"):]
            for s, _n, _l in PLOTS:
                if body == s or body.startswith(s + "_"):
                    key = "plot:" + s
                    break
        else:
            for k in KINDS:
                if stem == k or stem.startswith(k + "_"):
                    key = k
                    break
        if key is None:
            continue
        img = _imread(os.path.join(tpl_dir, fn))
        if img is not None:
            out[key].append((fn, img))
    return out


def match_tpl(img, tpl, region=None):
    """Khớp xám. region = (x0,y0,x1,y1) pixel. Trả (cx, cy, điểm) theo toạ độ ảnh gốc."""
    if img is None or tpl is None:
        return None, None, 0.0
    x0, y0 = 0, 0
    sub = img
    if region:
        x0, y0, x1, y1 = [int(v) for v in region]
        sub = img[max(0, y0):y1, max(0, x0):x1]
        x0, y0 = max(0, x0), max(0, y0)
    th, tw = tpl.shape[:2]
    if sub.shape[0] < th or sub.shape[1] < tw:
        return None, None, 0.0
    a = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) if sub.ndim == 3 else sub
    b = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY) if tpl.ndim == 3 else tpl
    res = cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)
    _mn, mx, _ml, loc = cv2.minMaxLoc(res)
    return x0 + loc[0] + tw // 2, y0 + loc[1] + th // 2, float(mx)


def hue_name(h, s=255):
    if 92 <= h <= 112:
        return "blue"
    if 5 <= h <= 16:
        return "orange"
    if 17 <= h <= 32:
        return "yellow"
    if h >= 165 or h < 5:
        return "red"
    return "?"


def _tess(binary):
    import pytesseract
    b = cv2.copyMakeBorder(binary, 14, 14, 14, 14, cv2.BORDER_CONSTANT, value=255)
    txt = pytesseract.image_to_string(b, config="--psm 10 -c tessedit_char_whitelist=0123456789").strip()
    return int(txt) if txt.isdigit() else None


def _ocr_digits(crop):
    """Đọc số trong ảnh nhỏ (chữ trắng/kem, viền tối). Hai cách (lọc màu trắng ít bão hoà / Otsu xám); trùng nhau mới tin,
    khác nhau thì trả cách lọc màu. Trả int hoặc None. Cần pytesseract; thiếu thì None."""
    try:
        import pytesseract  # noqa: F401
    except Exception:
        return None
    try:
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        m = ((hsv[:, :, 1] < 85) & (hsv[:, :, 2] > 185)).astype(np.uint8) * 255
        m = cv2.resize(m, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        _t, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
        r1 = _tess(255 - m)
        g = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        _t, o = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if o.mean() < 127:                 # chữ phải đen trên nền trắng
            o = 255 - o
        r2 = _tess(o)
        return r1 if r1 == r2 or r2 is None else (r1 if r1 is not None else r2)
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Đọc màn hình
# ----------------------------------------------------------------------------
def read_hud(img, capture_s=20.0, count_circles=True):
    """Đọc thanh 'Số người'. Trả dict: timer (giây còn lại hoặc None), owner (màu phe đang đếm hoặc None), circles {màu: số}."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    row = hsv[BAR_Y, BAR_X0:BAR_X1].astype(int)
    fill = (row[:, 1] > 70) & (row[:, 2] > 45)
    n = len(fill)
    run = 0
    gap = 0
    for i in range(n):
        if fill[i]:
            run = i + 1
            gap = 0
        else:
            gap += 1
            if gap > 5:
                break
    frac = run / float(n)
    timer = None
    owner = None
    if run > 0:
        hs = row[:run][fill[:run]][:, 0]
        owner = hue_name(int(np.median(hs))) if len(hs) else None
        if frac < 0.97:
            timer = round(max(0.0, capture_s * (1.0 - frac)), 1)
    circles: Dict[str, Optional[int]] = {}
    if count_circles:
        x0, y0, x1, y1 = CIRCLE_BOX
        sub = hsv[y0:y1, x0:x1]
        out = {}
        for name, lo, hi in (("blue", 92, 112), ("yellow", 17, 32), ("orange", 5, 16), ("red", 165, 180)):
            vmin = 172 if name == "blue" else 150      # vòng xanh sáng hơn nền thanh (V 181 so với 156)
            m = ((sub[:, :, 0] >= lo) & (sub[:, :, 0] <= hi) & (sub[:, :, 1] > 120) & (sub[:, :, 2] > vmin)).astype(np.uint8)
            if name == "red":
                m |= ((sub[:, :, 0] < 5) & (sub[:, :, 1] > 150) & (sub[:, :, 2] > 150)).astype(np.uint8)
            cnt, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
            for k in range(1, cnt):
                if 120 <= st[k, cv2.CC_STAT_AREA] <= 900 and st[k, cv2.CC_STAT_WIDTH] >= 14:
                    cx, cy = int(cen[k][0]) + x0, int(cen[k][1]) + y0
                    out[name] = _ocr_digits(img[cy - 10:cy + 10, cx - 9:cx + 9])
        circles = out
    return {"timer": timer, "owner": owner, "frac": round(frac, 3), "circles": circles}


def helmets_near(img, cx, cy):
    """Đếm mũ bảo hiểm (số người từng phe) ngay dưới nhãn ô tại (cx,cy). Trả {màu: số, không đọc được số thì tính 1}."""
    h, w = img.shape[:2]
    x0, x1 = max(0, cx - 110), min(w, cx + 130)
    y0, y1 = min(h - 1, cy + 14), min(h, cy + 80)
    if y1 - y0 < 10:
        return {}
    hsv = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    hh = hsv[:, :, 0]
    m = (((hh >= 5) & (hh <= 32)) | ((hh >= 92) & (hh <= 112)) | (hh >= 165) | (hh < 3))
    m = (m & (hsv[:, :, 1] > 140) & (hsv[:, :, 2] > 170)).astype(np.uint8)
    m = cv2.dilate(m, np.ones((3, 3), np.uint8))
    cnt, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    out = {}
    for k in range(1, cnt):
        if not (250 <= st[k, cv2.CC_STAT_AREA] <= 1800):
            continue
        sel = (lab == k) & (hsv[:, :, 1] > 140) & (hsv[:, :, 2] > 170)
        med = int(np.median(hh[sel])) if sel.any() else 0
        name = "blue" if 92 <= med <= 112 else ("orange" if 5 <= med <= 18 else ("yellow" if 19 <= med <= 32 else "red"))
        xs = np.where(sel.any(axis=0))[0]
        bx = x0 + (int(xs.max()) if len(xs) else st[k, cv2.CC_STAT_LEFT] + st[k, cv2.CC_STAT_WIDTH])
        by = y0 + int(cen[k][1]) + 4
        num = _ocr_digits(img[max(0, by - 16):by + 16, bx + 3:bx + 19])
        if num is not None and not (1 <= num <= 40):
            num = None
        out[name] = out.get(name, 0) + (num if num else 1)
    return out


def ring_is_blue(img, cx, cy):
    """Vòng sáng quanh ô có màu XANH (= ô của phe xanh)? Nhìn vùng ngay trên nhãn."""
    h, w = img.shape[:2]
    y0, y1 = max(0, cy - 66), max(1, cy - 22)
    x0, x1 = max(0, cx - 110), min(w, cx + 110)
    reg = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV).reshape(-1, 3)
    m = (reg[:, 1] > 55) & (reg[:, 2] > 190)
    if m.sum() < 300:
        return False
    hs = reg[m][:, 0]
    blue = int(((hs >= 85) & (hs <= 112)).sum())
    return blue > 0.5 * len(hs)


def measure_shift(a_bgr, b_bgr):
    """Độ dịch (dx, dy) pixel của NỘI DUNG bản đồ từ ảnh a sang b (dương = trôi sang phải/xuống), và độ tin cậy."""
    def prep(im):
        g = cv2.cvtColor(im[140:1040, 130:720], cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, None, fx=0.5, fy=0.5)
        return g.astype(np.float32)
    a, b = prep(a_bgr), prep(b_bgr)
    win = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), resp = cv2.phaseCorrelate(a, b, win)
    return dx * 2.0, dy * 2.0, float(resp)


# ----------------------------------------------------------------------------
# Lập kế hoạch (thuần tính toán, test được)
# ----------------------------------------------------------------------------
def plan(now, cur, known, travel, cfg):
    """
    now: giờ hiện tại (s). cur: slug ô đang đứng hoặc None (đang ở bản đồ/phòng chờ).
    known: {slug: {"owner": "ours"|"enemy"|None, "done_at": giờ xong dự kiến hoặc None, "ours_ring": bool,
                   "allies": int, "enemies": int}}
    travel(a, b): giây đi từ a (hoặc None) sang b.
    Trả (chuỗi ô tốt nhất, điểm, {slug đầu tiên: điểm tốt nhất của các chuỗi bắt đầu bằng slug đó}).
    """
    margin = cfg.get("arrive_margin_s", 1.0)
    cap = cfg.get("capture_s", 20.0)
    horizon = cfg.get("horizon_s", 60.0)
    seq_len = int(cfg.get("seq_len", 3))
    hold = cfg.get("hold_factor", 0.05)

    cands = []
    for slug, _n, lv in PLOTS:
        info = known.get(slug, {})
        pts = LEVEL_PTS[lv]
        if info.get("ours_ring") and not info.get("done_at"):
            pts *= hold
        done_at = info.get("done_at")
        if done_at is not None and done_at <= now:   # đã xong lúc ta không thấy -> coi như đã thuộc ta
            info = dict(info, done_at=None)
            pts *= hold
            done_at = None
        al, en = info.get("allies", 0) or 0, info.get("enemies", 0) or 0
        p = (al + 1.0) / (al + en + 1.5)
        cands.append((slug, pts, done_at, p))
    # chỉ giữ ứng viên đáng xét
    cands.sort(key=lambda c: -(c[1] * (1.0 if c[2] is not None else c[3])))
    full = cands
    cands = cands[:7]
    if cur is not None and all(c[0] != cur for c in cands):     # ô đang đứng luôn được xét (để biết "ở lại" đáng bao nhiêu)
        cands.append(next(c for c in full if c[0] == cur))

    def run(seq):
        t = now
        place = cur
        total = 0.0
        for slug in seq:
            c = next(x for x in cands if x[0] == slug)
            tr = 0.0 if slug == place else travel(place, slug)
            arrive = t + tr
            if c[2] is not None:                       # ô đã có đồng hồ phe ta
                if arrive > c[2] - margin:
                    return None
                t = max(arrive, c[2])
                total += c[1]
            else:                                       # phải chiếm mới: đứng đủ capture_s
                t = arrive + cap
                total += c[1] * c[3]
            place = slug
            if t - now > horizon:
                break
        return total, t

    best = (None, -1.0, 1e9)
    first_best: Dict[str, float] = {}
    names = [c[0] for c in cands]
    for L in range(1, seq_len + 1):
        for seq in itertools.permutations(names, L):
            r = run(seq)
            if r is None:
                continue
            total, tend = r
            if total > first_best.get(seq[0], -1.0):
                first_best[seq[0]] = total
            if total > best[1] + 1e-9 or (abs(total - best[1]) < 1e-9 and tend < best[2]):
                best = (seq, total, tend)
    return (list(best[0]) if best[0] else []), max(best[1], 0.0), first_best


# ----------------------------------------------------------------------------
# Bot
# ----------------------------------------------------------------------------
class DeliveryBot:
    def __init__(self, adb, tpls, log=None, should_stop=None, **cfg):
        self.adb = adb
        self.tpls = tpls
        self.log = log or (lambda lv, m: print(f"[{lv}] {m}"))
        self.should_stop = should_stop or (lambda: False)
        d = dict(test=False, max_seconds=0, my_color="blue", capture_s=20.0, enter_s=3.0, open_map_s=1.5,
                 swipe_s=1.2, arrive_margin_s=1.0, seq_len=3, horizon_s=60.0, switch_gain=150.0, min_stay_s=5.0,
                 hold_factor=0.05, tap_dy=-90, bigmap_xy=[60, 1115], thr=0.80, poll_s=0.4, unknown_max=25,
                 debug=False, map_file=None)
        d.update({k: v for k, v in cfg.items() if v is not None})
        self.c = d
        self._now = time.time
        self._sleep = time.sleep
        self.sx = self.sy = 1.0
        self.known: Dict[str, dict] = {}
        self.world: Dict[str, Tuple[float, float]] = {}    # slug -> (wx, wy) tâm nhãn trong hệ toạ độ bản đồ
        self.off = [0.0, 0.0]                               # độ dịch nội dung tích luỹ (world = màn hình - off)
        self.have_off = False
        self.cur: Optional[str] = None
        self.enter_t: Optional[float] = None
        self.tap_t: Optional[float] = None
        self.stats = {"captures": 0, "deaths": 0, "switches": 0}
        self._load_map()

    # ---- tiện ích ----
    def _grab(self):
        img = self.adb.screencap_fast()
        if img is None:
            return None
        h, w = img.shape[:2]
        self.sx, self.sy = w / float(REF_W), h / float(REF_H)
        if (w, h) != (REF_W, REF_H):
            img = cv2.resize(img, (REF_W, REF_H))
        return img

    def _tap(self, x, y, why=""):
        if self.c["test"]:
            self.log("INFO", f"[TEST] sẽ bấm ({int(x)},{int(y)}) {why}")
            return
        self.adb.tap_px(x * self.sx, y * self.sy)

    def _drag(self, dx, dy):
        """Kéo NỘI DUNG bản đồ đi (dx,dy) pixel (vuốt từ tâm trừ nửa đến tâm cộng nửa)."""
        dx = max(-520, min(520, dx))
        dy = max(-700, min(700, dy))
        x1, y1 = 360 - dx / 2.0, 600 - dy / 2.0
        x2, y2 = 360 + dx / 2.0, 600 + dy / 2.0
        if self.c["test"]:
            self.log("INFO", f"[TEST] sẽ vuốt ({int(x1)},{int(y1)})->({int(x2)},{int(y2)})")
            return
        self.adb.swipe_px(x1 * self.sx, y1 * self.sy, x2 * self.sx, y2 * self.sy, 380)

    def _has(self, img, kind, thr=None, region=None):
        thr = thr or self.c["thr"]
        best = (None, None, 0.0)
        for _n, t in self.tpls.get(kind, []):
            r = match_tpl(img, t, region)
            if r[2] > best[2]:
                best = r
        return best if best[2] >= thr else (None, None, best[2])

    def detect(self, img):
        thr = 0.70
        if self._has(img, "dead", thr)[0] is not None or self._has(img, "respawn", thr)[0] is not None:
            return "dead"
        if self._has(img, "map", thr)[0] is not None:
            return "map"
        if self._has(img, "hud", thr)[0] is not None:
            return "zone"
        if self._has(img, "done", thr)[0] is not None:
            return "done"
        if self._has(img, "lobby", thr)[0] is not None:
            return "lobby"
        if self._has(img, "bigmap", 0.55)[0] is not None:
            return "room"
        return "unknown"

    # ---- bản đồ ----
    def _map_file(self):
        return self.c.get("map_file") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "delivery_map.json")

    def _load_map(self):
        try:
            with open(self._map_file(), "r", encoding="utf-8") as f:
                d = json.load(f)
            self.world = {k: tuple(v) for k, v in d.get("world", {}).items() if k in PLOT_LEVEL}
        except Exception:
            pass

    def _save_map(self):
        try:
            p = self._map_file()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"world": self.world}, f, ensure_ascii=False)
        except Exception:
            pass

    def visible_plots(self, img):
        out = {}
        for s, _n, _l in PLOTS:
            r = self._has(img, "plot:" + s, self.c["thr"], region=(0, 100, REF_W, 1100))
            if r[0] is not None:
                out[s] = (r[0], r[1], r[2])
        return out

    def _update_from_map(self, img, vis):
        for s, (cx, cy, _sc) in vis.items():
            if self.have_off:
                self.world[s] = (cx - self.off[0], cy - self.off[1])
            k = self.known.setdefault(s, {})
            k["ours_ring"] = ring_is_blue(img, int(cx), int(cy))
            hm = helmets_near(img, int(cx), int(cy))
            mine = hm.get(self.c["my_color"], 0)
            k["allies"] = mine
            k["enemies"] = sum(v for kk, v in hm.items() if kk != self.c["my_color"])
            if not k["ours_ring"] and k.get("owner") == "ours" and k.get("done_at") is None:
                k["owner"] = None

    def _localize(self, img, vis):
        """Biết ít nhất 1 ô đã có toạ độ thế giới -> suy ra off hiện tại."""
        ests = [(cx - self.world[s][0], cy - self.world[s][1]) for s, (cx, cy, _sc) in vis.items() if s in self.world]
        if ests:
            self.off = [float(np.median([e[0] for e in ests])), float(np.median([e[1] for e in ests]))]
            self.have_off = True
            return True
        return False

    def _move_view(self, dx, dy, prev):
        """Kéo nội dung (dx,dy), chụp lại, đo dịch thật, cập nhật off. Trả (ảnh mới, dịch thật dx, dy)."""
        self._drag(dx, dy)
        self._sleep(0.55)
        img = self._grab()
        if img is None or prev is None:
            return img, 0.0, 0.0
        rx, ry, resp = measure_shift(prev, img)
        if self.c["test"]:
            rx, ry = dx, dy
        self.off[0] += rx
        self.off[1] += ry
        return img, rx, ry

    def scan_map(self, img):
        """Quét toàn bản đồ lần đầu: về góc trên-trái rồi quét từng hàng; ghi toạ độ thế giới của mọi ô tìm thấy."""
        self.log("INFO", "🗺 Quét bản đồ lần đầu (kéo tìm đủ 14 ô)...")
        self.have_off = False
        for _ in range(14):                      # về góc trái-trên (nội dung trôi sang phải/xuống)
            img2, rx, ry = self._move_view(450, 600, img)
            if img2 is None:
                return img
            tiny = abs(rx) < 90 and abs(ry) < 120
            img = img2
            if tiny and not self.c["test"]:
                break
        self.off = [0.0, 0.0]
        self.have_off = True
        direction = -1
        for row in range(8):
            vis = self.visible_plots(img)
            self._update_from_map(img, vis)
            for _ in range(10):
                if self.should_stop():
                    return img
                img2, rx, ry = self._move_view(direction * 420, 0, img)
                if img2 is None:
                    return img
                img = img2
                self._update_from_map(img, self.visible_plots(img))
                if abs(rx) < 100 and not self.c["test"]:
                    break
            direction = -direction
            if len(self.world) >= len(PLOTS):
                break
            img2, rx, ry = self._move_view(0, -520, img)
            if img2 is None:
                return img
            img = img2
            if abs(ry) < 120 and not self.c["test"]:
                break
        self._save_map()
        self.log("INFO", f"🗺 Đã biết toạ độ {len(self.world)}/{len(PLOTS)} ô: " + ", ".join(sorted(self.world)))
        return img

    def goto_and_tap(self, slug, img):
        """Kéo bản đồ để thấy ô `slug` rồi bấm vào. Trả True nếu đã bấm."""
        for _ in range(9):
            if self.should_stop():
                return False
            vis = self.visible_plots(img)
            self._update_from_map(img, vis)
            if slug in vis:
                cx, cy, _sc = vis[slug]
                if 60 < cx < 660 and 190 < cy < 1060:
                    self.tap_t = self._now()
                    self._tap(cx, cy + self.c["tap_dy"], f"vào {PLOT_NAME[slug]}")
                    return True
            if slug in self.world and self.have_off:
                tx, ty = 360 - self.world[slug][0], 640 - self.world[slug][1]
                dx, dy = tx - self.off[0], ty - self.off[1]
            else:
                dx, dy = -400, 0
            img2, rx, ry = self._move_view(dx, dy, img)
            if img2 is None:
                return False
            img = img2
        return False

    def travel(self, a, b):
        """Ước lượng giây đi từ ô a (None = đang ở bản đồ) sang ô b."""
        t = self.c["enter_s"] + (0.0 if a is None else self.c["open_map_s"])
        if b in self.world:
            if a in self.world:
                d = max(abs(self.world[a][0] - self.world[b][0]) / 450.0, abs(self.world[a][1] - self.world[b][1]) / 600.0)
            else:
                d = 1.0
            t += int(d + 0.999) * self.c["swipe_s"]
        else:
            t += 2 * self.c["swipe_s"]
        return t

    # ---- vòng chính ----
    def _decide(self, now):
        seq, score, first = plan(now, self.cur, self.known, self.travel, self.c)
        return seq, score, first

    def _note_zone(self, hud, now):
        if self.cur is None:
            return
        k = self.known.setdefault(self.cur, {})
        t = hud["timer"]
        mine = hud["owner"] == self.c["my_color"]
        circ = hud["circles"]
        k["allies"] = circ.get(self.c["my_color"]) or k.get("allies", 0)
        k["enemies"] = sum((v or 1) for kk, v in circ.items() if kk != self.c["my_color"])
        if t is not None and mine:
            k["owner"], k["done_at"] = "ours", now + t
        elif t is not None:
            k["owner"], k["done_at"] = "enemy", None
        else:
            if k.get("done_at") is not None and k["done_at"] - now < 2.5:
                self.stats["captures"] += 1
                k["owner"], k["ours_ring"] = "ours", True
                self.log("INFO", f"✅ Xong ô {PLOT_NAME[self.cur]} (+{LEVEL_PTS[PLOT_LEVEL[self.cur]]}đ dự kiến)")
            k["done_at"] = None

    def run(self):
        c = self.c
        t0 = self._now()
        unknown = 0
        last_state = None
        entered = None
        while not self.should_stop():
            now = self._now()
            if c["max_seconds"] and now - t0 > c["max_seconds"]:
                self.log("INFO", "⏱ Hết thời gian tối đa -> dừng")
                break
            img = self._grab()
            if img is None:
                self._sleep(1.0)
                continue
            st = self.detect(img)
            if st != last_state:
                self.log("INFO", f"trạng thái: {st}")
                last_state = st
            if st != "unknown":
                unknown = 0
            if st == "done":
                self.log("INFO", "🏁 Sảnh báo 'Chờ nhận thưởng' = hết trận -> dừng")
                break
            if st == "dead":
                self.stats["deaths"] += 1
                self.cur = None
                x, y, _s = self._has(img, "respawn", 0.60)
                self._tap(x if x else 360, y if y else 1115, "Đến hồi sinh")
                self._sleep(1.5)
            elif st == "lobby":
                x, y, _s = self._has(img, "lobby", 0.60)
                self._tap(x, y, "vào Đại Chiến Giành Đơn")
                self._sleep(2.5)
            elif st == "room":
                self.cur = None
                bx, by = c["bigmap_xy"]
                x, y, _s = self._has(img, "bigmap", 0.60)
                self._tap(x or bx, y or by, "Bản đồ lớn")
                self._sleep(1.0)
            elif st == "map":
                img = self._on_map(img, now)
            elif st == "zone":
                if c["test"]:
                    hud = read_hud(img, c["capture_s"])
                    self.log("INFO", f"[TEST] HUD {hud}")
                    self._sleep(1.0)
                    break
                if self.enter_t is None or entered != self.cur:
                    entered = self.cur
                    self.enter_t = now
                    if self.tap_t is not None:       # đo thời gian vào ô thật, cập nhật enter_s (trung bình trượt)
                        dt = max(0.5, min(10.0, now - self.tap_t))
                        c["enter_s"] = round(0.7 * c["enter_s"] + 0.3 * dt, 2)
                        self.tap_t = None
                hud = read_hud(img, c["capture_s"], count_circles=True)
                self._note_zone(hud, now)
                self._zone_decide(img, hud, now)
            else:
                unknown += 1
                if c["test"]:
                    self.log("INFO", "[TEST] màn hình lạ, dừng")
                    break
                if unknown >= c["unknown_max"]:
                    self.log("WARN", "Màn hình lạ quá lâu -> dừng (kiểm ảnh mẫu delivery_*.png)")
                    break
                if unknown % 8 == 0:
                    self.adb.run_cmd(["shell", "input", "keyevent", "4"])
            if c["test"] and st in ("map", "dead", "lobby", "room"):
                break
            self._sleep(c["poll_s"])
        self.log("INFO", f"Kết thúc. {self.stats}")
        return True

    def _zone_decide(self, img, hud, now):
        c = self.c
        if self.cur is None:
            return
        stay_for = now - (self.enter_t or now)
        seq, score, first = self._decide(now)
        stay = first.get(self.cur, 0.0)
        best_first = seq[0] if seq else self.cur
        if c.get("debug"):
            self.log("DEBUG", f"HUD {hud} | chuỗi {seq} {score:.0f}đ | ở lại {stay:.0f}đ")
        if best_first != self.cur and stay_for >= c["min_stay_s"] and score - stay >= c["switch_gain"]:
            self.log("INFO", f"➡ Rời {PLOT_NAME[self.cur]} (ở lại {stay:.0f}đ) để đi {PLOT_NAME.get(best_first)} (chuỗi {score:.0f}đ)")
            self.stats["switches"] += 1
            self.target = best_first
            bx, by = c["bigmap_xy"]
            self._tap(bx, by, "mở Bản đồ lớn")
            self._sleep(c["open_map_s"])

    target: Optional[str] = None

    def _on_map(self, img, now):
        c = self.c
        vis = self.visible_plots(img)
        if c["test"]:
            self._update_from_map(img, vis)
            for s, (cx, cy, sc) in vis.items():
                self.log("INFO", f"[TEST] thấy {PLOT_NAME[s]} tại ({int(cx)},{int(cy)}) {sc:.2f} | vòng xanh={self.known[s].get('ours_ring')} "
                                 f"| ta {self.known[s].get('allies')} / địch {self.known[s].get('enemies')}")
            return img
        if not self.have_off or len(self.world) < len(PLOTS):
            if not self._localize(img, vis):
                if len(self.world) < len(PLOTS):
                    img = self.scan_map(img)
                    vis = self.visible_plots(img)
        self._localize(img, vis)
        self._update_from_map(img, vis)
        now = self._now()
        seq, score, first = self._decide(now)
        slug = seq[0] if seq else (self.target or PLOTS[-2][0])
        self.log("INFO", f"🎯 Chọn {PLOT_NAME[slug]} (chuỗi {[PLOT_NAME[s] for s in seq]} ~{score:.0f}đ)")
        if self.goto_and_tap(slug, img):
            self.cur = slug
            self.target = None
            self._sleep(c["enter_s"])
        return img


def run_auto_delivery_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy 1 bước `auto_delivery` (field xem mục 4 ở docstring đầu file)."""
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    tpl_dir = step.get("tpl_dir") or _tpl_dir_default()
    cfg = {k: step.get(k) for k in ("test", "max_seconds", "my_color", "capture_s", "enter_s", "open_map_s", "swipe_s",
                                    "arrive_margin_s", "seq_len", "horizon_s", "switch_gain", "min_stay_s", "hold_factor",
                                    "tap_dy", "bigmap_xy", "thr", "poll_s", "unknown_max", "debug")}
    bot = DeliveryBot(adb, load_templates(tpl_dir), log=log, should_stop=should_stop, **cfg)
    return bot.run()


# ----------------------------------------------------------------------------
# Công cụ dòng lệnh
# ----------------------------------------------------------------------------
def _cli_add(kind, img_path, x1, y1, x2, y2):
    valid = set(KINDS) | {"plot:" + s for s, _n, _l in PLOTS}
    if kind not in valid:
        sys.exit("loại phải là một trong: " + ", ".join(sorted(valid)))
    img = _imread(img_path)
    if img is None:
        sys.exit("không đọc được ảnh")
    x1, x2 = sorted((int(x1), int(x2)))
    y1, y2 = sorted((int(y1), int(y2)))
    crop = img[y1:y2, x1:x2]
    d = _tpl_dir_default()
    base = "delivery_plot_" + kind[5:] if kind.startswith("plot:") else "delivery_" + kind
    n = 1
    while os.path.exists(os.path.join(d, f"{base}_{n}.png")):
        n += 1
    p = os.path.join(d, f"{base}_{n}.png")
    _imwrite(p, crop)
    print("đã lưu", p, crop.shape[1], "x", crop.shape[0])


def _cli_check(img_path):
    img = _imread(img_path)
    if img is None:
        sys.exit("không đọc được ảnh")
    if img.shape[1] != REF_W:
        img = cv2.resize(img, (REF_W, REF_H))
    tpls = load_templates(_tpl_dir_default())

    class _A:
        pass
    bot = DeliveryBot(_A(), tpls, log=lambda lv, m: print(f"[{lv}] {m}"), test=True, map_file=os.devnull)
    st = bot.detect(img)
    print("trạng thái:", st)
    if st == "zone" or st == "dead":
        print("HUD:", read_hud(img))
    vis = bot.visible_plots(img)
    for s, (cx, cy, sc) in vis.items():
        hm = helmets_near(img, int(cx), int(cy))
        print(f"  ô {PLOT_NAME[s]:34s} ({int(cx)},{int(cy)}) {sc:.2f} vòng xanh={ring_is_blue(img, int(cx), int(cy))} mũ={hm}")


def _selftest():
    # 1) phaseCorrelate đúng chiều
    base = np.random.RandomState(1).randint(0, 255, (1280, 720, 3), np.uint8)
    base = cv2.GaussianBlur(base, (0, 0), 3)
    M = np.float32([[1, 0, 40], [0, 1, -30]])
    moved = cv2.warpAffine(base, M, (720, 1280), borderMode=cv2.BORDER_REFLECT)
    dx, dy, resp = measure_shift(base, moved)
    assert abs(dx - 40) < 4 and abs(dy + 30) < 4, (dx, dy)
    # 2) lập kế hoạch: 3 ô đang đếm (xong sau 20s / 10s / 4s), mỗi lần đi 3.5s
    cfg = dict(arrive_margin_s=1.0, capture_s=20.0, horizon_s=60.0, seq_len=3, hold_factor=0.05)
    known = {
        "lv3_toa_nha_ifc": {"done_at": 1020.0, "allies": 3},
        "lv2_cang_so": {"done_at": 1010.0, "allies": 3},
        "lv1_cho_cu": {"done_at": 1004.0, "allies": 3},
    }
    for sl, _n, _l in PLOTS:        # các ô khác đã là của ta -> không đáng đi
        known.setdefault(sl, {"ours_ring": True})
    seq, score, first = plan(1000.0, None, known, lambda a, b: 2.0, cfg)
    print("chuỗi:", seq, score)
    assert seq[:3] == ["lv1_cho_cu", "lv2_cang_so", "lv3_toa_nha_ifc"], seq
    # ô sắp xong (4s) mà đang đứng ở đó -> ở lại
    seq, score, first = plan(1000.0, "lv1_cho_cu", known, lambda a, b: 2.0, cfg)
    assert seq[0] == "lv1_cho_cu"
    # ô xa hơn thời gian còn lại bị loại
    known2 = {"lv1_cho_cu": {"done_at": 1003.0}, "lv3_toa_nha_ifc": {"done_at": 1040.0}}
    for sl, _n, _l in PLOTS:
        known2.setdefault(sl, {"ours_ring": True})
    seq, score, first = plan(1000.0, "lv3_toa_nha_ifc", known2, lambda a, b: 3.5, cfg)
    assert "lv1_cho_cu" not in seq, seq
    print("selftest OK")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
    elif a[0] == "--selftest":
        _selftest()
    elif a[0] == "--add" and len(a) == 7:
        _cli_add(*a[1:])
    elif a[0] == "--check" and len(a) == 2:
        _cli_check(a[1])
    else:
        _cli_check(a[0])

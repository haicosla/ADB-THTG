# -*- coding: utf-8 -*-
"""
Bot auto "Chụp Ảnh" (tiệm ảnh) - điều khiển qua ADB, dùng cho bước `auto_photo`.

Cơ chế game (suy từ ảnh chụp màn hình + PhotoQuestionDB.csv):
- Mỗi khách (25 mức = 5 phong cách x 5 mức) có 1 THANH ĐO nằm dưới ảnh preview, thang 0..20 điểm:
    * VÙNG VÀNG = khoảng điểm cần đạt, khớp cột `score` của CSV ("2|5", "6|9", "10|13", "14|17", "17|20");
      vạch đứng yên ở 0 khi chưa chọn gì. Khi vạch nằm TRONG vùng vàng thì vùng vàng SÁNG lên.
    * VẠCH CHỈ = điểm hình NỀN (bắt buộc) + điểm hình TRANG TRÍ (không bắt buộc).
- Có 12 hình Nền + 12 hình Trang Trí, mỗi loại là 1 dải cuộn ngang (kéo sang 2 bên), mỗi lần thấy 3 hình + 1 hình bị cắt.
- Điểm của 1 hình KHÁC NHAU theo từng khách/phong cách (cùng 1 hình có thể 3 điểm hoặc 5 điểm) nên KHÔNG thể ghi cứng
  bảng điểm: bot ĐO TRỰC TIẾP bằng cách bấm từng hình rồi đọc vị trí vạch chỉ.

Thuật toán (mỗi khách):
  1. Đọc vùng vàng [lo, hi] từ pixel thanh đo (không cần OCR).
  2. Đưa dải Nền về đầu, bấm lần lượt từng Nền, đọc điểm. Nền nào ĐƠN LẺ đã vào vùng vàng -> bấm "Chụp ảnh" luôn.
  3. Chưa có: giữ 1 Nền, bấm lần lượt từng Trang Trí, điểm trang trí = (vạch hiện tại - điểm nền). Gặp tổ hợp nền+trang trí
     (cộng điểm) vào vùng vàng thì chọn tổ hợp đó, kiểm lại bằng vạch THẬT rồi bấm "Chụp ảnh".
  4. Dự phòng: nếu cộng điểm không đúng (game có luật khác) thì thử lần lượt các cặp gần vùng vàng nhất.
Bảng điểm đo được ghi vào `photo_scores_log.jsonl` (mỗi khách 1 dòng) để sau này tối ưu/lưu sẵn bảng.

DÙNG LẠI DỮ LIỆU ĐÃ ĐO (bước 0, trước khi quét): đọc `photo_scores_log.jsonl`, lấy các lần ĐÃ THÀNH CÔNG cùng VÙNG VÀNG,
thử trước các tổ hợp (Nền[+Trang trí]) đã từng đúng - tổ hợp nào lặp lại nhiều lần / mới nhất / khớp số đo vừa đo thì thử trước,
kiểm lại bằng vạch THẬT (vào vùng vàng mới chụp). Sai hoặc chưa có dữ liệu thì chạy quy trình quét như cũ (số đã đo trong lúc thử được
dùng lại, không đo lại). Tắt bằng field `use_history=false`; giới hạn số tổ hợp thử bằng `hist_tries` (mặc định 6).
Lưu ý: điểm 1 hình phụ thuộc phong cách khách, mà màn hình chỉ cho biết vùng vàng (mức) nên 1 vùng vàng có thể ứng với nhiều khách khác nhau
-> dữ liệu chỉ là GỢI Ý, luôn kiểm lại bằng vạch thật.

Toạ độ tính theo màn hình DỌC 720x1280 (ảnh mẫu người dùng gửi), tự co giãn theo kích thước ảnh chụp thật.

Chạy riêng để kiểm tra nhận diện trên 1 ảnh chụp màn hình:  python photo_bot.py anh.png
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

# ----------------------------------------------------------------------------
# Hằng số hình học (đo trên ảnh 720x1280)
# ----------------------------------------------------------------------------
REF_W, REF_H = 720, 1280

BAR_X0 = 112.0                 # x của vạch khi 0 điểm
BAR_PX_PER_POINT = 24.65       # số px / 1 điểm (20 điểm = x 605)
BAR_MAX_SCORE = 20
BAR_ROWS_TOP = (708, 715)      # hàng pixel chỉ có nền thanh/vùng vàng (không dính chữ) - phía trên
BAR_ROWS_BOT = (726, 733)      # ... và phía dưới
BAR_X_RANGE = (100, 625)

DEFAULT_ZONES = [(2, 5), (6, 9), (10, 13), (14, 17), (17, 20)]   # cột `score` của CSV

LIST_X0 = 190.0                # tâm hình số 0 khi dải đang ở đầu
LIST_PITCH = 147.67            # khoảng cách tâm 2 hình liền kề
LIST_HALF_W = 63               # nửa bề rộng khung hình
LIST_HALF_H = 46               # nửa chiều cao khung hình
LIST_TAP_MIN, LIST_TAP_MAX = 183, 548   # tâm hình nằm trong khoảng này là thấy TRỌN hình -> bấm an toàn
LIST_STRIP_X = (120, 612)
LISTS = {
    "bg": {"cy": 871, "rows": (830, 912), "name": "Nền"},
    "deco": {"cy": 1032, "rows": (990, 1074), "name": "Trang trí"},
}
SHOOT_BTN = (355, 1141)        # nút "Chụp ảnh"
SWIPE_MAX = 300                # mỗi lần kéo tối đa (để 2 ảnh trước/sau vẫn còn chung nhau 1 đoạn đủ dò)


# ----------------------------------------------------------------------------
# 1) Nhận diện thanh đo
# ----------------------------------------------------------------------------
@dataclass
class BarState:
    zone_px: tuple          # (x0, x1) vùng vàng, toạ độ tham chiếu 720
    lo: int                 # điểm thấp nhất của vùng vàng
    hi: int                 # điểm cao nhất của vùng vàng
    marker_px: float        # x vạch chỉ (toạ độ tham chiếu), None nếu không thấy
    score: Optional[int]    # điểm hiện tại theo vạch (làm tròn), None nếu không thấy vạch
    active: bool            # vùng vàng đang SÁNG = vạch đang nằm trong vùng


def _runs(idx, gap=3):
    """Tách các đoạn liên tục (cho phép hở <= gap) trong mảng chỉ số đã sắp xếp."""
    runs = []
    if len(idx) == 0:
        return runs
    start = prev = int(idx[0])
    for v in idx[1:]:
        v = int(v)
        if v - prev > gap:
            runs.append((start, prev))
            start = v
        prev = v
    runs.append((start, prev))
    return runs


def load_zone_ranges(csv_path: Optional[str] = None):
    """Đọc các khoảng điểm hợp lệ (cột `score` dạng "2|5") từ PhotoQuestionDB.csv; không có file thì dùng mặc định."""
    paths = [csv_path] if csv_path else []
    paths += ["PhotoQuestionDB.csv", os.path.join("data", "PhotoQuestionDB.csv")]
    for p in paths:
        if not p or not os.path.isfile(p):
            continue
        try:
            zones = set()
            with open(p, "r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    sc = str(row.get("score", "")).strip()
                    if "|" in sc:
                        a, b = sc.split("|", 1)
                        zones.add((int(a), int(b)))
            if zones:
                return sorted(zones)
        except Exception:
            pass
    return list(DEFAULT_ZONES)


def detect_bar(frame, zones=None) -> Optional[BarState]:
    """Đọc vùng vàng + vạch chỉ từ 1 ảnh chụp màn hình (BGR). Trả None nếu không thấy thanh đo."""
    if frame is None or frame.ndim != 3:
        return None
    zones = zones or DEFAULT_ZONES
    h, w = frame.shape[:2]
    sx, sy = w / REF_W, h / REF_H
    xa, xb = int(BAR_X_RANGE[0] * sx), int(BAR_X_RANGE[1] * sx)

    top = frame[int(BAR_ROWS_TOP[0] * sy):int(BAR_ROWS_TOP[1] * sy), xa:xb].astype(np.int16)
    bot = frame[int(BAR_ROWS_BOT[0] * sy):int(BAR_ROWS_BOT[1] * sy), xa:xb].astype(np.int16)
    rows = np.concatenate([top, bot], axis=0)
    if rows.size == 0:
        return None
    b, g, r = rows[..., 0], rows[..., 1], rows[..., 2]
    orange = (r > 80) & (r - b > 45) & (r > g + 15)          # vùng vàng: cả lúc mờ (nâu) lẫn lúc sáng (cam)
    cols = np.where(orange.sum(0) >= max(4, rows.shape[0] // 2))[0]
    best = None
    for s, e in _runs(cols, gap=3):
        width = (e - s + 1) / sx
        if 50 <= width <= 100 and (best is None or e - s > best[1] - best[0]):
            best = (s, e)
    if best is None:
        return None
    zx0, zx1 = (best[0] + xa) / sx, (best[1] + xa) / sx

    lo = int(round((zx0 - BAR_X0) / BAR_PX_PER_POINT))
    hi = int(round((zx1 - BAR_X0) / BAR_PX_PER_POINT))
    # gắn về khoảng hợp lệ gần nhất (bù khi mép vùng vàng bị che)
    zbest = min(zones, key=lambda z: abs(z[0] - lo) + abs(z[1] - hi))
    if abs(zbest[0] - lo) + abs(zbest[1] - hi) <= 2:
        lo, hi = zbest

    band = frame[int(BAR_ROWS_TOP[0] * sy):int(BAR_ROWS_BOT[1] * sy), xa:xb].astype(np.int16)
    bright = (band[..., 2] > 215) & (band[..., 1] > 200) & (band[..., 0] > 140)
    mcols = np.where(bright.sum(0) >= max(6, int(band.shape[0] * 0.7)))[0]
    marker_px = None
    score = None
    mruns = _runs(mcols, gap=1)
    if mruns:
        s, e = mruns[0]
        marker_px = ((s + e) / 2.0 + xa) / sx
        score = int(round((marker_px - BAR_X0 - 0.3) / BAR_PX_PER_POINT))
        score = max(0, min(BAR_MAX_SCORE, score))

    zc = int((zx0 + zx1) / 2 * sx)
    zy = int(((BAR_ROWS_TOP[0] + BAR_ROWS_TOP[1]) / 2) * sy)
    active = bool(frame[zy, zc, 2] > 180)                     # kênh R của vùng vàng sáng ~230, mờ ~107
    return BarState((zx0, zx1), lo, hi, marker_px, score, active)


# ----------------------------------------------------------------------------
# 2) Dải hình cuộn ngang: đo độ trượt giữa 2 ảnh
# ----------------------------------------------------------------------------
def estimate_shift(before, after, expected=0.0, patch_w=130):
    """Dải trượt sang TRÁI bao nhiêu px giữa 2 ảnh xám (dương = nội dung trượt trái). Trả (shift, độ tin cậy 0..1)."""
    h, w = before.shape[:2]
    pw = min(int(patch_w), w // 2)
    if expected >= 25:
        xp = w - pw - 8
    elif expected <= -25:
        xp = 8
    else:
        xp = (w - pw) // 2
    patch = before[:, xp:xp + pw]
    if patch.std() < 6:
        return None, 0.0
    res = cv2.matchTemplate(after, patch, cv2.TM_CCOEFF_NORMED)[0]
    xa = int(res.argmax())
    return float(xp - xa), float(res[xa])


def bracket_score(frame, cx_ref, cy_ref):
    """Đếm điểm ảnh màu vàng của KHUNG GÓC bao quanh hình đang được chọn (nằm ngoài viền hình 1-10px).
    Hình được chọn ~140-160, không chọn = 0."""
    h, w = frame.shape[:2]
    sx, sy = w / REF_W, h / REF_H
    fr = frame.astype(np.int16)
    b, g, r = fr[..., 0], fr[..., 1], fr[..., 2]
    m = (r > 215) & (g > 190) & (b < 205) & ((g - b) > 30)
    X0, X1 = int((cx_ref - LIST_HALF_W - 10) * sx), int((cx_ref + LIST_HALF_W + 10) * sx)
    Y0, Y1 = int((cy_ref - LIST_HALF_H - 10) * sy), int((cy_ref + LIST_HALF_H + 10) * sy)
    x0, x1 = int((cx_ref - LIST_HALF_W - 1) * sx), int((cx_ref + LIST_HALF_W + 1) * sx)
    y0, y1 = int((cy_ref - LIST_HALF_H - 1) * sy), int((cy_ref + LIST_HALF_H + 1) * sy)
    X0, Y0 = max(0, X0), max(0, Y0)
    return int(m[Y0:Y1, X0:X1].sum() - m[y0:y1, x0:x1].sum())


class _Stop(Exception):
    pass


# ----------------------------------------------------------------------------
# 2b) Dữ liệu đã đo (photo_scores_log.jsonl)
# ----------------------------------------------------------------------------
def load_history(log_path, lo, hi, n_bg=12, n_deco=12, max_lines=3000):
    """Đọc các lần THÀNH CÔNG cùng vùng vàng [lo, hi] trong file log. Trả list dict (chỉ số 0-based):
    {"bg": Nền chọn, "deco": Trang trí chọn hoặc None, "bgs": {nền: điểm}, "dd": {trang trí: cộng thêm}, "t": thời điểm}.
    Dòng hỏng / khác vùng / không có lựa chọn (chỉ bấm Chụp ảnh) / chỉ số ngoài phạm vi thì bỏ qua; không có file -> []."""
    if not log_path or not os.path.isfile(log_path):
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-max_lines:]
    except OSError:
        return []

    def _tab(d, limit):
        out = {}
        for k, v in (d or {}).items():
            try:
                i, val = int(k) - 1, int(v)
            except (TypeError, ValueError):
                continue
            if 0 <= i < limit:
                out[i] = val
        return out

    recs = []
    for ln in lines:
        try:
            r = json.loads(ln)
            if not r.get("ok") or [int(x) for x in r.get("zone", [])] != [int(lo), int(hi)]:
                continue
            pick = r.get("pick") or {}
            if pick.get("bg") is None:
                continue
            bg = int(pick["bg"]) - 1
            deco = None if pick.get("deco") is None else int(pick["deco"]) - 1
            if not (0 <= bg < n_bg) or (deco is not None and not (0 <= deco < n_deco)):
                continue
            recs.append({"bg": bg, "deco": deco, "bgs": _tab(r.get("bg"), n_bg),
                         "dd": _tab(r.get("deco_delta"), n_deco), "t": str(r.get("t", ""))})
        except (ValueError, TypeError, AttributeError):
            continue
    return recs


def rank_history_picks(records, bg_meas, dd_meas, tried):
    """Xếp thứ tự các tổ hợp (nền, trang trí) đáng thử, tốt nhất trước. Loại bản ghi MÂU THUẪN với số vừa đo
    (cùng 1 khách thì cùng 1 hình phải ra cùng điểm). Thứ tự: số mục đo khớp nhiều hơn > lặp lại nhiều lần hơn > mới hơn.
    `tried` = tập (nền, trang trí) đã thử."""
    best = {}
    for r in records:
        if any(k in r["bgs"] and r["bgs"][k] != v for k, v in bg_meas.items()):
            continue
        if any(j in r["dd"] and r["dd"][j] != v for j, v in dd_meas.items()):
            continue
        key = (r["bg"], r["deco"])
        if key in tried:
            continue
        agree = sum(1 for k, v in bg_meas.items() if r["bgs"].get(k) == v) \
            + sum(1 for j, v in dd_meas.items() if r["dd"].get(j) == v)
        b = best.setdefault(key, [0, 0, ""])
        b[0] = max(b[0], agree)
        b[1] += 1
        b[2] = max(b[2], r["t"])
    order = sorted(best.items(), key=lambda kv: (-kv[1][0], -kv[1][1], _neg_str(kv[1][2])))
    return [k for k, _ in order]


def _neg_str(t):
    """Khoá sắp xếp giảm dần theo chuỗi thời gian (mới trước)."""
    return [-ord(c) for c in t]


# ----------------------------------------------------------------------------
# 3) Bot
# ----------------------------------------------------------------------------
class PhotoBot:
    def __init__(self, adb, log=None, should_stop=None, shoot=True, max_seconds=180,
                 n_bg=12, n_deco=12, log_path="photo_scores_log.jsonl", zones=None,
                 shoot_anyway=False, sleep=time.sleep, now=time.time,
                 use_history=True, hist_tries=6):
        self.adb = adb
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.should_stop = should_stop or (lambda: False)
        self.shoot = bool(shoot)
        self.max_seconds = float(max_seconds) if max_seconds else 0
        self.n = {"bg": int(n_bg), "deco": int(n_deco)}
        self.log_path = log_path
        self.zones = zones or load_zone_ranges()
        self.shoot_anyway = bool(shoot_anyway)
        self.sleep = sleep
        self.now = now
        self.sx = self.sy = 1.0
        self.off = {"bg": 0.0, "deco": 0.0}
        self.last_frame = None
        self.t0 = now()
        self.actions = 0
        self.use_history = bool(use_history)
        self.hist_tries = max(0, int(hist_tries))
        # Hình đang được chọn trên màn hình (đã đọc xác nhận qua vạch) + điểm trang trí đang cộng thêm
        self.sel_bg = None
        self.sel_deco = None
        self.sel_delta = 0

    # ---- tiện ích cấp thấp ----------------------------------------------
    def _check(self):
        if self.should_stop():
            raise _Stop("stop")
        if self.max_seconds and self.now() - self.t0 > self.max_seconds:
            raise _Stop("timeout")

    def _shot(self):
        for _ in range(3):
            frame = self.adb.screencap_fast()
            if frame is not None:
                h, w = frame.shape[:2]
                self.sx, self.sy = w / REF_W, h / REF_H
                self.last_frame = frame
                return frame
            self.sleep(0.3)
        raise RuntimeError("không chụp được màn hình")

    def _tap(self, x_ref, y_ref):
        self.actions += 1
        self.adb.tap_px(x_ref * self.sx, y_ref * self.sy)

    def _swipe(self, x1, y1, x2, y2, dur):
        self.actions += 1
        self.adb.swipe_px(x1 * self.sx, y1 * self.sy, x2 * self.sx, y2 * self.sy, dur)

    def _strip(self, frame, which):
        ya, yb = LISTS[which]["rows"]
        xa, xb = LIST_STRIP_X
        crop = frame[int(ya * self.sy):int(yb * self.sy), int(xa * self.sx):int(xb * self.sx)]
        return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

    def _settled_strip(self, which, tries=8):
        """Chụp liên tục tới khi dải hết trượt (quán tính) rồi trả ảnh xám của dải."""
        prev = self._strip(self._shot(), which)
        for _ in range(tries):
            self.sleep(0.18)
            cur = self._strip(self._shot(), which)
            if prev.shape == cur.shape and float(np.mean(np.abs(cur.astype(np.int16) - prev.astype(np.int16)))) < 1.2:
                return cur
            prev = cur
        return prev

    # ---- thanh đo ---------------------------------------------------------
    def read_bar(self, tries=14):
        """Đọc thanh đo, chờ vạch đứng yên (có thể đang chạy hiệu ứng)."""
        last = None
        bar = None
        for _ in range(tries):
            self._check()
            bar = detect_bar(self._shot(), self.zones)
            if bar is not None and bar.score is not None:
                if last is not None and abs(bar.marker_px - last) < 1.5:
                    return bar
                last = bar.marker_px
            self.sleep(0.18)
        return bar

    # ---- dải hình ----------------------------------------------------------
    def reset_left(self, which):
        """Kéo dải về ĐẦU (kéo sang phải tới khi không trượt nữa) -> offset = 0."""
        cy = LISTS[which]["cy"]
        prev = self._settled_strip(which)
        for _ in range(7):
            self._check()
            self._swipe(150, cy, 570, cy, 280)
            self.sleep(0.3)
            cur = self._settled_strip(which)
            if float(np.mean(np.abs(cur.astype(np.int16) - prev.astype(np.int16)))) < 2.0:
                self.off[which] = 0.0
                return True
            prev = cur
        self.off[which] = 0.0
        self.log("warn", f"📸 Dải {LISTS[which]['name']}: kéo về đầu 7 lần vẫn còn trượt - coi như đã ở đầu")
        return False

    def scroll_to(self, which, k, _depth=0):
        """Cuộn dải để hình k nằm trọn trong khung nhìn; trả toạ độ x (tham chiếu) của tâm hình, None nếu không được."""
        cy = LISTS[which]["cy"]
        for _ in range(12):
            self._check()
            cx = LIST_X0 + k * LIST_PITCH - self.off[which]
            if LIST_TAP_MIN <= cx <= LIST_TAP_MAX:
                return cx
            need = cx - 330.0
            d = max(-SWIPE_MAX, min(SWIPE_MAX, need))
            if abs(d) < 60:
                d = 60.0 if need > 0 else -60.0
            before = self._settled_strip(which)
            start = 560 if d > 0 else 160
            self._swipe(start, cy, start - d, cy, 650)
            self.sleep(0.3)
            after = self._settled_strip(which)
            shift, conf = estimate_shift(before, after, expected=d, patch_w=130 * self.sx)
            if shift is None or conf < 0.55:
                if _depth >= 2:
                    self.log("error", f"📸 Không đo được độ trượt dải {LISTS[which]['name']} (độ khớp {conf:.2f})")
                    return None
                self.log("warn", f"📸 Mất mốc dải {LISTS[which]['name']} (độ khớp {conf:.2f}) -> đồng bộ lại từ đầu")
                self.reset_left(which)
                return self.scroll_to(which, k, _depth + 1)
            shift = shift / self.sx
            self.off[which] += shift
            if abs(shift) < 8 and not (LIST_TAP_MIN <= LIST_X0 + k * LIST_PITCH - self.off[which] <= LIST_TAP_MAX):
                self.log("error", f"📸 Dải {LISTS[which]['name']} đã tới cuối nhưng chưa thấy hình {k + 1}")
                return None
        return None

    def tap_item(self, which, k):
        """Bấm hình thứ k (0..) của dải, đợi vạch đứng yên rồi trả BarState. Tự bấm lại 1 lần nếu rõ ràng chưa chọn được."""
        cx = self.scroll_to(which, k)
        if cx is None:
            return None
        cy = LISTS[which]["cy"]
        prev_score = self.cur_score
        self._tap(cx, cy)
        self.sleep(0.25)
        bar = self.read_bar()
        if bar is None or bar.score is None:
            return None
        sel = bracket_score(self.last_frame, cx, cy)
        if sel < 25 and bar.score == prev_score:
            self.log("warn", f"📸 {LISTS[which]['name']} {k + 1}: bấm chưa ăn (khung chọn={sel}) -> bấm lại")
            self.sleep(0.3)
            self._tap(cx, cy)
            self.sleep(0.25)
            bar = self.read_bar() or bar
        self.cur_score = bar.score
        if which == "bg":
            self.sel_bg = k
        else:
            self.sel_deco = k
        return bar

    # ---- logic chính --------------------------------------------------------
    def _ok(self, bar, lo, hi):
        return bar is not None and bar.score is not None and (lo <= bar.score <= hi or bar.active)

    def run(self):
        """Trả True nếu đã chọn được tổ hợp vào vùng vàng (và bấm Chụp ảnh nếu shoot=True)."""
        try:
            return self._run()
        except _Stop as e:
            self.log("warn", "📸 Auto Chụp Ảnh: dừng do " + ("hết thời gian giới hạn (max_seconds)" if str(e) == "timeout" else "người dùng bấm Dừng"))
            return False
        except Exception as e:  # không để lỗi làm sập cả kịch bản
            self.log("error", f"📸 Auto Chụp Ảnh: lỗi - {e}")
            return False

    def _finish(self, lo, hi, bg, deco, bg_scores, deco_delta, bar, how):
        names = f"Nền {bg + 1}" + (f" + Trang trí {deco + 1}" if deco is not None else " (không trang trí)")
        self.log("info", f"📸 ✅ {names} -> {bar.score} điểm, vùng vàng {lo}-{hi} ({how}); {self.actions} thao tác, {self.now() - self.t0:.0f}s")
        self._write_log(lo, hi, bg_scores, deco_delta, bg, deco, True)
        if self.shoot:
            self._tap(*SHOOT_BTN)
            self.sleep(0.5)
        else:
            self.log("info", "📸 [TEST] shoot=false: KHÔNG bấm nút Chụp ảnh")
        return True

    def _write_log(self, lo, hi, bg_scores, deco_delta, bg, deco, ok):
        if not self.log_path:
            return
        try:
            rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "zone": [lo, hi], "ok": ok,
                   "bg": {str(k + 1): v for k, v in sorted(bg_scores.items())},
                   "deco_delta": {str(k + 1): v for k, v in sorted(deco_delta.items())},
                   "pick": {"bg": None if bg is None else bg + 1, "deco": None if deco is None else deco + 1}}
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _run(self):
        bar0 = self.read_bar()
        if bar0 is None:
            self.log("error", "📸 Auto Chụp Ảnh: không thấy THANH ĐO (vùng vàng/vạch) - hãy mở màn hình chụp ảnh của khách trước bước này")
            return False
        lo, hi = bar0.lo, bar0.hi
        self.cur_score = bar0.score if bar0.score is not None else 0
        self.log("info", f"📸 Auto Chụp Ảnh: vùng vàng {lo}-{hi} điểm, vạch hiện {self.cur_score}")
        if bar0.active and (bar0.score or 0) > 0:
            self.log("info", "📸 Vạch đã nằm trong vùng vàng sẵn - chỉ bấm Chụp ảnh")
            return self._shoot_only(bar0)

        bg_scores, deco_delta = {}, {}
        cur_bg = None

        # --- Giai đoạn 0: thử trước các tổ hợp đã từng đúng (photo_scores_log.jsonl) ---
        if self._try_history(lo, hi, bg_scores, deco_delta):
            return True

        # --- Giai đoạn A: duyệt Nền, tìm nền ĐƠN LẺ đã vào vùng vàng ---
        self.reset_left("bg")
        for k in range(self.n["bg"]):
            if k in bg_scores and k != self.sel_bg and not (lo <= bg_scores[k] <= hi):
                continue        # đã đo ở bước dữ liệu có sẵn và nền đơn lẻ không vào vùng vàng -> khỏi bấm lại
            bar = self.read_bar() if k == self.sel_bg else self.tap_item("bg", k)
            if bar is None:
                self.log("warn", f"📸 Nền {k + 1}: không đọc được")
                continue
            bg_scores[k] = bar.score - self.sel_delta
            cur_bg = k
            self.log("info", f"📸 Nền {k + 1}: {bg_scores[k]} điểm")
            if self._ok(bar, lo, hi):
                return self._finish(lo, hi, k, self.sel_deco, bg_scores, deco_delta, bar, "nền đơn lẻ")
        if cur_bg is None and self.sel_bg is not None and self.sel_bg in bg_scores:
            cur_bg = self.sel_bg
        if cur_bg is None:
            self.log("error", "📸 Không đo được hình Nền nào")
            return False

        # --- Giai đoạn B: giữ 1 nền, duyệt Trang Trí ---
        base = cur_bg
        cur_deco = None
        self.reset_left("deco")
        for j in range(self.n["deco"]):
            bar = self.read_bar() if j == self.sel_deco else self.tap_item("deco", j)
            if bar is None:
                self.log("warn", f"📸 Trang trí {j + 1}: không đọc được")
                continue
            cur_deco = j
            deco_delta[j] = bar.score - bg_scores[base]
            self.log("info", f"📸 Trang trí {j + 1}: {deco_delta[j]:+d} điểm (vạch {bar.score})")
            if self._ok(bar, lo, hi):
                return self._finish(lo, hi, base, j, bg_scores, deco_delta, bar, "cộng điểm")
            # có nền khác cộng với trang trí này vào vùng vàng?
            for i, bs in sorted(bg_scores.items(), key=lambda kv: abs(kv[1] + deco_delta[j] - (lo + hi) / 2)):
                if i != base and lo <= bs + deco_delta[j] <= hi:
                    self.log("info", f"📸 Dự đoán Nền {i + 1} ({bs}) + Trang trí {j + 1} ({deco_delta[j]:+d}) = {bs + deco_delta[j]} -> thử")
                    b2 = self.tap_item("bg", i)
                    if b2 is not None and self._ok(b2, lo, hi):
                        return self._finish(lo, hi, i, j, bg_scores, deco_delta, b2, "cộng điểm")
                    if b2 is not None:
                        self.log("warn", f"📸 Thực tế ra {b2.score} (không cộng đúng như dự đoán) - bỏ qua")
                        base = i
                        bg_scores[i] = b2.score - deco_delta[j]
                    break

        # --- Dự phòng: thử các cặp gần vùng vàng nhất ---
        self.log("warn", "📸 Chưa thấy tổ hợp theo dự đoán - thử các cặp gần vùng vàng nhất")
        mid = (lo + hi) / 2
        near = (hi - lo) / 2.0 + 2          # chỉ thử cặp dự đoán lệch vùng vàng tối đa ~2 điểm, tối đa 8 cặp
        pairs = sorted((abs(bs + dd - mid), i, j) for i, bs in bg_scores.items() for j, dd in deco_delta.items()
                       if abs(bs + dd - mid) <= near)
        tries = 0
        for _, i, j in pairs[:8]:
            self._check()
            tries += 1
            b = self.tap_item("bg", i)
            d = self.tap_item("deco", j)
            if d is not None and self._ok(d, lo, hi):
                return self._finish(lo, hi, i, j, bg_scores, deco_delta, d, f"thử cặp lần {tries}")
        self._write_log(lo, hi, bg_scores, deco_delta, None, None, False)
        self.log("error", f"📸 ❌ Không tìm được tổ hợp vào vùng vàng {lo}-{hi} (nền: {bg_scores}, trang trí: {deco_delta})")
        if self.shoot_anyway and self.shoot:
            self._tap(*SHOOT_BTN)
            self.sleep(0.5)
        return False

    def _try_history(self, lo, hi, bg_scores, deco_delta):
        """Thử trước các tổ hợp đã từng đúng trong log cùng vùng vàng. True nếu đã chọn xong (và chụp nếu shoot=True).
        Số đo trong lúc thử (điểm nền, điểm cộng của trang trí) được ghi vào bg_scores/deco_delta để quy trình quét dùng lại."""
        if not self.use_history or self.hist_tries <= 0 or not self.log_path:
            return False
        recs = load_history(self.log_path, lo, hi, self.n["bg"], self.n["deco"])
        if not recs:
            self.log("info", f"📸 Chưa có dữ liệu đã đo cho vùng vàng {lo}-{hi} - quét như bình thường")
            return False
        n_pick = len({(r["bg"], r["deco"]) for r in recs})
        self.log("info", f"📸 Dữ liệu có sẵn: {len(recs)} lần thành công / {n_pick} tổ hợp cho vùng vàng {lo}-{hi} - thử trước (tối đa {self.hist_tries})")
        tried = set()
        for n in range(1, self.hist_tries + 1):
            self._check()
            order = rank_history_picks(recs, bg_scores, deco_delta, tried)
            if not order:
                break
            i, j = order[0]
            tried.add((i, j))
            nm = f"Nền {i + 1}" + (f" + Trang trí {j + 1}" if j is not None else "")
            self.log("info", f"📸 Thử theo dữ liệu #{n}: {nm}")
            bar = self.read_bar() if i == self.sel_bg else self.tap_item("bg", i)
            if bar is None or bar.score is None:
                self.log("warn", f"📸 Nền {i + 1}: không đọc được - bỏ qua")
                continue
            bg_scores[i] = bar.score - self.sel_delta       # điểm nền ĐƠN (trừ trang trí đang dính nếu có)
            if self._ok(bar, lo, hi):
                return self._finish(lo, hi, i, self.sel_deco, bg_scores, deco_delta, bar, f"theo dữ liệu có sẵn, lần thử {n}")
            if j is None:
                self.log("info", f"📸 Nền {i + 1}: {bar.score} điểm - không vào vùng vàng")
                continue
            if j == self.sel_deco:
                bar2 = bar                                      # đang chọn sẵn trang trí này (không bấm lại kẻo bị bỏ chọn)
            else:
                bar2 = self.tap_item("deco", j)
                if bar2 is None or bar2.score is None:
                    self.log("warn", f"📸 Trang trí {j + 1}: không đọc được - bỏ qua")
                    continue
            deco_delta[j] = bar2.score - bg_scores[i]
            self.sel_delta = deco_delta[j]
            self.log("info", f"📸 Nền {i + 1} ({bg_scores[i]}) + Trang trí {j + 1} ({deco_delta[j]:+d}) = vạch {bar2.score}")
            if self._ok(bar2, lo, hi):
                return self._finish(lo, hi, i, j, bg_scores, deco_delta, bar2, f"theo dữ liệu có sẵn, lần thử {n}")
        self.log("warn", "📸 Dữ liệu có sẵn không đúng với khách này - chạy kiểm lại (quét) như bình thường")
        return False

    def _shoot_only(self, bar):
        self._write_log(bar.lo, bar.hi, {}, {}, None, None, True)
        if self.shoot:
            self._tap(*SHOOT_BTN)
            self.sleep(0.5)
        return True


# ----------------------------------------------------------------------------
# Điểm nối thực thi bước `auto_photo` (logic_engine.py gọi)
# ----------------------------------------------------------------------------
def run_auto_photo_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """
    Field của bước (đều tuỳ chọn):
      shoot (true)        - false = CHẾ ĐỘ TEST: chọn xong vẫn KHÔNG bấm nút "Chụp ảnh"
      max_seconds (180)   - giới hạn thời gian cho 1 khách (0 = không giới hạn)
      n_bg / n_deco (12)  - số hình Nền / Trang trí
      log_path            - file ghi bảng điểm đo được (mặc định photo_scores_log.jsonl, "" = tắt)
      csv_path            - đường dẫn PhotoQuestionDB.csv (mặc định tự tìm ở thư mục chạy / data/)
      shoot_anyway (false)- không tìm được tổ hợp vẫn bấm Chụp ảnh
      use_history (true)  - thử trước các tổ hợp đã từng đúng trong log_path (cùng vùng vàng); sai/chưa có mới quét
      hist_tries (6)      - số tổ hợp tối đa thử theo dữ liệu có sẵn trước khi quét
    """
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    bot = PhotoBot(
        adb, log=log, should_stop=should_stop,
        shoot=step.get("shoot", True),
        max_seconds=step.get("max_seconds", 180),
        n_bg=step.get("n_bg", 12), n_deco=step.get("n_deco", 12),
        log_path=step.get("log_path", "photo_scores_log.jsonl"),
        zones=load_zone_ranges(step.get("csv_path")),
        shoot_anyway=step.get("shoot_anyway", False),
        use_history=step.get("use_history", True),
        hist_tries=step.get("hist_tries", 6),
    )
    return bot.run()


if __name__ == "__main__":
    # Kiểm tra nhận diện trên ảnh chụp màn hình: python photo_bot.py anh.png
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    img = cv2.imdecode(np.fromfile(sys.argv[1], dtype=np.uint8), cv2.IMREAD_COLOR)
    st = detect_bar(img, load_zone_ranges())
    if st is None:
        print("Không thấy thanh đo (vùng vàng) trong ảnh này.")
    else:
        print(f"Vùng vàng: {st.lo}-{st.hi} điểm | vạch: {st.score} điểm | vùng vàng sáng (đạt): {st.active}")

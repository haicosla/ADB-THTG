# -*- coding: utf-8 -*-
"""
Bot auto "Xem Quảng Cáo" (nhận vật phẩm bằng cách xem quảng cáo) - điều khiển qua ADB, dùng cho bước `auto_ads`.

>>> Bản 1 (28/10): CHƯA chạy thử trên LDPlayer thật. Đã kiểm bằng game giả (`python ads_bot.py --selftest`).
>>> Bot KHÔNG biết giao diện game của bạn: nó dùng ẢNH MẪU do bạn cắt (nút "Xem QC", nút X đóng, nút Nhận...). LẦN ĐẦU hãy chạy chế độ TEST.

======================================================================================================
1) CÁCH HOẠT ĐỘNG (mỗi vòng = 1 quảng cáo)
======================================================================================================
  a. Tìm nút "Xem quảng cáo" (mẫu `watch`) trên màn hình. Không thấy -> thử dọn popup (bấm `claim`/`close` nếu có) rồi dò lại vài lần;
     vẫn không thấy = hết lượt/hết QC hôm nay -> DỪNG. Thấy mẫu `limit` ("hết lượt", nút xám...) -> DỪNG ngay.
  b. Bấm nút, rồi chờ QC chạy, mỗi `poll_s` giây xem lại: (i) cửa sổ đang nhận phím có còn là game không (dumpsys window),
     (ii) có mẫu `unavail` (popup "chưa có QC, thử lại sau") không -> đóng rồi DỪNG luôn (mặc định `retry_max`=0; đặt >0 thì chờ `retry_wait_s` rồi thử lại tối đa chừng đó lần),
     (iii) có mẫu `claim` (nút Nhận thưởng) không -> bấm = XONG, (iv) có mẫu `close` (nút X / Bỏ qua / Tiếp tục của QC) không -> bấm.
  c. QC coi là XONG khi đã thấy rời game (đổi cửa sổ, hoặc nút xem biến mất) rồi quay lại màn game có nút xem; hoặc khi bấm được `claim`.
  c2. QC mở trang WEB / CH Play (cửa sổ chrome/vending/browser...): bấm BACK ngay (mỗi 2s), cứ 4 lần mà chưa về thì mở lại game.
      Không thấy nút xem khi đang ở trong QC/web = KHÔNG coi là hết lượt (cần mẫu `game` hoặc đọc được cửa sổ đang nhận phím).
      Cửa sổ nhận thưởng/xác nhận che màn (vd "Lợi nhuận offline" -> nút "Xác nhận") thì mẫu `claim` được bấm trước mọi thứ.
  c3. Không thấy nút xem còn bấm được ở màn game: cuộn danh sách theo `scroll_plan` (mặc định lên,xuống) rồi mới kết luận hết lượt.
  c4. QC ẨN nút đóng (phải chạm màn hình thì nút X mới hiện vài giây rồi ẩn lại): khi đang trong QC (cửa sổ khác game, hoặc QC cùng cửa sổ mà có mẫu `game`
      và không thấy mốc) bot chạm `reveal_taps` (mặc định giữa màn hình) rồi QUÉT NHANH mỗi `reveal_scan_s` giây trong `reveal_window_s` giây để bấm
      `close` kịp lúc X hiện; lặp mỗi `reveal_every_s` giây (tối đa `reveal_max` lần/QC); nếu chạm làm QC nhảy ra CH Play/web và phải BACK về thì ĐỢI `reveal_redirect_wait_s` (20s) tính từ lần BACK mới chạm tiếp. Cần có mẫu `close` (cắt lúc nút X đang hiện).
      Chạm vào QC có thể kích hoạt quảng cáo mở web/CH Play - bot sẽ BACK; không muốn chạm thì đặt reveal_taps = [].
  d. Kẹt (QC không có nút đóng): sau `back_after_s` giây bấm phím BACK (mỗi `back_every`s, tối đa `back_max` lần); sau `relaunch_after_s`
     giây mà vẫn đang ở app khác thì mở lại game (monkey). Có thể khai `corner_taps` (toạ độ tỉ lệ góc nơi hay có nút X) để bot thử bấm.
  e. Xong 1 QC: dọn các popup nhận thưởng còn lại, nghỉ `cooldown_s`, lặp. Dừng khi đủ `max_ads`, hết `max_seconds`, hết lượt, hoặc bấm Dừng.

======================================================================================================
2) ẢNH MẪU (thư mục templates/ads/, tên ads_<loại>_<số>.png; mỗi loại có thể nhiều file)
======================================================================================================
  watch   (BẮT BUỘC) nút xem QC. Nên cắt sát nút, kèm biểu tượng phim/tivi nếu có.
  close   nút X / "Bỏ qua" / "Skip" / "Tiếp tục" / "Đóng" của QC (thêm mẫu cho từng hãng QC hay gặp: mỗi hãng 1 kiểu X khác nhau).
  claim   nút "Nhận" / "Nhận thưởng" / "OK" / "Xác nhận" hiện sau khi xem xong.
  unavail popup "Chưa có quảng cáo" / "Thử lại sau" (không bắt buộc).
  limit   dấu hiệu HẾT LƯỢT của CẢ màn (vd chữ "5/5") (không bắt buộc; thấy là dừng hẳn).
  game    MỐC của màn game có nút xem (vd tiêu đề "Tiệm"). Có mốc này thì bot chỉ coi "hết lượt" khi đang THẤY mốc; đang trong QC/web/CH Play
          (không thấy mốc) thì bot chờ/đóng QC chứ KHÔNG dừng. Không có mốc thì dựa vào cửa sổ đang nhận phím (dumpsys). Khuyên có.
  disabled nút xem đã XÁM (hết lượt của dòng đó, vd "Còn: 0"): nút xem nào trùng vị trí mẫu này bị bỏ qua (không bắt buộc).
  Thêm mẫu từ ảnh chụp màn hình (toạ độ pixel):   python ads_bot.py --add watch anh.png x1 y1 x2 y2
  Cắt bằng LD Macro Studio rồi chép vào templates/ads/ đổi tên thành ads_<loại>_N.png cũng được.
  Xem cửa sổ đang nhận phím (để biết tên gói/activity của game & QC):   python ads_bot.py --focus
  Kiểm mẫu trên 1 ảnh chụp:   python ads_bot.py anh.png

  LƯU Ý: mẫu `close` chỉ bấm khi điểm khớp >= max(thr, close_thr=0.85); lúc dọn popup ở màn game (cửa sổ nhận phím vẫn là game) thì KHÔNG bấm `close`. Mẫu `close` được bấm trong lúc chờ QC nên đừng dùng mẫu X của 1 cửa sổ game khác
  mà bạn không muốn đóng. Nút X của QC mỗi hãng một kiểu, thường nằm góc trên phải/trái và HIỆN SAU vài giây - bot chờ và bấm khi thấy.

======================================================================================================
3) FIELD CỦA BƯỚC `auto_ads` (đều tuỳ chọn)
======================================================================================================
test (True = chỉ dò + báo, KHÔNG bấm; lưu ảnh debug_ads/), max_ads (0 = tới hết lượt; đặt nhanh bằng chuột phải vào bước trong GUI), max_seconds (0 = không giới hạn),
thr (0.80 độ khớp), match_mode ("gray" cho X/popup), watch_mode ("color": nút xem/xám phân biệt bằng màu),
watch_color_check (True: nút khớp mẫu `watch` mà bị XÁM màu = hết lượt, bỏ qua; mẫu `watch` phải là nút XANH/có màu), watch_color_ratio (0.5: độ bão hoà của chỗ khớp phải >= 50% của mẫu), close_thr (0.85: độ khớp TỐI THIỂU riêng cho mẫu `close`, chặt hơn thr để không bấm nhầm nút X/biểu tượng trong game), close_repeat (3: bấm `close` cùng 1 chỗ quá số lần này trong 1 lượt QC mà không ăn thì bỏ qua chỗ đó), scroll_plan (["up","down"]; [] = không cuộn), redirect_pkgs ([] gói thêm cần BACK ngay, ngoài chrome/vending/browser...), region ([x1,y1,x2,y2] tỉ lệ 0..1 chỉ để dò nút xem; None = cả màn),
tpl_dir ("templates/ads"), game_pkg ("" = lấy gói của cửa sổ đang nhận phím lúc bắt đầu - hãy để game ở màn có nút xem),
poll_s (1.0), start_wait_s (8: bấm xong mà 8s không thấy QC bắt đầu = coi là bấm hụt), ad_min_s (6), ad_max_s (120: tối đa chờ 1 QC),
quiet_s (4: QC cùng cửa sổ game, không thấy nút xem lẫn popup trong chừng này giây thì coi là xong - nút xem có thể ẩn vì hết lượt),
back_after_s (40), back_every (8), back_max (4), relaunch_after_s (75), corner_taps ([] ví dụ [[0.93,0.04],[0.07,0.04]]),
corner_after_s (25), corner_every (6), reveal_taps ([[0.5,0.5]] điểm chạm (tỉ lệ) để nút X hiện ra; nhiều điểm thì xoay vòng; [] = tắt), reveal_after_s (6), reveal_every_s (8), reveal_redirect_wait_s (20: bị đẩy ra CH Play/web rồi BACK về thì đợi chừng này giây mới chạm tiếp), reveal_max (15), reveal_window_s (3: sau mỗi lần chạm quét nhanh chừng này giây), reveal_scan_s (0.4), pre_tap_s (1.0: thấy nút xem thì ĐỢI chừng này giây, dò lại, rồi mới bấm đúng 1 lần), post_tap_s (5.0: bấm nút xem xong đợi ÍT NHẤT chừng này giây mới quét tiếp/bấm tiếp; hai lần bấm nút xem cũng cách nhau >= chừng này), cooldown_s (2), post_wait_s (3), find_tries (3), find_wait_s (2), retry_max (0: game báo chưa có QC = dừng luôn, không chờ/thử lại; đặt >0 để thử lại số lần đó),
retry_wait_s (30, chỉ dùng khi retry_max > 0), max_fail (4: số QC lỗi liên tiếp thì dừng), debug (False).
"""
import os
import re
import sys
import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    from adb_helper import _prep_for_mode, _match_map, normalize_match_mode
except Exception:  # chạy rời không có adb_helper -> dùng bản tối giản (chỉ chế độ xám)
    def normalize_match_mode(mode):
        return "gray"

    def _prep_for_mode(img, mode):
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    def _match_map(s_p, t_p, mode):
        return cv2.matchTemplate(s_p, t_p, cv2.TM_CCOEFF_NORMED)

KINDS = ("watch", "close", "claim", "unavail", "limit", "game", "disabled")
DEBUG_DIR = "debug_ads"


def _tpl_dir_default():
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "ads")
    return here if os.path.isdir(here) else os.path.join("templates", "ads")


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
    """Nạp mọi ads_<loại>*.png trong thư mục -> {loại: [(tên file, ảnh BGR), ...]}."""
    out: Dict[str, List[Tuple[str, np.ndarray]]] = {k: [] for k in KINDS}
    if not os.path.isdir(tpl_dir):
        return out
    for name in sorted(os.listdir(tpl_dir)):
        m = re.match(r"^ads_([a-z]+)(?:_[^.]*)?\.(png|jpg|jpeg|bmp)$", name, re.I)
        if not m or m.group(1).lower() not in out:
            continue
        img = _imread(os.path.join(tpl_dir, name))
        if img is not None and img.shape[0] >= 6 and img.shape[1] >= 6:
            out[m.group(1).lower()].append((name, img))
    return out


def match_one(screen, tpl, thr=0.80, region=None, mode="gray"):
    """Khớp 1 mẫu trên ảnh màn hình. Trả ((cx, cy) pixel hoặc None, điểm cao nhất)."""
    if screen is None or tpl is None:
        return None, 0.0
    mode = normalize_match_mode(mode)
    h, w = screen.shape[:2]
    x0 = y0 = 0
    sub = screen
    if region and len(region) == 4:
        x0 = max(0, min(w - 1, int(region[0] * w)))
        y0 = max(0, min(h - 1, int(region[1] * h)))
        x1 = max(x0 + 1, min(w, int(round(region[2] * w))))
        y1 = max(y0 + 1, min(h, int(round(region[3] * h))))
        sub = screen[y0:y1, x0:x1]
    s_p = _prep_for_mode(sub, mode)
    t_p = _prep_for_mode(tpl, mode)
    if s_p.shape[0] < t_p.shape[0] or s_p.shape[1] < t_p.shape[1]:
        return None, 0.0
    res = _match_map(s_p, t_p, mode)
    _, mx, _, loc = cv2.minMaxLoc(res)
    if mx >= thr:
        th, tw = t_p.shape[:2]
        return (x0 + loc[0] + tw // 2, y0 + loc[1] + th // 2), float(mx)
    return None, float(mx)


_FOCUS_RE = re.compile(r"([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)/([A-Za-z0-9_.$]+)")


def get_focus(adb) -> Tuple[Optional[str], Optional[str]]:
    """(gói, activity) của cửa sổ đang nhận phím; (None, None) nếu không đọc được (đang chuyển cảnh, popup hệ thống...)."""
    try:
        out = adb.run_cmd(["shell", "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'"], timeout=8)
    except Exception:
        return None, None
    txt = out.decode("utf-8", "ignore") if isinstance(out, (bytes, bytearray)) else str(out or "")
    for line in txt.splitlines():            # mCurrentFocus trước, mFocusedApp sau (thứ tự grep có thể khác)
        if "mCurrentFocus" in line:
            m = _FOCUS_RE.search(line)
            if m:
                return m.group(1), m.group(2)
    for line in txt.splitlines():
        if "mFocusedApp" in line:
            m = _FOCUS_RE.search(line)
            if m:
                return m.group(1), m.group(2)
    return None, None


REDIRECT_HINTS = ("com.android.vending", "chrome", "browser", "firefox", "opera", "sbrowser", "googlequicksearchbox", "play.google")


def match_all(screen, tpl, thr=0.80, region=None, mode="gray", max_n=8):
    """Mọi vị trí khớp của 1 mẫu (đã lọc trùng gần nhau): [(cx, cy, điểm), ...] theo điểm giảm dần."""
    if screen is None or tpl is None:
        return []
    mode = normalize_match_mode(mode)
    h, w = screen.shape[:2]
    x0 = y0 = 0
    sub = screen
    if region and len(region) == 4:
        x0 = max(0, min(w - 1, int(region[0] * w)))
        y0 = max(0, min(h - 1, int(region[1] * h)))
        x1 = max(x0 + 1, min(w, int(round(region[2] * w))))
        y1 = max(y0 + 1, min(h, int(round(region[3] * h))))
        sub = screen[y0:y1, x0:x1]
    s_p = _prep_for_mode(sub, mode)
    t_p = _prep_for_mode(tpl, mode)
    th, tw = t_p.shape[:2]
    if s_p.shape[0] < th or s_p.shape[1] < tw:
        return []
    res = _match_map(s_p, t_p, mode).copy()
    out = []
    for _ in range(max_n):
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx < thr:
            break
        out.append((x0 + loc[0] + tw // 2, y0 + loc[1] + th // 2, float(mx)))
        res[max(0, loc[1] - th // 2):loc[1] + th // 2 + 1, max(0, loc[0] - tw // 2):loc[0] + tw // 2 + 1] = -1.0
    return out


class AdsBot:
    def __init__(self, adb, templates, log=None, should_stop=None, now=time.time, sleep=time.sleep, **cfg):
        self.adb = adb
        self.tpls = templates
        self.log = log or (lambda level, msg: print(f"[{level}] {msg}"))
        self.should_stop = should_stop or (lambda: False)
        self._now = now
        self._sleep = sleep
        c = dict(test=True, max_ads=0, max_seconds=0, thr=0.80, match_mode="gray", watch_mode="color", region=None,
                 game_pkg="", poll_s=1.0, start_wait_s=8.0, ad_min_s=6.0, ad_max_s=120.0, quiet_s=4.0,
                 back_after_s=40.0, back_every=8.0, back_max=4, relaunch_after_s=75.0, corner_taps=[],
                 corner_after_s=25.0, corner_every=6.0, cooldown_s=2.0, post_wait_s=3.0, find_tries=3,
                 find_wait_s=2.0, retry_max=0, retry_wait_s=30.0, max_fail=2, debug=False,
                 scroll_plan=["up", "down"], redirect_pkgs=[],
                 watch_color_check=True, watch_color_ratio=0.5, close_thr=0.85, close_repeat=3,
                 pre_tap_s=1.0, post_tap_s=5.0,
                 reveal_taps=[[0.5, 0.5]], reveal_after_s=6.0, reveal_every_s=8.0, reveal_redirect_wait_s=20.0, reveal_max=15, reveal_window_s=3.0, reveal_scan_s=0.4)
        c.update({k: v for k, v in cfg.items() if v is not None})
        self.c = c
        self.game_pkg = c["game_pkg"] or ""
        self.watched = 0
        self.gray_seen = False
        self._last_tap = None                                  # thời điểm bấm nút xem QC gần nhất
        self._close_taps = {}                                  # {ô vị trí: số lần đã bấm `close` ở đó trong lượt QC hiện tại}
        self.stats = {"close": 0, "claim": 0, "back": 0, "relaunch": 0, "corner": 0, "redirect": 0, "scroll": 0, "reveal": 0}

    # ---------------- tiện ích ----------------
    def _L(self, msg, level="info"):
        self.log(level, f"[auto_ads] {msg}")

    def _shot(self):
        try:
            return self.adb.screencap_fast()
        except Exception:
            return None

    def _mode_of(self, kind):
        return self.c["watch_mode"] if kind in ("watch", "disabled") else self.c["match_mode"]

    def _find(self, scr, kind, region=None):
        """Mẫu tốt nhất của loại `kind` trên ảnh: (x, y, điểm, tên) hoặc None."""
        best = None
        for name, tpl in self.tpls.get(kind, []):
            pos, sc = match_one(scr, tpl, self.c["thr"], region, self._mode_of(kind))
            if pos and (best is None or sc > best[2]):
                best = (pos[0], pos[1], sc, name)
        return best

    def _find_close(self, scr):
        """Mẫu `close` (X/Bỏ qua của QC): CHẶT hơn các mẫu khác để không khớp nhầm nút X/biểu tượng trong game (vd cửa sổ chat ~0.74,
        màn thị trấn ~0.67): điểm phải >= max(thr, close_thr). Chỗ đã bấm `close_repeat` lần trong 1 lượt QC mà không ăn thì bỏ qua."""
        best = None
        thr = max(self.c["thr"], self.c["close_thr"])
        for name, tpl in self.tpls.get("close", []):
            pos, sc = match_one(scr, tpl, thr, None, self.c["match_mode"])
            if pos and (best is None or sc > best[2]):
                best = (pos[0], pos[1], sc, name)
        if best and self._close_taps.get((best[0] // 24, best[1] // 24), 0) >= self.c["close_repeat"]:
            return None
        return best

    def _count_close(self, hit):
        k = (hit[0] // 24, hit[1] // 24)
        self._close_taps[k] = self._close_taps.get(k, 0) + 1
        if self._close_taps[k] == self.c["close_repeat"]:
            self._L(f"đã bấm `close` {self.c['close_repeat']} lần tại ({hit[0]},{hit[1]}) mà không ăn - bỏ qua chỗ này (có thể không phải nút đóng QC)", "warn")

    @staticmethod
    def _mean_sat(img):
        return float(cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:, :, 1].mean())

    def _color_ok(self, scr, tpl, cx, cy):
        """Chỗ khớp có CÙNG MÀU với mẫu không? matchTemplate (kể cả chế độ 'color') gần như bỏ qua việc nút bị XÁM đi
        (cùng hình, cùng chữ, chỉ mất màu) nên nút xem xám (hết lượt) vẫn khớp mẫu nút xanh ~0.95. Mẫu có màu (độ bão hoà
        cao) mà vùng khớp gần như không có màu (xám) = nút đã bị vô hiệu -> không phải nút xem bấm được."""
        if not self.c["watch_color_check"]:
            return True
        th, tw = tpl.shape[:2]
        x0, y0 = int(cx - tw // 2), int(cy - th // 2)
        h, w = scr.shape[:2]
        if x0 < 0 or y0 < 0 or x0 + tw > w or y0 + th > h:
            return True
        s_tpl = self._mean_sat(tpl)
        if s_tpl < 40.0:                                       # mẫu vốn đã xám/ít màu (vd cắt nút xám làm mẫu `watch`) -> không so màu
            return True
        s_hit = self._mean_sat(scr[y0:y0 + th, x0:x0 + tw])
        return s_hit >= s_tpl * self.c["watch_color_ratio"]

    def _disabled_ok(self, scr, tpl, cx, cy):
        """Chỗ khớp mẫu `disabled` (nút xám) có THẬT SỰ xám như mẫu không? Cũng như nút xanh khớp nút xám, mẫu xám khớp ngược lại
        nút XANH còn lượt (~0.96-1.0) làm bot bỏ qua nút còn bấm được. Độ bão hoà của chỗ khớp phải gần mẫu `disabled`."""
        if not self.c["watch_color_check"]:
            return True
        th, tw = tpl.shape[:2]
        x0, y0 = int(cx - tw // 2), int(cy - th // 2)
        h, w = scr.shape[:2]
        if x0 < 0 or y0 < 0 or x0 + tw > w or y0 + th > h:
            return True
        return abs(self._mean_sat(scr[y0:y0 + th, x0:x0 + tw]) - self._mean_sat(tpl)) <= 30.0

    def _find_watch(self, scr):
        """Nút xem QC còn bấm được (loại nút bị XÁM màu và các nút trùng vị trí với mẫu `disabled` = hết lượt); lấy nút trên cùng."""
        reg, mode, thr = self.c["region"], self._mode_of("watch"), self.c["thr"]
        cands = []
        self.gray_seen = False
        for name, tpl in self.tpls.get("watch", []):
            for x, y, sc in match_all(scr, tpl, thr, reg, mode):
                if self._color_ok(scr, tpl, x, y):
                    cands.append((x, y, sc, name))
                else:
                    self.gray_seen = True                      # thấy nút xem nhưng đã xám = chắc chắn đang ở màn game có nút (hết lượt)
        dis = []
        for _n, tpl in self.tpls.get("disabled", []):
            dis += [(x, y) for x, y, _sc in match_all(scr, tpl, thr, reg, mode) if self._disabled_ok(scr, tpl, x, y)]
        cands = [k for k in cands if not any(abs(k[0] - dx) < 40 and abs(k[1] - dy) < 30 for dx, dy in dis)]
        cands.sort(key=lambda k: (k[1], k[0]))
        return cands[0] if cands else None

    def _tap(self, hit, why):
        self._L(f"bấm {why} ({hit[3]}, khớp {hit[2]:.2f}) tại ({hit[0]},{hit[1]})")
        self.adb.tap_px(hit[0], hit[1])

    def _save_debug(self, scr, tag):
        if scr is not None and (self.c["debug"] or self.c["test"] or tag.startswith("fail")):
            _imwrite(os.path.join(DEBUG_DIR, f"{time.strftime('%H%M%S')}_{tag}.png"), scr)

    def _wait(self, s):
        """Đợi s giây (ngắt được khi bấm Dừng). False nếu bị Dừng."""
        end = self._now() + max(0.0, float(s or 0))
        while self._now() < end:
            if self._stopped():
                return False
            self._sleep(min(0.5, max(0.0, end - self._now())))
        return not self._stopped()

    def _stopped(self):
        try:
            return bool(self.should_stop())
        except Exception:
            return False

    def _left_game(self, pkg):
        return bool(pkg and self.game_pkg and pkg != self.game_pkg)

    def _is_redirect(self, pkg):
        if not pkg:
            return False
        p = pkg.lower()
        return any(h in p for h in REDIRECT_HINTS) or pkg in (self.c["redirect_pkgs"] or [])

    def _in_game(self, scr, pkg):
        """Đang ở màn game? Có mẫu `game` (mốc của màn game, vd tiêu đề 'Tiệm') thì dựa vào mốc; không thì dựa vào cửa sổ đang nhận phím."""
        if self.tpls.get("game"):
            return bool(self._find(scr, "game"))
        return not self._left_game(pkg)

    def _relaunch(self):
        if not self.game_pkg:
            return
        self.stats["relaunch"] += 1
        self._L(f"mở lại game {self.game_pkg}", "warn")
        self.adb.run_cmd(["shell", "monkey", "-p", self.game_pkg, "-c", "android.intent.category.LAUNCHER", "1"], timeout=15)
        self._sleep(3.0)

    def _clear_popups(self, rounds=3):
        """Bấm nút nhận thưởng/đóng đang hiện (nếu có). True nếu đã bấm ít nhất 1 lần."""
        any_tap = False
        for _ in range(rounds):
            scr = self._shot()
            if scr is None:
                break
            hit = self._find(scr, "claim")
            kind = "nút nhận/xác nhận"
            if hit:
                self.stats["claim"] += 1
            else:
                # `close` là nút đóng của QC: chỉ bấm khi cửa sổ nhận phím KHÔNG còn là game (đang kẹt trong QC); ở màn game thì bỏ qua
                hit = self._find_close(scr) if self._left_game(get_focus(self.adb)[0]) else None
                kind = "nút đóng"
                if hit:
                    self.stats["close"] += 1
                    self._count_close(hit)
            if not hit:
                break
            self._tap(hit, kind)
            any_tap = True
            self._sleep(1.0)
        return any_tap

    def _ad_screen(self, scr, left, watch):
        """Đang ở màn QC (đáng chạm để hiện nút X)? Cửa sổ khác game = có; cùng cửa sổ thì phải có mẫu `game` mà KHÔNG thấy mốc."""
        if left:
            return True
        return (not watch) and bool(self.tpls.get("game")) and not self._find(scr, "game")

    def _reveal_close(self, scr, n):
        """QC ẩn nút X: chạm màn hình 1 cái rồi quét nhanh vài giây để bấm `close` lúc nó hiện. True nếu đã bấm được."""
        c = self.c
        pts = c["reveal_taps"]
        fx, fy = pts[n % len(pts)]
        h, w = scr.shape[:2]
        self.stats["reveal"] += 1
        self._L(f"QC ẩn nút đóng - chạm ({fx:.2f},{fy:.2f}) cho nút X hiện, quét nhanh {c['reveal_window_s']:.0f}s")
        self.adb.tap_px(fx * w, fy * h)
        t_end = self._now() + c["reveal_window_s"]
        while self._now() < t_end and not self._stopped():
            self._sleep(c["reveal_scan_s"])
            s2 = self._shot()
            if s2 is None:
                continue
            hit = self._find_close(s2)
            if hit:
                self.stats["close"] += 1
                self._count_close(hit)
                self._tap(hit, "nút đóng QC (vừa hiện)")
                self._sleep(1.0)
                return True
        return False

    def _scroll(self, plan_i):
        """Cuộn danh sách tìm nút xem ở chỗ khác. False nếu hết kế hoạch cuộn."""
        plan = self.c["scroll_plan"] or []
        if plan_i >= len(plan):
            return False
        w, h = int(self.adb.screen_w), int(self.adb.screen_h)
        if plan[plan_i] == "up":
            self.adb.swipe_px(w * 0.5, h * 0.75, w * 0.5, h * 0.45, 350)
        else:
            self.adb.swipe_px(w * 0.5, h * 0.45, w * 0.5, h * 0.75, 350)
        self.stats["scroll"] += 1
        self._L(f"không thấy nút xem - cuộn danh sách ({plan[plan_i]}) tìm tiếp")
        self._sleep(1.2)
        return True

    # ---------------- chờ 1 quảng cáo ----------------
    def _play_ad(self, resume=False, t0=None):
        """Sau khi đã bấm nút xem (resume=True: đang kẹt ở QC/web/CH Play từ trước, chỉ chờ quay về game).
        Trả 'ok' | 'unavail' | 'nostart' | 'stuck' | 'stop'."""
        c = self.c
        t0 = self._now() if t0 is None else t0                 # t0 = lúc BẤM nút xem (đã đợi post_tap_s trước khi vào đây)
        if not resume:
            self._close_taps = {}                              # lượt QC mới: tính lại số lần bấm `close`
        seen_ad = bool(resume)
        quiet_since = None
        last_back = t0
        last_rb = t0 - 10
        last_corner = t0
        last_reveal = t0
        no_reveal_until = t0                                   # sau khi bị đẩy ra CH Play/web + BACK: chưa chạm tiếp trước mốc này
        reveal_n = 0
        backs = rbacks = relaunched = 0
        while True:
            if self._stopped():
                return "stop"
            self._sleep(c["poll_s"])
            el = self._now() - t0
            if el > c["ad_max_s"]:
                self._L(f"QC quá {c['ad_max_s']:.0f}s chưa xong", "warn")
                return "stuck"
            pkg, _act = get_focus(self.adb)
            scr = self._shot()
            if scr is None:
                continue
            left = self._left_game(pkg)

            hit = self._find(scr, "unavail")
            if hit:
                self._L("game báo chưa có quảng cáo", "warn")
                cl = self._find_close(scr)
                self._tap(cl or hit, "nút đóng" if cl else "popup 'chưa có QC'")
                self._sleep(1.0)
                return "unavail"

            hit = self._find(scr, "claim")
            if hit and (seen_ad or el >= c["ad_min_s"]):
                self.stats["claim"] += 1
                self._tap(hit, "nút nhận thưởng/xác nhận")
                self._sleep(1.0)
                return "ok"

            # QC mở trang WEB / CH Play: bấm BACK ngay để quay lại (không đợi back_after_s)
            if left and self._is_redirect(pkg):
                seen_ad = True
                if self._now() - last_rb >= 2.0:
                    rbacks += 1
                    self.stats["redirect"] += 1
                    self._L(f"QC nhảy sang {pkg} - bấm BACK ({rbacks})", "warn")
                    self.adb.key_event("KEYCODE_BACK")
                    last_rb = self._now()
                    no_reveal_until = last_rb + c["reveal_redirect_wait_s"]
                    if rbacks % 4 == 0:
                        self._relaunch()
                continue
            rbacks = 0                                             # về lại QC rồi: đếm BACK liên tiếp bắt đầu lại (không mở lại game oan)

            watch = self._find_watch(scr)
            if left:
                seen_ad = True
            elif not watch:
                seen_ad = True                                     # nút xem biến mất mà vẫn ở cửa sổ game: QC cùng cửa sổ / popup
            if not seen_ad:
                if el >= c["start_wait_s"]:
                    return "nostart"
                continue

            hit = self._find_close(scr)
            if hit:
                self.stats["close"] += 1
                self._count_close(hit)
                self._tap(hit, "nút đóng QC")
                self._sleep(1.0)
                quiet_since = None
                continue

            if not left and watch and el >= min(c["ad_min_s"], 3.0):
                return "ok"                                        # đã về màn game, nút xem hiện lại
            if not left and not watch and self._in_game(scr, pkg):
                quiet_since = quiet_since or self._now()
                if el >= c["ad_min_s"] and self._now() - quiet_since >= c["quiet_s"]:
                    self._L("đã ở màn game, không còn nút xem bấm được (có thể đã hết lượt)")
                    return "ok"
            else:
                quiet_since = None                                 # chưa thấy màn game = vẫn đang trong QC, KHÔNG coi là xong

            # QC ẨN nút đóng: chạm màn hình cho nút X hiện vài giây rồi quét nhanh để bấm kịp
            if (c["reveal_taps"] and reveal_n < c["reveal_max"] and el >= c["reveal_after_s"]
                    and self._now() - last_reveal >= c["reveal_every_s"] and self._now() >= no_reveal_until
                    and self._ad_screen(scr, left, watch)):
                last_reveal = self._now()
                if self._reveal_close(scr, reveal_n):
                    quiet_since = None
                reveal_n += 1
                last_reveal = self._now()
                continue

            if left:
                if el >= c["back_after_s"] and backs < c["back_max"] and self._now() - last_back >= c["back_every"]:
                    self._L(f"QC không có nút đóng - bấm BACK ({backs + 1}/{c['back_max']})", "warn")
                    self.adb.key_event("KEYCODE_BACK")
                    backs += 1
                    self.stats["back"] += 1
                    last_back = self._now()
                if el >= c["relaunch_after_s"] and relaunched < 2:
                    self._relaunch()
                    relaunched += 1
                    backs = 0
            if c["corner_taps"] and el >= c["corner_after_s"] and self._now() - last_corner >= c["corner_every"]:
                last_corner = self._now()
                h, w = scr.shape[:2]
                for fx, fy in c["corner_taps"]:
                    self.adb.tap_px(fx * w, fy * h)
                self.stats["corner"] += 1
                self._L(f"thử bấm {len(c['corner_taps'])} góc tìm nút X")

    # ---------------- vòng chính ----------------
    def run(self):
        c = self.c
        if not self.tpls.get("watch"):
            self._L("THIẾU ảnh mẫu `watch` (nút xem quảng cáo) trong templates/ads/ads_watch_*.png - "
                    "xem docstring ads_bot.py mục 2 (python ads_bot.py --add watch anh.png x1 y1 x2 y2)", "error")
            return False
        if not self.game_pkg:
            self.game_pkg, _act = get_focus(self.adb)
            self.game_pkg = self.game_pkg or ""
            self._L(f"gói game: {self.game_pkg or '(không đọc được - chỉ dựa vào ảnh mẫu)'}")
        t_start = self._now()
        not_found = fails = retries = scroll_i = 0
        while not self._stopped():
            if c["max_ads"] and self.watched >= c["max_ads"]:
                self._L(f"đủ {self.watched} QC theo yêu cầu")
                break
            if c["max_seconds"] and self._now() - t_start > c["max_seconds"]:
                self._L("hết thời gian cho phép", "warn")
                break
            scr = self._shot()
            if scr is None:
                fails += 1
                if fails >= c["max_fail"]:
                    self._L("không chụp được màn hình", "error")
                    break
                self._sleep(1.0)
                continue
            if self._find(scr, "limit"):
                self._L("thấy dấu hiệu HẾT LƯỢT - dừng")
                break
            # cửa sổ nhận thưởng/xác nhận (vd "Lợi nhuận offline") che màn game: bấm trước, rồi mới dò nút xem
            pop = self._find(scr, "claim")
            if pop and not c["test"]:
                self.stats["claim"] += 1
                self._tap(pop, "cửa sổ xác nhận/nhận thưởng")
                self._sleep(1.0)
                continue
            pkg, _a = get_focus(self.adb)
            watch = self._find_watch(scr)
            if not watch:
                if c["test"]:
                    self._L("TEST: không thấy nút xem QC (còn bấm được) trên màn hình này", "warn")
                    self._save_debug(scr, "no_watch")
                    break
                if not self._in_game(scr, pkg) and not self.gray_seen:
                    # đang ở trong QC / web / CH Play / màn khác: KHÔNG coi là hết lượt, chờ quay về game
                    self._L(f"chưa ở màn game ({pkg or 'không rõ cửa sổ'}) - chờ/đóng QC rồi dò lại")
                    res = self._play_ad(resume=True)
                    if res == "stop":
                        break
                    if res != "ok":
                        fails += 1
                        self._save_debug(self._shot(), "fail_offgame")
                        if fails >= c["max_fail"]:
                            self._L("mãi không quay về được màn game - dừng (kiểm tra mẫu `game` hoặc tự đưa game về màn có nút xem)", "error")
                            break
                        self.adb.key_event("KEYCODE_BACK")
                        self._sleep(1.5)
                        if self._left_game(get_focus(self.adb)[0]):
                            self._relaunch()
                    continue
                if self.gray_seen and not_found == 0 and scroll_i == 0:
                    self._L("nút xem đã XÁM (hết lượt) - cuộn kiểm tra các dòng khác rồi dừng")
                if self._clear_popups():
                    not_found = 0
                    continue
                if self._scroll(scroll_i):
                    scroll_i += 1
                    continue
                not_found += 1
                if not_found >= c["find_tries"]:
                    self._L("đã ở màn game, cuộn hết vẫn KHÔNG còn nút xem QC bấm được - hết lượt, dừng", "warn")
                    self._save_debug(scr, "no_watch")
                    break
                self._sleep(c["find_wait_s"])
                continue
            not_found = scroll_i = 0
            if c["test"]:
                self._L(f"TEST: thấy nút xem QC ({watch[3]}, khớp {watch[2]:.2f}) tại ({watch[0]},{watch[1]}) - KHÔNG bấm")
                self._L(f"TEST: cửa sổ đang nhận phím: {pkg}; mốc màn game (mẫu `game`): "
                        f"{'thấy' if self._find(scr, 'game') else ('không thấy' if self.tpls.get('game') else 'chưa có mẫu')}")
                for k in ("close", "claim", "unavail", "limit", "disabled"):
                    h = self._find_close(scr) if k == "close" else self._find(scr, k)
                    if h:
                        self._L(f"TEST: cũng thấy mẫu `{k}` ({h[3]}, {h[2]:.2f}) trên màn này")
                vis = scr.copy()
                cv2.circle(vis, (watch[0], watch[1]), 30, (0, 255, 255), 3)
                self._save_debug(vis, "test_watch")
                return True
            # thấy nút xem: ĐỢI pre_tap_s, dò lại (nút còn đó/không bị cửa sổ khác che) rồi mới bấm ĐÚNG 1 lần;
            # hai lần bấm nút xem cách nhau >= post_tap_s; bấm xong đợi post_tap_s mới quét tiếp
            if not self._wait(c["pre_tap_s"]):
                break
            if self._last_tap is not None and not self._wait(c["post_tap_s"] - (self._now() - self._last_tap)):
                break
            scr2 = self._shot()
            watch2 = self._find_watch(scr2) if scr2 is not None else None
            if not watch2 or self._find(scr2, "claim"):
                self._L("sau khi đợi nút xem đã đổi/bị che - dò lại, chưa bấm")
                continue
            self._tap(watch2, "nút XEM QC (1 lần)")
            t_tap = self._now()
            self._last_tap = t_tap
            if not self._wait(c["post_tap_s"]):
                break
            res = self._play_ad(t0=t_tap)
            if res == "stop":
                break
            if res == "ok":
                self.watched += 1
                fails = retries = 0
                self._L(f"xong QC #{self.watched}")
                self._post_ad()
                self._sleep(c["cooldown_s"])
            elif res == "unavail":
                retries += 1
                if retries > c["retry_max"]:
                    self._L("game báo chưa có QC - dừng" if not c["retry_max"] else "game liên tục báo chưa có QC - dừng", "warn")
                    break
                self._L(f"chờ {c['retry_wait_s']:.0f}s rồi thử lại ({retries}/{c['retry_max']})")
                self._sleep(c["retry_wait_s"])
            else:                                                  # nostart / stuck
                fails += 1
                self._save_debug(self._shot(), f"fail_{res}")
                self._L(f"QC lỗi ({res}) lần {fails}/{c['max_fail']}", "warn")
                if res == "stuck":
                    self.adb.key_event("KEYCODE_BACK")
                    self._sleep(1.0)
                    if self._left_game(get_focus(self.adb)[0]):
                        self._relaunch()
                if fails >= c["max_fail"]:
                    self._L("quá nhiều lần lỗi liên tiếp - dừng", "error")
                    break
                self._sleep(2.0)
        self._L(f"KẾT THÚC: đã xem {self.watched} QC (bấm X {self.stats['close']}, nhận/xác nhận {self.stats['claim']}, "
                f"BACK {self.stats['back']}, nhảy web/CH Play {self.stats['redirect']}, mở lại game {self.stats['relaunch']}, "
                f"cuộn {self.stats['scroll']}, chạm hiện nút X {self.stats['reveal']})")
        return self.watched > 0

    def _post_ad(self):
        t_end = self._now() + self.c["post_wait_s"]
        while self._now() < t_end and not self._stopped():
            if not self._clear_popups(rounds=1):
                self._sleep(1.0)


def run_auto_ads_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy 1 bước `auto_ads` (field xem mục 3 ở docstring đầu file)."""
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    tpl_dir = step.get("tpl_dir") or _tpl_dir_default()
    cfg = {k: step.get(k) for k in ("test", "max_ads", "max_seconds", "thr", "match_mode", "watch_mode", "watch_color_check", "watch_color_ratio", "close_thr", "close_repeat",
                                    "scroll_plan", "redirect_pkgs", "region", "game_pkg", "poll_s",
                                    "start_wait_s", "ad_min_s", "ad_max_s", "quiet_s", "back_after_s", "back_every",
                                    "back_max", "relaunch_after_s", "corner_taps", "corner_after_s", "corner_every",
                                    "cooldown_s", "post_wait_s", "pre_tap_s", "post_tap_s", "reveal_taps", "reveal_after_s", "reveal_every_s", "reveal_redirect_wait_s", "reveal_max", "reveal_window_s", "reveal_scan_s", "find_tries", "find_wait_s", "retry_max", "retry_wait_s",
                                    "max_fail", "debug")}
    bot = AdsBot(adb, load_templates(tpl_dir), log=log, should_stop=should_stop, **cfg)
    return bot.run()


# ----------------------------------------------------------------------------
# Công cụ dòng lệnh + tự kiểm tra bằng game giả
# ----------------------------------------------------------------------------
def _cli_add(kind, img_path, x1, y1, x2, y2):
    if kind not in KINDS:
        sys.exit(f"loại phải là một trong {KINDS}")
    img = _imread(img_path)
    if img is None:
        sys.exit("không đọc được ảnh")
    x1, x2 = sorted((int(x1), int(x2)))
    y1, y2 = sorted((int(y1), int(y2)))
    crop = img[y1:y2, x1:x2]
    d = _tpl_dir_default()
    os.makedirs(d, exist_ok=True)
    n = 1
    while os.path.exists(os.path.join(d, f"ads_{kind}_{n}.png")):
        n += 1
    p = os.path.join(d, f"ads_{kind}_{n}.png")
    _imwrite(p, crop)
    print("đã lưu", p, crop.shape[1], "x", crop.shape[0])


def _cli_check(img_path):
    img = _imread(img_path)
    if img is None:
        sys.exit("không đọc được ảnh")
    tpls = load_templates(_tpl_dir_default())
    for k in KINDS:
        if not tpls[k]:
            print(f"{k:8s}: (chưa có mẫu)")
        for name, t in tpls[k]:
            pos, sc = match_one(img, t, 0.0)
            print(f"{k:8s}: {name:22s} điểm {sc:.3f} tại {pos}")


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def _selftest():
    """Game giả: nút xem -> QC (đổi cửa sổ) -> nút X hiện sau vài giây -> popup nhận -> về game; hết lượt thì nút biến mất."""
    import shutil
    import tempfile
    rng = np.random.RandomState(5)
    W, H = 360, 640

    def pattern(w, h, seed):
        r = np.random.RandomState(seed)
        small = (r.rand(h // 6 + 1, w // 6 + 1, 3) * 255).astype(np.uint8)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)

    P_WATCH, P_CLOSE, P_CLAIM, P_LIMIT = pattern(90, 36, 1), pattern(30, 30, 2), pattern(100, 40, 3), pattern(60, 30, 4)
    P_OFF, P_GAME = pattern(100, 40, 6), pattern(70, 30, 7)
    P_GRAYBTN = cv2.cvtColor(cv2.cvtColor(pattern(90, 36, 1), cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)   # nút xem XÁM (hết lượt)
    P_TINT = (P_GRAYBTN.astype(np.float32) * np.array([0.5, 1.0, 0.6], np.float32)).astype(np.uint8)    # CÙNG hình nhưng có màu xanh
    WATCH_AT, CLOSE_AT, CLAIM_AT = (200, 500), (330, 30), (180, 400)
    tmp = tempfile.mkdtemp()
    for k, p in (("watch", P_WATCH), ("close", P_CLOSE), ("claim", P_CLAIM), ("limit", P_LIMIT)):
        _imwrite(os.path.join(tmp, f"ads_{k}_1.png"), p)
    _imwrite(os.path.join(tmp, "ads_claim_2.png"), P_OFF)               # nút Xác nhận của cửa sổ lợi nhuận offline
    tmp_game = tempfile.mkdtemp()                                      # bộ mẫu có thêm mốc màn game
    for f in os.listdir(tmp):
        shutil.copy(os.path.join(tmp, f), tmp_game)
    _imwrite(os.path.join(tmp_game, "ads_game_1.png"), P_GAME)

    def paste(base, patt, cx, cy):
        h, w = patt.shape[:2]
        base[cy - h // 2:cy - h // 2 + h, cx - w // 2:cx - w // 2 + w] = patt

    class FakeAdb:
        def __init__(self, clock, ads_total, ad_len=12, x_after=5, has_x=True, same_activity=False, claim_popup=True,
                     redirect=False, offline=False, show_limit=True, gray_watch=False, tint_watch=False, x_dead=False, close_in_game=False,
                     dead_watch=False, hidden_x=False, touch_redirect=False):
            self.ck = clock
            self.screen_w, self.screen_h = W, H
            self.state = "game"
            self.t_state = clock.now()
            self.left = ads_total
            self.ad_len, self.x_after, self.has_x, self.same, self.claim_popup = ad_len, x_after, has_x, same_activity, claim_popup
            self.taps, self.keys, self.launched = [], [], 0
            self.ads_done = 0
            self.touch_redirect = touch_redirect              # chạm vào QC (không trúng X) -> nhảy ra CH Play
            self.hidden_x, self.last_touch = hidden_x, None      # hidden_x: nút X chỉ hiện 3s sau mỗi lần CHẠM màn hình
            self.dead_watch = dead_watch                       # bấm nút xem không ăn (QC không bắt đầu)
            self.tap_log = []                                  # [(giờ ảo, x, y, là bấm nút xem?)]
            self.redirect, self.offline, self.swipes, self.show_limit = redirect, offline, 0, show_limit
            self.x_dead, self.close_in_game = x_dead, close_in_game    # x_dead: bấm X không ăn; close_in_game: màn game có hình GIỐNG HỆT mẫu close
            self.tint_watch = tint_watch                       # nút xem XANH (P_TINT), có mẫu `disabled` xám cùng hình
            self.gray_watch = gray_watch                       # nút xem còn hiện nhưng đã XÁM (hết lượt) - bấm không ăn

        def _set(self, st):
            self.state, self.t_state = st, self.ck.now()

        def _tick(self):
            el = self.ck.now() - self.t_state
            if self.state == "ad" and el >= self.ad_len and self.has_x is False:
                pass                                            # QC không có X: chỉ BACK mới thoát

        def focus_pkg(self):
            if self.state == "ad" and not self.same:
                return "com.ads.sdk/com.ads.AdActivity"
            if self.state == "web":
                return "com.android.vending/com.android.vending.AssetBrowserActivity"
            return "com.game/com.game.Main"

        def run_cmd(self, args, timeout=None):
            if args[:2] == ["shell", "monkey"]:
                self.launched += 1
                if self.state == "ad":
                    self._set("game")
                return b""
            if args and "dumpsys" in " ".join(args):
                return f"  mCurrentFocus=Window{{abc u0 {self.focus_pkg()}}}\n".encode()
            return b""

        def _x_visible(self):
            return (not self.hidden_x) or (self.last_touch is not None and self.ck.now() - self.last_touch <= 3.0)

        def swipe_px(self, *a):
            self.swipes += 1

        def _finish(self):
            self.ads_done += 1
            self.left -= 1

        def key_event(self, k):
            self.keys.append(k)
            if k == "KEYCODE_BACK" and self.state == "web":
                self._set("ad")
                self.redirect_done = True
                return
            if k == "KEYCODE_BACK" and self.state == "ad":
                if self.ck.now() - self.t_state >= self.ad_len:
                    self._set("reward" if self.claim_popup else "game")
                    if not self.claim_popup:
                        self.ads_done += 1
                        self.left -= 1

        def screencap_fast(self):
            img = np.full((H, W, 3), 60, np.uint8)
            el = self.ck.now() - self.t_state
            if self.state == "game":
                paste(img, P_GAME, 180, 40)
                if self.gray_watch:
                    paste(img, P_GRAYBTN, *WATCH_AT)
                elif self.left > 0:
                    paste(img, P_TINT if self.tint_watch else P_WATCH, *WATCH_AT)
                elif self.show_limit:
                    paste(img, P_LIMIT, 100, 100)
                if self.close_in_game:
                    paste(img, P_CLOSE, *CLOSE_AT)
            elif self.state == "web":
                img[:] = 200
            elif self.state == "offline":
                paste(img, P_OFF, *CLAIM_AT)
            elif self.state == "ad":
                img[:] = 20 + int(el * 7) % 200
                if self.same and self.left > 0:
                    pass
                if self.has_x and el >= self.x_after and self._x_visible():
                    paste(img, P_CLOSE, *CLOSE_AT)
            elif self.state == "reward":
                paste(img, P_CLAIM, *CLAIM_AT)
            return img

        def tap_px(self, x, y):
            self.taps.append((int(x), int(y)))
            el = self.ck.now() - self.t_state
            is_watch = self.state == "game" and self.left > 0 and abs(x - WATCH_AT[0]) < 45 and abs(y - WATCH_AT[1]) < 18
            self.tap_log.append((self.ck.now(), int(x), int(y), is_watch))
            x_vis = self._x_visible()
            if self.state == "ad":
                self.last_touch = self.ck.now()
            if is_watch:
                if not self.dead_watch:
                    self._set("ad")
            elif self.state == "ad" and self.has_x and x_vis and not self.x_dead and el >= self.x_after and abs(x - CLOSE_AT[0]) < 15 and abs(y - CLOSE_AT[1]) < 15:
                if self.redirect and not getattr(self, "redirect_done", False):
                    self._set("web")                      # bấm trúng quảng cáo -> nhảy sang CH Play
                else:
                    self._set("reward" if self.claim_popup else "game")
                    if not self.claim_popup:
                        self._finish()
            elif self.state == "reward" and abs(x - CLAIM_AT[0]) < 50 and abs(y - CLAIM_AT[1]) < 20:
                if self.offline:
                    self._set("offline")
                else:
                    self._finish()
                    self._set("game")
            elif self.state == "offline" and abs(x - CLAIM_AT[0]) < 50 and abs(y - CLAIM_AT[1]) < 20:
                self._finish()
                self._set("game")
            elif self.state == "ad" and self.touch_redirect:
                self._set("web")

    def run(adb, **cfg):
        ck = adb.ck
        logs = []
        bot = AdsBot(adb, load_templates(tmp), log=lambda l, m: logs.append(m), now=ck.now, sleep=ck.sleep, test=False, **cfg)
        bot.run()
        return bot, logs

    try:
        # 1) 3 QC bình thường (có X + popup nhận) rồi hết lượt
        a = FakeAdb(_Clock(), ads_total=3)
        bot, logs = run(a)
        assert a.ads_done == 3 and bot.watched == 3, (a.ads_done, bot.watched, logs[-5:])
        assert a.left == 0 and a.keys == [], a.keys
        # 2) max_ads giới hạn
        a = FakeAdb(_Clock(), ads_total=5)
        bot, _ = run(a, max_ads=2)
        assert bot.watched == 2 and a.left == 3
        # 3) QC không có nút X: bot phải bấm BACK sau back_after_s rồi nhận thưởng
        a = FakeAdb(_Clock(), ads_total=1, has_x=False, ad_len=20)
        bot, logs = run(a, back_after_s=25)
        assert a.ads_done == 1 and "KEYCODE_BACK" in a.keys, (a.ads_done, a.keys, logs[-5:])
        # 3b) QC chạy NGAY TRONG cửa sổ game (focus không đổi), nút xem biến mất trong lúc chạy
        a = FakeAdb(_Clock(), ads_total=2, same_activity=True)
        bot, logs = run(a)
        assert a.ads_done == 2 and a.keys == [], (a.ads_done, a.keys, logs[-5:])
        # 3c) QC xong không có popup nhận: bấm X là về game
        a = FakeAdb(_Clock(), ads_total=2, claim_popup=False)
        bot, logs = run(a)
        assert a.ads_done == 2 and bot.watched == 2, (a.ads_done, bot.watched, logs[-5:])
        # 3d) QC bấm trúng nhảy sang CH Play: phải BACK ngay (không chờ 40s) và vẫn tính đủ QC
        a = FakeAdb(_Clock(), ads_total=2, redirect=True)
        bot, logs = run(a)
        assert a.ads_done == 2 and a.keys.count("KEYCODE_BACK") >= 1, (a.ads_done, a.keys, logs[-6:])
        assert a.ck.t < 1000 + 2 * 60, a.ck.t - 1000                    # không phải chờ back_after_s
        # 3e) sau mỗi QC có cửa sổ 'Lợi nhuận offline': bấm Xác nhận mới tính xong
        a = FakeAdb(_Clock(), ads_total=3, offline=True)
        bot, logs = run(a)
        assert a.ads_done == 3 and a.state == "game", (a.ads_done, a.state, logs[-6:])
        # 3f) CÓ mốc game: QC cùng cửa sổ chạy lâu (X hiện sau 15s) - không được coi là xong/hết lượt khi chưa thấy mốc game
        a = FakeAdb(_Clock(), ads_total=2, same_activity=True, ad_len=20, x_after=15)
        bot = AdsBot(a, load_templates(tmp_game), log=lambda l, m: None, now=a.ck.now, sleep=a.ck.sleep, test=False)
        bot.run()
        assert a.ads_done == 2 and bot.watched == 2, (a.ads_done, bot.watched)
        # 3g) hết lượt: cuộn danh sách trước khi kết luận, rồi dừng
        a = FakeAdb(_Clock(), ads_total=1, show_limit=False)
        bot = AdsBot(a, load_templates(tmp_game), log=lambda l, m: None, now=a.ck.now, sleep=a.ck.sleep, test=False)
        bot.run()
        assert a.ads_done == 1 and a.swipes >= 1
        # 3h) nút xem còn hiện nhưng đã XÁM (hết lượt): khớp mẫu nút xanh rất cao, bot phải bỏ qua, KHÔNG bấm
        tmp_g = tempfile.mkdtemp()
        _imwrite(os.path.join(tmp_g, "ads_watch_1.png"), P_TINT)
        a = FakeAdb(_Clock(), ads_total=3, gray_watch=True, show_limit=False)
        bot = AdsBot(a, load_templates(tmp_g), log=lambda l, m: None, now=a.ck.now, sleep=a.ck.sleep, test=False)
        bot.run()
        assert a.taps == [] and a.ads_done == 0 and bot.watched == 0, (a.taps, a.ads_done)
        # 3h2) nút xám + có mẫu game nhưng mốc game bị che: phải dừng nhanh, không chờ QC 120s
        a = FakeAdb(_Clock(), ads_total=3, gray_watch=True, show_limit=False)
        a.state = "game"
        bot = AdsBot(a, load_templates(tmp_g), log=lambda l, m: None, now=a.ck.now, sleep=a.ck.sleep, test=False)
        bot.tpls["game"] = [("g", pattern(70, 30, 99))]            # mốc không có trên màn -> trước đây rơi vào _play_ad chờ lâu
        bot.run()
        assert a.ck.t - 1000 < 60 and a.taps == [], (a.ck.t - 1000, a.taps)
        # 3h3) mẫu `disabled` (nút xám) KHÔNG được nuốt nút xem XANH cùng hình: nút xanh còn lượt vẫn phải được bấm
        tmp_h = tempfile.mkdtemp()
        for f in os.listdir(tmp):
            shutil.copy(os.path.join(tmp, f), tmp_h)
        _imwrite(os.path.join(tmp_h, "ads_watch_1.png"), P_TINT)
        _imwrite(os.path.join(tmp_h, "ads_disabled_1.png"), P_GRAYBTN)
        a = FakeAdb(_Clock(), ads_total=2, tint_watch=True)
        bot = AdsBot(a, load_templates(tmp_h), log=lambda l, m: None, now=a.ck.now, sleep=a.ck.sleep, test=False)
        bot.run()
        assert a.ads_done == 2 and bot.watched == 2, (a.ads_done, bot.watched)
        shutil.rmtree(tmp_h, ignore_errors=True)
        # 3i) tắt watch_color_check thì nút xám bị bấm như cũ (chứng tỏ ca 3h đúng là nhờ kiểm màu, không phải do không khớp mẫu)
        a = FakeAdb(_Clock(), ads_total=3, gray_watch=True, show_limit=False)
        bot = AdsBot(a, load_templates(tmp_g), log=lambda l, m: None, now=a.ck.now, sleep=a.ck.sleep, test=False,
                     watch_color_check=False, max_fail=1)
        bot.run()
        assert a.taps, "tắt kiểm màu mà vẫn không bấm nút xám?"
        shutil.rmtree(tmp_g, ignore_errors=True)
        # 3j) game báo 'chưa có QC': dừng luôn (không chờ retry_wait_s), không xem thêm
        tmp_u = tempfile.mkdtemp()
        for f in os.listdir(tmp):
            shutil.copy(os.path.join(tmp, f), tmp_u)
        _imwrite(os.path.join(tmp_u, "ads_unavail_1.png"), P_OFF)
        a = FakeAdb(_Clock(), ads_total=3)
        a.screencap_fast_orig = a.screencap_fast
        a.screencap_fast = lambda: (lambda im: (paste(im, P_OFF, 180, 300), im)[1])(a.screencap_fast_orig()) if a.state == "ad" else a.screencap_fast_orig()
        bot = AdsBot(a, load_templates(tmp_u), log=lambda l, m: None, now=a.ck.now, sleep=a.ck.sleep, test=False)
        bot.run()
        assert bot.watched == 0 and a.ck.t - 1000 < 25, (bot.watched, a.ck.t - 1000)
        shutil.rmtree(tmp_u, ignore_errors=True)
        # 3k) màn GAME có hình giống hệt mẫu close (nút X/biểu tượng của game): ở màn game KHÔNG được bấm close
        a = FakeAdb(_Clock(), ads_total=0, close_in_game=True, show_limit=False)
        bot = AdsBot(a, load_templates(tmp), log=lambda l, m: None, now=a.ck.now, sleep=a.ck.sleep, test=False)
        bot.run()
        assert not any(abs(x - CLOSE_AT[0]) < 15 and abs(y - CLOSE_AT[1]) < 15 for x, y in a.taps), a.taps
        # 3l) X của QC không ăn (hoặc khớp nhầm): chỉ bấm tối đa close_repeat lần rồi bỏ qua chỗ đó, không lặp mãi
        a = FakeAdb(_Clock(), ads_total=1, same_activity=True, x_dead=True, ad_len=30)
        bot = AdsBot(a, load_templates(tmp), log=lambda l, m: None, now=a.ck.now, sleep=a.ck.sleep, test=False, max_fail=1)
        bot.run()
        n_x = sum(1 for x, y in a.taps if abs(x - CLOSE_AT[0]) < 15 and abs(y - CLOSE_AT[1]) < 15)
        assert 1 <= n_x <= 3, n_x
        # 3i) đợi 1s trước khi bấm nút xem, bấm xong đợi >= 5s mới quét/bấm tiếp (kể cả nút bấm không ăn)
        a = FakeAdb(_Clock(), ads_total=3)
        t_begin = a.ck.now()
        bot, logs = run(a, ad_min_s=1.0)
        wt = [t for t, _x, _y, w in a.tap_log if w]
        assert len(wt) == 3 and wt[0] - t_begin >= 1.0, (wt, t_begin)
        for t_w in wt:                                                 # mọi cú bấm KHÁC (X, nhận...) cách lần bấm xem >= 5s
            assert not [1 for t, _x, _y, w in a.tap_log if not w and 0 <= t - t_w < 5.0], (t_w, a.tap_log)
        assert all(b - a_ >= 5.0 for a_, b in zip(wt, wt[1:])), wt
        a = FakeAdb(_Clock(), ads_total=3, dead_watch=True)
        bot, logs = run(a, max_fail=3)
        wt = [t for t, _x, _y, w in a.tap_log if w]
        assert len(wt) == 3 and all(b - a_ >= 5.0 for a_, b in zip(wt, wt[1:])), wt
        # 3j) max_ads = 1: đúng 1 lần xem
        a = FakeAdb(_Clock(), ads_total=5)
        bot, _ = run(a, max_ads=1)
        assert bot.watched == 1 and a.left == 4
        # 3k) QC ẨN nút X: phải chạm màn hình thì X hiện 3s rồi ẩn -> bot chạm rồi quét nhanh và bấm được X (không phải BACK)
        a = FakeAdb(_Clock(), ads_total=2, hidden_x=True, ad_len=60)
        bot, logs = run(a)
        assert a.ads_done == 2 and a.keys == [] and bot.stats["reveal"] >= 2, (a.ads_done, a.keys, bot.stats, logs[-6:])
        # 3l) reveal_taps=[] (tắt): không chạm gì thêm, X ẩn -> chỉ thoát bằng BACK sau back_after_s
        a = FakeAdb(_Clock(), ads_total=1, hidden_x=True, ad_len=20)
        bot, logs = run(a, reveal_taps=[], back_after_s=25)
        assert bot.stats["reveal"] == 0 and a.ads_done == 1 and "KEYCODE_BACK" in a.keys, (a.ads_done, a.keys, bot.stats)
        # 3m) chạm màn hình làm QC nhảy ra CH Play: BACK về rồi phải ĐỢI >= 20s mới chạm tiếp (không vào-ra liên tục)
        a = FakeAdb(_Clock(), ads_total=1, hidden_x=True, touch_redirect=True, ad_len=300)
        bot, logs = run(a, ad_max_s=70, max_fail=1)
        touches = [t for t, x, y, w in a.tap_log if (x, y) == (180, 320)]
        assert len(touches) >= 3 and all(b - a_ >= 20.0 for a_, b in zip(touches, touches[1:])), touches
        assert bot.stats["redirect"] >= 2 and a.launched <= 1, (bot.stats, a.launched)   # mỗi lần BACK đều về được QC; chỉ mở lại game 1 lần lúc kết thúc QC kẹt
        # 4) TEST: không bấm gì
        a = FakeAdb(_Clock(), ads_total=3)
        bot = AdsBot(a, load_templates(tmp), log=lambda l, m: None, now=a.ck.now, sleep=a.ck.sleep, test=True)
        assert bot.run() and a.taps == [] and a.ads_done == 0
        # 5) dừng giữa chừng
        a = FakeAdb(_Clock(), ads_total=10)
        n = {"i": 0}

        def stop():
            n["i"] += 1
            return n["i"] > 40
        bot = AdsBot(a, load_templates(tmp), log=lambda l, m: None, should_stop=stop, now=a.ck.now, sleep=a.ck.sleep, test=False)
        bot.run()
        assert 0 < a.ads_done < 10
        # 6) thiếu mẫu watch -> báo lỗi, không bấm
        empty = tempfile.mkdtemp()
        a = FakeAdb(_Clock(), ads_total=1)
        assert AdsBot(a, load_templates(empty), log=lambda l, m: None, now=a.ck.now, sleep=a.ck.sleep, test=False).run() is False and a.taps == []
        shutil.rmtree(empty, ignore_errors=True)
        shutil.rmtree(tmp_game, ignore_errors=True)
        print("selftest OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    av = sys.argv[1:]
    if av and av[0] == "--selftest":
        _selftest()
    elif av and av[0] == "--add" and len(av) == 7:
        _cli_add(av[1], av[2], *av[3:7])
    elif av and av[0] == "--focus":
        from adb_helper import ADBHelper
        _a = ADBHelper()
        print(get_focus(_a))
    elif len(av) == 1:
        _cli_check(av[0])
    else:
        print(__doc__)

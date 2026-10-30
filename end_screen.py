"""
end_screen.py - MÀN HÌNH KẾT THÚC (hết lượt / hết vé / hết thể lực...) DÙNG CHUNG cho MỌI bot auto_*.

Vấn đề: bot cứ thử đi tiếp (hoặc kẹt "không đi được") dù game đã hiện popup hết lượt (vd game 2048: cửa sổ "Cách Nhận" - Mứt Khô 0/1).
Cách làm: người dùng lưu ẢNH MẪU của màn hình/popup kết thúc vào `templates/end/`; mỗi lần bot chụp màn hình (`adb.screencap_fast()`),
module này so khớp ảnh với các mẫu - thấy mẫu nào thì bot KẾT THÚC (bot thoát vòng lặp như khi bấm Dừng, nhưng kịch bản vẫn đi tiếp bước kế).
Không sửa vòng lặp của từng bot: `run_bot_guarded()` bọc bot lại (xem logic_engine.py), chỉ cần thả ảnh mẫu vào thư mục.

1) ẢNH MẪU - thư mục `templates/end/` (cạnh file .py, hoặc theo thư mục chạy). Tên file quyết định bot nào dùng ảnh đó:
   <bot>_<số hoặc tên>.png        vd  merge2048_1.png, merge2048_het_luot.png, candy_2.png
   all_<...>.png                   dùng cho MỌI bot (vd popup "mất kết nối", "hết thể lực" chung)
   hoặc bỏ vào thư mục con         templates/end/<bot>/xxx.png   hoặc   templates/end/all/xxx.png
   (tiền tố "end_" thêm vào trước vẫn được: end_merge2048_1.png).
   <bot> là 1 trong: merge2048 (🧩 2048), photo (📸), thtg (⚔️ Ngưu Ma Vương), pig (🐷), xiangqi (♟️), animal (🦁), candy (🍪),
                     phs (📱), vohau (👑), upgrade (📈), ads (📺).
   Mẫu nên cắt từ ảnh chụp THÔ của giả lập (cùng độ phân giải với lúc bot chạy, vd 720x1280), chỉ lấy phần ĐẶC TRƯNG và ỔN ĐỊNH của
   màn hình kết thúc (tiêu đề "Cách Nhận" + khung vật phẩm "Mứt Khô 0/1"...), tránh vùng đổi theo ván (điểm số, hình nền động).
   Cắt nhanh:  python end_screen.py --add merge2048 anh.png x1 y1 x2 y2      (lưu thành templates/end/merge2048_N.png)
   Kiểm mẫu:   python end_screen.py anh.png [bot]                             (in độ khớp từng mẫu với ảnh)

2) FIELD của bước (đều tuỳ chọn, đặt trong bước auto_* tương ứng):
   end_screen (true)   - false = TẮT kiểm tra màn hình kết thúc cho bước này
   end_thr (0.85)      - ngưỡng khớp (0..1). Hạ xuống nếu mẫu không bắt được, nâng lên nếu bắt nhầm
   end_check_s (0.6)   - tối thiểu giây giữa 2 lần so khớp (bot chụp nhanh thì bỏ bớt cho nhẹ máy)
   end_idle_s (3.0)    - bot lâu không chụp (đang chờ/kẹt) thì tự chụp thêm 1 ảnh mỗi ngần này giây để kiểm (0 = tắt)
   end_confirm (2)     - số lần thấy LIÊN TIẾP mới coi là kết thúc (chống nháy); 1 = thấy 1 lần là dừng
   end_region          - [x1,y1,x2,y2] theo TỈ LỆ 0..1 của ảnh: chỉ so khớp trong vùng này (nhanh hơn, ít nhầm hơn)
   end_dir             - thư mục mẫu khác (mặc định templates/end)
   end_key             - dùng ảnh mẫu của bot khác (mặc định = bot đang chạy)

3) KẾT QUẢ: thấy màn hình kết thúc -> log "🏁 ..." -> bot thoát (kết thúc BÌNH THƯỜNG, không phải lỗi); kịch bản chạy tiếp bước sau
   (vd bước đóng popup / thoát game). Bot không có mẫu nào trong templates/end/ thì chạy y như cũ.

   python end_screen.py --selftest   (kiểm bằng game giả, không cần LDPlayer)
"""
import os
import sys
import time
import threading

import numpy as np
import cv2

KEYS = ("merge2048", "photo", "thtg", "pig", "xiangqi", "animal", "candy", "phs", "vohau", "upgrade", "ads")
_EXTS = (".png", ".jpg", ".jpeg", ".bmp")
_SCALE = 0.5            # so khớp trên ảnh thu nhỏ 1/2 cho nhanh (mẫu quá nhỏ thì giữ nguyên cỡ)
_warned = set()         # chỉ báo "chưa có ảnh mẫu" 1 lần mỗi bot / mỗi lần mở chương trình


def _dirs_default():
    out = []
    for p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "end"), os.path.join("templates", "end")):
        rp = os.path.realpath(p)
        if os.path.isdir(p) and rp not in [os.path.realpath(x) for x in out]:
            out.append(p)
    return out


def _stem_belongs(stem, key):
    """Tên file (không đuôi) có thuộc `key` không: key, key_xxx, key-xxx, key<số>; cho phép tiền tố end_."""
    s = stem.lower()
    if s.startswith("end_"):
        s = s[4:]
    k = key.lower()
    return s == k or s.startswith(k + "_") or s.startswith(k + "-") or (s.startswith(k) and s[len(k):].isdigit())


def _imread(path):
    try:
        return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


def list_template_files(key, tpl_dir=None):
    """[(tên hiển thị, đường dẫn)] các ảnh mẫu kết thúc dùng cho bot `key` (+ nhóm `all`)."""
    dirs = [tpl_dir] if tpl_dir else _dirs_default()
    found, seen = [], set()
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            full = os.path.join(d, name)
            if os.path.isdir(full):
                if name.lower() in (key.lower(), "all"):
                    for sub in sorted(os.listdir(full)):
                        if sub.lower().endswith(_EXTS):
                            found.append((name + "/" + sub, os.path.join(full, sub)))
                continue
            stem, ext = os.path.splitext(name)
            if ext.lower() in _EXTS and (_stem_belongs(stem, key) or _stem_belongs(stem, "all")):
                found.append((name, full))
    out = []
    for nm, fp in found:
        rp = os.path.realpath(fp)
        if rp not in seen:
            seen.add(rp)
            out.append((nm, fp))
    return out


class EndScreenDetector:
    """So khớp 1 ảnh chụp với các mẫu kết thúc của 1 bot."""

    def __init__(self, key, tpl_dir=None, thr=0.85, region=None):
        self.key = key
        self.thr = float(thr)
        self.region = self._norm_region(region)
        self.tpls = []          # [(tên, gray_đã_thu_nhỏ, scale)]
        for nm, fp in list_template_files(key, tpl_dir):
            img = _imread(fp)
            if img is None or img.size == 0:
                continue
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            sc = _SCALE if min(g.shape[:2]) * _SCALE >= 12 else 1.0
            if sc != 1.0:
                g = cv2.resize(g, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
            if float(g.std()) < 1.0:        # mẫu trơn 1 màu -> không so khớp được (NCC vô nghĩa)
                continue
            self.tpls.append((nm, g, sc))

    @staticmethod
    def _norm_region(region):
        try:
            x1, y1, x2, y2 = [float(v) for v in region]
            if 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1:
                return (x1, y1, x2, y2)
        except Exception:
            pass
        return None

    def available(self):
        return bool(self.tpls)

    def scores(self, frame):
        """[(tên mẫu, độ khớp)] cho mọi mẫu (cao nhất trước)."""
        if frame is None or not self.tpls:
            return []
        if self.region:
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = self.region
            frame = frame[int(y1 * h):int(y2 * h), int(x1 * w):int(x2 * w)]
        if frame.ndim == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        cache = {1.0: gray}
        res = []
        for nm, t, sc in self.tpls:
            if sc not in cache:
                cache[sc] = cv2.resize(gray, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
            g = cache[sc]
            if t.shape[0] > g.shape[0] or t.shape[1] > g.shape[1]:
                res.append((nm, 0.0))
                continue
            try:
                r = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED)
                mx = float(np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0).max())
            except Exception:
                mx = 0.0
            res.append((nm, mx))
        res.sort(key=lambda x: -x[1])
        return res

    def match(self, frame):
        """(tên mẫu, độ khớp) nếu khớp >= ngưỡng, ngược lại None."""
        sc = self.scores(frame)
        if sc and sc[0][1] >= self.thr:
            return sc[0]
        return None


class EndScreenGuard:
    """Gắn vào `adb.screencap_fast` (mỗi ảnh bot chụp được đem so khớp) và cung cấp `should_stop` mới (True khi đã thấy màn hình kết thúc)."""

    def __init__(self, adb, detector, should_stop=None, log=None, check_s=0.6, idle_s=3.0, confirm=2,
                 confirm_wait=0.4, now=time.monotonic, sleep=time.sleep):
        self.adb = adb
        self.det = detector
        self._user_stop = should_stop or (lambda: False)
        self.log = log or (lambda level, msg: print("[%s] %s" % (level, msg)))
        self.check_s = max(0.0, float(check_s))
        self.idle_s = max(0.0, float(idle_s))
        self.confirm = max(1, int(confirm))
        self.confirm_wait = max(0.0, float(confirm_wait))
        self.now = now
        self.sleep = sleep
        self.ended = False
        self.hit = None                     # (tên mẫu, độ khớp)
        self.last_frame = None
        self._last_check = -1e9
        self._lock = threading.Lock()
        self._orig = None
        self._had_attr = False
        self._orig_attr = None
        self._installed = False

    # ---- gắn / gỡ ------------------------------------------------------------------
    def install(self):
        if self._installed:
            return
        self._had_attr = "screencap_fast" in getattr(self.adb, "__dict__", {})
        self._orig_attr = self.adb.__dict__.get("screencap_fast") if self._had_attr else None
        self._orig = self.adb.screencap_fast
        self.adb.screencap_fast = self._cap
        self._installed = True

    def uninstall(self):
        if not self._installed:
            return
        try:
            if self._had_attr:
                self.adb.screencap_fast = self._orig_attr
            else:
                del self.adb.screencap_fast
        except Exception:
            pass
        self._installed = False

    # ---- chụp + kiểm ----------------------------------------------------------------
    def _cap(self):
        frame = self._orig()
        try:
            self._inspect(frame)
        except Exception as e:              # kiểm màn hình kết thúc KHÔNG BAO GIỜ được làm sập bot
            self.log("warn", "🏁 Lỗi kiểm màn hình kết thúc: %r" % (e,))
        return frame

    def _inspect(self, frame):
        if self.ended or frame is None:
            return
        t = self.now()
        if t - self._last_check < self.check_s:
            return
        if not self._lock.acquire(False):
            return
        try:
            self._last_check = t
            self.last_frame = frame
            hit = self.det.match(frame)
            if not hit:
                return
            for _ in range(self.confirm - 1):       # thấy LIÊN TIẾP đủ số lần mới tính (chống popup nháy qua)
                self.sleep(self.confirm_wait)
                f2 = self._orig()
                hit2 = self.det.match(f2) if f2 is not None else None
                if not hit2:
                    return
                hit = hit2
            self.hit = hit
            self.ended = True
            self.log("info", "🏁 Thấy màn hình KẾT THÚC (%s, khớp %.2f) -> bot dừng" % (hit[0], hit[1]))
        finally:
            self._last_check = self.now()
            self._lock.release()

    def should_stop(self):
        if self.ended:
            return True
        if self._user_stop():
            return True
        if self.idle_s > 0 and self._installed and self.now() - self._last_check >= self.idle_s:
            self._last_check = self.now()
            try:
                self._inspect_force()
            except Exception as e:
                self.log("warn", "🏁 Lỗi kiểm màn hình kết thúc: %r" % (e,))
        return self.ended

    def _inspect_force(self):
        """Bot lâu không chụp (đang chờ/kẹt) -> tự chụp 1 ảnh để kiểm."""
        saved = self.check_s
        self.check_s = 0.0
        try:
            self._inspect(self._orig())
        finally:
            self.check_s = saved


def run_bot_guarded(key, runner, adb, step, should_stop=None, log=None):
    """Chạy `runner(adb, step, should_stop=..., log=...)` (hàm run_auto_*_step) kèm kiểm màn hình kết thúc. Trả đúng giá trị của runner."""
    step = step if isinstance(step, dict) else {}
    log_f = log or (lambda level, msg: print("[%s] %s" % (level, msg)))
    if step.get("end_screen", True) is False:
        return runner(adb, step, should_stop=should_stop, log=log)
    k = str(step.get("end_key") or key)
    try:
        det = EndScreenDetector(k, tpl_dir=step.get("end_dir") or None, thr=step.get("end_thr", 0.85), region=step.get("end_region"))
    except Exception as e:
        log_f("warn", "🏁 Không nạp được ảnh mẫu kết thúc: %r - chạy như cũ" % (e,))
        return runner(adb, step, should_stop=should_stop, log=log)
    if not det.available():
        if k not in _warned:
            _warned.add(k)
            log_f("info", "🏁 Chưa có ảnh mẫu kết thúc cho '%s' (templates/end/%s_N.png) - bot chỉ tự dừng theo logic riêng" % (k, k))
        return runner(adb, step, should_stop=should_stop, log=log)
    guard = EndScreenGuard(adb, det, should_stop=should_stop, log=log_f,
                           check_s=step.get("end_check_s", 0.6), idle_s=step.get("end_idle_s", 3.0),
                           confirm=step.get("end_confirm", 2))
    try:
        guard.install()
    except Exception as e:
        log_f("warn", "🏁 Không gắn được kiểm màn hình kết thúc: %r - chạy như cũ" % (e,))
        return runner(adb, step, should_stop=should_stop, log=log)
    try:
        return runner(adb, step, should_stop=guard.should_stop, log=log)
    finally:
        guard.uninstall()
        if guard.ended and not (should_stop and should_stop()):
            log_f("info", "🏁 Bot đã kết thúc vì thấy màn hình kết thúc (%s) - kịch bản chạy tiếp bước sau" % (guard.hit[0],))


# ----------------------------------------------------------------------------------------------
# Công cụ dòng lệnh
# ----------------------------------------------------------------------------------------------
def add_template(key, img_path, x1, y1, x2, y2, tpl_dir=None):
    """Cắt vùng (pixel) của ảnh thành mẫu mới templates/end/<key>_N.png. Trả đường dẫn file."""
    img = _imread(img_path)
    if img is None:
        raise ValueError("không đọc được ảnh %s" % img_path)
    h, w = img.shape[:2]
    x1, x2 = sorted((max(0, int(x1)), min(w, int(x2))))
    y1, y2 = sorted((max(0, int(y1)), min(h, int(y2))))
    if x2 - x1 < 8 or y2 - y1 < 8:
        raise ValueError("vùng cắt quá nhỏ")
    d = tpl_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "end")
    os.makedirs(d, exist_ok=True)
    n = 1
    while os.path.exists(os.path.join(d, "%s_%d.png" % (key, n))):
        n += 1
    out = os.path.join(d, "%s_%d.png" % (key, n))
    ok, buf = cv2.imencode(".png", img[y1:y2, x1:x2])
    if not ok:
        raise ValueError("không ghi được ảnh")
    buf.tofile(out)
    return out


def _selftest():
    import tempfile
    import shutil

    rng = np.random.RandomState(7)
    tmp = tempfile.mkdtemp()
    try:
        d = os.path.join(tmp, "end")
        os.makedirs(d)
        game = (rng.rand(1280, 720, 3) * 60 + 100).astype(np.uint8)          # "màn game" nhiễu
        popup = (rng.rand(120, 400, 3) * 255).astype(np.uint8)               # "popup hết lượt"
        end_frame = game.copy()
        end_frame[500:620, 150:550] = popup
        buf = cv2.imencode(".png", popup)[1]
        buf.tofile(os.path.join(d, "merge2048_1.png"))
        buf.tofile(os.path.join(d, "all_x.png"))
        assert [n for n, _ in list_template_files("merge2048", d)] == ["all_x.png", "merge2048_1.png"]
        assert [n for n, _ in list_template_files("candy", d)] == ["all_x.png"]
        assert _stem_belongs("end_merge2048_3", "merge2048") and _stem_belongs("merge20481", "merge2048")
        assert not _stem_belongs("merge2048x", "merge2048") and not _stem_belongs("photo_1", "merge2048")

        det = EndScreenDetector("merge2048", tpl_dir=d)
        assert det.available()
        assert det.match(game) is None
        assert det.match(end_frame) is not None
        assert EndScreenDetector("merge2048", tpl_dir=d, region=(0.0, 0.0, 1.0, 0.3)).match(end_frame) is None   # popup nằm ngoài vùng
        assert EndScreenDetector("merge2048", tpl_dir=d, region=(0.0, 0.3, 1.0, 0.7)).match(end_frame) is not None

        class FakeAdb:
            def __init__(self, frames):
                self.frames, self.i = frames, 0

            def screencap_fast(self):
                f = self.frames[min(self.i, len(self.frames) - 1)]
                self.i += 1
                return f

        class Clock:
            t = 0.0

            def now(self):
                return self.t

            def sleep(self, s):
                self.t += s

        # 1) bot chụp liên tục: sau 5 ảnh game thì popup -> phải dừng, gỡ sạch hook
        ck, logs = Clock(), []
        adb = FakeAdb([game] * 5 + [end_frame] * 50)
        g = EndScreenGuard(adb, det, log=lambda l, m: logs.append(m), check_s=0.0, idle_s=0, confirm=2, now=ck.now, sleep=ck.sleep)
        g.install()
        shots = 0
        while not g.should_stop() and shots < 100:
            adb.screencap_fast()
            shots += 1
        g.uninstall()
        assert g.ended and shots < 12, (g.ended, shots)
        assert "screencap_fast" not in adb.__dict__ and any("KẾT THÚC" in m for m in logs)

        # 2) popup nháy 1 ảnh rồi biến mất -> KHÔNG dừng (confirm=2)
        ck = Clock()
        adb = FakeAdb([game, end_frame, game, game, game, game])
        g = EndScreenGuard(adb, det, log=lambda l, m: None, check_s=0.0, idle_s=0, confirm=2, now=ck.now, sleep=ck.sleep)
        g.install()
        for _ in range(5):
            adb.screencap_fast()
        g.uninstall()
        assert not g.ended

        # 3) bot KHÔNG chụp (kẹt) -> should_stop tự chụp mỗi idle_s giây
        ck = Clock()
        adb = FakeAdb([game, game, end_frame, end_frame])
        g = EndScreenGuard(adb, det, log=lambda l, m: None, check_s=0.0, idle_s=3.0, confirm=1, now=ck.now, sleep=ck.sleep)
        g.install()
        ck.t = 100.0
        assert g.should_stop() is False and adb.i == 1          # lần đầu: tự chụp 1 ảnh (game)
        assert g.should_stop() is False and adb.i == 1          # chưa tới 3s -> không chụp thêm
        ck.t += 3.1
        assert g.should_stop() is False and adb.i == 2
        ck.t += 3.1
        assert g.should_stop() is True and adb.i == 3           # thấy popup -> dừng
        g.uninstall()

        # 4) người dùng bấm Dừng vẫn được tôn trọng; run_bot_guarded trả đúng giá trị runner + gỡ hook
        ck = Clock()
        adb = FakeAdb([game] * 3 + [end_frame] * 50)
        calls = {"n": 0}

        def runner(a, step, should_stop=None, log=None):
            while not should_stop():
                a.screencap_fast()
                calls["n"] += 1
                if calls["n"] > 200:
                    return "timeout"
            return "done"

        step = {"end_dir": d, "end_check_s": 0, "end_idle_s": 0, "end_confirm": 1}
        assert run_bot_guarded("merge2048", runner, adb, step, should_stop=lambda: False, log=lambda l, m: None) == "done"
        assert calls["n"] < 10 and "screencap_fast" not in adb.__dict__
        # end_screen=false -> không kiểm
        adb = FakeAdb([end_frame] * 400)
        calls["n"] = 0
        assert run_bot_guarded("merge2048", runner, adb, dict(step, end_screen=False), should_stop=lambda: False, log=lambda l, m: None) == "timeout"
        # bot khác (candy) chỉ dùng mẫu `all_` -> popup giống cũng bắt; bot không có mẫu nào (thư mục rỗng) -> chạy như cũ
        empty = os.path.join(tmp, "empty")
        os.makedirs(empty)
        adb = FakeAdb([end_frame] * 400)
        calls["n"] = 0
        assert run_bot_guarded("candy", runner, adb, dict(step, end_dir=empty), should_stop=lambda: False, log=lambda l, m: None) == "timeout"
        # Dừng thủ công
        adb = FakeAdb([game] * 400)
        calls["n"] = 0
        assert run_bot_guarded("merge2048", runner, adb, step, should_stop=lambda: calls["n"] >= 3, log=lambda l, m: None) == "done" and calls["n"] == 3

        # 5) cắt mẫu bằng add_template
        p = os.path.join(tmp, "shot.png")
        cv2.imencode(".png", end_frame)[1].tofile(p)
        out = add_template("photo", p, 150, 500, 550, 620, tpl_dir=d)
        assert os.path.basename(out) == "photo_1.png" and EndScreenDetector("photo", tpl_dir=d).match(end_frame)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("end_screen selftest OK")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "--selftest":
        _selftest()
    elif a[0] == "--add" and len(a) >= 7:
        print("Đã lưu mẫu:", add_template(a[1], a[2], *[int(v) for v in a[3:7]]))
    else:
        im = _imread(a[0])
        if im is None:
            print("Không đọc được ảnh", a[0])
            sys.exit(1)
        for k in ([a[1]] if len(a) > 1 else KEYS):
            det = EndScreenDetector(k)
            if not det.available():
                continue
            print("== %s (ngưỡng %.2f)" % (k, det.thr))
            for nm, sc in det.scores(im):
                print("  %-30s %.3f %s" % (nm, sc, "<- KHỚP" if sc >= det.thr else ""))

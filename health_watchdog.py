"""
health_watchdog.py — Luồng GIÁM SÁT chạy nền song song với kịch bản, phát hiện 3 kiểu
"treo" mà adb vẫn trả lời bình thường (nên cơ chế timeout adb ở adb_helper.py không bắt được):

  1. "frozen"    - MÀN HÌNH ĐỨNG IM (so khung hình thu nhỏ liên tiếp, y hệt nhau suốt
                   `freeze_seconds`) -> game/giả lập đơ, không thao tác được gì.
  2. "left_game" - đang ở MÀN HÌNH CHÍNH LDPlayer (foreground là launcher) suốt
                   `left_game_seconds` -> game bị văng/crash ra ngoài.
  3. "anr"       - hộp thoại "Application Not Responding"/"Application Error" hiện suốt
                   `anr_seconds` -> game đơ/crash có hộp thoại.

Phát hiện xong gọi `adb.mark_hung(lý_do, kind)`: LogicEngine._should_stop() thấy cờ `hung`
sẽ dừng kịch bản, Dashboard (dashboard_run.py::_exec_entry -> _recover_hung_emulator) tự
phục hồi (mở lại game, hoặc khởi động lại giả lập) rồi chạy lại Hoạt Động từ đầu.

Cũng tự HỌC package của game (app foreground không phải launcher/hệ thống) để biết mở lại
game bằng gì; có thể đặt cứng bằng data/dashboard_settings.json -> "watchdog.game_package".

KHÔNG BAO GIỜ ném lỗi ra ngoài luồng (mọi lỗi được nuốt, luồng cứ chạy tiếp).
"""
import re
import threading
import time

import cv2
import numpy as np

DEFAULT_CFG = {
    "enabled": True,
    "freeze_seconds": 180,       # màn hình y hệt nhau liên tục ngần này giây -> coi là đơ
    "left_game_seconds": 25,     # ở màn hình chính LDPlayer ngần này giây -> coi là văng game
    "anr_seconds": 15,           # hộp thoại ANR/crash hiện ngần này giây -> coi là lỗi app
    "sample_seconds": 5,         # chu kỳ chụp khung hình để so sánh
    "foreground_seconds": 8,     # chu kỳ hỏi app đang ở foreground (dumpsys window)
    "game_package": "",          # để trống = tự học; điền cứng vd "com.abc.game" nếu tự học sai
}

# Hai khung hình thu nhỏ có sai khác trung bình (thang 0..255) <= ngưỡng này = "y hệt nhau".
STILL_DIFF = 0.8
_THUMB_SIZE = (48, 80)  # (w, h) ảnh thu nhỏ để so sánh

_FOCUS_RE = re.compile(r"mCurrentFocus=Window\{[0-9a-fA-F]+ u\d+ ([^}]*)\}")
_ERROR_TITLES = ("Application Not Responding", "Application Error", "isn't responding", "has stopped")
# Package KHÔNG coi là "game" khi tự học (launcher/hệ thống/bàn phím/Play Services của LD).
_NOT_GAME_PREFIXES = ("com.android.", "android", "com.google.android.", "com.ldmnq", "com.ld.", "com.microvirt")


def parse_focus(text):
    """Từ nội dung `dumpsys window` -> (package | None, tiêu_đề_cửa_sổ | None).
    Không thấy mCurrentFocus hoặc =null (đang chuyển cảnh) -> (None, None)."""
    m = _FOCUS_RE.search(text or "")
    if not m:
        return None, None
    title = m.group(1).strip()
    pkg = title.split("/")[0].strip() if "/" in title else None
    return pkg, title


def is_error_dialog(title):
    return bool(title) and any(t.lower() in title.lower() for t in _ERROR_TITLES)


def is_launcher(pkg):
    return bool(pkg) and "launcher" in pkg.lower()


def is_game_candidate(pkg):
    return bool(pkg) and not is_launcher(pkg) and not pkg.startswith(_NOT_GAME_PREFIXES)


class HealthWatchdog:
    def __init__(self, adb, cfg=None, log=None, suspended=None, game_pkg=None, on_learn=None):
        """adb: ADBHelper của giả lập đang chạy. log(level, msg). suspended() -> True khi người
        dùng đang TẠM DỪNG (không đếm giờ). game_pkg() -> package game đã biết (None nếu chưa).
        on_learn(pkg) được gọi khi tự học được package game mới."""
        self.adb = adb
        self.cfg = dict(DEFAULT_CFG)
        self.cfg.update(cfg or {})
        self._log = log or (lambda lvl, msg: None)
        self._suspended = suspended or (lambda: False)
        self._game_pkg = game_pkg or (lambda: None)
        self._on_learn = on_learn
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._paused = 0
        self._gen = 0          # tăng mỗi lần reset() - bỏ kết quả của lượt kiểm tra đã cũ
        self._clear_state()
        self._last_screen = 0.0
        self._last_fg = 0.0

    # ---------- vòng đời ----------
    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="HealthWatchdog", daemon=True)
            self._thread.start()
        return self

    def stop(self):
        self._stop.set()

    def pause(self):
        """Tạm ngưng giám sát (đang chạy Tự Login/đăng nhập/phục hồi giả lập...). Có đếm lồng nhau."""
        with self._lock:
            self._paused += 1
            self._gen += 1
            self._clear_state()

    def resume(self):
        with self._lock:
            self._paused = max(0, self._paused - 1)
            self._gen += 1
            self._clear_state()

    def reset(self):
        """Xoá mọi mốc thời gian (vd sau khi vừa khởi động lại giả lập)."""
        with self._lock:
            self._gen += 1
            self._clear_state()

    def _clear_state(self):
        self._prev = None
        self._still_since = None
        self._launcher_since = None
        self._anr_since = None
        self._cand_pkg = None
        self._cand_count = 0

    # ---------- vòng lặp ----------
    def _run(self):
        while not self._stop.wait(1.0):
            try:
                if self._paused or getattr(self.adb, "hung", False):
                    continue
                if self._suspended():
                    self.reset()
                    continue
                now = time.time()
                gen = self._gen
                if now - self._last_screen >= float(self.cfg["sample_seconds"]):
                    self._last_screen = now
                    self._check_screen(gen)
                if now - self._last_fg >= float(self.cfg["foreground_seconds"]):
                    self._last_fg = now
                    self._check_foreground(gen)
            except Exception:
                pass  # tuyệt đối không để luồng giám sát chết/gây lỗi cho kịch bản

    def _flag(self, gen, kind, reason):
        if gen != self._gen or self._paused or getattr(self.adb, "hung", False):
            return
        self._log("error", f"🧊 Watchdog: {reason}")
        self.adb.mark_hung(reason, kind)

    # ---------- 1) màn hình đứng im ----------
    def _check_screen(self, gen):
        img = self.adb.screencap_fast()  # tự ghi nhận thất bại vào sức khoẻ adb nếu chụp lỗi
        if img is None:
            return
        small = cv2.resize(img, _THUMB_SIZE, interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.int16)
        now = time.time()
        prev = self._prev
        self._prev = gray
        if prev is None or float(np.abs(gray - prev).mean()) > STILL_DIFF:
            self._still_since = None
            return
        if self._still_since is None:
            self._still_since = now - float(self.cfg["sample_seconds"])
        elapsed = now - self._still_since
        if elapsed >= float(self.cfg["freeze_seconds"]):
            self._flag(gen, "frozen", f"màn hình ĐỨNG IM {int(elapsed)}s liên tục (game/giả lập đơ)")

    # ---------- 2) văng game / ANR ----------
    def _check_foreground(self, gen):
        out = self.adb.run_cmd(["shell", "dumpsys", "window"], timeout=12)
        pkg, title = parse_focus(out.decode("utf-8", errors="ignore") if out else "")
        if title is None:
            return  # đang chuyển cảnh/không đọc được - bỏ qua mẫu này
        now = time.time()

        if is_error_dialog(title):
            if self._anr_since is None:
                self._anr_since = now
            elif now - self._anr_since >= float(self.cfg["anr_seconds"]):
                self._flag(gen, "anr", f"hộp thoại lỗi app hiện {int(now - self._anr_since)}s ('{title[:60]}')")
            return
        self._anr_since = None

        if is_launcher(pkg):
            if self._launcher_since is None:
                self._launcher_since = now
            elif now - self._launcher_since >= float(self.cfg["left_game_seconds"]):
                self._flag(gen, "left_game",
                           f"đang ở màn hình chính LDPlayer ({pkg}) {int(now - self._launcher_since)}s - game đã bị văng")
            return
        self._launcher_since = None

        # Tự học package game: cùng 1 app (không phải launcher/hệ thống) thấy 2 mẫu liên tiếp.
        if not str(self.cfg.get("game_package") or "").strip() and is_game_candidate(pkg):
            if pkg == self._cand_pkg:
                self._cand_count += 1
            else:
                self._cand_pkg, self._cand_count = pkg, 1
            if self._cand_count >= 2 and pkg != self._game_pkg() and self._on_learn:
                try:
                    self._on_learn(pkg)
                except Exception:
                    pass

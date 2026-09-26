# -*- coding: utf-8 -*-
"""
turbo_engine.py - ĐỘNG CƠ CỦA "CHẾ ĐỘ SIÊU TỐC" (turbo).

Chỉ được gọi khi 1 bước bật step["turbo"] = True (xem adb_helper.py:
_get_turbo_engine / turbo_poll_* / screencap_turbo / tap_turbo_px và
logic_engine.py: _poll_single_template / _poll_any_template). Mọi bước KHÔNG
bật Siêu Tốc vẫn chạy đúng đường cũ, không đụng tới file này.

Khác gì so với bản socket-PNG trước đó (vẫn được giữ nguyên làm phương án dự
phòng trong adb_helper.py)?

1) CHỤP: dùng `screencap` KHÔNG có -p (RAW framebuffer) qua socket thẳng tới
   ADB server -> bỏ hẳn bước nén PNG trên máy ảo + giải nén PNG ở PC. Chỉ
   chuyển màu (RGBA->xám/BGR) trên VÙNG QUÉT (region), không phải cả màn hình.
   Header raw 12 hay 16 byte tự suy ra từ kích thước dữ liệu (không đoán theo
   bản Android); không hợp lệ -> tự rơi về PNG qua socket.
2) QUÉT SONG SONG (pipeline): N luồng chụp (mặc định 2, lệch nhịp nhau) chạy
   liên tục, luồng so khớp luôn lấy khung MỚI NHẤT chưa xử lý -> KHÔNG còn
   chu kỳ "chụp -> so khớp -> ngủ -> chụp lại" và KHÔNG còn time.sleep(
   scan_interval). Khung giống hệt khung trước (trong vùng quét) bị bỏ qua,
   không tốn matchTemplate. Nếu chụp RAW dùng được, ưu tiên dùng KÊNH THƯỜNG
   TRỰC (_PersistentCapture, mục 2b) thay cho pipeline N luồng này.
2b) KÊNH CHỤP THƯỜNG TRỰC (chỉ khi RAW dùng được): mỗi lần trước đây phải
   MỞ KẾT NỐI ADB MỚI + máy ảo phải SPAWN TIẾN TRÌNH `screencap` MỚI cho
   MỖI khung hình (dù đã bỏ nén PNG) - đây là nguồn chính gây thời gian
   truyền dao động thất thường giữa các khung (đặc biệt khi 2 luồng cùng mở
   kết nối song song, tranh nhau tài nguyên phía máy ảo). Kênh thường trực
   mở 1 shell DUY NHẤT, gửi lệnh lặp `while true; do screencap; done` chạy
   ngay trong máy ảo, rồi đọc liên tục các khung có kích thước CỐ ĐỊNH nối
   tiếp nhau trên CÙNG 1 socket - chỉ mất chi phí mở kết nối ĐÚNG 1 LẦN cho
   TOÀN BỘ 1 lượt quét (1 lần gọi turbo_poll_single/_any), không phải mỗi
   khung. Chỉ áp dụng cho việc quét-tìm-ảnh-để-click của Siêu Tốc (mở khi
   _poll() bắt đầu, đóng khi _poll() kết thúc) - KHÔNG đụng tới các đường
   chụp ảnh khác (screencap_turbo() dùng ngoài lúc quét vẫn theo đường cũ).
   Lỗi/mất đồng bộ (đối chiếu kích thước+định dạng từng khung với khung đầu
   tiên) -> tự đóng kênh, rơi về pipeline N luồng (mục 2) cho phần còn lại.
3) CLICK: mở SẴN 1 shell thường trực (`exec:sh`) rồi gửi cả chuỗi
   sendevent (chạm xuống + nhả) trong 1 lần ghi -> bỏ chi phí khởi động Java
   của `input tap` (thường 100ms+). Tự dò thiết bị cảm ứng (dùng lại
   _detect_touch_device của adb_helper), tự kiểm tra quyền ghi; nếu không
   dùng được thì tự rơi về `input tap` như cũ. Giữa chạm xuống và nhả ra có
   1 khoảng nghỉ ngắn (mặc định 20ms, xem THTG_TURBO_TAP_HOLD_MS) để tạo ra
   1 cú chạm có THỜI LƯỢNG thật thay vì tức thời (0ms) - nhiều driver cảm
   ứng ảo/app coi chạm tức thời là nhiễu và không dispatch thành 2 sự kiện
   ACTION_DOWN/ACTION_UP tách biệt.

Điều chỉnh (biến môi trường, đặt trước khi chạy chương trình):
  THTG_TURBO_TAP          = auto (mặc định) | sendevent | input   (input = tắt sendevent)
  THTG_TURBO_WORKERS      = 1..3 (mặc định 2) - số luồng chụp song song
                            (CHỈ áp dụng khi kênh thường trực KHÔNG dùng
                            được - xem THTG_TURBO_CAP_PERSIST)
  THTG_TURBO_RAW          = 1 (mặc định) | 0  (0 = luôn dùng PNG qua socket)
  THTG_TURBO_TAP_HOLD_MS  = 0..500 (mặc định 20) - độ trễ giữa chạm xuống/
                            nhả ra khi click qua sendevent (xem tap())
  THTG_TURBO_CAP_PERSIST  = 1 (mặc định) | 0  (0 = tắt kênh chụp thường
                            trực mục 2b, luôn dùng pipeline N luồng cũ)
"""
import os
import re
import socket
import struct
import sys
import threading
import time

import cv2
import numpy as np

DEFAULT_TAP_MODE = "auto"
DEFAULT_WORKERS = 2
DEFAULT_RAW = True
# Khoảng nghỉ giữa "chạm xuống" (down) và "nhả ra" (up) khi click qua
# sendevent - xem THTG_TURBO_TAP_HOLD_MS bên dưới. Trước đây down+up gửi
# LIỀN MẠCH trong cùng 1 lần ghi, tức 1 cú chạm có thời lượng ~0ms; nhiều
# driver cảm ứng ảo / app coi đó là nhiễu và KHÔNG dispatch thành 2 sự kiện
# ACTION_DOWN/ACTION_UP tách biệt -> sendevent báo ghi thành công nhưng
# click không có tác dụng thật trên giả lập.
DEFAULT_TAP_HOLD_MS = 20

_MIN_DIM = 16
_MAX_DIM = 10000
_FAIL_RE = re.compile(rb"THTG_FAIL:(\d+)")

# _PersistentCapture: nếu 1 khung đọc được KHÔNG khớp header hợp lệ (lệch
# byte), thay vì bỏ cuộc ngay (coi cả kênh là hỏng), thử PHỤC HỒI đồng bộ
# bằng cách trượt cửa sổ tìm header hợp lệ kế tiếp trong dữ liệu đang có +
# đọc thêm từ socket - tối đa bấy nhiêu LẦN kích thước 1 khung trước khi
# thật sự bỏ cuộc (tránh treo vô hạn nếu kênh hỏng thật).
_RESYNC_MAX_FRAMES = 2

_TO_GRAY = {"rgba": cv2.COLOR_RGBA2GRAY, "bgra": cv2.COLOR_BGRA2GRAY, "bgr": cv2.COLOR_BGR2GRAY}
_TO_BGR = {"rgba": cv2.COLOR_RGBA2BGR, "bgra": cv2.COLOR_BGRA2BGR}


class TurboUnavailable(Exception):
    """Động cơ không chạy được -> nơi gọi tự rơi về đường cũ."""


class TurboFrame(object):
    __slots__ = ("arr", "kind", "t0", "t1", "seq")

    def __init__(self, arr, kind, t0, t1):
        self.arr = arr      # (h, w, 4) RGBA/BGRA hoặc (h, w, 3) BGR
        self.kind = kind    # "rgba" | "bgra" | "bgr"
        self.t0 = t0        # perf_counter lúc BẮT ĐẦU chụp
        self.t1 = t1        # perf_counter lúc nhận xong
        self.seq = 0


def _env_int(name, default, lo, hi):
    try:
        v = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


class _FramePump(object):
    """N luồng chụp chạy liên tục, chỉ giữ KHUNG MỚI NHẤT."""

    def __init__(self, eng):
        self.eng = eng
        self._cond = threading.Condition()
        self._stop = False
        self._latest = None
        self._seq = 0
        self._alive = 0
        self.failed = False
        self.last_error = None

    def start(self):
        n = self.eng.workers
        est = (self.eng.last_capture_ms or 80.0) / 1000.0
        self._alive = n
        for i in range(n):
            t = threading.Thread(target=self._run, args=(i, est * i / float(n)),
                                 name="turbo-cap%d" % i, daemon=True)
            t.start()

    def _run(self, idx, delay):
        try:
            if delay > 0:
                time.sleep(delay)
            fails = 0
            while not self._stop:
                try:
                    fr = self.eng.grab()
                except Exception as e:
                    fails += 1
                    self.last_error = "%s" % (e,)
                    if fails >= 3:
                        return
                    time.sleep(0.03)
                    continue
                fails = 0
                with self._cond:
                    # Khung chụp xong SAU nhưng bắt đầu chụp TRƯỚC khung đang giữ
                    # (chạy lệch nhịp giữa 2 luồng) thì bỏ - luôn giữ khung mới nhất.
                    if self._latest is None or fr.t0 > self._latest.t0:
                        self._seq += 1
                        fr.seq = self._seq
                        self._latest = fr
                        self._cond.notify_all()
        finally:
            with self._cond:
                self._alive -= 1
                if self._alive <= 0 and not self._stop:
                    self.failed = True
                self._cond.notify_all()

    def next_frame(self, last_seq, timeout):
        with self._cond:
            self._cond.wait_for(
                lambda: self.failed or (self._latest is not None and self._latest.seq > last_seq),
                timeout)
            if self._latest is not None and self._latest.seq > last_seq:
                return self._latest
            return None

    def stop(self):
        with self._cond:
            self._stop = True
            self._cond.notify_all()


class _PersistentCapture(object):
    """Kênh chụp RAW THƯỜNG TRỰC cho 1 LƯỢT quét (từ lúc TurboEngine._poll()
    bắt đầu tới lúc kết thúc) - xem mục 2b trong docstring đầu file.

    Khác _FramePump: chỉ 1 socket DUY NHẤT, mở 1 lần, chạy lệnh lặp
    `while true; do screencap; done` NGAY TRONG máy ảo rồi đọc liên tục các
    khung nối tiếp nhau trên socket đó - không mở kết nối/spawn tiến trình
    mới cho từng khung. ĐÓNG lại khi lượt quét kết thúc (gọi stop()) - không
    giữ chạy nền giữa các lượt quét, tránh máy ảo phải chụp liên tục vô ích
    lúc kịch bản đang làm việc khác.

    Kích thước 1 khung (frame_size) CỐ ĐỊNH trong suốt 1 phiên máy ảo (chỉ
    đổi khi đổi độ phân giải) nên chỉ cần dò 1 LẦN DUY NHẤT cho cả vòng đời
    TurboEngine (bằng 1 lần chụp kiểu CŨ, xem _bootstrap()) rồi CACHE lại ở
    eng._cap_frame_size/_cap_sig - các lượt quét sau tái sử dụng ngay,
    không tốn lại chi phí dò. Mọi khung nhận được sau đó đều được ĐỐI CHIẾU
    lại kích thước+định dạng với khung đầu tiên; lệch (vd đổi độ phân giải
    giữa chừng, hoặc mất đồng bộ byte do lỗi mạng) -> COI LÀ LỖI, dừng hẳn
    kênh này, KHÔNG BAO GIỜ trả về khung có thể đã bị lệch/sai mà không tự
    biết - nơi gọi (_poll) tự rơi về _FramePump (pipeline N luồng, mở kết
    nối riêng từng khung) cho phần còn lại."""

    def __init__(self, eng):
        self.eng = eng
        self._cond = threading.Condition()
        self._latest = None
        self._seq = 0
        self.failed = False
        self.last_error = None
        self._sock = None
        self._stop = False
        self._ready = threading.Event()
        self.frame_size = eng._cap_frame_size      # None nếu chưa từng dò
        self.sig = eng._cap_sig                    # (w, h, kind) khung đầu
        self.resync_count = 0                       # số lần đã tự phục hồi đồng bộ thành công

    def start(self):
        threading.Thread(target=self._run, name="turbo-cap-persist", daemon=True).start()

    def _bootstrap(self):
        """Dò kích thước 1 khung RAW bằng ĐÚNG 1 lần chụp kiểu CŨ (mở kết
        nối riêng, đọc tới hết) - xem docstring lớp. CHỈ chạy khi
        eng._cap_frame_size chưa có (lần đầu tiên cho cả vòng đời engine)."""
        try:
            buf, n = self.eng._recv_all("exec:screencap")
        except Exception as e:
            self.last_error = "dò khung đầu lỗi (%s)" % (e,)
            return False
        fr = self.eng._parse_raw(buf, n, 0.0)
        if fr is None:
            self.last_error = "khung RAW đầu tiên không hợp lệ (giả lập này có thể không hỗ trợ RAW)"
            return False
        self.frame_size = n
        self.sig = (fr.arr.shape[1], fr.arr.shape[0], fr.kind)
        self.eng._cap_frame_size = self.frame_size
        self.eng._cap_sig = self.sig
        return True

    @staticmethod
    def _recv_exact_into(sock, mv):
        n = len(mv)
        got = 0
        while got < n:
            r = sock.recv_into(mv[got:])
            if r == 0:
                return False
            got += r
        return True

    @staticmethod
    def _recv_n(sock, n):
        """Đọc đúng n byte MỚI từ socket, trả về bytes (hoặc None nếu kênh đóng)."""
        out = bytearray(n)
        if not _PersistentCapture._recv_exact_into(sock, memoryview(out)):
            return None
        return out

    def _header_at(self, buf, off):
        """Header 12 byte (w,h,fmt) tại vị trí off trong buf CÓ khớp đúng
        (w,h) đã dò lúc bootstrap không (fmt chỉ cần thuộc nhóm tương thích
        với self.sig[2]). Đây là cách kiểm tra RẺ (chỉ cần 12 byte, không
        cần đọc hết cả khung) dùng để dò lại điểm bắt đầu 1 khung khi dữ
        liệu bị lệch byte."""
        if off < 0 or off + 12 > len(buf):
            return False
        w, h, fmt = struct.unpack_from("<III", buf, off)
        if w != self.sig[0] or h != self.sig[1]:
            return False
        want_kind = self.sig[2]
        if want_kind == "rgba" and fmt not in (1, 2):
            return False
        if want_kind == "bgra" and fmt != 5:
            return False
        return True

    def _resync(self, s, stale):
        """`stale` là frame_size byte VỪA đọc nhưng KHÔNG khớp header ở vị
        trí 0 (lệch đồng bộ). Trượt từng byte một trong `stale` trước
        (không tốn thêm socket read), rồi nếu cần thì đọc thêm từ socket,
        tìm lại điểm có header hợp lệ (khớp đúng w,h đã dò) kế tiếp. Một
        khi tìm thấy, đọc bù cho đủ frame_size byte TỪ điểm đó rồi trả về
        khung mới. Tìm quá _RESYNC_MAX_FRAMES lần frame_size byte mà không
        thấy -> trả None (kênh coi như hỏng thật, không phải lệch byte
        nhỏ)."""
        window = bytearray(stale)
        limit = self.frame_size * _RESYNC_MAX_FRAMES
        searched = 0
        while searched < limit:
            # dò trong dữ liệu ĐANG CÓ trước (rẻ, không cần đọc thêm)
            max_off = len(window) - 12
            off = 1
            found = -1
            while off <= max_off:
                if self._header_at(window, off):
                    found = off
                    break
                off += 1
            if found >= 0:
                have = len(window) - found
                if have >= self.frame_size:
                    frame = window[found:found + self.frame_size]
                else:
                    more = self._recv_n(s, self.frame_size - have)
                    if more is None:
                        self.last_error = "kênh thường trực đóng giữa chừng khi đang phục hồi đồng bộ"
                        return None
                    frame = window[found:] + more
                self.resync_count += 1
                return frame
            # không thấy trong window hiện có -> đọc thêm 1 khối rồi tìm tiếp
            searched += len(window)
            chunk = self._recv_n(s, min(self.frame_size, limit - searched if limit > searched else self.frame_size))
            if chunk is None:
                self.last_error = "kênh thường trực đóng giữa chừng khi đang phục hồi đồng bộ"
                return None
            # chỉ giữ lại 11 byte cuối của window cũ (đủ nối liền header có
            # thể bắc cầu qua ranh giới) + dữ liệu mới đọc, tránh window
            # phình to vô hạn khi tìm lâu
            window = window[-11:] + chunk
        return None

    def _run(self):
        try:
            if self.frame_size is None and not self._bootstrap():
                self.failed = True
                self._ready.set()
                return
            s = self.eng._open("exec:sh")
        except Exception as e:
            self.last_error = "%s" % (e,)
            self.failed = True
            self._ready.set()
            return
        self._sock = s
        try:
            # 2>/dev/null: loại trừ khả năng screencap thỉnh thoảng in cảnh
            # báo/lỗi ra stdout xen giữa các khung RAW (1 nguồn gây lệch
            # đồng bộ đã gặp trên vài giả lập) - phòng ngừa thêm bên cạnh
            # cơ chế tự phục hồi bên dưới.
            s.sendall(b"while true; do screencap 2>/dev/null; done\n")
        except OSError as e:
            self.last_error = "%s" % (e,)
            self.failed = True
            self._close_sock()
            self._ready.set()
            return
        self._ready.set()
        try:
            while not self._stop:
                t0 = time.perf_counter()
                buf = bytearray(self.frame_size)
                if not self._recv_exact_into(s, memoryview(buf)):
                    self.last_error = "kênh thường trực đóng giữa chừng"
                    break
                if not self._header_at(buf, 0):
                    # lệch đồng bộ - thử tự phục hồi trước khi coi là lỗi hẳn
                    recovered = self._resync(s, buf)
                    if recovered is None:
                        if self.last_error is None:
                            self.last_error = "khung RAW mất đồng bộ trên kênh thường trực (đã thử phục hồi %d khung, không thành công)" % _RESYNC_MAX_FRAMES
                        break
                    buf = recovered
                fr = self.eng._parse_raw(buf, self.frame_size, t0)
                if fr is None:
                    self.last_error = "khung RAW mất đồng bộ trên kênh thường trực"
                    break
                sig = (fr.arr.shape[1], fr.arr.shape[0], fr.kind)
                if sig != self.sig:
                    self.last_error = "độ phân giải đổi giữa chừng (%r -> %r)" % (self.sig, sig)
                    break
                with self._cond:
                    self._seq += 1
                    fr.seq = self._seq
                    self._latest = fr
                    self._cond.notify_all()
        except Exception as e:
            self.last_error = "%s" % (e,)
        finally:
            self.failed = True
            self._close_sock()
            with self._cond:
                self._cond.notify_all()

    def next_frame(self, last_seq, timeout):
        with self._cond:
            self._cond.wait_for(
                lambda: self.failed or (self._latest is not None and self._latest.seq > last_seq),
                timeout)
            if self._latest is not None and self._latest.seq > last_seq:
                return self._latest
            return None

    def _close_sock(self):
        s, self._sock = self._sock, None
        if s is not None:
            try:
                s.close()
            except Exception:
                pass

    def stop(self):
        self._stop = True
        self._close_sock()          # phá blocking recv() để luồng đọc thoát ngay
        with self._cond:
            self._cond.notify_all()
        if self.resync_count:
            # Có lệch byte nhưng đã TỰ PHỤC HỒI được (không cần rơi về
            # đường cũ) - log lại để biết TẦN SUẤT lệch thật sự trên máy
            # này, dù lượt quét vẫn chạy trót lọt qua kênh thường trực.
            self.eng._note("kênh thường trực: đã tự phục hồi đồng bộ %d lần trong lượt quét này (vẫn dùng được, không rơi về đường cũ)" % self.resync_count)


class TurboEngine(object):
    def __init__(self, adb):
        self.adb = adb
        self._ah = sys.modules.get(type(adb).__module__)
        for name in ("_match_map", "_prep_for_mode", "normalize_match_mode"):
            if self._ah is None or not hasattr(self._ah, name):
                raise TurboUnavailable("adb_helper thiếu %s" % name)

        self.workers = _env_int("THTG_TURBO_WORKERS", DEFAULT_WORKERS, 1, 3)
        tm = os.environ.get("THTG_TURBO_TAP", DEFAULT_TAP_MODE).strip().lower()
        self.tap_mode = tm if tm in ("auto", "sendevent", "input") else "auto"
        # Giây (không phải ms) - dùng thẳng trong lệnh `sleep` của shell.
        self._tap_hold_s = _env_int("THTG_TURBO_TAP_HOLD_MS", DEFAULT_TAP_HOLD_MS, 0, 500) / 1000.0
        self._raw_enabled = os.environ.get("THTG_TURBO_RAW", "1" if DEFAULT_RAW else "0") != "0"

        self._raw_fail = 0
        self._size_hint = 0
        self.last_capture_ms = None
        self._announced_cap = False
        # 3 mốc bóc tách thêm cho capture_ms - xem docstring _recv_all().
        self._last_dispatch_ms = None
        self._last_wait_ms = None
        self._last_xfer_ms = None

        # --- kênh chụp thường trực (mục 2b docstring đầu file) ---
        self._cap_persist_enabled = os.environ.get("THTG_TURBO_CAP_PERSIST", "1") != "0"
        self._cap_persist_failed = False    # lỗi 1 lần -> tắt hẳn cho cả vòng đời engine
        self._cap_frame_size = None         # cache kích thước 1 khung RAW (byte), dò 1 lần
        self._cap_sig = None                # cache (w, h, kind) của khung đầu tiên
        self._announced_persist = False

        self._notes = []
        self._noted = set()
        self._notes_lock = threading.Lock()

        # --- click ---
        self._sh_lock = threading.Lock()
        self._sh = None
        self._touch = None      # None = chưa xong khởi động | False = không dùng được | dict
        self._se_bad = False
        # SỐ LẦN sendevent báo lỗi TRƯỚC KHI tắt vĩnh viễn cho cả phiên chạy.
        # Trước đây CHỈ 1 lần lỗi (có thể chỉ là trục trặc thoáng qua của
        # driver/thiết bị - không nhất thiết lặp lại) là tắt hẳn sendevent,
        # rơi về input tap (chậm hơn ~150-200ms/click) cho TOÀN BỘ phần còn
        # lại của kịch bản, dù toạ độ/thiết bị không đổi gì cả. Giờ cho phép
        # vài lần lỗi rời rạc trước khi thật sự bỏ cuộc, để không đánh mất
        # cả khoản tăng tốc chỉ vì 1 lần trục trặc ngẫu nhiên.
        self._se_fail_count = 0
        self._se_fail_limit = 3
        # SỐ LẦN được phép ĐÓNG + MỞ LẠI kênh shell thường trực khi 1 kênh
        # dính đủ _se_fail_limit lỗi liên tiếp, trước khi thật sự bỏ cuộc
        # (_se_bad = True, chuyển hẳn sang input tap). Mỗi kênh mới tính lỗi
        # lại từ đầu - xem _drain_sh().
        self._se_reopen_count = 0
        self._se_reopen_limit = 3
        # Toạ độ các lần chạm ĐÃ GỬI qua sendevent nhưng CHƯA BIẾT kết quả,
        # khoá theo tracking-id (self._tid) - khi phát hiện lỗi (bất đồng bộ,
        # có thể trễ vài lần chạm sau đó), tra lại ĐÚNG toạ độ của lần chạm
        # bị lỗi (không phải lần chạm gần nhất) để bắn 1 click `input tap` dự
        # phòng, đảm bảo KHÔNG BAO GIỜ mất hẳn 1 click dù sendevent có lỗi.
        self._pending_taps = {}
        self._pending_lock = threading.Lock()
        self._se_buf = b""
        self._tid = 1000
        self._warm_thread = None
        if self.tap_mode != "input":
            self._warm_thread = threading.Thread(target=self._warm_input, name="turbo-warm", daemon=True)
            self._warm_thread.start()

    # ------------------------------------------------------------------ ghi chú
    def _note(self, text):
        with self._notes_lock:
            if text not in self._noted:
                self._noted.add(text)
                self._notes.append(text)

    def _note_always(self, text):
        """Giống _note() nhưng KHÔNG lọc trùng - dùng cho các cảnh báo cần
        thấy được TẦN SUẤT lặp lại (vd đếm số lần sendevent lỗi), khác với
        _note() (chỉ 1 dòng duy nhất cho cả phiên, dùng cho thông báo trạng
        thái 1 lần như đang chụp RAW hay PNG)."""
        with self._notes_lock:
            self._notes.append(text)

    def pop_notes(self):
        with self._notes_lock:
            out, self._notes = self._notes, []
            return out

    # ------------------------------------------------------------------ socket
    @staticmethod
    def _send(sock, message):
        payload = message.encode("utf-8")
        sock.sendall(("%04x" % len(payload)).encode("ascii") + payload)

    @staticmethod
    def _recv_exact(sock, n):
        data = b""
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                raise OSError("ADB server đóng kết nối sớm")
            data += chunk
        return data

    def _status(self, sock):
        st = self._recv_exact(sock, 4)
        if st == b"OKAY":
            return
        if st == b"FAIL":
            try:
                ln = int(self._recv_exact(sock, 4), 16)
                reason = self._recv_exact(sock, ln).decode("utf-8", "ignore")
            except Exception:
                reason = "?"
            raise OSError("ADB server từ chối: %s" % reason)
        raise OSError("ADB server phản hồi lạ: %r" % (st,))

    def _open(self, service, timeout=3.0):
        addr = self.adb._turbo_server_addr()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 20)
            s.settimeout(timeout)
            s.connect(addr)
            dev = getattr(self.adb, "device_id", None)
            self._send(s, "host:transport:%s" % dev if dev else "host:transport-any")
            self._status(s)
            self._send(s, service)
            self._status(s)
            return s
        except Exception:
            try:
                s.close()
            except Exception:
                pass
            raise

    def _recv_all(self, service):
        """Đọc TOÀN BỘ dữ liệu của `service` vào 1 bytearray cấp phát sẵn.

        Đo thêm 2 MỐC THỜI GIAN (không chỉ tổng thời gian như trước) để biết
        CHỤP LÂU là do đâu:
        - t_open_done: xong bắt tay ADB (socket connect + gửi lệnh) - PHẦN
          NÀY thuộc về code/mạng, có thể tối ưu được.
        - t_first_byte: byte ĐẦU TIÊN của ảnh về tới - khoảng (t_open_done
          -> t_first_byte) là thời gian THIẾT BỊ/GIẢ LẬP tự dựng khung hình
          (SurfaceFlinger đọc framebuffer) TRƯỚC KHI có gì để gửi - phần
          NÀY là giới hạn phần cứng/giả lập, code không sửa được, chỉ có
          thể giảm bằng cách hạ độ phân giải giả lập.
        Phần còn lại (t_first_byte -> lúc đọc xong) là TRUYỀN DỮ LIỆU."""
        t_req = time.perf_counter()
        s = self._open(service)
        t_open_done = time.perf_counter()
        t_first_byte = None
        try:
            cap = max(self._size_hint + 4096, 1 << 20)
            buf = bytearray(cap)
            mv = memoryview(buf)
            n = 0
            extra = None
            while True:
                if n < cap:
                    r = s.recv_into(mv[n:])
                    if t_first_byte is None and r > 0:
                        t_first_byte = time.perf_counter()
                    if r == 0:
                        break
                    n += r
                else:
                    if extra is None:
                        extra = []
                    chunk = s.recv(1 << 20)
                    if not chunk:
                        break
                    extra.append(chunk)
            self._last_dispatch_ms = (t_open_done - t_req) * 1000.0
            self._last_wait_ms = ((t_first_byte or time.perf_counter()) - t_open_done) * 1000.0
            self._last_xfer_ms = (time.perf_counter() - (t_first_byte or t_open_done)) * 1000.0
            if extra:
                data = bytearray(bytes(mv[:n]) + b"".join(extra))
                n = len(data)
                self._size_hint = n
                return data, n
            self._size_hint = n
            return buf, n
        finally:
            try:
                s.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ chụp
    def _parse_raw(self, buf, n, t0):
        if n < 16:
            return None
        w, h, fmt = struct.unpack_from("<III", buf, 0)
        if not (_MIN_DIM <= w <= _MAX_DIM and _MIN_DIM <= h <= _MAX_DIM):
            return None
        px = w * h * 4
        extra = n - px
        if extra not in (12, 16):          # header Android <10 = 12B, >=10 = 16B
            return None
        if fmt in (1, 2):
            kind = "rgba"
        elif fmt == 5:
            kind = "bgra"
        else:
            return None
        arr = np.frombuffer(buf, np.uint8, count=px, offset=extra).reshape(h, w, 4)
        return TurboFrame(arr, kind, t0, time.perf_counter())

    def _grab_png(self, t0):
        buf, n = self._recv_all("exec:screencap -p")
        if n <= 0:
            raise OSError("screencap trả về rỗng")
        img = cv2.imdecode(np.frombuffer(buf, np.uint8, count=n), cv2.IMREAD_COLOR)
        if img is None:
            raise OSError("PNG nhận qua socket không giải mã được")
        return TurboFrame(img, "bgr", t0, time.perf_counter())

    def grab(self):
        t0 = time.perf_counter()
        fr = None
        if self._raw_enabled and self._raw_fail < 3:
            buf, n = self._recv_all("exec:screencap")
            fr = self._parse_raw(buf, n, t0)
            if fr is None:
                self._raw_fail += 1
                if self._raw_fail >= 3:
                    self._note("chụp RAW không hợp lệ trên giả lập này -> dùng PNG qua socket")
            else:
                self._raw_fail = 0
        if fr is None:
            fr = self._grab_png(time.perf_counter())
            fr.t0 = t0
        h, w = fr.arr.shape[:2]
        self.adb.screen_w, self.adb.screen_h = w, h
        ms = (fr.t1 - fr.t0) * 1000.0
        self.last_capture_ms = ms if self.last_capture_ms is None else (0.7 * self.last_capture_ms + 0.3 * ms)
        if not self._announced_cap:
            self._announced_cap = True
            self._note("chụp %s qua socket, %d luồng chụp song song, khung đầu %.0fms" % (
                "RAW" if fr.kind != "bgr" else "PNG", self.workers, ms))
        return fr

    def grab_bgr(self):
        fr = self.grab()
        if fr.kind == "bgr":
            return fr.arr
        return cv2.cvtColor(fr.arr, _TO_BGR[fr.kind])

    # ------------------------------------------------------------------ so khớp
    @staticmethod
    def _prep(arr, kind, mode):
        """Cùng kết quả với adb_helper._prep_for_mode() nhưng đi thẳng từ RGBA."""
        if mode in ("color", "color_sqdiff"):
            return arr if kind == "bgr" else cv2.cvtColor(arr, _TO_BGR[kind])
        gray = cv2.cvtColor(arr, _TO_GRAY[kind])
        if mode == "edge":
            return cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 50, 150)
        return gray

    def _tpl(self, t_cv, mode):
        cached = getattr(self.adb, "_prep_template_cached", None)
        if cached is not None:
            return cached(t_cv, mode)
        return self._ah._prep_for_mode(t_cv, mode)

    def _start_pump(self):
        """Chọn nguồn chụp cho 1 lượt _poll(): ưu tiên kênh thường trực
        (_PersistentCapture - mục 2b docstring đầu file) nếu RAW đang dùng
        được và chưa từng lỗi; KHÔNG dùng được (bootstrap lỗi, hoặc mở kênh
        lỗi) -> tự đóng lại và rơi về _FramePump (pipeline N luồng cũ) như
        trước đây, KHÔNG làm hỏng cả lượt quét."""
        if self._cap_persist_enabled and self._raw_enabled and not self._cap_persist_failed:
            pc = _PersistentCapture(self)
            pc.start()
            ready = pc._ready.wait(3.0)
            if ready and not pc.failed:
                if not self._announced_persist:
                    self._announced_persist = True
                    self._note("chụp RAW qua kênh thường trực (1 socket liên tục/lượt quét)")
                return pc
            self._cap_persist_failed = True
            if pc.last_error:
                self._note("kênh chụp thường trực lỗi (%s) -> dùng lại chụp từng khung như cũ" % pc.last_error)
            try:
                pc.stop()
            except Exception:
                pass
        pump = _FramePump(self)
        pump.start()
        return pump

    def _poll(self, timeout, should_stop, region, matcher):
        """Chạy pipeline chụp+so khớp. Trả về kết quả của matcher hoặc None (hết giờ/bị dừng)."""
        pump = self._start_pump()
        deadline = time.perf_counter() + max(0.0, float(timeout))
        last_seq = 0
        prev = None
        frames = 0
        skipped = 0
        stop_fn = should_stop if callable(should_stop) else (lambda: False)
        try:
            while True:
                if stop_fn():
                    return None
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    return None
                fr = pump.next_frame(last_seq, min(remaining, 0.05))
                if fr is None:
                    if pump.failed:
                        raise TurboUnavailable(pump.last_error or "luồng chụp đã dừng")
                    continue
                last_seq = fr.seq
                roi, ox, oy = self.adb._crop_region(fr.arr, region)
                if prev is not None and prev[0] == fr.kind and prev[1].shape == roi.shape:
                    try:
                        if cv2.norm(roi, prev[1], cv2.NORM_INF) == 0.0:
                            skipped += 1
                            continue   # vùng quét y hệt khung trước (đã không khớp) -> bỏ qua
                    except cv2.error:
                        pass
                prev = (fr.kind, roi)
                t_m0 = time.perf_counter()
                res = matcher(fr, roi, ox, oy)
                frames += 1
                if res is not None:
                    now = time.perf_counter()
                    self.adb.turbo_last_timing = {
                        "frame_t0": fr.t0,
                        "capture_ms": (fr.t1 - fr.t0) * 1000.0,
                        "match_ms": (now - t_m0) * 1000.0,
                        "frames": frames,
                        "skipped": skipped,
                        # Bóc tách thêm cho capture_ms (xem docstring _recv_all)
                        # - LƯU Ý: đây là số liệu của lần grab() GẦN NHẤT trên
                        # BẤT KỲ luồng nào (2 luồng chạy song song, không nhất
                        # thiết đúng của khung ĐÃ khớp) nên chỉ mang tính ước
                        # lượng chung, không tuyệt đối chính xác cho riêng
                        # khung này - nhưng đủ để biết xu hướng chụp lâu do
                        # đâu (thiết bị dựng hình hay truyền dữ liệu).
                        "dispatch_ms": self._last_dispatch_ms,
                        "wait_ms": self._last_wait_ms,
                        "xfer_ms": self._last_xfer_ms,
                    }
                    return res
        finally:
            pump.stop()

    def poll_single(self, tpl, timeout, conf, region, mode, should_stop):
        if tpl is None:
            return NotImplemented
        ah = self._ah
        mode = ah.normalize_match_mode(mode)
        t_p = self._tpl(tpl, mode)
        th, tw = t_p.shape[:2]

        def matcher(fr, roi, ox, oy):
            s_p = self._prep(roi, fr.kind, mode)
            if s_p.shape[0] < th or s_p.shape[1] < tw:
                return None
            res = ah._match_map(s_p, t_p, mode)
            _, mx, _, ml = cv2.minMaxLoc(res)
            if mx >= conf:
                fh, fw = fr.arr.shape[:2]
                cx = ox + ml[0] + tw // 2
                cy = oy + ml[1] + th // 2
                return ((round(cx / float(fw), 4), round(cy / float(fh), 4)), mx)
            return None

        try:
            r = self._poll(timeout, should_stop, region, matcher)
        except TurboUnavailable as e:
            # TRƯỚC ĐÂY: nuốt luôn lý do lỗi, rơi về vòng quét CŨ (find_image_
            # turbo + sleep) trong im lặng - khiến KHÔNG BAO GIỜ biết được vì
            # sao đường "quét siêu tốc thật" (_poll(), có turbo_last_timing/
            # breakdown ms) liên tục gãy giữa chừng dù mới khởi động thành
            # công (note "kênh thường trực..." vẫn in ra). Ghi lại lý do CỤ
            # THỂ (vd "khung RAW mất đồng bộ", "độ phân giải đổi giữa chừng",
            # "kênh thường trực đóng giữa chừng"...) để biết chính xác cần
            # sửa gì tiếp theo, thay vì đoán mò.
            self._note_always("⚠ quét siêu tốc (kênh thường trực) gãy giữa lượt quét (%s) -> lượt NÀY rơi về chụp từng khung kiểu cũ (chậm hơn, KHÔNG có breakdown ms)" % (e,))
            return NotImplemented
        return r if r is not None else (None, None)

    def poll_any(self, tpl_dict, timeout, conf, region, mode, modes, should_stop):
        ah = self._ah
        items = []
        for name, t_cv in tpl_dict.items():
            if t_cv is None:
                continue
            m = self.adb._mode_of(name, mode, modes)
            items.append((name, self._tpl(t_cv, m), m))
        if not items:
            return NotImplemented

        def matcher(fr, roi, ox, oy):
            fh, fw = fr.arr.shape[:2]
            cache = {}
            best = None
            hi = 0.0
            for name, t_p, m in items:
                s_p = cache.get(m)
                if s_p is None:
                    s_p = self._prep(roi, fr.kind, m)
                    cache[m] = s_p
                th, tw = t_p.shape[:2]
                if s_p.shape[0] < th or s_p.shape[1] < tw:
                    continue
                res = ah._match_map(s_p, t_p, m)
                _, mx, _, ml = cv2.minMaxLoc(res)
                if mx >= conf and mx > hi:
                    hi = mx
                    cx = ox + ml[0] + tw // 2
                    cy = oy + ml[1] + th // 2
                    best = (name, (round(cx / float(fw), 4), round(cy / float(fh), 4)), mx)
            return best

        try:
            r = self._poll(timeout, should_stop, region, matcher)
        except TurboUnavailable as e:
            self._note_always("⚠ quét siêu tốc (kênh thường trực) gãy giữa lượt quét (%s) -> lượt NÀY rơi về chụp từng khung kiểu cũ (chậm hơn, KHÔNG có breakdown ms)" % (e,))
            return NotImplemented
        return r if r is not None else (None, None, None)

    # ------------------------------------------------------------------ click
    def _warm_input(self):
        """Chạy NỀN ngay khi động cơ được tạo: dò thiết bị cảm ứng + mở shell thường trực."""
        try:
            dev = getattr(self.adb, "_touch_device_cache", None)
            if dev is None:
                dev = self.adb._detect_touch_device()     # ~1s, nên chạy nền
                self.adb._touch_device_cache = dev if dev else False
            if not dev:
                self._touch = False
                self._note("click: không dò được thiết bị cảm ứng -> dùng input tap")
                return
            path = dev.get("path", "")
            if not re.match(r"^/dev/input/[A-Za-z0-9_.\-]+$", path):
                self._touch = False
                self._note("click: đường dẫn thiết bị cảm ứng lạ (%s) -> dùng input tap" % path)
                return
            sh = self._open("exec:sh")
            buf = b""
            try:
                sh.sendall(("command -v sendevent >/dev/null 2>&1 && [ -w %s ] && echo THTG_OK || echo THTG_NO\n" % path).encode())
                sh.settimeout(2.0)
                while b"THTG_OK" not in buf and b"THTG_NO" not in buf:
                    d = sh.recv(256)
                    if not d:
                        break
                    buf += d
            except OSError:
                pass
            if b"THTG_OK" not in buf:
                try:
                    sh.close()
                except Exception:
                    pass
                self._touch = False
                self._note("click: không ghi được vào %s (thiếu sendevent/quyền) -> dùng input tap" % path)
                return
            sh.settimeout(None)
            with self._sh_lock:
                self._sh = sh
            threading.Thread(target=self._drain_sh, args=(sh,), name="turbo-sh", daemon=True).start()
            self._touch = dev
            self._note("click qua sendevent (shell thường trực, %s)" % path)
        except Exception as e:
            self._touch = False
            self._note("click: khởi động sendevent lỗi (%s) -> dùng input tap" % (e,))

    def _fallback_tap_for(self, tid):
        """Tra toạ độ của lần chạm mang tracking-id `tid` (đã gửi qua
        sendevent nhưng vừa bị báo lỗi) rồi bắn 1 click `input tap` dự
        phòng bù lại - chạy trong THREAD RIÊNG (không chặn luồng đọc
        _drain_sh) vì `input tap` tốn ~150-200ms. Không tìm thấy toạ độ
        (vd bị dọn khỏi cache do quá cũ) thì bỏ qua, không đoán bừa."""
        with self._pending_lock:
            xy = self._pending_taps.pop(tid, None)
        if xy is None:
            self._note_always("sendevent lỗi nhưng không còn nhớ toạ độ lần chạm #%d để bù (quá cũ) - có thể đã mất 1 click" % tid)
            return
        x_px, y_px = xy
        try:
            self.adb._turbo_transact("exec:input tap %d %d" % (int(round(x_px)), int(round(y_px))), timeout=1.5)
            self._note_always("sendevent lỗi lần chạm #%d -> đã bắn input tap DỰ PHÒNG bù lại tại (%d,%d)" % (tid, x_px, y_px))
        except Exception as e:
            self._note_always("sendevent lỗi lần chạm #%d -> BÙ BẰNG input tap CŨNG lỗi (%s) - click này có thể đã mất" % (tid, e))

    def _drain_sh(self, sock):
        try:
            while True:
                d = sock.recv(4096)
                if not d:
                    break
                self._se_buf += d
                # Có thể nhận nhiều "THTG_FAIL:<tid>" dồn lại trong 1 lần recv
                # (vd nhiều lần chạm lỗi liên tiếp) - bóc tách HẾT, không chỉ 1.
                matches = list(_FAIL_RE.finditer(self._se_buf))
                if matches:
                    # SỬA LỖI: trước đây cắt buffer về [-32:] (cửa sổ CỐ ĐỊNH
                    # tính từ cuối) để phòng recv() cắt giữa chừng 1 token dở
                    # dang - nhưng nếu token vừa match xong vẫn ngắn hơn 32
                    # byte, nó KHÔNG bị xoá, nên khi recv() kế tiếp nối thêm
                    # dữ liệu vào buffer, đúng chuỗi "THTG_FAIL:<tid>" đó bị
                    # regex bắt trùng lại lần 2 -> đếm lỗi 2 lần + gọi
                    # _fallback_tap_for 2 lần cho CÙNG 1 tid (lần 2 luôn báo
                    # "quá cũ" vì tid đã bị pop khỏi _pending_taps ở lần 1).
                    # Nay cắt CHÍNH XÁC tới vị trí kết thúc của match CUỐI
                    # CÙNG - phần đã match chắc chắn bị bỏ hết, chỉ còn lại
                    # đúng phần đuôi CHƯA từng được match (có thể là 1 token
                    # dở dang do recv() cắt giữa chừng, hoặc rỗng).
                    self._se_buf = self._se_buf[matches[-1].end():]
                need_reopen = False
                give_up = False
                for m in matches:
                    tid = int(m.group(1))
                    self._se_fail_count += 1
                    threading.Thread(target=self._fallback_tap_for, args=(tid,),
                                     name="turbo-se-fallback", daemon=True).start()
                    if self._se_fail_count >= self._se_fail_limit:
                        # TRƯỚC ĐÂY: đủ _se_fail_limit lỗi LIÊN TIẾP là tắt hẳn
                        # sendevent VĨNH VIỄN cho cả phiên chạy (self._se_bad =
                        # True), dù kênh shell thường trực vẫn đang mở suốt từ
                        # đầu tới cuối - tức 1 kênh "dính lỗi" (vd driver/ADB
                        # server phía sau tạm trục trặc) làm mất luôn khoản
                        # tăng tốc cho TOÀN BỘ phần còn lại, dù rất có thể chỉ
                        # cần ĐÓNG kênh cũ + MỞ kênh mới là hết lỗi ngay.
                        # NAY: thử ĐÓNG + MỞ LẠI kênh (tối đa _se_reopen_limit
                        # lần, xem __init__) trước khi thật sự bỏ cuộc - mỗi
                        # kênh mới được tính lỗi TỪ ĐẦU (reset _se_fail_count),
                        # không cộng dồn lỗi của kênh cũ đã đóng.
                        if self._se_reopen_count < self._se_reopen_limit:
                            need_reopen = True
                        else:
                            give_up = True
                        break
                    else:
                        # Chưa tắt hẳn - chỉ ghi chú (không dedup, để thấy được
                        # TẦN SUẤT lỗi thật) rồi vẫn tiếp tục dùng sendevent cho
                        # lần chạm kế tiếp, vì có thể chỉ là trục trặc thoáng qua.
                        self._note_always(
                            "sendevent báo lỗi lần %d/%d (đang thử tiếp, chưa tắt)" % (self._se_fail_count, self._se_fail_limit))
                if need_reopen:
                    self._se_reopen_count += 1
                    self._se_fail_count = 0
                    self._note_always(
                        "sendevent báo lỗi %d lần liên tiếp -> ĐÓNG kênh shell thường trực cũ, MỞ LẠI kênh mới thử tiếp (lần mở lại %d/%d)"
                        % (self._se_fail_limit, self._se_reopen_count, self._se_reopen_limit))
                    with self._sh_lock:
                        # Chỉ tự mở lại nếu kênh hiện tại VẪN LÀ kênh đang lỗi
                        # này (tránh trường hợp tap() ở luồng khác đã lỡ mở lại
                        # rồi, mở thêm lần 2 thành thừa 1 kết nối). Mở kênh MỚI
                        # trước khi return khỏi hàm - để finally() bên dưới
                        # (chạy ngay sau khi hàm này kết thúc) thấy self._sh đã
                        # trỏ sang socket MỚI, không tự ý xoá nó đi.
                        if self._sh is sock:
                            self._reopen_sh()
                    return
                if give_up:
                    self._se_bad = True
                    self._note(
                        "sendevent báo lỗi %d lần liên tiếp (đã thử mở lại kênh %d/%d lần, vẫn lỗi) -> chuyển hẳn sang input tap cho phần còn lại"
                        % (self._se_fail_limit, self._se_reopen_count, self._se_reopen_limit))
        except Exception:
            pass
        finally:
            with self._sh_lock:
                if self._sh is sock:
                    self._sh = None
            try:
                sock.close()
            except Exception:
                pass

    def _reopen_sh(self):
        sh = self._open("exec:sh")
        sh.settimeout(None)
        self._sh = sh
        threading.Thread(target=self._drain_sh, args=(sh,), name="turbo-sh", daemon=True).start()

    def tap(self, x_px, y_px):
        """True = đã gửi lệnh chạm qua sendevent. False = nơi gọi tự dùng `input tap` như cũ."""
        if self.tap_mode == "input" or self._se_bad:
            return False
        if self.tap_mode == "sendevent" and self._touch is None and self._warm_thread is not None:
            self._warm_thread.join(5.0)
        dev = self._touch
        if not dev:
            return False

        w = max(1, int(self.adb.screen_w))
        h = max(1, int(self.adb.screen_h))
        rx = dev["min_x"] + (float(x_px) / w) * (dev["max_x"] - dev["min_x"])
        ry = dev["min_y"] + (float(y_px) / h) * (dev["max_y"] - dev["min_y"])
        rx = int(round(min(max(rx, dev["min_x"]), dev["max_x"])))
        ry = int(round(min(max(ry, dev["min_y"]), dev["max_y"])))

        self._tid = 1000 + ((self._tid - 999) % 60000)
        tid = self._tid
        p = dev["path"]
        # Tách riêng chuỗi DOWN và chuỗi UP (trước đây gộp chung 1 chuỗi,
        # tức down+up gửi liền mạch trong CÙNG 1 lần ghi -> thời lượng chạm
        # ~0ms, bị nhiều driver cảm ứng ảo/app coi là nhiễu và không dispatch
        # thành 2 sự kiện ACTION_DOWN/ACTION_UP tách biệt -> sendevent báo
        # ghi thành công nhưng KHÔNG có tác dụng click thật trên giả lập).
        ev_down = [(3, 47, 0), (3, 57, tid), (3, 53, rx), (3, 54, ry), (1, 330, 1), (0, 0, 0)]
        ev_up = [(3, 57, -1), (1, 330, 0), (0, 0, 0)]

        def _chain(ev):
            return " && ".join("sendevent %s %d %d %d" % (p, t, c, v) for t, c, v in ev)

        parts = [_chain(ev_down)]
        if self._tap_hold_s > 0:
            # `sleep` GIỮA down và up, vẫn trong CÙNG 1 dòng lệnh/1 lần
            # sendall() trên kênh shell thường trực self._sh như cũ - không
            # tốn thêm round-trip nào, chỉ thêm đúng khoảng nghỉ cần thiết
            # để tạo ra 1 cú chạm có THỜI LƯỢNG thật thay vì tức thời.
            parts.append("sleep %.3f" % self._tap_hold_s)
        parts.append(_chain(ev_up))
        # THTG_FAIL:<tid> (thay vì chỉ "THTG_FAIL" như trước) - để _drain_sh
        # biết ĐÚNG lần chạm nào lỗi (toạ độ gốc x_px,y_px, KHÔNG PHẢI toạ độ
        # rx,ry đã quy đổi sang trục thiết bị) mà bắn click dự phòng bù đúng
        # chỗ, thay vì chỉ biết "có lỗi" chung chung không rõ của lần nào.
        line = " && ".join(parts) + " || echo THTG_FAIL:%d\n" % tid
        data = line.encode("ascii")

        with self._pending_lock:
            self._pending_taps[tid] = (x_px, y_px)
            if len(self._pending_taps) > 64:
                # Dọn bớt các lần chạm CŨ NHẤT còn treo (nếu vì lý do gì đó
                # _drain_sh không bao giờ báo lỗi/thành công cho chúng) - tránh
                # phình bộ nhớ vô hạn khi chạy rất lâu.
                for old_tid in sorted(self._pending_taps)[:-64]:
                    self._pending_taps.pop(old_tid, None)

        with self._sh_lock:
            for attempt in (0, 1):
                try:
                    if self._sh is None:
                        self._reopen_sh()
                    self._sh.sendall(data)
                    break
                except OSError:
                    try:
                        if self._sh is not None:
                            self._sh.close()
                    except Exception:
                        pass
                    self._sh = None
                    if attempt == 1:
                        return False
        return True

    def close(self):
        with self._sh_lock:
            sh, self._sh = self._sh, None
        if sh is not None:
            try:
                sh.close()
            except Exception:
                pass

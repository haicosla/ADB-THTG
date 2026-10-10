import os
import time
import json
import re
import unicodedata
import random
import cv2
import numpy as np

import data_groups
from safe_calc import safe_calc
from merge2048_bot import run_auto_merge2048_step
from photo_bot import run_auto_photo_step
from thtg_bot import run_auto_thtg_step
from pig_bot import run_auto_pig_step


class BreakGroupSignal(Exception):
    """Dùng nội bộ để thoát ngay khỏi vòng lặp của khối GROUP hiện tại khi
    gặp bước 'break_group' (thường đi kèm 1 điều kiện IF (Biến), vd:
    dừng vòng lặp khi đã tìm/click đủ 5 hình). Được bắt (catch) ngay tại nơi
    GROUP đó được thực thi; nếu dùng break_group ở ngoài mọi GROUP thì sẽ nổi
    lên tới tận nơi gọi execute_steps ở cấp cao nhất."""
    pass


class ContinueGroupSignal(Exception):
    """Dùng nội bộ khi gặp bước 'continue_group': nhảy ngay về ĐẦU của khối
    GROUP hiện tại (bỏ qua các bước còn lại trong lượt lặp này), giống
    'continue' trong lập trình - khác với BreakGroupSignal là thoát HẲN vòng
    lặp, cái này chỉ bỏ qua PHẦN CÒN LẠI của lượt lặp đang chạy rồi lặp tiếp."""
    pass


class GotoLabelSignal(Exception):
    """Dùng nội bộ cho bước 'goto_label' (Nhảy Tới Nhãn) khi nhãn đích KHÔNG
    nằm trong danh sách bước đang chạy (vd bước nhảy đặt BÊN TRONG 1 Nhóm,
    còn nhãn nằm ở bên ngoài Nhóm). Tín hiệu này thoát khỏi Nhóm hiện tại và
    được bắt ở cấp ngoài hơn; cấp nào tìm thấy nhãn thì nhảy tới đó."""

    def __init__(self, label_name):
        super().__init__(label_name)
        self.label_name = label_name


def _get_scan_interval(step, default=0.1):
    """Đọc TỐC ĐỘ QUÉT (khoảng nghỉ giữa 2 lần chụp+so khớp ảnh liên tiếp,
    đơn vị giây) từ field 'scan_interval' của bước wait_image/if_image/
    multi_image - do người dùng tự đặt trong GUI (mặc định 0.1s nếu chưa
    từng đặt, để tương thích ngược với các kịch bản JSON cũ chưa có field
    này). Đặt càng NHỎ thì quét càng NHANH (bắt được cả ảnh chỉ hiện rất
    ngắn) nhưng tốn CPU hơn vì lặp lại chụp màn hình+so khớp nhiều hơn -
    kẹp trong khoảng [0.02, 2.0]s để tránh người dùng lỡ tay đặt giá trị vô
    lý (0 hoặc âm sẽ quay vòng liên tục ngốn CPU không cần thiết, quá lớn
    thì lại dễ bỏ lỡ ảnh ngắn)."""
    try:
        val = float(step.get("scan_interval", default))
    except (TypeError, ValueError):
        val = default
    return max(0.02, min(2.0, val))


# Tên tiếng Việt của tuỳ chọn 'charset' (kiểu ký tự OCR nhận) - chỉ để ghi log.
_OCR_CHARSET_VN = {"all": "cả chữ và số", "digits": "chỉ số", "letters": "chỉ chữ",
                   "number": "số (âm/lẻ)"}


class LogicEngine:
    def __init__(self, adb_helper, stop_checker=None, step_notifier=None, popup_notifier=None, logger=None,
                 max_runtime_seconds=None):
        self.adb = adb_helper
        self.stop_checker = stop_checker if stop_checker else (lambda: False)
        # max_runtime_seconds: giới hạn AN TOÀN cho TỔNG thời gian chạy của
        # 1 lần execute_steps() CẤP GỐC (is_root=True), vd chỉnh 3600 =
        # tự dừng sau 1 tiếng dù kịch bản có lỡ bị treo (chờ ảnh mãi không
        # thấy, group lặp theo thời gian đặt nhầm số quá lớn...). None =
        # không giới hạn (giữ hành vi cũ). Xem _should_stop().
        self.max_runtime_seconds = max_runtime_seconds
        self._deadline = None
        self._deadline_logged = False
        self._hung_logged = False
        # alive_checker() -> bool (tuỳ chọn, Dashboard gắn vào trong _exec_entry):
        # False = tiến trình giả lập đã BỊ TẮT/đóng giữa lúc chạy. _should_stop()
        # gọi nó định kỳ (mỗi ALIVE_CHECK_INTERVAL giây) và đặt cờ `adb.hung`
        # NGAY, không đợi adb lỗi liên tiếp >= 30s. None = không kiểm tra
        # (Macro Studio giữ nguyên hành vi cũ).
        self.alive_checker = None
        self._alive_last = 0.0
        self.step_notifier = step_notifier
        # popup_notifier(message: str) -> gọi để hiện popup thông báo và CHỜ
        # người dùng bấm OK. Bắt buộc phải điều phối về main thread (Tkinter)
        # vì execute_steps chạy trên thread nền - xem gui.py _show_popup_and_wait.
        self.popup_notifier = popup_notifier
        # logger(level, message) -> ghi 1 dòng vào Nhật Ký Chạy (Run Log) bên
        # gui.py, vd: đã thực hiện hành động gì, tìm thấy ảnh hay không, biến
        # đổi giá trị ra sao, OCR đọc được gì, lỗi gì xảy ra... level là 1
        # trong "info"/"success"/"warn"/"error". Được gọi từ THREAD NỀN nên
        # phía gui.py phải tự điều phối về main thread (root.after) bên trong
        # hàm logger truyền vào - engine không cần biết việc đó.
        self.logger = logger
        # Biến do người dùng định nghĩa trong kịch bản (set_var/inc_var/if_var/
        # ocr_text), vd đếm số lần đã tìm thấy ảnh, hoặc chữ vừa quét được.
        self.variables = {}
        # Tên các biến đến từ preset_vars (Dashboard hỏi TRƯỚC khi chạy) -
        # xem apply_preset_vars()/reset_variables() và action 'input_var'.
        self._preset_var_names = set()
        # Ghi nhớ các lỗi Chế Độ Siêu Tốc ĐÃ CẢNH BÁO rồi (theo nội dung lỗi)
        # để KHÔNG log lặp lại y hệt mỗi vòng quét (có thể hàng chục lần/giây)
        # - xem _warn_turbo_fallback().
        self._turbo_warned = set()

    def _warn_turbo_fallback(self):
        """Gọi NGAY SAU mỗi lần dùng đường Siêu Tốc (turbo=True) - nếu
        adb.turbo_last_error đang có giá trị nghĩa là lần vừa rồi ĐÃ ÂM
        THẦM rơi về đường bình thường (socket lỗi) thay vì thật sự chạy
        nhanh, dù bước đó đang bật Chế Độ Siêu Tốc. Cảnh báo 1 LẦN DUY
        NHẤT cho mỗi loại lỗi khác nhau để người dùng biết turbo KHÔNG có
        tác dụng và vì sao, thay vì tưởng đã bật mà thực ra vẫn chạy đường
        cũ y hệt trước đây."""
        err = getattr(self.adb, "turbo_last_error", None)
        if err and err not in self._turbo_warned:
            self._turbo_warned.add(err)
            self._log("warn", f"⚡ Chế Độ Siêu Tốc KHÔNG hoạt động (đang tự rơi về đường bình thường) - {err}")
        self._turbo_report()

    def _turbo_report(self):
        """Ghi vào Nhật Ký các thông báo MỚI của động cơ Siêu Tốc (đang chụp
        RAW hay PNG, click bằng sendevent hay input tap...) - mỗi thông báo
        chỉ ghi 1 lần để biết chính xác turbo đang chạy bằng cách nào."""
        pop = getattr(self.adb, "turbo_pop_notes", None)
        if pop is None:
            return
        try:
            for note in pop():
                self._log("info", f"⚡ Siêu Tốc: {note}")
        except Exception:
            pass

    def _turbo_click_txt(self, step):
        """Đuôi Nhật Ký cho bước bật Siêu Tốc: ms từ lúc bắt đầu chụp khung
        chứa ảnh tới lúc lệnh click được gửi (rỗng nếu không có số liệu),
        kèm BÓC TÁCH chụp/so khớp (xem turbo_timing_breakdown() bên
        adb_helper.py) - để biết đang chậm ở khâu nào mà tối ưu tiếp,
        thay vì chỉ thấy 1 con số tổng không biết quy về đâu."""
        if not step.get("turbo"):
            return ""
        fn = getattr(self.adb, "turbo_click_latency_ms", None)
        try:
            ms = fn() if fn else None
        except Exception:
            ms = None
        if ms is None:
            return ""
        breakdown_fn = getattr(self.adb, "turbo_timing_breakdown", None)
        breakdown_txt = ""
        try:
            bd = breakdown_fn() if breakdown_fn else None
        except Exception:
            bd = None
        if bd:
            click_txt = ""
            if bd.get("click_ms") is not None:
                via = {"sendevent": "sendevent", "input_tap_socket": "input tap-socket",
                       "input_tap_process_fallback": "input tap-tiến trình"}.get(bd.get("click_via"), bd.get("click_via") or "?")
                click_txt = f" + click {bd['click_ms']:.0f}ms qua {via}"
            cap_detail = ""
            if bd.get("wait_ms") is not None:
                # dispatch = phần code/kết nối, wait = thiết bị TỰ DỰNG khung
                # hình (giới hạn phần cứng, không sửa bằng code được), xfer =
                # truyền dữ liệu về PC.
                cap_detail = f" (kết nối {bd.get('dispatch_ms', 0):.0f}ms/dựng hình {bd['wait_ms']:.0f}ms/truyền {bd.get('xfer_ms', 0):.0f}ms)"
            breakdown_txt = f" [chụp {bd['capture_ms']:.0f}ms{cap_detail} + khớp {bd['match_ms']:.0f}ms{click_txt}, quét {bd['frames_scanned']} khung/bỏ {bd['frames_skipped']}]"
        return f" ⚡{ms:.0f}ms{breakdown_txt}"

    def _log(self, level, message):
        if self.logger:
            try:
                self.logger(level, message)
            except Exception:
                pass

    ALIVE_CHECK_INTERVAL = 4.0  # giây giữa 2 lần hỏi alive_checker

    def _should_stop(self):
        """Kết hợp CẢ 2 điều kiện dừng: (1) người dùng bấm nút Dừng
        (self.stop_checker do GUI truyền vào) và (2) đã chạy quá
        max_runtime_seconds (nếu có đặt) tính từ lúc execute_steps() CẤP
        GỐC bắt đầu. Dùng hàm này THAY CHO self.stop_checker() ở MỌI nơi
        trong file - nhờ vậy chỉ cần đặt max_runtime_seconds 1 lần là chặn
        được HẾT mọi loại vòng lặp (repeat theo số lần/thời gian, quét ảnh,
        group...) mà không phải sửa riêng từng chỗ."""
        if self.stop_checker():
            return True
        # Giả lập bị TẮT/đóng giữa lúc chạy: kiểm tra trực tiếp tiến trình (rẻ,
        # throttle) thay vì đợi adb lỗi đủ lâu - rồi đi tiếp xuống nhánh `hung`.
        chk = self.alive_checker
        if chk is not None and not getattr(self.adb, "hung", False):
            now = time.time()
            if now - self._alive_last >= self.ALIVE_CHECK_INTERVAL:
                self._alive_last = now
                try:
                    alive = chk()
                except Exception:
                    alive = True
                if not alive and hasattr(self.adb, "mark_hung"):
                    self.adb.mark_hung("giả lập đã bị tắt/đóng giữa lúc đang chạy")
        # Giả lập TREO giữa lúc chạy (adb_helper.py đặt cờ `hung` sau nhiều
        # lần lệnh adb timeout/chụp rỗng liên tiếp) -> dừng kịch bản ngay thay
        # vì quét/chờ ảnh vô ích; nơi gọi (Dashboard _exec_entry) đọc cờ này
        # để tự khởi động lại giả lập rồi chạy lại.
        if getattr(self.adb, "hung", False):
            if not self._hung_logged:
                self._hung_logged = True
                self._log("error", "🧊 Giả lập có dấu hiệu TREO (%s) - dừng kịch bản hiện tại để xử lý"
                          % (getattr(self.adb, "last_fail_reason", None) or "adb không phản hồi"))
            return True
        if self._deadline is not None and time.time() > self._deadline:
            if not self._deadline_logged:
                self._deadline_logged = True
                self._log("error", f"⏱ Đã chạy quá thời gian tối đa cho phép "
                                    f"({self.max_runtime_seconds:.0f}s) - tự động DỪNG kịch bản để tránh treo vô hạn")
            return True
        return False

    _RAND_TOKEN_RE = re.compile(r"^\s*(rand|random)\s*:\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)\s*$", re.IGNORECASE)

    @staticmethod
    def _rand_from_range(a_txt, b_txt):
        """Sinh 1 số NGẪU NHIÊN trong [a, b] (tự đảo nếu a > b). Cả 2 đầu là
        số nguyên -> randint (trả chuỗi số nguyên), ngược lại uniform làm
        tròn 2 chữ số."""
        a, b = float(a_txt), float(b_txt)
        if a > b:
            a, b = b, a
        if "." not in a_txt and "." not in b_txt:
            return str(random.randint(int(a), int(b)))
        return str(round(random.uniform(a, b), 2))

    def _get_step_delay(self, step):
        """Delay (giây) SAU bước. Hành vi cũ giữ nguyên: field 'delay' là 1
        SỐ cố định. MỚI (tuỳ chọn):
          - 'delay_max' > 'delay' -> chờ NGẪU NHIÊN trong [delay, delay_max]
            (vd delay=10, delay_max=30 -> mỗi lần chạy chờ 10-30s khác nhau).
          - 'delay' là chuỗi (vd '{rand:10-30}', '{cho}*2') -> tính qua
            _resolve_step_number (hỗ trợ biến + biến random + phép tính).
        Áp dụng cho MỌI loại bước, kể cả 'sleep'."""
        raw = step.get("delay", 1.0)
        base = max(0.0, self._resolve_step_number(raw, default=1.0))
        dmax_raw = step.get("delay_max")
        if dmax_raw in (None, "", 0, 0.0):
            return base
        dmax = max(0.0, self._resolve_step_number(dmax_raw, default=base))
        if dmax <= base:
            return base
        value = round(random.uniform(base, dmax), 2)
        self._log("info", f"🎲 Chờ ngẫu nhiên {value}s (khoảng {base:g}-{dmax:g}s)")
        return value

    def _interpolate_vars(self, text):
        """Cho phép nhúng biến vào 1 chuỗi bằng cú pháp {tên_biến}, vd:
        'Điểm: {ocr_text}' -> thay {ocr_text} bằng GIÁ TRỊ biến ocr_text hiện
        tại. Phần chữ còn lại (ngoài dấu {}) LUÔN được coi là văn bản thuần,
        không tự động đoán "cái nào là biến, cái nào là chữ" nữa - trước đây
        Gõ Chữ / Popup không có cách nào phân biệt, nên gõ 'ocr_text' sẽ luôn
        gõ ra đúng 3 chữ đó thay vì lấy giá trị đã quét được.

        TRƯỚC ĐÂY regex chỉ nhận tên biến thuần ASCII ([a-zA-Z_][a-zA-Z0-9_]*)
        -> nếu tên biến có dấu tiếng Việt hoặc bắt đầu bằng số/ký tự khác thì
        {tên_biến} bị bỏ qua, giữ nguyên y hệt (nhìn như "không điền được tên
        biến" dù đã gõ đúng cú pháp). Nay nhận MỌI ký tự bên trong { } (trừ
        chính dấu { } lồng nhau) làm tên biến, khớp CHÍNH XÁC với tên đã đặt
        khi tạo biến (vd bước OCR/Đặt Biến), bất kể có dấu hay không."""
        if not text or "{" not in text:
            return text

        def repl(m):
            name = m.group(1)
            if name in self.variables:
                return str(self.variables[name])
            # BIẾN RANDOM: {rand:10-30} / {random:10-30} -> số NGẪU NHIÊN
            # trong khoảng, mỗi lần đọc ra 1 giá trị mới. Hai đầu là số
            # nguyên -> trả số nguyên; có số thập phân -> trả số thực (2
            # chữ số). Chỉ áp dụng khi KHÔNG có biến trùng tên ở trên.
            rm = self._RAND_TOKEN_RE.match(name)
            if rm:
                return self._rand_from_range(rm.group(2), rm.group(3))
            return m.group(0)  # giữ nguyên {ten_bien} nếu biến chưa tồn tại

        return re.sub(r"\{([^{}]+)\}", repl, text)

    def _resolve_step_number(self, raw, default=0.0):
        """Đọc 1 giá trị SỐ của bước (vd 'repeat', 'repeat_ms',
        'repeat_seconds') - giá trị này có thể là 1 SỐ CỐ ĐỊNH như trước
        đây, HOẶC 1 chuỗi chứa biến kiểu {ten_bien} (vd đặt 'Sửa Lặp' =
        '{so_luong}' để lặp ĐÚNG số lần người dùng vừa nhập ở bước 'Biến
        Nhập Trước Khi Chạy'/'Đặt Biến'), dùng lại _interpolate_vars() để
        thay {ten_bien} bằng giá trị biến hiện tại rồi mới ép kiểu số.

        Hỗ trợ thêm PHÉP TÍNH số học đơn giản NGAY SAU khi thay biến: + - *
        / và dấu ngoặc (vd '{so_phut}*60000' để lặp theo THỜI GIAN tính bằng
        phút, '{sach}-1' để lặp ít hơn số biến 1 lần, '({a}+{b})/2') -
        KHÔNG dùng eval() để tránh rủi ro, tính bằng safe_calc.safe_calc()
        (chỉ nhận số và + - * / ( ), thứ gì khác bị từ chối). Kiểu cũ
        '{so_phut}*60000' cho ra đúng kết quả như trước.

        Nếu không đọc được thành số (biến chưa tồn tại, gõ sai...) thì ghi
        log lỗi và trả về 'default' thay vì làm hỏng cả bước/kịch bản."""
        if isinstance(raw, (int, float)):
            return float(raw)
        text = self._interpolate_vars(str(raw))
        try:
            try:
                return float(text)
            except ValueError:
                return safe_calc(text)
        except (ValueError, TypeError, ZeroDivisionError):
            self._log("error", f"Không đọc được giá trị số '{raw}' (sau khi thay biến: '{text}') -> dùng mặc định {default}")
            return default

    def _get_repeat_ms(self, step):
        """Đọc thời gian lặp (ms) từ step. Ưu tiên field 'repeat_ms' (chuẩn
        mới). Vẫn đọc được field cũ 'repeat_seconds' (đơn vị giây) để tương
        thích ngược với các file JSON kịch bản đã lưu trước đây. Cả 2 field
        đều có thể là biểu thức chứa biến (xem _resolve_step_number)."""
        if "repeat_ms" in step:
            return self._resolve_step_number(step.get("repeat_ms", 0), default=0.0)
        return self._resolve_step_number(step.get("repeat_seconds", 0), default=0.0) * 1000.0

    def reset_variables(self):
        """Gọi trước mỗi lần CHẠY THỬ kịch bản để các biến (vd bộ đếm) không
        bị giữ lại giá trị từ lần chạy trước đó."""
        self.variables = {}
        self._preset_var_names = set()

    def apply_preset_vars(self, preset_vars):
        """Nạp preset_vars (Dashboard hỏi người dùng TRƯỚC khi chạy, xem
        _exec_entry trong dashboard_run.py) vào self.variables, ĐỒNG THỜI
        ghi nhớ CHÍNH XÁC những tên biến nào đến từ preset_vars (khác với
        biến chỉ tình cờ đã có giá trị do 1 bước SET_VAR nào đó chạy TRƯỚC
        bước 'input_var' trong CÙNG kịch bản) - xem chỗ dùng ở action
        'input_var' bên dưới: nếu 1 kịch bản lỡ đặt SET_VAR cho đúng tên
        biến của input_var TRƯỚC bước input_var, biến đó KHÔNG được coi là
        "đã hỏi trước khi chạy" nữa, input_var vẫn ép về giá trị default."""
        if preset_vars:
            self.variables.update(preset_vars)
            self._preset_var_names |= set(preset_vars.keys())

    @staticmethod
    def _normalize_ocr_text(text):
        """Chữ thường + bỏ dấu tiếng Việt (đ->d) + ký tự không phải chữ/số -> 1 khoảng trắng."""
        t = unicodedata.normalize("NFD", str(text or "").lower().replace("đ", "d"))
        t = "".join(c for c in t if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9]+", " ", t).strip()

    @staticmethod
    def _compare_values(current, op, target):
        # Toán tử CHỮ cho biến OCR: contains / not_contains / regex (không phân biệt hoa/thường)
        if op in ("contains", "not_contains", "regex"):
            cur_txt, tgt_txt = str(current), str(target)
            if op == "regex":
                try:
                    return re.search(tgt_txt, cur_txt, re.IGNORECASE) is not None
                except re.error:
                    return False
            found = tgt_txt.lower() in cur_txt.lower()
            return found if op == "contains" else not found
        try:
            a, b = float(current), float(target)
        except (TypeError, ValueError):
            a, b = str(current), str(target)
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        return False

    @staticmethod
    def _match_text(actual, expected, mode):
        """So khớp text OCR đọc được (actual) với text mong đợi (expected)
        - dùng chung cho if_ocr và nút lá 'ocr' trong if_group. 3 kiểu:
        contains (CHỨA, không phân biệt hoa/thường - mặc định), exact
        (khớp đúng tuyệt đối sau khi trim), regex (biểu thức chính quy -
        'expected' là pattern, khớp 1 phần bất kỳ trong 'actual', dùng
        re.search)."""
        actual = (actual or "").strip()
        expected = (expected or "").strip()
        if mode == "exact":
            return actual == expected
        if mode == "regex":
            try:
                return re.search(expected, actual) is not None
            except re.error:
                return False
        return expected.lower() in actual.lower()

    def _eval_condition_node(self, node):
        """Đánh giá 1 NÚT trong cây điều kiện lồng nhau AND/OR/NOT của
        if_group - gọi ĐỆ QUY xuống các nút con. Mỗi lần gọi cho 1 lá
        ẢNH/OCR là 1 lần CHỤP MÀN HÌNH MỚI (không tự lặp lại chờ bên trong
        từng lá) - vòng lặp CHỜ THEO TIMEOUT tổng thể của cả cây nằm ở
        NGOÀI (nhánh 'if_group' trong execute_steps()).
        node dạng nút GỘP: {"type": "and"/"or", "children": [node, ...]}
            hoặc {"type": "not", "children": [node]} (ĐÚNG 1 con).
        node dạng LÁ: {"type": "image", "template", "conf", "region",
            "match_mode"} / {"type": "var", "var", "op", "value"} /
            {"type": "ocr", "box", "text", "match", "lang"}.
        LƯU Ý: mỗi lá ảnh/OCR tự chụp màn hình RIÊNG - nếu màn hình đổi
        rất nhanh giữa lúc đánh giá 2 lá liền nhau trong 1 phép AND, về lý
        thuyết có thể lệch 1 khung hình; trong thực tế (UI game thường
        đứng yên vài trăm ms) điều này không đáng kể."""
        if not isinstance(node, dict):
            return False
        node_type = node.get("type")

        if node_type == "and":
            children = node.get("children") or []
            return len(children) > 0 and all(self._eval_condition_node(c) for c in children)
        if node_type == "or":
            children = node.get("children") or []
            return any(self._eval_condition_node(c) for c in children)
        if node_type == "not":
            children = node.get("children") or []
            return (not self._eval_condition_node(children[0])) if children else False

        if node_type == "image":
            tpl_name = node.get("template")
            if not tpl_name:
                return False
            tpl_path = os.path.join("templates", tpl_name)
            if not os.path.exists(tpl_path):
                return False
            tpl = cv2.imdecode(np.fromfile(tpl_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            coord, _ = self.adb.find_image_on_screen(tpl, threshold=node.get("conf", 0.80),
                                                       region=node.get("region"), mode=node.get("match_mode"))
            return coord is not None

        if node_type == "var":
            cur_val = self.variables.get(node.get("var", ""), 0)
            return self._compare_values(cur_val, node.get("op", "=="), node.get("value", 0))

        if node_type == "ocr":
            box_norm = node.get("box")
            if not box_norm:
                return False
            screen = self.adb.screencap_fast()
            if screen is None:
                return False
            h, w = screen.shape[:2]
            x1 = max(0, int(box_norm[0] * w))
            y1 = max(0, int(box_norm[1] * h))
            x2 = min(w, int(box_norm[2] * w))
            y2 = min(h, int(box_norm[3] * h))
            try:
                text = self.adb.ocr_text_in_box(screen, (x1, y1, x2, y2), lang=node.get("lang", "vie+eng"), charset=node.get("charset", "all"),
                                                      extra_chars=node.get("extra_chars", ""))
            except Exception:
                text = ""
            return self._match_text(text, node.get("text", ""), node.get("match", "contains"))

        return False

    @staticmethod
    def _describe_condition_node(node):
        """Tả ngắn gọn 1 cây điều kiện thành dạng chữ dễ đọc trong Nhật Ký
        Chạy, vd '(Ảnh:icon.png VÀ Biến:hp<10)' - chỉ để LOG, không ảnh
        hưởng logic đánh giá thật (xem _eval_condition_node)."""
        if not isinstance(node, dict):
            return "?"
        t = node.get("type")
        if t in ("and", "or"):
            joiner = " VÀ " if t == "and" else " HOẶC "
            parts = [LogicEngine._describe_condition_node(c) for c in (node.get("children") or [])]
            return "(" + joiner.join(parts) + ")" if parts else "(rỗng)"
        if t == "not":
            children = node.get("children") or []
            return "KHÔNG " + (LogicEngine._describe_condition_node(children[0]) if children else "(rỗng)")
        if t == "image":
            return f"Ảnh:{node.get('template') or '?'}"
        if t == "var":
            return f"Biến:{node.get('var', '?')}{node.get('op', '==')}{node.get('value', '?')}"
        if t == "ocr":
            return f"OCR:\"{node.get('text', '')}\""
        return "?"

    def find_matching_else_or_endif(self, steps, start_ip):
        """Tìm index của ELSE hoặc ENDIF đồng cấp với IF tại start_ip"""
        depth = 0
        for i in range(start_ip + 1, len(steps)):
            act = steps[i].get("action")
            if act in ("if_image", "if_var", "if_ocr", "if_group"):
                depth += 1
            elif act == "else" and depth == 0:
                return i
            elif act == "endif":
                if depth == 0:
                    return i
                depth -= 1
        return len(steps)

    def find_matching_endif(self, steps, start_ip):
        """Tìm index của ENDIF kết thúc khối điều kiện (IF ảnh hoặc IF biến)"""
        depth = 0
        for i in range(start_ip + 1, len(steps)):
            act = steps[i].get("action")
            if act in ("if_image", "if_var", "if_ocr", "if_group"):
                depth += 1
            elif act == "endif":
                if depth == 0:
                    return i
                depth -= 1
        return len(steps)

    def find_matching_group_end(self, steps, start_ip):
        """Tìm index của group_end kết thúc khối Nhóm (group_start) đồng cấp"""
        depth = 0
        for i in range(start_ip + 1, len(steps)):
            act = steps[i].get("action")
            if act == "group_start":
                depth += 1
            elif act == "group_end":
                if depth == 0:
                    return i
                depth -= 1
        return len(steps)

    @staticmethod
    def find_label_index(steps, label_name):
        """Tìm index của bước 'label' có tên trùng label_name TRONG CÙNG 1
        danh sách steps (không xuyên qua group ngoài/group_start lồng nhau
        khác cấp) - dùng làm đích nhảy tới cho on_fail="skip_to_label" của
        wait_image/if_image và bước 'goto_label'. Trả về None nếu không tìm
        thấy."""
        for i, s in enumerate(steps):
            if s.get("action") == "label" and s.get("name") == label_name:
                return i
        return None

    @staticmethod
    def _apply_jitter(step):
        """Đọc field click_jitter=[max_dx, max_dy] (PIXEL THẬT) từ step và
        trả về (dx, dy) NGẪU NHIÊN đều trong khoảng đó mỗi lần gọi - dùng
        để rải nhẹ vị trí click/tap mỗi lần thực hiện, tránh việc click
        ĐÚNG 1 pixel lặp đi lặp lại hàng trăm lần (dấu hiệu bot rất dễ bị
        app/game phát hiện và chặn). Không đặt click_jitter (hoặc đặt
        [0,0]) -> luôn trả về (0,0), giữ nguyên hành vi click chính xác
        tuyệt đối như trước đây."""
        jitter = step.get("click_jitter")
        if not jitter:
            return 0.0, 0.0
        try:
            max_dx, max_dy = float(jitter[0]), float(jitter[1])
        except (TypeError, ValueError, IndexError):
            return 0.0, 0.0
        if max_dx <= 0 and max_dy <= 0:
            return 0.0, 0.0
        return random.uniform(-max_dx, max_dx), random.uniform(-max_dy, max_dy)

    def _poll_single_template(self, tpl, timeout, conf, region, scan_interval, mode=None, turbo=False):
        """Quét màn hình lặp lại (cách nhau scan_interval giây) tìm 1 ẢNH
        ĐƠN cho tới khi THẤY hoặc hết timeout - logic quét DÙNG CHUNG cho
        if_image (qua check_condition), wait_image và wait_vanish, để
        tránh lặp lại y hệt đoạn vòng lặp này ở nhiều nơi (trước đây sửa 1
        nơi rất dễ quên sửa các nơi còn lại). Trả về (coord, score) khi
        thấy, hoặc (None, None) khi hết timeout/bị dừng.

        mode: KIỂU QUÉT ẢNH (step["match_mode"], xem adb_helper.MATCH_MODES);
        None/không truyền = "gray" = cách quét cũ.

        turbo: BƯỚC NÀY có bật Chế Độ Siêu Tốc hay không (step["turbo"]).
        False (mặc định) -> gọi find_image_on_screen() y hệt như trước
        đây, KHÔNG đổi hành vi. True -> gọi find_image_turbo() (hàm
        RIÊNG, xem adb_helper.py) - chỉ bước này đi đường nhanh hơn, mọi
        bước khác không bị ảnh hưởng."""
        if turbo:
            # Động cơ Siêu Tốc mới (turbo_engine.py): chụp RAW song song, KHÔNG
            # sleep(scan_interval). NotImplemented = động cơ không dùng được ->
            # rơi xuống vòng quét cũ bên dưới (y hệt trước đây).
            fast = getattr(self.adb, "turbo_poll_single", None)
            if fast is not None:
                res = fast(tpl, timeout, conf, region, mode, self._should_stop)
                self._warn_turbo_fallback()
                if res is not NotImplemented:
                    return res
        start = time.time()
        finder = self.adb.find_image_turbo if turbo else self.adb.find_image_on_screen
        while time.time() - start < timeout and not self._should_stop():
            coord, score = finder(tpl, threshold=conf, region=region, mode=mode)
            if turbo:
                self._warn_turbo_fallback()
            if coord:
                return coord, score
            time.sleep(scan_interval)
        return None, None

    def _poll_any_template(self, tpl_dict, timeout, conf, region, scan_interval, mode=None, modes=None, turbo=False):
        """Giống _poll_single_template nhưng cho DANH SÁCH nhiều ảnh (khớp 1
        trong nhiều ảnh là được) - DÙNG CHUNG cho if_image (nhánh nhiều
        ảnh) và multi_image (chế độ mặc định, không phải 'Click Tất Cả').
        Trả về (tên_ảnh, coord, score) hoặc (None, None, None).

        mode/modes: KIỂU QUÉT ẢNH chung của bước (step["match_mode"]) và kiểu
        riêng từng ảnh (step["template_modes"]) - xem adb_helper.MATCH_MODES.

        turbo: xem docstring _poll_single_template() - áp dụng tương tự,
        gọi find_any_image_turbo() (hàm RIÊNG) thay vì
        find_any_image_on_screen() khi bước này bật Chế Độ Siêu Tốc."""
        if turbo:
            fast = getattr(self.adb, "turbo_poll_any", None)
            if fast is not None:
                res = fast(tpl_dict, timeout, conf, region, mode, modes, self._should_stop)
                self._warn_turbo_fallback()
                if res is not NotImplemented:
                    return res
        start = time.time()
        finder = self.adb.find_any_image_turbo if turbo else self.adb.find_any_image_on_screen
        while time.time() - start < timeout and not self._should_stop():
            hit_name, hit_pos, score = finder(tpl_dict, threshold=conf, region=region, mode=mode, modes=modes)
            if turbo:
                self._warn_turbo_fallback()
            if hit_pos:
                return hit_name, hit_pos, score
            time.sleep(scan_interval)
        return None, None, None

    def _poll_single_template_until_absent(self, tpl, timeout, conf, region, scan_interval, mode=None):
        """NGƯỢC LẠI _poll_single_template(): quét lặp lại cho tới khi
        KHÔNG CÒN thấy ảnh nữa (đã "biến mất") hoặc hết timeout - dùng
        chung cho if_image (khi wait_for="vanish") và wait_vanish, để 2 nơi
        này luôn quét/biến mất theo đúng 1 kiểu logic như nhau (trước đây
        wait_vanish tự viết riêng 1 vòng lặp y hệt bên dưới -> nay gộp lại
        1 chỗ, sửa 1 lần áp dụng cho cả hai).
        Trả về True nếu đã biến mất trong lúc quét, False nếu hết timeout
        mà ảnh vẫn còn thấy (hoặc bị dừng giữa chừng)."""
        start = time.time()
        while time.time() - start < timeout and not self._should_stop():
            coord, _ = self.adb.find_image_on_screen(tpl, threshold=conf, region=region, mode=mode)
            if not coord:
                return True
            time.sleep(scan_interval)
        return False

    def _poll_any_template_until_absent(self, tpl_dict, timeout, conf, region, scan_interval, mode=None, modes=None):
        """Giống _poll_single_template_until_absent nhưng cho DANH SÁCH
        nhiều ảnh: coi là "đã biến mất" khi KHÔNG CÒN ảnh NÀO trong danh
        sách còn hiện trên màn hình (dùng cho if_image dạng nhóm khi
        wait_for="vanish")."""
        start = time.time()
        while time.time() - start < timeout and not self._should_stop():
            _, hit_pos, _ = self.adb.find_any_image_on_screen(tpl_dict, threshold=conf, region=region, mode=mode, modes=modes)
            if not hit_pos:
                return True
            time.sleep(scan_interval)
        return False

    def check_condition(self, step):
        """Kiểm tra điều kiện của ảnh đơn hoặc danh sách ảnh.

        step["wait_for"] quyết định kiểu điều kiện (mặc định "appear" -
        GIỮ NGUYÊN hành vi cũ, không phá vỡ các kịch bản if_image đã lưu
        trước đây vì field này thường không tồn tại):
          - "appear" (mặc định): ĐÚNG khi ảnh XUẤT HIỆN trong lúc quét
          - "vanish": ĐÚNG khi ảnh BIẾN MẤT (không còn thấy) trong lúc
            quét - cho phép if_image dùng làm "IF ảnh biến mất" với đầy đủ
            nhánh else/endif + on_fail (continue/retry/skip_to_label) y
            hệt if_image kiểu "appear", thay vì chỉ có mỗi bước wait_vanish
            đơn (không rẽ nhánh được)."""
        timeout = step.get("timeout", 2)
        conf = step.get("conf", 0.80)
        region = step.get("region")
        scan_interval = _get_scan_interval(step)
        match_mode = step.get("match_mode")
        template_modes = step.get("template_modes")
        wait_for = step.get("wait_for", "appear")
        turbo = step.get("turbo", False)

        templates = step.get("templates")
        single_tpl = step.get("template")

        if templates:
            tpl_dict = {}
            for fname in templates:
                p = os.path.join("templates", fname)
                if os.path.exists(p):
                    tpl_dict[fname] = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
            if wait_for == "vanish":
                return self._poll_any_template_until_absent(tpl_dict, timeout, conf, region, scan_interval, match_mode, template_modes)
            _, hit_pos, _ = self._poll_any_template(tpl_dict, timeout, conf, region, scan_interval, match_mode, template_modes, turbo=turbo)
            return hit_pos is not None

        elif single_tpl:
            tpl_path = os.path.join("templates", single_tpl)
            if os.path.exists(tpl_path):
                tpl = cv2.imdecode(np.fromfile(tpl_path, dtype=np.uint8), cv2.IMREAD_COLOR)
                if wait_for == "vanish":
                    return self._poll_single_template_until_absent(tpl, timeout, conf, region, scan_interval, match_mode)
                coord, _ = self._poll_single_template(tpl, timeout, conf, region, scan_interval, match_mode)
                return coord is not None

        return False

    def _run_if_block_repeated(self, steps, ip, s, is_root, index_offset):
        """IF (ảnh/đa ảnh/biến/OCR/nhóm điều kiện) có 'Số Lần Lặp' != 1 hoặc lặp theo THỜI GIAN:
        chạy lặp CẢ KHỐI IF...[ELSE...]...ENDIF (mỗi lượt đánh giá lại điều kiện từ đầu) - giống
        cách khối Nhóm lặp. TRƯỚC ĐÂY nhánh IF của execute_steps() không đọc 'repeat'/'repeat_mode'
        nên IF luôn chỉ chạy 1 lần dù đã đặt lặp nhiều lần. Trả về index bước kế tiếp cần chạy."""
        end_idx = self.find_matching_endif(steps, ip)
        block = list(steps[ip:end_idx + 1])
        inner = dict(s)
        inner["repeat"] = 1
        for k in ("repeat_mode", "repeat_ms", "repeat_seconds"):
            inner.pop(k, None)
        inner["_repeat_wrapped"] = True   # chỉ nằm trong bộ nhớ: cho phép skip_to_label nhảy RA NGOÀI khối
        block[0] = inner
        sub_offset = None if index_offset is None else index_offset + ip
        label = s.get("comment") or s.get("action")
        try:
            if s.get("repeat_mode") == "time":
                duration = self._get_repeat_ms(s) / 1000.0
                t0 = time.time()
                n = 0
                while time.time() - t0 < duration and not self._should_stop():
                    n += 1
                    iter_start = time.time()
                    self.execute_steps(block, is_root=False, index_offset=sub_offset)
                    if time.time() - iter_start < 0.02:   # tránh ngốn CPU khi khối chạy tức thì
                        time.sleep(0.02)
                self._log("info", f"  {label}: đã lặp {n} lượt trong {duration:g}s")
            else:
                total = max(0, int(self._resolve_step_number(s.get("repeat", 1), default=1)))
                if total == 0:
                    self._log("info", f"  {label}: lặp 0 lần -> BỎ QUA cả khối IF")
                for i in range(total):
                    if self._should_stop():
                        break
                    self._log("info", f"  {label} - lượt {i + 1}/{total}")
                    self.execute_steps(block, is_root=False, index_offset=sub_offset)
        except GotoLabelSignal as gs:
            tgt = self.find_label_index(steps, gs.label_name)
            if tgt is not None:
                self._log("warn", f"⏭ Nhảy tới nhãn '{gs.label_name}' (thoát khỏi IF lặp)")
                return tgt
            if not is_root:
                raise
            self._log("error", f"Không tìm thấy nhãn '{gs.label_name}' - bỏ qua, chạy tiếp sau khối IF")
        return end_idx + 1

    def execute_steps(self, steps, is_root=True, index_offset=0):
        """Duyệt và thực thi danh sách bước với cây logic Jump Table.

        index_offset: index_offset + ip = VỊ TRÍ THẬT của bước hiện tại
        trong danh sách bước gốc đã đưa cho step_notifier (self.steps hoặc
        tập con "Chạy Đã Chọn") - cần cộng dồn qua từng lớp đệ quy để
        BÔI DÙNG ĐÚNG DÒNG THẬT trên cây kể cả khi đang chạy BÊN TRONG 1
        khối Nhóm lồng (group_start/group_end), thay vì bị "đứng hình" ở
        đúng dòng group_start suốt cả lúc khối đó đang chạy như trước đây
        (lúc đó step_notifier chỉ được gọi ở lệnh gọi CẤP GỐC - is_root -
        nên mọi bước con bên trong 1 vòng lặp Nhóm hoàn toàn không được
        báo ra ngoài). Truyền index_offset=None khi 'steps' là 1 danh sách
        RỜI, không liên quan gì tới danh sách gốc (vd Nhóm Ngoài nạp từ 1
        file .json riêng, action="group") - lúc đó KHÔNG có dòng thật nào
        trên cây để ánh xạ tới nên CỐ TÌNH bỏ qua, không gọi step_notifier
        cho các bước bên trong (giữ nguyên bôi đen ở đúng dòng 'group' bên
        ngoài cho tới khi chạy xong nhóm ngoài đó - cây hiển thị không có
        chỗ nào để hiện các bước riêng của nhóm ngoài)."""
        if is_root:
            # Chỉ đặt (và reset) deadline ở lần gọi CẤP GỐC - các lệnh gọi
            # đệ quy bên trong (is_root=False, vd group_start/group ngoài)
            # KHÔNG được reset lại, để giới hạn áp dụng cho TOÀN BỘ 1 lần
            # chạy chứ không phải riêng từng Nhóm con.
            self._deadline = time.time() + self.max_runtime_seconds if self.max_runtime_seconds else None
            self._deadline_logged = False
            self._hung_logged = False
        ip = 0
        while ip < len(steps) and not self._should_stop():
            s = steps[ip]
            act = s.get("action")
            delay = s.get("delay", 1.0)
            # repeat = 0 (hoặc biểu thức ra <= 0, vd {sl}-1 khi {sl}=1) nghĩa là
            # BỎ QUA bước (chạy 0 lần) - TRƯỚC ĐÂY bị ép tối thiểu 1 lần.
            repeat = max(0, int(self._resolve_step_number(s.get("repeat", 1), default=1)))

            if index_offset is not None and self.step_notifier:
                self.step_notifier(index_offset + ip)

            # 1. Điều kiện IF (theo ẢNH, BIẾN, OCR, hoặc CÂY ĐIỀU KIỆN GỘP)
            if act in ("if_image", "if_var", "if_ocr", "if_group"):
                if not s.get("_repeat_wrapped") and (s.get("repeat_mode") == "time" or repeat != 1):
                    ip = self._run_if_block_repeated(steps, ip, s, is_root, index_offset)
                    continue
                if act == "if_image":
                    # on_fail="retry": nếu SAI (chưa thấy ảnh) thử quét lại
                    # thêm on_fail_retries lần nữa (mỗi lần vẫn quét đủ
                    # timeout) trước khi coi hẳn là SAI - dùng khi ảnh có
                    # thể xuất hiện MUỘN hơn 1 chút so với timeout đã đặt,
                    # thay vì phải tự dựng thêm group_start/if_var bên
                    # ngoài chỉ để "thử lại".
                    retries_total = 1
                    if s.get("on_fail") == "retry":
                        retries_total += max(0, int(s.get("on_fail_retries", 1)))
                    matched = False
                    for attempt in range(retries_total):
                        if attempt > 0:
                            self._log("info", f"🔁 IF Ảnh: thử lại lần {attempt + 1}/{retries_total}")
                        matched = self.check_condition(s)
                        if matched or self._should_stop():
                            break
                    # wait_for="vanish": IF ảnh BIẾN MẤT (ngược "appear" mặc
                    # định) - cho phép rẽ nhánh true/false y hệt IF Ảnh
                    # thường, thay vì chỉ có wait_vanish (không else được).
                    if s.get("wait_for") == "vanish":
                        if s.get("templates"):
                            cond_desc = f"IF cả {len(s.get('templates'))} ảnh đều biến mất"
                        else:
                            cond_desc = f"IF ảnh '{s.get('template')}' biến mất" if s.get("template") else "IF ảnh biến mất (⚠️ CHƯA CHỌN ẢNH)"
                    else:
                        if s.get("templates"):
                            cond_desc = f"IF thấy 1 trong {len(s.get('templates'))} ảnh"
                        else:
                            cond_desc = f"IF thấy ảnh '{s.get('template')}'" if s.get("template") else "IF ảnh (⚠️ CHƯA CHỌN ẢNH)"
                elif act == "if_var":
                    var_name = s.get("var", "")
                    op = s.get("op", "==")
                    target_val = s.get("value", 0)
                    cur_val = self.variables.get(var_name, 0)
                    matched = self._compare_values(cur_val, op, target_val)
                    cond_desc = f"IF biến {var_name} ({cur_val}) {op} {target_val}"
                elif act == "if_ocr":
                    # IF OCR: quét chữ lặp lại trong 1 vùng cho tới khi khớp
                    # (chứa/khớp đúng/regex) hoặc hết timeout - tận dụng lại
                    # ocr_text_in_box() đã có, KHÔNG cần dựng riêng 1 bước
                    # ocr_text + if_var như trước (2 bước gộp thành 1).
                    box_norm = s.get("box")
                    expected_text = s.get("text", "")
                    match_mode_txt = s.get("match", "contains")
                    timeout = s.get("timeout", 3)
                    scan_interval = _get_scan_interval(s)
                    matched = False
                    last_ocr_value = ""
                    if box_norm:
                        start_poll = time.time()
                        while time.time() - start_poll < timeout and not self._should_stop():
                            screen = self.adb.screencap_fast()
                            if screen is not None:
                                h, w = screen.shape[:2]
                                x1 = max(0, int(box_norm[0] * w))
                                y1 = max(0, int(box_norm[1] * h))
                                x2 = min(w, int(box_norm[2] * w))
                                y2 = min(h, int(box_norm[3] * h))
                                try:
                                    last_ocr_value = self.adb.ocr_text_in_box(screen, (x1, y1, x2, y2), lang=s.get("lang", "vie+eng"), charset=s.get("charset", "all"),
                                                                              extra_chars=s.get("extra_chars", ""))
                                except Exception as e:
                                    last_ocr_value = ""
                                    self._log("error", f"Lỗi khi quét OCR cho IF OCR: {e}")
                                if self._match_text(last_ocr_value, expected_text, match_mode_txt):
                                    matched = True
                                    break
                            time.sleep(scan_interval)
                        # Lưu text đọc được vào biến (nếu có đặt 'var') để
                        # dùng tiếp ở bước sau - tiện khi vừa muốn LÀM ĐIỀU
                        # KIỆN vừa muốn LẤY nội dung thật (vd số lượng, tên).
                        if s.get("var"):
                            self.variables[s["var"]] = last_ocr_value
                        # Khớp rồi thì CLICK vào GIỮA vùng đã quét (không
                        # phải toạ độ chữ cụ thể - OCR chỉ biết cả vùng box
                        # chứ không biết chữ nằm CHÍNH XÁC ở đâu trong đó).
                        if matched and s.get("click"):
                            cx = (box_norm[0] + box_norm[2]) / 2.0
                            cy = (box_norm[1] + box_norm[3]) / 2.0
                            jx, jy = self._apply_jitter(s)
                            self.adb.tap_px(cx * self.adb.screen_w + jx, cy * self.adb.screen_h + jy)
                        cond_desc = f"IF OCR \"{expected_text}\" ({match_mode_txt}) -> đọc được \"{last_ocr_value}\""
                    else:
                        cond_desc = "IF OCR (⚠️ CHƯA CHỌN VÙNG QUÉT)"
                else:  # if_group
                    # IF Nhóm Điều Kiện: cây AND/OR/NOT lồng nhau tuỳ ý, xem
                    # _eval_condition_node(). Toàn cây được re-check mỗi
                    # scan_interval giây cho tới khi ĐÚNG hoặc hết timeout -
                    # y hệt if_image/if_ocr, chỉ khác là mỗi lần re-check
                    # đánh giá CẢ CÂY thay vì 1 điều kiện đơn.
                    tree = s.get("tree")
                    timeout = s.get("timeout", 3)
                    scan_interval = _get_scan_interval(s)
                    matched = False
                    if tree:
                        start_poll = time.time()
                        while True:
                            matched = self._eval_condition_node(tree)
                            if matched or self._should_stop() or time.time() - start_poll >= timeout:
                                break
                            time.sleep(scan_interval)
                        cond_desc = f"IF Nhóm Điều Kiện {self._describe_condition_node(tree)}"
                    else:
                        cond_desc = "IF Nhóm Điều Kiện (⚠️ CHƯA CẤU HÌNH CÂY ĐIỀU KIỆN)"
                self._log("success" if matched else "info", f"{cond_desc} -> {'ĐÚNG' if matched else 'SAI'}")
                if matched:
                    ip += 1
                else:
                    # on_fail="skip_to_label": thay vì đi theo ELSE/ENDIF
                    # như bình thường, NHẢY THẲNG tới 1 bước 'label' cùng
                    # cấp - dùng để rẽ nhánh xa (vd bỏ qua nguyên 1 đoạn
                    # kịch bản) mà không cần lồng thêm group_start/if_var.
                    # Áp dụng chung cho MỌI loại IF (trước đây chỉ if_image)
                    # vì cơ chế nhảy nhãn không phụ thuộc loại điều kiện.
                    if s.get("on_fail") == "skip_to_label":
                        label_name = s.get("skip_to_label_name")
                        target_label = self.find_label_index(steps, label_name) if label_name else None
                        if target_label is not None:
                            self._log("warn", f"⏭ {cond_desc} -> nhảy tới nhãn '{label_name}'")
                            ip = target_label
                            continue
                        else:
                            if s.get("_repeat_wrapped") and label_name:
                                raise GotoLabelSignal(label_name)   # nhãn nằm NGOÀI khối IF lặp
                            self._log("error", f"on_fail=skip_to_label nhưng không tìm thấy nhãn '{label_name}' - dùng ELSE/ENDIF như bình thường")
                    target = self.find_matching_else_or_endif(steps, ip)
                    if target < len(steps) and steps[target].get("action") == "else":
                        ip = target + 1
                    else:
                        ip = target + 1
                continue

            # 2. Nhánh ELSE
            elif act == "else":
                target = self.find_matching_endif(steps, ip)
                ip = target + 1
                continue

            # 3. Đóng khối ENDIF
            elif act == "endif":
                ip += 1
                continue

            # 3b. Khối Nhóm (Group) - hiển thị dạng cây thu gọn/mở rộng, hỗ trợ lặp theo số lần hoặc theo thời gian
            elif act == "group_start":
                end_idx = self.find_matching_group_end(steps, ip)
                sub_steps = steps[ip + 1:end_idx]
                # Vị trí THẬT của dòng đầu tiên bên trong khối Nhóm này -
                # dùng để bôi đen ĐÚNG dòng con đang chạy (xem docstring
                # execute_steps() ở trên), thay vì để nguyên dòng
                # group_start suốt cả lúc khối đang chạy.
                sub_offset = None if index_offset is None else index_offset + ip + 1
                group_label = s.get("comment") or "(không tên)"
                self._log("info", f"▶ Bắt đầu NHÓM '{group_label}'")
                goto_name = None
                try:
                    if s.get("repeat_mode") == "time":
                        duration = self._get_repeat_ms(s) / 1000.0
                        t0 = time.time()
                        while time.time() - t0 < duration and not self._should_stop():
                            iter_start = time.time()
                            try:
                                self.execute_steps(sub_steps, is_root=False, index_offset=sub_offset)
                            except ContinueGroupSignal:
                                pass
                            # An toàn CPU: nếu Nhóm RỖNG hoặc chạy xong gần
                            # như tức thì (vd chỉ có set_var/inc_var, hoặc
                            # continue_group ngay bước đầu) thì vòng lặp
                            # 'while' này sẽ quay hàng nghìn lần/giây ngốn
                            # trọn 1 lõi CPU tới hết duration mà không làm
                            # thêm được gì - kẹp tối thiểu 20ms mỗi lượt để
                            # tránh việc đó. Không ảnh hưởng kịch bản bình
                            # thường vì mỗi bước vốn đã có delay >= vài
                            # trăm ms.
                            if time.time() - iter_start < 0.02:
                                time.sleep(0.02)
                    else:
                        group_repeat = max(0, int(self._resolve_step_number(s.get("repeat", 1), default=1)))
                        if group_repeat == 0:
                            self._log("info", f"  Nhóm '{group_label}' - lặp 0 lần -> BỎ QUA")
                        for loop_i in range(group_repeat):
                            if self._should_stop():
                                break
                            if group_repeat > 1:
                                self._log("info", f"  Nhóm '{group_label}' - lượt {loop_i + 1}/{group_repeat}")
                            try:
                                self.execute_steps(sub_steps, is_root=False, index_offset=sub_offset)
                            except ContinueGroupSignal:
                                continue
                except BreakGroupSignal:
                    # Gặp bước 'break_group' bên trong nhóm này (vd IF (Biến)
                    # đủ điều kiện -> Dừng vòng lặp) -> thoát vòng lặp NHÓM
                    # HIỆN TẠI ngay lập tức, không lặp thêm nữa.
                    self._log("warn", f"⛔ Dừng vòng lặp NHÓM '{group_label}' (break_group)")
                except GotoLabelSignal as gs:
                    # Bước 'goto_label' bên trong Nhóm muốn nhảy tới nhãn
                    # nằm NGOÀI Nhóm - thoát Nhóm rồi tìm nhãn ở cấp này.
                    goto_name = gs.label_name
                self._log("info", f"■ Kết thúc NHÓM '{group_label}'")
                if goto_name is not None:
                    tgt = self.find_label_index(steps, goto_name)
                    if tgt is not None:
                        self._log("warn", f"⏭ Nhảy tới nhãn '{goto_name}' (thoát khỏi NHÓM '{group_label}')")
                        ip = tgt
                        continue
                    elif not is_root:
                        raise GotoLabelSignal(goto_name)
                    else:
                        self._log("error", f"goto_label: không tìm thấy nhãn '{goto_name}' - bỏ qua, chạy tiếp sau Nhóm")
                ip = end_idx + 1
                continue

            elif act == "group_end":
                ip += 1
                continue

            # 3c. Nhãn (label) - điểm neo để on_fail="skip_to_label" của
            # wait_image/if_image nhảy tới, bản thân bước này không làm gì
            # khi chạy tới, chỉ dùng để ĐÁNH DẤU vị trí.
            elif act == "label":
                ip += 1
                continue

            # 3d. Nhảy Tới Nhãn (goto_label / "Skip to Label") - nhảy VÔ ĐIỀU
            # KIỆN tới 1 bước 'label' (không cần điều kiện thất bại như
            # on_fail=skip_to_label). Tên nhãn lưu ở 'skip_to_label_name'
            # (dùng chung tên field với on_fail để validator/sửa nhãn dùng
            # lại được). Nhãn nằm ở CẤP NGOÀI (bước nhảy đặt trong Nhóm) ->
            # ném GotoLabelSignal để thoát Nhóm rồi cấp ngoài tìm tiếp.
            elif act == "goto_label":
                label_name = str(s.get("skip_to_label_name") or "").strip()
                target_label = self.find_label_index(steps, label_name) if label_name else None
                if target_label is not None:
                    self._log("warn", f"⏭ Nhảy tới nhãn '{label_name}'")
                    if target_label <= ip:
                        # Nhảy NGƯỢC (tạo vòng lặp) - nghỉ chút để không
                        # ngốn CPU nếu đoạn lặp không có bước nào chờ.
                        time.sleep(0.05)
                    ip = target_label
                    continue
                elif label_name and not is_root:
                    self._log("info", f"⏭ Nhãn '{label_name}' không có ở cấp này - tìm ở cấp ngoài")
                    raise GotoLabelSignal(label_name)
                else:
                    if label_name:
                        self._log("error", f"goto_label: không tìm thấy nhãn '{label_name}' - bỏ qua, chạy tiếp bước kế tiếp")
                    else:
                        self._log("error", "goto_label: chưa chọn nhãn đích - bỏ qua, chạy tiếp bước kế tiếp")
                    ip += 1
                    continue

            # 4. Hành động thực thi
            repeat_mode = s.get("repeat_mode", "count")
            repeat_seconds = self._get_repeat_ms(s) / 1000.0
            loop_start = time.time()
            loop_count = 0
            # jump_target: khi on_fail="skip_to_label" của wait_image kích
            # hoạt (không tìm thấy ảnh sau khi đã thử hết on_fail_retries),
            # đặt biến này thay vì đơn giản ip+=1 ở cuối - đọc lại ngay sau
            # vòng lặp lặp-lại (repeat) bên dưới để NHẢY tới đúng nhãn thay
            # vì tiếp tục sang bước kế tiếp như bình thường.
            jump_target = None
            while not self._should_stop():
                if repeat_mode == "time":
                    if time.time() - loop_start >= repeat_seconds:
                        break
                else:
                    if loop_count >= repeat:
                        break
                loop_count += 1

                try:
                    if act == "tap":
                        pos = s.get("pos")
                        if pos:
                            # click_jitter: rải nhẹ vị trí click mỗi lần
                            # (xem docstring _apply_jitter) - cộng vào toạ
                            # độ PIXEL THẬT (không cộng trực tiếp vào tỉ lệ
                            # 0..1) để tránh lệch tỉ lệ khi màn hình lớn.
                            jx, jy = self._apply_jitter(s)
                            px = pos[0] * self.adb.screen_w + jx
                            py = pos[1] * self.adb.screen_h + jy
                            jitter_txt = f" (rải {jx:+.0f},{jy:+.0f}px)" if (jx or jy) else ""
                            # hold_ms > 0: Giữ Tay (long-press/long-click) -
                            # CHẠM XUỐNG, đứng yên hold_ms mili-giây rồi mới
                            # NHẤC LÊN, dùng cho UI cần giữ (menu ngữ cảnh,
                            # bắt đầu kéo-thả...) mà tap nhanh không đủ.
                            hold_ms = s.get("hold_ms", 0)
                            if hold_ms and hold_ms > 0:
                                self.adb.tap_hold_px(px, py, hold_ms)
                                self._log("info", f"Giữ Tay [{int(pos[0]*100)}%, {int(pos[1]*100)}%] ({hold_ms}ms){jitter_txt}")
                            else:
                                self.adb.tap_px(px, py)
                                self._log("info", f"Tap [{int(pos[0]*100)}%, {int(pos[1]*100)}%]{jitter_txt}")
                        else:
                            self._log("error", "Bước Tap chưa chọn tọa độ - hãy bấm đúp/chuột phải vào bước này để chọn")

                    elif act == "swipe":
                        p1 = s.get("from")
                        p2 = s.get("to")
                        if p1 and p2:
                            duration = s.get("duration", 250)
                            hold_ms = s.get("hold_ms", 0)
                            # click_jitter áp dụng RIÊNG cho từng đầu (2 lần
                            # random độc lập) để mỗi lần vuốt lệch nhẹ khác
                            # nhau cả điểm đầu lẫn điểm cuối, không chỉ dịch
                            # song song nguyên đường vuốt 1 khối.
                            jx1, jy1 = self._apply_jitter(s)
                            jx2, jy2 = self._apply_jitter(s)
                            x1 = p1[0] * self.adb.screen_w + jx1
                            y1 = p1[1] * self.adb.screen_h + jy1
                            x2 = p2[0] * self.adb.screen_w + jx2
                            y2 = p2[1] * self.adb.screen_h + jy2
                            if hold_ms and hold_ms > 0:
                                # Kéo & Giữ: dùng cho thanh trượt (slider) - xem
                                # docstring adb_helper.py::swipe_hold() để hiểu
                                # vì sao cần giữ yên tại đích trước khi nhả tay.
                                self.adb.swipe_hold_px(x1, y1, x2, y2,
                                                        move_duration_ms=duration, hold_ms=hold_ms)
                                self._log("info", f"Kéo & Giữ [{int(p1[0]*100)}%,{int(p1[1]*100)}%] -> [{int(p2[0]*100)}%,{int(p2[1]*100)}%] (giữ {hold_ms}ms)")
                            else:
                                self.adb.swipe_px(x1, y1, x2, y2, duration)
                                self._log("info", f"Swipe [{int(p1[0]*100)}%,{int(p1[1]*100)}%] -> [{int(p2[0]*100)}%,{int(p2[1]*100)}%]")
                        else:
                            self._log("error", "Bước Swipe chưa chọn điểm đầu/cuối - hãy bấm đúp/chuột phải vào bước này để chọn")

                    elif act == "swipe_path":
                        # Vuốt qua NHIỀU ĐIỂM liên tiếp trong 1 lần chạm
                        # (khác swipe thường chỉ có điểm đầu/cuối) - xem
                        # docstring adb_helper.py::swipe_path_px(). Mỗi
                        # điểm lưu dạng tỉ lệ [x, y] 0..1 trong field
                        # "points".
                        points_norm = s.get("points")
                        if points_norm and len(points_norm) >= 2:
                            points_px = []
                            for px_norm, py_norm in points_norm:
                                jx, jy = self._apply_jitter(s)
                                points_px.append((
                                    px_norm * self.adb.screen_w + jx,
                                    py_norm * self.adb.screen_h + jy,
                                ))
                            duration = s.get("duration", 400)
                            hold_ms = s.get("hold_ms", 0)
                            self.adb.swipe_path_px(points_px, duration_ms=duration, hold_ms=hold_ms)
                            pts_txt = " → ".join(f"[{int(nx*100)}%,{int(ny*100)}%]" for nx, ny in points_norm)
                            hold_txt = f" (giữ cuối {hold_ms}ms)" if hold_ms else ""
                            self._log("info", f"Vuốt {len(points_norm)} điểm: {pts_txt}{hold_txt}")
                        else:
                            self._log("error", "Bước Vuốt Nhiều Điểm cần ít nhất 2 điểm - hãy bấm đúp/chuột phải vào bước này để chọn lại")

                    elif act == "zoom":
                        center = s.get("center")
                        if center:
                            r1 = s.get("start_radius", 70)
                            r2 = s.get("end_radius", 260)
                            angle = s.get("angle", 90)
                            duration = s.get("duration", 400)
                            method = self.adb.pinch_zoom(center[0], center[1], r1, r2, angle_deg=angle, duration_ms=duration)
                            method_txt = "multi-touch thật" if method == "sendevent" else "⚠️ dự phòng (2 vuốt song song - có thể KHÔNG được app nhận diện)"
                            self._log("info", f"Zoom {'To' if r2 > r1 else 'Nhỏ'} tại [{int(center[0]*100)}%,{int(center[1]*100)}%] (bán kính {int(r1)}->{int(r2)}px, {duration}ms, {method_txt})")
                        else:
                            self._log("error", "Bước Zoom chưa chọn tâm cử chỉ - hãy bấm đúp/chuột phải vào bước này để chọn")

                    elif act == "auto_merge2048":
                        # Bước "🧩 Auto Merge2048" - dùng THẲNG self.adb đã kết
                        # nối sẵn của engine (screencap_fast()/swipe_px()) chứ
                        # không mở kết nối ADB riêng. Xem run_auto_merge2048_step
                        # trong merge2048_bot.py: chụp -> nhận diện lưới 4x4 ->
                        # Expectimax -> vuốt, lặp tới khi hết nước/bị Dừng/hết
                        # max_moves/max_seconds cấu hình trong bước.
                        run_auto_merge2048_step(
                            self.adb, s,
                            should_stop=self._should_stop,
                            log=self._log,
                        )

                    elif act == "auto_photo":
                        # Bước "📸 Auto Chụp Ảnh" (tiệm ảnh): dùng THẲNG self.adb
                        # của engine như auto_merge2048. Xem photo_bot.py: đọc
                        # vùng vàng trên thanh đo -> bấm thử từng Nền/Trang Trí,
                        # đọc vạch chỉ để đo điểm -> chọn tổ hợp vào vùng vàng
                        # -> bấm "Chụp ảnh" (trừ khi bước đặt shoot=false = test).
                        run_auto_photo_step(
                            self.adb, s,
                            should_stop=self._should_stop,
                            log=self._log,
                        )

                    elif act == "auto_thtg":
                        # Bước "⚔️ Auto Ngưu Ma Vương": dùng THẲNG self.adb của
                        # engine như auto_photo. Xem thtg_bot.py: chụp -> nhận diện lưới
                        # 7x7 -> beam search đường đi 8 hướng -> bấm từng ô -> chờ rơi
                        # quái mới -> lặp; nộ đầy thì bấm Chiến. test=true: chỉ tính.
                        run_auto_thtg_step(
                            self.adb, s,
                            should_stop=self._should_stop,
                            log=self._log,
                        )

                    elif act == "auto_pig":
                        # Bước "🐷 Auto Lợn Giống" (kiểu Suika): dùng THẲNG self.adb của
                        # engine như auto_thtg. Xem pig_bot.py: chụp -> nhận diện heo (viền
                        # màu + bán kính) -> mô phỏng Pymunk thử các vị trí thả -> bấm ->
                        # chờ heo lăn yên -> lặp; dừng khi thể lực < min_stamina/hết lượt/Dừng.
                        run_auto_pig_step(
                            self.adb, s,
                            should_stop=self._should_stop,
                            log=self._log,
                        )

                    elif act == "wait_image":
                        # s.get("template", "") CHỈ trả về "" khi key "template"
                        # KHÔNG TỒN TẠI - với bước RỖNG (tạo qua ESC) key này
                        # LUÔN TỒN TẠI nhưng giá trị là None, nên phải "or \"\"" 
                        # thêm 1 lớp nữa, nếu không os.path.join() sẽ crash vì
                        # nhận None thay vì str.
                        tpl_name = s.get("template") or ""
                        tpl_path = os.path.join("templates", tpl_name)
                        if tpl_name and os.path.exists(tpl_path):
                            tpl = cv2.imdecode(np.fromfile(tpl_path, dtype=np.uint8), cv2.IMREAD_COLOR)
                            timeout = s.get("timeout", 8)
                            conf = s.get("conf", 0.80)
                            region = s.get("region")
                            scan_interval = _get_scan_interval(s)
                            on_fail = s.get("on_fail", "continue")
                            # on_fail="retry": nếu hết timeout mà vẫn KHÔNG
                            # thấy ảnh, thử quét lại thêm on_fail_retries lần
                            # nữa (mỗi lần lại quét đủ timeout mới) trước khi
                            # coi hẳn là KHÔNG THẤY - thay cho việc phải tự
                            # dựng group_start lặp lại bên ngoài chỉ để retry.
                            retries_total = 1
                            if on_fail == "retry":
                                retries_total += max(0, int(s.get("on_fail_retries", 1)))
                            found = False
                            for attempt in range(retries_total):
                                if attempt > 0:
                                    self._log("info", f"🔁 Thử lại lần {attempt + 1}/{retries_total} tìm ảnh '{tpl_name}'")
                                coord, score = self._poll_single_template(tpl, timeout, conf, region, scan_interval, s.get("match_mode"), turbo=s.get("turbo", False))
                                if coord:
                                    found = True
                                    if s.get("click", True):
                                        # click_delay_after_found: CHỜ THÊM N giây SAU
                                        # KHI VỪA THẤY ẢNH, TRƯỚC KHI click - khác với
                                        # trường "delay" chung của bước (áp dụng SAU khi
                                        # cả bước đã chạy xong, tức SAU khi đã click).
                                        # Dùng khi cần chờ hiệu ứng/animation của nút
                                        # chạy xong hẳn rồi mới bấm, thay vì bấm ngay
                                        # lúc vừa nhận diện được ảnh.
                                        pre_click_delay = float(s.get("click_delay_after_found", 0) or 0)
                                        if pre_click_delay > 0:
                                            self._log("info", f"⏳ Thấy ảnh '{tpl_name}' - chờ {pre_click_delay}s trước khi click...")
                                            deadline_click = time.time() + pre_click_delay
                                            while time.time() < deadline_click and not self._should_stop():
                                                time.sleep(min(0.1, deadline_click - time.time()))
                                        if self._should_stop():
                                            break
                                        # Lệch điểm click (click_offset, đơn vị PIXEL
                                        # THẬT trên màn hình thiết bị) - cộng thêm vào
                                        # toạ độ TÂM ảnh vừa tìm thấy trước khi click,
                                        # dùng khi điểm cần bấm không trùng tâm ảnh mẫu
                                        # (vd ảnh mẫu là icon nhỏ nhưng nút bấm thật kéo
                                        # dài sang 1 bên). Mặc định [0,0] = click đúng tâm.
                                        off_x, off_y = (s.get("click_offset") or [0, 0])
                                        # click_jitter: rải nhẹ thêm 1 khoảng NGẪU NHIÊN
                                        # (xem docstring _apply_jitter) - tránh click
                                        # đúng 1 pixel lặp lại hàng trăm lần, dễ bị app/
                                        # game phát hiện là bot.
                                        jx, jy = self._apply_jitter(s)
                                        px = coord[0] * self.adb.screen_w + off_x + jx
                                        py = coord[1] * self.adb.screen_h + off_y + jy
                                        # tap_fast_px: bắn lệnh click NGAY, không chờ
                                        # adb.exe thoát hẳn - giảm độ trễ giữa lúc VỪA
                                        # thấy ảnh và lúc CLICK thật sự được gửi đi (chỉ
                                        # áp dụng riêng cho wait_image theo yêu cầu, các
                                        # bước ảnh khác giữ nguyên tap()); dùng bản "_px"
                                        # (toạ độ pixel tuyệt đối) vì cộng offset có thể
                                        # vô tình rơi vào khoảng 0..1 khiến tap_fast()
                                        # thường hiểu nhầm là toạ độ tỉ lệ.
                                        # turbo=True: dùng tap_turbo_px() (socket thẳng
                                        # tới ADB server, không spawn tiến trình mới) -
                                        # chỉ khi bước này bật Chế Độ Siêu Tốc.
                                        if s.get("turbo"):
                                            self.adb.tap_turbo_px(px, py)
                                            self._warn_turbo_fallback()
                                        else:
                                            self.adb.tap_fast_px(px, py)
                                        off_txt = f" (lệch {off_x:+d},{off_y:+d}px)" if (off_x or off_y) else ""
                                        jitter_txt = f" (rải {jx:+.0f},{jy:+.0f}px)" if (jx or jy) else ""
                                        self._log("success", f"Thấy ảnh '{tpl_name}' (khớp {score:.2f}) -> đã click {coord}{off_txt}{jitter_txt}{self._turbo_click_txt(s)}")
                                    else:
                                        self._log("success", f"Thấy ảnh '{tpl_name}' (khớp {score:.2f}) - CHỈ làm điều kiện, không click")
                                if found or self._should_stop():
                                    break
                            if not found:
                                self._log("warn", f"KHÔNG thấy ảnh '{tpl_name}' sau {timeout}s" + (f" (đã thử {retries_total} lần)" if retries_total > 1 else ""))
                                # on_fail="skip_to_label": nhảy thẳng tới 1
                                # bước 'label' cùng cấp thay vì tiếp tục sang
                                # bước kế tiếp như bình thường - dùng để rẽ
                                # nhánh khi KHÔNG thấy ảnh mà không cần tự
                                # dựng group_start/if_var bên ngoài.
                                if on_fail == "skip_to_label":
                                    label_name = s.get("skip_to_label_name")
                                    target_label = self.find_label_index(steps, label_name) if label_name else None
                                    if target_label is not None:
                                        self._log("warn", f"⏭ Không thấy ảnh -> nhảy tới nhãn '{label_name}'")
                                        jump_target = target_label
                                    else:
                                        self._log("error", f"on_fail=skip_to_label nhưng không tìm thấy nhãn '{label_name}' - tiếp tục bước kế tiếp như bình thường")
                        else:
                            self._log("error", f"Không tìm thấy file ảnh mẫu '{tpl_name}' trong thư mục templates" if tpl_name
                                       else "Bước Tìm & Click Ảnh chưa chọn ảnh - hãy bấm đúp/chuột phải vào bước này để chọn")
                        if jump_target is not None:
                            # Đã kích hoạt skip_to_label - thoát NGAY khỏi
                            # vòng lặp-lại (repeat) của bước này, không thử
                            # thêm lần nào nữa, để nhảy tới nhãn ở cuối vòng
                            # 'while' repeat bên dưới.
                            break

                    elif act == "wait_vanish":
                        # Chờ ẢNH BIẾN MẤT (ngược lại wait_image - chờ ảnh
                        # XUẤT HIỆN): dùng khi cần đợi 1 popup/loading đóng
                        # lại rồi mới làm bước kế tiếp. Đây là bước ĐƠN
                        # (không rẽ nhánh true/false được) - nếu cần LÀM GÌ
                        # KHÁC NHAU tuỳ biến mất hay không, dùng if_image
                        # với wait_for="vanish" thay vì bước này (có đầy đủ
                        # else/endif). Quét dùng CHUNG 1 hàm với if_image
                        # (wait_for="vanish") qua _poll_single_template_
                        # until_absent(), để sửa 1 nơi áp dụng cho cả hai.
                        tpl_name = s.get("template") or ""
                        tpl_path = os.path.join("templates", tpl_name)
                        if tpl_name and os.path.exists(tpl_path):
                            tpl = cv2.imdecode(np.fromfile(tpl_path, dtype=np.uint8), cv2.IMREAD_COLOR)
                            timeout = s.get("timeout", 8)
                            conf = s.get("conf", 0.80)
                            region = s.get("region")
                            scan_interval = _get_scan_interval(s)
                            on_fail = s.get("on_fail", "continue")
                            # on_fail="retry": giống wait_image - nếu hết
                            # timeout mà ảnh vẫn còn, thử chờ lại thêm
                            # on_fail_retries lần (mỗi lần quét đủ timeout
                            # mới) trước khi coi hẳn là KHÔNG biến mất.
                            retries_total = 1
                            if on_fail == "retry":
                                retries_total += max(0, int(s.get("on_fail_retries", 1)))
                            vanished = False
                            start = time.time()
                            for attempt in range(retries_total):
                                if attempt > 0:
                                    self._log("info", f"🔁 Thử lại lần {attempt + 1}/{retries_total} chờ ảnh '{tpl_name}' biến mất")
                                start = time.time()
                                vanished = self._poll_single_template_until_absent(tpl, timeout, conf, region, scan_interval, s.get("match_mode"))
                                if vanished or self._should_stop():
                                    break
                            if vanished:
                                self._log("success", f"Ảnh '{tpl_name}' đã biến mất sau {time.time() - start:.1f}s")
                            else:
                                self._log("warn", f"Ảnh '{tpl_name}' VẪN CÒN sau {timeout}s chờ biến mất" + (f" (đã thử {retries_total} lần)" if retries_total > 1 else ""))
                                # on_fail="skip_to_label": giống wait_image -
                                # nhảy thẳng tới 1 nhãn cùng cấp nếu hết
                                # timeout mà ảnh vẫn chưa biến mất.
                                if on_fail == "skip_to_label":
                                    label_name = s.get("skip_to_label_name")
                                    target_label = self.find_label_index(steps, label_name) if label_name else None
                                    if target_label is not None:
                                        self._log("warn", f"⏭ Ảnh chưa biến mất -> nhảy tới nhãn '{label_name}'")
                                        jump_target = target_label
                                    else:
                                        self._log("error", f"on_fail=skip_to_label nhưng không tìm thấy nhãn '{label_name}' - tiếp tục bước kế tiếp như bình thường")
                        else:
                            self._log("error", f"Không tìm thấy file ảnh mẫu '{tpl_name}' trong thư mục templates" if tpl_name
                                       else "Bước Chờ Ảnh Biến Mất chưa chọn ảnh - hãy bấm đúp/chuột phải vào bước này để chọn")
                        if jump_target is not None:
                            break

                    elif act == "sleep":
                        # Chờ thuần tuý N giây (trường 'delay' của bước, xử
                        # lý chung ở CUỐI vòng lặp repeat bên dưới cho MỌI
                        # loại action) - bản thân bước này không cần làm gì
                        # thêm. TRƯỚC ĐÂY không có nhánh riêng nên action lạ
                        # nào cũng "vô tình" rơi qua và chỉ chờ delay giống
                        # hệt sleep - nay khai báo tường minh để code rõ
                        # ràng, không bị nhầm là thiếu xử lý/bug.
                        pass

                    elif act == "multi_image":
                        tpl_dict = {}
                        for fname in s.get("templates", []):
                            p = os.path.join("templates", fname)
                            if os.path.exists(p):
                                tpl_dict[fname] = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)

                        start = time.time()
                        timeout = s.get("timeout", 8)
                        conf = s.get("conf", 0.80)
                        region = s.get("region")
                        scan_interval = _get_scan_interval(s)

                        if s.get("click_all") or s.get("count_var"):
                            # Chế độ CLICK TẤT CẢ (hoặc chỉ ĐẾM khi có count_var): tìm và click MỌI vị trí
                            # khớp thấy được trong 1 tấm ảnh chụp màn hình
                            # (vd nhặt hết vật phẩm cùng loại đang hiện trên
                            # màn hình) - khác chế độ mặc định (bên dưới)
                            # chỉ click 1 vị trí "tốt nhất" tìm thấy đầu tiên.
                            found_any = False
                            last_count = 0  # số vị trí khớp thấy được (ghi vào count_var nếu bước có đặt)
                            finder_all = self.adb.find_all_matches_turbo if s.get("turbo") else self.adb.find_all_matches_on_screen
                            while time.time() - start < timeout and not self._should_stop():
                                matches = finder_all(tpl_dict, threshold=conf, region=region,
                                                      mode=s.get("match_mode"), modes=s.get("template_modes"))
                                if s.get("turbo"):
                                    self._warn_turbo_fallback()
                                if matches:
                                    found_any = True
                                    last_count = len(matches)
                                    self._log("success", f"Quét đa ảnh (Click Tất Cả): thấy {len(matches)} vị trí khớp")
                                    click_delay = max(0.0, float(s.get("click_all_delay_ms", 150)) / 1000.0)
                                    if s.get("click", True):
                                        # Không bật click_all (chỉ có count_var): vẫn chỉ
                                        # click 1 vị trí tốt nhất như chế độ mặc định.
                                        click_list = matches if s.get("click_all") else matches[:1]
                                        for hit_name, hit_pos, score in click_list:
                                            if self._should_stop():
                                                break
                                            off_x, off_y = (s.get("click_offset") or [0, 0])
                                            jx, jy = self._apply_jitter(s)
                                            px = hit_pos[0] * self.adb.screen_w + off_x + jx
                                            py = hit_pos[1] * self.adb.screen_h + off_y + jy
                                            # turbo=True: click qua socket thẳng tới ADB
                                            # server (tap_turbo_px), không đổi hành vi
                                            # tap_px() mặc định khi bước KHÔNG bật Chế Độ
                                            # Siêu Tốc.
                                            if s.get("turbo"):
                                                self.adb.tap_turbo_px(px, py)
                                                self._warn_turbo_fallback()
                                            else:
                                                self.adb.tap_px(px, py)
                                            self._log("info", f"  -> Click '{hit_name}' (khớp {score:.2f}) tại {hit_pos}")
                                            if click_delay:
                                                time.sleep(click_delay)
                                    break
                                time.sleep(scan_interval)
                            # count_var (tuỳ chọn): lưu SỐ vị trí khớp vào biến để
                            # bước sau dùng, vd Sửa Lặp của Nhóm = {so_anh}. Không
                            # thấy gì -> biến = 0. Tắt Click (click=False) nếu chỉ
                            # muốn ĐẾM mà không bấm.
                            count_var = s.get("count_var")
                            if count_var:
                                self.variables[count_var] = last_count
                                self._log("info", f"Đếm ảnh -> biến {count_var} = {last_count}")
                            if not found_any:
                                self._log("warn", f"Quét đa ảnh: KHÔNG thấy ảnh nào trong nhóm sau {timeout}s")
                        else:
                            hit_name, hit_pos, score = self._poll_any_template(tpl_dict, timeout, conf, region, scan_interval,
                                                                               s.get("match_mode"), s.get("template_modes"),
                                                                               turbo=s.get("turbo", False))
                            if hit_pos:
                                if s.get("click", True):
                                    off_x, off_y = (s.get("click_offset") or [0, 0])
                                    jx, jy = self._apply_jitter(s)
                                    px = hit_pos[0] * self.adb.screen_w + off_x + jx
                                    py = hit_pos[1] * self.adb.screen_h + off_y + jy
                                    if s.get("turbo"):
                                        self.adb.tap_turbo_px(px, py)
                                        self._warn_turbo_fallback()
                                    else:
                                        self.adb.tap_px(px, py)
                                    off_txt = f" (lệch {off_x:+d},{off_y:+d}px)" if (off_x or off_y) else ""
                                    jitter_txt = f" (rải {jx:+.0f},{jy:+.0f}px)" if (jx or jy) else ""
                                    self._log("success", f"Quét đa ảnh: thấy '{hit_name}' (khớp {score:.2f}) -> đã click {hit_pos}{off_txt}{jitter_txt}{self._turbo_click_txt(s)}")
                                else:
                                    self._log("success", f"Quét đa ảnh: thấy '{hit_name}' (khớp {score:.2f}) - CHỈ làm điều kiện, không click")
                            else:
                                self._log("warn", f"Quét đa ảnh: KHÔNG thấy ảnh nào trong nhóm sau {timeout}s")

                    elif act == "type_text":
                        # Ghi thao tác bàn phím: gõ một chuỗi ký tự. Hỗ trợ nội
                        # suy biến bằng {ten_bien}, vd text="{ocr_text}" hoặc
                        # "Số dư: {ocr_text} xu" -> lấy giá trị biến thật.
                        text = self._interpolate_vars(s.get("text", ""))
                        if text:
                            self.adb.input_text(text)
                            self._log("info", f"Gõ chữ: \"{text}\"")

                    elif act == "key_combo":
                        # Ghi thao tác bàn phím: 1 phím hoặc tổ hợp phím (vd Ctrl+A)
                        keys = s.get("keys", [])
                        if keys:
                            self.adb.send_key_combo(keys)
                            keys_disp = "+".join(k.replace("KEYCODE_", "") for k in keys)
                            self._log("info", f"Gửi phím: {keys_disp}")

                    elif act == "group":
                        g_file = s.get("group_file", "")
                        g_path = os.path.join("groups", g_file)
                        if os.path.exists(g_path):
                            self._log("info", f"▶ Chạy nhóm ngoài: {g_file}")
                            try:
                                with open(g_path, "r", encoding="utf-8") as f:
                                    sub_steps = json.load(f)
                                # index_offset=None (CỐ Ý): sub_steps nạp từ 1
                                # file .json RIÊNG, không phải 1 lát cắt của
                                # self.steps, nên KHÔNG có dòng thật nào
                                # tương ứng trên cây hiển thị để bôi đen -
                                # giữ nguyên bôi đen ở đúng dòng "Nhóm:
                                # [file]" bên ngoài trong suốt lúc nhóm ngoài
                                # này chạy (muốn xem từng bước thì "Bung
                                # Nhóm" nó ra thành các dòng thật trước).
                                self.execute_steps(sub_steps, is_root=False, index_offset=None)
                            except (BreakGroupSignal, ContinueGroupSignal, GotoLabelSignal):
                                raise
                            except Exception as e:
                                self._log("error", f"Lỗi khi chạy nhóm ngoài '{g_file}': {e}")
                        else:
                            self._log("error", f"Không tìm thấy file nhóm '{g_file}' trong thư mục groups")

                    elif act == "set_var":
                        # Đặt biến = 1 giá trị cố định, vd đặt bộ đếm 'count' = 0
                        var_name = s.get("var", "")
                        if var_name:
                            old_val = self.variables.get(var_name, None)
                            new_val = s.get("value", 0)
                            # MỚI: giá trị dạng chuỗi có {..} (vd '{rand:10-30}')
                            # -> thay biến/biến random rồi ép về số nếu được.
                            # Giá trị số/chuỗi thường giữ NGUYÊN như cũ.
                            if isinstance(new_val, str) and "{" in new_val:
                                new_val = self._interpolate_vars(new_val)
                                try:
                                    _f = float(new_val)
                                    new_val = int(_f) if _f.is_integer() else _f
                                except ValueError:
                                    pass
                            self.variables[var_name] = new_val
                            self._log("info", f"Đặt biến {var_name}: {old_val} -> {new_val}")

                    elif act == "inc_var":
                        # Tăng/giảm 1 biến số, vd mỗi lần tìm thấy ảnh thì +1
                        var_name = s.get("var", "")
                        if var_name:
                            try:
                                old_val = float(self.variables.get(var_name, 0))
                                new_val = old_val + float(s.get("amount", 1))
                                if new_val.is_integer():
                                    new_val = int(new_val)
                                if old_val.is_integer():
                                    old_val = int(old_val)
                                self.variables[var_name] = new_val
                                self._log("info", f"Biến {var_name}: {old_val} -> {new_val}")
                            except (TypeError, ValueError) as e:
                                self._log("error", f"Không thể tăng/giảm biến {var_name}: {e}")

                    elif act == "input_var":
                        # Biến ĐẦU VÀO khai báo trước khi chạy (vd số lượng
                        # mua Shop): mỗi lần CHẠY TAY, Dashboard tự lấy giá
                        # trị của MỌI biến đã khai báo trong "🧩 Quản Lý
                        # Biến" (variables_registry.py) rồi truyền vào bằng
                        # preset_vars TRƯỚC khi execute_steps() bắt đầu (xem
                        # _get_registry_preset_vars()/_exec_entry() trong
                        # dashboard_run.py) - KHÔNG còn hộp thoại hỏi nữa,
                        # biến đã CÓ SẴN trong self.variables (nếu có khai
                        # báo trùng tên) nên bước này chỉ log lại, KHÔNG ghi
                        # đè. Biến nào KHÔNG có trong Quản Lý Biến (hoặc
                        # chạy Xoay Vòng/Hẹn Giờ tự động, "Chạy Thử" ngay
                        # trong LD Macro Studio) thì tự lấy 'default' làm
                        # giá trị, kịch bản vẫn chạy bình thường.
                        var_name = s.get("var", "")
                        if var_name:
                            if var_name in self._preset_var_names:
                                self._log("info", f"🧩 Biến nhập '{var_name}' = {self.variables.get(var_name)} (đã nhập trước khi chạy)")
                            else:
                                # CỐ Ý ép về 'default' dù biến đã lỡ có giá
                                # trị khác từ 1 bước SET_VAR nào đó chạy
                                # TRƯỚC bước này trong CÙNG kịch bản - biến
                                # đó KHÔNG đến từ preset_vars (Dashboard hỏi)
                                # nên không được coi là "đã nhập trước khi
                                # chạy" (xem apply_preset_vars()).
                                self.variables[var_name] = s.get("default", 0)
                                self._log("info", f"🧩 Biến nhập '{var_name}' = {self.variables[var_name]} (chưa được hỏi -> dùng mặc định)")
                        else:
                            self._log("error", "Bước 'Biến Nhập Trước Khi Chạy' chưa đặt tên biến (var) -> bỏ qua")

                    elif act == "ocr_text":
                        # Quét chữ trong 1 vùng (box theo tỉ lệ 0..1) trên màn hình
                        # HIỆN TẠI, lưu kết quả vào 1 biến để dùng với IF (Biến).
                        box_norm = s.get("box")
                        var_name = s.get("var", "ocr_text")
                        if box_norm:
                            screen = self.adb.screencap_fast()
                            if screen is not None:
                                h, w = screen.shape[:2]
                                x1 = max(0, int(box_norm[0] * w))
                                y1 = max(0, int(box_norm[1] * h))
                                x2 = min(w, int(box_norm[2] * w))
                                y2 = min(h, int(box_norm[3] * h))
                                self._log("info", f"OCR: cắt vùng ({x1},{y1})-({x2},{y2}) = {x2-x1}x{y2-y1}px trên ảnh {w}x{h}px "
                                                  f"(nhận: {_OCR_CHARSET_VN.get(s.get('charset', 'all'), 'cả chữ và số')}"
                                                  + (f" + '{s.get('extra_chars')}'" if s.get("extra_chars") else "") + ")")
                                try:
                                    text = self.adb.ocr_text_in_box(screen, (x1, y1, x2, y2), lang=s.get("lang", "vie+eng"), charset=s.get("charset", "all"),
                                                                    extra_chars=s.get("extra_chars", ""))
                                    if s.get("normalize"):
                                        # "normalize": true -> chữ thường, BỎ DẤU (OCR hay đọc sai dấu)
                                        text = self._normalize_ocr_text(text)
                                    self.variables[var_name] = text
                                    if text:
                                        self._log("success", f"OCR -> biến {var_name} = \"{text}\"")
                                    else:
                                        # QUAN TRỌNG: rỗng KHÔNG PHẢI luôn là lỗi code - Tesseract
                                        # có thể đã chạy đúng nhưng không đọc ra chữ nào trong vùng
                                        # đã chọn (chữ nhỏ/mờ/sai vùng...). Ghi rõ để người dùng biết
                                        # cách tự kiểm tra thay vì tưởng là bug im lặng.
                                        self._log("warn", f"OCR không đọc được chữ nào (biến {var_name} = \"\") - "
                                                           f"mở logs/last_ocr_crop.png (vùng vừa cắt) và "
                                                           f"logs/last_ocr_crop_bin.png (ảnh đã xử lý) để kiểm tra")
                                except Exception as e:
                                    text = f"[Lỗi OCR: {e}]"
                                    self.variables[var_name] = text
                                    self._log("error", f"Lỗi khi quét OCR vào biến {var_name}: {e}")
                            else:
                                self._log("error", "Không chụp được màn hình để quét OCR")
                        else:
                            self._log("error", "Bước Quét OCR chưa có vùng (box) - hãy chọn lại vùng quét")

                    elif act == "show_popup":
                        # Hiện thông báo NGAY TRÊN cửa sổ game (overlay đè lên
                        # khung hình LDPlayer), KHÔNG phải hộp thoại ngoài desktop
                        # như trước. Hỗ trợ nội suy biến {ten_bien} trong nội dung.
                        # duration>0: tự tắt sau N giây, KHÔNG chặn kịch bản chạy
                        # tiếp (giống toast). duration=0: hiện tới khi người dùng
                        # bấm Đóng, và kịch bản DỪNG chờ tại đây (dùng như checkpoint).
                        message = self._interpolate_vars(s.get("message", ""))
                        duration = float(s.get("duration", 0) or 0)
                        bg = s.get("bg") or None
                        fg = s.get("fg") or None
                        alpha = s.get("alpha")
                        pos_box = s.get("pos_box")
                        self._log("info", f"Popup: \"{message}\"")
                        if self.popup_notifier:
                            self.popup_notifier(message, duration, bg, fg, alpha, pos_box)

                    elif act == "next_data_item":
                        # Lấy PHẦN TỬ TIẾP THEO trong 1 "Nhóm Dữ Liệu" (xem
                        # data_groups.py) và gán vào 1 biến - dùng để LẶP qua
                        # 1 danh sách text tuỳ ý (vd id tài khoản 1..10) mỗi
                        # khi đặt bước này ở ĐẦU 1 khối GROUP lặp N lần, giống
                        # hệt cơ chế xoay tài khoản nhưng dùng được cho MỌI
                        # danh sách, không chỉ riêng login/logout.
                        group_id = s.get("group_id", "")
                        var_name = s.get("var", "")
                        wrap = bool(s.get("wrap", True))
                        cursor_key = f"__cursor_{group_id}"
                        if not group_id or not var_name:
                            self._log("error", "Bước Lấy Dữ Liệu (Nhóm) chưa chọn Nhóm Dữ Liệu hoặc chưa đặt tên biến")
                        else:
                            entries = data_groups.load_groups()
                            group = data_groups.get_group(entries, group_id)
                            items = (group or {}).get("items", [])
                            if not items:
                                self._log("error", f"Nhóm Dữ Liệu '{(group or {}).get('ten', group_id)}' rỗng hoặc không tồn tại")
                            else:
                                cursor = int(self.variables.get(cursor_key, 0))
                                if cursor >= len(items):
                                    if wrap:
                                        cursor = 0
                                    else:
                                        cursor = len(items) - 1
                                value = items[cursor]
                                self.variables[var_name] = value
                                group_name = group.get("ten", group_id)
                                self._log("info", f"Nhóm Dữ Liệu '{group_name}': lấy phần tử {cursor + 1}/{len(items)} -> biến {var_name} = \"{value}\"")
                                self.variables[cursor_key] = cursor + 1

                    elif act == "continue_group":
                        # Bỏ qua các bước còn lại trong lượt lặp NHÓM hiện tại,
                        # nhảy thẳng về đầu để lặp lượt tiếp theo ngay (giống
                        # 'continue' trong lập trình) - khác break_group là dừng
                        # HẲN vòng lặp.
                        self._log("info", "🔁 Continue: bỏ qua phần còn lại của lượt lặp Nhóm")
                        raise ContinueGroupSignal()

                    elif act == "break_group":
                        # Dừng ngay vòng lặp của khối GROUP đang chứa bước này
                        # (thường dùng sau 1 IF (Biến), vd: đủ 5 lần thì dừng)
                        raise BreakGroupSignal()

                except (BreakGroupSignal, ContinueGroupSignal, GotoLabelSignal):
                    raise
                except Exception as e:
                    # Ghi lỗi vào Nhật Ký Chạy kèm đúng loại hành động đang
                    # thực thi (vd lỗi ADB mất kết nối, lỗi đọc file ảnh...),
                    # rồi NỔI LỖI LÊN như cũ để không đổi hành vi dừng-khi-lỗi
                    # hiện tại - chỉ thêm khả năng NHÌN THẤY lỗi gì đã xảy ra.
                    self._log("error", f"Lỗi khi thực hiện '{act}': {e}")
                    raise

                delay = self._get_step_delay(s)
                steps_cnt = int(delay / 0.1)
                for _ in range(steps_cnt):
                    if self._should_stop():
                        break
                    time.sleep(0.1)

            if jump_target is not None:
                # on_fail="skip_to_label" đã kích hoạt (xem nhánh wait_image
                # ở trên) - nhảy THẲNG tới nhãn thay vì đi tiếp bước kế tiếp.
                ip = jump_target
                continue
            ip += 1
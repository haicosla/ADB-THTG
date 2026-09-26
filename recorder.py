import time
from pynput import mouse, keyboard


_MOD_KEYCODES = {
    "ctrl": "KEYCODE_CTRL_LEFT",
    "alt": "KEYCODE_ALT_LEFT",
    "shift": "KEYCODE_SHIFT_LEFT",
}

# Ngưỡng khoảng cách (tỉ lệ 0..1 so với khung giả lập) để lấy thêm 1 điểm
# MỚI trên đường vuốt khi đang ghi (xem _start_mouse::on_move). Đây chỉ là
# bộ lọc THÔ ở bước LẤY MẪU (giảm số điểm rác do chuột báo cáo quá dày đặc)
# - việc CHỌN điểm nào thực sự cần giữ lại nằm ở _simplify_swipe_points()
# (thuật toán Douglas-Peucker) bên dưới, KHÔNG phải ở ngưỡng này.
_PATH_SAMPLE_MIN_DIST = 0.006

# Khoảng dừng KHÔNG DI CHUYỂN tối thiểu (giây) TRƯỚC KHI THẢ tay để tính là
# người dùng CỐ Ý giữ yên (giống thao tác "kéo rồi giữ" trước khi buông) -
# nếu ngắn hơn mốc này thì chỉ là độ trễ tự nhiên giữa sự kiện di chuyển
# cuối cùng và sự kiện nhả chuột (không phải chủ ý), nên gộp vào thời gian
# di chuyển thay vì tách thành "hold_ms".
_HOLD_MIN_SEC = 0.12

# Sai số cho phép (tỉ lệ 0..1) khi RÚT GỌN đường vuốt bằng thuật toán
# Ramer-Douglas-Peucker (xem _rdp_simplify) - 1 điểm giữa chỉ được GIỮ LẠI
# nếu nó lệch khỏi đoạn thẳng (đang xét) quá ngưỡng này; nếu không sẽ bị bỏ
# vì coi như "nằm trên đường thẳng" (kể cả rung tay nhẹ khi vuốt thật).
_RDP_EPSILON = 0.02

# CHẶN CỨNG số điểm tối đa giữ lại cho 1 bước "swipe_path". LÝ DO: mỗi
# điểm trung gian trong swipe_path lúc PHÁT LẠI tốn HẲN 1 loạt lệnh
# `adb shell input touchscreen motionevent MOVE` RIÊNG (xem
# adb_helper.py::swipe_path_px) - vuốt tay thật ~1 giây luôn rung nhẹ nên
# có thể lấy mẫu thô được HÀNG CHỤC/HÀNG TRĂM điểm; nếu ghi lại y nguyên
# từng đó điểm thì lúc chạy phải gọi hàng trăm lệnh adb nối tiếp -> app
# "treo" rất lâu, và khoảng cách THỜI GIAN THỰC giữa các lệnh adb (do độ
# trễ subprocess/adb) kéo dài ra so với cử chỉ gốc khiến Android không còn
# nhận ra đây là 1 cử chỉ vuốt liên tục (kéo/thả không ăn) - ĐÂY CHÍNH LÀ
# lỗi "kéo 1s ghi 100 điểm, chạy bị treo, cũng không kéo được" người dùng
# gặp phải. Rút gọn xuống còn tối đa chừng này điểm là đủ để giữ ĐÚNG hình
# dạng đường vuốt (kể cả vẽ hình pattern phức tạp) mà vẫn chạy mượt.
_SWIPE_PATH_MAX_POINTS = 8

# Android KHÔNG có KEYCODE_BACKSPACE/KEYCODE_DELETE/KEYCODE_ESC/KEYCODE_UP...
# như PC - nếu gửi sai tên, `adb shell input keyevent` báo lỗi ra stderr rồi
# KHÔNG làm gì cả (key_event() không kiểm tra returncode nên lỗi bị im lặng
# nuốt mất, trông giống như "không gửi được"). Bảng dưới đây ánh xạ tên phím
# quen thuộc trên PC (gõ tay hoặc lấy từ pynput khi ghi trực tiếp F7) sang
# ĐÚNG tên KEYCODE Android tương ứng.
_KEYNAME_ALIASES = {
    "backspace": "KEYCODE_DEL",        # Backspace trên PC = KEYCODE_DEL của Android
    "delete": "KEYCODE_FORWARD_DEL",   # Delete trên PC = KEYCODE_FORWARD_DEL
    "del": "KEYCODE_DEL",
    "esc": "KEYCODE_ESCAPE",
    "escape": "KEYCODE_ESCAPE",
    "up": "KEYCODE_DPAD_UP",
    "down": "KEYCODE_DPAD_DOWN",
    "left": "KEYCODE_DPAD_LEFT",
    "right": "KEYCODE_DPAD_RIGHT",
    "enter": "KEYCODE_ENTER",
    "return": "KEYCODE_ENTER",
    "tab": "KEYCODE_TAB",
    "space": "KEYCODE_SPACE",
    "home": "KEYCODE_HOME",
    "caps_lock": "KEYCODE_CAPS_LOCK",
}


def _resolve_keyname(name):
    """name: tên phím chữ thường (vd 'backspace', 'a', '1', 'del').
    Trả về đúng KEYCODE Android, ưu tiên tra bảng alias trước."""
    name = name.strip().lower()
    if name in _KEYNAME_ALIASES:
        return _KEYNAME_ALIASES[name]
    if len(name) == 1 and name.isalpha():
        return f"KEYCODE_{name.upper()}"
    if name.isdigit():
        return f"KEYCODE_{name}"
    return f"KEYCODE_{name.upper()}"


def parse_key_combo_text(text):
    """Chuyển chuỗi người dùng gõ tay (vd 'ctrl+a', 'enter', 'shift+tab')
    thành danh sách KEYCODE Android, dùng cho bước 'key_combo'."""
    parts = [p.strip().lower() for p in text.replace(" ", "").split("+") if p.strip()]
    keys = []
    for p in parts:
        if p in _MOD_KEYCODES:
            keys.append(_MOD_KEYCODES[p])
        else:
            keys.append(_resolve_keyname(p))
    return keys


def _char_to_keycode(ch):
    if not ch:
        return None
    if ch.isalpha():
        return f"KEYCODE_{ch.upper()}"
    if ch.isdigit():
        return f"KEYCODE_{ch}"
    return None


class LiveRecorder:
    """Ghi lại thao tác chuột (tap/swipe) VÀ bàn phím (gõ chữ, tổ hợp phím
    như Ctrl+A) khi người dùng thao tác trực tiếp trên cửa sổ LDPlayer (F7).

    Các ký tự gõ liên tiếp (không có phím bổ trợ Ctrl/Alt/Shift) được gộp lại
    thành 1 bước "type_text" duy nhất; khi có phím bổ trợ hoặc phím đặc biệt
    (Enter, Tab, Backspace...) sẽ tạo thành bước "key_combo" riêng.
    """

    def __init__(self, coord_mapper, on_step_captured, focus_checker=None):
        """
        coord_mapper: hàm (sx, sy) -> (norm_x, norm_y) hoặc (None, None)
        on_step_captured: callback(step_dict) - LƯU Ý: được gọi từ thread nền
            của pynput, nơi gọi cần tự điều phối về main thread (vd root.after)
        focus_checker: hàm không tham số, trả về True nếu cửa sổ LDPlayer
            đang được focus. pynput lắng nghe bàn phím Ở TOÀN HỆ THỐNG (không
            như chuột vốn tự lọc được nhờ tọa độ nằm trong/ngoài khung giả
            lập), nên nếu không lọc theo focus thì mọi phím gõ ở BẤT KỲ cửa
            sổ nào (kể cả chính app này) cũng bị ghi nhận nhầm vào kịch bản -
            khiến việc ghi bàn phím trông như "không hoạt động"/không đáng
            tin cậy. Nếu để None (không truyền), sẽ ghi nhận mọi phím như cũ.
        """
        self.coord_mapper = coord_mapper
        self.on_step_captured = on_step_captured
        self.focus_checker = focus_checker

        self.mouse_listener = None
        self.kb_listener = None

        self.press_norm_pos = None
        self.press_time = 0
        self.last_action_time = 0
        # Tham chiếu tới step VỪA ghi được trước đó - xem _commit_delay() để
        # hiểu tại sao cần giữ lại tham chiếu này (fix lỗi delay bị "lùi"
        # sang sai bước, xem giải thích chi tiết ở _commit_delay).
        self._last_step_ref = None

        self._pressed_modifiers = set()
        self._typed_buffer = ""
        self._last_type_time = 0

        # Đường đi THẬT của con trỏ trong lúc đang giữ chuột (mỗi phần tử
        # là (norm_x, norm_y, thời_điểm)) - xem _start_mouse::on_move. Dùng
        # để ghi lại ĐÚNG hình dạng đường vuốt (kể cả cong/gấp khúc) và tách
        # đúng "thời gian di chuyển" khỏi "thời gian giữ yên trước khi thả",
        # thay vì chỉ đoán mò 2 điểm đầu/cuối + duration mặc định như cũ.
        self._drag_path = []

    def start(self):
        self.last_action_time = time.time()
        self._last_step_ref = None
        self._typed_buffer = ""
        self._pressed_modifiers = set()
        self._drag_path = []
        self._start_mouse()
        self._start_keyboard()

    # ---------------- FIX: gán ĐÚNG "delay" vào ĐÚNG bước ----------------
    def _commit_delay(self, new_step, action_start_time):
        """LỖI CŨ: mỗi khi ghi được 1 bước mới, code tính khoảng NGƯỜI DÙNG
        DỪNG LẠI trước khi làm hành động đó (vd: click A xong DỪNG 5 giây rồi
        mới click B), rồi lại gán khoảng dừng 5 giây đó vào field "delay" của
        CHÍNH bước B (bước vừa được tạo ra ứng với hành động SAU khoảng
        dừng) - trong khi logic_engine.py áp dụng "delay" của 1 bước là chờ
        THÊM sau khi bước đó đã CHẠY XONG (xem cuối vòng lặp run_steps()),
        KHÔNG PHẢI chờ trước khi bước đó bắt đầu.

        Hậu quả: kịch bản ghi được sẽ phát lại thành "click A (gần như ngay
        lập tức) -> click B -> (rồi mới) chờ 5 giây" - tức khoảng dừng bị
        "lùi" ra sau bước B thay vì nằm ĐÚNG giữa A và B như lúc ghi thật.

        FIX: khoảng dừng đo được trước khi bắt đầu hành động MỚI phải được
        gán vào field "delay" của BƯỚC TRƯỚC ĐÓ (self._last_step_ref) - vì
        đó chính là bước sẽ chạy NGAY TRƯỚC khoảng dừng này lúc phát lại.
        Bước MỚI vừa tạo thì tạm để "delay" mặc định (0.8s) - giá trị này sẽ
        được ghi đè lại đúng khi có hành động KẾ TIẾP xảy ra (hàm này được
        gọi lại lần nữa) hoặc giữ nguyên mặc định nếu đây là bước CUỐI CÙNG
        của cả kịch bản (không ảnh hưởng vì không còn bước nào cần chờ sau
        nó nữa).
        """
        gap = round(action_start_time - self.last_action_time, 2) if self.last_action_time else 0.8
        gap = max(0.2, gap)
        if self._last_step_ref is not None:
            self._last_step_ref["delay"] = gap
        new_step.setdefault("delay", 0.8)
        self._last_step_ref = new_step
        return new_step

    def stop(self):
        self._flush_typed_buffer()
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        if self.kb_listener:
            self.kb_listener.stop()
            self.kb_listener = None

    # ---------------- CHUỘT ----------------
    def _start_mouse(self):
        def on_move(x, y):
            # Chỉ lấy mẫu điểm khi ĐANG giữ chuột (đang vuốt dở) - bỏ qua
            # di chuyển chuột lúc không nhấn (hover/rê chuột xem trước),
            # tránh self._drag_path bị đầy vô nghĩa.
            if not self.press_norm_pos:
                return
            norm_pos = self.coord_mapper(x, y)
            if norm_pos[0] is None:
                return
            lx, ly, _lt = self._drag_path[-1]
            # Chỉ thêm điểm MỚI khi di chuyển đủ xa điểm đã lấy mẫu gần
            # nhất (_PATH_SAMPLE_MIN_DIST) - vừa để không phình to danh
            # sách điểm vì rung tay/nhiễu chuột, vừa giữ đúng mốc THỜI GIAN
            # của lần di chuyển CUỐI CÙNG (dùng để tách hold_ms bên dưới).
            if abs(norm_pos[0] - lx) >= _PATH_SAMPLE_MIN_DIST or abs(norm_pos[1] - ly) >= _PATH_SAMPLE_MIN_DIST:
                self._drag_path.append((norm_pos[0], norm_pos[1], time.time()))

        def on_click(x, y, button, pressed):
            if button != mouse.Button.left:
                return
            norm_pos = self.coord_mapper(x, y)
            if norm_pos[0] is None:
                return

            now = time.time()
            if pressed:
                # Xả (flush) sẵn phần chữ đang gõ dở TRƯỚC khi ghi bước
                # chuột mới, để bước "type_text" xuất hiện đúng thứ tự thời
                # gian (trước đây chỉ được xả khi gặp phím đặc biệt/tổ hợp
                # phím hoặc khi dừng ghi, nên nếu gõ chữ rồi bấm/chạm chuột
                # ngay thì bước gõ chữ bị trôi ra sau, trông như "mất").
                self._flush_typed_buffer()
                self.press_norm_pos = norm_pos
                self.press_time = now
                # Điểm NHẤN xuống luôn là điểm đầu tiên của đường đi vuốt.
                self._drag_path = [(norm_pos[0], norm_pos[1], now)]
            else:
                if not self.press_norm_pos:
                    return
                # Gán delay bằng ĐÚNG khoảnh khắc bắt đầu hành động (lúc NHẤN
                # chuột xuống = self.press_time), không phải lúc nhả ra (now)
                # - xem _commit_delay() để hiểu vì sao khoảng dừng phải nằm
                # ở bước TRƯỚC, không phải bước này. QUAN TRỌNG: phải LẤY
                # start_time RA TRƯỚC khi cập nhật self.last_action_time =
                # now, nếu không _commit_delay() sẽ tính gap với chính giá
                # trị vừa ghi đè (luôn ra ~0) thay vì gap với bước TRƯỚC ĐÓ.
                start_time = self.press_time

                p1 = self.press_norm_pos
                p2 = norm_pos
                self.press_norm_pos = None
                path = self._drag_path
                self._drag_path = []

                if abs(p2[0] - p1[0]) < 0.02 and abs(p2[1] - p1[1]) < 0.02:
                    # TAP - nếu người dùng GIỮ NGUYÊN (không rê đi) đủ lâu
                    # trước khi nhả ra thì đây là "giữ tay" (long-press),
                    # ghi lại bằng field hold_ms mà logic_engine.py/
                    # adb_helper.py::tap_hold_px() đã hỗ trợ sẵn - trước đây
                    # recorder luôn coi mọi cú tap như chạm-nhả tức thời, dù
                    # người dùng có giữ lâu cỡ nào.
                    hold_time = now - start_time
                    step = {
                        "action": "tap",
                        "pos": [p1[0], p1[1]],
                        "repeat": 1,
                        "comment": f"Tap [{int(p1[0]*100)}%, {int(p1[1]*100)}%]"
                    }
                    if hold_time >= _HOLD_MIN_SEC:
                        hold_ms = int(round(hold_time * 1000))
                        step["hold_ms"] = hold_ms
                        step["comment"] = f"Giữ Tay [{int(p1[0]*100)}%, {int(p1[1]*100)}%] ({hold_ms}ms)"
                else:
                    step = self._build_swipe_step(p1, p2, path, start_time, now)

                self._commit_delay(step, start_time)
                self.last_action_time = now
                self.on_step_captured(step)

        self.mouse_listener = mouse.Listener(on_click=on_click, on_move=on_move)
        self.mouse_listener.daemon = True
        self.mouse_listener.start()

    def _build_swipe_step(self, p1, p2, path, start_time, release_time):
        """Dựng bước 'swipe' (2 điểm) hoặc 'swipe_path' (nhiều điểm) từ
        ĐƯỜNG ĐI THẬT đã lấy mẫu được (path, xem on_move ở trên) khi người
        dùng vuốt trên cửa sổ giả lập.

        LỖI CŨ: chỉ lưu 2 điểm đầu/cuối (bỏ qua toàn bộ đường đi ở giữa dù
        có cong/gấp khúc) và ép cứng "duration" tối thiểu 200ms bất kể vuốt
        thật nhanh cỡ nào (int(max(200, hold_time*1000))), lại tính bằng
        TOÀN BỘ thời gian từ lúc nhấn tới lúc nhả (bao gồm cả lúc dừng lại
        giữ yên trước khi thả, nếu có) - khiến bản ghi phát lại khác hẳn
        thao tác thật cả về hình dạng đường vuốt lẫn tốc độ.

        NAY: dùng chính "path" để:
        1) Tính ĐÚNG "duration" = thời gian THỰC từ lúc bắt đầu di chuyển
           tới lúc NGƯNG di chuyển (không ép tối thiểu 200ms nữa - vuốt
           nhanh 50ms thì ghi lại đúng 50ms).
        2) Tách riêng khoảng GIỮ YÊN trước khi thả tay (nếu có) thành
           "hold_ms" - giống đúng 3 giai đoạn DOWN/MOVE/GIỮ YÊN/UP mà
           swipe_hold_px()/swipe_path_px() mô phỏng - thay vì gộp lẫn vào
           "duration" khiến lúc phát lại đường vuốt bị "trôi" chậm hơn hẳn
           thao tác thật.
        3) Nếu đường đi có từ 3 điểm phân biệt trở lên (vuốt cong/gấp khúc,
           không phải 1 đường thẳng) thì ghi thành "swipe_path" (đã hỗ trợ
           sẵn ở logic_engine.py/adb_helper.py::swipe_path_px) để GIỮ ĐÚNG
           hình dạng đường vuốt thật, thay vì "làm thẳng" thành 2 điểm.
        """
        # path luôn có ít nhất điểm NHẤN xuống (p1); nếu on_move không kịp
        # bắt sự kiện nào khác (vuốt cực nhanh) thì path chỉ có đúng 1 điểm
        # đó - khi ấy KHÔNG có mốc thời gian nào để tách "giữ yên", nên coi
        # TOÀN BỘ khoảng đó là thời gian di chuyển (an toàn hơn ép mặc định
        # 200ms như code cũ).
        if len(path) >= 2:
            last_move_time = path[-1][2]
        else:
            last_move_time = start_time

        movement_time = max(0.0, last_move_time - start_time)
        hold_time = max(0.0, release_time - last_move_time)

        if hold_time < _HOLD_MIN_SEC:
            # Khoảng dừng quá ngắn (vài chục ms) nhiều khả năng chỉ là độ
            # trễ tự nhiên giữa sự kiện di chuyển cuối và sự kiện nhả
            # chuột, KHÔNG phải người dùng cố tình giữ yên - gộp lại vào
            # duration cho khớp đúng TỔNG thời gian thật của cả thao tác.
            movement_time = max(0.0, release_time - start_time)
            hold_time = 0.0

        duration_ms = max(1, int(round(movement_time * 1000)))
        hold_ms = int(round(hold_time * 1000))

        # Điểm cuối LUÔN lấy đúng vị trí THẢ chuột thật (p2) - path lấy mẫu
        # qua on_move có thể dừng lấy mẫu sớm hơn 1 chút (do ngưỡng khoảng
        # cách _PATH_SAMPLE_MIN_DIST) nên không dùng điểm cuối của path.
        mid_points = [(x, y) for (x, y, _t) in path[1:]]
        all_points = [p1] + mid_points + [p2]

        # Gộp các điểm liền kề quá gần nhau (vd điểm cuối path trùng gần
        # đúng p2) để không tạo swipe_path thừa điểm vô nghĩa.
        dedup_points = [all_points[0]]
        for pt in all_points[1:]:
            lx, ly = dedup_points[-1]
            if abs(pt[0] - lx) >= _PATH_SAMPLE_MIN_DIST / 2 or abs(pt[1] - ly) >= _PATH_SAMPLE_MIN_DIST / 2:
                dedup_points.append(pt)

        # Rút gọn đường đi thô (có thể tới hàng chục/hàng trăm điểm nếu
        # vuốt chậm/rung tay) xuống chỉ còn những điểm THẬT SỰ cần thiết để
        # mô tả đúng hình dạng (xem _simplify_swipe_points/_rdp_simplify) -
        # đây là phần fix chính cho lỗi "vuốt 1s ghi 100 điểm, chạy bị
        # treo": KHÔNG dùng nguyên toàn bộ dedup_points làm swipe_path nữa.
        final_points = self._simplify_swipe_points(dedup_points)

        if len(final_points) > 2:
            step = {
                "action": "swipe_path",
                "points": [[x, y] for x, y in final_points],
                "duration": duration_ms,
                "repeat": 1,
                "comment": f"Vuốt {len(final_points)} điểm [{int(p1[0]*100)}%,{int(p1[1]*100)}%]→[{int(p2[0]*100)}%,{int(p2[1]*100)}%]"
            }
        else:
            step = {
                "action": "swipe",
                "from": [p1[0], p1[1]],
                "to": [p2[0], p2[1]],
                "duration": duration_ms,
                "repeat": 1,
                "comment": f"Swipe [{int(p1[0]*100)}%]->[{int(p2[0]*100)}%]"
            }

        if hold_ms > 0:
            step["hold_ms"] = hold_ms
            step["comment"] += f" (giữ {hold_ms}ms trước khi thả)"

        return step

    @classmethod
    def _simplify_swipe_points(cls, points):
        """Rút gọn 'points' (đã gồm cả điểm đầu p1 và điểm cuối p2) bằng
        thuật toán Ramer-Douglas-Peucker, CHỈ giữ lại những điểm thật sự
        cần thiết để mô tả đúng hình dạng đường vuốt (chỗ bẻ góc/đổi hướng
        rõ rệt), đồng thời CHẶN CỨNG số điểm tối đa
        (_SWIPE_PATH_MAX_POINTS - xem giải thích ở khai báo hằng số này) -
        nếu rút gọn theo epsilon mặc định vẫn còn quá nhiều điểm (đường đi
        cực kỳ ngoằn ngoèo) thì tăng dần epsilon cho tới khi đạt, cuối cùng
        nếu vẫn chưa đủ thì lấy đều theo chỉ số (luôn giữ điểm đầu/cuối)."""
        epsilon = _RDP_EPSILON
        simplified = cls._rdp_simplify(points, epsilon)
        tries = 0
        while len(simplified) > _SWIPE_PATH_MAX_POINTS and tries < 6:
            epsilon *= 1.8
            simplified = cls._rdp_simplify(points, epsilon)
            tries += 1
        if len(simplified) > _SWIPE_PATH_MAX_POINTS:
            n = _SWIPE_PATH_MAX_POINTS
            step_f = (len(simplified) - 1) / (n - 1)
            idxs = sorted({int(round(i * step_f)) for i in range(n)})
            simplified = [simplified[i] for i in idxs]
        return simplified

    @staticmethod
    def _rdp_simplify(points, epsilon):
        """Thuật toán Ramer-Douglas-Peucker: với 1 dãy điểm, chỉ giữ lại
        điểm ĐẦU, điểm CUỐI, và những điểm ở giữa lệch khỏi đoạn thẳng
        (đang xét đệ quy) quá 'epsilon' - những điểm nằm gần như trên
        đường thẳng nối 2 điểm lân cận đã giữ sẽ bị loại bỏ. Dùng để nén
        hàng chục/hàng trăm điểm lấy mẫu thô (do chuột báo cáo liên tục,
        kể cả trên đường gần như thẳng vì rung tay) xuống còn đúng những
        điểm mô tả hình dạng thật của đường vuốt."""
        if len(points) < 3:
            return list(points)
        x1, y1 = points[0]
        x2, y2 = points[-1]
        dx, dy = x2 - x1, y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        max_dist = -1.0
        max_idx = 0
        for i in range(1, len(points) - 1):
            px, py = points[i]
            if length <= 1e-9:
                dist = ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
            else:
                dist = abs(dx * (y1 - py) - (x1 - px) * dy) / length
            if dist > max_dist:
                max_dist = dist
                max_idx = i
        if max_dist > epsilon:
            left = LiveRecorder._rdp_simplify(points[:max_idx + 1], epsilon)
            right = LiveRecorder._rdp_simplify(points[max_idx:], epsilon)
            return left[:-1] + right
        return [points[0], points[-1]]

    # ---------------- BÀN PHÍM ----------------
    def _start_keyboard(self):
        def on_press(key):
            # Chỉ ghi phím khi cửa sổ LDPlayer đang thực sự được focus,
            # tránh ghi nhầm phím gõ ở cửa sổ khác vào kịch bản.
            if self.focus_checker and not self.focus_checker():
                return

            now = time.time()

            if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._pressed_modifiers.add("KEYCODE_CTRL_LEFT")
                return
            if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
                self._pressed_modifiers.add("KEYCODE_ALT_LEFT")
                return
            if key in (keyboard.Key.shift, keyboard.Key.shift_r):
                self._pressed_modifiers.add("KEYCODE_SHIFT_LEFT")
                return

            if self._pressed_modifiers:
                # Có phím bổ trợ đang giữ -> đây là tổ hợp phím, vd Ctrl+A
                char = getattr(key, "char", None)
                keycode = _char_to_keycode(char) if char else None
                if keycode is None and hasattr(key, "name"):
                    keycode = _resolve_keyname(key.name)
                if keycode:
                    self._flush_typed_buffer()
                    combo = sorted(self._pressed_modifiers) + [keycode]
                    step = {
                        "action": "key_combo",
                        "keys": combo,
                        "repeat": 1,
                        "comment": "Tổ hợp phím: " + " + ".join(k.replace("KEYCODE_", "") for k in combo)
                    }
                    self._commit_delay(step, now)
                    self.last_action_time = now
                    self.on_step_captured(step)
                return

            # Gõ chữ bình thường (không có phím bổ trợ)
            char = getattr(key, "char", None)
            if char:
                self._typed_buffer += char
                self._last_type_time = now
            else:
                # Phím đặc biệt: Enter, Tab, Backspace, mũi tên...
                self._flush_typed_buffer()
                name = getattr(key, "name", None)
                if name:
                    keycode = _resolve_keyname(name)
                    step = {
                        "action": "key_combo",
                        "keys": [keycode],
                        "repeat": 1,
                        "comment": f"Phím: {name}"
                    }
                    self._commit_delay(step, now)
                    self.last_action_time = now
                    self.on_step_captured(step)

        def on_release(key):
            if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self._pressed_modifiers.discard("KEYCODE_CTRL_LEFT")
            elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
                self._pressed_modifiers.discard("KEYCODE_ALT_LEFT")
            elif key in (keyboard.Key.shift, keyboard.Key.shift_r):
                self._pressed_modifiers.discard("KEYCODE_SHIFT_LEFT")

        self.kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.kb_listener.daemon = True
        self.kb_listener.start()

    def _flush_typed_buffer(self):
        if self._typed_buffer:
            text = self._typed_buffer
            self._typed_buffer = ""
            step = {
                "action": "type_text",
                "text": text,
                "repeat": 1,
                "comment": f"Gõ: {text}"
            }
            self._commit_delay(step, self._last_type_time)
            self.last_action_time = self._last_type_time
            self.on_step_captured(step)

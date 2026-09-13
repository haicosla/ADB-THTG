import time
from pynput import mouse, keyboard


_MOD_KEYCODES = {
    "ctrl": "KEYCODE_CTRL_LEFT",
    "alt": "KEYCODE_ALT_LEFT",
    "shift": "KEYCODE_SHIFT_LEFT",
}


def parse_key_combo_text(text):
    """Chuyển chuỗi người dùng gõ tay (vd 'ctrl+a', 'enter', 'shift+tab')
    thành danh sách KEYCODE Android, dùng cho bước 'key_combo'."""
    parts = [p.strip().lower() for p in text.replace(" ", "").split("+") if p.strip()]
    keys = []
    for p in parts:
        if p in _MOD_KEYCODES:
            keys.append(_MOD_KEYCODES[p])
        elif len(p) == 1 and p.isalpha():
            keys.append(f"KEYCODE_{p.upper()}")
        elif p.isdigit():
            keys.append(f"KEYCODE_{p}")
        else:
            keys.append(f"KEYCODE_{p.upper()}")
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

        self._pressed_modifiers = set()
        self._typed_buffer = ""
        self._last_type_time = 0

    def start(self):
        self.last_action_time = time.time()
        self._typed_buffer = ""
        self._pressed_modifiers = set()
        self._start_mouse()
        self._start_keyboard()

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
            else:
                if not self.press_norm_pos:
                    return
                hold_time = round(now - self.press_time, 2)
                delay_after = round(self.press_time - self.last_action_time, 2) if self.last_action_time else 0.8
                delay_after = max(0.2, delay_after)
                self.last_action_time = now

                p1 = self.press_norm_pos
                p2 = norm_pos
                self.press_norm_pos = None

                if abs(p2[0] - p1[0]) < 0.02 and abs(p2[1] - p1[1]) < 0.02:
                    step = {
                        "action": "tap",
                        "pos": [p1[0], p1[1]],
                        "repeat": 1,
                        "delay": delay_after,
                        "comment": f"Tap [{int(p1[0]*100)}%, {int(p1[1]*100)}%]"
                    }
                else:
                    duration_ms = int(max(200, hold_time * 1000))
                    step = {
                        "action": "swipe",
                        "from": [p1[0], p1[1]],
                        "to": [p2[0], p2[1]],
                        "duration": duration_ms,
                        "repeat": 1,
                        "delay": delay_after,
                        "comment": f"Swipe [{int(p1[0]*100)}%]->[{int(p2[0]*100)}%]"
                    }
                self.on_step_captured(step)

        self.mouse_listener = mouse.Listener(on_click=on_click)
        self.mouse_listener.daemon = True
        self.mouse_listener.start()

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
                    keycode = f"KEYCODE_{key.name.upper()}"
                if keycode:
                    self._flush_typed_buffer()
                    combo = sorted(self._pressed_modifiers) + [keycode]
                    delay_after = round(now - self.last_action_time, 2) if self.last_action_time else 0.5
                    delay_after = max(0.2, delay_after)
                    self.last_action_time = now
                    step = {
                        "action": "key_combo",
                        "keys": combo,
                        "repeat": 1,
                        "delay": delay_after,
                        "comment": "Tổ hợp phím: " + " + ".join(k.replace("KEYCODE_", "") for k in combo)
                    }
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
                    keycode = f"KEYCODE_{name.upper()}"
                    delay_after = round(now - self.last_action_time, 2) if self.last_action_time else 0.5
                    delay_after = max(0.2, delay_after)
                    self.last_action_time = now
                    step = {
                        "action": "key_combo",
                        "keys": [keycode],
                        "repeat": 1,
                        "delay": delay_after,
                        "comment": f"Phím: {name}"
                    }
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
            delay_after = round(self._last_type_time - self.last_action_time, 2) if self.last_action_time else 0.5
            delay_after = max(0.2, delay_after)
            self.last_action_time = self._last_type_time
            step = {
                "action": "type_text",
                "text": text,
                "repeat": 1,
                "delay": delay_after,
                "comment": f"Gõ: {text}"
            }
            self.on_step_captured(step)

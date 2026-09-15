import os
import time
import json
import re
import cv2
import numpy as np

import data_groups


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


def _get_repeat_ms(step):
    """Đọc thời gian lặp (ms) từ step. Ưu tiên field 'repeat_ms' (chuẩn mới).
    Vẫn đọc được field cũ 'repeat_seconds' (đơn vị giây) để tương thích ngược
    với các file JSON kịch bản đã lưu trước đây."""
    if "repeat_ms" in step:
        return float(step.get("repeat_ms", 0))
    return float(step.get("repeat_seconds", 0)) * 1000.0


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


class LogicEngine:
    def __init__(self, adb_helper, stop_checker=None, step_notifier=None, popup_notifier=None, logger=None):
        self.adb = adb_helper
        self.stop_checker = stop_checker if stop_checker else (lambda: False)
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

    def _log(self, level, message):
        if self.logger:
            try:
                self.logger(level, message)
            except Exception:
                pass

    def _interpolate_vars(self, text):
        """Cho phép nhúng biến vào 1 chuỗi bằng cú pháp {tên_biến}, vd:
        'Điểm: {ocr_text}' -> thay {ocr_text} bằng GIÁ TRỊ biến ocr_text hiện
        tại. Phần chữ còn lại (ngoài dấu {}) LUÔN được coi là văn bản thuần,
        không tự động đoán "cái nào là biến, cái nào là chữ" nữa - trước đây
        Gõ Chữ / Popup không có cách nào phân biệt, nên gõ 'ocr_text' sẽ luôn
        gõ ra đúng 3 chữ đó thay vì lấy giá trị đã quét được."""
        if not text or "{" not in text:
            return text

        def repl(m):
            name = m.group(1)
            if name in self.variables:
                return str(self.variables[name])
            return m.group(0)  # giữ nguyên {ten_bien} nếu biến chưa tồn tại

        return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", repl, text)

    def reset_variables(self):
        """Gọi trước mỗi lần CHẠY THỬ kịch bản để các biến (vd bộ đếm) không
        bị giữ lại giá trị từ lần chạy trước đó."""
        self.variables = {}

    @staticmethod
    def _compare_values(current, op, target):
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

    def find_matching_else_or_endif(self, steps, start_ip):
        """Tìm index của ELSE hoặc ENDIF đồng cấp với IF tại start_ip"""
        depth = 0
        for i in range(start_ip + 1, len(steps)):
            act = steps[i].get("action")
            if act in ("if_image", "if_var"):
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
            if act in ("if_image", "if_var"):
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

    def check_condition(self, step):
        """Kiểm tra điều kiện xuất hiện của ảnh đơn hoặc danh sách ảnh"""
        timeout = step.get("timeout", 2)
        conf = step.get("conf", 0.80)
        region = step.get("region")
        scan_interval = _get_scan_interval(step)
        start = time.time()

        templates = step.get("templates")
        single_tpl = step.get("template")

        if templates:
            tpl_dict = {}
            for fname in templates:
                p = os.path.join("templates", fname)
                if os.path.exists(p):
                    tpl_dict[fname] = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)

            while time.time() - start < timeout and not self.stop_checker():
                _, hit_pos, _ = self.adb.find_any_image_on_screen(tpl_dict, threshold=conf, region=region)
                if hit_pos:
                    return True
                # Bản thân chụp màn hình + so khớp đã tốn thời gian, sleep
                # thêm chỉ cần đủ để không "quay vòng" liên tục ngốn CPU -
                # tốc độ quét (scan_interval) do người dùng tự đặt trong GUI.
                time.sleep(scan_interval)

        elif single_tpl:
            tpl_path = os.path.join("templates", single_tpl)
            if os.path.exists(tpl_path):
                tpl = cv2.imdecode(np.fromfile(tpl_path, dtype=np.uint8), cv2.IMREAD_COLOR)
                while time.time() - start < timeout and not self.stop_checker():
                    coord, _ = self.adb.find_image_on_screen(tpl, threshold=conf, region=region)
                    if coord:
                        return True
                    time.sleep(scan_interval)

        return False

    def execute_steps(self, steps, is_root=True):
        """Duyệt và thực thi danh sách bước với cây logic Jump Table"""
        ip = 0
        while ip < len(steps) and not self.stop_checker():
            s = steps[ip]
            act = s.get("action")
            delay = s.get("delay", 1.0)
            repeat = max(1, int(s.get("repeat", 1)))

            if is_root and self.step_notifier:
                self.step_notifier(ip)

            # 1. Điều kiện IF (theo ẢNH hoặc theo BIẾN)
            if act in ("if_image", "if_var"):
                if act == "if_image":
                    matched = self.check_condition(s)
                    if s.get("templates"):
                        cond_desc = f"IF thấy 1 trong {len(s.get('templates'))} ảnh"
                    else:
                        cond_desc = f"IF thấy ảnh '{s.get('template')}'"
                else:
                    var_name = s.get("var", "")
                    op = s.get("op", "==")
                    target_val = s.get("value", 0)
                    cur_val = self.variables.get(var_name, 0)
                    matched = self._compare_values(cur_val, op, target_val)
                    cond_desc = f"IF biến {var_name} ({cur_val}) {op} {target_val}"
                self._log("success" if matched else "info", f"{cond_desc} -> {'ĐÚNG' if matched else 'SAI'}")
                if matched:
                    ip += 1
                else:
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
                group_label = s.get("comment") or "(không tên)"
                self._log("info", f"▶ Bắt đầu NHÓM '{group_label}'")
                try:
                    if s.get("repeat_mode") == "time":
                        duration = _get_repeat_ms(s) / 1000.0
                        t0 = time.time()
                        while time.time() - t0 < duration and not self.stop_checker():
                            try:
                                self.execute_steps(sub_steps, is_root=False)
                            except ContinueGroupSignal:
                                continue
                    else:
                        group_repeat = max(1, int(s.get("repeat", 1)))
                        for loop_i in range(group_repeat):
                            if self.stop_checker():
                                break
                            if group_repeat > 1:
                                self._log("info", f"  Nhóm '{group_label}' - lượt {loop_i + 1}/{group_repeat}")
                            try:
                                self.execute_steps(sub_steps, is_root=False)
                            except ContinueGroupSignal:
                                continue
                except BreakGroupSignal:
                    # Gặp bước 'break_group' bên trong nhóm này (vd IF (Biến)
                    # đủ điều kiện -> Dừng vòng lặp) -> thoát vòng lặp NHÓM
                    # HIỆN TẠI ngay lập tức, không lặp thêm nữa.
                    self._log("warn", f"⛔ Dừng vòng lặp NHÓM '{group_label}' (break_group)")
                self._log("info", f"■ Kết thúc NHÓM '{group_label}'")
                ip = end_idx + 1
                continue

            elif act == "group_end":
                ip += 1
                continue

            # 4. Hành động thực thi
            repeat_mode = s.get("repeat_mode", "count")
            repeat_seconds = _get_repeat_ms(s) / 1000.0
            loop_start = time.time()
            loop_count = 0
            while not self.stop_checker():
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
                            self.adb.tap(pos[0], pos[1])
                            self._log("info", f"Tap [{int(pos[0]*100)}%, {int(pos[1]*100)}%]")

                    elif act == "swipe":
                        p1 = s.get("from")
                        p2 = s.get("to")
                        if p1 and p2:
                            duration = s.get("duration", 250)
                            hold_ms = s.get("hold_ms", 0)
                            if hold_ms and hold_ms > 0:
                                # Kéo & Giữ: dùng cho thanh trượt (slider) - xem
                                # docstring adb_helper.py::swipe_hold() để hiểu
                                # vì sao cần giữ yên tại đích trước khi nhả tay.
                                self.adb.swipe_hold(p1[0], p1[1], p2[0], p2[1],
                                                     move_duration_ms=duration, hold_ms=hold_ms)
                                self._log("info", f"Kéo & Giữ [{int(p1[0]*100)}%,{int(p1[1]*100)}%] -> [{int(p2[0]*100)}%,{int(p2[1]*100)}%] (giữ {hold_ms}ms)")
                            else:
                                self.adb.swipe(p1[0], p1[1], p2[0], p2[1], duration)
                                self._log("info", f"Swipe [{int(p1[0]*100)}%,{int(p1[1]*100)}%] -> [{int(p2[0]*100)}%,{int(p2[1]*100)}%]")

                    elif act == "wait_image":
                        tpl_name = s.get("template", "")
                        tpl_path = os.path.join("templates", tpl_name)
                        if os.path.exists(tpl_path):
                            tpl = cv2.imdecode(np.fromfile(tpl_path, dtype=np.uint8), cv2.IMREAD_COLOR)
                            start = time.time()
                            timeout = s.get("timeout", 8)
                            conf = s.get("conf", 0.80)
                            region = s.get("region")
                            scan_interval = _get_scan_interval(s)
                            found = False
                            while time.time() - start < timeout and not self.stop_checker():
                                coord, score = self.adb.find_image_on_screen(tpl, threshold=conf, region=region)
                                if coord:
                                    found = True
                                    if s.get("click", True):
                                        # tap_fast: bắn lệnh click NGAY, không chờ
                                        # adb.exe thoát hẳn - giảm độ trễ giữa lúc
                                        # VỪA thấy ảnh và lúc CLICK thật sự được gửi
                                        # đi (chỉ áp dụng riêng cho wait_image theo
                                        # yêu cầu, các bước ảnh khác giữ nguyên tap()).
                                        self.adb.tap_fast(coord[0], coord[1])
                                        self._log("success", f"Thấy ảnh '{tpl_name}' (khớp {score:.2f}) -> đã click {coord}")
                                    else:
                                        self._log("success", f"Thấy ảnh '{tpl_name}' (khớp {score:.2f})")
                                    break
                                time.sleep(scan_interval)
                            if not found:
                                self._log("warn", f"KHÔNG thấy ảnh '{tpl_name}' sau {timeout}s")
                        else:
                            self._log("error", f"Không tìm thấy file ảnh mẫu '{tpl_name}' trong thư mục templates")

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
                        found_name = None
                        while time.time() - start < timeout and not self.stop_checker():
                            hit_name, hit_pos, score = self.adb.find_any_image_on_screen(tpl_dict, threshold=conf, region=region)
                            if hit_pos:
                                found_name = hit_name
                                if s.get("click", True):
                                    self.adb.tap(hit_pos[0], hit_pos[1])
                                    self._log("success", f"Quét đa ảnh: thấy '{hit_name}' (khớp {score:.2f}) -> đã click {hit_pos}")
                                else:
                                    self._log("success", f"Quét đa ảnh: thấy '{hit_name}' (khớp {score:.2f})")
                                break
                            time.sleep(scan_interval)
                        if not found_name:
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
                                self.execute_steps(sub_steps, is_root=False)
                            except (BreakGroupSignal, ContinueGroupSignal):
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
                                self._log("info", f"OCR: cắt vùng ({x1},{y1})-({x2},{y2}) = {x2-x1}x{y2-y1}px trên ảnh {w}x{h}px")
                                try:
                                    text = self.adb.ocr_text_in_box(screen, (x1, y1, x2, y2), lang=s.get("lang", "vie+eng"))
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
                        self._log("info", f"Popup: \"{message}\"")
                        if self.popup_notifier:
                            self.popup_notifier(message, duration)

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

                except (BreakGroupSignal, ContinueGroupSignal):
                    raise
                except Exception as e:
                    # Ghi lỗi vào Nhật Ký Chạy kèm đúng loại hành động đang
                    # thực thi (vd lỗi ADB mất kết nối, lỗi đọc file ảnh...),
                    # rồi NỔI LỖI LÊN như cũ để không đổi hành vi dừng-khi-lỗi
                    # hiện tại - chỉ thêm khả năng NHÌN THẤY lỗi gì đã xảy ra.
                    self._log("error", f"Lỗi khi thực hiện '{act}': {e}")
                    raise

                steps_cnt = int(delay / 0.1)
                for _ in range(steps_cnt):
                    if self.stop_checker():
                        break
                    time.sleep(0.1)

            ip += 1

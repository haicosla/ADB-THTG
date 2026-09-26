"""
gui_step_edit.py — StepEditMixin: sửa 1 bước đã có trong danh sách (double
click / menu chuột phải -> "Sửa bước"), quản lý ảnh mẫu của nhóm IF/ELSE,
và các hàm dùng chung khi thêm/chèn 1 bước mới vào danh sách (tính vị trí
chèn, huỷ thao tác đang chờ, phím ESC...).

Đây là 1 phần của class MacroStudioApp (xem gui.py), tách theo chức năng
như các Mixin dashboard_*.py - "self." trỏ vào cùng 1 instance
MacroStudioApp, KHÔNG đổi hành vi so với bản gộp 1 file trước đây.
""" 
import os
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk

from recorder import parse_key_combo_text
from gui_dialogs import SetVarDialog, IncVarDialog, IfVarDialog, IfOcrDialog, SwipePathParamsDialog, MatchModeDialog, _bind_esc_close


class StepEditMixin:

    def _edit_step_field(self, idx, field_type):
        step = self.steps[idx]
        if field_type == "comment":
            new_val = simpledialog.askstring("Sửa Ghi Chú", "Nhập ghi chú mới:", initialvalue=step.get("comment", ""))
            if new_val is not None:
                step["comment"] = new_val
        elif field_type == "repeat":
            raw = simpledialog.askstring(
                "Sửa Số Lần Lặp",
                "Nhập số lần (vd: 5) hoặc thời gian (500ms, 30s, 2p):",
                initialvalue=self._format_repeat_display(step)
            )
            if raw:
                parsed = self._parse_repeat_input(raw)
                if parsed:
                    step.pop("repeat_seconds", None)
                    step.pop("repeat_ms", None)
                    step.pop("repeat_mode", None)
                    step.update(parsed)
                else:
                    messagebox.showerror("Lỗi", "Định dạng lặp không hợp lệ!")
        elif field_type == "delay":
            new_val = simpledialog.askfloat("Sửa Delay", "Thời gian delay sau bước (giây):", initialvalue=step.get("delay", 1.0), minvalue=0.0, maxvalue=60.0)
            if new_val is not None:
                step["delay"] = round(new_val, 2)
        elif field_type == "swipe_duration":
            new_val = simpledialog.askinteger(
                "Sửa Thời Gian Kéo",
                "Thời gian DI CHUYỂN từ điểm đầu tới điểm cuối (mili-giây):",
                initialvalue=step.get("duration", 250), minvalue=50, maxvalue=5000
            )
            if new_val is not None:
                step["duration"] = new_val
        elif field_type == "swipe_hold_ms":
            new_val = simpledialog.askinteger(
                "Sửa Giữ Cuối (chống bật ngược thanh trượt)",
                "Thời gian GIỮ YÊN tại điểm đến trước khi nhả tay (mili-giây).\n"
                "Đặt 0 = TẮT, dùng lệnh 'input swipe' bình thường (nhả tay\n"
                "ngay khi vừa tới nơi - phù hợp kéo màn hình/danh sách).\n"
                "Đặt > 0 (khuyên dùng 150-300) = kéo qua nhiều điểm mượt rồi\n"
                "GIỮ YÊN thêm 1 chút mới nhả tay - dùng khi kéo THANH TRƯỢT\n"
                "(slider) mà kéo bình thường bị game bật ngược lại vị trí cũ.",
                initialvalue=step.get("hold_ms", 0), minvalue=0, maxvalue=2000
            )
            if new_val is not None:
                if new_val > 0:
                    step["hold_ms"] = new_val
                else:
                    step.pop("hold_ms", None)
        elif field_type == "conf":
            new_val = simpledialog.askfloat("Sửa Độ Khớp", "Độ chính xác (0.50 - 0.99):", initialvalue=step.get("conf", 0.80), minvalue=0.5, maxvalue=0.99)
            if new_val is not None:
                step["conf"] = round(new_val, 2)
        elif field_type == "timeout":
            # TRƯỚC ĐÂY: maxvalue=120 giới hạn tối đa 120 giây, khiến không
            # thể đặt bước quét/lặp chờ lâu hơn 2 phút dù người dùng muốn
            # chờ vô thời hạn (đến khi thấy ảnh hoặc bị bấm Dừng thủ công).
            # Nay bỏ trần trên - chỉ còn giữ minvalue=1 (0/âm không có nghĩa
            # với 1 vòng lặp time.time()-start<timeout, xem check_condition()
            # trong logic_engine.py).
            new_val = simpledialog.askinteger(
                "Sửa Timeout",
                "Thời gian chờ tối đa (giây) - để rất lớn nếu muốn gần như\n"
                "KHÔNG GIỚI HẠN (vd 86400 = chờ tối đa 24 giờ, dừng sớm hơn\n"
                "ngay khi thấy ảnh hoặc khi bấm nút DỪNG):",
                initialvalue=step.get("timeout", 8), minvalue=1
            )
            if new_val is not None:
                step["timeout"] = new_val
        elif field_type == "click_toggle":
            # Đảo trạng thái click: True <-> False. Khi False, logic_engine
            # SẼ KHÔNG bắn lệnh tap dù thấy ảnh - dùng để bước ảnh này chỉ
            # đóng vai trò XÁC NHẬN (điều kiện) cho các bước phía sau, không
            # tự thao tác gì lên máy ảo (vd: dùng chung với IF Biến/Set Var
            # ngay sau đó để rẽ nhánh tuỳ theo có thấy ảnh hay không, mà
            # không cần lo bước này lỡ tay bấm nhầm vào đâu đó).
            step["click"] = not step.get("click", True)
        elif field_type == "click_offset":
            cur = step.get("click_offset") or [0, 0]
            raw = simpledialog.askstring(
                "Đặt Lệch Điểm Click",
                "Lệch điểm click so với TÂM ảnh vừa tìm thấy, đơn vị PIXEL thật\n"
                "trên màn hình thiết bị. Định dạng: dx,dy\n"
                "VD: 50,-30  (lệch PHẢI 50px, lên TRÊN 30px)\n"
                "VD: 0,0     (click đúng tâm ảnh - mặc định)\n"
                "Số dương X = sang phải, số dương Y = xuống dưới.",
                initialvalue=f"{cur[0]},{cur[1]}"
            )
            if raw is not None:
                try:
                    parts = [p.strip() for p in raw.split(",")]
                    dx, dy = int(float(parts[0])), int(float(parts[1]))
                    step["click_offset"] = [dx, dy]
                except (ValueError, IndexError):
                    messagebox.showerror("Lỗi", "Định dạng không hợp lệ! Nhập theo dạng: dx,dy (vd: 50,-30)")
                    return
        elif field_type == "click_delay_after_found":
            # Chỉ dùng cho wait_image: THỜI GIAN CHỜ SAU KHI THẤY ẢNH, TRƯỚC
            # KHI CLICK - khác hẳn field "delay" (chờ SAU KHI cả bước xong,
            # tức sau khi đã click). VD: đặt 3 -> thấy ảnh xong đợi 3 giây
            # mới bấm (chờ hiệu ứng/animation nút chạy xong hẳn).
            new_val = simpledialog.askfloat(
                "Đặt Delay Trước Khi Click",
                "Sau khi THẤY ảnh, chờ bao nhiêu giây rồi mới CLICK?\n"
                "(0 = click ngay lập tức - hành vi mặc định cũ)",
                initialvalue=step.get("click_delay_after_found", 0) or 0,
                minvalue=0.0, maxvalue=60.0
            )
            if new_val is not None:
                if new_val > 0:
                    step["click_delay_after_found"] = round(new_val, 2)
                else:
                    step.pop("click_delay_after_found", None)
        elif field_type == "on_fail_config":
            # Cấu hình on_fail cho wait_image/if_image: hỏi lần lượt chế độ
            # -> (nếu retry) số lần thử lại -> (nếu skip_to_label) tên nhãn
            # cần nhảy tới, thay vì phải tự dựng group_start/if_var bên
            # ngoài chỉ để "thử lại" hoặc "rẽ nhánh khi không thấy ảnh".
            cur = step.get("on_fail", "continue")
            mode = simpledialog.askstring(
                "Khi KHÔNG thấy ảnh (on_fail)",
                "Nhập chế độ xử lý khi hết timeout mà vẫn KHÔNG thấy ảnh:\n"
                "  continue      = bỏ qua, chạy tiếp bước kế tiếp (mặc định)\n"
                "  retry         = quét lại thêm N lần trước khi bỏ qua\n"
                "  skip_to_label = nhảy thẳng tới 1 bước Nhãn (Label) khác\n"
                "Nhập đúng 1 trong 3 từ trên:",
                initialvalue=cur
            )
            if mode is None:
                return
            mode = mode.strip().lower()
            if mode not in ("continue", "retry", "skip_to_label"):
                messagebox.showerror("Lỗi", "Chế độ không hợp lệ! Chỉ chấp nhận: continue / retry / skip_to_label")
                return
            step["on_fail"] = mode
            step.pop("on_fail_retries", None)
            step.pop("skip_to_label_name", None)
            if mode == "retry":
                n = simpledialog.askinteger(
                    "Số lần thử lại", "Thử lại thêm bao nhiêu lần (mỗi lần quét đủ timeout)?",
                    initialvalue=1, minvalue=1, maxvalue=20
                )
                step["on_fail_retries"] = n if n is not None else 1
            elif mode == "skip_to_label":
                name = simpledialog.askstring(
                    "Tên Nhãn cần nhảy tới",
                    "Nhập đúng tên 1 bước 'Nhãn (Label)' đã có trong kịch bản\n"
                    "(cùng cấp - không xuyên qua Nhóm Ngoài khác file):"
                )
                if name:
                    step["skip_to_label_name"] = name.strip()
        elif field_type == "click_jitter":
            cur = step.get("click_jitter") or [0, 0]
            raw = simpledialog.askstring(
                "Rải Ngẫu Nhiên Điểm Click (click_jitter)",
                "Biên độ rải NGẪU NHIÊN quanh điểm click mỗi lần, đơn vị\n"
                "PIXEL THẬT trên màn hình thiết bị. Định dạng: max_dx,max_dy\n"
                "VD: 15,10  (mỗi lần click lệch ngẫu nhiên tối đa ±15px\n"
                "ngang, ±10px dọc) - giúp tránh click ĐÚNG 1 pixel lặp lại\n"
                "hàng trăm lần (dấu hiệu bot dễ bị phát hiện).\n"
                "VD: 0,0    (TẮT - click chính xác tuyệt đối, mặc định)",
                initialvalue=f"{cur[0]},{cur[1]}"
            )
            if raw is not None:
                try:
                    parts = [p.strip() for p in raw.split(",")]
                    dx, dy = max(0, int(float(parts[0]))), max(0, int(float(parts[1])))
                    if dx or dy:
                        step["click_jitter"] = [dx, dy]
                    else:
                        step.pop("click_jitter", None)
                except (ValueError, IndexError):
                    messagebox.showerror("Lỗi", "Định dạng không hợp lệ! Nhập theo dạng: max_dx,max_dy (vd: 15,10)")
                    return
        elif field_type == "tap_hold_ms":
            new_val = simpledialog.askinteger(
                "Giữ Tay (Long-click)",
                "Thời gian GIỮ TAY tại điểm tap trước khi nhả (mili-giây).\n"
                "Đặt 0 = TẮT, tap nhanh bình thường (chạm rồi nhả ngay).\n"
                "Đặt > 0 (vd 500-1000) = giữ tay, dùng cho menu ngữ cảnh/\n"
                "kéo-thả cần GIỮ mới kích hoạt được.",
                initialvalue=step.get("hold_ms", 0), minvalue=0, maxvalue=5000
            )
            if new_val is not None:
                if new_val > 0:
                    step["hold_ms"] = new_val
                else:
                    step.pop("hold_ms", None)
        elif field_type == "wait_for_toggle":
            # Đảo chế độ IF Ảnh giữa "appear" (mặc định - ĐÚNG khi ảnh
            # XUẤT HIỆN) và "vanish" (ĐÚNG khi ảnh BIẾN MẤT) - xem
            # logic_engine.check_condition(). Nhờ if_image vẫn giữ đầy đủ
            # nhánh ĐÚNG/SAI (else/endif) + on_fail (continue/retry/
            # skip_to_label) sẵn có, nên ở CẢ 2 chế độ đều chọn được rõ
            # ràng "sau khi [xuất hiện/biến mất] thì làm gì" (nhánh ĐÚNG,
            # ngay sau if_image) và "nếu KHÔNG [xuất hiện/biến mất] (hết
            # timeout) thì làm gì" (nhánh ELSE, hoặc on_fail=skip_to_label)
            # - khác với wait_vanish/wait_image (bước đơn, không rẽ nhánh
            # ĐÚNG/SAI được).
            cur = step.get("wait_for", "appear")
            step["wait_for"] = "vanish" if cur == "appear" else "appear"
        elif field_type == "turbo_toggle":
            # Đảo Chế Độ Siêu Tốc (turbo): True -> logic_engine sẽ gọi các
            # hàm RIÊNG find_image_turbo()/find_any_image_turbo()/
            # find_all_matches_turbo()/tap_turbo_px() (xem adb_helper.py) -
            # nói chuyện thẳng qua socket TCP với ADB server thay vì spawn
            # tiến trình adb.exe mới mỗi lần chụp/click, nhanh hơn nhiều cho
            # ảnh chỉ hiện rất ngắn. False (mặc định) -> giữ NGUYÊN đường
            # quét/click cũ, không đổi hành vi. Chỉ áp dụng cho ĐÚNG bước
            # này - bật ở 1 bước không ảnh hưởng các bước khác.
            step["turbo"] = not step.get("turbo", False)
        elif field_type == "match_mode_dialog":
            # Mở hộp thoại chọn KIỂU QUÉT ẢNH (Xám/Màu/Xám-Δ/Màu-Δ/Viền) cho
            # bước này - dialog (MatchModeDialog) đã có sẵn từ trước trong
            # gui_dialogs.py nhưng CHƯA TỪNG được gắn vào đâu cả (không có
            # menu/nút nào gọi tới) nên trước đây người dùng không có cách
            # nào đổi kiểu quét ngoài việc tự sửa tay file JSON kịch bản.
            # Nay gắn vào menu chuột phải (xem gui_ui_build.py).
            templates = step.get("templates")
            if not templates:
                single = step.get("template")
                templates = [single] if single else []
            dlg = MatchModeDialog(
                self.root,
                templates=templates,
                default_mode=step.get("match_mode"),
                template_modes=step.get("template_modes"),
            )
            self.root.wait_window(dlg)
            if dlg.result:
                step["match_mode"] = dlg.result["match_mode"]
                if dlg.result["template_modes"]:
                    step["template_modes"] = dlg.result["template_modes"]
                else:
                    step.pop("template_modes", None)
        elif field_type == "click_all_toggle":
            # Đảo trạng thái Click Tất Cả cho multi_image: True = tìm và
            # click MỌI vị trí khớp thấy được trong 1 tấm ảnh chụp màn hình
            # (vd nhặt hết vật phẩm cùng loại), False (mặc định) = chỉ click
            # 1 vị trí "tốt nhất" tìm thấy đầu tiên như trước đây.
            step["click_all"] = not step.get("click_all", False)
        elif field_type == "label_name":
            new_val = simpledialog.askstring("Sửa Tên Nhãn", "Tên nhãn (dùng để on_fail=skip_to_label nhảy tới):", initialvalue=step.get("name", ""))
            if new_val:
                step["name"] = new_val.strip()
                step["comment"] = f"🏷️ Nhãn: {step['name']}"
        elif field_type == "scan_interval":
            new_val = simpledialog.askfloat(
                "Sửa Tốc Độ Quét",
                "Khoảng nghỉ giữa 2 lần quét ảnh liên tiếp (giây).\n"
                "Càng NHỎ quét càng NHANH (bắt được cả ảnh chỉ hiện rất ngắn)\n"
                "nhưng tốn CPU hơn. Khuyên dùng 0.05 - 0.15:",
                initialvalue=step.get("scan_interval", 0.1), minvalue=0.02, maxvalue=2.0
            )
            if new_val is not None:
                step["scan_interval"] = round(new_val, 2)
        elif field_type == "set_var_params":
            existing = self._get_existing_variable_names()
            dlg = SetVarDialog(self.root, existing_vars=existing, initial_var=step.get("var", "a"), initial_val=step.get("value", 0))
            self.root.wait_window(dlg)
            if dlg.result:
                step["var"] = dlg.result["var"]
                step["value"] = dlg.result["value"]
                step["comment"] = f"Đặt biến {step['var']} = {step['value']}"
        elif field_type == "inc_var_params":
            existing = self._get_existing_variable_names()
            dlg = IncVarDialog(self.root, existing_vars=existing, initial_var=step.get("var", "a"), initial_amount=step.get("amount", 1))
            self.root.wait_window(dlg)
            if dlg.result:
                step["var"] = dlg.result["var"]
                step["amount"] = dlg.result["amount"]
                step["comment"] = f"Biến {step['var']} {'+' if step['amount']>=0 else ''}{step['amount']}"
        elif field_type == "if_var_params":
            existing = self._get_existing_variable_names()
            dlg = IfVarDialog(
                self.root,
                existing_vars=existing,
                initial_var=step.get("var", "a"),
                initial_op=step.get("op", ">="),
                initial_val=step.get("value", 5)
            )
            self.root.wait_window(dlg)
            if dlg.result:
                step["var"] = dlg.result["var"]
                step["op"] = dlg.result["op"]
                step["value"] = dlg.result["value"]
                step["comment"] = f"Nếu {step['var']} {step['op']} {step['value']}"
        elif field_type == "text_content":
            t = simpledialog.askstring(
                "Sửa Gõ Chữ",
                "Nhập nội dung gõ mới. Dùng {tên_biến} để lấy giá trị 1 biến (vd {ocr_text}):",
                initialvalue=step.get("text", "")
            )
            if t is not None:
                step["text"] = t
                step["comment"] = f"Gõ: {t}"

        elif field_type == "key_combo_keys":
            current = "+".join(k.replace("KEYCODE_", "") for k in step.get("keys", []))
            raw = simpledialog.askstring(
                "Sửa Tổ Hợp Phím",
                "Nhập tổ hợp phím (vd: ctrl+1, ctrl+shift+a, enter):",
                initialvalue=current
            )
            if raw:
                keys = parse_key_combo_text(raw)
                if keys:
                    step["keys"] = keys
                    step["comment"] = "Tổ hợp: " + raw
                else:
                    messagebox.showerror("Lỗi", "Không nhận dạng được tổ hợp phím!")

        elif field_type == "ocr_var":
            new_val = simpledialog.askstring("Sửa Tên Biến OCR", "Lưu kết quả OCR vào biến tên gì:", initialvalue=step.get("var", "ocr_text"))
            if new_val:
                step["var"] = new_val.strip()
                step["comment"] = f"OCR vùng -> biến {step['var']}"

        elif field_type == "if_ocr_config":
            dlg = IfOcrDialog(
                self.root,
                initial_text=step.get("text", ""),
                initial_match=step.get("match", "contains"),
                initial_click=step.get("click", False),
                initial_var=step.get("var", ""),
            )
            self.root.wait_window(dlg)
            if dlg.result:
                r = dlg.result
                step["text"] = r["text"]
                step["match"] = r["match"]
                step["click"] = r["click"]
                if r.get("var"):
                    step["var"] = r["var"]
                else:
                    step.pop("var", None)
                step["comment"] = f"IF OCR \"{r['text']}\"" if r["text"] else "IF OCR (chỉ đọc)"

        elif field_type == "popup_message":
            new_val = simpledialog.askstring(
                "Sửa Nội Dung Thông Báo",
                "Nội dung popup. Dùng {tên_biến} để chèn giá trị 1 biến, vd {ocr_text}:",
                initialvalue=step.get("message", "")
            )
            if new_val is not None:
                step["message"] = new_val
                step["comment"] = f"Thông báo: {new_val}"

        elif field_type == "popup_duration":
            new_val = simpledialog.askfloat(
                "Sửa Thời Gian Hiện Popup",
                "Số giây tự tắt (0 = hiện tới khi bấm Đóng, kịch bản DỪNG chờ):",
                initialvalue=step.get("duration", 2.0), minvalue=0.0, maxvalue=60.0
            )
            if new_val is not None:
                step["duration"] = new_val

        self.refresh_tree()
        self.tree.selection_set(str(idx))

    def convert_step_to_group_image(self, idx):
        """Menu chuột phải: chuyển 1 bước đang TÌM 1 ẢNH ĐƠN (field
        'template') sang TÌM ẢNH NHÓM (field 'templates' - nhiều ảnh, khớp
        ĐÚNG 1 TRONG SỐ ĐÓ là coi như đạt, hữu ích khi 1 nút/icon có nhiều
        biến thể hình ảnh khác nhau tuỳ trạng thái/sự kiện). Ảnh hiện tại
        được giữ lại làm ảnh ĐẦU TIÊN trong nhóm, sau đó mở ngay hộp thoại
        "Quản Lý Ảnh Trong Nhóm" (xem manage_group_templates) để thêm các
        ảnh còn lại - không cần tạo bước mới từ đầu.

        - if_image (điều kiện IF): giữ nguyên action - if_image đã hỗ trợ
          SẴN cả 'template' lẫn 'templates' (xem logic_engine.check_condition),
          chỉ cần đổi tên field.
        - wait_image (Tìm & Click 1 Ảnh): action này KHÔNG hỗ trợ
          'templates' (xem logic_engine.execute_steps) - phải đổi hẳn sang
          action 'multi_image' (Quét Đa Ảnh), tương đương gần nhất có hỗ
          trợ nhóm ảnh + click khi thấy. Đặt click_all=False (chỉ click 1
          vị trí khớp TỐT NHẤT tìm thấy) để giữ đúng hành vi wait_image cũ
          (nếu muốn click HẾT mọi vị trí khớp, tự bật lại qua menu chuột
          phải -> 🖱️ Bật/Tắt Click Tất Cả sau khi chuyển)."""
        if idx < 0 or idx >= len(self.steps):
            return
        step = self.steps[idx]
        act = step.get("action")
        if act not in ("wait_image", "if_image"):
            return
        if "templates" in step:
            messagebox.showinfo("Đã là nhóm ảnh", "Bước này đã đang ở chế độ Tìm Ảnh Nhóm rồi.")
            return

        current_tpl = step.get("template")
        templates = [current_tpl] if current_tpl else []
        step.pop("template", None)
        step["templates"] = templates

        if act == "wait_image":
            step["action"] = "multi_image"
            step.setdefault("click", True)
            step["click_all"] = False
            step["comment"] = f"Quét nhóm ảnh (đã chuyển từ Tìm & Click): {len(templates)} ảnh"
        else:
            step["comment"] = f"Nếu thấy bất kỳ ({len(templates)} ảnh, đã chuyển từ IF 1 ảnh)"

        self.refresh_tree()
        self.tree.selection_set(str(idx))
        self.manage_group_templates(idx)

    def manage_group_templates(self, idx):
        """Dialog quản lý danh sách ảnh cho 1 bước if_image (nhóm) hoặc
        multi_image (quét đa ảnh): đổi từng ảnh, xóa ảnh, thêm ảnh mới.
        Trước đây các bước này KHÔNG sửa được ảnh sau khi đã tạo vì menu
        chỉnh sửa không nhận ra field 'templates' (list)."""
        step = self.steps[idx]
        templates = list(step.get("templates", []))

        top = tk.Toplevel(self.root)
        top.title("Quản Lý Ảnh Trong Nhóm")
        top.transient(self.root)
        top.grab_set()
        _bind_esc_close(top)

        # Giữ tham chiếu PhotoImage ở đây, không thì bị Python dọn rác mất
        # ảnh ngay sau khi render_rows() return (lỗi kinh điển của Tkinter).
        top._thumb_refs = []

        f_list = ttk.Frame(top)
        f_list.pack(padx=10, pady=10, fill="both", expand=True)

        def load_thumb(fname, size=48):
            path = os.path.join("templates", fname)
            try:
                img = Image.open(path)
                img.thumbnail((size, size))
                photo = ImageTk.PhotoImage(img)
                top._thumb_refs.append(photo)
                return photo
            except Exception:
                return None

        def render_rows():
            top._thumb_refs.clear()
            for w in f_list.winfo_children():
                w.destroy()
            if not templates:
                ttk.Label(f_list, text="(Nhóm không còn ảnh nào)", foreground="red").pack(pady=6)
            for i, fname in enumerate(templates):
                row = ttk.Frame(f_list)
                row.pack(fill="x", pady=3)
                thumb = load_thumb(fname)
                if thumb:
                    tk.Label(row, image=thumb, bg="#212121").pack(side="left", padx=4)
                else:
                    tk.Label(row, text="(?)", width=6, bg="#212121", fg="gray").pack(side="left", padx=4)
                ttk.Label(row, text=fname, width=28).pack(side="left", padx=4)
                ttk.Button(row, text="🔄 Đổi", command=lambda i=i: replace_one(i)).pack(side="left", padx=2)
                ttk.Button(row, text="❌ Xóa", command=lambda i=i: remove_one(i)).pack(side="left", padx=2)

        def replace_one(i):
            path = filedialog.askopenfilename(initialdir="templates", title="Chọn ảnh thay thế",
                                              filetypes=[("Images", "*.png;*.jpg")], parent=top)
            if path:
                templates[i] = os.path.basename(path)
                render_rows()

        def remove_one(i):
            if len(templates) <= 1:
                messagebox.showwarning("Lưu ý", "Nhóm phải còn ít nhất 1 ảnh!", parent=top)
                return
            del templates[i]
            render_rows()

        def add_new():
            paths = filedialog.askopenfilenames(initialdir="templates", title="Thêm ảnh vào nhóm",
                                                filetypes=[("Images", "*.png;*.jpg")], parent=top)
            for p in paths:
                templates.append(os.path.basename(p))
            render_rows()

        render_rows()

        f_btn = ttk.Frame(top)
        f_btn.pack(pady=8)
        ttk.Button(f_btn, text="➕ Thêm Ảnh Mới", command=add_new).pack(side="left", padx=4)
        ttk.Button(f_btn, text="✔ Xong", command=top.destroy).pack(side="left", padx=4)

        top.wait_window()

        if templates:
            step["templates"] = templates
            label = "Quét song song" if step.get("action") == "multi_image" else "Nếu thấy bất kỳ"
            step["comment"] = f"{label} ({len(templates)} ảnh)"
        self.refresh_tree()
        self.tree.selection_set(str(idx))
        self.on_step_selected()

    def _on_recorder_step_captured(self, step):
        self.root.after(0, lambda: self._append_recorded_step(step))

    def _append_recorded_step(self, step):
        self.steps.append(step)
        self.refresh_tree()

    def _on_step_list_changed(self, select_index=None, select_range=None):
        self.refresh_tree()
        self._schedule_autosave()
        # Chỉ chọn lại những dòng THỰC SỰ đang hiện trên cây - phòng trường
        # hợp dòng cần chọn lại rơi vào bên trong 1 khối IF/Nhóm đang bị
        # thu gọn (ẩn khỏi cây) nên không có mặt để mà bôi đen được.
        visible = set(self.tree.get_children(""))
        if select_range is not None:
            start, end = select_range
            ids = [str(i) for i in range(start, end + 1) if 0 <= i < len(self.steps) and str(i) in visible]
            if ids:
                self.tree.selection_set(ids)
        elif select_index is not None and 0 <= select_index < len(self.steps) and str(select_index) in visible:
            self.tree.selection_set(str(select_index))

    def _get_insert_index(self):
        sel = self.tree.selection()
        if sel:
            return int(sel[-1]) + 1
        return len(self.steps)

    def _insert_step(self, step):
        idx = self._get_insert_index()
        self.steps.insert(idx, step)
        self.refresh_tree()
        self.tree.selection_set(str(idx))

    _CAPTURE_HINTS = {
        "wait_image": "🖱️ Kéo khung trên Preview để chọn ẢNH cần Tìm & Click... (ESC = để trống, chọn ảnh sau)",
        "wait_vanish": "🖱️ Kéo khung trên Preview để chọn ẢNH cần CHỜ BIẾN MẤT... (ESC = để trống, chọn ảnh sau)",
        "if_image": "🖱️ Kéo khung trên Preview để chọn ẢNH điều kiện IF... (ESC = để trống, chọn ảnh sau)",
        "tap": "🖱️ Bấm 1 điểm trên Preview để chọn tọa độ Tap... (ESC = để trống, chọn tọa độ sau)",
        "swipe": "🖱️ Kéo từ điểm đầu đến điểm cuối trên Preview để tạo Vuốt... (ESC = để trống, chọn tọa độ sau)",
        "zoom": "🖱️ Bấm 1 điểm trên Preview làm TÂM cử chỉ Zoom (Pinch)... (ESC = để trống, chọn tâm sau)",
        "ocr_text": "🖱️ Kéo khung trên Preview để chọn VÙNG cần quét chữ (OCR)... (ESC = hủy)",
        "if_ocr": "🖱️ Kéo khung trên Preview để chọn VÙNG cần quét chữ làm ĐIỀU KIỆN IF... (ESC = hủy)",
        "swipe_path": "🖱️ Click LẦN LƯỢT từng điểm trên đường vuốt · Backspace = xoá điểm vừa click · Enter = XONG (cần ≥2 điểm) · ESC = hủy",
        "image_region": "🖱️ Kéo khung trên Preview để GIỚI HẠN vùng quét ảnh cho bước này... (ESC = hủy)",
    }

    # Các loại hành động CHO PHÉP tạo bước RỖNG (chưa chọn ảnh/tọa độ) khi
    # bấm ESC thay vì quét ngay - "ocr_text"/"image_region" KHÔNG có trong
    # danh sách này vì bản thân chúng luôn gắn liền với 1 bước cụ thể (sửa
    # vùng của bước đã có, hoặc phải hỏi tên biến ngay lúc tạo) nên ESC ở 2
    # loại đó chỉ đơn giản là HỦY, không tạo gì cả.
    _PLACEHOLDER_KINDS = ("wait_image", "wait_vanish", "if_image", "tap", "swipe", "zoom")

    def _arm_capture(self, kind):
        if self.current_screen_cv is None:
            messagebox.showwarning("Lưu ý", "Hãy chụp màn hình hoặc bật Xem Trực Tiếp trước!")
            return
        self.pending_action = kind
        self.lbl_capture_hint.config(text=self._CAPTURE_HINTS.get(kind, ""))
        self.btn_cancel_capture.pack(side="left", padx=2)

    def _is_editing_existing_step(self):
        """True nếu pending_action hiện tại là đang SỬA LẠI (chọn lại ảnh/
        tọa độ/vùng quét) cho 1 bước ĐÃ CÓ SẴN trong danh sách, thay vì đang
        tạo mới - dùng để quyết định bấm ESC có nên chèn bước RỖNG hay không
        (chỉ chèn khi đang TẠO MỚI, sửa bước cũ thì ESC chỉ đơn giản là hủy
        sửa, giữ nguyên bước cũ)."""
        k = self.pending_action
        return (
            (k in ("wait_image", "if_image", "wait_vanish") and self._image_edit_idx is not None) or
            (k == "tap" and self._tap_edit_idx is not None) or
            (k == "swipe" and self._swipe_edit_idx is not None) or
            (k == "zoom" and self._zoom_edit_idx is not None) or
            (k == "swipe_path" and self._swipe_path_edit_idx is not None) or
            (k in ("ocr_text", "if_ocr") and self._ocr_edit_idx is not None) or
            (k == "image_region" and self._region_edit_idx is not None)
        )

    def _on_return_key(self, event=None):
        """Enter: CHỈ có tác dụng khi đang ở chế độ chọn nhiều điểm cho
        swipe_path (xem on_canvas_release trong gui_canvas.py) - hoàn tất
        và chèn/cập nhật bước. Mọi lúc khác trả về None (không "break") để
        không ảnh hưởng phím Enter ở nơi khác (hộp thoại Toplevel khác tự
        bind Return riêng lên chính nó, luôn được Tk ưu tiên gọi trước khi
        bind_all ở root được gọi)."""
        if self.pending_action != "swipe_path":
            return
        self._finish_swipe_path()
        return "break"

    def _on_backspace_key(self, event=None):
        """Backspace: CHỈ hoạt động khi đang chọn nhiều điểm cho swipe_path
        VÀ con trỏ KHÔNG đang ở trong 1 ô nhập liệu (Entry/Text) - để không
        phá việc xoá ký tự bình thường khi đang gõ chữ bất kỳ đâu khác
        trong app."""
        if self.pending_action != "swipe_path":
            return
        focus_widget = self.root.focus_get()
        if isinstance(focus_widget, (tk.Entry, tk.Text)):
            return
        try:
            widget_class = focus_widget.winfo_class() if focus_widget else ""
        except Exception:
            widget_class = ""
        if widget_class in ("TEntry", "TCombobox", "TSpinbox", "Text"):
            return
        self._undo_last_swipe_path_point()
        return "break"

    def _draw_swipe_path_markers(self):
        """Vẽ lại TOÀN BỘ chấm tròn + số thứ tự + đường nối cho các điểm
        đã click của swipe_path đang chọn dở - gọi lại sau MỖI lần thêm/bớt
        điểm (đơn giản hơn nhiều so với tính toán vẽ thêm/xoá riêng lẻ, và
        số điểm của 1 đường vuốt thường chỉ vài chục nên xoá-vẽ-lại không
        tốn kém gì đáng kể)."""
        for item_id in self._swipe_path_marker_ids:
            self.canvas.delete(item_id)
        self._swipe_path_marker_ids = []
        pts_canvas = [(nx * self.preview_w, ny * self.preview_h) for nx, ny in self._swipe_path_points]
        for i in range(len(pts_canvas) - 1):
            x1, y1 = pts_canvas[i]
            x2, y2 = pts_canvas[i + 1]
            self._swipe_path_marker_ids.append(
                self.canvas.create_line(x1, y1, x2, y2, fill="#ba00ff", width=2, arrow=tk.LAST))
        for i, (x, y) in enumerate(pts_canvas):
            self._swipe_path_marker_ids.append(
                self.canvas.create_oval(x - 6, y - 6, x + 6, y + 6, outline="#ba00ff", width=2, fill="#ffffff"))
            self._swipe_path_marker_ids.append(
                self.canvas.create_text(x + 12, y - 10, text=str(i + 1), fill="#ba00ff", font=("Segoe UI", 9, "bold")))

    def _undo_last_swipe_path_point(self):
        if self._swipe_path_points:
            self._swipe_path_points.pop()
            self._draw_swipe_path_markers()

    def _finish_swipe_path(self):
        """Hoàn tất chọn điểm cho swipe_path (Enter) - cần ÍT NHẤT 2 điểm,
        hỏi Thời Gian/Giữ Cuối qua SwipePathParamsDialog rồi chèn (hoặc cập
        nhật nếu đang SỬA LẠI 1 bước có sẵn) và dọn dẹp trạng thái đang
        chọn dở."""
        points = list(self._swipe_path_points)
        edit_idx = self._swipe_path_edit_idx
        if len(points) < 2:
            messagebox.showwarning("Lưu ý", "Cần click ÍT NHẤT 2 điểm trên Preview trước khi bấm Enter!\n(Click thêm điểm, Backspace để xoá điểm vừa click nhầm, ESC để huỷ hẳn)")
            return
        existing = self.steps[edit_idx] if (edit_idx is not None and 0 <= edit_idx < len(self.steps)) else None
        dlg = SwipePathParamsDialog(self.root, initial=existing or {})
        self.root.wait_window(dlg)
        self._cancel_pending_action()
        if not dlg.result:
            return
        params = dlg.result
        pts_txt = " → ".join(f"[{int(nx*100)}%,{int(ny*100)}%]" for nx, ny in points)
        if existing is not None:
            existing["points"] = [list(p) for p in points]
            existing.update(params)
            existing["comment"] = f"Vuốt {len(points)} điểm"
            self.refresh_tree()
            self.tree.selection_set(str(edit_idx))
        else:
            self._insert_step({
                "action": "swipe_path", "points": [list(p) for p in points],
                "duration": params["duration"], "hold_ms": params["hold_ms"],
                "repeat": 1, "delay": float(self.spin_default_delay.get() or 1.0),
                "comment": f"Vuốt {len(points)} điểm",
            })

    def _on_escape_key(self, event=None):
        """ESC khi đang chờ quét (pending_action): hủy bỏ. Nếu đang TẠO MỚI
        1 bước Tìm&Click Ảnh/IF Ảnh/Tap/Swipe/Zoom (không phải sửa lại bước
        cũ), thêm luôn 1 bước RỖNG (chưa chọn ảnh/tọa độ) thay vì không làm
        gì - cho phép soạn xong bố cục kịch bản trước, quay lại CHỌN ẢNH/TỌA
        ĐỘ SAU (bấm đúp hoặc menu chuột phải vào bước đó)."""
        if not self.pending_action:
            return
        kind = self.pending_action
        make_placeholder = kind in self._PLACEHOLDER_KINDS and not self._is_editing_existing_step()
        self._cancel_pending_action()
        if make_placeholder:
            self._insert_placeholder_step(kind)

    def _insert_placeholder_step(self, kind):
        """Chèn 1 bước RỖNG (chưa chọn ảnh/tọa độ) cho hành động `kind` -
        xem _on_escape_key(). Bấm đúp hoặc chuột phải -> chọn lại vào bước
        này trong danh sách để chọn ảnh/tọa độ thật khi cần."""
        if kind in ("wait_image", "if_image", "wait_vanish"):
            step = {
                "action": kind, "template": None,
                "timeout": 3 if kind == "if_image" else 8, "conf": 0.80,
                "scan_interval": float(self.spin_all_scan.get() or 0.10),
                "repeat": 1, "delay": float(self.spin_default_delay.get() or 1.0),
                "comment": "⚠️ Chưa chọn ảnh - bấm đúp/chuột phải để chọn",
            }
            if kind == "wait_image":
                step["click"] = True
        elif kind == "tap":
            step = {
                "action": "tap", "pos": None, "repeat": 1, "delay": float(self.spin_default_delay.get() or 1.0),
                "comment": "⚠️ Chưa chọn tọa độ - bấm đúp/chuột phải để chọn",
            }
        elif kind == "swipe":
            step = {
                "action": "swipe", "from": None, "to": None, "duration": 250,
                "repeat": 1, "delay": float(self.spin_default_delay.get() or 1.0),
                "comment": "⚠️ Chưa chọn tọa độ - bấm đúp/chuột phải để chọn",
            }
        elif kind == "zoom":
            step = {
                "action": "zoom", "center": None, "start_radius": 70, "end_radius": 260,
                "angle": 90, "duration": 400, "repeat": 1, "delay": float(self.spin_default_delay.get() or 1.0),
                "comment": "⚠️ Chưa chọn tâm - bấm đúp/chuột phải để chọn",
            }
        else:
            return
        self._insert_step(step)

    def _cancel_pending_action(self):
        self._ocr_edit_idx = None
        self._region_edit_idx = None
        self._image_edit_idx = None
        self._tap_edit_idx = None
        self._swipe_edit_idx = None
        self._zoom_edit_idx = None
        self._swipe_path_edit_idx = None
        self._swipe_path_points = []
        for item_id in self._swipe_path_marker_ids:
            self.canvas.delete(item_id)
        self._swipe_path_marker_ids = []
        self.pending_action = None
        self.lbl_capture_hint.config(text="")
        self.btn_cancel_capture.pack_forget()
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None


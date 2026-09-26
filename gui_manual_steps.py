"""
gui_manual_steps.py — ManualStepsMixin: các nút "Thêm Bước Thủ Công" ở
menu chuột phải (gõ chữ, tổ hợp phím, popup, IF/ELSE, GROUP, SET_VAR,
INC_VAR, IF_VAR, Dữ Liệu Kế Tiếp, BREAK/CONTINUE, chờ nhiều ảnh...) - mỗi
hàm add_manual_xxx() chèn 1 loại bước tương ứng vào self.steps mà KHÔNG
cần chụp ảnh màn hình (khác với các bước "chờ ảnh"/"chạm" cần capture).

Đây là 1 phần của class MacroStudioApp (xem gui.py), tách theo chức năng
như các Mixin dashboard_*.py - "self." trỏ vào cùng 1 instance
MacroStudioApp, KHÔNG đổi hành vi so với bản gộp 1 file trước đây.
""" 
import os
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from recorder import parse_key_combo_text
from gui_dialogs import SetVarDialog, IncVarDialog, IfVarDialog, ZoomStepDialog, SwipePathParamsDialog
from gui_dialogs_ifgroup import IfGroupDialog
from gui_dialogs_data import DataGroupManagerDialog, NextDataItemDialog


class ManualStepsMixin:

    def add_manual_wait_image(self):
        self._arm_capture("wait_image")

    def add_manual_wait_vanish(self):
        self._arm_capture("wait_vanish")

    def add_manual_tap(self):
        self._arm_capture("tap")

    def add_manual_swipe(self):
        self._arm_capture("swipe")

    def add_manual_zoom(self):
        self._arm_capture("zoom")

    def add_manual_swipe_path(self):
        self._arm_capture("swipe_path")

    def _arm_swipe_path_recapture(self, idx):
        """Chọn LẠI TOÀN BỘ các điểm cho 1 bước swipe_path ĐÃ CÓ SẴN - xoá
        sạch điểm cũ và bắt đầu click lại từ đầu (đơn giản hơn nhiều so
        với "sửa từng điểm 1", và số điểm của 1 đường vuốt thường không
        nhiều nên click lại toàn bộ không tốn công đáng kể)."""
        if not (0 <= idx < len(self.steps)):
            return
        self._swipe_path_edit_idx = idx
        self._swipe_path_points = []
        self._arm_capture("swipe_path")

    def _edit_swipe_path_params(self, idx):
        """Sửa Thời Gian/Giữ Cuối của 1 bước swipe_path ĐÃ CÓ SẴN - KHÔNG
        cần chọn lại các điểm (dùng _arm_swipe_path_recapture cho việc đó)."""
        if not (0 <= idx < len(self.steps)):
            return
        step = self.steps[idx]
        dlg = SwipePathParamsDialog(self.root, initial=step)
        self.root.wait_window(dlg)
        if dlg.result:
            step.update(dlg.result)
            self.refresh_tree()
            self.tree.selection_set(str(idx))

    def _arm_image_recapture(self, idx):
        """Chọn (hoặc chọn LẠI) ảnh cho 1 bước wait_image/if_image ĐÃ CÓ
        SẴN bằng cách quét khung trên Preview - dùng cho cả bước rỗng (tạo
        qua ESC) lẫn bước đã có ảnh muốn đổi ảnh khác."""
        if not (0 <= idx < len(self.steps)):
            return
        self._image_edit_idx = idx
        self._arm_capture(self.steps[idx].get("action", "wait_image"))

    def _arm_tap_recapture(self, idx):
        """Chọn (hoặc chọn LẠI) tọa độ cho 1 bước tap ĐÃ CÓ SẴN."""
        if not (0 <= idx < len(self.steps)):
            return
        self._tap_edit_idx = idx
        self._arm_capture("tap")

    def _arm_swipe_recapture(self, idx):
        """Chọn (hoặc chọn LẠI) điểm đầu/cuối cho 1 bước swipe ĐÃ CÓ SẴN."""
        if not (0 <= idx < len(self.steps)):
            return
        self._swipe_edit_idx = idx
        self._arm_capture("swipe")

    def _arm_zoom_recapture(self, idx):
        """Chọn (hoặc chọn LẠI) TÂM cử chỉ cho 1 bước zoom ĐÃ CÓ SẴN."""
        if not (0 <= idx < len(self.steps)):
            return
        self._zoom_edit_idx = idx
        self._arm_capture("zoom")

    def _edit_zoom_params(self, idx):
        """Sửa bán kính/góc/thời gian của 1 bước zoom ĐÃ CÓ SẴN - KHÔNG cần
        chọn lại tâm (dùng _arm_zoom_recapture cho việc đó)."""
        if not (0 <= idx < len(self.steps)):
            return
        step = self.steps[idx]
        dlg = ZoomStepDialog(self.root, initial=step)
        self.root.wait_window(dlg)
        if dlg.result:
            step.update(dlg.result)
            step["comment"] = "Phóng To" if dlg.result["end_radius"] > dlg.result["start_radius"] else "Thu Nhỏ"
            self.refresh_tree()
            self.tree.selection_set(str(idx))

    def _worker_send_zoom(self, nx, ny, start_radius, end_radius, angle, duration):
        method = self.adb.pinch_zoom(nx, ny, start_radius, end_radius, angle_deg=angle, duration_ms=duration)
        if method == "sendevent":
            self._log_run("success", "🔍 Đã gửi Zoom bằng multi-touch thật (sendevent) - nếu app/game vẫn không zoom, có thể app đó xử lý chạm không chuẩn.")
        else:
            self._log_run("warn", "🔍 Không dò được thiết bị cảm ứng đa điểm - đã gửi Zoom bằng phương án dự phòng (2 vuốt song song), CÓ THỂ không được app nhận diện là cử chỉ zoom.")
        time.sleep(0.4)
        if not self.is_streaming_active:
            self.capture_and_show()

    def add_manual_type_text(self):
        text = simpledialog.askstring(
            "Thêm Gõ Chữ",
            "Nhập nội dung cần gõ.\nDùng {tên_biến} để chèn GIÁ TRỊ 1 biến (vd biến từ bước OCR):\n"
            "vd: {ocr_text}  hoặc  Số dư: {ocr_text} xu"
        )
        if not text:
            return
        self._insert_step({"action": "type_text", "text": text, "repeat": 1, "delay": 0.5, "comment": f"Gõ: {text}"})

    def add_manual_key_combo(self):
        raw = simpledialog.askstring("Thêm Tổ Hợp Phím", "Nhập tổ hợp phím (vd: ctrl+a, enter):")
        if not raw:
            return
        keys = parse_key_combo_text(raw)
        if not keys:
            return
        self._insert_step({"action": "key_combo", "keys": keys, "repeat": 1, "delay": 0.5, "comment": "Tổ hợp: " + raw})

    def add_manual_ocr(self):
        self._arm_capture("ocr_text")

    def add_manual_if_ocr(self):
        self._arm_capture("if_ocr")

    def _arm_ocr_recapture(self, idx):
        """Chọn lại vùng quét OCR cho 1 bước ocr_text/if_ocr ĐÃ CÓ SẴN -
        dùng generic self.steps[idx]['action'] (giống _arm_image_recapture)
        để KHÔNG ép cứng về 'ocr_text' khi đang sửa 1 bước 'if_ocr'."""
        self._ocr_edit_idx = idx
        self._arm_capture(self.steps[idx].get("action", "ocr_text"))

    def _arm_region_recapture(self, idx):
        """Chọn (hoặc chọn lại) VÙNG QUÉT giới hạn cho 1 bước tìm ảnh
        (wait_image/if_image/multi_image) đã có sẵn. Khi đã đặt, mỗi lần
        quét chỉ so khớp TRONG vùng này thay vì toàn màn hình - nhanh hơn
        nhiều lần vì matchTemplate tốn CPU theo diện tích ảnh đem so khớp,
        mà vẫn GIỮ NGUYÊN độ phân giải gốc (không đánh đổi độ chính xác như
        cách thu nhỏ ảnh). Hữu ích khi đã biết trước icon/ảnh cần tìm luôn
        nằm trong 1 khu vực cố định (vd góc trên-phải, thanh dưới cùng...)."""
        self._region_edit_idx = idx
        self._arm_capture("image_region")

    def _clear_step_region(self, idx):
        """Bỏ vùng quét đã đặt cho 1 bước - trở lại quét TOÀN màn hình."""
        if 0 <= idx < len(self.steps):
            self.steps[idx].pop("region", None)
            self.refresh_tree()
            self.tree.selection_set(str(idx))
            self.on_step_selected()

    def add_manual_popup(self):
        msg = simpledialog.askstring(
            "Thêm Popup Thông Báo (hiện ĐÈ LÊN GAME)",
            "Nội dung thông báo. Dùng {tên_biến} để chèn giá trị 1 biến, vd:\n"
            "Kết quả: {ocr_text}"
        )
        if msg is None:
            return
        duration = simpledialog.askfloat(
            "Thời gian hiện",
            "Số giây tự tắt (0 = hiện tới khi bấm Đóng, kịch bản sẽ DỪNG chờ):",
            initialvalue=2.0, minvalue=0.0, maxvalue=60.0
        )
        if duration is None:
            duration = 2.0
        self._insert_step({
            "action": "show_popup", "message": msg, "duration": duration, "repeat": 1, "delay": 0.1,
            "comment": f"Thông báo ({'tự tắt ' + str(duration) + 's' if duration else 'chờ bấm Đóng'}): {msg}"
        })

    def add_if_else_group_template(self):
        """Chèn 1 khung có sẵn: IF (Biến) -> [Nhóm lặp nếu ĐÚNG] -> ELSE ->
        [Nhóm lặp nếu SAI] -> ENDIF. Engine đã hỗ trợ Group lồng bên trong
        nhánh IF/ELSE (chạy đệ quy qua execute_steps), chỉ là trước đây GUI
        chưa có cách chèn nhanh đúng cấu trúc lồng nhau này - người dùng phải
        tự ghép 7 bước thủ công theo đúng thứ tự, rất dễ sai. Sau khi chèn,
        chuột phải vào từng bước để: sửa điều kiện IF (Biến), đặt số lần lặp
        (hoặc lặp theo thời gian) cho từng Nhóm, và thêm hành động vào bên
        trong 2 Nhóm."""
        idx = self._get_insert_index()
        skeleton = [
            {"action": "if_var", "var": "a", "op": ">=", "value": 1, "repeat": 1, "delay": 0.1, "comment": "Điều kiện (bấm chuột phải để sửa)"},
            {"action": "group_start", "repeat": 1, "delay": 0.1, "comment": "Nhóm lặp nếu ĐÚNG"},
            {"action": "group_end", "repeat": 1, "delay": 0.1, "comment": ""},
            {"action": "else", "repeat": 1, "delay": 0.1, "comment": "Ngược lại"},
            {"action": "group_start", "repeat": 1, "delay": 0.1, "comment": "Nhóm lặp nếu SAI"},
            {"action": "group_end", "repeat": 1, "delay": 0.1, "comment": ""},
            {"action": "endif", "repeat": 1, "delay": 0.1, "comment": "Đóng IF"},
        ]
        self.steps[idx:idx] = skeleton
        self.refresh_tree()
        self.tree.selection_set(str(idx))
        messagebox.showinfo(
            "Đã chèn khung",
            "Đã chèn khung IF/ELSE với 2 Nhóm lặp sẵn (rỗng).\n\n"
            "- Chuột phải vào dòng [IF Biến] để sửa điều kiện thật.\n"
            "- Chọn dòng [GROUP] rồi thêm hành động NGAY SAU nó (chèn vào đúng vị trí).\n"
            "- Chuột phải vào [GROUP] để sửa số lần lặp hoặc lặp theo thời gian."
        )

    def add_group_block(self):
        sel = self.tree.selection()
        sel_indices = sorted(int(i) for i in sel) if sel else []
        group_name = simpledialog.askstring("Thêm Nhóm", "Nhập tên nhóm:") or "Nhóm lặp"

        raw_rep = simpledialog.askstring("Số lần lặp nhóm", "Nhập số lần lặp (vd: 999 hoặc 30s):", initialvalue="999") or "999"
        parsed_rep = self._parse_repeat_input(raw_rep) or {"repeat_mode": "count", "repeat": 999}

        start_step = {"action": "group_start", "delay": 0.1, "comment": group_name}
        start_step.update(parsed_rep)
        end_step = {"action": "group_end", "repeat": 1, "delay": 0.1, "comment": "Đóng nhóm"}

        if len(sel_indices) >= 2:
            start_i, end_i = sel_indices[0], sel_indices[-1]
            self.steps.insert(end_i + 1, end_step)
            self.steps.insert(start_i, start_step)
            self.refresh_tree()
            self.tree.selection_set(str(start_i))
            return

        idx = self._get_insert_index()
        self.steps.insert(idx, start_step)
        self.steps.insert(idx + 1, end_step)
        self.refresh_tree()
        self.tree.selection_set(str(idx))

    _VAR_OPS = ("==", "!=", ">", ">=", "<", "<=")

    @staticmethod
    def _parse_var_number(raw):
        raw = str(raw).strip()
        try:
            if "." in raw:
                return float(raw)
            return int(raw)
        except ValueError:
            return raw

    def _get_existing_variable_names(self):
        names = set()
        for s in self.steps:
            if s.get("var"):
                names.add(s["var"])
        return sorted(list(names)) if names else ["a"]

    def add_manual_set_var(self):
        existing = self._get_existing_variable_names()
        dlg = SetVarDialog(self.root, existing_vars=existing)
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        res = dlg.result
        self._insert_step({
            "action": "set_var",
            "var": res["var"],
            "value": res["value"],
            "repeat": 1,
            "delay": 0.1,
            "comment": f"Đặt biến {res['var']} = {res['value']}"
        })

    def add_manual_inc_var(self):
        existing = self._get_existing_variable_names()
        dlg = IncVarDialog(self.root, existing_vars=existing)
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        res = dlg.result
        self._insert_step({
            "action": "inc_var",
            "var": res["var"],
            "amount": res["amount"],
            "repeat": 1,
            "delay": 0.1,
            "comment": f"Biến {res['var']} {'+' if res['amount']>=0 else ''}{res['amount']}"
        })

    def add_if_var(self):
        existing = self._get_existing_variable_names()
        dlg = IfVarDialog(self.root, existing_vars=existing)
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        res = dlg.result
        step = {
            "action": "if_var",
            "var": res["var"],
            "op": res["op"],
            "value": res["value"],
            "repeat": 1,
            "delay": 0.1,
            "comment": f"Nếu {res['var']} {res['op']} {res['value']}"
        }
        self._insert_step(step)

    def add_if_group(self):
        """Thêm bước IF (Nhóm Điều Kiện) - cây AND/OR/NOT lồng nhau tuỳ ý,
        xem gui_dialogs_ifgroup.py::IfGroupDialog. Cần có ảnh xem trước
        (self.current_screen_cv) để dựng RegionPickerDialog bên trong -
        giống điều kiện các nút lá Ảnh/OCR cần "nhìn thấy màn hình" mới
        chọn được vùng/ảnh mẫu."""
        if self.current_screen_cv is None:
            messagebox.showwarning("Lưu ý", "Hãy chụp/kết nối màn hình trước (bấm Chụp Màn Hình) rồi mới thêm được IF Nhóm Điều Kiện!")
            return
        existing = self._get_existing_variable_names()
        dlg = IfGroupDialog(self.root, self.current_screen_cv, existing_vars=existing)
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        self._insert_step({
            "action": "if_group", "tree": dlg.result,
            "timeout": 3, "scan_interval": float(self.spin_all_scan.get() or 0.10),
            "repeat": 1, "delay": float(self.spin_default_delay.get() or 1.0),
            "comment": "IF Nhóm Điều Kiện",
        })

    def _arm_if_group_recapture(self, idx):
        """Sửa lại CÂY ĐIỀU KIỆN của 1 bước if_group ĐÃ CÓ SẴN - mở lại
        IfGroupDialog với cây hiện tại làm điểm bắt đầu (không mất công
        xây lại từ đầu, chỉ sửa/thêm/xoá nhánh cần thiết)."""
        if not (0 <= idx < len(self.steps)):
            return
        if self.current_screen_cv is None:
            messagebox.showwarning("Lưu ý", "Hãy chụp/kết nối màn hình trước rồi mới sửa được!")
            return
        step = self.steps[idx]
        existing = self._get_existing_variable_names()
        dlg = IfGroupDialog(self.root, self.current_screen_cv, initial_tree=step.get("tree"), existing_vars=existing)
        self.root.wait_window(dlg)
        if dlg.result:
            step["tree"] = dlg.result
            self.refresh_tree()
            self.tree.selection_set(str(idx))

    def open_data_group_manager(self):
        """Mở cửa sổ quản lý Nhóm Dữ Liệu (tạo/sửa/xoá danh sách text tuỳ ý
        dùng làm biến lặp trong kịch bản)."""
        DataGroupManagerDialog(self.root)

    def add_manual_next_data_item(self):
        existing = self._get_existing_variable_names()
        dlg = NextDataItemDialog(self.root, existing_vars=existing)
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        res = dlg.result
        self._insert_step({
            "action": "next_data_item",
            "group_id": res["group_id"],
            "var": res["var"],
            "wrap": res["wrap"],
            "repeat": 1,
            "delay": 0.1,
            "comment": f"Lấy dữ liệu từ Nhóm '{res['group_name']}' -> biến {res['var']}"
        })

    def add_break_group(self):
        self._insert_step({"action": "break_group", "repeat": 1, "delay": 0.1, "comment": "Dừng vòng lặp Nhóm"})

    def add_continue_group(self):
        self._insert_step({"action": "continue_group", "repeat": 1, "delay": 0.1, "comment": "Bỏ qua, lặp lại Nhóm"})

    def _parse_repeat_input(self, raw):
        raw = raw.strip().lower().replace(" ", "")
        if not raw:
            return None
        try:
            if raw.endswith("ms"):
                return {"repeat_mode": "time", "repeat_ms": max(1, float(raw[:-2]))}
            if raw.endswith("p") or raw.endswith("m"):
                return {"repeat_mode": "time", "repeat_ms": max(1, float(raw[:-1]) * 60000)}
            if raw.endswith("s"):
                return {"repeat_mode": "time", "repeat_ms": max(1, float(raw[:-1]) * 1000)}
            return {"repeat_mode": "count", "repeat": max(1, int(raw))}
        except ValueError:
            return None

    def _format_repeat_display(self, step):
        if step.get("repeat_mode") == "time":
            ms = step.get("repeat_ms", float(step.get("repeat_seconds", 0)) * 1000.0)
            if ms >= 60000 and ms % 60000 == 0:
                return f"{int(ms // 60000)}p"
            if ms >= 1000 and ms % 1000 == 0:
                return f"{int(ms // 1000)}s"
            return f"{int(ms)}ms"
        return str(step.get("repeat", 1))

    def add_manual_sleep(self):
        val = simpledialog.askfloat("Thêm Chờ", "Số giây cần chờ:", initialvalue=2.0, minvalue=0.1, maxvalue=300.0)
        if val is not None:
            self._insert_step({"action": "sleep", "repeat": 1, "delay": round(val, 2), "comment": f"Chờ {val}s"})


    def add_if_single_image(self):
        self._arm_capture("if_image")

    def add_if_multi_image(self):
        paths = filedialog.askopenfilenames(initialdir="templates", title="Chọn nhóm ảnh IF", filetypes=[("Images", "*.png;*.jpg")])
        if not paths:
            return
        filenames = [os.path.basename(p) for p in paths]
        scan = float(self.spin_all_scan.get() or 0.10)
        self._insert_step({"action": "if_image", "templates": filenames, "timeout": 3, "conf": 0.80, "scan_interval": scan, "repeat": 1, "delay": float(self.spin_default_delay.get() or 1.0), "comment": f"Nếu thấy bất kỳ ({len(filenames)} ảnh)"})

    def add_else_step(self):
        self._insert_step({"action": "else", "repeat": 1, "delay": 0.1, "comment": "Ngược lại"})

    def add_endif_step(self):
        self._insert_step({"action": "endif", "repeat": 1, "delay": 0.1, "comment": "Đóng IF"})

    def add_multi_image_step(self):
        paths = filedialog.askopenfilenames(initialdir="templates", title="Chọn nhiều ảnh quét song song", filetypes=[("Images", "*.png;*.jpg")])
        if not paths:
            return
        filenames = [os.path.basename(p) for p in paths]
        scan = float(self.spin_all_scan.get() or 0.10)
        self._insert_step({"action": "multi_image", "templates": filenames, "timeout": 8, "conf": 0.80, "scan_interval": scan, "click": True, "repeat": 1, "delay": float(self.spin_default_delay.get() or 1.0), "comment": f"Quét song song ({len(filenames)} ảnh)"})

    def add_manual_label(self):
        # Thêm 1 bước 'Nhãn (Label)' - điểm neo KHÔNG làm gì khi chạy tới,
        # chỉ dùng làm đích nhảy cho on_fail="skip_to_label" của các bước
        # Tìm & Click Ảnh / IF Ảnh phía trên (xem logic_engine.py).
        name = simpledialog.askstring("Thêm Nhãn (Label)", "Đặt tên cho nhãn này (dùng để on_fail=skip_to_label nhảy tới):")
        if name:
            name = name.strip()
            self._insert_step({"action": "label", "name": name, "repeat": 1, "delay": 0.0, "comment": f"🏷️ Nhãn: {name}"})


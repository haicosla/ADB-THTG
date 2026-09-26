"""
gui_steplist_ops.py — StepListOpsMixin: thao tác trên TOÀN BỘ danh sách
bước (chọn hết, áp dụng cài đặt ảnh hàng loạt, gộp/tách "Nhóm đã lưu",
xoá/di chuyển 1 bước, làm mới cây hiển thị, LƯU/MỞ file kịch bản .json,
và đăng ký kịch bản hiện tại vào Danh Mục Tác Vụ cho Dashboard).

Đây là 1 phần của class MacroStudioApp (xem gui.py), tách theo chức năng
như các Mixin dashboard_*.py - "self." trỏ vào cùng 1 instance
MacroStudioApp, KHÔNG đổi hành vi so với bản gộp 1 file trước đây.
""" 
import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

import task_registry
import paths
from gui_dialogs_data import RegisterTaskDialog
from logic_engine import LogicEngine


class StepListOpsMixin:

    def select_all_steps(self, event=None):
        items = self.tree.get_children()
        if items:
            self.tree.selection_set(items)
        return "break"

    def apply_batch_image_settings(self):
        try:
            new_timeout = int(self.spin_all_timeout.get())
            new_conf = round(float(self.spin_all_conf.get()), 2)
            new_scan = round(float(self.spin_all_scan.get()), 2)
            new_delay = round(float(self.spin_default_delay.get()), 2)
        except ValueError:
            messagebox.showerror("Lỗi", "Thông số không hợp lệ!")
            return
        count = 0
        for step in self.steps:
            if step.get("action") in ("wait_image", "if_image", "multi_image"):
                step["timeout"] = new_timeout
                step["conf"] = new_conf
                step["scan_interval"] = new_scan
                step["delay"] = new_delay
                count += 1
        self.refresh_tree()
        messagebox.showinfo("Thành công", f"Đã áp dụng cho {count} bước ảnh!")

    def check_ocr_setup_dialog(self):
        """Kiểm tra NHANH xem thư viện pytesseract + chương trình Tesseract-OCR
        đã sẵn sàng chưa, để chẩn đoán lý do bước Quét OCR không hoạt động mà
        không cần chạy thử cả kịch bản."""
        ok, msg = self.adb.check_ocr_setup()
        if ok:
            messagebox.showinfo("Kiểm Tra OCR", msg)
        else:
            messagebox.showerror("Kiểm Tra OCR - Chưa sẵn sàng", msg)

    def save_selection_as_group(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Lưu ý", "Hãy chọn các bước cần lưu nhóm!")
            return
        group_name = simpledialog.askstring("Lưu Nhóm", "Nhập tên nhóm:")
        if not group_name:
            return
        group_path = os.path.join("groups", f"{group_name.strip()}.json")
        group_steps = [self.steps[int(i)] for i in sorted([int(i) for i in selected])]
        # paths.save_json: ghi nguyên tử + tự sao lưu .bak trước khi đè -
        # trước đây dùng json.dump() thẳng, lỡ tay lưu ĐÈ nhầm nội dung là
        # mất bản Nhóm cũ vĩnh viễn, không có cách nào khôi phục lại.
        paths.save_json(group_path, group_steps)
        messagebox.showinfo("Thành công", f"Đã lưu nhóm '{group_name}'!")

    def insert_saved_group(self):
        path = filedialog.askopenfilename(initialdir="groups", title="Chọn nhóm thao tác", filetypes=[("JSON files", "*.json")])
        if not path:
            return
        group_name = os.path.splitext(os.path.basename(path))[0]
        self._insert_step({"action": "group", "group_file": os.path.basename(path), "repeat": 1, "delay": 1.0, "comment": f"Nhóm: [{group_name}]"})

    def expand_selected_group(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        step = self.steps[idx]
        if step.get("action") != "group":
            return
        g_path = os.path.join("groups", step.get("group_file", ""))
        if not os.path.exists(g_path):
            return
        with open(g_path, "r", encoding="utf-8") as f:
            sub_steps = json.load(f)
        self.steps[idx:idx + 1] = sub_steps
        self.refresh_tree()
        messagebox.showinfo("Thành công", f"Đã bung nhóm thành {len(sub_steps)} bước!")

    # Các loại bước "mở khối" có thể THU GỌN/MỞ RỘNG trên cây hiển thị (đi
    # kèm 1 bước "đóng khối" tương ứng: if_.../if_group -> endif,
    # group_start -> group_end) - xem _compute_block_ends()/refresh_tree().
    _BLOCK_OPEN_ACTIONS = ("if_image", "if_var", "if_ocr", "if_group", "group_start")

    def _compute_block_ends(self):
        """Ghép cặp mở/đóng khối IF (if_image/if_var/if_ocr/if_group ->
        endif) và Nhóm (group_start -> group_end) bằng 1 stack, HỖ TRỢ LỒNG
        NHAU (if trong if, nhóm trong nhóm...), trả về
        {idx_dòng_mở: idx_dòng_đóng}. Dùng để biết khoảng bước nào cần ẩn
        đi khi 1 khối đang được thu gọn."""
        ends = {}
        stack = []
        for idx, s in enumerate(self.steps):
            act = s.get("action")
            if act in ("if_image", "if_var", "if_ocr", "if_group"):
                stack.append(("if", idx))
            elif act == "endif":
                if stack and stack[-1][0] == "if":
                    ends[stack.pop()[1]] = idx
            elif act == "group_start":
                stack.append(("group", idx))
            elif act == "group_end":
                if stack and stack[-1][0] == "group":
                    ends[stack.pop()[1]] = idx
        return ends

    def toggle_block_collapse(self, idx):
        """Thu gọn (ẩn các bước con)/mở rộng lại 1 khối IF hoặc Nhóm trên
        cây hiển thị. CHỈ đổi cách HIỂN THỊ - self.steps (thứ tự/nội dung
        bước thật) không hề bị đụng tới, nên không ảnh hưởng gì tới chạy
        thử, di chuyển, kéo-thả, xoá, copy/paste... (các thao tác đó luôn
        làm việc trực tiếp trên self.steps, không phải trên các dòng đang
        ẩn/hiện trên cây)."""
        if idx in self._collapsed_headers:
            self._collapsed_headers.discard(idx)
        else:
            self._collapsed_headers.add(idx)
        self.refresh_tree()

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        block_ends = self._compute_block_ends()
        # Dọn các mục ĐÃ THU GỌN từ trước nhưng không còn khớp khối nào nữa
        # (vd người dùng vừa xoá/sửa làm mất cặp mở-đóng) để khỏi tồn đọng
        # vô ích trong bộ nhớ.
        self._collapsed_headers &= set(block_ends.keys())
        indent_level = 0
        skip_until = -1
        for idx, s in enumerate(self.steps):
            if idx <= skip_until:
                continue
            act = s.get("action")
            rep_str = self._format_repeat_display(s)
            conf_str = f"{s.get('conf', 0.80):.2f}" if act in ("wait_image", "if_image", "multi_image", "wait_vanish") else "-"
            tout_str = f"{s.get('timeout', 8)}s" if act in ("wait_image", "if_image", "multi_image", "wait_vanish") else "-"
            tag, indent_str = "tag_tap", "│   " * indent_level

            if act == "if_image":
                # wait_for="vanish" -> đổi nhãn hiển thị thành "IF Ảnh Biến
                # Mất" để phân biệt với kiểu mặc định "appear" (IF Ảnh -
                # chờ xuất hiện) ngay trên danh sách bước, không cần mở
                # bước ra mới biết - xem logic_engine.check_condition().
                label = "[IF Ảnh Biến Mất]" if s.get("wait_for") == "vanish" else "[IF Ảnh]"
                if not s.get("template") and not s.get("templates"):
                    detail = f"{indent_str}┌── {label} ⚠️ CHƯA CHỌN ẢNH ({s.get('comment', '')})"
                    tag = "tag_warn"
                else:
                    detail = f"{indent_str}┌── {label} {s.get('comment', '')}"
                    tag = "tag_logic"
                indent_level += 1
            elif act == "if_ocr":
                if not s.get("box"):
                    detail = f"{indent_str}┌── [IF OCR] ⚠️ CHƯA CHỌN VÙNG"
                    tag = "tag_warn"
                else:
                    detail = f"{indent_str}┌── [IF OCR] \"{s.get('text', '')}\" ({s.get('match', 'contains')})"
                    tag = "tag_logic"
                indent_level += 1
            elif act == "if_group":
                if not s.get("tree"):
                    detail = f"{indent_str}┌── [IF Nhóm Điều Kiện] ⚠️ CHƯA CẤU HÌNH"
                    tag = "tag_warn"
                else:
                    detail = f"{indent_str}┌── [IF Nhóm Điều Kiện] {LogicEngine._describe_condition_node(s['tree'])}"
                    tag = "tag_logic"
                indent_level += 1
            elif act == "else":
                detail = f"{indent_str}├── [ELSE]"
                tag = "tag_logic"
            elif act == "endif":
                indent_level = max(0, indent_level - 1)
                detail = f"{'│   ' * indent_level}└── [ENDIF]"
                tag = "tag_logic"
            elif act == "multi_image":
                detail = f"{indent_str}├── [OR] Quét đa ảnh"
                tag = "tag_multi"
            elif act == "wait_image":
                if not s.get("template"):
                    detail = f"{indent_str}├── ⚠️ CHƯA CHỌN ẢNH ({s.get('comment', '')})"
                    tag = "tag_warn"
                else:
                    detail = f"{indent_str}├── Ảnh: {s.get('template')} ({s.get('comment', '')})"
                    tag = "tag_image"
            elif act == "wait_vanish":
                if not s.get("template"):
                    detail = f"{indent_str}├── ⚠️ CHƯA CHỌN ẢNH ({s.get('comment', '')})"
                    tag = "tag_warn"
                else:
                    detail = f"{indent_str}├── 👻 Chờ biến mất: {s.get('template')} ({s.get('comment', '')})"
                    tag = "tag_image"
            elif act == "tap":
                if not s.get("pos"):
                    detail = f"{indent_str}├── ⚠️ CHƯA CHỌN TỌA ĐỘ ({s.get('comment', '')})"
                    tag = "tag_warn"
                else:
                    detail = f"{indent_str}├── Tap {s.get('pos')} ({s.get('comment', '')})"
                    tag = "tag_tap"
            elif act == "swipe":
                if not (s.get("from") and s.get("to")):
                    detail = f"{indent_str}├── ⚠️ CHƯA CHỌN ĐIỂM ĐẦU/CUỐI ({s.get('comment', '')})"
                    tag = "tag_warn"
                else:
                    hold_ms = s.get("hold_ms", 0)
                    detail = f"{indent_str}├── Swipe" + (f" (🐢 Giữ Cuối {hold_ms}ms)" if hold_ms else "")
                    tag = "tag_swipe"
            elif act == "zoom":
                if not s.get("center"):
                    detail = f"{indent_str}├── ⚠️ CHƯA CHỌN TÂM ZOOM ({s.get('comment', '')})"
                    tag = "tag_warn"
                else:
                    is_in = s.get("end_radius", 260) > s.get("start_radius", 70)
                    detail = f"{indent_str}├── 🔍 Zoom {'To' if is_in else 'Nhỏ'} ({s.get('duration', 400)}ms)"
                    tag = "tag_zoom"
            elif act == "swipe_path":
                n_pts = len(s.get("points") or [])
                if n_pts < 2:
                    detail = f"{indent_str}├── ⚠️ CHƯA CHỌN ĐỦ ĐIỂM ({s.get('comment', '')})"
                    tag = "tag_warn"
                else:
                    hold_ms = s.get("hold_ms", 0)
                    detail = f"{indent_str}├── 🧵 Vuốt {n_pts} điểm ({s.get('duration', 400)}ms)" + (f" (🐢 Giữ Cuối {hold_ms}ms)" if hold_ms else "")
                    tag = "tag_swipe"
            elif act == "sleep":
                detail = f"{indent_str}├── Chờ {s.get('delay')}s"
                tag = "tag_sleep"
            elif act == "type_text":
                detail = f"{indent_str}├── Gõ: \"{s.get('text', '')}\""
                tag = "tag_key"
            elif act == "key_combo":
                detail = f"{indent_str}├── Phím: {'+'.join(k.replace('KEYCODE_', '') for k in s.get('keys', []))}"
                tag = "tag_key"
            elif act == "group_start":
                detail = f"{indent_str}┌── [GROUP] {s.get('comment', '')} (Lặp {rep_str})"
                tag, indent_level = "tag_group", indent_level + 1
            elif act == "group_end":
                indent_level = max(0, indent_level - 1)
                detail = f"{'│   ' * indent_level}└── [Hết Nhóm]"
                tag = "tag_group"
            elif act == "group":
                detail = f"{indent_str}├── Nhóm: [{s.get('group_file')}]"
                tag = "tag_group"
            elif act == "set_var":
                detail = f"{indent_str}├── 🔢 [Biến] {s.get('var', '?')} = {s.get('value', 0)}"
                tag = "tag_var"
            elif act == "inc_var":
                amt = s.get("amount", 1)
                sign = "+" if (isinstance(amt, (int, float)) and amt >= 0) else ""
                detail = f"{indent_str}├── 🔢 [Biến] {s.get('var', '?')} {sign}{amt}"
                tag = "tag_var"
            elif act == "if_var":
                detail = f"{indent_str}┌── [IF Biến] {s.get('var', '?')} {s.get('op', '==')} {s.get('value', 0)}"
                tag, indent_level = "tag_logic", indent_level + 1
            elif act == "break_group":
                detail = f"{indent_str}├── ⛔ Dừng Vòng Lặp Nhóm"
                tag = "tag_var"
            elif act == "continue_group":
                detail = f"{indent_str}├── 🔁 Lặp Lại (Continue Nhóm)"
                tag = "tag_var"
            elif act == "ocr_text":
                detail = f"{indent_str}├── 🔤 OCR vùng -> biến {s.get('var', '?')}"
                tag = "tag_key"
            elif act == "next_data_item":
                detail = f"{indent_str}├── 🗂️ Lấy dữ liệu ({s.get('comment', '')}) -> biến {s.get('var', '?')}"
                tag = "tag_var"
            elif act == "show_popup":
                detail = f"{indent_str}├── 📢 Popup: \"{s.get('message', '')}\""
                tag = "tag_key"
            else:
                detail = f"{indent_str}├── {str(s)}"

            # Đánh dấu ⚡ ở đầu dòng cho bước nào đang BẬT Chế Độ Siêu Tốc
            # (turbo) - chỉ áp dụng cho 3 loại bước có tìm ảnh, để dễ nhận
            # ra ngay trong danh sách bước nào đang dùng đường tìm/click
            # nhanh riêng thay vì đường bình thường.
            if s.get("turbo") and act in ("wait_image", "if_image", "multi_image"):
                detail = f"⚡ {detail}"

            # Dòng MỞ 1 khối IF/Nhóm -> collapse_marker (▾/▸) hiện ở CỘT
            # RIÊNG (xem gui_ui_build.py) - KHÔNG gắn vào đầu chuỗi detail
            # nữa (trước đây gắn thẳng vào detail làm LỆCH hết đường kẻ
            # cây "┌──/│/└──", vì chỉ dòng mở khối bị đẩy thêm ký tự còn
            # dòng con bên dưới thì không). Nếu đang THU GỌN thì ẩn hẳn
            # các bước con (nhảy qua bằng skip_until), chỉ thêm dòng tóm
            # tắt số bước đang ẩn vào CUỐI chuỗi detail sẵn có.
            collapse_marker = ""
            if act in self._BLOCK_OPEN_ACTIONS and idx in block_ends:
                end_idx = block_ends[idx]
                hidden_n = end_idx - idx - 1
                if idx in self._collapsed_headers:
                    collapse_marker = "▸"
                    if hidden_n > 0:
                        detail = f"{detail}  … (đã thu gọn {hidden_n} bước bên trong)"
                    skip_until = end_idx - 1
                else:
                    collapse_marker = "▾"

            self.tree.insert("", "end", iid=str(idx),
                              values=(idx + 1, collapse_marker, act.upper(), detail, rep_str, conf_str, tout_str, s.get("delay", 1.0)),
                              tags=(tag,))

    def _select_step_row_for_run(self, idx):
        """Bôi đen đúng dòng thứ 'idx' trên cây trong lúc CHẠY THỬ - kể cả
        khi dòng đó đang bị ẨN bên trong 1 khối IF/Nhóm đang THU GỌN (tự
        MỞ RỘNG lại khối đó trước, thay vì bỏ qua/báo lỗi im lặng), để
        người xem luôn thấy đúng bước đang chạy thay vì tưởng chương trình
        bị "đứng" ở dòng đầu khối."""
        iid = str(idx)
        if iid not in self.tree.get_children(""):
            block_ends = self._compute_block_ends()
            changed = False
            for start, end in block_ends.items():
                if start in self._collapsed_headers and start < idx <= end:
                    self._collapsed_headers.discard(start)
                    changed = True
            if changed:
                self.refresh_tree()
        if iid in self.tree.get_children(""):
            self.tree.selection_set(iid)

    def move_step(self, direction):
        """Nút '▲ Lên' / '▼ Xuống': di chuyển TẤT CẢ các dòng đang bôi đen
        (không chỉ dòng đầu tiên như trước đây) lên/xuống 1 bậc, giữ nguyên
        thứ tự tương đối giữa chúng - giống kiểu di chuyển nhiều dòng trong
        Excel/File Explorer. Bôi đen nhiều dòng rồi bấm 1 cái là CẢ NHÓM
        cùng di chuyển, không phải bấm lặp lại cho từng dòng một."""
        sel = sorted(int(iid) for iid in self.tree.selection())
        if not sel:
            return
        if direction < 0:
            if sel[0] + direction < 0:
                return  # dòng đầu nhóm đã ở trên cùng, không thể lên nữa
            # Xử lý TỪ TRÊN XUỐNG khi đi LÊN: dòng phía trên nhóm phải được
            # "nhường chỗ" trước thì các dòng bên dưới trong nhóm mới hoán
            # đổi đúng, không bị dẫm lên nhau.
            for idx in sel:
                target = idx + direction
                self.steps[idx], self.steps[target] = self.steps[target], self.steps[idx]
        else:
            if sel[-1] + direction >= len(self.steps):
                return  # dòng cuối nhóm đã ở dưới cùng, không thể xuống nữa
            # Xử lý TỪ DƯỚI LÊN khi đi XUỐNG, lý do tương tự như trên.
            for idx in reversed(sel):
                target = idx + direction
                self.steps[idx], self.steps[target] = self.steps[target], self.steps[idx]
        self.refresh_tree()
        # Chỉ bôi đen lại những dòng THỰC SỰ còn hiện trên cây (phòng
        # trường hợp hiếm: dòng vừa dời tới lại rơi vào bên trong 1 khối
        # IF/Nhóm đang bị thu gọn nên không có mặt trên cây để chọn).
        visible = set(self.tree.get_children(""))
        new_sel = tuple(str(i + direction) for i in sel if str(i + direction) in visible)
        if new_sel:
            self.tree.selection_set(new_sel)

    def delete_selected_step(self):
        sel = self.tree.selection()
        if not sel:
            return
        for item_id in reversed(sorted([int(i) for i in sel])):
            del self.steps[item_id]
        self.refresh_tree()
        self._clear_inspector()

    def clear_all_steps(self):
        if messagebox.askyesno("Xác nhận", "Xóa toàn bộ kịch bản?"):
            self.steps = []
            self.refresh_tree()
            self._clear_inspector()

    def save_macro_file(self):
        path = filedialog.asksaveasfilename(
            initialdir="tasks", defaultextension=".json", filetypes=[("JSON files", "*.json")],
            initialfile=os.path.basename(self.current_macro_path) if self.current_macro_path else "tac_vu_moi.json"
        )
        if path:
            # paths.save_json: ghi nguyên tử + tự sao lưu .bak trước khi đè
            # - đây là file KỊCH BẢN THẬT (tasks/*.json), quan trọng nhất
            # trong toàn bộ dữ liệu người dùng - trước đây dùng json.dump()
            # thẳng, lỡ tay Lưu đè sai là MẤT SẠCH kịch bản cũ, không có
            # Undo, không có cách nào khôi phục lại.
            paths.save_json(path, self.steps)
            self.current_macro_path = path
            self._mark_saved()
            messagebox.showinfo("Thành công", "Đã lưu kịch bản!")

    def load_macro_file(self):
        path = filedialog.askopenfilename(initialdir="tasks", filetypes=[("JSON files", "*.json")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.steps = json.load(f)
            self.current_macro_path = path
            self._mark_saved()
            self.refresh_tree()

    def register_current_task(self):
        """Ghi kịch bản hiện tại vào Danh mục Tác Vụ (task_registry.json) để
        chương trình Auto Runner Dashboard đọc được. Nếu kịch bản chưa được
        lưu thành file lần nào, bắt lưu trước (Đăng Ký cần biết đường dẫn
        file cụ thể để Dashboard mở lại đúng lúc chạy)."""
        if not self.steps:
            messagebox.showwarning("Lưu ý", "Kịch bản đang trống, chưa có gì để đăng ký!")
            return

        if not self.current_macro_path:
            messagebox.showinfo("Cần lưu trước", "Hãy lưu kịch bản thành file JSON trước khi đăng ký!")
            self.save_macro_file()
            if not self.current_macro_path:
                return

        # Đảm bảo file trên đĩa khớp với danh sách bước đang hiển thị, tránh
        # trường hợp sửa thêm bước sau khi lưu rồi đăng ký nhầm bản cũ.
        # paths.save_json: ghi nguyên tử + tự sao lưu .bak (xem save_macro_file ở trên).
        try:
            paths.save_json(self.current_macro_path, self.steps)
            self._mark_saved()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không ghi được file kịch bản:\n{e}")
            return

        entries = task_registry.load_registry()
        task_id = task_registry.make_task_id(self.current_macro_path)
        existing = task_registry.find_task(entries, task_id)
        categories = task_registry.list_categories(entries)

        default_name = (existing or {}).get("ten_hien_thi") or os.path.splitext(os.path.basename(self.current_macro_path))[0].replace("_", " ").title()
        default_muc = (existing or {}).get("muc", "")
        default_enabled = (existing or {}).get("mac_dinh_bat", True)
        default_order = (existing or {}).get("thu_tu") or task_registry.next_order_in_category(entries, default_muc)

        dlg = RegisterTaskDialog(
            self.root, file_json=self.current_macro_path, existing_categories=categories,
            default_id=task_id, default_name=default_name, default_muc=default_muc,
            default_enabled=default_enabled, default_order=default_order
        )
        self.root.wait_window(dlg)
        if not dlg.result:
            return

        entry = dlg.result
        entry["file_json"] = self.current_macro_path.replace("\\", "/")
        task_registry.upsert_task(entries, entry)
        task_registry.save_registry(entries)

        messagebox.showinfo(
            "Đã đăng ký",
            f"Đã đăng ký tác vụ '{entry['ten_hien_thi']}' vào Mục '{entry['muc']}'.\n\n"
            f"Mở Auto Runner Dashboard (dashboard.py) và bấm 'Quét Lại Danh Mục' để thấy tác vụ này."
        )


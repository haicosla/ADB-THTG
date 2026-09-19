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
from gui_dialogs_data import RegisterTaskDialog


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
        except ValueError:
            messagebox.showerror("Lỗi", "Thông số không hợp lệ!")
            return
        count = 0
        for step in self.steps:
            if step.get("action") in ("wait_image", "if_image", "multi_image"):
                step["timeout"] = new_timeout
                step["conf"] = new_conf
                step["scan_interval"] = new_scan
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
        with open(group_path, "w", encoding="utf-8") as f:
            json.dump(group_steps, f, indent=2, ensure_ascii=False)
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

    def refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        indent_level = 0
        for idx, s in enumerate(self.steps):
            act = s.get("action")
            rep_str = self._format_repeat_display(s)
            conf_str = f"{s.get('conf', 0.80):.2f}" if act in ("wait_image", "if_image", "multi_image") else "-"
            tout_str = f"{s.get('timeout', 8)}s" if act in ("wait_image", "if_image", "multi_image") else "-"
            tag, indent_str = "tag_tap", "│   " * indent_level

            if act == "if_image":
                if not s.get("template") and not s.get("templates"):
                    detail = f"{indent_str}┌── [IF Ảnh] ⚠️ CHƯA CHỌN ẢNH ({s.get('comment', '')})"
                    tag = "tag_warn"
                else:
                    detail = f"{indent_str}┌── [IF Ảnh] {s.get('comment', '')}"
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

            self.tree.insert("", "end", iid=str(idx), values=(idx + 1, act.upper(), detail, rep_str, conf_str, tout_str, s.get("delay", 1.0)), tags=(tag,))

    def move_step(self, direction):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        target = idx + direction
        if 0 <= target < len(self.steps):
            self.steps[idx], self.steps[target] = self.steps[target], self.steps[idx]
            self.refresh_tree()
            self.tree.selection_set(str(target))

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
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.steps, f, indent=2, ensure_ascii=False)
            self.current_macro_path = path
            messagebox.showinfo("Thành công", "Đã lưu kịch bản!")

    def load_macro_file(self):
        path = filedialog.askopenfilename(initialdir="tasks", filetypes=[("JSON files", "*.json")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.steps = json.load(f)
            self.current_macro_path = path
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
        try:
            with open(self.current_macro_path, "w", encoding="utf-8") as f:
                json.dump(self.steps, f, indent=2, ensure_ascii=False)
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


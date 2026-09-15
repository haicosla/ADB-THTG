import os
import json
import time
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import cv2
from PIL import Image, ImageTk
from pynput import keyboard

from adb_helper import ADBHelper
from emulator_manager import EmulatorManager
from logic_engine import LogicEngine, BreakGroupSignal, ContinueGroupSignal
from window_finder import WindowFinder
from recorder import LiveRecorder, parse_key_combo_text
from step_list_controls import StepListController
import capture_tools
import task_registry
import data_groups


def _bind_esc_close(win):
    """Cho phép bấm phím ESC để đóng nhanh 1 cửa sổ popup (Toplevel), thay
    vì bắt buộc phải rê chuột tới nút X/Đóng."""
    win.bind("<Escape>", lambda e: win.destroy())


def parse_condition_string(raw_text):
    if not raw_text:
        return None, None, None
    text = raw_text.strip()
    match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)?\s*(==|!=|>=|<=|>|<)\s*(.*)$", text)
    if match:
        var_name, op, val_str = match.groups()
        val_str = val_str.strip()
        try:
            val = float(val_str) if "." in val_str else int(val_str)
        except ValueError:
            val = val_str
        return var_name, op, val
    return None, None, None


def parse_set_var_string(raw_text):
    if not raw_text:
        return None, None
    text = raw_text.strip()
    match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.*)$", text)
    if match:
        name, val_str = match.groups()
        val_str = val_str.strip()
        try:
            val = float(val_str) if "." in val_str else int(val_str)
        except ValueError:
            val = val_str
        return name, val
    return None, None


def parse_inc_var_string(raw_text):
    if not raw_text:
        return None, None
    text = raw_text.strip()
    match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*(\+=|-=|\+|-)\s*(.*)$", text)
    if match:
        name, sign, val_str = match.groups()
        try:
            val = float(val_str.strip())
            if "-" in sign:
                val = -val
            if val.is_integer():
                val = int(val)
            return name, val
        except ValueError:
            pass
    return None, None


class SetVarDialog(tk.Toplevel):
    def __init__(self, parent, existing_vars=None, initial_var="a", initial_val="0"):
        super().__init__(parent)
        self.title("Đặt Biến (Gán Giá Trị)")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        existing_vars = existing_vars or ["a"]
        pad = {"padx": 10, "pady": 5}

        ttk.Label(self, text="Nhập nhanh (vd: a = 0):", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        self.txt_quick = ttk.Entry(self, width=32)
        self.txt_quick.grid(row=1, column=0, columnspan=2, padx=10, pady=2, sticky="we")
        self.txt_quick.bind("<KeyRelease>", self._on_quick_type)

        ttk.Separator(self, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="we", padx=10, pady=8)

        ttk.Label(self, text="Tên biến:").grid(row=3, column=0, sticky="w", **pad)
        self.cbo_var = ttk.Combobox(self, values=existing_vars, width=18)
        self.cbo_var.set(initial_var)
        self.cbo_var.grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(self, text="Giá trị gán:").grid(row=4, column=0, sticky="w", **pad)
        self.txt_val = ttk.Entry(self, width=20)
        self.txt_val.insert(0, str(initial_val))
        self.txt_val.grid(row=4, column=1, sticky="w", **pad)

        f_btn = ttk.Frame(self)
        f_btn.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(f_btn, text="✔ Xác Nhận", command=self._on_confirm).pack(side="left", padx=6)
        ttk.Button(f_btn, text="✖ Hủy", command=self.destroy).pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._on_confirm())
        self.geometry(f"+{parent.winfo_rootx() + 150}+{parent.winfo_rooty() + 120}")
        self.txt_quick.focus_set()

    def _on_quick_type(self, event):
        name, val = parse_set_var_string(self.txt_quick.get())
        if name:
            self.cbo_var.set(name)
        if val is not None:
            self.txt_val.delete(0, tk.END)
            self.txt_val.insert(0, str(val))

    def _on_confirm(self):
        quick_raw = self.txt_quick.get().strip()
        if quick_raw:
            name, val = parse_set_var_string(quick_raw)
            if name and val is not None:
                self.result = {"var": name, "value": val}
                self.destroy()
                return

        name = self.cbo_var.get().strip()
        val_raw = self.txt_val.get().strip()
        if not name:
            messagebox.showerror("Lỗi", "Chưa nhập tên biến!", parent=self)
            return

        try:
            val = float(val_raw) if "." in val_raw else int(val_raw)
        except ValueError:
            val = val_raw

        self.result = {"var": name, "value": val}
        self.destroy()


class IncVarDialog(tk.Toplevel):
    def __init__(self, parent, existing_vars=None, initial_var="a", initial_amount=1):
        super().__init__(parent)
        self.title("Tăng / Giảm Biến")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        existing_vars = existing_vars or ["a"]
        pad = {"padx": 10, "pady": 5}

        ttk.Label(self, text="Nhập nhanh (vd: a + 1 hoặc a - 1):", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        self.txt_quick = ttk.Entry(self, width=32)
        self.txt_quick.grid(row=1, column=0, columnspan=2, padx=10, pady=2, sticky="we")
        self.txt_quick.bind("<KeyRelease>", self._on_quick_type)

        ttk.Separator(self, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="we", padx=10, pady=8)

        ttk.Label(self, text="Tên biến:").grid(row=3, column=0, sticky="w", **pad)
        self.cbo_var = ttk.Combobox(self, values=existing_vars, width=18)
        self.cbo_var.set(initial_var)
        self.cbo_var.grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(self, text="Số lượng thay đổi:").grid(row=4, column=0, sticky="w", **pad)
        self.txt_amt = ttk.Entry(self, width=20)
        self.txt_amt.insert(0, str(initial_amount))
        self.txt_amt.grid(row=4, column=1, sticky="w", **pad)

        f_btn = ttk.Frame(self)
        f_btn.grid(row=5, column=0, columnspan=2, pady=12)
        ttk.Button(f_btn, text="✔ Xác Nhận", command=self._on_confirm).pack(side="left", padx=6)
        ttk.Button(f_btn, text="✖ Hủy", command=self.destroy).pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._on_confirm())
        self.geometry(f"+{parent.winfo_rootx() + 150}+{parent.winfo_rooty() + 120}")
        self.txt_quick.focus_set()

    def _on_quick_type(self, event):
        name, amt = parse_inc_var_string(self.txt_quick.get())
        if name:
            self.cbo_var.set(name)
        if amt is not None:
            self.txt_amt.delete(0, tk.END)
            self.txt_amt.insert(0, str(amt))

    def _on_confirm(self):
        quick_raw = self.txt_quick.get().strip()
        if quick_raw:
            name, amt = parse_inc_var_string(quick_raw)
            if name and amt is not None:
                self.result = {"var": name, "amount": amt}
                self.destroy()
                return

        name = self.cbo_var.get().strip()
        amt_raw = self.txt_amt.get().strip()
        if not name:
            messagebox.showerror("Lỗi", "Chưa nhập tên biến!", parent=self)
            return

        try:
            amt = float(amt_raw)
            if amt.is_integer():
                amt = int(amt)
        except ValueError:
            messagebox.showerror("Lỗi", "Số lượng thay đổi phải là một số!", parent=self)
            return

        self.result = {"var": name, "amount": amt}
        self.destroy()


class IfVarDialog(tk.Toplevel):
    def __init__(self, parent, existing_vars=None, initial_var="a", initial_op=">=", initial_val="5"):
        super().__init__(parent)
        self.title("Cấu hình Điều Kiện IF (Biến)")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        existing_vars = existing_vars or ["a"]
        pad = {"padx": 10, "pady": 5}

        ttk.Label(self, text="Nhập nhanh (vd: a >= 5 hoặc >= 5 hoặc a < 5):", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        self.txt_quick = ttk.Entry(self, width=38)
        self.txt_quick.grid(row=1, column=0, columnspan=2, padx=10, pady=2, sticky="we")
        self.txt_quick.bind("<KeyRelease>", self._on_quick_type)

        ttk.Separator(self, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="we", padx=10, pady=8)

        ttk.Label(self, text="Tên biến:").grid(row=3, column=0, sticky="w", **pad)
        self.cbo_var = ttk.Combobox(self, values=existing_vars, width=22)
        self.cbo_var.set(initial_var)
        self.cbo_var.grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(self, text="Phép so sánh:").grid(row=4, column=0, sticky="w", **pad)
        self.cbo_op = ttk.Combobox(self, values=["==", "!=", ">", ">=", "<", "<="], state="readonly", width=10)
        self.cbo_op.set(initial_op)
        self.cbo_op.grid(row=4, column=1, sticky="w", **pad)

        ttk.Label(self, text="Giá trị so sánh:").grid(row=5, column=0, sticky="w", **pad)
        self.txt_val = ttk.Entry(self, width=24)
        self.txt_val.insert(0, str(initial_val))
        self.txt_val.grid(row=5, column=1, sticky="w", **pad)

        f_btn = ttk.Frame(self)
        f_btn.grid(row=6, column=0, columnspan=2, pady=12)
        ttk.Button(f_btn, text="✔ Xác Nhận", command=self._on_confirm).pack(side="left", padx=6)
        ttk.Button(f_btn, text="✖ Hủy", command=self.destroy).pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._on_confirm())
        self.geometry(f"+{parent.winfo_rootx() + 150}+{parent.winfo_rooty() + 120}")
        self.txt_quick.focus_set()

    def _on_quick_type(self, event):
        v, op, val = parse_condition_string(self.txt_quick.get())
        if op:
            self.cbo_op.set(op)
        if val is not None and str(val) != "":
            self.txt_val.delete(0, tk.END)
            self.txt_val.insert(0, str(val))
        if v:
            self.cbo_var.set(v)

    def _on_confirm(self):
        quick_raw = self.txt_quick.get().strip()
        if quick_raw:
            v, op, val = parse_condition_string(quick_raw)
            if op and val is not None:
                final_var = v or self.cbo_var.get().strip() or "a"
                self.result = {"var": final_var, "op": op, "value": val}
                self.destroy()
                return

        var_name = self.cbo_var.get().strip()
        op = self.cbo_op.get().strip()
        val_raw = self.txt_val.get().strip()

        if not var_name:
            messagebox.showerror("Lỗi", "Chưa nhập tên biến!", parent=self)
            return

        try:
            val = float(val_raw) if "." in val_raw else int(val_raw)
        except ValueError:
            val = val_raw

        self.result = {"var": var_name, "op": op, "value": val}
        self.destroy()


class DataGroupManagerDialog(tk.Toplevel):
    """Cửa sổ quản lý các NHÓM DỮ LIỆU (data_groups.json): tạo/sửa/xoá danh
    sách text tuỳ ý (vd id tài khoản 1..10) dùng làm biến lặp trong kịch
    bản (xem bước "➡️ Lấy Dữ Liệu (Nhóm)" - action next_data_item)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🗂️ Quản Lý Nhóm Dữ Liệu")
        self.geometry("640x420")
        self.transient(parent)
        self.grab_set()
        _bind_esc_close(self)

        self.entries = data_groups.load_groups()
        self.current_id = None

        f_main = ttk.Frame(self)
        f_main.pack(fill="both", expand=True, padx=10, pady=10)

        f_left = ttk.Frame(f_main)
        f_left.pack(side="left", fill="y", padx=(0, 10))
        ttk.Label(f_left, text="Các Nhóm Dữ Liệu:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.lst = tk.Listbox(f_left, width=26, height=18, exportselection=False)
        self.lst.pack(fill="y", expand=True, pady=4)
        self.lst.bind("<<ListboxSelect>>", self._on_select)

        f_left_btn = ttk.Frame(f_left)
        f_left_btn.pack(fill="x", pady=2)
        ttk.Button(f_left_btn, text="➕ Mới", command=self._on_new).pack(side="left", padx=2)
        ttk.Button(f_left_btn, text="🗑️ Xoá", command=self._on_delete).pack(side="left", padx=2)

        f_right = ttk.Frame(f_main)
        f_right.pack(side="left", fill="both", expand=True)
        ttk.Label(f_right, text="Tên nhóm:").pack(anchor="w")
        self.txt_name = ttk.Entry(f_right)
        self.txt_name.pack(fill="x", pady=(0, 8))

        ttk.Label(f_right, text="Danh sách phần tử (MỖI DÒNG 1 giá trị,\nthứ tự trên xuống = thứ tự lặp):").pack(anchor="w")
        f_items = ttk.Frame(f_right)
        f_items.pack(fill="both", expand=True, pady=4)
        self.txt_items = tk.Text(f_items, width=40, height=14, wrap="none")
        sb = ttk.Scrollbar(f_items, command=self.txt_items.yview)
        self.txt_items.configure(yscrollcommand=sb.set)
        self.txt_items.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")

        ttk.Button(f_right, text="💾 Lưu Nhóm Này", command=self._on_save).pack(anchor="e", pady=8)

        self._refresh_list()

    def _refresh_list(self, select_id=None):
        self.lst.delete(0, tk.END)
        for e in self.entries:
            n_items = len(e.get("items", []))
            self.lst.insert(tk.END, f"{e.get('ten', '(chưa đặt tên)')}  ({n_items})")
        if select_id:
            for i, e in enumerate(self.entries):
                if e.get("id") == select_id:
                    self.lst.selection_set(i)
                    self._load_entry(e)
                    break

    def _on_select(self, event=None):
        sel = self.lst.curselection()
        if not sel:
            return
        self._load_entry(self.entries[sel[0]])

    def _load_entry(self, e):
        self.current_id = e.get("id")
        self.txt_name.delete(0, tk.END)
        self.txt_name.insert(0, e.get("ten", ""))
        self.txt_items.delete("1.0", tk.END)
        self.txt_items.insert("1.0", data_groups.items_to_text(e.get("items", [])))

    def _on_new(self):
        self.current_id = None
        self.txt_name.delete(0, tk.END)
        self.txt_items.delete("1.0", tk.END)
        self.lst.selection_clear(0, tk.END)
        self.txt_name.focus_set()

    def _on_save(self):
        name = self.txt_name.get().strip()
        if not name:
            messagebox.showerror("Lỗi", "Chưa nhập tên Nhóm Dữ Liệu!", parent=self)
            return
        items = data_groups.items_from_text(self.txt_items.get("1.0", tk.END))
        if not items:
            messagebox.showerror("Lỗi", "Danh sách phần tử đang rỗng - mỗi dòng nhập 1 giá trị!", parent=self)
            return
        gid = self.current_id or data_groups.new_group_id()
        entry = {"id": gid, "ten": name, "items": items}
        data_groups.upsert_group(self.entries, entry)
        data_groups.save_groups(self.entries)
        self._refresh_list(select_id=gid)
        messagebox.showinfo("Đã lưu", f"Đã lưu Nhóm Dữ Liệu '{name}' ({len(items)} phần tử).", parent=self)

    def _on_delete(self):
        sel = self.lst.curselection()
        if not sel:
            return
        e = self.entries[sel[0]]
        if not messagebox.askyesno("Xác nhận", f"Xoá Nhóm Dữ Liệu '{e.get('ten')}'?", parent=self):
            return
        self.entries = data_groups.remove_group(self.entries, e.get("id"))
        data_groups.save_groups(self.entries)
        self._on_new()
        self._refresh_list()


class NextDataItemDialog(tk.Toplevel):
    """Cấu hình bước "➡️ Lấy Dữ Liệu (Nhóm)" (action next_data_item): chọn 1
    Nhóm Dữ Liệu đã tạo sẵn (xem DataGroupManagerDialog), đặt tên biến sẽ
    nhận giá trị, và có lặp lại từ đầu khi hết danh sách hay không."""

    def __init__(self, parent, existing_vars=None, initial_var="id"):
        super().__init__(parent)
        self.title("Lấy Dữ Liệu Từ Nhóm")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self.groups = data_groups.load_groups()
        existing_vars = existing_vars or [initial_var]
        pad = {"padx": 10, "pady": 5}

        if not self.groups:
            ttk.Label(
                self, text="Chưa có Nhóm Dữ Liệu nào.\nHãy bấm '🗂️ Nhóm Dữ Liệu' để tạo trước.",
                foreground="red", justify="left"
            ).grid(row=0, column=0, columnspan=2, padx=10, pady=10)
            ttk.Button(self, text="Đóng", command=self.destroy).grid(row=1, column=0, columnspan=2, pady=10)
            self.geometry(f"+{parent.winfo_rootx() + 150}+{parent.winfo_rooty() + 120}")
            return

        names = [f"{g.get('ten')} ({len(g.get('items', []))})" for g in self.groups]

        ttk.Label(self, text="Nhóm Dữ Liệu:").grid(row=0, column=0, sticky="w", **pad)
        self.cbo_group = ttk.Combobox(self, values=names, state="readonly", width=30)
        self.cbo_group.current(0)
        self.cbo_group.grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(self, text="Gán vào biến:").grid(row=1, column=0, sticky="w", **pad)
        self.cbo_var = ttk.Combobox(self, values=existing_vars, width=18)
        self.cbo_var.set(initial_var)
        self.cbo_var.grid(row=1, column=1, sticky="w", **pad)

        self.var_wrap = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self, text="Hết danh sách thì quay lại từ đầu (wrap)", variable=self.var_wrap
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 5))

        ttk.Label(
            self,
            text="Mẹo: đặt bước này ở ĐẦU 1 khối GROUP lặp N lần\n"
                 "(N = số phần tử) để mỗi lượt lặp tự đổi sang giá trị tiếp theo.",
            foreground="#555", justify="left"
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 8))

        f_btn = ttk.Frame(self)
        f_btn.grid(row=4, column=0, columnspan=2, pady=8)
        ttk.Button(f_btn, text="✔ Xác Nhận", command=self._on_confirm).pack(side="left", padx=6)
        ttk.Button(f_btn, text="✖ Hủy", command=self.destroy).pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._on_confirm())
        self.geometry(f"+{parent.winfo_rootx() + 150}+{parent.winfo_rooty() + 120}")

    def _on_confirm(self):
        idx = self.cbo_group.current()
        if idx < 0:
            return
        group = self.groups[idx]
        var_name = self.cbo_var.get().strip()
        if not var_name:
            messagebox.showerror("Lỗi", "Chưa nhập tên biến!", parent=self)
            return
        self.result = {
            "group_id": group.get("id"),
            "group_name": group.get("ten"),
            "var": var_name,
            "wrap": bool(self.var_wrap.get()),
        }
        self.destroy()


class RegisterTaskDialog(tk.Toplevel):
    """Hộp thoại 'Đăng Ký Tác Vụ' - ghi kịch bản hiện tại (đã lưu thành file
    JSON trong tasks/) vào Danh mục Tác Vụ (task_registry.json) để chương
    trình Auto Runner Dashboard đọc được và hiện thành 1 dòng checklist."""

    def __init__(self, parent, file_json, existing_categories, default_id, default_name,
                 default_muc="", default_enabled=True, default_order=1):
        super().__init__(parent)
        self.title("Đăng Ký Tác Vụ Vào Danh Mục")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        pad = {"padx": 10, "pady": 5}

        ttk.Label(self, text=f"File kịch bản: {file_json}", font=("Segoe UI", 9, "italic")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))

        ttk.Label(self, text="Tên hiển thị:").grid(row=1, column=0, sticky="w", **pad)
        self.txt_name = ttk.Entry(self, width=38)
        self.txt_name.insert(0, default_name)
        self.txt_name.grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(self, text="Mục (nhóm):").grid(row=2, column=0, sticky="w", **pad)
        self.cbo_muc = ttk.Combobox(self, values=existing_categories, width=35)
        self.cbo_muc.set(default_muc)
        self.cbo_muc.grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(self, text="Thứ tự trong Mục:").grid(row=3, column=0, sticky="w", **pad)
        self.spin_order = ttk.Spinbox(self, from_=1, to=999, width=8)
        self.spin_order.set(default_order)
        self.spin_order.grid(row=3, column=1, sticky="w", **pad)

        self.var_enabled = tk.BooleanVar(value=default_enabled)
        ttk.Checkbutton(self, text="Bật mặc định trên Dashboard", variable=self.var_enabled).grid(
            row=4, column=0, columnspan=2, sticky="w", padx=10, pady=2)

        ttk.Label(self, text=f"ID tác vụ (tự sinh từ tên file): {default_id}",
                  foreground="#757575", font=("Segoe UI", 8)).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 8))

        f_btn = ttk.Frame(self)
        f_btn.grid(row=6, column=0, columnspan=2, pady=12)
        ttk.Button(f_btn, text="✔ Đăng Ký", command=self._on_confirm).pack(side="left", padx=6)
        ttk.Button(f_btn, text="✖ Hủy", command=self.destroy).pack(side="left", padx=6)

        self.default_id = default_id
        self.bind("<Return>", lambda e: self._on_confirm())
        self.geometry(f"+{parent.winfo_rootx() + 150}+{parent.winfo_rooty() + 120}")
        self.txt_name.focus_set()
        self.txt_name.select_range(0, tk.END)

    def _on_confirm(self):
        name = self.txt_name.get().strip()
        muc = self.cbo_muc.get().strip() or "Chưa phân loại"
        if not name:
            messagebox.showerror("Lỗi", "Chưa nhập Tên hiển thị!", parent=self)
            return
        try:
            order = int(self.spin_order.get())
        except ValueError:
            order = 1

        self.result = {
            "id": self.default_id,
            "ten_hien_thi": name,
            "muc": muc,
            "thu_tu": order,
            "mac_dinh_bat": self.var_enabled.get(),
        }
        self.destroy()


class MacroStudioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LD Macro Studio - Modular Edition")
        
        self.config_path = "config.json"
        cfg = self._load_config()
        self.root.geometry(cfg.get("geometry", "1440x920"))

        self.adb = ADBHelper()
        self.window_finder = WindowFinder(self.adb)
        # LỖI ĐÃ TÌM RA: đổi giả lập ở ô "Thiết bị" chỉ đổi được lệnh ADB
        # (nên Preview đổi đúng) nhưng KHÔNG hề đổi cửa sổ đang gắn để ghi F7
        # - window_finder.find_ld_windows() quét MÙ, luôn bắt cửa sổ LDPlayer
        # ĐẦU TIÊN tìm thấy trên toàn hệ thống bất kể đang chọn giả lập nào,
        # nên khi mở NHIỀU giả lập cùng lúc, F7 luôn ghi vào ĐÚNG 1 giả lập
        # cố định (thường là giả lập mở đầu tiên) dù đã đổi ô chọn - đúng
        # như hiện tượng người dùng phát hiện ra ("tên giả lập bên cạnh
        # không đổi"). Nay dùng EmulatorManager (qua ldconsole list2) để biết
        # CHÍNH XÁC hwnd cửa sổ ứng với TỪNG serial ADB, rồi gọi
        # window_finder.attach_hwnd() thẳng vào đúng cửa sổ đó mỗi khi đổi
        # giả lập - không còn đoán mò nữa.
        self.emulator_manager = EmulatorManager(self.adb)
        self._device_hwnd_map = {}  # serial ADB -> EmulatorInfo (có .hwnd, .name)

        self.steps = []
        self.current_screen_cv = None
        # Đường dẫn file JSON đã Lưu/Nạp gần nhất - dùng cho nút "Đăng Ký Tác
        # Vụ" (cần biết tác vụ hiện tại tương ứng file nào trong tasks/).
        self.current_macro_path = None

        self.preview_scale = 1.0
        self.preview_w = 400
        self.preview_h = 600

        self.is_streaming_active = False
        self.frame_lock = threading.Lock()
        self.new_frame_ready = False

        self.is_recording_live = False
        self.recorder = LiveRecorder(
            coord_mapper=self.window_finder.win_coords_to_norm,
            on_step_captured=self._on_recorder_step_captured,
            focus_checker=self.window_finder.is_ld_focused
        )

        self.preview_action_mode = tk.StringVar(value="crop_and_tap")
        self.drag_start = None
        self.rect_id = None
        self.pending_action = None
        self._ocr_edit_idx = None
        self._region_edit_idx = None

        self.is_playing = False
        self.stop_flag = False

        os.makedirs("templates", exist_ok=True)
        os.makedirs("tasks", exist_ok=True)
        os.makedirs("groups", exist_ok=True)
        os.makedirs("logs", exist_ok=True)

        self._setup_styles()
        self._build_ui()
        
        sash_pos = cfg.get("sash_pos", None)
        sash_pos_v = cfg.get("sash_pos_v", None)
        if sash_pos or sash_pos_v:
            self.root.after(200, lambda: self._restore_sash(sash_pos, sash_pos_v))
        else:
            self.root.after(400, self._apply_default_preview_width)

        self.root.update()

        min_w = max(1100, self.root.winfo_reqwidth())
        min_h = max(700, self.root.winfo_reqheight())
        self.root.minsize(min_w, min_h)

        self.refresh_all()

        self.step_list_ctrl = StepListController(
            tree=self.tree,
            get_steps=lambda: self.steps,
            on_changed=self._on_step_list_changed,
            on_edit_step=self.open_step_edit_menu_at
        )

        self.engine = LogicEngine(
            self.adb,
            stop_checker=lambda: self.stop_flag,
            step_notifier=lambda idx: self.root.after(0, lambda: self.tree.selection_set(str(idx))),
            popup_notifier=self._show_ingame_popup,
            logger=self._log_run
        )

        self.stream_thread = threading.Thread(target=self._stream_capture_worker, daemon=True)
        self.stream_thread.start()
        self._render_poll_loop()
        self._start_global_hotkeys()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_config(self):
        try:
            cfg = {
                "geometry": self.root.geometry(),
                "sash_pos": self.paned.sashpos(0),
                "sash_pos_v": self.vpaned.sashpos(0)
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def _restore_sash(self, pos, pos_v=None):
        try:
            self.root.update_idletasks()
            if pos:
                self.paned.sashpos(0, int(pos))
            if pos_v:
                self.vpaned.sashpos(0, int(pos_v))
        except Exception:
            pass

    def on_close(self):
        self._save_config()
        self.root.destroy()

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Treeview", font=("Consolas", 9), rowheight=24)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        self.style.map("Treeview", background=[("selected", "#1976D2")], foreground=[("selected", "#FFFFFF")])

    def _build_ui(self):
        f_top = ttk.Frame(self.root)
        f_top.pack(fill="x", padx=10, pady=4)

        ttk.Label(f_top, text="Thiết bị:").pack(side="left", padx=4)
        self.cbo_dev = ttk.Combobox(f_top, state="readonly", width=14)
        self.cbo_dev.pack(side="left", padx=2)
        self.cbo_dev.bind("<<ComboboxSelected>>", self.on_select_device)

        self.lbl_ld_status = ttk.Label(f_top, text="LD: Chưa tìm thấy", foreground="red", font=("Segoe UI", 9, "bold"))
        self.lbl_ld_status.pack(side="left", padx=4)

        self.lbl_keycombo_warn = ttk.Label(f_top, text="", font=("Segoe UI", 8, "bold"))
        self.lbl_keycombo_warn.pack(side="left", padx=6)

        ttk.Button(f_top, text="Quét lại", command=self.refresh_all).pack(side="left", padx=2)
        ttk.Button(f_top, text="🔄 Chụp mới", command=self.capture_and_show).pack(side="left", padx=2)

        self.btn_toggle_stream = tk.Button(
            f_top, text="▶ LIVE", bg="#455A64", fg="white",
            font=("Segoe UI", 9, "bold"), relief="raised", padx=6, pady=2,
            command=self.toggle_live_stream
        )
        self.btn_toggle_stream.pack(side="left", padx=4)

        f_crop_cfg = ttk.LabelFrame(f_top, text=" Cắt ")
        f_crop_cfg.pack(side="left", padx=4)
        ttk.Label(f_crop_cfg, text="R:").pack(side="left", padx=1)
        self.spin_w = ttk.Spinbox(f_crop_cfg, from_=20, to=500, width=4)
        self.spin_w.set(100)
        self.spin_w.pack(side="left", padx=1)
        ttk.Label(f_crop_cfg, text="C:").pack(side="left", padx=1)
        self.spin_h = ttk.Spinbox(f_crop_cfg, from_=20, to=500, width=4)
        self.spin_h.set(100)
        self.spin_h.pack(side="left", padx=1)

        self.cbo_preset = ttk.Combobox(f_crop_cfg, values=["60x60", "80x80", "100x100", "120x120", "150x80"], state="readonly", width=6)
        self.cbo_preset.set("100x100")
        self.cbo_preset.pack(side="left", padx=2)
        self.cbo_preset.bind("<<ComboboxSelected>>", self.on_preset_change)

        self.btn_live_record = tk.Button(
            f_top, text="● GHI LD (F7)", bg="#2E7D32", fg="white",
            font=("Segoe UI", 9, "bold"), relief="raised", padx=8, pady=2,
            command=self.toggle_live_record
        )
        self.btn_live_record.pack(side="right", padx=4)

        self.lbl_fps = ttk.Label(f_top, text="FPS: OFF", foreground="gray", font=("Segoe UI", 9, "bold"))
        self.lbl_fps.pack(side="right", padx=4)

        f_batch = ttk.LabelFrame(self.root, text=" Cài đặt thông số ảnh hàng loạt & mặc định ")
        f_batch.pack(fill="x", padx=10, pady=2)

        ttk.Label(f_batch, text="Timeout (s):").pack(side="left", padx=4)
        self.spin_all_timeout = ttk.Spinbox(f_batch, from_=1, to=120, width=4)
        self.spin_all_timeout.set(8)
        self.spin_all_timeout.pack(side="left", padx=2)

        ttk.Label(f_batch, text="Độ khớp:").pack(side="left", padx=6)
        self.spin_all_conf = ttk.Spinbox(f_batch, from_=0.5, to=0.99, increment=0.05, width=5)
        self.spin_all_conf.set(0.80)
        self.spin_all_conf.pack(side="left", padx=2)

        ttk.Label(f_batch, text="Tốc độ quét (s):").pack(side="left", padx=6)
        self.spin_all_scan = ttk.Spinbox(f_batch, from_=0.02, to=2.0, increment=0.02, width=5)
        self.spin_all_scan.set(0.10)
        self.spin_all_scan.pack(side="left", padx=2)

        ttk.Button(f_batch, text="⚡ ÁP DỤNG CHO TẤT CẢ BƯỚC ẢNH", command=self.apply_batch_image_settings).pack(side="left", padx=8)

        ttk.Separator(f_batch, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)
        ttk.Button(f_batch, text="🔍 Kiểm Tra OCR", command=self.check_ocr_setup_dialog).pack(side="left", padx=4)

        self.vpaned = ttk.PanedWindow(self.root, orient="vertical")
        self.vpaned.pack(fill="both", expand=True, padx=10, pady=5)

        self.paned = ttk.PanedWindow(self.vpaned, orient="horizontal")
        self.vpaned.add(self.paned, weight=6)

        f_left = ttk.LabelFrame(self.paned, text=" Màn Hình Preview ")
        self.paned.add(f_left, weight=3)

        f_modes = ttk.Frame(f_left)
        f_modes.pack(fill="x", padx=5, pady=2)
        ttk.Radiobutton(f_modes, text="📸 Cắt + Chạm", variable=self.preview_action_mode, value="crop_and_tap").pack(side="left", padx=2)
        ttk.Radiobutton(f_modes, text="📍 Chạm", variable=self.preview_action_mode, value="tap_only").pack(side="left", padx=2)
        ttk.Radiobutton(f_modes, text="✂️ Cắt mẫu", variable=self.preview_action_mode, value="crop_only").pack(side="left", padx=2)

        self.lbl_capture_hint = ttk.Label(f_modes, text="", foreground="#B71C1C", font=("Segoe UI", 9, "bold"))
        self.lbl_capture_hint.pack(side="left", padx=4)
        self.btn_cancel_capture = ttk.Button(f_modes, text="✖ Hủy", width=5, command=self._cancel_pending_action)
        self.btn_cancel_capture.pack(side="left", padx=2)
        self.btn_cancel_capture.pack_forget()

        self.canvas = tk.Canvas(f_left, bg="#181818", cursor="crosshair")
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        f_right_container = ttk.Frame(self.paned)
        self.paned.add(f_right_container, weight=5)

        f_group_bar = ttk.Frame(f_right_container)
        f_group_bar.pack(fill="x", padx=5, pady=2)
        
        f_group_btns = ttk.Frame(f_group_bar)
        f_group_btns.pack(fill="x", anchor="w")
        ttk.Button(f_group_btns, text="☑️ Chọn tất cả", command=self.select_all_steps).pack(side="left", padx=2, pady=2)
        ttk.Button(f_group_btns, text="📦 Lưu Nhóm", command=self.save_selection_as_group).pack(side="left", padx=2, pady=2)
        ttk.Button(f_group_btns, text="📂 Chèn Nhóm...", command=self.insert_saved_group).pack(side="left", padx=2, pady=2)
        ttk.Button(f_group_btns, text="🔓 Bung Nhóm", command=self.expand_selected_group).pack(side="left", padx=2, pady=2)

        ttk.Label(f_group_bar, text="(Kéo-thả sắp xếp • Chuột phải vào hành động để sửa thông số / vào ô trống để thêm nhanh)",
                  foreground="#546E7A", font=("Segoe UI", 8, "italic")).pack(anchor="w", padx=2, pady=1)

        f_manual = ttk.LabelFrame(f_right_container, text=" Thêm Bước Thủ Công & Logic Vào Vị Trí Chọn ")
        f_manual.pack(fill="x", padx=5, pady=2)

        f_manual_sub1 = ttk.Frame(f_manual)
        f_manual_sub1.pack(fill="x", padx=2, pady=2)
        ttk.Button(f_manual_sub1, text="➕ Tìm & Click Ảnh", command=self.add_manual_wait_image).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="➕ Click Tọa Độ", command=self.add_manual_tap).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="➕ Vuốt (Swipe)", command=self.add_manual_swipe).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="⏳ Chờ (Sleep)", command=self.add_manual_sleep).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="⌨️ Gõ Chữ", command=self.add_manual_type_text).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="⌨️ Tổ Hợp Phím", command=self.add_manual_key_combo).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="🔤 Quét OCR", command=self.add_manual_ocr).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="📢 Popup Thông Báo", command=self.add_manual_popup).pack(side="left", padx=2)

        f_manual_sub2 = ttk.Frame(f_manual)
        f_manual_sub2.pack(fill="x", padx=2, pady=2)
        ttk.Button(f_manual_sub2, text="🔀 IF (1 Ảnh)", command=self.add_if_single_image).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="🔀 IF (Nhóm Ảnh)", command=self.add_if_multi_image).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="↪️ ELSE", command=self.add_else_step).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="⏹️ ENDIF", command=self.add_endif_step).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="🖼️ Quét Đa Ảnh (OR)", command=self.add_multi_image_step).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="📦+ Gộp Nhóm Đã Chọn", command=self.add_group_block).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="🔁 Khung IF/ELSE (2 Nhóm Lặp)", command=self.add_if_else_group_template).pack(side="left", padx=2)

        f_vars = ttk.LabelFrame(f_right_container, text=" Biến Số & Điều Kiện Nâng Cao ")
        f_vars.pack(fill="x", padx=5, pady=2)

        f_vars_sub = ttk.Frame(f_vars)
        f_vars_sub.pack(fill="x", padx=2, pady=2)
        ttk.Button(f_vars_sub, text="🔢 Đặt Biến", command=self.add_manual_set_var).pack(side="left", padx=2)
        ttk.Button(f_vars_sub, text="🔢 Tăng/Giảm Biến", command=self.add_manual_inc_var).pack(side="left", padx=2)
        ttk.Button(f_vars_sub, text="🔀 IF (Biến)", command=self.add_if_var).pack(side="left", padx=2)
        ttk.Button(f_vars_sub, text="🗂️ Nhóm Dữ Liệu", command=self.open_data_group_manager).pack(side="left", padx=2)
        ttk.Button(f_vars_sub, text="➡️ Lấy Dữ Liệu (Nhóm)", command=self.add_manual_next_data_item).pack(side="left", padx=2)
        ttk.Button(f_vars_sub, text="🔁 Lặp Lại (Continue)", command=self.add_continue_group).pack(side="left", padx=2)
        ttk.Button(f_vars_sub, text="⛔ Dừng Vòng Lặp Nhóm", command=self.add_break_group).pack(side="left", padx=2)

        f_nav = ttk.Frame(f_right_container)
        f_nav.pack(fill="x", padx=5, pady=2)
        ttk.Button(f_nav, text="▲ Lên", command=lambda: self.move_step(-1)).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(f_nav, text="▼ Xuống", command=lambda: self.move_step(1)).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(f_nav, text="❌ Xóa bước (Del)", command=self.delete_selected_step).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(f_nav, text="Clear", command=self.clear_all_steps).pack(side="left", expand=True, fill="x", padx=1)

        f_tree_and_inspector = ttk.Frame(f_right_container)
        f_tree_and_inspector.pack(fill="both", expand=True, padx=5, pady=2)

        cols = ("idx", "type", "detail", "repeat", "conf", "timeout", "delay")
        self.tree = ttk.Treeview(f_tree_and_inspector, columns=cols, show="headings", height=14, selectmode="extended")
        self.tree.heading("idx", text="#")
        self.tree.heading("type", text="Loại")
        self.tree.heading("detail", text="Cấu trúc quy trình (Click chuột phải để sửa)")
        self.tree.heading("repeat", text="Lặp")
        self.tree.heading("conf", text="Độ khớp")
        self.tree.heading("timeout", text="Timeout(s)")
        self.tree.heading("delay", text="Delay(s)")

        self.tree.column("idx", width=35, anchor="center")
        self.tree.column("type", width=95, anchor="center")
        self.tree.column("detail", width=250)
        self.tree.column("repeat", width=55, anchor="center")
        self.tree.column("conf", width=60, anchor="center")
        self.tree.column("timeout", width=65, anchor="center")
        self.tree.column("delay", width=60, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<Double-1>", lambda e: self.open_step_edit_menu_at(self.tree.selection()[0] if self.tree.selection() else None, e.x_root, e.y_root))
        self.tree.bind("<<TreeviewSelect>>", self.on_step_selected)
        self.tree.bind("<Delete>", lambda e: self.delete_selected_step())

        self.f_inspector = ttk.LabelFrame(f_tree_and_inspector, text=" Ảnh Mẫu ", width=220)
        self.f_inspector.pack(side="right", fill="y", padx=5)
        self.f_inspector.pack_propagate(False)

        self.lbl_inspect_img = tk.Label(self.f_inspector, text="Chưa chọn ảnh", bg="#212121", fg="gray")
        self.lbl_inspect_img.pack(padx=5, pady=5, fill="both", expand=True)
        self.lbl_inspect_img.bind("<Double-1>", self.open_large_inspect_image)
        self._inspect_resize_job = None
        self.lbl_inspect_img.bind("<Configure>", self._on_inspect_label_resize)

        self.lbl_inspect_info = ttk.Label(self.f_inspector, text="", font=("Segoe UI", 8))
        self.lbl_inspect_info.pack(padx=5, pady=2)

        self.btn_change_img = ttk.Button(self.f_inspector, text="🔄 Đổi Ảnh Khác", state="disabled", command=self.change_step_image)
        self.btn_change_img.pack(padx=5, pady=3, fill="x")

        self.tree.tag_configure("tag_image", background="#E3F2FD", foreground="#0D47A1")
        self.tree.tag_configure("tag_tap", background="#E8F5E9", foreground="#1B5E20")
        self.tree.tag_configure("tag_swipe", background="#FFF8E1", foreground="#B78103")
        self.tree.tag_configure("tag_group", background="#F3E5F5", foreground="#4A148C")
        self.tree.tag_configure("tag_logic", background="#FBE9E7", foreground="#BF360C")
        self.tree.tag_configure("tag_multi", background="#E0F2F1", foreground="#004D40")
        self.tree.tag_configure("tag_sleep", background="#ECEFF1", foreground="#37474F")
        self.tree.tag_configure("tag_key", background="#FFF3E0", foreground="#E65100")
        self.tree.tag_configure("tag_var", background="#FFFDE7", foreground="#F57F17")

        f_legend = ttk.Frame(f_right_container)
        f_legend.pack(fill="x", padx=5, pady=2)
        tk.Label(f_legend, text="■ Ảnh", bg="#E3F2FD", fg="#0D47A1", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Đa Ảnh", bg="#E0F2F1", fg="#004D40", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Tap", bg="#E8F5E9", fg="#1B5E20", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Swipe", bg="#FFF8E1", fg="#B78103", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Phím", bg="#FFF3E0", fg="#E65100", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Biến", bg="#FFFDE7", fg="#F57F17", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Logic", bg="#FBE9E7", fg="#BF360C", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Group", bg="#F3E5F5", fg="#4A148C", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)

        # --- Nhật Ký Chạy (Run Log): ghi lại từng hành động đã thực hiện,
        # tìm thấy ảnh hay không, biến thay đổi ra sao, kết quả OCR, và lỗi
        # gì xảy ra khi CHẠY THỬ kịch bản. Đặt trong 1 pane riêng (kéo được
        # để chỉnh cao/thấp, kích thước cũng được lưu lại như khung khác).
        f_log = ttk.LabelFrame(self.vpaned, text=" 📜 Nhật Ký Chạy (Run Log) ")
        self.vpaned.add(f_log, weight=2)

        f_log_toolbar = ttk.Frame(f_log)
        f_log_toolbar.pack(fill="x", padx=4, pady=(4, 0))
        ttk.Button(f_log_toolbar, text="🗑️ Xóa Log", command=self._clear_run_log).pack(side="left", padx=2)
        ttk.Button(f_log_toolbar, text="💾 Lưu Log Ra File...", command=self._save_run_log_to_file).pack(side="left", padx=2)
        self.var_log_autoscroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(f_log_toolbar, text="Tự cuộn xuống", variable=self.var_log_autoscroll).pack(side="left", padx=8)
        ttk.Label(f_log_toolbar, text="   ■ Info  ", foreground="#37474F", font=("Segoe UI", 8, "bold")).pack(side="left")
        ttk.Label(f_log_toolbar, text="■ Thành công  ", foreground="#1B5E20", font=("Segoe UI", 8, "bold")).pack(side="left")
        ttk.Label(f_log_toolbar, text="■ Cảnh báo  ", foreground="#E65100", font=("Segoe UI", 8, "bold")).pack(side="left")
        ttk.Label(f_log_toolbar, text="■ Lỗi", foreground="#B71C1C", font=("Segoe UI", 8, "bold")).pack(side="left")

        f_log_body = ttk.Frame(f_log)
        f_log_body.pack(fill="both", expand=True, padx=4, pady=4)

        log_scroll = ttk.Scrollbar(f_log_body, orient="vertical")
        self.txt_log = tk.Text(
            f_log_body, height=6, wrap="none", state="disabled",
            bg="#1E1E1E", fg="#ECEFF1", insertbackground="#ECEFF1",
            font=("Consolas", 9), yscrollcommand=log_scroll.set
        )
        log_scroll.config(command=self.txt_log.yview)
        log_scroll.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)

        self.txt_log.tag_configure("info", foreground="#B0BEC5")
        self.txt_log.tag_configure("success", foreground="#66BB6A")
        self.txt_log.tag_configure("warn", foreground="#FFA726")
        self.txt_log.tag_configure("error", foreground="#EF5350")
        self._log_line_count = 0
        self._LOG_MAX_LINES = 2000

        f_bot = ttk.Frame(self.root)
        f_bot.pack(fill="x", padx=10, pady=6)

        ttk.Button(f_bot, text="📁 Nạp JSON", command=self.load_macro_file).pack(side="left", padx=4)
        ttk.Button(f_bot, text="💾 Lưu JSON", command=self.save_macro_file).pack(side="left", padx=4)
        ttk.Button(f_bot, text="📋 Đăng Ký Tác Vụ", command=self.register_current_task).pack(side="left", padx=4)

        self.btn_run = ttk.Button(f_bot, text="▶ CHẠY THỬ (ADB)", command=self.run_macro)
        self.btn_run.pack(side="right", padx=4)
        self.btn_stop = ttk.Button(f_bot, text="⏹ DỪNG (F8)", state="disabled", command=self.stop_macro)
        self.btn_stop.pack(side="right", padx=4)

        self.tree.bind("<Control-a>", self.select_all_steps)

    def show_context_menu_on_blank(self, x_root, y_root):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="➕ Thêm Tìm & Click Ảnh", command=self.add_manual_wait_image)
        menu.add_command(label="➕ Thêm Click Tọa Độ (Tap)", command=self.add_manual_tap)
        menu.add_command(label="➕ Thêm Vuốt (Swipe)", command=self.add_manual_swipe)
        menu.add_command(label="⏳ Thêm Chờ (Sleep)", command=self.add_manual_sleep)
        menu.add_separator()
        menu.add_command(label="⌨️ Thêm Gõ Chữ", command=self.add_manual_type_text)
        menu.add_command(label="⌨️ Thêm Tổ Hợp Phím", command=self.add_manual_key_combo)
        menu.add_command(label="🔤 Thêm Quét OCR", command=self.add_manual_ocr)
        menu.add_command(label="📢 Thêm Popup Thông Báo", command=self.add_manual_popup)
        menu.add_separator()
        menu.add_command(label="🔀 Thêm IF (Ảnh)", command=self.add_if_single_image)
        menu.add_command(label="🔀 Thêm IF (Biến)", command=self.add_if_var)
        menu.add_command(label="↪️ Thêm ELSE", command=self.add_else_step)
        menu.add_command(label="⏹️ Thêm ENDIF", command=self.add_endif_step)
        menu.add_command(label="🔁 Thêm Khung IF/ELSE (2 Nhóm Lặp)", command=self.add_if_else_group_template)
        menu.add_separator()
        menu.add_command(label="🔢 Đặt Biến (Set Var)", command=self.add_manual_set_var)
        menu.add_command(label="🔢 Tăng/Giảm Biến (Inc Var)", command=self.add_manual_inc_var)
        menu.add_command(label="🔁 Thêm Lặp Lại (Continue Nhóm)", command=self.add_continue_group)
        menu.add_command(label="⛔ Dừng Vòng Lặp Nhóm", command=self.add_break_group)
        
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def open_step_edit_menu_at(self, idx_or_iid, x_root, y_root):
        if idx_or_iid is None:
            self.show_context_menu_on_blank(x_root, y_root)
            return

        try:
            idx = int(idx_or_iid)
        except ValueError:
            return

        if idx < 0 or idx >= len(self.steps):
            return

        self.tree.selection_set(str(idx))
        step = self.steps[idx]
        act = step.get("action")

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"📝 Sửa Ghi Chú ({step.get('comment', '')})", 
                         command=lambda: self._edit_step_field(idx, "comment"))
        menu.add_command(label=f"🔁 Sửa Lặp ({self._format_repeat_display(step)})", 
                         command=lambda: self._edit_step_field(idx, "repeat"))
        menu.add_command(label=f"⏱ Sửa Delay sau bước ({step.get('delay', 1.0)}s)", 
                         command=lambda: self._edit_step_field(idx, "delay"))

        if act in ("wait_image", "if_image", "multi_image"):
            menu.add_separator()
            menu.add_command(label=f"🎯 Sửa Độ Khớp ({step.get('conf', 0.80)})", 
                             command=lambda: self._edit_step_field(idx, "conf"))
            menu.add_command(label=f"⏳ Sửa Timeout ({step.get('timeout', 8)}s)", 
                             command=lambda: self._edit_step_field(idx, "timeout"))
            menu.add_command(label=f"⚡ Sửa Tốc Độ Quét ({step.get('scan_interval', 0.1)}s)",
                             command=lambda: self._edit_step_field(idx, "scan_interval"))
            region_txt = "đã đặt" if step.get("region") else "toàn màn hình"
            menu.add_command(label=f"📐 Chọn Vùng Quét ({region_txt})",
                             command=lambda: self._arm_region_recapture(idx))
            if step.get("region"):
                menu.add_command(label="🗑 Bỏ Vùng Quét (quét lại toàn màn hình)",
                                 command=lambda: self._clear_step_region(idx))
            # BUG CŨ: điều kiện chỉ kiểm tra "template" (số ít), nhưng if_image
            # (nhóm ảnh) và multi_image (quét đa ảnh) lưu ảnh ở "templates"
            # (số nhiều, list) -> menu đổi ảnh không bao giờ hiện ra cho 2 loại
            # bước này. Nay xử lý cả 2 trường hợp.
            if "template" in step:
                menu.add_command(label=f"🖼️ Đổi file ảnh ({step.get('template')})", 
                                 command=self.change_step_image)
            elif "templates" in step:
                menu.add_command(label=f"🖼️ Quản lý {len(step.get('templates', []))} ảnh trong nhóm...",
                                 command=lambda: self.manage_group_templates(idx))

        elif act == "key_combo":
            # THIẾU TRƯỚC ĐÂY: không có nhánh nào xử lý key_combo trong menu
            # sửa -> không thể sửa lại tổ hợp phím sau khi đã thêm.
            menu.add_separator()
            keys_display = "+".join(k.replace("KEYCODE_", "") for k in step.get("keys", []))
            menu.add_command(label=f"⌨️ Sửa Tổ Hợp Phím ({keys_display})",
                             command=lambda: self._edit_step_field(idx, "key_combo_keys"))

        elif act == "ocr_text":
            menu.add_separator()
            menu.add_command(label=f"🔤 Sửa Tên Biến Lưu Kết Quả ({step.get('var', 'ocr_text')})",
                             command=lambda: self._edit_step_field(idx, "ocr_var"))
            menu.add_command(label="🔤 Chọn Lại Vùng Quét", command=lambda: self._arm_ocr_recapture(idx))

        elif act == "show_popup":
            menu.add_separator()
            menu.add_command(label=f"📢 Sửa Nội Dung Thông Báo ({step.get('message', '')})",
                             command=lambda: self._edit_step_field(idx, "popup_message"))
            dur = step.get("duration", 0)
            dur_display = f"{dur}s" if dur else "chờ bấm Đóng"
            menu.add_command(label=f"⏱ Sửa Thời Gian Hiện ({dur_display})",
                             command=lambda: self._edit_step_field(idx, "popup_duration"))

        elif act in ("set_var", "inc_var", "if_var"):
            menu.add_separator()
            if act == "if_var":
                menu.add_command(label=f"🔀 Cấu hình điều kiện IF ({step.get('var')} {step.get('op')} {step.get('value')})", 
                                 command=lambda: self._edit_step_field(idx, "if_var_params"))
            elif act == "set_var":
                menu.add_command(label=f"🔢 Cấu hình Đặt Biến ({step.get('var')} = {step.get('value')})", 
                                 command=lambda: self._edit_step_field(idx, "set_var_params"))
            elif act == "inc_var":
                menu.add_command(label=f"🔢 Cấu hình Tăng/Giảm Biến ({step.get('var')} {step.get('amount')})", 
                                 command=lambda: self._edit_step_field(idx, "inc_var_params"))

        elif act == "type_text":
            menu.add_separator()
            menu.add_command(label=f"⌨️ Sửa Nội Dung Gõ ({step.get('text', '')})", 
                             command=lambda: self._edit_step_field(idx, "text_content"))

        elif act == "swipe":
            # THIẾU TRƯỚC ĐÂY: swipe không có menu sửa nào cả (không sửa được
            # Duration sau khi tạo). Nay thêm cả Duration lẫn "Giữ Cuối" -
            # giữ yên tay tại điểm đến 1 khoảng ngắn trước khi nhả, để KÉO
            # THANH TRƯỢT (slider) không bị game hiểu nhầm thành vuốt/ném rồi
            # bật ngược lại (xem docstring adb_helper.py::swipe_hold()).
            menu.add_separator()
            menu.add_command(label=f"⏳ Sửa Thời Gian Kéo - Duration ({step.get('duration', 250)}ms)",
                             command=lambda: self._edit_step_field(idx, "swipe_duration"))
            hold_ms = step.get("hold_ms", 0)
            hold_txt = f"{hold_ms}ms" if hold_ms else "TẮT (swipe thường)"
            menu.add_command(label=f"🐢 Sửa Giữ Cuối - chống bật ngược thanh trượt ({hold_txt})",
                             command=lambda: self._edit_step_field(idx, "swipe_hold_ms"))

        menu.add_separator()
        menu.add_command(label="❌ Xóa Bước Này", command=self.delete_selected_step)

        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

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
            new_val = simpledialog.askinteger("Sửa Timeout", "Thời gian chờ tối đa (giây):", initialvalue=step.get("timeout", 8), minvalue=1, maxvalue=120)
            if new_val is not None:
                step["timeout"] = new_val
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
        if select_range is not None:
            start, end = select_range
            ids = [str(i) for i in range(start, end + 1) if 0 <= i < len(self.steps)]
            if ids:
                self.tree.selection_set(ids)
        elif select_index is not None and 0 <= select_index < len(self.steps):
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
        "wait_image": "🖱️ Kéo khung trên Preview để chọn ẢNH cần Tìm & Click...",
        "if_image": "🖱️ Kéo khung trên Preview để chọn ẢNH điều kiện IF...",
        "tap": "🖱️ Bấm 1 điểm trên Preview để chọn tọa độ Tap...",
        "swipe": "🖱️ Kéo từ điểm đầu đến điểm cuối trên Preview để tạo Vuốt...",
        "ocr_text": "🖱️ Kéo khung trên Preview để chọn VÙNG cần quét chữ (OCR)...",
        "image_region": "🖱️ Kéo khung trên Preview để GIỚI HẠN vùng quét ảnh cho bước này...",
    }

    def _arm_capture(self, kind):
        if self.current_screen_cv is None:
            messagebox.showwarning("Lưu ý", "Hãy chụp màn hình hoặc bật Xem Trực Tiếp trước!")
            return
        self.pending_action = kind
        self.lbl_capture_hint.config(text=self._CAPTURE_HINTS.get(kind, ""))
        self.btn_cancel_capture.pack(side="left", padx=2)

    def _cancel_pending_action(self):
        self._ocr_edit_idx = None
        self._region_edit_idx = None
        self.pending_action = None
        self.lbl_capture_hint.config(text="")
        self.btn_cancel_capture.pack_forget()
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None

    def add_manual_wait_image(self):
        self._arm_capture("wait_image")

    def add_manual_tap(self):
        self._arm_capture("tap")

    def add_manual_swipe(self):
        self._arm_capture("swipe")

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

    def _arm_ocr_recapture(self, idx):
        """Chọn lại vùng quét OCR cho 1 bước ocr_text đã có sẵn."""
        self._ocr_edit_idx = idx
        self._arm_capture("ocr_text")

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

    def on_step_selected(self, event=None):
        sel = self.tree.selection()
        if not sel:
            self._clear_inspector()
            return
        idx = int(sel[0])
        step = self.steps[idx]
        target_file = step.get("template") if step.get("action") in ("wait_image", "if_image") else (step.get("templates")[0] if step.get("templates") else None)
        if target_file:
            path = os.path.join("templates", target_file)
            if os.path.exists(path):
                self.active_inspect_path = path
                self.btn_change_img.config(state="normal")
                self._render_inspect_thumbnail()
                return
        self._clear_inspector()

    def _on_inspect_label_resize(self, event=None):
        if not getattr(self, "active_inspect_path", None):
            return
        if self._inspect_resize_job:
            self.root.after_cancel(self._inspect_resize_job)
        self._inspect_resize_job = self.root.after(120, self._render_inspect_thumbnail)

    def _render_inspect_thumbnail(self):
        self._inspect_resize_job = None
        path = getattr(self, "active_inspect_path", None)
        if not path or not os.path.exists(path):
            return
        try:
            img = Image.open(path)
            w, h = img.size
            img.thumbnail((max(70, self.lbl_inspect_img.winfo_width() - 10), max(70, self.lbl_inspect_img.winfo_height() - 10)))
            self.current_inspect_photo = ImageTk.PhotoImage(img)
            self.lbl_inspect_img.config(image=self.current_inspect_photo, text="")
            self.lbl_inspect_info.config(text=f"{os.path.basename(path)}\n{w}x{h}px")
        except Exception:
            pass

    def _clear_inspector(self):
        if self._inspect_resize_job:
            self.root.after_cancel(self._inspect_resize_job)
            self._inspect_resize_job = None
        self.lbl_inspect_img.config(image="", text="Chưa chọn ảnh")
        self.lbl_inspect_info.config(text="")
        self.btn_change_img.config(state="disabled")
        self.active_inspect_path = None

    def open_large_inspect_image(self, event=None):
        if getattr(self, "active_inspect_path", None) and os.path.exists(self.active_inspect_path):
            top = tk.Toplevel(self.root)
            top.title(os.path.basename(self.active_inspect_path))
            _bind_esc_close(top)
            img = Image.open(self.active_inspect_path)
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(top, image=photo)
            lbl.image = photo
            lbl.pack(padx=10, pady=10)

    def change_step_image(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        step = self.steps[idx]
        path = filedialog.askopenfilename(initialdir="templates", title="Chọn ảnh thay thế", filetypes=[("Images", "*.png;*.jpg")])
        if not path:
            return
        new_name = os.path.basename(path)
        if "template" in step:
            step["template"] = new_name
            step["comment"] = f"Ảnh: {new_name}"
        elif "templates" in step:
            step["templates"][0] = new_name
        self.refresh_tree()
        self.tree.selection_set(str(idx))
        self.on_step_selected()

    def on_preset_change(self, _):
        val = self.cbo_preset.get()
        if "x" in val:
            w, h = val.split("x")
            self.spin_w.set(int(w))
            self.spin_h.set(int(h))

    def get_crop_wh(self):
        try:
            return max(20, int(self.spin_w.get())), max(20, int(self.spin_h.get()))
        except Exception:
            return 100, 100

    def refresh_all(self):
        # refresh_devices() giờ đã TỰ gắn đúng cửa sổ (qua
        # _attach_window_for_current_device()) - KHÔNG gọi find_ld_windows()
        # (quét mù) ở đây nữa, kẻo ghi đè mất kết quả đúng vừa gắn được bằng
        # 1 kết quả quét mù có thể SAI khi đang mở nhiều giả lập.
        self.refresh_devices()

    def refresh_devices(self):
        devs = self.adb.get_devices()
        self.cbo_dev["values"] = devs

        self._device_hwnd_map = {}
        if self.emulator_manager.has_ldconsole():
            try:
                for info in self.emulator_manager.refresh():
                    if info.adb_serial:
                        self._device_hwnd_map[info.adb_serial] = info
            except Exception:
                pass

        if devs:
            self.cbo_dev.current(0)
            self.adb.device_id = devs[0]
            self.adb.update_resolution()
            self.capture_and_show()
            self._attach_window_for_current_device()
        else:
            self.cbo_dev.set("Chưa có ADB")
        self._update_keycombo_warning()

    def _attach_window_for_current_device(self):
        """Gắn ĐÚNG cửa sổ LDPlayer (hwnd) tương ứng với giả lập ĐANG CHỌN ở
        ô 'Thiết bị' - quyết định F7 (ghi macro) và mọi thao tác canh toạ độ
        khác sẽ chạy trên cửa sổ nào. Ưu tiên hwnd biết CHẮC CHẮN từ
        `ldconsole list2` (đúng 100% dù mở bao nhiêu giả lập cùng lúc); chỉ
        khi không có ldconsole.exe trên máy mới lùi về cách quét mù cũ (bắt
        cửa sổ LDPlayer đầu tiên tìm thấy trên hệ thống - CÓ THỂ SAI nếu
        đang mở nhiều giả lập)."""
        serial = self.adb.device_id
        info = self._device_hwnd_map.get(serial)
        if info and info.hwnd:
            if self.window_finder.attach_hwnd(info.hwnd):
                self.lbl_ld_status.config(text=f"LD: {info.name}", foreground="green")
                return

        # Không có ánh xạ hwnd tin cậy -> quét mù như trước, kèm cảnh báo nếu
        # đang mở NHIỀU giả lập cùng lúc (lúc đó quét mù rất dễ bắt NHẦM).
        self.find_ld_windows()
        if len(self.adb.get_devices()) > 1:
            self.lbl_ld_status.config(
                text=self.lbl_ld_status.cget("text") + " (⚠️ nhiều giả lập, có thể SAI - cần ldconsole.exe để gắn đúng)",
                foreground="#E65100"
            )

    def _update_keycombo_warning(self):
        """Báo NGAY trên giao diện nếu máy ảo đang chạy Android < 12, vì khi
        đó bước 'Tổ Hợp Phím' (Ctrl+..., Alt+..., Shift+...) sẽ không giữ
        được đồng thời các phím - đây là giới hạn của chính Android, không
        phải app bị lỗi. Trước đây lỗi này hoàn toàn im lặng, không có gì
        báo cho người dùng biết."""
        if not self.adb.device_id:
            self.lbl_keycombo_warn.config(text="")
            return
        try:
            sdk = self.adb.get_sdk_version()
        except Exception:
            sdk = 0
        if sdk and sdk < 31:
            self.lbl_keycombo_warn.config(
                text=f"⚠️ Android SDK {sdk}: Tổ hợp phím (Ctrl/Alt/Shift+...) có thể KHÔNG hoạt động (cần Android 12+)",
                foreground="#B71C1C"
            )
        else:
            self.lbl_keycombo_warn.config(text="")

    def _apply_default_preview_width(self):
        try:
            self.root.update_idletasks()
            total_h = self.canvas.winfo_height()
            if total_h < 100:
                total_h = 620
            screen_w = self.adb.screen_w or 720
            screen_h = self.adb.screen_h or 1280
            ratio = screen_w / screen_h if screen_h else 0.5625
            target_w = int(total_h * ratio) + 40
            self.paned.sashpos(0, max(380, target_w))
        except Exception:
            pass

    def find_ld_windows(self):
        hwnd, title = self.window_finder.find_ld_windows()
        if hwnd:
            self.lbl_ld_status.config(text=f"LD: {title or 'Kyle'}", foreground="green")
        else:
            self.lbl_ld_status.config(text="LD: Không thấy", foreground="red")

    def on_select_device(self, _):
        self.adb.device_id = self.cbo_dev.get()
        self.adb._sdk_version = None  # đổi thiết bị -> phải dò lại SDK version
        self.adb.update_resolution()
        self.capture_and_show()
        self._attach_window_for_current_device()
        self._update_keycombo_warning()

    def capture_and_show(self):
        if not self.adb.device_id or self.is_recording_live:
            return
        img_cv = self.adb.screencap_fast()
        if img_cv is None:
            return
        self.current_screen_cv = img_cv
        self.render_preview(img_cv)

    def render_preview(self, img_cv, highlight_box=None):
        if img_cv is None:
            return
        self.root.update_idletasks()
        h, w = img_cv.shape[:2]
        cw = max(self.canvas.winfo_width(), 360)
        ch = max(self.canvas.winfo_height(), 500)
        scale = min(cw / w, ch / h)
        self.preview_scale = max(scale, 0.01)
        self.preview_w = max(1, int(w * self.preview_scale))
        self.preview_h = max(1, int(h * self.preview_scale))
        resized = cv2.resize(img_cv, (self.preview_w, self.preview_h), interpolation=cv2.INTER_AREA)

        if highlight_box:
            bx1, by1, bx2, by2 = highlight_box
            cv2.rectangle(resized, (int(bx1 * self.preview_scale), int(by1 * self.preview_scale)), (int(bx2 * self.preview_scale), int(by2 * self.preview_scale)), (0, 255, 0), 2)

        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        self.tk_img = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)

    def toggle_live_stream(self):
        if not self.is_streaming_active:
            if not self.adb.device_id:
                messagebox.showerror("Lỗi", "Chưa kết nối ADB!")
                return
            self.is_streaming_active = True
            self.btn_toggle_stream.config(text="⏹ DỪNG LIVE", bg="#C62828")
            self.lbl_fps.config(text="FPS: ...", foreground="#0D47A1")
        else:
            self.is_streaming_active = False
            self.btn_toggle_stream.config(text="▶ LIVE", bg="#455A64")
            self.lbl_fps.config(text="FPS: OFF", foreground="gray")

    def _stream_capture_worker(self):
        frame_count, last_t = 0, time.time()
        while True:
            if self.is_streaming_active and self.adb.device_id and not self.is_playing and not self.is_recording_live:
                frame = self.adb.screencap_fast()
                if frame is not None:
                    with self.frame_lock:
                        self.current_screen_cv = frame
                        self.new_frame_ready = True
                    frame_count += 1
                    now = time.time()
                    if now - last_t >= 1.0:
                        fps = round(frame_count / (now - last_t), 1)
                        self.root.after(0, lambda f=fps: self.lbl_fps.config(text=f"FPS: {f}"))
                        frame_count, last_t = 0, now
                else:
                    time.sleep(0.1)
                time.sleep(0.04)
            else:
                time.sleep(0.15)

    def _render_poll_loop(self):
        if self.is_streaming_active and self.new_frame_ready and self.current_screen_cv is not None:
            with self.frame_lock:
                img_to_draw = self.current_screen_cv.copy()
                self.new_frame_ready = False
            self.render_preview(img_to_draw)
        self.root.after(40, self._render_poll_loop)

    def add_if_single_image(self):
        self._arm_capture("if_image")

    def add_if_multi_image(self):
        paths = filedialog.askopenfilenames(initialdir="templates", title="Chọn nhóm ảnh IF", filetypes=[("Images", "*.png;*.jpg")])
        if not paths:
            return
        filenames = [os.path.basename(p) for p in paths]
        self._insert_step({"action": "if_image", "templates": filenames, "timeout": 3, "conf": 0.80, "repeat": 1, "delay": 0.2, "comment": f"Nếu thấy bất kỳ ({len(filenames)} ảnh)"})

    def add_else_step(self):
        self._insert_step({"action": "else", "repeat": 1, "delay": 0.1, "comment": "Ngược lại"})

    def add_endif_step(self):
        self._insert_step({"action": "endif", "repeat": 1, "delay": 0.1, "comment": "Đóng IF"})

    def add_multi_image_step(self):
        paths = filedialog.askopenfilenames(initialdir="templates", title="Chọn nhiều ảnh quét song song", filetypes=[("Images", "*.png;*.jpg")])
        if not paths:
            return
        filenames = [os.path.basename(p) for p in paths]
        self._insert_step({"action": "multi_image", "templates": filenames, "timeout": 8, "conf": 0.80, "click": True, "repeat": 1, "delay": 1.0, "comment": f"Quét song song ({len(filenames)} ảnh)"})

    def _start_global_hotkeys(self):
        def on_press(key):
            if key == keyboard.Key.f7:
                self.root.after(0, self.toggle_live_record)
            elif key == keyboard.Key.f8 and self.is_playing:
                self.root.after(0, self.stop_macro)
        self.kb_hotkey_listener = keyboard.Listener(on_press=on_press)
        self.kb_hotkey_listener.daemon = True
        self.kb_hotkey_listener.start()

    def toggle_live_record(self):
        if not self.is_recording_live:
            # QUAN TRỌNG: TRƯỚC ĐÂY gọi find_ld_windows() (quét mù, luôn bắt
            # cửa sổ LDPlayer ĐẦU TIÊN tìm thấy) ngay tại đây, ghi ĐÈ mất cửa
            # sổ ĐÚNG đã gắn theo giả lập đang chọn ở ô "Thiết bị" (qua
            # _attach_window_for_current_device() lúc đổi ô chọn) - khiến F7
            # LUÔN ghi nhầm vào 1 giả lập cố định (thường là giả lập mở đầu
            # tiên) mỗi khi mở nhiều giả lập cùng lúc, dù đã đổi đúng ô chọn
            # và Preview đã đổi đúng - CHÍNH LÀ lỗi người dùng phát hiện ra.
            # Nay CHỈ dùng cửa sổ đã gắn sẵn theo giả lập đang chọn; chỉ quét
            # mù lại như phương án CUỐI CÙNG nếu vì lý do gì đó chưa gắn được
            # cửa sổ nào (vd chưa có ldconsole.exe, hoặc chưa chọn giả lập).
            if not self.window_finder.main_hwnd:
                self._attach_window_for_current_device()
            if not self.window_finder.main_hwnd:
                messagebox.showerror("Lỗi", "Chưa nhận diện được cửa sổ LDPlayer!\nHãy chọn đúng giả lập ở ô 'Thiết bị' rồi thử lại.")
                return
            if self.is_streaming_active:
                self.is_streaming_active = False
                self.btn_toggle_stream.config(text="▶ LIVE", bg="#455A64")
                self.lbl_fps.config(text="FPS: OFF", foreground="gray")
                time.sleep(0.1)
            self.is_recording_live = True
            self.btn_live_record.config(text="⏹ DỪNG GHI (F7)", bg="#C62828")
            self.recorder.start()
        else:
            self.is_recording_live = False
            self.btn_live_record.config(text="● GHI LD (F7)", bg="#2E7D32")
            self.recorder.stop()
            self.capture_and_show()

    def on_canvas_press(self, event):
        self.drag_start = (event.x, event.y)
        cw, ch = self.get_crop_wh()
        half_w, half_h = int((cw // 2) * self.preview_scale), int((ch // 2) * self.preview_scale)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        if (self.pending_action in ("wait_image", "if_image", "ocr_text", "image_region")) or (self.pending_action is None and "crop" in self.preview_action_mode.get()):
            self.rect_id = self.canvas.create_rectangle(event.x - half_w, event.y - half_h, event.x + half_w, event.y + half_h, outline="#00ff00", width=2)

    def on_canvas_drag(self, event):
        if not self.drag_start:
            return
        if abs(event.x - self.drag_start[0]) > 15 or abs(event.y - self.drag_start[1]) > 15:
            if self.rect_id:
                self.canvas.coords(self.rect_id, self.drag_start[0], self.drag_start[1], event.x, event.y)
                self.canvas.itemconfig(self.rect_id, outline="yellow")

    def on_canvas_release(self, event):
        if not self.drag_start or self.current_screen_cv is None:
            return
        x1, y1, x2, y2 = self.drag_start[0], self.drag_start[1], event.x, event.y
        self.drag_start = None
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None

        rx1, ry1 = round(x1 / self.preview_w, 4), round(y1 / self.preview_h, 4)
        rx2, ry2 = round(x2 / self.preview_w, 4), round(y2 / self.preview_h, 4)
        cached_screen = self.current_screen_cv.copy()
        mode = self.preview_action_mode.get()
        dragged = abs(x2 - x1) > 20 or abs(y2 - y1) > 20

        if self.pending_action == "tap":
            self._insert_step({"action": "tap", "pos": [rx1, ry1], "repeat": 1, "delay": 1.0, "comment": f"Tap [{int(rx1*100)}%, {int(ry1*100)}%]"})
            threading.Thread(target=self._worker_send_tap, args=(rx1, ry1), daemon=True).start()
            self._cancel_pending_action()
            return
        elif self.pending_action == "swipe":
            self._insert_step({"action": "swipe", "from": [rx1, ry1], "to": [rx2, ry2], "duration": 250, "repeat": 1, "delay": 1.0, "comment": f"Swipe"})
            threading.Thread(target=self._worker_send_swipe, args=(rx1, ry1, rx2, ry2), daemon=True).start()
            self._cancel_pending_action()
            return
        elif self.pending_action in ("wait_image", "if_image"):
            if dragged:
                self._do_crop_custom(cached_screen, x1, y1, x2, y2, trigger_tap=(self.pending_action == "wait_image"), kind=self.pending_action)
            else:
                self._do_crop(cached_screen, int(x1 / self.preview_scale), int(y1 / self.preview_scale), rx1, ry1, trigger_tap=(self.pending_action == "wait_image"), kind=self.pending_action)
            self._cancel_pending_action()
            return
        elif self.pending_action == "image_region":
            # Vùng quét (region) lưu theo TỌA ĐỘ TỈ LỆ (0..1) trên toàn màn
            # hình, y hệt cách lưu box của ocr_text - matchTemplate của bước
            # ảnh này sẽ CHỈ so khớp trong vùng này thay vì toàn màn hình.
            nx1, ny1 = sorted((rx1, rx2))[0], sorted((ry1, ry2))[0]
            nx2, ny2 = sorted((rx1, rx2))[1], sorted((ry1, ry2))[1]
            if nx2 - nx1 < 0.02 or ny2 - ny1 < 0.02:
                messagebox.showwarning("Lưu ý", "Hãy KÉO một khung đủ lớn làm vùng quét!")
                self._cancel_pending_action()
                return
            edit_idx = self._region_edit_idx
            if edit_idx is not None and 0 <= edit_idx < len(self.steps):
                self.steps[edit_idx]["region"] = [nx1, ny1, nx2, ny2]
                self.refresh_tree()
                self.tree.selection_set(str(edit_idx))
            self._cancel_pending_action()
            return
        elif self.pending_action == "ocr_text":
            # Vùng OCR lưu theo TỌA ĐỘ TỈ LỆ (0..1), không lưu ảnh cố định,
            # vì mỗi lần chạy cần đọc chữ TRÊN MÀN HÌNH HIỆN TẠI (có thể thay
            # đổi liên tục), khác với wait_image/if_image là so khớp mẫu cố định.
            nx1, ny1 = sorted((rx1, rx2))[0], sorted((ry1, ry2))[0]
            nx2, ny2 = sorted((rx1, rx2))[1], sorted((ry1, ry2))[1]
            if nx2 - nx1 < 0.01 or ny2 - ny1 < 0.01:
                messagebox.showwarning("Lưu ý", "Hãy KÉO một khung đủ lớn quanh vùng chữ cần quét!")
                self._cancel_pending_action()
                return
            edit_idx = self._ocr_edit_idx
            if edit_idx is not None:
                step = self.steps[edit_idx]
                step["box"] = [nx1, ny1, nx2, ny2]
                self.refresh_tree()
                self.tree.selection_set(str(edit_idx))
            else:
                var_name = simpledialog.askstring("Quét OCR", "Lưu kết quả OCR vào biến tên gì (dùng với IF Biến):", initialvalue="ocr_text")
                if var_name:
                    self._insert_step({
                        "action": "ocr_text", "box": [nx1, ny1, nx2, ny2], "var": var_name.strip(),
                        "lang": "vie+eng", "repeat": 1, "delay": 0.5,
                        "comment": f"OCR vùng -> biến {var_name.strip()}"
                    })
            self._cancel_pending_action()
            return

        if dragged and mode == "tap_only":
            self._insert_step({"action": "swipe", "from": [rx1, ry1], "to": [rx2, ry2], "duration": 250, "repeat": 1, "delay": 1.0, "comment": f"Swipe"})
            threading.Thread(target=self._worker_send_swipe, args=(rx1, ry1, rx2, ry2), daemon=True).start()
        elif dragged and mode in ("crop_and_tap", "crop_only"):
            self._do_crop_custom(cached_screen, x1, y1, x2, y2, trigger_tap=(mode == "crop_and_tap"))
        else:
            real_cx, real_cy = int(x1 / self.preview_scale), int(y1 / self.preview_scale)
            if mode == "crop_and_tap":
                self._do_crop(cached_screen, real_cx, real_cy, rx1, ry1, trigger_tap=True)
            elif mode == "crop_only":
                self._do_crop(cached_screen, real_cx, real_cy, rx1, ry1, trigger_tap=False)
            elif mode == "tap_only":
                self._insert_step({"action": "tap", "pos": [rx1, ry1], "repeat": 1, "delay": 1.0, "comment": f"Tap"})
                threading.Thread(target=self._worker_send_tap, args=(rx1, ry1), daemon=True).start()

    def _do_crop(self, screen_img, cx, cy, norm_x, norm_y, trigger_tap=False, kind="wait_image"):
        cw, ch = self.get_crop_wh()
        box = capture_tools.crop_fixed_box(screen_img, cx, cy, cw, ch)
        filename = capture_tools.save_crop(screen_img, box)
        step = capture_tools.build_capture_step(kind, filename, int(self.spin_all_timeout.get() or 8), float(self.spin_all_conf.get() or 0.80))
        self._insert_step(step)
        self.render_preview(screen_img, highlight_box=box)
        if trigger_tap:
            threading.Thread(target=self._worker_send_tap, args=(norm_x, norm_y), daemon=True).start()

    def _do_crop_custom(self, screen_img, px1, py1, px2, py2, trigger_tap=False, kind="wait_image"):
        px1, px2 = sorted((px1, px2))
        py1, py2 = sorted((py1, py2))
        scr_h, scr_w = screen_img.shape[:2]
        x1, y1 = max(0, min(scr_w, int(px1 / self.preview_scale))), max(0, min(scr_h, int(py1 / self.preview_scale)))
        x2, y2 = max(0, min(scr_w, int(px2 / self.preview_scale))), max(0, min(scr_h, int(py2 / self.preview_scale)))
        if x2 - x1 < 5 or y2 - y1 < 5:
            return
        box = (x1, y1, x2, y2)
        filename = capture_tools.save_crop(screen_img, box)
        self.spin_w.delete(0, "end")
        self.spin_w.insert(0, str(x2 - x1))
        self.spin_h.delete(0, "end")
        self.spin_h.insert(0, str(y2 - y1))
        step = capture_tools.build_capture_step(kind, filename, int(self.spin_all_timeout.get() or 8), float(self.spin_all_conf.get() or 0.80))
        self._insert_step(step)
        self.render_preview(screen_img, highlight_box=box)
        if trigger_tap:
            threading.Thread(target=self._worker_send_tap, args=(round(((x1 + x2) / 2) / scr_w, 4), round(((y1 + y2) / 2) / scr_h, 4)), daemon=True).start()

    def _worker_send_tap(self, nx, ny):
        self.adb.tap(nx, ny)
        time.sleep(0.4)
        if not self.is_streaming_active:
            self.capture_and_show()

    def _worker_send_swipe(self, x1, y1, x2, y2):
        self.adb.swipe(x1, y1, x2, y2, 250)
        time.sleep(0.5)
        if not self.is_streaming_active:
            self.capture_and_show()

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
                detail = f"{indent_str}┌── [IF Ảnh] {s.get('comment', '')}"
                tag, indent_level = "tag_logic", indent_level + 1
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
                detail = f"{indent_str}├── Ảnh: {s.get('template')} ({s.get('comment', '')})"
                tag = "tag_image"
            elif act == "tap":
                detail = f"{indent_str}├── Tap {s.get('pos')} ({s.get('comment', '')})"
                tag = "tag_tap"
            elif act == "swipe":
                hold_ms = s.get("hold_ms", 0)
                detail = f"{indent_str}├── Swipe" + (f" (🐢 Giữ Cuối {hold_ms}ms)" if hold_ms else "")
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

    def _clear_run_log(self):
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.config(state="disabled")
        self._log_line_count = 0

    def _save_run_log_to_file(self):
        path = filedialog.asksaveasfilename(
            initialdir="logs", defaultextension=".txt",
            filetypes=[("Text files", "*.txt")]
        )
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            content = self.txt_log.get("1.0", "end-1c")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Thành công", "Đã lưu Nhật Ký ra file!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không lưu được log:\n{e}")

    def _log_run(self, level, message):
        """Được LogicEngine gọi từ THREAD NỀN mỗi khi thực hiện 1 hành động,
        gặp lỗi, đổi biến, quét OCR, tìm thấy/không thấy ảnh... Tkinter chỉ
        được thao tác từ main thread nên phải điều phối qua root.after()."""
        self.root.after(0, lambda: self._append_log_line(level, message))

    def _append_log_line(self, level, message):
        ts = time.strftime("%H:%M:%S")
        tag = level if level in ("info", "success", "warn", "error") else "info"
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", f"[{ts}] {message}\n", (tag,))
        self._log_line_count += 1
        # Giới hạn số dòng để log không phình to vô hạn khi chạy lâu / lặp nhiều
        if self._log_line_count > self._LOG_MAX_LINES:
            trim_to = self._log_line_count - self._LOG_MAX_LINES
            self.txt_log.delete("1.0", f"{trim_to + 1}.0")
            self._log_line_count = self._LOG_MAX_LINES
        if self.var_log_autoscroll.get():
            self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    def run_macro(self):
        if not self.steps:
            messagebox.showwarning("Lưu ý", "Chưa có bước nào!")
            return
        if self.is_streaming_active:
            self.is_streaming_active = False
            self.btn_toggle_stream.config(text="▶ LIVE", bg="#455A64")
            self.lbl_fps.config(text="FPS: OFF", foreground="gray")
            time.sleep(0.1)
        self.is_playing = True
        self.stop_flag = False
        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._append_log_line("info", f"══════ Bắt đầu chạy kịch bản ({len(self.steps)} bước) ══════")
        threading.Thread(target=self._worker_run, daemon=True).start()

    def stop_macro(self):
        self.stop_flag = True
        self._log_run("warn", "Người dùng bấm DỪNG - đang chờ bước hiện tại kết thúc...")

    def _show_ingame_popup(self, message, duration=0):
        """Hiện thông báo dạng OVERLAY đè lên đúng khung hình LDPlayer (không
        phải hộp thoại messagebox ở ngoài tool như trước - user phản hồi rõ
        là cần thông báo NGAY TRÊN GAME). Được LogicEngine gọi từ thread nền
        nên phải điều phối tạo cửa sổ qua root.after() (Tkinter chỉ thao tác
        được từ main thread).
        - duration > 0: tự đóng sau N giây, KHÔNG chặn kịch bản (giống toast).
        - duration == 0: hiện tới khi bấm "Đóng", kịch bản DỪNG chờ tại đây."""
        done_event = threading.Event() if not duration else None

        def _do():
            rect = self.window_finder.get_render_screen_rect()
            top = tk.Toplevel(self.root)
            top.overrideredirect(True)
            try:
                top.attributes("-topmost", True)
                top.attributes("-alpha", 0.93)
            except Exception:
                pass

            if rect:
                sx, sy, sw, sh = rect
                banner_h = 64
                top.geometry(f"{max(sw, 220)}x{banner_h}+{sx}+{max(0, sy)}")
                wrap = max(150, sw - 90)
            else:
                # Không tìm thấy cửa sổ LDPlayer -> vẫn hiện overlay ở góc
                # màn hình thay vì lỗi im lặng, kèm cảnh báo trong nội dung.
                top.geometry("420x64+200+200")
                wrap = 330
                message = "(Không tìm thấy cửa sổ LDPlayer) " + (message or "")

            frame = tk.Frame(top, bg="#212121", highlightbackground="#FFEB3B", highlightthickness=2)
            frame.pack(fill="both", expand=True)
            tk.Label(frame, text=message or "(không có nội dung)", bg="#212121", fg="#FFEB3B",
                     font=("Segoe UI", 12, "bold"), wraplength=wrap, justify="left").pack(
                side="left", expand=True, fill="both", padx=12, pady=6)

            def _close():
                try:
                    top.destroy()
                except Exception:
                    pass
                if done_event:
                    done_event.set()

            if duration and duration > 0:
                top.after(int(duration * 1000), _close)
            else:
                ttk.Button(frame, text="✔ Đóng", command=_close).pack(side="right", padx=10)

        self.root.after(0, _do)
        if done_event:
            done_event.wait()

    def _worker_run(self):
        error_msg = None
        self.engine.reset_variables()
        try:
            self.engine.execute_steps(self.steps, is_root=True)
        except (BreakGroupSignal, ContinueGroupSignal):
            pass
        except Exception as e:
            error_msg = str(e)
        self.root.after(0, lambda: self._on_finish_run(error_msg))

    def _on_finish_run(self, error_msg=None):
        self.is_playing = False
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")
        if not self.is_streaming_active:
            self.capture_and_show()
        if error_msg:
            self._append_log_line("error", f"══════ DỪNG DO LỖI: {error_msg} ══════")
            messagebox.showerror("Lỗi", f"Quy trình dừng do lỗi:\n{error_msg}")
        elif self.stop_flag:
            self._append_log_line("warn", "══════ Đã dừng theo yêu cầu người dùng ══════")
            messagebox.showinfo("Đã dừng", "Đã dừng quy trình theo yêu cầu!")
        else:
            self._append_log_line("success", "══════ Chạy xong toàn bộ kịch bản ══════")
            messagebox.showinfo("Xong", "Chạy xong quy trình!")
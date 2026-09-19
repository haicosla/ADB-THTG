"""
gui_dialogs.py — Các hộp thoại (Toplevel) nhỏ, dùng lại nhiều nơi trong LD
Macro Studio: nhập/sửa biến (SET_VAR, INC_VAR, IF_VAR) và hộp thoại chỉnh
tham số bước "Chờ + Vuốt Zoom" (ZoomStepDialog). Kèm vài hàm phụ trợ parse
chuỗi nhập nhanh (quick-type) cho từng loại hộp thoại.

Đây LÀ các class/hàm ĐỘC LẬP (không phải Mixin của MacroStudioApp) - được
gui.py và các gui_*.py khác import trực tiếp khi cần mở hộp thoại. Tách
riêng khỏi gui.py (vốn trước đây dài hơn 3500 dòng) để dễ tìm/sửa: MUỐN SỬA
giao diện/hành vi 1 hộp thoại cụ thể? Mở đúng class tương ứng ở đây, KHÔNG
cần lục file gui.py chính.

Xem thêm gui_dialogs_data.py cho các hộp thoại còn lại (quản lý nhóm dữ
liệu, "Dữ Liệu Kế Tiếp", đăng ký Hoạt Động).
"""

import re
import tkinter as tk
from tkinter import ttk, messagebox


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


class ZoomStepDialog(tk.Toplevel):
    """Hộp thoại nhập tham số cho 1 bước Zoom (Pinch) - GỬI VÀO GIẢ LẬP cử
    chỉ 2 ngón tay chụm/mở để phóng to/thu nhỏ (khác hẳn Zoom Preview bằng
    Ctrl+lăn chuột, vốn CHỈ phóng to ảnh xem trước trên máy tính, không gửi
    gì cho giả lập). Xem ADBHelper.pinch_zoom() để biết cách cử chỉ này
    được mô phỏng."""

    # (start_radius, end_radius) tính bằng px, theo hướng đã chọn.
    _PRESETS = {"in": (70, 260), "out": (260, 70)}

    def __init__(self, parent, initial=None):
        super().__init__(parent)
        self.title("Zoom (Pinch) - Gửi Vào Giả Lập")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = None
        initial = initial or {}
        pad = {"padx": 10, "pady": 5}

        r1_0 = initial.get("start_radius", 70)
        r2_0 = initial.get("end_radius", 260)
        direction0 = "in" if r2_0 >= r1_0 else "out"

        ttk.Label(self, text="Hướng cử chỉ:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        self.cbo_dir = ttk.Combobox(self, state="readonly", width=32,
                                     values=["🔍➕ Phóng To (2 ngón tách ra)", "🔍➖ Thu Nhỏ (2 ngón chụm lại)"])
        self.cbo_dir.current(0 if direction0 == "in" else 1)
        self.cbo_dir.grid(row=0, column=1, sticky="w", **pad)
        self.cbo_dir.bind("<<ComboboxSelected>>", self._on_dir_change)

        ttk.Label(self, text="Tâm cử chỉ (đã chọn trên Preview):").grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(6, 0))
        cx = initial.get("center") or [0.5, 0.5]
        ttk.Label(self, text=f"[{int(cx[0]*100)}%, {int(cx[1]*100)}%]", foreground="#1565C0").grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 6))

        ttk.Label(self, text="Bán kính đầu (px):").grid(row=3, column=0, sticky="w", **pad)
        self.txt_r1 = ttk.Entry(self, width=10)
        self.txt_r1.insert(0, str(int(r1_0)))
        self.txt_r1.grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(self, text="Bán kính cuối (px):").grid(row=4, column=0, sticky="w", **pad)
        self.txt_r2 = ttk.Entry(self, width=10)
        self.txt_r2.insert(0, str(int(r2_0)))
        self.txt_r2.grid(row=4, column=1, sticky="w", **pad)

        ttk.Label(self, text="Góc trục (0=Ngang, 90=Dọc):").grid(row=5, column=0, sticky="w", **pad)
        self.txt_angle = ttk.Entry(self, width=10)
        self.txt_angle.insert(0, str(initial.get("angle", 90)))
        self.txt_angle.grid(row=5, column=1, sticky="w", **pad)

        ttk.Label(self, text="Thời gian (ms):").grid(row=6, column=0, sticky="w", **pad)
        self.txt_duration = ttk.Entry(self, width=10)
        self.txt_duration.insert(0, str(int(initial.get("duration", 400))))
        self.txt_duration.grid(row=6, column=1, sticky="w", **pad)

        ttk.Label(self, text="(Tự dò cảm ứng đa điểm để gửi multi-touch\nTHẬT qua sendevent; nếu không dò được sẽ tự\ndùng phương án dự phòng - xem log khi chạy.)",
                  foreground="gray", justify="left").grid(row=7, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 4))

        f_btn = ttk.Frame(self)
        f_btn.grid(row=8, column=0, columnspan=2, pady=12)
        ttk.Button(f_btn, text="✔ Xác Nhận", command=self._on_confirm).pack(side="left", padx=6)
        ttk.Button(f_btn, text="✖ Hủy", command=self.destroy).pack(side="left", padx=6)

        self.bind("<Return>", lambda e: self._on_confirm())
        _bind_esc_close(self)
        self.geometry(f"+{parent.winfo_rootx() + 150}+{parent.winfo_rooty() + 120}")

    def _on_dir_change(self, event=None):
        direction = "in" if self.cbo_dir.current() == 0 else "out"
        r1, r2 = self._PRESETS[direction]
        self.txt_r1.delete(0, tk.END)
        self.txt_r1.insert(0, str(r1))
        self.txt_r2.delete(0, tk.END)
        self.txt_r2.insert(0, str(r2))

    def _on_confirm(self):
        try:
            r1 = float(self.txt_r1.get().strip())
            r2 = float(self.txt_r2.get().strip())
            angle = float(self.txt_angle.get().strip())
            duration = int(float(self.txt_duration.get().strip()))
        except ValueError:
            messagebox.showerror("Lỗi", "Bán kính/Góc/Thời gian phải là số!", parent=self)
            return
        if r1 <= 0 or r2 <= 0:
            messagebox.showerror("Lỗi", "Bán kính phải lớn hơn 0!", parent=self)
            return
        self.result = {"start_radius": r1, "end_radius": r2, "angle": angle, "duration": duration}
        self.destroy()



"""
gui_dialogs_data.py — Các hộp thoại (Toplevel) liên quan tới DỮ LIỆU/TÁC
VỤ dùng lại nhiều nơi trong LD Macro Studio:

    DataGroupManagerDialog -> quản lý các "Nhóm Dữ Liệu" (data_groups.json)
                               dùng cho bước NEXT_DATA_ITEM.
    NextDataItemDialog     -> chọn nhóm dữ liệu + tên biến cho 1 bước
                               "Dữ Liệu Kế Tiếp".
    RegisterTaskDialog     -> đăng ký 1 file kịch bản .json vào Danh Mục
                               Tác Vụ (task_registry.json) để Dashboard
                               thấy được.

Tách riêng khỏi gui_dialogs.py (vốn chỉ chứa các hộp thoại nhập/sửa biến)
để mỗi file không quá dài - xem thêm gui_dialogs.py cho SetVarDialog/
IncVarDialog/IfVarDialog/ZoomStepDialog.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import data_groups
from gui_dialogs import _bind_esc_close


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



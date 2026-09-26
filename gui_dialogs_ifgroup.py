"""
gui_dialogs_ifgroup.py — IfGroupDialog: trình xây CÂY điều kiện AND/OR/NOT
lồng nhau tuỳ ý cho bước "if_group" (xem logic_engine.py::LogicEngine.
_eval_condition_node để biết cây được ĐÁNH GIÁ thế nào lúc chạy thật - file
này chỉ lo phần XÂY DỰNG cây bằng chuột, không đánh giá gì cả).

Cấu trúc cây (dict lồng nhau), lưu y hệt schema mà logic_engine.py đọc:
    Nút GỘP:  {"type": "and"/"or", "children": [node, ...]}
              {"type": "not", "children": [node]}          (ĐÚNG 1 con)
    Nút LÁ:   {"type": "image", "template", "conf", "region"}
              {"type": "var", "var", "op", "value"}
              {"type": "ocr", "box", "text", "match", "lang"}

Tách riêng khỏi gui_dialogs.py vì đây là 1 trình soạn thảo cây tương đối
lớn (Treeview + nhiều dialog con) - xem gui_dialogs.py cho các hộp thoại
đơn giản hơn (SetVarDialog/IfVarDialog/IfOcrDialog/...).
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import cv2
from PIL import Image, ImageTk

from gui_dialogs import _bind_esc_close, IfVarDialog


GROUP_LABELS = {
    "and": "🔗 VÀ (AND) - TẤT CẢ điều kiện con phải ĐÚNG",
    "or": "🔀 HOẶC (OR) - CHỈ CẦN 1 điều kiện con ĐÚNG",
    "not": "🚫 KHÔNG (NOT) - đảo ngược ĐÚNG/SAI của điều kiện con",
}


def _node_label(node):
    """Tả ngắn gọn 1 nút để hiển thị trong Treeview - xem bản tương đương
    dùng khi LOG lúc CHẠY THẬT ở logic_engine.py::_describe_condition_node
    (2 hàm này KHÔNG dùng chung vì mục đích khác nhau: đây là để SOẠN, còn
    hàm kia là để LOG - không cần giữ y hệt nhau)."""
    t = node.get("type")
    if t == "and":
        return f"🔗 VÀ (AND) — {len(node.get('children', []))} điều kiện con"
    if t == "or":
        return f"🔀 HOẶC (OR) — {len(node.get('children', []))} điều kiện con"
    if t == "not":
        return "🚫 KHÔNG (NOT)" + (" — (rỗng, cần thêm 1 điều kiện)" if not node.get("children") else "")
    if t == "image":
        conf = node.get("conf", 0.80)
        region_txt = " [có giới hạn vùng]" if node.get("region") else ""
        return f"🖼️ Ảnh: {node.get('template') or '⚠️ CHƯA CHỌN'} (khớp ≥{conf:.2f}){region_txt}"
    if t == "var":
        return f"🔢 Biến: {node.get('var', '?')} {node.get('op', '==')} {node.get('value', '?')}"
    if t == "ocr":
        box = node.get("box")
        box_txt = "toàn màn hình" if not box else f"vùng đã chọn"
        return f"🔤 OCR: \"{node.get('text', '')}\" ({node.get('match', 'contains')}, {box_txt})"
    return "❓ (không rõ loại)"


class RegionPickerDialog(tk.Toplevel):
    """Hộp thoại con: hiện ảnh chụp màn hình hiện tại, cho KÉO 1 khung chữ
    nhật để chọn vùng (giống hệt thao tác kéo trên Preview chính, nhưng
    đóng gói riêng trong 1 Canvas của chính dialog này để không đụng chạm
    tới bộ máy pending_action/capture của cửa sổ chính - IfGroupDialog là
    1 cửa sổ MODAL (grab_set) nên không thể vừa mở nó vừa thao tác chuột
    trên Preview chính được). Trả về self.result = [x1,y1,x2,y2] (TỈ LỆ
    0..1) hoặc None nếu chọn "Toàn Màn Hình" / bấm Hủy."""

    MAX_W, MAX_H = 380, 680

    def __init__(self, parent, screen_cv, title="Chọn vùng", initial_box=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = "CANCELLED"  # phân biệt với None (= "toàn màn hình")

        h, w = screen_cv.shape[:2]
        scale = min(self.MAX_W / w, self.MAX_H / h, 1.0)
        self.disp_w, self.disp_h = int(w * scale), int(h * scale)
        img_rgb = cv2.cvtColor(cv2.resize(screen_cv, (self.disp_w, self.disp_h)), cv2.COLOR_BGR2RGB)
        self._photo = ImageTk.PhotoImage(Image.fromarray(img_rgb))

        ttk.Label(self, text="Kéo chuột để chọn vùng cần dùng (hoặc bấm \"Toàn Màn Hình\" bên dưới):").pack(padx=10, pady=(10, 4))
        self.canvas = tk.Canvas(self, width=self.disp_w, height=self.disp_h, cursor="cross", highlightthickness=1, highlightbackground="#999")
        self.canvas.pack(padx=10)
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)

        self._drag_start = None
        self._rect_id = None
        if initial_box:
            x1, y1, x2, y2 = initial_box
            self._rect_id = self.canvas.create_rectangle(
                x1 * self.disp_w, y1 * self.disp_h, x2 * self.disp_w, y2 * self.disp_h,
                outline="#ba00ff", width=2)
            self._box_norm = tuple(initial_box)
        else:
            self._box_norm = None

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        f_btn = ttk.Frame(self)
        f_btn.pack(pady=10)
        ttk.Button(f_btn, text="✔ Dùng Vùng Đã Kéo", command=self._on_confirm).pack(side="left", padx=6)
        ttk.Button(f_btn, text="🖥️ Toàn Màn Hình", command=self._on_full_screen).pack(side="left", padx=6)
        ttk.Button(f_btn, text="✖ Hủy", command=self.destroy).pack(side="left", padx=6)

        _bind_esc_close(self)
        self.geometry(f"+{parent.winfo_rootx() + 100}+{parent.winfo_rooty() + 60}")

    def _on_press(self, event):
        self._drag_start = (event.x, event.y)
        if self._rect_id:
            self.canvas.delete(self._rect_id)
            self._rect_id = None

    def _on_drag(self, event):
        if not self._drag_start:
            return
        x0, y0 = self._drag_start
        if self._rect_id:
            self.canvas.coords(self._rect_id, x0, y0, event.x, event.y)
        else:
            self._rect_id = self.canvas.create_rectangle(x0, y0, event.x, event.y, outline="#ba00ff", width=2)

    def _on_release(self, event):
        if not self._drag_start:
            return
        x0, y0 = self._drag_start
        x1, y1 = max(0, min(x0, event.x)), max(0, min(y0, event.y))
        x2, y2 = min(self.disp_w, max(x0, event.x)), min(self.disp_h, max(y0, event.y))
        self._drag_start = None
        if x2 - x1 < 6 or y2 - y1 < 6:
            # Kéo quá nhỏ (gần như click) - coi như CHƯA chọn gì, xoá khung
            if self._rect_id:
                self.canvas.delete(self._rect_id)
                self._rect_id = None
            self._box_norm = None
            return
        self._box_norm = (x1 / self.disp_w, y1 / self.disp_h, x2 / self.disp_w, y2 / self.disp_h)

    def _on_confirm(self):
        if not self._box_norm:
            messagebox.showwarning("Lưu ý", "Hãy KÉO một khung trên ảnh trước, hoặc bấm \"Toàn Màn Hình\"!", parent=self)
            return
        self.result = [round(v, 4) for v in self._box_norm]
        self.destroy()

    def _on_full_screen(self):
        self.result = None
        self.destroy()


class IfGroupOcrLeafDialog(tk.Toplevel):
    """Hộp thoại thêm/sửa 1 nút LÁ kiểu 'ocr' cho if_group - gồm chọn vùng
    (qua RegionPickerDialog) + text/kiểu khớp, cùng bản chất với if_ocr
    nhưng đóng gói lại thành 1 bước bấm duy nhất vì nằm TRONG 1 dialog con
    của cây, không capture trực tiếp trên Preview chính được (xem docstring
    RegionPickerDialog)."""

    def __init__(self, parent, screen_cv, initial=None):
        super().__init__(parent)
        self.title("Thêm Điều Kiện Lá: OCR")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = None
        self._screen_cv = screen_cv
        initial = initial or {}
        self._box = initial.get("box")
        pad = {"padx": 10, "pady": 5}

        self.lbl_box = ttk.Label(self, text=self._box_display())
        self.lbl_box.grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Button(self, text="🖼️ Chọn Vùng Quét...", command=self._pick_region).grid(row=1, column=0, columnspan=2, sticky="w", padx=10)

        ttk.Label(self, text="Chữ cần khớp:").grid(row=2, column=0, sticky="w", **pad)
        self.txt_text = ttk.Entry(self, width=32)
        self.txt_text.insert(0, initial.get("text", ""))
        self.txt_text.grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(self, text="Kiểu so khớp:").grid(row=3, column=0, sticky="w", **pad)
        self.cbo_match = ttk.Combobox(self, values=["contains", "exact", "regex"], state="readonly", width=14)
        self.cbo_match.set(initial.get("match", "contains"))
        self.cbo_match.grid(row=3, column=1, sticky="w", **pad)

        f_btn = ttk.Frame(self)
        f_btn.grid(row=4, column=0, columnspan=2, pady=12)
        ttk.Button(f_btn, text="✔ Xác Nhận", command=self._on_confirm).pack(side="left", padx=6)
        ttk.Button(f_btn, text="✖ Hủy", command=self.destroy).pack(side="left", padx=6)

        _bind_esc_close(self)
        self.geometry(f"+{parent.winfo_rootx() + 160}+{parent.winfo_rooty() + 100}")
        self.txt_text.focus_set()

    def _box_display(self):
        if not self._box:
            return "Vùng quét: (chưa chọn -> mặc định TOÀN MÀN HÌNH)"
        x1, y1, x2, y2 = self._box
        return f"Vùng quét: {int(x1*100)}%,{int(y1*100)}% → {int(x2*100)}%,{int(y2*100)}%"

    def _pick_region(self):
        dlg = RegionPickerDialog(self, self._screen_cv, title="Chọn vùng quét OCR", initial_box=self._box)
        self.wait_window(dlg)
        if dlg.result != "CANCELLED":
            self._box = dlg.result  # None = toàn màn hình (vẫn hợp lệ), hoặc [x1,y1,x2,y2]
            self.lbl_box.config(text=self._box_display())

    def _on_confirm(self):
        text = self.txt_text.get().strip()
        if not text:
            if not messagebox.askyesno("Lưu ý", "Chưa nhập chữ cần khớp - điều kiện này sẽ LUÔN ĐÚNG (chỉ để đọc). Tiếp tục?", parent=self):
                return
        self.result = {
            "type": "ocr",
            "box": self._box if self._box else [0.0, 0.0, 1.0, 1.0],
            "text": text,
            "match": self.cbo_match.get() or "contains",
            "lang": "vie+eng",
        }
        self.destroy()


class IfGroupImageLeafDialog(tk.Toplevel):
    """Hộp thoại thêm/sửa 1 nút LÁ kiểu 'image' cho if_group - chọn 1 file
    ảnh mẫu CÓ SẴN trong thư mục templates/ (giống hệt cách if_image nhiều
    ảnh / multi_image chọn ảnh - xem gui_manual_steps.py::add_if_multi_
    image, dùng filedialog.askopenfilename thay vì tự chụp mới, vì ảnh mẫu
    cho if_group cũng phải capture TRƯỚC bằng 1 bước wait_image/if_image
    thường rồi mới dùng lại được ở đây) + ngưỡng độ khớp + (tuỳ chọn) giới
    hạn vùng quét qua RegionPickerDialog."""

    def __init__(self, parent, screen_cv, initial=None):
        super().__init__(parent)
        self.title("Thêm Điều Kiện Lá: Ảnh")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result = None
        self._screen_cv = screen_cv
        initial = initial or {}
        self._template = initial.get("template")
        self._region = initial.get("region")
        pad = {"padx": 10, "pady": 5}

        self.lbl_template = ttk.Label(self, text=self._template_display())
        self.lbl_template.grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        ttk.Button(self, text="📂 Chọn File Ảnh Mẫu (trong thư mục templates)...",
                   command=self._pick_template).grid(row=1, column=0, columnspan=2, sticky="w", padx=10)
        ttk.Label(self, text="(Ảnh mẫu phải được CHỤP TRƯỚC bằng 1 bước Tìm & Click Ảnh / IF Ảnh thường,\nrồi mới chọn lại được ở đây)",
                  font=("Segoe UI", 8), foreground="#666").grid(row=2, column=0, columnspan=2, sticky="w", padx=10)

        ttk.Label(self, text="Ngưỡng độ khớp (0.5 - 1.0):").grid(row=3, column=0, sticky="w", **pad)
        self.txt_conf = ttk.Entry(self, width=10)
        self.txt_conf.insert(0, str(initial.get("conf", 0.80)))
        self.txt_conf.grid(row=3, column=1, sticky="w", **pad)

        self.lbl_region = ttk.Label(self, text=self._region_display())
        self.lbl_region.grid(row=4, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 2))
        ttk.Button(self, text="🖼️ Giới Hạn Vùng Quét (tuỳ chọn)...", command=self._pick_region).grid(row=5, column=0, columnspan=2, sticky="w", padx=10)

        f_btn = ttk.Frame(self)
        f_btn.grid(row=6, column=0, columnspan=2, pady=12)
        ttk.Button(f_btn, text="✔ Xác Nhận", command=self._on_confirm).pack(side="left", padx=6)
        ttk.Button(f_btn, text="✖ Hủy", command=self.destroy).pack(side="left", padx=6)

        _bind_esc_close(self)
        self.geometry(f"+{parent.winfo_rootx() + 160}+{parent.winfo_rooty() + 100}")

    def _template_display(self):
        return f"Ảnh mẫu: {self._template}" if self._template else "Ảnh mẫu: ⚠️ CHƯA CHỌN"

    def _region_display(self):
        if not self._region:
            return "Vùng quét: toàn màn hình (không giới hạn)"
        x1, y1, x2, y2 = self._region
        return f"Vùng quét: {int(x1*100)}%,{int(y1*100)}% → {int(x2*100)}%,{int(y2*100)}%"

    def _pick_template(self):
        path = filedialog.askopenfilename(
            initialdir="templates", title="Chọn ảnh mẫu cho điều kiện",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg")], parent=self)
        if path:
            self._template = os.path.basename(path)
            self.lbl_template.config(text=self._template_display())

    def _pick_region(self):
        dlg = RegionPickerDialog(self, self._screen_cv, title="Giới hạn vùng quét ảnh", initial_box=self._region)
        self.wait_window(dlg)
        if dlg.result != "CANCELLED":
            self._region = dlg.result
            self.lbl_region.config(text=self._region_display())

    def _on_confirm(self):
        if not self._template:
            messagebox.showerror("Lỗi", "Chưa chọn ảnh mẫu!", parent=self)
            return
        try:
            conf = float(self.txt_conf.get().strip())
        except ValueError:
            conf = 0.80
        node = {"type": "image", "template": self._template, "conf": max(0.3, min(1.0, conf))}
        if self._region:
            node["region"] = self._region
        self.result = node
        self.destroy()


class IfGroupDialog(tk.Toplevel):
    """Trình xây CÂY điều kiện AND/OR/NOT lồng nhau tuỳ ý cho bước
    "if_group" - xem docstring đầu file để biết schema. self.result là cả
    cây (dict) khi người dùng bấm "Lưu Cây Điều Kiện", hoặc None nếu Hủy.

    Quy tắc thao tác (đơn giản hoá tối đa để dễ dùng bằng chuột):
    - Gốc cây LUÔN là 1 nút GỘP (and/or/not) - không cho gốc là 1 lá đơn lẻ
      (nếu chỉ cần 1 điều kiện thì dùng thẳng if_image/if_var/if_ocr, không
      cần if_group).
    - Nút đang CHỌN trong cây quyết định điều mới THÊM VÀO ĐÂU: chọn 1 nút
      GỘP -> thêm làm CON của nút đó; chọn 1 LÁ -> thêm làm ANH EM của lá đó
      (tức con của CHA nó); KHÔNG chọn gì -> thêm vào GỐC.
    - Nút NOT chỉ chứa được ĐÚNG 1 con - thêm con thứ 2 sẽ bị từ chối kèm
      thông báo rõ ràng.
    """

    def __init__(self, parent, screen_cv, initial_tree=None, existing_vars=None):
        super().__init__(parent)
        self.title("Cấu hình IF (Nhóm Điều Kiện - AND/OR/NOT)")
        self.geometry("620x560")
        self.transient(parent)
        self.grab_set()

        self.result = None
        self._screen_cv = screen_cv
        self._existing_vars = existing_vars or ["a"]
        # Cây luôn có gốc là 1 nút GỘP - nếu cây truyền vào là 1 LÁ đơn lẻ
        # (lẽ ra không nên xảy ra vì if_group luôn lưu gốc là nhóm, nhưng
        # phòng hờ dữ liệu cũ/sửa tay JSON), bọc nó vào trong 1 "and" 1 con.
        if initial_tree and initial_tree.get("type") in ("and", "or", "not"):
            self.tree_data = initial_tree
        elif initial_tree:
            self.tree_data = {"type": "and", "children": [initial_tree]}
        else:
            self.tree_data = {"type": "and", "children": []}

        self._build_ui()
        self._refresh_tree_view()
        _bind_esc_close(self)
        self.geometry(f"+{parent.winfo_rootx() + 60}+{parent.winfo_rooty() + 40}")

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(top, text="Cây điều kiện (chọn 1 nút rồi bấm nút bên dưới để thêm/xoá/sửa):",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w")

        self.tv = ttk.Treeview(top, show="tree", height=16)
        self.tv.pack(fill="both", expand=True, pady=(4, 8))
        self.tv.bind("<Double-1>", lambda e: self._on_edit_selected())

        f_group = ttk.LabelFrame(top, text="Thêm NHÓM (chứa nhiều điều kiện con)")
        f_group.pack(fill="x", pady=(0, 6))
        ttk.Button(f_group, text="🔗 Thêm VÀ (AND)", command=lambda: self._add_group_node("and")).pack(side="left", padx=4, pady=4)
        ttk.Button(f_group, text="🔀 Thêm HOẶC (OR)", command=lambda: self._add_group_node("or")).pack(side="left", padx=4, pady=4)
        ttk.Button(f_group, text="🚫 Thêm KHÔNG (NOT)", command=lambda: self._add_group_node("not")).pack(side="left", padx=4, pady=4)

        f_leaf = ttk.LabelFrame(top, text="Thêm ĐIỀU KIỆN LÁ")
        f_leaf.pack(fill="x", pady=(0, 6))
        ttk.Button(f_leaf, text="🖼️ Ảnh...", command=self._add_leaf_image).pack(side="left", padx=4, pady=4)
        ttk.Button(f_leaf, text="🔢 Biến...", command=self._add_leaf_var).pack(side="left", padx=4, pady=4)
        ttk.Button(f_leaf, text="🔤 OCR...", command=self._add_leaf_ocr).pack(side="left", padx=4, pady=4)

        f_edit = ttk.Frame(top)
        f_edit.pack(fill="x", pady=(0, 8))
        ttk.Button(f_edit, text="✏️ Sửa Nút Đang Chọn", command=self._on_edit_selected).pack(side="left", padx=4)
        ttk.Button(f_edit, text="🗑 Xoá Nút Đang Chọn", command=self._on_delete_selected).pack(side="left", padx=4)

        f_btn = ttk.Frame(top)
        f_btn.pack(fill="x")
        ttk.Button(f_btn, text="✔ Lưu Cây Điều Kiện", command=self._on_save).pack(side="left", padx=4)
        ttk.Button(f_btn, text="✖ Hủy", command=self.destroy).pack(side="left", padx=4)

    # ----------------------------------------------------- Cây <-> path
    @staticmethod
    def _path_to_iid(path):
        return "-".join(str(p) for p in path) if path else "root"

    @staticmethod
    def _iid_to_path(iid):
        return () if iid == "root" else tuple(int(x) for x in iid.split("-"))

    def _get_node(self, path):
        node = self.tree_data
        for i in path:
            node = node["children"][i]
        return node

    def _get_parent_and_index(self, path):
        """Trả (nút CHA, chỉ số trong children của cha). Gốc (path rỗng)
        trả (None, None) vì gốc không có cha - KHÔNG xoá/di chuyển được
        gốc, chỉ sửa được TYPE của gốc (xem _on_edit_selected)."""
        if not path:
            return None, None
        return self._get_node(path[:-1]), path[-1]

    def _selected_path(self):
        sel = self.tv.selection()
        return self._iid_to_path(sel[0]) if sel else ()

    def _target_group_path(self):
        """Xác định THÊM VÀO ĐÂU dựa trên lựa chọn hiện tại - xem quy tắc
        ở docstring class."""
        path = self._selected_path()
        node = self._get_node(path)
        if node.get("type") in ("and", "or", "not"):
            return path
        return path[:-1]

    # --------------------------------------------------------- Vẽ lại
    def _refresh_tree_view(self, select_path=None):
        self.tv.delete(*self.tv.get_children())
        self._insert_recursive("", self.tree_data, ())
        for iid in self.tv.get_children(""):
            self._open_all(iid)
        target_iid = self._path_to_iid(select_path) if select_path is not None else "root"
        if self.tv.exists(target_iid):
            self.tv.selection_set(target_iid)
            self.tv.see(target_iid)

    def _open_all(self, iid):
        self.tv.item(iid, open=True)
        for child in self.tv.get_children(iid):
            self._open_all(child)

    def _insert_recursive(self, parent_iid, node, path):
        iid = self._path_to_iid(path)
        self.tv.insert(parent_iid, "end", iid=iid, text=_node_label(node), open=True)
        if node.get("type") in ("and", "or", "not"):
            for i, child in enumerate(node.get("children", [])):
                self._insert_recursive(iid, child, path + (i,))

    # ------------------------------------------------------- Thêm nút
    def _add_child(self, new_node):
        target_path = self._target_group_path()
        target = self._get_node(target_path)
        if target.get("type") == "not" and target.get("children"):
            messagebox.showwarning(
                "Lưu ý",
                "Nút KHÔNG (NOT) chỉ chứa được ĐÚNG 1 điều kiện con.\n"
                "Hãy chọn 1 nút khác (hoặc xoá điều kiện con hiện tại của NOT trước).",
                parent=self)
            return
        target.setdefault("children", []).append(new_node)
        new_path = target_path + (len(target["children"]) - 1,)
        self._refresh_tree_view(select_path=new_path)

    def _add_group_node(self, group_type):
        self._add_child({"type": group_type, "children": []})

    def _add_leaf_image(self):
        dlg = IfGroupImageLeafDialog(self, self._screen_cv)
        self.wait_window(dlg)
        if dlg.result:
            self._add_child(dlg.result)

    def _add_leaf_var(self):
        dlg = IfVarDialog(self, existing_vars=self._existing_vars)
        self.wait_window(dlg)
        if dlg.result:
            self._add_child({"type": "var", **dlg.result})

    def _add_leaf_ocr(self):
        dlg = IfGroupOcrLeafDialog(self, self._screen_cv)
        self.wait_window(dlg)
        if dlg.result:
            self._add_child(dlg.result)

    # ------------------------------------------------------- Sửa/Xoá
    def _on_edit_selected(self):
        path = self._selected_path()
        node = self._get_node(path)
        t = node.get("type")
        if t in ("and", "or", "not"):
            # Sửa 1 nút GỘP = đổi TYPE của nó (vd đổi AND thành OR) - dùng
            # 1 hộp thoại chọn nhanh 3 lựa chọn thay vì mở cả IfGroupDialog
            # lồng trong chính nó (không cần thiết, chỉ đổi type).
            choice = simpledialog.askstring(
                "Đổi loại Nhóm",
                "Nhập loại mới: and / or / not\n(NOT chỉ áp dụng được nếu nhóm đang có ĐÚNG 0 hoặc 1 điều kiện con)",
                initialvalue=t, parent=self)
            if not choice:
                return
            choice = choice.strip().lower()
            if choice not in ("and", "or", "not"):
                messagebox.showerror("Lỗi", "Chỉ nhận: and / or / not", parent=self)
                return
            if choice == "not" and len(node.get("children", [])) > 1:
                messagebox.showerror("Lỗi", "NOT chỉ chứa được tối đa 1 điều kiện con - hãy xoá bớt trước khi đổi sang NOT.", parent=self)
                return
            node["type"] = choice
            self._refresh_tree_view(select_path=path)
            return

        if t == "image":
            dlg = IfGroupImageLeafDialog(self, self._screen_cv, initial=node)
        elif t == "var":
            dlg = IfVarDialog(self, existing_vars=self._existing_vars,
                              initial_var=node.get("var", "a"), initial_op=node.get("op", "=="),
                              initial_val=node.get("value", 0))
        elif t == "ocr":
            dlg = IfGroupOcrLeafDialog(self, self._screen_cv, initial=node)
        else:
            return
        self.wait_window(dlg)
        if dlg.result:
            if t == "var":
                node.clear()
                node.update({"type": "var", **dlg.result})
            else:
                node.clear()
                node.update(dlg.result)
            self._refresh_tree_view(select_path=path)

    def _on_delete_selected(self):
        path = self._selected_path()
        if not path:
            messagebox.showwarning("Lưu ý", "Không thể xoá NÚT GỐC của cây - chỉ có thể đổi loại (AND/OR/NOT) hoặc xoá từng điều kiện con bên trong.", parent=self)
            return
        parent, idx = self._get_parent_and_index(path)
        if not messagebox.askyesno("Xác nhận", "Xoá nút này" + (" và TOÀN BỘ nút con bên trong nó" if self._get_node(path).get("type") in ("and", "or", "not") else "") + "?", parent=self):
            return
        del parent["children"][idx]
        self._refresh_tree_view(select_path=path[:-1])

    # --------------------------------------------------------------- Lưu
    def _on_save(self):
        problems = self._validate(self.tree_data, is_root=True)
        if problems:
            if not messagebox.askyesno(
                    "Cây điều kiện chưa hoàn chỉnh",
                    "Phát hiện vấn đề:\n\n" + "\n".join(f"• {p}" for p in problems) +
                    "\n\nVẫn LƯU cây này? (những nút lỗi sẽ luôn tính là SAI lúc chạy)",
                    parent=self):
                return
        self.result = self.tree_data
        self.destroy()

    def _validate(self, node, is_root=False):
        problems = []
        t = node.get("type")
        if t in ("and", "or"):
            children = node.get("children", [])
            if not children:
                problems.append(f"Nhóm {'GỐC ' if is_root else ''}{t.upper()} đang RỖNG (chưa có điều kiện con nào)")
            for c in children:
                problems.extend(self._validate(c))
        elif t == "not":
            children = node.get("children", [])
            if not children:
                problems.append("Nhóm NOT đang RỖNG (chưa có điều kiện con)")
            for c in children:
                problems.extend(self._validate(c))
        elif t == "image" and not node.get("template"):
            problems.append("Có 1 điều kiện Ảnh chưa chọn file ảnh mẫu")
        return problems

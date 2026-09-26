"""
gui_inspector.py — InspectorMixin: panel "xem chi tiết 1 bước đang chọn"
(ảnh mẫu thu nhỏ, phóng to xem full ảnh, thống kê ảnh mẫu nào đang được
dùng/không dùng ở "Thư Viện Ảnh Mẫu"), cùng vài lựa chọn ảnh hưởng khung
xem trước (đổi preset kích thước, đổi ảnh mẫu của 1 bước).

Đây là 1 phần của class MacroStudioApp (xem gui.py), tách theo chức năng
như các Mixin dashboard_*.py - "self." trỏ vào cùng 1 instance
MacroStudioApp, KHÔNG đổi hành vi so với bản gộp 1 file trước đây.
""" 
import os
import json
import glob
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw

from gui_dialogs import _bind_esc_close


class InspectorMixin:

    def on_step_selected(self, event=None):
        sel = self.tree.selection()
        if not sel:
            self._clear_inspector()
            self._update_region_overlay(None)
            return
        idx = int(sel[0])
        step = self.steps[idx]
        self._update_region_overlay(step)

        # "template" (1 ảnh) hoặc "templates" (NHÓM ảnh - if_image dạng
        # nhóm / multi_image) - key CHỈ CẦN TỒN TẠI (kể cả giá trị None
        # của bước RỖNG tạo qua ESC) là biết bước này thuộc loại có ảnh.
        if "template" in step or "templates" in step:
            self.active_inspect_step = step
            group = step.get("templates")
            if group:
                # TRƯỚC ĐÂY: luôn chỉ lấy templates[0] -> không xem được
                # các ảnh còn lại trong nhóm. Nay giữ lại VỊ TRÍ đang xem
                # (active_inspect_group_idx) và cho điều hướng ◀/▶ (xem
                # _inspect_group_nav) để xem hết cả nhóm ảnh.
                self.active_inspect_group = group
                gidx = getattr(self, "active_inspect_group_idx", 0)
                if not (0 <= gidx < len(group)):
                    gidx = 0
                self.active_inspect_group_idx = gidx
                target_file = group[gidx]
            else:
                self.active_inspect_group = None
                self.active_inspect_group_idx = 0
                target_file = step.get("template")

            if target_file:
                path = os.path.join("templates", target_file)
                if os.path.exists(path):
                    self.active_inspect_path = path
                    # Ghi nhớ bước đang chọn để _render_inspect_thumbnail()
                    # vẽ thêm điểm LỆCH CLICK (click_offset) đè lên
                    # thumbnail nếu có.
                    self.btn_change_img.config(state="normal")
                    self._render_inspect_thumbnail()
                    self._update_inspect_group_nav()
                    return

            # Bước RỖNG (tạo qua ESC, "chọn ảnh sau") hoặc file ảnh đã bị
            # mất khỏi templates/ - VẪN cho bấm '🔄 Đổi Ảnh Khác' ngay ở
            # đây để chọn ảnh luôn, không bắt buộc phải chuột phải -> chọn
            # ảnh nữa (chuột phải vào bước vẫn giữ nguyên dòng đổi ảnh
            # như cũ, không đổi gì ở đó).
            if self._inspect_resize_job:
                self.root.after_cancel(self._inspect_resize_job)
                self._inspect_resize_job = None
            self.active_inspect_path = None
            self.lbl_inspect_img.config(image="", text="⚠️ Chưa chọn ảnh\n(bấm 🔄 Đổi Ảnh Khác)")
            self.lbl_inspect_info.config(text="")
            self.btn_change_img.config(state="normal")
            self._update_inspect_group_nav()
            return

        self._clear_inspector()

    def _inspect_group_nav(self, delta):
        """Bấm ◀/▶ ở panel Ảnh Mẫu - chuyển sang ảnh kế tiếp/trước đó
        TRONG CÙNG 1 NHÓM (if_image dạng nhóm / multi_image) để xem hết
        cả nhóm thay vì chỉ luôn thấy ảnh đầu tiên."""
        group = getattr(self, "active_inspect_group", None)
        if not group or len(group) <= 1:
            return
        idx = (getattr(self, "active_inspect_group_idx", 0) + delta) % len(group)
        self.active_inspect_group_idx = idx
        target_file = group[idx]
        path = os.path.join("templates", target_file)
        if os.path.exists(path):
            self.active_inspect_path = path
            self._render_inspect_thumbnail()
        else:
            self.lbl_inspect_img.config(image="", text=f"⚠️ Không thấy file\n{target_file}")
            self.lbl_inspect_info.config(text="")
        self._update_inspect_group_nav()

    def _update_inspect_group_nav(self):
        """Cập nhật hàng ◀ [Ảnh i/N] ▶ phía trên khung ảnh - ẩn/disable
        khi bước đang chọn không phải NHÓM ảnh (chỉ 1 ảnh hoặc chưa có
        ảnh nào)."""
        group = getattr(self, "active_inspect_group", None)
        nav = getattr(self, "f_inspect_nav", None)
        if nav is None:
            return
        if group and len(group) > 1:
            idx = getattr(self, "active_inspect_group_idx", 0)
            self.lbl_inspect_group.config(text=f"🖼️ Nhóm ảnh {idx + 1}/{len(group)}")
            self.btn_inspect_prev.config(state="normal")
            self.btn_inspect_next.config(state="normal")
            nav.pack(padx=5, pady=(0, 2), fill="x", before=self.lbl_inspect_img)
        else:
            nav.pack_forget()

    def _update_region_overlay(self, step):
        """Cập nhật vùng quét (region của wait_image/if_image/multi_image,
        box của ocr_text), ĐIỂM CHẠM (pos của bước Tap), ĐƯỜNG VUỐT (from/to
        của bước Swipe) hoặc TÂM ZOOM (center của bước Zoom) cần vẽ đè lên
        Preview theo BƯỚC ĐANG ĐƯỢC CHỌN trong danh sách - giúp nhìn ngay
        bước đó tác động ở đâu trên màn hình mà không cần mở lại chế độ
        chọn vùng/tọa độ. Vẽ lại Preview ngay (nếu đang có sẵn 1 khung
        hình) để thấy hiệu lực tức thì kể cả khi KHÔNG bật Xem Trực Tiếp."""
        overlay = None
        if step:
            act = step.get("action")
            if act in ("wait_image", "if_image", "multi_image", "wait_vanish") and step.get("region"):
                overlay = {"type": "region", "box": step.get("region")}
            elif act in ("ocr_text", "if_ocr") and step.get("box"):
                overlay = {"type": "region", "box": step.get("box")}
            elif act == "tap" and step.get("pos"):
                overlay = {"type": "point", "pos": step.get("pos")}
            elif act == "swipe" and step.get("from") and step.get("to"):
                overlay = {"type": "swipe", "from": step.get("from"), "to": step.get("to")}
            elif act == "swipe_path" and step.get("points") and len(step.get("points")) >= 2:
                overlay = {"type": "path", "points": step.get("points")}
            elif act == "zoom" and step.get("center"):
                overlay = {
                    "type": "zoom", "center": step.get("center"),
                    "start_radius": step.get("start_radius", 70),
                    "end_radius": step.get("end_radius", 260),
                    "angle": step.get("angle", 90),
                }
        if overlay == self._step_action_overlay:
            return
        self._step_action_overlay = overlay
        if self.current_screen_cv is not None and not self.is_streaming_active:
            self.render_preview(self.current_screen_cv)

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
            img = Image.open(path).convert("RGB")
            w, h = img.size

            # Nếu bước đang chọn có đặt LỆCH ĐIỂM CLICK (click_offset) và
            # vẫn đang BẬT click, vẽ đè 1 dấu (+) đỏ lên đúng vị trí sẽ được
            # bấm thật (tính từ TÂM ảnh mẫu, cộng thêm độ lệch theo pixel
            # thật) - cho thấy ngay trên thumbnail thay vì phải tự hình dung.
            step = getattr(self, "active_inspect_step", None)
            offset = None
            if step and step.get("action") in ("wait_image", "multi_image") and step.get("click", True):
                off = step.get("click_offset") or [0, 0]
                if off[0] or off[1]:
                    offset = off

            if offset:
                img = img.copy()
                draw = ImageDraw.Draw(img)
                cx, cy = w / 2, h / 2
                # Kẹp điểm đánh dấu trong khung ảnh (min 4px lề) để vẫn NHÌN
                # THẤY được dấu ngay cả khi lệch ra ngoài phạm vi ảnh mẫu -
                # vị trí click THẬT lúc chạy vẫn đúng bằng số pixel đã đặt,
                # chỉ có hình vẽ minh hoạ này bị kẹp lại cho dễ nhìn.
                mx = max(4, min(w - 4, cx + offset[0]))
                my = max(4, min(h - 4, cy + offset[1]))
                r = max(5, min(w, h) // 10)
                draw.line([(cx, cy), (mx, my)], fill=(0, 230, 230), width=2)
                draw.ellipse([mx - r, my - r, mx + r, my + r], outline=(255, 40, 40), width=3)
                draw.line([(mx - r, my), (mx + r, my)], fill=(255, 40, 40), width=2)
                draw.line([(mx, my - r), (mx, my + r)], fill=(255, 40, 40), width=2)

            img.thumbnail((max(70, self.lbl_inspect_img.winfo_width() - 4), max(70, self.lbl_inspect_img.winfo_height() - 4)))
            self.current_inspect_photo = ImageTk.PhotoImage(img)
            self.lbl_inspect_img.config(image=self.current_inspect_photo, text="")
            info_txt = f"{os.path.basename(path)}\n{w}x{h}px"
            if offset:
                info_txt += f"\n🎯 Lệch click: {offset[0]:+d},{offset[1]:+d}px (chấm đỏ = điểm bấm thật)"
            self.lbl_inspect_info.config(text=info_txt)
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
        self.active_inspect_step = None
        self.active_inspect_group = None
        self.active_inspect_group_idx = 0
        self._update_inspect_group_nav()

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

    def _compute_template_usage(self):
        """Quét TẤT CẢ tác vụ đã lưu trong thư mục tasks/*.json, CỘNG với
        kịch bản đang mở trong bộ nhớ (self.steps - có thể đang sửa dở,
        chưa lưu ra đĩa), để biết mỗi ảnh trong templates/ đang được dùng
        ở những tác vụ nào. Trả về dict:
            {tên_file_ảnh: {"count": số lần dùng, "used_in": [tên các tác vụ]}}
        Ảnh KHÔNG có mặt trong dict này = ảnh chưa dùng trong task nào.
        Cố tình gộp cả kịch bản đang mở (chưa lưu) để tránh xoá nhầm ảnh
        đang dùng dở chỉ vì chưa kịp bấm Lưu JSON."""
        usage = {}

        def _register(fname, task_label):
            if not fname:
                return
            entry = usage.setdefault(fname, {"count": 0, "used_in": []})
            entry["count"] += 1
            if task_label not in entry["used_in"]:
                entry["used_in"].append(task_label)

        def _scan_steps(steps, task_label):
            for s in steps:
                if not isinstance(s, dict):
                    continue
                if s.get("template"):
                    _register(s["template"], task_label)
                for t in (s.get("templates") or []):
                    _register(t, task_label)

        for path in glob.glob(os.path.join("tasks", "*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    _scan_steps(data, os.path.splitext(os.path.basename(path))[0])
            except Exception:
                continue

        current_label = (
            os.path.splitext(os.path.basename(self.current_macro_path))[0] + " (đang mở)"
            if self.current_macro_path else "(kịch bản đang mở, chưa lưu)"
        )
        _scan_steps(self.steps, current_label)

        return usage

    def open_template_library(self):
        """Thư viện ảnh (thư mục templates/): xem toàn bộ ảnh kèm số lần &
        tác vụ đang dùng, lọc riêng ảnh KHÔNG dùng trong task nào, và xoá
        (đã chọn hoặc toàn bộ ảnh chưa dùng) ngay tại đây thay vì phải mở
        Explorer dò từng file."""
        os.makedirs("templates", exist_ok=True)

        top = tk.Toplevel(self.root)
        top.title("🖼️ Thư Viện Ảnh (Templates)")
        top.geometry("640x580")
        top.transient(self.root)
        top.grab_set()
        _bind_esc_close(top)
        top._thumb_refs = []

        var_only_unused = tk.BooleanVar(value=False)
        checks = {}  # tên_file -> tk.BooleanVar (trạng thái được chọn)

        f_top = ttk.Frame(top)
        f_top.pack(fill="x", padx=10, pady=(10, 4))
        lbl_summary = ttk.Label(f_top, text="")
        lbl_summary.pack(side="left")
        chk_unused = ttk.Checkbutton(
            f_top, text="Chỉ hiện ảnh CHƯA dùng trong task nào", variable=var_only_unused,
            command=lambda: render_grid()
        )
        chk_unused.pack(side="right")

        f_scroll = ttk.Frame(top)
        f_scroll.pack(fill="both", expand=True, padx=10, pady=4)
        canvas = tk.Canvas(f_scroll, highlightthickness=0)
        scrollbar = ttk.Scrollbar(f_scroll, orient="vertical", command=canvas.yview)
        f_list = ttk.Frame(canvas)
        f_list.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=f_list, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _load_thumb(fname, size=56):
            path = os.path.join("templates", fname)
            try:
                img = Image.open(path)
                img.thumbnail((size, size))
                photo = ImageTk.PhotoImage(img)
                top._thumb_refs.append(photo)
                return photo
            except Exception:
                return None

        def _list_all_files():
            return sorted(
                f for f in os.listdir("templates")
                if f.lower().endswith((".png", ".jpg", ".jpeg"))
            )

        def render_grid():
            usage = self._compute_template_usage()
            all_files = _list_all_files()
            unused = [f for f in all_files if f not in usage]
            lbl_summary.config(
                text=f"Tổng {len(all_files)} ảnh  —  {len(unused)} ảnh CHƯA dùng trong task nào"
            )

            top._thumb_refs.clear()
            for w in f_list.winfo_children():
                w.destroy()

            shown = unused if var_only_unused.get() else all_files
            # Giữ nguyên lựa chọn cũ cho ảnh vẫn còn hiển thị, dọn phần đã ẩn
            for fname in list(checks.keys()):
                if fname not in shown:
                    checks.pop(fname, None)

            if not shown:
                msg = "(Không còn ảnh nào chưa dùng 🎉)" if var_only_unused.get() else "(Thư mục templates trống)"
                ttk.Label(f_list, text=msg, foreground="gray").pack(pady=12)

            for fname in shown:
                row = ttk.Frame(f_list)
                row.pack(fill="x", pady=2, padx=2)
                var = checks.setdefault(fname, tk.BooleanVar(value=False))
                ttk.Checkbutton(row, variable=var).pack(side="left")
                thumb = _load_thumb(fname)
                if thumb:
                    tk.Label(row, image=thumb, bg="#212121").pack(side="left", padx=4)
                else:
                    tk.Label(row, text="(?)", width=8, bg="#212121", fg="gray").pack(side="left", padx=4)
                ttk.Label(row, text=fname, width=26).pack(side="left", padx=4)
                info = usage.get(fname)
                if info:
                    used_txt = ", ".join(info["used_in"][:3]) + ("..." if len(info["used_in"]) > 3 else "")
                    status_txt = f"Dùng {info['count']} lần — {used_txt}"
                    fg = "#2e7d32"
                else:
                    status_txt = "⚠️ CHƯA dùng trong task nào"
                    fg = "#c0392b"
                ttk.Label(row, text=status_txt, foreground=fg).pack(side="left", padx=4)

        def select_all(state):
            for var in checks.values():
                var.set(state)

        def _delete_files(names):
            errors = []
            for fname in names:
                try:
                    os.remove(os.path.join("templates", fname))
                except Exception as e:
                    errors.append(f"{fname}: {e}")
                checks.pop(fname, None)
            if errors:
                messagebox.showerror(
                    "Lỗi", "Một số ảnh không xoá được:\n" + "\n".join(errors), parent=top
                )

        def delete_selected():
            names = [f for f, v in checks.items() if v.get()]
            if not names:
                messagebox.showinfo("Lưu ý", "Chưa chọn ảnh nào để xoá.", parent=top)
                return
            if not messagebox.askyesno(
                "Xác nhận",
                f"Xoá {len(names)} ảnh đã chọn khỏi thư mục templates/?\n"
                "Hành động này KHÔNG thể hoàn tác!",
                parent=top,
            ):
                return
            _delete_files(names)
            render_grid()

        def delete_all_unused():
            usage = self._compute_template_usage()
            unused = [f for f in _list_all_files() if f not in usage]
            if not unused:
                messagebox.showinfo("Lưu ý", "Không có ảnh nào chưa dùng.", parent=top)
                return
            if not messagebox.askyesno(
                "Xác nhận",
                f"Xoá TẤT CẢ {len(unused)} ảnh KHÔNG dùng trong task nào?\n"
                "Hành động này KHÔNG thể hoàn tác!",
                parent=top,
            ):
                return
            _delete_files(unused)
            render_grid()

        f_btn = ttk.Frame(top)
        f_btn.pack(fill="x", padx=10, pady=8)
        ttk.Button(f_btn, text="☑ Chọn Tất Cả (đang hiện)", command=lambda: select_all(True)).pack(side="left", padx=2)
        ttk.Button(f_btn, text="☐ Bỏ Chọn Tất Cả", command=lambda: select_all(False)).pack(side="left", padx=2)
        ttk.Button(f_btn, text="🗑 Xoá Đã Chọn", command=delete_selected).pack(side="left", padx=8)
        ttk.Button(f_btn, text="🗑 Xoá TẤT CẢ Ảnh Chưa Dùng", command=delete_all_unused).pack(side="left", padx=2)
        ttk.Button(f_btn, text="✔ Đóng", command=top.destroy).pack(side="right", padx=4)

        render_grid()
        top.wait_window()

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
            # TRƯỚC ĐÂY: luôn đổi templates[0] (ảnh ĐẦU TIÊN) dù đang xem
            # ảnh nào trong nhóm qua ◀/▶ -> dễ đổi NHẦM ảnh khác. Nay đổi
            # ĐÚNG ảnh đang xem (active_inspect_group_idx).
            templates = step["templates"]
            gidx = getattr(self, "active_inspect_group_idx", 0)
            if not templates:
                templates.append(new_name)
            elif 0 <= gidx < len(templates):
                templates[gidx] = new_name
            else:
                templates[0] = new_name
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


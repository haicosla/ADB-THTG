"""
dashboard_tasks.py — Nạp/hiển thị danh mục Hoạt Động (task_registry.json) theo từng MỤC, theo dõi file để tự nạp lại khi có Hoạt Động mới đăng ký, mở lại chương trình soạn kịch bản cũ (LD Macro Studio), các nút chức năng nhanh, và popup 'Chọn Hành Động Để Chạy'.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import os
import sys
import json
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import window_geometry as wg

import task_registry
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, CategorySection, FlowBar, _bind_esc_close


class TaskMixin:
    # ================= NẠP DANH MỤC TÁC VỤ =================
    def reload_tasks(self):
        _warnings = []
        self.tasks = task_registry.load_registry(warnings_out=_warnings)
        for w in _warnings:
            self._log("error", f"⚠️ {w}")
            messagebox.showwarning(
                "task_registry.json bị lỗi - đã tự khôi phục",
                w + "\n\nKiểm tra lại Tên hiển thị/Mục/Thứ tự đã tuỳ chỉnh cho các Hoạt Động (nếu "
                    "có) trước khi lưu thêm gì mới.", parent=self.root)
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.task_vars = {}
        self.task_status_lbl = {}
        self.task_progress = {}

        if not self.tasks:
            tk.Label(
                self.list_frame,
                text="Chưa tìm thấy tác vụ nào trong thư mục tasks/.\n\n"
                     "Bấm '➕ Tạo Hoạt Động' để mở LD Macro Studio, soạn kịch\n"
                     "bản rồi Lưu Kịch Bản vào tasks/ - Dashboard tự nhận làm\n"
                     "1 Hoạt Động, KHÔNG cần đăng ký thủ công nữa.",
                bg=COL_BG, fg=COL_TEXT_MUTED, font=("Segoe UI", 11), justify="center"
            ).pack(pady=40)
            self._log("info", "Danh mục tác vụ trống (chưa có file .json nào trong tasks/).")
            return

        groups = {}
        order_keys = []
        for t in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0))):
            muc = t.get("muc") or "Chưa phân loại"
            if muc not in groups:
                groups[muc] = []
                order_keys.append(muc)
            groups[muc].append(t)

        # Áp thứ tự Mục người dùng đã tự sắp xếp ở '🔀 Sắp Xếp Hành Động'
        # (nếu có) THAY CHO thứ tự bảng chữ cái mặc định ở trên - Mục nào
        # MỚI xuất hiện (chưa từng nằm trong lần sắp xếp trước) vẫn giữ
        # đúng vị trí bảng chữ cái tương đối như cũ, không bị dồn hẳn ra
        # đầu/cuối một cách khó hiểu.
        muc_order_override = getattr(self, "_muc_order_override", None) or []
        if muc_order_override:
            ordered = [m for m in muc_order_override if m in groups]
            remaining = [m for m in order_keys if m not in ordered]
            order_keys = ordered + remaining

        for idx, muc in enumerate(order_keys):
            self._build_category_section(muc, groups[muc], show_shop_button=(idx == 0))

        self._log("info", f"Đã nạp {len(self.tasks)} tác vụ trong {len(groups)} mục.")

    def _build_category_section(self, muc, entries, show_shop_button=False):
        section = CategorySection(
            self.list_frame, title=muc, count=len(entries),
            show_shop_button=show_shop_button,
            on_shop_click=lambda m=muc: self._open_shop_settings(m)
        )
        section.pack(fill="x", padx=8, pady=6, anchor="n")

        for i, entry in enumerate(entries):
            task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", str(i)))
            var = tk.BooleanVar(value=bool(entry.get("mac_dinh_bat", True)))
            self.task_vars[task_id] = var
            self.task_progress[task_id] = {"total": 0, "done": 0, "error": 0, "running": 0, "stopped": 0}

            row = tk.Frame(section.body, bg=COL_PANEL)
            row.grid(row=i // 3, column=i % 3, sticky="w", padx=10, pady=5)

            DarkCheck(row, entry.get("ten_hien_thi", task_id), var, bg=COL_PANEL).pack(side="left")
            status_lbl = tk.Label(row, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"))
            status_lbl.pack(side="left", padx=6)
            self.task_status_lbl[task_id] = status_lbl

        for col in range(3):
            section.body.grid_columnconfigure(col, weight=1, uniform="task_col")

        section.set_select_all_command(lambda v, es=entries: self._set_category_checks(es, v))

    def _set_category_checks(self, entries, value):
        for e in entries:
            task_id = e.get("id") or task_registry.make_task_id(e.get("file_json", ""))
            var = self.task_vars.get(task_id)
            if var:
                var.set(value)

    def _set_all_checks(self, value):
        for var in self.task_vars.values():
            var.set(value)

    # ================= SẮP XẾP HÀNH ĐỘNG (kéo thả Mục/Hoạt Động, đổi tên, chuyển nhóm) =================
    def _open_arrange_tasks_dialog(self):
        """Popup '🔀 Sắp Xếp Hành Động' - làm việc trên 1 danh sách PHẲNG
        `flat` (mỗi phần tử là 1 khung 'muc' HOẶC 1 dòng 'task', ĐÚNG THEO
        THỨ TỰ hiển thị từ trên xuống - Mục của 1 Tác Vụ = khung 'muc' GẦN
        NHẤT phía TRƯỚC nó trong `flat`, không lưu `muc` cố định ở đâu
        khác cho tới lúc Lưu):
          - Kéo tay cầm '⠿' của 1 KHUNG MỤC: dời CẢ KHỐI (khung + toàn bộ
            Tác Vụ đang nằm trong) tới vị trí mới - đổi thứ tự Mục.
          - Kéo tay cầm '⠿' của 1 HOẠT ĐỘNG: thả vào bất kỳ đâu, kể cả
            NGAY DƯỚI 1 khung Mục khác - Tác Vụ đó coi như đã CHUYỂN SANG
            MỤC MỚI (không giới hạn chỉ đổi thứ tự trong cùng Mục như bản
            trước).
          - Gõ thẳng vào ô tên (Mục hoặc Hoạt Động) rồi Tab/click ra chỗ
            khác (hoặc Enter) để ĐỔI TÊN - chỉ sửa `item["name"]`/
            entry["ten_hien_thi"] ngay trong bộ nhớ, CHƯA ghi ra file.
          - '➕ Mục Mới': thêm 1 khung Mục trống ở cuối để kéo Hoạt Động
            vào (dùng khi muốn tách 1 nhóm hoàn toàn mới).

        CHỈ thật sự ghi ra task_registry.json/cài đặt app khi bấm '💾 Lưu'
        (xem _save_and_close) - đóng cửa sổ bằng nút 'Đóng (không lưu)'
        hoặc phím Esc sẽ KHÔNG đụng gì tới self.tasks/file thật."""
        if not self.tasks:
            messagebox.showinfo("Chưa có Hoạt Động", "Chưa có Hoạt Động nào để sắp xếp.")
            return

        win = tk.Toplevel(self.root)
        win.title("Sắp Xếp Hành Động")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "arrange_tasks", default="640x660")
        win.minsize(460, 380)
        _bind_esc_close(win)
        wg.autosave(win, "arrange_tasks")

        tk.Label(win, text="🔀 Sắp Xếp Hành Động", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(
            win,
            text="Giữ tay cầm '⠿' rồi RÊ CHUỘT để đổi chỗ: kéo 1 khung Mục để đổi thứ tự Mục (mang theo cả "
                 "Hoạt Động bên trong); kéo 1 Hoạt Động rồi thả vào Mục khác để CHUYỂN NHÓM. Gõ thẳng vào ô "
                 "tên để ĐỔI TÊN Mục/Hoạt Động. '➕ Mục Mới' để tạo 1 Mục trống rồi kéo Hoạt Động vào. Nhớ "
                 "bấm '💾 Lưu' để áp dụng - đóng cửa sổ không bấm Lưu sẽ KHÔNG đổi gì.",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=600, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        bottom_bar = FlowBar(win, bg=COL_PANEL)
        bottom_bar.pack(side="bottom", fill="x", padx=14, pady=(0, 14))

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=(0, 6))
        vbar.pack(side="right", fill="y", padx=(0, 6), pady=(0, 6))

        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # ----- Dựng `flat` ban đầu từ self.tasks (entry vẫn là ĐÚNG dict
        # object bên trong self.tasks, không copy - chỉ ĐỔI CHỖ/đổi field
        # "name"/"ten_hien_thi" ngay trên đó, KHÔNG đụng "muc"/"thu_tu"
        # thật cho tới lúc Lưu). -----
        groups = {}
        order_keys = []
        for t in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0))):
            muc = t.get("muc") or "Chưa phân loại"
            if muc not in groups:
                groups[muc] = []
                order_keys.append(muc)
            groups[muc].append(t)

        muc_order_override = getattr(self, "_muc_order_override", None) or []
        if muc_order_override:
            ordered = [m for m in muc_order_override if m in groups]
            remaining = [m for m in order_keys if m not in ordered]
            order_keys = ordered + remaining

        flat = []
        for muc in order_keys:
            flat.append({"kind": "muc", "name": muc})
            for entry in groups[muc]:
                flat.append({"kind": "task", "entry": entry})

        def _save_and_close(close_after=True):
            new_order_keys = []
            new_groups = {}
            current_muc = None
            for item in flat:
                if item["kind"] == "muc":
                    current_muc = (item["name"] or "").strip() or "Chưa phân loại"
                    if current_muc not in new_groups:
                        new_groups[current_muc] = []
                        new_order_keys.append(current_muc)
                else:
                    if current_muc is None:
                        continue  # an toàn - Hoạt Động luôn nằm sau ít nhất 1 khung Mục
                    new_groups[current_muc].append(item["entry"])

            for muc in new_order_keys:
                for i, entry in enumerate(new_groups[muc], start=1):
                    entry["thu_tu"] = i
                    entry["muc"] = muc

            self._muc_order_override = list(new_order_keys)
            self._save_settings()
            task_registry.save_registry(self.tasks)
            self.reload_tasks()
            if close_after:
                win.destroy()

        def _add_new_muc():
            n_existing = sum(1 for x in flat if x["kind"] == "muc")
            flat.append({"kind": "muc", "name": f"Mục Mới {n_existing + 1}"})
            _redraw()

        # ----- KÉO THẢ: dùng winfo_rooty() (toạ độ MÀN HÌNH tuyệt đối) để
        # xác định dòng đang trỏ tới - y hệt cách đã dùng ở popup '🎯 Chọn
        # Hoạt Động' (xem dashboard_dialogs.py::_open_multi_select_dialog),
        # nhưng ở đây thao tác trực tiếp trên `flat` (gồm cả khung Mục lẫn
        # dòng Hoạt Động) thay vì 1 danh sách phẳng chỉ toàn Hoạt Động. -----
        _drag = {"pos": None, "hover_row": None}

        def _drag_row_at_yroot(y_root):
            children = inner.winfo_children()
            if not children:
                return None
            for idx, w in enumerate(children):
                top = w.winfo_rooty()
                bottom = top + w.winfo_height()
                if top <= y_root < bottom:
                    return idx
            return 0 if y_root < children[0].winfo_rooty() else len(children) - 1

        def _drag_clear_highlight():
            if _drag["hover_row"] is not None:
                try:
                    _drag["hover_row"].configure(highlightthickness=0)
                except Exception:
                    pass
            _drag["hover_row"] = None

        def _drag_start(pos):
            _drag["pos"] = pos

        def _drag_motion(e):
            if _drag["pos"] is None:
                return
            target = _drag_row_at_yroot(e.y_root)
            _drag_clear_highlight()
            children = inner.winfo_children()
            if target is not None and 0 <= target < len(children):
                row_w = children[target]
                row_w.configure(highlightbackground=COL_BLUE, highlightcolor=COL_BLUE, highlightthickness=2)
                _drag["hover_row"] = row_w

        def _drag_end(e):
            _drag_clear_highlight()
            src = _drag["pos"]
            _drag["pos"] = None
            if src is None or not (0 <= src < len(flat)):
                return
            target = _drag_row_at_yroot(e.y_root)
            if target is None or target == src:
                return

            item = flat[src]
            if item["kind"] == "muc":
                # Dời CẢ KHỐI (khung Mục + toàn bộ Hoạt Động ngay sau nó
                # cho tới khung Mục kế tiếp) - giữ nguyên các Hoạt Động
                # bên trong, chỉ đổi VỊ TRÍ của cả khối.
                end = src + 1
                while end < len(flat) and flat[end]["kind"] == "task":
                    end += 1
                block = flat[src:end]
                del flat[src:end]
                if target > src:
                    target -= (end - src)
                target = max(0, min(target, len(flat)))
                # Không chèn khối MỚI vào GIỮA 1 khung Mục khác và các Hoạt
                # Động của nó - lùi tới khung Mục kế tiếp nếu đang trỏ giữa.
                while target < len(flat) and flat[target]["kind"] == "task":
                    target += 1
                flat[target:target] = block
            else:
                # Kéo 1 Hoạt Động - CHO PHÉP thả vào bất kỳ vị trí nào, kể
                # cả dưới 1 khung Mục KHÁC hẳn -> Tác Vụ này coi như đã
                # CHUYỂN SANG MỤC MỚI (Mục thật sự = khung Mục gần nhất
                # phía TRƯỚC vị trí vừa thả, tính lúc bấm '💾 Lưu').
                flat.pop(src)
                if target > src:
                    target -= 1
                target = max(0, min(target, len(flat)))
                if target == 0 and flat and flat[0]["kind"] == "muc":
                    # Không cho thả LÊN TRÊN khung Mục đầu tiên - mọi Hoạt
                    # Động đều phải thuộc 1 Mục nào đó.
                    target = 1
                flat.insert(target, item)

            _redraw()

        def _redraw():
            for w in inner.winfo_children():
                w.destroy()
            for i, item in enumerate(flat):
                if item["kind"] == "muc":
                    n_tasks = 0
                    for j in range(i + 1, len(flat)):
                        if flat[j]["kind"] == "muc":
                            break
                        n_tasks += 1

                    row = tk.Frame(inner, bg=COL_PANEL_ALT, highlightbackground=COL_BORDER, highlightthickness=1)
                    row.pack(fill="x", pady=(10 if i else 2, 2), padx=2)
                    handle = tk.Label(row, text="⠿", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                                       font=("Segoe UI", 12, "bold"), cursor="fleur")
                    handle.pack(side="left", padx=(8, 6), pady=8)

                    name_var = tk.StringVar(value=item["name"])
                    entry_w = tk.Entry(row, textvariable=name_var, width=20, bg=COL_PANEL, fg=COL_TEXT,
                                        insertbackground=COL_TEXT, relief="flat", font=("Segoe UI", 10, "bold"))
                    entry_w.pack(side="left", pady=8)

                    def _commit_muc_name(item=item, name_var=name_var):
                        item["name"] = name_var.get().strip() or "Chưa phân loại"
                    entry_w.bind("<FocusOut>", lambda e, f=_commit_muc_name: f())
                    entry_w.bind("<Return>", lambda e, f=_commit_muc_name: f())

                    tk.Label(row, text=f"📁 {n_tasks} Tác Vụ", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                             font=("Segoe UI", 8)).pack(side="left", padx=(6, 0), pady=8)
                else:
                    entry = item["entry"]
                    row = tk.Frame(inner, bg=COL_PANEL)
                    row.pack(fill="x", padx=(30, 8), pady=2)
                    handle = tk.Label(row, text="⠿", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                                       font=("Segoe UI", 10), cursor="fleur")
                    handle.pack(side="left", padx=(0, 6), pady=3)

                    tid = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
                    name_var = tk.StringVar(value=entry.get("ten_hien_thi", tid))
                    entry_w = tk.Entry(row, textvariable=name_var, width=30, bg=COL_PANEL_ALT, fg=COL_TEXT,
                                        insertbackground=COL_TEXT, relief="flat", font=("Segoe UI", 9))
                    entry_w.pack(side="left", pady=3)

                    def _commit_task_name(entry=entry, tid=tid, name_var=name_var):
                        entry["ten_hien_thi"] = name_var.get().strip() or tid
                    entry_w.bind("<FocusOut>", lambda e, f=_commit_task_name: f())
                    entry_w.bind("<Return>", lambda e, f=_commit_task_name: f())

                handle.bind("<ButtonPress-1>", lambda e, i=i: _drag_start(i))
                handle.bind("<B1-Motion>", _drag_motion)
                handle.bind("<ButtonRelease-1>", _drag_end)

        _redraw()

        bottom_bar.add(RoundedButton(bottom_bar, "➕ Mục Mới", command=_add_new_muc,
                                      bg=COL_TEAL, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))
        bottom_bar.add(RoundedButton(bottom_bar, "💾 Lưu", command=lambda: _save_and_close(True),
                                      bg=COL_ACCENT, fg="#241a00", container_bg=COL_PANEL,
                                      font=("Segoe UI", 9, "bold")))
        bottom_bar.add(RoundedButton(bottom_bar, "Đóng (không lưu)", command=win.destroy,
                                      bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))

    # ================= NÚT CHỨC NĂNG NHANH =================
    def _quick_action(self, action_id):
        if action_id == "mo_bang_gia_lap":
            self._open_emulator_panel()
            return
        if action_id == "huong_dan":
            self._open_help_panel()
            return

        entry = task_registry.find_task(self.tasks, action_id)
        if not entry:
            messagebox.showinfo(
                "Chưa cấu hình",
                "Chức năng này chưa có Hoạt Động tương ứng.\n\n"
                "Cách kích hoạt: bấm '➕ Tạo Hoạt Động', soạn kịch bản, LƯU FILE "
                f"với tên đúng quy ước:\n\n    tasks/{action_id}.json\n\n"
                "Dashboard sẽ tự nhận ngay từ lần quét kế tiếp (không cần đăng "
                "ký thủ công) - ID lấy đúng tên file, và nút này sẽ chạy thẳng "
                "kịch bản đó (xem thêm ở '📖 Hướng Dẫn')."
            )
            return

        selected_emulators = self._get_selected_emulators()
        if not selected_emulators:
            messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào để chạy!")
            return

        self._start_run([entry], selected_emulators, login_entry=None)

    # ================= TẠO HOẠT ĐỘNG (mở chương trình cũ) =================
    def open_creator_tool(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            main_py = os.path.join(script_dir, "main.py")
            subprocess.Popen([sys.executable, main_py], cwd=script_dir)
            self._log("info", "Đã mở LD Macro Studio (chương trình tạo Hoạt Động) ở cửa sổ riêng.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không mở được chương trình tạo Hoạt Động:\n{e}")

    def _watch_registry(self):
        """Tự động phát hiện có gì thay đổi để nạp lại danh mục MÀ KHÔNG
        CẦN người dùng tự bấm '🔄 Quét Lại Danh Mục': trước đây chỉ theo
        dõi mtime của task_registry.json (đăng ký thủ công), nên KHÔNG
        phát hiện được lúc người dùng chỉ đơn giản THẢ 1 file .json mới
        vào tasks/ mà chưa đụng gì tới task_registry.json. Giờ theo dõi
        thêm 1 'chữ ký' của toàn bộ file .json trong tasks/ (đường dẫn +
        thời điểm sửa đổi từng file) - bất kỳ file nào được thêm/xoá/sửa
        trong tasks/ (kể cả thư mục con) đều đổi chữ ký này."""
        try:
            reg_mtime = (os.path.getmtime(task_registry.REGISTRY_PATH)
                         if os.path.exists(task_registry.REGISTRY_PATH) else None)
        except Exception:
            reg_mtime = None

        try:
            tasks_signature = tuple(sorted(
                (task_id, entry.get("file_json"), os.path.getmtime(entry["file_json"]))
                for task_id, entry in task_registry._scan_task_files().items()
            ))
        except Exception:
            tasks_signature = None

        signature = (reg_mtime, tasks_signature)
        if signature != self._last_registry_mtime:
            if not self._first_watch_tick:
                self.reload_tasks()
                self._log("info", "Đã tự động nạp lại danh mục do phát hiện thay đổi mới trong tasks/.")
            self._last_registry_mtime = signature

        self._first_watch_tick = False
        self.root.after(2000, self._watch_registry)

    # ================= CHỌN HÀNH ĐỘNG ĐỂ CHẠY (chạy nhanh 1 tác vụ) =================
    def _open_task_picker(self):
        win = tk.Toplevel(self.root)
        win.title("Chọn Hành Động Để Chạy")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "tasks_pick_action", default="440x500")
        wg.autosave(win, "tasks_pick_action")
        _bind_esc_close(win)

        tk.Label(win, text="Bấm vào 1 Hoạt Động để chạy ngay:", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

        if not self.tasks:
            tk.Label(win, text="Chưa có Hoạt Động nào được đăng ký.", bg=COL_PANEL,
                     fg=COL_TEXT_MUTED).pack(pady=20)
            return

        def _run(e):
            win.destroy()
            selected_emulators = self._get_selected_emulators()
            if not selected_emulators:
                messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào để chạy!")
                return

            # Trước đây luôn chạy thẳng KHÔNG xoay vòng ở đây, bỏ qua hẳn
            # checkbox 'Xoay Vòng Tài Khoản' - dù đang bật, bấm "Chọn Hành
            # Động Để Chạy" vẫn KHÔNG hiện bảng chọn Tài Khoản như nút '▶
            # CHẠY TẤT CẢ...' chính. Giờ đọc đúng checkbox này, mirror y
            # hệt run_selected_tasks() để hành vi nhất quán giữa 2 nút.
            if self.account_rotate_var.get():
                self._start_run_with_accounts([e], selected_emulators)
                return

            # Trước đây luôn truyền login_entry=None ở đây, nên
            # "Chọn Hành Động Để Chạy" KHÔNG BAO GIỜ chạy 'auto_login'
            # dù checkbox 'Tự Login' đang bật - khác với nút '▶ Chạy'
            # chính. Giờ đọc đúng checkbox 'Tự Login' giống hệt
            # run_selected_tasks() để hành vi nhất quán.
            login_entry = None
            if self.auto_login_var.get():
                login_entry = task_registry.find_task(self.tasks, "auto_login")
                if not login_entry:
                    self._log("warn", "Đã bật 'Tự Login' nhưng chưa có Hoạt Động với id 'auto_login' "
                                       "(xem '📖 Hướng Dẫn').")
            self._start_run([e], selected_emulators, login_entry=login_entry)

        # ----- Danh sách Hoạt Động: TÁCH THEO TỪNG MỤC (phân loại), mỗi
        # Mục có tiêu đề riêng + hàng nút LIỀN NHAU tự xuống dòng
        # (FlowBar) bên dưới - giống cách chọn Tài khoản ở popup "⚡ Log
        # Nhanh" (dashboard_accounts.py), thay cho kiểu mỗi Hoạt Động 1
        # hàng ngang riêng (label + nút "▶ Chạy" tách biệt) chiếm nhiều
        # chỗ theo chiều dọc như trước đây - bấm THẲNG vào nút là chạy
        # ngay, không cần thêm bước tick chọn rồi bấm nút Chạy riêng. -----
        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas_window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        # QUAN TRỌNG: FlowBar tự xếp nút bằng place() nên KHÔNG tự nới rộng
        # theo nút con - phải CHỦ ĐỘNG ép chiều rộng của `inner` bằng đúng
        # chiều rộng hiển thị của canvas mỗi khi canvas đổi kích thước, để
        # mỗi FlowBar con (pack fill='x' bên trong inner) nhận đúng chiều
        # rộng thật mà tính chỗ đặt nút - nếu không các nút bị "giam" trong
        # vùng ~1px và không hiển thị ra ngoài (xem giải thích gốc trong
        # dashboard_accounts.py::acc_flow).
        def _on_canvas_configure(event):
            canvas.itemconfigure(canvas_window_id, width=event.width)

        canvas.bind("<Configure>", _on_canvas_configure)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=6)
        vbar.pack(side="right", fill="y", padx=(0, 6))

        by_muc = {}
        muc_order = []
        for entry in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0))):
            muc = (entry.get("muc") or "").strip() or "Chưa phân loại"
            if muc not in by_muc:
                by_muc[muc] = []
                muc_order.append(muc)
            by_muc[muc].append(entry)

        for muc in muc_order:
            tk.Label(inner, text=f"📁 {muc}", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 4), padx=2)
            flow = FlowBar(inner, bg=COL_PANEL)
            flow.pack(fill="x")
            for entry in by_muc[muc]:
                flow.add(RoundedButton(flow, entry.get("ten_hien_thi", "?"), command=lambda e=entry: _run(e),
                                        bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                                        font=("Segoe UI", 9, "bold"), padx=10, pady=6))

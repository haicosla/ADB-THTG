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
from tkinter import ttk, messagebox, simpledialog
import window_geometry as wg

import task_registry
import activity_groups
import run_state
import scheduler
from dashboard_theme import *
from dashboard_widgets import (RoundedButton, DarkCheck, CategorySection, FlowBar, ChipOrderBar, ChipBoard,
                               _bind_esc_close, ThemedToplevel)


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
        self.task_activity = {}

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
        """Popup '🔀 Sắp Xếp Hành Động' - dạng NÚT KÉO THẢ (`ChipBoard`), làm việc trên
        danh sách `secs` = [{"name": tên Mục, "entries": [entry Hoạt Động, ...]}] ĐÚNG THEO
        THỨ TỰ hiển thị (Mục của 1 Hoạt Động = khung chứa nó, không lưu `muc` cố định ở
        đâu khác cho tới lúc Lưu):
          - Mỗi Hoạt Động là 1 NÚT: giữ + rê rồi thả để đổi chỗ, thả sang khung Mục khác
            = CHUYỂN MỤC (thanh vàng chỉ chỗ sẽ chèn vào).
          - Nút xanh tên Mục (⠿ 📁 ...): giữ + rê rồi thả để đổi thứ tự Mục (mang theo
            cả các nút Hoạt Động bên trong).
          - Bấm đúp (hoặc chuột phải) vào nút Hoạt Động / bấm ✏ ở Mục để ĐỔI TÊN - chỉ
            sửa `item["name"]`/entry["ten_hien_thi"] trong bộ nhớ, CHƯA ghi ra file.
          - '➕ Mục Mới': thêm 1 khung Mục trống ở cuối để kéo Hoạt Động vào; Mục trống
            có nút ✕ để xoá.

        CHỈ thật sự ghi ra task_registry.json/cài đặt app khi bấm '💾 Lưu'
        (xem _save_and_close) - đóng cửa sổ bằng nút 'Đóng (không lưu)'
        hoặc phím Esc sẽ KHÔNG đụng gì tới self.tasks/file thật."""
        if not self.tasks:
            messagebox.showinfo("Chưa có Hoạt Động", "Chưa có Hoạt Động nào để sắp xếp.")
            return

        win = ThemedToplevel(self.root)
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
            text="Mỗi Hoạt Động là 1 NÚT: GIỮ chuột rồi RÊ để đổi chỗ, thả sang khung Mục khác để CHUYỂN NHÓM "
                 "(thanh vàng cho biết sẽ chèn vào đâu). Kéo NÚT XANH tên Mục để đổi thứ tự Mục (mang theo cả "
                 "Hoạt Động bên trong). BẤM ĐÚP nút Hoạt Động (hoặc ✏ ở Mục) để ĐỔI TÊN - đổi tên Hoạt Động sẽ "
                 "đổi luôn TÊN FILE .json trong tasks/ và cập nhật Lịch/Nhóm/Hành Động Cuối/Sự Kiện đang dùng nó "
                 "(7 Hoạt Động hệ thống như auto_login, account_login... chỉ đổi tên hiển thị). '➕ Mục Mới' tạo 1 "
                 "Mục trống rồi kéo Hoạt Động vào. Nhớ bấm '💾 Lưu' để áp dụng - đóng cửa sổ không bấm Lưu sẽ "
                 "KHÔNG đổi gì.",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=600, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        bottom_bar = FlowBar(win, bg=COL_PANEL)
        bottom_bar.pack(side="bottom", fill="x", padx=14, pady=(0, 14))

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        # Cho khung trong rộng bằng canvas để các nút tự xuống dòng đúng bề ngang cửa sổ.
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(inner_id, width=e.width))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=(0, 6))
        vbar.pack(side="right", fill="y", padx=(0, 6), pady=(0, 6))
        # Lăn chuột do wheel_scroll.install_wheel_scroll lo (không bind_all ở đây).

        # ----- Dựng `secs` ban đầu từ self.tasks (entry vẫn là ĐÚNG dict
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

        secs = [{"name": muc, "entries": list(groups[muc])} for muc in order_keys]

        # Tên hiển thị LÚC MỞ cửa sổ - để lúc Lưu biết Hoạt Động nào vừa bị
        # đổi tên (=> đổi luôn tên file .json + cập nhật mọi nơi đang dùng).
        orig_names = {id(e): (e.get("ten_hien_thi") or e.get("id") or "")
                      for s in secs for e in s["entries"]}

        def _tid(entry):
            return entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))

        def _save_and_close(close_after=True):
            rename_report = self._apply_task_file_renames(
                [(e, orig_names.get(id(e), "")) for s in secs for e in s["entries"]])
            new_order_keys = []
            new_groups = {}
            for s in secs:
                muc = (s["name"] or "").strip() or "Chưa phân loại"
                if muc not in new_groups:
                    new_groups[muc] = []
                    new_order_keys.append(muc)
                new_groups[muc].extend(s["entries"])

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
            if rename_report:
                messagebox.showinfo("Đổi tên Hoạt Động", "\n".join(rename_report), parent=self.root)

        def _redraw():
            board.set_sections([
                {"title": s["name"], "chips": [e.get("ten_hien_thi", _tid(e)) for e in s["entries"]],
                 "tips": [_tid(e) for e in s["entries"]], "can_delete": True}
                for s in secs])

        def _on_move_chip(si, ti, dsi, dti):
            entry = secs[si]["entries"].pop(ti)
            secs[dsi]["entries"].insert(dti, entry)
            _redraw()

        def _on_move_section(src, dst):
            secs.insert(dst, secs.pop(src))
            _redraw()

        def _on_rename_chip(si, ti):
            entry = secs[si]["entries"][ti]
            tid = _tid(entry)
            new = simpledialog.askstring("Đổi tên Hoạt Động", "Tên hiển thị mới:",
                                         initialvalue=entry.get("ten_hien_thi", tid), parent=win)
            if new is not None:
                entry["ten_hien_thi"] = new.strip() or tid
                _redraw()

        def _on_rename_section(si):
            new = simpledialog.askstring("Đổi tên Mục", "Tên Mục mới:", initialvalue=secs[si]["name"], parent=win)
            if new is not None:
                secs[si]["name"] = new.strip() or "Chưa phân loại"
                _redraw()

        def _on_delete_section(si):
            if not secs[si]["entries"]:      # chỉ xoá Mục TRỐNG - Mục có Hoạt Động thì không xoá
                secs.pop(si)
                _redraw()

        board = ChipBoard(inner, on_move_chip=_on_move_chip, on_move_section=_on_move_section,
                          on_rename_chip=_on_rename_chip, on_rename_section=_on_rename_section,
                          on_delete_section=_on_delete_section, scroll_canvas=canvas, bg=COL_PANEL)
        board.pack(fill="x", expand=True)

        def _add_new_muc():
            secs.append({"name": f"Mục Mới {len(secs) + 1}", "entries": []})
            _redraw()
            win.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(1.0)

        _redraw()

        bottom_bar.add(RoundedButton(bottom_bar, "➕ Mục Mới", command=_add_new_muc,
                                      bg=COL_TEAL, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))
        bottom_bar.add(RoundedButton(bottom_bar, "💾 Lưu", command=lambda: _save_and_close(True),
                                      bg=COL_ACCENT, fg="#241a00", container_bg=COL_PANEL,
                                      font=("Segoe UI", 9, "bold")))
        bottom_bar.add(RoundedButton(bottom_bar, "Đóng (không lưu)", command=win.destroy,
                                      bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))

    def _task_rename_blocker(self):
        """Lý do KHÔNG nên đổi tên file kịch bản lúc này ('' = đổi được): đang
        có giả lập chạy/xếp hàng chờ/Sự Kiện chạy nền vì các job này giữ id cũ."""
        try:
            if getattr(self, "is_running", False) or getattr(self, "active_threads", 0):
                return "đang có Hoạt Động chạy"
            if getattr(self, "_busy_emulator_indexes", None):
                return "đang có giả lập bận (chạy tay/Hẹn Giờ)"
            if getattr(self, "_event_active_indexes", None):
                return "🎁 Sự Kiện đang chạy nền"
            with self._queue_lock:
                if any(self._emulator_job_queue.values()):
                    return "Hàng Chờ còn job"
        except Exception:
            pass
        return ""

    def _apply_task_file_renames(self, items):
        """items = [(entry, tên_hiển_thị_lúc_mở_cửa_sổ)]. Với mỗi Hoạt Động mà
        Tên hiển thị vừa bị đổi: đổi tên file .json trong tasks/ theo tên mới
        (ID = tên file nên ID đổi theo), rồi cập nhật ID ở MỌI nơi dùng nó:
        Nhóm Hành Động, Lịch Hẹn Giờ (+ Hành Động Cuối của lịch), Hành Động
        Cuối/Sự Kiện theo giả lập, bộ nhớ 'đã chạy hôm nay'. Hoạt Động hệ thống
        (task_registry.RESERVED_TASK_IDS) chỉ đổi tên hiển thị. Trả về list
        dòng thông báo (rỗng nếu không có gì đáng báo)."""
        report = []
        pending = []
        for entry, orig in items:
            new_disp = (entry.get("ten_hien_thi") or "").strip()
            if new_disp and new_disp != (orig or "").strip():
                pending.append((entry, new_disp, orig))
        if not pending:
            return report

        blocker = self._task_rename_blocker()
        if blocker:
            # Hoàn tác tên hiển thị để tên + tên file luôn khớp nhau; người dùng
            # dừng hết rồi đổi tên lại là được.
            for entry, _new_disp, orig in pending:
                entry["ten_hien_thi"] = orig
            return [f"⚠️ CHƯA đổi tên Hoạt Động nào vì {blocker}. Dừng/đợi xong rồi đổi tên lại ở "
                    "'🔀 Sắp Xếp Hành Động'. (Thứ tự/Mục vẫn được lưu.)"]

        used = {(e.get("id") or task_registry.make_task_id(e.get("file_json", ""))).casefold()
                for e in self.tasks}
        mapping = {}
        for entry, new_disp, _orig in pending:
            old_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
            if old_id in task_registry.RESERVED_TASK_IDS:
                report.append(f"ℹ️ '{old_id}' là Hoạt Động hệ thống - chỉ đổi tên hiển thị, giữ nguyên tên file.")
                continue
            new_id = task_registry.slugify_task_stem(new_disp)
            if not new_id or new_id == old_id:
                continue
            if new_id.casefold() in task_registry.RESERVED_TASK_IDS or \
                    (new_id.casefold() in used and new_id.casefold() != old_id.casefold()):
                report.append(f"⚠️ Không đổi tên file '{old_id}' -> '{new_id}': trùng tên Hoạt Động khác/tên hệ thống.")
                continue
            if not entry.get("file_json"):
                continue
            try:
                new_path = task_registry.rename_task_file(entry["file_json"], new_id)
            except Exception as ex:
                report.append(f"⚠️ Không đổi được tên file '{old_id}': {ex}")
                continue
            used.discard(old_id.casefold())
            used.add(new_id.casefold())
            entry["id"] = new_id
            entry["file_json"] = new_path
            mapping[old_id] = new_id
            report.append(f"✅ {old_id}.json -> {new_id}.json")

        if not mapping:
            return report

        # ----- cập nhật mọi nơi đang dùng id cũ -----
        try:  # Lịch Hẹn Giờ (đang nằm trong bộ nhớ, sửa tại chỗ rồi lưu)
            n_sch = 0
            for sch in getattr(self, "schedules", []) or []:
                for key in ("hoat_dong_ids", "hanh_dong_cuoi_ids"):
                    new_list, n = task_registry.replace_ids(sch.get(key), mapping)
                    if n:
                        sch[key] = new_list
                        n_sch += 1
                per_emu_final = sch.get("hanh_dong_cuoi_theo_gia_lap")
                if isinstance(per_emu_final, dict):
                    for e_key, e_list in list(per_emu_final.items()):
                        new_list, n = task_registry.replace_ids(e_list, mapping)
                        if n:
                            per_emu_final[e_key] = new_list
                            n_sch += 1
            if n_sch:
                scheduler.save_schedules(self.schedules)
        except Exception as ex:
            report.append(f"⚠️ Lỗi cập nhật Lịch Hẹn Giờ: {ex}")
        try:
            activity_groups.rename_task_ids(mapping)
        except Exception as ex:
            report.append(f"⚠️ Lỗi cập nhật Nhóm Hành Động: {ex}")
        for attr in ("_post_run_steps_by_emulator", "_event_action_steps_by_emulator"):
            try:
                cur = getattr(self, attr, None) or {}
                for k in list(cur.keys()):
                    new_list, n = task_registry.replace_ids(cur[k], mapping)
                    if n:
                        cur[k] = new_list
            except Exception as ex:
                report.append(f"⚠️ Lỗi cập nhật {attr}: {ex}")
        try:
            run_state.rename_task_ids(mapping)
        except Exception as ex:
            report.append(f"⚠️ Lỗi cập nhật bộ nhớ 'đã chạy hôm nay': {ex}")
        try:
            self._log("info", "Đổi tên file Hoạt Động + cập nhật nơi dùng: "
                      + ", ".join(f"{a}->{b}" for a, b in mapping.items()))
        except Exception:
            pass
        report.append("Đã cập nhật Nhóm Hành Động / Lịch Hẹn Giờ / Hành Động Cuối / Sự Kiện. "
                      "Nếu LD Macro Studio đang mở đúng kịch bản vừa đổi tên, hãy đóng/mở lại bằng tên mới "
                      "(đừng Lưu bằng tên cũ).")
        return report

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

        preset_vars = self._get_registry_preset_vars()
        self._start_run([entry], selected_emulators, login_entry=None, preset_vars=preset_vars)

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

        try:
            manual_signature = task_registry.manual_file_states()
        except Exception:
            manual_signature = None

        signature = (reg_mtime, tasks_signature, manual_signature)
        if signature != self._last_registry_mtime:
            if not self._first_watch_tick:
                self.reload_tasks()
                self._log("info", "Đã tự động nạp lại danh mục do phát hiện thay đổi mới trong tasks/.")
            self._last_registry_mtime = signature

        self._first_watch_tick = False
        self.root.after(2000, self._watch_registry)

    # ================= CHỌN HÀNH ĐỘNG ĐỂ CHẠY (chạy nhanh 1 tác vụ) =================
    def _open_task_picker(self):
        win = ThemedToplevel(self.root)
        win.title("Chọn Hành Động Để Chạy")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "tasks_pick_action", default="480x600")
        wg.autosave(win, "tasks_pick_action")
        _bind_esc_close(win)

        tk.Label(win, text="Bấm chọn 1 hoặc NHIỀU Hoạt Động (chạy theo thứ tự chọn), rồi bấm ▶ Chạy:",
                 bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 10, "bold"), wraplength=440,
                 justify="left").pack(anchor="w", padx=12, pady=(12, 6))

        # "📦 Nhóm Hành Động" (activity_groups.py) cũng chọn được ở đây như
        # 1 Hoạt Động (chạy thẳng Nhóm đó, giống nút '▶ Chạy' ở cửa sổ
        # '📦 Nhóm Hành Động'), và có thể chọn XEN KẼ với Hoạt Động thường.
        try:
            action_groups = activity_groups.load_groups()
        except Exception:
            action_groups = []

        if not self.tasks and not action_groups:
            tk.Label(win, text="Chưa có Hoạt Động hay Nhóm Hành Động nào.", bg=COL_PANEL,
                     fg=COL_TEXT_MUTED).pack(pady=20)
            return

        def _task_id(entry):
            return entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))

        def _start_tasks(entries, selected_emulators):
            """Chạy các Hoạt Động THƯỜNG theo đúng thứ tự trong `entries` - giữ nguyên hành vi cũ khi chọn
            1 Hoạt Động: có tick 'Xoay Vòng Tài Khoản' thì hiện popup chọn Tài khoản, có tick 'Tự Login'
            thì chạy 'auto_login' - mirror y hệt run_selected_tasks() để nhất quán giữa 2 nút."""
            preset_vars = self._get_registry_preset_vars()
            if self.account_rotate_var.get():
                self._start_run_with_accounts(entries, selected_emulators, preset_vars)
                return
            login_entry = None
            if self.auto_login_var.get():
                login_entry = task_registry.find_task(self.tasks, "auto_login")
                if not login_entry:
                    self._log("warn", "Đã bật 'Tự Login' nhưng chưa có Hoạt Động với id 'auto_login' "
                                       "(xem '📖 Hướng Dẫn').")
            self._start_run(entries, selected_emulators, login_entry=login_entry, preset_vars=preset_vars)

        # ----- Danh sách ĐÃ CHỌN theo thứ tự bấm: mỗi phần tử (kind, key, obj, tên) -----
        chosen = []              # [("t"/"g", key, obj, ten_hien_thi)]
        item_btns = {}           # {(kind, key): (RoundedButton, màu gốc, tên)}
        flows = []

        def _find_idx(kind, key):
            for i, c in enumerate(chosen):
                if c[0] == kind and c[1] == key:
                    return i
            return -1

        def _refresh_chosen_ui():
            for (kind, key), (btn, base_bg, name) in item_btns.items():
                i = _find_idx(kind, key)
                if i >= 0:
                    btn.bg_color = COL_GREEN
                    btn.set_text(f"{i + 1}. {name}")
                else:
                    btn.bg_color = base_bg
                    btn.set_text(name)
            for f in flows:
                try:
                    f._reflow()
                except Exception:
                    pass
            # Danh sách chạy = các NÚT kéo thả được: bấm 1 nút để bỏ, GIỮ + RÊ tới nút khác rồi nhả để ĐỔI THỨ TỰ.
            run_flow.set_chips([f"{i + 1}. {name} ✕" for i, (_k, _key, _obj, name) in enumerate(chosen)])
            run_title.config(text=f"📋 Danh sách chạy ({len(chosen)}) - bấm 1 mục để bỏ, KÉO THẢ để đổi thứ tự:"
                             if chosen else "📋 Danh sách chạy: (chưa chọn gì)")
            btn_run.set_text(f"▶ Chạy ({len(chosen)})")

        def _toggle(kind, key, obj=None, name=None):
            i = _find_idx(kind, key)
            if i >= 0:
                chosen.pop(i)
            elif obj is not None:
                chosen.append((kind, key, obj, name))
            _refresh_chosen_ui()

        def _clear_all():
            chosen.clear()
            _refresh_chosen_ui()

        def _chip_remove(pos):
            if 0 <= pos < len(chosen):
                chosen.pop(pos)
                _refresh_chosen_ui()

        def _chip_reorder(src, dst):
            # Kéo thả nút trong "Danh sách chạy": mục nguồn chiếm đúng chỗ của nút đích.
            if 0 <= src < len(chosen) and 0 <= dst < len(chosen) and src != dst:
                chosen.insert(dst, chosen.pop(src))
                _refresh_chosen_ui()

        def _run_chosen():
            items = list(chosen)
            if not items:
                messagebox.showwarning("Lưu ý", "Chưa chọn Hoạt Động nào - bấm vào các nút ở trên để chọn.",
                                       parent=win)
                return
            selected_emulators = self._get_selected_emulators()
            if not selected_emulators:
                messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào để chạy!", parent=win)
                return
            for kind, _key, obj, name in items:
                if kind == "g" and not list(obj.get("hoat_dong_ids", [])):
                    messagebox.showwarning("Lưu ý", f"Nhóm '{name}' chưa soạn bước nào - mở '📦 Nhóm Hành Động' "
                                                     "và bấm '🏷️' để soạn trước.", parent=win)
                    return
            win.destroy()
            if len(items) == 1:
                kind, _key, obj, name = items[0]
                if kind == "g":
                    # Có tick 'Xoay Vòng Tài Khoản' -> hiện popup chọn Tài khoản như Hoạt Động thường.
                    self._run_group_from_ui(list(obj.get("hoat_dong_ids", [])), f"📦 {name}", selected_emulators)
                else:
                    _start_tasks([obj], selected_emulators)
                return
            if all(k == "t" for k, *_ in items):
                _start_tasks([obj for _k, _key, obj, _n in items], selected_emulators)
                return
            # Có chọn Nhóm Hành Động xen kẽ -> gộp tất cả thành 1 chuỗi id theo ĐÚNG thứ tự chọn
            # (Hoạt Động = id của nó, Nhóm = "GROUP:<id>") rồi chạy như 1 Nhóm. Cách này không chạy
            # 'Tự Login' riêng trước từng Hoạt Động (giống khi chạy 1 Nhóm).
            ids = []
            for kind, key, obj, _n in items:
                ids.append(key if kind == "t" else activity_groups.GROUP_PREFIX + key)
            tag = "🔀 " + " → ".join(n for *_x, n in items)
            if len(tag) > 70:
                tag = tag[:69] + "…"
            self._run_group_from_ui(ids, tag, selected_emulators)

        # ----- Thanh DƯỚI CÙNG (pack TRƯỚC vùng cuộn để luôn chiếm sẵn chỗ): list chạy + nút, xếp HÀNG NGANG -----
        bottom = tk.Frame(win, bg=COL_PANEL)
        bottom.pack(side="bottom", fill="x", padx=12, pady=(0, 10))
        btn_flow = FlowBar(bottom, bg=COL_PANEL)
        btn_flow.pack(side="bottom", fill="x", pady=(6, 0))
        run_flow = ChipOrderBar(bottom, on_reorder=_chip_reorder, on_click=_chip_remove, bg=COL_PANEL)
        run_flow.pack(side="bottom", fill="x")
        run_title = tk.Label(bottom, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9, "bold"))
        run_title.pack(side="bottom", anchor="w", pady=(6, 4))
        tk.Frame(bottom, bg=COL_BORDER, height=1).pack(side="bottom", fill="x")

        btn_run = RoundedButton(btn_flow, "▶ Chạy (0)", command=_run_chosen, bg=COL_GREEN,
                                container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"), padx=14, pady=6)
        btn_flow.add(btn_run)
        btn_flow.add(RoundedButton(btn_flow, "☐ Bỏ Chọn Tất Cả", command=_clear_all, bg=COL_GRAY_BTN,
                                    container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"), padx=12, pady=6))
        btn_flow.add(RoundedButton(btn_flow, "✖ Đóng", command=win.destroy, bg=COL_RED,
                                    container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"), padx=12, pady=6))

        # ----- Danh sách Hoạt Động: TÁCH THEO TỪNG MỤC, mỗi Mục có tiêu đề riêng + hàng nút LIỀN NHAU tự
        # xuống dòng (FlowBar). Bấm 1 nút = chọn (hiện số thứ tự + màu xanh), bấm lại = bỏ chọn. -----
        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas_window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        # QUAN TRỌNG: FlowBar tự xếp nút bằng place() nên KHÔNG tự nới rộng theo nút con - phải CHỦ ĐỘNG ép
        # chiều rộng của `inner` bằng đúng chiều rộng hiển thị của canvas mỗi khi canvas đổi kích thước (xem
        # giải thích gốc trong dashboard_accounts.py::acc_flow).
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

        def _add_item_btn(flow, kind, key, obj, name, base_bg):
            btn = RoundedButton(flow, name, command=lambda: _toggle(kind, key, obj, name), bg=base_bg,
                                container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"), padx=10, pady=6)
            flow.add(btn)
            item_btns[(kind, key)] = (btn, base_bg, name)

        if action_groups:
            tk.Label(inner, text="📦 Nhóm Hành Động", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 4), padx=2)
            gflow = FlowBar(inner, bg=COL_PANEL)
            gflow.pack(fill="x")
            flows.append(gflow)
            for g in action_groups:
                _add_item_btn(gflow, "g", g.get("id"), g, f"📦 {g.get('ten', '?')}", COL_PURPLE)

        for muc in muc_order:
            tk.Label(inner, text=f"📁 {muc}", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 4), padx=2)
            flow = FlowBar(inner, bg=COL_PANEL)
            flow.pack(fill="x")
            flows.append(flow)
            for entry in by_muc[muc]:
                _add_item_btn(flow, "t", _task_id(entry), entry, entry.get("ten_hien_thi", "?"), COL_GRAY_BTN)

        _refresh_chosen_ui()

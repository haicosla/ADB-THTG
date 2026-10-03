"""
dashboard_misc.py — Các tính năng phụ trợ lặt vặt: popup thông báo ĐÈ LÊN giả lập (dùng cho bước 'popup' trong kịch bản), cửa sổ Hướng Dẫn, Cài Đặt Mua Shop theo từng Mục, và Reset Bộ Nhớ Task Hôm Nay.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import os
import re
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from window_finder import WindowFinder
from popup_widget import show_ingame_popup
import window_geometry as wg
import run_state
import variables_registry
import task_registry
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, FlowBar, _bind_esc_close, ThemedToplevel


class MiscMixin:
    # ================= "🧩 QUẢN LÝ BIẾN" (variables_registry.py) =================
    # Khai báo biến 1 LẦN DUY NHẤT ở đây (tên, câu hỏi hiển thị, kiểu, GIÁ
    # TRỊ) - KHÔNG còn hộp thoại hỏi lúc bấm Chạy nữa (đã bỏ theo yêu cầu):
    # giá trị đặt sẵn ở đây được ÁP DỤNG THẲNG cho mọi lượt chạy, xem
    # _get_registry_preset_vars() bên dưới. Chỉ cần gõ {ten_bien} ở bất kỳ
    # ô nào hỗ trợ biến (Sửa Lặp, Gõ Chữ...) trong LD Macro Studio của BẤT
    # KỲ kịch bản nào - không cần tạo bước SET_VAR/INPUT_VAR trong từng
    # kịch bản nữa. Cột "Dùng bởi" (xem _scan_variable_usage_by_task())
    # cho biết rõ Hoạt Động nào đang tham chiếu biến đó, để dễ quản lý khi
    # có nhiều biến/nhiều kịch bản. Có nút ⬆️/⬇️ để tự sắp xếp thứ tự hiển
    # thị theo ý muốn (lưu lại đúng thứ tự này vào variables.json).
    def _get_registry_preset_vars(self):
        """Trả về TOÀN BỘ giá trị các biến đã khai báo trong "🧩 Quản Lý
        Biến" dưới dạng {tên biến: giá trị} - dùng làm preset_vars cho MỌI
        lượt CHẠY TAY (xem dashboard_run.py/dashboard_tasks.py), thay hẳn
        cho hộp thoại hỏi trước khi chạy trước đây. Hoạt Động nào không
        dùng tới 1 biến nào đó thì cứ bỏ qua, không ảnh hưởng gì."""
        return {v["var"]: v.get("default", 0) for v in variables_registry.load_variables() if v.get("var")}

    def _scan_variable_usage_by_task(self):
        """Quét TOÀN BỘ Hoạt Động đã đăng ký (self.tasks) để biết Hoạt
        Động nào đang tham chiếu {tên biến} nào (kể cả qua bước SET_VAR/
        INC_VAR/IF_VAR/INPUT_VAR hoặc chỉ đơn thuần gõ {tên biến} ở 1 ô
        bất kỳ) - trả về dict {tên biến: [tên hiển thị Hoạt Động, ...]},
        dùng để hiển thị cột "Dùng bởi" trong "🧩 Quản Lý Biến". CHỈ mang
        tính hiển thị/tham khảo, KHÔNG ảnh hưởng tới việc biến nào được áp
        dụng lúc chạy (mọi biến đã khai báo đều được áp dụng, xem
        _get_registry_preset_vars())."""
        usage = {}
        for task in getattr(self, "tasks", []):
            file_path = task.get("file_json")
            if not file_path or not os.path.exists(file_path):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_text = f.read()
                steps = json.loads(raw_text)
            except Exception:
                continue
            names_in_this_task = set()
            for s in steps:
                if s.get("var") and s.get("action") in ("set_var", "inc_var", "if_var", "input_var"):
                    names_in_this_task.add(s["var"])
            for m in re.finditer(r"\{([^{}\"]+)\}", raw_text):
                names_in_this_task.add(m.group(1))
            ten = task.get("ten_hien_thi") or task.get("id") or os.path.basename(file_path)
            for name in names_in_this_task:
                usage.setdefault(name, []).append(ten)
        return usage

    def _scan_variables_for_activity_ids(self, activity_ids):
        """Tập tên biến {tên} mà các Hoạt Động trong `activity_ids` đang
        dùng - phục vụ nút '🎯 Chỉ hiện biến của hành động đã chọn' ở hộp
        thoại 🧩 Biến riêng của lịch. `activity_ids` có thể chứa id Hoạt
        Động thường, 'GROUP:<id>' (Nhóm Hành Động - bung đệ quy, chống lặp
        vòng), hằng số __sys__* (bỏ qua). Bước 'Nhóm Ngoài' (action=group,
        file trong groups/) cũng được quét. Chỉ mang tính hiển thị/lọc -
        KHÔNG đổi biến nào được áp dụng lúc chạy."""
        import activity_groups
        tasks_by_id = {
            (t.get("id") or task_registry.make_task_id(t.get("file_json", ""))): t
            for t in getattr(self, "tasks", [])
        }
        groups_by_id = activity_groups.groups_by_id()
        names, seen_files, seen_groups = set(), set(), set()

        def _scan_text_file(path):
            if not path or path in seen_files or not os.path.exists(path):
                return
            seen_files.add(path)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw_text = f.read()
                steps = json.loads(raw_text)
            except Exception:
                return
            for m in re.finditer(r"\{([^{}\"]+)\}", raw_text):
                nm = m.group(1).strip()
                if nm and ":" not in nm:  # {rand:10-30} không phải biến
                    names.add(nm)
            for s in steps if isinstance(steps, list) else []:
                if not isinstance(s, dict):
                    continue
                if s.get("var") and s.get("action") in ("set_var", "inc_var", "if_var", "input_var", "ocr_text", "if_ocr"):
                    names.add(s["var"])
                if s.get("count_var"):
                    names.add(s["count_var"])
                if s.get("action") == "group" and s.get("group_file"):
                    _scan_text_file(os.path.join("groups", s["group_file"]))

        def _walk(ids):
            for tid in ids or []:
                if tid.startswith(activity_groups.GROUP_PREFIX):
                    gid = tid[len(activity_groups.GROUP_PREFIX):]
                    if gid in seen_groups:
                        continue
                    seen_groups.add(gid)
                    g = groups_by_id.get(gid)
                    if g:
                        _walk(g.get("hoat_dong_ids", []))
                elif tid in tasks_by_id:
                    _scan_text_file(tasks_by_id[tid].get("file_json"))
        _walk(list(activity_ids or []))
        return names

    def _open_variables_manager(self):
        entries = variables_registry.load_variables()
        usage_map = self._scan_variable_usage_by_task()
        # Thứ tự Hoạt Động dùng để sắp xếp các NHÓM theo đúng thứ tự Hoạt
        # Động xuất hiện trong self.tasks (ổn định, không đảo lộn linh
        # tinh mỗi lần mở lại Quản Lý Biến).
        task_order = [t.get("ten_hien_thi") or t.get("id") or "" for t in getattr(self, "tasks", [])]

        win = ThemedToplevel(self.root)
        win.title("Quản Lý Biến")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "variables_manager", default="1020x560")
        win.minsize(760, 380)
        _bind_esc_close(win)
        wg.autosave(win, "variables_manager")

        tk.Label(win, text="🧩 Danh Sách Biến Dùng Chung", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(
            win,
            text="Khai báo 1 LẦN DUY NHẤT ở đây (tên, câu hỏi hiển thị chỉ để ghi nhớ, kiểu, GIÁ TRỊ), rồi CHỈ CẦN "
                 "gõ {tên biến} ở bất kỳ ô nào hỗ trợ biến trong LD Macro Studio (vd 'Sửa Lặp' = {so_luong}, Gõ "
                 "Chữ...) của BẤT KỲ kịch bản nào. KHÔNG còn hộp thoại hỏi lúc bấm Chạy nữa - giá trị đặt ở đây "
                 "được dùng THẲNG mỗi lần chạy, đổi giá trị thì quay lại đây sửa rồi Lưu. Danh sách được CHIA "
                 "THÀNH TỪNG KHỐI theo Hoạt Động đang dùng biến đó (ngăn cách rõ ràng bằng thanh tiêu đề), biến "
                 "dùng chung nhiều Hoạt Động hoặc chưa dùng ở đâu xếp riêng ở cuối. Dùng nút ⬆️/⬇️ để sắp xếp thứ "
                 "tự TRONG cùng 1 khối. Đổi tên biến/chưa chắc thuộc khối nào xong thì bấm '🔄 Sắp Xếp Lại Theo "
                 "Hoạt Động' để chia khối lại đúng ngay lập tức. Chưa nhớ hết tên biến đã dùng ở đâu? Bấm '🔍 Quét "
                 "Biến Đang Dùng' để tự tìm.",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=980, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        header = tk.Frame(win, bg=COL_HEADER)
        header.pack(fill="x", padx=10)
        for text, w in (("", 4), ("Tên biến", 14), ("Câu hỏi hiển thị", 22), ("Kiểu", 7), ("Giá Trị", 10),
                        ("Ghi chú", 14)):
            tk.Label(header, text=text, bg=COL_HEADER, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"),
                     width=w, anchor="w").pack(side="left", padx=4, pady=6)
        tk.Label(header, text="", bg=COL_HEADER, width=4).pack(side="left")

        btn_bar = FlowBar(win, bg=COL_PANEL)
        btn_bar.pack(side="bottom", fill="x", padx=10, pady=8)

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 6))

        row_widgets = []
        # group_key -> (divider_frame, header_frame, header_label) - tạo 1
        # LẦN rồi dùng lại, chỉ ẩn/hiện (pack_forget/pack) theo nhóm đó
        # còn dòng nào hay không, KHÔNG tạo lại mỗi lần render để đỡ giật.
        group_headers = {}

        def _group_key_and_label(rw):
            """Xác định rw (1 dòng biến) thuộc KHỐI nào dựa theo TÊN BIẾN
            đang gõ trong ô (không phải tên lúc mở dialog) - nhờ vậy bấm
            '🔄 Sắp Xếp Lại Theo Hoạt Động' sau khi đổi tên biến sẽ chia
            đúng khối mới."""
            name = rw["var_entry"].get().strip()
            if not name:
                return ("unused",), "❓ Biến chưa đặt tên / chưa dùng ở Hoạt Động nào"
            usage = usage_map.get(name, [])
            if not usage:
                return ("unused",), "❓ Chưa dùng ở Hoạt Động nào"
            if len(usage) == 1:
                return ("task", usage[0]), f"🎯 Hoạt Động: {usage[0]}"
            return ("shared",), "🔗 Dùng chung nhiều Hoạt Động (" + ", ".join(usage) + ")"

        def _render_all():
            """Vẽ lại TOÀN BỘ danh sách, CHIA THÀNH TỪNG KHỐI rõ ràng theo
            Hoạt Động (mỗi khối có 1 thanh tiêu đề riêng ngăn cách hẳn với
            khối kế tiếp) - gọi sau mỗi lần Thêm/Xoá/Di chuyển 1 dòng, sau
            khi Quét Biến Đang Dùng, hoặc khi bấm '🔄 Sắp Xếp Lại'."""
            for rw in row_widgets:
                rw["frame"].pack_forget()
            for divider, hdr, _lbl in group_headers.values():
                divider.pack_forget()
                hdr.pack_forget()

            groups = {}
            group_labels = {}
            for rw in row_widgets:
                gk, label = _group_key_and_label(rw)
                groups.setdefault(gk, []).append(rw)
                group_labels[gk] = label

            ordered_keys = [("task", t) for t in task_order if ("task", t) in groups]
            # Hoạt Động nào có biến nhưng KHÔNG khớp task_order (vd Hoạt
            # Động vừa bị xoá khỏi self.tasks) vẫn phải hiển thị, xếp sau
            # các khối đã biết thứ tự.
            ordered_keys += [gk for gk in groups if gk[0] == "task" and gk not in ordered_keys]
            if ("shared",) in groups:
                ordered_keys.append(("shared",))
            if ("unused",) in groups:
                ordered_keys.append(("unused",))

            new_row_widgets = []
            for gk in ordered_keys:
                if gk not in group_headers:
                    divider = tk.Frame(inner, bg=COL_BORDER, height=2)
                    hdr = tk.Frame(inner, bg=COL_HEADER)
                    lbl = tk.Label(hdr, text="", bg=COL_HEADER, fg=COL_TEXT, font=("Segoe UI", 9, "bold"), anchor="w")
                    lbl.pack(fill="x", padx=8, pady=5)
                    group_headers[gk] = (divider, hdr, lbl)
                divider, hdr, lbl = group_headers[gk]
                lbl.config(text=group_labels[gk])
                divider.pack(fill="x", pady=(12, 0), padx=2)
                hdr.pack(fill="x", pady=(0, 4), padx=2)
                for rw in groups[gk]:
                    rw["frame"].pack(fill="x", pady=1, padx=(16, 2))
                    new_row_widgets.append(rw)
            row_widgets[:] = new_row_widgets

        def _move_row(rw, delta):
            idx = row_widgets.index(rw)
            jdx = idx + delta
            if not (0 <= jdx < len(row_widgets)):
                return
            other = row_widgets[jdx]
            # Chỉ cho đổi chỗ với dòng liền kề CÙNG KHỐI (Hoạt Động) - đổi
            # khác khối phải dùng '🔄 Sắp Xếp Lại Theo Hoạt Động' thay vì
            # kéo lung tung làm rối thứ tự hiển thị theo Hoạt Động.
            if _group_key_and_label(rw)[0] != _group_key_and_label(other)[0]:
                return
            row_widgets[idx], row_widgets[jdx] = row_widgets[jdx], row_widgets[idx]
            _render_all()

        def _add_row(data=None, render=True):
            data = data or {}
            row = tk.Frame(inner, bg=COL_PANEL_ALT)

            rw = {"id": data.get("id") or variables_registry.new_variable_id(), "frame": row}

            order_box = tk.Frame(row, bg=COL_PANEL_ALT, width=32)
            order_box.pack(side="left", padx=(2, 4))
            btn_up = tk.Label(order_box, text="⬆️", bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 8), cursor="hand2")
            btn_up.pack()
            btn_up.bind("<Button-1>", lambda e: _move_row(rw, -1))
            btn_down = tk.Label(order_box, text="⬇️", bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 8), cursor="hand2")
            btn_down.pack()
            btn_down.bind("<Button-1>", lambda e: _move_row(rw, 1))

            var_entry = tk.Entry(row, width=14, bg=COL_PANEL, fg=COL_TEXT, insertbackground=COL_TEXT, relief="flat")
            var_entry.insert(0, data.get("var", ""))
            var_entry.pack(side="left", padx=4, pady=4)

            label_entry = tk.Entry(row, width=22, bg=COL_PANEL, fg=COL_TEXT, insertbackground=COL_TEXT, relief="flat")
            label_entry.insert(0, data.get("label", ""))
            label_entry.pack(side="left", padx=4, pady=4)

            type_cbo = ttk.Combobox(row, values=["int", "float", "text"], state="readonly", width=6)
            type_cbo.set(data.get("var_type", "int"))
            type_cbo.pack(side="left", padx=4, pady=4)

            default_entry = tk.Entry(row, width=10, bg=COL_PANEL, fg=COL_TEXT, insertbackground=COL_TEXT, relief="flat")
            default_entry.insert(0, str(data.get("default", "")))
            default_entry.pack(side="left", padx=4, pady=4)

            note_entry = tk.Entry(row, width=12, bg=COL_PANEL, fg=COL_TEXT, insertbackground=COL_TEXT, relief="flat")
            note_entry.insert(0, data.get("ghi_chu", ""))
            note_entry.pack(side="left", padx=4, pady=4)

            rw.update({"var_entry": var_entry, "label_entry": label_entry, "type_cbo": type_cbo,
                       "default_entry": default_entry, "note_entry": note_entry})

            def _delete():
                row.destroy()
                row_widgets.remove(rw)
                _render_all()

            RoundedButton(row, "🗑", command=_delete, bg=COL_RED, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 8, "bold"), padx=6, pady=2).pack(side="left", padx=4)
            row_widgets.append(rw)
            if render:
                _render_all()

        for e in entries:
            _add_row(e, render=False)
        _render_all()

        def _save_all():
            new_entries = []
            seen_names = set()
            for rw in row_widgets:
                name = rw["var_entry"].get().strip()
                if not name:
                    continue
                if name in seen_names:
                    messagebox.showerror("Lỗi", f"Tên biến '{name}' bị lặp lại - mỗi tên biến chỉ được khai báo "
                                                 f"1 dòng.", parent=win)
                    return
                seen_names.add(name)
                var_type = rw["type_cbo"].get() or "int"
                default_raw = rw["default_entry"].get().strip()
                try:
                    if var_type == "int":
                        default_val = int(float(default_raw)) if default_raw else 0
                    elif var_type == "float":
                        default_val = float(default_raw) if default_raw else 0.0
                    else:
                        default_val = default_raw
                except ValueError:
                    messagebox.showerror("Lỗi", f"Giá trị của biến '{name}' không hợp lệ với kiểu đã chọn!",
                                          parent=win)
                    return
                new_entries.append({
                    "id": rw["id"], "var": name,
                    "label": rw["label_entry"].get().strip() or f"Biến '{name}'",
                    "var_type": var_type, "default": default_val,
                    "ghi_chu": rw["note_entry"].get().strip()
                })
            variables_registry.save_variables(new_entries)
            messagebox.showinfo("Đã lưu", f"Đã lưu {len(new_entries)} biến. Áp dụng ngay từ lượt Chạy tiếp theo, "
                                           f"không cần khởi động lại Dashboard.", parent=win)

        def _scan_used_variables():
            """Quét TOÀN BỘ file .json trong thư mục tasks/ (mọi kịch bản
            của cả dự án, KHÔNG chỉ Hoạt Động đang tick chạy) để tìm mọi
            {tên_biến} được tham chiếu ở bất kỳ đâu, CỘNG với tên biến của
            các bước SET_VAR/INC_VAR/IF_VAR/INPUT_VAR - thêm luôn 1 dòng
            TRỐNG (chưa có Câu hỏi hiển thị, giá trị 0) cho MỌI tên chưa
            có sẵn trong danh sách đang mở, để người dùng chỉ cần điền nốt
            Câu hỏi/Giá Trị thay vì phải tự nhớ & gõ lại từng tên biến."""
            existing_names = {rw["var_entry"].get().strip() for rw in row_widgets if rw["var_entry"].get().strip()}
            found_names = []
            found_set = set()
            for root_dir, _dirs, files in os.walk(task_registry.TASKS_DIR):
                for fname in files:
                    if not fname.lower().endswith(".json"):
                        continue
                    fpath = os.path.join(root_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            raw_text = f.read()
                        steps = json.loads(raw_text)
                    except Exception:
                        continue
                    for s in steps:
                        if s.get("var") and s.get("action") in ("set_var", "inc_var", "if_var", "input_var"):
                            name = s["var"]
                            if name not in found_set:
                                found_set.add(name)
                                found_names.append(name)
                    for m in re.finditer(r"\{([^{}\"]+)\}", raw_text):
                        name = m.group(1)
                        if name not in found_set:
                            found_set.add(name)
                            found_names.append(name)

            new_names = [n for n in found_names if n not in existing_names]
            for n in new_names:
                _add_row({"var": n, "label": "", "var_type": "int", "default": 0,
                          "ghi_chu": "Tự phát hiện - điền Câu hỏi/Giá Trị rồi bấm Lưu"}, render=False)
            if new_names:
                _render_all()
                messagebox.showinfo("Đã quét", f"Tìm thấy {len(new_names)} biến MỚI (chưa có trong danh sách): "
                                                f"{', '.join(new_names)}\n\nĐiền Câu hỏi hiển thị/Giá Trị rồi bấm "
                                                f"'💾 Lưu'.", parent=win)
            else:
                messagebox.showinfo("Đã quét", "Không tìm thấy biến nào MỚI - mọi {tên_biến} đang dùng trong các "
                                                "kịch bản đều đã có sẵn trong danh sách.", parent=win)

        RoundedButton(btn_bar, "➕ Thêm Biến", command=lambda: _add_row(), bg=COL_BLUE, container_bg=COL_PANEL,
                      font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)
        RoundedButton(btn_bar, "🔍 Quét Biến Đang Dùng", command=_scan_used_variables, bg=COL_TEAL,
                      container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)
        RoundedButton(btn_bar, "🔄 Sắp Xếp Lại Theo Hoạt Động", command=_render_all, bg=COL_GRAY_BTN,
                      container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)
        RoundedButton(btn_bar, "💾 Lưu", command=_save_all, bg=COL_GREEN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)

    # ================= POPUP (dùng cho bước 'popup' trong kịch bản) =================
    def _show_ingame_popup(self, wf, message, duration=0, bg=None, fg=None, alpha=None, pos_box=None):
        """Hiện popup thông báo ĐÈ LÊN cửa sổ LDPlayer - phần dựng popup
        thật sự nằm chung trong popup_widget.py (dùng chung với Macro
        Studio, xem gui_run.py) để khỏi lặp code 2 nơi.

        wf: WindowFinder RIÊNG của luồng đang chạy (đa luồng nhiều giả lập
        cùng lúc, mỗi luồng phải tự biết đúng cửa sổ LDPlayer của mình).
        bg/fg/alpha: tuỳ chỉnh màu nền/chữ/độ mờ theo từng bước popup, mặc
        định nền trắng/chữ đen/mờ 50%. pos_box: vị trí/kích thước tự chọn
        (xem gui_canvas.py) - để trống thì dùng dải ngang mặc định phía
        trên khung game. Mọi lỗi bất ngờ được ghi vào Nhật Ký (self._log)
        thay vì im lặng biến mất, để còn biết đường debug tiếp nếu vẫn có
        vấn đề."""
        done_event = threading.Event() if not duration else None

        def _log_err(where, e):
            try:
                self._log("error", f"Popup lỗi ({where}): {e}")
            except Exception:
                pass

        def _do():
            show_ingame_popup(
                self.root, wf.get_render_screen_rect, message, duration,
                bg=bg, fg=fg, alpha=alpha, pos_box=pos_box,
                log_fn=_log_err, done_event=done_event,
            )

        try:
            self.root.after(0, _do)
        except Exception as e:
            _log_err("schedule _do", e)
        if done_event:
            done_event.wait()

    def _open_help_panel(self):
        win = ThemedToplevel(self.root)
        win.title("Hướng Dẫn")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "misc_help", default="580x540")
        wg.autosave(win, "misc_help")
        _bind_esc_close(win)

        txt = tk.Text(win, bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 10), wrap="word",
                      relief="flat", padx=14, pady=14)
        txt.pack(fill="both", expand=True)
        txt.insert("end", HELP_TEXT)
        txt.config(state="disabled")

    def _open_shop_settings(self, muc):
        win = ThemedToplevel(self.root)
        win.title(f"Cài Đặt Mua Shop - {muc}")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "misc_shop_settings", default="400x190")
        wg.autosave(win, "misc_shop_settings")
        _bind_esc_close(win)

        var = tk.BooleanVar(value=bool(self.shop_settings.get(muc, False)))
        tk.Label(win, text=f"Mục: {muc}", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(14, 8))
        DarkCheck(win, "Tự động mua Shop khi chạy các tác vụ trong mục này", var, bg=COL_PANEL,
                  wraplength=340).pack(anchor="w", padx=14)

        def _save():
            self.shop_settings[muc] = var.get()
            self._save_settings()
            self._log("info", f"Đã lưu cài đặt Mua Shop cho mục '{muc}': {'BẬT' if var.get() else 'TẮT'}.")
            win.destroy()

        RoundedButton(win, "💾 Lưu", command=_save, bg=COL_GREEN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9, "bold")).pack(pady=16)

    # ================= RESET BỘ NHỚ TASK =================
    def reset_daily_memory(self):
        if not messagebox.askyesno("Xác nhận", "Xóa toàn bộ ghi nhớ 'đã chạy hôm nay' của mọi Hoạt Động/giả lập?"):
            return
        run_state.reset_today()
        self._log("info", "Đã reset bộ nhớ task hôm nay.")

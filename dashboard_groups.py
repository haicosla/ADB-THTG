"""
dashboard_groups.py — "📦 Nhóm Hành Động": cửa sổ quản lý các Nhóm Hành
Động (xem activity_groups.py) - tạo/đổi tên/xoá 1 Nhóm, soạn chuỗi bước
bên trong (tái dùng đúng popup '🎯 Chọn Hoạt Động + ⚙ Thao tác hệ thống'
qua self._open_steps_editor() ở dashboard_run.py), và bấm "▶ Chạy" để
chạy thẳng 1 Nhóm trên các giả lập đang tick ở thanh trên (tái dùng
self._start_run_group()).

1 Nhóm cũng tự động CHỌN ĐƯỢC ngay trong popup "🎯 Chọn Hoạt Động" của 1
Lịch Hẹn Giờ hay của "🏁 Hành Động Cuối" (xem cách thêm `activity_items`
GROUP_PREFIX ở dashboard_schedule.py::_open_schedule_manager và
dashboard_run.py::_pick_post_run_actions) - tạo/sửa Nhóm ở ĐÂY là đủ,
không cần thao tác gì thêm ở 2 chỗ kia.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""
import tkinter as tk
from tkinter import ttk, messagebox

import window_geometry as wg
import task_registry
import account_manager
import activity_groups
from dashboard_theme import *
from dashboard_widgets import RoundedButton, FlowBar, _bind_esc_close, Tooltip


class GroupsMixin:
    def _open_group_manager(self):
        self.accounts = account_manager.load_accounts()
        groups = activity_groups.load_groups()

        # Hoạt Động thường + Nhóm KHÁC (để 1 Nhóm được phép chứa Nhóm khác
        # bên trong, tự bung đệ quy khi chạy - xem
        # dashboard_schedule.py::_build_activity_steps) - loại của chính
        # Nhóm đang mở nếu đang gọi từ dòng nào đó ra khỏi danh sách chọn
        # (tránh gợi ý tự chứa chính nó, dù có chọn nhầm cũng không lỗi gì
        # nhờ chống lặp vòng ở _build_activity_steps).
        def _activity_items_excluding(exclude_group_id=None):
            items = [
                (t.get("id") or task_registry.make_task_id(t.get("file_json", "")), t.get("ten_hien_thi", "?"))
                for t in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0)))
            ]
            group_of = {
                (t.get("id") or task_registry.make_task_id(t.get("file_json", ""))): (t.get("muc") or "")
                for t in self.tasks
            }
            for g in groups:
                if g.get("id") == exclude_group_id:
                    continue
                gid = f"{activity_groups.GROUP_PREFIX}{g.get('id')}"
                items.append((gid, f"📦 {g.get('ten', '?')}"))
                group_of[gid] = "📦 Nhóm Hành Động"
            return items, group_of

        win = tk.Toplevel(self.root)
        win.title("Nhóm Hành Động")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "group_manager", default="760x560")
        win.minsize(560, 420)
        _bind_esc_close(win)
        wg.autosave(win, "group_manager")

        tk.Label(win, text="📦 Nhóm Hành Động", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(
            win,
            text="Mỗi Nhóm gộp nhiều Hoạt Động/Hành động hệ thống (Bật/Tắt giả lập, Đăng Xuất, Đăng Nhập 1 tài "
                 "khoản) - kể cả Nhóm khác - thành 1 gói đặt tên, chạy LẦN LƯỢT ĐÚNG THỨ TỰ. 1 Hoạt Động có thể "
                 "nằm trong NHIỀU Nhóm khác nhau (vd Nhóm 1: A,B,C - Nhóm 2: B,C,D) - không ảnh hưởng lẫn nhau. "
                 "Bấm '▶ Chạy' để chạy thẳng 1 Nhóm trên các giả lập đang tick ở thanh trên, hoặc chọn Nhóm này "
                 "làm 1 'Hoạt Động' khi soạn Lịch Hẹn Giờ / Hành Động Cuối. Dùng ⬆️/⬇️ ở đầu mỗi dòng để đổi THỨ "
                 "TỰ CÁC NHÓM với nhau; bấm '🏷️' để sắp xếp/đổi thứ tự các bước BÊN TRONG 1 Nhóm.",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=720, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        # ----- Thanh nút dưới cùng - PACK TRƯỚC vùng cuộn (side='bottom')
        # để LUÔN CHIẾM SẴN chỗ, không bị khuất trên cửa sổ nhỏ (đúng quy
        # ước đã dùng ở '👥 Quản Lý Tài Khoản'/'⏰ Hẹn Giờ'). Nội dung (2
        # nút) được thêm vào SAU khi đã có đủ hàm _add_row/_save_all. -----
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

        def _save_all():
            activity_groups.save_groups(groups)

        def _redraw():
            for w in inner.winfo_children():
                w.destroy()
            if not groups:
                tk.Label(inner, text="Chưa có Nhóm Hành Động nào - bấm '➕ Nhóm Mới' bên dưới để tạo.",
                         bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9)).pack(pady=20, padx=8)
            for g in groups:
                _add_row(g)

        def _move_group(g, delta):
            """Đổi chỗ Nhóm `g` lên/xuống 1 vị trí trong danh sách `groups`
            (delta=-1: lên, +1: xuống) - đây là THỨ TỰ HIỂN THỊ/ưu tiên của
            các Nhóm, lưu lại ngay rồi vẽ lại toàn bộ danh sách."""
            idx = next((i for i, gg in enumerate(groups) if gg.get("id") == g.get("id")), None)
            if idx is None:
                return
            new_idx = idx + delta
            if new_idx < 0 or new_idx >= len(groups):
                return
            groups[idx], groups[new_idx] = groups[new_idx], groups[idx]
            _save_all()
            _redraw()

        def _add_row(g):
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=3, padx=2)

            order_col = tk.Frame(row, bg=COL_PANEL_ALT)
            order_col.pack(side="left", padx=(6, 0), pady=4)
            RoundedButton(order_col, "⬆", command=lambda g=g: _move_group(g, -1), bg=COL_GRAY_BTN,
                          container_bg=COL_PANEL_ALT, font=("Segoe UI", 7, "bold"), padx=5, pady=1).pack(pady=(0, 1))
            RoundedButton(order_col, "⬇", command=lambda g=g: _move_group(g, 1), bg=COL_GRAY_BTN,
                          container_bg=COL_PANEL_ALT, font=("Segoe UI", 7, "bold"), padx=5, pady=1).pack()

            name_var = tk.StringVar(value=g.get("ten", ""))
            entry = tk.Entry(row, textvariable=name_var, width=22, bg=COL_PANEL, fg=COL_TEXT,
                              insertbackground=COL_TEXT, relief="flat", font=("Segoe UI", 9))
            entry.pack(side="left", padx=8, pady=6)

            def _save_name(g=g, name_var=name_var):
                g["ten"] = name_var.get().strip() or "Nhóm chưa đặt tên"
                name_var.set(g["ten"])
                _save_all()
            entry.bind("<FocusOut>", lambda e: _save_name())
            entry.bind("<Return>", lambda e: _save_name())

            steps = list(g.get("hoat_dong_ids", []))

            def _steps_label(steps=steps):
                return f"🏷️{len(steps)} bước" if steps else "🏷️(trống)"

            def _steps_detail(g=g):
                items, _ = _activity_items_excluding()
                label_by_id = dict(items)
                cur = g.get("hoat_dong_ids", [])
                if not cur:
                    return "(chưa soạn bước nào)"
                return "\n".join(f"{i + 1}. {label_by_id.get(sid, sid)}" for i, sid in enumerate(cur))

            btn_steps = RoundedButton(row, _steps_label(), bg=COL_BLUE, container_bg=COL_PANEL_ALT,
                                       font=("Segoe UI", 8, "bold"), padx=6, pady=3)
            btn_steps.pack(side="left", padx=4, pady=6)
            Tooltip(btn_steps, lambda g=g: _steps_detail(g))

            def _edit_steps(g=g, btn_steps=btn_steps):
                def _on_save(chosen):
                    g["hoat_dong_ids"] = list(chosen)
                    _save_all()
                    btn_steps.set_text(f"🏷️{len(chosen)} bước" if chosen else "🏷️(trống)")
                items, group_of = _activity_items_excluding(exclude_group_id=g.get("id"))
                self._open_steps_editor(f"Soạn các bước cho Nhóm '{g.get('ten', '')}'",
                                         g.get("hoat_dong_ids", []), self.accounts, items, group_of, _on_save)
            btn_steps.command = _edit_steps

            def _run_now(g=g):
                selected_emulators = self._get_selected_emulators()
                if not selected_emulators:
                    messagebox.showwarning("Lưu ý", "Chưa tick giả lập nào ở thanh trên để chạy!")
                    return
                ids = list(g.get("hoat_dong_ids", []))
                if not ids:
                    messagebox.showwarning("Lưu ý", "Nhóm này chưa soạn bước nào - bấm '🏷️' để soạn trước.")
                    return
                self._start_run_group(ids, f"📦 {g.get('ten', '?')}", selected_emulators)
            RoundedButton(row, "▶ Chạy", command=_run_now, bg=COL_GREEN, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(side="left", padx=4, pady=6)

            def _delete(g=g, row=row):
                if not messagebox.askyesno("Xoá Nhóm", f"Xoá hẳn Nhóm '{g.get('ten', '')}'? Lịch hẹn giờ/Hành "
                                            f"Động Cuối nào đang chọn Nhóm này sẽ tự bỏ qua bước đó (không báo "
                                            f"lỗi, coi như 1 Hoạt Động đã bị xoá).", parent=win):
                    return
                groups[:] = activity_groups.remove_group(groups, g.get("id"))
                _save_all()
                row.destroy()
            RoundedButton(row, "🗑 Xoá", command=_delete, bg=COL_RED, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(side="right", padx=8, pady=6)

        _redraw()

        def _add_new():
            g = {"id": activity_groups.new_group_id(), "ten": f"Nhóm {len(groups) + 1}",
                 "hoat_dong_ids": [], "ghi_chu": ""}
            groups.append(g)
            _save_all()
            _add_row(g)
            win.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(1.0)

        bottom_bar.add(RoundedButton(bottom_bar, "➕ Nhóm Mới", command=_add_new, bg=COL_ACCENT, fg="#241a00",
                                      container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))
        bottom_bar.add(RoundedButton(bottom_bar, "Đóng", command=win.destroy, bg=COL_GRAY_BTN,
                                      container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))

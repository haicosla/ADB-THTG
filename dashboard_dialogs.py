"""
dashboard_dialogs.py — Popup dùng CHUNG bởi nhiều tính năng khác nhau (chọn Hoạt Động cho lịch, chọn Tài khoản chỉ định hậu kỳ, gán Giả Lập/Tài Khoản cho 1 lịch...): chọn nhiều mục (multi-select) với ô lọc + các nút chọn nhanh theo Nhóm.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import tkinter as tk
from tkinter import ttk, messagebox

from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, FlowBar, _bind_esc_close


class DialogsMixin:
    def _open_multi_select_dialog(self, parent, title, items, selected_ids, on_save, group_of=None):
        """Popup chọn nhiều mục bằng checkbox (dùng chung cho chọn Hoạt Động
        / chọn Tài Khoản / chọn Giả Lập khi soạn 1 lịch hẹn giờ). `items`:
        list (id, nhãn). `on_save(list_id_đã_chọn)` được gọi khi bấm Lưu.

        `group_of` (tuỳ chọn): dict {item_id: tên_nhóm} - nếu có: (1) hiển
        thị 1 hàng nút "chọn nhanh theo nhóm" (vd Clone / Acc chính, hoặc
        theo Mục của Hoạt Động), bấm 1 nút là tick hết các mục cùng nhóm đó
        ngay lập tức thay vì phải tick tay từng mục; và (2) chính danh sách
        checkbox bên dưới cũng được XẾP THEO TỪNG NHÓM (có tiêu đề nhóm ở
        giữa), dễ rà soát hơn khi danh sách dài thay vì 1 danh sách phẳng.

        LƯU Ý: hàng nút (chọn nhanh theo nhóm, Tất cả/Bỏ chọn/Lưu) dùng
        FlowBar - TỰ XUỐNG DÒNG khi cửa sổ hẹp, và hàng nút 💾 Lưu được
        pack(side='bottom') TRƯỚC khi tạo vùng cuộn - đảm bảo LUÔN hiển thị
        sẵn, không bị khuất mất cho tới khi người dùng tự kéo rộng cửa sổ
        (lỗi ở bản trước: vùng cuộn pack(expand=True) trước choán hết chỗ,
        đẩy hàng nút Lưu ra ngoài phần hiển thị của cửa sổ nhỏ)."""
        win = tk.Toplevel(parent)
        win.title(title)
        win.configure(bg=COL_PANEL)
        win.geometry("400x480")
        win.minsize(320, 260)
        win.transient(parent)
        win.grab_set()
        win.focus_set()
        _bind_esc_close(win)

        tk.Label(win, text=title, bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 11, "bold"), wraplength=380, justify="left").pack(anchor="w", padx=14, pady=(14, 2))
        count_lbl = tk.Label(win, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8))
        count_lbl.pack(anchor="w", padx=14, pady=(0, 6))

        vars_by_id = {}

        def _update_count():
            n = sum(1 for v in vars_by_id.values() if v.get())
            count_lbl.config(text=f"Đã chọn {n}/{len(vars_by_id)} mục")

        # ----- Hàng nút "chọn nhanh theo nhóm" (vd Clone / Acc chính) -----
        # Xác định danh sách nhóm TRƯỚC (cần cho cả hàng nút lẫn việc xếp
        # checklist theo nhóm bên dưới).
        groups_seen = []
        if group_of:
            for item_id, _label in items:
                g = (group_of.get(item_id) or "Chưa phân nhóm").strip() or "Chưa phân nhóm"
                if g not in groups_seen:
                    groups_seen.append(g)
        show_groups = group_of and (len(groups_seen) > 1 or (groups_seen and groups_seen[0] != "Chưa phân nhóm"))

        if show_groups:
            tk.Label(win, text="Chọn nhanh theo nhóm:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                     font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(0, 2))
            group_bar = FlowBar(win, bg=COL_PANEL)
            group_bar.pack(fill="x", padx=14, pady=(0, 6))

        # ----- Hàng nút dưới cùng (Tất cả / Bỏ chọn / Lưu) - PACK TRƯỚC vùng
        # cuộn (side='bottom') để LUÔN CHIẾM SẴN chỗ, không bị khuất. -----
        def _save():
            chosen = [iid for iid, v in vars_by_id.items() if v.get()]
            on_save(chosen)
            win.destroy()
            messagebox.showinfo("Đã chọn", f"Đã chọn {len(chosen)} mục cho '{title}'.\n"
                                            f"Nhớ bấm 💾 ở dòng lịch để lưu lại toàn bộ.", parent=parent)

        btn_bar = FlowBar(win, bg=COL_PANEL)
        btn_bar.pack(side="bottom", fill="x", padx=14, pady=10)
        btn_bar.add(RoundedButton(btn_bar, "☑ Tất cả",
                                   command=lambda: ([v.set(True) for v in vars_by_id.values()], _update_count()),
                                   bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_bar.add(RoundedButton(btn_bar, "☐ Bỏ chọn",
                                   command=lambda: ([v.set(False) for v in vars_by_id.values()], _update_count()),
                                   bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_bar.add(RoundedButton(btn_bar, "💾 Lưu", command=_save, bg=COL_GREEN, container_bg=COL_PANEL,
                                   font=("Segoe UI", 9, "bold"), padx=12, pady=6))

        # ----- Vùng cuộn danh sách checkbox (chiếm phần còn lại) -----
        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 8))

        # Cuộn được bằng con lăn chuột khi trỏ nằm trên danh sách - trước
        # đây chỉ kéo được thanh cuộn bên phải, dễ khiến người dùng tưởng
        # nhầm là "không chọn được" các mục nằm khuất bên dưới.
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        inner.bind("<MouseWheel>", _on_mousewheel)

        if show_groups:
            def _select_group(g):
                for iid, _lbl in items:
                    grp = (group_of.get(iid) or "Chưa phân nhóm").strip() or "Chưa phân nhóm"
                    if grp == g:
                        vars_by_id[iid].set(True)
                _update_count()

            for g in groups_seen:
                group_bar.add(RoundedButton(group_bar, f"☑ {g}", command=lambda g=g: _select_group(g),
                                             bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"),
                                             padx=8, pady=3))

        if not items:
            tk.Label(inner, text="(Không có mục nào)", bg=COL_PANEL, fg=COL_TEXT_MUTED).pack(anchor="w", pady=10)
        elif show_groups:
            # Xếp checklist THEO TỪNG NHÓM (có tiêu đề nhóm) thay vì 1 danh
            # sách phẳng - dễ rà soát hơn khi có nhiều mục thuộc nhiều nhóm.
            items_by_group = {g: [] for g in groups_seen}
            for item_id, label in items:
                g = (group_of.get(item_id) or "Chưa phân nhóm").strip() or "Chưa phân nhóm"
                items_by_group[g].append((item_id, label))
            for g in groups_seen:
                tk.Label(inner, text=f"— {g} —", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                         font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 2), padx=2)
                for item_id, label in items_by_group[g]:
                    v = tk.BooleanVar(value=item_id in selected_ids)
                    vars_by_id[item_id] = v
                    chk = DarkCheck(inner, label, v, command=_update_count, bg=COL_PANEL, wraplength=300)
                    chk.pack(anchor="w", pady=2, padx=2, fill="x")
                    chk.bind("<MouseWheel>", _on_mousewheel)
        else:
            for item_id, label in items:
                v = tk.BooleanVar(value=item_id in selected_ids)
                vars_by_id[item_id] = v
                chk = DarkCheck(inner, label, v, command=_update_count, bg=COL_PANEL, wraplength=300)
                chk.pack(anchor="w", pady=2, padx=2, fill="x")
                chk.bind("<MouseWheel>", _on_mousewheel)
        _update_count()

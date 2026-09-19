"""
dashboard_dialogs.py — Popup dùng CHUNG bởi nhiều tính năng khác nhau (chọn Hoạt Động cho lịch, chọn Tài khoản xoay vòng, gán Giả Lập/Tài Khoản cho 1 lịch...): chọn nhiều mục (multi-select) VÀ SẮP XẾP ĐƯỢC THỨ TỰ CHẠY, có ô lọc theo Nhóm.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import tkinter as tk
from tkinter import ttk, messagebox

from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, FlowBar, _bind_esc_close
import window_geometry as wg


class DialogsMixin:
    def _open_multi_select_dialog(self, parent, title, items, selected_ids, on_save, group_of=None):
        """Popup chọn nhiều mục bằng checkbox, CÓ SẮP XẾP ĐƯỢC THỨ TỰ CHẠY
        (dùng chung cho chọn Hoạt Động / chọn Tài Khoản khi soạn 1 lịch hẹn
        giờ hoặc xoay vòng tài khoản). `items`: list (id, nhãn).

        `selected_ids`: danh sách (hoặc set) id đã chọn SẴN - nếu là 1
        LIST thì ĐÚNG THỨ TỰ trong đó sẽ được giữ lại làm thứ tự chạy ban
        đầu khi mở lại popup; nếu là set thì thứ tự ban đầu không đảm bảo
        (chỉ ảnh hưởng lúc MỞ LẠI, không ảnh hưởng gì tới việc sắp xếp lúc
        đang thao tác trong popup).

        `on_save(list_id_đã_chọn)` được gọi khi bấm Lưu, LUÔN trả về 1
        LIST theo ĐÚNG THỨ TỰ người dùng đã sắp xếp (không phải thứ tự
        trong `items`) - bên gọi cần LƯU LẠI list này (không được tự ý
        đổi lại thành set/dict rồi mất thứ tự).

        Bố cục:
          - CỘT TRÁI: checklist tick chọn (lọc theo Nhóm nếu có `group_of`),
            y hệt bản cũ.
          - CỘT PHẢI "▶ Thứ tự chạy": liệt kê CHÍNH XÁC các mục đã tick,
            theo đúng thứ tự sẽ chạy (trên chạy trước, dưới chạy sau), kèm
            nút ⬆️/⬇️ để đổi chỗ và ✕ để bỏ chọn nhanh. Tick/bỏ tick ở cột
            trái sẽ tự thêm mục vào CUỐI cột phải / bỏ khỏi cột phải; muốn
            đổi thứ tự thì dùng nút ⬆️/⬇️ ở cột phải.

        `group_of` (tuỳ chọn): dict {item_id: tên_nhóm} - nếu có: (1) hiển
        thị 1 hàng nút "chọn nhanh theo nhóm" (vd Clone / Acc chính, hoặc
        theo Mục của Hoạt Động), bấm 1 nút là tick hết các mục cùng nhóm đó
        ngay lập tức (mục nào CHƯA có trong thứ tự sẽ được thêm vào CUỐI,
        mục đã có giữ nguyên vị trí); và (2) chính danh sách checkbox cột
        trái cũng được XẾP THEO TỪNG NHÓM (có tiêu đề nhóm ở giữa), dễ rà
        soát hơn khi danh sách dài thay vì 1 danh sách phẳng.

        LƯU Ý: hàng nút (chọn nhanh theo nhóm, Tất cả/Bỏ chọn/Lưu) dùng
        FlowBar - TỰ XUỐNG DÒNG khi cửa sổ hẹp, và hàng nút 💾 Lưu được
        pack(side='bottom') TRƯỚC khi tạo vùng cuộn - đảm bảo LUÔN hiển thị
        sẵn, không bị khuất mất cho tới khi người dùng tự kéo rộng cửa sổ
        (lỗi ở bản trước: vùng cuộn pack(expand=True) trước choán hết chỗ,
        đẩy hàng nút Lưu ra ngoài phần hiển thị của cửa sổ nhỏ)."""
        win = tk.Toplevel(parent)
        win.title(title)
        win.configure(bg=COL_PANEL)
        _geo_name = wg.slug_name("multiselect", title)
        wg.restore_geometry(win, _geo_name, default="680x520")
        win.minsize(460, 320)
        wg.autosave(win, _geo_name)
        win.transient(parent)
        win.grab_set()
        win.focus_set()
        _bind_esc_close(win)

        tk.Label(win, text=title, bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 11, "bold"), wraplength=650, justify="left").pack(anchor="w", padx=14, pady=(14, 2))
        count_lbl = tk.Label(win, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8))
        count_lbl.pack(anchor="w", padx=14, pady=(0, 6))

        vars_by_id = {}
        label_by_id = {iid: lbl for iid, lbl in items}
        valid_ids = set(label_by_id.keys())
        # Thứ tự chạy HIỆN TẠI (nguồn sự thật duy nhất cho thứ tự - checkbox
        # bên trái chỉ là công cụ thêm/bớt khỏi list này). Khởi tạo từ
        # selected_ids, GIỮ NGUYÊN thứ tự được truyền vào, bỏ qua id nào
        # không còn tồn tại trong `items` (vd Hoạt Động/Tài khoản đã bị xoá).
        order_list = [iid for iid in selected_ids if iid in valid_ids]

        def _update_count():
            count_lbl.config(text=f"Đã chọn {len(order_list)}/{len(vars_by_id)} mục")

        def _add_to_order(iid):
            if iid not in order_list:
                order_list.append(iid)

        def _remove_from_order(iid):
            if iid in order_list:
                order_list.remove(iid)

        def _on_toggle(iid):
            if vars_by_id[iid].get():
                _add_to_order(iid)
            else:
                _remove_from_order(iid)
            _update_count()
            _refresh_order_panel()

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
            chosen = list(order_list)
            on_save(chosen)
            win.destroy()
            messagebox.showinfo("Đã chọn", f"Đã chọn {len(chosen)} mục cho '{title}' (đã lưu đúng thứ tự chạy).\n"
                                            f"Nhớ bấm 💾 ở dòng lịch để lưu lại toàn bộ.", parent=parent)

        def _select_all():
            for iid, v in vars_by_id.items():
                v.set(True)
                _add_to_order(iid)
            _update_count()
            _refresh_order_panel()

        def _deselect_all():
            for v in vars_by_id.values():
                v.set(False)
            order_list.clear()
            _update_count()
            _refresh_order_panel()

        btn_bar = FlowBar(win, bg=COL_PANEL)
        btn_bar.pack(side="bottom", fill="x", padx=14, pady=10)
        btn_bar.add(RoundedButton(btn_bar, "☑ Tất cả", command=_select_all,
                                   bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_bar.add(RoundedButton(btn_bar, "☐ Bỏ chọn", command=_deselect_all,
                                   bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_bar.add(RoundedButton(btn_bar, "💾 Lưu", command=_save, bg=COL_GREEN, container_bg=COL_PANEL,
                                   font=("Segoe UI", 9, "bold"), padx=12, pady=6))

        # ----- Thân cửa sổ: CỘT TRÁI (checklist, cuộn dọc) + CỘT PHẢI (thứ
        # tự chạy, cuộn dọc riêng) - 2 vùng cuộn ĐỘC LẬP nhau. -----
        body = tk.Frame(win, bg=COL_PANEL)
        body.pack(side="top", fill="both", expand=True, padx=(14, 0), pady=4)

        # --- Cột PHẢI "▶ Thứ tự chạy" - dựng TRƯỚC (pack side='right') để
        # luôn giữ được đủ chỗ cố định, cột trái sẽ co giãn chiếm phần còn
        # lại (fill='both', expand=True). ---
        right = tk.Frame(body, bg=COL_PANEL_ALT, width=230)
        right.pack(side="right", fill="y", padx=(8, 14))
        right.pack_propagate(False)

        tk.Label(right, text="▶ Thứ tự chạy (trên → dưới):", bg=COL_PANEL_ALT, fg=COL_TEXT,
                 font=("Segoe UI", 8, "bold"), wraplength=210, justify="left").pack(anchor="w", padx=6, pady=(6, 4))

        order_canvas = tk.Canvas(right, bg=COL_PANEL_ALT, highlightthickness=0)
        order_vbar = ttk.Scrollbar(right, orient="vertical", command=order_canvas.yview)
        order_inner = tk.Frame(order_canvas, bg=COL_PANEL_ALT)
        order_canvas.create_window((0, 0), window=order_inner, anchor="nw")
        order_inner.bind("<Configure>", lambda e: order_canvas.configure(scrollregion=order_canvas.bbox("all")))
        order_canvas.configure(yscrollcommand=order_vbar.set)
        order_canvas.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=(0, 6))
        order_vbar.pack(side="right", fill="y", pady=(0, 6))

        def _on_order_mousewheel(event):
            order_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        order_canvas.bind("<MouseWheel>", _on_order_mousewheel)
        order_inner.bind("<MouseWheel>", _on_order_mousewheel)

        def _move(iid, delta):
            i = order_list.index(iid)
            j = i + delta
            if 0 <= j < len(order_list):
                order_list[i], order_list[j] = order_list[j], order_list[i]
                _refresh_order_panel()

        def _remove_via_panel(iid):
            _remove_from_order(iid)
            if iid in vars_by_id:
                vars_by_id[iid].set(False)
            _update_count()
            _refresh_order_panel()

        def _refresh_order_panel():
            for w in order_inner.winfo_children():
                w.destroy()
            if not order_list:
                tk.Label(order_inner, text="(Chưa chọn mục nào)", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                         font=("Segoe UI", 8, "italic"), wraplength=200, justify="left").pack(anchor="w", padx=4, pady=6)
                return
            for pos, iid in enumerate(order_list):
                row = tk.Frame(order_inner, bg=COL_PANEL_ALT)
                row.pack(fill="x", pady=1, padx=2)
                tk.Label(row, text=f"{pos + 1}.", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                         font=("Segoe UI", 8), width=2, anchor="w").pack(side="left")
                tk.Label(row, text=label_by_id.get(iid, iid), bg=COL_PANEL_ALT, fg=COL_TEXT,
                         font=("Segoe UI", 8), anchor="w", wraplength=110, justify="left").pack(
                    side="left", padx=2, fill="x", expand=True)
                btn_up = tk.Label(row, text="⬆️", bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 8), cursor="hand2")
                btn_up.pack(side="left", padx=1)
                btn_up.bind("<Button-1>", lambda e, iid=iid: _move(iid, -1))
                btn_down = tk.Label(row, text="⬇️", bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 8), cursor="hand2")
                btn_down.pack(side="left", padx=1)
                btn_down.bind("<Button-1>", lambda e, iid=iid: _move(iid, 1))
                btn_del = tk.Label(row, text="✕", bg=COL_PANEL_ALT, fg=COL_RED, font=("Segoe UI", 8, "bold"),
                                    cursor="hand2")
                btn_del.pack(side="left", padx=(1, 4))
                btn_del.bind("<Button-1>", lambda e, iid=iid: _remove_via_panel(iid))

        # --- Cột TRÁI: checklist tick chọn (như bản cũ, chỉ đổi command) ---
        left = tk.Frame(body, bg=COL_PANEL)
        left.pack(side="left", fill="both", expand=True)

        canvas = tk.Canvas(left, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(left, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
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
                        _add_to_order(iid)
                _update_count()
                _refresh_order_panel()

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
                    v = tk.BooleanVar(value=item_id in order_list)
                    vars_by_id[item_id] = v
                    chk = DarkCheck(inner, label, v, command=lambda iid=item_id: _on_toggle(iid),
                                     bg=COL_PANEL, wraplength=260)
                    chk.pack(anchor="w", pady=2, padx=2, fill="x")
                    chk.bind("<MouseWheel>", _on_mousewheel)
        else:
            for item_id, label in items:
                v = tk.BooleanVar(value=item_id in order_list)
                vars_by_id[item_id] = v
                chk = DarkCheck(inner, label, v, command=lambda iid=item_id: _on_toggle(iid),
                                 bg=COL_PANEL, wraplength=260)
                chk.pack(anchor="w", pady=2, padx=2, fill="x")
                chk.bind("<MouseWheel>", _on_mousewheel)

        _update_count()
        _refresh_order_panel()

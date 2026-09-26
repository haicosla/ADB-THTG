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
    def _open_single_select_dialog(self, parent, title, items, on_pick):
        """Popup CHỌN 1 MỤC DUY NHẤT bằng danh sách nút bấm (khác với
        _open_multi_select_dialog - không tick chọn nhiều, không sắp thứ
        tự) - dùng khi cần chọn NHANH 1 tài khoản cụ thể (vd cho thao tác
        hệ thống "🔑 Đăng nhập tài khoản", xem `system_actions` bên dưới).
        `items`: list (id, nhãn). Bấm 1 dòng là chọn NGAY và đóng popup,
        gọi `on_pick(id)`. Có ô lọc nhanh theo tên khi danh sách dài."""
        win = tk.Toplevel(parent)
        win.title(title)
        win.configure(bg=COL_PANEL)
        _geo_name = wg.slug_name("singleselect", title)
        wg.restore_geometry(win, _geo_name, default="380x460")
        win.minsize(280, 260)
        wg.autosave(win, _geo_name)
        win.transient(parent)
        win.grab_set()
        win.focus_set()
        _bind_esc_close(win)

        tk.Label(win, text=title, bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 11, "bold"), wraplength=350, justify="left").pack(anchor="w", padx=14, pady=(14, 6))

        if len(items) > 8:
            filter_var = tk.StringVar()
            filt = tk.Entry(win, textvariable=filter_var, font=("Segoe UI", 9))
            filt.pack(fill="x", padx=14, pady=(0, 6))
            filt.focus_set()
        else:
            filter_var = None

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=(0, 10))
        vbar.pack(side="right", fill="y", padx=(0, 8), pady=(0, 10))

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        inner.bind("<MouseWheel>", _on_mousewheel)

        def _pick(iid):
            win.destroy()
            on_pick(iid)

        def _render(filter_text=""):
            for w in inner.winfo_children():
                w.destroy()
            ft = (filter_text or "").strip().lower()
            shown = [(iid, lbl) for iid, lbl in items if ft in lbl.lower()] if ft else list(items)
            if not shown:
                tk.Label(inner, text="(Không tìm thấy mục nào)", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                         font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=10)
                return
            for iid, lbl in shown:
                btn = tk.Label(inner, text=lbl, bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 9),
                                anchor="w", padx=8, pady=6, cursor="hand2")
                btn.pack(fill="x", pady=1)
                btn.bind("<Button-1>", lambda e, iid=iid: _pick(iid))
                btn.bind("<MouseWheel>", _on_mousewheel)
                btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=COL_GRAY_BTN))
                btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=COL_PANEL_ALT))

        if filter_var is not None:
            filter_var.trace_add("write", lambda *_a: _render(filter_var.get()))
        _render()

    def _open_multi_select_dialog(self, parent, title, items, selected_ids, on_save, group_of=None,
                                   allow_duplicates=False, system_actions=None, extra_labels=None):
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
            tay cầm "⠿" để KÉO THẢ đổi chỗ trực tiếp, nút ⬆️/⬇️ để đổi chỗ
            từng bước và ✕ để bỏ chọn nhanh. Tick/bỏ tick ở cột trái sẽ tự
            thêm mục vào CUỐI cột phải / bỏ khỏi cột phải; muốn đổi thứ tự
            thì kéo thả tay cầm "⠿" tới đúng vị trí muốn thả (viền xanh
            báo dòng đang trỏ tới), hoặc dùng nút ⬆️/⬇️ nếu muốn đổi từng
            bước một.

        `allow_duplicates` (mặc định False): False = mỗi mục CHỈ chọn được
        1 lần (checkbox tick/bỏ tick như bản cũ, dùng cho chọn Tài Khoản -
        chạy lặp cùng 1 tài khoản liên tiếp không hợp lý). True = mỗi mục
        có thêm nút "➕" riêng để THÊM LẠI vào cuối thứ tự chạy bao nhiêu
        lần cũng được (dùng cho chọn Hoạt Động - vd muốn chạy A, B, C, A,
        D thì tick A/B/C/D 1 lần rồi bấm thêm "➕" ở A, sau đó dùng ⬆️/⬇️ ở
        cột phải để dời bản A thứ 2 xuống đúng vị trí mong muốn). Checkbox
        vẫn hoạt động: tick lần đầu = thêm 1 bản; bỏ tick = xoá HẾT các
        bản của mục đó (không chỉ 1 bản) - muốn xoá riêng lẻ 1 bản thì dùng
        nút ✕ ở ĐÚNG DÒNG đó trong cột phải "▶ Thứ tự chạy".

        `group_of` (tuỳ chọn): dict {item_id: tên_nhóm} - nếu có: (1) hiển
        thị 1 hàng nút "chọn nhanh theo nhóm" (vd Clone / Acc chính, hoặc
        theo Mục của Hoạt Động), bấm 1 nút là tick hết các mục cùng nhóm đó
        ngay lập tức (mục nào CHƯA có trong thứ tự sẽ được thêm vào CUỐI,
        mục đã có giữ nguyên vị trí); và (2) chính danh sách checkbox cột
        trái cũng được XẾP THEO TỪNG NHÓM (có tiêu đề nhóm ở giữa), dễ rà
        soát hơn khi danh sách dài thay vì 1 danh sách phẳng.

        `system_actions` (tuỳ chọn): list các thao tác hệ thống hiển thị
        thành 1 HÀNG NÚT BẤM riêng (KHÔNG nằm trong checklist cột trái,
        không tick/bỏ tick) ngay DƯỚI hàng "Chọn nhanh theo nhóm" - mỗi
        phần tử là tuple (nhãn_nút, on_click), `on_click(add_fn)` được gọi
        khi bấm nút, TỰ QUYẾT ĐỊNH lúc nào gọi `add_fn(id, nhãn)` để thêm
        1 bước vào cuối "▶ Thứ tự chạy" (có thể mở thêm 1 popup con trước,
        vd chọn tài khoản cụ thể rồi mới add_fn - xem cách gọi ở
        dashboard_schedule.py, thao tác "🔑 Đăng nhập tài khoản").

        `extra_labels` (tuỳ chọn): dict {id: nhãn} để hiển thị ĐÚNG TÊN cho
        các id đã có sẵn trong `selected_ids` (vd lịch đã lưu từ trước) mà
        KHÔNG còn nằm trong `items` (vd id thao tác hệ thống, giờ chỉ tạo
        được qua `system_actions` chứ không còn là 1 dòng checklist) - nếu
        không truyền, các id này vẫn hiển thị ĐÚNG THỨ TỰ đã lưu nhưng
        nhãn sẽ hiện tạm bằng chính id (xấu, khó đọc).

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
        count_lbl.pack(anchor="w", padx=14, pady=(0, 2 if allow_duplicates else 6))
        if allow_duplicates:
            tk.Label(win, text="💡 Bấm ➕ cạnh 1 mục để THÊM LẠI mục đó vào cuối thứ tự chạy (chọn được nhiều "
                                "lần, vd A, B, C, A, D) - rồi dùng ⬆️/⬇️ ở cột phải để dời tới đúng vị trí.",
                     bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "italic"),
                     wraplength=650, justify="left").pack(anchor="w", padx=14, pady=(0, 6))

        vars_by_id = {}
        label_by_id = {iid: lbl for iid, lbl in items}
        if extra_labels:
            # Chỉ BỔ SUNG nhãn cho các id KHÔNG có trong checklist `items`
            # (vd thao tác hệ thống đã chọn từ trước) - không ghi đè nhãn
            # của các mục checklist bình thường.
            for iid, lbl in extra_labels.items():
                label_by_id.setdefault(iid, lbl)
        valid_ids = set(label_by_id.keys())
        # Thứ tự chạy HIỆN TẠI (nguồn sự thật duy nhất cho thứ tự - checkbox
        # bên trái chỉ là công cụ thêm/bớt khỏi list này). Khởi tạo từ
        # selected_ids, GIỮ NGUYÊN thứ tự được truyền vào, bỏ qua id nào
        # không còn tồn tại trong `items` (vd Hoạt Động/Tài khoản đã bị xoá).
        order_list = [iid for iid in selected_ids if iid in valid_ids]

        def _update_count():
            if allow_duplicates:
                n_distinct = len({iid for iid in order_list})
                count_lbl.config(text=f"Đã chọn {len(order_list)} bước ({n_distinct}/{len(vars_by_id)} mục khác nhau)")
            else:
                count_lbl.config(text=f"Đã chọn {len(order_list)}/{len(vars_by_id)} mục")

        def _add_to_order(iid):
            # allow_duplicates=True: LUÔN thêm 1 bản mới vào cuối (cho phép
            # 1 mục xuất hiện nhiều lần trong thứ tự chạy). False (mặc
            # định): chỉ thêm nếu CHƯA có (hành vi CŨ, mỗi mục 1 lần).
            if allow_duplicates or iid not in order_list:
                order_list.append(iid)

        def _remove_from_order(iid):
            # Bỏ tick checkbox = xoá HẾT các bản của mục đó (không chỉ 1
            # bản) - muốn xoá riêng lẻ 1 bản thì dùng nút ✕ ở cột phải
            # (xem _remove_at_pos), tác động ĐÚNG 1 VỊ TRÍ theo chỉ số.
            order_list[:] = [x for x in order_list if x != iid]

        def _add_extra(iid):
            """Chỉ dùng khi allow_duplicates=True - nút '➕' riêng ở mỗi
            mục trong checklist, LUÔN thêm 1 bản mới vào cuối thứ tự chạy
            dù mục đó đã có hay chưa (không phụ thuộc trạng thái checkbox)."""
            order_list.append(iid)
            if iid in vars_by_id:
                vars_by_id[iid].set(True)
            _update_count()
            _refresh_order_panel()

        def _on_toggle(iid):
            if vars_by_id[iid].get():
                _add_to_order(iid)
            else:
                _remove_from_order(iid)
            _update_count()
            _refresh_order_panel()

        def _add_system_action(iid, label):
            """Dùng bởi hàng nút `system_actions` (xem docstring ở trên) -
            LUÔN thêm 1 bước mới vào CUỐI thứ tự chạy, không qua checkbox
            (thao tác hệ thống không nằm trong checklist cột trái nữa)."""
            label_by_id[iid] = label
            order_list.append(iid)
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

        # ----- Hàng nút "⚙ Thao tác hệ thống" - NẰM NGAY DƯỚI hàng "Chọn
        # nhanh theo nhóm" ở trên (khi có `system_actions`, xem docstring).
        # Đây là NÚT BẤM (không phải checkbox) - bấm 1 phát là THÊM NGAY 1
        # bước vào cuối "▶ Thứ tự chạy" (qua _add_system_action), bấm được
        # nhiều lần thoải mái (y hệt nút ➕ ở 1 mục khi allow_duplicates). -----
        if system_actions:
            tk.Label(win, text="⚙ Thao tác hệ thống (bấm để thêm vào thứ tự chạy):", bg=COL_PANEL,
                     fg=COL_TEXT_MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=14, pady=(0, 2))
            sys_bar = FlowBar(win, bg=COL_PANEL)
            sys_bar.pack(fill="x", padx=14, pady=(0, 6))
            for act_label, on_click in system_actions:
                sys_bar.add(RoundedButton(
                    sys_bar, act_label, command=lambda on_click=on_click: on_click(_add_system_action),
                    bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=3))

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
        # lại (fill='both', expand=True). Rộng KÉO THẢ được (xem _divider
        # bên dưới) - bắt đầu ở 230px, kéo tay cầm "⋮⋮" để to/nhỏ lại tuỳ ý
        # (vd tên Hoạt Động dài, kéo rộng ra để đọc trọn không bị cắt). ---
        right = tk.Frame(body, bg=COL_PANEL_ALT, width=230)
        right.pack(side="right", fill="y", padx=(0, 14))
        right.pack_propagate(False)

        # ----- Tay cầm KÉO THẢ đổi bề rộng cột phải - đứng GIỮA 2 cột, kéo
        # sang trái để cột phải TO ra (kéo sang phải để nhỏ lại). Chỉ đổi
        # width của Frame `right` (đã pack_propagate(False) nên width đặt
        # tay mới có tác dụng), giữ trong khoảng [160, 640] cho hợp lý. -----
        divider = tk.Frame(body, bg=COL_GRAY_BTN, width=6, cursor="sb_h_double_arrow")
        divider.pack(side="right", fill="y", padx=(2, 2))
        tk.Label(divider, text="⋮", bg=COL_GRAY_BTN, fg=COL_TEXT_MUTED, font=("Segoe UI", 8)).place(
            relx=0.5, rely=0.5, anchor="center")

        _resize_state = {"dragging": False, "start_x": 0, "start_w": 230}

        def _resize_start(e):
            _resize_state["dragging"] = True
            _resize_state["start_x"] = e.x_root
            _resize_state["start_w"] = right.winfo_width()
            divider.configure(bg=COL_BLUE)

        def _resize_motion(e):
            if not _resize_state["dragging"]:
                return
            dx = _resize_state["start_x"] - e.x_root  # kéo tay cầm SANG TRÁI -> cột phải TO ra
            new_w = max(160, min(_resize_state["start_w"] + dx, 640))
            right.configure(width=new_w)
            _refresh_order_panel()  # cập nhật wraplength theo bề rộng mới ngay khi đang kéo

        def _resize_end(e):
            _resize_state["dragging"] = False
            divider.configure(bg=COL_GRAY_BTN)

        for _w in (divider,):
            _w.bind("<ButtonPress-1>", _resize_start)
            _w.bind("<B1-Motion>", _resize_motion)
            _w.bind("<ButtonRelease-1>", _resize_end)
            _w.bind("<Enter>", lambda e: divider.configure(bg=COL_BLUE))
            _w.bind("<Leave>", lambda e: None if _resize_state["dragging"] else divider.configure(bg=COL_GRAY_BTN))

        tk.Label(right, text="▶ Thứ tự chạy (trên → dưới) - kéo tay cầm ⋮ bên trái để to ra:", bg=COL_PANEL_ALT,
                 fg=COL_TEXT, font=("Segoe UI", 8, "bold"), wraplength=210, justify="left").pack(
            anchor="w", padx=6, pady=(6, 4))

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

        # ----- KÉO THẢ đổi thứ tự (bổ sung thêm cách, KHÔNG thay thế nút
        # ⬆️/⬇️ - vẫn giữ nguyên cho ai quen bấm nút hoặc dùng chuột cảm
        # ứng khó kéo chính xác). Bấm giữ chuột TRÁI vào tay cầm "⠿" ở đầu
        # 1 dòng rồi rê tới vị trí muốn thả - dòng đang rê tới được viền
        # xanh để biết thả vào đâu. Dùng winfo_rooty() (toạ độ MÀN HÌNH
        # tuyệt đối) để xác định dòng đang trỏ tới - ổn định ngay cả khi
        # cột đang cuộn dở (không phụ thuộc scrollregion/offset canvas).
        _drag = {"pos": None, "hover_row": None}

        def _drag_row_at_yroot(y_root):
            children = order_inner.winfo_children()
            if not children:
                return None
            for i, w in enumerate(children):
                top = w.winfo_rooty()
                bottom = top + w.winfo_height()
                if top <= y_root < bottom:
                    return i
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
            children = order_inner.winfo_children()
            if target is not None and 0 <= target < len(children):
                row_w = children[target]
                row_w.configure(highlightbackground=COL_BLUE, highlightcolor=COL_BLUE, highlightthickness=2)
                _drag["hover_row"] = row_w

        def _drag_end(e):
            _drag_clear_highlight()
            src = _drag["pos"]
            _drag["pos"] = None
            if src is None:
                return
            target = _drag_row_at_yroot(e.y_root)
            if target is None or target == src or not (0 <= src < len(order_list)):
                return
            item = order_list.pop(src)
            if target > src:
                target -= 1
            order_list.insert(max(0, min(target, len(order_list))), item)
            _refresh_order_panel()

        def _move(pos, delta):
            # Dùng VỊ TRÍ (pos) thay vì id - an toàn khi 1 mục xuất hiện
            # NHIỀU LẦN trong order_list (allow_duplicates=True): tra theo
            # id như bản cũ sẽ luôn đổi chỗ NHẦM bản ĐẦU TIÊN thay vì đúng
            # dòng người dùng vừa bấm.
            j = pos + delta
            if 0 <= pos < len(order_list) and 0 <= j < len(order_list):
                order_list[pos], order_list[j] = order_list[j], order_list[pos]
                _refresh_order_panel()

        def _remove_at_pos(pos):
            # Cũng dùng VỊ TRÍ - xoá ĐÚNG 1 bản tại dòng đã bấm ✕, không
            # đụng tới các bản khác của cùng mục đó (nếu allow_duplicates).
            if not (0 <= pos < len(order_list)):
                return
            iid = order_list.pop(pos)
            if iid in vars_by_id and iid not in order_list:
                # Không còn bản nào khác của mục này -> bỏ tick checkbox.
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
                row = tk.Frame(order_inner, bg=COL_PANEL_ALT, highlightthickness=0)
                row.pack(fill="x", pady=1, padx=2)
                handle = tk.Label(row, text="⠿", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                                   font=("Segoe UI", 9), cursor="fleur")
                handle.pack(side="left", padx=(2, 1))
                handle.bind("<ButtonPress-1>", lambda e, pos=pos: _drag_start(pos))
                handle.bind("<B1-Motion>", _drag_motion)
                handle.bind("<ButtonRelease-1>", _drag_end)
                tk.Label(row, text=f"{pos + 1}.", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                         font=("Segoe UI", 8), width=2, anchor="w").pack(side="left")
                # wraplength tính THEO BỀ RỘNG HIỆN TẠI của cột phải (đã
                # kéo to/nhỏ được, xem tay cầm _divider ở trên) - trừ chỗ
                # tay cầm ⠿/số thứ tự/nút ⬆️⬇️✕ chiếm khoảng ~100px.
                _wrap = max(90, right.winfo_width() - 100)
                tk.Label(row, text=label_by_id.get(iid, iid), bg=COL_PANEL_ALT, fg=COL_TEXT,
                         font=("Segoe UI", 8), anchor="w", wraplength=_wrap, justify="left").pack(
                    side="left", padx=2, fill="x", expand=True)
                btn_up = tk.Label(row, text="⬆️", bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 8), cursor="hand2")
                btn_up.pack(side="left", padx=1)
                btn_up.bind("<Button-1>", lambda e, pos=pos: _move(pos, -1))
                btn_down = tk.Label(row, text="⬇️", bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 8), cursor="hand2")
                btn_down.pack(side="left", padx=1)
                btn_down.bind("<Button-1>", lambda e, pos=pos: _move(pos, 1))
                btn_del = tk.Label(row, text="✕", bg=COL_PANEL_ALT, fg=COL_RED, font=("Segoe UI", 8, "bold"),
                                    cursor="hand2")
                btn_del.pack(side="left", padx=(1, 4))
                btn_del.bind("<Button-1>", lambda e, pos=pos: _remove_at_pos(pos))

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
                    item_row = tk.Frame(inner, bg=COL_PANEL)
                    item_row.pack(anchor="w", pady=2, padx=2, fill="x")
                    v = tk.BooleanVar(value=item_id in order_list)
                    vars_by_id[item_id] = v
                    chk = DarkCheck(item_row, label, v, command=lambda iid=item_id: _on_toggle(iid),
                                     bg=COL_PANEL, wraplength=230)
                    chk.pack(side="left", fill="x", expand=True)
                    chk.bind("<MouseWheel>", _on_mousewheel)
                    if allow_duplicates:
                        add_btn = tk.Label(item_row, text="➕", bg=COL_PANEL, fg=COL_GREEN,
                                            font=("Segoe UI", 9, "bold"), cursor="hand2")
                        add_btn.pack(side="right", padx=(2, 4))
                        add_btn.bind("<Button-1>", lambda e, iid=item_id: _add_extra(iid))
        else:
            for item_id, label in items:
                item_row = tk.Frame(inner, bg=COL_PANEL)
                item_row.pack(anchor="w", pady=2, padx=2, fill="x")
                v = tk.BooleanVar(value=item_id in order_list)
                vars_by_id[item_id] = v
                chk = DarkCheck(item_row, label, v, command=lambda iid=item_id: _on_toggle(iid),
                                 bg=COL_PANEL, wraplength=230)
                chk.pack(side="left", fill="x", expand=True)
                chk.bind("<MouseWheel>", _on_mousewheel)
                if allow_duplicates:
                    add_btn = tk.Label(item_row, text="➕", bg=COL_PANEL, fg=COL_GREEN,
                                        font=("Segoe UI", 9, "bold"), cursor="hand2")
                    add_btn.pack(side="right", padx=(2, 4))
                    add_btn.bind("<Button-1>", lambda e, iid=item_id: _add_extra(iid))

        _update_count()
        _refresh_order_panel()

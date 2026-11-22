"""
dashboard_ui.py — Xây dựng toàn bộ khung giao diện chính (toolbar trên cùng, thanh chọn giả lập, vùng cuộn danh sách Hoạt Động, các nút điều khiển CHẠY/DỪNG, khung Nhật Ký) - các hàm _build_*() được gọi 1 lần duy nhất từ DashboardApp.__init__() (xem dashboard.py).

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import tkinter as tk
from tkinter import ttk

from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, FlowBar, ToolGroup, make_separator, Tooltip
from dashboard_layout import make_paned, save_layout, build_vertical_panes, apply_saved_layout, reset_layout, DEFAULT_LOG_H
from ui_scale import S


class UIBuildMixin:
    # ================= GIAO DIỆN =================
    def _build_ui(self):
        # Hàng tiêu đề cố định phía trên; dưới nó là 4 KHUNG KÉO ĐỔI KÍCH THƯỚC (dashboard_layout.py): PHẦN ĐẦU |
        # DANH SÁCH TÁC VỤ | PHẦN CHẠY | NHẬT KÝ - kéo thanh ngăn giữa các khung để đổi chiều cao, kích thước được
        # nhớ cho lần mở sau. Danh sách tác vụ giãn theo cửa sổ, 3 khung còn lại giữ chiều cao đã kéo.
        self._build_title_row()
        body = tk.Frame(self.root, bg=COL_BG)
        body.pack(fill="both", expand=True)
        build_vertical_panes(self, body, [
            ("_pane_header", self._build_header_pane, "never", "header"),
            ("_pane_tasks", self._build_task_scroll_area, "always", "tasks"),
            ("_pane_run", self._build_bottom_controls, "never", "run"),
            ("_pane_log", self._build_log_panel, "never", "log"),
        ])
        # Mặc định nhật ký cao vừa phải; sau đó áp kích thước người dùng đã kéo lần trước (nếu có).
        try:
            self._vpane.paneconfigure(self._pane_log, height=S(DEFAULT_LOG_H))
        except Exception:
            pass
        apply_saved_layout(self)

    # ---------- Hàng tiêu đề ----------
    def _build_title_row(self):
        F9 = ("Segoe UI", 9, "bold")
        top = tk.Frame(self.root, bg=COL_BG)
        top.pack(fill="x", padx=10, pady=(10, 6))

        tk.Label(top, text="📋 DANH SÁCH TÁC VỤ AUTO", bg=COL_BG, fg=COL_TEXT,
                 font=("Segoe UI", 14, "bold")).pack(side="left")

        self.btn_create_activity = RoundedButton(
            top, "➕ Tạo Hoạt Động", command=self.open_creator_tool,
            bg=COL_ACCENT, fg="#241a00", container_bg=COL_BG,
            font=("Segoe UI", 10, "bold"), padx=16, pady=8
        )
        self.btn_create_activity.pack(side="right", padx=4)
        RoundedButton(top, "📖 Hướng Dẫn", command=lambda: self._quick_action("huong_dan"),
                      bg=COL_PURPLE, container_bg=COL_BG, font=F9, pady=8
                      ).pack(side="right", padx=4)
        # 🔍 Tỷ lệ giao diện: kéo thanh trượt 50%-200% (toàn bộ chữ + khung + nút), áp dụng sau khi mở lại app.
        self.btn_ui_scale = RoundedButton(top, "🔍 Tỷ Lệ", command=self._open_ui_scale_dialog,
                                          bg=COL_GRAY_BTN, container_bg=COL_BG, font=F9, pady=8)
        self.btn_ui_scale.pack(side="right", padx=4)
        Tooltip(self.btn_ui_scale, lambda: "🔍 Tỷ lệ giao diện (50% - 200%): thu nhỏ/phóng to toàn bộ chữ, khung, nút")
        # 🔄 Cập nhật từ GitHub (xem dashboard_update.py); đổi thành '🔄 Có bản mới vX' màu cam khi có bản mới.
        self.btn_update = RoundedButton(top, "🔄 Cập Nhật", command=self._update_clicked,
                                        bg=COL_BLUE, container_bg=COL_BG, font=F9, pady=8)
        self.btn_update.pack(side="right", padx=4)
        # 🚀 Phát hành bản cập nhật cho các máy khác (xem dashboard_publish.py / publisher.py).
        self.btn_publish = RoundedButton(top, "🚀 Phát Hành", command=self._publish_clicked,
                                         bg=COL_GREEN, container_bg=COL_BG, font=F9, pady=8)
        self.btn_publish.pack(side="right", padx=4)
        # ↔ Đặt lại kích thước các khung (kéo thanh ngăn giữa các khung để đổi chiều cao/rộng).
        btn_rl = RoundedButton(top, "↔ Đặt Lại Khung", command=lambda: reset_layout(self),
                               bg=COL_GRAY_BTN, container_bg=COL_BG, font=F9, pady=8)
        btn_rl.pack(side="right", padx=4)
        Tooltip(btn_rl, lambda: "Đặt lại kích thước các khung (Đầu / Danh sách tác vụ / Phần chạy / Nhật ký).\n"
                                "Kéo thanh ngăn mỏng giữa các khung để tự chỉnh; kích thước được nhớ cho lần mở sau.")

    # ---------- PHẦN ĐẦU: các nhóm nút + bảng Hành động tiếp theo + thanh giả lập ----------
    def _build_header_pane(self, parent):
        wrap = tk.Frame(parent, bg=COL_BG)
        # Thanh giả lập pack DƯỚI trước -> khung đầu bị kéo thấp thì phần nhóm nút bị cắt chứ thanh giả lập vẫn hiện.
        emu = tk.Frame(wrap, bg=COL_BG)
        emu.pack(side="bottom", fill="x", padx=10, pady=(0, 6))
        self._build_emulator_bar(emu)

        # Ngang: [khối nút 2x2 thẳng cột] | [📋 HÀNH ĐỘNG TIẾP THEO] - kéo thanh ngăn giữa để đổi độ rộng.
        hp = make_paned(wrap, "horizontal")
        hp.pack(side="top", fill="both", expand=True, padx=10, pady=(0, 6))
        self._hpane = hp
        self._hp_left = tk.Frame(hp, bg=COL_BG)
        hp.add(self._hp_left, stretch="never", minsize=S(520))
        self._build_tool_groups(self._hp_left)
        right = tk.Frame(hp, bg=COL_BG)
        hp.add(right, stretch="always", minsize=S(300))
        # Bảng HÀNH ĐỘNG TIẾP THEO của từng giả lập (hẹn giờ + hàng chờ + Sự Kiện) - xem dashboard_event.py.
        g = self._build_next_action_table(right)
        g.pack(fill="both", expand=True)
        hp.bind("<ButtonRelease-1>", lambda e: save_layout(self), add="+")
        return wrap

    def _build_tool_groups(self, parent):
        # Các nút GOM THEO NHÓM, mỗi nhóm 1 thẻ có tiêu đề + màu nhấn; 4 thẻ xếp lưới 2x2 CÙNG RỘNG, nút trong thẻ
        # xếp lưới đều cột (thẳng hàng, tự giãn đủ ngang thẻ). TÊN các biến/nút cũ (btn_create_activity,
        # btn_view_errors, btn_queue, auto_login_var, boot_wait_var, account_rotate_var, lbl_post_run_action,
        # btn_event_pause...) giữ NGUYÊN vì nơi khác đang dùng.
        F9 = ("Segoe UI", 9, "bold")
        F8 = ("Segoe UI", 8, "bold")
        for c in (0, 1):
            parent.columnconfigure(c, weight=1, uniform="cards")
        for r_ in (0, 1):
            parent.rowconfigure(r_, weight=1, uniform="cardrows")

        def _card(title, accent, row, col):
            g = ToolGroup(parent, title, accent=accent)
            g.grid(row=row, column=col, sticky="nsew", padx=(0 if col == 0 else 4, 4 if col == 0 else 0),
                   pady=(0 if row == 0 else 4, 4 if row == 0 else 0))
            for c in range(3):
                g.body.columnconfigure(c, weight=1, uniform="b")
            return g

        def _b(g, text, cmd, color, r, c, span=1, font=F9):
            b = RoundedButton(g.body, text, command=cmd, bg=color, container_bg=g.card_bg, font=font,
                              padx=6, pady=5)
            b.grid(row=r, column=c, columnspan=span, sticky="ew", padx=2, pady=2)
            return b

        # ---- 🚀 TÁC VỤ NHANH (chạy thẳng 1 Hoạt Động cụ thể) ----
        g = _card("🚀 TÁC VỤ NHANH", COL_BLUE, 0, 0)
        _b(g, "📱 Mở Bảng Giả Lập", lambda: self._quick_action("mo_bang_gia_lap"), COL_BLUE, 0, 0)
        _b(g, "🆕 Setup Người Mới", lambda: self._quick_action("setup_nguoi_moi"), COL_ORANGE, 0, 1)
        _b(g, "🛠 Setup LDPlayer", self._open_ld_setup_dialog, COL_TEAL, 0, 2)
        _b(g, "🚗 Quét Xe", lambda: self._quick_action("quet_xe"), COL_ORANGE, 1, 0)
        _b(g, "🆔 UID Like", lambda: self._quick_action("uid_like"), COL_BLUE, 1, 1)
        _b(g, "🛍 Cài Đặt Shop", self._open_shop_qty_settings, COL_GREEN, 1, 2)

        # ---- 👤 TÀI KHOẢN ----
        g = _card("👤 TÀI KHOẢN", COL_PURPLE, 0, 1)
        _b(g, "👥 Quản Lý TK", self._open_account_manager, COL_PURPLE, 0, 0)
        # ⭐ Tài khoản mặc định theo giả lập: cuối phiên có đổi tài khoản thì tự Đăng Xuất + Đăng
        # Nhập lại tài khoản này - xem dashboard_accounts.py::_restore_default_account.
        b = _b(g, "⭐ TK Mặc Định", self._open_default_account_dialog, COL_PURPLE, 0, 1)
        Tooltip(b, lambda: "⭐ Tài khoản mặc định theo giả lập: cuối phiên nếu có đổi tài khoản thì tự Đăng Xuất + "
                           "Đăng Nhập lại tài khoản này.")
        _b(g, "🧩 Quản Lý Biến", self._open_variables_manager, COL_PURPLE, 0, 2)
        _b(g, "⚡ Log Nhanh", self._open_quick_login_dialog, COL_GREEN, 1, 0)
        _b(g, "🔑 Đăng Nhập 1 Acc", self._open_single_login_dialog, COL_GREEN_DARK, 1, 1)
        self.account_rotate_var = tk.BooleanVar(value=bool(self._settings.get("account_rotate", False)))
        DarkCheck(g.body, "Xoay Vòng TK", self.account_rotate_var, bg=g.card_bg
                  ).grid(row=1, column=2, sticky="w", padx=(8, 2), pady=2)

        # ---- ⏰ LỊCH & HÀNG CHỜ ----
        g = _card("⏰ LỊCH & HÀNG CHỜ", COL_TEAL, 1, 0)
        _b(g, "⏰ Hẹn Giờ", self._open_schedule_manager, COL_TEAL, 0, 0)
        _b(g, "📦 Nhóm Hành Động", self._open_group_manager, COL_PURPLE, 0, 1, span=2)
        # ⏳ Hàng Chờ: số trong ngoặc = tổng job đang chờ, tự cập nhật - xem
        # dashboard_queue.py::_update_queue_badge.
        self.btn_queue = _b(g, "⏳ Hàng Chờ (0)", self._open_queue_manager, COL_ORANGE, 1, 0)
        self.btn_view_errors = _b(g, "⚠ Lỗi / Chưa Xong (0)", self.show_error_panel, COL_RED, 1, 1, span=2)

        # ===== HÀNH ĐỘNG CUỐI + HÀNH ĐỘNG SỰ KIỆN =====
        # Hành Động Cuối: kịch bản mini nhiều bước áp dụng SAU KHI 1 giả lập chạy xong hết tác vụ của lượt hiện tại
        # (xem _apply_post_run_options, _pick_post_run_actions / self._post_run_steps_by_emulator ở dashboard_run.py).
        # Hành Động Sự Kiện: chuỗi bước riêng theo giả lập, LẶP LẠI SUỐT NGÀY, tự nhường ưu tiên cho Chạy tay/Hẹn
        # Giờ/Nhóm Hành Động rồi tự chạy tiếp khi rảnh - xem dashboard_event.py (EventActionMixin).
        g = ToolGroup(parent, "🏁 HÀNH ĐỘNG CUỐI  &  🎁 SỰ KIỆN", accent=COL_ORANGE)
        g.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=(4, 0))
        g.body.columnconfigure(0, weight=0)
        for c in range(1, 5):
            g.body.columnconfigure(c, weight=1, uniform="ev")

        # ---- Hàng 1: 🏁 HÀNH ĐỘNG CUỐI ----
        self._post_run_steps_by_emulator = self._settings.get("post_run_steps_by_emulator", {}) or {}
        # Tick = Hành Động Cuối CHỈ chạy sau lượt Hẹn Giờ; chạy tay/chạy ngay (CHẠY, Chọn Hành Động Để Chạy,
        # Xoay Vòng) thì bỏ qua - xem dashboard_run.py::_apply_post_run_options.
        self.post_run_schedule_only_var = tk.BooleanVar(value=bool(self._settings.get("post_run_schedule_only", False)))
        tk.Label(g.body, text="🏁 Cuối", bg=g.card_bg, fg=COL_PURPLE, font=F8, anchor="w"
                 ).grid(row=0, column=0, sticky="w", padx=(2, 6), pady=2)
        # Nhãn tóm tắt vẫn tạo (nơi khác cập nhật qua .config) nhưng KHÔNG hiện cho gọn - xem ở tooltip nút.
        self.lbl_post_run_action = tk.Label(g.body, text=self._post_run_action_summary_text(),
                                             bg=g.card_bg, fg=COL_TEXT_MUTED, font=("Segoe UI", 8))
        btn_post = _b(g, "⚙ Cài Đặt", self._pick_post_run_actions, COL_PURPLE, 0, 1, font=F8)
        Tooltip(btn_post, lambda: "🏁 Hành Động Cuối Theo Giả Lập - chuỗi bước chạy SAU KHI giả lập xong hết tác vụ.\n"
                                  + self._post_run_action_summary_text())
        chk_sched = DarkCheck(g.body, "Chỉ khi Hẹn Giờ", self.post_run_schedule_only_var, bg=g.card_bg,
                              font=("Segoe UI", 8, "bold"), box_size=14,
                              command=self._on_toggle_post_run_schedule_only)
        chk_sched.grid(row=0, column=2, columnspan=3, sticky="w", padx=(8, 2), pady=2)
        Tooltip(chk_sched, lambda: (
            "Chỉ chạy Hành Động Cuối cho HẸN GIỜ\n"
            "• Tick: Hành Động Cuối chỉ chạy sau các lượt ⏰ Hẹn Giờ (kể cả bấm ▶ Chạy Ngay ở cửa sổ Hẹn Giờ).\n"
            "• Chạy tay (CHẠY TẤT CẢ / Chọn Hành Động Để Chạy / Xoay Vòng Tài Khoản) KHÔNG chạy Hành Động Cuối.\n"
            "• Bỏ tick: như cũ - mọi lượt chạy xong đều chạy Hành Động Cuối."))

        # ---- Hàng 2: 🎁 HÀNH ĐỘNG SỰ KIỆN ----
        self._event_action_steps_by_emulator = self._settings.get("event_action_steps_by_emulator", {}) or {}
        self._event_interval_by_emulator = self._settings.get("event_interval_by_emulator", {}) or {}
        # Giờ bắt đầu RIÊNG từng giả lập ({"<index>": "HH:MM"}), giờ bắt đầu CHUNG và ô tích Tự Login trước mỗi lượt
        # của Sự Kiện (xem dashboard_event.py).
        self._event_start_by_emulator = self._settings.get("event_start_by_emulator", {}) or {}
        self.event_start_var = tk.StringVar(value=str(self._settings.get("event_start_time", "") or ""))
        self.event_auto_login_var = tk.BooleanVar(value=bool(self._settings.get("event_auto_login", False)))
        # Giả lập được CHỌN chạy Sự Kiện (tick ở '🎁 Soạn Hành Động Sự Kiện Theo Giả Lập') - LƯU lại để
        # đóng/mở lại cửa sổ hay mở lại app không bị mất tick (xem dashboard_event.py).
        self._event_selected_indexes = set()
        for _x in (self._settings.get("event_selected_emulators") or []):
            try:
                self._event_selected_indexes.add(int(_x))
            except (TypeError, ValueError):
                pass
        tk.Label(g.body, text="🎁 Sự Kiện", bg=g.card_bg, fg=COL_ORANGE, font=F8, anchor="w"
                 ).grid(row=1, column=0, sticky="w", padx=(2, 6), pady=2)
        # 2 nhãn tóm tắt cũ KHÔNG còn hiện trên thanh nhưng vẫn tạo ra vì _refresh_event_action_summary() còn
        # cập nhật chúng; thông tin giả lập đang chọn/đang chạy nền xem ở bảng '📋 HÀNH ĐỘNG TIẾP THEO'.
        self.lbl_event_action = tk.Label(g.body, text=self._event_action_summary_text(),
                                          bg=g.card_bg, fg=COL_TEXT_MUTED, font=("Segoe UI", 8))
        self.lbl_event_selected = tk.Label(g.body, text=self._event_selected_summary_text(), bg=g.card_bg,
                                            fg=COL_ORANGE, font=("Segoe UI", 8, "bold"), anchor="w",
                                            justify="left", wraplength=560)
        try:
            _ei = int(float(self._settings.get("event_interval_minutes", 5)))
        except Exception:
            _ei = 5
        # Ô 'Nghỉ chung (phút)' đã chuyển vào cửa sổ '⚙ Cài Đặt' (biến vẫn là event_interval_var). 0 = chạy liên tục.
        self.event_interval_var = tk.IntVar(value=max(0, min(_ei, 240)))
        # 4 NÚT: Cài Đặt (soạn chuỗi bước + chọn giả lập + nghỉ), Chạy, Tạm Dừng, Dừng.
        _b(g, "⚙ Cài Đặt", self._pick_event_actions, COL_ORANGE, 1, 1, font=F8)
        _b(g, "▶ Chạy", self.start_event_action, COL_GREEN, 1, 2, font=F8)
        self.btn_event_pause = _b(g, "⏸ Tạm Dừng", self.toggle_pause_event_action, COL_TEAL, 1, 3, font=F8)
        _b(g, "⏹ Dừng", self.stop_event_action, COL_RED, 1, 4, font=F8)

    def _build_emulator_bar(self, parent):
        # Thanh GIẢ LẬP: dòng 1 = nhãn + chip giả lập (FlowBar tự xuống dòng) + nút chọn ldconsole.exe; dòng 2 = 3
        # cụm nút CÙNG RỘNG, mỗi cụm lưới 3 cột x 2 hàng nút đều nhau (ĐIỀU KHIỂN | CHỌN & QUÉT | TỰ ĐỘNG).
        bar = tk.Frame(parent, bg=COL_PANEL, highlightbackground=COL_BORDER, highlightthickness=1)
        bar.pack(fill="x")

        chip_row = tk.Frame(bar, bg=COL_PANEL)
        chip_row.pack(fill="x")

        tk.Label(chip_row, text="🖥 Giả lập:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(10, 6), pady=8)

        # FlowBar - các chip giả lập được dashboard_emulators.py thêm bằng self.emu_chip_frame.add(...) và dọn
        # bằng self.emu_chip_frame.clear() mỗi lần quét lại, để chip TỰ XUỐNG DÒNG khi có nhiều giả lập/cửa sổ hẹp.
        RoundedButton(chip_row, "📁 Chọn ldconsole.exe", command=self.choose_ldconsole_path,
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=(4, 8), pady=4)
        self.emu_chip_frame = FlowBar(chip_row, bg=COL_PANEL)
        self.emu_chip_frame.pack(side="left", fill="x", expand=True, pady=4)

        clusters = tk.Frame(bar, bg=COL_PANEL)
        clusters.pack(fill="x", padx=6, pady=(0, 6))
        for c in range(3):
            clusters.columnconfigure(c, weight=1, uniform="emu_cl")

        F8 = ("Segoe UI", 8, "bold")

        def _cluster(col, title):
            f = tk.Frame(clusters, bg=COL_PANEL_ALT, highlightbackground=COL_BORDER, highlightthickness=1)
            f.grid(row=0, column=col, sticky="nsew", padx=3)
            tk.Label(f, text=title, bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED, font=("Segoe UI", 7, "bold"),
                     anchor="w").grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(3, 0))
            inner = tk.Frame(f, bg=COL_PANEL_ALT)
            inner.grid(row=1, column=0, columnspan=3, sticky="ew", padx=4, pady=(0, 4))
            f.columnconfigure(0, weight=1)
            for c in range(3):
                inner.columnconfigure(c, weight=1, uniform="eb")
            return inner

        def _eb(inner, text, cmd, color, r, c, span=1):
            b = RoundedButton(inner, text, command=cmd, bg=color, container_bg=COL_PANEL_ALT, font=F8,
                              padx=6, pady=4)
            b.grid(row=r, column=c, columnspan=span, sticky="ew", padx=2, pady=2)
            return b

        # ---- Cụm 1: ĐIỀU KHIỂN cửa sổ giả lập đã tick ----
        k = _cluster(0, "ĐIỀU KHIỂN (giả lập đã chọn)")
        _eb(k, "🟢 Bật", self.launch_selected_emulators, COL_GREEN, 0, 0)
        _eb(k, "🔴 Tắt", self.quit_selected_emulators, COL_RED, 0, 1)
        _eb(k, "🗕 Thu Nhỏ", self.minimize_selected_emulators, COL_GRAY_BTN, 0, 2)
        # "Đưa Lên Trên" chỉ nâng cửa sổ 1 lần (KHÔNG ghim); ô tick 📌 bên cạnh mới là GHIM (luôn nổi).
        _eb(k, "⬆ Đưa Lên Trên", self.bring_selected_emulators_to_front, COL_PURPLE, 1, 0, span=2)
        self._emu_pin_var = tk.BooleanVar(value=False)
        pin_chk = DarkCheck(k, "📌 Ghim", self._emu_pin_var, bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"),
                            box_size=14, command=self._on_pin_check_toggled)
        pin_chk.grid(row=1, column=2, sticky="w", padx=(6, 2))
        Tooltip(pin_chk, lambda: (
            "📌 Ghim các giả lập đã chọn\n"
            "• Tick: cửa sổ LUÔN NỔI trên mọi cửa sổ khác (kể cả khi app khác đang focus).\n"
            "• Bỏ tick: trở lại bình thường.\n"
            "Nút '⬆ Đưa Lên Trên' bên cạnh chỉ nâng cửa sổ lên 1 lần, không ghim."))

        # ---- Cụm 2: CHỌN & QUÉT ----
        k = _cluster(1, "CHỌN & QUÉT")
        _eb(k, "☑ Chọn Tất Cả", lambda: self._set_all_checks(True), COL_GRAY_BTN, 0, 0)
        _eb(k, "☐ Bỏ Chọn", lambda: self._set_all_checks(False), COL_GRAY_BTN, 0, 1)
        _eb(k, "🔄 Quét Giả Lập", self.refresh_emulators, COL_TEAL, 0, 2)
        _eb(k, "🔄 Quét Lại Danh Mục", self.reload_tasks, COL_TEAL, 1, 0, span=2)
        b = _eb(k, "🔀 Sắp Xếp", self._open_arrange_tasks_dialog, COL_BLUE, 1, 2)
        Tooltip(b, lambda: "🔀 Sắp Xếp Hành Động - đổi thứ tự các Hoạt Động trong danh sách.")

        # ---- Cụm 3: TỰ ĐỘNG ----
        k = _cluster(2, "TỰ ĐỘNG")
        _eb(k, "⚙ Giả Lập Tự Bật", self._open_autostart_dialog, COL_GRAY_BTN, 0, 0, span=3)
        chk_row = tk.Frame(k, bg=COL_PANEL_ALT)
        chk_row.grid(row=1, column=0, columnspan=3, sticky="ew", padx=2, pady=2)
        # 🚀 Tự bật giả lập (đã cài đặt trước) mỗi khi MỞ chương trình; bật xong vẫn chạy Tự Login
        # nếu ô '🔐 Tự Login' đang tick (xem dashboard_emulators.py::_auto_launch_on_startup).
        self.auto_launch_var = tk.BooleanVar(value=bool(self._settings.get("auto_launch_on_start", False)))
        al_chk = DarkCheck(chk_row, "🚀 Tự bật khi mở app", self.auto_launch_var, bg=COL_PANEL_ALT,
                           font=F8, box_size=14, command=self._on_toggle_autostart)
        al_chk.pack(side="left", padx=(4, 8))
        # 🪟 Khởi động cùng Windows: đăng ký Dashboard vào mục Run của registry (xem
        # dashboard_emulators.py::_set_windows_startup). Trạng thái đọc thẳng từ registry.
        self.win_startup_var = tk.BooleanVar(value=self._windows_startup_sync())
        ws_chk = DarkCheck(chk_row, "🪟 Cùng Windows", self.win_startup_var, bg=COL_PANEL_ALT,
                           font=F8, box_size=14, command=self._on_toggle_windows_startup)
        ws_chk.pack(side="left", padx=(0, 4))
        Tooltip(ws_chk, lambda: (
            "🪟 Khởi động cùng Windows\n"
            "• Tick: mỗi lần đăng nhập Windows, Dashboard tự mở (không hiện cửa sổ console).\n"
            "• Kết hợp với '🚀 Tự bật khi mở app' để mở máy là tự bật giả lập + Tự Login.\n"
            "• Bỏ tick: gỡ khỏi danh sách khởi động của Windows."))
        Tooltip(al_chk, lambda: (
            "🚀 Tự bật giả lập khi mở chương trình\n"
            "• Tick: mỗi lần mở Dashboard sẽ tự bật các giả lập chọn ở '⚙ Giả Lập Tự Bật'.\n"
            "• Bật xong, nếu ô '🔐 Tự Login' đang tick thì tự chạy Tự Login để vào game."))

    def _build_task_scroll_area(self, parent):
        wrap = tk.Frame(parent, bg=COL_BG)
        outer = tk.Frame(wrap, bg=COL_BG)
        outer.pack(fill="both", expand=True, padx=10, pady=(0, 2))

        self.canvas = tk.Canvas(outer, highlightthickness=0, bg=COL_BG)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.list_frame = tk.Frame(self.canvas, bg=COL_BG)

        self._list_frame_id = self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self._list_frame_id, width=e.width))
        self.canvas.configure(yscrollcommand=vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))
        return wrap

    def _build_bottom_controls(self, parent):
        wrap = tk.Frame(parent, bg=COL_BG)
        bar = tk.Frame(wrap, bg=COL_PANEL, highlightbackground=COL_BORDER, highlightthickness=1)
        bar.pack(fill="x", padx=10, pady=4)
        inner = tk.Frame(bar, bg=COL_PANEL)
        inner.pack(fill="x", padx=6, pady=(6, 2))
        inner2 = tk.Frame(bar, bg=COL_PANEL)
        inner2.pack(fill="x", padx=6, pady=(0, 6))

        F10 = ("Segoe UI", 10, "bold")

        self.btn_run = RoundedButton(
            inner, "▶ CHẠY TẤT CẢ TÁC VỤ ĐANG CHỌN", command=self.run_selected_tasks,
            bg=COL_GREEN, container_bg=COL_PANEL, font=F10, padx=14, pady=9)
        self.btn_run.pack(side="left", padx=4)

        RoundedButton(
            inner, "🔀 Chọn Hành Động Để Chạy", command=self._open_task_picker,
            bg=COL_BLUE, container_bg=COL_PANEL, font=F10, padx=14, pady=9
        ).pack(side="left", padx=4)

        make_separator(inner, height=30).pack(side="left", padx=8)

        self.btn_stop = RoundedButton(
            inner, "⏹ DỪNG LẠI (STOP)", command=self.stop_run,
            bg=COL_RED, container_bg=COL_PANEL, font=F10, padx=14, pady=9)
        self.btn_stop.set_state("disabled")
        self.btn_stop.pack(side="left", padx=4)

        self.btn_pause = RoundedButton(
            inner, "⏸ Tạm Dừng", command=self.toggle_pause,
            bg=COL_ORANGE, container_bg=COL_PANEL, font=F10, padx=14, pady=9)
        self.btn_pause.set_state("disabled")
        self.btn_pause.pack(side="left", padx=4)

        # ---- Tuỳ chọn ĐĂNG NHẬP TỰ ĐỘNG (đặt cạnh nút CHẠY vì ảnh hưởng trực
        # tiếp tới lượt chạy) ----
        self.auto_login_var = tk.BooleanVar(value=bool(self._settings.get("auto_login", False)))
        DarkCheck(inner2, "🔐 Tự Login", self.auto_login_var, bg=COL_PANEL).pack(side="left", padx=(6, 4), pady=4)
        # Chế độ chạy Tự Login: 1 lần mỗi phiên (mặc định) hoặc trước MỖI hành động.
        _mode_saved = self._settings.get("auto_login_mode", "session")
        self.auto_login_mode_var = tk.StringVar(
            value=self.AUTO_LOGIN_MODE_LABELS.get(_mode_saved, self.AUTO_LOGIN_MODE_LABELS["session"]))
        ttk.Combobox(inner2, textvariable=self.auto_login_mode_var, state="readonly", width=28,
                     values=list(self.AUTO_LOGIN_MODE_LABELS.values())).pack(side="left", padx=(0, 8), pady=4)
        # Chờ thêm N giây sau khi giả lập khởi động xong (Android boot) rồi mới chạy Tự Login -
        # máy khởi động chậm thì tăng lên, máy nhanh thì giảm xuống.
        try:
            _bw = int(float(self._settings.get("boot_wait_seconds", 10)))
        except Exception:
            _bw = 10
        self.boot_wait_var = tk.IntVar(value=max(0, min(_bw, 600)))
        tk.Label(inner2, text="Chờ boot (s):", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        ttk.Spinbox(inner2, from_=0, to=600, increment=5, width=4,
                    textvariable=self.boot_wait_var).pack(side="left", padx=(0, 4))
        make_separator(inner2, height=24).pack(side="left", padx=8)

        # Ô "Áp dụng cho" - chọn DỪNG/TẠM DỪNG áp dụng cho TẤT CẢ giả lập
        # đang chạy (mặc định, giữ đúng hành vi cũ) HOẶC CHỈ 1 giả lập cụ
        # thể đang bận - mỗi giả lập chạy 1 luồng riêng nên có thể dừng/tạm
        # dừng RIÊNG từng luồng mà không ảnh hưởng các giả lập khác (xem
        # _get_stop_target_index/_is_stop_requested/_is_pause_requested ở
        # dashboard_run.py). Danh sách được làm mới mỗi khi bấm mở (và mỗi
        # khi phiên chạy bắt đầu/kết thúc) để luôn khớp với các giả lập
        # ĐANG THỰC SỰ bận tại thời điểm đó.
        tk.Label(inner2, text="Áp dụng cho:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8)).pack(side="left", padx=(6, 2))
        self.stop_target_var = tk.StringVar(value=self._STOP_TARGET_ALL)
        self.combo_stop_target = ttk.Combobox(
            inner2, textvariable=self.stop_target_var, state="readonly",
            width=24, font=("Segoe UI", 8))
        self.combo_stop_target["values"] = [self._STOP_TARGET_ALL]
        self.combo_stop_target.pack(side="left", padx=(0, 4))
        self.combo_stop_target.bind("<Button-1>", lambda e: self._refresh_stop_target_options())
        RoundedButton(
            inner2, "🪟 Popup Dừng/Tạm Dừng", command=self.open_run_control_popup,
            bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"), padx=10, pady=5
        ).pack(side="left", padx=4)

        make_separator(inner2, height=24).pack(side="left", padx=8)

        RoundedButton(
            inner2, "♻ Reset Bộ Nhớ Task Hôm Nay", command=self.reset_daily_memory,
            bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"), padx=12, pady=5
        ).pack(side="left", padx=4)

        RoundedButton(
            inner2, "📨 Telegram", command=self.open_telegram_settings,
            bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"), padx=12, pady=5
        ).pack(side="left", padx=4)

        self.lbl_status = tk.Label(inner, text="Trạng thái: Sẵn sàng", bg=COL_PANEL, fg=COL_TEXT,
                                    font=("Segoe UI", 9, "bold"))
        self.lbl_status.pack(side="right", padx=8)
        return wrap

    def _build_log_panel(self, parent):
        wrap = tk.Frame(parent, bg=COL_BG)
        frame = tk.Frame(wrap, bg=COL_PANEL, highlightbackground=COL_BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        header = tk.Frame(frame, bg=COL_PANEL)
        header.pack(fill="x", padx=8, pady=(8, 0))
        tk.Label(header, text="📜 NHẬT KÝ THỰC THI THỜI GIAN THỰC", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 9, "bold")).pack(side="left")

        tk.Label(header, text="Xem Log Giả Lập:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8)).pack(side="left", padx=(20, 4))
        self.cbo_log_filter = ttk.Combobox(header, state="readonly", width=26,
                                            textvariable=self.log_filter_var,
                                            values=[self.LOG_FILTER_ALL])
        self.cbo_log_filter.pack(side="left")
        self.cbo_log_filter.bind("<<ComboboxSelected>>", self._on_log_filter_changed)

        RoundedButton(header, "🗑 Xóa Log", command=self._clear_log, bg=COL_GRAY_BTN,
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="left", padx=6)
        RoundedButton(header, "📋 Sao Chép", command=self._copy_log, bg=COL_BLUE,
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="left", padx=4)

        self.var_log_autoscroll = tk.BooleanVar(value=True)
        DarkCheck(header, "Tự cuộn xuống", self.var_log_autoscroll, bg=COL_PANEL).pack(side="left", padx=12)

        self.lbl_log_count = tk.Label(header, text="0 dòng", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8))
        self.lbl_log_count.pack(side="right", padx=4)

        # ----- Dòng trạng thái CỐ ĐỊNH (KHÔNG cuộn mất như log thường) -
        # hiển thị NGAY đang chạy tác vụ nào, của lịch hẹn giờ/xoay vòng
        # tài khoản nào, tài khoản thứ mấy - tên gì (xem _exec_entry +
        # _set_current_task_status). Nằm trên 1 dòng riêng, ngay dưới
        # hàng nút của thanh Nhật Ký, luôn hiện sẵn kể cả khi log đã cuộn
        # qua dòng đó từ lâu. -----
        status_row = tk.Frame(frame, bg=COL_PANEL_ALT)
        status_row.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(status_row, text="⏳ Đang chạy:", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(6, 6), pady=4)
        self.lbl_current_task = tk.Label(status_row, text="Không có tác vụ nào đang chạy.", bg=COL_PANEL_ALT,
                                          fg=COL_TEXT_MUTED, font=("Segoe UI", 8), anchor="w", justify="left")
        self.lbl_current_task.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=4)

        # Dòng "⏰ Kế tiếp (hẹn giờ)": hành động hẹn giờ sắp chạy của từng giả lập đang chạy
        # (không có giả lập nào chạy thì hiện lịch sớm nhất) - xem _refresh_next_action_label.
        next_row = tk.Frame(frame, bg=COL_PANEL_ALT)
        next_row.pack(fill="x", padx=8, pady=(2, 0))
        tk.Label(next_row, text="⏰ Kế tiếp (hẹn giờ):", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(6, 6), pady=3)
        self.lbl_next_action = tk.Label(next_row, text="...", bg=COL_PANEL_ALT, fg=COL_TEAL,
                                        font=("Segoe UI", 8), anchor="w", justify="left")
        self.lbl_next_action.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=3)
        self.root.after(1500, self._next_action_tick)

        body = tk.Frame(frame, bg=COL_PANEL)
        body.pack(fill="both", expand=True, padx=8, pady=8)

        log_scroll = ttk.Scrollbar(body, orient="vertical")
        self.txt_log = tk.Text(
            body, height=4, wrap="none", state="disabled",
            bg="#0b0f18", fg="#dfe4ee", font=("Consolas", 9), relief="flat",
            yscrollcommand=log_scroll.set
        )
        log_scroll.config(command=self.txt_log.yview)
        log_scroll.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)
        self.txt_log.tag_configure("info", foreground="#9aa5bd")
        self.txt_log.tag_configure("success", foreground="#3ddc84")
        self.txt_log.tag_configure("warn", foreground="#ffb020")
        self.txt_log.tag_configure("error", foreground="#ff5c5c")
        return wrap

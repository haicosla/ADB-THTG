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
from dashboard_widgets import RoundedButton, DarkCheck, FlowBar, ToolGroup, make_separator


class UIBuildMixin:
    # ================= GIAO DIỆN =================
    def _build_ui(self):
        self._build_top_toolbar()
        self._build_emulator_bar()
        # Nhật Ký + thanh CHẠY/DỪNG được pack side="bottom" TRƯỚC vùng danh
        # Hoạt Động (vùng này expand) -> cửa sổ thấp thì DANH SÁCH co lại,
        # còn Nhật Ký và các nút điều khiển luôn hiện đủ (trước đây bị đẩy
        # ra khỏi màn hình khi thanh nút phía trên chiếm nhiều chỗ).
        self._build_log_panel()
        self._build_bottom_controls()
        self._build_task_scroll_area()

    def _build_top_toolbar(self):
        # ===== BỐ CỤC MỚI: các nút được GOM THEO NHÓM CHỨC NĂNG (mỗi nhóm 1
        # khối có tiêu đề + màu nhấn riêng), thay vì 1 hàng dài trộn lẫn
        # mọi loại nút. Các nhóm nằm trong FlowBar nên tự xuống dòng khi
        # cửa sổ hẹp. TÊN các biến/nút cũ (btn_create_activity,
        # btn_view_errors, btn_queue, auto_login_var, boot_wait_var,
        # account_rotate_var, lbl_post_run_action, btn_event_pause...) giữ
        # NGUYÊN vì nơi khác đang dùng. =====
        F9 = ("Segoe UI", 9, "bold")
        F8 = ("Segoe UI", 8, "bold")

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

        def _btn(parent, text, cmd, color, font=F9, **kw):
            kw.setdefault("padx", 12)
            kw.setdefault("pady", 5)
            b = RoundedButton(parent, text, command=cmd, bg=color, container_bg=parent.cget("bg"),
                              font=font, **kw)
            b.pack(side="left", padx=3, pady=2)
            return b

        groups = FlowBar(self.root, bg=COL_BG, hgap=8, vgap=4)
        groups.pack(fill="x", padx=10, pady=(0, 6))

        # ---- Nhóm 1: TÁC VỤ NHANH (chạy thẳng 1 Hoạt Động cụ thể) ----
        g = ToolGroup(groups, "🚀 TÁC VỤ NHANH", accent=COL_BLUE)
        r = g.new_row()
        _btn(r, "📱 Mở Bảng Giả Lập", lambda: self._quick_action("mo_bang_gia_lap"), COL_BLUE)
        _btn(r, "🆕 Setup Người Mới", lambda: self._quick_action("setup_nguoi_moi"), COL_ORANGE)
        _btn(r, "🛠 Setup LDPlayer", self._open_ld_setup_dialog, COL_TEAL)
        r = g.new_row()
        _btn(r, "🚗 Quét Xe", lambda: self._quick_action("quet_xe"), COL_ORANGE)
        _btn(r, "🆔 UID Like", lambda: self._quick_action("uid_like"), COL_BLUE)
        _btn(r, "🛍 Cài Đặt Shop", self._open_shop_qty_settings, COL_GREEN)
        groups.add(g)

        # ---- Nhóm 2: TÀI KHOẢN ----
        g = ToolGroup(groups, "👤 TÀI KHOẢN", accent=COL_PURPLE)
        r = g.new_row()
        _btn(r, "👥 Quản Lý Tài Khoản", self._open_account_manager, COL_PURPLE)
        _btn(r, "🧩 Quản Lý Biến", self._open_variables_manager, COL_PURPLE)
        r = g.new_row(pady=(2, 0))
        _btn(r, "⚡ Log Nhanh", self._open_quick_login_dialog, COL_GREEN)
        _btn(r, "🔑 Đăng Nhập 1 Acc", self._open_single_login_dialog, COL_GREEN_DARK)
        self.account_rotate_var = tk.BooleanVar(value=bool(self._settings.get("account_rotate", False)))
        DarkCheck(r, "Xoay Vòng Tài Khoản", self.account_rotate_var, bg=g.card_bg
                  ).pack(side="left", padx=(10, 2))
        groups.add(g)

        # ---- Nhóm 3: LỊCH & HÀNG CHỜ ----
        g = ToolGroup(groups, "⏰ LỊCH & HÀNG CHỜ", accent=COL_TEAL)
        r = g.new_row()
        _btn(r, "⏰ Hẹn Giờ", self._open_schedule_manager, COL_TEAL)
        _btn(r, "📦 Nhóm Hành Động", self._open_group_manager, COL_PURPLE)
        r = g.new_row()
        # ⏳ Hàng Chờ: số trong ngoặc = tổng job đang chờ, tự cập nhật - xem
        # dashboard_queue.py::_update_queue_badge.
        self.btn_queue = _btn(r, "⏳ Hàng Chờ (0)", self._open_queue_manager, COL_ORANGE)
        self.btn_view_errors = _btn(r, "⚠ Xem Lỗi / Chưa Xong (0)", self.show_error_panel, COL_RED)
        groups.add(g)

        # ===== HÀNG 2: HÀNH ĐỘNG CUỐI + HÀNH ĐỘNG SỰ KIỆN =====
        # Hành Động Cuối: kịch bản mini nhiều bước áp dụng SAU KHI 1 giả lập
        # chạy xong hết tác vụ của lượt hiện tại (xem _apply_post_run_options,
        # _pick_post_run_actions / self._post_run_steps_by_emulator ở
        # dashboard_run.py).
        # Hành Động Sự Kiện: chuỗi bước riêng theo giả lập, LẶP LẠI SUỐT
        # NGÀY, tự nhường ưu tiên cho Chạy tay/Hẹn Giờ/Nhóm Hành Động rồi
        # tự chạy tiếp khi rảnh - xem dashboard_event.py (EventActionMixin).
        groups2 = FlowBar(self.root, bg=COL_BG, hgap=8, vgap=4)
        groups2.pack(fill="x", padx=10, pady=(0, 8))

        self._post_run_steps_by_emulator = self._settings.get("post_run_steps_by_emulator", {}) or {}
        g = ToolGroup(groups2, "🏁 HÀNH ĐỘNG CUỐI", accent=COL_PURPLE)
        r = g.new_row()
        self.lbl_post_run_action = tk.Label(r, text=self._post_run_action_summary_text(),
                                             bg=g.card_bg, fg=COL_TEXT_MUTED, font=("Segoe UI", 8))
        self.lbl_post_run_action.pack(side="left", padx=(2, 8))
        _btn(r, "🏁 Hành Động Cuối Theo Giả Lập", self._pick_post_run_actions, COL_PURPLE, font=F8)
        groups2.add(g)

        self._event_action_steps_by_emulator = self._settings.get("event_action_steps_by_emulator", {}) or {}
        self._event_interval_by_emulator = self._settings.get("event_interval_by_emulator", {}) or {}
        g = ToolGroup(groups2, "🎁 HÀNH ĐỘNG SỰ KIỆN", accent=COL_ORANGE)
        r = g.new_row()
        self.lbl_event_action = tk.Label(r, text=self._event_action_summary_text(),
                                          bg=g.card_bg, fg=COL_TEXT_MUTED, font=("Segoe UI", 8))
        self.lbl_event_action.pack(side="left", padx=(2, 8))
        _btn(r, "🎁 Soạn Hành Động Sự Kiện Theo Giả Lập", self._pick_event_actions, COL_ORANGE, font=F8)
        r = g.new_row(pady=(2, 0))
        try:
            _ei = int(float(self._settings.get("event_interval_minutes", 5)))
        except Exception:
            _ei = 5
        self.event_interval_var = tk.IntVar(value=max(1, min(_ei, 240)))
        tk.Label(r, text="Nghỉ chung (phút):", bg=g.card_bg, fg=COL_TEXT,
                 font=("Segoe UI", 8)).pack(side="left", padx=(2, 4))
        ttk.Spinbox(r, from_=1, to=240, increment=1, width=4,
                    textvariable=self.event_interval_var).pack(side="left", padx=(0, 6))
        _btn(r, "▶ Bắt Đầu Sự Kiện (Giả Lập Đã Tick)", self.start_event_action, COL_GREEN, font=F8)
        self.btn_event_pause = _btn(r, "⏸ Tạm Dừng Sự Kiện", self.toggle_pause_event_action, COL_TEAL, font=F8)
        _btn(r, "⏹ Dừng Sự Kiện", self.stop_event_action, COL_RED, font=F8)
        groups2.add(g)

    def _build_emulator_bar(self):
        # Tách thành 2 DÒNG RIÊNG (thay vì nhồi chung 1 dòng "nhãn + chip giả
        # lập (expand) + cụm nút" như bản cũ) - cách cũ khiến vùng chip giả
        # lập (fill='x', expand=True) tranh chỗ trực tiếp với cụm nút bên
        # phải, nên khi thu nhỏ cửa sổ, các nút bị ĐẨY RA NGOÀI VÙNG HIỂN THỊ
        # (biến mất) thay vì tự co giãn/xuống dòng. Tách riêng: dòng 1 = nhãn
        # + FlowBar các chip giả lập (tự xuống dòng khi nhiều giả lập), dòng
        # 2 = FlowBar cụm nút thao tác giả lập (cũng tự xuống dòng) - không
        # dòng nào còn phải tranh chỗ với dòng kia nữa.
        bar = tk.Frame(self.root, bg=COL_PANEL, highlightbackground=COL_BORDER, highlightthickness=1)
        bar.pack(fill="x", padx=10, pady=(0, 8))

        chip_row = tk.Frame(bar, bg=COL_PANEL)
        chip_row.pack(fill="x")

        tk.Label(chip_row, text="🖥 Giả lập:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(10, 6), pady=8)

        # FlowBar (không còn là Frame thường) - các chip giả lập được
        # dashboard_emulators.py thêm vào bằng self.emu_chip_frame.add(...)
        # và dọn sạch bằng self.emu_chip_frame.clear() mỗi lần quét lại,
        # THAY VÌ .pack(side="left") + tự lặp winfo_children() để destroy()
        # như trước - để chip TỰ XUỐNG DÒNG khi có nhiều giả lập/cửa sổ hẹp.
        RoundedButton(chip_row, "📁 Chọn ldconsole.exe", command=self.choose_ldconsole_path,
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=(4, 8), pady=4)
        self.emu_chip_frame = FlowBar(chip_row, bg=COL_PANEL)
        self.emu_chip_frame.pack(side="left", fill="x", expand=True, pady=4)

        btn_row = FlowBar(bar, bg=COL_PANEL)
        btn_row.pack(fill="x", padx=8, pady=(0, 6))

        def _eb(text, cmd, color):
            btn_row.add(RoundedButton(btn_row, text, command=cmd, bg=color, container_bg=COL_PANEL,
                                       font=("Segoe UI", 8, "bold"), padx=8, pady=4))

        def _sep():
            btn_row.add(make_separator(btn_row, height=22))

        # Nhóm 1: bật/tắt/điều khiển cửa sổ giả lập đã tick
        _eb("🟢 Bật Đã Chọn", self.launch_selected_emulators, COL_GREEN)
        _eb("🔴 Tắt Đã Chọn", self.quit_selected_emulators, COL_RED)
        _eb("📌 Đưa Lên Đầu", self.toggle_pin_selected_emulators, COL_PURPLE)
        _eb("🗕 Thu Nhỏ Đã Chọn", self.minimize_selected_emulators, COL_GRAY_BTN)
        _sep()
        # Nhóm 2: chọn nhanh các ô tick
        _eb("☑ Chọn Tất Cả", lambda: self._set_all_checks(True), COL_GRAY_BTN)
        _eb("☐ Bỏ Chọn", lambda: self._set_all_checks(False), COL_GRAY_BTN)
        _sep()
        # Nhóm 3: quét/nạp lại dữ liệu + sắp xếp
        _eb("🔄 Quét Giả Lập", self.refresh_emulators, COL_TEAL)
        _eb("🔄 Quét Lại Danh Mục", self.reload_tasks, COL_TEAL)
        _eb("🔀 Sắp Xếp Hành Động", self._open_arrange_tasks_dialog, COL_BLUE)

    def _build_task_scroll_area(self):
        outer = tk.Frame(self.root, bg=COL_BG)
        outer.pack(fill="both", expand=True, padx=10, pady=(0, 6))

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

    def _build_bottom_controls(self):
        wrap = tk.Frame(self.root, bg=COL_BG)
        wrap.pack(side="bottom", fill="x", padx=10, pady=6)
        bar = tk.Frame(wrap, bg=COL_PANEL, highlightbackground=COL_BORDER, highlightthickness=1)
        bar.pack(fill="x")
        tk.Frame(wrap, bg=COL_SHADOW, height=3).pack(fill="x", padx=3)
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
        ttk.Combobox(inner2, textvariable=self.auto_login_mode_var, state="readonly", width=20,
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

    def _build_log_panel(self):
        frame = tk.Frame(self.root, bg=COL_PANEL, highlightbackground=COL_BORDER, highlightthickness=1)
        frame.pack(side="bottom", fill="x", expand=False, padx=10, pady=(0, 10))

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

        body = tk.Frame(frame, bg=COL_PANEL)
        body.pack(fill="both", expand=True, padx=8, pady=8)

        log_scroll = ttk.Scrollbar(body, orient="vertical")
        self.txt_log = tk.Text(
            body, height=10, wrap="none", state="disabled",
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

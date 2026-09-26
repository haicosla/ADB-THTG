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
from dashboard_widgets import RoundedButton, DarkCheck, FlowBar


class UIBuildMixin:
    # ================= GIAO DIỆN =================
    def _build_ui(self):
        self._build_top_toolbar()
        self._build_emulator_bar()
        self._build_task_scroll_area()
        self._build_bottom_controls()
        self._build_log_panel()

    def _build_top_toolbar(self):
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

        # FlowBar (thay vì Frame thường + pack(side="left")) để hàng nút TỰ
        # XUỐNG DÒNG khi thu nhỏ cửa sổ, thay vì bị Tkinter âm thầm cắt/giấu
        # mất những nút không còn đủ chỗ (xem docstring FlowBar ở
        # dashboard_widgets.py).
        actions_bar = FlowBar(self.root, bg=COL_BG)
        actions_bar.pack(fill="x", padx=10, pady=(0, 8))

        actions_bar.add(RoundedButton(actions_bar, "📱 Mở Bảng Giả Lập", command=lambda: self._quick_action("mo_bang_gia_lap"),
                                       bg=COL_BLUE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")))
        actions_bar.add(RoundedButton(actions_bar, "🆕 Setup Người Mới", command=lambda: self._quick_action("setup_nguoi_moi"),
                                       bg=COL_ORANGE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")))
        actions_bar.add(RoundedButton(actions_bar, "📖 Hướng Dẫn", command=lambda: self._quick_action("huong_dan"),
                                       bg=COL_PURPLE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")))

        self.auto_login_var = tk.BooleanVar(value=bool(self._settings.get("auto_login", False)))
        actions_bar.add(DarkCheck(actions_bar, "Tự Login", self.auto_login_var, bg=COL_BG))

        # Chờ thêm N giây sau khi giả lập khởi động xong (Android boot) rồi mới chạy Tự Login -
        # máy khởi động chậm thì tăng lên, máy nhanh thì giảm xuống.
        try:
            _bw = int(float(self._settings.get("boot_wait_seconds", 10)))
        except Exception:
            _bw = 10
        self.boot_wait_var = tk.IntVar(value=max(0, min(_bw, 600)))
        boot_wait_box = tk.Frame(actions_bar, bg=COL_BG)
        tk.Label(boot_wait_box, text="Chờ boot (s):", bg=COL_BG, fg=COL_TEXT,
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        ttk.Spinbox(boot_wait_box, from_=0, to=600, increment=5, width=4,
                    textvariable=self.boot_wait_var).pack(side="left")
        actions_bar.add(boot_wait_box)

        self.account_rotate_var = tk.BooleanVar(value=bool(self._settings.get("account_rotate", False)))
        actions_bar.add(DarkCheck(actions_bar, "Xoay Vòng Tài Khoản", self.account_rotate_var, bg=COL_BG))

        actions_bar.add(RoundedButton(actions_bar, "👥 Quản Lý Tài Khoản", command=self._open_account_manager,
                                       bg=COL_PURPLE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")))

        actions_bar.add(RoundedButton(actions_bar, "⚡ Log Nhanh", command=self._open_quick_login_dialog,
                                       bg=COL_GREEN, container_bg=COL_BG, font=("Segoe UI", 9, "bold")))

        actions_bar.add(RoundedButton(actions_bar, "🔑 Đăng Nhập 1 Acc", command=self._open_single_login_dialog,
                                       bg=COL_GREEN_DARK, container_bg=COL_BG, font=("Segoe UI", 9, "bold")))

        actions_bar.add(RoundedButton(actions_bar, "⏰ Hẹn Giờ", command=self._open_schedule_manager,
                                       bg=COL_TEAL, container_bg=COL_BG, font=("Segoe UI", 9, "bold")))

        actions_bar.add(RoundedButton(actions_bar, "📦 Nhóm Hành Động", command=self._open_group_manager,
                                       bg=COL_PURPLE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")))

        actions_bar.add(RoundedButton(actions_bar, "🚗 Quét Xe", command=lambda: self._quick_action("quet_xe"),
                                       bg=COL_ORANGE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")))
        actions_bar.add(RoundedButton(actions_bar, "🆔 UID Like", command=lambda: self._quick_action("uid_like"),
                                       bg=COL_BLUE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")))

        self.btn_view_errors = RoundedButton(
            actions_bar, "⚠ Xem Lỗi / Chưa Xong (0)", command=self.show_error_panel,
            bg=COL_RED, container_bg=COL_BG, font=("Segoe UI", 9, "bold"))
        actions_bar.add(self.btn_view_errors)

        actions_bar.add(RoundedButton(actions_bar, "🛍 Cài Đặt Shop", command=lambda: self._quick_action("cai_dat_shop"),
                                       bg=COL_GREEN, container_bg=COL_BG, font=("Segoe UI", 9, "bold")))

        # ===== HÀNH ĐỘNG CUỐI (kịch bản mini nhiều bước, áp dụng SAU KHI 1
        # giả lập chạy xong hết tác vụ của lượt hiện tại - CHẠY tay/Chọn
        # Hành Động Để Chạy/Xoay Vòng Tài Khoản/lịch hẹn giờ đều dùng
        # chung, xem _apply_post_run_options). Mỗi giả lập soạn 1 DANH
        # SÁCH BƯỚC có thứ tự (Hoạt Động thường xen kẽ Hành động hệ thống:
        # Bật/Tắt giả lập, Đăng Xuất, Đăng Nhập 1 TK bất kỳ) - xem
        # _pick_post_run_actions() / self._post_run_steps_by_emulator ở
        # dashboard_run.py. =====
        actions_bar2 = FlowBar(self.root, bg=COL_BG)
        actions_bar2.pack(fill="x", padx=10, pady=(0, 8))

        self._post_run_steps_by_emulator = self._settings.get("post_run_steps_by_emulator", {}) or {}

        actions_bar2.add(tk.Label(actions_bar2, text="🏁 Hành Động Cuối:", bg=COL_BG,
                                   fg=COL_TEXT_MUTED, font=("Segoe UI", 8)))
        self.lbl_post_run_action = tk.Label(actions_bar2, text=self._post_run_action_summary_text(),
                                             bg=COL_BG, fg=COL_TEXT_MUTED, font=("Segoe UI", 8))
        actions_bar2.add(self.lbl_post_run_action)
        actions_bar2.add(RoundedButton(actions_bar2, "🏁 Hành Động Cuối Theo Giả Lập",
                                        command=self._pick_post_run_actions,
                                        bg=COL_PURPLE, container_bg=COL_BG, font=("Segoe UI", 8, "bold")))

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
        self.emu_chip_frame = FlowBar(chip_row, bg=COL_PANEL)
        self.emu_chip_frame.pack(side="left", fill="x", expand=True, pady=4)

        btn_row = FlowBar(bar, bg=COL_PANEL)
        btn_row.pack(fill="x", padx=8, pady=(0, 6))

        btn_row.add(RoundedButton(btn_row, "📁 Chọn ldconsole.exe", command=self.choose_ldconsole_path,
                                   bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                                   font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_row.add(RoundedButton(btn_row, "🟢 Bật Đã Chọn", command=self.launch_selected_emulators,
                                   bg=COL_GREEN, container_bg=COL_PANEL,
                                   font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_row.add(RoundedButton(btn_row, "🔴 Tắt Đã Chọn", command=self.quit_selected_emulators,
                                   bg=COL_RED, container_bg=COL_PANEL,
                                   font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_row.add(RoundedButton(btn_row, "📌 Đưa Lên Đầu", command=self.toggle_pin_selected_emulators,
                                   bg=COL_PURPLE, container_bg=COL_PANEL,
                                   font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_row.add(RoundedButton(btn_row, "🗕 Thu Nhỏ Đã Chọn", command=self.minimize_selected_emulators,
                                   bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                                   font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_row.add(RoundedButton(btn_row, "🔄 Quét Giả Lập", command=self.refresh_emulators,
                                   bg=COL_TEAL, container_bg=COL_PANEL,
                                   font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_row.add(RoundedButton(btn_row, "☑ Chọn Tất Cả", command=lambda: self._set_all_checks(True),
                                   bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                                   font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_row.add(RoundedButton(btn_row, "☐ Bỏ Chọn", command=lambda: self._set_all_checks(False),
                                   bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                                   font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_row.add(RoundedButton(btn_row, "🔄 Quét Lại Danh Mục", command=self.reload_tasks,
                                   bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                                   font=("Segoe UI", 8, "bold"), padx=8, pady=4))
        btn_row.add(RoundedButton(btn_row, "🔀 Sắp Xếp Hành Động", command=self._open_arrange_tasks_dialog,
                                   bg=COL_BLUE, container_bg=COL_PANEL,
                                   font=("Segoe UI", 8, "bold"), padx=8, pady=4))

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
        bar = tk.Frame(self.root, bg=COL_BG)
        bar.pack(fill="x", padx=10, pady=6)

        self.btn_run = RoundedButton(
            bar, "▶ CHẠY TẤT CẢ TÁC VỤ ĐANG CHỌN", command=self.run_selected_tasks,
            bg=COL_GREEN, container_bg=COL_BG, font=("Segoe UI", 10, "bold"), padx=14, pady=9)
        self.btn_run.pack(side="left", padx=4)

        RoundedButton(
            bar, "🔀 Chọn Hành Động Để Chạy", command=self._open_task_picker,
            bg=COL_BLUE, container_bg=COL_BG, font=("Segoe UI", 10, "bold"), padx=14, pady=9
        ).pack(side="left", padx=4)

        self.btn_stop = RoundedButton(
            bar, "⏹ DỪNG LẠI (STOP)", command=self.stop_run,
            bg=COL_RED, container_bg=COL_BG, font=("Segoe UI", 10, "bold"), padx=14, pady=9)
        self.btn_stop.set_state("disabled")
        self.btn_stop.pack(side="left", padx=4)

        self.btn_pause = RoundedButton(
            bar, "⏸ Tạm Dừng", command=self.toggle_pause,
            bg=COL_ORANGE, container_bg=COL_BG, font=("Segoe UI", 10, "bold"), padx=14, pady=9)
        self.btn_pause.set_state("disabled")
        self.btn_pause.pack(side="left", padx=4)

        # Ô "Áp dụng cho" - chọn DỪNG/TẠM DỪNG áp dụng cho TẤT CẢ giả lập
        # đang chạy (mặc định, giữ đúng hành vi cũ) HOẶC CHỈ 1 giả lập cụ
        # thể đang bận - mỗi giả lập chạy 1 luồng riêng nên có thể dừng/tạm
        # dừng RIÊNG từng luồng mà không ảnh hưởng các giả lập khác (xem
        # _get_stop_target_index/_is_stop_requested/_is_pause_requested ở
        # dashboard_run.py). Danh sách được làm mới mỗi khi bấm mở (và mỗi
        # khi phiên chạy bắt đầu/kết thúc) để luôn khớp với các giả lập
        # ĐANG THỰC SỰ bận tại thời điểm đó.
        tk.Label(bar, text="Áp dụng cho:", bg=COL_BG, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8)).pack(side="left", padx=(10, 2))
        self.stop_target_var = tk.StringVar(value=self._STOP_TARGET_ALL)
        self.combo_stop_target = ttk.Combobox(
            bar, textvariable=self.stop_target_var, state="readonly",
            width=24, font=("Segoe UI", 8))
        self.combo_stop_target["values"] = [self._STOP_TARGET_ALL]
        self.combo_stop_target.pack(side="left", padx=(0, 4))
        self.combo_stop_target.bind("<Button-1>", lambda e: self._refresh_stop_target_options())

        RoundedButton(
            bar, "♻ Reset Bộ Nhớ Task Hôm Nay", command=self.reset_daily_memory,
            bg=COL_GRAY_BTN, container_bg=COL_BG, font=("Segoe UI", 9, "bold"), padx=12, pady=9
        ).pack(side="left", padx=4)

        self.lbl_status = tk.Label(bar, text="Trạng thái: Sẵn sàng", bg=COL_BG, fg=COL_TEXT,
                                    font=("Segoe UI", 9, "bold"))
        self.lbl_status.pack(side="right", padx=8)

    def _build_log_panel(self):
        frame = tk.Frame(self.root, bg=COL_PANEL, highlightbackground=COL_BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=False, padx=10, pady=(0, 10))

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

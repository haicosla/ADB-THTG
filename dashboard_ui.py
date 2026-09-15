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
from dashboard_widgets import RoundedButton, DarkCheck


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

        actions_bar = tk.Frame(self.root, bg=COL_BG)
        actions_bar.pack(fill="x", padx=10, pady=(0, 8))

        RoundedButton(actions_bar, "📱 Mở Bảng Giả Lập", command=lambda: self._quick_action("mo_bang_gia_lap"),
                      bg=COL_BLUE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)
        RoundedButton(actions_bar, "🆕 Setup Người Mới", command=lambda: self._quick_action("setup_nguoi_moi"),
                      bg=COL_ORANGE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)
        RoundedButton(actions_bar, "📖 Hướng Dẫn", command=lambda: self._quick_action("huong_dan"),
                      bg=COL_PURPLE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)

        self.auto_login_var = tk.BooleanVar(value=bool(self._settings.get("auto_login", False)))
        DarkCheck(actions_bar, "Tự Login", self.auto_login_var, bg=COL_BG).pack(side="left", padx=10)

        self.account_rotate_var = tk.BooleanVar(value=bool(self._settings.get("account_rotate", False)))
        DarkCheck(actions_bar, "Xoay Vòng Tài Khoản", self.account_rotate_var, bg=COL_BG).pack(side="left", padx=10)

        RoundedButton(actions_bar, "👥 Quản Lý Tài Khoản", command=self._open_account_manager,
                      bg=COL_PURPLE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)

        RoundedButton(actions_bar, "⏰ Hẹn Giờ", command=self._open_schedule_manager,
                      bg=COL_TEAL, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)

        # ===== 2 tuỳ chọn HẬU KỲ (áp dụng SAU KHI 1 giả lập chạy xong hết
        # tác vụ của lượt hiện tại - chạy tay/Chạy Ngay/Xoay Vòng Tài Khoản
        # /lịch hẹn giờ đều dùng chung, xem _apply_post_run_options). Đặt ở
        # 1 dòng riêng (actions_bar2) để không làm chật dòng nút phía trên. =====
        actions_bar2 = tk.Frame(self.root, bg=COL_BG)
        actions_bar2.pack(fill="x", padx=10, pady=(0, 8))

        self.shutdown_after_var = tk.BooleanVar(value=bool(self._settings.get("shutdown_after", False)))
        DarkCheck(actions_bar2, "🔌 Tắt Giả Lập Sau Khi Chạy Xong", self.shutdown_after_var,
                  bg=COL_BG).pack(side="left", padx=10)

        self.post_login_after_var = tk.BooleanVar(value=bool(self._settings.get("post_login_after", False)))
        DarkCheck(actions_bar2, "🔑 Đăng Nhập TK Chỉ Định Sau Khi Chạy Xong", self.post_login_after_var,
                  bg=COL_BG).pack(side="left", padx=10)

        self._post_login_account_id = self._settings.get("post_login_account_id")
        self.lbl_post_login_account = tk.Label(actions_bar2, text=self._post_login_account_label_text(),
                                                bg=COL_BG, fg=COL_TEXT_MUTED, font=("Segoe UI", 8))
        self.lbl_post_login_account.pack(side="left", padx=(0, 4))
        RoundedButton(actions_bar2, "🎯 Chọn TK", command=self._pick_post_login_account,
                      bg=COL_PURPLE, container_bg=COL_BG, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 10))

        RoundedButton(actions_bar, "🚗 Quét Xe", command=lambda: self._quick_action("quet_xe"),
                      bg=COL_ORANGE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)
        RoundedButton(actions_bar, "🆔 UID Like", command=lambda: self._quick_action("uid_like"),
                      bg=COL_BLUE, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)

        self.btn_view_errors = RoundedButton(
            actions_bar, "⚠ Xem Lỗi / Chưa Xong (0)", command=self.show_error_panel,
            bg=COL_RED, container_bg=COL_BG, font=("Segoe UI", 9, "bold"))
        self.btn_view_errors.pack(side="left", padx=3)

        RoundedButton(actions_bar, "🛍 Cài Đặt Shop", command=lambda: self._quick_action("cai_dat_shop"),
                      bg=COL_GREEN, container_bg=COL_BG, font=("Segoe UI", 9, "bold")).pack(side="left", padx=3)

    def _build_emulator_bar(self):
        bar = tk.Frame(self.root, bg=COL_PANEL, highlightbackground=COL_BORDER, highlightthickness=1)
        bar.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(bar, text="🖥 Giả lập:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(10, 6), pady=8)

        self.emu_chip_frame = tk.Frame(bar, bg=COL_PANEL)
        self.emu_chip_frame.pack(side="left", fill="x", expand=True)

        RoundedButton(bar, "🔄 Quét Lại Danh Mục", command=self.reload_tasks,
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=3, pady=6)
        RoundedButton(bar, "☐ Bỏ Chọn", command=lambda: self._set_all_checks(False),
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=3, pady=6)
        RoundedButton(bar, "☑ Chọn Tất Cả", command=lambda: self._set_all_checks(True),
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=3, pady=6)
        RoundedButton(bar, "🔄 Quét Giả Lập", command=self.refresh_emulators,
                      bg=COL_TEAL, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=6, pady=6)
        RoundedButton(bar, "🔴 Tắt Đã Chọn", command=self.quit_selected_emulators,
                      bg=COL_RED, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=3, pady=6)
        RoundedButton(bar, "🟢 Bật Đã Chọn", command=self.launch_selected_emulators,
                      bg=COL_GREEN, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=3, pady=6)
        RoundedButton(bar, "📁 Chọn ldconsole.exe", command=self.choose_ldconsole_path,
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL,
                      font=("Segoe UI", 8, "bold"), padx=8, pady=4).pack(side="right", padx=3, pady=6)

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

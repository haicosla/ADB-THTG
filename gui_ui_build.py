"""
gui_ui_build.py — UIBuildMixin: dựng toàn bộ khung giao diện Tkinter của
LD Macro Studio (thanh trên cùng, panel trái danh sách bước, panel giữa
xem trước màn hình, panel phải thanh log/inspector, menu chuột phải trên
danh sách bước...).

Đây là 1 phần của class MacroStudioApp (xem gui.py) - tách riêng thành 1
Mixin theo chức năng để dễ đọc/sửa, y hệt cách dashboard.py đã tách các
Mixin dashboard_*.py. Mọi tham chiếu "self." trong file này trỏ vào cùng
1 instance MacroStudioApp như khi mọi hàm còn nằm chung 1 file gui.py -
KHÔNG đổi hành vi, chỉ tổ chức lại code.

MUỐN SỬA bố cục/giao diện? Sửa ở đây. Muốn sửa HÀNH VI khi bấm 1 nút cụ
thể, tìm đúng gui_*.py chứa hàm xử lý (xem bảng phân chia ở đầu gui.py).
""" 
import tkinter as tk
from tkinter import ttk


class UIBuildMixin:

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Treeview", font=("Consolas", 9), rowheight=24)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        self.style.map("Treeview", background=[("selected", "#1976D2")], foreground=[("selected", "#FFFFFF")])

    def _build_ui(self):
        f_top = ttk.Frame(self.root)
        f_top.pack(fill="x", padx=10, pady=4)

        ttk.Label(f_top, text="Thiết bị:").pack(side="left", padx=4)
        self.cbo_dev = ttk.Combobox(f_top, state="readonly", width=14)
        self.cbo_dev.pack(side="left", padx=2)
        self.cbo_dev.bind("<<ComboboxSelected>>", self.on_select_device)

        self.lbl_ld_status = ttk.Label(f_top, text="LD: Chưa tìm thấy", foreground="red", font=("Segoe UI", 9, "bold"))
        self.lbl_ld_status.pack(side="left", padx=4)

        self.lbl_keycombo_warn = ttk.Label(f_top, text="", font=("Segoe UI", 8, "bold"))
        self.lbl_keycombo_warn.pack(side="left", padx=6)

        ttk.Button(f_top, text="Quét lại", command=self.refresh_all).pack(side="left", padx=2)
        ttk.Button(f_top, text="🔄 Chụp mới", command=self.capture_and_show).pack(side="left", padx=2)

        self.btn_toggle_stream = tk.Button(
            f_top, text="▶ LIVE", bg="#455A64", fg="white",
            font=("Segoe UI", 9, "bold"), relief="raised", padx=6, pady=2,
            command=self.toggle_live_stream
        )
        self.btn_toggle_stream.pack(side="left", padx=4)

        f_crop_cfg = ttk.LabelFrame(f_top, text=" Cắt ")
        f_crop_cfg.pack(side="left", padx=4)
        ttk.Label(f_crop_cfg, text="R:").pack(side="left", padx=1)
        self.spin_w = ttk.Spinbox(f_crop_cfg, from_=20, to=500, width=4)
        self.spin_w.set(100)
        self.spin_w.pack(side="left", padx=1)
        ttk.Label(f_crop_cfg, text="C:").pack(side="left", padx=1)
        self.spin_h = ttk.Spinbox(f_crop_cfg, from_=20, to=500, width=4)
        self.spin_h.set(100)
        self.spin_h.pack(side="left", padx=1)

        self.cbo_preset = ttk.Combobox(f_crop_cfg, values=["60x60", "80x80", "100x100", "120x120", "150x80"], state="readonly", width=6)
        self.cbo_preset.set("100x100")
        self.cbo_preset.pack(side="left", padx=2)
        self.cbo_preset.bind("<<ComboboxSelected>>", self.on_preset_change)

        self.btn_live_record = tk.Button(
            f_top, text="● GHI LD (F7)", bg="#2E7D32", fg="white",
            font=("Segoe UI", 9, "bold"), relief="raised", padx=8, pady=2,
            command=self.toggle_live_record
        )
        self.btn_live_record.pack(side="right", padx=4)

        self.lbl_fps = ttk.Label(f_top, text="FPS: OFF", foreground="gray", font=("Segoe UI", 9, "bold"))
        self.lbl_fps.pack(side="right", padx=4)

        f_batch = ttk.LabelFrame(self.root, text=" Cài đặt thông số ảnh hàng loạt & mặc định ")
        f_batch.pack(fill="x", padx=10, pady=2)

        ttk.Label(f_batch, text="Timeout (s):").pack(side="left", padx=4)
        # TRƯỚC ĐÂY: to=120 giới hạn timeout hàng loạt tối đa 120s. Nay nới
        # rất rộng (999999s ~ 11 ngày) để coi như KHÔNG GIỚI HẠN thực tế -
        # Spinbox bắt buộc có trần trên nên không thể để thật sự vô hạn,
        # nhưng người dùng vẫn có thể tự gõ tay số lớn hơn nếu muốn.
        self.spin_all_timeout = ttk.Spinbox(f_batch, from_=1, to=999999, width=6)
        self.spin_all_timeout.set(8)
        self.spin_all_timeout.pack(side="left", padx=2)

        ttk.Label(f_batch, text="Độ khớp:").pack(side="left", padx=6)
        self.spin_all_conf = ttk.Spinbox(f_batch, from_=0.5, to=0.99, increment=0.05, width=5)
        self.spin_all_conf.set(0.80)
        self.spin_all_conf.pack(side="left", padx=2)

        ttk.Label(f_batch, text="Tốc độ quét (s):").pack(side="left", padx=6)
        self.spin_all_scan = ttk.Spinbox(f_batch, from_=0.02, to=2.0, increment=0.02, width=5)
        self.spin_all_scan.set(0.10)
        self.spin_all_scan.pack(side="left", padx=2)

        ttk.Button(f_batch, text="⚡ ÁP DỤNG CHO TẤT CẢ BƯỚC ẢNH", command=self.apply_batch_image_settings).pack(side="left", padx=8)

        ttk.Separator(f_batch, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)
        ttk.Button(f_batch, text="🔍 Kiểm Tra OCR", command=self.check_ocr_setup_dialog).pack(side="left", padx=4)
        ttk.Button(f_batch, text="🧪 Test Quét Ảnh", command=self.open_image_test_dialog).pack(side="left", padx=4)

        self.vpaned = ttk.PanedWindow(self.root, orient="vertical")
        self.vpaned.pack(fill="both", expand=True, padx=10, pady=5)

        self.paned = ttk.PanedWindow(self.vpaned, orient="horizontal")
        self.vpaned.add(self.paned, weight=6)

        f_left = ttk.LabelFrame(self.paned, text=" Màn Hình Preview ")
        self.paned.add(f_left, weight=3)

        f_modes = ttk.Frame(f_left)
        f_modes.pack(fill="x", padx=5, pady=2)
        ttk.Radiobutton(f_modes, text="📸 Cắt + Chạm", variable=self.preview_action_mode, value="crop_and_tap").pack(side="left", padx=2)
        ttk.Radiobutton(f_modes, text="📍 Chạm", variable=self.preview_action_mode, value="tap_only").pack(side="left", padx=2)
        ttk.Radiobutton(f_modes, text="✂️ Cắt mẫu", variable=self.preview_action_mode, value="crop_only").pack(side="left", padx=2)

        self.lbl_capture_hint = ttk.Label(f_modes, text="", foreground="#B71C1C", font=("Segoe UI", 9, "bold"))
        self.lbl_capture_hint.pack(side="left", padx=4)
        self.btn_cancel_capture = ttk.Button(f_modes, text="✖ Hủy", width=5, command=self._cancel_pending_action)
        self.btn_cancel_capture.pack(side="left", padx=2)
        self.btn_cancel_capture.pack_forget()

        self.lbl_zoom_info = ttk.Label(f_modes, text="Zoom: 100%", foreground="#37474F")
        self.lbl_zoom_info.pack(side="right", padx=4)
        ttk.Button(f_modes, text="🔍 100%", width=8, command=self.reset_preview_zoom).pack(side="right", padx=2)

        f_canvas_wrap = ttk.Frame(f_left)
        f_canvas_wrap.pack(fill="both", expand=True, padx=5, pady=5)
        f_canvas_wrap.grid_rowconfigure(0, weight=1)
        f_canvas_wrap.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(f_canvas_wrap, bg="#181818", cursor="crosshair")
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self._canvas_vscroll = ttk.Scrollbar(f_canvas_wrap, orient="vertical", command=self.canvas.yview)
        self._canvas_vscroll.grid(row=0, column=1, sticky="ns")
        self._canvas_hscroll = ttk.Scrollbar(f_canvas_wrap, orient="horizontal", command=self.canvas.xview)
        self._canvas_hscroll.grid(row=1, column=0, sticky="ew")
        self.canvas.config(yscrollcommand=self._canvas_vscroll.set, xscrollcommand=self._canvas_hscroll.set)

        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        # Zoom PREVIEW (xem trước trên máy tính - KHÔNG liên quan bước "zoom"
        # gửi cho giả lập) bằng Ctrl + lăn chuột, giống Photoshop/trình
        # duyệt. Windows/macOS bắn <MouseWheel> kèm event.delta; Linux (X11)
        # thường bắn <Button-4>/<Button-5> thay vì delta nên bind thêm 2 phím
        # đó để chạy được trên nhiều nền tảng.
        self.canvas.bind("<Control-MouseWheel>", self.on_canvas_ctrl_wheel)
        self.canvas.bind("<Control-Button-4>", self.on_canvas_ctrl_wheel)
        self.canvas.bind("<Control-Button-5>", self.on_canvas_ctrl_wheel)

        # Lăn chuột thường (không giữ Ctrl) = cuộn dọc Preview khi đã zoom
        # to hơn khung nhìn hiện tại; giữ thêm Shift để cuộn ngang.
        self.canvas.bind("<MouseWheel>", self.on_canvas_plain_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self.on_canvas_shift_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))
        # ESC hủy quét khung ảnh/tọa độ đang chờ (pending_action). Bind vào
        # bind_all để bắt được dù focus đang ở đâu trong cửa sổ chính (KHÔNG
        # ảnh hưởng ESC đóng các cửa sổ Toplevel riêng - _bind_esc_close() ở
        # đó bind trực tiếp lên từng Toplevel nên luôn được ưu tiên trước).
        self.root.bind_all("<Escape>", self._on_escape_key)

        f_right_container = ttk.Frame(self.paned)
        self.paned.add(f_right_container, weight=5)

        f_group_bar = ttk.Frame(f_right_container)
        f_group_bar.pack(fill="x", padx=5, pady=2)
        
        f_group_btns = ttk.Frame(f_group_bar)
        f_group_btns.pack(fill="x", anchor="w")
        ttk.Button(f_group_btns, text="☑️ Chọn tất cả", command=self.select_all_steps).pack(side="left", padx=2, pady=2)
        ttk.Button(f_group_btns, text="📦 Lưu Nhóm", command=self.save_selection_as_group).pack(side="left", padx=2, pady=2)
        ttk.Button(f_group_btns, text="📂 Chèn Nhóm...", command=self.insert_saved_group).pack(side="left", padx=2, pady=2)
        ttk.Button(f_group_btns, text="🔓 Bung Nhóm", command=self.expand_selected_group).pack(side="left", padx=2, pady=2)

        ttk.Label(f_group_bar, text="(Kéo-thả sắp xếp • Chuột phải vào hành động để sửa thông số / vào ô trống để thêm nhanh)",
                  foreground="#546E7A", font=("Segoe UI", 8, "italic")).pack(anchor="w", padx=2, pady=1)

        f_manual = ttk.LabelFrame(f_right_container, text=" Thêm Bước Thủ Công & Logic Vào Vị Trí Chọn ")
        f_manual.pack(fill="x", padx=5, pady=2)

        f_manual_sub1 = ttk.Frame(f_manual)
        f_manual_sub1.pack(fill="x", padx=2, pady=2)
        ttk.Button(f_manual_sub1, text="➕ Tìm & Click Ảnh", command=self.add_manual_wait_image).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="➕ Click Tọa Độ", command=self.add_manual_tap).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="➕ Vuốt (Swipe)", command=self.add_manual_swipe).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="🔍 Zoom (Pinch)", command=self.add_manual_zoom).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="⏳ Chờ (Sleep)", command=self.add_manual_sleep).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="⌨️ Gõ Chữ", command=self.add_manual_type_text).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="⌨️ Tổ Hợp Phím", command=self.add_manual_key_combo).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="🔤 Quét OCR", command=self.add_manual_ocr).pack(side="left", padx=2)
        ttk.Button(f_manual_sub1, text="📢 Popup Thông Báo", command=self.add_manual_popup).pack(side="left", padx=2)

        f_manual_sub2 = ttk.Frame(f_manual)
        f_manual_sub2.pack(fill="x", padx=2, pady=2)
        ttk.Button(f_manual_sub2, text="🔀 IF (1 Ảnh)", command=self.add_if_single_image).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="🔀 IF (Nhóm Ảnh)", command=self.add_if_multi_image).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="↪️ ELSE", command=self.add_else_step).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="⏹️ ENDIF", command=self.add_endif_step).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="🖼️ Quét Đa Ảnh (OR)", command=self.add_multi_image_step).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="📦+ Gộp Nhóm Đã Chọn", command=self.add_group_block).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="🏷️ Thêm Nhãn (Label)", command=self.add_manual_label).pack(side="left", padx=2)
        ttk.Button(f_manual_sub2, text="🔁 Khung IF/ELSE (2 Nhóm Lặp)", command=self.add_if_else_group_template).pack(side="left", padx=2)

        f_vars = ttk.LabelFrame(f_right_container, text=" Biến Số & Điều Kiện Nâng Cao ")
        f_vars.pack(fill="x", padx=5, pady=2)

        f_vars_sub = ttk.Frame(f_vars)
        f_vars_sub.pack(fill="x", padx=2, pady=2)
        ttk.Button(f_vars_sub, text="🔢 Đặt Biến", command=self.add_manual_set_var).pack(side="left", padx=2)
        ttk.Button(f_vars_sub, text="🔢 Tăng/Giảm Biến", command=self.add_manual_inc_var).pack(side="left", padx=2)
        ttk.Button(f_vars_sub, text="🔀 IF (Biến)", command=self.add_if_var).pack(side="left", padx=2)
        ttk.Button(f_vars_sub, text="🗂️ Nhóm Dữ Liệu", command=self.open_data_group_manager).pack(side="left", padx=2)
        ttk.Button(f_vars_sub, text="➡️ Lấy Dữ Liệu (Nhóm)", command=self.add_manual_next_data_item).pack(side="left", padx=2)
        ttk.Button(f_vars_sub, text="🔁 Lặp Lại (Continue)", command=self.add_continue_group).pack(side="left", padx=2)
        ttk.Button(f_vars_sub, text="⛔ Dừng Vòng Lặp Nhóm", command=self.add_break_group).pack(side="left", padx=2)

        f_nav = ttk.Frame(f_right_container)
        f_nav.pack(fill="x", padx=5, pady=2)
        ttk.Button(f_nav, text="▲ Lên", command=lambda: self.move_step(-1)).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(f_nav, text="▼ Xuống", command=lambda: self.move_step(1)).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(f_nav, text="❌ Xóa bước (Del)", command=self.delete_selected_step).pack(side="left", expand=True, fill="x", padx=1)
        ttk.Button(f_nav, text="Clear", command=self.clear_all_steps).pack(side="left", expand=True, fill="x", padx=1)

        f_tree_and_inspector = ttk.Frame(f_right_container)
        f_tree_and_inspector.pack(fill="both", expand=True, padx=5, pady=2)

        cols = ("idx", "type", "detail", "repeat", "conf", "timeout", "delay")
        self.tree = ttk.Treeview(f_tree_and_inspector, columns=cols, show="headings", height=14, selectmode="extended")
        self.tree.heading("idx", text="#")
        self.tree.heading("type", text="Loại")
        self.tree.heading("detail", text="Cấu trúc quy trình (Click chuột phải để sửa)")
        self.tree.heading("repeat", text="Lặp")
        self.tree.heading("conf", text="Độ khớp")
        self.tree.heading("timeout", text="Timeout(s)")
        self.tree.heading("delay", text="Delay(s)")

        self.tree.column("idx", width=35, anchor="center")
        self.tree.column("type", width=95, anchor="center")
        self.tree.column("detail", width=250)
        self.tree.column("repeat", width=55, anchor="center")
        self.tree.column("conf", width=60, anchor="center")
        self.tree.column("timeout", width=65, anchor="center")
        self.tree.column("delay", width=60, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<Double-1>", lambda e: self.open_step_edit_menu_at(self.tree.selection()[0] if self.tree.selection() else None, e.x_root, e.y_root))
        self.tree.bind("<<TreeviewSelect>>", self.on_step_selected)
        self.tree.bind("<Delete>", lambda e: self.delete_selected_step())

        self.f_inspector = ttk.LabelFrame(f_tree_and_inspector, text=" Ảnh Mẫu ", width=220)
        self.f_inspector.pack(side="right", fill="y", padx=5)
        self.f_inspector.pack_propagate(False)

        self.lbl_inspect_img = tk.Label(self.f_inspector, text="Chưa chọn ảnh", bg="#212121", fg="gray")
        self.lbl_inspect_img.pack(padx=5, pady=5, fill="both", expand=True)
        self.lbl_inspect_img.bind("<Double-1>", self.open_large_inspect_image)
        self._inspect_resize_job = None
        self.lbl_inspect_img.bind("<Configure>", self._on_inspect_label_resize)

        self.lbl_inspect_info = ttk.Label(self.f_inspector, text="", font=("Segoe UI", 8))
        self.lbl_inspect_info.pack(padx=5, pady=2)

        self.btn_change_img = ttk.Button(self.f_inspector, text="🔄 Đổi Ảnh Khác", state="disabled", command=self.change_step_image)
        self.btn_change_img.pack(padx=5, pady=3, fill="x")

        self.tree.tag_configure("tag_image", background="#E3F2FD", foreground="#0D47A1")
        self.tree.tag_configure("tag_tap", background="#E8F5E9", foreground="#1B5E20")
        self.tree.tag_configure("tag_swipe", background="#FFF8E1", foreground="#B78103")
        self.tree.tag_configure("tag_zoom", background="#E1F5FE", foreground="#01579B")
        self.tree.tag_configure("tag_group", background="#F3E5F5", foreground="#4A148C")
        self.tree.tag_configure("tag_logic", background="#FBE9E7", foreground="#BF360C")
        self.tree.tag_configure("tag_multi", background="#E0F2F1", foreground="#004D40")
        self.tree.tag_configure("tag_sleep", background="#ECEFF1", foreground="#37474F")
        self.tree.tag_configure("tag_key", background="#FFF3E0", foreground="#E65100")
        self.tree.tag_configure("tag_var", background="#FFFDE7", foreground="#F57F17")
        self.tree.tag_configure("tag_warn", background="#FFEBEE", foreground="#B71C1C")

        f_legend = ttk.Frame(f_right_container)
        f_legend.pack(fill="x", padx=5, pady=2)
        tk.Label(f_legend, text="■ Ảnh", bg="#E3F2FD", fg="#0D47A1", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Đa Ảnh", bg="#E0F2F1", fg="#004D40", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Tap", bg="#E8F5E9", fg="#1B5E20", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Swipe", bg="#FFF8E1", fg="#B78103", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Phím", bg="#FFF3E0", fg="#E65100", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Biến", bg="#FFFDE7", fg="#F57F17", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Logic", bg="#FBE9E7", fg="#BF360C", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)
        tk.Label(f_legend, text="■ Group", bg="#F3E5F5", fg="#4A148C", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2)

        # --- Nhật Ký Chạy (Run Log): ghi lại từng hành động đã thực hiện,
        # tìm thấy ảnh hay không, biến thay đổi ra sao, kết quả OCR, và lỗi
        # gì xảy ra khi CHẠY THỬ kịch bản. Đặt trong 1 pane riêng (kéo được
        # để chỉnh cao/thấp, kích thước cũng được lưu lại như khung khác).
        f_log = ttk.LabelFrame(self.vpaned, text=" 📜 Nhật Ký Chạy (Run Log) ")
        self.vpaned.add(f_log, weight=2)

        f_log_toolbar = ttk.Frame(f_log)
        f_log_toolbar.pack(fill="x", padx=4, pady=(4, 0))
        ttk.Button(f_log_toolbar, text="🗑️ Xóa Log", command=self._clear_run_log).pack(side="left", padx=2)
        ttk.Button(f_log_toolbar, text="💾 Lưu Log Ra File...", command=self._save_run_log_to_file).pack(side="left", padx=2)
        self.var_log_autoscroll = tk.BooleanVar(value=True)
        ttk.Checkbutton(f_log_toolbar, text="Tự cuộn xuống", variable=self.var_log_autoscroll).pack(side="left", padx=8)
        ttk.Label(f_log_toolbar, text="   ■ Info  ", foreground="#37474F", font=("Segoe UI", 8, "bold")).pack(side="left")
        ttk.Label(f_log_toolbar, text="■ Thành công  ", foreground="#1B5E20", font=("Segoe UI", 8, "bold")).pack(side="left")
        ttk.Label(f_log_toolbar, text="■ Cảnh báo  ", foreground="#E65100", font=("Segoe UI", 8, "bold")).pack(side="left")
        ttk.Label(f_log_toolbar, text="■ Lỗi", foreground="#B71C1C", font=("Segoe UI", 8, "bold")).pack(side="left")

        f_log_body = ttk.Frame(f_log)
        f_log_body.pack(fill="both", expand=True, padx=4, pady=4)

        log_scroll = ttk.Scrollbar(f_log_body, orient="vertical")
        self.txt_log = tk.Text(
            f_log_body, height=6, wrap="none", state="disabled",
            bg="#1E1E1E", fg="#ECEFF1", insertbackground="#ECEFF1",
            font=("Consolas", 9), yscrollcommand=log_scroll.set
        )
        log_scroll.config(command=self.txt_log.yview)
        log_scroll.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)

        self.txt_log.tag_configure("info", foreground="#B0BEC5")
        self.txt_log.tag_configure("success", foreground="#66BB6A")
        self.txt_log.tag_configure("warn", foreground="#FFA726")
        self.txt_log.tag_configure("error", foreground="#EF5350")
        self._log_line_count = 0
        self._LOG_MAX_LINES = 2000

        f_bot = ttk.Frame(self.root)
        f_bot.pack(fill="x", padx=10, pady=6)

        ttk.Button(f_bot, text="📁 Nạp JSON", command=self.load_macro_file).pack(side="left", padx=4)
        ttk.Button(f_bot, text="💾 Lưu JSON", command=self.save_macro_file).pack(side="left", padx=4)
        ttk.Button(f_bot, text="📋 Đăng Ký Tác Vụ", command=self.register_current_task).pack(side="left", padx=4)
        ttk.Button(f_bot, text="🖼️ Thư Viện Ảnh", command=self.open_template_library).pack(side="left", padx=4)
        ttk.Button(f_bot, text="🔍 Kiểm Tra Kịch Bản", command=self.validate_current_task).pack(side="left", padx=4)

        self.btn_run = ttk.Button(f_bot, text="▶ CHẠY THỬ (ADB)", command=self.run_macro)
        self.btn_run.pack(side="right", padx=4)
        self.btn_stop = ttk.Button(f_bot, text="⏹ DỪNG (F8)", state="disabled", command=self.stop_macro)
        self.btn_stop.pack(side="right", padx=4)
        # Chạy CHỈ những bước đang được bôi đen (chọn) trong danh sách -
        # tiện để thử lại nhanh 1-vài bước mà không cần chạy lại từ đầu.
        self.btn_run_selected = ttk.Button(f_bot, text="▶ Chạy Đã Chọn", command=self.run_selected_steps)
        self.btn_run_selected.pack(side="right", padx=4)

        self.tree.bind("<Control-a>", self.select_all_steps)

    def show_context_menu_on_blank(self, x_root, y_root):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="➕ Thêm Tìm & Click Ảnh", command=self.add_manual_wait_image)
        menu.add_command(label="➕ Thêm Click Tọa Độ (Tap)", command=self.add_manual_tap)
        menu.add_command(label="➕ Thêm Vuốt (Swipe)", command=self.add_manual_swipe)
        menu.add_command(label="🔍 Thêm Zoom (Pinch)", command=self.add_manual_zoom)
        menu.add_command(label="⏳ Thêm Chờ (Sleep)", command=self.add_manual_sleep)
        menu.add_separator()
        menu.add_command(label="⌨️ Thêm Gõ Chữ", command=self.add_manual_type_text)
        menu.add_command(label="⌨️ Thêm Tổ Hợp Phím", command=self.add_manual_key_combo)
        menu.add_command(label="🔤 Thêm Quét OCR", command=self.add_manual_ocr)
        menu.add_command(label="📢 Thêm Popup Thông Báo", command=self.add_manual_popup)
        menu.add_separator()
        menu.add_command(label="🔀 Thêm IF (Ảnh)", command=self.add_if_single_image)
        menu.add_command(label="🔀 Thêm IF (Biến)", command=self.add_if_var)
        menu.add_command(label="↪️ Thêm ELSE", command=self.add_else_step)
        menu.add_command(label="⏹️ Thêm ENDIF", command=self.add_endif_step)
        menu.add_command(label="🔁 Thêm Khung IF/ELSE (2 Nhóm Lặp)", command=self.add_if_else_group_template)
        menu.add_separator()
        menu.add_command(label="🔢 Đặt Biến (Set Var)", command=self.add_manual_set_var)
        menu.add_command(label="🔢 Tăng/Giảm Biến (Inc Var)", command=self.add_manual_inc_var)
        menu.add_command(label="🔁 Thêm Lặp Lại (Continue Nhóm)", command=self.add_continue_group)
        menu.add_command(label="⛔ Dừng Vòng Lặp Nhóm", command=self.add_break_group)
        
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def open_step_edit_menu_at(self, idx_or_iid, x_root, y_root):
        if idx_or_iid is None:
            self.show_context_menu_on_blank(x_root, y_root)
            return

        try:
            idx = int(idx_or_iid)
        except ValueError:
            return

        if idx < 0 or idx >= len(self.steps):
            return

        self.tree.selection_set(str(idx))
        step = self.steps[idx]
        act = step.get("action")

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"📝 Sửa Ghi Chú ({step.get('comment', '')})", 
                         command=lambda: self._edit_step_field(idx, "comment"))
        menu.add_command(label=f"🔁 Sửa Lặp ({self._format_repeat_display(step)})", 
                         command=lambda: self._edit_step_field(idx, "repeat"))
        menu.add_command(label=f"⏱ Sửa Delay sau bước ({step.get('delay', 1.0)}s)", 
                         command=lambda: self._edit_step_field(idx, "delay"))

        if act in ("wait_image", "if_image", "multi_image"):
            menu.add_separator()
            menu.add_command(label=f"🎯 Sửa Độ Khớp ({step.get('conf', 0.80)})", 
                             command=lambda: self._edit_step_field(idx, "conf"))
            menu.add_command(label=f"⏳ Sửa Timeout ({step.get('timeout', 8)}s)", 
                             command=lambda: self._edit_step_field(idx, "timeout"))
            menu.add_command(label=f"⚡ Sửa Tốc Độ Quét ({step.get('scan_interval', 0.1)}s)",
                             command=lambda: self._edit_step_field(idx, "scan_interval"))
            region_txt = "đã đặt" if step.get("region") else "toàn màn hình"
            menu.add_command(label=f"📐 Chọn Vùng Quét ({region_txt})",
                             command=lambda: self._arm_region_recapture(idx))
            if step.get("region"):
                menu.add_command(label="🗑 Bỏ Vùng Quét (quét lại toàn màn hình)",
                                 command=lambda: self._clear_step_region(idx))
            # if_image KHÔNG BAO GIỜ click (chỉ dùng làm điều kiện IF) nên
            # không cần tuỳ chọn Click/Lệch Điểm Click - chỉ áp dụng cho
            # wait_image (Tìm & Click 1 ảnh) và multi_image (Quét đa ảnh).
            if act in ("wait_image", "multi_image"):
                does_click = step.get("click", True)
                click_lbl = "✅ Có Click Khi Thấy Ảnh" if does_click else "🚫 KHÔNG Click (chỉ làm điều kiện)"
                menu.add_command(label=f"🖱️ Bật/Tắt Click Khi Thấy Ảnh ({click_lbl})",
                                 command=lambda: self._edit_step_field(idx, "click_toggle"))
                if does_click:
                    off = step.get("click_offset") or [0, 0]
                    off_txt = f"lệch {off[0]:+d}, {off[1]:+d} px" if (off[0] or off[1]) else "click đúng tâm ảnh"
                    menu.add_command(label=f"🎯 Đặt Lệch Điểm Click ({off_txt})",
                                     command=lambda: self._edit_step_field(idx, "click_offset"))
            # BUG CŨ: điều kiện chỉ kiểm tra "template" (số ít), nhưng if_image
            # (nhóm ảnh) và multi_image (quét đa ảnh) lưu ảnh ở "templates"
            # (số nhiều, list) -> menu đổi ảnh không bao giờ hiện ra cho 2 loại
            # bước này. Nay xử lý cả 2 trường hợp.
            if "template" in step:
                tpl_display = step.get("template") or "⚠️ chưa chọn"
                menu.add_command(label=f"🖼️ Chọn/Quét Lại Ảnh Bằng Preview... ({tpl_display})",
                                 command=lambda: self._arm_image_recapture(idx))
                # TRƯỚC ĐÂY: chỉ hiện khi đã có sẵn "template" (dùng để ĐỔI
                # ảnh) -> bước RỖNG (tạo qua ESC, template=None) không có
                # cách nào lấy ảnh từ file có sẵn, buộc phải quét Preview.
                # Nay luôn hiện, đổi nhãn tuỳ trường hợp rỗng hay đã có ảnh.
                lbl_pick_file = ("🖼️ Đổi Bằng File Ảnh Có Sẵn Trong Thư Mục templates..."
                                  if step.get("template") else
                                  "🖼️ Lấy Từ File Ảnh Có Sẵn Trong Thư Mục templates...")
                menu.add_command(label=lbl_pick_file, command=self.change_step_image)
            elif "templates" in step:
                menu.add_command(label=f"🖼️ Quản lý {len(step.get('templates', []))} ảnh trong nhóm...",
                                 command=lambda: self.manage_group_templates(idx))

            # on_fail (retry/skip_to_label khi KHÔNG thấy ảnh) - chỉ áp
            # dụng cho wait_image/if_image, KHÔNG áp dụng cho multi_image
            # (chưa hỗ trợ, xem logic_engine.py).
            if act in ("wait_image", "if_image"):
                menu.add_separator()
                on_fail = step.get("on_fail", "continue")
                if on_fail == "retry":
                    on_fail_txt = f"retry (x{step.get('on_fail_retries', 1)})"
                elif on_fail == "skip_to_label":
                    on_fail_txt = f"skip_to_label -> '{step.get('skip_to_label_name', '?')}'"
                else:
                    on_fail_txt = "continue (mặc định)"
                menu.add_command(label=f"↩️ Khi KHÔNG thấy ảnh - on_fail ({on_fail_txt})",
                                 command=lambda: self._edit_step_field(idx, "on_fail_config"))

            # click_jitter (rải ngẫu nhiên điểm click) - chỉ có ý nghĩa với
            # các bước THỰC SỰ click (wait_image/multi_image có click=True),
            # if_image không click nên không cần.
            if act in ("wait_image", "multi_image") and step.get("click", True):
                jitter = step.get("click_jitter") or [0, 0]
                jitter_txt = f"±{jitter[0]},±{jitter[1]} px" if (jitter[0] or jitter[1]) else "TẮT"
                menu.add_command(label=f"🎲 Rải Ngẫu Nhiên Điểm Click - click_jitter ({jitter_txt})",
                                 command=lambda: self._edit_step_field(idx, "click_jitter"))

            if act == "multi_image":
                click_all = step.get("click_all", False)
                click_all_lbl = "✅ Click TẤT CẢ vị trí khớp" if click_all else "🎯 Chỉ Click 1 vị trí tốt nhất (mặc định)"
                menu.add_command(label=f"🖱️ Chế Độ Click - Quét Đa Ảnh ({click_all_lbl})",
                                 command=lambda: self._edit_step_field(idx, "click_all_toggle"))

        elif act == "tap":
            # THIẾU TRƯỚC ĐÂY: bước tap (kể cả bước RỖNG tạo qua ESC) không
            # có menu nào để chọn/chọn lại tọa độ - phải xóa đi làm lại.
            menu.add_separator()
            pos = step.get("pos")
            pos_display = f"{int(pos[0]*100)}%, {int(pos[1]*100)}%" if pos else "⚠️ chưa chọn"
            menu.add_command(label=f"🎯 Chọn/Chọn Lại Tọa Độ Bằng Preview... ({pos_display})",
                             command=lambda: self._arm_tap_recapture(idx))
            hold_ms = step.get("hold_ms", 0)
            hold_txt = f"{hold_ms}ms" if hold_ms else "TẮT (tap nhanh)"
            menu.add_command(label=f"✋ Giữ Tay - Long Click ({hold_txt})",
                             command=lambda: self._edit_step_field(idx, "tap_hold_ms"))
            jitter = step.get("click_jitter") or [0, 0]
            jitter_txt = f"±{jitter[0]},±{jitter[1]} px" if (jitter[0] or jitter[1]) else "TẮT"
            menu.add_command(label=f"🎲 Rải Ngẫu Nhiên Điểm Click - click_jitter ({jitter_txt})",
                             command=lambda: self._edit_step_field(idx, "click_jitter"))

        elif act == "key_combo":
            # THIẾU TRƯỚC ĐÂY: không có nhánh nào xử lý key_combo trong menu
            # sửa -> không thể sửa lại tổ hợp phím sau khi đã thêm.
            menu.add_separator()
            keys_display = "+".join(k.replace("KEYCODE_", "") for k in step.get("keys", []))
            menu.add_command(label=f"⌨️ Sửa Tổ Hợp Phím ({keys_display})",
                             command=lambda: self._edit_step_field(idx, "key_combo_keys"))

        elif act == "ocr_text":
            menu.add_separator()
            menu.add_command(label=f"🔤 Sửa Tên Biến Lưu Kết Quả ({step.get('var', 'ocr_text')})",
                             command=lambda: self._edit_step_field(idx, "ocr_var"))
            menu.add_command(label="🔤 Chọn Lại Vùng Quét", command=lambda: self._arm_ocr_recapture(idx))

        elif act == "show_popup":
            menu.add_separator()
            menu.add_command(label=f"📢 Sửa Nội Dung Thông Báo ({step.get('message', '')})",
                             command=lambda: self._edit_step_field(idx, "popup_message"))
            dur = step.get("duration", 0)
            dur_display = f"{dur}s" if dur else "chờ bấm Đóng"
            menu.add_command(label=f"⏱ Sửa Thời Gian Hiện ({dur_display})",
                             command=lambda: self._edit_step_field(idx, "popup_duration"))
            menu.add_command(label="🎨 Sửa Màu Nền/Chữ/Độ Mờ",
                             command=lambda: self._edit_step_field(idx, "popup_style"))
            pos_display = "đã đặt" if step.get("pos_box") else "mặc định (dải trên)"
            menu.add_command(label=f"📍 Chọn Vị Trí Hiển Thị ({pos_display})",
                             command=lambda: self._arm_popup_pos(idx))
            if step.get("pos_box"):
                menu.add_command(label="↩️ Bỏ Vị Trí Tuỳ Chỉnh (về mặc định)",
                                 command=lambda: self._clear_popup_pos(idx))

        elif act in ("set_var", "inc_var", "if_var"):
            menu.add_separator()
            if act == "if_var":
                menu.add_command(label=f"🔀 Cấu hình điều kiện IF ({step.get('var')} {step.get('op')} {step.get('value')})", 
                                 command=lambda: self._edit_step_field(idx, "if_var_params"))
            elif act == "set_var":
                menu.add_command(label=f"🔢 Cấu hình Đặt Biến ({step.get('var')} = {step.get('value')})", 
                                 command=lambda: self._edit_step_field(idx, "set_var_params"))
            elif act == "inc_var":
                menu.add_command(label=f"🔢 Cấu hình Tăng/Giảm Biến ({step.get('var')} {step.get('amount')})", 
                                 command=lambda: self._edit_step_field(idx, "inc_var_params"))

        elif act == "type_text":
            menu.add_separator()
            menu.add_command(label=f"⌨️ Sửa Nội Dung Gõ ({step.get('text', '')})", 
                             command=lambda: self._edit_step_field(idx, "text_content"))

        elif act == "swipe":
            # THIẾU TRƯỚC ĐÂY: swipe không có menu sửa nào cả (không sửa được
            # Duration sau khi tạo). Nay thêm cả Duration lẫn "Giữ Cuối" -
            # giữ yên tay tại điểm đến 1 khoảng ngắn trước khi nhả, để KÉO
            # THANH TRƯỢT (slider) không bị game hiểu nhầm thành vuốt/ném rồi
            # bật ngược lại (xem docstring adb_helper.py::swipe_hold()).
            menu.add_separator()
            has_pts = step.get("from") and step.get("to")
            pts_display = "đã chọn" if has_pts else "⚠️ chưa chọn"
            menu.add_command(label=f"🎯 Chọn/Chọn Lại Điểm Đầu-Cuối Bằng Preview... ({pts_display})",
                             command=lambda: self._arm_swipe_recapture(idx))
            menu.add_command(label=f"⏳ Sửa Thời Gian Kéo - Duration ({step.get('duration', 250)}ms)",
                             command=lambda: self._edit_step_field(idx, "swipe_duration"))
            hold_ms = step.get("hold_ms", 0)
            hold_txt = f"{hold_ms}ms" if hold_ms else "TẮT (swipe thường)"
            menu.add_command(label=f"🐢 Sửa Giữ Cuối - chống bật ngược thanh trượt ({hold_txt})",
                             command=lambda: self._edit_step_field(idx, "swipe_hold_ms"))
            jitter = step.get("click_jitter") or [0, 0]
            jitter_txt = f"±{jitter[0]},±{jitter[1]} px" if (jitter[0] or jitter[1]) else "TẮT"
            menu.add_command(label=f"🎲 Rải Ngẫu Nhiên 2 Đầu Vuốt - click_jitter ({jitter_txt})",
                             command=lambda: self._edit_step_field(idx, "click_jitter"))

        elif act == "zoom":
            menu.add_separator()
            has_center = bool(step.get("center"))
            center_display = "đã chọn" if has_center else "⚠️ chưa chọn"
            menu.add_command(label=f"🎯 Chọn/Chọn Lại Tâm Bằng Preview... ({center_display})",
                             command=lambda: self._arm_zoom_recapture(idx))
            is_in = step.get("end_radius", 260) > step.get("start_radius", 70)
            menu.add_command(
                label=f"🔍 Sửa Tham Số Zoom (hiện: {'Phóng To' if is_in else 'Thu Nhỏ'}, {step.get('duration', 400)}ms)...",
                command=lambda: self._edit_zoom_params(idx))

        elif act == "label":
            menu.add_separator()
            menu.add_command(label=f"🏷️ Sửa Tên Nhãn ({step.get('name', '')})",
                             command=lambda: self._edit_step_field(idx, "label_name"))

        menu.add_separator()
        menu.add_command(label="❌ Xóa Bước Này", command=self.delete_selected_step)

        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()


"""
dashboard_accounts.py — Xoay Vòng Tài Khoản: chạy lần lượt nhiều tài khoản trên CÙNG 1 giả lập (đăng xuất - đổi - đăng nhập - chạy các Hoạt Động đã chọn), và cửa sổ 'Quản Lý Tài Khoản' (thêm/sửa/xoá tài khoản, lọc theo Nhóm).

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import json
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from adb_helper import ADBHelper
from logic_engine import LogicEngine
from window_finder import WindowFinder
import task_registry
import account_manager
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, FlowBar, _bind_esc_close


class AccountsMixin:
    # ================= CHẠY XOAY VÒNG TÀI KHOẢN (tự bật giả lập + đổi tài khoản) =================
    def _start_run_with_accounts(self, selected, selected_emulators):
        self.accounts = account_manager.load_accounts()

        # KHÔNG loại giả lập đang bận ở bước này nữa - vẫn cho người dùng
        # gán Tài khoản cho MỌI giả lập đã tick ở màn hình chính (kể cả
        # đang bận), rồi mới tách phần bận ra XẾP HÀNG CHỜ ở
        # _launch_run_with_accounts (sau khi đã có đủ assignment gán cho
        # từng giả lập) thay vì loại âm thầm ngay từ đầu.

        # Tài khoản không còn gán cố định theo giả lập (xem account_manager.py)
        # - trước khi chạy, mở popup để CHỌN THỦ CÔNG tài khoản xoay vòng cho
        # TỪNG giả lập đã tick sẵn ở màn hình chính. Để trống 1 giả lập =
        # chạy các tác vụ đã tick 1 lần trên giả lập đó, không xoay vòng.
        account_items = [(a.get("id"), a.get("ten_hien_thi") or a.get("username") or a.get("id"))
                         for a in self.accounts]
        account_group_of = {a.get("id"): (a.get("nhom") or "") for a in self.accounts}
        emulator_items = [(e.index, f"#{e.index} - {e.name}") for e in selected_emulators]
        current = {e.index: [] for e in selected_emulators}

        def _on_confirm(assignment):
            self._launch_run_with_accounts(selected, selected_emulators, assignment)

        self._open_gan_may_tk_dialog(
            self.root, "Chọn Tài Khoản xoay vòng cho từng giả lập", emulator_items, account_items,
            account_group_of, current, _on_confirm, allow_toggle_emulator=False,
            intro_text="Các giả lập dưới đây đã được tick sẵn ở màn hình chính. Bấm '👤 Chọn TK' để chọn tài "
                       "khoản xoay vòng cho TỪNG giả lập - để trống 1 giả lập nếu chỉ muốn chạy các tác vụ đã "
                       "tick 1 lần trên đó, không xoay vòng tài khoản.")

    def _launch_run_with_accounts(self, selected, selected_emulators, assignment):
        available, busy = self._split_busy_emulators(selected_emulators)
        for e in busy:
            self._queue_job(e, {"kind": "manual_accounts", "selected": selected,
                                 "account_ids": assignment.get(e.index, [])},
                             "xoay vòng tài khoản")
        selected_emulators = available
        if not selected_emulators:
            if not busy:
                messagebox.showwarning("Lưu ý", "Tất cả giả lập đã chọn đang bận (có lịch hẹn giờ hoặc phiên khác "
                                                 "đang chạy).\nThử lại sau.")
            return

        self.is_running = True
        self.stop_flag = False
        self.pause_flag = False
        self.btn_pause.set_text("⏸ Tạm Dừng")
        self.active_threads = len(selected_emulators)
        self.btn_run.set_state("disabled")
        self._refresh_run_control_buttons()

        for entry in selected:
            task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
            self.task_progress[task_id] = {"total": len(selected_emulators), "done": 0, "error": 0, "running": 0, "stopped": 0}
            lbl = self.task_status_lbl.get(task_id)
            if lbl:
                lbl.config(text="⏳ Đang chờ", fg=COL_TEXT_MUTED)

        self._update_status_label()
        names = ", ".join(e.name for e in selected_emulators)
        self._log("info", f"══════ Bắt đầu phiên CHẠY XOAY VÒNG TÀI KHOẢN: {len(selected)} tác vụ trên [{names}] ══════")

        for emulator in selected_emulators:
            self._busy_emulator_indexes.add(emulator.index)
            account_ids = assignment.get(emulator.index, [])
            threading.Thread(target=self._worker_run_emulator_with_accounts,
                              args=(emulator, selected, account_ids), daemon=True).start()

    def _worker_run_emulator_with_accounts(self, emulator, selected, account_ids):
        # 1) Đảm bảo giả lập ĐANG BẬT VÀ SẴN SÀNG - tự khởi động qua
        # ldconsole nếu đang tắt (đây chính là "tự nhận diện bật/tắt, nếu
        # tắt thì khởi động" mà tính năng xoay vòng tài khoản cần).
        ready_info, _auto_started = self.emu_manager.ensure_running(
            emulator.index, timeout=120,
            on_log=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )
        if not ready_info:
            self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
            return
        emulator = ready_info  # dùng thông tin MỚI NHẤT (hwnd/serial có thể đổi sau khi vừa bật lại)

        if not self.emu_manager.ensure_adb_connected(emulator):
            self._log("error", f"Không thấy giả lập trong 'adb devices' (serial: {emulator.adb_serial}) sau khi "
                                f"khởi động. Bỏ qua giả lập này.", emulator_name=emulator.name)
            self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
            return

        adb = ADBHelper()
        adb.device_id = emulator.adb_serial
        adb.update_resolution()
        self._log("info", f"Độ phân giải nhận diện: {adb.screen_w}x{adb.screen_h}px", emulator_name=emulator.name)

        wf = WindowFinder(adb)
        attached = wf.attach_hwnd(emulator.hwnd) if emulator.hwnd else False
        if not attached:
            wf.find_ld_windows()

        if wf.ensure_window_visible():
            self._log("warn", f"Cửa sổ LDPlayer '{emulator.name}' đang bị THU NHỎ - đã tự khôi phục lại.",
                       emulator_name=emulator.name)
            time.sleep(0.5)

        engine = LogicEngine(
            adb,
            stop_checker=self._make_stop_checker(),
            popup_notifier=lambda msg, dur=0, _wf=wf: self._show_ingame_popup(_wf, msg, dur),
            logger=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )

        # 2) Danh sách tài khoản đã CHỌN THỦ CÔNG cho giả lập này (qua popup
        # '👤 Chọn TK' ngay lúc bấm CHẠY - xem _start_run_with_accounts).
        # Không chọn tài khoản nào -> chạy tác vụ 1 lần bình thường (không
        # xoay vòng) thay vì bỏ trắng cả phiên chạy.
        accounts_by_id = {a.get("id"): a for a in self.accounts}
        accounts = [accounts_by_id[aid] for aid in account_ids
                    if aid in accounts_by_id and accounts_by_id[aid].get("bat", True)]
        if not accounts:
            self._log("warn", f"Giả lập '{emulator.name}' (#{emulator.index}) không chọn Tài khoản nào để xoay "
                               f"vòng - chạy các tác vụ đã chọn 1 lần, không xoay vòng.",
                       emulator_name=emulator.name)
            for entry in selected:
                if self.stop_flag:
                    break
                self._exec_entry(engine, emulator, entry, preset_vars=None, tracked=True)
            self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
            return

        login_entry = task_registry.find_task(self.tasks, "account_login")
        logout_entry = task_registry.find_task(self.tasks, "account_logout")
        if not login_entry:
            self._log("error", "Chưa có Hoạt Động với id 'account_login' - hãy soạn kịch bản đăng nhập (dùng "
                                "{tk_user} / {tk_pass} ở bước Gõ Chữ) rồi Đăng Ký Tác Vụ với tên file "
                                "tasks/account_login.json. Đã bỏ qua xoay vòng cho giả lập này.",
                       emulator_name=emulator.name)
            self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
            return
        if not logout_entry:
            self._log("warn", "Chưa có Hoạt Động với id 'account_logout' - sẽ đăng nhập tài khoản mới mà KHÔNG "
                               "đăng xuất tài khoản trước đó (nên soạn thêm tasks/account_logout.json để tránh "
                               "đăng nhập chồng).", emulator_name=emulator.name)

        # 3) Lần lượt từng tài khoản: đăng xuất (nếu có) -> đăng nhập (điền
        # {tk_user}/{tk_pass}) -> chạy các tác vụ đã tick -> tài khoản kế tiếp.
        for acc in accounts:
            if self.stop_flag:
                break

            ten = acc.get("ten_hien_thi") or acc.get("username") or acc.get("id")
            self._log("info", f"═══ Tài khoản: {ten} ═══", emulator_name=emulator.name)

            if logout_entry:
                self._exec_entry(engine, emulator, logout_entry, preset_vars=None, tracked=False)
                if self.stop_flag:
                    break

            preset_vars = {"tk_user": acc.get("username", ""), "tk_pass": acc.get("password", "")}
            ok_login = self._exec_entry(engine, emulator, login_entry, preset_vars=preset_vars, tracked=False)
            if not ok_login:
                self._log("error", f"Đăng nhập thất bại cho tài khoản '{ten}' - bỏ qua tài khoản này, chuyển "
                                    f"tiếp tài khoản kế tiếp.", emulator_name=emulator.name)
                continue

            for entry in selected:
                if self.stop_flag:
                    break
                self._exec_entry(engine, emulator, entry, preset_vars=preset_vars, tracked=True)

            if not self.stop_flag:
                account_manager.mark_run(self.accounts, acc.get("id"))
                self._log("success", f"Hoàn thành tài khoản '{ten}' trên giả lập '{emulator.name}'.",
                           emulator_name=emulator.name)

        self._apply_post_run_options(engine, emulator)
        self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))

    def _open_account_manager(self):
        self.accounts = account_manager.load_accounts()

        win = tk.Toplevel(self.root)
        win.title("Quản Lý Tài Khoản (Xoay Vòng)")
        win.configure(bg=COL_PANEL)
        win.geometry("960x560")
        win.minsize(720, 460)
        _bind_esc_close(win)

        tk.Label(win, text="👥 Danh Sách Tài Khoản Xoay Vòng", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(
            win,
            text="Tài khoản ở đây KHÔNG gán cố định theo 1 giả lập nào - bạn tự chọn tài khoản chạy trên giả lập "
                 "nào ngay lúc bấm '👥 Xoay Vòng Tài Khoản' hoặc lúc soạn 1 lịch hẹn giờ (dùng lại được cùng danh "
                 "sách này cho bất kỳ giả lập/lịch nào). Có thể gắn 1 Nhóm - gõ tên tuỳ ý, không giới hạn chỉ "
                 "'Clone' / 'Acc chính' (dùng ô 'Thêm Nhóm mới' ở trên để lưu hẳn 1 tên Nhóm vào danh sách gợi ý, "
                 "hiện sẵn cho cả những lần sau dù chưa có tài khoản nào thuộc nhóm đó) - để lọc/chọn nhanh. Khi "
                 "xoay vòng: Dashboard tự BẬT giả lập nếu đang tắt, "
                 "rồi lần lượt từng tài khoản: Đăng Xuất -> Đăng Nhập (điền {tk_user}/{tk_pass}) -> chạy các tác vụ "
                 "đang tick -> sang tài khoản kế tiếp. Cần soạn sẵn 2 Hoạt Động 'account_login' và 'account_logout' "
                 "(xem '📖 Hướng Dẫn').",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=920, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        filter_bar = tk.Frame(win, bg=COL_PANEL)
        filter_bar.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(filter_bar, text="Lọc nhanh theo Nhóm:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8)).pack(side="left", padx=(0, 6))
        filter_btns_frame = FlowBar(filter_bar, bg=COL_PANEL)
        filter_btns_frame.pack(side="left", fill="x", expand=True)

        # Thêm hẳn 1 tên Nhóm MỚI vào danh sách GỢI Ý đã lưu (account_groups.json)
        # - khác với gõ tay trực tiếp vào ô 'Nhóm' của 1 dòng tài khoản (chỉ lưu
        # cho đúng dòng đó): tên thêm ở đây sẽ hiện sẵn trong combobox 'Nhóm' của
        # TẤT CẢ các dòng (kể cả dòng mới thêm sau) NGAY CẢ KHI chưa có tài khoản
        # nào gán vào nhóm đó.
        new_group_var = tk.StringVar()
        RoundedButton(filter_bar, "➕ Thêm Nhóm", command=lambda: _add_group_preset(),
                      bg=COL_BLUE, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"),
                      padx=8, pady=3).pack(side="right", padx=(4, 0))
        tk.Entry(filter_bar, textvariable=new_group_var, width=12, bg=COL_PANEL, fg=COL_TEXT,
                 insertbackground=COL_TEXT, relief="flat").pack(side="right", padx=(4, 0))
        tk.Label(filter_bar, text="Thêm Nhóm mới:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8)).pack(side="right", padx=(10, 0))

        header = tk.Frame(win, bg=COL_HEADER)
        header.pack(fill="x", padx=10)
        for text, w in [("Bật", 4), ("Tên hiển thị", 14), ("Username", 14), ("Password", 14),
                         ("Nhóm", 10), ("Ghi chú", 12), ("Chạy cuối", 14)]:
            tk.Label(header, text=text, bg=COL_HEADER, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"),
                     width=w, anchor="w").pack(side="left", padx=2, pady=6)

        # ----- Thanh nút dưới cùng (➕ Thêm Tài Khoản / 💾 Lưu Tất Cả) - PACK
        # TRƯỚC vùng cuộn (side='bottom') để LUÔN CHIẾM SẴN chỗ, không bị
        # khuất trên cửa sổ nhỏ (xem giải thích trong _open_multi_select_dialog).
        # Nội dung (2 nút) được thêm vào SAU khi đã có đủ hàm _add_row/_save_all. -----
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

        # Gợi ý Nhóm: danh sách đã LƯU SẴN (account_groups.json - mặc định
        # 'Acc chính'/'Clone' nếu chưa từng lưu, có thể bổ sung thêm qua ô
        # 'Thêm Nhóm mới' phía trên) + nhóm đã có sẵn trong dữ liệu tài
        # khoản nhưng chưa được lưu vào danh sách gợi ý - vẫn gõ tay được
        # tên nhóm khác tuỳ ý (combobox KHÔNG readonly).
        saved_presets = account_manager.load_group_presets()
        existing_groups = sorted({(a.get("nhom") or "").strip() for a in self.accounts if (a.get("nhom") or "").strip()})
        group_suggestions = list(saved_presets) + [g for g in existing_groups if g not in saved_presets]

        def _add_row(acc):
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=2)

            bat_var = tk.BooleanVar(value=bool(acc.get("bat", True)))
            DarkCheck(row, "", bat_var, bg=COL_PANEL_ALT, box_size=14).pack(side="left", padx=(6, 2), pady=4)

            ten_var = tk.StringVar(value=acc.get("ten_hien_thi", ""))
            tk.Entry(row, textvariable=ten_var, width=14, bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2, pady=4)

            user_var = tk.StringVar(value=acc.get("username", ""))
            tk.Entry(row, textvariable=user_var, width=14, bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2)

            pass_var = tk.StringVar(value=acc.get("password", ""))
            tk.Entry(row, textvariable=pass_var, width=14, show="•", bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2)

            nhom_var = tk.StringVar(value=acc.get("nhom", ""))
            nhom_combo = ttk.Combobox(row, textvariable=nhom_var, values=group_suggestions, width=12)
            nhom_combo.pack(side="left", padx=2)

            ghichu_var = tk.StringVar(value=acc.get("ghi_chu", ""))
            tk.Entry(row, textvariable=ghichu_var, width=12, bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2)

            tk.Label(row, text=acc.get("lan_chay_cuoi") or "-", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                     font=("Segoe UI", 8), width=14, anchor="w").pack(side="left", padx=2)

            rid = acc.get("id") or account_manager.new_account_id()
            rw = {
                "id": rid, "bat_var": bat_var, "ten_var": ten_var, "user_var": user_var,
                "pass_var": pass_var, "nhom_var": nhom_var, "nhom_combo": nhom_combo, "ghichu_var": ghichu_var,
                "lan_chay_cuoi": acc.get("lan_chay_cuoi"), "row": row,
            }

            def _delete(rid=rid, row=row):
                row.destroy()
                row_widgets[:] = [x for x in row_widgets if x["id"] != rid]

            RoundedButton(row, "🗑", command=_delete, bg=COL_RED, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 8, "bold"), padx=8, pady=2).pack(side="left", padx=4)

            row_widgets.append(rw)

        for acc in self.accounts:
            _add_row(acc)

        def _rebuild_filter_buttons():
            """Vẽ lại hàng nút lọc nhanh theo Nhóm - gọi lại sau khi Lưu Tất
            Cả để nhóm MỚI người dùng vừa gõ (chưa từng có trước đó) cũng
            xuất hiện thành nút lọc ngay, không cần đóng mở lại cửa sổ."""
            filter_btns_frame.clear()
            groups_now = sorted({(rw["nhom_var"].get() or "").strip() for rw in row_widgets if (rw["nhom_var"].get() or "").strip()})

            def _apply_filter(g):
                for rw in row_widgets:
                    match = (g is None) or ((rw["nhom_var"].get() or "").strip() == g)
                    if match:
                        rw["row"].pack(fill="x", pady=2)
                    else:
                        rw["row"].pack_forget()

            filter_btns_frame.add(RoundedButton(filter_btns_frame, "Tất cả", command=lambda: _apply_filter(None),
                                                 bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"),
                                                 padx=8, pady=3))
            for g in groups_now:
                filter_btns_frame.add(RoundedButton(filter_btns_frame, g, command=lambda g=g: _apply_filter(g),
                                                     bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"),
                                                     padx=8, pady=3))

        _rebuild_filter_buttons()

        def _add_group_preset():
            """Lưu tên Nhóm mới gõ ở ô 'Thêm Nhóm mới' vào account_groups.json,
            rồi cập nhật NGAY combobox 'Nhóm' của mọi dòng đang mở + nút lọc
            nhanh - không cần đóng mở lại cửa sổ này."""
            name = new_group_var.get().strip()
            if not name:
                return
            updated_presets = account_manager.add_group_preset(name)
            new_group_var.set("")
            groups_in_rows = sorted({(rw["nhom_var"].get() or "").strip() for rw in row_widgets
                                      if (rw["nhom_var"].get() or "").strip()})
            all_suggestions = list(updated_presets) + [g for g in groups_in_rows if g not in updated_presets]
            for rw in row_widgets:
                rw["nhom_combo"]["values"] = all_suggestions
            _rebuild_filter_buttons()

        btn_bar.add(RoundedButton(btn_bar, "➕ Thêm Tài Khoản", command=lambda: _add_row({}),
                                   bg=COL_BLUE, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))

        def _save_all():
            new_entries = []
            for rw in row_widgets:
                new_entries.append({
                    "id": rw["id"],
                    "ten_hien_thi": rw["ten_var"].get().strip(),
                    "username": rw["user_var"].get(),
                    "password": rw["pass_var"].get(),
                    "nhom": rw["nhom_var"].get().strip(),
                    "ghi_chu": rw["ghichu_var"].get(),
                    "bat": bool(rw["bat_var"].get()),
                    "lan_chay_cuoi": rw.get("lan_chay_cuoi"),
                })
            account_manager.save_accounts(new_entries)
            self.accounts = new_entries
            self._log("info", f"Đã lưu {len(new_entries)} tài khoản vào accounts.json.")
            _rebuild_filter_buttons()
            messagebox.showinfo("Đã lưu", f"Đã lưu {len(new_entries)} tài khoản.", parent=win)

        btn_bar.add(RoundedButton(btn_bar, "💾 Lưu Tất Cả", command=_save_all,
                                   bg=COL_GREEN, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))

    # ================= ⚡ LOG NHANH (chọn 1 giả lập + 1 tài khoản, đăng nhập ngay) =================
    def _open_quick_login_dialog(self):
        """Popup '⚡ Log Nhanh' - chọn ĐÚNG 1 Giả lập + ĐÚNG 1 Tài khoản rồi
        đăng nhập NGAY LẬP TỨC (đăng xuất tài khoản cũ trước, nếu có Hoạt
        Động 'account_logout'), KHÔNG cần mở popup 'Xoay Vòng Tài Khoản'
        hay tick chọn Hoạt Động/chạy nguyên phiên - dùng khi chỉ cần đổi
        nhanh/kiểm tra 1 tài khoản trên 1 giả lập cụ thể."""
        if not getattr(self, "emulators", None):
            messagebox.showinfo("Chưa có giả lập",
                                 "Chưa quét được giả lập nào - bấm '🔄 Quét Giả Lập' rồi thử lại.")
            return
        accounts = account_manager.load_accounts()
        if not accounts:
            messagebox.showinfo("Chưa có Tài khoản",
                                 "Chưa có Tài khoản nào - vào '👥 Quản Lý Tài Khoản' để thêm trước.")
            return

        win = tk.Toplevel(self.root)
        win.title("⚡ Log Nhanh")
        win.configure(bg=COL_PANEL)
        win.geometry("440x210")
        win.resizable(False, False)
        _bind_esc_close(win)

        tk.Label(win, text="Chọn 1 Giả lập + 1 Tài khoản để đăng nhập NGAY (tự đăng xuất tài khoản cũ trước nếu "
                            "có Hoạt Động 'account_logout', cần có Hoạt Động 'account_login' để hoạt động):",
                 bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 9, "bold"),
                 wraplength=400, justify="left").pack(anchor="w", padx=14, pady=(14, 10))

        row1 = tk.Frame(win, bg=COL_PANEL)
        row1.pack(fill="x", padx=14, pady=4)
        tk.Label(row1, text="Giả lập:", bg=COL_PANEL, fg=COL_TEXT_MUTED, width=10, anchor="w",
                 font=("Segoe UI", 9)).pack(side="left")
        emu_labels = [f"#{e.index} - {e.name}" + ("" if e.running else " (đang tắt)") for e in self.emulators]
        emu_var = tk.StringVar(value=emu_labels[0] if emu_labels else "")
        ttk.Combobox(row1, textvariable=emu_var, values=emu_labels, width=32,
                     state="readonly").pack(side="left", padx=4)

        row2 = tk.Frame(win, bg=COL_PANEL)
        row2.pack(fill="x", padx=14, pady=4)
        tk.Label(row2, text="Tài khoản:", bg=COL_PANEL, fg=COL_TEXT_MUTED, width=10, anchor="w",
                 font=("Segoe UI", 9)).pack(side="left")
        acc_labels = [(a.get("ten_hien_thi") or a.get("username") or a.get("id")) +
                      (f"  [{a.get('nhom')}]" if a.get("nhom") else "") for a in accounts]
        acc_var = tk.StringVar(value=acc_labels[0] if acc_labels else "")
        ttk.Combobox(row2, textvariable=acc_var, values=acc_labels, width=32,
                     state="readonly").pack(side="left", padx=4)

        def _confirm():
            if not emu_var.get() or not acc_var.get():
                return
            emulator = self.emulators[emu_labels.index(emu_var.get())]
            account = accounts[acc_labels.index(acc_var.get())]
            win.destroy()
            self._start_quick_login(emulator, account)

        RoundedButton(win, "🔑 Đăng Nhập Ngay", command=_confirm, bg=COL_GREEN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9, "bold"), padx=16, pady=8).pack(pady=14)

    def _start_quick_login(self, emulator, account):
        """Kiểm tra giả lập có đang bận không rồi bắt đầu luồng nền Log
        Nhanh - KHÔNG xếp hàng chờ như phiên CHẠY chính (job Log Nhanh chỉ
        đăng nhập 1 tài khoản, không đáng để chờ lâu), chỉ báo bận và huỷ
        nếu giả lập đang có việc khác."""
        if emulator.index in self._busy_emulator_indexes:
            messagebox.showwarning("Giả lập đang bận",
                                    f"Giả lập '{emulator.name}' đang bận (có lịch hẹn giờ hoặc phiên chạy khác) "
                                    f"- thử lại sau khi giả lập rảnh.")
            return
        self._busy_emulator_indexes.add(emulator.index)
        ten = account.get("ten_hien_thi") or account.get("username") or account.get("id")
        self._log("info", f"⚡ Log Nhanh: bắt đầu đăng nhập '{ten}' trên '{emulator.name}'...",
                   emulator_name=emulator.name)
        threading.Thread(target=self._worker_quick_login, args=(emulator, account), daemon=True).start()

    def _worker_quick_login(self, emulator, account):
        """Luồng nền của '⚡ Log Nhanh' - tự bật giả lập nếu đang tắt, đăng
        xuất (nếu có 'account_logout') rồi đăng nhập ĐÚNG 1 tài khoản đã
        chọn, KHÔNG chạy thêm Hoạt Động nào khác và KHÔNG áp dụng 2 tuỳ
        chọn hậu kỳ (tắt giả lập / đăng nhập TK chỉ định) - Log Nhanh chỉ
        làm đúng 1 việc: đổi/kiểm tra nhanh tài khoản đang đăng nhập."""
        ready_info, _auto_started = self.emu_manager.ensure_running(
            emulator.index, timeout=120,
            on_log=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )
        if not ready_info:
            self.root.after(0, lambda: self._finish_quick_login(emulator.index))
            return
        emulator = ready_info  # dùng thông tin MỚI NHẤT (hwnd/serial có thể đổi sau khi vừa bật lại)

        if not self.emu_manager.ensure_adb_connected(emulator):
            self._log("error", f"Không thấy giả lập trong 'adb devices' (serial: {emulator.adb_serial}) sau khi "
                                f"khởi động - huỷ Log Nhanh trên giả lập này.", emulator_name=emulator.name)
            self.root.after(0, lambda: self._finish_quick_login(emulator.index))
            return

        adb = ADBHelper()
        adb.device_id = emulator.adb_serial
        adb.update_resolution()
        self._log("info", f"Độ phân giải nhận diện: {adb.screen_w}x{adb.screen_h}px", emulator_name=emulator.name)

        wf = WindowFinder(adb)
        attached = wf.attach_hwnd(emulator.hwnd) if emulator.hwnd else False
        if not attached:
            wf.find_ld_windows()
        if wf.ensure_window_visible():
            self._log("warn", f"Cửa sổ LDPlayer '{emulator.name}' đang bị THU NHỎ - đã tự khôi phục lại.",
                       emulator_name=emulator.name)
            time.sleep(0.5)

        engine = LogicEngine(
            adb,
            stop_checker=self._make_stop_checker(),
            popup_notifier=lambda msg, dur=0, _wf=wf: self._show_ingame_popup(_wf, msg, dur),
            logger=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )

        login_entry = task_registry.find_task(self.tasks, "account_login")
        logout_entry = task_registry.find_task(self.tasks, "account_logout")
        if not login_entry:
            self._log("error", "Chưa có Hoạt Động với id 'account_login' - hãy soạn kịch bản đăng nhập (dùng "
                                "{tk_user}/{tk_pass} ở bước Gõ Chữ) rồi Đăng Ký Tác Vụ với tên file "
                                "tasks/account_login.json. Đã huỷ Log Nhanh.", emulator_name=emulator.name)
            self.root.after(0, lambda: self._finish_quick_login(emulator.index))
            return

        ten = account.get("ten_hien_thi") or account.get("username") or account.get("id")

        if logout_entry:
            self._exec_entry(engine, emulator, logout_entry, preset_vars=None, tracked=False)
            if self.stop_flag:
                self.root.after(0, lambda: self._finish_quick_login(emulator.index))
                return

        preset_vars = {"tk_user": account.get("username", ""), "tk_pass": account.get("password", "")}
        ok = self._exec_entry(engine, emulator, login_entry, preset_vars=preset_vars, tracked=False)
        if ok:
            account_manager.mark_run(account_manager.load_accounts(), account.get("id"))
            self._log("success", f"⚡ Log Nhanh: đã đăng nhập '{ten}' trên '{emulator.name}'.",
                       emulator_name=emulator.name)
        else:
            self._log("error", f"⚡ Log Nhanh: đăng nhập '{ten}' trên '{emulator.name}' THẤT BẠI.",
                       emulator_name=emulator.name)

        self.root.after(0, lambda: self._finish_quick_login(emulator.index))

    def _finish_quick_login(self, emulator_index):
        """Dọn trạng thái bận sau khi luồng '_worker_quick_login' kết thúc
        (thành công/lỗi/bị huỷ đều gọi tới đây) - giải phóng giả lập và lấy
        tiếp job đang XẾP HÀNG CHỜ cho giả lập đó nếu có (xem
        _after_emulator_freed ở dashboard_schedule.py), để không làm kẹt
        hàng chờ của các tính năng khác (CHẠY tay/Xoay Vòng/Hẹn Giờ)."""
        self._busy_emulator_indexes.discard(emulator_index)
        self._after_emulator_freed(emulator_index)

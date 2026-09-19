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

import window_geometry as wg

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
            popup_notifier=lambda msg, dur=0, bg=None, fg=None, alpha=None, pos_box=None, _wf=wf: self._show_ingame_popup(_wf, msg, dur, bg, fg, alpha, pos_box),
            logger=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )

        # 2) Danh sách tài khoản đã CHỌN THỦ CÔNG cho giả lập này (qua popup
        # '👤 Chọn TK' ngay lúc bấm CHẠY - xem _start_run_with_accounts).
        # Không chọn tài khoản nào -> chạy tác vụ 1 lần bình thường (không
        # xoay vòng) thay vì bỏ trắng cả phiên chạy.
        # "Tự Login" (Hoạt Động id 'auto_login') dùng để KIỂM TRA đã vào
        # đúng màn hình game hay chưa. Với luồng CÓ XOAY VÒNG TÀI KHOẢN (bên
        # dưới), 'auto_login' chỉ chạy ĐÚNG 1 LẦN cho mỗi tài khoản, NGAY
        # TRƯỚC Đăng Xuất (không chạy lại trước mỗi tác vụ nữa) - lý do:
        # phải chắc đang ở TRONG GAME thì mới bấm được nút Đăng Xuất; nếu
        # giữa chừng bị văng ra khỏi game (crash, bị đá về màn hình chờ...)
        # thì 'auto_login' sẽ tự vào lại game trước khi đổi tài khoản. Nếu
        # 'auto_login' THẤT BẠI vẫn KHÔNG chặn gì - cứ Đăng Xuất/Đăng Nhập
        # tài khoản mới rồi chạy tiếp như bình thường (chỉ log cảnh báo).
        # Trường hợp KHÔNG xoay vòng tài khoản (fallback bên dưới, không
        # chọn Tài khoản nào) vẫn giữ hành vi CŨ: gọi 'auto_login' TRƯỚC
        # MỖI tác vụ, giống hệt luồng CHẠY TAY không xoay vòng (xem
        # _worker_run_emulator ở dashboard_run.py).
        auto_login_entry = None
        if getattr(self, "auto_login_var", None) and self.auto_login_var.get():
            auto_login_entry = task_registry.find_task(self.tasks, "auto_login")
            if not auto_login_entry:
                self._log("warn", "Đã bật 'Tự Login' nhưng chưa có Hoạt Động với id 'auto_login' (xem "
                                   "'📖 Hướng Dẫn').", emulator_name=emulator.name)

        def _run_selected_with_autologin(preset_vars_for_tasks, context_label=None):
            """CHỈ dùng cho trường hợp KHÔNG xoay vòng tài khoản (fallback
            bên dưới): chạy lần lượt các tác vụ đã tick, gọi 'auto_login'
            TRƯỚC MỖI tác vụ (nếu đang bật) - tác vụ nào mà lúc đó
            'auto_login' báo THẤT BẠI sẽ bị BỎ QUA RIÊNG tác vụ đó, không
            huỷ hẳn cả phiên, rồi vẫn thử tiếp tác vụ kế tiếp (giống hệt
            hành vi ở _worker_run_emulator của dashboard_run.py)."""
            for entry in selected:
                if self.stop_flag:
                    break
                if auto_login_entry is not None:
                    ok_login = self._exec_entry(engine, emulator, auto_login_entry, preset_vars=None,
                                                 tracked=False, context_label=context_label)
                    if self.stop_flag:
                        break
                    if not ok_login:
                        task_name = entry.get("ten_hien_thi", entry.get("id"))
                        self._log("error", f"Tự Login thất bại (chưa vào được game) trên '{emulator.name}' "
                                            f"trước khi chạy '{task_name}' - bỏ qua RIÊNG tác vụ này, thử tiếp "
                                            f"tác vụ kế tiếp.", emulator_name=emulator.name)
                        continue
                self._exec_entry(engine, emulator, entry, preset_vars=preset_vars_for_tasks, tracked=True,
                                  context_label=context_label)

        def _run_selected_plain(preset_vars_for_tasks, context_label=None):
            """Dùng cho trường hợp CÓ xoay vòng tài khoản: chạy lần lượt các
            tác vụ đã tick, KHÔNG kiểm tra lại 'auto_login' trước mỗi tác vụ
            nữa (đã kiểm tra ĐÚNG 1 LẦN ngay trước khi Đăng Xuất, xem vòng
            lặp xoay vòng bên dưới)."""
            for entry in selected:
                if self.stop_flag:
                    break
                self._exec_entry(engine, emulator, entry, preset_vars=preset_vars_for_tasks, tracked=True,
                                  context_label=context_label)

        accounts_by_id = {a.get("id"): a for a in self.accounts}
        accounts = [accounts_by_id[aid] for aid in account_ids
                    if aid in accounts_by_id and accounts_by_id[aid].get("bat", True)]
        if not accounts:
            self._log("warn", f"Giả lập '{emulator.name}' (#{emulator.index}) không chọn Tài khoản nào để xoay "
                               f"vòng - chạy các tác vụ đã chọn 1 lần, không xoay vòng.",
                       emulator_name=emulator.name)
            _run_selected_with_autologin(None)
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
        tong_so_tk = len(accounts)
        for idx, acc in enumerate(accounts, start=1):
            if self.stop_flag:
                break

            ten = acc.get("ten_hien_thi") or acc.get("username") or acc.get("id")
            # context_label: hiện NGAY trong Nhật Ký (tiền tố mỗi dòng tác
            # vụ bên dưới) để biết đang xoay vòng tới tài khoản thứ mấy -
            # tên gì, không cần đếm ngược lên dòng '═══ Tài khoản ═══' phía
            # trên để đoán.
            context_label = f"👥 Xoay Vòng - Tài khoản thứ {idx}/{tong_so_tk} - {ten}"
            self._log("info", f"═══ Tài khoản thứ {idx}/{tong_so_tk}: {ten} ═══", emulator_name=emulator.name)

            if auto_login_entry is not None:
                ok_pre = self._exec_entry(engine, emulator, auto_login_entry, preset_vars=None,
                                           tracked=False, context_label=context_label)
                if self.stop_flag:
                    break
                if not ok_pre:
                    self._log("warn", f"Tự Login thất bại (chưa vào được game) trước khi đổi sang tài khoản "
                                       f"'{ten}' - vẫn tiếp tục Đăng Xuất/Đăng Nhập như bình thường.",
                               emulator_name=emulator.name)

            if logout_entry:
                self._exec_entry(engine, emulator, logout_entry, preset_vars=None, tracked=False,
                                  context_label=context_label)
                if self.stop_flag:
                    break

            preset_vars = {"tk_user": acc.get("username", ""), "tk_pass": acc.get("password", "")}
            ok_login = self._exec_entry(engine, emulator, login_entry, preset_vars=preset_vars, tracked=False,
                                         context_label=context_label)
            if not ok_login:
                self._log("error", f"Đăng nhập thất bại cho tài khoản '{ten}' - bỏ qua tài khoản này, chuyển "
                                    f"tiếp tài khoản kế tiếp.", emulator_name=emulator.name)
                continue

            _run_selected_plain(preset_vars, context_label=context_label)

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
        wg.restore_geometry(win, "accounts_manager", default="960x560")
        win.minsize(720, 460)
        _bind_esc_close(win)
        wg.autosave(win, "accounts_manager")

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

        # ----- 1 nút DÙNG CHUNG để ẩn/hiện Mật khẩu cho TOÀN BỘ danh sách
        # cùng lúc (thay vì phải bấm riêng từng dòng) - chỉ đổi hiển thị
        # TẠM THỜI trên popup này, KHÔNG đổi dữ liệu đã lưu trong
        # accounts.json. pass_visible dùng dict để đổi được giá trị từ
        # trong hàm lồng nhau (_toggle_all_pass, _add_row). -----
        pass_visible = {"value": False}

        def _toggle_all_pass():
            pass_visible["value"] = not pass_visible["value"]
            show_char = "" if pass_visible["value"] else "•"
            for rw in row_widgets:
                rw["pass_entry"].configure(show=show_char)
            pass_toggle_btn.set_text("🙈 Ẩn Mật Khẩu" if pass_visible["value"] else "👁 Hiện Mật Khẩu")

        pass_toggle_btn = RoundedButton(filter_bar, "👁 Hiện Mật Khẩu", command=_toggle_all_pass,
                                         bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"),
                                         padx=8, pady=3)
        pass_toggle_btn.pack(side="right", padx=(10, 0))

        # ----- Độ rộng cột Username/Password DÙNG CHUNG cho header + TOÀN
        # BỘ các dòng (áp dụng đồng thời khi kéo giãn) - mặc định RỘNG HƠN
        # trước (18/16 ký tự thay vì 14) cho đỡ bị che chữ, và có thể KÉO
        # GIÃN/THU HẸP tay qua vạch kéo (⋮⋮) đặt cạnh mỗi tiêu đề cột. -----
        col_width = {"user": tk.IntVar(value=18), "pass": tk.IntVar(value=16)}
        header_col_labels = {}  # "user"/"pass" -> Label tiêu đề cột (đổi width theo col_width)

        def _apply_col_width(key):
            w = max(6, col_width[key].get())
            lbl = header_col_labels.get(key)
            if lbl is not None:
                lbl.configure(width=w)
            entry_key = f"{key}_entry"
            for rw in row_widgets:
                entry = rw.get(entry_key)
                if entry is not None:
                    entry.configure(width=w)

        col_width["user"].trace_add("write", lambda *_a: _apply_col_width("user"))
        col_width["pass"].trace_add("write", lambda *_a: _apply_col_width("pass"))

        def _make_resize_handle(parent, key):
            """Vạch kéo (⋮⋮) đặt giữa 2 cột - rê chuột ngang (giữ chuột
            trái) để tăng/giảm độ rộng cột `key` - áp dụng NGAY cho cả
            header lẫn toàn bộ ô nhập liệu cùng cột ở mọi dòng bên dưới
            (thông qua trace ở 'col_width' phía trên), không cần bấm Lưu."""
            handle = tk.Label(parent, text="⋮", bg=COL_HEADER, fg=COL_TEXT_MUTED, font=("Segoe UI", 8),
                               cursor="sb_h_double_arrow", width=1)
            handle.pack(side="left", fill="y")
            drag = {"x0": 0, "w0": 0}

            def _press(e):
                drag["x0"] = e.x_root
                drag["w0"] = col_width[key].get()

            def _motion(e):
                dx = e.x_root - drag["x0"]
                # ước lượng ~7px ngang / 1 ký tự độ rộng - đủ mượt tay kéo,
                # không cần đo pixel chính xác tuyệt đối theo font.
                new_w = max(6, drag["w0"] + round(dx / 7))
                if new_w != col_width[key].get():
                    col_width[key].set(new_w)

            handle.bind("<Button-1>", _press)
            handle.bind("<B1-Motion>", _motion)
            return handle

        header = tk.Frame(win, bg=COL_HEADER)
        header.pack(fill="x", padx=10)
        tk.Label(header, text="Bật", bg=COL_HEADER, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"),
                 width=4, anchor="w").pack(side="left", padx=2, pady=6)
        tk.Label(header, text="Tên hiển thị", bg=COL_HEADER, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"),
                 width=14, anchor="w").pack(side="left", padx=2, pady=6)

        header_col_labels["user"] = tk.Label(header, text="Username", bg=COL_HEADER, fg=COL_TEXT_MUTED,
                                              font=("Segoe UI", 8, "bold"), width=col_width["user"].get(), anchor="w")
        header_col_labels["user"].pack(side="left", padx=2, pady=6)
        _make_resize_handle(header, "user")

        header_col_labels["pass"] = tk.Label(header, text="Password", bg=COL_HEADER, fg=COL_TEXT_MUTED,
                                              font=("Segoe UI", 8, "bold"), width=col_width["pass"].get(), anchor="w")
        header_col_labels["pass"].pack(side="left", padx=2, pady=6)
        _make_resize_handle(header, "pass")

        for text, w in [("Nhóm", 10), ("Ghi chú", 12), ("Chạy cuối", 14)]:
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
            user_entry = tk.Entry(row, textvariable=user_var, width=col_width["user"].get(), bg=COL_PANEL,
                                   fg=COL_TEXT, insertbackground=COL_TEXT, relief="flat")
            user_entry.pack(side="left", padx=2)

            pass_var = tk.StringVar(value=acc.get("password", ""))
            pass_entry = tk.Entry(row, textvariable=pass_var, width=col_width["pass"].get(),
                                   show=("" if pass_visible["value"] else "•"),
                                   bg=COL_PANEL, fg=COL_TEXT, insertbackground=COL_TEXT, relief="flat")
            pass_entry.pack(side="left", padx=2)

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
                "id": rid, "bat_var": bat_var, "ten_var": ten_var, "user_var": user_var, "user_entry": user_entry,
                "pass_var": pass_var, "pass_entry": pass_entry, "nhom_var": nhom_var, "nhom_combo": nhom_combo,
                "ghichu_var": ghichu_var, "lan_chay_cuoi": acc.get("lan_chay_cuoi"), "row": row,
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

    # ================= ⚡ LOG NHANH (chọn NHIỀU giả lập, mỗi giả lập gán 1 tài khoản, đăng nhập đồng thời, lưu theo Nhóm) =================
    def _open_quick_login_dialog(self):
        """Popup '⚡ Log Nhanh' - tick chọn 1 hay NHIỀU Giả lập, mỗi giả lập
        được gán ĐÚNG 1 Tài khoản (qua combobox riêng trên từng dòng) rồi
        đăng nhập NGAY LẬP TỨC & ĐỒNG THỜI trên TẤT CẢ giả lập đã tick
        (đăng xuất tài khoản cũ trước, nếu có Hoạt Động 'account_logout'),
        KHÔNG cần mở popup 'Xoay Vòng Tài Khoản' hay tick chọn Hoạt
        Động/chạy nguyên phiên - dùng khi cần đổi nhanh/kiểm tra nhiều tài
        khoản trên nhiều giả lập cùng lúc. Mỗi cặp Giả lập/Tài khoản được
        khởi chạy qua '_start_quick_login' RIÊNG (1 luồng nền/giả lập) nên
        các giả lập đăng nhập SONG SONG, không chờ nhau.

        Có thêm 'Nhóm Log Nhanh' (xem account_manager.load/save/delete_
        quick_login_group) - 1 bộ gán SẴN Giả lập <-> Tài khoản đã đặt
        tên, LƯU LẠI để chọn 1 phát ra đúng bộ tick + Tài khoản đó (vd
        Nhóm 1 = dàn giả lập X đi kèm 4 tài khoản A, Nhóm 2 = CÙNG dàn
        giả lập X đó nhưng đi kèm 4 tài khoản B khác) thay vì phải chọn
        tay lại từ đầu mỗi lần đổi lượt tài khoản. Bấm '🔑 Đăng Nhập Ngay'
        KHÔNG tự đóng cửa sổ này nữa - để có thể tiếp tục theo dõi/đổi
        Nhóm khác và bấm đăng nhập tiếp cho đợt giả lập khác mà không cần
        mở lại popup từ đầu."""
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
        wg.restore_geometry(win, "accounts_quick_log", default="700x620")
        win.minsize(620, 420)
        wg.autosave(win, "accounts_quick_log")
        win.transient(self.root)
        win.grab_set()
        win.focus_set()
        _bind_esc_close(win)

        tk.Label(win, text="Tick chọn 1 hay NHIỀU Giả lập, chọn Tài khoản cho từng giả lập rồi bấm "
                            "'🔑 Đăng Nhập Ngay' để đăng nhập ĐỒNG THỜI trên tất cả cùng lúc (tự đăng xuất tài "
                            "khoản cũ trước nếu có Hoạt Động 'account_logout', cần có Hoạt Động 'account_login' "
                            "để hoạt động). Có thể LƯU bộ tick+Tài khoản hiện tại thành 1 'Nhóm' để chọn lại "
                            "nhanh sau này:",
                 bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 9, "bold"),
                 wraplength=670, justify="left").pack(anchor="w", padx=14, pady=(14, 8))

        acc_by_id = {a.get("id"): a for a in accounts}
        acc_labels = [(a.get("ten_hien_thi") or a.get("username") or a.get("id")) +
                      (f"  [{a.get('nhom')}]" if a.get("nhom") else "") for a in accounts]
        acc_label_by_id = {a.get("id"): lbl for a, lbl in zip(accounts, acc_labels)}

        quick_groups = account_manager.load_quick_login_groups()

        # ----- Hàng chọn/lưu/xoá 'Nhóm Log Nhanh' -----
        group_bar = tk.Frame(win, bg=COL_PANEL)
        group_bar.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(group_bar, text="Nhóm:", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9)).pack(side="left")
        group_var = tk.StringVar(value="")
        group_combo = ttk.Combobox(group_bar, textvariable=group_var, values=sorted(quick_groups.keys()),
                                    width=20)
        group_combo.pack(side="left", padx=(4, 8))

        # ----- Hàng nút Chọn Tất Cả/Bỏ Chọn/Đăng Nhập Ngay - PACK TRƯỚC
        # vùng cuộn (side="bottom") để LUÔN CHIẾM SẴN chỗ, không bị khuất
        # trên cửa sổ nhỏ (giống _open_gan_may_tk_dialog ở dashboard_schedule.py). -----
        btn_bar = FlowBar(win, bg=COL_PANEL)
        btn_bar.pack(side="bottom", fill="x", padx=14, pady=(0, 10))

        status_lbl = tk.Label(win, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "italic"),
                               wraplength=670, justify="left")
        status_lbl.pack(side="bottom", anchor="w", padx=14, pady=(0, 2))

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 8))

        row_state = {}  # emulator_index -> {"emulator": obj, "check_var": BooleanVar, "acc_var": StringVar}

        for e in self.emulators:
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=2, padx=2)

            check_var = tk.BooleanVar(value=False)
            DarkCheck(row, "", check_var, bg=COL_PANEL_ALT, box_size=14).pack(side="left", padx=(6, 2), pady=6)

            label = f"#{e.index} - {e.name}" + ("" if e.running else " (đang tắt)")
            tk.Label(row, text=label, bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 9),
                     anchor="w", width=24).pack(side="left", padx=4, pady=6)

            acc_var = tk.StringVar(value=acc_labels[0] if acc_labels else "")
            ttk.Combobox(row, textvariable=acc_var, values=acc_labels, width=28,
                         state="readonly").pack(side="left", padx=4, pady=6, fill="x", expand=True)

            row_state[e.index] = {"emulator": e, "check_var": check_var, "acc_var": acc_var}

        def _set_all(value):
            for st in row_state.values():
                st["check_var"].set(value)

        def _refresh_group_values(select=None):
            names = sorted(quick_groups.keys())
            group_combo.configure(values=names)
            group_var.set(select if select is not None else "")

        def _apply_group():
            name = group_var.get().strip()
            mapping = quick_groups.get(name)
            if not name or mapping is None:
                messagebox.showinfo("Chưa chọn Nhóm",
                                     "Hãy chọn (hoặc gõ đúng) tên 1 Nhóm Log Nhanh đã lưu ở ô 'Nhóm' rồi bấm lại.",
                                     parent=win)
                return
            missing = []
            applied = 0
            _set_all(False)
            for idx_str, acc_id in mapping.items():
                try:
                    idx = int(idx_str)
                except ValueError:
                    continue
                st = row_state.get(idx)
                acc_label = acc_label_by_id.get(acc_id)
                if not st or acc_id not in acc_by_id or acc_label is None:
                    missing.append(idx_str)
                    continue
                st["check_var"].set(True)
                st["acc_var"].set(acc_label)
                applied += 1
            msg = f"Đã áp dụng Nhóm '{name}': {applied} giả lập."
            if missing:
                msg += (f" ({len(missing)} dòng trong Nhóm này bị bỏ qua vì giả lập/tài khoản không còn tồn tại: "
                        f"{', '.join(missing)})")
            status_lbl.configure(text=msg)

        def _save_group():
            name = group_var.get().strip()
            if not name:
                messagebox.showinfo("Chưa đặt tên Nhóm",
                                     "Hãy gõ 1 tên cho Nhóm (vd 'Nhóm 1') vào ô 'Nhóm' rồi bấm lại để lưu.",
                                     parent=win)
                return
            mapping = {}
            for idx, st in row_state.items():
                if not st["check_var"].get() or not st["acc_var"].get():
                    continue
                account = accounts[acc_labels.index(st["acc_var"].get())]
                mapping[str(idx)] = account.get("id")
            if not mapping:
                messagebox.showinfo("Chưa tick giả lập nào",
                                     "Hãy tick ít nhất 1 giả lập + chọn Tài khoản cho giả lập đó trước khi lưu "
                                     "thành Nhóm.", parent=win)
                return
            overwrite = name in quick_groups
            quick_groups[name] = account_manager.save_quick_login_group(name, mapping)[name]
            _refresh_group_values(select=name)
            status_lbl.configure(text=f"Đã {'ghi đè' if overwrite else 'lưu'} Nhóm '{name}' ({len(mapping)} giả lập).")

        def _delete_group():
            name = group_var.get().strip()
            if not name or name not in quick_groups:
                messagebox.showinfo("Không tìm thấy Nhóm",
                                     "Hãy chọn đúng tên 1 Nhóm Log Nhanh đã lưu ở ô 'Nhóm' rồi bấm lại để xoá.",
                                     parent=win)
                return
            if not messagebox.askyesno("Xoá Nhóm", f"Xoá hẳn Nhóm '{name}' đã lưu?", parent=win):
                return
            account_manager.delete_quick_login_group(name)
            quick_groups.pop(name, None)
            _refresh_group_values()
            status_lbl.configure(text=f"Đã xoá Nhóm '{name}'.")

        group_bar_btns = FlowBar(group_bar, bg=COL_PANEL)
        group_bar_btns.pack(side="left", fill="x", expand=True)
        group_bar_btns.add(RoundedButton(group_bar_btns, "📂 Áp Dụng", command=_apply_group, bg=COL_PURPLE,
                                          container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=10, pady=5))
        group_bar_btns.add(RoundedButton(group_bar_btns, "💾 Lưu thành Nhóm", command=_save_group, bg=COL_GRAY_BTN,
                                          container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=10, pady=5))
        group_bar_btns.add(RoundedButton(group_bar_btns, "🗑️ Xoá Nhóm", command=_delete_group, bg=COL_GRAY_BTN,
                                          container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=10, pady=5))

        def _confirm():
            pairs = []
            for st in row_state.values():
                if not st["check_var"].get() or not st["acc_var"].get():
                    continue
                account = accounts[acc_labels.index(st["acc_var"].get())]
                pairs.append((st["emulator"], account))
            if not pairs:
                messagebox.showinfo("Chưa chọn giả lập",
                                     "Hãy tick ít nhất 1 giả lập và chọn Tài khoản cho giả lập đó.", parent=win)
                return
            # KHÔNG đóng cửa sổ (win.destroy()) nữa - để người dùng còn thấy
            # trạng thái, đổi Nhóm khác, hoặc bấm đăng nhập tiếp cho đợt
            # giả lập khác mà không phải mở lại popup từ đầu. Mỗi cặp Giả
            # lập/Tài khoản được khởi qua '_start_quick_login' RIÊNG - mỗi
            # lần gọi tự mở 1 luồng nền (xem _worker_quick_login) nên vòng
            # lặp này chỉ tuần tự ở bước "khởi", còn việc đăng nhập thực tế
            # trên từng giả lập chạy SONG SONG với nhau.
            for emulator, account in pairs:
                self._start_quick_login(emulator, account)
            ten_list = ", ".join(e.name for e, _a in pairs)
            status_lbl.configure(text=f"⏳ Đã bắt đầu đăng nhập song song trên {len(pairs)} giả lập: {ten_list} "
                                       f"- theo dõi tiến trình ở khung Nhật Ký.")

        btn_bar.add(RoundedButton(btn_bar, "☑️ Chọn Tất Cả", command=lambda: _set_all(True), bg=COL_GRAY_BTN,
                                   container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=10, pady=6))
        btn_bar.add(RoundedButton(btn_bar, "◻️ Bỏ Chọn", command=lambda: _set_all(False), bg=COL_GRAY_BTN,
                                   container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=10, pady=6))
        btn_bar.add(RoundedButton(btn_bar, "🔑 Đăng Nhập Ngay", command=_confirm, bg=COL_GREEN,
                                   container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"), padx=16, pady=8))

    # ================= 🔑 ĐĂNG NHẬP 1 ACC (chọn ĐÚNG 1 giả lập, chọn Tài khoản qua các NÚT + lọc nhanh theo Nhóm) =================
    def _open_single_login_dialog(self):
        """Popup '🔑 Đăng Nhập 1 Acc' - phiên bản ĐƠN GIẢN của '⚡ Log Nhanh'
        cho trường hợp chỉ cần đổi/đăng nhập 1 Tài khoản trên 1 Giả lập:
        chọn Giả lập ở 1 combobox (chỉ chọn được 1), có hàng nút 'Lọc nhanh
        theo Nhóm' (giống '👥 Quản Lý Tài Khoản') để rút gọn danh sách, rồi
        chọn Tài khoản bằng cách BẤM 1 NÚT trong danh sách các nút - MỖI
        NÚT LÀ TÊN 1 TÀI KHOẢN (không phải dropdown, cũng không phải bảng
        dạng hàng) - nút Tài khoản đang chọn được tô nổi bật màu khác. Bấm
        '🔑 Đăng Nhập' để đăng nhập NGAY trên Giả lập đã chọn - dùng lại
        đúng luồng nền '_start_quick_login'/'_worker_quick_login' sẵn có
        của '⚡ Log Nhanh' (đăng xuất tài khoản cũ trước nếu có Hoạt Động
        'account_logout', cần có Hoạt Động 'account_login' để hoạt động)."""
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
        win.title("🔑 Đăng Nhập 1 Acc")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "accounts_single_login", default="640x560")
        win.minsize(520, 420)
        wg.autosave(win, "accounts_single_login")
        win.transient(self.root)
        win.grab_set()
        win.focus_set()
        _bind_esc_close(win)

        tk.Label(win, text="Chọn 1 Giả lập, (tuỳ chọn) lọc nhanh theo Nhóm, rồi bấm chọn 1 nút Tài khoản bên "
                            "dưới (nút đang chọn được tô nổi bật), sau đó bấm '🔑 Đăng Nhập' để đăng nhập tài "
                            "khoản đó trên giả lập đã chọn (tự đăng xuất tài khoản cũ trước nếu có Hoạt Động "
                            "'account_logout', cần có Hoạt Động 'account_login' để hoạt động).",
                 bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 9, "bold"),
                 wraplength=610, justify="left").pack(anchor="w", padx=14, pady=(14, 8))

        # ----- Chọn 1 Giả lập -----
        emu_bar = tk.Frame(win, bg=COL_PANEL)
        emu_bar.pack(fill="x", padx=14, pady=(0, 8))
        tk.Label(emu_bar, text="Giả lập:", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9)).pack(side="left")
        emu_labels = [f"#{e.index} - {e.name}" + ("" if e.running else " (đang tắt)") for e in self.emulators]
        emu_by_label = {lbl: e for lbl, e in zip(emu_labels, self.emulators)}
        emu_var = tk.StringVar(value=emu_labels[0] if emu_labels else "")
        ttk.Combobox(emu_bar, textvariable=emu_var, values=emu_labels, state="readonly",
                     width=40).pack(side="left", padx=(6, 0), fill="x", expand=True)

        # ----- Lọc nhanh theo Nhóm (giống '👥 Quản Lý Tài Khoản') -----
        group_filter_bar = tk.Frame(win, bg=COL_PANEL)
        group_filter_bar.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(group_filter_bar, text="Lọc nhanh theo Nhóm:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8)).pack(side="left", padx=(0, 6))
        group_filter_btns = FlowBar(group_filter_bar, bg=COL_PANEL)
        group_filter_btns.pack(side="left", fill="x", expand=True)

        # ----- Ô lọc nhanh theo chữ (tên/username/Nhóm/Ghi chú) -----
        filter_bar = tk.Frame(win, bg=COL_PANEL)
        filter_bar.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(filter_bar, text="Lọc:", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9)).pack(side="left")
        filter_var = tk.StringVar()
        tk.Entry(filter_bar, textvariable=filter_var, bg=COL_PANEL_ALT, fg=COL_TEXT,
                  insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=(6, 0), fill="x",
                                                                  expand=True, ipady=3)

        # ----- Hàng nút Đăng Nhập (PACK TRƯỚC vùng cuộn, side="bottom", để
        # luôn chiếm sẵn chỗ, không bị khuất trên cửa sổ nhỏ) -----
        btn_bar = FlowBar(win, bg=COL_PANEL)
        btn_bar.pack(side="bottom", fill="x", padx=14, pady=(0, 10))

        status_lbl = tk.Label(win, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "italic"),
                               wraplength=610, justify="left")
        status_lbl.pack(side="bottom", anchor="w", padx=14, pady=(0, 2))

        # ----- Vùng cuộn chứa các NÚT Tài khoản (mỗi nút = tên 1 Tài
        # khoản) - CHỌN BẰNG CÁCH BẤM 1 NÚT, không phải dropdown/bảng -----
        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        acc_flow = FlowBar(canvas, bg=COL_PANEL)
        canvas_window_id = canvas.create_window((0, 0), window=acc_flow, anchor="nw")

        # QUAN TRỌNG: acc_flow (FlowBar) tự xếp nút bằng place() nên KHÔNG
        # tự nới rộng theo nút con - nếu để canvas tự đo kích thước mặc
        # định (rất nhỏ, ~1px) thì các nút coi như bị "giam" trong vùng
        # 1px đó và KHÔNG hiển thị ra ngoài (dù vẫn được tạo ra bình
        # thường). Phải CHỦ ĐỘNG ép chiều rộng của acc_flow bằng đúng
        # chiều rộng hiển thị của canvas mỗi khi canvas đổi kích thước,
        # để FlowBar có đủ chiều rộng thật mà tính toán chỗ đặt nút.
        def _on_canvas_configure(event):
            canvas.itemconfigure(canvas_window_id, width=event.width)

        canvas.bind("<Configure>", _on_canvas_configure)
        # FlowBar (acc_flow) đã TỰ bind sẵn '<Configure>' để tự xếp lại nút
        # (_reflow) - dùng add='+' để CHỈ THÊM việc cập nhật scrollregion,
        # không ghi đè mất callback tự xếp nút có sẵn của FlowBar.
        acc_flow.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")), add="+")
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 8))

        acc_by_id = {a.get("id"): a for a in accounts}
        acc_buttons = {}  # id -> RoundedButton
        selected = {"id": None, "group": None}

        def _account_label(a):
            lbl = a.get("ten_hien_thi") or a.get("username") or a.get("id")
            if a.get("nhom"):
                lbl += f"  [{a.get('nhom')}]"
            return lbl

        def _select_account(acc_id):
            prev = selected["id"]
            if prev is not None and prev in acc_buttons:
                acc_buttons[prev].bg_color = COL_GRAY_BTN
                acc_buttons[prev]._redraw()
            selected["id"] = acc_id
            btn = acc_buttons.get(acc_id)
            if btn is not None:
                btn.bg_color = COL_BLUE
                btn._redraw()
            acc = acc_by_id.get(acc_id)
            ten = (acc.get("ten_hien_thi") or acc.get("username") or acc.get("id")) if acc else ""
            status_lbl.configure(text=f"Đã chọn Tài khoản: {ten}")

        def _populate(group=None, text_filter=""):
            acc_flow.clear()
            acc_buttons.clear()
            needle = (text_filter or "").strip().lower()
            for a in accounts:
                if group and (a.get("nhom") or "").strip() != group:
                    continue
                if needle:
                    haystack = " ".join([a.get("ten_hien_thi") or "", a.get("username") or "",
                                          a.get("nhom") or "", a.get("ghi_chu") or ""]).lower()
                    if needle not in haystack:
                        continue
                aid = a.get("id")
                is_sel = (aid == selected["id"])
                btn = RoundedButton(acc_flow, _account_label(a), command=lambda aid=aid: _select_account(aid),
                                     bg=COL_BLUE if is_sel else COL_GRAY_BTN, container_bg=COL_PANEL,
                                     font=("Segoe UI", 9, "bold"), padx=10, pady=6)
                acc_flow.add(btn)
                acc_buttons[aid] = btn

        def _apply_group_filter(g):
            selected["group"] = g
            _populate(group=g, text_filter=filter_var.get())

        groups_now = sorted({(a.get("nhom") or "").strip() for a in accounts if (a.get("nhom") or "").strip()})
        group_filter_btns.add(RoundedButton(group_filter_btns, "Tất cả", command=lambda: _apply_group_filter(None),
                                             bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"),
                                             padx=8, pady=3))
        for g in groups_now:
            group_filter_btns.add(RoundedButton(group_filter_btns, g, command=lambda g=g: _apply_group_filter(g),
                                                 bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"),
                                                 padx=8, pady=3))

        _populate()
        filter_var.trace_add("write", lambda *_a: _populate(group=selected["group"], text_filter=filter_var.get()))

        def _do_login():
            emulator = emu_by_label.get(emu_var.get())
            if emulator is None:
                messagebox.showinfo("Chưa chọn Giả lập", "Hãy chọn 1 Giả lập ở ô 'Giả lập' trước.", parent=win)
                return
            account = acc_by_id.get(selected["id"])
            if account is None:
                messagebox.showinfo("Chưa chọn Tài khoản",
                                     "Hãy bấm chọn 1 nút Tài khoản trong danh sách bên dưới trước.", parent=win)
                return
            self._start_quick_login(emulator, account)
            ten = account.get("ten_hien_thi") or account.get("username") or account.get("id")
            status_lbl.configure(text=f"⏳ Đã bắt đầu đăng nhập '{ten}' trên '{emulator.name}' - theo dõi "
                                       f"tiến trình ở khung Nhật Ký.")

        btn_bar.add(RoundedButton(btn_bar, "🔑 Đăng Nhập", command=_do_login, bg=COL_GREEN,
                                   container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"), padx=16, pady=8))

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
        # Trước đây Log Nhanh không set self.is_running/không gọi
        # _refresh_run_control_buttons() nên nút '⏹ Dừng' vẫn bị khoá
        # (disabled) suốt quá trình đăng nhập, dù stop_flag vẫn hoạt động
        # bên trong - người dùng bấm Dừng không có phản ứng gì vì nút
        # đang bị khoá. Dùng riêng 1 bộ đếm (không đụng self.is_running,
        # vốn dành cho phiên CHẠY chính) để _any_active_work() biết có
        # việc đang chạy và bật nút Dừng/Tạm Dừng lên đúng lúc.
        self._active_quicklogin_count = getattr(self, "_active_quicklogin_count", 0) + 1
        self._refresh_run_control_buttons()
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
            popup_notifier=lambda msg, dur=0, bg=None, fg=None, alpha=None, pos_box=None, _wf=wf: self._show_ingame_popup(_wf, msg, dur, bg, fg, alpha, pos_box),
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
        self._active_quicklogin_count = max(0, getattr(self, "_active_quicklogin_count", 0) - 1)
        self._refresh_run_control_buttons()
        self._clear_current_task_for_index(emulator_index)
        self._after_emulator_freed(emulator_index)

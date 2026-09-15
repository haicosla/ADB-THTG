"""
dashboard_run.py — Chạy các Hoạt Động đã tick trên (các) giả lập đã chọn, đa luồng theo giả lập: xếp hàng chờ khi giả lập bận, tạm dừng/dừng, gate theo kết quả 'Tự Login', thực thi 1 Hoạt Động (_exec_entry, dùng chung cho cả 3 kiểu chạy: tay/xoay vòng/lịch hẹn giờ), và 2 tuỳ chọn hậu kỳ (tắt giả lập / đăng nhập tài khoản chỉ định sau khi chạy xong).

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import os
import json
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from adb_helper import ADBHelper
from logic_engine import LogicEngine, BreakGroupSignal, ContinueGroupSignal
from window_finder import WindowFinder
import task_registry
import run_state
import account_manager
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, _bind_esc_close


class RunMixin:
    # ================= CHẠY TÁC VỤ (ĐA LUỒNG THEO GIẢ LẬP) =================
    def run_selected_tasks(self):
        if self.is_running:
            return

        selected = [
            t for t in self.tasks
            if self.task_vars.get(t.get("id") or task_registry.make_task_id(t.get("file_json", "")), tk.BooleanVar(value=False)).get()
        ]
        if not selected:
            messagebox.showwarning("Lưu ý", "Chưa chọn tác vụ nào để chạy!")
            return

        selected_emulators = self._get_selected_emulators()
        if not selected_emulators:
            messagebox.showwarning(
                "Lưu ý",
                "Chưa chọn giả lập nào để chạy!\nBấm '🔄 Quét Giả Lập' rồi tick chọn ít nhất 1 giả lập."
            )
            return

        selected = sorted(selected, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0)))

        if self.account_rotate_var.get():
            self._start_run_with_accounts(selected, selected_emulators)
            return

        login_entry = None
        if self.auto_login_var.get():
            login_entry = task_registry.find_task(self.tasks, "auto_login")
            if not login_entry:
                self._log("warn", "Đã bật 'Tự Login' nhưng chưa có Hoạt Động với id 'auto_login' (xem '📖 Hướng Dẫn').")

        self._start_run(selected, selected_emulators, login_entry)

    def _split_busy_emulators(self, selected_emulators):
        """Tách danh sách giả lập đã chọn thành (available, busy) dựa theo
        self._busy_emulator_indexes - dùng ở các nơi cần XẾP HÀNG CHỜ cho
        phần busy thay vì bỏ qua hẳn (xem _queue_job)."""
        available = [e for e in selected_emulators if e.index not in self._busy_emulator_indexes]
        busy = [e for e in selected_emulators if e.index in self._busy_emulator_indexes]
        return available, busy

    def _queue_job(self, emulator, job, context_label=""):
        """XẾP 1 job (dict có khoá 'kind', xem self._emulator_job_queue ở
        __init__) vào hàng chờ của đúng giả lập đang bận - job này sẽ tự
        được lấy ra chạy tiếp ngay khi giả lập đó rảnh (_after_emulator_freed),
        KHÔNG cần người dùng làm gì thêm và KHÔNG bị bỏ qua/bỏ dở như trước
        đây (trước đây các giả lập bận bị loại thẳng khỏi lượt CHẠY hiện tại,
        khiến người dùng phải tự bấm CHẠY lại thủ công sau khi giả lập rảnh)."""
        self._emulator_job_queue.setdefault(emulator.index, []).append(job)
        queue_len = len(self._emulator_job_queue[emulator.index])
        self._log("warn", f"Giả lập '{emulator.name}' đang bận (có lịch hẹn giờ hoặc phiên khác đang chạy) - "
                           f"lượt {context_label} vừa yêu cầu đã XẾP HÀNG CHỜ (vị trí {queue_len} trên giả lập "
                           f"này), sẽ tự chạy tiếp ngay khi giả lập rảnh, KHÔNG bị bỏ qua.",
                   emulator_name=emulator.name)

    def _start_run(self, selected, selected_emulators, login_entry):
        available, busy = self._split_busy_emulators(selected_emulators)
        for e in busy:
            self._queue_job(e, {"kind": "manual_run", "selected": selected, "login_entry": login_entry},
                             "chạy tác vụ")
        selected_emulators = available
        if not selected_emulators:
            if not busy:
                messagebox.showwarning("Lưu ý", "Tất cả giả lập đã chọn đang bận (có lịch hẹn giờ hoặc phiên khác "
                                                 "đang chạy).\nThử lại sau.")
            # busy != [] -> đã xếp hàng chờ hết, không cần cảnh báo lỗi, chỉ
            # cần các dòng log ở _queue_job là đủ rõ.
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
        self._log("info", f"══════ Bắt đầu phiên chạy: {len(selected)} tác vụ trên [{names}] ══════")

        for emulator in selected_emulators:
            self._busy_emulator_indexes.add(emulator.index)
            threading.Thread(target=self._worker_run_emulator, args=(emulator, selected, login_entry), daemon=True).start()

    def stop_run(self):
        self.stop_flag = True
        self.pause_flag = False
        self.btn_pause.set_text("⏸ Tạm Dừng")
        self._log("warn", "Người dùng bấm DỪNG - đang chờ các luồng/lịch hiện tại kết thúc...")

    def _any_active_work(self):
        """True nếu có BẤT KỲ việc gì đang chạy - phiên CHẠY thủ công (tick
        chọn tác vụ) HOẶC 1 lịch hẹn giờ đang thực thi. Dùng để bật/tắt nút
        DỪNG + Tạm Dừng đúng lúc kể cả khi việc đang chạy là do lịch tự kích
        hoạt (người dùng không hề bấm nút CHẠY)."""
        return self.is_running or self._active_schedule_count > 0

    def _refresh_run_control_buttons(self):
        active = self._any_active_work()
        self.btn_stop.set_state("normal" if active else "disabled")
        self.btn_pause.set_state("normal" if active else "disabled")
        if not active:
            # Không còn gì chạy -> RESET stop_flag để LẦN TRIGGER TIẾP THEO
            # của 1 lịch hẹn giờ (không đi qua _start_run - nơi duy nhất
            # trước đây reset cờ này) không bị coi là "đã bị dừng" ngay từ
            # đầu và im lặng không chạy gì cả.
            self.stop_flag = False
            self.pause_flag = False
            self.btn_pause.set_text("⏸ Tạm Dừng")

    def toggle_pause(self):
        """Bật/tắt tạm dừng phiên chạy hiện tại (thủ công hoặc lịch hẹn
        giờ). Không dừng hẳn luồng - chỉ chặn LogicEngine lại NGAY TRƯỚC
        lần kiểm tra dừng kế tiếp (xem _make_stop_checker), nên độ trễ tạm
        dừng chỉ trong vòng 1 bước/1 vòng lặp chờ ảnh, không phải chờ hết
        cả tác vụ."""
        if not self._any_active_work():
            return
        self.pause_flag = not self.pause_flag
        if self.pause_flag:
            self.btn_pause.set_text("▶ Tiếp Tục")
            self._log("warn", "Người dùng bấm TẠM DỪNG - các giả lập sẽ dừng lại giữa bước hiện tại, "
                               "bấm '▶ Tiếp Tục' để chạy tiếp.")
        else:
            self.btn_pause.set_text("⏸ Tạm Dừng")
            self._log("info", "Đã bấm TIẾP TỤC - các giả lập chạy lại bình thường.")

    def _make_stop_checker(self):
        """Trả về hàm stop_checker() cho LogicEngine của 1 luồng giả lập.
        LogicEngine gọi hàm này liên tục ở MỌI điểm dừng an toàn (giữa mỗi
        bước, trong vòng lặp chờ ảnh...) để biết có nên dừng hẳn không - tận
        dụng luôn các điểm gọi đó làm điểm TẠM DỪNG: khi self.pause_flag
        đang bật, hàm sẽ 'đứng chờ' tại đây (vẫn kiểm tra stop_flag để nút
        DỪNG luôn hoạt động ngay cả khi đang tạm dừng) thay vì trả về ngay,
        nên KHÔNG cần sửa gì trong logic_engine.py."""
        def checker():
            while self.pause_flag and not self.stop_flag:
                time.sleep(0.15)
            return self.stop_flag
        return checker

    def _worker_run_emulator(self, emulator, selected, login_entry):
        if not self.emu_manager.ensure_adb_connected(emulator):
            self._log("error", f"Không thấy giả lập trong 'adb devices' (serial: {emulator.adb_serial}). "
                                f"Bỏ qua giả lập này - hãy bấm 'Quét Giả Lập' hoặc 'Kết nối lại ADB' rồi thử lại.",
                       emulator_name=emulator.name)
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
            self._log("warn", f"Cửa sổ LDPlayer '{emulator.name}' đang bị THU NHỎ - đã tự khôi phục lại "
                               f"(cửa sổ thu nhỏ thường khiến ADB gửi được lệnh nhưng KHÔNG có tác dụng chạm/vuốt).",
                       emulator_name=emulator.name)
            time.sleep(0.5)

        engine = LogicEngine(
            adb,
            stop_checker=self._make_stop_checker(),
            popup_notifier=lambda msg, dur=0, _wf=wf: self._show_ingame_popup(_wf, msg, dur),
            logger=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )

        # "Tự Login" (login_entry, Hoạt Động id 'auto_login') là 1 HÀNH
        # ĐỘNG RIÊNG, KHÔNG phải kịch bản đăng nhập tài khoản
        # ('account_login' - dùng cho Xoay Vòng Tài Khoản) - mục đích CHỈ
        # là đưa giả lập VÀO ĐÚNG MÀN HÌNH GAME (tự soạn kịch bản này với
        # các bước wait_image/if_image để tự kiểm tra đã vào game hay
        # chưa). Kịch bản chính (các tác vụ đã tick) CHỈ được chạy SAU KHI
        # 'auto_login' báo THÀNH CÔNG - nếu thất bại (không vào được game),
        # bỏ qua hẳn các tác vụ đã tick trên giả lập này để tránh chạy
        # kịch bản khi màn hình chưa đúng trạng thái mong đợi.
        if login_entry is not None:
            ok_login = self._exec_entry(engine, emulator, login_entry, preset_vars=None, tracked=False)
            if self.stop_flag:
                self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
                return
            if not ok_login:
                self._log("error", f"Tự Login thất bại (chưa vào được game) trên '{emulator.name}' - bỏ qua "
                                    f"{len(selected)} tác vụ đã chọn cho giả lập này để tránh chạy kịch bản khi "
                                    f"chưa đúng màn hình.", emulator_name=emulator.name)
                self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
                return

        for entry in selected:
            if self.stop_flag:
                break
            self._exec_entry(engine, emulator, entry, preset_vars=None, tracked=True)

        self._apply_post_run_options(engine, emulator)
        self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))

    def _apply_post_run_options(self, engine, emulator):
        """Áp dụng 2 tuỳ chọn HẬU KỲ (độc lập với phiên chạy chính, xem 2
        checkbox 'Tắt Giả Lập Sau Khi Chạy Xong' / 'Đăng Nhập TK Chỉ Định
        Sau Khi Chạy Xong' ở thanh trên) - gọi SAU KHI 1 giả lập vừa chạy
        xong hết các tác vụ của lượt hiện tại (CHẠY tay/Chạy Ngay/Xoay
        Vòng Tài Khoản/lịch hẹn giờ đều dùng chung). KHÔNG áp dụng nếu
        người dùng đã bấm DỪNG giữa chừng (self.stop_flag) - tắt giả lập
        hoặc đăng nhập lại ngay sau khi vừa bị dừng dở dang dễ gây hiểu
        nhầm/ghi đè trạng thái người dùng đang muốn giữ nguyên để kiểm tra.

        CẢ 2 tuỳ chọn đều có 2 lớp: 1 công tắc TỔNG (checkbox ở thanh trên -
        bật/tắt cả tính năng) + 1 lựa chọn RIÊNG cho từng giả lập (nút
        '⚙'/'🎯' cạnh checkbox - giả lập nào áp dụng, giả lập nào bỏ qua /
        TK nào). Nếu CẢ 2 tuỳ chọn cùng áp dụng cho đúng giả lập này: ưu
        tiên TẮT GIẢ LẬP (đăng nhập xong rồi tắt ngay sau đó là vô nghĩa) -
        chỉ cảnh báo, không coi là lỗi."""
        if self.stop_flag:
            return

        want_shutdown = bool(getattr(self, "shutdown_after_var", None) and self.shutdown_after_var.get()
                              and self._shutdown_after_enabled_for_emulator(emulator))
        want_post_login = bool(getattr(self, "post_login_after_var", None) and self.post_login_after_var.get())

        if want_shutdown:
            if want_post_login and self._get_post_run_account(emulator):
                self._log("warn", f"Đã bật cả 'Tắt Giả Lập' và 'Đăng Nhập TK Chỉ Định' sau khi chạy xong trên "
                                   f"'{emulator.name}' - ưu tiên TẮT GIẢ LẬP, bỏ qua đăng nhập.",
                           emulator_name=emulator.name)
            try:
                self._log("info", f"Đang tắt giả lập '{emulator.name}' theo tuỳ chọn 'Tắt Giả Lập Sau Khi Chạy "
                                   f"Xong'...", emulator_name=emulator.name)
                self.emu_manager.quit_emulator(emulator.index)
                self._log("success", f"Đã tắt giả lập '{emulator.name}'.", emulator_name=emulator.name)
            except Exception as e:
                self._log("error", f"Không tắt được giả lập '{emulator.name}': {e}", emulator_name=emulator.name)
            return

        if want_post_login:
            acc = self._get_post_run_account(emulator)
            if not acc:
                self._log("warn", f"Đã bật 'Đăng Nhập TK Chỉ Định Sau Khi Chạy Xong' nhưng chưa chọn Tài khoản "
                                   f"hợp lệ cho giả lập này (bấm '🎯 Chọn TK Theo Giả Lập' để chọn riêng cho "
                                   f"'{emulator.name}', hoặc tài khoản đã chọn đang TẮT/bị xoá) - bỏ qua trên "
                                   f"'{emulator.name}'.", emulator_name=emulator.name)
                return
            login_entry = task_registry.find_task(self.tasks, "account_login")
            if not login_entry:
                self._log("warn", f"Chưa có Hoạt Động 'account_login' - không thể tự đăng nhập tài khoản chỉ "
                                   f"định sau khi chạy xong trên '{emulator.name}'.", emulator_name=emulator.name)
                return
            ten = acc.get("ten_hien_thi") or acc.get("username") or acc.get("id")
            self._log("info", f"Đang đăng nhập tài khoản chỉ định '{ten}' trên '{emulator.name}' theo tuỳ chọn "
                               f"sau khi chạy xong...", emulator_name=emulator.name)
            preset_vars = {"tk_user": acc.get("username", ""), "tk_pass": acc.get("password", "")}
            self._exec_entry(engine, emulator, login_entry, preset_vars=preset_vars, tracked=False)

    def _shutdown_after_enabled_for_emulator(self, emulator):
        """True nếu giả lập này được ÁP DỤNG tuỳ chọn 'Tắt Giả Lập Sau Khi
        Chạy Xong' (chỉ có ý nghĩa khi công tắc TỔNG shutdown_after_var
        đang bật - xem _apply_post_run_options).

        self._shutdown_after_by_emulator là dict khoá str(emulator.index)
        -> True/False, chỉnh qua popup '⚙ Chọn Giả Lập' cạnh checkbox.
        Giả lập CHƯA từng được cấu hình riêng (chưa mở popup, hoặc là giả
        lập mới quét thêm sau) mặc định TRUE - giữ đúng hành vi bản cũ
        (checkbox tổng áp dụng cho MỌI giả lập) cho tới khi người dùng chủ
        động bỏ tick giả lập nào đó."""
        mapping = getattr(self, "_shutdown_after_by_emulator", None) or {}
        return bool(mapping.get(str(emulator.index), True))

    def _shutdown_after_label_text(self):
        """Chuỗi hiển thị cạnh nút '⚙ Chọn Giả Lập' của tuỳ chọn 'Tắt Giả
        Lập Sau Khi Chạy Xong' - tóm tắt có bao nhiêu giả lập đang bị LOẠI
        TRỪ khỏi tuỳ chọn này (không tính giả lập nào = áp dụng cho tất cả,
        giống hành vi bản cũ)."""
        mapping = getattr(self, "_shutdown_after_by_emulator", None) or {}
        excluded = sum(1 for v in mapping.values() if not v)
        return f"(bỏ qua {excluded} giả lập)" if excluded else "(áp dụng cho tất cả giả lập)"

    def _pick_shutdown_emulators(self):
        """Popup liệt kê TỪNG giả lập đang có, cho phép bỏ tick giả lập
        nào KHÔNG muốn tự tắt sau khi chạy xong - dùng cho tuỳ chọn '🔌
        Tắt Giả Lập Sau Khi Chạy Xong' (công tắc tổng vẫn phải bật thì
        lựa chọn ở đây mới có tác dụng)."""
        if not getattr(self, "emulators", None):
            messagebox.showinfo("Chưa có giả lập",
                                 "Chưa quét được giả lập nào - bấm '🔄 Quét Giả Lập' rồi thử lại.")
            return

        mapping = getattr(self, "_shutdown_after_by_emulator", None)
        if mapping is None:
            mapping = {}
            self._shutdown_after_by_emulator = mapping

        win = tk.Toplevel(self.root)
        win.title("Chọn Giả Lập Áp Dụng 'Tắt Sau Khi Chạy Xong'")
        win.configure(bg=COL_PANEL)
        win.geometry("380x460")
        _bind_esc_close(win)

        tk.Label(win, text="Bỏ tick giả lập nào KHÔNG muốn tự tắt sau khi chạy xong. Mặc định TẤT CẢ giả lập "
                            "đều áp dụng khi công tắc '🔌 Tắt Giả Lập Sau Khi Chạy Xong' ở trên đang BẬT:",
                 bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 9, "bold"),
                 wraplength=340, justify="left").pack(anchor="w", padx=12, pady=(12, 6))

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=6)
        vbar.pack(side="right", fill="y", padx=(0, 6))

        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        check_vars = {}
        for e in self.emulators:
            var = tk.BooleanVar(value=bool(mapping.get(str(e.index), True)))
            check_vars[e.index] = var
            label = f"🟢 {e.name}" if e.running else f"⚪ {e.name} (đang tắt)"
            DarkCheck(inner, label, var, bg=COL_PANEL_ALT).pack(anchor="w", padx=8, pady=4, fill="x")

        def _save():
            for idx, var in check_vars.items():
                mapping[str(idx)] = bool(var.get())
            self._save_settings()
            if hasattr(self, "lbl_shutdown_after"):
                self.lbl_shutdown_after.config(text=self._shutdown_after_label_text())
            win.destroy()

        RoundedButton(win, "💾 Lưu", command=_save, bg=COL_GREEN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9, "bold"), padx=16, pady=6).pack(side="bottom", pady=10)

    def _get_post_run_account(self, emulator):
        """Trả về dict Tài khoản đã chọn RIÊNG cho `emulator` này, dùng cho
        tuỳ chọn 'Đăng Nhập TK Chỉ Định Sau Khi Chạy Xong' (None nếu giả
        lập này chưa được gán TK / TK đã chọn đã bị xoá / đang TẮT).

        Mỗi giả lập có 1 TK riêng (self._post_login_account_by_emulator,
        khoá là str(emulator.index)) - cho phép ví dụ giả lập A tự đăng
        nhập TK 'shop1' còn giả lập B tự đăng nhập TK 'shop2' sau khi mỗi
        giả lập chạy xong, thay vì dùng chung đúng 1 TK cho mọi giả lập.

        Tương thích ngược: nếu giả lập chưa có TK riêng, thử dùng
        'post_login_account_id' (cấu hình bản CŨ trước khi hỗ trợ chọn
        theo giả lập - lúc đó chỉ có đúng 1 TK dùng chung)."""
        mapping = getattr(self, "_post_login_account_by_emulator", None) or {}
        aid = mapping.get(str(emulator.index)) or self._settings.get("post_login_account_id")
        if not aid:
            return None
        for a in account_manager.load_accounts():
            if a.get("id") == aid and a.get("bat", True):
                return a
        return None

    def _exec_entry(self, engine, emulator, entry, preset_vars, tracked):
        task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
        name = entry.get("ten_hien_thi", task_id)
        file_path = entry.get("file_json")

        # THÊM ĐOẠN NÀY VÀO ĐẦU HÀM _exec_entry:
        if not file_path or not os.path.exists(file_path):
            if file_path:
                base_name = os.path.basename(file_path)
                local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks", base_name)
                if os.path.exists(local_path):
                    file_path = local_path

        if tracked:
            self._bump_task_progress(task_id, "running")
        self._log("info", f"── Bắt đầu tác vụ: {name} ──", emulator_name=emulator.name)

        if not file_path or not os.path.exists(file_path):
            self._log("error", f"Không tìm thấy file kịch bản: {file_path}", emulator_name=emulator.name)
            if tracked:
                self._bump_task_progress(task_id, "error")
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                steps = json.load(f)
            engine.reset_variables()
            if preset_vars:
                engine.variables.update(preset_vars)
            engine.execute_steps(steps, is_root=True)

            if self.stop_flag:
                if tracked:
                    self._bump_task_progress(task_id, "stopped")
                self._log("warn", f"Tác vụ '{name}' bị dừng giữa chừng.", emulator_name=emulator.name)
                return False

            if tracked:
                self._bump_task_progress(task_id, "done")
                run_state.mark_done(task_id, emulator.name)
            self._log("success", f"Hoàn thành tác vụ: {name}", emulator_name=emulator.name)
            return True

        except (BreakGroupSignal, ContinueGroupSignal):
            if tracked:
                self._bump_task_progress(task_id, "done")
                run_state.mark_done(task_id, emulator.name)
            self._log("warn", f"Tác vụ '{name}' kết thúc sớm do break/continue nằm ngoài GROUP.", emulator_name=emulator.name)
            return True
        except Exception as e:
            if tracked:
                self._bump_task_progress(task_id, "error")
            self._log("error", f"Lỗi khi chạy '{name}': {e}", emulator_name=emulator.name)
            return False

    def _on_emulator_thread_done(self, emulator_index=None):
        if emulator_index is not None:
            self._busy_emulator_indexes.discard(emulator_index)
            self._after_emulator_freed(emulator_index)
        self.active_threads = max(0, self.active_threads - 1)
        if self.active_threads == 0:
            self._on_finish_all()
        else:
            self._update_status_label()

    def _update_status_label(self):
        parts = []
        if self.active_threads > 1:
            parts.append(f"Đang chạy đa luồng ({self.active_threads} luồng)")
        elif self.active_threads == 1:
            parts.append("Đang chạy...")
        if self._active_schedule_count:
            parts.append(f"⏰ {self._active_schedule_count} lịch hẹn giờ đang chạy nền")
        self.lbl_status.config(text="Trạng thái: " + (" | ".join(parts) if parts else "Sẵn sàng"))

    def _on_finish_all(self):
        self.is_running = False
        self.btn_run.set_state("normal")
        self._refresh_run_control_buttons()
        self._update_status_label()
        self._log("info", "══════ Kết thúc phiên chạy ══════")

    # ================= QUẢN LÝ TÀI KHOẢN (xoay vòng) =================
    def _post_login_account_label_text(self, emulator_index=None):
        """Chuỗi hiển thị Tài khoản đang được gán cho tuỳ chọn 'Đăng Nhập
        TK Chỉ Định Sau Khi Chạy Xong'.

        - emulator_index=None (dùng cho nhãn tóm tắt ở thanh trên): trả về
          số giả lập đã được gán TK riêng.
        - emulator_index=<số> (dùng trong popup chọn theo giả lập): trả về
          tên TK đã gán cho ĐÚNG giả lập đó (hoặc thông báo chưa chọn /
          TK đã bị xoá)."""
        mapping = getattr(self, "_post_login_account_by_emulator", None) or {}
        if emulator_index is None:
            n = len(mapping)
            return f"Đã gán TK riêng cho {n} giả lập" if n else "(chưa gán TK cho giả lập nào)"
        aid = mapping.get(str(emulator_index))
        if not aid:
            return "(chưa chọn TK)"
        for a in account_manager.load_accounts():
            if a.get("id") == aid:
                ten = a.get("ten_hien_thi") or a.get("username") or aid
                return f"TK: {ten}"
        return "(TK đã chọn đã bị xoá)"

    def _pick_post_login_account(self):
        """Popup liệt kê TỪNG giả lập đang có, cho phép gán RIÊNG 1 Tài
        khoản cho mỗi giả lập (dùng cho tuỳ chọn 'Đăng Nhập TK Chỉ Định
        Sau Khi Chạy Xong') - khác với popup chọn NHIỀU tài khoản dùng
        chung (_open_multi_select_dialog) cho Xoay Vòng/Hẹn Giờ, và khác
        bản cũ vốn chỉ cho chọn ĐÚNG 1 TK áp dụng chung cho mọi giả lập."""
        if not getattr(self, "emulators", None):
            messagebox.showinfo("Chưa có giả lập",
                                 "Chưa quét được giả lập nào - bấm '🔄 Quét Giả Lập' rồi thử lại.")
            return

        win = tk.Toplevel(self.root)
        win.title("Chọn Tài Khoản Đăng Nhập Theo Giả Lập")
        win.configure(bg=COL_PANEL)
        win.geometry("440x480")
        _bind_esc_close(win)

        tk.Label(win, text="Mỗi giả lập có thể gán 1 Tài khoản RIÊNG để tự đăng nhập ngay sau khi "
                            "giả lập đó chạy xong (cần Hoạt Động 'account_login' để hoạt động):",
                 bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 9, "bold"),
                 wraplength=400, justify="left").pack(anchor="w", padx=12, pady=(12, 6))

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=6)
        vbar.pack(side="right", fill="y", padx=(0, 6))

        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        row_labels = {}

        def _refresh_row(idx):
            lbl = row_labels.get(idx)
            if lbl:
                lbl.config(text=self._post_login_account_label_text(idx))
            if hasattr(self, "lbl_post_login_account"):
                self.lbl_post_login_account.config(text=self._post_login_account_label_text())

        for e in self.emulators:
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=3, padx=4)
            tk.Label(row, text=e.name, bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 9, "bold"),
                     width=16, anchor="w").pack(side="left", padx=8, pady=6)
            lbl = tk.Label(row, text=self._post_login_account_label_text(e.index), bg=COL_PANEL_ALT,
                           fg=COL_TEXT_MUTED, font=("Segoe UI", 8))
            lbl.pack(side="left", padx=4, pady=6, fill="x", expand=True)
            row_labels[e.index] = lbl
            RoundedButton(row, "🎯 Chọn TK", command=lambda idx=e.index: self._pick_account_for_emulator(idx, _refresh_row),
                          bg=COL_PURPLE, container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold")).pack(
                side="right", padx=8, pady=4)

    def _pick_account_for_emulator(self, emulator_index, on_done=None):
        """Popup chọn ĐÚNG 1 Tài khoản gán cho 1 giả lập cụ thể
        (`emulator_index`) - mở ra từ 1 dòng giả lập trong
        _pick_post_login_account(). Gọi `on_done(emulator_index)` sau khi
        lưu xong để cập nhật lại nhãn hiển thị."""
        accounts = account_manager.load_accounts()
        win = tk.Toplevel(self.root)
        win.title("Chọn Tài Khoản Đăng Nhập Sau Khi Chạy Xong")
        win.configure(bg=COL_PANEL)
        win.geometry("380x460")
        _bind_esc_close(win)

        tk.Label(win, text="Chọn 1 Tài khoản để tự đăng nhập ngay sau khi giả lập này chạy xong "
                            "(cần Hoạt Động 'account_login' để hoạt động):",
                 bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 9, "bold"),
                 wraplength=350, justify="left").pack(anchor="w", padx=12, pady=(12, 6))

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=6)
        vbar.pack(side="right", fill="y", padx=(0, 6))

        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        if not accounts:
            tk.Label(inner, text="Chưa có Tài khoản nào - vào '👥 Quản Lý Tài Khoản' để thêm trước.",
                     bg=COL_PANEL, fg=COL_TEXT_MUTED, wraplength=320, justify="left").pack(pady=20, padx=8)

        def _choose(acc_id):
            mapping = getattr(self, "_post_login_account_by_emulator", None)
            if mapping is None:
                mapping = {}
                self._post_login_account_by_emulator = mapping
            if acc_id:
                mapping[str(emulator_index)] = acc_id
            else:
                mapping.pop(str(emulator_index), None)
            self._save_settings()
            if on_done:
                on_done(emulator_index)
            win.destroy()

        row = tk.Frame(inner, bg=COL_PANEL_ALT)
        row.pack(fill="x", pady=3, padx=4)
        tk.Label(row, text="— Bỏ chọn (không dùng tuỳ chọn này cho giả lập này) —", bg=COL_PANEL_ALT,
                 fg=COL_TEXT_MUTED, font=("Segoe UI", 9, "italic")).pack(side="left", padx=8, pady=6)
        RoundedButton(row, "Chọn", command=lambda: _choose(None), bg=COL_RED, container_bg=COL_PANEL_ALT,
                      font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="right", padx=8, pady=4)

        current_id = (getattr(self, "_post_login_account_by_emulator", {}) or {}).get(str(emulator_index))
        for a in accounts:
            aid = a.get("id")
            ten = a.get("ten_hien_thi") or a.get("username") or aid
            nhom = a.get("nhom") or ""
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=3, padx=4)
            label_text = f"{ten}" + (f"  [{nhom}]" if nhom else "")
            fg = COL_ACCENT if aid == current_id else COL_TEXT
            tk.Label(row, text=label_text, bg=COL_PANEL_ALT, fg=fg, font=("Segoe UI", 9)).pack(
                side="left", padx=8, pady=6)
            RoundedButton(row, "Chọn", command=lambda i=aid: _choose(i), bg=COL_GREEN, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="right", padx=8, pady=4)

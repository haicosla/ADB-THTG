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
from dashboard_widgets import RoundedButton, _bind_esc_close


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

        Nếu CẢ 2 tuỳ chọn cùng bật: ưu tiên TẮT GIẢ LẬP (đăng nhập xong rồi
        tắt ngay sau đó là vô nghĩa) - chỉ cảnh báo, không coi là lỗi."""
        if self.stop_flag:
            return

        want_shutdown = bool(getattr(self, "shutdown_after_var", None) and self.shutdown_after_var.get())
        want_post_login = bool(getattr(self, "post_login_after_var", None) and self.post_login_after_var.get())

        if want_shutdown:
            if want_post_login:
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
            acc = self._get_post_run_account()
            if not acc:
                self._log("warn", f"Đã bật 'Đăng Nhập TK Chỉ Định Sau Khi Chạy Xong' nhưng chưa chọn Tài khoản "
                                   f"hợp lệ (bấm '🎯 Chọn TK' để chọn, hoặc tài khoản đã chọn đang TẮT/bị xoá) - "
                                   f"bỏ qua trên '{emulator.name}'.", emulator_name=emulator.name)
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

    def _get_post_run_account(self):
        """Trả về dict Tài khoản đã chọn cho tuỳ chọn 'Đăng Nhập TK Chỉ
        Định Sau Khi Chạy Xong' (None nếu chưa chọn/đã bị xoá/đang TẮT)."""
        aid = getattr(self, "_post_login_account_id", None) or self._settings.get("post_login_account_id")
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
    def _post_login_account_label_text(self):
        """Chuỗi hiển thị cạnh nút '🎯 Chọn TK' - tên Tài khoản đang được
        chọn cho tuỳ chọn 'Đăng Nhập TK Chỉ Định Sau Khi Chạy Xong' (hoặc
        thông báo chưa chọn / tài khoản đã bị xoá)."""
        aid = getattr(self, "_post_login_account_id", None)
        if not aid:
            return "(chưa chọn TK)"
        for a in account_manager.load_accounts():
            if a.get("id") == aid:
                ten = a.get("ten_hien_thi") or a.get("username") or aid
                return f"TK: {ten}"
        return "(TK đã chọn đã bị xoá)"

    def _pick_post_login_account(self):
        """Popup chọn ĐÚNG 1 Tài khoản dùng cho tuỳ chọn 'Đăng Nhập TK Chỉ
        Định Sau Khi Chạy Xong' - khác với popup chọn NHIỀU tài khoản
        (_open_multi_select_dialog) dùng cho Xoay Vòng/Hẹn Giờ."""
        accounts = account_manager.load_accounts()
        win = tk.Toplevel(self.root)
        win.title("Chọn Tài Khoản Đăng Nhập Sau Khi Chạy Xong")
        win.configure(bg=COL_PANEL)
        win.geometry("380x460")
        _bind_esc_close(win)

        tk.Label(win, text="Chọn 1 Tài khoản để tự đăng nhập ngay sau khi giả lập chạy xong "
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
            self._post_login_account_id = acc_id
            self.lbl_post_login_account.config(text=self._post_login_account_label_text())
            self._save_settings()
            win.destroy()

        row = tk.Frame(inner, bg=COL_PANEL_ALT)
        row.pack(fill="x", pady=3, padx=4)
        tk.Label(row, text="— Bỏ chọn (không dùng tuỳ chọn này) —", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 9, "italic")).pack(side="left", padx=8, pady=6)
        RoundedButton(row, "Chọn", command=lambda: _choose(None), bg=COL_RED, container_bg=COL_PANEL_ALT,
                      font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="right", padx=8, pady=4)

        for a in accounts:
            aid = a.get("id")
            ten = a.get("ten_hien_thi") or a.get("username") or aid
            nhom = a.get("nhom") or ""
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=3, padx=4)
            label_text = f"{ten}" + (f"  [{nhom}]" if nhom else "")
            fg = COL_ACCENT if aid == getattr(self, "_post_login_account_id", None) else COL_TEXT
            tk.Label(row, text=label_text, bg=COL_PANEL_ALT, fg=fg, font=("Segoe UI", 9)).pack(
                side="left", padx=8, pady=6)
            RoundedButton(row, "Chọn", command=lambda i=aid: _choose(i), bg=COL_GREEN, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="right", padx=8, pady=4)

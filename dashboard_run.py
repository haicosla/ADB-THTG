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
import window_geometry as wg
import run_state
import account_manager
import activity_groups
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, _bind_esc_close
from dashboard_schedule import SYS_EMU_ON, SYS_EMU_OFF, SYS_LOGOUT, SYS_LOGIN_PREFIX


class RunMixin:
    _STOP_TARGET_ALL = "🌐 Tất cả giả lập"

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
        # Xoá cờ DỪNG/TẠM DỪNG RIÊNG còn sót lại (nếu giả lập này từng bị
        # dừng riêng ở lượt chạy trước) - tránh lượt chạy MỚI bị coi là "đã
        # bị dừng" ngay từ đầu do cờ cũ chưa được dọn.
        for e in selected_emulators:
            self.stop_flags.pop(e.index, None)
            self.pause_flags.pop(e.index, None)
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

    # ================= DỪNG / TẠM DỪNG (TẤT CẢ hoặc 1 giả lập chỉ định) =================
    def _emulator_name_by_index(self, emulator_index):
        for e in getattr(self, "emulators", []) or []:
            if e.index == emulator_index:
                return e.name
        return f"#{emulator_index}"

    def _refresh_stop_target_options(self):
        """Cập nhật danh sách lựa chọn ở ô 'Áp dụng cho' (combo_stop_target,
        xem dashboard_ui.py) - luôn có mục '🌐 Tất cả giả lập' + 1 mục cho
        MỖI giả lập đang bận (self._busy_emulator_indexes) để người dùng có
        thể chọn Dừng/Tạm Dừng RIÊNG đúng luồng đang chạy trên giả lập đó."""
        if not hasattr(self, "combo_stop_target"):
            return
        all_label = self._STOP_TARGET_ALL
        options = [all_label]
        mapping = {all_label: None}
        for idx in sorted(self._busy_emulator_indexes):
            label = f"🎯 {self._emulator_name_by_index(idx)} (#{idx})"
            options.append(label)
            mapping[label] = idx
        self.combo_stop_target["values"] = options
        self._stop_target_label_to_index = mapping
        if self.stop_target_var.get() not in mapping:
            self.stop_target_var.set(all_label)

    def _get_stop_target_index(self):
        """None = đang chọn '🌐 Tất cả giả lập'; ngược lại trả về index của
        1 giả lập cụ thể đang được chọn ở ô 'Áp dụng cho'."""
        if not hasattr(self, "stop_target_var"):
            return None
        label = self.stop_target_var.get()
        mapping = getattr(self, "_stop_target_label_to_index", {})
        return mapping.get(label)

    def _is_stop_requested(self, emulator_index):
        """True nếu luồng của giả lập `emulator_index` cần DỪNG HẲN - do
        bấm DỪNG áp dụng cho TẤT CẢ (self.stop_flag) HOẶC bấm DỪNG chỉ định
        RIÊNG đúng giả lập này (self.stop_flags[emulator_index])."""
        return self.stop_flag or self.stop_flags.get(emulator_index, False)

    def _is_pause_requested(self, emulator_index):
        """Tương tự _is_stop_requested nhưng cho TẠM DỪNG."""
        return self.pause_flag or self.pause_flags.get(emulator_index, False)

    def stop_run(self):
        target = self._get_stop_target_index()
        if target is None:
            self.stop_flag = True
            self.pause_flag = False
            # Bấm DỪNG "Tất cả" thì các cờ dừng/tạm dừng RIÊNG từng giả lập
            # (nếu có) cũng coi như đã dừng theo, không cần giữ lại riêng lẻ.
            for idx in list(self.stop_flags.keys()):
                self.stop_flags[idx] = True
            for idx in list(self.pause_flags.keys()):
                self.pause_flags[idx] = False
            self._log("warn", "Người dùng bấm DỪNG (Tất cả giả lập) - đang chờ các luồng/lịch hiện tại kết thúc...")
        else:
            self.stop_flags[target] = True
            self.pause_flags[target] = False
            self._log("warn", f"Người dùng bấm DỪNG RIÊNG giả lập '{self._emulator_name_by_index(target)}' - "
                               f"các giả lập khác vẫn tiếp tục chạy bình thường.",
                       emulator_name=self._emulator_name_by_index(target))
        self.btn_pause.set_text("⏸ Tạm Dừng")

    def _any_active_work(self):
        """True nếu có BẤT KỲ việc gì đang chạy - phiên CHẠY thủ công (tick
        chọn tác vụ) HOẶC 1 lịch hẹn giờ đang thực thi. Dùng để bật/tắt nút
        DỪNG + Tạm Dừng đúng lúc kể cả khi việc đang chạy là do lịch tự kích
        hoạt (người dùng không hề bấm nút CHẠY)."""
        return (self.is_running or self._active_schedule_count > 0
                or getattr(self, "_active_quicklogin_count", 0) > 0)

    def _refresh_run_control_buttons(self):
        active = self._any_active_work()
        self.btn_stop.set_state("normal" if active else "disabled")
        self.btn_pause.set_state("normal" if active else "disabled")
        self._refresh_stop_target_options()
        if not active:
            # Không còn gì chạy -> RESET stop_flag để LẦN TRIGGER TIẾP THEO
            # của 1 lịch hẹn giờ (không đi qua _start_run - nơi duy nhất
            # trước đây reset cờ này) không bị coi là "đã bị dừng" ngay từ
            # đầu và im lặng không chạy gì cả. Dọn luôn các cờ dừng/tạm dừng
            # RIÊNG theo giả lập (self.stop_flags/self.pause_flags) vì
            # không còn giả lập nào đang bận để áp dụng nữa.
            self.stop_flag = False
            self.pause_flag = False
            self.stop_flags.clear()
            self.pause_flags.clear()
            self.btn_pause.set_text("⏸ Tạm Dừng")
            if hasattr(self, "stop_target_var"):
                self.stop_target_var.set(self._STOP_TARGET_ALL)

    def toggle_pause(self):
        """Bật/tắt tạm dừng - áp dụng cho TẤT CẢ giả lập đang chạy hoặc CHỈ
        1 giả lập cụ thể, tuỳ theo lựa chọn ở ô 'Áp dụng cho' cạnh nút
        Dừng/Tạm Dừng (xem _get_stop_target_index). Không dừng hẳn luồng -
        chỉ chặn LogicEngine lại NGAY TRƯỚC lần kiểm tra dừng kế tiếp (xem
        _make_stop_checker), nên độ trễ tạm dừng chỉ trong vòng 1 bước/1
        vòng lặp chờ ảnh, không phải chờ hết cả tác vụ."""
        if not self._any_active_work():
            return
        target = self._get_stop_target_index()
        if target is None:
            self.pause_flag = not self.pause_flag
            paused = self.pause_flag
            who = "TẤT CẢ giả lập"
        else:
            paused = not self.pause_flags.get(target, False)
            self.pause_flags[target] = paused
            who = f"giả lập '{self._emulator_name_by_index(target)}'"

        if paused:
            self.btn_pause.set_text("▶ Tiếp Tục")
            self._log("warn", f"Người dùng bấm TẠM DỪNG ({who}) - sẽ dừng lại giữa bước hiện tại, "
                               f"bấm '▶ Tiếp Tục' để chạy tiếp.")
        else:
            self.btn_pause.set_text("⏸ Tạm Dừng")
            self._log("info", f"Đã bấm TIẾP TỤC ({who}) - chạy lại bình thường.")

    def _make_stop_checker(self, emulator_index):
        """Trả về hàm stop_checker() cho LogicEngine của 1 luồng giả lập
        (`emulator_index`). LogicEngine gọi hàm này liên tục ở MỌI điểm
        dừng an toàn (giữa mỗi bước, trong vòng lặp chờ ảnh...) để biết có
        nên dừng hẳn không - tận dụng luôn các điểm gọi đó làm điểm TẠM
        DỪNG: khi _is_pause_requested(emulator_index) đang bật, hàm sẽ
        'đứng chờ' tại đây (vẫn kiểm tra _is_stop_requested để nút DỪNG
        luôn hoạt động ngay cả khi đang tạm dừng) thay vì trả về ngay, nên
        KHÔNG cần sửa gì trong logic_engine.py.

        Cả 2 hàm _is_stop_requested/_is_pause_requested đều gộp CẢ cờ TỔNG
        (self.stop_flag/self.pause_flag - áp dụng Tất Cả) LẪN cờ RIÊNG của
        đúng emulator_index này (self.stop_flags/self.pause_flags) - nên
        luồng này dừng/tạm dừng khi BẤT KỲ cờ nào trong 2 loại đó bật lên."""
        def checker():
            while self._is_pause_requested(emulator_index) and not self._is_stop_requested(emulator_index):
                time.sleep(0.15)
            return self._is_stop_requested(emulator_index)
        return checker

    def _worker_run_emulator(self, emulator, selected, login_entry):
        # Tự BẬT giả lập nếu đang tắt (trước đây hàm này chỉ kiểm tra
        # 'adb devices' bằng ensure_adb_connected() - nếu giả lập đang tắt
        # thì DỪNG LUÔN, không tự bật, khác với luồng Xoay Vòng Tài Khoản/
        # Hẹn Giờ vốn đã tự bật từ trước - giờ đồng bộ lại, dùng
        # ensure_running() giống 2 luồng kia để hành vi nhất quán dù chạy
        # kiểu nào (CHẠY tay/Chọn Hành Động Để Chạy/Xoay Vòng/Hẹn Giờ)).
        if not self.emu_manager.is_ready(emulator):
            self._log("info", f"Giả lập '{emulator.name}' đang tắt - đang tự bật...", emulator_name=emulator.name)
            ready_info, _auto_started = self.emu_manager.ensure_running(
                emulator.index, timeout=120,
                on_log=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name))
            if not ready_info:
                self._log("error", f"Không tự bật được giả lập '{emulator.name}' - bỏ qua giả lập này.",
                           emulator_name=emulator.name)
                self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
                return
            emulator = ready_info  # dùng thông tin MỚI NHẤT (hwnd/serial có thể đổi sau khi vừa bật lại)
            # Vừa TỰ KHỞI ĐỘNG -> chờ thêm (ô 'Chờ boot') cho game lên hẳn; ngay sau đó
            # vòng lặp bên dưới chạy 'auto_login' trước tác vụ đầu tiên như thường lệ.
            if _auto_started and login_entry is not None:
                self._wait_after_boot_for_autologin(emulator)

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
            stop_checker=self._make_stop_checker(emulator.index),
            popup_notifier=lambda msg, dur=0, bg=None, fg=None, alpha=None, pos_box=None, _wf=wf: self._show_ingame_popup(_wf, msg, dur, bg, fg, alpha, pos_box),
            logger=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )

        # "Tự Login" (login_entry, Hoạt Động id 'auto_login') là 1 HÀNH
        # ĐỘNG RIÊNG, KHÔNG phải kịch bản đăng nhập tài khoản
        # ('account_login' - dùng cho Xoay Vòng Tài Khoản) - mục đích CHỈ
        # là đưa giả lập VÀO ĐÚNG MÀN HÌNH GAME (tự soạn kịch bản này với
        # các bước wait_image/if_image để tự kiểm tra đã vào game hay
        # chưa). Chạy lại TRƯỚC MỖI tác vụ đã tick (không chỉ 1 lần đầu)
        # để tự phát hiện + đăng nhập lại nếu giữa chừng bị văng ra khỏi
        # game (crash, bị đá về màn hình chờ...) - tác vụ nào mà lúc đó
        # 'auto_login' báo THẤT BẠI (không vào được game) sẽ bị BỎ QUA
        # RIÊNG tác vụ đó (không huỷ hẳn cả phiên), rồi vẫn thử tiếp tác
        # vụ kế tiếp trong danh sách đã tick.
        for entry in selected:
            if self._is_stop_requested(emulator.index):
                break
            if login_entry is not None:
                ok_login = self._exec_entry(engine, emulator, login_entry, preset_vars=None, tracked=False)
                if self._is_stop_requested(emulator.index):
                    break
                if not ok_login:
                    task_name = entry.get("ten_hien_thi", entry.get("id"))
                    self._log("error", f"Tự Login thất bại (chưa vào được game) trên '{emulator.name}' trước khi "
                                        f"chạy '{task_name}' - bỏ qua RIÊNG tác vụ này, thử tiếp tác vụ kế tiếp.",
                               emulator_name=emulator.name)
                    continue
            self._exec_entry(engine, emulator, entry, preset_vars=None, tracked=True)

        self._apply_post_run_options(engine, emulator)
        self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))

    # ================= "📦 NHÓM HÀNH ĐỘNG" - CHẠY THẲNG 1 NHÓM (xem
    # activity_groups.py + dashboard_groups.py) =================
    def _start_run_group(self, group_ids, tag, selected_emulators):
        """Chạy thẳng 1 '📦 Nhóm Hành Động' (danh sách bước đã soạn sẵn -
        Hoạt Động/Hành động hệ thống/Nhóm lồng nhau) trên các giả lập đã
        chọn - mirror y hệt _start_run() (xếp hàng chờ nếu giả lập đang
        bận, KHÔNG tự bỏ qua) nhưng KHÔNG đụng tới self.task_progress/nhãn
        trạng thái trên danh sách Hoạt Động chính, vì 1 Nhóm không phải là
        1 dòng trong danh sách đó (xem _worker_run_group bên dưới, tái
        dùng lõi _run_post_run_steps() để thực thi)."""
        available, busy = self._split_busy_emulators(selected_emulators)
        for e in busy:
            self._queue_job(e, {"kind": "run_group", "group_ids": group_ids, "tag": tag}, f"chạy Nhóm '{tag}'")
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
        for e in selected_emulators:
            self.stop_flags.pop(e.index, None)
            self.pause_flags.pop(e.index, None)
        self._refresh_run_control_buttons()
        self._update_status_label()
        names = ", ".join(e.name for e in selected_emulators)
        self._log("info", f"══════ Bắt đầu chạy Nhóm '{tag}' trên [{names}] ══════")

        for emulator in selected_emulators:
            self._busy_emulator_indexes.add(emulator.index)
            threading.Thread(target=self._worker_run_group, args=(emulator, group_ids, tag), daemon=True).start()

    def _worker_run_group(self, emulator, group_ids, tag):
        """Chạy 1 '📦 Nhóm Hành Động' trên ĐÚNG 1 giả lập - tự bật giả lập
        nếu đang tắt (giống _worker_run_emulator), rồi giao hẳn việc thực
        thi cho _run_post_run_steps() (lõi dùng chung 3 nơi: Hành Động Cuối
        theo giả lập, Hành Động Cuối riêng theo lịch, và Nhóm chạy thẳng ở
        đây)."""
        if not self.emu_manager.is_ready(emulator):
            self._log("info", f"Giả lập '{emulator.name}' đang tắt - đang tự bật...", emulator_name=emulator.name)
            ready_info, _auto_started = self.emu_manager.ensure_running(
                emulator.index, timeout=120,
                on_log=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name))
            if not ready_info:
                self._log("error", f"Không tự bật được giả lập '{emulator.name}' - bỏ qua giả lập này.",
                           emulator_name=emulator.name)
                self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))
                return
            emulator = ready_info
            if _auto_started:
                self._wait_after_boot_for_autologin(emulator, context_label=tag)

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
            self._log("warn", f"Cửa sổ LDPlayer '{emulator.name}' đang bị THU NHỎ - đã tự khôi phục lại.",
                       emulator_name=emulator.name)
            time.sleep(0.5)

        engine = LogicEngine(
            adb,
            stop_checker=self._make_stop_checker(emulator.index),
            popup_notifier=lambda msg, dur=0, bg=None, fg=None, alpha=None, pos_box=None, _wf=wf: self._show_ingame_popup(_wf, msg, dur, bg, fg, alpha, pos_box),
            logger=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )

        self._run_post_run_steps(engine, emulator, group_ids, tag=tag)
        self.root.after(0, lambda: self._on_emulator_thread_done(emulator.index))

    # ================= TỰ LOGIN KHI GIẢ LẬP VỪA KHỞI ĐỘNG / TRƯỚC ĐĂNG XUẤT-ĐĂNG NHẬP =================
    def _get_boot_wait_seconds(self):
        """Số giây CHỜ thêm sau khi giả lập báo boot xong (Android đã lên)
        rồi mới chạy 'auto_login' - đọc từ ô 'Chờ boot (s)' ở thanh trên.
        Máy khởi động nhanh để nhỏ, máy chậm để lớn. Giá trị hỏng -> 10s."""
        try:
            v = int(float(self.boot_wait_var.get()))
        except Exception:
            v = 10
        return max(0, min(v, 600))

    def _wait_after_boot_for_autologin(self, emulator, context_label=None):
        """Sau khi 1 giả lập VỪA ĐƯỢC KHỞI ĐỘNG (boot xong theo ADB), chờ
        thêm `_get_boot_wait_seconds()` giây cho launcher/game kịp lên hẳn
        rồi mới cho 'auto_login' chạy. CHỈ chờ khi 'Tự Login' đang bật (nếu
        không có gì chạy 'auto_login' thì chờ cũng vô ích). Ngắt ngay nếu
        người dùng bấm DỪNG."""
        if not (getattr(self, "auto_login_var", None) and self.auto_login_var.get()):
            return
        secs = self._get_boot_wait_seconds()
        if secs <= 0:
            return
        prefix = f"[{context_label}] " if context_label else ""
        self._log("info", f"{prefix}Giả lập '{emulator.name}' vừa khởi động - chờ thêm {secs}s cho game/launcher "
                           f"lên hẳn rồi mới chạy Tự Login...", emulator_name=emulator.name)
        end = time.time() + secs
        while time.time() < end:
            if self._is_stop_requested(emulator.index):
                return
            time.sleep(0.5)

    def _autologin_after_boot(self, engine, emulator, context_label=None):
        """Dùng cho bước hệ thống 'Bật giả lập' (kể cả 'Tắt' rồi 'Bật' lại):
        khi giả lập THẬT SỰ vừa được khởi động -> chờ boot-wait rồi chạy
        'auto_login' để vào game, bất kể bước này nằm ở đâu trong chuỗi.
        Trả về True nếu không cần/đã vào game, False nếu Tự Login thất bại
        hoặc bị dừng (nơi gọi chỉ cảnh báo, KHÔNG coi là 'Bật giả lập' thất bại)."""
        if not (getattr(self, "auto_login_var", None) and self.auto_login_var.get()):
            return True
        entry = task_registry.find_task(self.tasks, "auto_login")
        if not entry:
            self._log("warn", "Đã bật 'Tự Login' nhưng chưa có Hoạt Động với id 'auto_login' (xem '📖 Hướng Dẫn') "
                               "- bỏ qua Tự Login sau khi khởi động.", emulator_name=emulator.name)
            return False
        self._wait_after_boot_for_autologin(emulator, context_label)
        if self._is_stop_requested(emulator.index):
            return False
        ok = self._exec_entry(engine, emulator, entry, preset_vars=None, tracked=False, context_label=context_label)
        if not ok and not self._is_stop_requested(emulator.index):
            self._log("warn", f"Tự Login thất bại (chưa vào được game) sau khi khởi động '{emulator.name}'.",
                       emulator_name=emulator.name)
        return ok

    def _autologin_before_step(self, engine, emulator, context_label, tag, step_name):
        """Chạy 'auto_login' NGAY TRƯỚC 1 bước hệ thống Đăng Xuất/Đăng Nhập
        (nếu 'Tự Login' đang bật) để chắc giả lập đang ở trong game - giống
        luồng Xoay Vòng Tài Khoản/Log Nhanh. Thất bại chỉ cảnh báo, vẫn chạy
        tiếp bước đó. Trả về False nếu người dùng bấm DỪNG giữa chừng."""
        if not (getattr(self, "auto_login_var", None) and self.auto_login_var.get()):
            return True
        entry = task_registry.find_task(self.tasks, "auto_login")
        if not entry:
            self._log("warn", f"[{tag}] {step_name}: đã bật 'Tự Login' nhưng chưa có Hoạt Động 'auto_login' - "
                               f"chạy thẳng bước này.", emulator_name=emulator.name)
            return True
        ok = self._exec_entry(engine, emulator, entry, preset_vars=None, tracked=False, context_label=context_label)
        if self._is_stop_requested(emulator.index):
            return False
        if not ok:
            self._log("warn", f"[{tag}] {step_name}: Tự Login thất bại (chưa vào được game) - vẫn chạy bước này "
                               f"như bình thường.", emulator_name=emulator.name)
        return True

    def _run_login_check_standalone(self, emulator, context_label="Tự Login"):
        """Chạy Hoạt Động 'auto_login' (nếu có) trên `emulator` MỘT MÌNH,
        KHÔNG cần đã có sẵn 1 phiên CHẠY nào đang mở - tự dựng riêng
        ADB/WindowFinder/LogicEngine cho đúng 1 lần chạy này. Dùng ở
        NHỮNG NƠI CHƯA có `engine` sẵn (vd tự chạy ngay sau khi khởi
        động xong 1 giả lập ở dashboard_emulators.py, xem
        _worker_wait_boot_then_autologin) - nơi ĐÃ có `engine` sẵn (vòng
        lặp tác vụ trong _worker_run_emulator ở trên) thì gọi thẳng
        `_exec_entry(engine, ...)` cho nhẹ, không cần qua hàm này.

        Trả về True/False (có vào được game hay không); False luôn kèm
        1 dòng log giải thích lý do (chưa soạn 'auto_login', mất kết nối
        ADB, hay 'auto_login' tự báo thất bại)."""
        login_entry = task_registry.find_task(self.tasks, "auto_login")
        if not login_entry:
            self._log("warn", f"Đã bật 'Tự Login' nhưng chưa có Hoạt Động với id 'auto_login' (xem "
                               f"'📖 Hướng Dẫn') - bỏ qua {context_label} trên '{emulator.name}'.",
                       emulator_name=emulator.name)
            return False

        if not self.emu_manager.ensure_adb_connected(emulator):
            self._log("error", f"Không thấy giả lập '{emulator.name}' trong 'adb devices' - bỏ qua "
                                f"{context_label}.", emulator_name=emulator.name)
            return False

        adb = ADBHelper()
        adb.device_id = emulator.adb_serial
        adb.update_resolution()

        wf = WindowFinder(adb)
        attached = wf.attach_hwnd(emulator.hwnd) if emulator.hwnd else False
        if not attached:
            wf.find_ld_windows()
        if wf.ensure_window_visible():
            time.sleep(0.5)

        engine = LogicEngine(
            adb,
            stop_checker=self._make_stop_checker(emulator.index),
            popup_notifier=lambda msg, dur=0, bg=None, fg=None, alpha=None, pos_box=None, _wf=wf: self._show_ingame_popup(_wf, msg, dur, bg, fg, alpha, pos_box),
            logger=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )
        ok = self._exec_entry(engine, emulator, login_entry, preset_vars=None, tracked=False)
        if ok:
            self._log("success", f"{context_label}: đã vào game trên '{emulator.name}'.", emulator_name=emulator.name)
        else:
            self._log("error", f"{context_label}: KHÔNG vào được game trên '{emulator.name}'.", emulator_name=emulator.name)
        return ok

    # ================= HÀNH ĐỘNG CUỐI (KỊCH BẢN MINI SAU KHI 1 GIẢ LẬP
    # CHẠY XONG) =================
    # Thay vì chỉ 1 hành động cố định (4 mode) như bản trước, giờ mỗi giả
    # lập được gán 1 DANH SÁCH BƯỚC CÓ THỨ TỰ (self._post_run_steps_by_emulator,
    # khoá str(emulator.index) -> list id) - TÁI DÙNG NGUYÊN XI cơ chế "Hành
    # động hệ thống" (SYS_EMU_ON/SYS_EMU_OFF/SYS_LOGOUT/SYS_LOGIN_PREFIX,
    # _build_activity_steps(), _exec_system_action()) đã có sẵn ở '⏰ Hẹn
    # Giờ' (xem dashboard_schedule.py) thay vì viết lại 1 bộ khác - mỗi id
    # trong danh sách hoặc là 1 Hoạt Động thật (macro), hoặc là 1 "Hành
    # động hệ thống" (Bật/Tắt giả lập, Đăng Xuất, Đăng Nhập 1 TK CỤ THỂ -
    # chọn thẳng bất kỳ tài khoản nào, không còn khái niệm "TK mặc định"
    # riêng nữa). Nhờ vậy có thể soạn ví dụ: Đăng Xuất -> Đăng Nhập TK X ->
    # Hoạt Động B -> Tắt giả lập, y hệt cách soạn 1 lịch hẹn giờ.
    def _post_run_action_summary_text(self):
        """Chuỗi tóm tắt cạnh nút '🏁 Hành Động Cuối Theo Giả Lập' ở thanh
        trên - đếm bao nhiêu giả lập đã được soạn ít nhất 1 bước."""
        mapping = getattr(self, "_post_run_steps_by_emulator", None) or {}
        n = sum(1 for v in mapping.values() if v)
        return f"Đã cấu hình {n} giả lập" if n else "(chưa cấu hình giả lập nào)"

    def _run_post_run_steps(self, engine, emulator, ids, tag="🏁 Hành Động Cuối"):
        """Chạy lần lượt (ĐÚNG THỨ TỰ) 1 danh sách bước `ids` (Hoạt Động +
        Hành động hệ thống, cùng định dạng `hoat_dong_ids` của 1 lịch hẹn
        giờ) trên `emulator` - hàm LÕI dùng chung cho cả 2 chỗ:
          - Hành Động Cuối GỘP theo GIẢ LẬP (self._post_run_steps_by_emulator,
            xem _apply_post_run_options bên dưới).
          - Hành Động Cuối RIÊNG theo TỪNG LỊCH hẹn giờ (entry['hanh_dong_cuoi_ids'],
            xem _apply_post_run_options_for_schedule ở dashboard_schedule.py) -
            độc lập hẳn với giả lập, mỗi lịch tự soạn chuỗi bước của riêng
            nó, không ảnh hưởng lẫn nhau hay ảnh hưởng cấu hình theo giả lập."""
        if not ids:
            return
        tasks_by_id = {(t.get("id") or task_registry.make_task_id(t.get("file_json", ""))): t
                        for t in self.tasks}
        accounts_by_id = {a.get("id"): a for a in account_manager.load_accounts()}
        steps = self._build_activity_steps(ids, tasks_by_id, accounts_by_id)
        if not steps:
            return

        login_entry = task_registry.find_task(self.tasks, "account_login")
        logout_entry = task_registry.find_task(self.tasks, "account_logout")
        self._log("info", f"[{tag}] Bắt đầu {len(steps)} bước hậu kỳ trên '{emulator.name}'...",
                   emulator_name=emulator.name)
        for step in steps:
            if self._is_stop_requested(emulator.index):
                break
            if step.get("__he_thong__"):
                self._exec_system_action(engine, emulator, step, tag, tag, login_entry, logout_entry)
            else:
                self._exec_entry(engine, emulator, step, preset_vars=None, tracked=False, context_label=tag)

    def _apply_post_run_options(self, engine, emulator):
        """Chạy 'Hành Động Cuối' GỘP THEO GIẢ LẬP (xem '🏁 Hành Động Cuối
        Theo Giả Lập' ở thanh trên, self._post_run_steps_by_emulator) -
        gọi SAU KHI 1 giả lập vừa chạy xong hết các tác vụ của lượt hiện
        tại (CHẠY tay/Chọn Hành Động Để Chạy/Xoay Vòng Tài Khoản đều dùng
        chung). Lịch hẹn giờ KHÔNG gọi thẳng hàm này nữa - xem
        _apply_post_run_options_for_schedule() ở dashboard_schedule.py
        (mỗi lịch có Hành Động Cuối RIÊNG, độc lập, chỉ rơi về dùng hàm
        này khi lịch đó CHƯA soạn Hành Động Cuối riêng).

        KHÔNG áp dụng nếu người dùng đã bấm DỪNG giữa chừng (self.stop_flag)
        - chạy tiếp hành động cuối ngay sau khi vừa bị dừng dở dang dễ gây
        hiểu nhầm/ghi đè trạng thái người dùng đang muốn giữ nguyên để
        kiểm tra."""
        if self._is_stop_requested(emulator.index):
            return
        ids = (getattr(self, "_post_run_steps_by_emulator", None) or {}).get(str(emulator.index)) or []
        self._run_post_run_steps(engine, emulator, ids, tag="🏁 Hành Động Cuối")

    def _pick_post_run_actions(self):
        """Popup DUY NHẤT liệt kê từng giả lập, mỗi giả lập soạn 1 DANH
        SÁCH BƯỚC có thứ tự (tái dùng popup '🎯 Chọn Hoạt Động' kèm '⚙
        Thao tác hệ thống' y hệt Hẹn Giờ, xem _open_multi_select_dialog
        ở dashboard_dialogs.py) - thay cho popup chọn 1-trong-4-mode ở
        bản trước."""
        if not getattr(self, "emulators", None):
            messagebox.showinfo("Chưa có giả lập",
                                 "Chưa quét được giả lập nào - bấm '🔄 Quét Giả Lập' rồi thử lại.")
            return

        mapping = getattr(self, "_post_run_steps_by_emulator", None)
        if mapping is None:
            mapping = {}
            self._post_run_steps_by_emulator = mapping

        accounts = account_manager.load_accounts()
        activity_items = [
            (t.get("id") or task_registry.make_task_id(t.get("file_json", "")), t.get("ten_hien_thi", "?"))
            for t in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0)))
        ]
        activity_group_of = {
            (t.get("id") or task_registry.make_task_id(t.get("file_json", ""))): (t.get("muc") or "")
            for t in self.tasks
        }
        # "Nhóm Hành Động" cũng chọn được như 1 Hoạt Động (xem cách dùng y
        # hệt ở dashboard_schedule.py::_open_schedule_manager).
        for g in activity_groups.load_groups():
            gid = f"{activity_groups.GROUP_PREFIX}{g.get('id')}"
            activity_items.append((gid, f"📦 {g.get('ten', '?')}"))
            activity_group_of[gid] = "📦 Nhóm Hành Động"

        win = tk.Toplevel(self.root)
        win.title("Chọn Hành Động Cuối Theo Giả Lập")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "run_pick_post_run_actions", default="480x520")
        wg.autosave(win, "run_pick_post_run_actions")
        _bind_esc_close(win)

        tk.Label(win, text="Mỗi giả lập soạn 1 CHUỖI BƯỚC (Hoạt Động thường xen kẽ Hành động hệ thống: Bật/"
                            "Tắt giả lập, Đăng Xuất, Đăng Nhập 1 TK cụ thể) tự chạy LẦN LƯỢT ĐÚNG THỨ TỰ ngay "
                            "sau khi giả lập đó chạy xong hết:",
                 bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 9, "bold"),
                 wraplength=440, justify="left").pack(anchor="w", padx=12, pady=(12, 6))

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

        def _refresh_summary():
            if hasattr(self, "lbl_post_run_action"):
                self.lbl_post_run_action.config(text=self._post_run_action_summary_text())

        row_btns = {}

        def _btn_label(idx):
            n = len(mapping.get(str(idx)) or [])
            return f"🏁 Hành Động Cuối ({n} bước)" if n else "🏁 Hành Động Cuối (chưa soạn)"

        for e in self.emulators:
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=3, padx=4)
            tk.Label(row, text=e.name, bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 9, "bold"),
                     width=16, anchor="w").pack(side="left", padx=8, pady=6)

            btn = RoundedButton(row, _btn_label(e.index), bg=COL_PURPLE, container_bg=COL_PANEL_ALT,
                                 font=("Segoe UI", 8, "bold"), padx=8, pady=3)
            btn.pack(side="right", padx=8, pady=4)
            row_btns[e.index] = btn

            def _open_editor(idx=e.index, btn=btn):
                self._open_post_run_steps_editor(idx, accounts, activity_items, activity_group_of,
                                                  on_saved=lambda: (btn.set_text(_btn_label(idx)), _refresh_summary()))
            btn.command = _open_editor

        RoundedButton(win, "Đóng", command=win.destroy, bg=COL_GREEN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9, "bold"), padx=16, pady=6).pack(side="bottom", pady=10)

    def _open_steps_editor(self, title, current_ids, accounts, activity_items, activity_group_of, on_save):
        """Mở popup '🎯 Chọn Hoạt Động' kèm '⚙ Thao tác hệ thống' (dùng
        chung `_open_multi_select_dialog`, xem cách dựng `system_actions`
        y hệt ở dashboard_schedule.py::_open_schedule_manager) để soạn 1
        chuỗi bước có thứ tự - hàm TỔNG QUÁT, không tự lưu vào đâu cả, chỉ
        gọi `on_save(list_id_đã_chọn)` khi bấm Lưu - bên gọi tự quyết định
        lưu vào đâu (mapping theo GIẢ LẬP hay theo TỪNG LỊCH riêng, xem
        _open_post_run_steps_editor() bên dưới và
        dashboard_schedule.py::_open_schedule_final_action_editor())."""
        sys_extra_labels = {
            SYS_EMU_ON: "🟢 Bật giả lập",
            SYS_EMU_OFF: "🔴 Tắt giả lập",
            SYS_LOGOUT: "🚪 Đăng xuất tài khoản",
        }
        sys_extra_labels.update({
            f"{SYS_LOGIN_PREFIX}{a.get('id')}":
                f"🔑 Đăng nhập tài khoản: {a.get('ten_hien_thi') or a.get('username') or a.get('id')}"
            for a in accounts
        })

        def _sys_action_login(add_fn):
            if not accounts:
                messagebox.showwarning("Chưa có tài khoản",
                                        "Chưa có Tài Khoản nào - hãy thêm ở '👥 Quản Lý Tài Khoản' trước.",
                                        parent=self.root)
                return
            acc_by_id = {a.get("id"): a for a in accounts}
            acc_choices = [(a.get("id"), a.get("ten_hien_thi") or a.get("username") or a.get("id"))
                           for a in accounts]

            def _on_pick(acc_id):
                acc = acc_by_id.get(acc_id)
                if not acc:
                    return
                iid = f"{SYS_LOGIN_PREFIX}{acc_id}"
                label = f"🔑 Đăng nhập tài khoản: {acc.get('ten_hien_thi') or acc.get('username') or acc_id}"
                add_fn(iid, label)

            self._open_single_select_dialog(self.root, "Chọn tài khoản để Đăng Nhập", acc_choices, _on_pick)

        system_actions = [
            ("🟢 Bật giả lập", lambda add_fn: add_fn(SYS_EMU_ON, "🟢 Bật giả lập")),
            ("🔴 Tắt giả lập", lambda add_fn: add_fn(SYS_EMU_OFF, "🔴 Tắt giả lập")),
            ("🚪 Đăng xuất tài khoản", lambda add_fn: add_fn(SYS_LOGOUT, "🚪 Đăng xuất tài khoản")),
            ("🔑 Đăng nhập tài khoản", _sys_action_login),
        ]

        self._open_multi_select_dialog(
            self.root, title, activity_items, list(current_ids or []), on_save,
            group_of=activity_group_of, allow_duplicates=True,
            system_actions=system_actions, extra_labels=sys_extra_labels)

    def _open_post_run_steps_editor(self, emulator_index, accounts, activity_items, activity_group_of, on_saved=None):
        """Soạn Hành Động Cuối GỘP THEO GIẢ LẬP (self._post_run_steps_by_emulator) -
        wrapper mỏng quanh _open_steps_editor()."""
        mapping = getattr(self, "_post_run_steps_by_emulator", None)
        if mapping is None:
            mapping = {}
            self._post_run_steps_by_emulator = mapping
        current = mapping.get(str(emulator_index)) or []

        def _on_save(chosen_ids):
            mapping[str(emulator_index)] = list(chosen_ids)
            self._save_settings()
            if on_saved:
                on_saved()

        self._open_steps_editor("Chọn Hành Động Cuối (Hoạt Động + Hành động hệ thống)", current, accounts,
                                 activity_items, activity_group_of, _on_save)

    def _exec_entry(self, engine, emulator, entry, preset_vars, tracked, context_label=None):
        task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
        name = entry.get("ten_hien_thi", task_id)
        file_path = entry.get("file_json")

        # `context_label` (tuỳ chọn): mô tả NGẮN gọn đang chạy trong bối
        # cảnh nào - vd '⏰ Đá Gà - Tài khoản thứ 5/8 - Hân' hoặc '👥 Xoay
        # Vòng - Tài khoản thứ 2/3 - Clone01' - được ghép sẵn vào các dòng
        # Nhật Ký của tác vụ này (bên dưới) để lúc xem Nhật Ký thời gian
        # thực BIẾT NGAY đang chạy tác vụ nào, của lịch hẹn giờ/xoay vòng
        # nào, và đang ở tài khoản thứ mấy - trùng tên - trong danh sách.
        # Chỉ áp dụng cho các nơi CÓ xoay vòng tài khoản (xem nơi gọi ở
        # dashboard_accounts.py/dashboard_schedule.py); các nơi khác gọi
        # _exec_entry() như cũ (không truyền context_label) thì log vẫn
        # như trước, không đổi gì.
        prefix = f"[{context_label}] " if context_label else ""

        # Bất kỳ Hoạt Động nào chạy = bước liền trước KHÔNG còn là "Đăng Xuất"
        # hệ thống (xem _exec_system_action: Đăng Nhập ngay sau Đăng Xuất thì
        # không chạy auto_login xen giữa).
        getattr(self, "_prev_sys_loai", {}).pop(emulator.index, None)

        # Dòng trạng thái CỐ ĐỊNH (self.lbl_current_task, KHÔNG cuộn mất
        # như log thường) - hiển thị NGAY đang chạy tác vụ nào, TRÊN GIẢ
        # LẬP nào, kèm bối cảnh lịch hẹn giờ/xoay vòng + tài khoản thứ mấy
        # nếu có. LUÔN có tên giả lập trong status_text (kể cả khi có
        # context_label) - trước đây nhánh có context_label KHÔNG kèm tên
        # giả lập, nên khi 2+ giả lập cùng chạy song song 1 lịch/xoay vòng,
        # dòng trạng thái gộp (xem _set_current_task_status) hiện 2 đoạn y
        # hệt nhau về nội dung, KHÔNG cách nào biết đoạn nào của giả lập
        # nào - phải tự đoán qua Nhật Ký cuộn liên tục.
        status_text = f"[{emulator.name}] {context_label} → {name}" if context_label \
            else f"{name} (trên {emulator.name})"
        self._set_current_task_status(emulator.name, status_text)

        # THÊM ĐOẠN NÀY VÀO ĐẦU HÀM _exec_entry:
        if not file_path or not os.path.exists(file_path):
            if file_path:
                base_name = os.path.basename(file_path)
                local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks", base_name)
                if os.path.exists(local_path):
                    file_path = local_path

        if tracked:
            self._bump_task_progress(task_id, "running")
        self._log("info", f"{prefix}── Bắt đầu tác vụ: {name} ──", emulator_name=emulator.name)

        if not file_path or not os.path.exists(file_path):
            self._log("error", f"{prefix}Không tìm thấy file kịch bản: {file_path}", emulator_name=emulator.name)
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

            if self._is_stop_requested(emulator.index):
                if tracked:
                    self._bump_task_progress(task_id, "stopped")
                self._log("warn", f"{prefix}Tác vụ '{name}' bị dừng giữa chừng (thủ công).", emulator_name=emulator.name)
                return False

            if tracked:
                self._bump_task_progress(task_id, "done")
                run_state.mark_done(task_id, emulator.name)
            self._log("success", f"{prefix}Hoàn thành tác vụ: {name}", emulator_name=emulator.name)
            return True

        except (BreakGroupSignal, ContinueGroupSignal):
            if tracked:
                self._bump_task_progress(task_id, "done")
                run_state.mark_done(task_id, emulator.name)
            self._log("warn", f"{prefix}Tác vụ '{name}' kết thúc sớm do break/continue nằm ngoài GROUP.",
                       emulator_name=emulator.name)
            return True
        except Exception as e:
            if tracked:
                self._bump_task_progress(task_id, "error")
            self._log("error", f"{prefix}Lỗi khi chạy '{name}': {e}", emulator_name=emulator.name)
            return False

    def _on_emulator_thread_done(self, emulator_index=None):
        if emulator_index is not None:
            self._busy_emulator_indexes.discard(emulator_index)
            # Dọn cờ dừng/tạm dừng RIÊNG của đúng giả lập này - luồng đã kết
            # thúc nên cờ cũ không còn ý nghĩa gì, để lại có thể khiến lượt
            # chạy KẾ TIẾP trên cùng giả lập này bị coi là "đã bị dừng" ngay
            # từ đầu một cách oan uổng.
            self.stop_flags.pop(emulator_index, None)
            self.pause_flags.pop(emulator_index, None)
            self._clear_current_task_for_index(emulator_index)
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


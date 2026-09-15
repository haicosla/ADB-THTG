"""
dashboard_schedule.py — Hẹn Giờ Tự Động: kiểm tra định kỳ lịch nào tới giờ chạy, xếp hàng chờ theo giả lập, thực thi 1 lượt lịch (đăng xuất/đăng nhập tài khoản xoay vòng + các Hoạt Động đã chọn), và cửa sổ quản lý lịch '⏰ Hẹn Giờ' (thêm/sửa/xoá lịch, gán Giả Lập ↔ Tài Khoản).

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
from datetime import datetime

from adb_helper import ADBHelper
from logic_engine import LogicEngine
from window_finder import WindowFinder
import task_registry
import account_manager
import scheduler
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, FlowBar, _bind_esc_close


class ScheduleMixin:
    # ================= HẸN GIỜ TỰ ĐỘNG =================
    def _check_schedules(self):
        """Chạy mỗi 20s (xem __init__) - kiểm tra từng lịch trong
        schedules.json xem đã đến giờ chưa (scheduler.is_due), nếu có thì
        trigger ngay (scheduler.mark_triggered + lưu file TRƯỚC khi chạy
        xong, xem lý do trong scheduler.py)."""
        try:
            now = datetime.now()
            due_list = [e for e in self.schedules if scheduler.is_due(e, now)]
            if due_list:
                for entry in due_list:
                    scheduler.mark_triggered(entry, now)
                scheduler.save_schedules(self.schedules)
                for entry in due_list:
                    self._trigger_schedule(entry)

            # CẢNH BÁO 1 LẦN/NGÀY cho các lịch đang TẮT ('Bật' chưa tick)
            # nhưng lẽ ra đã tới giờ chạy - nếu không có dòng này, người
            # dùng quên tick 'Bật' sẽ thấy lịch "im lặng không chạy" mà
            # KHÔNG có bất kỳ log nào giải thích vì sao (is_due trả về
            # False ngay từ bước kiểm tra 'bat', không rớt vào due_list).
            today = now.strftime("%Y-%m-%d")
            for entry in self.schedules:
                if entry.get("bat", True):
                    continue
                if not scheduler.would_be_due_if_enabled(entry, now):
                    continue
                if self._disabled_schedule_notified.get(entry.get("id")) == today:
                    continue
                self._disabled_schedule_notified[entry.get("id")] = today
                self._log("warn", f"⏰ Lịch '{entry.get('ten', '?')}' đã tới giờ hẹn nhưng đang ở trạng thái "
                                   f"TẮT ('Bật' chưa tick) nên KHÔNG tự chạy - vào '⏰ Hẹn Giờ' tick 'Bật' "
                                   f"rồi bấm 💾 nếu muốn lịch này tự chạy.")
        except Exception as e:
            self._log("error", f"Lỗi kiểm tra lịch hẹn giờ: {e}")
        finally:
            self.root.after(20000, self._check_schedules)

    def _trigger_schedule(self, entry):
        """Tới giờ 1 lịch - dựng danh sách Hoạt Động tương ứng, rồi CHẠY theo
        đúng bảng gán THỦ CÔNG 'gan_may_tk' đã soạn sẵn qua '🔗 Gán GL/TK':
        {str(emulator_index): [tai_khoan_id, ...]}. Mỗi giả lập có mặt trong
        bảng gán luôn được chạy trên 1 luồng riêng (giống cơ chế đa luồng của
        nút CHẠY thủ công):
          - Danh sách tài khoản KHÔNG rỗng: xoay vòng Đăng Xuất - Đăng Nhập -
            chạy Hoạt Động cho từng tài khoản, y hệt '👥 Xoay Vòng Tài Khoản'.
          - Danh sách tài khoản RỖNG: chạy thẳng các Hoạt Động 1 lần trên
            giả lập đó, KHÔNG đăng xuất/đăng nhập đổi tài khoản gì cả."""
        name = entry.get("ten", "Lịch không tên")
        hoat_dong_ids = set(entry.get("hoat_dong_ids", []))
        gan_may_tk = entry.get("gan_may_tk") or {}

        activities = [
            t for t in self.tasks
            if (t.get("id") or task_registry.make_task_id(t.get("file_json", ""))) in hoat_dong_ids
        ]
        if not activities:
            self._log("error", f"⏰ Lịch '{name}' đến giờ chạy nhưng không tìm thấy Hoạt Động nào khớp "
                                f"(có thể đã bị xoá khỏi Danh Mục) - bỏ qua lượt này.")
            return

        if not gan_may_tk:
            self._log("error", f"⏰ Lịch '{name}' đến giờ chạy nhưng chưa gán Giả Lập nào - bấm '🔗 Gán GL/TK' "
                                f"rồi lưu lại - bỏ qua lượt này.")
            return

        accounts_by_id = {a.get("id"): a for a in account_manager.load_accounts()}
        n_tk_dong = sum(1 for v in gan_may_tk.values() if v)
        self._log("info", f"⏰ Lịch '{name}' đến giờ chạy - {len(activities)} hoạt động trên "
                           f"{len(gan_may_tk)} giả lập ({n_tk_dong} giả lập có xoay vòng tài khoản).")

        for idx_str, tk_ids in gan_may_tk.items():
            try:
                idx = int(idx_str)
            except (TypeError, ValueError):
                continue
            accs = [accounts_by_id[tid] for tid in tk_ids if tid in accounts_by_id and accounts_by_id[tid].get("bat", True)]

            if idx in self._busy_emulator_indexes:
                # Giả lập đang bận (đang chạy tay HOẶC 1 lịch khác/lượt
                # trước của CHÍNH lịch này còn dở dang) -> XẾP HÀNG CHỜ thay
                # vì bỏ qua hẳn - sẽ tự chạy ngay khi giả lập rảnh (xem
                # _after_emulator_freed), không cần người dùng làm gì thêm.
                # Dùng chung self._emulator_job_queue với lượt CHẠY tay/Chạy
                # Ngay (xem _queue_job) - "▶ Chạy Ngay" của 1 lịch cũng đi
                # qua đúng đường này vì cũng gọi _trigger_schedule().
                self._emulator_job_queue.setdefault(idx, []).append(
                    {"kind": "schedule", "name": name, "accs": accs, "activities": activities}
                )
                queue_len = len(self._emulator_job_queue[idx])
                self._log("warn", f"⏰ Lịch '{name}': giả lập #{idx} đang bận (đang chạy tay hoặc 1 lịch khác) - "
                                   f"đã XẾP HÀNG CHỜ (vị trí {queue_len}), sẽ tự chạy tiếp ngay khi giả lập rảnh, "
                                   f"KHÔNG bị bỏ qua.")
                continue

            self._start_schedule_worker(name, idx, accs, activities)

    def _start_schedule_worker(self, name, idx, accs, activities):
        """Đánh dấu giả lập #idx đang bận rồi chạy 1 luồng riêng cho lượt
        lịch này. Tách thành hàm riêng để dùng chung cho cả lượt chạy NGAY
        (khi đến giờ, giả lập đang rảnh) lẫn lượt LẤY TỪ HÀNG CHỜ ra chạy
        (khi giả lập vừa rảnh xong việc trước đó, xem _after_emulator_freed)."""
        self._busy_emulator_indexes.add(idx)
        self._active_schedule_count += 1
        self._refresh_run_control_buttons()
        self._update_status_label()
        threading.Thread(target=self._worker_run_schedule, args=(name, idx, accs, activities), daemon=True).start()

    def _worker_run_schedule(self, schedule_name, emulator_index, accounts, activities):
        """Chạy 1 lượt lịch hẹn giờ trên 1 giả lập (emulator_index): tự bật
        giả lập nếu đang tắt, rồi:
          - Nếu `accounts` KHÔNG rỗng: lần lượt từng tài khoản - Đăng Xuất
            (nếu có) -> Đăng Nhập -> chạy đúng các Hoạt Động của lịch này -
            giống hệt '👥 Xoay Vòng Tài Khoản' nhưng do THỜI GIAN kích hoạt
            thay vì người dùng bấm CHẠY.
          - Nếu `accounts` RỖNG (lịch không chọn Tài khoản, chỉ chọn thẳng
            Giả lập): chạy các Hoạt Động NGAY 1 lần trên giả lập này, KHÔNG
            đăng xuất/đăng nhập đổi tài khoản gì cả."""
        tag = f"⏰ {schedule_name}"
        try:
            ready_info, _auto_started = self.emu_manager.ensure_running(
                emulator_index, timeout=120,
                on_log=lambda lvl, msg: self._log(lvl, f"[{tag}] {msg}")
            )
            if not ready_info:
                self._log("error", f"[{tag}] Không bật được giả lập #{emulator_index} - bỏ qua lượt này.")
                return
            emulator = ready_info

            if not self.emu_manager.ensure_adb_connected(emulator):
                self._log("error", f"[{tag}] Không thấy giả lập '{emulator.name}' trong 'adb devices' sau khi "
                                    f"khởi động - bỏ qua lượt này.", emulator_name=emulator.name)
                return

            adb = ADBHelper()
            adb.device_id = emulator.adb_serial
            adb.update_resolution()

            wf = WindowFinder(adb)
            attached = wf.attach_hwnd(emulator.hwnd) if emulator.hwnd else False
            if not attached:
                wf.find_ld_windows()
            if wf.ensure_window_visible():
                self._log("warn", f"[{tag}] Cửa sổ LDPlayer '{emulator.name}' đang bị THU NHỎ - đã tự khôi phục lại.",
                           emulator_name=emulator.name)
                time.sleep(0.5)

            engine = LogicEngine(
                adb,
                stop_checker=self._make_stop_checker(),
                popup_notifier=lambda msg, dur=0, _wf=wf: self._show_ingame_popup(_wf, msg, dur),
                logger=lambda lvl, msg, _e=emulator: self._log(lvl, f"[{tag}] {msg}", emulator_name=_e.name)
            )

            # KHÔNG có tài khoản nào (lịch chọn thẳng Giả lập, không chọn
            # Tài khoản) -> chạy các Hoạt Động NGAY trên giả lập này, dùng
            # đúng phiên đang đăng nhập sẵn, KHÔNG đăng xuất/đăng nhập đổi
            # tài khoản gì cả.
            if not accounts:
                self._log("info", f"[{tag}] Chạy thẳng trên '{emulator.name}' (không chọn Tài khoản - "
                                   f"không đổi tài khoản).", emulator_name=emulator.name)
                for act_entry in activities:
                    if self.stop_flag:
                        break
                    self._exec_entry(engine, emulator, act_entry, preset_vars=None, tracked=False)
                if not self.stop_flag:
                    self._log("success", f"[{tag}] Hoàn thành trên '{emulator.name}'.", emulator_name=emulator.name)
                self._apply_post_run_options(engine, emulator)
                return

            login_entry = task_registry.find_task(self.tasks, "account_login")
            logout_entry = task_registry.find_task(self.tasks, "account_logout")
            if not login_entry:
                self._log("warn", f"[{tag}] Chưa có Hoạt Động 'account_login' - sẽ chạy thẳng các Hoạt Động đã "
                                   f"hẹn mà KHÔNG đăng nhập lại đúng tài khoản (dùng đúng phiên đang đăng nhập sẵn "
                                   f"trên giả lập).", emulator_name=emulator.name)

            for acc in accounts:
                if self.stop_flag:
                    break
                ten = acc.get("ten_hien_thi") or acc.get("username") or acc.get("id")
                self._log("info", f"[{tag}] ═══ Tài khoản: {ten} trên '{emulator.name}' ═══", emulator_name=emulator.name)

                preset_vars = None
                ok_login = True
                if login_entry:
                    if logout_entry:
                        self._exec_entry(engine, emulator, logout_entry, preset_vars=None, tracked=False)
                        if self.stop_flag:
                            break
                    preset_vars = {"tk_user": acc.get("username", ""), "tk_pass": acc.get("password", "")}
                    ok_login = self._exec_entry(engine, emulator, login_entry, preset_vars=preset_vars, tracked=False)

                if not ok_login:
                    self._log("error", f"[{tag}] Đăng nhập thất bại cho '{ten}' - bỏ qua tài khoản này.",
                               emulator_name=emulator.name)
                    continue

                for act_entry in activities:
                    if self.stop_flag:
                        break
                    self._exec_entry(engine, emulator, act_entry, preset_vars=preset_vars, tracked=False)

                if not self.stop_flag:
                    account_manager.mark_run(account_manager.load_accounts(), acc.get("id"))
                    self._log("success", f"[{tag}] Hoàn thành tài khoản '{ten}'.", emulator_name=emulator.name)

            self._apply_post_run_options(engine, emulator)

        except Exception as e:
            self._log("error", f"[{tag}] Lỗi khi chạy trên giả lập #{emulator_index}: {e}")
        finally:
            self.root.after(0, lambda: self._on_schedule_thread_done(emulator_index))

    def _on_schedule_thread_done(self, emulator_index):
        self._busy_emulator_indexes.discard(emulator_index)
        self._active_schedule_count = max(0, self._active_schedule_count - 1)
        self._refresh_run_control_buttons()
        self._update_status_label()
        self._after_emulator_freed(emulator_index)

    def _after_emulator_freed(self, emulator_index):
        """Gọi NGAY SAU KHI 1 giả lập vừa hết bận (chạy tay xong HOẶC 1 lượt
        lịch hẹn giờ xong) - nếu có job nào đang XẾP HÀNG CHỜ cho đúng giả
        lập đó (xem _trigger_schedule), lấy job ĐẦU HÀNG ra chạy tiếp ngay,
        không cần đợi tới lần _check_schedules() kế tiếp (tối đa 20s) mới
        phát hiện lại - job trễ hơn được xử lý sớm nhất có thể."""
        queue = self._emulator_job_queue.get(emulator_index)
        if not queue:
            return
        job = queue.pop(0)
        if not queue:
            self._emulator_job_queue.pop(emulator_index, None)
        remain_note = f" (còn {len(queue)} lượt khác đang chờ giả lập này)." if queue else "."

        kind = job.get("kind")
        if kind == "schedule":
            self._log("info", f"⏰ Giả lập #{emulator_index} vừa rảnh - chạy tiếp lịch đang XẾP HÀNG CHỜ: "
                               f"'{job['name']}'" + remain_note)
            self._start_schedule_worker(job["name"], emulator_index, job["accs"], job["activities"])
            return

        # "manual_run" / "manual_accounts" - lượt CHẠY tay/Chạy Ngay/xoay
        # vòng đang xếp hàng chờ giả lập này. Lấy lại thông tin giả lập MỚI
        # NHẤT qua emu_manager (hwnd/serial có thể đổi nếu giả lập vừa được
        # khởi động lại) thay vì dùng lại info cũ có thể đã lỗi thời.
        emulator = self.emu_manager.find_by_index(emulator_index)
        if not emulator:
            self._log("error", f"Không tìm thấy thông tin giả lập #{emulator_index} để chạy lượt đang XẾP HÀNG "
                                f"CHỜ - bỏ qua lượt này (bấm 'Quét Giả Lập' rồi tự chạy lại nếu cần).")
            return

        if kind == "manual_run":
            self._log("info", f"Giả lập '{emulator.name}' vừa rảnh - chạy tiếp lượt CHẠY đang XẾP HÀNG CHỜ"
                               f" ({len(job['selected'])} tác vụ)." + remain_note, emulator_name=emulator.name)
            self._run_queued_manual_job(job, emulator)
        elif kind == "manual_accounts":
            self._log("info", f"Giả lập '{emulator.name}' vừa rảnh - chạy tiếp lượt XOAY VÒNG TÀI KHOẢN đang "
                               f"XẾP HÀNG CHỜ ({len(job['selected'])} tác vụ)." + remain_note,
                       emulator_name=emulator.name)
            self._run_queued_manual_accounts_job(job, emulator)

    def _begin_queue_replay_session(self):
        """Chuẩn bị trạng thái phiên chạy (is_running/pause/nút bấm) khi 1
        job đang XẾP HÀNG CHỜ được lấy ra chạy - dùng chung cho cả
        'manual_run' lẫn 'manual_accounts'. KHÔNG reset self.active_threads
        (dùng += 1 ở nơi gọi) vì có thể đang có phiên khác chạy song song
        trên các giả lập rảnh khác - reset về 1 sẽ làm mất dấu các luồng đó."""
        if not self.is_running:
            self.is_running = True
            self.stop_flag = False
            self.pause_flag = False
            self.btn_pause.set_text("⏸ Tạm Dừng")
            self.btn_run.set_state("disabled")

    def _run_queued_manual_job(self, job, emulator):
        """Chạy 1 job 'manual_run' (CHẠY tay thường, có thể kèm Tự Login)
        vừa được lấy ra khỏi hàng chờ vì giả lập vừa rảnh."""
        selected = job["selected"]
        login_entry = job.get("login_entry")
        self._begin_queue_replay_session()
        self.active_threads += 1
        for entry in selected:
            task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
            prog = self.task_progress.setdefault(
                task_id, {"total": 0, "done": 0, "error": 0, "running": 0, "stopped": 0})
            prog["total"] += 1
        self._refresh_run_control_buttons()
        self._update_status_label()
        self._busy_emulator_indexes.add(emulator.index)
        threading.Thread(target=self._worker_run_emulator, args=(emulator, selected, login_entry), daemon=True).start()

    def _run_queued_manual_accounts_job(self, job, emulator):
        """Chạy 1 job 'manual_accounts' (CHẠY Xoay Vòng Tài Khoản) vừa được
        lấy ra khỏi hàng chờ vì giả lập vừa rảnh."""
        selected = job["selected"]
        account_ids = job.get("account_ids") or []
        self._begin_queue_replay_session()
        self.active_threads += 1
        for entry in selected:
            task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
            prog = self.task_progress.setdefault(
                task_id, {"total": 0, "done": 0, "error": 0, "running": 0, "stopped": 0})
            prog["total"] += 1
        self._refresh_run_control_buttons()
        self._update_status_label()
        self._busy_emulator_indexes.add(emulator.index)
        threading.Thread(target=self._worker_run_emulator_with_accounts,
                          args=(emulator, selected, account_ids), daemon=True).start()

    def _migrate_schedules_gan_may_tk(self, entries):
        """Chuyển các lịch ĐỊNH DẠNG CŨ (2 danh sách tách rời 'tai_khoan_ids'
        + 'may_ids', tài khoản tự "nhớ" 1 giả lập cố định qua
        account_manager.emulator_index) sang định dạng MỚI 'gan_may_tk':
        dict {str(emulator_index): [tai_khoan_id, ...]} - vì bản này bỏ hẳn
        việc gán tài khoản cố định theo giả lập (xem account_manager.py),
        người dùng giờ tự chọn Giả Lập <-> Tài Khoản NGAY khi soạn lịch qua
        nút '🔗 Gán GL/TK' (xem _open_gan_may_tk_dialog).

        CỐ GẮNG migrate không mất dữ liệu: nếu accounts.json cũ VẪN CÒN field
        "emulator_index" (vd người dùng chưa mở lại '👥 Quản Lý Tài Khoản' để
        lưu đè theo định dạng mới), dùng field đó để nhóm tài khoản vào đúng
        giả lập cũ. Tài khoản không xác định được giả lập cũ (hoặc tài khoản
        cũ đã bị lưu đè mất field) được gán tạm vào giả lập ĐẦU TIÊN trong
        'may_ids' cũ của lịch đó (nếu có) - nếu vẫn không có gì để suy luận,
        lịch đó sẽ có 'gan_may_tk' rỗng và người dùng cần vào '⏰ Hẹn Giờ' bấm
        '🔗 Gán GL/TK' để gán lại thủ công (được log rõ khi lịch đó tới giờ
        chạy nhưng chưa gán gì, xem _trigger_schedule)."""
        accounts_by_id = {a.get("id"): a for a in self.accounts}
        changed = False
        for entry in entries:
            if "gan_may_tk" in entry:
                continue
            changed = True
            tai_khoan_ids = entry.pop("tai_khoan_ids", None) or []
            may_ids = entry.pop("may_ids", None) or []
            gan = {}
            leftover = []
            for tk_id in tai_khoan_ids:
                acc = accounts_by_id.get(tk_id)
                idx = acc.get("emulator_index") if acc else None
                if idx is not None:
                    gan.setdefault(str(idx), []).append(tk_id)
                else:
                    leftover.append(tk_id)
            if leftover:
                target = str(may_ids[0]) if may_ids else None
                if target is not None:
                    gan.setdefault(target, []).extend(leftover)
            for idx in may_ids:
                gan.setdefault(str(idx), gan.get(str(idx), []))
            entry["gan_may_tk"] = gan
        if changed:
            scheduler.save_schedules(entries)
        return entries

    def _open_gan_may_tk_dialog(self, parent, title, emulator_items, account_items, account_group_of,
                                 current_assignment, on_save, allow_toggle_emulator=True, intro_text=""):
        """Popup GÁN THỦ CÔNG Giả Lập <-> Tài Khoản cho 1 lượt chạy/1 lịch hẹn
        giờ - THAY THẾ cho việc tài khoản tự "nhớ" 1 giả lập cố định (đã bỏ ở
        bản này). `emulator_items`: list (emulator_index, nhãn). `current_assignment`:
        dict {emulator_index: [tai_khoan_id, ...]} - CHỈ các giả lập có mặt
        trong dict này (khi `allow_toggle_emulator=True`) mới được coi là
        "áp dụng"; danh sách tài khoản RỖNG cho 1 giả lập nghĩa là "chạy
        thẳng trên giả lập đó, không đổi tài khoản" (vẫn hợp lệ). Khi
        `allow_toggle_emulator=False` (dùng cho nút CHẠY thủ công, nơi tập
        giả lập đã CỐ ĐỊNH sẵn theo ô tick ở màn hình chính), mọi giả lập
        trong `emulator_items` LUÔN được áp dụng, chỉ cần chọn tài khoản cho
        từng cái. `on_save(dict)` được gọi khi bấm Lưu."""
        win = tk.Toplevel(parent)
        win.title(title)
        win.configure(bg=COL_PANEL)
        win.geometry("640x560")
        win.minsize(360, 320)
        win.transient(parent)
        win.grab_set()
        win.focus_set()
        _bind_esc_close(win)

        tk.Label(win, text=title, bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        if intro_text:
            tk.Label(win, text=intro_text, bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8),
                     wraplength=590, justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        # ----- Hàng nút Lưu - PACK TRƯỚC vùng cuộn (side='bottom') để LUÔN
        # CHIẾM SẴN chỗ, không bị khuất mất trên cửa sổ nhỏ (xem giải thích
        # trong _open_multi_select_dialog). Nội dung bên trong (nhãn gợi ý +
        # nút Lưu) được thêm vào SAU, khi đã có đủ dữ liệu row_state. -----
        btn_bar = FlowBar(win, bg=COL_PANEL)
        btn_bar.pack(side="bottom", fill="x", padx=14, pady=10)

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 8))

        if not emulator_items:
            tk.Label(inner, text="(Không có giả lập nào)", bg=COL_PANEL, fg=COL_TEXT_MUTED).pack(anchor="w", pady=10)

        row_state = {}  # emulator_index -> {"applied_var": BooleanVar, "accounts": [ids], "btn": RoundedButton}

        for idx, label in emulator_items:
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=2, padx=2)

            applied_default = idx in current_assignment
            applied_var = tk.BooleanVar(value=applied_default if allow_toggle_emulator else True)
            if allow_toggle_emulator:
                DarkCheck(row, "", applied_var, bg=COL_PANEL_ALT, box_size=14).pack(side="left", padx=(6, 2), pady=6)

            tk.Label(row, text=label, bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 9),
                     anchor="w", width=26).pack(side="left", padx=4, pady=6)

            chosen_accounts = list(current_assignment.get(idx, []))
            btn = RoundedButton(row, f"👤 Chọn TK ({len(chosen_accounts)})", bg=COL_PURPLE,
                                 container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=8, pady=3)
            btn.pack(side="right", padx=6, pady=4)

            def _pick(idx=idx, btn=btn, applied_var=applied_var, label=label):
                def _on_save(chosen):
                    row_state[idx]["accounts"] = list(chosen)
                    btn.set_text(f"👤 Chọn TK ({len(chosen)})")
                    if chosen and allow_toggle_emulator:
                        applied_var.set(True)
                self._open_multi_select_dialog(
                    win, f"Chọn Tài Khoản xoay vòng trên {label}",
                    account_items, set(row_state[idx]["accounts"]), _on_save, group_of=account_group_of)
            btn.command = _pick

            row_state[idx] = {"applied_var": applied_var, "accounts": chosen_accounts, "btn": btn}

        def _save():
            result = {}
            for idx, st in row_state.items():
                if st["applied_var"].get():
                    result[idx] = list(st["accounts"])
            on_save(result)
            win.destroy()

        btn_bar.add(tk.Label(btn_bar, text="💡 Trống Tài khoản = chạy thẳng, không đổi tài khoản.",
                              bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "italic")))
        btn_bar.add(RoundedButton(btn_bar, "💾 Lưu", command=_save, bg=COL_GREEN, container_bg=COL_PANEL,
                                   font=("Segoe UI", 9, "bold"), padx=12, pady=6))

    def _open_schedule_manager(self):
        self.accounts = account_manager.load_accounts()
        self.schedules = self._migrate_schedules_gan_may_tk(scheduler.load_schedules())
        configured_emus = self.emu_manager.list_configured()

        win = tk.Toplevel(self.root)
        win.title("Hẹn Giờ Tự Động")
        win.configure(bg=COL_PANEL)
        win.geometry("1150x620")
        win.minsize(760, 480)
        _bind_esc_close(win)

        tk.Label(win, text="⏰ Lịch Chạy Tự Động", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(
            win,
            text="Mỗi lịch: chọn Hoạt Động áp dụng, đặt Giờ hẹn (mốc chạy lần đầu) và Lặp lại (hh:mm) - muốn "
                 "hằng ngày thì để 24:00, muốn mỗi 4 tiếng thì để 04:00. Rồi bấm '🔗 Gán GL/TK' để chỉ định THỦ "
                 "CÔNG: giả lập nào chạy, và trên mỗi giả lập đó chọn (các) Tài khoản để xoay vòng (Đăng Xuất - "
                 "Đăng Nhập - chạy Hoạt Động) - để trống Tài khoản của 1 giả lập nghĩa là chạy thẳng Hoạt Động "
                 "trên giả lập đó, KHÔNG đổi tài khoản (dùng đúng phiên đang đăng nhập sẵn). Tự BẬT giả lập nếu "
                 "đang tắt. Có thể bấm '▶ Chạy Ngay' để chạy thử ngay lập tức mà không cần chờ tới giờ. Dashboard "
                 "cần MỞ SẴN (chạy nền) để lịch tự kích hoạt - không cần tick chọn thủ công trong danh sách tác "
                 "vụ. Nhớ bấm 💾 ở từng dòng sau khi sửa để lưu lại.",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=1110, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        if not self.tasks:
            tk.Label(win, text="⚠ Chưa có Hoạt Động nào trong Danh Mục - hãy Tạo & Đăng Ký Hoạt Động trước.",
                     bg=COL_PANEL, fg=COL_ORANGE, wraplength=1110, justify="left").pack(anchor="w", padx=14, pady=(0, 4))
        if not self.accounts:
            tk.Label(win, text="⚠ Chưa có Tài Khoản nào - hãy thêm ở '👥 Quản Lý Tài Khoản' trước nếu muốn xoay "
                                "vòng tài khoản (không bắt buộc - có thể để trống Tài khoản của 1 giả lập để chạy "
                                "thẳng).",
                     bg=COL_PANEL, fg=COL_ORANGE, wraplength=1110, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        if not configured_emus:
            tk.Label(win, text="⚠ Không tìm thấy giả lập nào (kiểm tra đường dẫn ldconsole.exe) - chưa thể chọn "
                                "Giả lập cho lịch.",
                     bg=COL_PANEL, fg=COL_ORANGE, wraplength=1110, justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        header = tk.Frame(win, bg=COL_HEADER)
        header.pack(fill="x", padx=10)
        for text, w in [("Bật", 4), ("Tên lịch", 16), ("Giờ hẹn (hh:mm)", 13), ("Lặp lại (hh:mm)", 12)]:
            tk.Label(header, text=text, bg=COL_HEADER, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"),
                     width=w, anchor="w").pack(side="left", padx=2, pady=6)
        tk.Label(header, text="Hoạt Động chọn ở dòng dưới, Giả Lập/Tài khoản gán qua nút '🔗 Gán GL/TK' ↓", bg=COL_HEADER,
                 fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"), anchor="w").pack(side="left", padx=8, pady=6)
        tk.Label(
            win,
            text="💡 Giờ hẹn = mốc chạy LẦN ĐẦU, theo đúng giờ này VĨNH VIỄN (kể cả sau khi bấm 'Chạy Ngay' để "
                 "test). Lặp lại (hh:mm) = cách bao lâu chạy lại 1 lần - muốn chạy hằng ngày thì để 24:00, "
                 "muốn mỗi 4 tiếng thì để 04:00, muốn mỗi 30 phút (để test nhanh) thì để 00:30.",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=1040, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 6))

        # ----- Thanh nút dưới cùng (➕ Thêm Lịch Mới) - PACK TRƯỚC vùng cuộn
        # (side='bottom') để LUÔN CHIẾM SẴN chỗ, không bị khuất trên cửa sổ
        # nhỏ (xem giải thích trong _open_multi_select_dialog). -----
        bottom_bar = FlowBar(win, bg=COL_PANEL)
        bottom_bar.pack(side="bottom", fill="x", padx=14, pady=10)

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 6))

        activity_items = [
            (t.get("id") or task_registry.make_task_id(t.get("file_json", "")), t.get("ten_hien_thi", "?"))
            for t in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0)))
        ]
        # Nhóm tác vụ = đúng Mục đã đặt khi Đăng Ký Tác Vụ (vd Mục "A" gồm
        # các Hoạt Động "b","c","d") - dùng lại làm "group_of" để có nút chọn
        # nhanh theo Mục ngay trong popup "🎯 HĐ", đỡ phải tick tay từng cái.
        activity_group_of = {
            (t.get("id") or task_registry.make_task_id(t.get("file_json", ""))): (t.get("muc") or "")
            for t in self.tasks
        }
        account_items = [
            (a.get("id"), a.get("ten_hien_thi") or a.get("username") or a.get("id"))
            for a in self.accounts
        ]
        account_group_of = {a.get("id"): (a.get("nhom") or "") for a in self.accounts}
        emulator_items = [
            (e.index, f"#{e.index} - {e.name}" + ("" if e.running else "  (đang tắt)"))
            for e in configured_emus
        ]

        def _add_row(entry):
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=3)

            # ----- DÒNG 1: Bật / Tên / Giờ hẹn / Lặp lại / Chạy lần cuối -----
            line1 = tk.Frame(row, bg=COL_PANEL_ALT)
            line1.pack(fill="x")

            bat_var = tk.BooleanVar(value=bool(entry.get("bat", True)))
            DarkCheck(line1, "", bat_var, bg=COL_PANEL_ALT, box_size=14).pack(side="left", padx=(6, 2), pady=4)

            ten_var = tk.StringVar(value=entry.get("ten", ""))
            tk.Entry(line1, textvariable=ten_var, width=16, bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2, pady=4)

            gio_var = tk.StringVar(value=entry.get("gio_hen", "07:00"))
            tk.Entry(line1, textvariable=gio_var, width=10, bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2, pady=4)

            interval_var = tk.StringVar(value=scheduler.hours_to_hhmm(entry.get("interval_hours", 24)))
            tk.Entry(line1, textvariable=interval_var, width=8, bg=COL_PANEL, fg=COL_TEXT,
                     insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=2, pady=4)

            last_run_text = entry.get("lan_chay_luc") or "Chưa chạy lần nào"
            last_run_lbl = tk.Label(line1, text=f"Chạy cuối: {last_run_text}", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                                     font=("Segoe UI", 8), anchor="w")
            last_run_lbl.pack(side="left", padx=(10, 4), pady=4)

            # ----- DÒNG 2: chọn Hoạt Động / Tài khoản / Giả lập + hành động -----
            line2 = tk.Frame(row, bg=COL_PANEL_ALT)
            line2.pack(fill="x")

            chosen_activities = list(entry.get("hoat_dong_ids", []))
            # gan_may_tk: {str(emulator_index): [tai_khoan_id, ...]} - giả lập
            # nào KHÔNG có mặt trong dict này = KHÔNG áp dụng lịch. Danh sách
            # tài khoản rỗng cho 1 giả lập = chạy thẳng (không đổi tài khoản).
            gan_may_tk = {str(k): list(v) for k, v in (entry.get("gan_may_tk") or {}).items()}

            def _gan_count_text():
                n_may = len(gan_may_tk)
                n_tk = sum(1 for v in gan_may_tk.values() if v)
                return f"🔗 Gán GL/TK ({n_may} GL, {n_tk} xoay TK)"

            btn_act = RoundedButton(line2, f"🎯 HĐ ({len(chosen_activities)})", bg=COL_BLUE,
                                     container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=8, pady=3)
            btn_act.pack(side="left", padx=(6, 2), pady=(0, 6))

            btn_gan = RoundedButton(line2, _gan_count_text(), bg=COL_PURPLE,
                                     container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=8, pady=3)
            btn_gan.pack(side="left", padx=2, pady=(0, 6))

            mode_lbl = tk.Label(line2, text="", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "italic"))
            mode_lbl.pack(side="left", padx=(6, 2), pady=(0, 6))

            def _refresh_mode_label():
                if not gan_may_tk:
                    mode_lbl.config(text="→ (chưa gán Giả Lập nào)")
                elif any(gan_may_tk.values()):
                    mode_lbl.config(text="→ có xoay vòng tài khoản")
                else:
                    mode_lbl.config(text="→ chạy thẳng, không đổi tài khoản")
            _refresh_mode_label()

            def _pick_activities():
                def _on_save(chosen):
                    chosen_activities[:] = chosen
                    btn_act.set_text(f"🎯 HĐ ({len(chosen_activities)})")
                self._open_multi_select_dialog(win, "Chọn Hoạt Động cho lịch này",
                                                activity_items, set(chosen_activities), _on_save,
                                                group_of=activity_group_of)
            btn_act.command = _pick_activities

            def _pick_gan():
                # Chuyển key int cho dialog (emulator_items dùng index kiểu int).
                current = {int(k): v for k, v in gan_may_tk.items()}

                def _on_save(result):
                    gan_may_tk.clear()
                    gan_may_tk.update({str(k): v for k, v in result.items()})
                    btn_gan.set_text(_gan_count_text())
                    _refresh_mode_label()
                self._open_gan_may_tk_dialog(
                    win, f"Gán Giả Lập ↔ Tài Khoản cho lịch '{entry.get('ten', '')}'",
                    emulator_items, account_items, account_group_of, current, _on_save,
                    allow_toggle_emulator=True,
                    intro_text="Tick chọn (các) giả lập áp dụng cho lịch này, rồi bấm '👤 Chọn TK' của từng giả "
                               "lập để chọn tài khoản xoay vòng trên đúng giả lập đó (để trống = chạy thẳng, "
                               "không đổi tài khoản).")
            btn_gan.command = _pick_gan

            def _save_row(silent=False):
                entry["bat"] = bool(bat_var.get())
                entry["ten"] = ten_var.get().strip() or "Lịch không tên"
                gio_text = gio_var.get().strip() or "07:00"
                try:
                    hh, mm = [int(x) for x in gio_text.split(":")]
                    assert 0 <= hh <= 23 and 0 <= mm <= 59
                    entry["gio_hen"] = f"{hh:02d}:{mm:02d}"
                except Exception:
                    messagebox.showerror("Giờ hẹn không hợp lệ",
                                          f"'{gio_text}' không phải giờ hợp lệ. Nhập theo dạng HH:MM, "
                                          f"vd 07:00 hoặc 22:30.", parent=win)
                    return False
                try:
                    entry["interval_hours"] = scheduler.hhmm_to_hours(interval_var.get())
                except Exception:
                    messagebox.showerror("Giờ lặp lại không hợp lệ",
                                          f"'{interval_var.get()}' không đúng định dạng hh:mm. Nhập vd 24:00 "
                                          f"(hằng ngày), 04:00 (mỗi 4 tiếng), 00:30 (mỗi 30 phút để test).",
                                          parent=win)
                    return False
                entry["hoat_dong_ids"] = list(chosen_activities)
                entry["gan_may_tk"] = dict(gan_may_tk)
                self.schedules = scheduler.upsert_schedule(self.schedules, entry)
                scheduler.save_schedules(self.schedules)
                trang_thai = "🟢 ĐANG BẬT - sẽ tự chạy đúng giờ" if entry["bat"] else "🔴 ĐANG TẮT - sẽ KHÔNG tự chạy cho tới khi bạn tick lại 'Bật'"
                if not silent:
                    che_do = "có xoay vòng tài khoản" if any(gan_may_tk.values()) else "chạy thẳng giả lập"
                    self._log("success", f"Đã lưu lịch '{entry['ten']}' ({scheduler.describe(entry)}, "
                                          f"{len(chosen_activities)} hoạt động, {len(gan_may_tk)} giả lập, chế độ "
                                          f"{che_do}) - {trang_thai}.")
                    messagebox.showinfo("Đã lưu", f"Đã lưu lịch '{entry['ten']}'.\n\n{trang_thai}.", parent=win)
                return True

            def _delete_row():
                if not messagebox.askyesno("Xác nhận", f"Xoá lịch '{entry.get('ten', '')}' này?", parent=win):
                    return
                self.schedules = scheduler.remove_schedule(self.schedules, entry.get("id"))
                scheduler.save_schedules(self.schedules)
                row.destroy()
                self._log("warn", f"Đã xoá lịch '{entry.get('ten', '')}'.")

            def _run_now():
                if not _save_row(silent=True):
                    return
                if not entry.get("hoat_dong_ids"):
                    messagebox.showwarning("Thiếu Hoạt Động",
                                            "Lịch này chưa chọn Hoạt Động nào - bấm '🎯 HĐ' để chọn trước.",
                                            parent=win)
                    return
                if not entry.get("gan_may_tk"):
                    messagebox.showwarning("Chưa gán Giả Lập",
                                            "Lịch này chưa gán Giả Lập nào - bấm '🔗 Gán GL/TK' để chọn ít nhất 1 "
                                            "giả lập trước (có thể để trống Tài khoản của giả lập đó nếu chỉ "
                                            "muốn chạy thẳng, không đổi tài khoản).",
                                            parent=win)
                    return
                if not entry.get("bat", True):
                    # "Chạy Ngay" vẫn cho chạy thử dù lịch đang TẮT (không tick
                    # 'Bật') - nhưng phải cảnh báo rõ, nếu không người dùng dễ
                    # hiểu nhầm là lịch "vẫn hoạt động bình thường, tự chạy
                    # được" trong khi thực ra _check_schedules() sẽ bỏ qua nó
                    # hoàn toàn (không ghi log gì cả) cho tới khi tick lại Bật.
                    messagebox.showwarning(
                        "Lịch đang TẮT",
                        f"Lịch '{entry.get('ten', '')}' đang ở trạng thái TẮT (cột 'Bật' chưa tick) - "
                        f"nó sẽ KHÔNG tự chạy khi đến giờ hẹn. Lượt chạy thử này vẫn tiếp tục vì bạn bấm "
                        f"'Chạy Ngay' thủ công. Hãy tick 'Bật' rồi bấm 💾 nếu muốn lịch tự chạy sau này.",
                        parent=win)
                scheduler.mark_triggered(entry)
                scheduler.save_schedules(self.schedules)
                last_run_lbl.config(text=f"Chạy cuối: {entry.get('lan_chay_luc') or 'Chưa chạy lần nào'}")
                self._log("info", f"▶ Chạy ngay lịch '{entry.get('ten', '')}' theo yêu cầu thủ công.")
                self._trigger_schedule(entry)

            RoundedButton(line2, "▶ Chạy Ngay", command=_run_now, bg=COL_TEAL, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(side="right", padx=2, pady=(0, 6))
            RoundedButton(line2, "💾", command=_save_row, bg=COL_GREEN, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 9, "bold"), padx=8, pady=3).pack(side="right", padx=4, pady=(0, 6))
            RoundedButton(line2, "🗑", command=_delete_row, bg=COL_RED, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 9, "bold"), padx=8, pady=3).pack(side="right", padx=2, pady=(0, 6))

            sep = tk.Frame(row, bg=COL_HEADER, height=1)
            sep.pack(fill="x", pady=(2, 0))

        # Hiển thị theo THỨ TỰ THỜI GIAN CHẠY trong ngày (giờ hẹn sớm nhất
        # lên đầu) thay vì thứ tự thêm vào file - dễ nhìn tổng quan lịch
        # nào chạy trước/sau trong ngày. KHÔNG đổi thứ tự lưu trong
        # schedules.json, chỉ đổi thứ tự HIỂN THỊ ở đây.
        for entry in sorted(self.schedules, key=scheduler.sort_key):
            _add_row(entry)

        def _add_new():
            entry = {
                "id": scheduler.new_schedule_id(),
                "ten": "Lịch mới",
                "gio_hen": "07:00",
                "interval_hours": 24,
                "hoat_dong_ids": [],
                "gan_may_tk": {},
                "bat": True,
                "lan_chay_ngay": None,
                "lan_chay_luc": None,
            }
            _add_row(entry)

        bottom_bar.add(RoundedButton(bottom_bar, "➕ Thêm Lịch Mới", command=_add_new, bg=COL_ACCENT, fg="#241a00",
                                      container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))

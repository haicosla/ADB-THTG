"""
dashboard_emulators.py — Quét/hiển thị danh sách giả lập LDPlayer, chọn đường dẫn ldconsole.exe, bật/tắt giả lập theo tick chọn, và cửa sổ 'Bảng Giả Lập' (kèm nút 'Chụp Thử' để debug ảnh chụp màn hình của 1 giả lập).

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import os
import json
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
import cv2
import win32gui
import win32con
import window_geometry as wg

from adb_helper import ADBHelper
from emulator_manager import normalize_console_path
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, _bind_esc_close, ThemedToplevel


class EmulatorMixin:
    # ================= GIẢ LẬP =================
    def refresh_emulators(self):
        """Quét TOÀN BỘ giả lập đã cấu hình trong LDPlayer, KỂ CẢ những giả
        lập đang TẮT (dùng list_configured() thay vì refresh() vốn chỉ thấy
        giả lập đang chạy) - để người dùng vẫn tick chọn và bấm '🟢 Bật Đã
        Chọn' được ngay cả khi chưa mở sẵn giả lập nào."""
        self.emulators = self.emu_manager.list_configured()
        # emu_chip_frame giờ là FlowBar (tự xuống dòng, xem dashboard_ui.py)
        # - dùng .clear() thay vì tự lặp winfo_children() để destroy(), để
        # FlowBar dọn đúng cả danh sách nội bộ _widgets của nó (không thì
        # lần _reflow() kế tiếp vẫn cố định vị các widget đã bị destroy()).
        self.emu_chip_frame.clear()
        self.emu_vars = {}

        if not self.emulators:
            self.emu_chip_frame.add(tk.Label(
                self.emu_chip_frame,
                text="Không tìm thấy giả lập nào. Kiểm tra đường dẫn ldconsole.exe "
                     "(bấm '📁 Chọn ldconsole.exe') rồi bấm '🔄 Quét Giả Lập' lại.",
                bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9)))
            self._refresh_log_filter_options()
            return

        self.emu_chip_frame.add(DarkCheck(self.emu_chip_frame, "Tất cả giả lập", self.emu_all_var, bg=COL_PANEL,
                                           command=self._on_toggle_all_emulators))

        for e in self.emulators:
            # Mặc định KHÔNG tự tick giả lập đang TẮT dù "Tất cả giả lập"
            # đang bật, tránh bấm CHẠY xong ăn lỗi "không thấy trong adb
            # devices" ngay lập tức - người dùng có thể tự tick tay nếu
            # muốn (vd để dùng chung với '🟢 Bật Đã Chọn').
            default_checked = bool(self.emu_all_var.get() and e.running)
            var = tk.BooleanVar(value=default_checked)
            self.emu_vars[e.name] = var
            var.trace_add("write", lambda *_: self._sync_pin_checkbox())   # ô 📌 theo lựa chọn
            label = f"🟢 {e.name}" if e.running else f"⚪ {e.name} (đang tắt)"
            fg = COL_TEXT if e.running else COL_TEXT_MUTED
            self.emu_chip_frame.add(DarkCheck(self.emu_chip_frame, label, var, bg=COL_PANEL, fg=fg))

        if not self.emu_manager.has_ldconsole():
            self._log("warn", "Không tìm thấy ldconsole.exe - chỉ hiển thị được serial ADB, không có tên "
                               "giả lập thật và KHÔNG quét được giả lập đang TẮT. Bấm '📁 Chọn ldconsole.exe' "
                               "để chỉ đường dẫn thủ công (file ldconsole.exe nằm trong thư mục cài LDPlayer).")
        elif getattr(self.emu_manager, "last_console_diag", ""):
            # Đã có đường dẫn console nhưng `list2` không dùng được (sai file, bản LDPlayer
            # khác, không trả lời...) -> danh sách trên đang lấy từ `adb devices`, nói rõ lý do.
            self._log("warn", f"ldconsole không liệt kê được giả lập - đang dùng tạm danh sách từ "
                               f"'adb devices' (tên = serial). Lý do: {self.emu_manager.last_console_diag}")

        self._sync_pin_checkbox()
        running_count = sum(1 for e in self.emulators if e.running)
        off_count = len(self.emulators) - running_count
        self._refresh_log_filter_options()
        self._log("info", f"Đã quét thấy {len(self.emulators)} giả lập ({running_count} đang chạy, {off_count} đang tắt).")

    def _on_toggle_all_emulators(self):
        val = self.emu_all_var.get()
        for var in self.emu_vars.values():
            var.set(val)

    def _get_selected_emulators(self):
        return [e for e in self.emulators if self.emu_vars.get(e.name, tk.BooleanVar(value=False)).get()]

    # ================= CHỌN ĐƯỜNG DẪN ldconsole.exe THỦ CÔNG =================
    def choose_ldconsole_path(self):
        """Cho phép người dùng tự trỏ tới file ldconsole.exe khi tự động dò
        không thành công (vd ldconsole.exe không nằm cùng thư mục adb.exe,
        không có tiến trình dnplayer.exe nào đang chạy để dò theo, và không
        cài ở 2 đường dẫn mặc định C:/D:\\leidian\\LDPlayer9). Lưu lại vào
        dashboard_settings.json để lần mở app sau không phải chọn lại."""
        path = filedialog.askopenfilename(
            title="Chọn file ldconsole.exe (trong thư mục cài LDPlayer)",
            filetypes=[("ldconsole.exe", "ldconsole.exe"), ("Tệp thực thi", "*.exe"), ("Tất cả file", "*.*")]
        )
        if not path:
            return
        fixed = normalize_console_path(path)
        if fixed != path:
            self._log("info", f"Đã tự đổi sang {fixed} (file bạn chọn không phải ldconsole.exe/dnconsole.exe).")
            path = fixed
        self.emu_manager.set_console_path(path)   # đồng thời trỏ adb.exe về cùng thư mục LDPlayer
        self._save_settings()
        self._log("success", f"Đã đặt đường dẫn ldconsole.exe: {path}")
        # Thử chạy `list2` NGAY để biết đường dẫn vừa chọn có dùng được không, thay vì chỉ
        # thấy danh sách giả lập trống mà không hiểu vì sao.
        rows, diag = self.emu_manager.query_list2()
        if rows:
            self._log("success", f"ldconsole hoạt động - thấy {len(rows)} giả lập đã cấu hình.")
        else:
            self._log("warn", f"ldconsole chạy nhưng không đọc được giả lập: {diag}")
            self._show_console_diag(diag)
        self.refresh_emulators()

    def _show_console_diag(self, diag):
        """Cửa sổ chẩn đoán ldconsole: theme của dự án (nền COL_PANEL, ô nội dung COL_ENTRY), KHÔNG tự
        tắt vì nội dung dài cần đọc/sao chép (khác thông báo 5s của auto_notify)."""
        win = ThemedToplevel(self.root)
        win.title("Chẩn đoán ldconsole")
        win.configure(bg=COL_PANEL)
        win.transient(self.root)
        wg.restore_geometry(win, "ldconsole_diag", default="560x300")
        wg.autosave(win, "ldconsole_diag")
        _bind_esc_close(win)

        tk.Frame(win, bg=COL_ORANGE, height=4).pack(fill="x")
        tk.Label(win, text="⚠ ldconsole chưa dùng được", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(win, text=f"Đường dẫn đang dùng: {self.emu_manager.ldconsole_path or '(chưa có)'}",
                 bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=520,
                 justify="left").pack(anchor="w", padx=14)

        bar = tk.Frame(win, bg=COL_HEADER)
        bar.pack(side="bottom", fill="x")
        body = tk.Frame(win, bg=COL_PANEL)
        body.pack(fill="both", expand=True, padx=14, pady=10)
        txt = tk.Text(body, wrap="word", bg=COL_ENTRY, fg=COL_TEXT, insertbackground=COL_TEXT,
                      selectbackground=COL_SELECT, relief="flat", font=("Consolas", 9),
                      highlightthickness=1, highlightbackground=COL_BORDER, highlightcolor=COL_BORDER)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", diag)
        txt.config(state="disabled")

        def _copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(diag)

        RoundedButton(bar, "Đóng", command=win.destroy, bg=COL_GRAY_BTN, container_bg=COL_HEADER,
                      font=("Segoe UI", 9, "bold"), padx=18, pady=6).pack(side="right", padx=(0, 10), pady=10)
        RoundedButton(bar, "📋 Sao chép", command=_copy, bg=COL_TEAL, container_bg=COL_HEADER,
                      font=("Segoe UI", 9, "bold"), padx=14, pady=6).pack(side="right", padx=(0, 6), pady=10)

    # ================= BẬT / TẮT GIẢ LẬP ĐÃ CHỌN =================
    def launch_selected_emulators(self):
        selected = self._get_selected_emulators()
        if not selected:
            messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào để khởi động!\nTick chọn ở thanh 'Giả lập' trước.")
            return
        if not self.emu_manager.has_ldconsole():
            messagebox.showwarning("Lưu ý", "Chưa tìm thấy ldconsole.exe.\n"
                                             "Bấm '📁 Chọn ldconsole.exe' để chỉ đường dẫn thủ công.")
            return
        threading.Thread(target=self._worker_launch_emulators, args=(list(selected),), daemon=True).start()

    def _worker_launch_emulators(self, selected):
        for e in selected:
            # Kiểm tra TRƯỚC: nếu giả lập này đang CHẠY nhưng KHÔNG PHẢN HỒI
            # (mất kết nối ADB hoặc không boot xong dù tiến trình vẫn sống)
            # = có thể đang TREO - gọi thẳng launch() lúc này KHÔNG có tác
            # dụng gì (LDPlayer bỏ qua vì thấy index đó "đã chạy"), sẽ cứ
            # đứng chờ boot xong mãi rồi báo lỗi "khởi động quá lâu" dù
            # chẳng có gì đang khởi động cả - phải tự TẮT HẲN rồi khởi động
            # lại thì mới thật sự phục hồi được (xem emulator_manager.
            # quit_and_wait_stopped/ensure_running).
            info = self.emu_manager.find_by_index(e.index)
            if info and info.running:
                if self.emu_manager.is_ready(info):
                    self._log("info", f"Giả lập '{e.name}' (#{e.index}) đã bật sẵn và sẵn sàng - bỏ qua.",
                               emulator_name=e.name)
                    continue
                self._log("warn", f"Giả lập '{e.name}' (#{e.index}) đang chạy nhưng KHÔNG PHẢN HỒI (có thể bị "
                                   f"TREO) - đang tự TẮT HẲN rồi khởi động lại...", emulator_name=e.name)
                self.emu_manager.quit_and_wait_stopped(
                    e.index, on_log=lambda lvl, msg, _e=e: self._log(lvl, f"[{_e.name}] {msg}", emulator_name=_e.name))

            self._log("info", f"Đang khởi động giả lập '{e.name}' (#{e.index})...", emulator_name=e.name)
            ok, msg = self.emu_manager.launch(e.index)
            if ok:
                self._log("success", f"Đã gửi lệnh khởi động giả lập '{e.name}' (#{e.index}). "
                                      f"Đang tự chờ Android boot xong ở nền...", emulator_name=e.name)
                # Chờ boot ở 1 LUỒNG RIÊNG cho TỪNG giả lập (không chặn việc
                # gửi lệnh khởi động các giả lập khác trong danh sách đã
                # chọn) - đánh dấu BẬN ngay để 1 lượt CHẠY tay/lịch hẹn giờ
                # nhắm đúng giả lập này trong lúc đang chờ/tự login sẽ tự
                # XẾP HÀNG CHỜ (xem _queue_job) thay vì đá nhau/chạm chuột
                # chồng chéo lên cùng lúc.
                self._busy_emulator_indexes.add(e.index)
                threading.Thread(target=self._worker_wait_boot_then_autologin, args=(e,), daemon=True).start()
            else:
                self._log("error", f"Không khởi động được giả lập '{e.name}' (#{e.index}): {msg}", emulator_name=e.name)
        self.root.after(1500, self.refresh_emulators)

    def _worker_wait_boot_then_autologin(self, emulator):
        """Chạy ở 1 luồng riêng NGAY SAU KHI gửi lệnh khởi động 1 giả lập:
        tự chờ tới khi Android bên trong nó boot xong THẬT SỰ (không chỉ
        tiến trình LDPlayer đã chạy - xem emulator_manager.wait_until_ready),
        rồi nếu đang bật 'Tự Login' (self.auto_login_var), tự chạy luôn
        Hoạt Động 'auto_login' để vào game - KHÔNG cần người dùng tick
        thêm tác vụ nào rồi bấm CHẠY chỉ để vào game sau khi vừa bật máy.

        LƯU Ý: trước đây luồng này KHÔNG hề đụng tới self.is_running hay
        bất kỳ bộ đếm nào mà _any_active_work() theo dõi, nên trong lúc
        đang chờ boot/chạy Tự Login ở đây, nút '⏹ Dừng' và '⏸ Tạm Dừng'
        trên Dashboard vẫn bị KHOÁ (disabled) - bấm vào không có phản ứng
        gì dù cờ dừng/tạm dừng bên trong (self.stop_flags/pause_flags) vẫn
        hoạt động bình thường. Sửa y hệt cách đã sửa cho '⚡ Log Nhanh' ở
        dashboard_accounts.py::_start_quick_login: dùng CHUNG bộ đếm
        self._active_quicklogin_count (không đụng self.is_running, vốn
        dành riêng cho phiên CHẠY chính) để _any_active_work() biết có
        việc đang chạy và tự bật nút Dừng/Tạm Dừng lên đúng lúc - người
        dùng bấm Dừng/Tạm Dừng giữa lúc đang chờ boot hay đang Tự Login
        đều có tác dụng ngay."""
        self._active_quicklogin_count = getattr(self, "_active_quicklogin_count", 0) + 1
        self.root.after(0, self._refresh_run_control_buttons)
        try:
            ready = self.emu_manager.wait_until_ready(emulator.index, timeout=180)
            self.root.after(0, self.refresh_emulators)

            if not ready:
                self._log("error", f"Giả lập '{emulator.name}' khởi động quá lâu (>180s) hoặc chưa boot xong - "
                                    f"bỏ qua Tự Login, thử bấm '🔄 Quét Giả Lập' rồi kiểm tra lại thủ công.",
                           emulator_name=emulator.name)
            else:
                self._log("success", f"Giả lập '{ready.name}' đã boot xong.", emulator_name=ready.name)
                if self.auto_login_var.get():
                    # Chờ thêm (ô 'Chờ boot (s)' ở thanh trên) cho game/launcher lên hẳn
                    # rồi mới chạy Tự Login - tuỳ máy khởi động nhanh hay chậm.
                    self._wait_after_boot_for_autologin(ready)
                    if not self._is_stop_requested(ready.index):
                        self._run_login_check_standalone(ready, context_label="Tự Login (sau khi khởi động)")
        finally:
            self._busy_emulator_indexes.discard(emulator.index)
            self.stop_flags.pop(emulator.index, None)
            self.pause_flags.pop(emulator.index, None)
            self._active_quicklogin_count = max(0, getattr(self, "_active_quicklogin_count", 0) - 1)
            self.root.after(0, self._refresh_run_control_buttons)
            self._after_emulator_freed(emulator.index)

    def quit_selected_emulators(self):
        selected = self._get_selected_emulators()
        if not selected:
            messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào để tắt!\nTick chọn ở thanh 'Giả lập' trước.")
            return
        if not self.emu_manager.has_ldconsole():
            messagebox.showwarning("Lưu ý", "Chưa tìm thấy ldconsole.exe.\n"
                                             "Bấm '📁 Chọn ldconsole.exe' để chỉ đường dẫn thủ công.")
            return
        if not messagebox.askyesno("Xác nhận", f"Tắt {len(selected)} giả lập đã chọn?"):
            return
        threading.Thread(target=self._worker_quit_emulators, args=(list(selected),), daemon=True).start()

    def _worker_quit_emulators(self, selected):
        for e in selected:
            self._log("info", f"Đang tắt giả lập '{e.name}' (#{e.index})...", emulator_name=e.name)
            ok, msg = self.emu_manager.quit_emulator(e.index)
            if ok:
                self._log("success", f"Đã gửi lệnh tắt giả lập '{e.name}' (#{e.index}).", emulator_name=e.name)
            else:
                self._log("error", f"Không tắt được giả lập '{e.name}' (#{e.index}): {msg}", emulator_name=e.name)
        self.root.after(1500, self.refresh_emulators)

    # ================= ĐƯA LÊN TRÊN / GHIM / THU NHỎ GIẢ LẬP ĐÃ CHỌN =================
    def _get_live_hwnd(self, e):
        """Lấy hwnd MỚI NHẤT cho giả lập `e` - ưu tiên e.hwnd sẵn có (từ lần
        quét gần nhất), tự dò lại qua emu_manager.find_by_index() nếu hwnd
        cũ không còn hợp lệ (giả lập vừa khởi động lại nên hwnd đã đổi)
        hoặc chưa có sẵn (vd đang dùng chế độ fallback ADB, không có
        ldconsole.exe)."""
        hwnd = getattr(e, "hwnd", None)
        if hwnd and win32gui.IsWindow(hwnd):
            return hwnd
        info = self.emu_manager.find_by_index(e.index)
        if info and info.hwnd and win32gui.IsWindow(info.hwnd):
            return info.hwnd
        return None

    def bring_selected_emulators_to_front(self):
        """⬆ Đưa Lên Trên: nâng cửa sổ LDPlayer của các giả lập ĐÃ CHỌN lên trên các cửa sổ khác MỘT LẦN
        (nếu đang thu nhỏ thì khôi phục) - KHÔNG ghim: sau đó bấm sang cửa sổ khác thì cửa sổ khác lại
        đè lên bình thường. Muốn cửa sổ luôn nổi thì tick ô 📌 bên cạnh (xem set_pin_selected_emulators)."""
        selected = self._get_selected_emulators()
        if not selected:
            messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào!\nTick chọn ở thanh 'Giả lập' trước.")
            return

        ok_count = 0
        for e in selected:
            hwnd = self._get_live_hwnd(e)
            if not hwnd:
                self._log("warn", f"Không tìm thấy cửa sổ LDPlayer của '{e.name}' để đưa lên trên.", emulator_name=e.name)
                continue
            try:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                # Trước đây chỉ gọi SetWindowPos(HWND_TOP, ...|SWP_NOACTIVATE): Windows thường BỎ QUA lệnh này
                # khi tiến trình gọi không phải cửa sổ đang focus (cửa sổ LDPlayer là tiến trình khác) nên
                # nút không có tác dụng. Mẹo đáng tin cậy: bật TOPMOST rồi trả về NOTOPMOST ngay -> cửa sổ
                # nhảy lên đầu thứ tự xếp lớp BÌNH THƯỜNG (không ghim). Giả lập đang được ghim (📌) thì giữ
                # nguyên TOPMOST, không trả về NOTOPMOST.
                _flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, _flags)
                _pinned = getattr(self, "_topmost_emu_indexes", None) or set()
                if e.index not in _pinned:
                    win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, _flags)
                try:
                    win32gui.BringWindowToTop(hwnd)
                except Exception:
                    pass
                ok_count += 1
            except Exception as ex:
                self._log("warn", f"Không đưa lên trên được cửa sổ '{e.name}': {ex}", emulator_name=e.name)

        if ok_count:
            self._log("success", f"Đã ĐƯA LÊN TRÊN {ok_count} cửa sổ giả lập đã chọn.")

    def set_pin_selected_emulators(self, pin):
        """GHIM (pin=True: luôn nổi trên mọi cửa sổ khác, kể cả khi app khác đang được focus) hoặc BỎ GHIM
        (pin=False) các giả lập ĐÃ CHỌN - điều khiển bởi ô tick 📌 cạnh nút '⬆ Đưa Lên Trên'.
        Trả về số cửa sổ thao tác được (0 = không làm gì được)."""
        selected = self._get_selected_emulators()
        pinned = getattr(self, "_topmost_emu_indexes", None)
        if pinned is None:
            pinned = set()
            self._topmost_emu_indexes = pinned

        target_flag = win32con.HWND_TOPMOST if pin else win32con.HWND_NOTOPMOST
        ok_count = 0
        for e in selected:
            hwnd = self._get_live_hwnd(e)
            if not hwnd:
                self._log("warn", f"Không tìm thấy cửa sổ LDPlayer của '{e.name}' để "
                                   f"{'ghim' if pin else 'bỏ ghim'}.", emulator_name=e.name)
                continue
            try:
                win32gui.SetWindowPos(hwnd, target_flag, 0, 0, 0, 0,
                                       win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
                if pin:
                    pinned.add(e.index)
                else:
                    pinned.discard(e.index)
                ok_count += 1
            except Exception as ex:
                self._log("warn", f"Không thao tác được cửa sổ '{e.name}': {ex}", emulator_name=e.name)

        if ok_count:
            verb = "Đã GHIM (luôn nổi trên các cửa sổ khác)" if pin else "Đã BỎ GHIM"
            self._log("success", f"{verb} {ok_count} cửa sổ giả lập đã chọn.")
        return ok_count

    def _on_pin_check_toggled(self):
        """Người dùng vừa bấm ô tick 📌: ghim/bỏ ghim các giả lập đang chọn theo trạng thái mới của ô."""
        want = bool(self._emu_pin_var.get())
        if not self._get_selected_emulators():
            messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào!\nTick chọn ở thanh 'Giả lập' trước.")
            self._emu_pin_var.set(False)
            return
        self.set_pin_selected_emulators(want)
        self._sync_pin_checkbox()     # hiện đúng trạng thái THỰC (vd có cửa sổ không thao tác được)

    def _sync_pin_checkbox(self):
        """Ô tick 📌 phản ánh các giả lập ĐANG CHỌN: tick khi (có chọn và) TẤT CẢ đều đang được ghim.
        Gọi mỗi khi đổi lựa chọn giả lập / quét lại danh sách / sau khi ghim."""
        var = getattr(self, "_emu_pin_var", None)
        if var is None:
            return
        try:
            selected = self._get_selected_emulators()
            pinned = getattr(self, "_topmost_emu_indexes", None) or set()
            var.set(bool(selected) and all(e.index in pinned for e in selected))
        except Exception:
            pass

    def minimize_selected_emulators(self):
        """Thu nhỏ (minimize) cửa sổ LDPlayer của các giả lập ĐÃ CHỌN, y hệt
        bấm nút thu nhỏ trên thanh tiêu đề cửa sổ đó."""
        selected = self._get_selected_emulators()
        if not selected:
            messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào!\nTick chọn ở thanh 'Giả lập' trước.")
            return

        ok_count = 0
        for e in selected:
            hwnd = self._get_live_hwnd(e)
            if not hwnd:
                self._log("warn", f"Không tìm thấy cửa sổ LDPlayer của '{e.name}' để thu nhỏ.", emulator_name=e.name)
                continue
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                ok_count += 1
            except Exception as ex:
                self._log("warn", f"Không thu nhỏ được cửa sổ '{e.name}': {ex}", emulator_name=e.name)

        if ok_count:
            self._log("success", f"Đã thu nhỏ {ok_count} cửa sổ giả lập đã chọn.")

    # ================= BẢNG GIẢ LẬP / HƯỚNG DẪN / CÀI ĐẶT SHOP =================
    def _debug_capture_emulator(self, emulator, parent_win):
        """Chụp màn hình bằng ĐÚNG serial mà Dashboard sẽ dùng để chạy tác vụ
        trên giả lập này, lưu ra file rồi mở lên - để người dùng TỰ MẮT so
        sánh với cửa sổ LDPlayer thật, xác nhận serial có đang trỏ đúng giả
        lập hay không (thay vì chỉ tin 'adb connect' báo thành công - lệnh
        đó chỉ xác nhận CÓ kết nối, không xác nhận kết nối tới ĐÚNG cửa sổ)."""
        connected = self.emu_manager.ensure_adb_connected(emulator)
        if not connected:
            messagebox.showerror(
                "Chụp thử thất bại",
                f"Không kết nối được tới serial: {emulator.adb_serial}", parent=parent_win)
            return

        test_adb = ADBHelper()
        test_adb.device_id = emulator.adb_serial
        img = test_adb.screencap_fast()
        if img is None:
            messagebox.showerror(
                "Chụp thử thất bại",
                f"Serial '{emulator.adb_serial}' kết nối được nhưng KHÔNG chụp được màn hình.\n"
                "Có thể serial này không thật sự tương ứng với giả lập đang hiển thị.",
                parent=parent_win)
            return

        try:
            os.makedirs("logs", exist_ok=True)
            safe_name = "".join(c if c.isalnum() else "_" for c in emulator.name)
            out_path = os.path.abspath(os.path.join("logs", f"debug_capture_{safe_name}.png"))
            cv2.imwrite(out_path, img)
            os.startfile(out_path)
            messagebox.showinfo(
                "Đã chụp",
                f"Đã chụp màn hình qua serial '{emulator.adb_serial}' và mở ảnh lên.\n\n"
                f"So sánh ảnh vừa mở với cửa sổ LDPlayer '{emulator.name}' thật trên màn hình bạn:\n"
                "- Nếu KHỚP -> serial đúng, vấn đề nằm ở nơi khác (vd sai vùng ảnh mẫu, thư mục templates).\n"
                "- Nếu KHÔNG khớp (ảnh khác hẳn, hoặc là màn hình 1 giả lập/app khác) -> serial đang bị "
                "gán NHẦM cho giả lập này.",
                parent=parent_win)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không lưu/mở được ảnh chụp thử:\n{e}", parent=parent_win)

    def _open_emulator_panel(self):
        win = ThemedToplevel(self.root)
        win.title("Bảng Giả Lập")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "emulators_table", default="480x440")
        wg.autosave(win, "emulators_table")
        _bind_esc_close(win)

        tk.Label(win, text="🖥 Giả Lập LDPlayer Đang Chạy", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 4))

        if not self.emu_manager.has_ldconsole():
            tk.Label(win, text="⚠ Không tìm thấy ldconsole.exe - chỉ hiển thị serial ADB thô.",
                     bg=COL_PANEL, fg=COL_ORANGE, font=("Segoe UI", 9), wraplength=440, justify="left").pack(
                anchor="w", padx=14, pady=(0, 8))

        body = tk.Frame(win, bg=COL_PANEL)
        body.pack(fill="both", expand=True, padx=10, pady=4)

        if not self.emulators:
            tk.Label(body, text="Chưa quét thấy giả lập nào. Bấm 'Quét Lại' bên dưới.",
                     bg=COL_PANEL, fg=COL_TEXT_MUTED).pack(pady=20)
        else:
            for e in self.emulators:
                row = tk.Frame(body, bg=COL_PANEL_ALT)
                row.pack(fill="x", pady=3)
                status = "🟢 Đã khởi động" if e.android_started else "🟡 Đang khởi động"
                tk.Label(row, text=e.name, bg=COL_PANEL_ALT, fg=COL_TEXT,
                         font=("Segoe UI", 9, "bold")).pack(side="left", padx=8, pady=6)
                adb_label = tk.Label(row, text=f"{status}  •  ADB: {e.adb_serial}", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                         font=("Segoe UI", 8))
                adb_label.pack(side="left", padx=6)

                def _reconnect(em=e, lbl=adb_label, st=status):
                    ok = self.emu_manager.ensure_adb_connected(em)
                    # ensure_adb_connected() có thể vừa TỰ NÂNG CẤP em.adb_serial
                    # (127.0.0.1:YYYY -> emulator-XXXX) - Label ở trên là text
                    # TĨNH tạo lúc mở panel, tự nó không vẽ lại, nên phải cập
                    # nhật tay ở đây thì chữ trên "Bảng Giả Lập" mới khớp với
                    # serial thật đang dùng, không cần bấm "Quét Lại".
                    lbl.config(text=f"{st}  •  ADB: {em.adb_serial}")
                    messagebox.showinfo("Kết nối ADB", f"{'Thành công' if ok else 'Thất bại'}: {em.adb_serial}", parent=win)

                def _test_capture(em=e, lbl=adb_label, st=status):
                    self._debug_capture_emulator(em, win)
                    # _debug_capture_emulator() cũng gọi ensure_adb_connected()
                    # bên trong (có thể tự nâng cấp serial) - đồng bộ lại chữ
                    # trên Label như ở _reconnect().
                    lbl.config(text=f"{st}  •  ADB: {em.adb_serial}")

                RoundedButton(row, "📸 Chụp Thử", command=_test_capture, bg=COL_PURPLE,
                              container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(side="right", padx=4, pady=4)
                RoundedButton(row, "🔌 Kết nối lại", command=_reconnect, bg=COL_TEAL,
                              container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(side="right", padx=6, pady=4)

        def _rescan():
            self.refresh_emulators()
            win.destroy()
            self._open_emulator_panel()

        RoundedButton(win, "🔄 Quét Lại", command=_rescan,
                      bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")).pack(pady=10)

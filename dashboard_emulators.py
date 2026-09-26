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
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, _bind_esc_close


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
            label = f"🟢 {e.name}" if e.running else f"⚪ {e.name} (đang tắt)"
            fg = COL_TEXT if e.running else COL_TEXT_MUTED
            self.emu_chip_frame.add(DarkCheck(self.emu_chip_frame, label, var, bg=COL_PANEL, fg=fg))

        if not self.emu_manager.has_ldconsole():
            self._log("warn", "Không tìm thấy ldconsole.exe - chỉ hiển thị được serial ADB, không có tên "
                               "giả lập thật và KHÔNG quét được giả lập đang TẮT. Bấm '📁 Chọn ldconsole.exe' "
                               "để chỉ đường dẫn thủ công (file ldconsole.exe nằm trong thư mục cài LDPlayer).")

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
        self.emu_manager.ldconsole_path = path
        self._save_settings()
        self._log("success", f"Đã đặt đường dẫn ldconsole.exe: {path}")
        self.refresh_emulators()

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

    # ================= ĐƯA LÊN ĐẦU / THU NHỎ GIẢ LẬP ĐÃ CHỌN =================
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

    def toggle_pin_selected_emulators(self):
        """Đưa cửa sổ LDPlayer của các giả lập ĐÃ CHỌN lên TRÊN CÙNG (luôn
        nổi trên mọi cửa sổ khác trên Desktop, kể cả khi Dashboard hay app
        khác đang được focus) - bấm lại 1 lần nữa để BỎ GHIM (trở lại bình
        thường, không còn luôn nổi trên nữa). Dùng chung 1 nút, tự đổi
        hành vi theo trạng thái hiện tại của các giả lập đã chọn: nếu TẤT
        CẢ đang được ghim -> bỏ ghim hết; ngược lại (chưa ghim hoặc mới
        ghim 1 phần) -> ghim hết."""
        selected = self._get_selected_emulators()
        if not selected:
            messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào!\nTick chọn ở thanh 'Giả lập' trước.")
            return

        pinned = getattr(self, "_topmost_emu_indexes", None)
        if pinned is None:
            pinned = set()
            self._topmost_emu_indexes = pinned

        all_pinned = all(e.index in pinned for e in selected)
        target_flag = win32con.HWND_NOTOPMOST if all_pinned else win32con.HWND_TOPMOST

        ok_count = 0
        for e in selected:
            hwnd = self._get_live_hwnd(e)
            if not hwnd:
                self._log("warn", f"Không tìm thấy cửa sổ LDPlayer của '{e.name}' để "
                                   f"{'bỏ ghim' if all_pinned else 'đưa lên đầu'}.", emulator_name=e.name)
                continue
            try:
                win32gui.SetWindowPos(hwnd, target_flag, 0, 0, 0, 0,
                                       win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
                if all_pinned:
                    pinned.discard(e.index)
                else:
                    pinned.add(e.index)
                ok_count += 1
            except Exception as ex:
                self._log("warn", f"Không thao tác được cửa sổ '{e.name}': {ex}", emulator_name=e.name)

        if ok_count:
            verb = "Đã BỎ GHIM" if all_pinned else "Đã ĐƯA LÊN ĐẦU (luôn nổi trên các cửa sổ khác)"
            self._log("success", f"{verb} {ok_count} cửa sổ giả lập đã chọn.")

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
        win = tk.Toplevel(self.root)
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

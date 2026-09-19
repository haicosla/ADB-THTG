"""
gui_run.py — RunMixin: chạy thử kịch bản NGAY TRONG LD Macro Studio (khác
với Dashboard vốn chạy hàng loạt nhiều giả lập) - "Chạy Thử"/"Chạy Đã
Chọn"/"Dừng", ghi & hiển thị Nhật Ký chạy, và popup "trong game" dùng để
xem trước hiệu ứng popup trước khi lưu vào kịch bản.

Đây là 1 phần của class MacroStudioApp (xem gui.py), tách theo chức năng
như các Mixin dashboard_*.py - "self." trỏ vào cùng 1 instance
MacroStudioApp, KHÔNG đổi hành vi so với bản gộp 1 file trước đây.
""" 
import os
import time
import threading
from tkinter import filedialog, messagebox

from logic_engine import LogicEngine, BreakGroupSignal, ContinueGroupSignal
from popup_widget import show_ingame_popup
import script_validator


class RunMixin:

    def validate_current_task(self):
        """Nút '🔍 Kiểm Tra Kịch Bản': quét TOÀN BỘ danh sách bước hiện tại
        (kể cả đệ quy vào các Nhóm Ngoài) để tìm ảnh mẫu/file Nhóm/nhãn bị
        THIẾU, báo ra NGAY bằng hộp thoại - thay vì chỉ phát hiện giữa
        chừng lúc CHẠY THỬ (trước đây chỉ ghi "warn" vào Nhật Ký, rất dễ bị
        bỏ sót cho tới khi kịch bản chạy sai)."""
        if not self.steps:
            messagebox.showinfo("Kiểm Tra Kịch Bản", "Kịch bản đang trống - chưa có bước nào để kiểm tra.")
            return
        result = script_validator.validate_steps(self.steps)
        if not script_validator.has_issues(result):
            messagebox.showinfo("Kiểm Tra Kịch Bản", "✅ Không thấy ảnh/file Nhóm/nhãn nào bị thiếu - kịch bản hợp lệ!")
            return
        report = script_validator.format_validation_report(result)
        self._log_run("error", "🔍 Kiểm Tra Kịch Bản: phát hiện thiếu file - xem hộp thoại chi tiết")
        messagebox.showwarning("Kiểm Tra Kịch Bản - Phát hiện thiếu", report)

    def _clear_run_log(self):
        self.txt_log.config(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.config(state="disabled")
        self._log_line_count = 0

    def _save_run_log_to_file(self):
        path = filedialog.asksaveasfilename(
            initialdir="logs", defaultextension=".txt",
            filetypes=[("Text files", "*.txt")]
        )
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            content = self.txt_log.get("1.0", "end-1c")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Thành công", "Đã lưu Nhật Ký ra file!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không lưu được log:\n{e}")

    def _log_run(self, level, message):
        """Được LogicEngine gọi từ THREAD NỀN mỗi khi thực hiện 1 hành động,
        gặp lỗi, đổi biến, quét OCR, tìm thấy/không thấy ảnh... Tkinter chỉ
        được thao tác từ main thread nên phải điều phối qua root.after()."""
        self.root.after(0, lambda: self._append_log_line(level, message))

    def _append_log_line(self, level, message):
        ts = time.strftime("%H:%M:%S")
        tag = level if level in ("info", "success", "warn", "error") else "info"
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", f"[{ts}] {message}\n", (tag,))
        self._log_line_count += 1
        # Giới hạn số dòng để log không phình to vô hạn khi chạy lâu / lặp nhiều
        if self._log_line_count > self._LOG_MAX_LINES:
            trim_to = self._log_line_count - self._LOG_MAX_LINES
            self.txt_log.delete("1.0", f"{trim_to + 1}.0")
            self._log_line_count = self._LOG_MAX_LINES
        if self.var_log_autoscroll.get():
            self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    def run_macro(self):
        if not self.steps:
            messagebox.showwarning("Lưu ý", "Chưa có bước nào!")
            return
        self._start_run(self.steps, f"══════ Bắt đầu chạy kịch bản ({len(self.steps)} bước) ══════")

    def _selected_steps_in_order(self):
        """Trả về (indices, steps) của các dòng đang được BÔI ĐEN trong
        danh sách, sắp theo đúng thứ tự xuất hiện trong self.steps (bôi đen
        bằng Shift/Ctrl+Click có thể trả về thứ tự bất kỳ)."""
        try:
            indices = sorted(int(iid) for iid in self.tree.selection())
        except ValueError:
            indices = []
        return indices, [self.steps[i] for i in indices]

    def run_selected_steps(self):
        indices, selected_steps = self._selected_steps_in_order()
        if not selected_steps:
            messagebox.showwarning("Lưu ý", "Chưa chọn bước nào trong danh sách để chạy!\n"
                                             "(Bôi đen 1 hoặc nhiều bước rồi bấm lại)")
            return

        # Cảnh báo nhẹ nếu chọn thiếu 1 nửa của khối IF/Nhóm - chạy 1 khối
        # không trọn vẹn (vd chỉ chọn IF mà không chọn ENDIF, hoặc ngược
        # lại) có thể khiến logic không hoạt động đúng như khi chạy toàn bộ.
        counts = {"if": 0, "endif": 0, "group_start": 0, "group_end": 0}
        for s in selected_steps:
            act = s.get("action")
            if act in ("if_image", "if_var"):
                counts["if"] += 1
            elif act == "endif":
                counts["endif"] += 1
            elif act == "group_start":
                counts["group_start"] += 1
            elif act == "group_end":
                counts["group_end"] += 1
        if counts["if"] != counts["endif"] or counts["group_start"] != counts["group_end"]:
            if not messagebox.askyesno(
                "Cảnh báo",
                "Các bước đã chọn có vẻ chứa khối IF/Nhóm KHÔNG TRỌN VẸN "
                "(thiếu ENDIF hoặc điểm kết thúc Nhóm tương ứng).\n"
                "Logic điều kiện/lặp có thể chạy không đúng như mong đợi.\n\n"
                "Vẫn chạy các bước đã chọn?"
            ):
                return

        # Đổi tạm step_notifier để đánh dấu ĐÚNG dòng thật trong self.steps
        # (engine chỉ biết index trong tập con selected_steps đang chạy).
        self.engine.step_notifier = lambda sub_idx: self.root.after(
            0, lambda: self.tree.selection_set(str(indices[sub_idx])) if sub_idx < len(indices) else None
        )
        self._start_run(selected_steps, f"══════ Bắt đầu chạy {len(selected_steps)} bước ĐÃ CHỌN ══════")

    def _start_run(self, steps_to_run, log_header):
        if self.is_streaming_active:
            self.is_streaming_active = False
            self.btn_toggle_stream.config(text="▶ LIVE", bg="#455A64")
            self.lbl_fps.config(text="FPS: OFF", foreground="gray")
            time.sleep(0.1)
        self._active_run_steps = steps_to_run
        self.is_playing = True
        self.stop_flag = False
        self.btn_run.config(state="disabled")
        self.btn_run_selected.config(state="disabled")
        self.btn_stop.config(state="normal")
        self._append_log_line("info", log_header)
        threading.Thread(target=self._worker_run, daemon=True).start()

    def stop_macro(self):
        self.stop_flag = True
        self._log_run("warn", "Người dùng bấm DỪNG - đang chờ bước hiện tại kết thúc...")

    def _show_ingame_popup(self, message, duration=0, bg=None, fg=None, alpha=None, pos_box=None):
        """Hiện thông báo dạng OVERLAY nổi "topmost" đè lên cửa sổ
        LDPlayer - phần dựng popup thật sự nằm chung trong popup_widget.py
        (dùng chung với Dashboard nhiều giả lập, xem dashboard_misc.py) để
        khỏi lặp code 2 nơi.

        LƯU Ý (đổi cách làm so với bản nhúng cửa sổ con qua win32
        SetParent trước đây): cách nhúng làm con không đáng tin với các
        bản LDPlayer vẽ khung hình bằng GPU/DirectX, vì game tự vẽ đè lên
        TOÀN BỘ client area kể cả cửa sổ con nằm phía trên theo Z-order,
        khiến chữ trong popup bị vẽ đè mất ngay lập tức. Cửa sổ "topmost"
        bình thường được Windows/DWM compositing đè lên MỌI cửa sổ khác
        nên luôn hiện được chữ chắc chắn. Để vẫn bám theo LDPlayer nếu cửa
        sổ đó di chuyển trong lúc popup đang hiện, tự canh lại vị trí mỗi
        300ms thay vì nhúng làm con thật.

        Được LogicEngine gọi từ thread nền nên phải điều phối tạo cửa sổ
        qua root.after() (Tkinter chỉ thao tác được từ main thread).
        - duration > 0: tự đóng sau N giây, KHÔNG chặn kịch bản (giống toast).
        - duration == 0: hiện tới khi bấm nút ✖, kịch bản DỪNG chờ tại đây.
        Mọi lỗi bất ngờ được ghi vào Nhật Ký chạy (self._log_run) thay vì
        im lặng biến mất, để còn biết đường debug tiếp nếu vẫn có vấn đề."""
        done_event = threading.Event() if not duration else None

        def _log_err(where, e):
            try:
                self._log_run("error", f"Popup lỗi ({where}): {e}")
            except Exception:
                pass

        def _do():
            show_ingame_popup(
                self.root, self.window_finder.get_render_screen_rect, message, duration,
                bg=bg, fg=fg, alpha=alpha, pos_box=pos_box,
                log_fn=_log_err, done_event=done_event,
            )

        try:
            self.root.after(0, _do)
        except Exception as e:
            _log_err("schedule _do", e)
        if done_event:
            done_event.wait()

    def _worker_run(self):
        error_msg = None
        self.engine.reset_variables()
        try:
            self.engine.execute_steps(self._active_run_steps or self.steps, is_root=True)
        except (BreakGroupSignal, ContinueGroupSignal):
            pass
        except Exception as e:
            error_msg = str(e)
        self.root.after(0, lambda: self._on_finish_run(error_msg))

    def _on_finish_run(self, error_msg=None):
        self.is_playing = False
        self._active_run_steps = None
        # Nếu vừa "Chạy Đã Chọn" đã đổi tạm step_notifier -> trả về notifier
        # mặc định (đánh dấu theo index trong TOÀN BỘ self.steps) để lần
        # "CHẠY THỬ" toàn bộ tiếp theo đánh dấu đúng dòng như bình thường.
        if self._default_step_notifier is not None:
            self.engine.step_notifier = self._default_step_notifier
        self.btn_run.config(state="normal")
        self.btn_run_selected.config(state="normal")
        self.btn_stop.config(state="disabled")
        if not self.is_streaming_active:
            self.capture_and_show()
        if error_msg:
            self._append_log_line("error", f"══════ DỪNG DO LỖI: {error_msg} ══════")
            messagebox.showerror("Lỗi", f"Quy trình dừng do lỗi:\n{error_msg}")
        elif self.stop_flag:
            self._append_log_line("warn", "══════ Đã dừng theo yêu cầu người dùng ══════")
            messagebox.showinfo("Đã dừng", "Đã dừng quy trình theo yêu cầu!")
        else:
            self._append_log_line("success", "══════ Chạy xong toàn bộ kịch bản ══════")
            messagebox.showinfo("Xong", "Chạy xong quy trình!")

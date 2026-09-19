"""
gui_canvas.py — CanvasMixin: tương tác trực tiếp trên khung xem trước
(canvas) bằng chuột (kéo để chọn vùng chụp ảnh mẫu, lăn chuột để zoom/pan)
và bàn phím tắt toàn cục (F7 ghi thao tác trực tiếp). Cũng chứa các nút
chèn nhanh IF/ELSE/chờ nhiều ảnh và 2 hàm cắt ảnh mẫu từ vùng đã chọn
(_do_crop/_do_crop_custom) dùng chung cho nhiều loại bước.

Đây là 1 phần của class MacroStudioApp (xem gui.py), tách theo chức năng
như các Mixin dashboard_*.py - "self." trỏ vào cùng 1 instance
MacroStudioApp, KHÔNG đổi hành vi so với bản gộp 1 file trước đây.
""" 
import time
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
from pynput import keyboard

import capture_tools
from gui_dialogs import ZoomStepDialog


class CanvasMixin:

    def _start_global_hotkeys(self):
        def on_press(key):
            if key == keyboard.Key.f7:
                self.root.after(0, self.toggle_live_record)
            elif key == keyboard.Key.f8 and self.is_playing:
                self.root.after(0, self.stop_macro)
        self.kb_hotkey_listener = keyboard.Listener(on_press=on_press)
        self.kb_hotkey_listener.daemon = True
        self.kb_hotkey_listener.start()

    def toggle_live_record(self):
        if not self.is_recording_live:
            # QUAN TRỌNG: TRƯỚC ĐÂY gọi find_ld_windows() (quét mù, luôn bắt
            # cửa sổ LDPlayer ĐẦU TIÊN tìm thấy) ngay tại đây, ghi ĐÈ mất cửa
            # sổ ĐÚNG đã gắn theo giả lập đang chọn ở ô "Thiết bị" (qua
            # _attach_window_for_current_device() lúc đổi ô chọn) - khiến F7
            # LUÔN ghi nhầm vào 1 giả lập cố định (thường là giả lập mở đầu
            # tiên) mỗi khi mở nhiều giả lập cùng lúc, dù đã đổi đúng ô chọn
            # và Preview đã đổi đúng - CHÍNH LÀ lỗi người dùng phát hiện ra.
            # Nay CHỈ dùng cửa sổ đã gắn sẵn theo giả lập đang chọn; chỉ quét
            # mù lại như phương án CUỐI CÙNG nếu vì lý do gì đó chưa gắn được
            # cửa sổ nào (vd chưa có ldconsole.exe, hoặc chưa chọn giả lập).
            if not self.window_finder.main_hwnd:
                self._attach_window_for_current_device()
            if not self.window_finder.main_hwnd:
                messagebox.showerror("Lỗi", "Chưa nhận diện được cửa sổ LDPlayer!\nHãy chọn đúng giả lập ở ô 'Thiết bị' rồi thử lại.")
                return
            if self.is_streaming_active:
                self.is_streaming_active = False
                self.btn_toggle_stream.config(text="▶ LIVE", bg="#455A64")
                self.lbl_fps.config(text="FPS: OFF", foreground="gray")
                time.sleep(0.1)
            self.is_recording_live = True
            self.btn_live_record.config(text="⏹ DỪNG GHI (F7)", bg="#C62828")
            self.recorder.start()
        else:
            self.is_recording_live = False
            self.btn_live_record.config(text="● GHI LD (F7)", bg="#2E7D32")
            self.recorder.stop()
            self.capture_and_show()

    def on_canvas_ctrl_wheel(self, event):
        """Ctrl + lăn chuột để Zoom PREVIEW quanh đúng vị trí con trỏ (điểm
        con trỏ đang trỏ tới được giữ nguyên trên màn hình sau khi zoom,
        thay vì ảnh nhảy về góc trên-trái) - giống Photoshop/trình duyệt.
        CHỈ phóng to ảnh xem trước trên máy tính, KHÔNG gửi gì cho giả lập
        (khác với bước "Zoom (Pinch)" - xem add_manual_zoom())."""
        if self.current_screen_cv is None:
            return "break"
        # Windows/macOS: event.delta dương = lăn lên (zoom in), âm = lăn
        # xuống (zoom out). Linux X11 không có delta, thay vào đó bắn
        # event.num = 4 (lên) hoặc 5 (xuống) qua <Control-Button-4/5>.
        delta = getattr(event, "delta", 0)
        zoom_in = (delta > 0) if delta else (getattr(event, "num", 4) == 4)

        old_zoom = self.preview_zoom
        factor = 1.1 if zoom_in else (1 / 1.1)
        new_zoom = max(self.preview_zoom_min, min(self.preview_zoom_max, old_zoom * factor))
        if abs(new_zoom - old_zoom) < 1e-6:
            return "break"

        # Điểm con trỏ đang trỏ tới, quy về tỉ lệ 0..1 trên ẢNH HIỆN TẠI -
        # tính TRƯỚC khi preview_w/h đổi theo độ zoom mới.
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        frac_x = cx / self.preview_w if self.preview_w else 0.5
        frac_y = cy / self.preview_h if self.preview_h else 0.5

        self.preview_zoom = new_zoom
        self.render_preview(self.current_screen_cv)

        new_cx, new_cy = frac_x * self.preview_w, frac_y * self.preview_h
        target_x = max(0.0, min(1.0, (new_cx - event.x) / max(1, self.preview_w)))
        target_y = max(0.0, min(1.0, (new_cy - event.y) / max(1, self.preview_h)))
        self.canvas.xview_moveto(target_x)
        self.canvas.yview_moveto(target_y)
        return "break"

    def on_canvas_plain_wheel(self, event):
        """Lăn chuột thường (không giữ Ctrl) = cuộn dọc Preview khi ảnh đã
        zoom to hơn khung nhìn hiện tại."""
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def on_canvas_shift_wheel(self, event):
        """Shift + lăn chuột = cuộn ngang Preview."""
        self.canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def reset_preview_zoom(self):
        self.preview_zoom = 1.0
        if self.current_screen_cv is not None:
            self.render_preview(self.current_screen_cv)

    def on_canvas_press(self, event):
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.drag_start = (cx, cy)
        cw, ch = self.get_crop_wh()
        half_w, half_h = int((cw // 2) * self.preview_scale), int((ch // 2) * self.preview_scale)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        if (self.pending_action in ("wait_image", "if_image", "ocr_text", "image_region", "popup_pos")) or (self.pending_action is None and "crop" in self.preview_action_mode.get()):
            self.rect_id = self.canvas.create_rectangle(cx - half_w, cy - half_h, cx + half_w, cy + half_h, outline="#00ff00", width=2)

    def on_canvas_drag(self, event):
        if not self.drag_start:
            return
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if abs(cx - self.drag_start[0]) > 15 or abs(cy - self.drag_start[1]) > 15:
            if self.rect_id:
                self.canvas.coords(self.rect_id, self.drag_start[0], self.drag_start[1], cx, cy)
                self.canvas.itemconfig(self.rect_id, outline="yellow")

    def on_canvas_release(self, event):
        if not self.drag_start or self.current_screen_cv is None:
            return
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        x1, y1, x2, y2 = self.drag_start[0], self.drag_start[1], cx, cy
        self.drag_start = None
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None

        rx1, ry1 = round(x1 / self.preview_w, 4), round(y1 / self.preview_h, 4)
        rx2, ry2 = round(x2 / self.preview_w, 4), round(y2 / self.preview_h, 4)
        cached_screen = self.current_screen_cv.copy()
        mode = self.preview_action_mode.get()
        dragged = abs(x2 - x1) > 20 or abs(y2 - y1) > 20

        if self.pending_action == "tap":
            if self._tap_edit_idx is not None and 0 <= self._tap_edit_idx < len(self.steps):
                idx = self._tap_edit_idx
                self.steps[idx]["pos"] = [rx1, ry1]
                self.steps[idx]["comment"] = f"Tap [{int(rx1*100)}%, {int(ry1*100)}%]"
                self.refresh_tree()
                self.tree.selection_set(str(idx))
            else:
                self._insert_step({"action": "tap", "pos": [rx1, ry1], "repeat": 1, "delay": 1.0, "comment": f"Tap [{int(rx1*100)}%, {int(ry1*100)}%]"})
                threading.Thread(target=self._worker_send_tap, args=(rx1, ry1), daemon=True).start()
            self._cancel_pending_action()
            return
        elif self.pending_action == "swipe":
            if self._swipe_edit_idx is not None and 0 <= self._swipe_edit_idx < len(self.steps):
                idx = self._swipe_edit_idx
                self.steps[idx]["from"] = [rx1, ry1]
                self.steps[idx]["to"] = [rx2, ry2]
                self.refresh_tree()
                self.tree.selection_set(str(idx))
            else:
                self._insert_step({"action": "swipe", "from": [rx1, ry1], "to": [rx2, ry2], "duration": 250, "repeat": 1, "delay": 1.0, "comment": f"Swipe"})
                threading.Thread(target=self._worker_send_swipe, args=(rx1, ry1, rx2, ry2), daemon=True).start()
            self._cancel_pending_action()
            return
        elif self.pending_action == "zoom":
            # Zoom (Pinch) chỉ cần 1 điểm BẤM làm TÂM cử chỉ (bỏ qua kéo lệch
            # nếu có, không giống swipe cần cả 2 đầu) - bán kính/góc/thời
            # gian hỏi riêng qua ZoomStepDialog vì không thể chọn bằng 1 cú
            # bấm/kéo chuột đơn giản.
            center = [rx1, ry1]
            existing_idx = self._zoom_edit_idx
            existing_step = self.steps[existing_idx] if (existing_idx is not None and 0 <= existing_idx < len(self.steps)) else None
            self._cancel_pending_action()
            dlg = ZoomStepDialog(self.root, initial={**(existing_step or {}), "center": center})
            self.root.wait_window(dlg)
            if not dlg.result:
                return
            params = dlg.result
            is_in = params["end_radius"] > params["start_radius"]
            if existing_step is not None:
                existing_step["center"] = center
                existing_step.update(params)
                existing_step["comment"] = "Phóng To" if is_in else "Thu Nhỏ"
                self.refresh_tree()
                self.tree.selection_set(str(existing_idx))
            else:
                self._insert_step({
                    "action": "zoom", "center": center,
                    "start_radius": params["start_radius"], "end_radius": params["end_radius"],
                    "angle": params["angle"], "duration": params["duration"],
                    "repeat": 1, "delay": 1.0,
                    "comment": "Phóng To" if is_in else "Thu Nhỏ",
                })
                threading.Thread(target=self._worker_send_zoom, args=(rx1, ry1, params["start_radius"], params["end_radius"], params["angle"], params["duration"]), daemon=True).start()
            return
        elif self.pending_action in ("wait_image", "if_image"):
            edit_idx = self._image_edit_idx
            # Không tự bắn tap thử khi đang CHỌN LẠI ảnh cho 1 bước đã có sẵn
            # (chỉ muốn đổi ảnh mẫu, không muốn vô tình tap vào máy ảo).
            do_tap = (self.pending_action == "wait_image") and edit_idx is None
            if dragged:
                self._do_crop_custom(cached_screen, x1, y1, x2, y2, trigger_tap=do_tap, kind=self.pending_action, edit_idx=edit_idx)
            else:
                self._do_crop(cached_screen, int(x1 / self.preview_scale), int(y1 / self.preview_scale), rx1, ry1, trigger_tap=do_tap, kind=self.pending_action, edit_idx=edit_idx)
            self._cancel_pending_action()
            return
        elif self.pending_action == "image_region":
            # Vùng quét (region) lưu theo TỌA ĐỘ TỈ LỆ (0..1) trên toàn màn
            # hình, y hệt cách lưu box của ocr_text - matchTemplate của bước
            # ảnh này sẽ CHỈ so khớp trong vùng này thay vì toàn màn hình.
            nx1, ny1 = sorted((rx1, rx2))[0], sorted((ry1, ry2))[0]
            nx2, ny2 = sorted((rx1, rx2))[1], sorted((ry1, ry2))[1]
            if nx2 - nx1 < 0.02 or ny2 - ny1 < 0.02:
                messagebox.showwarning("Lưu ý", "Hãy KÉO một khung đủ lớn làm vùng quét!")
                self._cancel_pending_action()
                return
            edit_idx = self._region_edit_idx
            if edit_idx is not None and 0 <= edit_idx < len(self.steps):
                self.steps[edit_idx]["region"] = [nx1, ny1, nx2, ny2]
                self.refresh_tree()
                self.tree.selection_set(str(edit_idx))
            self._cancel_pending_action()
            return
        elif self.pending_action == "popup_pos":
            # Vị trí/kích thước hiển thị popup lưu theo TỌA ĐỘ TỈ LỆ (0..1)
            # trên toàn màn hình, giống ocr_text/image_region - lúc chạy sẽ
            # quy đổi ra toạ độ pixel THẬT trên khung game hiện tại (bám
            # theo game khi cửa sổ LDPlayer di chuyển/đổi kích thước).
            nx1, ny1 = sorted((rx1, rx2))[0], sorted((ry1, ry2))[0]
            nx2, ny2 = sorted((rx1, rx2))[1], sorted((ry1, ry2))[1]
            if nx2 - nx1 < 0.03 or ny2 - ny1 < 0.02:
                messagebox.showwarning("Lưu ý", "Hãy KÉO một khung đủ lớn làm vị trí hiển thị popup!")
                self._cancel_pending_action()
                return
            edit_idx = self._popup_pos_edit_idx
            if edit_idx is not None and 0 <= edit_idx < len(self.steps):
                self.steps[edit_idx]["pos_box"] = [nx1, ny1, nx2, ny2]
                self.refresh_tree()
                self.tree.selection_set(str(edit_idx))
            self._cancel_pending_action()
            return
        elif self.pending_action == "ocr_text":
            # Vùng OCR lưu theo TỌA ĐỘ TỈ LỆ (0..1), không lưu ảnh cố định,
            # vì mỗi lần chạy cần đọc chữ TRÊN MÀN HÌNH HIỆN TẠI (có thể thay
            # đổi liên tục), khác với wait_image/if_image là so khớp mẫu cố định.
            nx1, ny1 = sorted((rx1, rx2))[0], sorted((ry1, ry2))[0]
            nx2, ny2 = sorted((rx1, rx2))[1], sorted((ry1, ry2))[1]
            if nx2 - nx1 < 0.01 or ny2 - ny1 < 0.01:
                messagebox.showwarning("Lưu ý", "Hãy KÉO một khung đủ lớn quanh vùng chữ cần quét!")
                self._cancel_pending_action()
                return
            edit_idx = self._ocr_edit_idx
            if edit_idx is not None:
                step = self.steps[edit_idx]
                step["box"] = [nx1, ny1, nx2, ny2]
                self.refresh_tree()
                self.tree.selection_set(str(edit_idx))
            else:
                var_name = simpledialog.askstring("Quét OCR", "Lưu kết quả OCR vào biến tên gì (dùng với IF Biến):", initialvalue="ocr_text")
                if var_name:
                    self._insert_step({
                        "action": "ocr_text", "box": [nx1, ny1, nx2, ny2], "var": var_name.strip(),
                        "lang": "vie+eng", "repeat": 1, "delay": 0.5,
                        "comment": f"OCR vùng -> biến {var_name.strip()}"
                    })
            self._cancel_pending_action()
            return

        if dragged and mode == "tap_only":
            self._insert_step({"action": "swipe", "from": [rx1, ry1], "to": [rx2, ry2], "duration": 250, "repeat": 1, "delay": 1.0, "comment": f"Swipe"})
            threading.Thread(target=self._worker_send_swipe, args=(rx1, ry1, rx2, ry2), daemon=True).start()
        elif dragged and mode in ("crop_and_tap", "crop_only"):
            self._do_crop_custom(cached_screen, x1, y1, x2, y2, trigger_tap=(mode == "crop_and_tap"))
        else:
            real_cx, real_cy = int(x1 / self.preview_scale), int(y1 / self.preview_scale)
            if mode == "crop_and_tap":
                self._do_crop(cached_screen, real_cx, real_cy, rx1, ry1, trigger_tap=True)
            elif mode == "crop_only":
                self._do_crop(cached_screen, real_cx, real_cy, rx1, ry1, trigger_tap=False)
            elif mode == "tap_only":
                self._insert_step({"action": "tap", "pos": [rx1, ry1], "repeat": 1, "delay": 1.0, "comment": f"Tap"})
                threading.Thread(target=self._worker_send_tap, args=(rx1, ry1), daemon=True).start()

    def _do_crop(self, screen_img, cx, cy, norm_x, norm_y, trigger_tap=False, kind="wait_image", edit_idx=None):
        cw, ch = self.get_crop_wh()
        box = capture_tools.crop_fixed_box(screen_img, cx, cy, cw, ch)
        filename = capture_tools.save_crop(screen_img, box)
        if edit_idx is not None and 0 <= edit_idx < len(self.steps):
            self.steps[edit_idx]["template"] = filename
            self.steps[edit_idx]["comment"] = f"Ảnh: {filename}"
            self.refresh_tree()
            self.tree.selection_set(str(edit_idx))
        else:
            step = capture_tools.build_capture_step(
                kind, filename,
                int(self.spin_all_timeout.get() or 8),
                float(self.spin_all_conf.get() or 0.80),
                float(self.spin_all_scan.get() or 0.10),
            )
            self._insert_step(step)
        self.render_preview(screen_img, highlight_box=box)
        if trigger_tap:
            threading.Thread(target=self._worker_send_tap, args=(norm_x, norm_y), daemon=True).start()

    def _do_crop_custom(self, screen_img, px1, py1, px2, py2, trigger_tap=False, kind="wait_image", edit_idx=None):
        px1, px2 = sorted((px1, px2))
        py1, py2 = sorted((py1, py2))
        scr_h, scr_w = screen_img.shape[:2]
        x1, y1 = max(0, min(scr_w, int(px1 / self.preview_scale))), max(0, min(scr_h, int(py1 / self.preview_scale)))
        x2, y2 = max(0, min(scr_w, int(px2 / self.preview_scale))), max(0, min(scr_h, int(py2 / self.preview_scale)))
        if x2 - x1 < 5 or y2 - y1 < 5:
            return
        box = (x1, y1, x2, y2)
        filename = capture_tools.save_crop(screen_img, box)
        self.spin_w.delete(0, "end")
        self.spin_w.insert(0, str(x2 - x1))
        self.spin_h.delete(0, "end")
        self.spin_h.insert(0, str(y2 - y1))
        if edit_idx is not None and 0 <= edit_idx < len(self.steps):
            self.steps[edit_idx]["template"] = filename
            self.steps[edit_idx]["comment"] = f"Ảnh: {filename}"
            self.refresh_tree()
            self.tree.selection_set(str(edit_idx))
        else:
            step = capture_tools.build_capture_step(
                kind, filename,
                int(self.spin_all_timeout.get() or 8),
                float(self.spin_all_conf.get() or 0.80),
                float(self.spin_all_scan.get() or 0.10),
            )
            self._insert_step(step)
        self.render_preview(screen_img, highlight_box=box)
        if trigger_tap:
            threading.Thread(target=self._worker_send_tap, args=(round(((x1 + x2) / 2) / scr_w, 4), round(((y1 + y2) / 2) / scr_h, 4)), daemon=True).start()

    def _worker_send_tap(self, nx, ny):
        self.adb.tap(nx, ny)
        time.sleep(0.4)
        if not self.is_streaming_active:
            self.capture_and_show()

    def _worker_send_swipe(self, x1, y1, x2, y2):
        self.adb.swipe(x1, y1, x2, y2, 250)
        time.sleep(0.5)
        if not self.is_streaming_active:
            self.capture_and_show()


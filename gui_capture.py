"""
gui_capture.py — CaptureMixin: kết nối tới giả lập LDPlayer đang chọn
(quét danh sách, tìm cửa sổ, chụp màn hình 1 lần hoặc xem trực tiếp -
"stream"), và vẽ lại khung xem trước (kể cả khung highlight khi đang chọn
vùng chụp mẫu).

Đây là 1 phần của class MacroStudioApp (xem gui.py), tách theo chức năng
như các Mixin dashboard_*.py - "self." trỏ vào cùng 1 instance
MacroStudioApp, KHÔNG đổi hành vi so với bản gộp 1 file trước đây.
""" 
import time
import math
import tkinter as tk
from tkinter import messagebox
import cv2
from PIL import Image, ImageTk


class CaptureMixin:

    def refresh_all(self):
        # refresh_devices() giờ đã TỰ gắn đúng cửa sổ (qua
        # _attach_window_for_current_device()) - KHÔNG gọi find_ld_windows()
        # (quét mù) ở đây nữa, kẻo ghi đè mất kết quả đúng vừa gắn được bằng
        # 1 kết quả quét mù có thể SAI khi đang mở nhiều giả lập.
        self.refresh_devices()

    def refresh_devices(self):
        devs = self.adb.get_devices()
        self.cbo_dev["values"] = devs

        self._device_hwnd_map = {}
        if self.emulator_manager.has_ldconsole():
            try:
                for info in self.emulator_manager.refresh():
                    if info.adb_serial:
                        self._device_hwnd_map[info.adb_serial] = info
            except Exception:
                pass

        if devs:
            self.cbo_dev.current(0)
            self.adb.device_id = devs[0]
            self.adb.update_resolution()
            self.capture_and_show()
            self._attach_window_for_current_device()
        else:
            self.cbo_dev.set("Chưa có ADB")
        self._update_keycombo_warning()

    def _attach_window_for_current_device(self):
        """Gắn ĐÚNG cửa sổ LDPlayer (hwnd) tương ứng với giả lập ĐANG CHỌN ở
        ô 'Thiết bị' - quyết định F7 (ghi macro) và mọi thao tác canh toạ độ
        khác sẽ chạy trên cửa sổ nào. Ưu tiên hwnd biết CHẮC CHẮN từ
        `ldconsole list2` (đúng 100% dù mở bao nhiêu giả lập cùng lúc); chỉ
        khi không có ldconsole.exe trên máy mới lùi về cách quét mù cũ (bắt
        cửa sổ LDPlayer đầu tiên tìm thấy trên hệ thống - CÓ THỂ SAI nếu
        đang mở nhiều giả lập)."""
        serial = self.adb.device_id
        info = self._device_hwnd_map.get(serial)
        if info and info.hwnd:
            if self.window_finder.attach_hwnd(info.hwnd):
                self.lbl_ld_status.config(text=f"LD: {info.name}", foreground="green")
                return

        # Không có ánh xạ hwnd tin cậy -> quét mù như trước, kèm cảnh báo nếu
        # đang mở NHIỀU giả lập cùng lúc (lúc đó quét mù rất dễ bắt NHẦM).
        self.find_ld_windows()
        if len(self.adb.get_devices()) > 1:
            self.lbl_ld_status.config(
                text=self.lbl_ld_status.cget("text") + " (⚠️ nhiều giả lập, có thể SAI - cần ldconsole.exe để gắn đúng)",
                foreground="#E65100"
            )

    def _update_keycombo_warning(self):
        """Báo NGAY trên giao diện nếu máy ảo đang chạy Android < 12, vì khi
        đó bước 'Tổ Hợp Phím' (Ctrl+..., Alt+..., Shift+...) sẽ không giữ
        được đồng thời các phím - đây là giới hạn của chính Android, không
        phải app bị lỗi. Trước đây lỗi này hoàn toàn im lặng, không có gì
        báo cho người dùng biết."""
        if not self.adb.device_id:
            self.lbl_keycombo_warn.config(text="")
            return
        try:
            sdk = self.adb.get_sdk_version()
        except Exception:
            sdk = 0
        if sdk and sdk < 31:
            self.lbl_keycombo_warn.config(
                text=f"⚠️ Android SDK {sdk}: Tổ hợp phím (Ctrl/Alt/Shift+...) có thể KHÔNG hoạt động (cần Android 12+)",
                foreground="#B71C1C"
            )
        else:
            self.lbl_keycombo_warn.config(text="")

    def _apply_default_preview_width(self):
        try:
            self.root.update_idletasks()
            total_h = self.canvas.winfo_height()
            if total_h < 100:
                total_h = 620
            screen_w = self.adb.screen_w or 720
            screen_h = self.adb.screen_h or 1280
            ratio = screen_w / screen_h if screen_h else 0.5625
            target_w = int(total_h * ratio) + 40
            self.paned.sashpos(0, max(380, target_w))
        except Exception:
            pass

    def find_ld_windows(self):
        hwnd, title = self.window_finder.find_ld_windows()
        if hwnd:
            self.lbl_ld_status.config(text=f"LD: {title or 'Kyle'}", foreground="green")
        else:
            self.lbl_ld_status.config(text="LD: Không thấy", foreground="red")

    def on_select_device(self, _):
        self.adb.device_id = self.cbo_dev.get()
        self.adb._sdk_version = None  # đổi thiết bị -> phải dò lại SDK version
        self.adb.update_resolution()
        self.capture_and_show()
        self._attach_window_for_current_device()
        self._update_keycombo_warning()

    def capture_and_show(self):
        if not self.adb.device_id or self.is_recording_live:
            return
        img_cv = self.adb.screencap_fast()
        if img_cv is None:
            return
        self.current_screen_cv = img_cv
        self.render_preview(img_cv)

    def render_preview(self, img_cv, highlight_box=None):
        if img_cv is None:
            return
        self.root.update_idletasks()
        h, w = img_cv.shape[:2]
        cw = max(self.canvas.winfo_width(), 360)
        ch = max(self.canvas.winfo_height(), 500)
        # preview_zoom = 1.0 nghĩa là vừa khít khung (fit_scale). Ctrl + lăn
        # chuột (on_canvas_ctrl_wheel) chỉ chỉnh preview_zoom rồi gọi lại
        # render_preview() để vẽ lại theo độ phóng mới.
        fit_scale = min(cw / w, ch / h)
        scale = max(fit_scale * self.preview_zoom, 0.01)
        self.preview_scale = scale
        self.preview_w = max(1, int(w * self.preview_scale))
        self.preview_h = max(1, int(h * self.preview_scale))
        # Phóng to (zoom > 1) dùng nội suy tuyến tính cho mượt hơn INTER_AREA
        # (vốn hợp để THU nhỏ); thu nhỏ vẫn dùng INTER_AREA như cũ.
        interp = cv2.INTER_AREA if self.preview_scale <= fit_scale else cv2.INTER_LINEAR
        resized = cv2.resize(img_cv, (self.preview_w, self.preview_h), interpolation=interp)

        if highlight_box:
            bx1, by1, bx2, by2 = highlight_box
            cv2.rectangle(resized, (int(bx1 * self.preview_scale), int(by1 * self.preview_scale)), (int(bx2 * self.preview_scale), int(by2 * self.preview_scale)), (0, 255, 0), 2)

        # Vẽ đè VÙNG QUÉT / ĐIỂM CHẠM / ĐƯỜNG VUỐT / TÂM ZOOM của bước ĐANG
        # ĐƯỢC CHỌN trong danh sách (nếu có) - xem _update_region_overlay().
        # Toạ độ lưu theo tỉ lệ 0..1 trên TOÀN màn hình gốc nên nhân thẳng
        # với preview_w/h hiện tại (không nhân với w/h gốc) là ra đúng vị
        # trí trên canvas.
        overlay = getattr(self, "_step_action_overlay", None)
        if overlay and overlay.get("type") == "region":
            ox1, oy1, ox2, oy2 = overlay["box"]
            px1, py1 = int(ox1 * self.preview_w), int(oy1 * self.preview_h)
            px2, py2 = int(ox2 * self.preview_w), int(oy2 * self.preview_h)
            cv2.rectangle(resized, (px1, py1), (px2, py2), (255, 190, 0), 2)
            cv2.putText(resized, "Vùng quét", (px1 + 3, max(12, py1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 190, 0), 1, cv2.LINE_AA)
        elif overlay and overlay.get("type") == "point":
            ox, oy = overlay["pos"]
            px, py = int(ox * self.preview_w), int(oy * self.preview_h)
            # Chấm tròn + dấu cộng để dễ thấy điểm Tap sẽ bấm vào đâu.
            cv2.circle(resized, (px, py), 10, (0, 140, 255), 2)
            cv2.circle(resized, (px, py), 2, (0, 140, 255), -1)
            cv2.line(resized, (px - 14, py), (px + 14, py), (0, 140, 255), 1)
            cv2.line(resized, (px, py - 14), (px, py + 14), (0, 140, 255), 1)
            cv2.putText(resized, "Tap", (px + 12, max(12, py - 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 140, 255), 1, cv2.LINE_AA)
        elif overlay and overlay.get("type") == "swipe":
            fx, fy = overlay["from"]
            tx, ty = overlay["to"]
            pfx, pfy = int(fx * self.preview_w), int(fy * self.preview_h)
            ptx, pty = int(tx * self.preview_w), int(ty * self.preview_h)
            cv2.arrowedLine(resized, (pfx, pfy), (ptx, pty), (186, 0, 255), 2, tipLength=0.15)
            cv2.circle(resized, (pfx, pfy), 6, (186, 0, 255), 2)
            cv2.putText(resized, "Vuốt", (pfx + 8, max(12, pfy - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (186, 0, 255), 1, cv2.LINE_AA)
        elif overlay and overlay.get("type") == "path":
            # Đường VUỐT NHIỀU ĐIỂM (swipe_path) - nối các điểm bằng mũi tên
            # liên tiếp, đánh số thứ tự từng điểm để dễ phân biệt điểm nào
            # đi trước/sau, giống hệt cách "swipe" vẽ 1 mũi tên nhưng lặp
            # lại cho từng đoạn của cả đường.
            pts = [(int(px * self.preview_w), int(py * self.preview_h)) for px, py in overlay["points"]]
            for i in range(len(pts) - 1):
                cv2.arrowedLine(resized, pts[i], pts[i + 1], (186, 0, 255), 2, tipLength=0.12)
            for i, (px, py) in enumerate(pts):
                cv2.circle(resized, (px, py), 6, (186, 0, 255), 2)
                cv2.putText(resized, str(i + 1), (px + 8, max(12, py - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (186, 0, 255), 1, cv2.LINE_AA)
        elif overlay and overlay.get("type") == "zoom":
            # Vẽ TÂM cử chỉ + 2 mũi tên đối xứng dọc trục "angle" cho thấy
            # 2 "ngón tay" sẽ đi từ bán kính đầu -> bán kính cuối ở đâu -
            # xanh lá = Phóng To (tách ra), xanh dương = Thu Nhỏ (chụm lại).
            ocx, ocy = overlay["center"]
            pcx, pcy = int(ocx * self.preview_w), int(ocy * self.preview_h)
            r1 = overlay.get("start_radius", 70) * self.preview_scale
            r2 = overlay.get("end_radius", 260) * self.preview_scale
            ang = math.radians(overlay.get("angle", 90))
            adx, ady = math.cos(ang), math.sin(ang)
            zoom_in = r2 >= r1
            color = (0, 190, 0) if zoom_in else (255, 120, 0)
            for sign in (-1, 1):
                sx, sy = int(pcx + sign * adx * r1), int(pcy + sign * ady * r1)
                ex, ey = int(pcx + sign * adx * r2), int(pcy + sign * ady * r2)
                cv2.arrowedLine(resized, (sx, sy), (ex, ey), color, 2, tipLength=0.25)
            cv2.circle(resized, (pcx, pcy), 4, color, -1)
            cv2.putText(resized, ("Zoom To" if zoom_in else "Zoom Nho"), (pcx + 8, max(12, pcy - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        self.tk_img = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        # Cho phép cuộn (scrollbar/lăn chuột) khi ảnh đã zoom to hơn khung
        # nhìn hiện tại; khi ảnh nhỏ hơn khung thì scrollregion này vô hại.
        self.canvas.config(scrollregion=(0, 0, self.preview_w, self.preview_h))
        if hasattr(self, "lbl_zoom_info"):
            self.lbl_zoom_info.config(text=f"Zoom: {round(self.preview_zoom * 100)}%")

    def toggle_live_stream(self):
        if not self.is_streaming_active:
            if not self.adb.device_id:
                messagebox.showerror("Lỗi", "Chưa kết nối ADB!")
                return
            self.is_streaming_active = True
            self.btn_toggle_stream.config(text="⏹ DỪNG LIVE", bg="#C62828")
            self.lbl_fps.config(text="FPS: ...", foreground="#0D47A1")
        else:
            self.is_streaming_active = False
            self.btn_toggle_stream.config(text="▶ LIVE", bg="#455A64")
            self.lbl_fps.config(text="FPS: OFF", foreground="gray")

    def _stream_capture_worker(self):
        frame_count, last_t = 0, time.time()
        while True:
            if self.is_streaming_active and self.adb.device_id and not self.is_playing and not self.is_recording_live:
                frame = self.adb.screencap_fast()
                if frame is not None:
                    with self.frame_lock:
                        self.current_screen_cv = frame
                        self.new_frame_ready = True
                    frame_count += 1
                    now = time.time()
                    if now - last_t >= 1.0:
                        fps = round(frame_count / (now - last_t), 1)
                        self.root.after(0, lambda f=fps: self.lbl_fps.config(text=f"FPS: {f}"))
                        frame_count, last_t = 0, now
                else:
                    time.sleep(0.1)
                time.sleep(0.04)
            else:
                time.sleep(0.15)

    def _render_poll_loop(self):
        if self.is_streaming_active and self.new_frame_ready and self.current_screen_cv is not None:
            with self.frame_lock:
                img_to_draw = self.current_screen_cv.copy()
                self.new_frame_ready = False
            self.render_preview(img_to_draw)
        self.root.after(40, self._render_poll_loop)


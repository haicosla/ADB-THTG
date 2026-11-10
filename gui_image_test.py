"""
gui_image_test.py — ImageTestMixin: cửa sổ "🧪 Test Quét Ảnh" (đặt cạnh nút
"🔍 Kiểm Tra OCR") - công cụ CHẨN ĐOÁN nhanh 1 ảnh mẫu mà KHÔNG cần thêm hẳn
1 bước wait_image/if_image vào kịch bản rồi chạy thử cả kịch bản mới biết
ảnh có tìm thấy hay không.

Cách dùng: chọn file ảnh mẫu + tốc độ quét (giây/lần) (+ tuỳ chọn "🖼️ Chọn Vùng
Quét..." để chỉ quét 1 vùng của màn hình, giống ô vùng quét của bước wait_image/
if_image - đổi vùng được cả khi đang quét, vùng hiện khung vàng trên Preview) -> bấm "▶ Bắt Đầu" ->
liên tục chụp màn hình LDPlayer hiện tại, so khớp, rồi ghi từng kết quả vào
Nhật Ký (giống hệt log lúc Chạy Thử) - "Tìm thấy ảnh ... tại (x, y) - khớp
0.87" hoặc "Không thấy ảnh ... (khớp cao nhất 0.42)" - tới khi bấm "⏹ Dừng"
hoặc đóng cửa sổ.

Đây là 1 phần của class MacroStudioApp (xem gui.py), tách theo chức năng
như các Mixin khác - "self." trỏ vào cùng 1 instance MacroStudioApp.
"""
import os
import time
import threading
import numpy as np
import cv2
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dashboard_widgets import ThemedToplevel, Btn3D

from gui_dialogs import _bind_esc_close
from gui_dialogs_ifgroup import RegionPickerDialog
from adb_helper import (
    MATCH_MODES, DEFAULT_MATCH_MODE, match_mode_label, match_mode_from_label, match_mode_short,
)


class ImageTestMixin:

    def open_image_test_dialog(self):
        """Nút '🧪 Test Quét Ảnh' - mở cửa sổ chọn ảnh mẫu + tốc độ quét,
        chạy quét LIÊN TỤC và ghi kết quả ra Nhật Ký cho tới khi bấm Dừng."""
        if getattr(self, "is_playing", False):
            messagebox.showwarning(
                "Lưu ý", "Đang Chạy Thử kịch bản - hãy bấm Dừng kịch bản trước "
                         "khi test ảnh (2 tác vụ cùng chụp màn hình lúc này dễ đá nhau)."
            )
            return
        if getattr(self, "_img_test_running", False):
            # Đã có 1 cửa sổ test đang chạy - đưa lên trước thay vì mở thêm cửa sổ mới.
            try:
                self._img_test_win.lift()
                self._img_test_win.focus_force()
                return
            except Exception:
                pass

        win = ThemedToplevel(self.root)
        self._img_test_win = win
        win.title("🧪 Test Quét Ảnh")
        win.resizable(False, False)
        win.transient(self.root)
        _bind_esc_close(win)

        self._img_test_running = False
        self._img_test_stop_flag = False
        self._img_test_tpl_path = None
        self._img_test_tpl_cv = None
        # VÙNG QUÉT của lần test này: None = toàn màn hình, hoặc [x1,y1,x2,y2] tỉ lệ 0..1 (cùng
        # định dạng step["region"]). Luồng quét đọc lại giá trị này MỖI vòng nên đổi được lúc đang quét.
        self._img_test_region = None
        self._img_test_region_ov = None   # khung vàng vẽ trên Preview (gui_capture.render_preview)

        pad = {"padx": 10, "pady": 5}

        f_pick = ttk.Frame(win)
        f_pick.grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        lbl_path = ttk.Label(f_pick, text="(chưa chọn ảnh)", foreground="#8b96ad", width=42)
        lbl_path.pack(side="left")

        def _pick_image():
            # Mặc định mở ở thư mục "templates" (nơi lưu ảnh mẫu cắt từ Preview) -
            # vẫn chuyển sang thư mục khác được ngay trong hộp thoại.
            tpl_dir = os.path.abspath("templates")
            if not os.path.isdir(tpl_dir):
                tpl_dir = os.path.abspath(".")
            path = filedialog.askopenfilename(
                parent=win,
                title="Chọn ảnh mẫu cần test",
                initialdir=tpl_dir,
                filetypes=[("Ảnh", "*.png *.jpg *.jpeg *.bmp"), ("Tất cả file", "*.*")]
            )
            if not path:
                return
            tpl = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
            if tpl is None:
                messagebox.showerror("Lỗi", "Không đọc được file ảnh này!", parent=win)
                return
            self._img_test_tpl_path = path
            self._img_test_tpl_cv = tpl
            lbl_path.config(text=os.path.basename(path), foreground="#e7ebf3")

        Btn3D(f_pick, text="📂 Chọn Ảnh...", command=_pick_image).pack(side="left", padx=6)

        ttk.Label(win, text="Tốc độ quét (giây/lần):").grid(row=1, column=0, sticky="w", **pad)
        spin_interval = ttk.Spinbox(win, from_=0.05, to=5.0, increment=0.05, width=8)
        try:
            spin_interval.set(round(float(self.spin_all_scan.get()), 2))
        except Exception:
            spin_interval.set(0.30)
        spin_interval.grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(win, text="Độ khớp tối thiểu:").grid(row=2, column=0, sticky="w", **pad)
        spin_conf = ttk.Spinbox(win, from_=0.3, to=0.99, increment=0.05, width=8)
        try:
            spin_conf.set(round(float(self.spin_all_conf.get()), 2))
        except Exception:
            spin_conf.set(0.80)
        spin_conf.grid(row=2, column=1, sticky="w", **pad)

        # KIỂU QUÉT ẢNH (xem adb_helper.MATCH_MODES) - mặc định lấy theo ô "Kiểu
        # quét" ở khung thông số hàng loạt (nếu đang chọn 1 kiểu cụ thể), còn
        # không thì Xám như cũ. Chọn kiểu tốt nhất ở đây rồi đặt cho bước ảnh
        # bằng menu chuột phải -> "Sửa Kiểu Quét Ảnh".
        ttk.Label(win, text="Kiểu quét:").grid(row=3, column=0, sticky="w", **pad)
        cbo_mode = ttk.Combobox(win, values=[v[0] for v in MATCH_MODES.values()], state="readonly", width=24)
        try:
            cbo_mode.set(match_mode_label(self._panel_match_mode()))
        except Exception:
            cbo_mode.set(match_mode_label(DEFAULT_MATCH_MODE))
        cbo_mode.grid(row=3, column=1, sticky="w", **pad)

        # VÙNG QUÉT (tuỳ chọn): chỉ quét 1 vùng của màn hình thay vì toàn màn hình - dùng chính
        # RegionPickerDialog như ô "Giới Hạn Vùng Quét" của bước ảnh; kết quả lưu vào cùng định dạng
        # step["region"] nên test xong đặt y hệt cho bước (menu chuột phải -> vùng quét ảnh).
        f_region = ttk.Frame(win)
        f_region.grid(row=4, column=0, columnspan=2, sticky="w", **pad)
        lbl_region = ttk.Label(f_region, text=self._img_test_region_text(None), width=42)
        lbl_region.pack(side="left")

        def _set_region(box):
            self._img_test_region = box
            self._img_test_region_ov = ({"box": tuple(box)} if box else None)
            lbl_region.config(text=self._img_test_region_text(box))
            scr = getattr(self, "current_screen_cv", None)
            if scr is not None:
                try:
                    self.render_preview(scr)
                except Exception:
                    pass
            if getattr(self, "_img_test_running", False):
                self._log_run("info", f"🧪 Test Quét Ảnh: đổi vùng quét -> {self._img_test_region_text(box)}")

        def _pick_region():
            scr = getattr(self, "current_screen_cv", None)
            if scr is None:
                try:
                    scr = self.adb.screencap_fast() if self.adb.device_id else None
                except Exception:
                    scr = None
            if scr is None:
                messagebox.showwarning(
                    "Lưu ý", "Chưa có ảnh màn hình để chọn vùng - hãy kết nối giả lập và bấm Chụp Màn Hình trước!",
                    parent=win)
                return
            dlg = RegionPickerDialog(win, scr, title="Chọn vùng quét để test", initial_box=self._img_test_region)
            win.wait_window(dlg)
            if dlg.result != "CANCELLED":      # None = bấm "Toàn Màn Hình"
                _set_region(dlg.result)

        Btn3D(f_region, text="🖼️ Chọn Vùng...", command=_pick_region).pack(side="left", padx=(6, 0))
        Btn3D(f_region, text="🖥️ Toàn Màn", command=lambda: _set_region(None)).pack(side="left", padx=(6, 0))

        var_compare = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            win, text="So sánh điểm của MỌI kiểu (để chọn kiểu phù hợp cho ảnh này)",
            variable=var_compare
        ).grid(row=5, column=0, columnspan=2, sticky="w", **pad)

        lbl_status = ttk.Label(win, text="Chưa chạy.", foreground="#8b96ad")
        lbl_status.grid(row=6, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 8))

        f_btn = ttk.Frame(win)
        f_btn.grid(row=7, column=0, columnspan=2, pady=(0, 10))
        btn_start = Btn3D(f_btn, text="▶ Bắt Đầu")
        btn_start.pack(side="left", padx=6)
        btn_stop = Btn3D(f_btn, text="⏹ Dừng", state="disabled")
        btn_stop.pack(side="left", padx=6)

        def _set_running(running):
            self._img_test_running = running
            btn_start.config(state="disabled" if running else "normal")
            btn_stop.config(state="normal" if running else "disabled")
            lbl_status.config(
                text="Đang quét liên tục... (xem Nhật Ký)" if running else "Đã dừng.",
                foreground="#3ddc84" if running else "#757575"
            )

        def _start():
            if self._img_test_tpl_cv is None:
                messagebox.showwarning("Lưu ý", "Hãy chọn 1 ảnh mẫu trước!", parent=win)
                return
            try:
                interval = max(0.05, float(spin_interval.get()))
                conf = max(0.1, min(0.99, float(spin_conf.get())))
            except ValueError:
                messagebox.showerror("Lỗi", "Tốc độ quét/Độ khớp không hợp lệ!", parent=win)
                return
            name = os.path.basename(self._img_test_tpl_path)
            mode = match_mode_from_label(cbo_mode.get(), DEFAULT_MATCH_MODE)
            compare = bool(var_compare.get())
            self._img_test_stop_flag = False
            _set_running(True)
            self._log_run(
                "info",
                f"🧪 Test Quét Ảnh: bắt đầu quét '{name}' mỗi {interval}s (khớp ≥ {conf}, kiểu: {match_mode_label(mode)}, "
                f"{self._img_test_region_text(self._img_test_region)})..."
            )
            threading.Thread(
                target=self._img_test_worker,
                args=(self._img_test_tpl_cv, name, interval, conf, mode, compare),
                daemon=True
            ).start()

        def _stop():
            self._img_test_stop_flag = True

        btn_start.config(command=_start)
        btn_stop.config(command=_stop)

        def _on_close():
            self._img_test_stop_flag = True
            self._img_test_region_ov = None      # tắt khung vàng vùng quét trên Preview
            win.destroy()
            scr = getattr(self, "current_screen_cv", None)
            if scr is not None:
                try:
                    self.render_preview(scr)
                except Exception:
                    pass

        win.protocol("WM_DELETE_WINDOW", _on_close)
        # Đặt lệch sang PHẢI (không đè lên Màn Hình Preview ở bên trái) để nhìn thấy
        # khung đánh dấu vị trí tìm thấy ảnh ngay khi đang quét.
        win.geometry(f"+{self.root.winfo_rootx() + max(150, self.root.winfo_width() - 520)}+{self.root.winfo_rooty() + 120}")

        # Cho vòng lặp nền biết cách BÁO LẠI cho UI khi tự dừng (vd lỗi liên
        # tục) - gán ở đây vì mỗi lần mở dialog là 1 bộ widget mới.
        self._img_test_on_stopped = lambda: (_set_running(False) if win.winfo_exists() else None)

    def _img_test_worker(self, tpl_cv, name, interval, conf, mode=DEFAULT_MATCH_MODE, compare=False):
        """Chạy trong THREAD NỀN - liên tục screencap + so khớp, ghi từng
        kết quả vào Nhật Ký qua self._log_run (tự điều phối về main thread).
        Dừng khi self._img_test_stop_flag được bật (bấm Dừng/đóng cửa sổ)."""
        count = 0
        tpl_h, tpl_w = tpl_cv.shape[:2]
        warned_small = None     # vùng quét đã cảnh báo "nhỏ hơn ảnh mẫu" (chỉ báo 1 lần/vùng)
        while not self._img_test_stop_flag:
            count += 1
            all_scores = None
            screen = None
            # Đọc lại vùng quét MỖI vòng: đổi vùng giữa chừng có hiệu lực ngay, không cần Dừng/Bắt Đầu lại.
            region = self._img_test_region
            try:
                # Chụp 1 LẦN rồi quét ngay trên khung hình đó (truyền screen=...) để
                # khung đánh dấu vẽ lên Preview khớp đúng ảnh vừa quét.
                screen = self.adb.screencap_fast()
                if region and screen is not None and warned_small != tuple(region):
                    sh_px, sw_px = screen.shape[:2]
                    if (region[2] - region[0]) * sw_px < tpl_w or (region[3] - region[1]) * sh_px < tpl_h:
                        warned_small = tuple(region)
                        self._log_run(
                            "warn",
                            f"🧪 Vùng quét ({self._img_test_region_text(region)}) NHỎ HƠN ảnh mẫu "
                            f"({tpl_w}x{tpl_h}px) nên không thể khớp - hãy chọn vùng lớn hơn."
                        )
                if compare:
                    # 1 lần chụp, tính điểm theo MỌI kiểu quét để so sánh.
                    pos, score, all_scores = self.adb.find_image_all_modes(tpl_cv, threshold=conf, region=region, mode=mode, screen=screen)
                else:
                    pos, score = self.adb.find_image_on_screen(tpl_cv, threshold=conf, region=region, mode=mode, screen=screen)
            except Exception as e:
                self._log_run("error", f"🧪 Test Quét Ảnh: lỗi khi quét - {e}")
                pos, score = None, 0.0
            self._img_test_push_preview(screen, pos, score, tpl_w, tpl_h)
            # Điểm hiện 3 chữ số thập phân (trước đây .2f làm tròn 0.998 thành
            # "1.00" nên 2 ảnh KHÁC nhau vẫn trông như khớp tuyệt đối).
            if pos:
                # Thêm toạ độ điểm ảnh (px) cạnh toạ độ tỉ lệ 0..1 cho dễ đối chiếu.
                sw, sh = (self.adb.screen_w or 0), (self.adb.screen_h or 0)
                px_txt = f" ≈ {round(pos[0] * sw)},{round(pos[1] * sh)}px" if sw and sh else ""
                self._log_run(
                    "success",
                    f"🧪 [{count}] Tìm thấy ảnh '{name}' tại ({pos[0]:.3f}, {pos[1]:.3f}){px_txt} - khớp {score:.3f} [{match_mode_short(mode)}]"
                )
            else:
                self._log_run(
                    "warn",
                    f"🧪 [{count}] Không thấy ảnh '{name}' (khớp cao nhất {score:.3f} [{match_mode_short(mode)}], cần ≥ đã đặt)"
                )
            if all_scores:
                self._log_run(
                    "info",
                    "     ↳ điểm từng kiểu: " + " | ".join(f"{match_mode_short(m)} {v:.3f}" for m, v in all_scores.items())
                )
            time.sleep(interval)
        self._log_run("info", f"🧪 Test Quét Ảnh: đã dừng (quét {count} lần).")
        try:
            self.root.after(0, self._img_test_clear_overlay)
        except Exception:
            pass
        cb = getattr(self, "_img_test_on_stopped", None)
        if cb:
            self.root.after(0, cb)

    @staticmethod
    def _img_test_region_text(box):
        """'Vùng quét: toàn màn hình' hoặc 'Vùng quét: 10%,20% → 80%,90%' (cùng cách hiển thị ô vùng quét của bước ảnh)."""
        if not box:
            return "Vùng quét: toàn màn hình"
        x1, y1, x2, y2 = box
        return f"Vùng quét: {int(x1*100)}%,{int(y1*100)}% → {int(x2*100)}%,{int(y2*100)}%"

    def _img_test_push_preview(self, screen, pos, score, tpl_w, tpl_h):
        """Gọi từ THREAD NỀN của _img_test_worker: xếp lịch (root.after) để MAIN
        THREAD vẽ lại Preview bằng đúng khung hình vừa quét + khung đánh dấu VỊ TRÍ
        TÌM THẤY (nếu có). Chỉ giữ payload MỚI NHẤT - quét nhanh hơn tốc độ vẽ thì
        bỏ bớt khung cũ thay vì dồn hàng đợi."""
        overlay = None
        sw = self.adb.screen_w or (screen.shape[1] if screen is not None else 0)
        sh = self.adb.screen_h or (screen.shape[0] if screen is not None else 0)
        if pos and sw and sh:
            hw, hh = (tpl_w / 2.0) / sw, (tpl_h / 2.0) / sh
            overlay = {"box": (pos[0] - hw, pos[1] - hh, pos[0] + hw, pos[1] + hh),
                       "center": pos, "score": score}
        self._img_test_latest = (screen, overlay)
        if getattr(self, "_img_test_render_pending", False):
            return
        self._img_test_render_pending = True

        def _apply():
            self._img_test_render_pending = False
            latest = getattr(self, "_img_test_latest", None)
            if not latest or self._img_test_stop_flag:
                return
            scr, ov = latest
            self._img_test_overlay = ov
            if scr is not None:
                self.current_screen_cv = scr
                try:
                    self.render_preview(scr)
                except Exception:
                    pass

        try:
            self.root.after(0, _apply)
        except Exception:
            self._img_test_render_pending = False

    def _img_test_clear_overlay(self):
        """Xoá khung đánh dấu khỏi Preview khi Test Quét Ảnh dừng/đóng cửa sổ."""
        self._img_test_overlay = None
        self._img_test_latest = None
        self._img_test_render_pending = False
        scr = getattr(self, "current_screen_cv", None)
        if scr is not None:
            try:
                self.render_preview(scr)
            except Exception:
                pass

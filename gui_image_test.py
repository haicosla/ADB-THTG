"""
gui_image_test.py — ImageTestMixin: cửa sổ "🧪 Test Quét Ảnh" (đặt cạnh nút
"🔍 Kiểm Tra OCR") - công cụ CHẨN ĐOÁN nhanh 1 ảnh mẫu mà KHÔNG cần thêm hẳn
1 bước wait_image/if_image vào kịch bản rồi chạy thử cả kịch bản mới biết
ảnh có tìm thấy hay không.

Cách dùng: chọn file ảnh mẫu + tốc độ quét (giây/lần) -> bấm "▶ Bắt Đầu" ->
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

from gui_dialogs import _bind_esc_close


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

        win = tk.Toplevel(self.root)
        self._img_test_win = win
        win.title("🧪 Test Quét Ảnh")
        win.resizable(False, False)
        win.transient(self.root)
        _bind_esc_close(win)

        self._img_test_running = False
        self._img_test_stop_flag = False
        self._img_test_tpl_path = None
        self._img_test_tpl_cv = None

        pad = {"padx": 10, "pady": 5}

        f_pick = ttk.Frame(win)
        f_pick.grid(row=0, column=0, columnspan=2, sticky="w", **pad)
        lbl_path = ttk.Label(f_pick, text="(chưa chọn ảnh)", foreground="#757575", width=42)
        lbl_path.pack(side="left")

        def _pick_image():
            path = filedialog.askopenfilename(
                title="Chọn ảnh mẫu cần test",
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
            lbl_path.config(text=os.path.basename(path), foreground="black")

        ttk.Button(f_pick, text="📂 Chọn Ảnh...", command=_pick_image).pack(side="left", padx=6)

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

        lbl_status = ttk.Label(win, text="Chưa chạy.", foreground="#757575")
        lbl_status.grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 8))

        f_btn = ttk.Frame(win)
        f_btn.grid(row=4, column=0, columnspan=2, pady=(0, 10))
        btn_start = ttk.Button(f_btn, text="▶ Bắt Đầu")
        btn_start.pack(side="left", padx=6)
        btn_stop = ttk.Button(f_btn, text="⏹ Dừng", state="disabled")
        btn_stop.pack(side="left", padx=6)

        def _set_running(running):
            self._img_test_running = running
            btn_start.config(state="disabled" if running else "normal")
            btn_stop.config(state="normal" if running else "disabled")
            lbl_status.config(
                text="Đang quét liên tục... (xem Nhật Ký)" if running else "Đã dừng.",
                foreground="#2E7D32" if running else "#757575"
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
            self._img_test_stop_flag = False
            _set_running(True)
            self._log_run("info", f"🧪 Test Quét Ảnh: bắt đầu quét '{name}' mỗi {interval}s (khớp ≥ {conf})...")
            threading.Thread(
                target=self._img_test_worker,
                args=(self._img_test_tpl_cv, name, interval, conf),
                daemon=True
            ).start()

        def _stop():
            self._img_test_stop_flag = True

        btn_start.config(command=_start)
        btn_stop.config(command=_stop)

        def _on_close():
            self._img_test_stop_flag = True
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close)
        win.geometry(f"+{self.root.winfo_rootx() + 150}+{self.root.winfo_rooty() + 120}")

        # Cho vòng lặp nền biết cách BÁO LẠI cho UI khi tự dừng (vd lỗi liên
        # tục) - gán ở đây vì mỗi lần mở dialog là 1 bộ widget mới.
        self._img_test_on_stopped = lambda: (_set_running(False) if win.winfo_exists() else None)

    def _img_test_worker(self, tpl_cv, name, interval, conf):
        """Chạy trong THREAD NỀN - liên tục screencap + so khớp, ghi từng
        kết quả vào Nhật Ký qua self._log_run (tự điều phối về main thread).
        Dừng khi self._img_test_stop_flag được bật (bấm Dừng/đóng cửa sổ)."""
        count = 0
        while not self._img_test_stop_flag:
            count += 1
            try:
                pos, score = self.adb.find_image_on_screen(tpl_cv, threshold=conf)
            except Exception as e:
                self._log_run("error", f"🧪 Test Quét Ảnh: lỗi khi quét - {e}")
                pos, score = None, 0.0
            if pos:
                self._log_run(
                    "success",
                    f"🧪 [{count}] Tìm thấy ảnh '{name}' tại ({pos[0]:.3f}, {pos[1]:.3f}) - khớp {score:.2f}"
                )
            else:
                self._log_run(
                    "warn",
                    f"🧪 [{count}] Không thấy ảnh '{name}' (khớp cao nhất {score:.2f}, cần ≥ đã đặt)"
                )
            time.sleep(interval)
        self._log_run("info", f"🧪 Test Quét Ảnh: đã dừng (quét {count} lần).")
        cb = getattr(self, "_img_test_on_stopped", None)
        if cb:
            self.root.after(0, cb)

"""
Điểm khởi chạy chương trình LD Macro Studio.

File này CHỈ có nhiệm vụ khởi tạo cửa sổ Tkinter và chạy ứng dụng.
- Toàn bộ giao diện nằm ở gui.py (MacroStudioApp).
- Các tính năng chi tiết nằm ở các module riêng:
    adb_helper.py         -> giao tiếp ADB (tap/swipe/gõ phím/chụp màn hình)
    logic_engine.py        -> chạy kịch bản (IF/ELSE/GROUP/lặp...)
    window_finder.py        -> tìm cửa sổ LDPlayer & quy đổi tọa độ
    recorder.py              -> ghi thao tác chuột + bàn phím trực tiếp (F7)
    step_list_controls.py    -> kéo-thả sắp xếp & Ctrl+C/X/V trên danh sách bước
    capture_tools.py         -> cắt ảnh mẫu từ màn hình preview
"""
import ctypes
import tkinter as tk

from gui import MacroStudioApp


def _set_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


if __name__ == "__main__":
    _set_dpi_awareness()
    root = tk.Tk()
    app = MacroStudioApp(root)
    root.mainloop()

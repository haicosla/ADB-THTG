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
import os
import tkinter as tk

# QUAN TRỌNG: mọi nơi trong dự án (accounts.json, task_registry.json,
# tasks/, templates/, groups/, logs/...) đều dùng ĐƯỜNG DẪN TƯƠNG ĐỐI, tức
# phụ thuộc "thư mục làm việc hiện tại" (current working directory) lúc
# chạy - KHÔNG tự neo theo vị trí thật của file main.py. Bấm đúp trực tiếp
# main.py thường tự set cwd đúng, nhưng chạy qua shortcut/.bat có "Start
# in" khác, qua IDE, hoặc copy nguyên bộ dự án sang máy khác rồi khởi chạy
# theo cách khác thì cwd có thể LỆCH khỏi thư mục dự án -> toàn bộ tài
# khoản/tác vụ/ảnh mẫu "biến mất" dù file vẫn còn nguyên trên đĩa. Ép cwd về
# đúng thư mục chứa main.py ngay từ dòng đầu tiên để đảm bảo LUÔN đúng, bất
# kể chạy bằng cách nào hay trên máy nào.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

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

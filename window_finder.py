import win32gui
import win32con
import win32process
import psutil


class WindowFinder:
    """Tìm cửa sổ LDPlayer đang chạy và quy đổi tọa độ chuột thật (toàn màn hình)
    sang tọa độ chuẩn hóa (0..1) trên khung hình render của giả lập.

    Tách riêng module này để cả giao diện (gui.py) và bộ ghi thao tác
    (recorder.py) đều dùng chung một nguồn quy đổi tọa độ duy nhất.
    """

    def __init__(self, adb):
        self.adb = adb
        self.main_hwnd = None
        self.render_hwnd = None

    def find_ld_windows(self):
        """Quét lại và cập nhật self.main_hwnd / self.render_hwnd.
        Trả về tuple (main_hwnd, title) - main_hwnd = None nếu không tìm thấy."""
        self.main_hwnd = None
        self.render_hwnd = None
        found_title = {"value": None}

        def enum_win(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            cls = win32gui.GetClassName(hwnd).strip()
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                pname = psutil.Process(pid).name().lower()
            except Exception:
                pname = ""

            if (pname == "dnplayer.exe" or pname == "ldplayer.exe") and cls == "LDPlayerMainFrame":
                self.main_hwnd = hwnd
                found_title["value"] = win32gui.GetWindowText(hwnd).strip()

                def enum_child(c_hwnd, _):
                    c_cls = win32gui.GetClassName(c_hwnd).strip()
                    if "render" in c_cls.lower():
                        self.render_hwnd = c_hwnd
                    return True

                win32gui.EnumChildWindows(hwnd, enum_child, None)
            return True

        try:
            win32gui.EnumWindows(enum_win, None)
        except Exception:
            pass

        return self.main_hwnd, found_title["value"]

    def attach_hwnd(self, main_hwnd):
        """Gán trực tiếp main_hwnd ĐÃ BIẾT TRƯỚC (vd lấy từ `ldconsole
        list2` qua emulator_manager.py) thay vì phải quét EnumWindows theo
        tên tiến trình/class như find_ld_windows(). CẦN THIẾT khi chạy ĐA
        LUỒNG nhiều cửa sổ LDPlayer giống hệt nhau cùng lúc: find_ld_windows()
        gốc chỉ tìm được 1 cửa sổ đầu tiên khớp class name trên toàn hệ
        thống, không phân biệt được cửa sổ nào ứng với giả lập/luồng nào.

        Trả về True nếu hwnd hợp lệ và đã gán được main_hwnd (kể cả khi
        không tìm thấy render_hwnd con - lúc đó get_render_screen_rect() /
        win_coords_to_norm() sẽ tự dùng main_hwnd thay thế)."""
        self.main_hwnd = None
        self.render_hwnd = None
        if not main_hwnd or not win32gui.IsWindow(main_hwnd):
            return False
        self.main_hwnd = main_hwnd

        def enum_child(c_hwnd, _):
            c_cls = win32gui.GetClassName(c_hwnd).strip()
            if "render" in c_cls.lower():
                self.render_hwnd = c_hwnd
            return True

        try:
            win32gui.EnumChildWindows(main_hwnd, enum_child, None)
        except Exception:
            pass
        return True

    def get_render_screen_rect(self):
        """Trả về (screen_x, screen_y, width, height) - vùng THẬT trên màn
        hình chứa khung hình game đang render (đã trừ viền đen letterbox nếu
        có), dùng để đặt overlay thông báo ĐÈ LÊN đúng game thay vì hiện ở
        chỗ khác trên desktop. Tính toán y hệt win_coords_to_norm() nhưng
        theo chiều ngược lại (từ tỉ lệ khung ra toạ độ màn hình thật)."""
        target_h = self.render_hwnd if (self.render_hwnd and win32gui.IsWindow(self.render_hwnd)) else self.main_hwnd
        if not target_h or not win32gui.IsWindow(target_h):
            return None

        pt_origin = win32gui.ClientToScreen(target_h, (0, 0))
        c_rect = win32gui.GetClientRect(target_h)
        c_w = c_rect[2] - c_rect[0]
        c_h = c_rect[3] - c_rect[1]
        if c_w <= 0 or c_h <= 0:
            return None

        target_ratio = self.adb.screen_w / self.adb.screen_h
        client_ratio = c_w / c_h

        if client_ratio > target_ratio:
            actual_w = c_h * target_ratio
            actual_h = c_h
            offset_x = (c_w - actual_w) / 2.0
            offset_y = 0.0
        else:
            actual_w = c_w
            actual_h = c_w / target_ratio
            offset_x = 0.0
            offset_y = (c_h - actual_h) / 2.0

        return int(pt_origin[0] + offset_x), int(pt_origin[1] + offset_y), int(actual_w), int(actual_h)

    def win_coords_to_norm(self, sx, sy):
        """Quy đổi tọa độ (sx, sy) trên màn hình thật sang tọa độ chuẩn hóa (0..1)
        bên trong khung hình giả lập. Trả về (None, None) nếu ngoài khung hoặc
        chưa tìm thấy cửa sổ."""
        target_h = self.render_hwnd if (self.render_hwnd and win32gui.IsWindow(self.render_hwnd)) else self.main_hwnd
        if not target_h or not win32gui.IsWindow(target_h):
            return None, None

        pt_origin = win32gui.ClientToScreen(target_h, (0, 0))
        c_rect = win32gui.GetClientRect(target_h)
        c_w = c_rect[2] - c_rect[0]
        c_h = c_rect[3] - c_rect[1]

        if c_w <= 0 or c_h <= 0:
            return None, None

        target_ratio = self.adb.screen_w / self.adb.screen_h
        client_ratio = c_w / c_h

        if client_ratio > target_ratio:
            actual_w = c_h * target_ratio
            actual_h = c_h
            offset_x = (c_w - actual_w) / 2.0
            offset_y = 0.0
        else:
            actual_w = c_w
            actual_h = c_w / target_ratio
            offset_x = 0.0
            offset_y = (c_h - actual_h) / 2.0

        rel_x = sx - (pt_origin[0] + offset_x)
        rel_y = sy - (pt_origin[1] + offset_y)

        if 0 <= rel_x <= actual_w and 0 <= rel_y <= actual_h:
            return round(rel_x / actual_w, 4), round(rel_y / actual_h, 4)

        return None, None

    def ensure_window_visible(self):
        """Khôi phục cửa sổ LDPlayer nếu đang bị THU NHỎ (minimized).

        NHIỀU BẢN LDPLAYER TẠM DỪNG XỬ LÝ THAO TÁC CHẠM/VUỐT gửi qua ADB khi
        cửa sổ đang thu nhỏ - trong khi `adb exec-out screencap` vẫn đọc
        được framebuffer bình thường (đọc thẳng bộ nhớ, không qua hàng đợi
        input). Hậu quả: kịch bản chạy 'như bình thường' (chụp ảnh, so khớp
        ảnh mẫu OK) nhưng KHÔNG có bất kỳ thao tác tap/swipe nào thực sự tác
        động lên giả lập - rất dễ xảy ra khi chạy Dashboard đa luồng nhiều
        giả lập cùng lúc và 1 trong số đó bị thu nhỏ.

        Gọi hàm này TRƯỚC khi bắt đầu chạy 1 tác vụ. Trả về True nếu VỪA
        khôi phục (đang bị thu nhỏ), False nếu không cần (đã hiện sẵn) hoặc
        không tìm thấy cửa sổ."""
        target_h = self.main_hwnd
        if not target_h or not win32gui.IsWindow(target_h):
            return False
        try:
            if win32gui.IsIconic(target_h):
                win32gui.ShowWindow(target_h, win32con.SW_RESTORE)
                return True
        except Exception:
            pass
        return False

    def is_ld_focused(self):
        """True nếu cửa sổ LDPlayer (khung chính hoặc khung render) đang là
        cửa sổ đang được focus trên Windows. Dùng để chỉ ghi lại thao tác
        BÀN PHÍM khi người dùng thật sự đang thao tác trên giả lập, tương tự
        cách chuột đã được lọc theo tọa độ trong win_coords_to_norm - tránh
        ghi nhầm phím gõ ở cửa sổ khác (vd đang gõ vào 1 hộp thoại của app)."""
        try:
            fg_hwnd = win32gui.GetForegroundWindow()
        except Exception:
            return False

        if not fg_hwnd:
            return False

        if self.main_hwnd and fg_hwnd == self.main_hwnd:
            return True
        if self.render_hwnd and fg_hwnd == self.render_hwnd:
            return True

        # Một số bản LDPlayer có thể có cửa sổ con khác đang focus (vd render
        # nằm trong 1 khung trung gian) -> kiểm tra thêm xem fg_hwnd có phải
        # là con cháu của main_hwnd hay không.
        if self.main_hwnd:
            try:
                parent = fg_hwnd
                for _ in range(6):
                    if parent == self.main_hwnd:
                        return True
                    parent = win32gui.GetParent(parent)
                    if not parent:
                        break
            except Exception:
                pass

        return False
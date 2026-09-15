import os
import subprocess
import shutil
import time
import cv2
import numpy as np
import psutil

try:
    import pytesseract
    _HAS_PYTESSERACT_LIB = True
except ImportError:
    pytesseract = None
    _HAS_PYTESSERACT_LIB = False


def _project_root_dir():
    """Thư mục chứa file .py này (nơi main.py và các module khác đang nằm,
    cũng LÀ nơi platform-tools/ và Tesseract-OCR/ được đặt CÙNG CẤP khi
    đóng gói dự án dạng portable) - dùng làm nơi ƯU TIÊN dò sẵn adb.exe /
    tesseract.exe, thay vì chỉ trông chờ vào việc cài đặt hệ thống hoặc các
    đường dẫn ổ đĩa cố định (vd C:\\leidian...) vốn không đúng trên mọi máy.

    TRƯỚC ĐÂY hàm này trả về thư mục CHA của thư mục dự án (đi lên thêm 1
    cấp nữa ngoài ý muốn) -> không bao giờ tìm thấy platform-tools/
    Tesseract-OCR nằm NGAY TRONG thư mục dự án khi copy nguyên bộ sang máy
    khác (chỉ "chạy được" trên máy cũ nhờ tình cờ LDPlayer đang mở sẵn hoặc
    adb có trong PATH hệ thống, che giấu mất lỗi này)."""
    return os.path.dirname(os.path.abspath(__file__))


# Các đường dẫn cài đặt Tesseract-OCR phổ biến trên Windows - thử lần lượt
# trước khi trông chờ vào PATH hệ thống. Ưu tiên bản portable đặt sẵn ở
# THƯ MỤC CHA của dự án (xem _project_root_dir) TRƯỚC các đường dẫn cài đặt
# hệ thống cố định bên dưới, vì đây là nơi người dùng CHỦ ĐỘNG đặt sẵn cho
# đúng máy này, không phụ thuộc ổ đĩa/tên thư mục cài đặt mặc định.
_TESSERACT_CANDIDATE_PATHS = [
    os.path.join(_project_root_dir(), "tesseract.exe"),
    os.path.join(_project_root_dir(), "Tesseract-OCR", "tesseract.exe"),
    os.path.join(_project_root_dir(), "tesseract", "tesseract.exe"),
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]

_HAS_TESSERACT = False
_TESSERACT_INIT_ERROR = ""

if _HAS_PYTESSERACT_LIB:
    _found_path = next((p for p in _TESSERACT_CANDIDATE_PATHS if os.path.exists(p)), None)
    if not _found_path:
        _found_path = shutil.which("tesseract")
    if _found_path:
        pytesseract.pytesseract.tesseract_cmd = _found_path

    # QUAN TRỌNG: TRƯỚC ĐÂY cứ import được thư viện pytesseract là coi như
    # "_HAS_TESSERACT = True" và ép cứng tesseract_cmd vào 1 đường dẫn cố
    # định, KHÔNG hề kiểm tra file đó có thật sự tồn tại/chạy được không.
    # Nếu người dùng cài Tesseract-OCR ở nơi khác (vd Program Files (x86),
    # hoặc không cài ở nơi mặc định), mọi lần OCR sẽ ngầm lỗi - lỗi đó vẫn bị
    # try/except bên trong ocr_text_in_box() bắt lại và trả về chuỗi lỗi, NÊN
    # KHÔNG PHẢI nguyên nhân của việc biến OCR ra "" (rỗng) mà không có lỗi
    # gì hiển thị - nếu bạn thấy log ghi 'OCR -> biến ... = ""' (rỗng, không
    # có dòng "Lỗi khi quét OCR"), nghĩa là Tesseract ĐÃ CHẠY nhưng KHÔNG ĐỌC
    # RA CHỮ NÀO trong vùng đã cắt (xem ocr_text_in_box() bên dưới để biết
    # cách chẩn đoán qua ảnh debug đã lưu). Việc kiểm tra thật sự bằng
    # get_tesseract_version() ở đây chỉ để phát hiện SỚM trường hợp Tesseract
    # hoàn toàn chưa cài/không gọi được, và báo lỗi rõ ràng thay vì im lặng.
    try:
        pytesseract.get_tesseract_version()
        _HAS_TESSERACT = True
    except Exception as e:
        _HAS_TESSERACT = False
        _TESSERACT_INIT_ERROR = str(e)
else:
    _TESSERACT_INIT_ERROR = "Chưa cài thư viện pytesseract (pip install pytesseract)"


class ADBHelper:
    def __init__(self):
        self.adb_path = self.detect_adb()
        self.device_id = None
        self.screen_w = 720
        self.screen_h = 1280
        self._sdk_version = None

    def detect_adb(self):
        # 1) ƯU TIÊN CAO NHẤT: bản adb.exe mang theo CÙNG dự án, đặt ở THƯ
        # MỤC CHA (1 cấp trên thư mục chứa mã nguồn, vd .../MyApp/adb_helper.py
        # thì tìm ở .../adb.exe, .../adb/adb.exe hoặc .../platform-tools/adb.exe).
        # Đây là đường dẫn NGƯỜI DÙNG TỰ ĐẶT SẴN cho đúng máy này nên đáng tin
        # cậy hơn cả việc dò tiến trình lẫn các đường dẫn ổ đĩa cố định bên
        # dưới (trước đây chỉ dò C:\leidian / D:\leidian - máy nào cài
        # LDPlayer ở ổ khác, vd H:\LDPlayer như PROJECT_CONTEXT.md, sẽ không
        # tìm thấy gì và rơi về "adb" trần trơ, lỗi ngay nếu adb không có
        # trong PATH hệ thống).
        root_dir = _project_root_dir()
        for rel in ("adb.exe", os.path.join("adb", "adb.exe"), os.path.join("platform-tools", "adb.exe")):
            candidate = os.path.join(root_dir, rel)
            if os.path.exists(candidate):
                return candidate

        # 2) Dò qua tiến trình dnplayer.exe ĐANG CHẠY (chắc chắn đúng bản
        # LDPlayer thật sự đang dùng trên máy, nếu giả lập đã mở sẵn).
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                if proc.info['name'] and 'dnplayer.exe' in proc.info['name'].lower():
                    ld_dir = os.path.dirname(proc.info['exe'])
                    candidate = os.path.join(ld_dir, "adb.exe")
                    if os.path.exists(candidate):
                        return candidate
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # 3) Vài đường dẫn cài đặt mặc định phổ biến (fallback cuối cùng - có
        # thể sai trên máy cài ở ổ đĩa khác, xem mục 1 ở trên).
        for path in [r"C:\leidian\LDPlayer9\adb.exe", r"D:\leidian\LDPlayer9\adb.exe"]:
            if os.path.exists(path):
                return path
        return "adb"

    def run_cmd(self, args):
        cmd = [self.adb_path]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(args)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
        return proc.stdout

    def run_cmd_full(self, args):
        """Giống run_cmd nhưng trả về (stdout_text, stderr_text, returncode).
        Cần dùng khi phải BIẾT CHẮC lệnh adb có thật sự chạy thành công hay
        không (vd input keycombination) - subprocess.run mặc định không tự
        ném exception khi tiến trình adb trả về lỗi, nên nếu chỉ dùng
        run_cmd() thông thường thì lỗi sẽ bị bỏ qua trong im lặng."""
        cmd = [self.adb_path]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(args)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=startupinfo)
        out = proc.stdout.decode("utf-8", errors="ignore")
        err = proc.stderr.decode("utf-8", errors="ignore")
        return out, err, proc.returncode

    def get_sdk_version(self):
        """Trả về SDK version (vd 28, 31) của thiết bị hiện tại, có cache lại.
        Dùng để biết trước liệu 'input keycombination' (Ctrl+phím giữ đồng
        thời) có được hỗ trợ hay không - lệnh này CHỈ chạy được từ Android 12
        (API 31) trở lên."""
        if self._sdk_version is not None:
            return self._sdk_version
        try:
            out, _, rc = self.run_cmd_full(["shell", "getprop", "ro.build.version.sdk"])
            self._sdk_version = int(out.strip()) if rc == 0 else 0
        except Exception:
            self._sdk_version = 0
        return self._sdk_version

    def is_keycombo_supported(self):
        return self.get_sdk_version() >= 31

    def get_devices(self):
        try:
            out = self.run_cmd(["devices"]).decode("utf-8", errors="ignore")
            lines = out.strip().split("\n")[1:]
            return [l.split()[0] for l in lines if "\tdevice" in l]
        except Exception:
            return []

    def update_resolution(self):
        try:
            out = self.run_cmd(["shell", "wm", "size"]).decode("utf-8", errors="ignore")
            for line in out.splitlines():
                if "Physical size:" in line or "Override size:" in line:
                    parts = line.split(":")[-1].strip().split("x")
                    self.screen_w = int(parts[0])
                    self.screen_h = int(parts[1])
        except Exception:
            pass

        # QUAN TRỌNG - LÝ DO "chạy ở Dashboard bị lệch tọa độ, chạy ở app
        # chính (gui.py) vẫn đúng":
        # `adb shell wm size` trả về kích thước LOGIC của Android, đôi khi
        # KHÁC với kích thước PIXEL THẬT của ảnh chụp màn hình (vd do
        # LDPlayer áp DPI/resolution override cho từng giả lập) - trong khi
        # tap()/swipe() tính toạ độ pixel bằng cách nhân tỉ lệ (0..1) với
        # self.screen_w/h, và tỉ lệ (0..1) đó lại được TẠO RA lúc ghi/chọn
        # điểm trên khung preview trong gui.py dựa trên đúng KÍCH THƯỚC ẢNH
        # CHỤP MÀN HÌNH thật (screencap), KHÔNG dựa trên 'wm size'.
        # Nếu 2 kích thước lệch nhau dù chỉ 1 chút, MỌI thao tác tap/swipe
        # phát lại sẽ bị lệch tọa độ theo đúng tỉ lệ lệch đó.
        # - Ở app chính (gui.py): trước khi người dùng bấm "Chạy Thử", màn
        #   hình Preview đã tự chụp/refresh nhiều lần rồi (Live/preview),
        #   nên self.screen_w/h ĐÃ ĐƯỢC ảnh chụp thật ghi đè đúng từ trước.
        # - Ở Dashboard (đa luồng): mỗi luồng tạo ADBHelper() MỚI rồi chạy
        #   kịch bản NGAY, chưa từng chụp màn hình lần nào trước đó, nên vẫn
        #   dùng nguyên số liệu (có thể sai) từ 'wm size' cho tới tận bước
        #   ảnh đầu tiên (wait_image/if_image) - nếu kịch bản có TAP/SWIPE
        #   trước bước ảnh đầu tiên thì các bước đó sẽ bị lệch.
        # -> Luôn chụp thử 1 tấm ảnh THẬT ngay tại đây để screen_w/h khớp
        # đúng kích thước pixel thật ngay từ đầu, bất kể gọi từ đâu.
        try:
            self.screencap_fast()
        except Exception:
            pass

    def tap(self, x, y):
        if 0.0 <= float(x) <= 1.0 and 0.0 <= float(y) <= 1.0:
            rx = int(float(x) * self.screen_w)
            ry = int(float(y) * self.screen_h)
        else:
            rx = int(float(x))
            ry = int(float(y))
        self.run_cmd(["shell", "input", "tap", str(rx), str(ry)])

    def tap_fast(self, x, y):
        """Giống tap() nhưng BẮN LỆNH ĐI NGAY (fire-and-forget), KHÔNG chờ
        tiến trình adb.exe chạy xong hẳn rồi mới trả quyền điều khiển lại
        cho code gọi - trong khi tap() thường dùng run_cmd() -> subprocess.
        run() vốn LUÔN CHỜ tiến trình adb.exe kết nối, gửi lệnh, nhận phản
        hồi rồi thoát hẳn mới thôi (an toàn, biết chắc lệnh đã chạy, nhưng
        cộng thêm 1 khoảng round-trip mỗi lần gọi).

        DÙNG RIÊNG cho bước "Tìm & Click 1 ảnh" (wait_image) NGAY SAU KHI
        vừa phát hiện ảnh - đây là bước cần PHẢN XẠ NHANH NHẤT có thể vì ảnh
        có thể chỉ hiện trên màn hình trong thời gian rất ngắn (vd 0.5s),
        nên chấp nhận đánh đổi: không đợi xác nhận adb.exe đã thoát/có lỗi
        gì hay không, miễn là lệnh tap được ĐẨY ĐI SỚM NHẤT có thể, để giảm
        tối đa khoảng thời gian từ lúc script BIẾT đã thấy ảnh tới lúc thao
        tác chạm THỰC SỰ được gửi đi. Các nơi khác (tap/swipe thủ công,
        if_image, multi_image...) vẫn dùng tap() thường như cũ - không đổi
        hành vi ở đó theo đúng yêu cầu chỉ tối ưu riêng cho tìm-và-click 1
        ảnh."""
        if 0.0 <= float(x) <= 1.0 and 0.0 <= float(y) <= 1.0:
            rx = int(float(x) * self.screen_w)
            ry = int(float(y) * self.screen_h)
        else:
            rx = int(float(x))
            ry = int(float(y))
        cmd = [self.adb_path]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(["shell", "input", "tap", str(rx), str(ry)])
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)

    def tap_px(self, x_px, y_px):
        """Giống tap() nhưng LUÔN coi (x_px, y_px) là TOẠ ĐỘ PIXEL TUYỆT ĐỐI,
        bỏ qua hẳn kiểm tra "0..1 = tỉ lệ" của tap() thường - dùng khi toạ
        độ đã được TỰ TÍNH TOÁN từ trước (vd: tâm ảnh tìm thấy + độ lệch
        click_offset người dùng đặt), vì kết quả cộng thêm độ lệch có thể
        vô tình rơi lại vào khoảng 0..1 (rất hiếm nhưng không phải KHÔNG
        THỂ) khiến tap() thường hiểu nhầm là toạ độ tỉ lệ rồi nhân sai."""
        self.run_cmd(["shell", "input", "tap", str(int(round(x_px))), str(int(round(y_px)))])

    def tap_fast_px(self, x_px, y_px):
        """Bản BẮN NGAY (fire-and-forget) của tap_px() - xem docstring
        tap_fast() để biết lý do cần bản không chờ riêng cho wait_image."""
        cmd = [self.adb_path]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(["shell", "input", "tap", str(int(round(x_px))), str(int(round(y_px)))])
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)

    def swipe(self, x1, y1, x2, y2, duration_ms=250):
        if 0.0 <= float(x1) <= 1.0 and 0.0 <= float(y1) <= 1.0:
            rx1 = int(float(x1) * self.screen_w)
            ry1 = int(float(y1) * self.screen_h)
            rx2 = int(float(x2) * self.screen_w)
            ry2 = int(float(y2) * self.screen_h)
        else:
            rx1, ry1 = int(float(x1)), int(float(y1))
            rx2, ry2 = int(float(x2)), int(float(y2))
        self.run_cmd(["shell", "input", "swipe", str(rx1), str(ry1), str(rx2), str(ry2), str(int(duration_ms))])

    def swipe_hold(self, x1, y1, x2, y2, move_duration_ms=300, hold_ms=200, steps=14):
        """Kéo (drag) MƯỢT qua nhiều điểm trung gian rồi GIỮ YÊN tại điểm đến
        1 khoảng ngắn TRƯỚC KHI nhả tay - khác với swipe() thường (dùng lệnh
        "input swipe" atomic của Android, LUÔN nhả tay NGAY LẬP TỨC khi vừa
        chạm tới điểm đến, đúng lúc còn nguyên vận tốc di chuyển).

        VÌ SAO CẦN HÀM NÀY: nhiều THANH TRƯỢT (slider) trong game coi 1 cú
        nhả tay còn vận tốc là "vuốt/ném" (fling) chứ không phải "đã kéo
        xong" (committed drag) -> tự động BẬT NGƯỢC lại vị trí cũ dù đã kéo
        đúng khoảng cách, trong khi kéo để CUỘN/DI CHUYỂN màn hình bình
        thường (không có ngưỡng "committed") thì swipe() thường vẫn hoạt
        động tốt - đúng như hiện tượng người dùng gặp phải.

        BẰNG CHỨNG: file ghi thao tác THẬT (LDPlayer tự ghi khi người dùng
        kéo thanh trượt bằng tay) cho thấy đúng 3 giai đoạn: (1) chạm xuống,
        (2) di chuyển mượt qua ~14 điểm liên tiếp trong ~300ms tới đích,
        (3) ĐỨNG YÊN tại đích thêm ~200ms (không còn sự kiện chạm nào khác,
        vẫn giữ tay) rồi MỚI nhấc lên. Hàm này mô phỏng lại ĐÚNG 3 giai đoạn
        đó bằng nhiều lệnh "input touchscreen motionevent DOWN/MOVE/UP" rời
        rạc (thay vì 1 lệnh "input swipe" atomic không thể chèn khoảng dừng
        vào giữa) - do CHÍNH kịch bản Python tự canh thời gian (time.sleep)
        giữa các lệnh; toàn bộ vẫn được Android xử lý như 1 CHUỖI CHẠM LIÊN
        TỤC (1 lần DOWN, nhiều MOVE, 1 lần UP) trên cùng 1 điểm chạm, không
        phải nhiều lần chạm rời rạc.

        move_duration_ms: tổng thời gian DI CHUYỂN từ điểm đầu tới điểm cuối.
        hold_ms: thời gian GIỮ YÊN tại điểm đến trước khi nhả tay - đây là
            phần THEN CHỐT giúp game nhận thao tác là "đã kéo xong, hợp lệ"
            thay vì hiểu nhầm là vuốt/ném. Thử 150-300ms nếu 200ms mặc định
            (đúng bằng số đo thực tế) chưa đủ ăn.
        steps: số điểm trung gian khi di chuyển - càng nhiều càng mượt
            (giống ngón tay thật) nhưng tốn nhiều lệnh adb hơn (mỗi điểm là
            1 tiến trình adb.exe riêng) - 10-20 là đủ mượt, không cần hơn.
        """
        if 0.0 <= float(x1) <= 1.0 and 0.0 <= float(y1) <= 1.0:
            rx1 = int(float(x1) * self.screen_w)
            ry1 = int(float(y1) * self.screen_h)
            rx2 = int(float(x2) * self.screen_w)
            ry2 = int(float(y2) * self.screen_h)
        else:
            rx1, ry1 = int(float(x1)), int(float(y1))
            rx2, ry2 = int(float(x2)), int(float(y2))

        self.run_cmd(["shell", "input", "touchscreen", "motionevent", "DOWN", str(rx1), str(ry1)])

        steps = max(1, int(steps))
        step_delay = max(0.001, (move_duration_ms / 1000.0) / steps)
        for i in range(1, steps + 1):
            alpha = i / steps
            mx = int(rx1 + (rx2 - rx1) * alpha)
            my = int(ry1 + (ry2 - ry1) * alpha)
            time.sleep(step_delay)
            self.run_cmd(["shell", "input", "touchscreen", "motionevent", "MOVE", str(mx), str(my)])

        # Đứng yên tại đích - giống hệt bản ghi thật: không gửi thêm sự kiện
        # nào trong lúc giữ, chỉ đơn giản CHỜ rồi mới nhả tay.
        if hold_ms > 0:
            time.sleep(hold_ms / 1000.0)

        self.run_cmd(["shell", "input", "touchscreen", "motionevent", "UP", str(rx2), str(ry2)])

    def screencap_fast(self):
        cmd = [self.adb_path]
        if self.device_id:
            cmd.extend(["-s", self.device_id])
        cmd.extend(["exec-out", "screencap", "-p"])

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
        raw_bytes, _ = proc.communicate()

        if not raw_bytes:
            return None
        arr = np.frombuffer(raw_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is not None:
            self.screen_h, self.screen_w = img.shape[:2]
        return img

    @staticmethod
    def _to_gray(img):
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

    @staticmethod
    def _crop_region(screen, region):
        """Cắt ảnh chụp màn hình theo VÙNG QUÉT (region) người dùng đã chọn
        trên Preview - normalized [x1,y1,x2,y2] trong khoảng 0..1 tính theo
        toàn bộ màn hình giả lập. Trả về (ảnh đã cắt, offset_x, offset_y)
        theo PIXEL GỐC (dùng để cộng ngược lại khi quy đổi toạ độ click về
        đúng vị trí trên TOÀN màn hình). region=None/không hợp lệ -> trả về
        chính ảnh gốc, offset=(0,0) - tức quét TOÀN màn hình như trước.

        ĐÂY LÀ CÁCH TĂNG TỐC CHÍNH thay cho việc thu nhỏ ảnh: chi phí
        cv2.matchTemplate tỉ lệ với DIỆN TÍCH ảnh đem so khớp - giới hạn
        đúng vùng cần tìm (thay vì quét cả màn hình) giúp nhanh hơn NHIỀU
        LẦN mà vẫn giữ NGUYÊN độ phân giải gốc, không đánh đổi độ chính xác
        như cách thu nhỏ ảnh trước đây."""
        if not region or len(region) != 4:
            return screen, 0, 0

        h, w = screen.shape[:2]
        x1 = max(0, min(w - 1, int(region[0] * w)))
        y1 = max(0, min(h - 1, int(region[1] * h)))
        x2 = max(x1 + 1, min(w, int(round(region[2] * w))))
        y2 = max(y1 + 1, min(h, int(round(region[3] * h))))
        return screen[y1:y2, x1:x2], x1, y1

    def find_image_on_screen(self, template_cv, threshold=0.80, region=None):
        screen = self.screencap_fast()
        if screen is None or template_cv is None:
            return None, 0.0

        search_img, off_x, off_y = self._crop_region(screen, region)
        s_gray = self._to_gray(search_img)
        t_gray = self._to_gray(template_cv)

        if s_gray.shape[0] < t_gray.shape[0] or s_gray.shape[1] < t_gray.shape[1]:
            # Vùng quét đã chọn nhỏ hơn cả ảnh mẫu (vd chọn nhầm khung quá bé)
            # -> không thể so khớp, coi như không thấy thay vì lỗi.
            return None, 0.0

        res = cv2.matchTemplate(s_gray, t_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            h, w = t_gray.shape[:2]
            cx = off_x + max_loc[0] + w // 2
            cy = off_y + max_loc[1] + h // 2
            return (round(cx / self.screen_w, 4), round(cy / self.screen_h, 4)), max_val
        return None, max_val

    def find_any_image_on_screen(self, templates_dict, threshold=0.80, region=None):
        screen = self.screencap_fast()
        if screen is None:
            return None, None, 0.0

        search_img, off_x, off_y = self._crop_region(screen, region)
        s_gray = self._to_gray(search_img)

        best_name = None
        best_pos = None
        highest_score = 0.0

        for name, t_cv in templates_dict.items():
            if t_cv is None:
                continue
            t_gray = self._to_gray(t_cv)
            if s_gray.shape[0] < t_gray.shape[0] or s_gray.shape[1] < t_gray.shape[1]:
                continue

            res = cv2.matchTemplate(s_gray, t_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= threshold and max_val > highest_score:
                highest_score = max_val
                h, w = t_gray.shape[:2]
                cx = off_x + max_loc[0] + w // 2
                cy = off_y + max_loc[1] + h // 2
                best_name = name
                best_pos = (round(cx / self.screen_w, 4), round(cy / self.screen_h, 4))

        return best_name, best_pos, highest_score

    def find_all_images_on_screen(self, templates_dict, threshold=0.80, region=None):
        """Logic AND: kiểm tra TẤT CẢ ảnh trong templates_dict có xuất hiện
        ĐỒNG THỜI trên CÙNG 1 tấm ảnh chụp màn hình hay không - khác với
        find_any_image_on_screen() (logic OR) là chỉ cần 1 trong số đó xuất
        hiện là đã tính khớp. Dùng cho if_image/multi_image khi người dùng
        chọn chế độ "khớp TẤT CẢ ảnh trong nhóm" (match_mode="and"), vd chỉ
        coi là ĐÚNG khi cả icon A và icon B cùng hiện trên màn hình.

        Trả về (all_matched: bool, results: dict[tên_file] -> (pos, score))
        - results chỉ chứa những ảnh ĐÃ tìm thấy (kể cả khi chưa đủ TẤT CẢ),
        hữu ích để log/debug xem còn thiếu ảnh nào."""
        screen = self.screencap_fast()
        if screen is None or not templates_dict:
            return False, {}

        search_img, off_x, off_y = self._crop_region(screen, region)
        s_gray = self._to_gray(search_img)

        results = {}
        for name, t_cv in templates_dict.items():
            if t_cv is None:
                continue
            t_gray = self._to_gray(t_cv)
            if s_gray.shape[0] < t_gray.shape[0] or s_gray.shape[1] < t_gray.shape[1]:
                continue

            res = cv2.matchTemplate(s_gray, t_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= threshold:
                h, w = t_gray.shape[:2]
                cx = off_x + max_loc[0] + w // 2
                cy = off_y + max_loc[1] + h // 2
                results[name] = ((round(cx / self.screen_w, 4), round(cy / self.screen_h, 4)), max_val)

        all_matched = len(results) == len(templates_dict)
        return all_matched, results

    # ---- BÀN PHÍM (mới) ----
    @staticmethod
    def _is_ascii(text):
        try:
            text.encode("ascii")
            return True
        except UnicodeEncodeError:
            return False

    def get_current_ime(self):
        """Trả về ID bàn phím (IME) đang được đặt làm mặc định trên thiết bị,
        vd 'com.android.adbkeyboard/.AdbIME' nếu đã bật ADBKeyboard."""
        try:
            out = self.run_cmd(["shell", "settings", "get", "secure", "default_input_method"])
            return out.decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""

    def is_adbkeyboard_active(self):
        return "adbkeyboard" in self.get_current_ime().lower()

    def is_adbkeyboard_installed(self):
        try:
            out = self.run_cmd(["shell", "pm", "list", "packages", "com.android.adbkeyboard"])
            return b"com.android.adbkeyboard" in out
        except Exception:
            return False

    def enable_adbkeyboard(self):
        """Bật ADBKeyboard làm bàn phím ĐANG DÙNG trên thiết bị - cần cài
        sẵn ADBKeyboard.apk từ trước (xem is_adbkeyboard_installed)."""
        self.run_cmd(["shell", "ime", "enable", "com.android.adbkeyboard/.AdbIME"])
        self.run_cmd(["shell", "ime", "set", "com.android.adbkeyboard/.AdbIME"])

    def _input_text_via_adbkeyboard(self, text):
        """Gõ chữ CÓ DẤU (Unicode) qua broadcast tới bàn phím ảo ADBKeyboard
        (https://github.com/senzhk/ADBKeyBoard) - vì `adb shell input text`
        gốc của Android CHỈ hỗ trợ ký tự ASCII, ký tự có dấu (tiếng Việt...)
        bị coi là không hợp lệ và ADB ÂM THẦM BỎ QUA (không báo lỗi gì) -
        đây là lý do các bước Gõ Chữ có dấu trước đây "chạy xong" trong log
        nhưng không thấy chữ nào xuất hiện trên máy ảo. Gửi dạng base64 qua
        action ADB_INPUT_B64 để không phải tự escape khoảng trắng/ký tự đặc
        biệt/Unicode như input text thường."""
        import base64
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        self.run_cmd(["shell", "am", "broadcast", "-a", "ADB_INPUT_B64", "--es", "msg", b64])

    def input_text(self, text):
        """Gõ một chuỗi ký tự lên thiết bị.

        - Chữ THUẦN ASCII (không dấu): dùng `adb shell input text` như cũ -
          nhanh, không cần cài thêm gì.
        - Chữ CÓ DẤU (tiếng Việt, kết quả OCR...) VÀ máy ảo đã cài + bật sẵn
          ADBKeyboard: gửi qua ADBKeyboard để gõ đúng dấu.
        - Chữ có dấu mà CHƯA có ADBKeyboard: TRƯỚC ĐÂY sẽ âm thầm gọi
          `input text` và Android lặng lẽ bỏ qua các ký tự có dấu (không báo
          lỗi, không gõ ra gì) - người dùng thấy log "chạy xong" nhưng chữ
          không hề xuất hiện, tưởng là bug. GIỜ báo lỗi rõ ràng ngay tại đây
          để biết chính xác cần làm gì (xem nút '⌨️ Cài/Bật ADBKeyboard' trên
          giao diện)."""
        if not text:
            return
        if self._is_ascii(text):
            escaped = text.replace(" ", "%s")
            for ch in ['&', '<', '>', '|', ';', '(', ')', '"', "'", '$', '`', '\\']:
                escaped = escaped.replace(ch, "\\" + ch)
            self.run_cmd(["shell", "input", "text", escaped])
            return

        if self.is_adbkeyboard_active():
            self._input_text_via_adbkeyboard(text)
            return

        raise RuntimeError(
            "Chữ cần gõ có dấu (vd tiếng Việt) nhưng lệnh gõ chữ mặc định của Android "
            "('adb shell input text') KHÔNG hỗ trợ ký tự có dấu, và máy ảo CHƯA bật bàn "
            "phím ADBKeyboard để gõ được Unicode. Bấm nút '⌨️ Cài/Bật ADBKeyboard' trên "
            "giao diện để xem hướng dẫn cài đặt."
        )

    def key_event(self, keycode):
        """Gửi 1 phím đơn lẻ, vd 'KEYCODE_ENTER', 'KEYCODE_A'."""
        self.run_cmd(["shell", "input", "keyevent", keycode])

    # ---- OCR (mới) ----
    def check_ocr_setup(self):
        """Trả về (ok: bool, message: str) - dùng cho nút '🔍 Kiểm Tra OCR'
        trên giao diện để CHẨN ĐOÁN NHANH lý do OCR không hoạt động, thay vì
        phải đoán mò qua từng lần chạy macro."""
        if not _HAS_PYTESSERACT_LIB:
            return False, "Chưa cài thư viện Python 'pytesseract'.\nChạy: pip install pytesseract"
        if not _HAS_TESSERACT:
            return False, (
                "Có thư viện pytesseract nhưng KHÔNG gọi được chương trình Tesseract-OCR "
                "(đây là 1 chương trình riêng, không phải thư viện Python).\n\n"
                f"Chi tiết lỗi: {_TESSERACT_INIT_ERROR}\n\n"
                "Cách khắc phục: cài Tesseract-OCR tại "
                "https://github.com/UB-Mannheim/tesseract/wiki, hoặc nếu đã cài mà vẫn "
                "báo lỗi này, hãy sửa biến pytesseract.pytesseract.tesseract_cmd trong "
                "adb_helper.py trỏ đúng tới nơi cài đặt file tesseract.exe của bạn."
            )
        try:
            version = pytesseract.get_tesseract_version()
        except Exception as e:
            return False, f"Tesseract báo cài rồi nhưng gọi thử bị lỗi: {e}"
        try:
            langs = pytesseract.get_languages(config="")
        except Exception:
            langs = []
        missing = [l for l in ("vie", "eng") if langs and l not in langs]
        msg = f"✔ Tesseract-OCR hoạt động bình thường (phiên bản {version}).\n"
        msg += f"Đường dẫn: {pytesseract.pytesseract.tesseract_cmd}\n"
        msg += f"Ngôn ngữ đã cài: {', '.join(langs) if langs else '(không đọc được danh sách)'}"
        if missing:
            msg += (f"\n\n⚠️ CHƯA cài gói ngôn ngữ: {', '.join(missing)}."
                    " Nếu kịch bản đang quét với lang='vie+eng' mà thiếu gói 'vie', "
                    "Tesseract sẽ báo LỖI (không phải rỗng) khi quét - cài thêm traineddata "
                    "tương ứng tại https://github.com/tesseract-ocr/tessdata")
        msg += ("\n\nLƯU Ý: nếu bước Quét OCR trong kịch bản trả về BIẾN RỖNG (\"\") mà KHÔNG "
                "kèm dòng lỗi trong Nhật Ký Chạy, nghĩa là Tesseract ĐÃ CHẠY nhưng không đọc "
                "ra chữ nào trong vùng đã chọn - hãy mở 2 file "
                "logs/last_ocr_crop.png (vùng vừa cắt) và logs/last_ocr_crop_bin.png (ảnh đã "
                "xử lý đưa vào Tesseract) được lưu lại sau MỖI lần quét để kiểm tra xem vùng "
                "chọn có đúng chỗ có chữ hay không, và chữ có còn rõ nét sau xử lý hay không.")
        return True, msg

    def ocr_text_in_box(self, screen_img, box, lang="vie+eng", debug_dir="logs"):
        """Quét chữ (OCR) trong 1 vùng box=(x1,y1,x2,y2) tính bằng pixel trên
        ảnh chụp màn hình. Cần cài thư viện pytesseract (pip install
        pytesseract) VÀ cài chương trình Tesseract-OCR riêng (không phải thư
        viện Python) từ https://github.com/UB-Mannheim/tesseract/wiki.

        CẢI TIẾN so với trước:
        1. LUÔN lưu lại ảnh vùng vừa cắt ra 'logs/last_ocr_crop.png' và ảnh
           đã xử lý nhị phân dùng để đưa vào Tesseract ra
           'logs/last_ocr_crop_bin.png' sau MỖI lần quét - để chẩn đoán được
           BẰNG MẮT khi kết quả trả về rỗng: có phải do chọn sai vùng, hay do
           chữ mờ/nhỏ sau xử lý. Trước đây quét ra rỗng là hết cách kiểm tra.
        2. Xử lý ảnh kỹ hơn (phóng to 3x + khử nhiễu nhẹ + nhị phân hóa Otsu)
           thay vì chỉ resize ảnh xám thô - chữ nhỏ/nhiều màu trong UI game là
           lý do phổ biến nhất khiến Tesseract mặc định đọc ra rỗng.
        3. Thử cả 2 chiều màu (chữ sáng nền tối / chữ tối nền sáng) vì không
           biết trước UI game dùng kiểu nào, rồi lấy kết quả dài nhất.
        """
        if not _HAS_TESSERACT:
            reason = _TESSERACT_INIT_ERROR or "Chưa cài Tesseract-OCR."
            raise RuntimeError(f"OCR chưa sẵn sàng: {reason}")

        x1, y1, x2, y2 = box
        crop = screen_img[y1:y2, x1:x2]
        if crop.size == 0:
            raise RuntimeError(f"Vùng cắt rỗng (box pixel={box}) - có thể tọa độ vùng quét bị sai.")

        try:
            os.makedirs(debug_dir, exist_ok=True)
            cv2.imwrite(os.path.join(debug_dir, "last_ocr_crop.png"), crop)
        except Exception:
            pass

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
        gray = cv2.resize(gray, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.bilateralFilter(gray, 5, 40, 40)

        _, bin_normal = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bin_inverted = cv2.bitwise_not(bin_normal)

        try:
            cv2.imwrite(os.path.join(debug_dir, "last_ocr_crop_bin.png"), bin_normal)
        except Exception:
            pass

        candidates = []
        for img_variant in (bin_normal, bin_inverted, gray):
            try:
                txt = pytesseract.image_to_string(img_variant, lang=lang, config="--psm 6").strip()
            except Exception as e:
                txt = f"[Lỗi OCR: {e}]"
                # Nếu Tesseract lỗi thật sự (vd thiếu gói ngôn ngữ), báo lỗi
                # ngay thay vì lặng lẽ thử tiếp các biến thể khác - lỗi ngôn
                # ngữ sẽ giống nhau ở cả 3 lần thử nên báo sớm cho rõ ràng.
                raise RuntimeError(str(e))
            candidates.append(txt)

        # Chọn kết quả DÀI NHẤT trong các lần thử (bình thường / đảo màu /
        # xám thô không nhị phân) - cách đơn giản nhưng khá hiệu quả để tự
        # chọn bản đọc tốt nhất khi không biết trước UI sáng/tối.
        best = max(candidates, key=len) if candidates else ""
        return best

    def send_key_combo(self, keycodes):
        """Gửi tổ hợp phím, vd ['KEYCODE_CTRL_LEFT', 'KEYCODE_A'] (Ctrl+A).

        Lưu ý quan trọng: lệnh `adb shell input keycombination` chỉ được hỗ trợ
        trên Android 12 (API 31) trở lên - đây là giới hạn của chính Android,
        không phải lỗi code. TRƯỚC ĐÂY: run_cmd() không kiểm tra returncode/
        stderr, nên khi lệnh thất bại trên máy ảo Android cũ, Python không hề
        biết là nó đã lỗi -> nhánh "gửi rời rạc từng phím" phía dưới KHÔNG BAO
        GIỜ được kích hoạt -> tổ hợp phím im lặng không có tác dụng gì. Giờ
        kiểm tra SDK version + returncode/stderr thật để biết chắc chắn."""
        if not keycodes:
            return
        if len(keycodes) == 1:
            self.key_event(keycodes[0])
            return

        sdk = self.get_sdk_version()
        if sdk >= 31:
            _, err, rc = self.run_cmd_full(["shell", "input", "keycombination"] + list(keycodes))
            if rc == 0 and not err.strip():
                return
            print(f"[CẢNH BÁO] 'input keycombination' báo lỗi dù SDK={sdk} (rc={rc}, err={err.strip()}). "
                  f"Sẽ gửi rời rạc từng phím thay thế.")
        else:
            print(f"[CẢNH BÁO] Thiết bị đang chạy Android SDK {sdk} (< 12/API 31) nên KHÔNG hỗ trợ "
                  f"giữ đồng thời nhiều phím qua adb. Gửi rời rạc {keycodes} - với tổ hợp có Ctrl/Alt/Shift, "
                  f"rất nhiều app sẽ KHÔNG nhận ra vì phím bổ trợ đã nhả trước khi phím chính được gửi. "
                  f"Cách khắc phục triệt để: đổi image hệ điều hành của máy ảo LDPlayer sang bản Android 12+ "
                  f"(LDPlayer 9 hỗ trợ chọn khi tạo máy ảo mới).")

        for kc in keycodes:
            self.key_event(kc)
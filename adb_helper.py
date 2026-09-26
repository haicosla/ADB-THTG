import os
import subprocess
import shutil
import time
import math
import re
import socket
import threading
import cv2
import numpy as np
import psutil

try:
    import pytesseract
    _HAS_PYTESSERACT_LIB = True
except ImportError:
    pytesseract = None
    _HAS_PYTESSERACT_LIB = False


# ---------------------------------------------------------------------------
# KIỂU QUÉT ẢNH (match_mode) - mỗi ảnh/bước có thể chọn 1 kiểu phù hợp.
# Lưu trong bước kịch bản: step["match_mode"] (str) và, với bước nhiều ảnh,
# step["template_modes"] = {tên_file: kiểu} để ghi đè riêng từng ảnh.
# KHÔNG có field này (hoặc giá trị lạ) => dùng "gray" = đúng cách quét CŨ
# (chuyển xám + TM_CCOEFF_NORMED), nên kịch bản cũ chạy y hệt như trước.
# Điểm trả về LUÔN theo thang "càng CAO càng khớp" (0..1) với mọi kiểu -
# kiểu dùng SQDIFF (đo sai khác, vốn càng nhỏ càng khớp) đã được đảo lại
# thành 1 - sai_khác, nên threshold/"Độ khớp" dùng chung 1 cách cho mọi kiểu.
# Tuple: (nhãn hiển thị, nhãn ngắn hiện ở cột Độ khớp, mô tả).
# ---------------------------------------------------------------------------
DEFAULT_MATCH_MODE = "gray"
MATCH_MODES = {
    "gray": (
        "Xám (mặc định)", "Xám",
        "Chuyển ảnh xám + tương quan chuẩn hoá (TM_CCOEFF_NORMED). Nhanh, "
        "bỏ qua khác biệt độ sáng/tương phản nên KHÔNG phân biệt được 2 ảnh "
        "cùng hình dạng chỉ khác độ sáng/màu."
    ),
    "color": (
        "Màu (BGR)", "Màu",
        "Như 'Xám' nhưng so cả 3 kênh màu (TM_CCOEFF_NORMED). Phân biệt "
        "được icon khác màu; vẫn ít nhạy với chênh lệch sáng đều."
    ),
    "gray_sqdiff": (
        "Xám - sai khác pixel", "Xám-Δ",
        "So độ sai khác từng pixel trên ảnh xám (TM_SQDIFF_NORMED, điểm = "
        "1 - sai khác). NHẠY với độ sáng: ảnh tối/sáng khác nhau bị coi là "
        "khác. Hợp icon có hình giống nhau nhưng khác trạng thái sáng/tối."
    ),
    "color_sqdiff": (
        "Màu - sai khác pixel", "Màu-Δ",
        "So độ sai khác từng pixel trên 3 kênh màu (TM_SQDIFF_NORMED, điểm = "
        "1 - sai khác). Nghiêm ngặt nhất: khác màu HOẶC khác độ sáng đều "
        "bị loại. Hợp icon đổi màu theo trạng thái (bật/tắt, đủ/thiếu...)."
    ),
    "edge": (
        "Đường viền (Canny)", "Viền",
        "So khớp bản đồ đường viền (Canny) - chỉ quan tâm HÌNH DẠNG, bỏ qua "
        "màu/nền. Hợp icon/chữ có nền thay đổi. Điểm khớp đúng thường chỉ "
        "~0.8-0.9 nên nên hạ Độ khớp xuống khoảng 0.6-0.75."
    ),
}


def normalize_match_mode(mode):
    """Trả về mode hợp lệ; None/rỗng/giá trị lạ -> DEFAULT_MATCH_MODE."""
    return mode if mode in MATCH_MODES else DEFAULT_MATCH_MODE


def match_mode_label(mode):
    """Nhãn hiển thị đầy đủ của 1 kiểu quét (vd 'Xám (mặc định)')."""
    return MATCH_MODES[normalize_match_mode(mode)][0]


def match_mode_short(mode):
    """Nhãn NGẮN của 1 kiểu quét (vd 'Màu-Δ') - dùng ở cột Độ khớp."""
    return MATCH_MODES[normalize_match_mode(mode)][1]


def match_mode_from_label(label, default=None):
    """Đổi nhãn hiển thị (nhãn đầy đủ) ngược lại thành key; không khớp -> default."""
    for key, (lbl, _short, _desc) in MATCH_MODES.items():
        if lbl == label:
            return key
    return default


def _prep_for_mode(img, mode):
    """Tiền xử lý ảnh (màn hình HOẶC ảnh mẫu) theo kiểu quét - cả 2 phải
    được xử lý CÙNG 1 kiểu trước khi đưa vào _match_map()."""
    if mode in ("color", "color_sqdiff"):
        if len(img.shape) == 2:
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if img.shape[2] == 4:
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    if mode == "edge":
        return cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 50, 150)
    return gray


def _match_map(s_p, t_p, mode):
    """Chạy matchTemplate và trả về BẢN ĐỒ ĐIỂM (float32) theo thang
    'càng cao càng khớp' cho MỌI kiểu. Kiểu 'gray' (mặc định) giữ NGUYÊN kết
    quả thô của TM_CCOEFF_NORMED như trước đây."""
    if mode in ("gray_sqdiff", "color_sqdiff"):
        res = cv2.matchTemplate(s_p, t_p, cv2.TM_SQDIFF_NORMED)
        res = np.nan_to_num(res, nan=1.0, posinf=1.0, neginf=1.0)
        return np.clip(1.0 - res, 0.0, 1.0)
    res = cv2.matchTemplate(s_p, t_p, cv2.TM_CCOEFF_NORMED)
    if mode != DEFAULT_MATCH_MODE:
        res = np.nan_to_num(res, nan=0.0, posinf=0.0, neginf=0.0)
    return res


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
        # Cache kết quả dò thiết bị cảm ứng đa điểm (xem _detect_touch_device)
        # - None = CHƯA dò, False = đã dò nhưng KHÔNG tìm thấy/không dùng
        # được (khỏi dò lại mỗi lần gọi pinch_zoom, tốn ~1s/lần), dict = đã
        # tìm thấy và cache lại thông tin thiết bị.
        self._touch_device_cache = None
        # Lý do lần gần nhất Chế Độ Siêu Tốc phải TỰ RƠI VỀ đường bình
        # thường (None = lần gần nhất chạy turbo bình thường, không lỗi) -
        # logic_engine.py đọc biến này ngay sau mỗi lần gọi hàm turbo để
        # biết CÓ THẬT SỰ đang chạy nhanh hay không, tránh trường hợp âm
        # thầm rơi về đường cũ (vd không kết nối được ADB server đúng
        # cổng/đúng phiên bản) mà người dùng tưởng đã bật turbo nhưng thực
        # ra không có tác dụng gì.
        self.turbo_last_error = None
        # Cache tiền xử lý ẢNH MẪU theo (kiểu quét, nội dung ảnh) - xem
        # _prep_template_cached() ngay bên dưới _prep_for_mode().
        self._tpl_prep_cache = {}
        # Động cơ Siêu Tốc (turbo_engine.py) - tạo NGẦM lần đầu 1 bước
        # bật Siêu Tốc chạy tới (xem _get_turbo_engine). Không có/lỗi file đó
        # thì mọi hàm *_turbo bên dưới tự dùng lại đường socket-PNG cũ.
        self._turbo_eng = None
        self._turbo_eng_failed = False
        self._turbo_eng_lock = threading.Lock()
        self._turbo_err_reported = False
        self.turbo_engine_error = None
        self.turbo_last_timing = None
        self.turbo_last_click_ms = None
        self._turbo_click_via = None
        self.turbo_click_ms = None

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

    def tap_hold_px(self, x_px, y_px, hold_ms=500):
        """Giữ tay (long-press/long-click) tại 1 điểm: CHẠM XUỐNG, đứng yên
        đúng vị trí trong hold_ms mili-giây, rồi mới NHẤC LÊN - khác với
        tap()/tap_px() (chạm rồi nhấc ngay lập tức). Dùng cho các UI cần
        GIỮ TAY mới hiện ra (menu ngữ cảnh khi giữ lâu 1 icon, bắt đầu 1 cử
        chỉ kéo-thả bằng cách giữ trước...) mà tap nhanh không kích hoạt
        được. (x_px, y_px) LUÔN là toạ độ PIXEL THẬT trên màn hình thiết bị
        (không tự đoán tỉ lệ 0..1 như tap() thường) - xem docstring tap_px()
        để biết lý do cần tách riêng bản pixel tuyệt đối."""
        rx, ry = int(round(x_px)), int(round(y_px))
        self.run_cmd(["shell", "input", "touchscreen", "motionevent", "DOWN", str(rx), str(ry)])
        time.sleep(max(0.05, float(hold_ms) / 1000.0))
        self.run_cmd(["shell", "input", "touchscreen", "motionevent", "UP", str(rx), str(ry)])

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

    def swipe_px(self, x1_px, y1_px, x2_px, y2_px, duration_ms=250):
        """Giống swipe() nhưng LUÔN coi toạ độ là PIXEL THẬT (không tự đoán
        tỉ lệ 0..1) - dùng khi toạ độ đã được TỰ TÍNH TOÁN từ trước (vd cộng
        thêm click_jitter), xem lý do tương tự tap_px()/tap_fast_px()."""
        self.run_cmd(["shell", "input", "swipe",
                      str(int(round(x1_px))), str(int(round(y1_px))),
                      str(int(round(x2_px))), str(int(round(y2_px))), str(int(duration_ms))])

    def swipe_hold_px(self, x1_px, y1_px, x2_px, y2_px, move_duration_ms=300, hold_ms=200, steps=14):
        """Bản PIXEL THẬT (không tự đoán tỉ lệ 0..1) của swipe_hold() - dùng
        khi toạ độ đã được TỰ TÍNH TOÁN từ trước (vd cộng thêm click_jitter)
        - xem docstring swipe_hold() để hiểu 3 giai đoạn DOWN/MOVE.../GIỮ
        YÊN/UP, chỉ khác ở chỗ KHÔNG kiểm tra "0..1 = tỉ lệ" nữa."""
        rx1, ry1 = int(round(x1_px)), int(round(y1_px))
        rx2, ry2 = int(round(x2_px)), int(round(y2_px))

        self.run_cmd(["shell", "input", "touchscreen", "motionevent", "DOWN", str(rx1), str(ry1)])

        steps = max(1, int(steps))
        step_delay = max(0.001, (move_duration_ms / 1000.0) / steps)
        for i in range(1, steps + 1):
            alpha = i / steps
            mx = int(rx1 + (rx2 - rx1) * alpha)
            my = int(ry1 + (ry2 - ry1) * alpha)
            time.sleep(step_delay)
            self.run_cmd(["shell", "input", "touchscreen", "motionevent", "MOVE", str(mx), str(my)])

        if hold_ms > 0:
            time.sleep(hold_ms / 1000.0)

        self.run_cmd(["shell", "input", "touchscreen", "motionevent", "UP", str(rx2), str(ry2)])

    def swipe_path_px(self, points_px, duration_ms=400, hold_ms=0, steps_per_segment=8):
        """Vuốt qua NHIỀU điểm liên tiếp (không chỉ 2 đầu-cuối như swipe()/
        swipe_hold()) trong 1 lần chạm LIÊN TỤC: DOWN tại điểm đầu -> nội
        suy MOVE mượt qua từng đoạn nối 2 điểm kế tiếp -> (tuỳ chọn) GIỮ
        YÊN tại điểm cuối -> UP. Dùng cho các thao tác cần đường vuốt phức
        tạp mà 1 đoạn thẳng 2 điểm không mô phỏng được (vd vẽ hình để mở
        khoá kiểu pattern, kéo qua nhiều ô cờ liên tiếp, vẽ 1 nét chữ...).

        points_px: danh sách >= 2 điểm [(x, y), ...] TOẠ ĐỘ PIXEL THẬT
            (không phải tỉ lệ 0..1 - bên gọi từ logic_engine tự nhân với
            screen_w/screen_h trước khi gọi hàm này, giống swipe_px()).
        duration_ms: TỔNG thời gian di chuyển qua toàn bộ đường - được
            chia cho từng đoạn theo TỈ LỆ độ dài đoạn đó (đoạn dài đi lâu
            hơn đoạn ngắn), để tốc độ di chuyển đều nhau trên cả đường.
        hold_ms: thời gian GIỮ YÊN tại điểm CUỐI CÙNG trước khi nhả tay,
            giống swipe_hold_px() - dùng khi điểm cuối cần được "chốt"
            (committed) thay vì nhả tay khi còn vận tốc.
        steps_per_segment: số điểm trung gian nội suy CHO MỖI đoạn.
        """
        if not points_px or len(points_px) < 2:
            return
        pts = [(int(round(x)), int(round(y))) for x, y in points_px]

        seg_lens = []
        total_len = 0.0
        for i in range(len(pts) - 1):
            dx = pts[i + 1][0] - pts[i][0]
            dy = pts[i + 1][1] - pts[i][1]
            seg_len = (dx * dx + dy * dy) ** 0.5
            seg_lens.append(seg_len)
            total_len += seg_len
        n_segments = len(pts) - 1
        if total_len <= 0:
            total_len = 1.0

        self.run_cmd(["shell", "input", "touchscreen", "motionevent", "DOWN", str(pts[0][0]), str(pts[0][1])])

        for i in range(n_segments):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            seg_duration = duration_ms * (seg_lens[i] / total_len) if seg_lens[i] > 0 else duration_ms / max(1, n_segments)
            n_steps = max(1, int(steps_per_segment))
            step_delay = max(0.001, (seg_duration / 1000.0) / n_steps)
            for k in range(1, n_steps + 1):
                alpha = k / n_steps
                mx = int(x1 + (x2 - x1) * alpha)
                my = int(y1 + (y2 - y1) * alpha)
                time.sleep(step_delay)
                self.run_cmd(["shell", "input", "touchscreen", "motionevent", "MOVE", str(mx), str(my)])

        if hold_ms > 0:
            time.sleep(hold_ms / 1000.0)

        self.run_cmd(["shell", "input", "touchscreen", "motionevent", "UP", str(pts[-1][0]), str(pts[-1][1])])

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

    def _detect_touch_device(self):
        """Dò THIẾT BỊ CẢM ỨNG ĐA ĐIỂM (multi-touch) thật của giả lập qua
        `adb shell getevent -pl` (liệt kê toàn bộ input device + khả năng
        hỗ trợ). Trả về dict {"path", "min_x", "max_x", "min_y", "max_y"}
        nếu tìm được 1 thiết bị có ABS_MT_POSITION_X/Y (đúng chuẩn multi-
        touch Protocol B), hoặc None nếu không tìm thấy / không đọc được
        (vd giả lập chặn quyền đọc /dev/input qua shell). Kết quả nên được
        CACHE lại (self._touch_device_cache) vì lệnh này khá chậm (~1s)."""
        out, err, rc = self.run_cmd_full(["shell", "getevent", "-pl"])
        if rc != 0 or not out.strip():
            return None

        devices = []
        cur = None
        for line in out.splitlines():
            m = re.match(r"\s*add device \d+:\s*(.+)", line)
            if m:
                cur = {"path": m.group(1).strip(), "raw": []}
                devices.append(cur)
            elif cur is not None:
                cur["raw"].append(line)

        def _abs_range(raw_lines, code):
            # Dòng mẫu: "    ABS_MT_POSITION_X  : value 0, min 0, max 1079, ..."
            for ln in raw_lines:
                if code in ln and "min" in ln:
                    mo = re.search(r"min\s+(-?\d+),\s*max\s+(-?\d+)", ln)
                    if mo:
                        return int(mo.group(1)), int(mo.group(2))
            return None

        for dev in devices:
            raw = dev["raw"]
            joined = "\n".join(raw)
            if "ABS_MT_POSITION_X" not in joined or "ABS_MT_POSITION_Y" not in joined:
                continue
            xr = _abs_range(raw, "ABS_MT_POSITION_X")
            yr = _abs_range(raw, "ABS_MT_POSITION_Y")
            if not xr or not yr or xr[1] <= xr[0] or yr[1] <= yr[0]:
                continue
            return {"path": dev["path"], "min_x": xr[0], "max_x": xr[1], "min_y": yr[0], "max_y": yr[1]}
        return None

    def pinch_zoom_sendevent(self, cx, cy, start_radius, end_radius, angle_deg=90.0, duration_ms=400, steps=14):
        """Phiên bản ĐÚNG CHUẨN multi-touch THẬT (2 ngón trong CÙNG 1 chuỗi
        sự kiện chạm, theo chuẩn Linux MT Protocol B - y hệt 2 ngón tay
        thật) của pinch_zoom(), bắn TRỰC TIẾP bằng `adb shell sendevent`
        vào ĐÚNG thiết bị cảm ứng của giả lập (dò qua _detect_touch_device).
        Đây là cách DUY NHẤT tạo ra 1 MotionEvent có 2 pointer thật sự mà
        ScaleGestureDetector (bộ nhận diện pinch chuẩn của Android, hầu hết
        app/game dùng) nhận ra - khác với 2 lệnh "input touchscreen swipe"
        chạy song song (_pinch_zoom_parallel_swipe bên dưới): cách đó tạo
        ra 2 chuỗi ACTION_DOWN...ACTION_UP ĐỘC LẬP đè lên nhau về THỜI
        GIAN chứ KHÔNG PHẢI 1 sự kiện 2-pointer, nên phần lớn app/game có
        pinch-to-zoom (Google Maps, camera trong game, v.v...) sẽ KHÔNG
        nhận ra đó là 1 cử chỉ zoom - đây chính là lý do nếu bạn thấy
        "chưa zoom được" khi dùng bản cũ.

        Trả về True nếu đã gửi lệnh sendevent thành công (KHÔNG chắc chắn
        app có xử lý đúng), False nếu KHÔNG dò được thiết bị cảm ứng phù
        hợp hoặc `adb shell sendevent` bị từ chối (thiếu quyền) - khi đó
        nên fallback sang _pinch_zoom_parallel_swipe().
        """
        dev = self._touch_device_cache
        if dev is None:
            dev = self._detect_touch_device()
            self._touch_device_cache = dev if dev else False
        if not dev:
            return False

        if 0.0 <= float(cx) <= 1.0 and 0.0 <= float(cy) <= 1.0:
            rcx, rcy = float(cx) * self.screen_w, float(cy) * self.screen_h
        else:
            rcx, rcy = float(cx), float(cy)

        rad = math.radians(angle_deg)
        adx, ady = math.cos(rad), math.sin(rad)

        def _raw(px, py):
            # Quy đổi toạ độ PIXEL màn hình (self.screen_w x self.screen_h)
            # sang biên độ RAW của thiết bị cảm ứng (min_x..max_x/min_y..
            # max_y) - 2 hệ toạ độ này thường KHÁC NHAU (vd màn hình báo
            # 1080x1920 nhưng cảm biến raw lại là 0..32767) nên bắt buộc
            # phải quy đổi, không thể dùng thẳng toạ độ pixel.
            rx = dev["min_x"] + (px / max(1, self.screen_w)) * (dev["max_x"] - dev["min_x"])
            ry = dev["min_y"] + (py / max(1, self.screen_h)) * (dev["max_y"] - dev["min_y"])
            return int(round(rx)), int(round(ry))

        def _point(radius, sign):
            return _raw(rcx + sign * adx * radius, rcy + sign * ady * radius)

        a0, a1 = _point(start_radius, -1), _point(end_radius, -1)
        b0, b1 = _point(start_radius, 1), _point(end_radius, 1)

        path = dev["path"]
        # Mã type/code chuẩn Linux input-event (decimal, KHÔNG phải hex) -
        # xem <linux/input-event-codes.h>: EV_KEY=1, EV_ABS=3, EV_SYN=0.
        EV_KEY, EV_ABS = 1, 3
        ABS_MT_SLOT, ABS_MT_TRACKING_ID = 47, 57
        ABS_MT_POSITION_X, ABS_MT_POSITION_Y = 53, 54
        BTN_TOUCH = 330
        TID_A, TID_B = 1001, 1002

        cmds = []

        def sev(t, c, v):
            cmds.append(f"sendevent {path} {t} {c} {v}")

        def syn():
            sev(0, 0, 0)

        # Đặt 2 "ngón tay" xuống CÙNG 1 chuỗi sự kiện (khác slot 0/1) rồi mới
        # SYN_REPORT 1 lần duy nhất cho cả 2 - đây chính là điểm mấu chốt
        # tạo ra 1 MotionEvent 2-pointer thật, thay vì 2 sự kiện rời rạc.
        sev(EV_ABS, ABS_MT_SLOT, 0)
        sev(EV_ABS, ABS_MT_TRACKING_ID, TID_A)
        sev(EV_ABS, ABS_MT_POSITION_X, a0[0])
        sev(EV_ABS, ABS_MT_POSITION_Y, a0[1])
        sev(EV_KEY, BTN_TOUCH, 1)
        sev(EV_ABS, ABS_MT_SLOT, 1)
        sev(EV_ABS, ABS_MT_TRACKING_ID, TID_B)
        sev(EV_ABS, ABS_MT_POSITION_X, b0[0])
        sev(EV_ABS, ABS_MT_POSITION_Y, b0[1])
        syn()

        steps = max(2, int(steps))
        per_step_delay = max(0.0, (duration_ms / 1000.0) / steps)
        for i in range(1, steps + 1):
            t = i / steps
            xa, ya = int(a0[0] + (a1[0] - a0[0]) * t), int(a0[1] + (a1[1] - a0[1]) * t)
            xb, yb = int(b0[0] + (b1[0] - b0[0]) * t), int(b0[1] + (b1[1] - b0[1]) * t)
            sev(EV_ABS, ABS_MT_SLOT, 0)
            sev(EV_ABS, ABS_MT_POSITION_X, xa)
            sev(EV_ABS, ABS_MT_POSITION_Y, ya)
            sev(EV_ABS, ABS_MT_SLOT, 1)
            sev(EV_ABS, ABS_MT_POSITION_X, xb)
            sev(EV_ABS, ABS_MT_POSITION_Y, yb)
            syn()
            if per_step_delay > 0:
                cmds.append(f"sleep {per_step_delay:.3f}")

        # Nhấc CẢ 2 ngón (tracking id = -1) rồi mới BTN_TOUCH UP + SYN_REPORT
        # cuối cùng - đúng thứ tự chuẩn khi kết thúc 1 cử chỉ multi-touch.
        sev(EV_ABS, ABS_MT_SLOT, 0)
        sev(EV_ABS, ABS_MT_TRACKING_ID, -1)
        sev(EV_ABS, ABS_MT_SLOT, 1)
        sev(EV_ABS, ABS_MT_TRACKING_ID, -1)
        sev(EV_KEY, BTN_TOUCH, 0)
        syn()

        # Gộp TOÀN BỘ thành 1 lệnh `adb shell` DUY NHẤT (nối bằng ";") thay
        # vì gọi sendevent riêng lẻ từng dòng - mỗi lần gọi `adb shell` mới
        # tốn ~50-100ms khởi động tiến trình, với vài chục sự kiện/lần zoom
        # sẽ cộng dồn thành độ trễ rất lớn, phá vỡ cảm giác "1 cử chỉ liền
        # mạch" mà app cần để nhận diện đúng pinch.
        full_cmd = " ; ".join(cmds)
        out, err, rc = self.run_cmd_full(["shell", full_cmd])
        if rc != 0 or (err and ("Permission denied" in err or "No such file" in err)):
            # Giả lập/thiết bị KHÔNG cho phép ghi trực tiếp /dev/input qua
            # shell (hiếm với giả lập nhưng vẫn có thể xảy ra) - xoá cache
            # để lần sau dò lại (phòng trường hợp đổi giả lập khác) và báo
            # thất bại để nơi gọi tự fallback.
            self._touch_device_cache = None
            return False
        return True

    def _pinch_zoom_parallel_swipe(self, cx, cy, start_radius, end_radius, angle_deg=90.0, duration_ms=400):
        """Phương án DỰ PHÒNG khi không dò/ghi được thiết bị cảm ứng thật
        (xem pinch_zoom_sendevent) - bắn ĐỒNG THỜI (song song thật sự qua 2
        luồng threading) 2 lệnh `adb shell input touchscreen swipe` riêng
        biệt, mỗi lệnh là quỹ đạo của 1 "ngón tay" di chuyển đối xứng qua
        tâm. LƯU Ý: cách này tạo ra 2 chuỗi ACTION_DOWN...ACTION_UP ĐỘC LẬP
        chồng thời gian lên nhau, KHÔNG PHẢI 1 MotionEvent 2-pointer thật,
        nên nhiều app/game có ScaleGestureDetector chuẩn sẽ KHÔNG nhận ra
        đây là cử chỉ zoom - chỉ nên coi là phương án cuối cùng khi
        pinch_zoom_sendevent() thất bại."""
        if 0.0 <= float(cx) <= 1.0 and 0.0 <= float(cy) <= 1.0:
            rcx = float(cx) * self.screen_w
            rcy = float(cy) * self.screen_h
        else:
            rcx, rcy = float(cx), float(cy)

        rad = math.radians(angle_deg)
        dx, dy = math.cos(rad), math.sin(rad)

        def _point(radius, sign):
            return (int(rcx + sign * dx * radius), int(rcy + sign * dy * radius))

        a1, a2 = _point(start_radius, -1), _point(end_radius, -1)
        b1, b2 = _point(start_radius, 1), _point(end_radius, 1)
        dur = str(int(duration_ms))

        def _fire(p1, p2):
            self.run_cmd(["shell", "input", "touchscreen", "swipe",
                          str(p1[0]), str(p1[1]), str(p2[0]), str(p2[1]), dur])

        t1 = threading.Thread(target=_fire, args=(a1, a2))
        t2 = threading.Thread(target=_fire, args=(b1, b2))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    def pinch_zoom(self, cx, cy, start_radius, end_radius, angle_deg=90.0, duration_ms=400):
        """Mô phỏng cử chỉ CHỤM/MỞ 2 NGÓN TAY (pinch-to-zoom) GỬI VÀO GIẢ
        LẬP, dùng để phóng to/thu nhỏ nội dung đang hiển thị (bản đồ, camera
        trong game, v.v...). Đây là hàm CHÍNH nên gọi (GUI/logic_engine đều
        gọi hàm này) - tự động chọn cách làm tốt nhất:

        1) THỬ TRƯỚC: pinch_zoom_sendevent() - bắn thẳng sự kiện multi-touch
           CHUẨN (2 pointer trong CÙNG 1 MotionEvent, đúng như 2 ngón tay
           thật) vào thiết bị cảm ứng của giả lập qua `adb shell sendevent`.
           Đây là cách DUY NHẤT được hầu hết app/game (kể cả những app dùng
           ScaleGestureDetector chuẩn của Android) nhận diện đúng là cử chỉ
           zoom. Tự dò thiết bị + biên độ toạ độ, không cần cấu hình tay.
        2) NẾU (1) THẤT BẠI (không dò được thiết bị / giả lập chặn quyền
           ghi /dev/input - hiếm gặp): fallback sang
           _pinch_zoom_parallel_swipe() - bắn song song 2 lệnh `adb shell
           input touchscreen swipe`. Cách này KHÔNG tạo MotionEvent
           2-pointer thật nên CHỈ hoạt động với 1 số app/game có xử lý
           chạm đơn giản, KHÔNG đảm bảo nhận diện được zoom trên mọi app.

        cx, cy: TÂM cử chỉ - theo ĐÚNG quy ước tap()/swipe(): nếu cả 2 giá
            trị đều nằm trong [0..1] thì hiểu là TỈ LỆ trên màn hình, ngược
            lại hiểu là TOẠ ĐỘ PIXEL tuyệt đối.
        start_radius, end_radius (px): khoảng cách từ TÂM đến MỖI ngón tay
            lúc BẮT ĐẦU / lúc KẾT THÚC cử chỉ.
            - end_radius > start_radius (2 ngón TÁCH XA tâm dần)  -> PHÓNG TO
            - end_radius < start_radius (2 ngón CHỤM LẠI gần tâm) -> THU NHỎ
        angle_deg: trục di chuyển của 2 ngón quanh tâm - 90 = dọc (mặc định,
            giống thao tác zoom bản đồ phổ biến), 0 = ngang, có thể đặt góc
            bất kỳ (vd 45 = chéo).
        duration_ms: tổng thời gian thực hiện cử chỉ.

        Trả về "sendevent" nếu đã gửi được bằng multi-touch CHUẨN (cách 1),
        hoặc "parallel_swipe" nếu phải fallback sang cách 2 - nơi gọi (xem
        logic_engine.py) ghi lại giá trị này vào log để biết cử chỉ vừa gửi
        có đáng tin cậy hay không.
        """
        ok = self.pinch_zoom_sendevent(cx, cy, start_radius, end_radius, angle_deg=angle_deg, duration_ms=duration_ms)
        if ok:
            return "sendevent"
        self._pinch_zoom_parallel_swipe(cx, cy, start_radius, end_radius, angle_deg=angle_deg, duration_ms=duration_ms)
        return "parallel_swipe"

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

    # -----------------------------------------------------------------
    # CHẾ ĐỘ SIÊU TỐC (turbo) - nói thêm ở đây vì đây là chỗ khác biệt
    # DUY NHẤT so với đường quét/click bình thường phía trên.
    #
    # VẤN ĐỀ của screencap_fast()/tap_fast_px() (đường bình thường): mỗi
    # lần gọi đều `subprocess.Popen([adb.exe, ...])` - TỨC LÀ TẠO MỘT
    # TIẾN TRÌNH adb.exe HOÀN TOÀN MỚI mỗi lần. Trên máy yếu (ít lõi CPU,
    # ổ đĩa chậm, hoặc có antivirus quét lại file .exe mỗi lần nó chạy),
    # riêng việc TẠO tiến trình có thể tốn 50-300ms - trong khi ảnh cần
    # tìm chỉ hiện trên màn hình vỏn vẹn 0.3-0.5s. Đây chính là lý do máy
    # yếu bị trễ dù CPU/RAM chưa hề "full" - máy đang CHỜ hệ điều hành
    # tạo tiến trình mới, không phải đang tính toán.
    #
    # GIẢI PHÁP của Chế Độ Siêu Tốc: bỏ qua hẳn adb.exe, nói chuyện THẲNG
    # với ADB SERVER (tiến trình adb đang chạy nền, luôn có sẵn mỗi khi
    # bạn dùng ADB dù qua Chế Độ Siêu Tốc hay không) bằng 1 kết nối
    # socket TCP - đúng giao thức "HOST" mà adb.exe cũng dùng bên trong,
    # chỉ khác là KHÔNG PHẢI TẠO TIẾN TRÌNH MỚI cho mỗi lần chụp/click,
    # chỉ tạo 1 socket (rẻ hơn tạo tiến trình rất nhiều, thường dưới
    # 1-2ms trên máy yếu vì luôn là kết nối 127.0.0.1 nội bộ).
    #
    # AN TOÀN: nếu vì lý do gì đó (ADB server đổi cổng, tường lửa chặn...)
    # socket lỗi, các hàm bên dưới TỰ ĐỘNG rơi về lại đường bình thường
    # (screencap_fast/tap_fast_px) thay vì làm cả kịch bản dừng hẳn -
    # Chế Độ Siêu Tốc chỉ nên NHANH HƠN, không được phép KÉM ỔN ĐỊNH HƠN
    # đường cũ.
    # -----------------------------------------------------------------

    @staticmethod
    def _turbo_server_addr():
        """Địa chỉ ADB server - mặc định 127.0.0.1:5037 (chuẩn của mọi bản
        ADB), có tôn trọng biến môi trường ANDROID_ADB_SERVER_PORT nếu
        người dùng từng đổi cổng thủ công."""
        port = os.environ.get("ANDROID_ADB_SERVER_PORT", "5037")
        try:
            port = int(port)
        except ValueError:
            port = 5037
        return ("127.0.0.1", port)

    @staticmethod
    def _turbo_send(sock, message):
        """Gửi 1 lệnh theo đúng khung giao thức HOST của ADB: 4 ký tự hex
        = độ dài, nối liền theo sau là nội dung lệnh (UTF-8)."""
        payload = message.encode("utf-8")
        sock.sendall(("%04x" % len(payload)).encode("ascii") + payload)

    @staticmethod
    def _turbo_read_status(sock):
        """Đọc 4 byte trạng thái ADB server trả về ngay sau khi nhận lệnh
        (OKAY = chấp nhận, FAIL = từ chối kèm lý do dài biến thiên phía
        sau) - ném lỗi nếu FAIL hoặc đóng kết nối bất thường."""
        status = sock.recv(4)
        if status == b"OKAY":
            return
        if status == b"FAIL":
            try:
                length = int(sock.recv(4), 16)
                reason = sock.recv(length).decode("utf-8", errors="ignore")
            except Exception:
                reason = "?"
            raise RuntimeError(f"ADB server từ chối: {reason}")
        raise RuntimeError(f"ADB server phản hồi lạ: {status!r}")

    def _turbo_transact(self, service, timeout=3.0):
        """Mở 1 socket TCP tới ADB server, chuyển tiếp sang đúng thiết bị
        đang dùng (nếu có device_id), gửi `service` rồi đọc TOÀN BỘ dữ
        liệu nhị phân phản hồi cho tới khi thiết bị đóng kết nối. Dùng
        chung cho cả chụp màn hình (service="exec:screencap -p") lẫn
        click (service="exec:input tap X Y")."""
        sock = socket.create_connection(self._turbo_server_addr(), timeout=timeout)
        try:
            sock.settimeout(timeout)
            if self.device_id:
                self._turbo_send(sock, f"host:transport:{self.device_id}")
                self._turbo_read_status(sock)
            self._turbo_send(sock, service)
            self._turbo_read_status(sock)
            chunks = []
            while True:
                data = sock.recv(65536)
                if not data:
                    break
                chunks.append(data)
            return b"".join(chunks)
        finally:
            try:
                sock.close()
            except Exception:
                pass

    # -----------------------------------------------------------------
    # ĐỘNG CƠ SIÊU TỐC MỚI (turbo_engine.py): chụp RAW + quét song song +
    # click bằng sendevent. Các hàm dưới đây CHỈ là lớp nối - hễ động cơ không
    # có/lỗi thì trả NotImplemented / rơi về code socket-PNG cũ bên dưới.
    # -----------------------------------------------------------------

    def _get_turbo_engine(self):
        if self._turbo_eng is not None:
            return self._turbo_eng
        if self._turbo_eng_failed:
            return None
        with self._turbo_eng_lock:
            if self._turbo_eng is not None:
                return self._turbo_eng
            if self._turbo_eng_failed:
                return None
            try:
                import turbo_engine
                self._turbo_eng = turbo_engine.TurboEngine(self)
            except Exception as e:
                self._turbo_eng_failed = True
                self.turbo_engine_error = "%s" % (e,)
                return None
        return self._turbo_eng

    def turbo_poll_single(self, tpl, timeout, conf, region=None, mode=DEFAULT_MATCH_MODE, should_stop=None):
        """Quét liên tục tìm 1 ảnh bằng động cơ Siêu Tốc (không sleep, chụp
        song song). Trả về (coord, score) / (None, None) như _poll_single_
        template, hoặc NotImplemented nếu động cơ không dùng được (nơi gọi
        tự rơi về vòng quét cũ)."""
        eng = self._get_turbo_engine()
        if eng is None:
            return NotImplemented
        try:
            return eng.poll_single(tpl, timeout, conf, region, mode, should_stop)
        except Exception as e:
            self.turbo_last_error = "Động cơ Siêu Tốc lỗi khi quét: %s" % (e,)
            return NotImplemented

    def turbo_poll_any(self, tpl_dict, timeout, conf, region=None, mode=DEFAULT_MATCH_MODE, modes=None, should_stop=None):
        """Bản nhiều ảnh của turbo_poll_single(): (tên, coord, score) hoặc
        (None, None, None) hoặc NotImplemented."""
        eng = self._get_turbo_engine()
        if eng is None:
            return NotImplemented
        try:
            return eng.poll_any(tpl_dict, timeout, conf, region, mode, modes, should_stop)
        except Exception as e:
            self.turbo_last_error = "Động cơ Siêu Tốc lỗi khi quét: %s" % (e,)
            return NotImplemented

    def turbo_pop_notes(self):
        """Lấy (và xoá) các thông báo mới của động cơ Siêu Tốc để ghi Nhật Ký."""
        notes = []
        if self.turbo_engine_error and not self._turbo_err_reported:
            self._turbo_err_reported = True
            notes.append("không tải được turbo_engine.py (%s) -> dùng bản socket-PNG cũ" % self.turbo_engine_error)
        eng = self._turbo_eng
        if eng is not None:
            notes.extend(eng.pop_notes())
        return notes

    def turbo_click_latency_ms(self):
        """ms từ lúc BẮT ĐẦU chụp khung chứa ảnh tới lúc lệnh click vừa được
        gửi đi (None nếu không có số liệu)."""
        return self.turbo_click_ms

    def turbo_timing_breakdown(self):
        """Tách riêng 2 phần cộng nên turbo_click_latency_ms(): thời gian
        CHỤP 1 khung (capture_ms - phụ thuộc thiết bị/giả lập + truyền dữ
        liệu) và thời gian SO KHỚP khung đó (match_ms - phụ thuộc kích
        thước vùng quét + kiểu quét + số ảnh mẫu). Biết được 2 số này TÁCH
        BIỆT mới biết nên tối ưu tiếp ở đâu: capture_ms cao -> nên giảm độ
        phân giải giả lập; match_ms cao -> nên thu nhỏ region hoặc đổi
        sang kiểu quét nhẹ hơn (vd gray_sqdiff). Trả về dict hoặc None nếu
        chưa có số liệu (vd bước chưa từng chạy qua turbo_engine)."""
        tm = self.turbo_last_timing
        if not tm or (time.perf_counter() - tm["frame_t0"]) >= 5.0:
            return None
        return {"capture_ms": tm["capture_ms"], "match_ms": tm["match_ms"],
                "frames_scanned": tm["frames"], "frames_skipped": tm["skipped"],
                "click_ms": self.turbo_last_click_ms, "click_via": self._turbo_click_via,
                "dispatch_ms": tm.get("dispatch_ms"), "wait_ms": tm.get("wait_ms"), "xfer_ms": tm.get("xfer_ms")}

    def turbo_shutdown(self):
        eng = self._turbo_eng
        if eng is not None:
            try:
                eng.close()
            except Exception:
                pass

    def screencap_turbo(self):
        """Bản SIÊU TỐC của screencap_fast() - chụp màn hình qua socket
        thẳng tới ADB server thay vì spawn adb.exe mới. Trả về CÙNG kiểu
        dữ liệu như screencap_fast() (ảnh OpenCV BGR hoặc None) để dùng
        thay thế được ngay trong mọi chỗ đang gọi screencap_fast().
        Tự rơi về screencap_fast() nếu socket lỗi vì bất kỳ lý do gì."""
        eng = self._get_turbo_engine()
        if eng is not None:
            try:
                img = eng.grab_bgr()
                if img is not None:
                    self.turbo_last_error = None
                    return img
            except Exception as e:
                eng._note("chụp RAW lỗi (%s) -> dùng socket-PNG cũ" % (e,))
        try:
            raw_bytes = self._turbo_transact("exec:screencap -p")
        except Exception as e:
            self.turbo_last_error = f"Không chụp được qua socket: {e}"
            return self.screencap_fast()
        if not raw_bytes:
            self.turbo_last_error = "Socket trả về rỗng (không có dữ liệu ảnh)"
            return self.screencap_fast()
        arr = np.frombuffer(raw_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            self.turbo_last_error = "Dữ liệu ảnh nhận qua socket không giải mã được (PNG lỗi)"
            return self.screencap_fast()
        self.screen_h, self.screen_w = img.shape[:2]
        self.turbo_last_error = None
        return img

    def tap_turbo_px(self, x_px, y_px):
        """Bản SIÊU TỐC của tap_fast_px() - bắn lệnh chạm qua socket thẳng
        tới ADB server. Vẫn ĐỢI ADB server xác nhận đã nhận lệnh (bước
        này rất rẻ, chỉ vài ms qua socket nội bộ, khác hẳn việc phải chờ
        cả 1 tiến trình adb.exe khởi động) nên vẫn đáng tin cậy hơn kiểu
        'bắn xong không biết có tới hay không' của tap_fast_px(), mà vẫn
        nhanh hơn nhiều so với spawn tiến trình mới. Tự rơi về
        tap_fast_px() nếu socket lỗi."""
        x_px, y_px = int(round(x_px)), int(round(y_px))
        # Đo riêng THỜI GIAN GỬI LỆNH CHẠM (không tính vào capture_ms/match_ms)
        # - xem turbo_timing_breakdown(): nếu tổng ⚡ cao hơn hẳn chụp+khớp
        # cộng lại, phần chênh lệch gần như chắc chắn nằm ở đây (vd đang rơi
        # về exec:input tap thay vì sendevent, do sendevent chưa khởi động
        # xong hoặc không dùng được trên thiết bị này).
        t_click0 = time.perf_counter()
        self._turbo_click_via = None
        eng = self._get_turbo_engine()
        if eng is not None:
            try:
                if eng.tap(x_px, y_px):
                    self.turbo_last_error = None
                    self.turbo_last_click_ms = (time.perf_counter() - t_click0) * 1000.0
                    self._turbo_click_via = "sendevent"
                    self._turbo_mark_click()
                    return
            except Exception as e:
                eng._note("click sendevent lỗi (%s) -> dùng input tap" % (e,))
        try:
            self._turbo_transact(f"exec:input tap {x_px} {y_px}", timeout=1.5)
            self.turbo_last_error = None
            self._turbo_click_via = "input_tap_socket"
        except Exception as e:
            self.turbo_last_error = f"Không click được qua socket: {e}"
            self.tap_fast_px(x_px, y_px)
            self._turbo_click_via = "input_tap_process_fallback"
        self.turbo_last_click_ms = (time.perf_counter() - t_click0) * 1000.0
        self._turbo_mark_click()

    def _turbo_mark_click(self):
        tm = self.turbo_last_timing
        if tm and (time.perf_counter() - tm["frame_t0"]) < 5.0:
            self.turbo_click_ms = (time.perf_counter() - tm["frame_t0"]) * 1000.0
        else:
            self.turbo_click_ms = None

    def find_image_turbo(self, template_cv, threshold=0.80, region=None, mode=DEFAULT_MATCH_MODE):
        """Bản SIÊU TỐC của find_image_on_screen() - HÀM RIÊNG, không đụng
        gì tới đường quét bình thường (khớp đúng yêu cầu: chỉ bước nào
        BẬT Chế Độ Siêu Tốc mới đi qua đây, còn lại y hệt như cũ). Logic
        so khớp giữ nguyên 100% so với find_image_on_screen(), chỉ khác
        đúng 1 chỗ: dùng screencap_turbo() thay vì screencap_fast()."""
        screen = self.screencap_turbo()
        if screen is None or template_cv is None:
            return None, 0.0

        mode = normalize_match_mode(mode)
        search_img, off_x, off_y = self._crop_region(screen, region)
        s_gray = _prep_for_mode(search_img, mode)
        t_gray = self._prep_template_cached(template_cv, mode)

        if s_gray.shape[0] < t_gray.shape[0] or s_gray.shape[1] < t_gray.shape[1]:
            return None, 0.0

        res = _match_map(s_gray, t_gray, mode)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            h, w = t_gray.shape[:2]
            cx = off_x + max_loc[0] + w // 2
            cy = off_y + max_loc[1] + h // 2
            return (round(cx / self.screen_w, 4), round(cy / self.screen_h, 4)), max_val
        return None, max_val

    def find_any_image_turbo(self, templates_dict, threshold=0.80, region=None, mode=DEFAULT_MATCH_MODE, modes=None):
        """Bản SIÊU TỐC của find_any_image_on_screen() - HÀM RIÊNG, xem
        docstring find_image_turbo() ở trên. Logic so khớp giữ nguyên
        100%, chỉ khác đúng 1 chỗ: dùng screencap_turbo()."""
        screen = self.screencap_turbo()
        if screen is None:
            return None, None, 0.0

        search_img, off_x, off_y = self._crop_region(screen, region)
        s_cache = {}

        best_name = None
        best_pos = None
        highest_score = 0.0

        for name, t_cv in templates_dict.items():
            if t_cv is None:
                continue
            m = self._mode_of(name, mode, modes)
            if m not in s_cache:
                s_cache[m] = _prep_for_mode(search_img, m)
            s_gray = s_cache[m]
            t_gray = self._prep_template_cached(t_cv, m)
            if s_gray.shape[0] < t_gray.shape[0] or s_gray.shape[1] < t_gray.shape[1]:
                continue

            res = _match_map(s_gray, t_gray, m)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= threshold and max_val > highest_score:
                highest_score = max_val
                h, w = t_gray.shape[:2]
                cx = off_x + max_loc[0] + w // 2
                cy = off_y + max_loc[1] + h // 2
                best_name = name
                best_pos = (round(cx / self.screen_w, 4), round(cy / self.screen_h, 4))

        return best_name, best_pos, highest_score

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

    @staticmethod
    def _mode_of(name, mode, modes):
        """Kiểu quét áp dụng cho ảnh `name`: ưu tiên modes[name], nếu không
        có thì dùng `mode` chung; giá trị lạ/None luôn rơi về mặc định."""
        if modes and name in modes:
            return normalize_match_mode(modes[name])
        return normalize_match_mode(mode)

    def _prep_template_cached(self, template_cv, mode):
        """Tiền xử lý ẢNH MẪU (template) theo kiểu quét, có CACHE lại kết
        quả - KHÔNG dùng cho ảnh CHỤP MÀN HÌNH (search_img), vì màn hình
        đổi liên tục mỗi khung hình nên cache ở đó vô nghĩa (và SAI).

        LÝ DO CACHE: các vòng quét chờ ảnh (_poll_single_template/
        _poll_any_template bên logic_engine.py) gọi lại hàm tìm ảnh mỗi
        scan_interval (mặc định 0.1s) CHO TỚI KHI thấy ảnh hoặc hết
        timeout - nghĩa là CÙNG 1 ảnh mẫu bị tiền xử lý lại TỪ ĐẦU hàng
        chục/hàng trăm lần trong 1 lần chờ, dù kết quả luôn giống hệt
        nhau. Tốn nhất là kiểu 'edge' (Gaussian Blur + Canny mỗi lần).

        CACHE KEY dùng NỘI DUNG ảnh (mode, shape, tobytes()) chứ KHÔNG
        dùng id(template_cv) - vì id() của 1 mảng numpy có thể bị Python
        TÁI SỬ DỤNG cho 1 mảng HOÀN TOÀN KHÁC sau khi mảng cũ bị dọn rác,
        nếu chỉ dựa id() có thể vô tình trả nhầm kết quả của ảnh mẫu khác
        - lỗi so khớp sai rất khó phát hiện. Dùng nội dung ảnh làm key tốn
        thêm chút thời gian tính tobytes(), nhưng LUÔN ĐÚNG và vẫn rẻ hơn
        nhiều so với chạy lại Canny/cvtColor mỗi khung hình.

        Giới hạn cache tối đa 500 mục, tự xoá sạch nếu vượt - tránh phình
        bộ nhớ vô hạn nếu kịch bản chạy rất lâu với nhiều ảnh mẫu khác
        nhau, dù thực tế 1 kịch bản thường chỉ dùng vài chục ảnh cố định."""
        key = (mode, template_cv.shape, template_cv.tobytes())
        cached = self._tpl_prep_cache.get(key)
        if cached is not None:
            return cached
        prepped = _prep_for_mode(template_cv, mode)
        if len(self._tpl_prep_cache) > 500:
            self._tpl_prep_cache.clear()
        self._tpl_prep_cache[key] = prepped
        return prepped

    def find_image_on_screen(self, template_cv, threshold=0.80, region=None, mode=DEFAULT_MATCH_MODE):
        """Tìm 1 ảnh mẫu trên màn hình. Trả về ((x, y) tỉ lệ 0..1 của TÂM ảnh
        hoặc None nếu không đạt threshold, điểm khớp cao nhất).

        KIỂU QUÉT: `mode` (str) chọn kiểu so khớp cho các ảnh trong lần gọi
        (xem MATCH_MODES); `modes` (dict tên_ảnh -> kiểu) nếu có sẽ ghi đè riêng
        từng ảnh. Mặc định "gray" = đúng cách quét cũ."""

        screen = self.screencap_fast()
        if screen is None or template_cv is None:
            return None, 0.0

        mode = normalize_match_mode(mode)
        search_img, off_x, off_y = self._crop_region(screen, region)
        s_gray = _prep_for_mode(search_img, mode)
        t_gray = self._prep_template_cached(template_cv, mode)

        if s_gray.shape[0] < t_gray.shape[0] or s_gray.shape[1] < t_gray.shape[1]:
            # Vùng quét đã chọn nhỏ hơn cả ảnh mẫu (vd chọn nhầm khung quá bé)
            # -> không thể so khớp, coi như không thấy thay vì lỗi.
            return None, 0.0

        res = _match_map(s_gray, t_gray, mode)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            h, w = t_gray.shape[:2]
            cx = off_x + max_loc[0] + w // 2
            cy = off_y + max_loc[1] + h // 2
            return (round(cx / self.screen_w, 4), round(cy / self.screen_h, 4)), max_val
        return None, max_val

    def find_image_all_modes(self, template_cv, threshold=0.80, region=None, mode=DEFAULT_MATCH_MODE):
        """Dùng cho 🧪 Test Quét Ảnh: CHỤP 1 LẦN rồi tính điểm khớp cao nhất
        của ảnh mẫu theo TỪNG kiểu quét trong MATCH_MODES - để so sánh nhanh
        xem kiểu nào phân biệt đúng ảnh cần tìm.

        Trả về (pos, score, scores): pos/score tính theo kiểu `mode` (giống
        find_image_on_screen), scores = {kiểu: điểm cao nhất} cho MỌI kiểu."""
        screen = self.screencap_fast()
        if screen is None or template_cv is None:
            return None, 0.0, {}

        mode = normalize_match_mode(mode)
        search_img, off_x, off_y = self._crop_region(screen, region)
        scores = {}
        pos, score = None, 0.0
        for m in MATCH_MODES:
            s_p = _prep_for_mode(search_img, m)
            t_p = self._prep_template_cached(template_cv, m)
            if s_p.shape[0] < t_p.shape[0] or s_p.shape[1] < t_p.shape[1]:
                continue
            res = _match_map(s_p, t_p, m)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            scores[m] = max_val
            if m == mode:
                score = max_val
                if max_val >= threshold:
                    h, w = t_p.shape[:2]
                    cx = off_x + max_loc[0] + w // 2
                    cy = off_y + max_loc[1] + h // 2
                    pos = (round(cx / self.screen_w, 4), round(cy / self.screen_h, 4))
        return pos, score, scores

    def find_any_image_on_screen(self, templates_dict, threshold=0.80, region=None, mode=DEFAULT_MATCH_MODE, modes=None):
        """Logic OR: tìm ảnh khớp CAO NHẤT trong templates_dict. Trả về
        (tên_ảnh, (x, y) tỉ lệ 0..1, điểm) hoặc (None, None, 0.0).

        KIỂU QUÉT: `mode` (str) chọn kiểu so khớp cho các ảnh trong lần gọi
        (xem MATCH_MODES); `modes` (dict tên_ảnh -> kiểu) nếu có sẽ ghi đè riêng
        từng ảnh. Mặc định "gray" = đúng cách quét cũ."""

        screen = self.screencap_fast()
        if screen is None:
            return None, None, 0.0

        search_img, off_x, off_y = self._crop_region(screen, region)
        s_cache = {}  # kiểu -> ảnh màn hình đã tiền xử lý (mỗi kiểu chỉ làm 1 lần)

        best_name = None
        best_pos = None
        highest_score = 0.0

        for name, t_cv in templates_dict.items():
            if t_cv is None:
                continue
            m = self._mode_of(name, mode, modes)
            if m not in s_cache:
                s_cache[m] = _prep_for_mode(search_img, m)
            s_gray = s_cache[m]
            t_gray = self._prep_template_cached(t_cv, m)
            if s_gray.shape[0] < t_gray.shape[0] or s_gray.shape[1] < t_gray.shape[1]:
                continue

            res = _match_map(s_gray, t_gray, m)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= threshold and max_val > highest_score:
                highest_score = max_val
                h, w = t_gray.shape[:2]
                cx = off_x + max_loc[0] + w // 2
                cy = off_y + max_loc[1] + h // 2
                best_name = name
                best_pos = (round(cx / self.screen_w, 4), round(cy / self.screen_h, 4))

        return best_name, best_pos, highest_score

    def find_all_images_on_screen(self, templates_dict, threshold=0.80, region=None, mode=DEFAULT_MATCH_MODE, modes=None):
        """Logic AND: kiểm tra TẤT CẢ ảnh trong templates_dict có xuất hiện
        ĐỒNG THỜI trên CÙNG 1 tấm ảnh chụp màn hình hay không - khác với
        find_any_image_on_screen() (logic OR) là chỉ cần 1 trong số đó xuất
        hiện là đã tính khớp. Dùng cho if_image/multi_image khi người dùng
        chọn chế độ "khớp TẤT CẢ ảnh trong nhóm" (match_mode="and"), vd chỉ
        coi là ĐÚNG khi cả icon A và icon B cùng hiện trên màn hình.

        Trả về (all_matched: bool, results: dict[tên_file] -> (pos, score))
        - results chỉ chứa những ảnh ĐÃ tìm thấy (kể cả khi chưa đủ TẤT CẢ),
        hữu ích để log/debug xem còn thiếu ảnh nào.

        KIỂU QUÉT: `mode` (str) chọn kiểu so khớp cho các ảnh trong lần gọi
        (xem MATCH_MODES); `modes` (dict tên_ảnh -> kiểu) nếu có sẽ ghi đè riêng
        từng ảnh. Mặc định "gray" = đúng cách quét cũ."""

        screen = self.screencap_fast()
        if screen is None or not templates_dict:
            return False, {}

        search_img, off_x, off_y = self._crop_region(screen, region)
        s_cache = {}

        results = {}
        for name, t_cv in templates_dict.items():
            if t_cv is None:
                continue
            m = self._mode_of(name, mode, modes)
            if m not in s_cache:
                s_cache[m] = _prep_for_mode(search_img, m)
            s_gray = s_cache[m]
            t_gray = self._prep_template_cached(t_cv, m)
            if s_gray.shape[0] < t_gray.shape[0] or s_gray.shape[1] < t_gray.shape[1]:
                continue

            res = _match_map(s_gray, t_gray, m)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val >= threshold:
                h, w = t_gray.shape[:2]
                cx = off_x + max_loc[0] + w // 2
                cy = off_y + max_loc[1] + h // 2
                results[name] = ((round(cx / self.screen_w, 4), round(cy / self.screen_h, 4)), max_val)

        all_matched = len(results) == len(templates_dict)
        return all_matched, results

    def find_all_matches_on_screen(self, templates_dict, threshold=0.80, region=None, max_matches=30, min_dist_px=20, mode=DEFAULT_MATCH_MODE, modes=None):
        """Tìm TẤT CẢ vị trí khớp (không chỉ 1 vị trí "tốt nhất") của các
        ảnh mẫu trong templates_dict trên CÙNG 1 tấm ảnh chụp màn hình -
        dùng khi 1 ảnh (vd icon vật phẩm) xuất hiện NHIỀU LẦN cùng lúc và
        cần CLICK HẾT (vd nhặt hết vật phẩm cùng loại trong danh sách) thay
        vì chỉ click đúng 1 vị trí đầu tiên tìm thấy như
        find_image_on_screen()/find_any_image_on_screen().

        Thuật toán: với MỖI ảnh mẫu, chạy cv2.matchTemplate 1 lần rồi lấy
        TẤT CẢ điểm ảnh có độ khớp >= threshold (không chỉ điểm cao nhất
        qua minMaxLoc), sau đó lọc bớt các điểm QUÁ GẦN NHAU (non-max
        suppression đơn giản theo khoảng cách min_dist_px) - vì quanh MỖI
        vị trí khớp thật, matchTemplate thường trả về CẢ 1 CỤM điểm liền kề
        đều vượt threshold (không phải mỗi vị trí thật chỉ đúng 1 điểm),
        nếu không lọc sẽ bị đếm/click trùng 1 chỗ nhiều lần liên tiếp.

        Trả về list các tuple (tên_ảnh, (x,y) tỉ lệ 0..1, score), sắp theo
        score giảm dần, tối đa max_matches phần tử. Trả về [] nếu không
        chụp được màn hình hoặc không có ảnh nào khớp.

        KIỂU QUÉT: `mode` (str) chọn kiểu so khớp cho các ảnh trong lần gọi
        (xem MATCH_MODES); `modes` (dict tên_ảnh -> kiểu) nếu có sẽ ghi đè riêng
        từng ảnh. Mặc định "gray" = đúng cách quét cũ."""
        screen = self.screencap_fast()
        return self._find_all_matches_from_screen(screen, templates_dict, threshold, region, max_matches, min_dist_px, mode, modes)

    def find_all_matches_turbo(self, templates_dict, threshold=0.80, region=None, max_matches=30, min_dist_px=20, mode=DEFAULT_MATCH_MODE, modes=None):
        """Bản SIÊU TỐC (HÀM RIÊNG) của find_all_matches_on_screen() - dùng
        cho bước Quét Đa Ảnh ở chế độ 'Click Tất Cả' khi BẬT Chế Độ Siêu
        Tốc. Thuật toán so khớp giữ nguyên 100% (dùng chung
        _find_all_matches_from_screen với bản thường), chỉ khác đúng 1
        chỗ: chụp màn hình qua screencap_turbo() (socket thẳng tới ADB
        server) thay vì screencap_fast() (spawn tiến trình adb.exe mới)."""
        screen = self.screencap_turbo()
        return self._find_all_matches_from_screen(screen, templates_dict, threshold, region, max_matches, min_dist_px, mode, modes)

    def _find_all_matches_from_screen(self, screen, templates_dict, threshold, region, max_matches, min_dist_px, mode, modes):
        """Lõi thuật toán DÙNG CHUNG cho find_all_matches_on_screen() (bản
        thường) và find_all_matches_turbo() (bản Siêu Tốc) - 2 hàm công
        khai đó chỉ khác nhau ở CÁCH chụp màn hình, còn cách so khớp thì
        phải giống hệt nhau tuyệt đối để không lệch hành vi giữa 2 chế độ."""
        if screen is None or not templates_dict:
            return []

        search_img, off_x, off_y = self._crop_region(screen, region)
        s_cache = {}

        all_hits = []  # (score, cx_px, cy_px, name)
        for name, t_cv in templates_dict.items():
            if t_cv is None:
                continue
            m = self._mode_of(name, mode, modes)
            if m not in s_cache:
                s_cache[m] = _prep_for_mode(search_img, m)
            s_gray = s_cache[m]
            t_gray = self._prep_template_cached(t_cv, m)
            th, tw = t_gray.shape[:2]
            if s_gray.shape[0] < th or s_gray.shape[1] < tw:
                continue

            res = _match_map(s_gray, t_gray, m)
            ys, xs = np.where(res >= threshold)
            for x, y in zip(xs.tolist(), ys.tolist()):
                score = float(res[y, x])
                cx = off_x + x + tw // 2
                cy = off_y + y + th // 2
                all_hits.append((score, cx, cy, name))

        # Sắp theo score GIẢM DẦN rồi lọc các điểm quá gần 1 điểm đã CHỌN
        # trước đó (non-max suppression) - giữ điểm khớp CAO NHẤT trong mỗi
        # cụm, bỏ các điểm liền kề còn lại của CÙNG cụm đó.
        all_hits.sort(key=lambda h: h[0], reverse=True)
        kept = []
        for score, cx, cy, name in all_hits:
            too_close = False
            for _, kx, ky, _ in kept:
                if (cx - kx) ** 2 + (cy - ky) ** 2 < min_dist_px ** 2:
                    too_close = True
                    break
            if not too_close:
                kept.append((score, cx, cy, name))
                if len(kept) >= max_matches:
                    break

        return [
            (name, (round(cx / self.screen_w, 4), round(cy / self.screen_h, 4)), score)
            for score, cx, cy, name in kept
        ]

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
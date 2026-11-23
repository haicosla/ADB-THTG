"""
emulator_manager.py — Quản lý DANH SÁCH GIẢ LẬP LDPlayer đang mở, phục vụ
tính năng "chạy đa luồng, target theo TÊN giả lập" của Dashboard.

Vì sao cần file riêng thay vì chỉ dùng adb_helper.get_devices():
- `adb devices` chỉ trả về SERIAL (vd "emulator-5554", "127.0.0.1:5555"),
  KHÔNG có tên giả lập người dùng đặt (vd "LDPlayer-1", "Nick Vip 2"...).
- LDPlayer có sẵn công cụ dòng lệnh `ldconsole.exe` (nằm CÙNG THƯ MỤC với
  adb.exe) hỗ trợ lệnh `list2` trả về đúng TÊN + HWND cửa sổ + trạng thái
  của từng giả lập đang chạy -> dùng để:
    1) Hiển thị tên thật cho người dùng chọn (thay vì serial vô nghĩa).
    2) Suy ra cổng ADB tương ứng để không cần "adb connect" thủ công.
    3) Lấy sẵn HWND cửa sổ chính -> WindowFinder không cần dò lại bằng
       tên class/tiến trình (vốn KHÔNG phân biệt được nhiều cửa sổ
       LDPlayer giống hệt nhau khi chạy đa luồng cùng lúc).

QUY ƯỚC CỔNG ADB CỦA LDPLAYER (mặc định, không đổi cấu hình nâng cao):
    cổng console (kiểu 'emulator-XXXX')   = 5554 + index * 2
    cổng adb TCP (kiểu '127.0.0.1:YYYY')  = 5555 + index * 2
Cả 2 serial này cùng trỏ tới 1 giả lập. TRƯỚC ĐÂY module này chỉ TỰ TÍNH ra
serial dạng '127.0.0.1:YYYY' theo công thức trên mà KHÔNG hề đối chiếu với
`adb devices` thật - trên nhiều máy, kiểu serial này tồn tại trong
`adb devices` (trạng thái vẫn là 'device') nhưng LDPlayer lại không chuyển
tiếp đúng thao tác chạm/vuốt qua đó, khiến Dashboard "chạy" mà giả lập
không phản hồi gì, trong khi LD Macro Studio (gui.py) vẫn chạy tốt vì nó
luôn cho người dùng chọn thẳng serial thật lấy từ `adb devices`
(thường là dạng 'emulator-XXXX').

GIỜ ĐÃ SỬA: hàm refresh() đối chiếu index của từng giả lập (từ
`ldconsole list2`) với danh sách SERIAL THẬT đang có trong `adb devices`,
ưu tiên dùng đúng kiểu 'emulator-XXXX' (kiểu đã xác nhận hoạt động), chỉ
dùng '127.0.0.1:YYYY' làm phương án dự phòng nếu không thấy serial
'emulator-XXXX' tương ứng, và chỉ dùng công thức đoán mò cũ khi cả 2 kiểu
trên đều không có trong `adb devices` (vd giả lập vừa mở, adb chưa kịp
đăng ký).
"""
import os
import re
import time
import locale
import subprocess
import psutil

# Tên file công cụ dòng lệnh của LDPlayer: bản 9 dùng ldconsole.exe, bản cũ (3/4)
# có thể chỉ có dnconsole.exe - cùng cú pháp lệnh.
_CONSOLE_NAMES = ("ldconsole.exe", "dnconsole.exe")


def _find_console_in_dir(directory):
    for name in _CONSOLE_NAMES:
        candidate = os.path.join(directory, name)
        if directory and os.path.exists(candidate):
            return candidate
    return None


def normalize_console_path(path):
    """Người dùng lỡ chọn nhầm file khác trong thư mục LDPlayer (dnplayer.exe,
    adb.exe...) hoặc chọn cả thư mục -> tự quy về ldconsole.exe/dnconsole.exe
    nằm cùng chỗ nếu có. Không tìm được thì trả nguyên `path`."""
    if not path:
        return path
    if os.path.isdir(path):
        return _find_console_in_dir(path) or path
    if os.path.basename(path).lower() in _CONSOLE_NAMES:
        return path
    return _find_console_in_dir(os.path.dirname(path)) or path


def _decode_console_output(raw):
    """ldconsole in theo code page của Windows (không phải lúc nào cũng UTF-8) -
    thử UTF-8 trước rồi tới code page hệ thống/GBK, để tên giả lập có dấu/chữ
    Trung không làm hỏng cả dòng."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or (len(raw) > 2 and b"\x00" in raw[:8]):
        try:  # 1 số bản console in UTF-16 khi bị chuyển hướng
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8-sig", locale.getpreferredencoding(False), "gbk"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError, TypeError):
            continue
    return raw.decode("utf-8", errors="ignore")


def _parse_list2_line(line):
    """1 dòng `list2`: index,title,top_hwnd,bind_hwnd,android_started,pid,vbox_pid[,w,h,dpi].
    Trả về (index, name, top_hwnd, android_started, pid) hoặc None nếu KHÔNG phải dòng giả lập.
    Đọc các cột số từ PHẢI sang (4/5/8 cột cuối) nên tên có dấu phẩy, kể cả dạng 'Nick,5', vẫn đúng;
    cột android_started chỉ được là 0/1 để loại dòng rác tình cờ toàn số."""
    parts = [x.strip() for x in line.strip().split(",")]
    try:
        index = int(parts[0])
    except ValueError:
        return None
    for n in (8, 5, 4):
        if index < 0 or len(parts) < n + 2:
            continue
        try:
            nums = [int(x) for x in parts[-n:]]
        except ValueError:
            continue
        top_hwnd, _bind, android, pid = nums[:4]
        if android in (0, 1):
            return index, ",".join(parts[1:-n]), top_hwnd, android == 1, pid
    return None


def _parse_list2_output(raw):
    """Toàn bộ stdout của `list2` (bytes) -> list các tuple của _parse_list2_line, bỏ dòng rác/trùng index."""
    rows = {}
    for line in _decode_console_output(raw or b"").splitlines():
        row = _parse_list2_line(line)
        if row:
            rows.setdefault(row[0], row)
    return list(rows.values())


def _dedupe_names(infos):
    """Giả lập trùng tên (vd 2 máy cùng tên 'LDPlayer') -> thêm ' (#index)' để mỗi ô tick/log/lịch
    phân biệt được; tên không trùng giữ NGUYÊN."""
    count = {}
    for i in infos:
        count[i.name] = count.get(i.name, 0) + 1
    for i in infos:
        if count[i.name] > 1:
            i.name = f"{i.name} (#{i.index})"
    return infos


class EmulatorInfo:
    """Thông tin 1 giả lập LDPlayer (có thể đang chạy hoặc đang tắt - xem
    field `running`)."""
    __slots__ = ("index", "name", "hwnd", "adb_serial", "android_started", "running")

    def __init__(self, index, name, hwnd, adb_serial, android_started, running=True):
        self.index = index
        self.name = name
        self.hwnd = hwnd
        self.adb_serial = adb_serial
        self.android_started = android_started
        # running=True mặc định vì phần lớn nơi gọi cũ (refresh()) chỉ liệt
        # kê giả lập ĐANG CHẠY - chỉ list_configured() mới có thể trả về
        # running=False (giả lập đã tạo nhưng đang tắt).
        self.running = running

    def __repr__(self):
        return f"EmulatorInfo(index={self.index}, name={self.name!r}, serial={self.adb_serial}, running={self.running})"


def _hidden_startupinfo():
    """STARTUPINFO ẩn cửa sổ console đen khi gọi ldconsole.exe/adb.exe -
    giống hệt cách adb_helper.py đã làm, tránh flash cửa sổ CMD khi chạy."""
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return info


class EmulatorManager:
    def __init__(self, adb_helper):
        self.adb = adb_helper
        self.ldconsole_path = self._detect_ldconsole()
        self.emulators = []  # list[EmulatorInfo], cập nhật mỗi lần refresh()
        # Lý do `ldconsole list2` KHÔNG dùng được ở lần quét gần nhất ('' = ổn) -
        # Dashboard hiển thị cho người dùng thay vì im lặng báo "không thấy giả lập".
        self.last_console_diag = ""

    # ---------------- DÒ TÌM ldconsole.exe ----------------
    def _detect_ldconsole(self):
        # Ưu tiên: cùng thư mục với adb.exe đã dò được (đáng tin cậy nhất vì
        # chắc chắn đúng bản LDPlayer đang thật sự chạy trên máy).
        adb_dir = os.path.dirname(self.adb.adb_path) if self.adb.adb_path else ""
        if adb_dir:
            candidate = _find_console_in_dir(adb_dir)
            if candidate:
                return candidate

        # Dò qua tiến trình dnplayer.exe đang chạy (giống cách adb_helper.py
        # tự dò đường dẫn adb.exe).
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                if proc.info['name'] and 'dnplayer.exe' in proc.info['name'].lower():
                    ld_dir = os.path.dirname(proc.info['exe'])
                    candidate = _find_console_in_dir(ld_dir)
                    if candidate:
                        return candidate
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        for path in [r"C:\leidian\LDPlayer9\ldconsole.exe", r"D:\leidian\LDPlayer9\ldconsole.exe"]:
            if os.path.exists(path):
                return path
        return None

    def has_ldconsole(self):
        return bool(self.ldconsole_path)

    def set_console_path(self, path):
        """Đặt đường dẫn ldconsole.exe VÀ trỏ adb.exe về cùng thư mục LDPlayer đó (nếu có) - máy mới
        chưa mở giả lập/không cài ở C:,D:\\leidian thì ADBHelper() chỉ còn 'adb' trần, không thấy
        serial thật nào. Gọi cả khi nạp từ cài đặt lúc khởi động."""
        self.ldconsole_path = path
        ld_dir = os.path.dirname(path or "")
        if ld_dir and os.path.exists(os.path.join(ld_dir, "adb.exe")):
            type(self.adb).adb_dir_hint = ld_dir
            self.adb.adb_path = self.adb.detect_adb()

    # ---------------- ĐỐI CHIẾU VỚI SERIAL THẬT TRONG `adb devices` ----------------
    def _real_serials_by_index(self):
        """Quét `adb devices` THẬT (giống hệt cách gui.py/Macro Studio lấy
        danh sách device) và quy về 2 dict {index: serial}, tách theo 2 kiểu
        serial mà LDPlayer đăng ký cho CÙNG 1 giả lập:
            - 'emulator-XXXX'   (index = (XXXX - 5554) // 2) - kiểu ĐÃ XÁC
              NHẬN hoạt động tốt với thao tác chạm/vuốt.
            - '127.0.0.1:YYYY'  (index = (YYYY - 5555) // 2) - có thể xuất
              hiện trong `adb devices` với trạng thái 'device' nhưng KHÔNG
              chắc nhận thao tác chạm đúng trên mọi máy.
        Trả về (emu_style, tcp_style)."""
        emu_style = {}
        tcp_style = {}
        for serial in self.adb.get_devices():
            m = re.match(r"^emulator-(\d+)$", serial)
            if m:
                port = int(m.group(1))
                emu_style[(port - 5554) // 2] = serial
                continue
            m = re.match(r"^127\.0\.0\.1:(\d+)$", serial)
            if m:
                port = int(m.group(1))
                tcp_style[(port - 5555) // 2] = serial
        return emu_style, tcp_style

    def _resolve_real_serial(self, index, emu_style, tcp_style, guessed_serial):
        """Chọn serial THẬT ưu tiên theo thứ tự:
        1) 'emulator-XXXX' đang thật sự có trong `adb devices` (đáng tin cậy nhất).
        2) '127.0.0.1:YYYY' đang thật sự có trong `adb devices` (dự phòng).
        3) Serial ĐOÁN theo công thức cũ (chỉ khi cả 2 kiểu trên đều chưa kịp
           đăng ký với adb server - vd giả lập vừa khởi động)."""
        if index in emu_style:
            return emu_style[index]
        if index in tcp_style:
            return tcp_style[index]
        return guessed_serial

    # ---------------- LIỆT KÊ GIẢ LẬP ----------------
    def refresh(self):
        """Cập nhật self.emulators. Trả về danh sách vừa dò được.
        Nếu không tìm thấy ldconsole.exe, fallback về danh sách serial thô
        từ `adb devices` (KHÔNG có tên thật, chỉ dùng serial làm tên tạm)."""
        if self.has_ldconsole():
            self.emulators = self._list_via_ldconsole()
        else:
            self.emulators = self._list_via_adb_fallback()
        return self.emulators

    def query_list2(self):
        """Chạy `ldconsole list2` -> (rows, diag). rows = list các tuple (index, name,
        top_hwnd, android_started, pid); diag = '' nếu có dòng hợp lệ, ngược lại là
        LÝ DO bằng tiếng Việt (không thấy file / quá thời gian / nội dung nhận được...)."""
        path = self.ldconsole_path
        if not path:
            self.last_console_diag = "Chưa có đường dẫn ldconsole.exe."
            return [], self.last_console_diag
        if not os.path.exists(path):
            self.last_console_diag = f"File không tồn tại: {path}"
            return [], self.last_console_diag
        # Thử vài cách gọi: trực tiếp, rồi chạy TRONG thư mục LDPlayer (1 số bản cần tìm file
        # cấu hình theo thư mục hiện hành). Dùng kết quả đầu tiên có dòng giả lập hợp lệ.
        last_proc, last_err = None, ""
        for extra in ({}, {"cwd": os.path.dirname(path) or None}):
            try:
                proc = subprocess.run(
                    [path, "list2"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    startupinfo=_hidden_startupinfo(), timeout=8, **extra
                )
            except subprocess.TimeoutExpired:
                last_err = f"'{os.path.basename(path)} list2' không trả lời sau 8 giây."
                continue
            except Exception as ex:
                last_err = f"Không chạy được '{path}': {ex}"
                continue
            last_proc = proc
            rows = _parse_list2_output(proc.stdout)
            if rows:
                self.last_console_diag = ""
                return rows, ""

        if last_proc is None:
            self.last_console_diag = last_err
            return [], self.last_console_diag
        out = _decode_console_output(last_proc.stdout or b"")
        err = _decode_console_output(last_proc.stderr or b"")
        snippet = (out.strip() or err.strip())[:200].replace("\r", "").replace("\n", " | ")
        self.last_console_diag = (
            f"'{os.path.basename(path)} list2' (mã thoát {last_proc.returncode}) không trả về dòng giả lập "
            f"hợp lệ nào. Nội dung nhận được: {snippet or '(rỗng)'} [thô: {(last_proc.stdout or b'')[:60]!r}]. "
            f"Kiểm tra đã chọn đúng ldconsole.exe của bản LDPlayer đang dùng (không phải bản cài khác).")
        return [], self.last_console_diag

    def _infos_from_rows(self, rows):
        """rows -> list[EmulatorInfo] (đủ cả giả lập đang TẮT). Giả lập coi là ĐANG CHẠY
        nếu pid > 0 HOẶC đang thật sự có serial của nó trong `adb devices` (1 số bản/máy
        list2 báo pid -1 dù giả lập đã mở và adb thấy bình thường)."""
        emu_style, tcp_style = self._real_serials_by_index()
        result = []
        for index, name, top_hwnd, android_started, pid in rows:
            guessed_serial = f"127.0.0.1:{5555 + index * 2}"
            serial = self._resolve_real_serial(index, emu_style, tcp_style, guessed_serial)
            running = pid > 0 or index in emu_style or index in tcp_style
            result.append(EmulatorInfo(
                index=index, name=name or f"Giả lập {index}",
                hwnd=top_hwnd if top_hwnd > 0 else None,
                adb_serial=serial, android_started=android_started, running=running
            ))
        return _dedupe_names(result)

    def _list_via_ldconsole(self):
        rows, _diag = self.query_list2()
        # refresh() chỉ trả giả lập ĐANG CHẠY (list2/cấu hình vẫn có cả giả lập đang tắt).
        if not rows:
            return [i for i in self._list_via_adb_fallback() if i.running]
        result = [i for i in self._infos_from_rows(rows) if i.running]
        return result if result else [i for i in self._list_via_adb_fallback() if i.running]

    def _names_from_vms_configs(self):
        """{index: tên} đọc thẳng từ file cấu hình LDPlayer (<thư mục cài>/vms/config/leidianN.config,
        khoá "statusSettings.playerName") - dùng khi `ldconsole list2` không dùng được, để vẫn có TÊN
        thật và thấy cả giả lập đang TẮT. Không có/lỗi -> {} (không bao giờ ném lỗi)."""
        names = {}
        if not self.ldconsole_path:
            return names
        try:
            cfg_dir = os.path.join(os.path.dirname(self.ldconsole_path or ""), "vms", "config")
            if not os.path.isdir(cfg_dir):
                return names
            for fname in os.listdir(cfg_dir):
                m = re.match(r"^leidian(\d+)\.config$", fname, re.IGNORECASE)
                if not m:
                    continue
                with open(os.path.join(cfg_dir, fname), "r", encoding="utf-8", errors="ignore") as f:
                    mm = re.search(r'"statusSettings\.playerName"\s*:\s*"([^"]*)"', f.read())
                names[int(m.group(1))] = (mm.group(1).strip() if mm else "") or f"Giả lập {m.group(1)}"
        except Exception:
            return {}
        return names

    def _list_via_adb_fallback(self):
        """Không có ldconsole.exe (hoặc list2 không trả về gì) -> dựng danh sách từ `adb devices`,
        GHÉP thêm tên + các giả lập đang tắt từ file cấu hình LDPlayer nếu đọc được (xem
        _names_from_vms_configs). Nhược điểm còn lại: không có hwnd cửa sổ nên WindowFinder phải tự
        dò cửa sổ theo class/tiến trình (không dùng được attach_hwnd khi mở nhiều giả lập)."""
        emu_style, tcp_style = self._real_serials_by_index()
        configured = self._names_from_vms_configs()
        result = []
        used_serials = set()
        for index in sorted(configured):
            serial = emu_style.get(index) or tcp_style.get(index)
            if serial:
                used_serials.add(serial)
            result.append(EmulatorInfo(
                index=index, name=configured[index], hwnd=None,
                adb_serial=serial or f"127.0.0.1:{5555 + index * 2}",
                android_started=bool(serial), running=bool(serial)
            ))
        # Thiết bị adb chưa khớp giả lập nào đã đọc được (vd điện thoại thật, giả lập khác) -> hiện bằng serial.
        next_index = (max(configured) + 1) if configured else 0
        for serial in self.adb.get_devices():
            if serial in used_serials:
                continue
            result.append(EmulatorInfo(
                index=next_index, name=serial, hwnd=None,
                adb_serial=serial, android_started=True, running=True
            ))
            next_index += 1
        return _dedupe_names(result)

    # ---------------- LIỆT KÊ TẤT CẢ GIẢ LẬP ĐÃ CẤU HÌNH (kể cả đang TẮT) ----------------
    def list_configured(self):
        """Giống refresh() nhưng KHÔNG lọc bỏ giả lập đang tắt (pid <= 0) -
        dùng cho tính năng "tự nhận diện bật/tắt rồi tự khởi động" (xem
        ensure_running). refresh() vẫn giữ nguyên hành vi cũ (chỉ giả lập
        đang chạy) vì đó là danh sách hiển thị cho người dùng TICK CHỌN ở
        Dashboard - không nên hiện giả lập đang tắt vào đó."""
        if not self.has_ldconsole():
            return self._list_via_adb_fallback()
        rows, _diag = self.query_list2()
        if not rows:
            # TRƯỚC ĐÂY trả về danh sách RỖNG ở đây (Dashboard báo "không tìm thấy
            # giả lập nào" dù Macro Studio - lấy thẳng từ `adb devices` - vẫn thấy).
            # Giờ lùi về `adb devices` như refresh(); lý do nằm ở self.last_console_diag.
            return self._list_via_adb_fallback()
        return self._infos_from_rows(rows)

    def find_by_index(self, index):
        """Tìm 1 giả lập theo index trong danh sách CẤU HÌNH ĐẦY ĐỦ (kể cả
        đang tắt). Trả về None nếu không tìm thấy index này (vd đã bị xoá
        khỏi LDMultiPlayer)."""
        for e in self.list_configured():
            if e.index == index:
                return e
        return None

    # ---------------- KẾT NỐI ADB ----------------
    def ensure_adb_connected(self, emulator):
        """Đảm bảo giả lập THẬT SỰ có mặt trong `adb devices` trước khi 1
        luồng riêng dùng serial này.

        LƯU Ý: lệnh `adb connect <serial>` CHỈ áp dụng cho serial dạng
        'host:port' (vd '127.0.0.1:5555') - gọi nó với serial kiểu
        'emulator-XXXX' (kết nối qua local transport, không qua TCP) luôn
        trả lỗi 'unable to connect' dù giả lập vẫn đang chạy hoàn toàn bình
        thường, khiến nút '🔌 Kết nối lại' báo sai "Thất bại". Nên với kiểu
        'emulator-XXXX' chỉ cần kiểm tra nó có đang nằm trong `adb devices`
        hay không, không cần (và không nên) gọi `adb connect`.

        TỰ NÂNG CẤP SERIAL: nếu emulator.adb_serial đang là kiểu
        '127.0.0.1:YYYY' (do lúc refresh() ban đầu giả lập vừa bật, adb
        chưa kịp đăng ký 'emulator-XXXX') mà giờ 'emulator-XXXX' tương ứng
        đã xuất hiện trong `adb devices`, đổi luôn emulator.adb_serial
        sang kiểu đó rồi mới kiểm tra/kết nối. Hàm này được gọi NGAY TRƯỚC
        MỖI LẦN dùng serial (chạy tay/xoay vòng/hẹn giờ) nên đây là chỗ
        duy nhất tự sửa lại được, không cần người dùng mở lại Dashboard."""
        serial = emulator.adb_serial
        if ":" in serial:
            upgraded = f"emulator-{5554 + emulator.index * 2}"
            if upgraded in self.adb.get_devices():
                emulator.adb_serial = upgraded
                serial = upgraded

        if ":" not in serial:
            return serial in self.adb.get_devices()

        try:
            proc = subprocess.run(
                [self.adb.adb_path, "connect", serial],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                startupinfo=_hidden_startupinfo(), timeout=6
            )
            out = proc.stdout.decode("utf-8", errors="ignore").lower()
            return "connected" in out or "already" in out
        except Exception:
            return False

    # ---------------- BẬT / TẮT / KHỞI ĐỘNG LẠI GIẢ LẬP ----------------
    def launch(self, index):
        """Bật giả lập tại `index` qua `ldconsole.exe launch --index N`.
        Lệnh này TRẢ VỀ NGAY (không chờ Android boot xong) - phải gọi
        wait_until_ready() sau đó để biết khi nào thật sự dùng được.
        Trả về (thành_công: bool, thông_báo: str)."""
        if not self.has_ldconsole():
            return False, "Không tìm thấy ldconsole.exe trên máy này."
        try:
            proc = subprocess.run(
                [self.ldconsole_path, "launch", "--index", str(index)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                startupinfo=_hidden_startupinfo(), timeout=10
            )
            msg = proc.stdout.decode("utf-8", errors="ignore").strip()
            # ldconsole báo LỖI thật = mã trả về khác 0 KÈM nội dung ở stderr (chỉ mã khác 0 mà không có
            # nội dung lỗi thì vẫn coi là gửi được, tránh báo sai trên bản LDPlayer trả mã lạ).
            err = proc.stderr.decode("utf-8", errors="ignore").strip()
            if proc.returncode not in (0, None) and err:
                return False, f"ldconsole trả mã {proc.returncode}: {err}"
            return True, msg
        except Exception as e:
            return False, str(e)

    def quit_emulator(self, index):
        """Tắt giả lập tại `index` qua `ldconsole.exe quit --index N`."""
        if not self.has_ldconsole():
            return False, "Không tìm thấy ldconsole.exe trên máy này."
        try:
            proc = subprocess.run(
                [self.ldconsole_path, "quit", "--index", str(index)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                startupinfo=_hidden_startupinfo(), timeout=10
            )
            return True, proc.stdout.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            return False, str(e)

    def reboot(self, index):
        """Khởi động lại giả lập tại `index` qua `ldconsole.exe reboot --index N`."""
        if not self.has_ldconsole():
            return False, "Không tìm thấy ldconsole.exe trên máy này."
        try:
            proc = subprocess.run(
                [self.ldconsole_path, "reboot", "--index", str(index)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                startupinfo=_hidden_startupinfo(), timeout=10
            )
            return True, proc.stdout.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            return False, str(e)

    def _boot_completed(self, serial):
        """Kiểm tra Android bên trong giả lập đã boot xong thật sự chưa
        (không chỉ là tiến trình LDPlayer đã chạy) - tránh trường hợp bắt
        đầu chạm/gõ chữ khi hệ thống Android còn đang khởi động dở."""
        try:
            proc = subprocess.run(
                [self.adb.adb_path, "-s", serial, "shell", "getprop", "sys.boot_completed"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                startupinfo=_hidden_startupinfo(), timeout=6
            )
            return proc.stdout.decode("utf-8", errors="ignore").strip() == "1"
        except Exception:
            return False

    def is_ready(self, info):
        """True nếu 1 EmulatorInfo (đã có sẵn, vd từ find_by_index()) đang
        THẬT SỰ sẵn sàng dùng ngay: tiến trình đang chạy + có serial ADB kết
        nối được + Android bên trong đã boot xong. Dùng để phân biệt 1 giả
        lập "đang chạy nhưng TREO" (running=True nhưng cái này trả False)
        với 1 giả lập chạy bình thường - xem quit_and_wait_stopped()/
        ensure_running() bên dưới."""
        return bool(info and info.running and self.ensure_adb_connected(info) and self._boot_completed(info.adb_serial))

    def quit_and_wait_stopped(self, index, timeout=20, on_log=None):
        """PHỤC HỒI 1 giả lập bị TREO (tiến trình LDPlayer vẫn sống - list2
        vẫn báo running=True - nhưng Android bên trong không phản hồi ADB
        hoặc không boot xong được, dù chờ bao lâu): gọi thẳng launch() lên
        1 giả lập ĐANG CHẠY (dù đang treo) THƯỜNG KHÔNG CÓ TÁC DỤNG GÌ -
        `ldconsole.exe launch` bỏ qua nếu index đó đã ở trạng thái đang
        chạy, nên cứ đứng chờ "boot xong" mãi mà không bao giờ tới - phải
        TẮT HẲN (quit) rồi CHỜ tiến trình thật sự biến mất khỏi `list2`
        trước, thì launch() sau đó mới thật sự khởi động lại được.

        Trả về True nếu đã xác nhận tiến trình dừng hẳn trong `timeout`
        giây, False nếu hết giờ mà vẫn còn thấy running (khi đó nơi gọi vẫn
        nên thử launch() lại - đa phần LDPlayer vẫn kịp dừng ngay sau đó)."""
        def _log(level, msg):
            if on_log:
                try:
                    on_log(level, msg)
                except Exception:
                    pass
        self.quit_emulator(index)
        deadline = time.time() + timeout
        while time.time() < deadline:
            info = self.find_by_index(index)
            if not (info and info.running):
                return True
            time.sleep(1)
        # Giả lập ĐƠ thật thì `ldconsole quit` thường không tắt nổi -> GIẾT CỨNG tiến trình.
        _log("warn", f"Giả lập #{index} không tắt sau {timeout}s chờ - đang GIẾT CỨNG tiến trình LDPlayer...")
        if self.kill_emulator_process(index):
            end = time.time() + 15
            while time.time() < end:
                info = self.find_by_index(index)
                if not (info and info.running):
                    _log("info", f"Đã giết cứng giả lập #{index}.")
                    return True
                time.sleep(1)
        _log("warn", f"Giả lập #{index} vẫn chưa dừng hẳn - vẫn thử khởi động lại.")
        return False

    def kill_emulator_process(self, index):
        """Giết cứng tiến trình của giả lập `index` (pid + vbox_pid lấy từ `ldconsole list2`, kèm
        tiến trình con) bằng psutil - dùng khi `quit` không tắt nổi 1 giả lập đang ĐƠ. Trả về True
        nếu đã giết được ít nhất 1 tiến trình."""
        try:
            import psutil
            proc = subprocess.run([self.ldconsole_path, "list2"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  startupinfo=_hidden_startupinfo(), timeout=8)
            out = proc.stdout.decode("utf-8", errors="ignore")
        except Exception:
            return False
        pids = []
        for line in out.splitlines():
            parts = line.strip().split(",")
            try:
                if len(parts) >= 7 and int(parts[0]) == index:
                    pids = [int(parts[5]), int(parts[6])]
                    break
            except ValueError:
                continue
        killed = False
        for pid in pids:
            if pid <= 0:
                continue
            try:
                p = psutil.Process(pid)
                for child in p.children(recursive=True):
                    try:
                        child.kill()
                    except Exception:
                        pass
                p.kill()
                killed = True
            except Exception:
                pass
        return killed

    def wait_until_stopped(self, index, timeout=30, poll_interval=1):
        """Chờ tới khi giả lập tại `index` THẬT SỰ đã tắt hẳn (tiến trình
        LDPlayer biến mất khỏi list2). Dùng sau `quit_emulator()` (lệnh quit
        chỉ GỬI yêu cầu tắt, giả lập vẫn còn chạy thêm vài giây) - nếu bước
        'Bật giả lập' đến ngay sau 'Tắt giả lập' mà không chờ, is_ready()
        có thể vẫn thấy giả lập đang sống và bỏ qua việc bật lại.
        Trả về True nếu đã tắt hẳn trong `timeout` giây, False nếu chưa."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            info = self.find_by_index(index)
            if not (info and info.running):
                return True
            time.sleep(poll_interval)
        return False

    # ----- PHÂN LOẠI GIAI ĐOẠN KẸT KHI KHỞI ĐỘNG (xem wait_until_ready) -----
    BOOT_STAGE_ORDER = ("process", "adb", "boot")
    BOOT_STAGE_TEXT = {
        "process": "tiến trình LDPlayer CHƯA chạy (lệnh ldconsole launch không bật được giả lập)",
        "adb": "tiến trình đã chạy nhưng ADB CHƯA thấy giả lập (không có trong `adb devices`)",
        "boot": "ADB đã thấy giả lập nhưng Android CHƯA boot xong (sys.boot_completed != 1) - nghi TREO lúc khởi động",
        "stopped": "bị người dùng bấm Dừng",
        "ready": "đã sẵn sàng",
    }
    # Chờ bao lâu (giây) ở 1 giai đoạn thì tự cứu (chỉ khi auto_recover=True):
    BOOT_PROC_GRACE = 30    # chưa thấy tiến trình -> gửi lại launch 1 lần
    BOOT_ADB_GRACE = 60     # chưa thấy trong adb devices -> `adb start-server` 1 lần
    BOOT_BOOT_GRACE = 100   # chưa boot xong -> TẮT HẲN rồi bật lại (tối đa BOOT_MAX_RESTARTS lần)
    BOOT_ADB_RESTART_GRACE = 90   # cửa sổ LDPlayer mở mà ADB vẫn không thấy (vd kẹt 0% + hộp thoại lỗi
                                  # WriteDataDenied) -> cũng TẮT HẲN rồi bật lại (dùng chung BOOT_MAX_RESTARTS)
    BOOT_MIN_FREE_GB = 3    # ổ chứa LDPlayer còn dưới số GB này -> cảnh báo hết dung lượng
    BOOT_MAX_RESTARTS = 1
    BOOT_REPORT_EVERY = 15  # cứ 15s báo 1 dòng "đang chờ giai đoạn ..."

    def check_disk_and_write(self):
        """Kiểm tra nhanh 2 nguyên nhân hay gặp gây lỗi ghi dữ liệu của LDPlayer (WriteDataDenied):
        ổ chứa LDPlayer/VM gần hết dung lượng, hoặc KHÔNG ghi được file vào thư mục đó (thiếu quyền /
        antivirus chặn). Trả về list câu mô tả các vấn đề TÌM THẤY (rỗng = không thấy vấn đề). Không ném lỗi."""
        problems = []
        try:
            import shutil
            base = os.path.dirname(self.ldconsole_path or "")
            if not base or not os.path.isdir(base):
                return problems
            dirs = [base]
            vms = os.path.join(base, "vms")
            if os.path.isdir(vms):
                dirs.append(vms)
            for d in dirs:
                try:
                    free_gb = shutil.disk_usage(d).free / (1024 ** 3)
                    if free_gb < self.BOOT_MIN_FREE_GB:
                        problems.append(f"ổ chứa '{d}' chỉ còn {free_gb:.1f} GB trống")
                except Exception:
                    pass
                probe = os.path.join(d, f".thtg_write_test_{os.getpid()}.tmp")
                try:
                    with open(probe, "wb") as f:
                        f.write(b"x")
                    os.remove(probe)
                except Exception as e:
                    problems.append(f"KHÔNG ghi được file vào '{d}' ({type(e).__name__})")
        except Exception:
            pass
        return problems

    def boot_stage_text(self, index, with_hint=True):
        """Mô tả bằng chữ giai đoạn kẹt của lần wait_until_ready() gần nhất cho giả lập `index`
        ('' nếu chưa có). Dùng để báo lỗi khởi động ĐÚNG chỗ kẹt thay vì câu chung chung. Kẹt ở
        'adb'/'boot' (cửa sổ LDPlayer mở nhưng không lên Android - hay kèm hộp thoại lỗi như
        WriteDataDenied) thì kèm kết quả kiểm tra ổ đĩa/quyền ghi + gợi ý các nguyên nhân thường gặp."""
        st = (getattr(self, "last_boot_stage", {}) or {}).get(index)
        if not st:
            return ""
        txt = self.BOOT_STAGE_TEXT.get(st.get("stage"), st.get("stage", ""))
        extra = []
        if st.get("restarts"):
            extra.append(f"đã tự tắt/bật lại {st['restarts']} lần")
        if st.get("relaunched"):
            extra.append("đã gửi lại lệnh bật")
        out = txt + (f" ({', '.join(extra)})" if extra else "")
        if with_hint and st.get("stage") in ("adb", "boot"):
            problems = self.check_disk_and_write()
            if problems:
                out += " | PHÁT HIỆN: " + "; ".join(problems)
            out += (" | Nếu cửa sổ LDPlayer hiện hộp thoại lỗi (vd WriteDataDenied = lỗi ghi dữ liệu), nguyên nhân "
                    "thường gặp: ổ đĩa đầy; thiếu quyền ghi (chạy Dashboard + LDPlayer bằng quyền Administrator); "
                    "Windows Defender/antivirus chặn (Controlled folder access) - thêm thư mục LDPlayer vào danh "
                    "sách ngoại lệ; còn tiến trình LDPlayer cũ giữ file (tắt dnplayer.exe/LdVBoxHeadless.exe "
                    "trong Task Manager rồi bật lại)")
        return out

    def wait_until_ready(self, index, timeout=90, poll_interval=2, on_wait=None,
                         on_stage=None, should_stop=None, auto_recover=False):
        """Chờ tới khi giả lập tại `index` THẬT SỰ sẵn sàng nhận lệnh ADB, theo 3 GIAI ĐOẠN:
        1) 'process': tiến trình LDPlayer đã chạy (pid > 0, qua list_configured()).
        2) 'adb'    : có serial ADB thật trong `adb devices` (ensure_adb_connected).
        3) 'boot'   : Android đã boot xong (sys.boot_completed == '1').

        Giai đoạn đang kẹt được ghi vào self.last_boot_stage[index] (xem boot_stage_text) để nơi gọi
        báo lỗi đúng chỗ. `on_wait` (nếu có) được gọi mỗi vòng chờ. `on_stage(level, msg)` (nếu có)
        nhận log đổi giai đoạn + nhắc tiến độ mỗi BOOT_REPORT_EVERY giây + log các bước tự cứu.
        `should_stop()` (nếu có) trả True -> thoát sớm (trả None, giai đoạn 'stopped').

        auto_recover=True: tự cứu theo giai đoạn - 'process' quá BOOT_PROC_GRACE giây -> gửi lại
        launch 1 lần; 'adb' quá BOOT_ADB_GRACE -> `adb start-server` 1 lần (KHÔNG kill-server vì
        sẽ ngắt cả các giả lập khác); 'boot' quá BOOT_BOOT_GRACE -> tắt hẳn + bật lại (tối đa
        BOOT_MAX_RESTARTS lần, mỗi lần tính lại đồng hồ timeout). Mặc định False = như cũ.

        Trả về EmulatorInfo nếu sẵn sàng trong thời gian timeout (giây), ngược lại trả về None."""
        if not hasattr(self, "last_boot_stage"):
            self.last_boot_stage = {}

        def _emit(level, msg):
            if on_stage:
                try:
                    on_stage(level, msg)
                except Exception:
                    pass

        start = time.time()
        stage, stage_t0, last_report = None, start, start
        relaunched, adb_kicked, restarts = False, False, 0

        def _record(st):
            self.last_boot_stage[index] = {"stage": st, "restarts": restarts, "relaunched": relaunched,
                                           "elapsed": time.time() - start, "t": time.time()}

        while time.time() - start < timeout:
            if should_stop and should_stop():
                _record("stopped")
                return None
            info = self.find_by_index(index)
            if not (info and info.running):
                cur = "process"
            elif not self.ensure_adb_connected(info):
                cur = "adb"
            elif not self._boot_completed(info.adb_serial):
                cur = "boot"
            else:
                _record("ready")
                return info

            now = time.time()
            if cur != stage:
                stage, stage_t0, last_report = cur, now, now
                _record(cur)
                _emit("info", f"Khởi động giả lập #{index}: giai đoạn {self.BOOT_STAGE_ORDER.index(cur) + 1}/3 - "
                              f"{self.BOOT_STAGE_TEXT[cur]}...")
            elif now - last_report >= self.BOOT_REPORT_EVERY:
                last_report = now
                _record(cur)
                _emit("info", f"Khởi động giả lập #{index}: vẫn đang kẹt giai đoạn "
                              f"{self.BOOT_STAGE_ORDER.index(cur) + 1}/3 ({int(now - stage_t0)}s) - "
                              f"{self.BOOT_STAGE_TEXT[cur]}")

            if auto_recover:
                waited = now - stage_t0
                if cur == "process" and not relaunched and waited >= self.BOOT_PROC_GRACE:
                    relaunched = True
                    ok, msg = self.launch(index)
                    _emit("warn", f"Giả lập #{index}: {int(waited)}s mà tiến trình chưa chạy - đã gửi lại lệnh bật"
                                  + ("" if ok else f" (LỖI: {msg})") + ".")
                    stage_t0 = time.time()
                elif cur == "adb" and not adb_kicked and waited >= self.BOOT_ADB_GRACE:
                    adb_kicked = True
                    _emit("warn", f"Giả lập #{index}: {int(waited)}s mà ADB chưa thấy giả lập - thử `adb start-server`.")
                    try:
                        subprocess.run([self.adb.adb_path, "start-server"], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, startupinfo=_hidden_startupinfo(), timeout=15)
                    except Exception:
                        pass
                elif (restarts < self.BOOT_MAX_RESTARTS
                      and ((cur == "boot" and waited >= self.BOOT_BOOT_GRACE)
                           or (cur == "adb" and waited >= self.BOOT_ADB_RESTART_GRACE))):
                    restarts += 1
                    _emit("warn", f"Giả lập #{index}: kẹt giai đoạn '{cur}' {int(waited)}s "
                                  f"({self.BOOT_STAGE_TEXT[cur]}) - nghi TREO/LỖI, "
                                  f"đang TẮT HẲN rồi bật lại (lần {restarts}/{self.BOOT_MAX_RESTARTS})...")
                    for _p in self.check_disk_and_write():
                        _emit("warn", f"Giả lập #{index}: phát hiện {_p} - có thể là nguyên nhân lỗi khởi động.")
                    self.quit_and_wait_stopped(index, on_log=on_stage)
                    ok, msg = self.launch(index)
                    if not ok:
                        _emit("error", f"Giả lập #{index}: bật lại thất bại: {msg}")
                    start = time.time()          # tính lại đồng hồ timeout cho lần khởi động mới
                    stage, stage_t0, last_report = None, start, start
                    relaunched = adb_kicked = False
                    continue

            if on_wait:
                try:
                    on_wait()
                except Exception:
                    pass
            time.sleep(poll_interval)
        if stage:
            _record(stage)
        return None

    def ensure_running(self, index, timeout=90, on_log=None):
        """Đảm bảo giả lập tại `index` ĐANG BẬT VÀ SẴN SÀNG dùng được ngay:
        - Nếu đang chạy sẵn và đã boot xong -> trả về luôn, không làm gì thêm.
        - Nếu đang TẮT -> tự gọi launch() rồi chờ tới khi sẵn sàng (tối đa
          `timeout` giây).
        - Nếu ĐANG CHẠY nhưng KHÔNG SẴN SÀNG (mất kết nối ADB hoặc không
          boot xong dù process vẫn sống) = có thể đang TREO: gọi launch()
          thẳng lúc này KHÔNG có tác dụng gì (LDPlayer bỏ qua vì thấy index
          "đã chạy") - phải tự TẮT HẲN (quit_and_wait_stopped) rồi mới
          launch() lại thì mới thật sự phục hồi được, thay vì cứ đứng chờ
          "boot xong" mãi rồi báo lỗi "khởi động quá lâu" trong khi thực ra
          chẳng có gì đang khởi động cả.

        `on_log(level, message)` (tuỳ chọn) dùng để báo tiến độ ra Dashboard.

        Trả về (EmulatorInfo, đã_tự_khởi_động: bool) khi thành công, hoặc
        (None, False) nếu không thể bật được / chờ quá lâu."""
        def _log(level, msg):
            if on_log:
                try:
                    on_log(level, msg)
                except Exception:
                    pass

        info = self.find_by_index(index)
        if self.is_ready(info):
            return info, False

        if info is None:
            _log("error", f"Không tìm thấy giả lập nào có index #{index} trong LDPlayer (có thể đã bị xoá).")
            return None, False

        if info.running:
            _log("warn", f"Giả lập '{info.name}' (#{index}) đang chạy nhưng KHÔNG PHẢN HỒI (mất kết nối ADB "
                          f"hoặc chưa boot xong được, dù tiến trình vẫn sống) - có thể đang TREO. Đang tự TẮT "
                          f"HẲN rồi khởi động lại (launch() sẽ KHÔNG có tác dụng nếu cứ để nguyên đang chạy)...")
            self.quit_and_wait_stopped(index, on_log=on_log)
        else:
            _log("info", f"Giả lập '{info.name}' (#{index}) đang TẮT - đang tự khởi động...")

        ok, msg = self.launch(index)
        if not ok:
            _log("error", f"Không khởi động được giả lập '{info.name}' (#{index}): {msg}")
            return None, False

        ready = self.wait_until_ready(index, timeout=timeout, on_stage=on_log, auto_recover=True)
        if not ready:
            _log("error", f"Giả lập '{info.name}' (#{index}) khởi động quá lâu (>{timeout}s) - bỏ qua. "
                          f"Kẹt ở: {self.boot_stage_text(index) or 'không rõ'}.")
            return None, False

        _log("success", f"Giả lập '{ready.name}' (#{index}) đã bật xong và sẵn sàng.")
        return ready, True
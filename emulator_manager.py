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
import subprocess
import psutil


class EmulatorInfo:
    """Thông tin 1 giả lập LDPlayer đang chạy."""
    __slots__ = ("index", "name", "hwnd", "adb_serial", "android_started")

    def __init__(self, index, name, hwnd, adb_serial, android_started):
        self.index = index
        self.name = name
        self.hwnd = hwnd
        self.adb_serial = adb_serial
        self.android_started = android_started

    def __repr__(self):
        return f"EmulatorInfo(index={self.index}, name={self.name!r}, serial={self.adb_serial})"


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

    # ---------------- DÒ TÌM ldconsole.exe ----------------
    def _detect_ldconsole(self):
        # Ưu tiên: cùng thư mục với adb.exe đã dò được (đáng tin cậy nhất vì
        # chắc chắn đúng bản LDPlayer đang thật sự chạy trên máy).
        adb_dir = os.path.dirname(self.adb.adb_path) if self.adb.adb_path else ""
        if adb_dir:
            candidate = os.path.join(adb_dir, "ldconsole.exe")
            if os.path.exists(candidate):
                return candidate

        # Dò qua tiến trình dnplayer.exe đang chạy (giống cách adb_helper.py
        # tự dò đường dẫn adb.exe).
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                if proc.info['name'] and 'dnplayer.exe' in proc.info['name'].lower():
                    ld_dir = os.path.dirname(proc.info['exe'])
                    candidate = os.path.join(ld_dir, "ldconsole.exe")
                    if os.path.exists(candidate):
                        return candidate
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        for path in [r"C:\leidian\LDPlayer9\ldconsole.exe", r"D:\leidian\LDPlayer9\ldconsole.exe"]:
            if os.path.exists(path):
                return path
        return None

    def has_ldconsole(self):
        return bool(self.ldconsole_path)

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

    def _list_via_ldconsole(self):
        try:
            proc = subprocess.run(
                [self.ldconsole_path, "list2"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                startupinfo=_hidden_startupinfo(), timeout=8
            )
            out = proc.stdout.decode("utf-8", errors="ignore")
        except Exception:
            return self._list_via_adb_fallback()

        emu_style, tcp_style = self._real_serials_by_index()

        result = []
        # Định dạng mỗi dòng: index,title,top_hwnd,bind_hwnd,android_started,pid,vbox_pid
        for line in out.splitlines():
            parts = line.strip().split(",")
            if len(parts) < 6:
                continue
            try:
                index = int(parts[0])
                name = parts[1]
                top_hwnd = int(parts[2])
                android_started = parts[4] == "1"
                pid = int(parts[5])
            except (ValueError, IndexError):
                continue

            # Chỉ lấy giả lập ĐANG THẬT SỰ CHẠY (có pid tiến trình > 0) -
            # ldconsole list2 vẫn liệt kê cả những giả lập đã tạo nhưng
            # đang tắt, ta không muốn hiện chúng trong danh sách target.
            if pid <= 0:
                continue

            guessed_serial = f"127.0.0.1:{5555 + index * 2}"
            serial = self._resolve_real_serial(index, emu_style, tcp_style, guessed_serial)
            result.append(EmulatorInfo(
                index=index, name=name or f"Giả lập {index}",
                hwnd=top_hwnd if top_hwnd > 0 else None,
                adb_serial=serial, android_started=android_started
            ))

        return result if result else self._list_via_adb_fallback()

    def _list_via_adb_fallback(self):
        """Không có ldconsole.exe (hoặc list2 không trả về gì) -> chỉ còn
        cách dùng thẳng serial ADB làm tên hiển thị. Nhược điểm: không phân
        biệt được multi-instance theo TÊN THẬT, và WindowFinder sẽ phải tự
        dò cửa sổ theo class/tiến trình như cũ (không dùng được attach_hwnd)."""
        result = []
        for i, serial in enumerate(self.adb.get_devices()):
            result.append(EmulatorInfo(
                index=i, name=serial, hwnd=None,
                adb_serial=serial, android_started=True
            ))
        return result

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
        hay không, không cần (và không nên) gọi `adb connect`."""
        serial = emulator.adb_serial
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
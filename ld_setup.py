"""
ld_setup.py — Cài đặt LDPlayer cho MÁY MỚI bằng 1 lần bấm (không import tkinter):
  1) Đặt độ phân giải giả lập về 1280x720 (DPI 240) qua `ldconsole modify --resolution`.
  2) BẬT "Gỡ lỗi ADB" (ADB debugging) của giả lập bằng cách ghi khoá
     `basicSettings.adbDebug` trong <thư mục LDPlayer>/vms/config/leidianN.config
     (ldconsole KHÔNG có lệnh cho việc này).

Cả 2 thay đổi chỉ có hiệu lực khi giả lập ĐANG TẮT (LDPlayer ghi đè lại file cấu hình
lúc thoát) - nơi gọi (dashboard_ld_setup.py) tự tắt giả lập trước, áp dụng xong bật lại.

Giá trị `basicSettings.adbDebug`: 0 = tắt, 1 = bật kết nối LOCAL (đủ cho tool này), 2 = bật cả
kết nối từ xa. Tên khoá/ý nghĩa dựa trên file cấu hình của LDPlayer 9 - mọi hàm ở đây ĐỌC LẠI
file sau khi ghi để xác nhận, không khớp thì báo lỗi chứ không im lặng coi như thành công.
"""
import json
import os
import shutil
import subprocess

TARGET_WIDTH = 1280
TARGET_HEIGHT = 720
TARGET_DPI = 240
ADB_DEBUG_KEY = "basicSettings.adbDebug"
RES_KEY = "basicSettings.resolution"
DPI_KEY = "basicSettings.resolutionDpi"
ADB_DEBUG_LABELS = {0: "Tắt", 1: "Bật (local)", 2: "Bật (từ xa)"}


def ld_dir_of(console_path):
    return os.path.dirname(console_path or "")


def config_path(console_path, index):
    """<thư mục LDPlayer>/vms/config/leidianN.config (có thể chưa tồn tại)."""
    return os.path.join(ld_dir_of(console_path), "vms", "config", f"leidian{int(index)}.config")


def _load_config(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("file cấu hình không phải đối tượng JSON")
    return data


def read_settings(console_path, index):
    """Đọc (không ném lỗi) {'adb_debug': int|None, 'width','height','dpi': int|None}."""
    out = {"adb_debug": None, "width": None, "height": None, "dpi": None}
    try:
        cfg = _load_config(config_path(console_path, index))
    except Exception:
        return out
    try:
        v = cfg.get(ADB_DEBUG_KEY)
        out["adb_debug"] = int(v) if v is not None else 0
    except Exception:
        pass
    res = cfg.get(RES_KEY)
    if isinstance(res, dict):
        try:
            out["width"], out["height"] = int(res.get("width")), int(res.get("height"))
        except Exception:
            pass
    try:
        if cfg.get(DPI_KEY) is not None:
            out["dpi"] = int(cfg.get(DPI_KEY))
    except Exception:
        pass
    return out


def describe_settings(st):
    res = f"{st['width']}x{st['height']}" + (f"/{st['dpi']}" if st.get("dpi") else "") \
        if st.get("width") and st.get("height") else "?"
    adb = ADB_DEBUG_LABELS.get(st.get("adb_debug"), "?") if st.get("adb_debug") is not None else "?"
    return res, adb


def _backup_once(path):
    bak = path + ".bak_ldsetup"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)


def _write_config(path, cfg):
    tmp = path + ".tmp_ldsetup"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)
    os.replace(tmp, path)


def set_adb_debug(console_path, index, mode=1):
    """Ghi `basicSettings.adbDebug` = mode (giả lập PHẢI đang tắt). Trả về (ok, thông_báo)."""
    path = config_path(console_path, index)
    if not os.path.isfile(path):
        return False, f"Không thấy file cấu hình: {path}"
    try:
        cfg = _load_config(path)
        if cfg.get(ADB_DEBUG_KEY) == mode:
            return True, "Gỡ lỗi ADB đã ở trạng thái yêu cầu"
        _backup_once(path)
        cfg[ADB_DEBUG_KEY] = mode
        _write_config(path, cfg)
        if _load_config(path).get(ADB_DEBUG_KEY) != mode:
            return False, "Ghi xong nhưng đọc lại không khớp"
        return True, f"adbDebug = {mode} ({ADB_DEBUG_LABELS.get(mode, mode)})"
    except Exception as e:
        return False, f"Lỗi ghi cấu hình: {e}"


def _run_console(console_path, args, timeout=30):
    kw = {}
    if hasattr(subprocess, "STARTUPINFO"):
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kw["startupinfo"] = info
    proc = subprocess.run([console_path] + list(args), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout, **kw)
    text = (proc.stdout or b"").decode("utf-8", errors="ignore").strip()
    err = (proc.stderr or b"").decode("utf-8", errors="ignore").strip()
    return proc.returncode, (text or err)


def set_resolution(console_path, index, width=TARGET_WIDTH, height=TARGET_HEIGHT, dpi=TARGET_DPI):
    """`ldconsole modify --index N --resolution W,H,DPI` rồi đọc lại file cấu hình để xác nhận
    (giả lập PHẢI đang tắt). Trả về (ok, thông_báo)."""
    try:
        code, msg = _run_console(console_path, ["modify", "--index", str(index),
                                                "--resolution", f"{width},{height},{dpi}"])
    except Exception as e:
        return False, f"Không chạy được ldconsole modify: {e}"
    st = read_settings(console_path, index)
    if st["width"] == width and st["height"] == height:
        return True, f"{width}x{height}/{dpi}"
    if st["width"] is None:
        # Không đọc được định dạng cấu hình để đối chiếu -> tin theo mã thoát của ldconsole.
        return (code == 0), (f"{width}x{height}/{dpi} (chưa xác nhận được qua file cấu hình)"
                             if code == 0 else f"ldconsole modify lỗi (mã {code}): {msg}")
    return False, f"ldconsole modify chạy (mã {code}) nhưng cấu hình vẫn là {st['width']}x{st['height']}: {msg}"


def apply_to_emulator(console_path, index, set_res=True, adb_mode=1):
    """Áp dụng các tuỳ chọn cho 1 giả lập ĐÃ TẮT. adb_mode=None -> không đụng ADB.
    Trả về list (ok, mô_tả) từng việc."""
    results = []
    if set_res:
        ok, msg = set_resolution(console_path, index)
        results.append((ok, f"Độ phân giải: {msg}"))
    if adb_mode is not None:
        ok, msg = set_adb_debug(console_path, index, adb_mode)
        results.append((ok, f"Gỡ lỗi ADB: {msg}"))
    return results


def looks_like_console(path):
    return bool(path) and os.path.isfile(path) and \
        os.path.basename(path).lower() in ("ldconsole.exe", "dnconsole.exe")


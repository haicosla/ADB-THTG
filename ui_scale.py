"""
ui_scale.py - TỶ LỆ GIAO DIỆN (UX scale) cho Dashboard: 50% = toàn bộ nhỏ lại một nửa (chữ, nút, khung,
khoảng đệm, cửa sổ popup), 100% = như cũ, 200% = to gấp đôi.

Không import dashboard_*; chỉ dùng tkinter + json nên import ở đâu cũng được.

CÁCH HOẠT ĐỘNG (cài 1 lần bằng `install(root, percent)` TRƯỚC khi dựng bất kỳ widget nào):
  1. CHỮ: mọi font trong code khai báo bằng POINT, nên đổi `tk scaling` = scaling gốc x tỷ lệ là chữ (và mọi
     thứ đo theo chữ như nút RoundedButton, ô Entry/Combobox, Listbox...) tự to/nhỏ theo.
  2. PIXEL CỨNG (padx/pady, width/height của Frame/Canvas, wraplength, viền...): các hàm tạo widget và
     pack/grid được vá nhẹ để NHÂN các giá trị số nguyên theo tỷ lệ NGAY LÚC TẠO / LÚC pack/grid.
     Cố ý KHÔNG nhân ở `widget.config(...)`, `place(...)`, `itemconfigure(...)` vì các chỗ đó trong code
     thường truyền số vừa ĐO THẬT (winfo_width...), nhân nữa sẽ bị đúp.
  3. CỬA SỔ: `win.geometry("WxH")`, `minsize/maxsize` nhân theo tỷ lệ (không đụng phần +x+y) và bị chặn không
     vượt quá màn hình. `window_geometry.py` lưu kích thước đã CHIA lại tỷ lệ nên đổi tỷ lệ không làm lệch.
  4. Widget tự vẽ (RoundedButton, DarkCheck, FlowBar...) tự gọi `S(n)` cho các hằng pixel của riêng chúng.

Dùng trong code mới: `from ui_scale import S, raw`
  S(n)        -> n nhân tỷ lệ hiện tại (làm tròn, số khác 0 luôn >= 1).
  with raw(): -> tạm tắt việc nhân tự động (khi truyền cho Tk 1 con số đã đo thật / đã nhân sẵn).

Tỷ lệ lưu ở dashboard_settings.json khoá "ui_scale" (số nguyên %, 50..200) và chỉ có hiệu lực SAU KHI KHỞI
ĐỘNG LẠI (widget đã dựng không đổi cỡ tại chỗ được).
"""
import json
import re
import subprocess
import sys
import tkinter as tk
from contextlib import contextmanager

MIN_PERCENT = 50
MAX_PERCENT = 200
STEP_PERCENT = 5
DEFAULT_PERCENT = 100
SETTINGS_KEY = "ui_scale"

_scale = 1.0          # tỷ lệ đang áp dụng (1.0 = 100%)
_raw_depth = 0        # >0: đang trong `with raw():` -> không nhân tự động
_installed = False


# ============================ tiện ích ============================
def clamp_percent(value):
    """Ép về số nguyên trong [MIN_PERCENT, MAX_PERCENT], bội của STEP_PERCENT; lỗi -> 100."""
    try:
        v = int(round(float(value) / STEP_PERCENT) * STEP_PERCENT)
    except (TypeError, ValueError):
        return DEFAULT_PERCENT
    return max(MIN_PERCENT, min(MAX_PERCENT, v))


def load_percent(settings_path):
    """Đọc tỷ lệ đã lưu (%), chưa có/lỗi -> 100."""
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            return clamp_percent(json.load(f).get(SETTINGS_KEY, DEFAULT_PERCENT))
    except Exception:
        return DEFAULT_PERCENT


def get_scale():
    return _scale


def get_percent():
    return int(round(_scale * 100))


def S(n):
    """Nhân 1 số pixel theo tỷ lệ hiện tại. 0 giữ 0, số khác 0 không bao giờ nhỏ hơn 1 (để vạch 1px không mất)."""
    if _scale == 1.0 or n == 0:
        return n
    try:
        v = n * _scale
        r = int(round(v))
        if r == 0:
            r = 1 if v > 0 else -1
        return r
    except TypeError:
        return n


def S2(pair):
    """Như S() nhưng cho (a, b) hoặc 1 số."""
    if isinstance(pair, (tuple, list)):
        return tuple(S(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else x for x in pair)
    return S(pair)


def unscale(n):
    """Ngược của S() - dùng khi LƯU kích thước cửa sổ."""
    if _scale == 1.0:
        return n
    return max(1, int(round(n / _scale)))


def unscale_geometry(geo):
    """'WxH+x+y' đang đo THẬT -> 'W'xH'+x+y' đã chia tỷ lệ (để lưu; lúc khôi phục geometry() nhân lại)."""
    if _scale == 1.0 or not isinstance(geo, str):
        return geo
    m = re.match(r"^(\d+)x(\d+)(.*)$", geo.strip())
    if not m:
        return geo
    return f"{unscale(int(m.group(1)))}x{unscale(int(m.group(2)))}{m.group(3)}"


@contextmanager
def raw():
    """Trong khối này Tk nhận đúng số pixel truyền vào (không nhân tỷ lệ)."""
    global _raw_depth
    _raw_depth += 1
    try:
        yield
    finally:
        _raw_depth -= 1


def _active():
    return _scale != 1.0 and _raw_depth == 0


# ============================ vá Tk ============================
# Tuỳ chọn pixel LUÔN là pixel ở mọi loại widget.
_PX_KEYS = {"padx", "pady", "ipadx", "ipady", "borderwidth", "bd", "highlightthickness", "wraplength",
            "insertwidth", "selectborderwidth", "sliderlength", "sashwidth", "sashpad", "handlesize",
            "spacing1", "spacing2", "spacing3", "minsize", "pad", "length"}
# width/height là pixel CHỈ ở các loại widget này (ở Label/Button/Entry/Text/Listbox là ký tự/dòng -> đã theo chữ).
_PX_WH_WIDGETS = {"frame", "labelframe", "canvas", "scrollbar", "panedwindow", "scale"}
_WH_KEYS = {"width", "height"}


def _scale_value(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return S(v)
    if isinstance(v, (tuple, list)):
        return tuple(_scale_value(x) for x in v)
    if isinstance(v, str) and re.fullmatch(r"-?\d+", v.strip() or "x"):
        return S(int(v))
    return v


def _scale_opts(opts, widget_name, geometry_mgr=False):
    """Trả bản sao dict tuỳ chọn đã nhân các khoá pixel."""
    out = {}
    wh_ok = (not geometry_mgr) and widget_name in _PX_WH_WIDGETS
    for k, v in opts.items():
        if k in _PX_KEYS or (wh_ok and k in _WH_KEYS):
            out[k] = _scale_value(v)
        else:
            out[k] = v
    return out


def _patch_tk():
    # --- tạo widget ---
    orig_init = tk.BaseWidget.__init__

    def _init(self, master, widgetName, cnf={}, kw={}, extra=()):
        if _active():
            cnf = _scale_opts(cnf, widgetName) if isinstance(cnf, dict) else cnf
            kw = _scale_opts(kw, widgetName) if isinstance(kw, dict) else kw
        orig_init(self, master, widgetName, cnf, kw, extra)

    tk.BaseWidget.__init__ = _init

    # --- pack / grid (chỉ các khoá đệm; không đụng row/column/side...) ---
    orig_pack = tk.Pack.pack_configure

    def _pack(self, cnf={}, **kw):
        if _active():
            cnf = _scale_opts(cnf, "", True) if isinstance(cnf, dict) else cnf
            kw = _scale_opts(kw, "", True)
        return orig_pack(self, cnf, **kw)

    tk.Pack.pack_configure = _pack
    tk.Pack.pack = _pack

    orig_grid = tk.Grid.grid_configure

    def _grid(self, cnf={}, **kw):
        if _active():
            cnf = _scale_opts(cnf, "", True) if isinstance(cnf, dict) else cnf
            kw = _scale_opts(kw, "", True)
        return orig_grid(self, cnf, **kw)

    tk.Grid.grid_configure = _grid
    tk.Grid.grid = _grid

    # --- grid_columnconfigure / rowconfigure (minsize, pad) ---
    orig_gc = tk.Misc._grid_configure

    def _gc(self, command, index, cnf, kw):
        if _active() and not (isinstance(cnf, str) and not kw):     # không phải truy vấn
            if isinstance(cnf, dict):
                cnf = _scale_opts(cnf, "", True)
            if isinstance(kw, dict):
                kw = _scale_opts(kw, "", True)
        return orig_gc(self, command, index, cnf, kw)

    tk.Misc._grid_configure = _gc

    # --- kích thước cửa sổ ---
    geo_re = re.compile(r"^(\d+)x(\d+)(.*)$")
    orig_geo = tk.Wm.wm_geometry

    def _geometry(self, newGeometry=None):
        if newGeometry and isinstance(newGeometry, str) and _active():
            m = geo_re.match(newGeometry.strip())
            if m:
                w, h = S(int(m.group(1))), S(int(m.group(2)))
                try:
                    w = min(w, self.winfo_screenwidth() - 20)
                    h = min(h, self.winfo_screenheight() - 60)
                except Exception:
                    pass
                newGeometry = f"{w}x{h}{m.group(3)}"
        return orig_geo(self, newGeometry)

    tk.Wm.wm_geometry = _geometry
    tk.Wm.geometry = _geometry

    for name, alias in (("wm_minsize", "minsize"), ("wm_maxsize", "maxsize")):
        orig = getattr(tk.Wm, name)

        def _mk(orig):
            def _size(self, width=None, height=None):
                if _active() and width is not None and height is not None:
                    width, height = S(width), S(height)
                return orig(self, width, height)
            return _size

        patched = _mk(orig)
        setattr(tk.Wm, name, patched)
        setattr(tk.Wm, alias, patched)


def install(root, percent=None):
    """Cài tỷ lệ cho TOÀN chương trình. Gọi ĐÚNG 1 lần, ngay sau khi tạo `root`, trước khi dựng widget."""
    global _scale, _installed
    if _installed:
        return
    _installed = True
    pct = clamp_percent(DEFAULT_PERCENT if percent is None else percent)
    _scale = pct / 100.0
    if _scale == 1.0:
        return                                  # 100% = không vá gì, giữ hệt hành vi cũ
    try:
        base = float(root.tk.call("tk", "scaling"))
        root.tk.call("tk", "scaling", base * _scale)
    except Exception:
        pass
    _patch_tk()


# ============================ lưu / khởi động lại ============================
def save_percent(settings_path, percent):
    """Ghi tỷ lệ vào dashboard_settings.json (giữ nguyên các khoá khác). Trả về % đã lưu."""
    pct = clamp_percent(percent)
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    data[SETTINGS_KEY] = pct
    try:
        import paths
        paths.save_json(settings_path, data)
    except Exception:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return pct


def relaunch_command(script_path):
    """Lệnh mở lại chương trình bằng đúng trình Python đang chạy."""
    return [sys.executable, script_path]


def spawn_new_instance(script_path, cwd):
    """Mở 1 tiến trình Dashboard mới (độc lập, không dính console cũ). Raise nếu không mở được."""
    flags = 0
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(relaunch_command(script_path), cwd=cwd, creationflags=flags,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

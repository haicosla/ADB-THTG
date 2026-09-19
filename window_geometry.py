"""
window_geometry.py — Tự lưu & khôi phục VỊ TRÍ + KÍCH THƯỚC của mọi cửa sổ
Tkinter trong Dashboard (cửa sổ chính + mọi popup), theo TỪNG MÁY.

Lưu vào data/window_geometry.json (cùng chỗ với dashboard_settings.json,
accounts.json...) - file này KHÔNG nên đồng bộ/copy giữa các máy, vì mỗi
máy có độ phân giải màn hình khác nhau, nên bố cục "vừa mắt" của máy này
chưa chắc hợp với máy kia. Cứ để mỗi máy tự ghi đè theo cách người dùng
kéo/co giãn cửa sổ của MÁY ĐÓ.

CÁCH DÙNG cho 1 cửa sổ (root hoặc Toplevel) MỚI:

    import window_geometry as wg

    win = tk.Toplevel(self.root)
    wg.restore_geometry(win, "ten_rieng_cua_cua_so", default="640x480")
    win.title("...")
    ... (dựng các widget con như cũ) ...
    wg.autosave(win, "ten_rieng_cua_cua_so")

- `restore_geometry` nên gọi NGAY sau khi tạo Toplevel, TRƯỚC khi dựng
  widget con (đỡ giật/nhấp nháy) - thay cho dòng `win.geometry("WxH")`
  cũ. `default` là kích thước cũ (dùng khi CHƯA có gì được lưu, vd lần
  đầu mở trên 1 máy mới).
- `autosave` gọi 1 lần sau đó (thứ tự không quan trọng) - tự bắt MỌI cách
  đóng cửa sổ (bấm nút "Đóng" gọi win.destroy(), hay bấm nút X góc trên)
  và lưu lại vị trí/kích thước LÚC ĐÓNG, không cần sửa gì thêm ở nút
  Đóng/handler đã có sẵn.

Mỗi cửa sổ cần 1 `name` (chuỗi) DUY NHẤT để phân biệt trong file JSON -
với các popup dùng CHUNG cho nhiều nội dung khác nhau (vd hộp thoại chọn
nhiều mục ở dashboard_dialogs.py), dùng `slug_name()` để tự tạo `name`
khác nhau theo tiêu đề (title) truyền vào, tránh các nội dung khác nhau
đè kích thước lên nhau.
"""
import json
import re

import paths

GEOMETRY_PATH = paths.resolve_data_path("window_geometry.json")


def slug_name(prefix, title):
    """Tạo 1 `name` ổn định từ `prefix` (vd 'dialog') + `title` hiển thị
    của popup (vd 'Chọn Hành Động Để Chạy') - dùng cho các popup DÙNG
    CHUNG 1 hàm dựng giao diện nhưng hiển thị nội dung khác nhau tuỳ nơi
    gọi, để mỗi loại nội dung nhớ kích thước riêng của nó."""
    slug = re.sub(r"[^a-z0-9]+", "_", title.strip().lower()).strip("_")
    return f"{prefix}_{slug}" if slug else prefix


def _load_all():
    try:
        with open(GEOMETRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_one(name, geometry_str):
    data = _load_all()
    data[name] = geometry_str
    try:
        paths.save_json(GEOMETRY_PATH, data, backup=False)
    except Exception:
        pass


def restore_geometry(win, name, default=None):
    """Áp lại vị trí+kích thước đã lưu cho `win` (nếu có) - dùng THAY cho
    `win.geometry("WxH")`. Chưa từng lưu -> dùng `default` (nếu có)."""
    geo = _load_all().get(name) or default
    if geo:
        try:
            win.geometry(geo)
        except Exception:
            pass


def autosave(win, name, manage_close=True):
    """Tự lưu vị trí+kích thước của `win` mỗi khi nó bị đóng, bất kể đóng
    bằng nút X hay bằng 1 nút "Đóng"/"Huỷ" tự gọi win.destroy().

    `manage_close=True` (mặc định - dùng cho các popup CHƯA tự đặt sẵn
    handler riêng cho nút X): Tkinter tự đặt SẴN 1 handler mặc định cho
    WM_DELETE_WINDOW trỏ thẳng tới bản destroy() GỐC ngay lúc tạo cửa sổ
    (trước khi hàm này chạy) - nên chỉ ghi đè `win.destroy` thôi CHƯA đủ
    để bắt được nút X (handler mặc định đó không tra `win.destroy` lại
    mỗi lần bấm mà đã "chốt" sẵn bản gốc từ đầu) - vì vậy cần đặt lại
    handler cho WM_DELETE_WINDOW trỏ sang bản destroy MỚI (đã ghi đè).

    `manage_close=False`: dùng cho cửa sổ đã tự có handler riêng cho nút
    X (vd cửa sổ chính dashboard.py có `_on_close` riêng lo việc khác rồi
    mới gọi `self.root.destroy()`) - khi đó KHÔNG đụng tới protocol đã
    đặt, chỉ ghi đè `win.destroy`: vì handler riêng đó rồi cũng tự gọi
    `win.destroy()` (tra cứu lại thuộc tính mỗi lần gọi) nên vẫn lưu được
    bình thường mà không phá mất việc riêng của handler đó."""

    def _capture_and_destroy(_orig_destroy=win.destroy):
        try:
            _save_one(name, win.geometry())
        except Exception:
            pass
        _orig_destroy()

    win.destroy = _capture_and_destroy

    if manage_close:
        win.protocol("WM_DELETE_WINDOW", win.destroy)

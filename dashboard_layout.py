"""
dashboard_layout.py — Khung giao diện chính KÉO ĐỔI KÍCH THƯỚC được + lưu/khôi phục kích thước các khung.

Cửa sổ chính gồm 4 khung xếp dọc trong 1 PanedWindow (`app._vpane`): PHẦN ĐẦU (các nhóm nút + bảng
'Hành động tiếp theo' + thanh giả lập) | DANH SÁCH TÁC VỤ | PHẦN CHẠY (nút CHẠY/DỪNG...) | NHẬT KÝ. Kéo thanh
ngăn giữa các khung để đổi chiều cao; trong PHẦN ĐẦU còn 1 thanh ngăn dọc (`app._hpane`) giữa khối nút và bảng
'Hành động tiếp theo' để đổi chiều rộng. Kích thước (đã quy về 100% - xem ui_scale.unscale) lưu theo TỪNG MÁY vào
data/window_geometry.json (khoá LAYOUT_KEY), mở lại app là giữ nguyên.
"""

import tkinter as tk

import window_geometry as wg
from dashboard_theme import *
from ui_scale import S, unscale

LAYOUT_KEY = "dashboard_layout"
SASH_W = 6

# Cao tối thiểu mỗi khung khi kéo (100%): đầu, danh sách, phần chạy, nhật ký.
_MIN_H = {"header": 120, "tasks": 90, "run": 60, "log": 70}
DEFAULT_LOG_H = 180


def make_paned(parent, orient):
    """PanedWindow có thanh ngăn dễ thấy/dễ nắm (màu viền, dày ~6px, đổi kích thước ngay khi kéo)."""
    return tk.PanedWindow(parent, orient=orient, bg=COL_BORDER, sashwidth=SASH_W, sashrelief="flat",
                          sashpad=0, bd=0, opaqueresize=True, showhandle=False)


def _saved(app):
    try:
        d = wg.get_value(LAYOUT_KEY, {}) or {}
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def apply_saved_layout(app):
    """Áp kích thước đã lưu (nếu có) cho các khung - gọi 1 lần sau khi dựng xong giao diện."""
    d = _saved(app)
    try:
        for key, pane in (("header_h", app._pane_header), ("run_h", app._pane_run), ("log_h", app._pane_log)):
            v = d.get(key)
            if isinstance(v, (int, float)) and v > 20:
                app._vpane.paneconfigure(pane, height=S(int(v)))
        v = d.get("split_left_w")
        if isinstance(v, (int, float)) and v > 100:
            app._hpane.paneconfigure(app._hp_left, width=S(int(v)))
    except Exception:
        pass


def save_layout(app, _event=None):
    """Lưu kích thước hiện tại của các khung (gọi khi nhả chuột sau khi kéo thanh ngăn)."""
    try:
        app.root.update_idletasks()
        data = {
            "header_h": unscale(app._pane_header.winfo_height()),
            "run_h": unscale(app._pane_run.winfo_height()),
            "log_h": unscale(app._pane_log.winfo_height()),
            "split_left_w": unscale(app._hp_left.winfo_width()),
        }
        wg.set_value(LAYOUT_KEY, data)
    except Exception:
        pass


def reset_layout(app):
    """Đưa các khung về kích thước mặc định (theo nội dung) và xoá phần đã lưu."""
    try:
        wg.set_value(LAYOUT_KEY, {})
        app.root.update_idletasks()
        for pane in (app._pane_header, app._pane_run):
            app._vpane.paneconfigure(pane, height=pane.winfo_reqheight())
        app._vpane.paneconfigure(app._pane_log, height=S(DEFAULT_LOG_H))
        app._hpane.paneconfigure(app._hp_left, width=app._hp_left.winfo_reqwidth())
    except Exception:
        pass


def build_vertical_panes(app, parent, panes):
    """Tạo PanedWindow dọc `app._vpane` trong `parent`. `panes` = [(attr_name, builder, stretch, min_key)];
    builder(vpane) trả về Frame (khung con TRỰC TIẾP của vpane)."""
    vp = make_paned(parent, "vertical")
    vp.pack(fill="both", expand=True)
    app._vpane = vp
    for attr, builder, stretch, min_key in panes:
        w = builder(vp)
        setattr(app, attr, w)
        vp.add(w, stretch=stretch, minsize=S(_MIN_H[min_key]))
    vp.bind("<ButtonRelease-1>", lambda e: save_layout(app), add="+")
    return vp

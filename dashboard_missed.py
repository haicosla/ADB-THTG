"""
dashboard_missed.py — Bảng "LỊCH HẸN GIỜ ĐÃ BỎ LỠ" hiện ra khi MỞ LẠI Dashboard
mà có lịch đã tới giờ chạy lúc chương trình đang tắt.

TRƯỚC ĐÂY Dashboard tự chạy bù NGAY, không hỏi gì. Giờ hiện bảng liệt kê
từng lịch bị lỡ (kèm các Hoạt Động của lịch đó theo đúng thứ tự chạy) để
người dùng tự TICK chọn lịch nào chạy bù; lịch không tick (hoặc bấm "Không
chạy") sẽ được đặt thành "vừa chạy xong" - xem
ScheduleMixin._handle_missed_schedules ở dashboard_schedule.py.

File này CHỈ lo phần GIAO DIỆN (không đụng tới lịch/không chạy gì): nhận
`rows` (list dict, xem MissedSchedulesDialog) và trả về ở thuộc tính
`result` danh sách CHỈ SỐ các dòng đã tick, theo đúng thứ tự trong bảng
(hoặc [] nếu người dùng chọn không chạy gì, hoặc None nếu cửa sổ bị huỷ khi
chương trình đang tắt).
"""
import tkinter as tk
from tkinter import ttk
from datetime import datetime

import window_geometry as wg
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, FlowBar


def _fmt_ago(delta):
    """'5 giờ 20 phút' / '35 phút' / '2 ngày 3 giờ' - độ trễ so với mốc lỡ."""
    total_min = max(0, int(delta.total_seconds() // 60))
    days, rem = divmod(total_min, 1440)
    hours, minutes = divmod(rem, 60)
    if days:
        return f"{days} ngày {hours} giờ" if hours else f"{days} ngày"
    if hours:
        return f"{hours} giờ {minutes} phút" if minutes else f"{hours} giờ"
    return f"{minutes} phút"


class MissedSchedulesDialog:
    """Hộp thoại chọn lịch nào chạy bù.

    `rows`: list dict, THEO ĐÚNG THỨ TỰ SẼ CHẠY (trên chạy trước), mỗi dict:
        {"ten": str,                # tên lịch
         "missed_at": datetime,     # mốc giờ hẹn bị lỡ (gần nhất)
         "missed_count": int,       # đã lỡ bao nhiêu mốc (>=1)
         "activities": [str, ...],  # tên các Hoạt Động, đúng thứ tự chạy
         "emulators": [str, ...]}   # giả lập gán cho lịch, vd ["#0", "#1"]

    Kết quả nằm ở `self.result` sau khi cửa sổ đóng (xem docstring đầu file).
    Mặc định TICK SẴN tất cả (giữ đúng hành vi cũ nếu chỉ bấm 'Chạy').
    """

    def __init__(self, parent, rows):
        self.rows = rows
        self.result = None
        self.vars = []

        win = self.win = tk.Toplevel(parent)
        win.title("Lịch Hẹn Giờ Đã Bỏ Lỡ")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "missed_schedules", default="980x560")
        win.minsize(700, 380)
        wg.autosave(win, "missed_schedules")
        # Đặt SAU wg.autosave (nó tự gán lại WM_DELETE_WINDOW): nút X và ESC
        # = "Không chạy" (xem _chon_khong_chay).
        win.protocol("WM_DELETE_WINDOW", self._chon_khong_chay)
        win.bind("<Escape>", lambda e: self._chon_khong_chay())

        tk.Label(win, text="⏰ Có lịch hẹn giờ đã BỎ LỠ lúc chương trình đang tắt",
                 bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(
            win,
            text="Tick lịch nào muốn CHẠY BÙ ngay bây giờ - các lịch tick sẽ chạy theo đúng thứ tự trong bảng "
                 "(từ trên xuống, mỗi lịch giữ nguyên thứ tự Hoạt Động của nó). Lịch KHÔNG tick sẽ KHÔNG chạy và "
                 "được đặt thành 'vừa chạy xong' (lần chạy kế tiếp là mốc giờ hẹn tiếp theo). Lịch lặp lại lỡ "
                 "nhiều mốc cũng chỉ chạy bù 1 lượt. Nút X / phím ESC = 'Không chạy'.",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=940, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        # ----- Thanh dưới cùng: PACK TRƯỚC vùng cuộn để luôn hiện đủ nút -----
        bottom = tk.Frame(win, bg=COL_PANEL)
        bottom.pack(side="bottom", fill="x", padx=14, pady=(4, 10))
        self.lbl_count = tk.Label(bottom, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9))
        self.lbl_count.pack(anchor="w", pady=(0, 6))
        bar = self.bar = FlowBar(bottom, bg=COL_PANEL)
        bar.pack(fill="x")
        bar.add(RoundedButton(bar, "☑ Tick tất cả", command=lambda: self._set_all(True), bg=COL_GRAY_BTN,
                              container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))
        bar.add(RoundedButton(bar, "☐ Bỏ tick tất cả", command=lambda: self._set_all(False), bg=COL_GRAY_BTN,
                              container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))
        bar.add(RoundedButton(bar, "⏭ Không chạy gì (coi như vừa chạy xong)", command=self._chon_khong_chay,
                              bg=COL_ORANGE, fg="#241a00", container_bg=COL_PANEL,
                              font=("Segoe UI", 9, "bold")))
        self.btn_run = RoundedButton(bar, "▶ Chạy", command=self._chon_chay, bg=COL_GREEN,
                                     container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"))
        bar.add(self.btn_run)

        # ----- Vùng cuộn chứa các dòng -----
        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 6), pady=4)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        # Lưới chung: hàng 0 = tiêu đề cột, hàng 1.. = từng lịch - dùng CHUNG các
        # cột nên tiêu đề luôn thẳng hàng với nội dung.
        self._act_labels = []
        heads = ["Chạy", "#  Tên lịch", "Mốc bị lỡ", "Hoạt Động (theo thứ tự chạy)", "Giả lập"]
        for c, text in enumerate(heads):
            tk.Label(inner, text=text, bg=COL_HEADER, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"),
                     anchor="w").grid(row=0, column=c, sticky="nsew", ipadx=6, ipady=6)
        inner.columnconfigure(0, minsize=56)
        inner.columnconfigure(1, minsize=190)
        inner.columnconfigure(2, minsize=190)
        inner.columnconfigure(3, weight=1)
        inner.columnconfigure(4, minsize=90)

        now = datetime.now()
        for i, row in enumerate(rows):
            self._add_row(inner, i + 1, i, row, now)

        def _on_canvas_resize(e):
            canvas.itemconfigure(win_id, width=e.width)
            wrap = max(220, e.width - 560)
            for lbl in self._act_labels:
                lbl.config(wraplength=wrap)
        canvas.bind("<Configure>", _on_canvas_resize)

        self._refresh()
        # Đưa lên trên cùng + lấy focus: app có thể đang thu nhỏ/nằm dưới cửa sổ khác lúc vừa mở.
        try:
            win.lift()
            win.attributes("-topmost", True)
            win.after(500, lambda: win.attributes("-topmost", False))
            win.focus_force()
        except tk.TclError:
            pass
        try:
            win.wait_visibility()
            win.grab_set()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    def _add_row(self, inner, grid_row, i, row, now):
        bg = COL_PANEL_ALT if i % 2 == 0 else COL_PANEL
        pad = dict(sticky="nsew", ipadx=6, ipady=8)

        var = tk.BooleanVar(value=True)
        self.vars.append(var)
        DarkCheck(inner, "", var, command=self._refresh, bg=bg).grid(row=grid_row, column=0, **pad)

        tk.Label(inner, text=f"{i + 1}.  {row.get('ten', '?')}", bg=bg, fg=COL_TEXT, font=("Segoe UI", 9, "bold"),
                 anchor="w", justify="left", wraplength=180).grid(row=grid_row, column=1, **pad)

        missed_at = row.get("missed_at")
        n = int(row.get("missed_count") or 1)
        if isinstance(missed_at, datetime):
            time_txt = f"{missed_at.strftime('%H:%M  %d/%m')}\n(cách đây {_fmt_ago(now - missed_at)})"
        else:
            time_txt = "?"
        if n > 1:
            time_txt += f"\nlỡ {n} lần - chỉ chạy bù 1 lượt"
        tk.Label(inner, text=time_txt, bg=bg, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), anchor="w",
                 justify="left").grid(row=grid_row, column=2, **pad)

        acts = row.get("activities") or []
        act_txt = "  →  ".join(f"{k + 1}) {name}" for k, name in enumerate(acts)) if acts else "(không có Hoạt Động nào)"
        lbl_act = tk.Label(inner, text=act_txt, bg=bg, fg=COL_TEXT, font=("Segoe UI", 8), anchor="w",
                           justify="left", wraplength=400)
        lbl_act.grid(row=grid_row, column=3, **pad)
        self._act_labels.append(lbl_act)

        emu_txt = ", ".join(row.get("emulators") or []) or "(chưa gán)"
        tk.Label(inner, text=emu_txt, bg=bg, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), anchor="w",
                 justify="left", wraplength=90).grid(row=grid_row, column=4, **pad)

    def _ticked_indexes(self):
        return [i for i, v in enumerate(self.vars) if v.get()]

    def _refresh(self):
        n_tick = len(self._ticked_indexes())
        n_all = len(self.vars)
        self.lbl_count.config(
            text=f"Đã tick {n_tick}/{n_all} lịch."
                 + (f" {n_all - n_tick} lịch không tick sẽ được đặt là 'vừa chạy xong'." if n_all - n_tick else ""))
        if n_tick:
            self.btn_run.set_text(f"▶ Chạy {n_tick} lịch đã tick")
            self.btn_run.set_state("normal")
        else:
            self.btn_run.set_text("▶ Chạy (chưa tick lịch nào)")
            self.btn_run.set_state("disabled")
        self.bar.after_idle(self.bar._reflow)   # chữ nút đổi -> bề ngang đổi

    def _set_all(self, value):
        for v in self.vars:
            v.set(value)
        self._refresh()

    def _chon_chay(self):
        picked = self._ticked_indexes()
        if not picked:
            return
        self.result = picked
        self.win.destroy()

    def _chon_khong_chay(self):
        self.result = []
        self.win.destroy()

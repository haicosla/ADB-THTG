"""
dashboard_popup_ctl.py - RunControlPopupMixin: popup NHỎ "🪟 Điều Khiển Nhanh".

Nút CHỈ CÓ ICON; các dòng trạng thái nhỏ như cũ vẫn còn. Thanh nút phía trên = [📌 ghim luôn trên cùng] [⬆ đưa TẤT CẢ
giả lập lên trên (giống '⬆ Đưa Lên Trên' ở thanh Giả lập nhưng cho mọi giả lập, không cần tick)]
[🔀 mở '🔀 Chọn Hành Động Để Chạy']; mỗi giả lập đang chạy 1 dòng: [tên ngắn] [⏸/▶] [⏹], phía trên mỗi dòng có 2 dòng chữ nhỏ: 'Hoạt Động, TK i/n' và '⏰ Tiếp: <lịch hẹn giờ>';
chân popup: '⏰ Lịch kế tiếp: ...'. Rê chuột vào tên giả lập cũng hiện tooltip chi tiết.
Popup có KÍCH THƯỚC CỐ ĐỊNH (bề ngang cố định `_CTL_W`, KHÔNG kéo giãn được; chiều cao tự co đúng theo số dòng
giả lập đang chạy), nhỏ gọn và mở ở CUỐI màn hình (góc phải dưới, nằm trên thanh taskbar). Khi số dòng đổi,
cạnh DƯỚI của popup được giữ nguyên (popup mọc lên trên). Dời chỗ bằng thanh tiêu đề HOẶC thanh nắm '⠿ kéo để di chuyển'
trong popup (không lưu vị trí); bề ngang không bao giờ hẹp hơn `_CTL_MIN_W` để thanh tiêu đề luôn còn chỗ nắm.

Dùng LẠI đúng cơ chế cờ có sẵn ở dashboard_run.py (không tạo cơ chế mới):
  - Giả lập đang chạy tay/Hẹn Giờ/Nhóm/Xoay Vòng/Log Nhanh -> self.stop_flags[idx] /
    self.pause_flags[idx] (giống chọn "Áp dụng cho" 1 giả lập rồi bấm Dừng/Tạm Dừng).
  - Giả lập đang chạy 1 lượt 🎁 Hành Động Sự Kiện (self._event_cycle_indexes, xem
    dashboard_event.py) -> cờ RIÊNG của Sự Kiện (self._event_stop_flags /
    self._event_pause_flags); dòng này có thêm biểu tượng 🎁 trước tên.
Danh sách dòng tự cập nhật theo self._busy_emulator_indexes (giả lập nào bận thì hiện).
"""
import tkinter as tk

from ui_scale import S, raw as _ui_raw   # Tỷ Lệ Giao Diện (xem ui_scale.py)

from dashboard_theme import (COL_PANEL, COL_TEXT, COL_TEXT_MUTED, COL_RED,
                             COL_ORANGE, COL_GREEN, COL_TEAL, COL_PURPLE, COL_BLUE, COL_PANEL_ALT)
from dashboard_widgets import ThemedToplevel, RoundedButton, DarkCheck, Tooltip


class RunControlPopupMixin:
    _CTL_POPUP_NAME = "run_control_popup"
    _CTL_TICK_MS = 400
    _CTL_W = 250              # bề ngang CỐ ĐỊNH (px, nhân theo Tỷ Lệ Giao Diện); chiều cao tự co theo nội dung
    _CTL_MIN_W = 230          # bề ngang TỐI THIỂU (px thật): Tỷ Lệ Giao Diện nhỏ làm popup hẹp tới mức thanh tiêu đề
                              # chỉ còn 3 nút (thu nhỏ/phóng to/đóng) - không còn chỗ nắm để kéo
    _CTL_MARGIN = 10          # cách mép phải / mép dưới vùng làm việc (px)
    _CTL_TITLEBAR = 32        # chừa chỗ thanh tiêu đề khi đặt popup sát cuối màn hình

    def _ctl_width(self):
        """Bề ngang popup (px thật) = `_CTL_W` theo Tỷ Lệ Giao Diện nhưng không bao giờ hẹp hơn `_CTL_MIN_W`."""
        return max(S(self._CTL_W), self._CTL_MIN_W)

    # ---------- mở / dựng popup ----------
    def open_run_control_popup(self):
        win = getattr(self, "_ctl_popup", None)
        try:
            if win is not None and win.winfo_exists():
                win.deiconify()
                win.lift()
                return
        except Exception:
            pass

        win = ThemedToplevel(self.root)
        self._ctl_popup = win
        win.title("Điều khiển")
        win.resizable(False, False)       # kích thước CỐ ĐỊNH (chiều cao tự co theo số dòng)
        self._ctl_last_h = None           # chiều cao đã áp lần trước (để chỉ đổi khi nội dung đổi)
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass

        # Thanh NẮM KÉO ngay trong popup: kéo chuột trái vào đây để dời popup (dùng được cả khi thanh tiêu đề
        # của Windows quá hẹp / bị che, không còn chỗ nắm).
        grip = tk.Label(win, text="⠿  kéo để di chuyển  ⠿", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                        font=("Segoe UI", 7), cursor="fleur")
        grip.pack(fill="x", padx=4, pady=(4, 0))
        self._ctl_bind_drag(grip, win)
        Tooltip(grip, lambda: "Giữ chuột trái và kéo để dời popup sang chỗ khác")

        # Thanh nút phía trên: 📌 ghim | ⬆ đưa tất cả giả lập lên trên | 🔀 chọn hành động để chạy
        top = tk.Frame(win, bg=COL_PANEL)
        top.pack(fill="x", padx=4, pady=(2, 2))
        self._ctl_topmost_var = tk.BooleanVar(value=True)
        pin = DarkCheck(top, "📌", self._ctl_topmost_var, bg=COL_PANEL, font=("Segoe UI", 9),
                        box_size=14, command=lambda: self._ctl_apply_topmost(win))
        pin.pack(side="left", padx=(2, 4))
        Tooltip(pin, lambda: "📌 Luôn trên cùng (tick = popup luôn nổi trên các cửa sổ khác)")
        b_all = RoundedButton(top, "⬆", command=self._ctl_bring_all, bg=COL_PURPLE, container_bg=COL_PANEL,
                              font=("Segoe UI", 9, "bold"), padx=6, pady=1, radius=6)
        b_all.pack(side="left", fill="x", expand=True, padx=1)
        Tooltip(b_all, lambda: "⬆ Đưa TẤT CẢ giả lập lên trên (không cần tick chọn)")
        b_pick = RoundedButton(top, "🔀", command=self._ctl_pick_action, bg=COL_BLUE, container_bg=COL_PANEL,
                               font=("Segoe UI", 9, "bold"), padx=6, pady=1, radius=6)
        b_pick.pack(side="left", fill="x", expand=True, padx=1)
        Tooltip(b_pick, lambda: "🔀 Chọn Hành Động Để Chạy")

        self._ctl_rows = {}       # {idx: {"frame", "pause", "event", "paused", "status", "next"...}}
        self._ctl_rows_keys = None   # tập dòng lần vẽ trước (để biết khi nào cần xếp lại + nới chiều cao)
        self._ctl_empty_lbl = None

        # Chân popup LUÔN hiện: lịch Hẹn Giờ sớm nhất sắp chạy trên toàn bộ giả lập (_next_schedule_text(None)).
        foot = tk.Frame(win, bg=COL_PANEL)
        foot.pack(side="bottom", fill="x", padx=8, pady=(0, 6))
        tk.Frame(foot, bg=COL_TEXT_MUTED, height=1).pack(fill="x", pady=(0, 4))
        self._ctl_footer_next = tk.Label(foot, text=self._ctl_footer_text(), bg=COL_PANEL, fg=COL_TEAL,
                                         font=("Segoe UI", 8), anchor="w", justify="left", wraplength=self._CTL_W - 20)
        self._ctl_footer_next.pack(fill="x")
        self._ctl_footer_text_cache = self._ctl_footer_next.cget("text")

        self._ctl_body = tk.Frame(win, bg=COL_PANEL)
        self._ctl_body.pack(fill="x", padx=4, pady=(0, 2))

        self._ctl_refresh_rows()          # dựng sẵn các dòng để đo đúng chiều cao rồi mới đặt vị trí
        self._ctl_place_bottom(win)
        self._ctl_tick()

    def _ctl_bind_drag(self, widget, win):
        """Cho phép kéo cả cửa sổ `win` bằng cách kéo `widget` (giữ chuột trái)."""
        st = {}

        def _press(e):
            st["dx"] = e.x_root - win.winfo_x()
            st["dy"] = e.y_root - win.winfo_y()

        def _move(e):
            if "dx" not in st:
                return
            try:
                with _ui_raw():
                    win.geometry(f"+{e.x_root - st['dx']}+{e.y_root - st['dy']}")
            except Exception:
                pass

        widget.bind("<ButtonPress-1>", _press)
        widget.bind("<B1-Motion>", _move)

    def _ctl_apply_topmost(self, win):
        try:
            win.attributes("-topmost", bool(self._ctl_topmost_var.get()))
        except Exception:
            pass

    def _ctl_bring_all(self):
        """Nút ⬆: đưa cửa sổ của TẤT CẢ giả lập lên trên (xem bring_all_emulators_to_front), rồi nâng
        lại chính popup để không bị cửa sổ giả lập vừa nâng che mất."""
        try:
            self.bring_all_emulators_to_front()
        except Exception as ex:
            try:
                self._log("warn", f"Popup: không đưa được giả lập lên trên: {ex}")
            except Exception:
                pass
        win = getattr(self, "_ctl_popup", None)
        try:
            if win is not None and win.winfo_exists():
                win.after(80, win.lift)
        except Exception:
            pass

    def _ctl_pick_action(self):
        """Nút 🔀: mở '🔀 Chọn Hành Động Để Chạy' (giống nút cùng tên ở thanh dưới cửa sổ chính)."""
        try:
            self._open_task_picker()
        except Exception as ex:
            try:
                self._log("warn", f"Popup: không mở được 'Chọn Hành Động Để Chạy': {ex}")
            except Exception:
                pass

    def _ctl_work_area(self):
        """(trái, trên, phải, dưới) của vùng làm việc màn hình chính (không tính taskbar Windows)."""
        try:
            import ctypes
            from ctypes import wintypes
            rc = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rc), 0):   # SPI_GETWORKAREA
                return rc.left, rc.top, rc.right, rc.bottom
        except Exception:
            pass
        try:
            return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight() - 48
        except Exception:
            return 0, 0, 1280, 720

    def _ctl_place_bottom(self, win):
        """Lần mở đầu: đặt popup ở GÓC PHẢI DƯỚI vùng làm việc, bề ngang cố định, chiều cao theo nội dung."""
        left, top, right, bottom = self._ctl_work_area()
        try:
            win.update_idletasks()
            h = win.winfo_reqheight()
        except Exception:
            h = 120
        w = self._ctl_width()
        x = max(left, right - w - S(self._CTL_MARGIN))
        y = max(top, bottom - h - S(self._CTL_MARGIN) - S(self._CTL_TITLEBAR))
        try:
            with _ui_raw():           # w/h đã là pixel thật
                win.geometry(f"{w}x{h}+{x}+{y}")
            self._ctl_last_h = h
        except Exception:
            pass

    # ---------- trạng thái ----------
    def _ctl_is_event(self, idx):
        return idx in getattr(self, "_event_cycle_indexes", ())

    def _ctl_is_paused(self, idx):
        if self._ctl_is_event(idx):
            return bool(self._event_pause_flags.get(idx, False))
        return bool(self._is_pause_requested(idx))

    def _ctl_stop(self, idx):
        name = self._emulator_name_by_index(idx)
        if self._ctl_is_event(idx):
            self._event_stop_flags[idx] = True
            self._event_pause_flags[idx] = False
            self._log("warn", f"🎁 Popup: DỪNG Sự Kiện trên '{name}'.", emulator_name=name)
        else:
            self.stop_flags[idx] = True
            self.pause_flags[idx] = False
            self._log("warn", f"Popup: DỪNG RIÊNG giả lập '{name}' - các giả lập khác vẫn chạy bình thường.",
                       emulator_name=name)
        self._ctl_sync_main_pause_button()
        self._ctl_refresh_rows()

    def _ctl_toggle_pause(self, idx):
        name = self._emulator_name_by_index(idx)
        if self._ctl_is_event(idx):
            paused = not self._event_pause_flags.get(idx, False)
            self._event_pause_flags[idx] = paused
        else:
            paused = not self._is_pause_requested(idx)
            if self.pause_flag and not paused:
                # Đang bấm "Tạm Dừng" cho TẤT CẢ ở thanh chính: tiếp tục RIÊNG giả lập này
                # = gỡ cờ tổng và giữ nguyên trạng thái tạm dừng của các giả lập còn lại.
                self.pause_flag = False
                for j in list(self._busy_emulator_indexes):
                    if j != idx and not self._ctl_is_event(j):
                        self.pause_flags[j] = True
            self.pause_flags[idx] = paused
        if paused:
            self._log("warn", f"Popup: TẠM DỪNG giả lập '{name}'.", emulator_name=name)
        else:
            self._log("info", f"Popup: TIẾP TỤC giả lập '{name}'.", emulator_name=name)
        self._ctl_sync_main_pause_button()
        self._ctl_refresh_rows()

    def _ctl_sync_main_pause_button(self):
        """Giữ nút Tạm Dừng ở thanh chính khớp với trạng thái sau khi bấm ở popup."""
        try:
            target = self._get_stop_target_index()
            paused = self.pause_flag if target is None else self.pause_flags.get(target, False)
            self.btn_pause.set_text("▶ Tiếp Tục" if paused else "⏸ Tạm Dừng")
        except Exception:
            pass

    # ---------- vẽ lại ----------
    def _ctl_tick(self):
        win = getattr(self, "_ctl_popup", None)
        try:
            if win is None or not win.winfo_exists():
                return
        except Exception:
            return
        try:
            self._ctl_refresh_rows()
        except Exception:
            pass
        try:
            win.after(self._CTL_TICK_MS, self._ctl_tick)
        except Exception:
            pass

    def _ctl_refresh_rows(self):
        body = getattr(self, "_ctl_body", None)
        if body is None:
            return
        wanted = {idx: self._ctl_is_event(idx) for idx in sorted(set(self._busy_emulator_indexes))}

        # bỏ dòng không còn chạy / đổi loại (Sự Kiện <-> thường)
        for idx in list(self._ctl_rows.keys()):
            row = self._ctl_rows[idx]
            if idx not in wanted or row["event"] != wanted[idx]:
                try:
                    row["frame"].destroy()
                except Exception:
                    pass
                del self._ctl_rows[idx]

        # thêm dòng mới
        for idx, is_event in wanted.items():
            if idx not in self._ctl_rows:
                self._ctl_rows[idx] = self._ctl_build_row(body, idx, is_event)

        # cập nhật dòng trạng thái nhỏ (Hoạt Động, TK i/n) + dòng "⏰ Tiếp: ..." (lịch hẹn giờ kế tiếp)
        for idx, row in self._ctl_rows.items():
            txt = self._ctl_status_text(idx)
            if row["status_text"] != txt:
                row["status_text"] = txt
                row["status"].config(text=txt)
            ntxt = self._ctl_next_text(idx)
            if row["next_text"] != ntxt:
                row["next_text"] = ntxt
                row["next"].config(text=ntxt)

        # cập nhật nhãn nút Tạm dừng/Tiếp tục
        for idx, row in self._ctl_rows.items():
            paused = self._ctl_is_paused(idx)
            if row["paused"] != paused:
                row["paused"] = paused
                row["pause"].bg_color = COL_GREEN if paused else COL_ORANGE
                row["pause"].set_text("▶" if paused else "⏸")

        # chân popup: lịch hẹn giờ sớm nhất của TẤT CẢ giả lập
        ftxt = self._ctl_footer_text()
        lbl = getattr(self, "_ctl_footer_next", None)
        if lbl is not None and getattr(self, "_ctl_footer_text_cache", None) != ftxt:
            self._ctl_footer_text_cache = ftxt
            lbl.config(text=ftxt)

        # dòng "trống"
        if not wanted:
            if self._ctl_empty_lbl is None:
                self._ctl_empty_lbl = tk.Label(body, text="Không có giả lập nào đang chạy",
                                               bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9))
                self._ctl_empty_lbl.pack(padx=8, pady=4)
        elif self._ctl_empty_lbl is not None:
            self._ctl_empty_lbl.destroy()
            self._ctl_empty_lbl = None

        # tập dòng đổi -> sắp xếp lại thứ tự theo index + nới chiều cao cho đủ chỗ
        keys = tuple(sorted(self._ctl_rows))
        n = len(keys)
        if keys != getattr(self, "_ctl_rows_keys", None):
            self._ctl_rows_keys = keys
            for idx in keys:
                try:
                    self._ctl_rows[idx]["frame"].pack_forget()
                    self._ctl_rows[idx]["frame"].pack(fill="x", pady=1)
                except Exception:
                    pass

        # nội dung có thể đổi chiều cao (thêm/bớt dòng, chân popup xuống dòng) -> co lại cho vừa, giữ nguyên cạnh dưới
        self._ctl_fit_height(n)

    def _ctl_fit_height(self, n=None):
        """Co/giãn CHIỀU CAO popup đúng bằng nội dung (bề ngang cố định `_CTL_W`). Giữ nguyên CẠNH DƯỚI
        (popup mọc lên trên khi thêm dòng, nên luôn nằm sát cuối màn hình); không đụng tới x. `n` giữ lại cho
        tương thích chỗ gọi cũ, không dùng."""
        win = getattr(self, "_ctl_popup", None)
        try:
            if win is None or not win.winfo_exists():
                return
            win.update_idletasks()
            h = win.winfo_reqheight()
            if h == getattr(self, "_ctl_last_h", None):
                return
            left, top, right, bottom = self._ctl_work_area()
            cur_h = win.winfo_height()
            if cur_h <= 1 or getattr(self, "_ctl_last_h", None) is None:
                y = bottom - h - S(self._CTL_MARGIN) - S(self._CTL_TITLEBAR)
            else:
                y = win.winfo_y() + cur_h - h        # cạnh dưới đứng yên
            y = max(top, y)
            with _ui_raw():
                win.geometry(f"{self._ctl_width()}x{h}+{win.winfo_x()}+{y}")
            self._ctl_last_h = h
        except Exception:
            pass

    def _ctl_set_phase(self, emulator_index, text):
        """Đặt dòng trạng thái popup cho 1 GIAI ĐOẠN không phải Hoạt Động (đang bật giả lập, chờ game lên,
        bước hệ thống Bật/Tắt/Đăng xuất/Đăng nhập...). Giữ lại 'TK i/n' + bối cảnh của bước trước. Không bao giờ
        ném lỗi (chạy từ luồng nền)."""
        try:
            if not hasattr(self, "_ctl_status"):
                self._ctl_status = {}
            prev = self._ctl_status.get(emulator_index) or {}
            self._ctl_status[emulator_index] = {"task": text, "acc": prev.get("acc"), "ctx": prev.get("ctx", "")}
        except Exception:
            pass

    def _ctl_tip_text(self, idx, name):
        """Tooltip của tên giả lập: tên đầy đủ + đang chạy gì (kèm bối cảnh đầy đủ: lịch/xoay vòng, tài khoản
        thứ mấy) + lịch hẹn giờ kế tiếp."""
        try:
            st = getattr(self, "_ctl_status", {}).get(idx) or {}
            ctx = f"\n{st['ctx']}" if st.get("ctx") else ""
            return f"{name}\n{self._ctl_status_text(idx)}{ctx}\n{self._ctl_next_text(idx)}"
        except Exception:
            return name

    _CTL_STATUS_MAX_CHARS = 38

    def _ctl_status_text(self, idx):
        """Dòng nhỏ phía trên mỗi giả lập, vd 'Thư Kí, TK 2/14' (không có xoay vòng thì chỉ tên Hoạt Động)."""
        st = getattr(self, "_ctl_status", {}).get(idx)
        if not st:
            return "Đang chuẩn bị..."
        txt = str(st.get("task") or "")
        if st.get("acc"):
            txt += f", TK {st['acc'][0]}/{st['acc'][1]}"
        mx = self._CTL_STATUS_MAX_CHARS
        return txt if len(txt) <= mx else txt[:mx - 1] + "…"

    def _ctl_footer_text(self):
        """Dòng chân popup '⏰ Lịch kế tiếp: <tên> lúc hh:mm (còn ...)' (lịch BẬT sớm nhất, mọi giả lập)."""
        try:
            t = self._next_schedule_text(None)
        except Exception:
            t = ""
        return f"⏰ Lịch kế tiếp: {t}" if t else "⏰ Lịch kế tiếp: chưa có lịch hẹn giờ nào đang BẬT"

    _CTL_NEXT_MAX_CHARS = 46

    def _ctl_next_text(self, idx):
        """Dòng nhỏ 'Tiếp: <lịch hẹn giờ> lúc hh:mm (còn ...)' của 1 giả lập."""
        try:
            t = self._next_schedule_text(idx)
        except Exception:
            t = ""
        txt = f"⏰ Tiếp: {t}" if t else "⏰ Tiếp: chưa có lịch hẹn giờ"
        mx = self._CTL_NEXT_MAX_CHARS
        return txt if len(txt) <= mx else txt[:mx - 1] + "…"

    _CTL_NAME_MAX_CHARS = 11

    def _ctl_build_row(self, body, idx, is_event):
        """1 dòng = 2 dòng chữ nhỏ (trạng thái, lịch kế tiếp) + [tên ngắn] [⏸/▶] [⏹] (nút chỉ icon, chia đều bề ngang)."""
        outer = tk.Frame(body, bg=COL_PANEL)
        outer.pack(fill="x", pady=1)
        status_text = self._ctl_status_text(idx)
        status_lbl = tk.Label(outer, text=status_text, bg=COL_PANEL, fg=COL_TEXT_MUTED,
                              font=("Segoe UI", 8), anchor="w")
        status_lbl.pack(fill="x", padx=2)
        next_text = self._ctl_next_text(idx)
        next_lbl = tk.Label(outer, text=next_text, bg=COL_PANEL, fg=COL_TEAL,
                            font=("Segoe UI", 8), anchor="w")
        next_lbl.pack(fill="x", padx=2)
        row_f = tk.Frame(outer, bg=COL_PANEL)
        row_f.pack(fill="x")
        name = self._emulator_name_by_index(idx)
        short = name if len(name) <= self._CTL_NAME_MAX_CHARS else name[:self._CTL_NAME_MAX_CHARS - 1] + "…"
        lbl = tk.Label(row_f, text=(f"🎁 {short}" if is_event else short), bg=COL_PANEL, fg=COL_TEXT,
                       font=("Segoe UI", 8, "bold"), anchor="w")
        lbl.pack(side="left", padx=(2, 4))
        Tooltip(lbl, lambda i=idx, n=name: self._ctl_tip_text(i, n))
        paused = self._ctl_is_paused(idx)
        btn_pause = RoundedButton(
            row_f, "▶" if paused else "⏸",
            command=lambda i=idx: self._ctl_toggle_pause(i),
            bg=COL_GREEN if paused else COL_ORANGE, container_bg=COL_PANEL,
            font=("Segoe UI", 10, "bold"), padx=6, pady=2, radius=6)
        btn_pause.pack(side="left", fill="x", expand=True, padx=1)
        Tooltip(btn_pause, lambda i=idx: "▶ Tiếp tục" if self._ctl_is_paused(i) else "⏸ Tạm dừng")
        btn_stop = RoundedButton(
            row_f, "⏹", command=lambda i=idx: self._ctl_stop(i),
            bg=COL_RED, container_bg=COL_PANEL,
            font=("Segoe UI", 10, "bold"), padx=6, pady=2, radius=6)
        btn_stop.pack(side="left", fill="x", expand=True, padx=1)
        Tooltip(btn_stop, lambda: "⏹ Dừng")
        return {"frame": outer, "pause": btn_pause, "event": is_event, "paused": paused,
                "status": status_lbl, "status_text": status_text, "next": next_lbl, "next_text": next_text}

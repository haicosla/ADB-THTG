"""
dashboard_popup_ctl.py - RunControlPopupMixin: popup NHỎ "🪟 Điều Khiển Nhanh".

Mỗi giả lập đang chạy 1 dòng: [Tên giả lập] [⏸ Tạm dừng / ▶ Tiếp tục] [⏹ Dừng].
Chỉ có tên giả lập + 2 nút, không thêm gì khác. Phía trên cùng có 1 ô tích nhỏ
"📌 Luôn trên cùng" (mặc định BẬT) để popup luôn nổi trên các cửa sổ khác.

Dùng LẠI đúng cơ chế cờ có sẵn ở dashboard_run.py (không tạo cơ chế mới):
  - Giả lập đang chạy tay/Hẹn Giờ/Nhóm/Xoay Vòng/Log Nhanh -> self.stop_flags[idx] /
    self.pause_flags[idx] (giống chọn "Áp dụng cho" 1 giả lập rồi bấm Dừng/Tạm Dừng).
  - Giả lập đang chạy 1 lượt 🎁 Hành Động Sự Kiện (self._event_cycle_indexes, xem
    dashboard_event.py) -> cờ RIÊNG của Sự Kiện (self._event_stop_flags /
    self._event_pause_flags); dòng này có thêm biểu tượng 🎁 trước tên.
Danh sách dòng tự cập nhật theo self._busy_emulator_indexes (giả lập nào bận thì hiện).
"""
import tkinter as tk

from dashboard_theme import (COL_PANEL, COL_TEXT, COL_TEXT_MUTED, COL_RED,
                             COL_ORANGE, COL_GREEN)
from dashboard_widgets import ThemedToplevel, RoundedButton, DarkCheck
import window_geometry as wg


class RunControlPopupMixin:
    _CTL_POPUP_NAME = "run_control_popup"
    _CTL_TICK_MS = 400

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
        win.resizable(False, False)
        self._ctl_restore_position(win)
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass

        top = tk.Frame(win, bg=COL_PANEL)
        top.pack(fill="x", padx=8, pady=(6, 2))
        self._ctl_topmost_var = tk.BooleanVar(value=True)
        DarkCheck(top, "📌 Luôn trên cùng", self._ctl_topmost_var, bg=COL_PANEL,
                  font=("Segoe UI", 8), box_size=14,
                  command=lambda: self._ctl_apply_topmost(win)).pack(side="left")

        self._ctl_body = tk.Frame(win, bg=COL_PANEL)
        self._ctl_body.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self._ctl_rows = {}       # {idx: {"frame", "pause", "key"}}
        self._ctl_empty_lbl = None

        wg.autosave(win, self._CTL_POPUP_NAME)
        self._ctl_tick()

    def _ctl_apply_topmost(self, win):
        try:
            win.attributes("-topmost", bool(self._ctl_topmost_var.get()))
        except Exception:
            pass

    def _ctl_restore_position(self, win):
        """Chỉ khôi phục VỊ TRÍ (không ép kích thước vì số dòng thay đổi theo số giả lập đang chạy)."""
        pos = None
        try:
            geo = wg._load_all().get(self._CTL_POPUP_NAME)
            if wg._sane(geo):
                m = wg._GEO_RE.match(geo)
                pos = f"{m.group(3)}{m.group(4)}"
        except Exception:
            pos = None
        if not pos:
            try:
                x = self.root.winfo_rootx() + max(40, self.root.winfo_width() - 330)
                y = self.root.winfo_rooty() + 60
                pos = f"+{x}+{y}"
            except Exception:
                pos = "+100+100"
        try:
            win.geometry(pos)
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

        # cập nhật dòng trạng thái nhỏ (Hoạt Động, TK i/n)
        for idx, row in self._ctl_rows.items():
            txt = self._ctl_status_text(idx)
            if row["status_text"] != txt:
                row["status_text"] = txt
                row["status"].config(text=txt)

        # cập nhật nhãn nút Tạm dừng/Tiếp tục
        for idx, row in self._ctl_rows.items():
            paused = self._ctl_is_paused(idx)
            if row["paused"] != paused:
                row["paused"] = paused
                row["pause"].bg_color = COL_GREEN if paused else COL_ORANGE
                row["pause"].set_text("▶ Tiếp tục" if paused else "⏸ Tạm dừng")

        # dòng "trống"
        if not wanted:
            if self._ctl_empty_lbl is None:
                self._ctl_empty_lbl = tk.Label(body, text="Không có giả lập nào đang chạy",
                                               bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9))
                self._ctl_empty_lbl.pack(padx=8, pady=6)
        elif self._ctl_empty_lbl is not None:
            self._ctl_empty_lbl.destroy()
            self._ctl_empty_lbl = None

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

    def _ctl_build_row(self, body, idx, is_event):
        outer = tk.Frame(body, bg=COL_PANEL)
        outer.pack(fill="x", pady=2)
        status_text = self._ctl_status_text(idx)
        status_lbl = tk.Label(outer, text=status_text, bg=COL_PANEL, fg=COL_TEXT_MUTED,
                              font=("Segoe UI", 8), anchor="w")
        status_lbl.pack(fill="x", padx=2)
        frame = tk.Frame(outer, bg=COL_PANEL)
        frame.pack(fill="x")
        name = self._emulator_name_by_index(idx)
        tk.Label(frame, text=(f"🎁 {name}" if is_event else name), bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 9, "bold"), anchor="w", width=14).pack(side="left", padx=(0, 6))
        paused = self._ctl_is_paused(idx)
        btn_pause = RoundedButton(
            frame, "▶ Tiếp tục" if paused else "⏸ Tạm dừng",
            command=lambda i=idx: self._ctl_toggle_pause(i),
            bg=COL_GREEN if paused else COL_ORANGE, container_bg=COL_PANEL,
            font=("Segoe UI", 9, "bold"), padx=8, pady=3, radius=8, width=92)
        btn_pause.pack(side="left", padx=2)
        RoundedButton(
            frame, "⏹ Dừng", command=lambda i=idx: self._ctl_stop(i),
            bg=COL_RED, container_bg=COL_PANEL,
            font=("Segoe UI", 9, "bold"), padx=8, pady=3, radius=8, width=70
        ).pack(side="left", padx=2)
        return {"frame": outer, "pause": btn_pause, "event": is_event, "paused": paused,
                "status": status_lbl, "status_text": status_text}

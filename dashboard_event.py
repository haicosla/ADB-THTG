"""
dashboard_event.py — EventActionMixin: "🎁 Hành Động Sự Kiện" - dành cho các
sự kiện trong game chỉ diễn ra trong vài ngày (thỉnh thoảng hiện quà để
nhận): soạn 1 CHUỖI BƯỚC riêng cho từng giả lập (y hệt cách soạn "🏁 Hành
Động Cuối" - tái dùng chung self._open_steps_editor()/self._run_post_run_steps(),
KHÔNG viết lại phần thực thi), rồi bấm "▶ Bắt Đầu Sự Kiện" để chuỗi bước đó
tự LẶP LẠI SUỐT NGÀY trên các giả lập đã tick, cho tới khi bấm Dừng.

ƯU TIÊN (yêu cầu gốc của người dùng - "tích chọn thì chạy suốt cả ngày,
nhưng có hành động khác (chạy tay/hẹn giờ) thì dừng lại ưu tiên hành động
khác trước, xong lại chạy tiếp"):
  - Mỗi khi CHẠY tay / Hẹn Giờ / Nhóm Hành Động cần dùng ĐÚNG giả lập đang
    chạy Sự Kiện, Sự Kiện tự NHƯỜNG NGAY - không đợi hết cả chuỗi bước, chỉ
    đợi tới điểm dừng an toàn kế tiếp (giữa 2 bước, hoặc giữa 1 vòng lặp chờ
    ảnh - đúng độ trễ như nút "⏸ Tạm Dừng" thường, xem
    self._is_stop_requested(idx, event=True)/self._make_stop_checker(idx,
    event=True) đã sửa ở dashboard_run.py để tự kiểm tra
    self._emulator_job_queue).
  - Ngay sau khi nhường xong (self._busy_emulator_indexes.discard +
    self._after_emulator_freed), job đang xếp hàng chờ (CHẠY tay/Hẹn Giờ/
    Nhóm) được chạy NGAY, y hệt cơ chế XẾP HÀNG CHỜ sẵn có.
  - Sự Kiện tự đứng chờ giả lập rảnh trở lại rồi tự chạy tiếp (chạy LẠI TỪ
    ĐẦU chuỗi bước - chuỗi Sự Kiện thường ngắn/lặp lại được, không cố resume
    dở dang).

NGHỈ GIỮA CÁC LƯỢT: có ô 'Nghỉ (phút)' CHUNG ở thanh chính (event_interval_var) và
ô 'Nghỉ (p)' RIÊNG từng giả lập trong '🎁 Soạn Hành Động Sự Kiện Theo Giả Lập'
(self._event_interval_by_emulator) - giả lập nào ĐÃ đặt nghỉ riêng thì dùng số
riêng đó (ƯU TIÊN), để trống thì dùng nghỉ chung (xem _get_event_interval_seconds).

ĐỘC LẬP VỚI CHẠY TAY/HẸN GIỜ: Sự Kiện dùng RIÊNG self._event_stop_flags /
self._event_pause_flags (theo từng emulator_index) - KHÔNG dùng chung
self.stop_flag(s)/pause_flag(s) - nên bấm DỪNG/TẠM DỪNG ở thanh CHẠY chính
KHÔNG ảnh hưởng Sự Kiện và ngược lại; có nút Dừng/Tạm Dừng RIÊNG cho Sự Kiện
(xem stop_event_action/toggle_pause_event_action bên dưới).

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như các Mixin khác.
"""

import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from adb_helper import ADBHelper
from logic_engine import LogicEngine
from window_finder import WindowFinder
import task_registry
import account_manager
import activity_groups
import window_geometry as wg
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, _bind_esc_close, ThemedToplevel


class EventActionMixin:
    # ================= TÓM TẮT / TIỆN ÍCH =================
    def _event_rest_summary_text(self):
        """Tóm tắt nghỉ RIÊNG đang đặt, vd 'Nghỉ riêng: LD1 2p, LD3 0.5p ·
        còn lại dùng nghỉ chung 5p' - để xem lại sau khi áp."""
        mp = getattr(self, "_event_interval_by_emulator", None) or {}
        parts = []
        for k in sorted(mp, key=lambda x: (not str(x).isdigit(), int(x) if str(x).isdigit() else 0, str(x))):
            v = self._get_event_rest_override_minutes(k)
            if v is None:
                continue
            try:
                name = self._emulator_name_by_index(int(k))
            except Exception:
                name = f"#{k}"
            parts.append(f"{name} {v:g}p")
        try:
            common = int(self._get_event_interval_seconds() // 60)
        except Exception:
            common = 5
        if not parts:
            return f"Chưa đặt nghỉ riêng - tất cả giả lập dùng nghỉ chung {common}p"
        return "Nghỉ riêng: " + ", ".join(parts) + f"  ·  còn lại dùng nghỉ chung {common}p"

    def _event_action_summary_text(self):
        mapping = getattr(self, "_event_action_steps_by_emulator", None) or {}
        n_cfg = sum(1 for v in mapping.values() if v)
        n_active = len(getattr(self, "_event_active_indexes", None) or ())
        base = f"Đã soạn {n_cfg} giả lập" if n_cfg else "(chưa soạn giả lập nào)"
        n_rest = sum(1 for k in (getattr(self, "_event_interval_by_emulator", None) or {})
                     if self._get_event_rest_override_minutes(k) is not None)
        if n_rest:
            base += f" - nghỉ riêng {n_rest} giả lập"
        if n_active:
            base += f" - ĐANG CHẠY NỀN {n_active} giả lập"
        return base

    def _refresh_event_action_summary(self):
        if hasattr(self, "lbl_event_action"):
            self.lbl_event_action.config(text=self._event_action_summary_text())

    EVENT_REST_MIN_MINUTES = 0.5
    EVENT_REST_MAX_MINUTES = 240.0

    @staticmethod
    def _parse_event_rest_text(text):
        """Đọc ô 'Nghỉ (phút)' RIÊNG của 1 giả lập: rỗng -> None (= dùng ô
        Nghỉ CHUNG); số (cho phép thập phân, dấu phẩy hoặc chấm) -> float
        phút, kẹp trong [0.5, 240]. Không đọc được -> ValueError."""
        t = str(text or "").strip().replace(",", ".")
        if not t:
            return None
        v = float(t)  # ValueError nếu gõ sai
        if v != v or v <= 0:
            raise ValueError("phải > 0")
        return max(EventActionMixin.EVENT_REST_MIN_MINUTES,
                   min(v, EventActionMixin.EVENT_REST_MAX_MINUTES))

    def _get_event_rest_override_minutes(self, emulator_index):
        """Số phút nghỉ RIÊNG đã đặt cho giả lập này (self._event_interval_by_emulator),
        None nếu chưa đặt/không hợp lệ."""
        mp = getattr(self, "_event_interval_by_emulator", None) or {}
        try:
            return self._parse_event_rest_text(mp.get(str(emulator_index)))
        except (ValueError, TypeError):
            return None

    def _event_rest_text(self, emulator_index):
        v = self._get_event_rest_override_minutes(emulator_index)
        return "" if v is None else f"{v:g}"

    def _get_event_interval_seconds(self, emulator_index=None):
        """Khoảng nghỉ giữa 2 lượt chạy chuỗi bước Sự Kiện - tránh chạy dồn
        dập liên tục cả ngày.
        ƯU TIÊN: nếu truyền emulator_index và giả lập đó ĐÃ đặt ô 'Nghỉ (phút)'
        RIÊNG (trong '🎁 Soạn Hành Động Sự Kiện Theo Giả Lập') -> dùng số
        riêng đó. Không đặt riêng (hoặc không truyền index) -> dùng ô 'Nghỉ
        (phút)' CHUNG cạnh nút Bắt Đầu Sự Kiện, mặc định 5 phút."""
        if emulator_index is not None:
            own = self._get_event_rest_override_minutes(emulator_index)
            if own is not None:
                return own * 60
        try:
            v = int(float(self.event_interval_var.get()))
        except Exception:
            v = 5
        return max(1, min(v, 240)) * 60

    # ================= SOẠN CHUỖI BƯỚC (giống 🏁 Hành Động Cuối) =================
    def _pick_event_actions(self):
        if not getattr(self, "emulators", None):
            messagebox.showinfo("Chưa có giả lập",
                                 "Chưa quét được giả lập nào - bấm '🔄 Quét Giả Lập' rồi thử lại.")
            return

        mapping = getattr(self, "_event_action_steps_by_emulator", None)
        if mapping is None:
            mapping = {}
            self._event_action_steps_by_emulator = mapping

        accounts = account_manager.load_accounts()
        activity_items = [
            (t.get("id") or task_registry.make_task_id(t.get("file_json", "")), t.get("ten_hien_thi", "?"))
            for t in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0)))
        ]
        activity_group_of = {
            (t.get("id") or task_registry.make_task_id(t.get("file_json", ""))): (t.get("muc") or "")
            for t in self.tasks
        }
        # "Nhóm Hành Động" cũng chọn được như 1 Hoạt Động (giống 🏁 Hành Động Cuối/⏰ Hẹn Giờ).
        for g in activity_groups.load_groups():
            gid = f"{activity_groups.GROUP_PREFIX}{g.get('id')}"
            activity_items.append((gid, f"📦 {g.get('ten', '?')}"))
            activity_group_of[gid] = "📦 Nhóm Hành Động"

        win = ThemedToplevel(self.root)
        win.title("Chọn Hành Động Sự Kiện Theo Giả Lập")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "pick_event_actions", default="600x560")
        wg.autosave(win, "pick_event_actions")
        _bind_esc_close(win)

        tk.Label(win, text="Mỗi giả lập soạn 1 CHUỖI BƯỚC (Hoạt Động thường xen kẽ Hành động hệ thống: Bật/Tắt "
                            "giả lập, Đăng Xuất, Đăng Nhập) - khi bấm '▶ Bắt Đầu Sự Kiện', chuỗi này tự LẶP LẠI "
                            "SUỐT NGÀY trên giả lập đó, tự NHƯỜNG NGAY mỗi khi CHẠY tay/Hẹn Giờ/Nhóm Hành Động "
                            "cần dùng giả lập này, rồi tự chạy tiếp ngay khi giả lập rảnh trở lại:",
                 bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 9, "bold"),
                 wraplength=560, justify="left").pack(anchor="w", padx=12, pady=(12, 6))

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=6)
        vbar.pack(side="right", fill="y", padx=(0, 6))

        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>") if e.widget is win else None, add="+")

        def _refresh_summary():
            self._refresh_event_action_summary()

        def _btn_label(idx):
            n = len(mapping.get(str(idx)) or [])
            return f"🎁 Sự Kiện ({n} bước)" if n else "🎁 Sự Kiện (chưa soạn)"

        # ---- Chọn nhanh nhiều giả lập cùng lúc, để soạn CHUNG 1 lần rồi áp
        # dụng đồng loạt (đỡ phải bấm '🎁 Sự Kiện' + soạn lại từng giả lập
        # một) - pick_vars chỉ tồn tại trong lúc mở dialog này, không lưu lại. ----
        pick_vars = {e.index: tk.BooleanVar(value=False) for e in self.emulators}
        row_btns = {}

        def _set_all_picks(val):
            for v in pick_vars.values():
                v.set(val)

        def _apply_common_to_picked(chosen_ids):
            picked = [idx for idx, v in pick_vars.items() if v.get()]
            for idx in picked:
                mapping[str(idx)] = list(chosen_ids)
                if idx in row_btns:
                    row_btns[idx].set_text(_btn_label(idx))
            self._save_settings()
            _refresh_summary()
            if picked:
                names = ", ".join(self._emulator_name_by_index(idx) for idx in picked)
                self._log("info", f"🎁 Đã áp dụng CHUNG 1 chuỗi bước Sự Kiện cho [{names}].")

        def _compose_for_picked():
            picked = [idx for idx, v in pick_vars.items() if v.get()]
            if not picked:
                messagebox.showwarning("Lưu ý", "Chưa tick giả lập nào ở cột ☑ bên trái mỗi dòng - tick giả lập "
                                                 "cần soạn CHUNG rồi bấm lại nút này.")
                return
            # Lấy chuỗi bước đang có sẵn của giả lập ĐẦU TIÊN được tick làm gợi ý
            # khởi điểm (nếu có) để đỡ soạn lại từ đầu khi các giả lập đã có sẵn
            # cấu hình gần giống nhau.
            current = mapping.get(str(picked[0])) or []
            self._open_steps_editor("Soạn CHUNG Hành Động Sự Kiện (áp dụng cho các giả lập đã tick)",
                                     current, accounts, activity_items, activity_group_of,
                                     _apply_common_to_picked)

        pick_bar = tk.Frame(win, bg=COL_PANEL)
        pick_bar.pack(fill="x", padx=12, pady=(0, 6))
        RoundedButton(pick_bar, "☑ Chọn Tất Cả", command=lambda: _set_all_picks(True), bg=COL_PANEL_ALT,
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(side="left")
        RoundedButton(pick_bar, "☐ Bỏ Chọn", command=lambda: _set_all_picks(False), bg=COL_PANEL_ALT,
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(side="left", padx=6)
        RoundedButton(pick_bar, "🎁 Soạn Chung Cho Đã Tick", command=_compose_for_picked, bg=COL_ORANGE,
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(side="left")

        # ---- Ô 'Nghỉ (phút)' RIÊNG từng giả lập (ƯU TIÊN hơn ô Nghỉ chung ở
        # thanh chính). Để TRỐNG = dùng ô Nghỉ chung. Lưu vào
        # self._event_interval_by_emulator {"<index>": phút}. ----
        rest_vars = {e.index: tk.StringVar(value=self._event_rest_text(e.index)) for e in self.emulators}
        rest_entries = {}
        rest_map = getattr(self, "_event_interval_by_emulator", None)
        if rest_map is None:
            rest_map = {}
            self._event_interval_by_emulator = rest_map

        def _commit_rest(idx, save=False):
            ent = rest_entries.get(idx)
            try:
                val = self._parse_event_rest_text(rest_vars[idx].get())
            except (ValueError, TypeError):
                if ent is not None:
                    ent.config(fg=COL_RED)
                return False
            if ent is not None:
                ent.config(fg=COL_TEXT)
            if val is None:
                rest_map.pop(str(idx), None)
            else:
                rest_map[str(idx)] = val
            if save:
                self._save_settings()
            try:
                _refresh_rest_summary()
            except NameError:
                pass  # chưa dựng xong nhãn tóm tắt (lúc khởi tạo)
            return True

        def _apply_rest_to_picked():
            picked = [idx for idx, v in pick_vars.items() if v.get()]
            if not picked:
                messagebox.showwarning("Lưu ý", "Chưa tick giả lập nào ở cột ☑ bên trái mỗi dòng.")
                return
            text = bulk_rest_var.get()
            try:
                self._parse_event_rest_text(text)
            except (ValueError, TypeError):
                messagebox.showerror("Lỗi", "Số phút nghỉ không hợp lệ (vd 2, 10, 0.5) - để trống để xoá nghỉ riêng.")
                return
            for idx in picked:
                rest_vars[idx].set(text.strip())
                _commit_rest(idx)
            self._save_settings()
            shown = f"{text.strip()} phút" if text.strip() else "dùng Nghỉ chung"
            names = ", ".join(self._emulator_name_by_index(idx) for idx in picked)
            self._log("info", f"🎁 Đã đặt nghỉ RIÊNG [{shown}] cho [{names}].")
            messagebox.showinfo("Đã áp nghỉ riêng", f"Đã đặt [{shown}] cho: {names}\n\n" + self._event_rest_summary_text())

        bulk_rest_var = tk.StringVar(value="")
        rest_bar = tk.Frame(win, bg=COL_PANEL)
        rest_bar.pack(fill="x", padx=12, pady=(0, 6), before=canvas)
        tk.Label(rest_bar, text="⏱ Nghỉ riêng (phút):", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Entry(rest_bar, textvariable=bulk_rest_var, width=6, bg=COL_ENTRY, fg=COL_TEXT,
                 insertbackground=COL_TEXT, relief="flat").pack(side="left", padx=6)
        RoundedButton(rest_bar, "Áp Cho Đã Tick", command=_apply_rest_to_picked, bg=COL_TEAL,
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=3).pack(side="left")
        tk.Label(rest_bar, text="(trống = dùng Nghỉ chung)", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8)).pack(side="left", padx=6)

        lbl_rest_summary = tk.Label(win, text=self._event_rest_summary_text(), bg=COL_PANEL, fg=COL_ORANGE,
                                    font=("Segoe UI", 8, "bold"), wraplength=560, justify="left", anchor="w")
        lbl_rest_summary.pack(fill="x", padx=12, pady=(0, 6), before=canvas)

        def _refresh_rest_summary():
            lbl_rest_summary.config(text=self._event_rest_summary_text())
            self._refresh_event_action_summary()

        def _commit_all_rest(_e=None):
            for _idx in list(rest_vars):
                _commit_rest(_idx)
            self._save_settings()
        win.bind("<Destroy>", lambda e: _commit_all_rest() if e.widget is win else None, add="+")

        for e in self.emulators:
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=3, padx=4)
            DarkCheck(row, "", pick_vars[e.index], bg=COL_PANEL_ALT, box_size=16).pack(side="left", padx=(6, 0))
            tk.Label(row, text=e.name, bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 9, "bold"),
                     width=16, anchor="w").pack(side="left", padx=8, pady=6)

            btn = RoundedButton(row, _btn_label(e.index), bg=COL_ORANGE, container_bg=COL_PANEL_ALT,
                                 font=("Segoe UI", 8, "bold"), padx=8, pady=3)
            btn.pack(side="right", padx=8, pady=4)
            row_btns[e.index] = btn

            # Ô nghỉ RIÊNG của giả lập này (trống = dùng Nghỉ chung).
            ent = tk.Entry(row, textvariable=rest_vars[e.index], width=5, bg=COL_ENTRY, fg=COL_TEXT,
                           insertbackground=COL_TEXT, relief="flat", justify="center")
            ent.pack(side="right", padx=(0, 2), pady=4)
            tk.Label(row, text="Nghỉ (p):", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED,
                     font=("Segoe UI", 8)).pack(side="right")
            rest_entries[e.index] = ent
            rest_vars[e.index].trace_add("write", lambda *_a, _i=e.index: _commit_rest(_i))
            ent.bind("<FocusOut>", lambda _ev, _i=e.index: _commit_rest(_i, save=True))
            ent.bind("<Return>", lambda _ev, _i=e.index: _commit_rest(_i, save=True))

            def _open_editor(idx=e.index, btn=btn):
                self._open_event_steps_editor(idx, accounts, activity_items, activity_group_of,
                                               on_saved=lambda: (btn.set_text(_btn_label(idx)), _refresh_summary()))
            btn.command = _open_editor

        RoundedButton(win, "Đóng", command=win.destroy, bg=COL_GREEN, container_bg=COL_PANEL,
                      font=("Segoe UI", 9, "bold"), padx=16, pady=6).pack(side="bottom", pady=10)

    def _open_event_steps_editor(self, emulator_index, accounts, activity_items, activity_group_of, on_saved=None):
        """Soạn Hành Động Sự Kiện của 1 GIẢ LẬP (self._event_action_steps_by_emulator) -
        wrapper mỏng quanh self._open_steps_editor() (TÁI DÙNG NGUYÊN XI popup
        '🎯 Chọn Hoạt Động' + '⚙ Thao tác hệ thống' đã có ở dashboard_run.py,
        y hệt cách '🏁 Hành Động Cuối' đang dùng)."""
        mapping = getattr(self, "_event_action_steps_by_emulator", None)
        if mapping is None:
            mapping = {}
            self._event_action_steps_by_emulator = mapping
        current = mapping.get(str(emulator_index)) or []

        def _on_save(chosen_ids):
            mapping[str(emulator_index)] = list(chosen_ids)
            self._save_settings()
            if on_saved:
                on_saved()

        self._open_steps_editor("Chọn Hành Động Sự Kiện (Hoạt Động + Hành động hệ thống)", current, accounts,
                                 activity_items, activity_group_of, _on_save)

    # ================= BẮT ĐẦU / TẠM DỪNG / DỪNG =================
    def start_event_action(self):
        """Bắt đầu chạy nền Sự Kiện trên các giả lập ĐANG ĐƯỢC TICK ở thanh
        Giả Lập (self._get_selected_emulators(), giống mọi nút CHẠY khác) -
        mỗi giả lập ĐÃ SOẠN chuỗi bước (self._event_action_steps_by_emulator)
        và CHƯA đang chạy sẵn sẽ được mở 1 luồng nền riêng
        (_worker_event_action), tự lặp lại tới khi bấm Dừng."""
        selected_emulators = self._get_selected_emulators()
        if not selected_emulators:
            messagebox.showwarning("Lưu ý", "Chưa chọn giả lập nào (tick ở thanh Giả Lập) để Bắt Đầu Sự Kiện!")
            return
        mapping = getattr(self, "_event_action_steps_by_emulator", None) or {}
        started, skipped = [], []
        for e in selected_emulators:
            ids = mapping.get(str(e.index)) or []
            if not ids:
                skipped.append(e.name)
                continue
            if e.index in self._event_active_indexes:
                continue  # đã đang chạy sẵn rồi - không mở thêm luồng thứ 2 trên cùng 1 giả lập
            self._event_stop_flags[e.index] = False
            self._event_pause_flags[e.index] = False
            self._event_active_indexes.add(e.index)
            started.append(e.name)
            threading.Thread(target=self._worker_event_action, args=(e,), daemon=True).start()
        if started:
            self._log("info", f"🎁 Bắt đầu Hành Động Sự Kiện (chạy nền suốt ngày, tự nhường ưu tiên cho CHẠY "
                               f"tay/Hẹn Giờ/Nhóm Hành Động) trên [{', '.join(started)}].")
        if skipped:
            self._log("warn", f"🎁 Bỏ qua [{', '.join(skipped)}] - chưa soạn Hành Động Sự Kiện cho giả lập này "
                               f"(bấm '🎁 Soạn Hành Động Sự Kiện Theo Giả Lập').")
        self._refresh_event_action_summary()

    def _event_targets_from_ui(self):
        """Danh sách emulator_index để áp dụng Tạm Dừng/Dừng Sự Kiện - ưu
        tiên đúng các giả lập ĐANG ĐƯỢC TICK ở thanh Giả Lập (nếu trong số
        đó có giả lập đang chạy Sự Kiện); không tick trúng giả lập nào đang
        chạy Sự Kiện thì áp dụng cho TẤT CẢ giả lập đang chạy Sự Kiện (giống
        '🌐 Tất cả giả lập' ở nút Dừng/Tạm Dừng CHẠY tay)."""
        active = set(self._event_active_indexes)
        if not active:
            return []
        ticked = {e.index for e in self._get_selected_emulators()} & active
        return sorted(ticked) if ticked else sorted(active)

    def stop_event_action(self):
        targets = self._event_targets_from_ui()
        if not targets:
            messagebox.showinfo("Sự Kiện", "Hiện không có giả lập nào đang chạy Hành Động Sự Kiện.")
            return
        for idx in targets:
            self._event_stop_flags[idx] = True
            self._event_pause_flags[idx] = False
        names = ", ".join(self._emulator_name_by_index(idx) for idx in targets)
        self._log("warn", f"🎁 Người dùng bấm DỪNG Sự Kiện trên [{names}] - sẽ dừng lại ở điểm an toàn kế tiếp "
                           f"(không huỷ dở bước đang chạy dở nếu có).")

    def toggle_pause_event_action(self):
        targets = self._event_targets_from_ui()
        if not targets:
            messagebox.showinfo("Sự Kiện", "Hiện không có giả lập nào đang chạy Hành Động Sự Kiện.")
            return
        # Đảo NGƯỢC theo trạng thái của giả lập ĐẦU TIÊN trong danh sách rồi áp
        # dụng ĐỒNG LOẠT 1 chiều (tất cả cùng Tạm Dừng hoặc cùng Tiếp Tục) -
        # tránh rối khi mỗi giả lập đang ở 1 trạng thái khác nhau lúc bấm hàng loạt.
        new_state = not self._event_pause_flags.get(targets[0], False)
        for idx in targets:
            self._event_pause_flags[idx] = new_state
        names = ", ".join(self._emulator_name_by_index(idx) for idx in targets)
        if new_state:
            self._log("warn", f"🎁 Đã TẠM DỪNG Sự Kiện trên [{names}] - bấm lại để Tiếp Tục.")
        else:
            self._log("info", f"🎁 Đã TIẾP TỤC Sự Kiện trên [{names}].")
        if hasattr(self, "btn_event_pause"):
            self.btn_event_pause.set_text("▶ Tiếp Tục Sự Kiện" if new_state else "⏸ Tạm Dừng Sự Kiện")

    # ================= LUỒNG NỀN (1 luồng / 1 giả lập) =================
    def _worker_event_action(self, emulator):
        idx = emulator.index
        logged_waiting = False
        try:
            while idx in self._event_active_indexes and not self._event_stop_flags.get(idx, False):
                # Tạm dừng RIÊNG của Sự Kiện - đứng chờ tại đây, vẫn kiểm tra
                # Dừng để nút Dừng luôn có tác dụng ngay cả khi đang tạm dừng.
                while self._event_pause_flags.get(idx, False) and not self._event_stop_flags.get(idx, False):
                    time.sleep(0.3)
                if self._event_stop_flags.get(idx, False):
                    break

                mapping = getattr(self, "_event_action_steps_by_emulator", None) or {}
                ids = mapping.get(str(idx)) or []
                if not ids:
                    # Chuỗi bước vừa bị xoá/chưa soạn - đứng chờ, tự kiểm tra lại
                    # định kỳ thay vì thoát hẳn luồng (người dùng có thể soạn lại
                    # ngay trong lúc Sự Kiện đang "Bắt Đầu").
                    time.sleep(15)
                    continue

                # Nhường giả lập nếu đang bận (CHẠY tay/Hẹn Giờ/Nhóm/1 lượt Sự
                # Kiện khác) - KHÔNG tự xếp hàng chờ qua self._queue_job (Sự
                # Kiện không phải job "phải chạy đúng 1 lần" như CHẠY tay/Hẹn
                # Giờ - bỏ lỡ 1 lượt cũng không sao, tự thử lại ngay vòng sau).
                if idx in self._busy_emulator_indexes:
                    if not logged_waiting:
                        self._log("info", f"🎁 Giả lập '{emulator.name}' đang bận (CHẠY tay/Hẹn Giờ/Nhóm Hành "
                                           f"Động khác) - Sự Kiện đứng chờ, sẽ tự chạy tiếp ngay khi rảnh.",
                                   emulator_name=emulator.name)
                        logged_waiting = True
                    time.sleep(2)
                    continue
                logged_waiting = False

                fresh = self.emu_manager.find_by_index(idx) or emulator
                if not self.emu_manager.is_ready(fresh):
                    self._log("info", f"🎁 Giả lập '{fresh.name}' đang tắt - Sự Kiện tự bật...",
                               emulator_name=fresh.name)
                    ready, _auto_started = self.emu_manager.ensure_running(
                        idx, timeout=120,
                        on_log=lambda lvl, msg, _e=fresh: self._log(lvl, f"🎁 {msg}", emulator_name=_e.name))
                    if not ready:
                        self._log("error", f"🎁 Không tự bật được giả lập '{fresh.name}' - Sự Kiện thử lại sau "
                                            f"60s.", emulator_name=fresh.name)
                        time.sleep(60)
                        continue
                    fresh = ready
                emulator = fresh

                self._busy_emulator_indexes.add(idx)
                self._event_cycle_indexes.add(idx)
                try:
                    self._run_one_event_cycle(emulator, ids)
                finally:
                    self._event_cycle_indexes.discard(idx)
                    self._busy_emulator_indexes.discard(idx)
                    # Nhả giả lập NGAY - nếu có job CHẠY tay/Hẹn Giờ/Nhóm nào
                    # đang xếp hàng chờ đúng giả lập này, job đó được chạy
                    # NGAY LẬP TỨC ở đây, không cần đợi vòng kiểm tra kế tiếp.
                    self._after_emulator_freed(idx)

                if self._event_stop_flags.get(idx, False):
                    break

                # Nghỉ giữa các lượt (ô 'Nghỉ giữa lượt (phút)') - chờ theo
                # TỪNG GIÂY để Dừng/Tạm Dừng vẫn phản hồi ngay trong lúc nghỉ,
                # không phải đợi hết cả khoảng nghỉ mới nhận ra.
                rest_s = self._get_event_interval_seconds(idx)
                if self._get_event_rest_override_minutes(idx) is not None:
                    self._log("info", f"🎁 '{emulator.name}' nghỉ {rest_s / 60:g} phút (nghỉ RIÊNG của giả lập này) "
                                       f"rồi chạy lượt tiếp.", emulator_name=emulator.name)
                rest_end = time.time() + rest_s
                while time.time() < rest_end:
                    if self._event_stop_flags.get(idx, False):
                        break
                    time.sleep(1)
        except Exception as e:
            self._log("error", f"🎁 Lỗi Hành Động Sự Kiện trên '{emulator.name}': {e}", emulator_name=emulator.name)
        finally:
            self._event_active_indexes.discard(idx)
            self._event_stop_flags.pop(idx, None)
            self._event_pause_flags.pop(idx, None)
            self.root.after(0, self._refresh_event_action_summary)
            self._log("info", f"🎁 Hành Động Sự Kiện trên '{emulator.name}' đã DỪNG HẲN.",
                       emulator_name=emulator.name)

    def _run_one_event_cycle(self, emulator, ids):
        """Chạy ĐÚNG 1 LƯỢT chuỗi bước Sự Kiện trên `emulator` - tự dựng
        ADB/WindowFinder/LogicEngine riêng cho lượt này (giống
        _run_login_check_standalone ở dashboard_run.py), rồi giao thẳng cho
        self._run_post_run_steps(..., event=True) (LÕI dùng chung với 🏁
        Hành Động Cuối) để thực thi - KHÔNG viết lại phần chạy bước."""
        if not self.emu_manager.ensure_adb_connected(emulator):
            self._log("error", f"🎁 Không thấy giả lập '{emulator.name}' trong 'adb devices' - bỏ qua lượt Sự "
                                f"Kiện này, thử lại ở lượt kế tiếp.", emulator_name=emulator.name)
            return

        adb = ADBHelper()
        adb.device_id = emulator.adb_serial
        adb.update_resolution()

        wf = WindowFinder(adb)
        attached = wf.attach_hwnd(emulator.hwnd) if emulator.hwnd else False
        if not attached:
            wf.find_ld_windows()
        if wf.ensure_window_visible():
            time.sleep(0.5)

        engine = LogicEngine(
            adb,
            stop_checker=self._make_stop_checker(emulator.index, event=True),
            popup_notifier=lambda msg, dur=0, bg=None, fg=None, alpha=None, pos_box=None, _wf=wf:
                self._show_ingame_popup(_wf, msg, dur, bg, fg, alpha, pos_box),
            logger=lambda lvl, msg, _e=emulator: self._log(lvl, msg, emulator_name=_e.name)
        )
        self._run_post_run_steps(engine, emulator, ids, tag="🎁 Sự Kiện", event=True)

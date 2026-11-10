"""
dashboard_progress.py — Theo dõi tiến độ chạy của từng Hoạt Động (đang chờ/đang chạy/xong/lỗi/đã dừng) và khung 'Lỗi / Chưa Xong' liệt kê các Hoạt Động bị lỗi trong phiên chạy gần nhất.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import time
import tkinter as tk
from tkinter import ttk

import notifier
import task_registry
from dashboard_theme import *
from dashboard_widgets import _bind_esc_close, ThemedToplevel
import window_geometry as wg


class ProgressMixin:
    def _bump_task_progress(self, task_id, kind):
        self.root.after(0, lambda: self._apply_task_progress(task_id, kind))

    # ---- Dòng trạng thái hoạt động NGẮN (giống tin Telegram nhưng 1 dòng) ----
    # self.task_activity = {task_id: {tên giả lập: {state, t_start, t_end, note}}}
    # - ghi từ _exec_entry (dashboard_run.py) cùng lúc với _bump_task_progress, hiển thị ở
    # khung '⚠ Xem Lỗi / Chưa Xong' (show_error_panel) dưới tên từng tác vụ.
    def _note_task_activity(self, task_id, emulator_name, state, t_start=None, note=""):
        """state: running | done | error | stopped. Không bao giờ ném lỗi."""
        try:
            acts = self.task_activity.setdefault(task_id, {})
            old = acts.get(emulator_name) or {}
            acts[emulator_name] = {
                "state": state,
                "t_start": t_start if t_start is not None else old.get("t_start"),
                "t_end": None if state == "running" else time.time(),
                "note": str(note or ""),
            }
        except Exception:
            pass

    def _task_activity_line(self, task_id):
        """1 dòng ngắn tổng hợp trạng thái tác vụ trên từng giả lập, vd:
        '⚠ Clone01 12:15 lỗi: không thấy ảnh  │  ✅ Clone02 12:10→12:12 (2p13s)'.
        Rỗng nếu chưa có ghi nhận nào."""
        acts = dict(self.task_activity.get(task_id) or {})
        if not acts:
            return ""
        order = {"error": 0, "stopped": 1, "running": 2, "done": 3}
        parts = []
        for emu, a in sorted(acts.items(), key=lambda kv: (order.get(kv[1].get("state"), 9), kv[0])):
            st = a.get("state")
            t0, t1 = a.get("t_start"), a.get("t_end")
            hm0 = time.strftime("%H:%M", time.localtime(t0)) if t0 else ""
            hm1 = time.strftime("%H:%M", time.localtime(t1)) if t1 else ""
            dur = notifier.fmt_duration(t1 - t0) if (t0 and t1) else ""
            note = a.get("note", "")
            note = (note[:38] + "…") if len(note) > 38 else note
            if st == "done":
                parts.append(f"✅ {emu} {hm0}→{hm1} ({dur})" if dur else f"✅ {emu} {hm1}")
            elif st == "error":
                parts.append(f"⚠ {emu} {hm1}" + (f" lỗi: {note}" if note else " lỗi"))
            elif st == "stopped":
                parts.append(f"⏹ {emu} {hm1} đã dừng")
            elif st == "running":
                parts.append(f"▶ {emu} từ {hm0} đang chạy")
        return "  │  ".join(parts)

    def _apply_task_progress(self, task_id, kind):
        prog = self.task_progress.get(task_id)
        if prog is None:
            return
        if kind == "running":
            prog["running"] += 1
        elif kind == "done":
            prog["done"] += 1
            prog["running"] = max(0, prog["running"] - 1)
        elif kind == "error":
            prog["error"] += 1
            prog["running"] = max(0, prog["running"] - 1)
        elif kind == "stopped":
            prog["stopped"] += 1
            prog["running"] = max(0, prog["running"] - 1)

        lbl = self.task_status_lbl.get(task_id)
        if lbl:
            total = prog["total"]
            if prog["error"] > 0:
                lbl.config(text=f"⚠ Lỗi {prog['error']}/{total}", fg=COL_RED)
            elif total > 0 and prog["done"] == total:
                lbl.config(text=f"✅ Hoàn thành ({total}/{total})", fg=COL_GREEN)
            elif prog["running"] > 0:
                lbl.config(text=f"▶ Đang chạy ({prog['done']}/{total})", fg=COL_TEAL)
            elif prog["stopped"] > 0:
                lbl.config(text=f"⏹ Đã dừng ({prog['done']}/{total})", fg=COL_ORANGE)
            else:
                lbl.config(text="⏳ Đang chờ", fg=COL_TEXT_MUTED)

        self._refresh_error_badge()

    def _task_progress_status(self, p):
        """Suy ra (nhãn, màu) trạng thái TỔNG QUÁT của 1 tác vụ từ
        self.task_progress[task_id] (total/done/error/running/stopped) -
        dùng chung cho cả badge (_refresh_error_badge) lẫn bảng chi tiết
        (show_error_panel), để 2 nơi này LUÔN khớp nhau, không lệch logic.

        Có LỖI ở bất kỳ giả lập nào -> ưu tiên hiển thị LỖI trước tiên (kể
        cả khi các giả lập khác đã xong) vì đây là trạng thái người dùng
        cần biết sớm nhất."""
        total = p.get("total", 0)
        done = p.get("done", 0)
        error = p.get("error", 0)
        running = p.get("running", 0)
        stopped = p.get("stopped", 0)

        if error > 0:
            return f"⚠ Lỗi {error}/{total}", COL_RED
        if running > 0:
            return f"▶ Đang chạy ({done}/{total})", COL_TEAL
        if stopped > 0:
            return f"⏹ Đã dừng thủ công ({done}/{total})", COL_ORANGE
        if total > 0 and done >= total:
            return f"✅ Đã chạy xong ({done}/{total})", COL_GREEN
        return f"⏳ Chưa xong ({done}/{total})", COL_TEXT_MUTED

    def _task_progress_has_problem(self, p):
        """True nếu tác vụ này CẦN người dùng chú ý: có Lỗi, có Dừng thủ
        công, hoặc đang KHÔNG chạy mà vẫn CHƯA hoàn thành hết số giả lập
        (total) - tức "Chưa Xong" đúng nghĩa. Tác vụ đang chạy dở
        (running > 0) KHÔNG tính là có vấn đề (chỉ là chưa tới lượt xong),
        và tác vụ đã xong hết (done == total, không lỗi/không dừng) cũng
        không tính là có vấn đề."""
        total = p.get("total", 0)
        error = p.get("error", 0)
        stopped = p.get("stopped", 0)
        running = p.get("running", 0)
        done = p.get("done", 0)
        if error > 0 or stopped > 0:
            return True
        if running == 0 and total > 0 and done < total:
            return True
        return False

    def _refresh_error_badge(self):
        # Đếm CẢ Lỗi lẫn Chưa Xong/Đã Dừng Thủ Công (xem
        # _task_progress_has_problem) - trước đây chỉ đếm Lỗi nên số hiện ở
        # nút này không khớp với tên nút "Xem Lỗi / Chưa Xong".
        n = sum(1 for p in self.task_progress.values() if self._task_progress_has_problem(p))
        self.btn_view_errors.set_text(f"⚠ Xem Lỗi / Chưa Xong ({n})")

    def show_error_panel(self):
        win = ThemedToplevel(self.root)
        win.title("Lỗi / Chưa Xong")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "progress_errors", default="480x520")
        wg.autosave(win, "progress_errors")
        _bind_esc_close(win)

        if not self.task_progress:
            tk.Label(win, text="Chưa có phiên chạy nào trong lần mở Dashboard này. ✅",
                     bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 10)).pack(pady=30, padx=20)
            return

        name_by_id = {}
        for t in self.tasks:
            tid = t.get("id") or task_registry.make_task_id(t.get("file_json", ""))
            name_by_id[tid] = t.get("ten_hien_thi", tid)

        # Tác vụ có VẤN ĐỀ (lỗi/chưa xong/đã dừng thủ công) hiện TRƯỚC, tác
        # vụ đã chạy xong hiện SAU CÙNG để người dùng thấy ngay việc cần xử
        # lý mà không phải lướt qua các dòng "✅ Đã chạy xong" trước.
        items = list(self.task_progress.items())
        items.sort(key=lambda kv: (0 if self._task_progress_has_problem(kv[1]) else 1,
                                    name_by_id.get(kv[0], kv[0])))

        problem_count = sum(1 for _, p in items if self._task_progress_has_problem(p))
        summary = (f"{problem_count} tác vụ cần chú ý (lỗi/chưa xong/đã dừng thủ công) trên tổng "
                   f"{len(items)} tác vụ của phiên chạy gần nhất:") if problem_count else \
                  f"Tất cả {len(items)} tác vụ của phiên chạy gần nhất đều đã chạy xong. ✅"
        tk.Label(win, text=summary, bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 10, "bold"),
                 wraplength=440, justify="left").pack(anchor="w", padx=12, pady=(12, 6))

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
        win.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        for tid, p in items:
            text, color = self._task_progress_status(p)
            card = tk.Frame(inner, bg=COL_PANEL_ALT)
            card.pack(fill="x", pady=3, padx=4)
            row = tk.Frame(card, bg=COL_PANEL_ALT)
            row.pack(fill="x")
            tk.Label(row, text=name_by_id.get(tid, tid), bg=COL_PANEL_ALT, fg=COL_TEXT,
                     font=("Segoe UI", 9)).pack(side="left", padx=8, pady=(6, 2))
            tk.Label(row, text=text, bg=COL_PANEL_ALT, fg=color,
                     font=("Segoe UI", 9, "bold")).pack(side="right", padx=8)
            line = self._task_activity_line(tid)
            if line:
                tk.Label(card, text=line, bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED, font=("Segoe UI", 8),
                         anchor="w", justify="left", wraplength=420).pack(fill="x", padx=8, pady=(0, 6))
            else:
                row.pack_configure(pady=(0, 4))

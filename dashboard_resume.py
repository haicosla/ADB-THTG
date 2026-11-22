"""
dashboard_resume.py — Hộp "PHIÊN CHẠY BỊ GIÁN ĐOẠN" hiện khi MỞ LẠI Dashboard mà lần chạy trước còn dở
(chương trình bị tắt đột ngột / treo / mất điện), và LƯU HÀNG CHỜ job xuống đĩa để không mất.

Dữ liệu lấy từ session_journal.py (ghi liên tục lúc chạy). Hộp liệt kê, mỗi dòng 1 tick:
  - Chạy tay: các tác vụ CHƯA xong (tác vụ đang dở lúc bị ngắt chạy LẠI từ đầu), rồi Hành Động Cuối.
  - Lịch Hẹn Giờ: tài khoản đang dở (đăng nhập lại) + hoạt động chưa xong của nó, các tài khoản sau, Hành Động Cuối.
  - 👥 Xoay Vòng Tài Khoản: y như lịch (tài khoản đang dở + mục chưa xong, tài khoản sau, Hành Động Cuối).
  - 📦 Nhóm Hành Động: các bước CHƯA xong của nhóm.
  - ⏳ Hàng chờ: các job đang xếp hàng chờ từng giả lập lúc app tắt (Hẹn Giờ / Chạy tay / Xoay Vòng / Nhóm / Log
    Nhanh) - tick để NẠP LẠI vào hàng chờ; tự chạy khi giả lập rảnh (giả lập không còn phiên dở thì chạy ngay).
Không tick = xoá (không chạy). Không lưu mật khẩu: tài khoản lưu theo id.
Không phủ: 🎁 Hành Động Sự Kiện (tự lặp suốt ngày, bật lại bằng tay).
"""
import tkinter as tk
from datetime import datetime

import task_registry
import account_manager
import session_journal
from dashboard_theme import *
from dashboard_widgets import RoundedButton, ThemedToplevel


def _fmt_time(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m %H:%M")
    except Exception:
        return str(iso or "?")


def specs_to_selected(specs, tasks_by_id):
    """Ngược của session_journal.selected_to_specs: dựng lại danh sách `selected` (bỏ Hoạt Động đã bị xoá)."""
    out = []
    for sp in specs or []:
        if sp.get("group") is not None:
            out.append({"id": "GROUP-RUN", "ten_hien_thi": sp.get("name", "📦 Nhóm"),
                        "__group_ids__": list(sp.get("group") or [])})
        elif sp.get("id") in tasks_by_id:
            out.append(tasks_by_id[sp["id"]])
    return out


class ResumeMixin:
    # ------------------------------------------------------------------ hàng chờ <-> đĩa
    def _serialize_job(self, job):
        """Job trong hàng chờ -> dict JSON gọn (None nếu loại job không lưu được)."""
        kind = job.get("kind")
        if kind == "schedule":
            return {"kind": kind, "name": job.get("name"), "schedule_id": job.get("schedule_id"),
                    "account_ids": [a.get("id") for a in job.get("accs") or []],
                    "final_ids": list(job.get("final_ids") or []), "schedule_vars": dict(job.get("schedule_vars") or {})}
        if kind == "manual_run":
            return {"kind": kind, "specs": session_journal.selected_to_specs(job.get("selected")),
                    "login": job.get("login_entry") is not None, "preset_vars": dict(job.get("preset_vars") or {})}
        if kind == "manual_accounts":
            return {"kind": kind, "specs": session_journal.selected_to_specs(job.get("selected")),
                    "account_ids": list(job.get("account_ids") or []), "preset_vars": dict(job.get("preset_vars") or {})}
        if kind == "run_group":
            return {"kind": kind, "group_ids": list(job.get("group_ids") or []), "tag": job.get("tag", "")}
        if kind == "quick_login":
            return {"kind": kind, "account_id": (job.get("account") or {}).get("id")}
        return None

    def _persist_queue(self):
        """Ghi toàn bộ hàng chờ hiện tại xuống data/session_journal.json (gọi mỗi khi hàng chờ đổi)."""
        if not getattr(self, "_queue_persist_enabled", False):
            return          # chưa xử lý xong hộp 'chạy tiếp' lúc mở app - tránh ghi đè hàng chờ cũ bằng rỗng
        try:
            with self._queue_lock:
                snap = {}
                for idx, q in self._emulator_job_queue.items():
                    specs = [s for s in (self._serialize_job(j) for j in q) if s]
                    if specs:
                        snap[str(idx)] = specs
            session_journal.save_queue(snap)
        except Exception:
            pass

    def _restore_job(self, sp, tasks_by_id, acc_by_id):
        kind = sp.get("kind")
        job = None
        if kind == "schedule":
            sch = next((x for x in self.schedules if x.get("id") == sp.get("schedule_id")), None)
            if sch is None:
                return None
            activities = self._build_activity_steps(list(sch.get("hoat_dong_ids", [])), tasks_by_id, acc_by_id)
            if not activities:
                return None
            job = {"kind": kind, "name": sp.get("name") or sch.get("ten", "Lịch"), "schedule_id": sp.get("schedule_id"),
                   "accs": [acc_by_id[i] for i in sp.get("account_ids", []) if i in acc_by_id],
                   "activities": activities, "final_ids": sp.get("final_ids") or [],
                   "schedule_vars": sp.get("schedule_vars") or {}}
        elif kind == "manual_run":
            selected = specs_to_selected(sp.get("specs"), tasks_by_id)
            if not selected:
                return None
            login = task_registry.find_task(self.tasks, "auto_login") if sp.get("login") else None
            job = {"kind": kind, "selected": selected, "login_entry": login, "preset_vars": sp.get("preset_vars") or None}
        elif kind == "manual_accounts":
            selected = specs_to_selected(sp.get("specs"), tasks_by_id)
            if not selected:
                return None
            job = {"kind": kind, "selected": selected, "account_ids": sp.get("account_ids") or [],
                   "preset_vars": sp.get("preset_vars") or None}
        elif kind == "run_group":
            job = {"kind": kind, "group_ids": sp.get("group_ids") or [], "tag": sp.get("tag", "")}
        elif kind == "quick_login":
            acc = acc_by_id.get(sp.get("account_id"))
            if not acc:
                return None
            job = {"kind": kind, "account": acc}
        if job is not None:
            job["queued_at"] = datetime.now()
        return job

    # ------------------------------------------------------------------ hộp hỏi lúc mở app
    def _offer_resume_interrupted(self):
        """Gọi 1 lần sau khi mở app: còn phiên dở / hàng chờ lần trước -> hiện hộp chọn chạy tiếp."""
        try:
            recs = session_journal.pending()
            queue_specs = session_journal.load_queue()
            if not recs and not queue_specs:
                self._queue_persist_enabled = True
                return
            tasks_by_id = {(t.get("id") or task_registry.make_task_id(t.get("file_json", ""))): t
                           for t in self.tasks}
            acc_by_id = {a.get("id"): a for a in account_manager.load_accounts()}

            def tname(i):
                t = tasks_by_id.get(i)
                return t.get("ten_hien_thi", i) if t else str(i).replace("__sys__", "⚙ ")

            def spec_names(specs):
                return [(sp.get("name") or "📦 Nhóm") if sp.get("group") is not None else tname(sp.get("id"))
                        for sp in specs or []]

            def left_text(names, done_n):
                left = names[done_n:]
                return ", ".join(left[:6]) + (f" (+{len(left) - 6})" if len(left) > 6 else "")

            rows = []
            for r in recs:
                done_n = int(r.get("act_pos", 0) or 0)
                kind = r.get("kind")
                accs = r.get("account_ids", [])
                ap = int(r.get("acc_pos", 0) or 0)
                if kind == "manual":
                    names = [tname(i) for i in r.get("task_ids", [])]
                    title = "Chạy tay"
                    detail = ("chỉ còn Hành Động Cuối" if r.get("phase") == "final" else
                              f"đã xong {min(done_n, len(names))}/{len(names)} tác vụ; còn: {left_text(names, done_n)}")
                elif kind == "group":
                    title = f"Nhóm '{r.get('tag', '')}'"
                    detail = f"đã xong {done_n} bước"
                else:      # schedule / rotation
                    if kind == "schedule":
                        title = f"Lịch '{r.get('schedule_name', '?')}'"
                        names = [tname(i) for i in r.get("activity_ids", [])]
                    else:
                        title = "Xoay Vòng Tài Khoản"
                        names = spec_names(r.get("specs"))
                    if r.get("phase") == "final":
                        detail = "chỉ còn Hành Động Cuối"
                    elif accs:
                        an = (acc_by_id.get(accs[ap], {}).get("ten_hien_thi") or "?") if ap < len(accs) else "?"
                        detail = (f"đang ở tài khoản {ap + 1}/{len(accs)} ({an}), đã xong {done_n}/{len(names)} mục; "
                                  f"còn {max(0, len(accs) - ap - 1)} tài khoản sau đó")
                    else:
                        detail = f"đã xong {done_n}/{len(names)} mục"
                rows.append({"rec": r, "text": f"{r.get('emu_name', '#' + str(r.get('emu_index')))}  •  {title}  "
                                               f"(bắt đầu {_fmt_time(r.get('started'))}, ngắt lúc {_fmt_time(r.get('updated'))})"
                                               f"\n      {detail}"})
            labels = {"schedule": "⏰ lịch", "manual_run": "▶ chạy tay", "manual_accounts": "👥 xoay vòng",
                      "run_group": "📦 nhóm", "quick_login": "⚡ log nhanh"}
            for idx, specs in queue_specs.items():
                parts = []
                for sp in specs:
                    k = sp.get("kind")
                    extra = sp.get("name") or sp.get("tag") or ""
                    parts.append(labels.get(k, k) + (f" {extra}" if extra else ""))
                rows.append({"queue": (idx, specs),
                             "text": f"⏳ Hàng chờ giả lập #{idx}: {len(specs)} lượt\n      " + "; ".join(parts[:6])
                                     + (f" (+{len(parts) - 6})" if len(parts) > 6 else "")})
            self._resume_dialog_open = True
            self._show_resume_dialog(rows, tasks_by_id, acc_by_id)
        except Exception as e:
            self._resume_dialog_open = False
            self._queue_persist_enabled = True
            try:
                self._log("warn", f"Không kiểm tra được phiên chạy dở: {e}")
            except Exception:
                pass

    def _show_resume_dialog(self, rows, tasks_by_id, acc_by_id):
        win = ThemedToplevel(self.root)
        win.title("Phiên chạy bị gián đoạn")
        win.configure(bg=COL_PANEL)
        win.geometry("860x460")
        win.transient(self.root)
        tk.Label(win, text="⚠ Lần chạy trước còn DỞ / còn việc đang chờ (chương trình bị tắt/treo giữa chừng)",
                 bg=COL_PANEL, fg=COL_TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(win, text="Tick mục muốn CHẠY TIẾP / NẠP LẠI. Việc đang dở lúc bị ngắt sẽ chạy lại từ đầu. "
                           "Mục không tick sẽ bị xoá (không chạy).", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8), wraplength=820, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        bottom = tk.Frame(win, bg=COL_PANEL)
        bottom.pack(side="bottom", fill="x", padx=14, pady=10)
        body = tk.Frame(win, bg=COL_PANEL)
        body.pack(fill="both", expand=True, padx=14)
        vars_ = []
        for row in rows:
            v = tk.BooleanVar(value=True)
            vars_.append(v)
            tk.Checkbutton(body, text=row["text"], variable=v, bg=COL_PANEL, fg=COL_TEXT, selectcolor=COL_PANEL_ALT,
                           activebackground=COL_PANEL, activeforeground=COL_TEXT, anchor="w", justify="left",
                           font=("Segoe UI", 9), wraplength=810).pack(fill="x", pady=3, anchor="w")

        def _finish(do_resume):
            chosen = [row for row, v in zip(rows, vars_) if do_resume and v.get()]
            for row in rows:
                if "rec" in row and row not in chosen:
                    session_journal.end(row["rec"].get("emu_index"))
            self._resume_dialog_open = False
            win.destroy()
            # 1) phiên dở -> chạy tiếp (đánh dấu giả lập bận)
            for row in chosen:
                if "rec" in row:
                    try:
                        self._resume_one(row["rec"])
                    except Exception as e:
                        self._log("error", f"Không chạy tiếp được giả lập #{row['rec'].get('emu_index')}: {e}")
                        session_journal.end(row["rec"].get("emu_index"))
            # 2) hàng chờ -> nạp lại vào bộ nhớ; giả lập nào đang rảnh thì chạy job đầu hàng ngay
            restored = []
            for row in chosen:
                if "queue" not in row:
                    continue
                idx, specs = row["queue"]
                idx = int(idx)
                n = 0
                for sp in specs:
                    try:
                        job = self._restore_job(sp, tasks_by_id, acc_by_id)
                    except Exception as e:
                        job = None
                        self._log("warn", f"Không nạp lại được 1 lượt hàng chờ giả lập #{idx}: {e}")
                    if job is None:
                        continue
                    with self._queue_lock:
                        self._emulator_job_queue.setdefault(idx, []).append(job)
                    n += 1
                if n:
                    restored.append(idx)
                    self._log("info", f"⏳ Đã nạp lại {n} lượt vào hàng chờ giả lập #{idx} (từ lần chạy trước).")
            self._queue_persist_enabled = True
            self._persist_queue()
            self._notify_queue_changed()
            for idx in restored:
                if idx not in self._busy_emulator_indexes:
                    try:
                        self._after_emulator_freed(idx)
                    except Exception as e:
                        self._log("error", f"Không chạy được hàng chờ giả lập #{idx}: {e}")

        RoundedButton(bottom, "▶ Chạy tiếp / nạp lại các mục đã tick", command=lambda: _finish(True), bg=COL_GREEN,
                      container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))
        RoundedButton(bottom, "⏭ Bỏ qua tất cả", command=lambda: _finish(False), bg=COL_GRAY_BTN,
                      container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")).pack(side="left")
        win.protocol("WM_DELETE_WINDOW", lambda: _finish(False))

    # ------------------------------------------------------------------ chạy tiếp 1 bản ghi
    def _resume_one(self, rec):
        idx = rec.get("emu_index")
        emulator = self.emu_manager.find_by_index(idx)
        if emulator is None:
            raise RuntimeError("không tìm thấy giả lập này trong cấu hình LDPlayer")
        tasks_by_id = {(t.get("id") or task_registry.make_task_id(t.get("file_json", ""))): t for t in self.tasks}
        acc_by_id = {a.get("id"): a for a in account_manager.load_accounts()}
        done_n = int(rec.get("act_pos", 0) or 0)
        kind = rec.get("kind")
        if kind == "manual":
            ids = rec.get("task_ids", [])
            selected = [] if rec.get("phase") == "final" else [tasks_by_id[i] for i in ids[done_n:] if i in tasks_by_id]
            login_entry = task_registry.find_task(self.tasks, "auto_login") if rec.get("login") else None
            self._log("info", f"▶ Chạy tiếp phiên chạy tay dở trên '{emulator.name}': {len(selected)} tác vụ còn lại.")
            self._start_run(selected, [emulator], login_entry, rec.get("preset_vars") or None)
            return
        if kind == "group":
            job = {"kind": "run_group", "group_ids": rec.get("group_ids", []), "tag": rec.get("tag", ""),
                   "resume": {"act_pos": done_n}}
            self._log("info", f"▶ Chạy tiếp Nhóm '{rec.get('tag', '')}' trên '{emulator.name}' (từ bước {done_n + 1}).")
            self._run_queued_group_job(job, emulator)
            return
        all_acc = rec.get("account_ids", [])
        ap = int(rec.get("acc_pos", 0) or 0)
        if kind == "rotation":
            selected = specs_to_selected(rec.get("specs"), tasks_by_id)
            if len(selected) != len(rec.get("specs", [])):
                done_n = 0      # có Hoạt Động đã bị xoá từ lúc ngắt -> vị trí không còn đáng tin
                self._log("warn", "Danh sách tác vụ đã đổi từ lúc bị ngắt - chạy tiếp từ tác vụ đầu của tài khoản đang dở.")
            remaining = all_acc[ap:]
            final_only = rec.get("phase") == "final" or bool(all_acc and not remaining)
            job = {"kind": "manual_accounts", "selected": selected, "account_ids": remaining,
                   "preset_vars": rec.get("preset_vars") or None,
                   "resume": {"act_pos": done_n, "final_only": final_only}}
            self._log("info", f"▶ Chạy tiếp Xoay Vòng Tài Khoản trên '{emulator.name}'.")
            self._run_queued_manual_accounts_job(job, emulator)
            return
        # ---- lịch Hẹn Giờ ----
        sch = next((x for x in self.schedules if x.get("id") == rec.get("schedule_id")), None)
        if sch is None:
            raise RuntimeError(f"lịch '{rec.get('schedule_name')}' không còn tồn tại")
        ids = list(sch.get("hoat_dong_ids", []))
        activities = self._build_activity_steps(ids, tasks_by_id, acc_by_id)
        if len(ids) != len(rec.get("activity_ids", [])):
            done_n = 0          # lịch đã bị sửa từ lúc ngắt -> vị trí không còn đáng tin, chạy lại từ hoạt động đầu
            self._log("warn", f"Lịch '{rec.get('schedule_name')}' đã đổi danh sách Hoạt Động từ lúc bị ngắt - "
                               f"chạy tiếp từ Hoạt Động đầu của tài khoản đang dở.")
        accs = [acc_by_id[i] for i in all_acc[ap:] if i in acc_by_id]
        final_only = rec.get("phase") == "final" or bool(all_acc and not accs)
        resume = {"act_pos": done_n, "final_only": final_only}
        self._log("info", f"▶ Chạy tiếp lịch '{rec.get('schedule_name')}' trên '{emulator.name}'.")
        self._start_schedule_worker(rec.get("schedule_name"), idx, accs, activities, rec.get("final_ids"),
                                    rec.get("schedule_vars") or None, schedule_id=rec.get("schedule_id"),
                                    resume=resume)

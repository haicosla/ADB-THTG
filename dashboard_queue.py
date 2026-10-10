"""
dashboard_queue.py — QueueMixin: QUẢN LÝ HÀNG CHỜ theo từng giả lập.

Hàng chờ (self._emulator_job_queue = {emulator_index: [job, job, ...]}) là
nơi các lượt việc bị "xếp lại" khi giả lập đang bận - job đầu hàng tự chạy
khi giả lập rảnh (xem _after_emulator_freed ở dashboard_schedule.py). Mỗi
job là 1 dict có khoá "kind":

    "schedule"        lượt Hẹn Giờ (xem _trigger_schedule)
    "manual_run"      lượt CHẠY tay / Tự Login (xem _start_run)
    "manual_accounts" lượt CHẠY Xoay Vòng Tài Khoản
    "run_group"       lượt ▶ Chạy Nhóm ở '📦 Nhóm Hành Động'
    "quick_login"     ⚡ Log Nhanh / 🔑 Đăng Nhập 1 Acc (MỚI - trước đây chỉ
                      báo "đang bận" rồi huỷ, không xếp hàng)

File này lo:
  - _enqueue_job(): cách DUY NHẤT nên dùng để thêm 1 job vào hàng chờ (có
    khoá luồng + đóng dấu giờ xếp hàng + báo giao diện cập nhật).
  - Nút "⏳ Hàng Chờ (N)" trên thanh nút chính + cửa sổ QUẢN LÝ HÀNG CHỜ:
    xem toàn bộ job đang chờ (theo từng giả lập, kèm việc giả lập đó đang
    chạy), XOÁ job, ĐỔI THỨ TỰ job (⬆ ⬇ ⤒ ⤓, chọn nhiều bằng Ctrl/Shift).
  - _run_queued_quick_login_job(): chạy job "quick_login" lấy từ hàng chờ.

AN TOÀN LUỒNG: _after_emulator_freed có thể được gọi từ luồng nền (luồng
Sự Kiện, luồng bật giả lập...) trong khi cửa sổ này xoá/đổi thứ tự trên luồng
giao diện -> mọi thao tác sửa hàng chờ đều giữ self._queue_lock (RLock, khởi
tạo ở dashboard.py). Cửa sổ nhận diện job bằng CHÍNH đối tượng dict (id()),
không bằng chỉ số vị trí, nên job nào vừa được lấy ra chạy giữa chừng thì
thao tác lên nó tự bị bỏ qua chứ không nhầm sang job khác.

LƯU Ý XOÁ job Hẹn Giờ: lịch đã được đánh dấu "vừa chạy" từ lúc tới giờ (xem
scheduler.mark_triggered) nên xoá job khỏi hàng chờ chỉ BỎ QUA lượt này -
lịch KHÔNG tự xếp lại, lần chạy kế tiếp vẫn theo mốc giờ hẹn bình thường.
(Nếu lịch đang dùng 'Chu kỳ xoay tài khoản' thì tài khoản xoay tới lượt đã
được tính là dùng rồi - lượt bị xoá không được bù lại.)
"""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import window_geometry as wg
from dashboard_theme import *
from dashboard_widgets import RoundedButton, FlowBar, ThemedToplevel

# kind -> (nhãn hiển thị, màu nhãn)
QUEUE_KIND_LABELS = {
    "schedule": ("⏰ Hẹn Giờ", COL_TEAL),
    "manual_run": ("▶ Chạy tay", COL_GREEN),
    "manual_accounts": ("👥 Xoay vòng TK", COL_BLUE),
    "run_group": ("📦 Nhóm", COL_PURPLE),
    "quick_login": ("⚡ Log Nhanh", COL_ORANGE),
}
_QUEUE_SEL_BG = "#22406f"   # nền dòng đang được chọn trong cửa sổ Hàng Chờ


def _fmt_queued_ago(delta):
    secs = max(0, int(delta.total_seconds()))
    if secs < 60:
        return "vừa xong"
    mins = secs // 60
    if mins < 60:
        return f"{mins} phút trước"
    hours, mins = divmod(mins, 60)
    if hours < 24:
        return f"{hours} giờ {mins} phút trước" if mins else f"{hours} giờ trước"
    days, hours = divmod(hours, 24)
    return f"{days} ngày {hours} giờ trước" if hours else f"{days} ngày trước"


class QueueMixin:
    # ------------------------------------------------------------------
    # 1) THÊM job / báo thay đổi / đếm
    # ------------------------------------------------------------------
    def _enqueue_job(self, emulator_index, job):
        """Thêm `job` vào CUỐI hàng chờ của giả lập `emulator_index`, đóng
        dấu giờ xếp hàng (job['queued_at'], chỉ để hiển thị) và báo giao
        diện cập nhật. Trả về VỊ TRÍ (1 = đầu hàng) của job trong hàng chờ
        giả lập đó."""
        with self._queue_lock:
            job.setdefault("queued_at", datetime.now())
            q = self._emulator_job_queue.setdefault(emulator_index, [])
            q.append(job)
            position = len(q)
        self._notify_queue_changed()
        return position

    def _notify_queue_changed(self):
        """Báo hàng chờ vừa đổi - AN TOÀN gọi từ luồng nền (việc cập nhật
        giao diện được xếp lịch về luồng chính qua root.after)."""
        try:
            self.root.after(0, self._on_queue_changed)
        except Exception:
            pass   # cửa sổ chính đã đóng

    def _on_queue_changed(self):
        self._update_queue_badge()
        self._refresh_queue_window()

    def _queue_total_count(self):
        with self._queue_lock:
            return sum(len(q) for q in self._emulator_job_queue.values())

    def _update_queue_badge(self):
        btn = getattr(self, "btn_queue", None)
        if btn is None:
            return
        try:
            btn.set_text(f"⏳ Hàng Chờ ({self._queue_total_count()})")
            bar = btn.master
            if hasattr(bar, "_reflow"):
                bar.after_idle(bar._reflow)   # chữ nút đổi -> bề ngang đổi
        except tk.TclError:
            pass

    def _queue_has_quick_login(self, emulator_index, account_id):
        """Đã có sẵn 1 job Log Nhanh cùng Tài khoản đang chờ trên giả lập
        này chưa (chống bấm đúp -> xếp trùng 2 lượt đăng nhập y hệt)."""
        if not account_id:
            return False
        with self._queue_lock:
            return any(j.get("kind") == "quick_login"
                       and (j.get("account") or {}).get("id") == account_id
                       for j in self._emulator_job_queue.get(emulator_index, []))

    # ------------------------------------------------------------------
    # 2) Chạy job "quick_login" khi đến lượt
    # ------------------------------------------------------------------
    def _run_queued_quick_login_job(self, job, emulator):
        """Chạy 1 job 'quick_login' vừa được lấy ra khỏi hàng chờ vì giả lập
        vừa rảnh. Giả lập được GIỮ CHỖ (đánh dấu bận) NGAY để không lượt nào
        khác chen vào giữa; việc bắt đầu thật chạy ở luồng chính (root.after)
        vì hàm này có thể được gọi từ luồng nền."""
        self._busy_emulator_indexes.add(emulator.index)
        account = job.get("account") or {}

        def _go():
            try:
                self._begin_quick_login(emulator, account)
            except Exception as e:
                self._busy_emulator_indexes.discard(emulator.index)
                self._log("error", f"⚡ Log Nhanh (từ hàng chờ) lỗi khi bắt đầu: {e}",
                           emulator_name=emulator.name)
                self._after_emulator_freed(emulator.index)

        self.root.after(0, _go)

    # ------------------------------------------------------------------
    # 3) Mô tả job / tên giả lập
    # ------------------------------------------------------------------
    @staticmethod
    def _queue_task_names(entries, limit=3):
        names = [(e.get("ten_hien_thi") or e.get("id") or "?") for e in (entries or [])]
        if not names:
            return "(không có tác vụ)"
        txt = ", ".join(names[:limit])
        return txt + (f" … +{len(names) - limit}" if len(names) > limit else "")

    def _queue_job_summary(self, job):
        """(nhãn loại, màu nhãn, chi tiết) của 1 job - dùng để hiện ở cửa sổ
        Hàng Chờ và ghi Nhật Ký khi xoá."""
        kind = job.get("kind")
        label, color = QUEUE_KIND_LABELS.get(kind, (f"❓ {kind}", COL_GRAY_BTN))
        if kind == "schedule":
            n_act = len(job.get("activities") or [])
            n_acc = len(job.get("accs") or [])
            detail = f"Lịch '{job.get('name', '?')}' - {n_act} hoạt động"
            if n_acc:
                detail += f", xoay {n_acc} tài khoản"
        elif kind == "manual_run":
            sel = job.get("selected") or []
            detail = f"{len(sel)} tác vụ: {self._queue_task_names(sel)}"
            if job.get("login_entry"):
                detail += " (kèm Tự Login)"
        elif kind == "manual_accounts":
            sel = job.get("selected") or []
            detail = (f"{len(sel)} tác vụ: {self._queue_task_names(sel)} - xoay "
                      f"{len(job.get('account_ids') or [])} tài khoản")
        elif kind == "run_group":
            detail = f"{job.get('tag') or 'Nhóm Hành Động'}"
        elif kind == "quick_login":
            acc = job.get("account") or {}
            ten = acc.get("ten_hien_thi") or acc.get("username") or acc.get("id") or "?"
            detail = f"Đăng nhập tài khoản '{ten}'"
        else:
            detail = "(loại việc không xác định)"
        return label, color, detail

    def _queue_emulator_name(self, emulator_index):
        for e in getattr(self, "emulators", None) or []:
            if getattr(e, "index", None) == emulator_index:
                return e.name
        return f"#{emulator_index}"

    def _queue_snapshot(self):
        """Bản sao {emulator_index: [job, ...]} (chỉ giả lập còn job chờ)."""
        with self._queue_lock:
            return {idx: list(q) for idx, q in self._emulator_job_queue.items() if q}

    # ------------------------------------------------------------------
    # 4) XOÁ / ĐỔI THỨ TỰ (dùng chung cho cửa sổ và test)
    # ------------------------------------------------------------------
    def _queue_remove_jobs(self, job_ids):
        """Xoá các job có id() nằm trong `job_ids`. Trả về số job đã xoá
        (job nào vừa được chạy/xoá trước đó thì không tính)."""
        job_ids = set(job_ids)
        removed = []   # [(emulator_index, job)]
        with self._queue_lock:
            for idx in list(self._emulator_job_queue):
                q = self._emulator_job_queue[idx]
                keep = []
                for j in q:
                    if id(j) in job_ids:
                        removed.append((idx, j))
                    else:
                        keep.append(j)
                if keep:
                    q[:] = keep
                else:
                    del self._emulator_job_queue[idx]
        for idx, j in removed:
            label, _c, detail = self._queue_job_summary(j)
            self._log("info", f"🗑 Đã xoá khỏi hàng chờ giả lập '{self._queue_emulator_name(idx)}': "
                               f"{label} - {detail}")
        if removed:
            self._notify_queue_changed()
        return len(removed)

    def _queue_move_jobs(self, job_ids, mode):
        """Đổi thứ tự các job có id() trong `job_ids` TRONG PHẠM VI hàng chờ
        của từng giả lập (job không chuyển sang giả lập khác được).
        mode: 'up' / 'down' (nhích 1 bậc, chọn nhiều thì cả khối cùng nhích),
        'top' / 'bottom' (đưa lên đầu / xuống cuối, giữ nguyên thứ tự tương
        đối giữa các job đã chọn). Trả về True nếu thứ tự thực sự thay đổi."""
        job_ids = set(job_ids)
        changed = False
        with self._queue_lock:
            for q in self._emulator_job_queue.values():
                sel = [id(j) in job_ids for j in q]
                if not any(sel):
                    continue
                before = [id(j) for j in q]
                if mode == "up":
                    for i in range(1, len(q)):
                        if sel[i] and not sel[i - 1]:
                            q[i - 1], q[i] = q[i], q[i - 1]
                            sel[i - 1], sel[i] = sel[i], sel[i - 1]
                elif mode == "down":
                    for i in range(len(q) - 2, -1, -1):
                        if sel[i] and not sel[i + 1]:
                            q[i], q[i + 1] = q[i + 1], q[i]
                            sel[i], sel[i + 1] = sel[i + 1], sel[i]
                elif mode == "top":
                    q[:] = [j for j in q if id(j) in job_ids] + [j for j in q if id(j) not in job_ids]
                elif mode == "bottom":
                    q[:] = [j for j in q if id(j) not in job_ids] + [j for j in q if id(j) in job_ids]
                if [id(j) for j in q] != before:
                    changed = True
        if changed:
            self._notify_queue_changed()
        return changed

    # ------------------------------------------------------------------
    # 5) CỬA SỔ QUẢN LÝ HÀNG CHỜ
    # ------------------------------------------------------------------
    def _open_queue_manager(self):
        old = getattr(self, "_queue_win", None)
        if old is not None:
            try:
                if old.winfo_exists():
                    old.deiconify()
                    old.lift()
                    old.focus_force()
                    return
            except tk.TclError:
                pass

        win = self._queue_win = ThemedToplevel(self.root)
        win.title("⏳ Hàng Chờ Giả Lập")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "queue_manager", default="960x560")
        win.minsize(720, 380)
        wg.autosave(win, "queue_manager")

        self._q_sel = set()          # id(job) đang được chọn
        self._q_last_clicked = None  # id(job) bấm gần nhất (làm mốc cho Shift)
        self._q_order = []           # [(emulator_index, job)] theo thứ tự đang hiển thị
        self._q_rows = {}            # id(job) -> [các widget của dòng]
        self._q_wrap_labels = []
        self._q_signature = None
        self._q_poll_id = None

        tk.Label(win, text="⏳ Hàng Chờ Giả Lập", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        tk.Label(
            win,
            text="Các lượt việc đang chờ giả lập rảnh (Hẹn Giờ, CHẠY tay, Xoay Vòng Tài Khoản, Nhóm Hành Động, "
                 "Log Nhanh) - trong mỗi giả lập, job trên cùng sẽ chạy trước. Bấm vào dòng để chọn (Ctrl = chọn "
                 "thêm, Shift = chọn cả khoảng), rồi dùng nút bên dưới để đổi thứ tự hoặc xoá. Việc đổi thứ tự "
                 "chỉ áp dụng TRONG CÙNG 1 giả lập. Job đã chạy xong/đang chạy không nằm ở đây.",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=920, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        # ----- Thanh dưới cùng: PACK TRƯỚC vùng cuộn để luôn hiện đủ nút -----
        bottom = tk.Frame(win, bg=COL_PANEL)
        bottom.pack(side="bottom", fill="x", padx=14, pady=(4, 10))
        self._q_total = tk.Label(bottom, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9),
                                 anchor="w", justify="left")
        self._q_total.pack(anchor="w")
        self._q_status = tk.Label(bottom, text="", bg=COL_PANEL, fg=COL_ACCENT, font=("Segoe UI", 9),
                                  anchor="w", justify="left")
        self._q_status.pack(anchor="w", pady=(0, 6))
        bar = FlowBar(bottom, bg=COL_PANEL)
        bar.pack(fill="x")
        fnt = ("Segoe UI", 9, "bold")
        self._q_sel_buttons = []
        for text, mode in (("⬆ Lên", "up"), ("⬇ Xuống", "down"), ("⤒ Lên đầu", "top"), ("⤓ Xuống cuối", "bottom")):
            b = RoundedButton(bar, text, command=lambda m=mode: self._q_ui_move(m), bg=COL_BLUE,
                              container_bg=COL_PANEL, font=fnt)
            bar.add(b)
            self._q_sel_buttons.append(b)
        b_del = RoundedButton(bar, "🗑 Xoá Đã Chọn", command=self._q_ui_delete, bg=COL_RED,
                              container_bg=COL_PANEL, font=fnt)
        bar.add(b_del)
        self._q_sel_buttons.append(b_del)
        self._q_btn_clear = RoundedButton(bar, "🧹 Xoá Tất Cả", command=self._q_ui_clear_all, bg=COL_GRAY_BTN,
                                          container_bg=COL_PANEL, font=fnt)
        bar.add(self._q_btn_clear)
        bar.add(RoundedButton(bar, "Đóng", command=win.destroy, bg=COL_GRAY_BTN, container_bg=COL_PANEL, font=fnt))

        # ----- Vùng cuộn chứa các dòng -----
        canvas = self._q_canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = self._q_inner = tk.Frame(canvas, bg=COL_PANEL)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 6), pady=4)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        win.bind("<Delete>", lambda e: self._q_ui_delete())

        self._q_canvas_w = 900

        def _on_canvas_resize(e):
            canvas.itemconfigure(win_id, width=e.width)
            self._q_canvas_w = e.width
            self._q_apply_wrap()
        canvas.bind("<Configure>", _on_canvas_resize)

        def _on_destroy(e):
            if e.widget is win:
                pid = self._q_poll_id
                self._q_poll_id = None
                self._queue_win = None
                if pid is not None:
                    try:
                        win.after_cancel(pid)
                    except Exception:
                        pass
        win.bind("<Destroy>", _on_destroy, add="+")

        self._refresh_queue_window(force=True)
        self._q_poll_id = win.after(1000, self._q_poll)
        try:
            win.lift()
            win.focus_force()
        except tk.TclError:
            pass

    def _q_poll(self):
        win = getattr(self, "_queue_win", None)
        if win is None:
            return
        try:
            if not win.winfo_exists():
                self._queue_win = None
                return
        except tk.TclError:
            self._queue_win = None
            return
        self._refresh_queue_window()
        self._q_poll_id = win.after(1000, self._q_poll)

    def _q_set_status(self, text):
        """Dòng thông báo kết quả thao tác gần nhất (chọn/xoá/đổi thứ tự)."""
        try:
            self._q_status.config(text=text)
        except (tk.TclError, AttributeError):
            pass

    def _refresh_queue_window(self, force=False):
        """Dựng lại danh sách dòng nếu hàng chờ/giả lập đổi (hoặc force).
        Không có cửa sổ đang mở thì không làm gì."""
        win = getattr(self, "_queue_win", None)
        if win is None:
            return
        try:
            if not win.winfo_exists():
                return
        except tk.TclError:
            return

        snap = self._queue_snapshot()
        busy = set(self._busy_emulator_indexes)
        cur = getattr(self, "_current_task_by_emulator", {}) or {}
        now = datetime.now()
        signature = (
            tuple((idx, tuple(id(j) for j in jobs)) for idx, jobs in sorted(snap.items())),
            tuple(sorted(idx for idx in snap if idx in busy)),
            tuple((idx, cur.get(self._queue_emulator_name(idx))) for idx in sorted(snap)),
            int(now.timestamp() // 60),   # đổi mỗi phút -> cập nhật chữ "x phút trước"
        )
        if not force and signature == self._q_signature:
            return
        self._q_signature = signature

        canvas, inner = self._q_canvas, self._q_inner
        try:
            top_frac = canvas.yview()[0]
        except tk.TclError:
            top_frac = 0.0
        for w in inner.winfo_children():
            w.destroy()
        self._q_order = []
        self._q_rows = {}
        self._q_wrap_labels = []

        if not snap:
            tk.Label(inner, text="✅ Hàng chờ đang trống - không có lượt việc nào phải chờ giả lập.",
                     bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=12, pady=20)
        for idx in sorted(snap):
            jobs = snap[idx]
            name = self._queue_emulator_name(idx)
            running = cur.get(name)
            if idx in busy:
                st_txt = f"▶ Đang chạy: {running}" if running else "▶ Đang bận (đang chạy việc khác)"
                st_col = COL_GREEN
            else:
                st_txt = "● Giả lập đang rảnh - job đầu hàng sẽ tự chạy ngay"
                st_col = COL_ACCENT
            hdr = tk.Frame(inner, bg=COL_HEADER)
            hdr.pack(fill="x", pady=(8, 2))
            tk.Label(hdr, text=f"📱 #{idx} - {name}", bg=COL_HEADER, fg=COL_TEXT,
                     font=("Segoe UI", 9, "bold")).pack(side="left", padx=8, pady=6)
            tk.Label(hdr, text=st_txt, bg=COL_HEADER, fg=st_col, font=("Segoe UI", 8)).pack(side="left", padx=8)
            tk.Label(hdr, text=f"{len(jobs)} job đang chờ", bg=COL_HEADER, fg=COL_TEXT_MUTED,
                     font=("Segoe UI", 8)).pack(side="right", padx=8)
            for pos, job in enumerate(jobs, 1):
                self._q_add_row(inner, idx, pos, job, now)
                self._q_order.append((idx, job))

        # Bỏ chọn những job không còn trong hàng chờ
        alive = {id(j) for _i, j in self._q_order}
        self._q_sel &= alive
        if self._q_last_clicked not in alive:
            self._q_last_clicked = None
        for jid in self._q_sel:
            self._q_paint_row(jid)
        self._q_refresh_buttons()
        total = len(self._q_order)
        self._q_total.config(text=f"Tổng cộng {total} job đang chờ trên {len(snap)} giả lập." if total
                             else "Không có job nào đang chờ.")
        self._q_apply_wrap()
        try:
            inner.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(top_frac)
        except tk.TclError:
            pass

    def _q_apply_wrap(self):
        """Cho cột chi tiết tự xuống dòng theo bề ngang hiện tại của cửa sổ."""
        wrap = max(220, int(getattr(self, "_q_canvas_w", 900)) - 400)
        for lbl in self._q_wrap_labels:
            try:
                lbl.config(wraplength=wrap)
            except tk.TclError:
                pass

    def _q_add_row(self, inner, emulator_index, pos, job, now):
        label, color, detail = self._queue_job_summary(job)
        row = tk.Frame(inner, bg=COL_PANEL_ALT, highlightthickness=1, highlightbackground=COL_BORDER, cursor="hand2")
        row.pack(fill="x", pady=1, padx=(14, 0))
        widgets = [row]

        lbl_pos = tk.Label(row, text=f"{pos}.", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED, font=("Segoe UI", 9, "bold"),
                           width=3, anchor="e")
        lbl_pos.pack(side="left", padx=(6, 4), pady=6)
        lbl_kind = tk.Label(row, text=label, bg=color, fg="white", font=("Segoe UI", 8, "bold"), padx=8, pady=2,
                            width=14)
        lbl_kind.pack(side="left", padx=4)
        qat = job.get("queued_at")
        if isinstance(qat, datetime):
            when = f"{qat.strftime('%H:%M %d/%m')}\n({_fmt_queued_ago(now - qat)})"
        else:
            when = ""
        lbl_when = tk.Label(row, text=when, bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED, font=("Segoe UI", 8),
                            justify="right", width=16)
        lbl_when.pack(side="right", padx=8)
        lbl_detail = tk.Label(row, text=detail, bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 9), anchor="w",
                              justify="left", wraplength=520)
        lbl_detail.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        self._q_wrap_labels.append(lbl_detail)
        widgets += [lbl_pos, lbl_kind, lbl_when, lbl_detail]

        jid = id(job)
        self._q_rows[jid] = widgets
        for w in widgets:
            w.bind("<Button-1>", lambda e, j=jid: self._q_on_click(j, e))

    def _q_paint_row(self, jid):
        widgets = self._q_rows.get(jid)
        if not widgets:
            return
        bg = _QUEUE_SEL_BG if jid in self._q_sel else COL_PANEL_ALT
        row, lbl_pos, lbl_kind, lbl_when, lbl_detail = widgets
        for w in (row, lbl_pos, lbl_when, lbl_detail):   # nhãn loại giữ màu riêng
            try:
                w.config(bg=bg)
            except tk.TclError:
                pass

    def _q_on_click(self, jid, event):
        ctrl = bool(event.state & 0x4)
        shift = bool(event.state & 0x1)
        ids_in_order = [id(j) for _i, j in self._q_order]
        if shift and self._q_last_clicked in ids_in_order and jid in ids_in_order:
            a, b = ids_in_order.index(self._q_last_clicked), ids_in_order.index(jid)
            lo, hi = min(a, b), max(a, b)
            new_sel = set(ids_in_order[lo:hi + 1])
            self._q_sel = (self._q_sel | new_sel) if ctrl else new_sel
        elif ctrl:
            self._q_sel ^= {jid}
            self._q_last_clicked = jid
        else:
            self._q_sel = {jid}
            self._q_last_clicked = jid
        for j in ids_in_order:
            self._q_paint_row(j)
        self._q_refresh_buttons()
        self._q_set_status(f"Đã chọn {len(self._q_sel)}/{len(ids_in_order)} job." if self._q_sel
                           else "Chưa chọn job nào.")

    def _q_refresh_buttons(self):
        state = "normal" if self._q_sel else "disabled"
        for b in self._q_sel_buttons:
            b.set_state(state)
        self._q_btn_clear.set_state("normal" if self._q_order else "disabled")

    def _q_ui_move(self, mode):
        if not self._q_sel:
            return
        changed = self._queue_move_jobs(self._q_sel, mode)
        name = {"up": "lên 1 bậc", "down": "xuống 1 bậc", "top": "lên đầu hàng", "bottom": "xuống cuối hàng"}[mode]
        self._q_set_status(f"↕ Đã đưa {len(self._q_sel)} job {name}." if changed
                           else "Không đổi được nữa (đã ở đầu/cuối hàng chờ).")
        self._refresh_queue_window(force=True)

    def _q_ui_delete(self):
        if not self._q_sel:
            return
        want = len(self._q_sel)
        n = self._queue_remove_jobs(self._q_sel)
        self._q_sel = set()
        if n == want:
            self._q_set_status(f"🗑 Đã xoá {n} job khỏi hàng chờ.")
        else:
            self._q_set_status(f"🗑 Đã xoá {n}/{want} job - số còn lại đã được chạy/xoá trước đó.")
        self._refresh_queue_window(force=True)

    def _q_ui_clear_all(self):
        total = len(self._q_order)
        if not total:
            return
        if not messagebox.askyesno("Xoá tất cả hàng chờ",
                                   f"Xoá TẤT CẢ {total} job đang chờ ở mọi giả lập?\n\nCác lượt này sẽ KHÔNG "
                                   f"được chạy nữa (lịch Hẹn Giờ vẫn chạy lại ở mốc giờ kế tiếp).",
                                   parent=self._queue_win):
            return
        n = self._queue_remove_jobs({id(j) for _i, j in self._q_order})
        self._q_sel = set()
        self._q_set_status(f"🧹 Đã xoá {n} job khỏi hàng chờ.")
        self._refresh_queue_window(force=True)

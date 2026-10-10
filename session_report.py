"""
session_report.py — Gom kết quả TỪNG lượt chạy Hoạt Động trong 1 phiên rồi dựng tin Telegram
"🏁 Xong toàn bộ phiên" nêu rõ: chạy cái gì, trên giả lập nào, tài khoản nào, mất bao lâu.

Chỉ dùng thư viện chuẩn, KHÔNG import tkinter -> test được độc lập. Không bao giờ ném lỗi
ra ngoài (nơi gọi là luồng chạy thật).

Luồng dùng (xem dashboard_run.py):
  - _exec_entry(): sau mỗi lượt chạy gọi REPORT.add(...)  (dòng nằm ở "mở" theo giả lập)
  - _on_emulator_thread_done(idx): REPORT.close(idx)       (dòng chuyển sang "đã đóng" = thuộc phiên)
  - các worker (CHẠY tay / Nhóm / Xoay Vòng / Hẹn Giờ): REPORT.set_label(idx, "phiên Thư ký" /
    "nhóm X" / "lịch hẹn giờ Y") ngay khi bắt đầu -> mỗi dòng mang nhãn đó, tin tổng kết nêu đúng tên
  - _on_schedule_thread_done: rows = REPORT.take(idx) -> format_report(rows, title="🏁 Xong lịch hẹn giờ Y")
    gửi tin RIÊNG cho lịch hẹn giờ (KHÔNG lẫn vào tin tổng kết phiên chạy tay)
  - _finish_quick_login: REPORT.discard(idx)  (Log Nhanh không có tin tổng kết)
  - _on_finish_all(): rows = REPORT.drain() -> format_report(rows) -> gửi Telegram
"""
import re
import threading
import time

MAX_ROWS_PER_EMU = 300     # chặn phình bộ nhớ nếu có luồng không bao giờ đóng
MAX_CHARS = 3500           # tin Telegram tối đa ~4000 ký tự (notifier cắt ở 4000, chừa chỗ tên máy)

STATUS_ICON = {"done": "✅", "error": "⚠️", "stopped": "⏹"}

_ACC_RE = re.compile(r"Tài khoản thứ\s*\d+\s*/\s*\d+\s*-\s*(.+)$")


def _fmt_hms(ts):
    return time.strftime("%H:%M:%S", time.localtime(ts))


def _fmt_dmy(ts):
    return time.strftime("%d/%m", time.localtime(ts))


def fmt_duration(seconds):
    """Số giây -> '2p13s' / '1g05p' / '8s' (giống notifier.fmt_duration, giữ ở đây để không phụ thuộc)."""
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}g{m:02d}p"
    if m:
        return f"{m}p{sec:02d}s"
    return f"{sec}s"


def short_names(names, limit=3):
    """['A','B','C','D'] -> 'A, B, C +1' (bỏ trùng/rỗng, giữ thứ tự) - dùng làm nhãn ngắn cho tiêu đề tin."""
    seen = []
    for n in names or []:
        n = str(n or "").strip()
        if n and n not in seen:
            seen.append(n)
    if len(seen) <= limit:
        return ", ".join(seen)
    return ", ".join(seen[:limit]) + f" +{len(seen) - limit}"


def account_from_context(context_label):
    """Lấy tên tài khoản từ context_label kiểu '⏰ Đá Gà - Tài khoản thứ 5/8 - Hân' (không có -> None)."""
    if not context_label:
        return None
    m = _ACC_RE.search(str(context_label))
    return m.group(1).strip() if m else None


class SessionReport:
    def __init__(self):
        self._lock = threading.Lock()
        self._open = {}          # emulator_index -> [row]
        self._closed = []        # các row thuộc phiên chạy tay đã đóng
        self._last_account = {}  # emulator_index -> tên tài khoản đăng nhập gần nhất qua app
        self._labels = {}        # emulator_index -> nhãn đang chạy, vd "phiên Thư ký" / "nhóm X"

    # ---------------------------------------------------------- ghi nhận
    def add(self, emu_index, emu_name, task, t_start, t_end, status, account=None,
            account_is_last=False, note=""):
        """status: 'done' | 'error' | 'stopped'. account=None nếu không biết."""
        try:
            row = {"emu_index": emu_index, "emu": str(emu_name), "task": str(task),
                   "t_start": float(t_start), "t_end": float(t_end), "status": status,
                   "account": account, "account_is_last": bool(account_is_last),
                   "note": str(note or "")}
            with self._lock:
                row["label"] = self._labels.get(emu_index, "")
                rows = self._open.setdefault(emu_index, [])
                if len(rows) < MAX_ROWS_PER_EMU:
                    rows.append(row)
        except Exception:
            pass

    def add_note(self, emu_index, emu_name, note):
        """Ghi 1 dòng 'không chạy được' (vd giả lập không bật được) để tin tổng kết không trống trơn."""
        now = time.time()
        self.add(emu_index, emu_name, "(không chạy được)", now, now, "error", note=note)

    def set_label(self, emu_index, label):
        """Đặt nhãn cho các dòng ghi nhận TIẾP THEO của giả lập này (vd 'phiên Thư ký', 'nhóm X').
        Tự xoá khi luồng của giả lập kết thúc (close/discard/take)."""
        with self._lock:
            if label:
                self._labels[emu_index] = str(label)

    def set_last_account(self, emu_index, name):
        with self._lock:
            if name:
                self._last_account[emu_index] = name

    def last_account(self, emu_index):
        with self._lock:
            return self._last_account.get(emu_index)

    def resolve_account(self, emu_index, context_label=None, account_label=None):
        """-> (tên, là_gần_nhất). Ưu tiên: account_label > context_label > tài khoản đăng nhập
        gần nhất trên giả lập này (do chính app đăng nhập) > (None, False)."""
        name = account_label or account_from_context(context_label)
        if name:
            return name, False
        last = self.last_account(emu_index)
        return (last, True) if last else (None, False)

    # ---------------------------------------------------------- vòng đời
    def close(self, emu_index):
        with self._lock:
            self._closed.extend(self._open.pop(emu_index, []))
            self._labels.pop(emu_index, None)

    def discard(self, emu_index):
        with self._lock:
            self._open.pop(emu_index, None)
            self._labels.pop(emu_index, None)

    def take(self, emu_index):
        """Lấy (và xoá) các dòng đang mở của ĐÚNG giả lập này - dùng cho tin tổng kết riêng của lịch hẹn giờ."""
        with self._lock:
            self._labels.pop(emu_index, None)
            return self._open.pop(emu_index, [])

    def drain(self):
        with self._lock:
            rows, self._closed = self._closed, []
        return rows


REPORT = SessionReport()


# ---------------------------------------------------------- dựng tin nhắn
def _row_line(r):
    icon = STATUS_ICON.get(r["status"], "•")
    if r["task"] == "(không chạy được)":
        return f"   {icon} {r['note']}"
    line = (f"   {icon} {r['task']} · {_fmt_hms(r['t_start'])} → {_fmt_hms(r['t_end'])}"
            f" · {fmt_duration(r['t_end'] - r['t_start'])}")
    if r["note"]:
        line += f" · {r['note']}"
    return line


def format_report(rows, t_finish=None, title=None):
    """Dựng nội dung tin 'xong phiên' từ danh sách row (đã drain). Luôn trả về chuỗi.
    title: dòng tiêu đề tự đặt (vd '🏁 Xong lịch hẹn giờ Y'); None -> ghép từ nhãn của các dòng
    ('🏁 Xong phiên Thư ký · nhóm X'), không có nhãn -> '🏁 Xong toàn bộ phiên'."""
    try:
        return _format_report(rows, t_finish, title)
    except Exception:
        return title or "🏁 Đã chạy xong toàn bộ phiên."


def _auto_title(rows):
    labels = []
    for r in rows:
        lb = r.get("label") or ""
        if lb and lb not in labels:
            labels.append(lb)
    return ("🏁 Xong " + " · ".join(labels)) if labels else "🏁 Xong toàn bộ phiên"


def _format_report(rows, t_finish, title=None):
    t_finish = t_finish if t_finish is not None else time.time()
    if not rows:
        if title:
            return title + "\n(Không có Hoạt Động nào được chạy: giả lập không bật được / bị bỏ qua / đã bị dừng ngay từ đầu.)"
        return ("🏁 Đã chạy xong toàn bộ phiên.\n"
                "(Không có Hoạt Động nào được chạy: giả lập không bật được / bị bỏ qua / đã bị dừng ngay từ đầu.)")

    real = [r for r in rows if r["task"] != "(không chạy được)"]
    t0 = min((r["t_start"] for r in real), default=min(r["t_start"] for r in rows))
    n_ok = sum(1 for r in real if r["status"] == "done")
    n_err = sum(1 for r in real if r["status"] == "error")
    n_stop = sum(1 for r in real if r["status"] == "stopped")

    head = [
        title or _auto_title(rows),
        f"🕐 {_fmt_hms(t0)} → {_fmt_hms(t_finish)} {_fmt_dmy(t_finish)} (⏱ {fmt_duration(t_finish - t0)})",
        f"📊 {len(real)} lượt chạy: ✅ {n_ok} · ⚠️ {n_err} · ⏹ {n_stop}",
    ]

    # nhóm: giả lập -> tài khoản -> các lượt (giữ thứ tự xuất hiện)
    emus = {}
    for r in sorted(rows, key=lambda x: x["t_start"]):
        accs = emus.setdefault((r["emu_index"], r["emu"]), {})
        accs.setdefault(r["account"], []).append(r)

    def build(compact):
        out = []
        for (_idx, emu), accs in emus.items():
            out.append("")
            out.append(f"🖥 {emu}")
            for acc, lst in accs.items():
                if acc:
                    # tên lấy từ "lần đăng nhập gần nhất qua app" (không chắc chắn) -> ghi chú rõ
                    guess = all(r["account_is_last"] for r in lst)
                    out.append(f"  👤 {acc}" + (" (đăng nhập gần nhất qua app)" if guess else ""))
                else:
                    out.append("  👤 (không đổi tài khoản / không rõ tài khoản)")
                if compact:
                    ok = sum(1 for r in lst if r["status"] == "done")
                    er = sum(1 for r in lst if r["status"] == "error")
                    st = sum(1 for r in lst if r["status"] == "stopped")
                    tot = sum(r["t_end"] - r["t_start"] for r in lst)
                    out.append(f"   {len(lst)} lượt: ✅ {ok} · ⚠️ {er} · ⏹ {st} · tổng {fmt_duration(tot)}")
                    for r in lst:
                        if r["status"] != "done":
                            out.append(_row_line(r))
                else:
                    out.extend(_row_line(r) for r in lst)
        return "\n".join(head + out)

    text = build(compact=False)
    if len(text) > MAX_CHARS:
        text = build(compact=True)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS - 20].rstrip() + "\n… (đã cắt bớt)"
    return text

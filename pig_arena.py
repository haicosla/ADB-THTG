# -*- coding: utf-8 -*-
"""
pig_arena.py - Sân thử nghiệm bot phối heo (auto_pig) có giao diện.

Chạy:  python pig_arena.py      (cần: pymunk, numpy, opencv - giống pig_bot.py; tkinter có sẵn trong Python)

Làm được gì
  1) TAB "So sánh": thêm NHIỀU file bot (pig_bot.py bản này, bản kia...) hoặc NHÂN BẢN cùng 1 file với thông số khác,
     cho TỰ CHƠI N ván trên CÙNG bộ seed (cùng dãy heo cầm -> so công bằng), chạy song song nhiều LUỒNG (tiến trình).
     Bảng kết quả: tỉ lệ lên cấp thắng + khoảng tin cậy 95%, số lượt TB, cấp cao nhất TB, giây/nước, và so cặp với bot 1
     (số seed bot này thắng mà bot 1 thua / ngược lại, kiểm định dấu p).
  2) Thông số chỉnh được cho từng bot: SimParams (vật lý), EvalParams (trọng số chấm điểm), nước đi (thời gian nghĩ, số điểm thử x).
     Chỉ cần bot có class SimParams/EvalParams và hàm simulate/choose_drop/r_for như pig_bot.py -> tự đọc danh sách thông số từ file.
  3) TAB "Xem lại ván": chạy 1 ván (chọn bot + seed), ghi lại, xem từng lượt: trước khi thả (vạch thả) / sau khi heo yên.
  4) TAB "Log thật": nạp pig_log.jsonl từ máy thật; với mỗi bot đo mô phỏng dự đoán lệch bao nhiêu so ảnh thật lượt sau,
     và (tuỳ chọn) bot sẽ thả ở đâu trên đúng các bàn cờ thật đó so với chỗ đã thả thật.

Lưu ý: kết quả tự chơi dùng CHÍNH bộ vật lý của bot nên lạc quan hơn game thật; dùng để SO SÁNH các bản với nhau, không phải
để đọc tỉ lệ thắng tuyệt đối. Muốn biết sát thật: tab "Log thật".
"""
import copy
import csv
import importlib.util
import inspect
import json
import math
import multiprocessing as mp
import os
import queue
import random
import sys
import threading
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

# ---------------------------------------------------------------------------------------------------------------------
# PHẦN LÕI (chạy được cả trong tiến trình con)
# ---------------------------------------------------------------------------------------------------------------------
_STOP = None


def _init_worker(ev):
    global _STOP
    _STOP = ev


_MODS = {}


def load_bot(path):
    """Nạp file bot thành module (cache theo đường dẫn + thời điểm sửa file)."""
    path = os.path.abspath(path)
    key = (path, os.path.getmtime(path))
    m = _MODS.get(key)
    if m is not None:
        return m
    d = os.path.dirname(path)
    if d not in sys.path:
        sys.path.insert(0, d)
    name = "_pigbot_%d" % (abs(hash(key)) % (10 ** 9))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    _MODS[key] = mod
    return mod


DEFAULT_MOVE = {"think_s": 0.3, "n_x": 17}


def default_params(mod):
    """Đọc danh sách thông số (số/bool) từ SimParams, EvalParams của file bot."""
    out = {"sim": {}, "eval": {}, "move": dict(DEFAULT_MOVE)}
    for sec, cls in (("sim", "SimParams"), ("eval", "EvalParams")):
        c = getattr(mod, cls, None)
        if c is None:
            continue
        try:
            o = c()
        except Exception:
            continue
        for k, v in vars(o).items():
            if not k.startswith("_") and isinstance(v, (bool, int, float)):
                out[sec][k] = v
    return out


def build_params(mod, params):
    sp, ep = mod.SimParams(), mod.EvalParams()
    for k, v in params.get("sim", {}).items():
        setattr(sp, k, v)
    for k, v in params.get("eval", {}).items():
        setattr(ep, k, v)
    return sp, ep


def _call_choose(mod, balls, held, W, H, sp, ep, move, held_top):
    sig = inspect.signature(mod.choose_drop).parameters
    kw = {}
    if "think_s" in sig:
        kw["think_s"] = float(move.get("think_s", 0.3))
    if "n_x" in sig:
        kw["n_x"] = int(move.get("n_x", 17))
    if "held_top" in sig and held_top is not None:
        kw["held_top"] = held_top
    return mod.choose_drop(balls, held, W, H, sp, ep, **kw)


def play(task):
    """Một ván tự chơi. task = (idx, path, params, game_cfg, seed, record)."""
    idx, path, params, g, seed, record = task
    out = {"idx": idx, "seed": seed, "res": "error", "turns": 0, "maxlv": 0, "gain": 0.0, "sec": 0.0, "move_sec": 0.0}
    t00 = time.time()
    try:
        mod = load_bot(path)
        sp, ep = build_params(mod, params)
        move = params.get("move", DEFAULT_MOVE)
        W, H = float(g["W"]), float(g["H"])
        rnd = random.Random(seed)
        levels = g["held_levels"]
        held_top = getattr(mod, "HELD_TOP", None)
        balls, gain_tot, maxlv, tmove = [], 0.0, 0, 0.0
        frames = []
        res = "cap"
        turn = 0
        for turn in range(1, int(g["max_turns"]) + 1):
            if _STOP is not None and _STOP.is_set():
                res = "stop"
                break
            if time.time() - t00 > g["max_sec"]:
                res = "time"
                break
            held = rnd.choice(levels)          # rút TRƯỚC khi bot làm gì -> mọi bot cùng seed cùng dãy heo cầm
            r = mod.r_for(held, W)
            t1 = time.time()
            x, _info = _call_choose(mod, balls, (held, r), W, H, sp, ep, move, held_top)
            tmove += time.time() - t1
            y0 = (-held_top * W + r) if held_top is not None else None
            before = balls
            balls, gain = mod.simulate(balls, W, H, (held, x, r, y0), sp)
            gain_tot += gain
            maxlv = max([maxlv] + [b[0] for b in balls])
            if record:
                frames.append({"held": held, "x": x, "r": r, "y0": y0, "gain": gain,
                               "before": [[a, round(b, 1), round(c, 1), round(d, 1)] for a, b, c, d in before],
                               "after": [[a, round(b, 1), round(c, 1), round(d, 1)] for a, b, c, d in balls]})
            if maxlv >= int(g["win_level"]):
                res = "win"
                break
            top = min((b[2] - b[3] for b in balls), default=H)
            if top < g["danger"] * H:
                res = "lose"
                break
        out.update(res=res, turns=turn, maxlv=maxlv, gain=gain_tot, sec=time.time() - t00,
                   move_sec=tmove / max(1, turn))
        if record:
            out["frames"] = frames
    except Exception:
        out["err"] = traceback.format_exc()
    return out


def analyze_log(task):
    """Đo mô phỏng của 1 bot trên log thật. task = (idx, path, params, rows, choose)."""
    idx, path, params, rows, choose = task
    res = {"idx": idx, "rows": [], "err": None}
    try:
        mod = load_bot(path)
        sp, ep = build_params(mod, params)
        move = params.get("move", DEFAULT_MOVE)
        held_top = getattr(mod, "HELD_TOP", None)
        W, H = rows[0]["W"], rows[0]["H"]
        for i, r0 in enumerate(rows):
            if _STOP is not None and _STOP.is_set():
                break
            before = [tuple(b) for b in r0["before"]]
            held = r0["held"]
            r = mod.r_for(held, W)
            rec = {"turn": r0["turn"], "held": held, "x_real": r0["x_act"], "err": None, "miss": None, "x_bot": None}
            if i + 1 < len(rows):
                y0 = (-held_top * W + r) if held_top is not None else None
                pred, _ = mod.simulate(before, W, H, (held, r0["x_act"], r, y0), sp)
                obs = [tuple(b) for b in rows[i + 1]["before"]]
                rec["err"], rec["miss"] = mod.pred_error(pred, obs, W)
            if choose:
                try:
                    xb, _ = _call_choose(mod, before, (held, r), W, H, sp, ep, move, held_top)
                    rec["x_bot"] = xb
                except Exception:
                    rec["x_bot"] = None
            res["rows"].append(rec)
        res["W"] = W
    except Exception:
        res["err"] = traceback.format_exc()
    return res


def wilson(k, n, z=1.96):
    if n <= 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - s) / d), min(1.0, (c + s) / d)


def sign_test_p(a, b):
    """Kiểm định dấu 2 phía chính xác: a, b = số cặp bên này/ bên kia hơn."""
    n = a + b
    if n == 0:
        return 1.0
    k = min(a, b)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / (2.0 ** n)
    return min(1.0, 2 * p)


def parse_val(txt, old):
    t = str(txt).strip()
    if isinstance(old, bool):
        return t.lower() in ("1", "true", "t", "yes", "y", "on", "co", "có")
    if isinstance(old, int):
        return int(float(t))
    return float(t)


# ---------------------------------------------------------------------------------------------------------------------
# GIAO DIỆN
# ---------------------------------------------------------------------------------------------------------------------
def run_gui():
    import colorsys
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Sân thử bot phối heo - so sánh các bản")
            self.geometry("1280x860")
            self.entries = []          # {"label","path","defaults","params"}
            self.results = {}          # idx -> {seed: dict}
            self.q = queue.Queue()
            self.ev = None
            self.executor = None
            self.running = False
            self.t_start = 0.0
            self.total = 0
            self.done_n = 0
            self.rec = None            # ván đang xem lại
            self.play_job = None
            self.log_rows = None
            self.log_res = {}
            self._build()
            self.after(150, self._poll)

        # ---------------------------------------------------------------- dựng giao diện
        def _build(self):
            nb = ttk.Notebook(self)
            nb.pack(fill="both", expand=True)
            self.tab_cmp = ttk.Frame(nb)
            self.tab_rep = ttk.Frame(nb)
            self.tab_log = ttk.Frame(nb)
            nb.add(self.tab_cmp, text="So sánh các bản")
            nb.add(self.tab_rep, text="Xem lại ván")
            nb.add(self.tab_log, text="Log thật")
            self._build_cmp()
            self._build_rep()
            self._build_log()

        def _build_cmp(self):
            f = self.tab_cmp
            top = ttk.Frame(f)
            top.pack(fill="both", expand=True, padx=6, pady=6)
            # trái: danh sách bot
            left = ttk.LabelFrame(top, text="Các bản bot (mỗi dòng 1 bot)")
            left.pack(side="left", fill="y")
            self.lb = tk.Listbox(left, width=34, height=14, exportselection=False)
            self.lb.pack(fill="x", padx=4, pady=4)
            self.lb.bind("<<ListboxSelect>>", lambda e: self._show_params())
            b = ttk.Frame(left)
            b.pack(fill="x", padx=4)
            for txt, cmd in (("Thêm file bot...", self.add_bot), ("Nhân bản (đổi thông số)", self.clone_bot),
                             ("Đổi tên", self.rename_bot), ("Xoá", self.del_bot), ("Tải lại file", self.reload_bot)):
                ttk.Button(b, text=txt, command=cmd).pack(fill="x", pady=1)
            # giữa: thông số
            mid = ttk.LabelFrame(top, text="Thông số của bot đang chọn (bấm đúp vào dòng để sửa; dòng đỏ = khác mặc định)")
            mid.pack(side="left", fill="both", expand=True, padx=6)
            cols = ("nhom", "ten", "macdinh", "giatri")
            self.ptree = ttk.Treeview(mid, columns=cols, show="headings", height=14)
            for c, t, w in (("nhom", "Nhóm", 60), ("ten", "Thông số", 170), ("macdinh", "Mặc định", 90), ("giatri", "Giá trị", 90)):
                self.ptree.heading(c, text=t)
                self.ptree.column(c, width=w, anchor="w")
            sb = ttk.Scrollbar(mid, orient="vertical", command=self.ptree.yview)
            self.ptree.configure(yscrollcommand=sb.set)
            self.ptree.pack(side="left", fill="both", expand=True)
            sb.pack(side="left", fill="y")
            self.ptree.tag_configure("chg", foreground="#c00000")
            self.ptree.bind("<Double-1>", self.edit_param)
            pb = ttk.Frame(mid)
            pb.pack(side="left", fill="y", padx=4)
            ttk.Button(pb, text="Đặt lại mặc định", command=self.reset_params).pack(fill="x", pady=1)
            ttk.Button(pb, text="Chép thông số\nsang TẤT CẢ bot", command=self.copy_params_all).pack(fill="x", pady=1)
            # phải: cài đặt chạy
            right = ttk.LabelFrame(top, text="Cài đặt chạy")
            right.pack(side="left", fill="y")
            self.cfg = {}
            cpu = os.cpu_count() or 2
            rows = (("n", "Số ván / bot", "40"), ("seed0", "Seed bắt đầu", "1"), ("workers", "Số luồng (tiến trình)", str(max(1, cpu - 1))),
                    ("max_turns", "Số lượt tối đa / ván", "600"), ("danger", "Vạch thua (% chiều cao khung)", "6"),
                    ("win_level", "Cấp thắng", "10"), ("held_levels", "Cấp heo cầm (cách nhau dấu phẩy)", "1,2,3,4"),
                    ("max_sec", "Giới hạn giây / ván", "900"), ("W", "Rộng khung (px)", "692"), ("H", "Cao khung (px)", "787"))
            for i, (k, t, d) in enumerate(rows):
                ttk.Label(right, text=t).grid(row=i, column=0, sticky="w", padx=4, pady=1)
                v = tk.StringVar(value=d)
                self.cfg[k] = v
                ttk.Entry(right, textvariable=v, width=9).grid(row=i, column=1, padx=4, pady=1)
            bar = ttk.Frame(f)
            bar.pack(fill="x", padx=6)
            self.btn_run = ttk.Button(bar, text="▶ Chạy so sánh", command=self.start_run)
            self.btn_run.pack(side="left")
            self.btn_stop = ttk.Button(bar, text="■ Dừng", command=self.stop_run, state="disabled")
            self.btn_stop.pack(side="left", padx=4)
            ttk.Button(bar, text="Xoá kết quả", command=self.clear_results).pack(side="left")
            ttk.Button(bar, text="Xuất CSV...", command=self.export_csv).pack(side="left", padx=4)
            self.prog = ttk.Progressbar(bar, length=320)
            self.prog.pack(side="left", padx=8)
            self.prog_lbl = ttk.Label(bar, text="")
            self.prog_lbl.pack(side="left")
            res = ttk.LabelFrame(f, text="Kết quả (cùng seed cho mọi bot; 'so bot 1' = số seed bot này thắng mà bot 1 thua / ngược lại)")
            res.pack(fill="both", expand=True, padx=6, pady=6)
            cols = ("bot", "xong", "thang", "ti_le", "ci", "luot", "cap", "giay", "sbot", "so")
            self.rtree = ttk.Treeview(res, columns=cols, show="headings", height=7)
            for c, t, w in (("bot", "Bot", 220), ("xong", "Ván xong", 70), ("thang", "Thắng", 60), ("ti_le", "Tỉ lệ %", 70),
                            ("ci", "KTC 95%", 110), ("luot", "Lượt TB", 70), ("cap", "Cấp cao TB", 80),
                            ("giay", "Giây/ván", 70), ("sbot", "Giây/nước", 80), ("so", "So bot 1 (thắng+ / thắng-)  p", 260)):
                self.rtree.heading(c, text=t)
                self.rtree.column(c, width=w, anchor="w")
            self.rtree.pack(fill="x")
            self.txt = tk.Text(res, height=8, wrap="word")
            self.txt.pack(fill="both", expand=True, pady=(6, 0))

        def _build_rep(self):
            f = self.tab_rep
            bar = ttk.Frame(f)
            bar.pack(fill="x", padx=6, pady=6)
            ttk.Label(bar, text="Bot:").pack(side="left")
            self.rep_bot = ttk.Combobox(bar, state="readonly", width=30)
            self.rep_bot.pack(side="left", padx=4)
            ttk.Label(bar, text="Seed:").pack(side="left")
            self.rep_seed = tk.StringVar(value="1")
            ttk.Entry(bar, textvariable=self.rep_seed, width=7).pack(side="left", padx=4)
            self.rep_btn = ttk.Button(bar, text="Chạy & ghi lại ván", command=self.rep_run)
            self.rep_btn.pack(side="left", padx=4)
            self.rep_play = ttk.Button(bar, text="▶ Phát", command=self.rep_toggle, state="disabled")
            self.rep_play.pack(side="left")
            ttk.Label(bar, text="Tốc độ (ms/khung):").pack(side="left", padx=(10, 2))
            self.rep_speed = tk.StringVar(value="350")
            ttk.Entry(bar, textvariable=self.rep_speed, width=6).pack(side="left")
            self.rep_info = ttk.Label(bar, text="")
            self.rep_info.pack(side="left", padx=10)
            self.cv_w, self.cv_h = 520, 590
            self.cv = tk.Canvas(f, width=self.cv_w, height=self.cv_h, bg="#efe6cf", highlightthickness=1)
            self.cv.pack(side="left", padx=8, pady=4)
            side = ttk.Frame(f)
            side.pack(side="left", fill="both", expand=True, padx=6)
            self.rep_scale = tk.Scale(side, from_=0, to=0, orient="horizontal", command=lambda v: self.rep_draw(int(float(v))), length=500)
            self.rep_scale.pack(fill="x")
            self.rep_txt = tk.Text(side, height=24, wrap="word")
            self.rep_txt.pack(fill="both", expand=True, pady=6)

        def _build_log(self):
            f = self.tab_log
            bar = ttk.Frame(f)
            bar.pack(fill="x", padx=6, pady=6)
            self.log_path = tk.StringVar()
            ttk.Entry(bar, textvariable=self.log_path, width=70).pack(side="left")
            ttk.Button(bar, text="Chọn pig_log.jsonl...", command=self.log_browse).pack(side="left", padx=4)
            self.log_choose = tk.BooleanVar(value=True)
            ttk.Checkbutton(bar, text="Cho bot chọn lại x trên bàn thật (chậm hơn)", variable=self.log_choose).pack(side="left", padx=6)
            self.log_btn = ttk.Button(bar, text="Phân tích", command=self.log_run)
            self.log_btn.pack(side="left")
            self.log_lbl = ttk.Label(bar, text="")
            self.log_lbl.pack(side="left", padx=8)
            cols = ("bot", "luot", "sai", "lech", "dx")
            self.ltree = ttk.Treeview(f, columns=cols, show="headings", height=6)
            for c, t, w in (("bot", "Bot", 240), ("luot", "Số lượt đo", 80), ("sai", "Sai số mô phỏng TB (x rộng khung)", 220),
                            ("lech", "Lượt lệch lớn (>0.05)", 150), ("dx", "|x bot - x thật| TB (% khung)", 220)):
                self.ltree.heading(c, text=t)
                self.ltree.column(c, width=w, anchor="w")
            self.ltree.pack(fill="x", padx=6)
            self.ltree.bind("<<TreeviewSelect>>", lambda e: self.log_detail())
            cols = ("turn", "held", "x_real", "err", "miss", "x_bot")
            self.dtree = ttk.Treeview(f, columns=cols, show="headings", height=18)
            for c, t, w in (("turn", "Lượt", 60), ("held", "Cầm", 60), ("x_real", "x đã thả (%)", 100), ("err", "Sai số dự đoán", 120),
                            ("miss", "Heo lệch", 80), ("x_bot", "x bot chọn (%)", 110)):
                self.dtree.heading(c, text=t)
                self.dtree.column(c, width=w, anchor="w")
            self.dtree.pack(fill="both", expand=True, padx=6, pady=6)
            ttk.Label(f, text="Sai số mô phỏng lớn = vật lý chưa giống game thật (hoặc lượt đó đọc sai). 'x bot chọn' khác xa 'x đã thả' "
                              "= bot này sẽ đi khác bản đã chạy thật.").pack(anchor="w", padx=6)

        # ---------------------------------------------------------------- quản lý bot
        def add_bot(self):
            ps = filedialog.askopenfilenames(title="Chọn file bot (.py)", filetypes=[("Python", "*.py")])
            for p in ps:
                self._add_entry(p, os.path.basename(p))

        def _add_entry(self, path, label, params=None):
            try:
                mod = load_bot(path)
                d = default_params(mod)
            except Exception:
                messagebox.showerror("Lỗi nạp bot", "%s\n\n%s" % (path, traceback.format_exc()[-1500:]))
                return
            used = {e["label"] for e in self.entries}
            lb, n = label, 2
            while lb in used:
                lb = "%s #%d" % (label, n)
                n += 1
            self.entries.append({"label": lb, "path": path, "defaults": d, "params": params or copy.deepcopy(d)})
            self._refresh_list(len(self.entries) - 1)

        def _refresh_list(self, sel=None):
            self.lb.delete(0, "end")
            for i, e in enumerate(self.entries):
                self.lb.insert("end", "%d. %s" % (i + 1, e["label"]))
            self.rep_bot["values"] = [e["label"] for e in self.entries]
            if self.entries and not self.rep_bot.get():
                self.rep_bot.current(0)
            if sel is not None and self.entries:
                self.lb.selection_clear(0, "end")
                self.lb.selection_set(sel)
            self._show_params()

        def _cur(self):
            s = self.lb.curselection()
            return self.entries[s[0]] if s else None

        def clone_bot(self):
            e = self._cur()
            if not e:
                return
            lab = simpledialog.askstring("Nhân bản", "Tên bản mới:", initialvalue=e["label"] + " (thử)")
            if lab:
                self._add_entry(e["path"], lab, copy.deepcopy(e["params"]))

        def rename_bot(self):
            e = self._cur()
            if e:
                lab = simpledialog.askstring("Đổi tên", "Tên mới:", initialvalue=e["label"])
                if lab:
                    e["label"] = lab
                    self._refresh_list(self.lb.curselection()[0])

        def del_bot(self):
            s = self.lb.curselection()
            if s:
                del self.entries[s[0]]
                self.results.clear()
                self._refresh_list(min(s[0], len(self.entries) - 1) if self.entries else None)
                self.refresh_results()

        def reload_bot(self):
            e = self._cur()
            if not e:
                return
            try:
                mod = load_bot(e["path"])
                d = default_params(mod)
            except Exception:
                messagebox.showerror("Lỗi nạp bot", traceback.format_exc()[-1500:])
                return
            old = e["params"]
            new = copy.deepcopy(d)
            for sec in new:
                for k in new[sec]:
                    if k in old.get(sec, {}) and old[sec][k] != e["defaults"].get(sec, {}).get(k):
                        new[sec][k] = old[sec][k]          # giữ giá trị đã sửa
            e["defaults"], e["params"] = d, new
            self._show_params()

        # ---------------------------------------------------------------- thông số
        def _show_params(self):
            self.ptree.delete(*self.ptree.get_children())
            e = self._cur()
            if not e:
                return
            names = {"sim": "Vật lý", "eval": "Chấm điểm", "move": "Nước đi"}
            for sec in ("move", "sim", "eval"):
                for k, v in e["params"].get(sec, {}).items():
                    d = e["defaults"].get(sec, {}).get(k)
                    chg = ("chg",) if v != d else ()
                    self.ptree.insert("", "end", iid="%s|%s" % (sec, k), values=(names[sec], k, d, v), tags=chg)

        def edit_param(self, ev):
            e = self._cur()
            iid = self.ptree.identify_row(ev.y)
            if not e or not iid:
                return
            sec, k = iid.split("|", 1)
            old = e["params"][sec][k]
            s = simpledialog.askstring("Sửa thông số", "%s.%s  (mặc định %s)" % (sec, k, e["defaults"][sec].get(k)), initialvalue=str(old))
            if s is None:
                return
            try:
                e["params"][sec][k] = parse_val(s, e["defaults"][sec].get(k, old))
            except Exception:
                messagebox.showerror("Sai giá trị", "Không đọc được số: %s" % s)
            self._show_params()

        def reset_params(self):
            e = self._cur()
            if e:
                e["params"] = copy.deepcopy(e["defaults"])
                self._show_params()

        def copy_params_all(self):
            e = self._cur()
            if not e:
                return
            for o in self.entries:
                if o is e:
                    continue
                for sec in e["params"]:
                    for k, v in e["params"][sec].items():
                        if k in o["params"].get(sec, {}):
                            o["params"][sec][k] = v

        # ---------------------------------------------------------------- chạy so sánh
        def _game_cfg(self):
            c = {k: v.get().strip() for k, v in self.cfg.items()}
            lv = [int(x) for x in c["held_levels"].replace(" ", "").split(",") if x]
            return {"W": float(c["W"]), "H": float(c["H"]), "max_turns": int(c["max_turns"]), "danger": float(c["danger"]) / 100.0,
                    "win_level": int(c["win_level"]), "held_levels": lv, "max_sec": float(c["max_sec"])}, \
                   int(c["n"]), int(c["seed0"]), int(c["workers"])

        def _new_pool(self, workers):
            ctx = mp.get_context("spawn")
            self.ev = ctx.Event()
            return ProcessPoolExecutor(max_workers=max(1, workers), mp_context=ctx, initializer=_init_worker, initargs=(self.ev,))

        def start_run(self):
            if self.running:
                return
            if not self.entries:
                messagebox.showinfo("Chưa có bot", "Bấm 'Thêm file bot...' trước.")
                return
            try:
                g, n, seed0, workers = self._game_cfg()
            except Exception as ex:
                messagebox.showerror("Sai cài đặt", str(ex))
                return
            tasks = []
            for seed in range(seed0, seed0 + n):          # xen kẽ theo seed -> kết quả cặp đôi sớm
                for i, e in enumerate(self.entries):
                    if seed not in self.results.get(i, {}):
                        tasks.append((i, e["path"], copy.deepcopy(e["params"]), g, seed, False))
            if not tasks:
                messagebox.showinfo("Đã đủ", "Các seed này đã chạy xong. Đổi seed bắt đầu / số ván hoặc xoá kết quả.")
                return
            self.total, self.done_n, self.t_start, self.running = len(tasks), 0, time.time(), True
            self.prog.configure(maximum=self.total, value=0)
            self.btn_run.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.executor = self._new_pool(workers)
            ex, label_of = self.executor, {i: e["label"] for i, e in enumerate(self.entries)}

            def runner():
                try:
                    futs = [ex.submit(play, t) for t in tasks]
                    for f in as_completed(futs):
                        try:
                            self.q.put(("res", f.result()))
                        except Exception as exn:
                            self.q.put(("err", repr(exn)))
                except Exception:
                    self.q.put(("err", traceback.format_exc()))
                self.q.put(("done", None))

            threading.Thread(target=runner, daemon=True).start()

        def stop_run(self):
            if self.ev is not None:
                self.ev.set()
            if self.executor is not None:
                try:
                    self.executor.shutdown(wait=False, cancel_futures=True)
                except Exception:
                    pass

        def clear_results(self):
            if self.running:
                return
            self.results.clear()
            self.refresh_results()

        def _poll(self):
            try:
                while True:
                    kind, d = self.q.get_nowait()
                    if kind == "res":
                        self.done_n += 1
                        if d.get("err"):
                            self.txt.insert("end", "[Lỗi bot %d seed %s]\n%s\n" % (d["idx"] + 1, d["seed"], d["err"][-1200:]))
                            self.txt.see("end")
                        elif d["res"] not in ("stop",):
                            self.results.setdefault(d["idx"], {})[d["seed"]] = d
                        self.prog.configure(value=self.done_n)
                        el = time.time() - self.t_start
                        eta = el / max(1, self.done_n) * (self.total - self.done_n)
                        self.prog_lbl.configure(text="%d/%d ván - còn ~%d giây" % (self.done_n, self.total, eta))
                        self.refresh_results()
                    elif kind == "err":
                        self.txt.insert("end", "[Lỗi] %s\n" % d)
                    elif kind == "done":
                        self.running = False
                        self.btn_run.configure(state="normal")
                        self.btn_stop.configure(state="disabled")
                        self.prog_lbl.configure(text="Xong %d ván trong %d giây" % (self.done_n, time.time() - self.t_start))
                    elif kind == "rep":
                        self._rep_done(d)
                    elif kind == "log":
                        self._log_done(d)
            except queue.Empty:
                pass
            self.after(150, self._poll)

        def refresh_results(self):
            self.rtree.delete(*self.rtree.get_children())
            base = self.results.get(0, {})
            lines = []
            for i, e in enumerate(self.entries):
                rs = list(self.results.get(i, {}).values())
                n = len(rs)
                if not n:
                    self.rtree.insert("", "end", values=(e["label"], 0, "", "", "", "", "", "", "", ""))
                    continue
                w = sum(1 for r in rs if r["res"] == "win")
                lo, hi = wilson(w, n)
                so = ""
                if i > 0 and base:
                    common = [s for s in self.results[i] if s in base]
                    a = sum(1 for s in common if base[s]["res"] == "win" and self.results[i][s]["res"] != "win")
                    b = sum(1 for s in common if base[s]["res"] != "win" and self.results[i][s]["res"] == "win")
                    so = "%d cặp: +%d / -%d  p=%.2f" % (len(common), b, a, sign_test_p(a, b))
                self.rtree.insert("", "end", values=(
                    e["label"], n, w, "%.1f" % (100.0 * w / n), "%.0f–%.0f%%" % (100 * lo, 100 * hi),
                    "%.0f" % (sum(r["turns"] for r in rs) / n), "%.2f" % (sum(r["maxlv"] for r in rs) / n),
                    "%.0f" % (sum(r["sec"] for r in rs) / n), "%.2f" % (sum(r["move_sec"] for r in rs) / n), so))
                lines.append((e["label"], n, w))
            if len(lines) >= 2:
                self.txt.delete("1.0", "end")
                self.txt.insert("end", "Gợi ý đọc: nếu khoảng tin cậy 95%% của hai bản chồng nhau nhiều và p (so cặp) > 0.05 thì CHƯA đủ bằng chứng "
                                       "bản nào hơn - tăng số ván (vài chục đến vài trăm). KTC = khoảng tin cậy Wilson của tỉ lệ thắng. "
                                       "'Thắng' = đạt cấp thắng trước khi heo chạm vạch thua.\n")

        def export_csv(self):
            p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if not p:
                return
            with open(p, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["bot", "seed", "ket_qua", "luot", "cap_cao", "diem_gop", "giay", "giay_moi_nuoc"])
                for i, e in enumerate(self.entries):
                    for s, r in sorted(self.results.get(i, {}).items()):
                        w.writerow([e["label"], s, r["res"], r["turns"], r["maxlv"], round(r["gain"], 1), round(r["sec"], 1), round(r["move_sec"], 3)])

        # ---------------------------------------------------------------- xem lại ván
        def rep_run(self):
            if not self.entries or not self.rep_bot.get():
                return
            i = self.rep_bot.current()
            e = self.entries[i]
            try:
                g, _n, _s, _w = self._game_cfg()
                seed = int(self.rep_seed.get())
            except Exception as ex:
                messagebox.showerror("Sai cài đặt", str(ex))
                return
            self.rep_btn.configure(state="disabled")
            self.rep_info.configure(text="Đang chạy ván...")
            task = (i, e["path"], copy.deepcopy(e["params"]), g, seed, True)
            self._rep_g = g

            def run():
                ex = self._new_pool(1)
                try:
                    self.q.put(("rep", ex.submit(play, task).result()))
                except Exception:
                    self.q.put(("rep", {"err": traceback.format_exc()}))
                finally:
                    ex.shutdown(wait=False)

            threading.Thread(target=run, daemon=True).start()

        def _rep_done(self, d):
            self.rep_btn.configure(state="normal")
            if d.get("err"):
                self.rep_info.configure(text="Lỗi")
                self.rep_txt.delete("1.0", "end")
                self.rep_txt.insert("end", d["err"])
                return
            self.rec = d
            n = len(d["frames"]) * 2
            self.rep_scale.configure(to=max(0, n - 1))
            self.rep_scale.set(0)
            self.rep_play.configure(state="normal")
            self.rep_info.configure(text="Kết quả: %s sau %d lượt, cấp cao nhất %d" % (d["res"], d["turns"], d["maxlv"]))
            self.rep_draw(0)

        def _lv_color(self, lv):
            r, g, b = colorsys.hsv_to_rgb((lv * 0.083) % 1.0, 0.45, 0.95)
            return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))

        def rep_draw(self, k):
            if not self.rec:
                return
            fr = self.rec["frames"][k // 2]
            g = self._rep_g
            W, H = g["W"], g["H"]
            sc = min((self.cv_w - 8) / W, (self.cv_h - 8) / H)
            ox, oy = 4, 4
            c = self.cv
            c.delete("all")
            c.create_rectangle(ox, oy, ox + W * sc, oy + H * sc, outline="#444")
            yl = oy + g["danger"] * H * sc
            c.create_line(ox, yl, ox + W * sc, yl, fill="red", dash=(4, 3))
            before = (k % 2 == 0)
            for lv, x, y, r in (fr["before"] if before else fr["after"]):
                c.create_oval(ox + (x - r) * sc, oy + (y - r) * sc, ox + (x + r) * sc, oy + (y + r) * sc, fill=self._lv_color(lv), outline="#333")
                c.create_text(ox + x * sc, oy + y * sc, text="L%d" % lv, font=("Arial", max(8, int(r * sc * 0.6)), "bold"))
            if before:
                x, r = fr["x"], fr["r"]
                c.create_line(ox + x * sc, oy, ox + x * sc, oy + H * sc, fill="#ff8800", width=2)
                c.create_oval(ox + (x - r) * sc, oy + 2, ox + (x + r) * sc, oy + 2 + 2 * r * sc, fill=self._lv_color(fr["held"]), outline="#0050ff", width=2)
                c.create_text(ox + x * sc, oy + 2 + r * sc, text="L%d" % fr["held"])
            self.rep_txt.delete("1.0", "end")
            self.rep_txt.insert("end", "Lượt %d/%d - %s\nCầm cấp %d, thả x=%.0f (%.0f%% khung), điểm gộp lượt này %.0f\nSố heo: %d trước, %d sau\n" % (
                k // 2 + 1, len(self.rec["frames"]), "TRƯỚC khi thả (vạch cam = nơi thả)" if before else "SAU khi heo yên",
                fr["held"], fr["x"], 100.0 * fr["x"] / W, fr["gain"], len(fr["before"]), len(fr["after"])))

        def rep_toggle(self):
            if self.play_job:
                self.after_cancel(self.play_job)
                self.play_job = None
                self.rep_play.configure(text="▶ Phát")
                return
            self.rep_play.configure(text="⏸ Dừng phát")
            self._rep_step()

        def _rep_step(self):
            k = self.rep_scale.get() + 1
            if not self.rec or k >= len(self.rec["frames"]) * 2:
                self.play_job = None
                self.rep_play.configure(text="▶ Phát")
                return
            self.rep_scale.set(k)
            try:
                ms = max(30, int(self.rep_speed.get()))
            except Exception:
                ms = 350
            self.play_job = self.after(ms, self._rep_step)

        # ---------------------------------------------------------------- log thật
        def log_browse(self):
            p = filedialog.askopenfilename(filetypes=[("pig_log.jsonl", "*.jsonl"), ("Tất cả", "*.*")])
            if p:
                self.log_path.set(p)

        def log_run(self):
            if not self.entries:
                messagebox.showinfo("Chưa có bot", "Thêm bot ở tab So sánh trước.")
                return
            try:
                rows = []
                with open(self.log_path.get(), encoding="utf-8") as f:
                    for ln in f:
                        if ln.strip():
                            rows.append(json.loads(ln))
                if len(rows) < 2:
                    raise ValueError("Log cần >= 2 lượt")
            except Exception as ex:
                messagebox.showerror("Không đọc được log", str(ex))
                return
            self.log_rows = rows
            self.log_res = {}
            self.ltree.delete(*self.ltree.get_children())
            self.dtree.delete(*self.dtree.get_children())
            self.log_btn.configure(state="disabled")
            self.log_lbl.configure(text="Đang phân tích...")
            tasks = [(i, e["path"], copy.deepcopy(e["params"]), rows, bool(self.log_choose.get())) for i, e in enumerate(self.entries)]
            self._log_left = len(tasks)
            workers = int(self.cfg["workers"].get() or 1)

            def run():
                ex = self._new_pool(min(workers, len(tasks)))
                try:
                    for f in as_completed([ex.submit(analyze_log, t) for t in tasks]):
                        try:
                            self.q.put(("log", f.result()))
                        except Exception:
                            self.q.put(("log", {"idx": -1, "err": traceback.format_exc(), "rows": []}))
                finally:
                    ex.shutdown(wait=False)

            threading.Thread(target=run, daemon=True).start()

        def _log_done(self, d):
            self._log_left -= 1
            if self._log_left <= 0:
                self.log_btn.configure(state="normal")
                self.log_lbl.configure(text="Xong")
            if d.get("err"):
                messagebox.showerror("Lỗi phân tích", d["err"][-1500:])
                return
            self.log_res[d["idx"]] = d
            rs = d["rows"]
            W = d.get("W", 692)
            errs = [r["err"] for r in rs if r["err"] is not None]
            dxs = [abs(r["x_bot"] - r["x_real"]) / W * 100 for r in rs if r["x_bot"] is not None]
            self.ltree.insert("", "end", iid=str(d["idx"]), values=(
                self.entries[d["idx"]]["label"], len(errs), "%.4f" % (sum(errs) / len(errs)) if errs else "",
                sum(1 for e in errs if e > 0.05), "%.1f" % (sum(dxs) / len(dxs)) if dxs else "(không chọn lại)"))

        def log_detail(self):
            s = self.ltree.selection()
            self.dtree.delete(*self.dtree.get_children())
            if not s:
                return
            d = self.log_res.get(int(s[0]))
            if not d:
                return
            W = d.get("W", 692)
            for r in d["rows"]:
                self.dtree.insert("", "end", values=(
                    r["turn"], "L%d" % r["held"], "%.0f" % (100.0 * r["x_real"] / W),
                    "" if r["err"] is None else "%.3f" % r["err"], "" if r["miss"] is None else r["miss"],
                    "" if r["x_bot"] is None else "%.0f" % (100.0 * r["x_bot"] / W)))

    App().mainloop()


if __name__ == "__main__":
    mp.freeze_support()
    run_gui()

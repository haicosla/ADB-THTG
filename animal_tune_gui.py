# -*- coding: utf-8 -*-
"""
animal_tune_gui.py - GIAO DIỆN để thử cấu hình bot "Thế Giới Động Vật" trên game giả (animal_sim.py), không cần LDPlayer.
Cần animal_bot.py, animal_sim.py, animal_tune.py cùng thư mục.   Chạy:  python animal_tune_gui.py

Tab "So sánh": chọn nhiều cấu hình (có sẵn hoặc tự viết) -> chạy cùng seed -> bảng hiệp sống TB, chênh lệch ghép cặp so với cấu hình ĐẦU TIÊN (** = đáng tin).
Tab "Chỉnh trọng số (CE)": tự tìm trọng số tốt hơn (Cross-Entropy), có đồ thị từng thế hệ và kiểm lại trên ván mới.
Cài đặt chung (trên cùng): số ván, cap, depth/beam, lịch trâu (20 -> 4 từ hiệp 300), bậc năng lượng, FILE LUẬT game (engine)...  Ván mô phỏng chạy nền, đa nhân; bấm Dừng để hủy.
MẶC ĐỊNH CHUNG: thông số chốt (vd bull_cell=24) tự áp lên MỌI cấu hình khi chạy, lưu ở animal_defaults.json; cấu hình nào tự đặt khóa đó thì đè lên. Chọn 1 dòng trong bảng rồi bấm "★ Đặt làm mặc định" để chốt, sau đó test tiếp thông số khác trên nền mới.
FILE BOT: bấm "Thêm file…" để chọn các bản animal_bot.py khác (bản cũ, bản đang sửa...). Mỗi file chạy bằng logic/trọng số của chính nó trên CÙNG luật game và CÙNG seed nên so sánh công bằng.
"""
from __future__ import annotations

import os
import queue
import threading
import time
import traceback
from multiprocessing import Pool, cpu_count, freeze_support
from types import SimpleNamespace
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import animal_tune as T

MONO = ("Consolas", 9) if os.name == "nt" else ("DejaVu Sans Mono", 9)
TREE_COLS = [("label", "Cấu hình", 130, "w"), ("params", "Thông số đang dùng (đã gồm mặc định chung)", 230, "w"), ("mean", "Hiệp TB", 68, "e"), ("se", "±SE", 48, "e"),
             ("median", "Trung vị", 68, "e"), ("r300", "≥300", 52, "center"), ("cap", "Tới cap", 64, "center"), ("bull", "Trâu thừa", 72, "e"),
             ("used", "Kỹ năng", 64, "e"), ("delta", "Δ so với mốc ± SE", 150, "e"), ("wl", "Thắng/Thua", 84, "center")]
CE_PARAMS = ["bull_cell", "row_fill", "hole", "height", "danger", "fit", "points", "bull_sq", "bull_rows", "shrink"]
CE_DEFAULT_ON = {"bull_cell", "row_fill", "hole", "height", "danger", "fit", "bull_sq", "bull_rows", "shrink"}
HELP = {"bull_cell": "phạt mỗi ô trâu", "row_fill": "thưởng hàng gần đầy", "hole": "phạt ô trống dưới thanh", "height": "phạt độ cao", "danger": "phạt chạm sát hàng 0",
        "fit": "thưởng thanh vừa khít", "points": "hệ số điểm ăn (không nên chỉnh)", "bull_sq": "phạt độ dài trâu² (trâu dài nặng hơn)", "bull_rows": "phạt số hàng có trâu",
        "shrink": "thưởng mỗi ô trâu rút trong 1 nước"}


def make_tree(parent, height):
    fr = ttk.Frame(parent)
    tree = ttk.Treeview(fr, columns=[c[0] for c in TREE_COLS], show="headings", height=height)
    for key, title, w, anc in TREE_COLS:
        tree.heading(key, text=title)
        tree.column(key, width=w, anchor=anc, stretch=(key == "params"))
    sb = ttk.Scrollbar(fr, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    tree.tag_configure("good", background="#d6f0d0")
    tree.tag_configure("bad", background="#f6d3d3")
    return fr, tree


def fill_tree(tree, rows):
    tree.delete(*tree.get_children())
    for i, r in enumerate(rows):
        if r["dm"] is None:
            delta, wl, tag = "(mốc so sánh)", "-", ""
        else:
            delta = f"{r['dm']:+.1f} ± {r['dse']:.1f}" + ("  **" if r["sig"] else "")
            wl = f"{r['win']}/{r['loss']}"
            tag = "good" if r["sig"] > 0 else "bad" if r["sig"] < 0 else ""
        tree.insert("", "end", iid=str(i), tags=(tag,), values=(r["label"], r["params"], f"{r['mean']:.1f}", f"{r['se']:.1f}", f"{r['median']:.0f}", f"{r['r300']}/{r['n']}",
                                                    f"{r['rcap']}/{r['n']}", f"{r['bull']:.1f}", f"{r['used']:.1f}", delta, wl))


class App:
    def __init__(self, root):
        self.root = root
        root.title("Animal Bot - Thử cấu hình trên game giả")
        root.geometry("1200x940")
        root.minsize(980, 700)
        self.q = queue.Queue()
        self.stop_ev = threading.Event()
        self.thread = None
        self.t0 = 0.0
        self.last = None            # (cfgs, res, seeds) của lần so sánh gần nhất, để lưu CSV
        self.hist = []
        self.ce_out = None
        self.v = {}
        self._build_common()
        self._build_defaults()
        self._build_bottom()
        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(4, 0))
        self._build_compare()
        self._build_tune()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(100, self.poll)

    # ------------------------------------------------------------ giao diện
    def _field(self, parent, key, label, default, col, row=0, width=7, values=None):
        ttk.Label(parent, text=label).grid(row=row, column=col * 2, sticky="e", padx=(10, 2), pady=2)
        var = tk.StringVar(value=str(default))
        self.v[key] = var
        w = ttk.Combobox(parent, textvariable=var, values=values, width=width, state="readonly") if values else ttk.Entry(parent, textvariable=var, width=width)
        w.grid(row=row, column=col * 2 + 1, sticky="w", pady=2)
        return w

    def _build_common(self):
        f = ttk.LabelFrame(self.root, text=" Cài đặt chung ")
        f.pack(fill="x", padx=8, pady=(8, 0))
        self._field(f, "n", "Ván/cấu hình", 24, 0)
        self._field(f, "cap", "Cap (hiệp)", 500, 1)
        self._field(f, "depth", "Depth", 2, 2, width=4)
        self._field(f, "beam", "Beam", 20, 3, width=4)
        self._field(f, "crowd", "Depth đông", 0, 4, width=4)
        self._field(f, "workers", "Số nhân", max(1, cpu_count() - 1), 5, width=4)
        self._field(f, "lens", "Độ dài thú", "real", 0, row=1, width=10, values=list(T.LENS))
        self._field(f, "seed0", "Seed đầu", 1000, 1, row=1)
        self._field(f, "bull_early", "Trâu/hiệp sớm", 20, 2, row=1, width=4)
        self._field(f, "bull_late", "muộn", 4, 3, row=1, width=4)
        self._field(f, "bull_from", "từ hiệp", 300, 4, row=1, width=4)
        self._field(f, "ramp", "giảm dần tới", "", 5, row=1, width=5)
        ttk.Label(f, text="Bậc năng lượng").grid(row=2, column=0, sticky="e", padx=(8, 2), pady=2)
        self.v["ladder"] = tk.StringVar(value="1000,1500,2000,3000,4000,5000,6000,10000")
        ttk.Entry(f, textvariable=self.v["ladder"], width=50).grid(row=2, column=1, columnspan=5, sticky="w", pady=2)
        ttk.Label(f, text="File luật game").grid(row=3, column=0, sticky="e", padx=(10, 2), pady=2)
        self.v["engine"] = tk.StringVar(value="")
        ttk.Entry(f, textvariable=self.v["engine"], width=70).grid(row=3, column=1, columnspan=8, sticky="w", pady=2)
        ttk.Button(f, text="Chọn…", width=7, command=self.pick_engine).grid(row=3, column=9, sticky="w", padx=4)
        ttk.Label(f, text="Depth đông = depth khi bàn đông (0 = tắt). Giảm dần tới: trống = đổi đột ngột. File luật game: trống = animal_bot.py cùng thư mục. ~10-30 giây/ván 500 hiệp/nhân.", foreground="#666").grid(row=4, column=0, columnspan=12, sticky="w", padx=8, pady=(0, 4))

    def _build_defaults(self):
        f = ttk.LabelFrame(self.root, text=" Mặc định chung — tự áp lên MỌI cấu hình (lưu trong animal_defaults.json) ")
        f.pack(fill="x", padx=8, pady=(6, 0))
        self.v["defaults"] = tk.StringVar(value=T.defaults_string(T.load_defaults()))
        ttk.Label(f, text="Thông số:").pack(side="left", padx=(8, 2))
        e = ttk.Entry(f, textvariable=self.v["defaults"], width=40)
        e.pack(side="left", pady=4)
        e.bind("<Return>", lambda ev: self.apply_defaults())
        ttk.Button(f, text="Áp dụng", command=self.apply_defaults).pack(side="left", padx=4)
        ttk.Button(f, text="Về gốc", command=self.clear_defaults).pack(side="left")
        self.baseline_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Luôn có dòng mốc", variable=self.baseline_var).pack(side="left", padx=(12, 0))
        self.defbots_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Áp cả cho file bot", variable=self.defbots_var).pack(side="left", padx=(8, 0))
        ttk.Button(f, text="Xem đầy đủ…", command=self.show_effective).pack(side="left", padx=(12, 0))
        ttk.Label(f, text="vd: bull_cell=24,skill=K", foreground="#666").pack(side="left", padx=8)

    def current_defaults(self, save=True):
        d = T.parse_defaults_string(self.v["defaults"].get())      # ValueError nếu sai
        if save:
            T.save_defaults(d)
        self.v["defaults"].set(T.defaults_string(d))
        return d

    def apply_defaults(self):
        try:
            d = self.current_defaults()
        except ValueError as e:
            messagebox.showerror("Mặc định chung", str(e))
            return
        self.status.set("Mặc định chung: " + (T.defaults_string(d) or "(trọng số gốc của bot)"))

    def clear_defaults(self):
        self.v["defaults"].set("")
        self.apply_defaults()

    def set_defaults_from_cfg(self, cfg):
        d = T.extract_defaults(cfg)
        if not d:
            messagebox.showinfo("Mặc định chung", "Dòng này không có thông số nào khác trọng số gốc của bot nên không có gì để chốt.")
            return
        notes = []
        if cfg.get("bot"):
            notes.append("file bot không thuộc mặc định chung")
        try:
            if cfg.get("depth") and cfg["depth"] != int(self.v["depth"].get()) or cfg.get("beam") and cfg["beam"] != int(self.v["beam"].get()):
                notes.append(f"depth/beam của dòng này ({cfg.get('depth')}/{cfg.get('beam')}) khác Cài đặt chung - chưa đổi")
        except ValueError:
            pass
        self.v["defaults"].set(T.defaults_string(d))
        self.apply_defaults()
        messagebox.showinfo("Đã chốt mặc định chung", f"Mặc định chung = {T.defaults_string(d)}\n\nTừ giờ mọi cấu hình đều chạy trên nền này (cấu hình nào tự đặt khóa đó thì đè lên). "
                            "Chọn thêm cấu hình khác rồi bấm Chạy để test tiếp." + ("\n\nLưu ý: " + "; ".join(notes) if notes else ""))

    def summary_text(self, rows):
        """Dòng tóm tắt: mốc đang dùng thông số gì, có dòng nào hơn mốc ĐÁNG TIN (**) không."""
        base = rows[0]
        t = f"Mốc (dòng đầu) = {base['label']} [{base['params']}] → TB {base['mean']:.1f} hiệp.  "
        others = rows[1:]
        if not others:
            return t
        better = [r for r in others if r["sig"] > 0]
        worse = [r for r in others if r["sig"] < 0]
        if better:
            best = max(better, key=lambda r: r["mean"])
            t += f"Hơn mốc đáng tin: {best['label']} [{best['params']}] → TB {best['mean']:.1f} (Δ {best['dm']:+.1f} ± {best['dse']:.1f} **). Chọn dòng đó rồi bấm ★ để chốt làm mặc định."
        else:
            t += "Chưa có cấu hình nào hơn mốc một cách đáng tin (không có **) → nên giữ nguyên mặc định chung."
            top = max(others, key=lambda r: r["mean"])
            if top["mean"] > base["mean"]:
                t += f" Cao nhất nhưng chưa đáng tin: {top['label']} [{top['params']}] TB {top['mean']:.1f} (Δ {top['dm']:+.1f} ± {top['dse']:.1f}) - thử thêm ván."
        if worse:
            t += " Kém mốc rõ rệt: " + ", ".join(r["label"] for r in worse) + "."
        return t

    def show_effective(self):
        """Bảng đầy đủ mọi trọng số: giá trị gốc của bot, giá trị đang dùng (sau mặc định chung), ý nghĩa."""
        try:
            d = self.current_defaults(save=False)
        except ValueError as e:
            messagebox.showerror("Mặc định chung", str(e))
            return
        dw = T.ab.Weights()
        w = d.get("w", {})
        win = tk.Toplevel(self.root)
        win.title("Thông số đang dùng (mặc định chung + trọng số gốc của bot)")
        win.geometry("760x430")
        cols = [("k", "Thông số", 110), ("orig", "Gốc của bot", 90), ("cur", "Đang dùng", 90), ("flag", "", 70), ("help", "Ý nghĩa", 380)]
        tv = ttk.Treeview(win, columns=[c[0] for c in cols], show="headings", height=16)
        for k, t_, wd in cols:
            tv.heading(k, text=t_)
            tv.column(k, width=wd, anchor="w" if k in ("k", "help") else "e")
        tv.tag_configure("chg", background="#fff1c7")
        for name in ("row_fill", "hole", "height", "danger", "fit", "points", "bull_cell"):
            o, c = getattr(dw, name), w.get(name, getattr(dw, name))
            tv.insert("", "end", tags=("chg",) if c != o else (), values=(name, f"{o:g}", f"{c:g}", "đã đổi" if c != o else "", HELP.get(name, "")))
        for name in ("bull_sq", "bull_rows", "shrink"):
            c = d.get(name, 0.0)
            tv.insert("", "end", tags=("chg",) if c else (), values=(name, "0 (tắt)", f"{c:g}" if c else "0 (tắt)", "đã đổi" if c else "", HELP.get(name, "")))
        tv.insert("", "end", tags=("chg",) if d.get("skill") else (), values=("skill", "(không)", d.get("skill") or "(không)", "đã đổi" if d.get("skill") else "", "loài dùng kỹ năng: K Gấu, Y Sư tử, P Hươu, B Voi, W Ngựa vằn, O Đà điểu"))
        bf = d.get("bear_from")
        tv.insert("", "end", tags=("chg",) if bf is not None else (), values=("bear_from", "(tắt)", bf if bf is not None else "(tắt)", "đã đổi" if bf is not None else "", "dùng Gấu chủ động từ hiệp này"))
        tv.insert("", "end", values=("bear_bulls", "8", d.get("bear_bulls", 8), "", "ngưỡng ô trâu thừa để dùng Gấu chủ động"))
        tv.pack(fill="both", expand=True, padx=8, pady=8)
        ttk.Label(win, foreground="#666", text="Dòng tô vàng = đã đổi khác trọng số gốc của bot. Depth/beam/lịch trâu nằm ở Cài đặt chung.").pack(anchor="w", padx=8, pady=(0, 8))

    def promote_selected(self):
        sel = self.tree.selection()
        if not sel or not self.last:
            messagebox.showinfo("Mặc định chung", "Chọn 1 dòng trong bảng kết quả trước.")
            return
        self.set_defaults_from_cfg(self.last[0][int(sel[0])])

    def promote_cand(self):
        c = self._cand()
        if c:
            self.set_defaults_from_cfg(c)

    def _build_compare(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  So sánh cấu hình  ")
        ttk.Label(tab, foreground="#444", wraplength=1100, justify="left",
                  text="Chọn các cấu hình có sẵn và/hoặc tự viết (mỗi dòng 1 cấu hình, vd: bull_cell=24,skill=K,bear_from=280). Mọi cấu hình chạy trên 'Mặc định chung' ở trên; khóa nào cấu hình tự đặt thì đè lên. Dòng ĐẦU TIÊN là mốc so sánh. "
                       "Chỉ tin chênh lệch có dấu ** (lớn hơn 2 lần sai số chuẩn); ít ván thì kết quả rất nhiễu.").pack(anchor="w", padx=8, pady=(6, 2))
        top = ttk.Frame(tab)
        top.pack(fill="x", padx=8)
        left = ttk.LabelFrame(top, text=" Cấu hình có sẵn (Ctrl/Shift để chọn nhiều) ")
        left.pack(side="left", fill="both", expand=True)
        self.lb = tk.Listbox(left, selectmode="extended", height=8, exportselection=False, font=MONO, width=38)
        for k, d in T.PRESETS.items():
            self.lb.insert("end", f"{k:18s} {'= mặc định chung' if k == 'base' else T.cfg_string(T.make_cfg(d))}")
        for i, k in enumerate(T.PRESETS):
            if k in ("base", "bull24", "sq3", "shrink10", "K", "K_bear280"):
                self.lb.selection_set(i)
        sb = ttk.Scrollbar(left, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb.set)
        self.lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        mid = ttk.LabelFrame(top, text=" File bot (.py) để so sánh ")
        mid.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.bots = [os.path.abspath(T.ab.__file__)]           # animal_bot.py mặc định luôn có sẵn trong danh sách
        self.bl = tk.Listbox(mid, selectmode="extended", height=6, exportselection=False, font=MONO, width=30)
        sbb = ttk.Scrollbar(mid, orient="vertical", command=self.bl.yview)
        self.bl.configure(yscrollcommand=sbb.set)
        self.bl.pack(side="top", fill="both", expand=True, padx=(4, 0), pady=(4, 2))
        self._refresh_bots()
        bb = ttk.Frame(mid)
        bb.pack(fill="x", padx=4)
        ttk.Button(bb, text="Thêm file…", command=self.add_bots).pack(side="left")
        ttk.Button(bb, text="Bỏ file chọn", command=self.remove_bots).pack(side="left", padx=4)
        ob = ttk.Frame(mid)
        ob.pack(fill="x", padx=4, pady=(4, 2))
        self.cross_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ob, text="Mỗi file × mỗi cấu hình đã chọn", variable=self.cross_var).pack(anchor="w")
        kb = ttk.Frame(ob)
        kb.pack(anchor="w")
        ttk.Label(kb, text="Kỹ năng cho file bot:").pack(side="left")
        self.v["bot_skill"] = tk.StringVar(value="")
        ttk.Entry(kb, textvariable=self.v["bot_skill"], width=6).pack(side="left", padx=4)
        ttk.Label(kb, text="(K, KYPB; trống = không)", foreground="#666").pack(side="left")
        right = ttk.LabelFrame(top, text=" Cấu hình tự viết (mỗi dòng 1 cấu hình) ")
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.custom = tk.Text(right, height=8, width=30, font=MONO)
        self.custom.pack(fill="both", expand=True, padx=4, pady=4)
        ttk.Label(right, foreground="#666", wraplength=330, justify="left",
                  text="Khóa: bull_cell, row_fill, hole, height, danger, fit, bull_sq, bull_rows, shrink, depth, beam, crowd_depth, "
                       "skill (K / KYPB), bear_from, bear_bulls, label, bot (đường dẫn file bot, không có dấu phẩy)").pack(anchor="w", padx=4, pady=(0, 4))
        bt = ttk.Frame(tab)
        bt.pack(fill="x", padx=8, pady=6)
        self.btn_run = ttk.Button(bt, text="▶ Chạy so sánh", command=self.run_compare)
        self.btn_run.pack(side="left")
        self.btn_stop = ttk.Button(bt, text="■ Dừng", command=self.stop, state="disabled")
        self.btn_stop.pack(side="left", padx=6)
        ttk.Button(bt, text="Chọn hết", command=lambda: self.lb.selection_set(0, "end")).pack(side="left", padx=(18, 0))
        ttk.Button(bt, text="Bỏ chọn", command=lambda: self.lb.selection_clear(0, "end")).pack(side="left", padx=6)
        self.btn_csv = ttk.Button(bt, text="Lưu CSV…", command=self.save_csv, state="disabled")
        self.btn_csv.pack(side="right")
        ttk.Button(bt, text="★ Đặt dòng chọn làm mặc định chung", command=self.promote_selected).pack(side="right", padx=8)
        self.sumvar = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.sumvar, foreground="#1a3d7c", wraplength=1100, justify="left").pack(anchor="w", padx=8, pady=(0, 3))
        fr, self.tree = make_tree(tab, 4)
        fr.pack(fill="both", expand=True, padx=8, pady=(0, 6))

    def _build_tune(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="  Chỉnh trọng số (CE)  ")
        ttk.Label(tab, foreground="#444", wraplength=1100, justify="left",
                  text="Cross-Entropy: mỗi thế hệ thử nhiều bộ trọng số ngẫu nhiên quanh bộ hiện tại (cùng seed), giữ nhóm tốt nhất rồi thu hẹp dần. "
                       "Cuối cùng kiểm lại bằng ván MỚI. Độ thích nghi = hiệp sống TB − hệ số × ô trâu thừa cuối ván. Nên dùng depth 2, beam 15 cho nhanh, rồi kiểm lại ở tab So sánh bằng depth 3.").pack(anchor="w", padx=8, pady=(6, 2))
        top = ttk.Frame(tab)
        top.pack(fill="x", padx=8)
        pf = ttk.LabelFrame(top, text=" Tham số được chỉnh ")
        pf.pack(side="left", fill="y")
        self.pvars = {}
        for i, k in enumerate(CE_PARAMS):
            var = tk.BooleanVar(value=k in CE_DEFAULT_ON)
            self.pvars[k] = var
            ttk.Checkbutton(pf, text=f"{k}  ({HELP[k]})", variable=var).grid(row=i % 5, column=i // 5, sticky="w", padx=8, pady=1)
        sf = ttk.LabelFrame(top, text=" Thiết lập CE ")
        sf.pack(side="left", fill="both", expand=True, padx=8)
        self._field(sf, "pop", "Quần thể", 16, 0, width=5)
        self._field(sf, "games", "Ván/ứng viên", 8, 1, width=5)
        self._field(sf, "gens", "Số thế hệ", 10, 2, width=5)
        self._field(sf, "elite", "Tỉ lệ elite", 0.25, 0, row=1, width=5)
        self._field(sf, "alpha", "Làm mượt", 0.7, 1, row=1, width=5)
        self._field(sf, "fit_bull", "Hệ số trâu", 0.3, 2, row=1, width=5)
        self._field(sf, "verify", "Ván kiểm lại", 24, 0, row=2, width=5)
        ttk.Label(sf, text="Xuất phát từ").grid(row=2, column=2, sticky="e", padx=(8, 2))
        self.v["basecfg"] = tk.StringVar(value="")
        ttk.Entry(sf, textvariable=self.v["basecfg"], width=22).grid(row=2, column=3, sticky="w")
        ttk.Button(sf, text="Chọn file bot…", command=self.pick_tune_bot).grid(row=2, column=4, columnspan=2, sticky="w", padx=4)
        ttk.Label(sf, text=" ").grid(row=0, column=6, padx=6)
        bt = ttk.Frame(tab)
        bt.pack(fill="x", padx=8, pady=6)
        self.btn_run2 = ttk.Button(bt, text="▶ Chạy chỉnh trọng số", command=self.run_tune)
        self.btn_run2.pack(side="left")
        self.btn_stop2 = ttk.Button(bt, text="■ Dừng", command=self.stop, state="disabled")
        self.btn_stop2.pack(side="left", padx=6)
        self.chart = tk.Canvas(tab, height=125, background="white", highlightthickness=1, highlightbackground="#bbb")
        self.chart.pack(fill="x", padx=8)
        self.chart.bind("<Configure>", lambda e: self.draw_chart())
        fr, self.tree2 = make_tree(tab, 3)
        fr.pack(fill="x", padx=8, pady=6)
        rf = ttk.Frame(bt)
        rf.pack(side="right")
        ttk.Label(rf, text="Kết quả:").pack(side="left")
        self.cand_var = tk.StringVar()
        self.cand_cb = ttk.Combobox(rf, textvariable=self.cand_var, state="readonly", width=20)
        self.cand_cb.pack(side="left", padx=6)
        self.btn_cp1 = ttk.Button(rf, text="Copy --cfg", command=lambda: self.copy_cand("cfg"), state="disabled")
        self.btn_cp1.pack(side="left")
        self.btn_cp2 = ttk.Button(rf, text="Copy Weights(...)", command=lambda: self.copy_cand("w"), state="disabled")
        self.btn_cp2.pack(side="left", padx=6)
        self.btn_send = ttk.Button(rf, text="→ Thử ở tab So sánh", command=self.send_to_compare, state="disabled")
        self.btn_send.pack(side="left")
        self.btn_def = ttk.Button(rf, text="★ Đặt làm mặc định", command=self.promote_cand, state="disabled")
        self.btn_def.pack(side="left", padx=6)

    def _build_bottom(self):
        f = ttk.Frame(self.root)
        f.pack(side="bottom", fill="x", padx=8, pady=6)
        pr = ttk.Frame(f)
        pr.pack(fill="x")
        self.bar = ttk.Progressbar(pr, mode="determinate")
        self.bar.pack(side="left", fill="x", expand=True)
        self.status = tk.StringVar(value="Sẵn sàng.")
        ttk.Label(pr, textvariable=self.status, width=44, anchor="e").pack(side="left", padx=6)
        ttk.Button(pr, text="Xóa log", command=lambda: self.log.delete("1.0", "end")).pack(side="left")
        self.log = ScrolledText(f, height=8, font=MONO)
        self.log.pack(fill="x", pady=(4, 0))

    # ------------------------------------------------------------ đọc thiết lập
    def _i(self, key, name, lo=0):
        try:
            x = int(self.v[key].get())
        except ValueError:
            raise ValueError(f"'{name}' phải là số nguyên")
        if x < lo:
            raise ValueError(f"'{name}' phải >= {lo}")
        return x

    def _f(self, key, name, lo=0.0, hi=None):
        try:
            x = float(self.v[key].get())
        except ValueError:
            raise ValueError(f"'{name}' phải là số")
        if x < lo or (hi is not None and x > hi):
            raise ValueError(f"'{name}' ngoài khoảng cho phép")
        return x

    def common(self):
        ramp = self.v["ramp"].get().strip()
        lad = self.v["ladder"].get().strip()
        try:
            [int(x) for x in lad.split(",") if x.strip()]
        except ValueError:
            raise ValueError("'Bậc năng lượng' phải là dãy số cách nhau bởi dấu phẩy")
        return SimpleNamespace(n=self._i("n", "Ván / cấu hình", 1), cap=self._i("cap", "Cap", 10), depth=self._i("depth", "Depth", 1), beam=self._i("beam", "Beam", 1),
                               crowd_depth=self._i("crowd", "Depth khi đông"), workers=self._i("workers", "Số nhân", 1), lens=self.v["lens"].get(),
                               seed0=self._i("seed0", "Seed đầu"), bull_early=self._i("bull_early", "Trâu sớm", 1), bull_late=self._i("bull_late", "Trâu muộn", 1),
                               bull_from=self._i("bull_from", "Từ hiệp"), bull_ramp_to=int(ramp) if ramp else None, ladder=lad,
                               engine=self.v["engine"].get().strip())

    # ------------------------------------------------------------ chạy nền
    def set_running(self, on):
        st_run = "disabled" if on else "normal"
        st_stop = "normal" if on else "disabled"
        for b in (self.btn_run, self.btn_run2):
            b.configure(state=st_run)
        for b in (self.btn_stop, self.btn_stop2):
            b.configure(state=st_stop)

    def start(self, kind, opts, cfgs=None):
        self.stop_ev.clear()
        self.set_running(True)
        self.t0 = time.time()
        self.bar["value"] = 0
        self.status.set("Đang khởi động các tiến trình…")
        self.thread = threading.Thread(target=self._worker, args=(kind, opts, cfgs), daemon=True)
        self.thread.start()

    def _worker(self, kind, opts, cfgs):
        pool = None
        try:
            pool = Pool(opts.workers)
            log = lambda s: self.q.put(("log", s))
            prog = lambda d, t: self.q.put(("progress", d, t))
            if kind == "compare":
                res, seeds, rows = T.run_compare(opts, pool, cfgs, log, prog, self.stop_ev.is_set)
                self.q.put(("compare_done", cfgs, res, seeds, rows))
            else:
                out = T.run_ce(opts, pool, log, prog, self.stop_ev.is_set, on_gen=lambda h: self.q.put(("gen", h)))
                self.q.put(("tune_done", out))
        except T.Stopped:
            self.q.put(("log", "(đã dừng)"))
        except (ValueError, SystemExit) as e:
            self.q.put(("error", str(e)))
        except Exception:
            self.q.put(("log", "LỖI:\n" + traceback.format_exc()))
        finally:
            if pool is not None:
                pool.terminate()
                pool.join()
            self.q.put(("finished",))

    def stop(self):
        self.stop_ev.set()
        self.status.set("Đang dừng…")

    def poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                k = m[0]
                if k == "log":
                    self.log.insert("end", m[1] + "\n")
                    self.log.see("end")
                elif k == "progress":
                    d, t = m[1], m[2]
                    self.bar["maximum"], self.bar["value"] = t, d
                    el = time.time() - self.t0
                    eta = f" | còn ~{el * (t - d) / d / 60:.1f} phút" if d > 0 and t > d else ""
                    self.status.set(f"{d:.0f}/{t} | đã chạy {el:.0f}s{eta}")
                elif k == "compare_done":
                    _, cfgs, res, seeds, rows = m
                    self.last = (cfgs, res, seeds)
                    fill_tree(self.tree, rows)
                    self.btn_csv.configure(state="normal")
                    self.sumvar.set(self.summary_text(rows))
                elif k == "gen":
                    self.hist.append(m[1])
                    self.draw_chart()
                elif k == "tune_done":
                    self.ce_out = m[1]
                    fill_tree(self.tree2, m[1]["rows"])
                    names = list(m[1]["cands"])
                    self.cand_cb.configure(values=names)
                    self.cand_var.set(names[0])
                    for b in (self.btn_cp1, self.btn_cp2, self.btn_send, self.btn_def):
                        b.configure(state="normal")
                elif k == "error":
                    self.log.insert("end", "LỖI: " + m[1] + "\n")
                    self.log.see("end")
                    messagebox.showerror("Không chạy được", m[1])
                elif k == "finished":
                    self.set_running(False)
                    self.status.set(f"Xong sau {time.time() - self.t0:.0f}s." if not self.stop_ev.is_set() else "Đã dừng.")
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    # ------------------------------------------------------------ hành động
    def run_compare(self):
        try:
            o = self.common()
            names = [list(T.PRESETS)[i] for i in self.lb.curselection()]
            lines = [x for x in self.custom.get("1.0", "end").splitlines() if x.strip()]
            bots = [self.bots[i] for i in self.bl.curselection()]
            bot_skill = self.v["bot_skill"].get().strip().upper()
            if bot_skill and any(c not in "KYPBWO" for c in bot_skill):
                raise ValueError("'Kỹ năng cho file bot' chỉ gồm các chữ K, Y, P, B, W, O")
            o.defaults = self.current_defaults()
            cfgs = T.build_cfgs(names, lines, None, o.depth, o.beam, o.crowd_depth, bots, self.cross_var.get(), bot_skill,
                                defaults=o.defaults, defaults_bots=self.defbots_var.get(), add_baseline=self.baseline_var.get())
            if len(cfgs) < 1:
                raise ValueError("Chưa chọn cấu hình nào.")
        except (Exception, SystemExit) as e:
            messagebox.showerror("Thiếu/sai thiết lập", str(e))
            return
        est = len(cfgs) * o.n * 20 * o.cap / 500 / o.workers / 60
        self.log.insert("end", f"\n=== SO SÁNH: {len(cfgs)} cấu hình x {o.n} ván (ước tính thô ~{est:.0f} phút) ===\nmặc định chung: {T.defaults_string(o.defaults) or '(không - trọng số gốc của bot)'}\n")
        self.start("compare", o, cfgs)

    def run_tune(self):
        try:
            o = self.common()
            params = [k for k, v in self.pvars.items() if v.get()]
            if not params:
                raise ValueError("Chọn ít nhất 1 tham số để chỉnh.")
            o.params = ",".join(params)
            o.pop, o.games, o.gens = self._i("pop", "Quần thể", 4), self._i("games", "Ván / ứng viên", 1), self._i("gens", "Số thế hệ", 1)
            o.elite, o.alpha, o.fit_bull = self._f("elite", "Tỉ lệ elite", 0.05, 0.9), self._f("alpha", "Làm mượt", 0.05, 1.0), self._f("fit_bull", "Hệ số trâu thừa", 0.0)
            o.verify = self._i("verify", "Ván kiểm lại")
            b = self.v["basecfg"].get().strip()
            o.cfg = [b] if b else []
            if b:
                T.parse_cfg_string(b)
            o.out = os.path.join(os.getcwd(), "tune_log.json")
            o.defaults = self.current_defaults()
        except SystemExit as e:
            messagebox.showerror("Thiếu/sai thiết lập", str(e))
            return
        except Exception as e:
            messagebox.showerror("Thiếu/sai thiết lập", str(e))
            return
        self.hist = []
        self.draw_chart()
        est = o.pop * o.games * o.gens * 20 * o.cap / 500 / o.workers / 60
        self.log.insert("end", f"\n=== CHỈNH TRỌNG SỐ CE (ước tính thô ~{est:.0f} phút) ===\n")
        self.start("tune", o)

    def _bot_text(self, p):
        tag = "  (mặc định)" if os.path.abspath(p) == os.path.abspath(T.ab.__file__) else ""
        return f"{os.path.basename(p)}{tag}  —  {os.path.dirname(p)}"

    def _refresh_bots(self, select=()):
        sel = set(self.bl.curselection()) | set(select)
        self.bl.delete(0, "end")
        for i, p in enumerate(self.bots):
            self.bl.insert("end", self._bot_text(p))
            if i in sel:
                self.bl.selection_set(i)

    def _ask_dir(self):
        return getattr(self, "last_dir", None) or os.path.dirname(os.path.abspath(T.ab.__file__))

    def add_bots(self):
        files = filedialog.askopenfilenames(title="Chọn file bot (.py)", initialdir=self._ask_dir(), filetypes=[("Python", "*.py"), ("Tất cả", "*.*")])
        new = []
        for f in files:
            f = os.path.abspath(f)
            self.last_dir = os.path.dirname(f)
            if f not in self.bots:
                self.bots.append(f)
            new.append(self.bots.index(f))
        self._refresh_bots(select=new)

    def remove_bots(self):
        keep = [p for i, p in enumerate(self.bots) if i not in set(self.bl.curselection())]
        self.bots = keep
        self.bl.selection_clear(0, "end")
        self._refresh_bots()

    def pick_engine(self):
        f = filedialog.askopenfilename(title="Chọn file cung cấp LUẬT game", initialdir=self._ask_dir(), filetypes=[("Python", "*.py"), ("Tất cả", "*.*")])
        if f:
            self.v["engine"].set(os.path.abspath(f))

    def pick_tune_bot(self):
        f = filedialog.askopenfilename(title="Chọn file bot làm điểm xuất phát", initialdir=self._ask_dir(), filetypes=[("Python", "*.py"), ("Tất cả", "*.*")])
        if f:
            rest = [x for x in self.v["basecfg"].get().split(",") if x.strip() and not x.strip().startswith("bot=")]
            self.v["basecfg"].set(",".join(["bot=" + os.path.abspath(f)] + rest))

    def save_csv(self):
        if not self.last:
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="so_sanh.csv")
        if p:
            T.write_csv(p, *self.last)
            self.log.insert("end", f"đã ghi {p}\n")

    def _cand(self):
        return self.ce_out["cands"][self.cand_var.get()] if self.ce_out else None

    def copy_cand(self, what):
        c = self._cand()
        if not c:
            return
        if what == "cfg":
            txt = T.cfg_string(c)
        else:
            txt = "replace(Weights(), " + ", ".join(f"{k}={v:.3f}" for k, v in c["w"].items()) + ")"
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self.status.set("Đã copy: " + txt[:60])
        extra = {k: round(c[k], 3) for k in T.EXTRA if c.get(k)}
        if what == "w" and extra:
            messagebox.showinfo("Lưu ý", f"Cấu hình này còn dùng đặc trưng phụ {extra} - chưa có trong animal_bot.py, "
                                         "cần thêm vào evaluate_items/step_state nếu muốn dùng thật.")

    def send_to_compare(self):
        c = self._cand()
        if c:
            self.custom.insert("end", T.cfg_string(c) + f",label=CE_{self.cand_var.get().replace(' ', '_')}\n")
            self.nb.select(0)

    def draw_chart(self):
        c = self.chart
        c.delete("all")
        w, h = max(c.winfo_width(), 300), max(c.winfo_height(), 120)
        pad = 34
        if not self.hist:
            c.create_text(w // 2, h // 2, text="Đồ thị độ thích nghi theo thế hệ sẽ hiện ở đây", fill="#888")
            return
        series = [("tốt nhất", "best", "#2a9d3a"), ("trung bình", "mean", "#888888"), ("tâm cũ", "center_fit", "#2b6cd4")]
        vals = [x[k] for x in self.hist for _, k, _ in series]
        lo, hi = min(vals), max(vals)
        if hi - lo < 1:
            hi = lo + 1
        n = len(self.hist)
        px = lambda i: pad + (w - 2 * pad) * (i / (n - 1) if n > 1 else 0.5)
        py = lambda v: h - pad + 8 - (h - 2 * pad) * ((v - lo) / (hi - lo))
        c.create_line(pad, 6, pad, h - pad + 8, fill="#ccc")
        c.create_text(pad - 4, 10, text=f"{hi:.0f}", anchor="e", fill="#555", font=("", 8))
        c.create_text(pad - 4, h - pad + 8, text=f"{lo:.0f}", anchor="e", fill="#555", font=("", 8))
        for i in range(n):
            c.create_text(px(i), h - pad + 20, text=str(i + 1), fill="#555", font=("", 8))
        for j, (name, key, col) in enumerate(series):
            pts = [(px(i), py(x[key])) for i, x in enumerate(self.hist)]
            if len(pts) > 1:
                c.create_line(*[v for p in pts for v in p], fill=col, width=2)
            for x_, y_ in pts:
                c.create_oval(x_ - 3, y_ - 3, x_ + 3, y_ + 3, fill=col, outline=col)
            c.create_text(w - 170 + 0, 10 + 13 * j, text=f"● {name}", anchor="w", fill=col, font=("", 9))

    def on_close(self):
        self.stop_ev.set()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista" if os.name == "nt" else "clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    freeze_support()
    main()

"""
dashboard_shop.py — "🛍 Cài Đặt Shop": bảng đặt SỐ LƯỢNG MUA cho từng biến, từng shop.

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành 1
Mixin (ShopQtyMixin) - mọi "self." trỏ vào cùng 1 instance DashboardApp.

CÁCH HOẠT ĐỘNG
- Danh sách shop + vật phẩm được ĐỌC TỰ ĐỘNG từ kịch bản `tasks/cai_dat_shop.json`
  (Hoạt Động có id "cai_dat_shop", cũng là kịch bản mà nút "🛍 Cài Đặt Shop" chạy):
  mỗi NHÓM (group_start) ngoài cùng = 1 shop, mỗi bước IF Biến (`if_var`) trong
  nhóm = 1 vật phẩm với biến tương ứng. Thêm/bớt vật phẩm trong kịch bản thì bảng
  này tự cập nhật, KHÔNG cần sửa code. Tên vật phẩm lấy trong ngoặc ở cuối ghi chú
  của bước IF, vd "Nếu tc_sach > 0  (Bí Quyết Làm Giàu)".
- ICON vật phẩm: lấy ảnh mẫu của bước ảnh ĐẦU TIÊN sau IF Biến (chính là icon món trong
  kịch bản) trong thư mục templates/, thu nhỏ 40px. Thiếu file ảnh -> hiện dấu "?".
- Số lượng: 0 = BỎ QUA (click 0 lần), 1 = mua 1 lần, N = mua N lần
  (kịch bản đặt Sửa Lặp = `{biến}-1` cho nút "+", xem logic_engine.py).
- Bấm Lưu: ghi số lượng thành GIÁ TRỊ MẶC ĐỊNH (`default`) của biến trong
  "🧩 Quản Lý Biến" (variables_registry.py / variables.json). Biến chưa có thì
  tự tạo mới (kiểu int). Dashboard áp `default` này mỗi lần chạy
  (xem _get_registry_preset_vars() trong dashboard_misc.py). Chỉ đổi `default`,
  KHÔNG đổi tên/nhãn/kiểu của biến đã có.
"""

import os
import re
import json
import tkinter as tk
from tkinter import messagebox

import window_geometry as wg
import variables_registry
import task_registry
from dashboard_theme import *
from dashboard_widgets import RoundedButton, FlowBar, _bind_esc_close, ThemedToplevel

SHOP_TASK_ID = "cai_dat_shop"
SHOP_TASK_FALLBACK_FILE = os.path.join("tasks", "cai_dat_shop.json")
ICON_SIZE = 40  # cạnh icon vật phẩm trong bảng (px)


class ShopQtyMixin:
    # ------------------------------------------------------------------
    # Đọc danh sách shop/vật phẩm từ kịch bản
    # ------------------------------------------------------------------
    def _shop_script_path(self):
        entry = task_registry.find_task(getattr(self, "tasks", []), SHOP_TASK_ID)
        path = entry.get("file_json") if entry else None
        if path and os.path.exists(path):
            return path
        if os.path.exists(SHOP_TASK_FALLBACK_FILE):
            return SHOP_TASK_FALLBACK_FILE
        return None

    @staticmethod
    def _shop_extract_item_name(comment):
        m = re.search(r"\(([^()]+)\)\s*$", comment or "")
        return m.group(1).strip() if m else ""

    def _shop_load_items(self):
        """Trả về (path, [(tên_shop, [(biến, tên_vật_phẩm), ...]), ...], {biến: ảnh mẫu}).
        path=None nếu không tìm thấy kịch bản; danh sách rỗng nếu kịch bản
        không có bước IF Biến nào. {biến: ảnh mẫu} = tên file ảnh trong templates/ của
        bước ảnh ĐẦU TIÊN nằm sau IF Biến đó (chính là icon vật phẩm), dùng để hiện icon."""
        path = self._shop_script_path()
        if not path:
            return None, [], {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                steps = json.load(f)
        except Exception:
            return path, [], {}

        tpl_map = {}
        shops, order = {}, []
        seen_vars = set()

        # Biến NỘI BỘ do chính kịch bản tính ra (đếm ảnh, tăng biến, OCR) -> không
        # phải số lượng người dùng đặt, bỏ qua.
        internal = set()
        for s in steps if isinstance(steps, list) else []:
            if s.get("action") in ("inc_var", "ocr_text") and s.get("var"):
                internal.add(s["var"])
            if s.get("count_var"):
                internal.add(s["count_var"])

        def _add(shop, var, comment):
            if not var or var in seen_vars or var in internal:
                return
            seen_vars.add(var)
            if shop.islower():
                shop = shop.title()
            if shop not in shops:
                shops[shop] = []
                order.append(shop)
            shops[shop].append((var, self._shop_extract_item_name(comment)))

        def _item_template(idx):
            """Ảnh mẫu đầu tiên sau bước if_var ở vị trí idx (dừng ở endif / if_var kế)."""
            for k in range(idx + 1, len(steps)):
                st = steps[k]
                if st.get("action") in ("endif", "if_var"):
                    break
                tpl = st.get("template")
                if not tpl and isinstance(st.get("templates"), list) and st["templates"]:
                    tpl = st["templates"][0]
                    tpl = tpl.get("template") if isinstance(tpl, dict) else tpl
                if isinstance(tpl, str) and tpl:
                    return tpl
            return None

        stack = []
        for idx, s in enumerate(steps if isinstance(steps, list) else []):
            act = s.get("action")
            if act == "group_start":
                stack.append((s.get("comment") or "").strip() or "(không tên)")
                continue
            if act == "group_end":
                if stack:
                    stack.pop()
                continue
            shop = stack[0] if stack else "Khác"
            # Vật phẩm = biến trong IF Biến / Biến Nhập Trước Khi Chạy ...
            if act in ("if_var", "input_var") and s.get("var"):
                _add(shop, s["var"], s.get("comment"))
                if act == "if_var" and s["var"] not in tpl_map:
                    t = _item_template(idx)
                    if t:
                        tpl_map[s["var"]] = t
            # ... hoặc biến dùng trong Sửa Lặp/Delay (vd repeat = {tc_sach}-1) - để
            # bước thêm KHÔNG có IF Biến đi kèm vẫn hiện trong bảng.
            for key in ("repeat", "repeat_ms", "repeat_seconds"):
                for v in re.findall(r"\{([A-Za-z_]\w*)\}", str(s.get(key, ""))):
                    _add(shop, v, s.get("comment"))
        return path, [(name, shops[name]) for name in order], tpl_map

    @staticmethod
    def _shop_parse_qty(text):
        text = str(text).strip()
        return int(text) if re.fullmatch(r"\d+", text) else None

    @staticmethod
    def _shop_default_text(value):
        try:
            return str(max(0, int(float(value))))
        except (TypeError, ValueError):
            return "0"

    # ------------------------------------------------------------------
    # Cửa sổ
    # ------------------------------------------------------------------
    def _open_shop_qty_settings(self, overrides=None):
        """overrides: {biến: chữ số lượng} - giữ lại số đang gõ dở khi Tải lại."""
        existing = getattr(self, "_shop_qty_win", None)
        try:
            if existing is not None and existing.winfo_exists():
                # Đang mở sẵn -> đóng và dựng lại từ kịch bản MỚI NHẤT (giữ số đang gõ).
                if overrides is None and getattr(self, "_shop_qty_get_values", None):
                    overrides = self._shop_qty_get_values()
                existing.destroy()
        except tk.TclError:
            pass
        path, shops, tpl_map = self._shop_load_items()
        if not shops:
            messagebox.showinfo(
                "Cài Đặt Shop",
                "Chưa tìm thấy danh sách mua Shop.\n\n"
                "Cần có kịch bản tasks/cai_dat_shop.json (Hoạt Động 'cai_dat_shop'), "
                "trong đó mỗi shop là 1 NHÓM và mỗi vật phẩm là 1 bước IF Biến "
                "(vd: Nếu tc_sach > 0)."
            )
            return

        registry = {v.get("var"): v for v in variables_registry.load_variables() if v.get("var")}
        qty_vars = {}  # biến -> StringVar (giữ giá trị khi đổi qua lại giữa các shop)
        for _, items in shops:
            for var, _name in items:
                init = (overrides or {}).get(var)
                qty_vars[var] = tk.StringVar(
                    value=init if init is not None else self._shop_default_text(registry.get(var, {}).get("default", 0)))

        win = ThemedToplevel(self.root)
        self._shop_qty_win = win
        win.title("🛍 Cài Đặt Số Lượng Mua Shop")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "shop_qty_settings", default="560x620")
        win.minsize(460, 380)
        wg.autosave(win, "shop_qty_settings")
        _bind_esc_close(win)

        tk.Label(win, text="🛍 Số lượng mua theo từng Shop", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(win, text="0 = bỏ qua (không mua)  ·  1 = mua 1 lần  ·  N = mua N lần.\n"
                           "Bấm Lưu sẽ ghi thành GIÁ TRỊ MẶC ĐỊNH của biến trong 🧩 Quản Lý Biến.",
                 bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9), justify="left"
                 ).pack(anchor="w", padx=14, pady=(0, 6))

        tabbar = FlowBar(win, bg=COL_PANEL, hgap=4, vgap=4)
        tabbar.pack(fill="x", padx=10, pady=(0, 4))

        tools = tk.Frame(win, bg=COL_PANEL)
        tools.pack(fill="x", padx=12, pady=(0, 4))
        lbl_shop = tk.Label(tools, text="", bg=COL_PANEL, fg=COL_ACCENT, font=("Segoe UI", 10, "bold"))
        lbl_shop.pack(side="left")

        outer = tk.Frame(win, bg=COL_PANEL)
        outer.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        canvas = tk.Canvas(outer, bg=COL_PANEL, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=COL_PANEL)
        body_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(body_id, width=e.width))
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        self._shop_qty_get_values = lambda: {v: sv.get() for v, sv in qty_vars.items()}
        # Icon vật phẩm: nạp ảnh mẫu trong templates/, thu nhỏ; giữ tham chiếu để không bị xóa.
        icons = {}
        win._shop_icons = icons

        def _get_icon(var):
            tpl = tpl_map.get(var)
            if not tpl:
                return None
            if tpl in icons:
                return icons[tpl]
            photo = None
            fpath = os.path.join("templates", tpl)
            if os.path.isfile(fpath):
                try:
                    from PIL import Image, ImageTk
                    im = Image.open(fpath).convert("RGBA")
                    im.thumbnail((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(im)
                except Exception:
                    photo = None
            icons[tpl] = photo
            return photo

        state = {"idx": 0}
        tab_btns = []
        entry_widgets = {}  # biến -> Entry (chỉ của shop đang hiển thị)

        def _shop_count(i):
            n = 0
            for var, _ in shops[i][1]:
                q = self._shop_parse_qty(qty_vars[var].get())
                if q:
                    n += 1
            return n

        def _refresh_tabs():
            for i, b in enumerate(tab_btns):
                n = _shop_count(i)
                b.set_text(f"{shops[i][0]} ({n})" if n else shops[i][0])
                b.bg_color = COL_BLUE if i == state["idx"] else "#3a4358"
                b._redraw()

        def _on_change(var):
            e = entry_widgets.get(var)
            if e is not None:
                try:
                    e.config(fg=COL_TEXT if self._shop_parse_qty(qty_vars[var].get()) is not None else COL_RED)
                except tk.TclError:
                    pass
            _refresh_tabs()

        for var, sv in qty_vars.items():
            sv.trace_add("write", lambda *a, v=var: _on_change(v))

        def _step(var, delta):
            q = self._shop_parse_qty(qty_vars[var].get())
            qty_vars[var].set(str(max(0, (q or 0) + delta)))

        def _set_all(value):
            for var, _ in shops[state["idx"]][1]:
                qty_vars[var].set(str(value))

        def _show_shop(i):
            state["idx"] = i
            for w in body.winfo_children():
                w.destroy()
            entry_widgets.clear()
            name, items = shops[i]
            lbl_shop.config(text=f"{name}  -  {len(items)} vật phẩm")
            for r, (var, item_name) in enumerate(items):
                row = tk.Frame(body, bg=COL_PANEL_ALT if r % 2 else COL_PANEL)
                row.pack(fill="x", pady=1)
                icon_box = tk.Frame(row, bg=row.cget("bg"), width=ICON_SIZE + 8, height=ICON_SIZE + 6)
                icon_box.pack(side="left", padx=(6, 0))
                icon_box.pack_propagate(False)
                photo = _get_icon(var)
                if photo is not None:
                    tk.Label(icon_box, image=photo, bg=row.cget("bg")).pack(expand=True)
                else:
                    tk.Label(icon_box, text="?" if tpl_map.get(var) else "", bg=row.cget("bg"),
                             fg=COL_TEXT_MUTED, font=("Segoe UI", 11, "bold")).pack(expand=True)
                tk.Label(row, text=item_name or var, bg=row.cget("bg"), fg=COL_TEXT,
                         font=("Segoe UI", 10), anchor="w").pack(side="left", padx=(4, 6), pady=3)
                tk.Label(row, text=var if item_name else "", bg=row.cget("bg"), fg=COL_TEXT_MUTED,
                         font=("Consolas", 8)).pack(side="left")
                RoundedButton(row, "+", command=lambda v=var: _step(v, 1), bg=COL_GREEN_DARK,
                              container_bg=row.cget("bg"), font=("Segoe UI", 9, "bold"),
                              padx=8, pady=1).pack(side="right", padx=(2, 8), pady=2)
                ent = tk.Entry(row, textvariable=qty_vars[var], width=6, justify="center",
                               bg=COL_ENTRY, fg=COL_TEXT, insertbackground=COL_TEXT, relief="flat",
                               font=("Segoe UI", 10, "bold"))
                ent.pack(side="right", padx=2, pady=3, ipady=2)
                entry_widgets[var] = ent
                RoundedButton(row, "−", command=lambda v=var: _step(v, -1), bg="#3a4358",
                              container_bg=row.cget("bg"), font=("Segoe UI", 9, "bold"),
                              padx=8, pady=1).pack(side="right", padx=(8, 2), pady=2)
                _on_change(var)
            canvas.yview_moveto(0)
            _refresh_tabs()

        for i, (name, _items) in enumerate(shops):
            b = RoundedButton(tabbar, name, command=lambda k=i: _show_shop(k), bg="#3a4358",
                              container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"), padx=10, pady=4)
            tabbar.add(b)
            tab_btns.append(b)

        RoundedButton(tools, "🔄 Tải lại kịch bản", command=lambda: self._open_shop_qty_settings(self._shop_qty_get_values()),
                      bg=COL_BLUE, container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=2
                      ).pack(side="right", padx=(2, 10))
        RoundedButton(tools, "Tất cả = 1", command=lambda: _set_all(1), bg="#3a4358",
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=2
                      ).pack(side="right", padx=2)
        RoundedButton(tools, "Tất cả = 0", command=lambda: _set_all(0), bg="#3a4358",
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=2
                      ).pack(side="right", padx=2)

        # ------------------------------ Lưu ------------------------------
        def _save(run_after=False):
            values = {}
            for si, (shop_name, items) in enumerate(shops):
                for var, item_name in items:
                    q = self._shop_parse_qty(qty_vars[var].get())
                    if q is None:
                        _show_shop(si)
                        entry_widgets[var].focus_set()
                        messagebox.showwarning(
                            "Sai số lượng",
                            f"Shop '{shop_name}' - '{item_name or var}': số lượng phải là số nguyên ≥ 0 "
                            f"(hiện là '{qty_vars[var].get()}')."
                        )
                        return
                    values[var] = (q, shop_name, item_name)

            entries = variables_registry.load_variables()
            by_name = {}
            for e in entries:
                if e.get("var") and e["var"] not in by_name:
                    by_name[e["var"]] = e
            created = 0
            for var, (q, shop_name, item_name) in values.items():
                e = by_name.get(var)
                if e is not None:
                    e["default"] = q
                else:
                    entries.append({
                        "id": variables_registry.new_variable_id(),
                        "var": var,
                        "label": f"Mua {shop_name}: {item_name or var} (số lượng)",
                        "var_type": "int",
                        "default": q,
                        "ghi_chu": f"Shop {shop_name} - đặt từ Cài Đặt Shop. 0 = bỏ qua",
                    })
                    created += 1
            variables_registry.save_variables(entries)
            buying = sum(1 for q, _, _ in values.values() if q > 0)
            self._log("info", f"🛍 Đã lưu số lượng mua Shop: {buying}/{len(values)} vật phẩm sẽ mua"
                              f"{f' (tạo mới {created} biến)' if created else ''}.")
            win.destroy()
            if run_after:
                self._quick_action(SHOP_TASK_ID)

        btns = tk.Frame(win, bg=COL_PANEL)
        btns.pack(fill="x", padx=10, pady=(2, 12))
        RoundedButton(btns, "💾 Lưu", command=lambda: _save(False), bg=COL_GREEN,
                      container_bg=COL_PANEL, font=("Segoe UI", 10, "bold"), padx=18, pady=6
                      ).pack(side="left", padx=4)
        RoundedButton(btns, "💾 Lưu & ▶ Chạy Mua Shop", command=lambda: _save(True), bg=COL_BLUE,
                      container_bg=COL_PANEL, font=("Segoe UI", 10, "bold"), padx=18, pady=6
                      ).pack(side="left", padx=4)
        RoundedButton(btns, "Đóng", command=win.destroy, bg="#3a4358",
                      container_bg=COL_PANEL, font=("Segoe UI", 10, "bold"), padx=18, pady=6
                      ).pack(side="right", padx=4)
        try:
            from datetime import datetime
            mt = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%H:%M:%S %d/%m")
        except OSError:
            mt = "?"
        total = sum(len(i) for _, i in shops)
        tk.Label(win, text=f"Nguồn: {os.path.abspath(path)}  (sửa lúc {mt})  ·  {total} vật phẩm",
                 bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=520, justify="left"
                 ).pack(anchor="w", padx=14, pady=(0, 8))
        if overrides:
            new_vars = [v for v in qty_vars if v not in overrides]
            if new_vars:
                tk.Label(win, text=f"✨ Đã nạp thêm {len(new_vars)} vật phẩm mới từ kịch bản: " + ", ".join(new_vars[:6])
                                   + ("..." if len(new_vars) > 6 else ""),
                         bg=COL_PANEL, fg=COL_GREEN, font=("Segoe UI", 9), wraplength=520, justify="left"
                         ).pack(anchor="w", padx=14, pady=(0, 4), before=btns)

        _show_shop(0)

    # ------------------------------------------------------------------
    # Bảng Cài Đặt Shop THEO GIẢ LẬP (mở từ hộp thoại 🧩 của Hẹn Giờ)
    # ------------------------------------------------------------------
    def _open_shop_qty_per_emulator(self, parent, emulators, base_vars, per_emu, on_save):
        """Cùng giao diện Cài Đặt Shop (tab Shop, +/−, Tất cả = 0/1) + thêm hàng
        tab GIẢ LẬP để đặt số lượng mua RIÊNG cho từng giả lập của 1 lịch Hẹn Giờ.

        Tham số (do `dashboard_schedule.py::_open_schedule_vars_dialog` truyền):
          parent     : cửa sổ cha (hộp thoại 🧩 Biến riêng của lịch).
          emulators  : [(index giả lập dạng chữ, nhãn hiển thị), ...] - các giả lập đang gán cho lịch.
          base_vars  : {biến: giá trị} = giá trị CHUNG của lịch (biến riêng của lịch đè Quản Lý Biến);
                       biến không có trong đây thì lấy `default` ở 🧩 Quản Lý Biến.
          per_emu    : {"<index>": {biến: số}} đang lưu của lịch (khoá `bien_theo_gia_lap`).
          on_save    : callback(new_map) khi bấm Lưu; new_map cùng định dạng per_emu.

        Lưu CHỈ các biến KHÁC giá trị chung (giả lập nào không có số riêng thì không
        có mục). Biến riêng KHÔNG thuộc danh sách Shop và giả lập không hiện trong
        bảng được giữ nguyên. Cài Đặt Shop gốc (`_open_shop_qty_settings`) không bị đổi."""
        existing = getattr(self, "_shop_emu_win", None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.destroy()
        except tk.TclError:
            pass

        emus = []
        for item in (emulators or []):
            try:
                emus.append((str(item[0]), str(item[1])))
            except (TypeError, IndexError):
                continue
        if not emus:
            messagebox.showinfo(
                "Cài Đặt Shop Theo Giả Lập",
                "Lịch này chưa gán giả lập nào.\n\nHãy gán giả lập cho lịch (nút 📱 trên dòng lịch) "
                "rồi mở lại bảng này.", parent=parent)
            return
        path, shops, tpl_map = self._shop_load_items()
        if not shops:
            messagebox.showinfo(
                "Cài Đặt Shop Theo Giả Lập",
                "Chưa tìm thấy danh sách mua Shop.\n\n"
                "Cần có kịch bản tasks/cai_dat_shop.json (Hoạt Động 'cai_dat_shop'), "
                "trong đó mỗi shop là 1 NHÓM và mỗi vật phẩm là 1 bước IF Biến "
                "(vd: Nếu tc_sach > 0).", parent=parent)
            return

        base_vars = base_vars if isinstance(base_vars, dict) else {}
        saved = {str(k): v for k, v in (per_emu or {}).items() if isinstance(v, dict)}
        registry = {v.get("var"): v for v in variables_registry.load_variables() if v.get("var")}
        shop_vars = {var for _, items in shops for var, _n in items}

        # Giá trị CHUNG của từng biến: biến riêng của lịch > default ở Quản Lý Biến.
        common = {}
        for var in shop_vars:
            raw = base_vars[var] if var in base_vars else registry.get(var, {}).get("default", 0)
            common[var] = int(self._shop_default_text(raw))

        # Số đang hiện cho (giả lập, biến): số riêng đã lưu, thiếu thì = giá trị chung.
        qty_vars = {}
        for ekey, _label in emus:
            for var in shop_vars:
                one = saved.get(ekey, {})
                init = self._shop_default_text(one[var]) if var in one else str(common[var])
                qty_vars[(ekey, var)] = tk.StringVar(value=init)

        win = ThemedToplevel(parent)
        self._shop_emu_win = win
        win.title("🛍 Cài Đặt Shop Theo Giả Lập")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "shop_qty_per_emulator", default="620x680")
        win.minsize(500, 420)
        wg.autosave(win, "shop_qty_per_emulator")
        _bind_esc_close(win)

        tk.Label(win, text="🛍 Số lượng mua Shop theo từng Giả Lập", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(win, text="Chọn GIẢ LẬP ở hàng trên, chọn SHOP ở hàng dưới. 0 = bỏ qua · 1 = mua 1 lần · N = mua N lần.\n"
                           "Ô màu CAM = khác giá trị chung của lịch (sẽ được lưu riêng cho giả lập đó); "
                           "ô bằng giá trị chung thì không lưu.",
                 bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9), justify="left", wraplength=580
                 ).pack(anchor="w", padx=14, pady=(0, 6))

        emu_bar = FlowBar(win, bg=COL_PANEL, hgap=4, vgap=4)
        emu_bar.pack(fill="x", padx=10, pady=(0, 4))
        shop_bar = FlowBar(win, bg=COL_PANEL, hgap=4, vgap=4)
        shop_bar.pack(fill="x", padx=10, pady=(0, 4))

        tools = tk.Frame(win, bg=COL_PANEL)
        tools.pack(fill="x", padx=12, pady=(0, 4))
        lbl_shop = tk.Label(tools, text="", bg=COL_PANEL, fg=COL_ACCENT, font=("Segoe UI", 10, "bold"))
        lbl_shop.pack(side="left")

        # Nút Lưu/Đóng pack TRƯỚC vùng cuộn (side=bottom) để luôn nằm ở đáy, không bị cắt.
        btns = tk.Frame(win, bg=COL_PANEL)
        btns.pack(side="bottom", fill="x", padx=10, pady=(2, 12))

        outer = tk.Frame(win, bg=COL_PANEL)
        outer.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        canvas = tk.Canvas(outer, bg=COL_PANEL, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=COL_PANEL)
        body_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(body_id, width=e.width))

        icons = {}
        win._shop_icons = icons

        def _get_icon(var):
            tpl = tpl_map.get(var)
            if not tpl:
                return None
            if tpl in icons:
                return icons[tpl]
            photo = None
            fpath = os.path.join("templates", tpl)
            if os.path.isfile(fpath):
                try:
                    from PIL import Image, ImageTk
                    im = Image.open(fpath).convert("RGBA")
                    im.thumbnail((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(im)
                except Exception:
                    photo = None
            icons[tpl] = photo
            return photo

        state = {"shop": 0, "emu": 0}
        emu_btns, shop_btns = [], []
        entry_widgets = {}  # biến -> Entry (chỉ của shop + giả lập đang hiển thị)

        def _ekey():
            return emus[state["emu"]][0]

        def _entry_color(ekey, var):
            q = self._shop_parse_qty(qty_vars[(ekey, var)].get())
            if q is None:
                return COL_RED
            return COL_ORANGE if q != common[var] else COL_TEXT

        def _own_count(ekey):
            n = 0
            for var in shop_vars:
                q = self._shop_parse_qty(qty_vars[(ekey, var)].get())
                if q is not None and q != common[var]:
                    n += 1
            return n

        def _shop_count(i, ekey):
            n = 0
            for var, _ in shops[i][1]:
                q = self._shop_parse_qty(qty_vars[(ekey, var)].get())
                if q:
                    n += 1
            return n

        def _refresh_tabs():
            for k, b in enumerate(emu_btns):
                n = _own_count(emus[k][0])
                b.set_text(f"{emus[k][1]} ({n} riêng)" if n else emus[k][1])
                b.bg_color = COL_TEAL if k == state["emu"] else "#3a4358"
                b._redraw()
            ek = _ekey()
            for i, b in enumerate(shop_btns):
                n = _shop_count(i, ek)
                b.set_text(f"{shops[i][0]} ({n})" if n else shops[i][0])
                b.bg_color = COL_BLUE if i == state["shop"] else "#3a4358"
                b._redraw()

        def _on_change(ekey, var):
            if ekey == _ekey():
                e = entry_widgets.get(var)
                if e is not None:
                    try:
                        e.config(fg=_entry_color(ekey, var))
                    except tk.TclError:
                        pass
            _refresh_tabs()

        for (ekey, var), sv in qty_vars.items():
            sv.trace_add("write", lambda *a, k=ekey, v=var: _on_change(k, v))

        def _step(var, delta):
            sv = qty_vars[(_ekey(), var)]
            q = self._shop_parse_qty(sv.get())
            sv.set(str(max(0, (q or 0) + delta)))

        def _set_all(value):
            ek = _ekey()
            for var, _ in shops[state["shop"]][1]:
                qty_vars[(ek, var)].set(str(value))

        def _show_shop(i):
            state["shop"] = i
            for w in body.winfo_children():
                w.destroy()
            entry_widgets.clear()
            ek = _ekey()
            name, items = shops[i]
            lbl_shop.config(text=f"{emus[state['emu']][1]}  ›  {name}  -  {len(items)} vật phẩm")
            for r, (var, item_name) in enumerate(items):
                row = tk.Frame(body, bg=COL_PANEL_ALT if r % 2 else COL_PANEL)
                row.pack(fill="x", pady=1)
                icon_box = tk.Frame(row, bg=row.cget("bg"), width=ICON_SIZE + 8, height=ICON_SIZE + 6)
                icon_box.pack(side="left", padx=(6, 0))
                icon_box.pack_propagate(False)
                photo = _get_icon(var)
                if photo is not None:
                    tk.Label(icon_box, image=photo, bg=row.cget("bg")).pack(expand=True)
                else:
                    tk.Label(icon_box, text="?" if tpl_map.get(var) else "", bg=row.cget("bg"),
                             fg=COL_TEXT_MUTED, font=("Segoe UI", 11, "bold")).pack(expand=True)
                tk.Label(row, text=item_name or var, bg=row.cget("bg"), fg=COL_TEXT,
                         font=("Segoe UI", 10), anchor="w").pack(side="left", padx=(4, 6), pady=3)
                tk.Label(row, text=var if item_name else "", bg=row.cget("bg"), fg=COL_TEXT_MUTED,
                         font=("Consolas", 8)).pack(side="left")
                RoundedButton(row, "+", command=lambda v=var: _step(v, 1), bg=COL_GREEN_DARK,
                              container_bg=row.cget("bg"), font=("Segoe UI", 9, "bold"),
                              padx=8, pady=1).pack(side="right", padx=(2, 8), pady=2)
                ent = tk.Entry(row, textvariable=qty_vars[(ek, var)], width=6, justify="center",
                               bg=COL_ENTRY, fg=_entry_color(ek, var), insertbackground=COL_TEXT,
                               relief="flat", font=("Segoe UI", 10, "bold"))
                ent.pack(side="right", padx=2, pady=3, ipady=2)
                entry_widgets[var] = ent
                RoundedButton(row, "−", command=lambda v=var: _step(v, -1), bg="#3a4358",
                              container_bg=row.cget("bg"), font=("Segoe UI", 9, "bold"),
                              padx=8, pady=1).pack(side="right", padx=(8, 2), pady=2)
                tk.Label(row, text=f"chung: {common[var]}", bg=row.cget("bg"), fg=COL_TEXT_MUTED,
                         font=("Segoe UI", 8)).pack(side="right", padx=(0, 6))
            canvas.yview_moveto(0)
            _refresh_tabs()

        def _select_emu(k):
            state["emu"] = k
            _show_shop(state["shop"])

        for k, (_ekey_k, label) in enumerate(emus):
            b = RoundedButton(emu_bar, label, command=lambda n=k: _select_emu(n), bg="#3a4358",
                              container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"), padx=10, pady=4)
            emu_bar.add(b)
            emu_btns.append(b)
        for i, (name, _items) in enumerate(shops):
            b = RoundedButton(shop_bar, name, command=lambda n=i: _show_shop(n), bg="#3a4358",
                              container_bg=COL_PANEL, font=("Segoe UI", 9, "bold"), padx=10, pady=4)
            shop_bar.add(b)
            shop_btns.append(b)

        def _reset_this_emulator():
            ek = _ekey()
            for var in shop_vars:
                qty_vars[(ek, var)].set(str(common[var]))

        def _copy_to_all():
            ek = _ekey()
            others = [e for e, _ in emus if e != ek]
            if not others:
                messagebox.showinfo("Chép sang mọi giả lập", "Lịch này chỉ có 1 giả lập.", parent=win)
                return
            if not messagebox.askyesno(
                    "Chép sang mọi giả lập",
                    f"Chép TOÀN BỘ số lượng (mọi Shop) của '{emus[state['emu']][1]}' sang {len(others)} giả lập còn lại?\n"
                    "Số đang đặt ở các giả lập đó sẽ bị ghi đè.", parent=win):
                return
            for var in shop_vars:
                val = qty_vars[(ek, var)].get()
                for o in others:
                    qty_vars[(o, var)].set(val)

        RoundedButton(tools, "↩ Giả lập này = giá trị chung", command=_reset_this_emulator, bg=COL_BLUE,
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=2
                      ).pack(side="right", padx=(2, 10))
        RoundedButton(tools, "📋 Chép sang mọi giả lập", command=_copy_to_all, bg=COL_PURPLE,
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=2
                      ).pack(side="right", padx=2)
        RoundedButton(tools, "Tất cả = 1", command=lambda: _set_all(1), bg="#3a4358",
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=2
                      ).pack(side="right", padx=2)
        RoundedButton(tools, "Tất cả = 0", command=lambda: _set_all(0), bg="#3a4358",
                      container_bg=COL_PANEL, font=("Segoe UI", 8, "bold"), padx=8, pady=2
                      ).pack(side="right", padx=2)

        # ------------------------------ Lưu ------------------------------
        def _save():
            new_map = dict(saved)  # giữ nguyên giả lập không hiện trong bảng
            for ei, (ekey, elabel) in enumerate(emus):
                # Giữ biến riêng KHÔNG thuộc danh sách Shop (do chỗ khác đặt).
                keep = {v: q for v, q in (saved.get(ekey) or {}).items() if v not in shop_vars}
                for si, (shop_name, items) in enumerate(shops):
                    for var, item_name in items:
                        q = self._shop_parse_qty(qty_vars[(ekey, var)].get())
                        if q is None:
                            state["emu"] = ei
                            _show_shop(si)
                            entry_widgets[var].focus_set()
                            messagebox.showwarning(
                                "Sai số lượng",
                                f"Giả lập '{elabel}' - Shop '{shop_name}' - '{item_name or var}': số lượng phải là "
                                f"số nguyên ≥ 0 (hiện là '{qty_vars[(ekey, var)].get()}').", parent=win)
                            return
                        if q != common[var]:
                            keep[var] = q
                if keep:
                    new_map[ekey] = keep
                else:
                    new_map.pop(ekey, None)
            win.destroy()
            on_save(new_map)

        RoundedButton(btns, "💾 Lưu", command=_save, bg=COL_GREEN, container_bg=COL_PANEL,
                      font=("Segoe UI", 10, "bold"), padx=18, pady=6).pack(side="left", padx=4)
        RoundedButton(btns, "Đóng", command=win.destroy, bg="#3a4358", container_bg=COL_PANEL,
                      font=("Segoe UI", 10, "bold"), padx=18, pady=6).pack(side="right", padx=4)

        _show_shop(0)

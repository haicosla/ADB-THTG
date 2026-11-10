"""
dashboard_ld_setup.py — LdSetupMixin: cửa sổ "🛠 Setup LDPlayer" cho MÁY MỚI:
  - chọn/dò ldconsole.exe,
  - chọn giả lập rồi 1 lần bấm: đặt màn hình 1280x720 (DPI 240) + bật Gỡ lỗi ADB.
Logic ghi cấu hình nằm ở ld_setup.py (không import tkinter). Giả lập đang chạy sẽ được tự TẮT
trước khi áp dụng (LDPlayer chỉ nhận thay đổi khi tắt) và tuỳ chọn BẬT LẠI sau đó.

Đây là 1 phần của class DashboardApp (xem dashboard.py) - `self.` trỏ vào cùng 1 instance.
"""
import threading
import tkinter as tk
from tkinter import messagebox

import ld_setup
import window_geometry as wg
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, _bind_esc_close, ThemedToplevel


class LdSetupMixin:
    def _open_ld_setup_dialog(self):
        win = ThemedToplevel(self.root)
        win.title("Setup LDPlayer (Máy Mới)")
        win.configure(bg=COL_PANEL)
        wg.restore_geometry(win, "ld_setup", default="680x560")
        win.minsize(560, 420)
        wg.autosave(win, "ld_setup")
        _bind_esc_close(win)

        tk.Label(win, text="🛠 Setup LDPlayer cho máy mới", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        tk.Label(win, text="Chọn ldconsole.exe, tick giả lập cần cài rồi bấm Áp Dụng: tự chỉnh màn hình về "
                           "1280x720 (DPI 240) và bật Gỡ lỗi ADB. Giả lập đang chạy sẽ được TẮT để áp dụng "
                           "(LDPlayer chỉ nhận thay đổi khi tắt).",
                 bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=640,
                 justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        # ----- 1) ldconsole -----
        box1 = tk.Frame(win, bg=COL_PANEL_ALT)
        box1.pack(fill="x", padx=14, pady=(0, 8))
        path_lbl = tk.Label(box1, text="", bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 9),
                            anchor="w", justify="left", wraplength=620)
        path_lbl.pack(fill="x", padx=10, pady=(8, 4))
        btn_row = tk.Frame(box1, bg=COL_PANEL_ALT)
        btn_row.pack(fill="x", padx=10, pady=(0, 8))

        # ----- 2) tuỳ chọn -----
        res_var = tk.BooleanVar(value=True)
        adb_var = tk.BooleanVar(value=True)
        relaunch_var = tk.BooleanVar(value=True)
        opt = tk.Frame(win, bg=COL_PANEL)
        opt.pack(fill="x", padx=14, pady=(0, 6))
        DarkCheck(opt, f"Đặt màn hình {ld_setup.TARGET_WIDTH}x{ld_setup.TARGET_HEIGHT} (DPI {ld_setup.TARGET_DPI})",
                  res_var, bg=COL_PANEL).pack(anchor="w", pady=1)
        DarkCheck(opt, "Bật Gỡ lỗi ADB (kết nối local)", adb_var, bg=COL_PANEL).pack(anchor="w", pady=1)
        DarkCheck(opt, "Bật lại những giả lập đang chạy sau khi áp dụng xong", relaunch_var,
                  bg=COL_PANEL).pack(anchor="w", pady=1)

        # ----- 3) danh sách giả lập -----
        status_lbl = tk.Label(win, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 9),
                              anchor="w", justify="left", wraplength=640)
        bottom = tk.Frame(win, bg=COL_PANEL)
        bottom.pack(side="bottom", fill="x", padx=14, pady=(0, 12))
        status_lbl.pack(side="bottom", fill="x", padx=14, pady=(0, 4))

        list_holder = tk.Frame(win, bg=COL_PANEL)
        list_holder.pack(fill="both", expand=True, padx=14, pady=(4, 6))

        rows = {}  # index -> {"var": BooleanVar, "info": EmulatorInfo}
        busy = {"running": False}

        def _set_status(text, color=None):
            try:
                status_lbl.config(text=text, fg=color or COL_TEXT_MUTED)
            except Exception:
                pass

        def _refresh_path():
            p = self.emu_manager.ldconsole_path
            ok = ld_setup.looks_like_console(p)
            path_lbl.config(text=(f"ldconsole: {p}" if p else "ldconsole: (chưa có - bấm 'Chọn ldconsole.exe' "
                                                              "hoặc 'Tự dò')"),
                            fg=COL_TEXT if ok else COL_ORANGE)

        def _rebuild_list():
            for w in list_holder.winfo_children():
                w.destroy()
            rows.clear()
            if not self.emu_manager.has_ldconsole():
                tk.Label(list_holder, text="Chưa có ldconsole.exe - chọn trước để liệt kê giả lập.",
                         bg=COL_PANEL, fg=COL_TEXT_MUTED).pack(pady=20)
                return
            try:
                infos = [i for i in self.emu_manager.list_configured() if i.index is not None]
            except Exception as e:
                tk.Label(list_holder, text=f"Không liệt kê được giả lập: {e}", bg=COL_PANEL,
                         fg=COL_ORANGE).pack(pady=20)
                return
            if not infos:
                tk.Label(list_holder, text="Không thấy giả lập nào đã tạo trong LDPlayer.",
                         bg=COL_PANEL, fg=COL_TEXT_MUTED).pack(pady=20)
                return
            hdr = tk.Frame(list_holder, bg=COL_PANEL)
            hdr.pack(fill="x")
            all_var = tk.BooleanVar(value=True)

            def _toggle_all():
                for r in rows.values():
                    r["var"].set(all_var.get())
            DarkCheck(hdr, "Chọn tất cả", all_var, command=_toggle_all, bg=COL_PANEL).pack(side="left")
            for info in sorted(infos, key=lambda i: i.index):
                st = ld_setup.read_settings(self.emu_manager.ldconsole_path, info.index)
                res, adb = ld_setup.describe_settings(st)
                var = tk.BooleanVar(value=True)
                rows[info.index] = {"var": var, "info": info}
                line = tk.Frame(list_holder, bg=COL_PANEL)
                line.pack(fill="x", pady=1)
                DarkCheck(line, f"#{info.index}  {info.name}", var, bg=COL_PANEL).pack(side="left")
                tk.Label(line, text=f"{'🟢 đang chạy' if info.running else '⚫ tắt'}   màn hình: {res}   ADB: {adb}",
                         bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8)).pack(side="left", padx=10)

        def _reload_all():
            _refresh_path()
            _rebuild_list()

        def _pick_console():
            self.choose_ldconsole_path()
            _reload_all()

        def _auto_detect():
            found = self.emu_manager._detect_ldconsole()
            if not found:
                _set_status("Không tự dò được ldconsole.exe - hãy bấm 'Chọn ldconsole.exe' và trỏ tới thư mục "
                            "cài LDPlayer.", COL_ORANGE)
                return
            self.emu_manager.set_console_path(found)
            self._save_settings()
            _set_status(f"Đã dò thấy: {found}", COL_GREEN)
            self.refresh_emulators()
            _reload_all()

        # ----- áp dụng -----
        def _worker(targets, set_res, adb_mode, relaunch):
            mgr = self.emu_manager
            console = mgr.ldconsole_path
            summary = []
            for info in targets:
                name, idx = info.name, info.index
                tag = f"'{name}' (#{idx})"
                self._busy_emulator_indexes.add(idx)
                try:
                    cur = mgr.find_by_index(idx)
                    was_running = bool(cur and cur.running)
                    if was_running:
                        self._log("info", f"[Setup LD] Đang tắt {tag} để áp dụng...", emulator_name=name)
                        mgr.quit_and_wait_stopped(
                            idx, on_log=lambda lv, m, _n=name: self._log(lv, f"[{_n}] {m}", emulator_name=_n))
                        again = mgr.find_by_index(idx)
                        if again and again.running:
                            self._log("error", f"[Setup LD] {tag} chưa tắt hẳn - bỏ qua.", emulator_name=name)
                            summary.append(f"❌ {tag}: không tắt được")
                            continue
                    results = ld_setup.apply_to_emulator(console, idx, set_res=set_res, adb_mode=adb_mode)
                    all_ok = True
                    for ok, msg in results:
                        all_ok &= ok
                        self._log("success" if ok else "error", f"[Setup LD] {tag} - {msg}", emulator_name=name)
                    summary.append(f"{'✅' if all_ok else '❌'} {tag}")
                    if was_running and relaunch:
                        ok, msg = mgr.launch(idx)
                        self._log("info" if ok else "error",
                                  f"[Setup LD] Bật lại {tag}: {msg or 'đã gửi lệnh'}", emulator_name=name)
                except Exception as e:
                    self._log("error", f"[Setup LD] Lỗi với {tag}: {e}", emulator_name=name)
                    summary.append(f"❌ {tag}: {e}")
                finally:
                    self._busy_emulator_indexes.discard(idx)

            def _done():
                busy["running"] = False
                try:
                    if win.winfo_exists():
                        _set_status("Xong: " + "  ".join(summary), COL_GREEN)
                        _rebuild_list()
                except Exception:
                    pass
                self.refresh_emulators()
            self.root.after(0, _done)

        def _apply():
            if busy["running"]:
                return
            if not ld_setup.looks_like_console(self.emu_manager.ldconsole_path):
                messagebox.showwarning("Lưu ý", "Chưa có ldconsole.exe hợp lệ - chọn trước đã.", parent=win)
                return
            set_res, set_adb = res_var.get(), adb_var.get()
            if not (set_res or set_adb):
                messagebox.showwarning("Lưu ý", "Chưa tick việc nào để áp dụng.", parent=win)
                return
            targets = [r["info"] for r in rows.values() if r["var"].get()]
            if not targets:
                messagebox.showwarning("Lưu ý", "Chưa tick giả lập nào.", parent=win)
                return
            skipped = [t for t in targets if t.index in self._busy_emulator_indexes]
            if skipped:
                messagebox.showwarning("Lưu ý", "Giả lập đang bận (chạy tay/Hẹn Giờ/đang bật): "
                                       + ", ".join(f"#{t.index}" for t in skipped)
                                       + ".\nBỏ tick chúng hoặc đợi xong rồi thử lại.", parent=win)
                return
            running = [t for t in targets if t.running]
            if running and not messagebox.askyesno(
                    "Tắt giả lập để áp dụng",
                    "Các giả lập đang chạy sẽ bị TẮT để áp dụng: "
                    + ", ".join(f"#{t.index} {t.name}" for t in running)
                    + ("\n(sẽ tự bật lại sau khi xong)" if relaunch_var.get() else "")
                    + "\n\nTiếp tục?", parent=win):
                return
            busy["running"] = True
            _set_status(f"Đang áp dụng cho {len(targets)} giả lập... (xem chi tiết ở Nhật Ký)")
            threading.Thread(target=_worker, daemon=True,
                             args=(targets, set_res, 1 if set_adb else None, relaunch_var.get())).start()

        mk = lambda parent, text, cmd, color: RoundedButton(parent, text, command=cmd, bg=color,
                                                           container_bg=parent.cget("bg"),
                                                           font=("Segoe UI", 9, "bold"))
        mk(btn_row, "📁 Chọn ldconsole.exe", _pick_console, COL_BLUE).pack(side="left", padx=(0, 6))
        mk(btn_row, "🔍 Tự dò", _auto_detect, COL_TEAL).pack(side="left", padx=(0, 6))
        mk(btn_row, "🔄 Quét lại", _reload_all, COL_GRAY_BTN).pack(side="left")
        mk(bottom, "▶ Áp Dụng", _apply, COL_ACCENT).pack(side="left", padx=(0, 6))
        mk(bottom, "Đóng", win.destroy, COL_GRAY_BTN).pack(side="left")

        _reload_all()

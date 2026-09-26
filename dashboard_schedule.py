"""
dashboard_schedule.py — Hẹn Giờ Tự Động: kiểm tra định kỳ lịch nào tới giờ chạy, xếp hàng chờ theo giả lập, thực thi 1 lượt lịch (đăng xuất/đăng nhập tài khoản xoay vòng + các Hoạt Động đã chọn), và cửa sổ quản lý lịch '⏰ Hẹn Giờ' (thêm/sửa/xoá lịch, gán Giả Lập ↔ Tài Khoản).

Đây là 1 phần của class DashboardApp (xem dashboard.py), tách riêng thành
1 Mixin theo chức năng để dễ đọc/sửa - mọi tham chiếu "self." trong file
này trỏ vào cùng 1 instance DashboardApp như khi mọi hàm còn nằm chung
1 file (không đổi hành vi, chỉ tổ chức lại code).
"""

import json
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import window_geometry as wg

from adb_helper import ADBHelper
from logic_engine import LogicEngine
from window_finder import WindowFinder
import task_registry
import account_manager
import scheduler
import activity_groups
from dashboard_theme import *
from dashboard_widgets import RoundedButton, DarkCheck, FlowBar, _bind_esc_close, Tooltip
from dashboard_missed import MissedSchedulesDialog

# ================= HÀNH ĐỘNG HỆ THỐNG (chọn được ngay trong danh sách
# "🎯 Chọn Hoạt Động" của 1 lịch, XEN KẼ với các Hoạt Động (macro) bình
# thường - id dùng tiền tố "__sys__" để chắc chắn KHÔNG trùng với id thật
# của Hoạt Động (task_registry) hay Tài khoản (account_manager) nào. Xem
# _build_activity_steps() và _exec_system_action() bên dưới. =================
SYS_EMU_ON = "__sys__emu_on"
SYS_EMU_OFF = "__sys__emu_off"
SYS_LOGOUT = "__sys__logout"
SYS_LOGIN_PREFIX = "__sys__login:"  # + tai_khoan_id ngay sau dấu ":"
SYS_GROUP_LABEL = "⚙ Hành động hệ thống"


class ScheduleMixin:
    # ================= HẸN GIỜ TỰ ĐỘNG =================
    def _check_schedules(self):
        """Chạy mỗi 20s (xem __init__) - kiểm tra từng lịch trong
        schedules.json xem đã đến giờ chưa (scheduler.is_due), nếu có thì
        trigger ngay (scheduler.mark_triggered + lưu file TRƯỚC khi chạy
        xong, xem lý do trong scheduler.py)."""
        try:
            now = datetime.now()
            due_list = [e for e in self.schedules if scheduler.is_due(e, now)]

            # LẦN KIỂM TRA ĐẦU TIÊN sau khi mở app: tách riêng các lịch đã
            # BỎ LỠ (mốc giờ hẹn rơi vào lúc chương trình đang TẮT - sớm hơn
            # lúc mở app) ra khỏi các lịch vừa tới giờ bình thường - lịch bỏ
            # lỡ KHÔNG tự chạy nữa mà hiện bảng cho người dùng chọn chạy bù
            # hay không (xem _handle_missed_schedules). Các lần kiểm tra sau
            # (app đang mở) hành xử y như cũ.
            missed_list = []
            if not getattr(self, "_missed_startup_checked", True):
                self._missed_startup_checked = True
                start_time = getattr(self, "_app_start_time", None)
                if start_time is not None:
                    missed_list = [e for e in due_list
                                   if (scheduler.last_due_time(e, now) or now) < start_time]
                    missed_ids = {id(e) for e in missed_list}
                    due_list = [e for e in due_list if id(e) not in missed_ids]

            if due_list:
                for entry in due_list:
                    scheduler.mark_triggered(entry, now)
                scheduler.save_schedules(self.schedules)
                for entry in due_list:
                    self._trigger_schedule(entry)

            if missed_list:
                self._handle_missed_schedules(missed_list, now)

            # CẢNH BÁO 1 LẦN/NGÀY cho các lịch đang TẮT ('Bật' chưa tick)
            # nhưng lẽ ra đã tới giờ chạy - nếu không có dòng này, người
            # dùng quên tick 'Bật' sẽ thấy lịch "im lặng không chạy" mà
            # KHÔNG có bất kỳ log nào giải thích vì sao (is_due trả về
            # False ngay từ bước kiểm tra 'bat', không rớt vào due_list).
            today = now.strftime("%Y-%m-%d")
            for entry in self.schedules:
                if entry.get("bat", True):
                    continue
                if not scheduler.would_be_due_if_enabled(entry, now):
                    continue
                if self._disabled_schedule_notified.get(entry.get("id")) == today:
                    continue
                self._disabled_schedule_notified[entry.get("id")] = today
                self._log("warn", f"⏰ Lịch '{entry.get('ten', '?')}' đã tới giờ hẹn nhưng đang ở trạng thái "
                                   f"TẮT ('Bật' chưa tick) nên KHÔNG tự chạy - vào '⏰ Hẹn Giờ' tick 'Bật' "
                                   f"rồi bấm 💾 nếu muốn lịch này tự chạy.")
        except Exception as e:
            self._log("error", f"Lỗi kiểm tra lịch hẹn giờ: {e}")
        finally:
            self.root.after(20000, self._check_schedules)

    def _handle_missed_schedules(self, missed_entries, now):
        """Hiện bảng '⏰ Lịch Hẹn Giờ Đã Bỏ Lỡ' (dashboard_missed.py) cho các
        lịch đã tới giờ lúc chương trình đang tắt, để người dùng TICK chọn
        lịch nào chạy bù:
          - Lịch được tick: chạy bù NGAY theo đúng thứ tự trong bảng (mốc bị
            lỡ sớm nhất chạy trước; cùng mốc thì theo thứ tự trong file), mỗi
            lịch giữ nguyên thứ tự Hoạt Động đã lưu - qua _trigger_schedule
            như mọi lượt lịch khác (giả lập bận thì tự xếp hàng chờ).
          - Lịch KHÔNG tick (kể cả khi bấm 'Không chạy gì', nút X, ESC): KHÔNG
            chạy, và được ĐẶT THÀNH 'VỪA CHẠY XONG' (scheduler.mark_triggered
            như lúc thực sự vừa chạy) - nên lần chạy kế tiếp là mốc giờ hẹn
            tiếp theo, không bị hỏi/chạy bù lại.
        Chạy trong luồng giao diện, chờ người dùng chọn xong mới đi tiếp
        (các tác vụ nền đang chạy, nếu có, vẫn chạy bình thường trong lúc chờ).
        Nếu bảng lỗi không mở được thì chạy bù tất cả như hành vi cũ."""
        order = sorted(range(len(missed_entries)),
                       key=lambda i: (scheduler.last_due_time(missed_entries[i], now) or now, i))
        entries = [missed_entries[i] for i in order]

        tasks_by_id = {
            (t.get("id") or task_registry.make_task_id(t.get("file_json", ""))): t for t in self.tasks
        }
        rows = []
        for e in entries:
            act_names = []
            for tid in e.get("hoat_dong_ids", []):
                t = tasks_by_id.get(tid)
                act_names.append(t.get("ten_hien_thi") or tid if t else f"{tid} (không còn trong Danh Mục)")
            rows.append({
                "ten": e.get("ten", "Lịch không tên"),
                "missed_at": scheduler.last_due_time(e, now),
                "missed_count": scheduler.missed_count(e, now) or 1,
                "activities": act_names,
                "emulators": [f"#{k}" for k in (e.get("gan_may_tk") or {}).keys()],
            })

        self._log("warn", f"⏰ Có {len(entries)} lịch hẹn giờ đã BỎ LỠ lúc chương trình đang tắt - chờ bạn chọn "
                           f"chạy bù lịch nào ở bảng '⏰ Lịch Hẹn Giờ Đã Bỏ Lỡ'.")
        try:
            dlg = MissedSchedulesDialog(self.root, rows)
            self.root.wait_window(dlg.win)
            picked = dlg.result
        except Exception as e:
            self._log("error", f"Không mở được bảng lịch đã bỏ lỡ ({e}) - chạy bù TẤT CẢ như trước đây.")
            picked = list(range(len(entries)))
        if picked is None:
            # Cửa sổ bị đóng cùng lúc app tắt - không quyết định gì, lần mở sau sẽ hỏi lại.
            return

        picked_set = set(picked)
        decided_at = datetime.now()
        # Đánh dấu 'vừa chạy xong' TẤT CẢ (cả tick lẫn không tick) và lưu TRƯỚC
        # khi chạy - cùng lý do như _check_schedules (xem scheduler.py).
        for e in entries:
            scheduler.mark_triggered(e, decided_at)
        scheduler.save_schedules(self.schedules)

        for i, e in enumerate(entries):
            name = e.get("ten", "Lịch không tên")
            if i in picked_set:
                self._log("info", f"⏰ Chạy bù lịch '{name}' (đã lỡ mốc {rows[i]['missed_at'].strftime('%H:%M %d/%m')}).")
                try:
                    self._trigger_schedule(e)
                except Exception as ex:
                    self._log("error", f"Lỗi khi chạy bù lịch '{name}': {ex}")
            else:
                nxt = scheduler.next_due_time(e, decided_at)
                self._log("info", f"⏭ Bỏ qua lịch '{name}' đã lỡ - đặt là 'vừa chạy xong', lần chạy kế tiếp "
                                   f"lúc {nxt.strftime('%H:%M %d/%m')}.")

    def _trigger_schedule(self, entry):
        """Tới giờ 1 lịch - dựng danh sách Hoạt Động tương ứng, rồi CHẠY theo
        đúng bảng gán THỦ CÔNG 'gan_may_tk' đã soạn sẵn qua '🔗 Gán GL/TK':
        {str(emulator_index): [tai_khoan_id, ...]}. Mỗi giả lập có mặt trong
        bảng gán luôn được chạy trên 1 luồng riêng (giống cơ chế đa luồng của
        nút CHẠY thủ công):
          - Danh sách tài khoản KHÔNG rỗng: xoay vòng Đăng Xuất - Đăng Nhập -
            chạy Hoạt Động cho từng tài khoản, y hệt '👥 Xoay Vòng Tài Khoản'.
          - Danh sách tài khoản RỖNG: chạy thẳng các Hoạt Động 1 lần trên
            giả lập đó, KHÔNG đăng xuất/đăng nhập đổi tài khoản gì cả."""
        name = entry.get("ten", "Lịch không tên")
        # GIỮ NGUYÊN thứ tự đã lưu trong hoat_dong_ids (list, do người dùng
        # tự sắp xếp ⬆️⬇️ ở popup "Chọn Hoạt Động") - KHÔNG chuyển qua set()
        # nữa vì set không có thứ tự, làm mất hẳn thứ tự chạy đã chọn.
        hoat_dong_ids = list(entry.get("hoat_dong_ids", []))
        gan_may_tk = entry.get("gan_may_tk") or {}
        # Hành Động Cuối RIÊNG của lịch này (độc lập với Hành Động Cuối
        # GỘP theo giả lập, xem _apply_post_run_options_for_schedule() bên
        # dưới) - CHUA soạn (rỗng) thì lượt chạy này rơi về dùng Hành Động
        # Cuối chung của giả lập như trước đây, KHÔNG mất tính năng cũ.
        final_ids = list(entry.get("hanh_dong_cuoi_ids", []))

        tasks_by_id = {
            (t.get("id") or task_registry.make_task_id(t.get("file_json", ""))): t for t in self.tasks
        }
        accounts_by_id = {a.get("id"): a for a in account_manager.load_accounts()}
        # Dựng `activities` ĐÚNG THEO thứ tự trong hoat_dong_ids (không phải
        # thứ tự chung trong Danh Mục Hoạt Động nữa) - id nào không còn tồn
        # tại (Hoạt Động đã bị xoá khỏi Danh Mục) sẽ tự bị bỏ qua. Cũng NHẬN
        # DIỆN LUÔN các "Hành động hệ thống" (Bật/Tắt giả lập, Đăng xuất,
        # Đăng nhập 1 tài khoản cụ thể) đã chọn xen kẽ - xem
        # _build_activity_steps().
        activities = self._build_activity_steps(hoat_dong_ids, tasks_by_id, accounts_by_id)
        if not activities:
            self._log("error", f"⏰ Lịch '{name}' đến giờ chạy nhưng không tìm thấy Hoạt Động/Hành động nào khớp "
                                f"(có thể đã bị xoá khỏi Danh Mục) - bỏ qua lượt này.")
            return

        if not gan_may_tk:
            self._log("error", f"⏰ Lịch '{name}' đến giờ chạy nhưng chưa gán Giả Lập nào - bấm '🔗 Gán GL/TK' "
                                f"rồi lưu lại - bỏ qua lượt này.")
            return

        n_tk_dong = sum(1 for v in gan_may_tk.values() if v)
        self._log("info", f"⏰ Lịch '{name}' đến giờ chạy - {len(activities)} hoạt động trên "
                           f"{len(gan_may_tk)} giả lập ({n_tk_dong} giả lập có xoay vòng tài khoản).")

        for idx_str, tk_ids in gan_may_tk.items():
            try:
                idx = int(idx_str)
            except (TypeError, ValueError):
                continue
            accs_full = [accounts_by_id[tid] for tid in tk_ids if tid in accounts_by_id and accounts_by_id[tid].get("bat", True)]
            # Áp dụng 'Chu kỳ xoay tài khoản' RIÊNG của lịch này (nếu có đặt,
            # xem scheduler.resolve_rotation_accounts) - mặc định (= 0) vẫn
            # chạy HẾT accs_full như cũ; > 0 thì chỉ lấy ĐÚNG 1 tài khoản
            # đang tới lượt, và MUTATE trạng thái xoay vòng ngay trong entry
            # (lưu file bên dưới, sau khi xử lý xong TẤT CẢ giả lập của lịch
            # này).
            accs = scheduler.resolve_rotation_accounts(entry, idx_str, accs_full)
            if accs_full and accs and accs != accs_full:
                ten_tk = accs[0].get("ten_hien_thi") or accs[0].get("username") or "?"
                self._log("info", f"⏰ Lịch '{name}' - giả lập #{idx}: đang xoay tới tài khoản '{ten_tk}' "
                                   f"({len(accs_full)} tài khoản trong danh sách).")

            if idx in self._busy_emulator_indexes:
                # Giả lập đang bận (đang chạy tay HOẶC 1 lịch khác/lượt
                # trước của CHÍNH lịch này còn dở dang) -> XẾP HÀNG CHỜ thay
                # vì bỏ qua hẳn - sẽ tự chạy ngay khi giả lập rảnh (xem
                # _after_emulator_freed), không cần người dùng làm gì thêm.
                # Dùng chung self._emulator_job_queue với lượt CHẠY tay/Chạy
                # Ngay (xem _queue_job) - "▶ Chạy Ngay" của 1 lịch cũng đi
                # qua đúng đường này vì cũng gọi _trigger_schedule().
                self._emulator_job_queue.setdefault(idx, []).append(
                    {"kind": "schedule", "name": name, "accs": accs, "activities": activities,
                     "final_ids": final_ids}
                )
                queue_len = len(self._emulator_job_queue[idx])
                self._log("warn", f"⏰ Lịch '{name}': giả lập #{idx} đang bận (đang chạy tay hoặc 1 lịch khác) - "
                                   f"đã XẾP HÀNG CHỜ (vị trí {queue_len}), sẽ tự chạy tiếp ngay khi giả lập rảnh, "
                                   f"KHÔNG bị bỏ qua.")
                continue

            self._start_schedule_worker(name, idx, accs, activities, final_ids)

        # Lưu lại NGAY nếu resolve_rotation_accounts() vừa MUTATE trạng thái
        # xoay vòng (tk_xoay_trang_thai) của lịch này ở vòng lặp trên - nếu
        # không lưu, lần trigger SAU sẽ không nhớ đã xoay tới đâu (mất trạng
        # thái khi tắt/mở lại app giữa chừng).
        scheduler.save_schedules(self.schedules)

    def _start_schedule_worker(self, name, idx, accs, activities, final_ids=None):
        """Đánh dấu giả lập #idx đang bận rồi chạy 1 luồng riêng cho lượt
        lịch này. Tách thành hàm riêng để dùng chung cho cả lượt chạy NGAY
        (khi đến giờ, giả lập đang rảnh) lẫn lượt LẤY TỪ HÀNG CHỜ ra chạy
        (khi giả lập vừa rảnh xong việc trước đó, xem _after_emulator_freed)."""
        self._busy_emulator_indexes.add(idx)
        # Dọn cờ dừng/tạm dừng RIÊNG còn sót lại của đúng giả lập #idx (nếu
        # có từ lượt trước) - tránh lượt lịch MỚI bị coi là "đã bị dừng"
        # ngay từ đầu một cách oan uổng.
        self.stop_flags.pop(idx, None)
        self.pause_flags.pop(idx, None)
        self._active_schedule_count += 1
        self._refresh_run_control_buttons()
        self._update_status_label()
        threading.Thread(target=self._worker_run_schedule, args=(name, idx, accs, activities, final_ids),
                          daemon=True).start()

    def _build_activity_steps(self, hoat_dong_ids, tasks_by_id, accounts_by_id, groups_by_id=None,
                               _visited_group_ids=None):
        """Chuyển `hoat_dong_ids` (danh sách id, GIỮ NGUYÊN thứ tự, CÓ THỂ
        LẶP LẠI - xem allow_duplicates ở popup '🎯 Chọn Hoạt Động') thành
        danh sách "bước chạy" thật (`activities`) cho 1 lượt lịch:
          - id khớp 1 Hoạt Động (macro) trong Danh Mục -> giữ nguyên dict
            Hoạt Động đó (như trước đây).
          - id là 1 trong các HẰNG SỐ SYS_* (xem đầu file) -> 1 "Hành động
            hệ thống" (Bật/Tắt giả lập, Đăng xuất, Đăng nhập 1 tài khoản cụ
            thể) - trả về 1 dict ĐÁNH DẤU bằng khoá "__he_thong__" (KHÔNG
            phải Hoạt Động thật, KHÔNG chạy qua LogicEngine) để
            _exec_system_action() xử lý riêng. "Đăng nhập" đính kèm sẵn
            TOÀN BỘ dict tài khoản đã chọn (khoá "tai_khoan") - nếu tài
            khoản đó đã bị xoá khỏi '👥 Quản Lý Tài Khoản' thì bỏ qua bước
            này (không tìm thấy trong accounts_by_id).
          - id có tiền tố GROUP_PREFIX ("GROUP:<id>") -> 1 THAM CHIẾU tới 1
            "Nhóm Hành Động" khác (xem activity_groups.py) - tự BUNG ĐỆ QUY
            thành đúng các bước con của Nhóm đó, TẠI VỊ TRÍ này (giữ nguyên
            thứ tự). Nhóm có thể LỒNG NHÓM khác bên trong (Nhóm A chứa Nhóm
            B) - `_visited_group_ids` chống LẶP VÔ HẠN nếu lỡ tạo vòng tự
            tham chiếu (Nhóm A chứa chính nó, hoặc A chứa B mà B lại chứa
            A) bằng cách bỏ qua (không bung nữa) Nhóm nào đã bung 1 lần
            trên CÙNG 1 nhánh đệ quy.
          - id không khớp gì cả (Hoạt Động/Tài khoản/Nhóm đã bị xoá) -> bỏ qua."""
        if groups_by_id is None:
            groups_by_id = activity_groups.groups_by_id()
        if _visited_group_ids is None:
            _visited_group_ids = frozenset()

        steps = []
        for tid in hoat_dong_ids:
            if tid == SYS_EMU_ON:
                steps.append({"__he_thong__": "bat_gia_lap", "ten_hien_thi": "🟢 [Hệ thống] Bật giả lập"})
            elif tid == SYS_EMU_OFF:
                steps.append({"__he_thong__": "tat_gia_lap", "ten_hien_thi": "🔴 [Hệ thống] Tắt giả lập"})
            elif tid == SYS_LOGOUT:
                steps.append({"__he_thong__": "dang_xuat", "ten_hien_thi": "🚪 [Hệ thống] Đăng xuất tài khoản"})
            elif tid.startswith(SYS_LOGIN_PREFIX):
                acc_id = tid[len(SYS_LOGIN_PREFIX):]
                acc = accounts_by_id.get(acc_id)
                if acc:
                    ten = acc.get("ten_hien_thi") or acc.get("username") or acc_id
                    steps.append({"__he_thong__": "dang_nhap", "tai_khoan": acc,
                                  "ten_hien_thi": f"🔑 [Hệ thống] Đăng nhập tài khoản: {ten}"})
                # acc không còn tồn tại -> lặng lẽ bỏ qua bước này, giống hệt
                # cách 1 Hoạt Động đã xoá khỏi Danh Mục bị bỏ qua.
            elif tid.startswith(activity_groups.GROUP_PREFIX):
                gid = tid[len(activity_groups.GROUP_PREFIX):]
                if gid in _visited_group_ids:
                    continue  # chống lặp vòng tự tham chiếu - xem docstring
                group = groups_by_id.get(gid)
                if group:
                    steps.extend(self._build_activity_steps(
                        group.get("hoat_dong_ids", []), tasks_by_id, accounts_by_id,
                        groups_by_id, _visited_group_ids | {gid}))
            elif tid in tasks_by_id:
                steps.append(tasks_by_id[tid])
        return steps

    def _exec_system_action(self, engine, emulator, act_entry, context_label, tag, login_entry, logout_entry):
        """Thực thi 1 'Hành động hệ thống' (xem _build_activity_steps) tại
        ĐÚNG vị trí của nó trong thứ tự chạy - trả về True/False (thành
        công/thất bại) giống _exec_entry() để bên gọi log/xử lý nhất quán.

        LƯU Ý khi soạn thứ tự: sau 'Tắt giả lập', MỌI bước tiếp theo cần
        ADB (Hoạt Động thường, Đăng Xuất/Đăng Nhập) sẽ THẤT BẠI - chỉ nên
        đặt 'Tắt giả lập' làm bước CUỐI CÙNG. Sau 'Bật giả lập', engine vẫn
        dùng lại đúng adb_serial cũ (LDPlayer giữ nguyên serial theo index
        qua các lần bật/tắt) nên KHÔNG cần khởi tạo lại."""
        loai = act_entry.get("__he_thong__")
        ten = act_entry.get("ten_hien_thi", loai)

        if loai == "bat_gia_lap":
            # Dùng thông tin MỚI (find_by_index) thay vì `emulator` cũ - sau bước
            # 'Tắt giả lập' đối tượng cũ vẫn ghi running=True, dễ bị coi nhầm là
            # "đã bật sẵn" và bỏ qua việc bật lại.
            fresh = self.emu_manager.find_by_index(emulator.index)
            if fresh and self.emu_manager.is_ready(fresh):
                self._log("info", f"[{tag}] {ten}: giả lập '{emulator.name}' đã bật sẵn và sẵn sàng - bỏ qua "
                                   f"bước này.", emulator_name=emulator.name)
                return True
            # Dùng ensure_running() (thay vì tự launch()+wait_until_ready()
            # như trước) vì nó đã biết tự PHỤC HỒI giả lập đang TREO (tiến
            # trình LDPlayer vẫn "running" nhưng KHÔNG phản hồi ADB/chưa
            # boot xong) - gọi thẳng launch() lên 1 giả lập đang chạy dù
            # đang treo thường KHÔNG có tác dụng gì, phải tự TẮT HẲN rồi
            # khởi động lại mới phục hồi được (xem emulator_manager.
            # quit_and_wait_stopped/ensure_running).
            self._log("info", f"[{tag}] {ten}: đang bật giả lập '{emulator.name}'...", emulator_name=emulator.name)
            ready, auto_started = self.emu_manager.ensure_running(
                emulator.index, timeout=180,
                on_log=lambda lvl, msg: self._log(lvl, f"[{tag}] {ten}: {msg}", emulator_name=emulator.name))
            if not ready:
                return False
            self._log("success", f"[{tag}] {ten}: giả lập '{ready.name}' đã boot xong.", emulator_name=ready.name)
            # Cập nhật thông tin MỚI (hwnd/serial có thể đổi sau khi tắt rồi bật lại)
            # vào đối tượng đang dùng chung cho các bước sau.
            try:
                emulator.hwnd = ready.hwnd
                emulator.adb_serial = ready.adb_serial
                emulator.running = True
                engine.adb.device_id = ready.adb_serial
            except Exception:
                pass
            getattr(self, "_prev_sys_loai", {}).pop(emulator.index, None)
            # Vừa THẬT SỰ khởi động (kể cả 'Tắt' rồi 'Bật' lại) -> chờ boot-wait rồi
            # chạy Tự Login để vào game, bất kể bước này nằm ở đâu trong chuỗi.
            if auto_started:
                self._autologin_after_boot(engine, emulator, context_label=context_label)
            return True

        if loai == "tat_gia_lap":
            self._log("info", f"[{tag}] {ten}: đang tắt giả lập '{emulator.name}'...", emulator_name=emulator.name)
            ok, msg = self.emu_manager.quit_emulator(emulator.index)
            if not ok:
                self._log("error", f"[{tag}] {ten}: tắt giả lập thất bại - {msg}", emulator_name=emulator.name)
                return False
            # Chờ tiến trình tắt HẲN (tối đa 30s) - để bước 'Bật giả lập' liền sau
            # (tắt rồi bật lại) không thấy giả lập "còn sống" mà bỏ qua việc bật.
            stopped = self.emu_manager.wait_until_stopped(emulator.index, timeout=30)
            try:
                emulator.running = False
            except Exception:
                pass
            getattr(self, "_prev_sys_loai", {}).pop(emulator.index, None)
            self._log("success", f"[{tag}] {ten}: đã tắt giả lập '{emulator.name}'" +
                                  ("" if stopped else " (lệnh tắt đã gửi, chưa xác nhận dừng hẳn sau 30s)") +
                                  " - CÁC BƯỚC SAU (nếu có) cần ADB sẽ không chạy được.", emulator_name=emulator.name)
            return True

        if loai == "dang_xuat":
            if not logout_entry:
                self._log("error", f"[{tag}] {ten}: chưa có Hoạt Động 'account_logout' trong Danh Mục - bỏ qua "
                                    f"bước này.", emulator_name=emulator.name)
                return False
            # Chạy Tự Login TRƯỚC để chắc đang ở TRONG GAME thì 'account_logout' mới
            # bấm được nút Đăng Xuất (giống Xoay Vòng Tài Khoản/Log Nhanh).
            if not self._autologin_before_step(engine, emulator, context_label, tag, ten):
                return False
            ok = self._exec_entry(engine, emulator, logout_entry, preset_vars=None, tracked=False,
                                   context_label=context_label)
            # Ghi nhớ "bước vừa rồi là Đăng Xuất" (đặt SAU _exec_entry vì _exec_entry tự xoá cờ này).
            if not hasattr(self, "_prev_sys_loai"):
                self._prev_sys_loai = {}
            self._prev_sys_loai[emulator.index] = "dang_xuat"
            return ok

        if loai == "dang_nhap":
            if not login_entry:
                self._log("error", f"[{tag}] {ten}: chưa có Hoạt Động 'account_login' trong Danh Mục - bỏ qua "
                                    f"bước này.", emulator_name=emulator.name)
                return False
            # Ngay SAU 1 bước Đăng Xuất thì game đang ở màn hình đăng nhập - chạy Tự Login
            # xen giữa sẽ vào lại game bằng tài khoản cũ, phá luôn việc vừa đăng xuất -> bỏ qua.
            just_logged_out = getattr(self, "_prev_sys_loai", {}).get(emulator.index) == "dang_xuat"
            if just_logged_out:
                self._log("info", f"[{tag}] {ten}: ngay sau Đăng Xuất - không chạy Tự Login xen giữa.",
                           emulator_name=emulator.name)
            elif not self._autologin_before_step(engine, emulator, context_label, tag, ten):
                return False
            acc = act_entry.get("tai_khoan") or {}
            preset_vars = {"tk_user": acc.get("username", ""), "tk_pass": acc.get("password", "")}
            return self._exec_entry(engine, emulator, login_entry, preset_vars=preset_vars, tracked=False,
                                     context_label=context_label)

        self._log("warn", f"[{tag}] Bước hệ thống không xác định ('{loai}') - bỏ qua.", emulator_name=emulator.name)
        return False

    def _apply_post_run_options_for_schedule(self, engine, emulator, final_ids, tag):
        """Dispatcher: nếu lịch này ĐÃ soạn Hành Động Cuối RIÊNG
        (`final_ids` không rỗng, xem entry['hanh_dong_cuoi_ids'] và
        '🏁 Hành Động Cuối Của Lịch Này' ở popup sửa lịch) thì chạy ĐÚNG
        chuỗi bước đó (độc lập hẳn, KHÔNG chạy thêm Hành Động Cuối gộp
        theo giả lập nữa - tránh chạy 2 lần/đá nhau, vd lịch A muốn Tắt
        Giả Lập nhưng giả lập lại đang được gán Hành Động Cuối chung là
        Đăng Nhập TK khác). Lịch nào CHƯA soạn (rỗng) thì rơi về dùng
        Hành Động Cuối GỘP theo giả lập như trước đây (self._apply_post_run_options),
        không đổi hành vi cho các lịch cũ chưa cấu hình gì thêm."""
        if self._is_stop_requested(emulator.index):
            return
        if final_ids:
            self._run_post_run_steps(engine, emulator, final_ids, tag=f"{tag} 🏁 Hành Động Cuối")
        else:
            self._apply_post_run_options(engine, emulator)

    def _worker_run_schedule(self, schedule_name, emulator_index, accounts, activities, final_ids=None):
        """Chạy 1 lượt lịch hẹn giờ trên 1 giả lập (emulator_index): tự bật
        giả lập nếu đang tắt, rồi:
          - Nếu `accounts` KHÔNG rỗng: lần lượt từng tài khoản - Đăng Xuất
            (nếu có) -> Đăng Nhập -> chạy đúng các Hoạt Động của lịch này -
            giống hệt '👥 Xoay Vòng Tài Khoản' nhưng do THỜI GIAN kích hoạt
            thay vì người dùng bấm CHẠY.
          - Nếu `accounts` RỖNG (lịch không chọn Tài khoản, chỉ chọn thẳng
            Giả lập): chạy các Hoạt Động NGAY 1 lần trên giả lập này, KHÔNG
            đăng xuất/đăng nhập đổi tài khoản gì cả."""
        tag = f"⏰ {schedule_name}"
        try:
            ready_info, _auto_started = self.emu_manager.ensure_running(
                emulator_index, timeout=120,
                on_log=lambda lvl, msg: self._log(lvl, f"[{tag}] {msg}")
            )
            if not ready_info:
                self._log("error", f"[{tag}] Không bật được giả lập #{emulator_index} - bỏ qua lượt này.")
                return
            emulator = ready_info
            # Vừa TỰ KHỞI ĐỘNG -> chờ thêm (ô 'Chờ boot') cho game lên hẳn; ngay sau đó
            # luồng bên dưới chạy 'auto_login' như thường lệ (trước mỗi Hoạt Động /
            # trước Đăng Xuất / trước bước hệ thống Đăng Xuất-Đăng Nhập).
            if _auto_started:
                self._wait_after_boot_for_autologin(emulator, tag)

            if not self.emu_manager.ensure_adb_connected(emulator):
                self._log("error", f"[{tag}] Không thấy giả lập '{emulator.name}' trong 'adb devices' sau khi "
                                    f"khởi động - bỏ qua lượt này.", emulator_name=emulator.name)
                return

            adb = ADBHelper()
            adb.device_id = emulator.adb_serial
            adb.update_resolution()

            wf = WindowFinder(adb)
            attached = wf.attach_hwnd(emulator.hwnd) if emulator.hwnd else False
            if not attached:
                wf.find_ld_windows()
            if wf.ensure_window_visible():
                self._log("warn", f"[{tag}] Cửa sổ LDPlayer '{emulator.name}' đang bị THU NHỎ - đã tự khôi phục lại.",
                           emulator_name=emulator.name)
                time.sleep(0.5)

            engine = LogicEngine(
                adb,
                stop_checker=self._make_stop_checker(emulator.index),
                popup_notifier=lambda msg, dur=0, bg=None, fg=None, alpha=None, pos_box=None, _wf=wf: self._show_ingame_popup(_wf, msg, dur, bg, fg, alpha, pos_box),
                logger=lambda lvl, msg, _e=emulator: self._log(lvl, f"[{tag}] {msg}", emulator_name=_e.name)
            )

            # "Tự Login" (Hoạt Động id 'auto_login'):
            #   - Lịch KHÔNG chọn Tài khoản (nhánh "không có accounts" bên
            #     dưới): giữ hành vi CŨ - chạy TRƯỚC MỖI Hoạt Động, Hoạt
            #     Động nào mà lúc đó 'auto_login' thất bại sẽ bị bỏ qua
            #     RIÊNG hoạt động đó (xem _run_activities_with_autologin).
            #   - Lịch CÓ chọn Tài khoản (xoay vòng, nhánh bên dưới): CHỈ
            #     chạy ĐÚNG 1 LẦN cho mỗi tài khoản, NGAY TRƯỚC Đăng Xuất
            #     (không chạy lại trước mỗi Hoạt Động nữa) - vì phải chắc
            #     đang ở TRONG GAME thì mới bấm được nút Đăng Xuất. Thất
            #     bại KHÔNG chặn gì - vẫn Đăng Xuất/Đăng Nhập tài khoản mới
            #     rồi chạy tiếp như bình thường (chỉ log cảnh báo), xem
            #     vòng lặp xoay vòng tài khoản bên dưới.
            auto_login_entry = None
            if getattr(self, "auto_login_var", None) and self.auto_login_var.get():
                auto_login_entry = task_registry.find_task(self.tasks, "auto_login")
                if not auto_login_entry:
                    self._log("warn", f"[{tag}] Đã bật 'Tự Login' nhưng chưa có Hoạt Động với id "
                                       f"'auto_login' (xem '📖 Hướng Dẫn').", emulator_name=emulator.name)

            # login_entry/logout_entry: ĐƯA LÊN SỚM (trước đây chỉ tính
            # trong nhánh "CÓ chọn Tài khoản" bên dưới) vì giờ 1 bước "Đăng
            # Xuất"/"Đăng Nhập TK cụ thể" (Hành động hệ thống) có thể xuất
            # hiện NGAY TRONG `activities`, kể cả ở nhánh "chạy thẳng"
            # (không chọn Tài khoản để xoay vòng) - xem
            # _build_activity_steps()/_exec_system_action().
            login_entry = task_registry.find_task(self.tasks, "account_login")
            logout_entry = task_registry.find_task(self.tasks, "account_logout")
            has_sys_dang_nhap_xuat = any(a.get("__he_thong__") in ("dang_nhap", "dang_xuat") for a in activities)
            if not login_entry and (accounts or has_sys_dang_nhap_xuat):
                self._log("warn", f"[{tag}] Chưa có Hoạt Động 'account_login' trong Danh Mục - các bước Đăng "
                                   f"Nhập (xoay vòng hoặc Hành động hệ thống) sẽ bị bỏ qua.", emulator_name=emulator.name)

            def _run_activities_with_autologin(preset_vars_for_tasks, context_label=None):
                """CHỈ dùng cho nhánh KHÔNG chọn Tài khoản (không xoay
                vòng) - xem docstring ở khối comment phía trên."""
                for act_entry in activities:
                    if self._is_stop_requested(emulator.index):
                        break
                    if act_entry.get("__he_thong__"):
                        self._exec_system_action(engine, emulator, act_entry, context_label, tag,
                                                  login_entry, logout_entry)
                        continue
                    if auto_login_entry is not None:
                        ok_login = self._exec_entry(engine, emulator, auto_login_entry, preset_vars=None,
                                                     tracked=False, context_label=context_label)
                        if self._is_stop_requested(emulator.index):
                            break
                        if not ok_login:
                            act_name = act_entry.get("ten_hien_thi", act_entry.get("id"))
                            self._log("error", f"[{tag}] Tự Login thất bại (chưa vào được game) trên "
                                                f"'{emulator.name}' trước khi chạy '{act_name}' - bỏ qua RIÊNG "
                                                f"Hoạt Động này.", emulator_name=emulator.name)
                            continue
                    self._exec_entry(engine, emulator, act_entry, preset_vars=preset_vars_for_tasks,
                                      tracked=False, context_label=context_label)

            def _run_activities_plain(preset_vars_for_tasks, context_label=None):
                """Dùng cho nhánh CÓ chọn Tài khoản (xoay vòng): chạy các
                Hoạt Động, KHÔNG kiểm tra lại 'auto_login' trước mỗi Hoạt
                Động nữa (đã kiểm tra ĐÚNG 1 LẦN ngay trước khi Đăng Xuất,
                xem vòng lặp xoay vòng bên dưới)."""
                for act_entry in activities:
                    if self._is_stop_requested(emulator.index):
                        break
                    if act_entry.get("__he_thong__"):
                        self._exec_system_action(engine, emulator, act_entry, context_label, tag,
                                                  login_entry, logout_entry)
                        continue
                    self._exec_entry(engine, emulator, act_entry, preset_vars=preset_vars_for_tasks,
                                      tracked=False, context_label=context_label)

            # KHÔNG có tài khoản nào (lịch chọn thẳng Giả lập, không chọn
            # Tài khoản) -> chạy các Hoạt Động NGAY trên giả lập này, dùng
            # đúng phiên đang đăng nhập sẵn, KHÔNG đăng xuất/đăng nhập đổi
            # tài khoản gì cả.
            if not accounts:
                self._log("info", f"[{tag}] Chạy thẳng trên '{emulator.name}' (không chọn Tài khoản - "
                                   f"không đổi tài khoản).", emulator_name=emulator.name)
                _run_activities_with_autologin(None, context_label=tag)
                if not self._is_stop_requested(emulator.index):
                    self._log("success", f"[{tag}] Hoàn thành trên '{emulator.name}'.", emulator_name=emulator.name)
                self._apply_post_run_options_for_schedule(engine, emulator, final_ids, tag)
                return

            tong_so_tk = len(accounts)
            for idx, acc in enumerate(accounts, start=1):
                if self._is_stop_requested(emulator.index):
                    break
                ten = acc.get("ten_hien_thi") or acc.get("username") or acc.get("id")
                # context_label: hiện NGAY trong Nhật Ký (tiền tố mỗi dòng
                # tác vụ bên dưới, vd '[⏰ Đá Gà - Tài khoản thứ 5/8 - Hân]
                # ── Bắt đầu tác vụ: ... ──') để biết NGAY đang chạy lịch
                # hẹn giờ nào, tới tài khoản thứ mấy - tên gì trong danh
                # sách xoay vòng - không cần đoán qua các dòng log khác.
                context_label = f"{tag} - Tài khoản thứ {idx}/{tong_so_tk} - {ten}"
                self._log("info", f"[{tag}] ═══ Tài khoản thứ {idx}/{tong_so_tk}: {ten} trên '{emulator.name}' ═══",
                           emulator_name=emulator.name)

                if auto_login_entry is not None:
                    ok_pre = self._exec_entry(engine, emulator, auto_login_entry, preset_vars=None,
                                               tracked=False, context_label=context_label)
                    if self._is_stop_requested(emulator.index):
                        break
                    if not ok_pre:
                        self._log("warn", f"[{tag}] Tự Login thất bại (chưa vào được game) trước khi đổi sang "
                                           f"tài khoản '{ten}' - vẫn tiếp tục Đăng Xuất/Đăng Nhập như bình "
                                           f"thường.", emulator_name=emulator.name)

                preset_vars = None
                ok_login = True
                if login_entry:
                    if logout_entry:
                        self._exec_entry(engine, emulator, logout_entry, preset_vars=None, tracked=False,
                                          context_label=context_label)
                        if self._is_stop_requested(emulator.index):
                            break
                    preset_vars = {"tk_user": acc.get("username", ""), "tk_pass": acc.get("password", "")}
                    ok_login = self._exec_entry(engine, emulator, login_entry, preset_vars=preset_vars,
                                                 tracked=False, context_label=context_label)

                if not ok_login:
                    self._log("error", f"[{tag}] Đăng nhập thất bại cho '{ten}' - bỏ qua tài khoản này.",
                               emulator_name=emulator.name)
                    continue

                _run_activities_plain(preset_vars, context_label=context_label)

                if not self._is_stop_requested(emulator.index):
                    # mark_run_by_id (KHÔNG PHẢI mark_run(load_accounts(),...))
                    # - tự load+sửa+save dưới 1 khoá, an toàn khi nhiều giả
                    # lập cùng ghi accounts.json song song (xem docstring).
                    account_manager.mark_run_by_id(acc.get("id"))
                    self._log("success", f"[{tag}] Hoàn thành tài khoản '{ten}'.", emulator_name=emulator.name)

            self._apply_post_run_options_for_schedule(engine, emulator, final_ids, tag)

        except Exception as e:
            self._log("error", f"[{tag}] Lỗi khi chạy trên giả lập #{emulator_index}: {e}")
        finally:
            self.root.after(0, lambda: self._on_schedule_thread_done(emulator_index))

    def _on_schedule_thread_done(self, emulator_index):
        self._busy_emulator_indexes.discard(emulator_index)
        self.stop_flags.pop(emulator_index, None)
        self.pause_flags.pop(emulator_index, None)
        self._active_schedule_count = max(0, self._active_schedule_count - 1)
        self._clear_current_task_for_index(emulator_index)
        self._refresh_run_control_buttons()
        self._update_status_label()
        self._after_emulator_freed(emulator_index)

    def _after_emulator_freed(self, emulator_index):
        """Gọi NGAY SAU KHI 1 giả lập vừa hết bận (chạy tay xong HOẶC 1 lượt
        lịch hẹn giờ xong) - nếu có job nào đang XẾP HÀNG CHỜ cho đúng giả
        lập đó (xem _trigger_schedule), lấy job ĐẦU HÀNG ra chạy tiếp ngay,
        không cần đợi tới lần _check_schedules() kế tiếp (tối đa 20s) mới
        phát hiện lại - job trễ hơn được xử lý sớm nhất có thể."""
        queue = self._emulator_job_queue.get(emulator_index)
        if not queue:
            return
        job = queue.pop(0)
        if not queue:
            self._emulator_job_queue.pop(emulator_index, None)
        remain_note = f" (còn {len(queue)} lượt khác đang chờ giả lập này)." if queue else "."

        kind = job.get("kind")
        if kind == "schedule":
            self._log("info", f"⏰ Giả lập #{emulator_index} vừa rảnh - chạy tiếp lịch đang XẾP HÀNG CHỜ: "
                               f"'{job['name']}'" + remain_note)
            self._start_schedule_worker(job["name"], emulator_index, job["accs"], job["activities"],
                                         job.get("final_ids"))
            return

        # "manual_run" / "manual_accounts" - lượt CHẠY tay/Chạy Ngay/xoay
        # vòng đang xếp hàng chờ giả lập này. Lấy lại thông tin giả lập MỚI
        # NHẤT qua emu_manager (hwnd/serial có thể đổi nếu giả lập vừa được
        # khởi động lại) thay vì dùng lại info cũ có thể đã lỗi thời.
        emulator = self.emu_manager.find_by_index(emulator_index)
        if not emulator:
            self._log("error", f"Không tìm thấy thông tin giả lập #{emulator_index} để chạy lượt đang XẾP HÀNG "
                                f"CHỜ - bỏ qua lượt này (bấm 'Quét Giả Lập' rồi tự chạy lại nếu cần).")
            return

        if kind == "manual_run":
            self._log("info", f"Giả lập '{emulator.name}' vừa rảnh - chạy tiếp lượt CHẠY đang XẾP HÀNG CHỜ"
                               f" ({len(job['selected'])} tác vụ)." + remain_note, emulator_name=emulator.name)
            self._run_queued_manual_job(job, emulator)
        elif kind == "manual_accounts":
            self._log("info", f"Giả lập '{emulator.name}' vừa rảnh - chạy tiếp lượt XOAY VÒNG TÀI KHOẢN đang "
                               f"XẾP HÀNG CHỜ ({len(job['selected'])} tác vụ)." + remain_note,
                       emulator_name=emulator.name)
            self._run_queued_manual_accounts_job(job, emulator)
        elif kind == "run_group":
            self._log("info", f"Giả lập '{emulator.name}' vừa rảnh - chạy tiếp Nhóm Hành Động '{job.get('tag', '')}' "
                               f"đang XẾP HÀNG CHỜ." + remain_note, emulator_name=emulator.name)
            self._run_queued_group_job(job, emulator)

    def _begin_queue_replay_session(self):
        """Chuẩn bị trạng thái phiên chạy (is_running/pause/nút bấm) khi 1
        job đang XẾP HÀNG CHỜ được lấy ra chạy - dùng chung cho cả
        'manual_run' lẫn 'manual_accounts'. KHÔNG reset self.active_threads
        (dùng += 1 ở nơi gọi) vì có thể đang có phiên khác chạy song song
        trên các giả lập rảnh khác - reset về 1 sẽ làm mất dấu các luồng đó."""
        if not self.is_running:
            self.is_running = True
            self.stop_flag = False
            self.pause_flag = False
            self.btn_pause.set_text("⏸ Tạm Dừng")
            self.btn_run.set_state("disabled")

    def _run_queued_manual_job(self, job, emulator):
        """Chạy 1 job 'manual_run' (CHẠY tay thường, có thể kèm Tự Login)
        vừa được lấy ra khỏi hàng chờ vì giả lập vừa rảnh."""
        selected = job["selected"]
        login_entry = job.get("login_entry")
        self._begin_queue_replay_session()
        self.stop_flags.pop(emulator.index, None)
        self.pause_flags.pop(emulator.index, None)
        self.active_threads += 1
        for entry in selected:
            task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
            prog = self.task_progress.setdefault(
                task_id, {"total": 0, "done": 0, "error": 0, "running": 0, "stopped": 0})
            prog["total"] += 1
        self._refresh_run_control_buttons()
        self._update_status_label()
        self._busy_emulator_indexes.add(emulator.index)
        threading.Thread(target=self._worker_run_emulator, args=(emulator, selected, login_entry), daemon=True).start()

    def _run_queued_group_job(self, job, emulator):
        """Chạy 1 job 'run_group' (▶ Chạy Nhóm ở '📦 Nhóm Hành Động') vừa
        được lấy ra khỏi hàng chờ vì giả lập vừa rảnh."""
        self._begin_queue_replay_session()
        self.stop_flags.pop(emulator.index, None)
        self.pause_flags.pop(emulator.index, None)
        self.active_threads += 1
        self._refresh_run_control_buttons()
        self._update_status_label()
        self._busy_emulator_indexes.add(emulator.index)
        threading.Thread(target=self._worker_run_group, args=(emulator, job["group_ids"], job["tag"]),
                          daemon=True).start()

    def _run_queued_manual_accounts_job(self, job, emulator):
        """Chạy 1 job 'manual_accounts' (CHẠY Xoay Vòng Tài Khoản) vừa được
        lấy ra khỏi hàng chờ vì giả lập vừa rảnh."""
        selected = job["selected"]
        account_ids = job.get("account_ids") or []
        self._begin_queue_replay_session()
        self.stop_flags.pop(emulator.index, None)
        self.pause_flags.pop(emulator.index, None)
        self.active_threads += 1
        for entry in selected:
            task_id = entry.get("id") or task_registry.make_task_id(entry.get("file_json", ""))
            prog = self.task_progress.setdefault(
                task_id, {"total": 0, "done": 0, "error": 0, "running": 0, "stopped": 0})
            prog["total"] += 1
        self._refresh_run_control_buttons()
        self._update_status_label()
        self._busy_emulator_indexes.add(emulator.index)
        threading.Thread(target=self._worker_run_emulator_with_accounts,
                          args=(emulator, selected, account_ids), daemon=True).start()

    def _migrate_schedules_gan_may_tk(self, entries):
        """Chuyển các lịch ĐỊNH DẠNG CŨ (2 danh sách tách rời 'tai_khoan_ids'
        + 'may_ids', tài khoản tự "nhớ" 1 giả lập cố định qua
        account_manager.emulator_index) sang định dạng MỚI 'gan_may_tk':
        dict {str(emulator_index): [tai_khoan_id, ...]} - vì bản này bỏ hẳn
        việc gán tài khoản cố định theo giả lập (xem account_manager.py),
        người dùng giờ tự chọn Giả Lập <-> Tài Khoản NGAY khi soạn lịch qua
        nút '🔗 Gán GL/TK' (xem _open_gan_may_tk_dialog).

        CỐ GẮNG migrate không mất dữ liệu: nếu accounts.json cũ VẪN CÒN field
        "emulator_index" (vd người dùng chưa mở lại '👥 Quản Lý Tài Khoản' để
        lưu đè theo định dạng mới), dùng field đó để nhóm tài khoản vào đúng
        giả lập cũ. Tài khoản không xác định được giả lập cũ (hoặc tài khoản
        cũ đã bị lưu đè mất field) được gán tạm vào giả lập ĐẦU TIÊN trong
        'may_ids' cũ của lịch đó (nếu có) - nếu vẫn không có gì để suy luận,
        lịch đó sẽ có 'gan_may_tk' rỗng và người dùng cần vào '⏰ Hẹn Giờ' bấm
        '🔗 Gán GL/TK' để gán lại thủ công (được log rõ khi lịch đó tới giờ
        chạy nhưng chưa gán gì, xem _trigger_schedule)."""
        accounts_by_id = {a.get("id"): a for a in self.accounts}
        changed = False
        for entry in entries:
            if "gan_may_tk" in entry:
                continue
            changed = True
            tai_khoan_ids = entry.pop("tai_khoan_ids", None) or []
            may_ids = entry.pop("may_ids", None) or []
            gan = {}
            leftover = []
            for tk_id in tai_khoan_ids:
                acc = accounts_by_id.get(tk_id)
                idx = acc.get("emulator_index") if acc else None
                if idx is not None:
                    gan.setdefault(str(idx), []).append(tk_id)
                else:
                    leftover.append(tk_id)
            if leftover:
                target = str(may_ids[0]) if may_ids else None
                if target is not None:
                    gan.setdefault(target, []).extend(leftover)
            for idx in may_ids:
                gan.setdefault(str(idx), gan.get(str(idx), []))
            entry["gan_may_tk"] = gan
        if changed:
            scheduler.save_schedules(entries)
        return entries

    def _open_gan_may_tk_dialog(self, parent, title, emulator_items, account_items, account_group_of,
                                 current_assignment, on_save, allow_toggle_emulator=True, intro_text=""):
        """Popup GÁN THỦ CÔNG Giả Lập <-> Tài Khoản cho 1 lượt chạy/1 lịch hẹn
        giờ - THAY THẾ cho việc tài khoản tự "nhớ" 1 giả lập cố định (đã bỏ ở
        bản này). `emulator_items`: list (emulator_index, nhãn). `current_assignment`:
        dict {emulator_index: [tai_khoan_id, ...]} - CHỈ các giả lập có mặt
        trong dict này (khi `allow_toggle_emulator=True`) mới được coi là
        "áp dụng"; danh sách tài khoản RỖNG cho 1 giả lập nghĩa là "chạy
        thẳng trên giả lập đó, không đổi tài khoản" (vẫn hợp lệ). Khi
        `allow_toggle_emulator=False` (dùng cho nút CHẠY thủ công, nơi tập
        giả lập đã CỐ ĐỊNH sẵn theo ô tick ở màn hình chính), mọi giả lập
        trong `emulator_items` LUÔN được áp dụng, chỉ cần chọn tài khoản cho
        từng cái. `on_save(dict)` được gọi khi bấm Lưu."""
        win = tk.Toplevel(parent)
        win.title(title)
        win.configure(bg=COL_PANEL)
        _geo_name = wg.slug_name("gan_may_tk", title)
        wg.restore_geometry(win, _geo_name, default="640x560")
        win.minsize(360, 320)
        wg.autosave(win, _geo_name)
        win.transient(parent)
        win.grab_set()
        win.focus_set()
        _bind_esc_close(win)

        tk.Label(win, text=title, bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        if intro_text:
            tk.Label(win, text=intro_text, bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8),
                     wraplength=590, justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        # ----- Hàng nút Lưu - PACK TRƯỚC vùng cuộn (side='bottom') để LUÔN
        # CHIẾM SẴN chỗ, không bị khuất mất trên cửa sổ nhỏ (xem giải thích
        # trong _open_multi_select_dialog). Nội dung bên trong (nhãn gợi ý +
        # nút Lưu) được thêm vào SAU, khi đã có đủ dữ liệu row_state. -----
        btn_bar = FlowBar(win, bg=COL_PANEL)
        btn_bar.pack(side="bottom", fill="x", padx=14, pady=10)

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 8))

        if not emulator_items:
            tk.Label(inner, text="(Không có giả lập nào)", bg=COL_PANEL, fg=COL_TEXT_MUTED).pack(anchor="w", pady=10)

        row_state = {}  # emulator_index -> {"applied_var": BooleanVar, "accounts": [ids], "btn": RoundedButton}

        for idx, label in emulator_items:
            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.pack(fill="x", pady=2, padx=2)

            applied_default = idx in current_assignment
            applied_var = tk.BooleanVar(value=applied_default if allow_toggle_emulator else True)
            if allow_toggle_emulator:
                DarkCheck(row, "", applied_var, bg=COL_PANEL_ALT, box_size=14).pack(side="left", padx=(6, 2), pady=6)

            tk.Label(row, text=label, bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 9),
                     anchor="w", width=26).pack(side="left", padx=4, pady=6)

            chosen_accounts = list(current_assignment.get(idx, []))
            btn = RoundedButton(row, f"👤 Chọn TK ({len(chosen_accounts)})", bg=COL_PURPLE,
                                 container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=8, pady=3)
            btn.pack(side="right", padx=6, pady=4)

            def _pick(idx=idx, btn=btn, applied_var=applied_var, label=label):
                def _on_save(chosen):
                    row_state[idx]["accounts"] = list(chosen)
                    btn.set_text(f"👤 Chọn TK ({len(chosen)})")
                    if chosen and allow_toggle_emulator:
                        applied_var.set(True)
                self._open_multi_select_dialog(
                    win, f"Chọn Tài Khoản xoay vòng trên {label}",
                    account_items, list(row_state[idx]["accounts"]), _on_save, group_of=account_group_of)
            btn.command = _pick

            row_state[idx] = {"applied_var": applied_var, "accounts": chosen_accounts, "btn": btn}

        def _save():
            result = {}
            for idx, st in row_state.items():
                if st["applied_var"].get():
                    result[idx] = list(st["accounts"])
            on_save(result)
            win.destroy()

        btn_bar.add(tk.Label(btn_bar, text="💡 Trống Tài khoản = chạy thẳng, không đổi tài khoản.",
                              bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "italic")))
        btn_bar.add(RoundedButton(btn_bar, "💾 Lưu", command=_save, bg=COL_GREEN, container_bg=COL_PANEL,
                                   font=("Segoe UI", 9, "bold"), padx=12, pady=6))

    def _open_schedule_manager(self):
        self.accounts = account_manager.load_accounts()
        self.schedules = self._migrate_schedules_gan_may_tk(scheduler.load_schedules())
        configured_emus = self.emu_manager.list_configured()

        # Tính TRƯỚC các danh sách dùng chung (Hoạt Động/Tài khoản/Giả lập) -
        # dời lên đầu hàm (trước đây tính SAU khi đã tạo canvas) vì thanh
        # LỌC THEO GIẢ LẬP (filter_bar, thêm bên dưới) cần emulator_items
        # ngay khi dựng header, trước cả khi vẽ danh sách lịch.
        activity_items = [
            (t.get("id") or task_registry.make_task_id(t.get("file_json", "")), t.get("ten_hien_thi", "?"))
            for t in sorted(self.tasks, key=lambda e: (e.get("muc", ""), e.get("thu_tu", 0)))
        ]
        # Nhóm tác vụ = đúng Mục đã đặt khi Đăng Ký Tác Vụ (vd Mục "A" gồm
        # các Hoạt Động "b","c","d") - dùng lại làm "group_of" để có nút chọn
        # nhanh theo Mục ngay trong popup "🎯 HĐ", đỡ phải tick tay từng cái.
        activity_group_of = {
            (t.get("id") or task_registry.make_task_id(t.get("file_json", ""))): (t.get("muc") or "")
            for t in self.tasks
        }
        # ----- "Nhóm Hành Động" (xem activity_groups.py, quản lý ở '📦 Nhóm
        # Hành Động' trên Dashboard) - CŨNG chọn được ngay trong popup "🎯
        # Chọn Hoạt Động" như 1 Hoạt Động bình thường (id có tiền tố
        # GROUP_PREFIX, tự "bung" thành đúng các bước con của Nhóm đó khi
        # chạy - xem _build_activity_steps() bên dưới), xếp riêng 1 Mục
        # "📦 Nhóm Hành Động" để không lẫn với Hoạt Động/Mục thường.
        self._activity_groups = activity_groups.load_groups()
        for g in self._activity_groups:
            gid = f"{activity_groups.GROUP_PREFIX}{g.get('id')}"
            activity_items.append((gid, f"📦 {g.get('ten', '?')}"))
            activity_group_of[gid] = "📦 Nhóm Hành Động"
        # ----- Hành động hệ thống (Bật/Tắt giả lập, Đăng Xuất, Đăng Nhập 1
        # tài khoản cụ thể) - KHÔNG còn nằm trong checklist Hoạt Động nữa
        # (trước đây mỗi tài khoản chiếm 1 dòng riêng trong checklist, dài
        # dòng khi có nhiều tài khoản) - giờ hiển thị thành 1 HÀNG NÚT BẤM
        # riêng "⚙ Thao tác hệ thống" ngay dưới hàng "Chọn nhanh theo nhóm"
        # trong popup "🎯 Chọn Hoạt Động" (xem `system_actions` truyền vào
        # _open_multi_select_dialog, và tham số cùng tên trong
        # dashboard_dialogs.py). Bấm 1 nút là THÊM NGAY 1 bước vào cuối
        # thứ tự chạy, bấm được nhiều lần thoải mái, xen kẽ Hoạt Động
        # thường - vd Bật giả lập, HĐ A, Đăng Xuất, Đăng Nhập TK X, HĐ B,
        # Tắt giả lập. Riêng "🔑 Đăng nhập tài khoản" chỉ có 1 NÚT DUY NHẤT
        # (không phải 1 nút/tài khoản) - bấm vào sẽ MỞ POPUP CON để CHỌN
        # tài khoản cần đăng nhập (_open_single_select_dialog), rồi mới
        # thêm đúng bước "Đăng nhập tài khoản: <tên>" đã chọn vào thứ tự
        # chạy - xem _sys_action_login bên dưới.
        sys_extra_labels = {
            SYS_EMU_ON: "🟢 Bật giả lập",
            SYS_EMU_OFF: "🔴 Tắt giả lập",
            SYS_LOGOUT: "🚪 Đăng xuất tài khoản",
        }
        sys_extra_labels.update({
            f"{SYS_LOGIN_PREFIX}{a.get('id')}":
                f"🔑 Đăng nhập tài khoản: {a.get('ten_hien_thi') or a.get('username') or a.get('id')}"
            for a in self.accounts
        })

        def _sys_action_login(add_fn):
            if not self.accounts:
                messagebox.showwarning(
                    "Chưa có tài khoản",
                    "Chưa có Tài Khoản nào - hãy thêm ở '👥 Quản Lý Tài Khoản' trước.", parent=win)
                return
            acc_by_id = {a.get("id"): a for a in self.accounts}
            acc_choices = [(a.get("id"), a.get("ten_hien_thi") or a.get("username") or a.get("id"))
                           for a in self.accounts]

            def _on_pick(acc_id):
                acc = acc_by_id.get(acc_id)
                if not acc:
                    return
                iid = f"{SYS_LOGIN_PREFIX}{acc_id}"
                label = f"🔑 Đăng nhập tài khoản: {acc.get('ten_hien_thi') or acc.get('username') or acc_id}"
                add_fn(iid, label)

            self._open_single_select_dialog(win, "Chọn tài khoản để Đăng Nhập", acc_choices, _on_pick)

        system_actions = [
            ("🟢 Bật giả lập", lambda add_fn: add_fn(SYS_EMU_ON, "🟢 Bật giả lập")),
            ("🔴 Tắt giả lập", lambda add_fn: add_fn(SYS_EMU_OFF, "🔴 Tắt giả lập")),
            ("🚪 Đăng xuất tài khoản", lambda add_fn: add_fn(SYS_LOGOUT, "🚪 Đăng xuất tài khoản")),
            ("🔑 Đăng nhập tài khoản", _sys_action_login),
        ]
        account_items = [
            (a.get("id"), a.get("ten_hien_thi") or a.get("username") or a.get("id"))
            for a in self.accounts
        ]
        account_group_of = {a.get("id"): (a.get("nhom") or "") for a in self.accounts}
        emulator_items = [
            (e.index, f"#{e.index} - {e.name}" + ("" if e.running else "  (đang tắt)"))
            for e in configured_emus
        ]

        # ----- Tra cứu NHANH tên hiển thị theo id - dùng để xây nội dung
        # tooltip (rê chuột xem chi tiết) cho nút 🎯/🔗 trên mỗi dòng lịch,
        # xem _gan_detail_text/_act_detail_text bên dưới. `activity_label_by_id`
        # gồm CẢ Hoạt Động thường LẪN thao tác hệ thống (sys_extra_labels) -
        # để tooltip hiện đúng tên dù lịch đã lưu chọn thao tác hệ thống nào.
        acc_label_by_id = {a.get("id"): (a.get("ten_hien_thi") or a.get("username") or a.get("id"))
                            for a in self.accounts}
        emu_label_by_idx = {str(idx): label for idx, label in emulator_items}
        activity_label_by_id = dict(activity_items)
        activity_label_by_id.update(sys_extra_labels)

        win = tk.Toplevel(self.root)
        win.title("Hẹn Giờ Tự Động")
        win.configure(bg=COL_PANEL)
        # Rộng hơn bản cũ (1150->1400): mỗi lịch giờ gộp CHỈ 1 DÒNG (trước đây
        # 2 dòng: dòng 1 Bật/Tên/Giờ, dòng 2 nút Hoạt Động/Gán GL-TK/hành
        # động) - gộp lại cần rộng hơn theo chiều ngang để không bị dồn cục,
        # đổi lại xem được NHIỀU LỊCH hơn trong 1 màn hình (đỡ cuộn khi có
        # vài chục lịch).
        wg.restore_geometry(win, "schedule_manager", default="1400x620")
        win.minsize(900, 480)
        wg.autosave(win, "schedule_manager")
        _bind_esc_close(win)

        tk.Label(win, text="⏰ Lịch Chạy Tự Động", bg=COL_PANEL, fg=COL_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        tk.Label(
            win,
            text="Mỗi lịch: chọn Hoạt Động áp dụng, đặt Giờ hẹn (mốc chạy trong ngày - có thể nhập NHIỀU mốc cách "
                 "nhau dấu phẩy, vd '07:00, 09:00, 14:00' để chạy cả 3 mốc đó mỗi ngày) và Lặp lại (hh:mm) - muốn "
                 "chỉ chạy ĐÚNG (các) mốc đã nhập, mỗi ngày 1 lần thì để 24:00 ở ô Lặp lại (mặc định), muốn LẶP "
                 "THÊM sau mỗi mốc thì để số giờ khác (vd 04:00 = mỗi 4 tiếng lặp lại thêm 1 lần nữa tính từ mỗi "
                 "mốc). Rồi bấm '🔗 Gán GL/TK' để chỉ định THỦ CÔNG: giả lập nào chạy, và trên mỗi giả lập đó chọn "
                 "(các) Tài khoản để xoay vòng (Đăng Xuất - Đăng Nhập - chạy Hoạt Động) - để trống Tài khoản của 1 "
                 "giả lập nghĩa là chạy thẳng Hoạt Động trên giả lập đó, KHÔNG đổi tài khoản (dùng đúng phiên đang "
                 "đăng nhập sẵn). Tự BẬT giả lập nếu đang tắt. Có thể bấm '▶ Chạy Ngay' để chạy thử ngay lập tức "
                 "mà không cần chờ tới giờ. Dashboard cần MỞ SẴN (chạy nền) để lịch tự kích hoạt - không cần tick "
                 "chọn thủ công trong danh sách tác vụ. Trong popup '🎯 Chọn Hoạt Động' còn có sẵn nhóm '⚙ Hành "
                 "động hệ thống' (Bật/Tắt giả lập, Đăng Xuất, Đăng Nhập từng tài khoản cụ thể) - xen được vào bất "
                 "kỳ vị trí nào trong thứ tự chạy, chọn lặp lại nhiều lần thoải mái (vd Bật giả lập, HĐ A, Đăng "
                 "Nhập TK X, HĐ B, Tắt giả lập). Nhớ bấm 💾 ở từng dòng sau khi sửa để lưu lại.",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=1110, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))
        tk.Label(
            win,
            text="💡 Giờ hẹn = (các) mốc chạy trong ngày, theo đúng giờ này VĨNH VIỄN (kể cả sau khi bấm 'Chạy "
                 "Ngay' để test) - nhập nhiều mốc bằng dấu phẩy, vd '07:00, 09:00, 14:00'. Lặp lại (hh:mm) = lặp "
                 "THÊM bao lâu sau mỗi mốc - để 24:00 (mặc định) nghĩa là mỗi mốc chỉ chạy đúng 1 lần/ngày, để "
                 "04:00 nghĩa là mỗi mốc còn tự lặp lại thêm mỗi 4 tiếng, để 00:30 (mỗi 30 phút) để test nhanh. "
                 "'Đổi TK sau' (hh:mm, chỉ áp dụng khi 1 giả lập có TỪ 2 tài khoản trở lên) = để 00:00 (mặc "
                 "định) thì mỗi lượt tới giờ chạy HẾT cả danh sách tài khoản như trước; đặt vd 24:00 thì mỗi "
                 "lượt CHỈ chạy 1 tài khoản, và chỉ chuyển sang tài khoản KẾ TIẾP sau khi đã đủ 24 giờ kể từ "
                 "lần đổi gần nhất - dùng để xoay vòng tài khoản THEO NGÀY (vd ngày 1 tài khoản A, ngày 2 tài "
                 "khoản B...). 🔗/🎯 trên mỗi dòng lịch: RÊ CHUỘT vào (không cần bấm) để xem ĐÚNG giả lập/tài "
                 "khoản/Hoạt Động đã gán cho dòng đó.",
            bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8), wraplength=1110, justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 8))

        if not self.tasks:
            tk.Label(win, text="⚠ Chưa có Hoạt Động nào trong Danh Mục - hãy Tạo & Đăng Ký Hoạt Động trước.",
                     bg=COL_PANEL, fg=COL_ORANGE, wraplength=1110, justify="left").pack(anchor="w", padx=14, pady=(0, 4))
        if not self.accounts:
            tk.Label(win, text="⚠ Chưa có Tài Khoản nào - hãy thêm ở '👥 Quản Lý Tài Khoản' trước nếu muốn xoay "
                                "vòng tài khoản (không bắt buộc - có thể để trống Tài khoản của 1 giả lập để chạy "
                                "thẳng).",
                     bg=COL_PANEL, fg=COL_ORANGE, wraplength=1110, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        if not configured_emus:
            tk.Label(win, text="⚠ Không tìm thấy giả lập nào (kiểm tra đường dẫn ldconsole.exe) - chưa thể chọn "
                                "Giả lập cho lịch.",
                     bg=COL_PANEL, fg=COL_ORANGE, wraplength=1110, justify="left").pack(anchor="w", padx=14, pady=(0, 8))

        # ----- Từ đây trở xuống là thông báo lịch chạy kế tiếp, header (tiêu
        # đề cột, kéo giãn/thu hẹp + bấm để sắp xếp được) + thanh lọc, rồi
        # NGAY BÊN DƯỚI là danh sách lịch (canvas cuộn) - không còn đoạn
        # ghi chú nào chen giữa 2 phần này nữa (trước đây có 1 đoạn ghi chú
        # "💡 Giờ hẹn..." nằm GIỮA thanh lọc và danh sách, làm header/thanh
        # lọc bị TÁCH XA khỏi các dòng lịch bên dưới, khó đối chiếu cột nào
        # ứng với giá trị nào) - toàn bộ ghi chú đã gộp lên TRÊN CÙNG rồi. -----

        # ----- 📢 THÔNG BÁO LỊCH CHẠY KẾ TIẾP: tổng hợp TOÀN BỘ danh sách
        # (không phải riêng từng dòng như cột "Chạy kế tiếp") - lấy mốc SỚM
        # NHẤT trong số các lịch đang BẬT và đã gán đủ Hoạt Động + Giả Lập,
        # hiện ngay trên đầu cửa sổ để biết NGAY lịch nào/mấy giờ sắp chạy
        # mà không cần dò từng dòng. Tự cập nhật lại mỗi 30 giây (khi cửa sổ
        # còn mở) và ngay sau khi Lưu/Xoá/Thêm/Chạy Ngay 1 lịch bất kỳ. -----
        def _compute_next_overall_text():
            try:
                now = datetime.now()
                candidates = []
                for e in self.schedules:
                    if not e.get("bat", True):
                        continue
                    if not e.get("hoat_dong_ids") or not e.get("gan_may_tk"):
                        continue
                    try:
                        nxt = scheduler.next_due_time(e, now)
                    except Exception:
                        continue
                    candidates.append((nxt, e.get("ten") or "Lịch không tên"))
                if not candidates:
                    return "⏰ Lịch chạy tiếp theo: chưa có lịch nào đang BẬT và đã gán đủ Hoạt Động + Giả Lập."
                nxt, ten = min(candidates, key=lambda c: c[0])
                mins_total = max(0, int((nxt - now).total_seconds() // 60))
                hh, mm = divmod(mins_total, 60)
                con_lai = f"{hh} giờ {mm:02d} phút" if hh else f"{mm} phút"
                return f"⏰ Lịch chạy tiếp theo: '{ten}' lúc {nxt.strftime('%d/%m %H:%M')} (còn {con_lai} nữa)"
            except Exception:
                return "⏰ Lịch chạy tiếp theo: (chưa tính được)"

        next_overall_lbl = tk.Label(win, text=_compute_next_overall_text(), bg=COL_PANEL, fg=COL_TEAL,
                                     font=("Segoe UI", 9, "bold"), anchor="w", wraplength=1370, justify="left")
        next_overall_lbl.pack(anchor="w", padx=14, pady=(0, 8))

        def _refresh_next_overall(*_args):
            # Cập nhật lại NGAY nội dung dòng thông báo - gọi hàm này sau
            # mỗi lần Lưu/Xoá/Thêm/Chạy Ngay 1 lịch bất kỳ. KHÔNG tự đặt
            # lịch gọi lại (xem _next_overall_loop bên dưới cho vòng lặp
            # tự động 30s) để tránh chồng nhiều vòng lặp mỗi lần gọi tay.
            if win.winfo_exists():
                next_overall_lbl.config(text=_compute_next_overall_text())

        def _next_overall_loop():
            if not win.winfo_exists():
                return
            _refresh_next_overall()
            win.after(30000, _next_overall_loop)
        _next_overall_loop()

        # ----- Header (tiêu đề cột) giờ CÓ THỂ: (1) KÉO GIÃN/THU HẸP từng
        # cột - rê chuột vào thanh mảnh giữa 2 tiêu đề rồi kéo trái/phải;
        # (2) BẤM TRỰC TIẾP vào tên cột để SẮP XẾP cả danh sách theo đúng
        # cột đó (vd bấm "Giờ hẹn" để sắp theo giờ hẹn tăng dần, bấm lại
        # lần 2 để đảo ngược giảm dần; bấm cột "🎯 HĐ / 🔗 GL-TK" để sắp theo
        # Giả Lập đã gán). Độ rộng cột (col_width) và widget của từng dòng
        # theo cột (col_widgets, để cập nhật width khi kéo giãn) chỉ tồn tại
        # trong phiên làm việc này - đóng mở lại cửa sổ sẽ về mặc định. -----
        col_specs = [
            ("bat", "Bật", 4, False),
            ("ten", "Tên lịch", 14, True),
            ("gio", "Giờ hẹn (có thể nhiều mốc)", 20, True),
            ("interval", "Lặp lại", 8, True),
            ("xoay_tk", "Đổi TK sau", 9, True),
            ("last_run", "Chạy cuối", 12, True),
            ("next_run", "Chạy kế tiếp", 12, True),
            ("gan", "🎯 HĐ / 🔗 GL-TK (bấm để sắp theo Giả Lập) ↓", None, False),
            ("smart", "Tên GL/TK/HĐ đã chọn (hiện TÊN nếu chỉ 1, hiện SỐ LƯỢNG nếu nhiều) ↓", 32, True),
        ]
        col_width = {key: w for key, _txt, w, _rs in col_specs if w is not None}
        col_widgets = {key: [] for key, *_rest in col_specs}
        col_header_lbl = {}
        sort_state = {"key": None, "reverse": False}

        def _col_sort_key(key):
            now = datetime.now()

            def _safe_next_due(e):
                try:
                    return scheduler.next_due_time(e, now)
                except Exception:
                    return datetime.max

            def _safe_gio_sort(e):
                try:
                    return scheduler.sort_key(e)
                except Exception:
                    return 10 ** 9

            return {
                "bat": lambda e: 0 if e.get("bat", True) else 1,
                "ten": lambda e: (e.get("ten") or "").lower(),
                "gio": _safe_gio_sort,
                "interval": lambda e: e.get("interval_hours", 24),
                "xoay_tk": lambda e: e.get("chu_ky_xoay_tk_gio", 0),
                "last_run": lambda e: e.get("lan_chay_luc") or "",
                "next_run": _safe_next_due,
                "gan": lambda e: min((int(i) for i in (e.get("gan_may_tk") or {}).keys()), default=9999),
                "smart": lambda e: (e.get("ten") or "").lower(),
            }.get(key, _safe_gio_sort)

        def _update_header_titles():
            for key, txt, _w, _rs in col_specs:
                lbl = col_header_lbl.get(key)
                if not lbl:
                    continue
                arrow = ""
                if sort_state["key"] == key:
                    arrow = "  ▼" if sort_state["reverse"] else "  ▲"
                lbl.config(text=txt + arrow)

        def _sort_by(key):
            if sort_state["key"] == key:
                sort_state["reverse"] = not sort_state["reverse"]
            else:
                sort_state["key"] = key
                sort_state["reverse"] = False
            # Lưu lại các thay đổi ĐANG GÕ DỞ trên từng dòng (chưa bấm 💾)
            # trước khi vẽ lại theo thứ tự mới, để KHÔNG bị mất.
            for r in list(all_rows):
                save_fn = r.get("save")
                if save_fn:
                    try:
                        save_fn(silent=True)
                    except Exception:
                        pass
            ordered = sorted(self.schedules, key=_col_sort_key(key), reverse=sort_state["reverse"])
            for r in list(all_rows):
                r["frame"].destroy()
            all_rows.clear()
            for widgets in col_widgets.values():
                widgets.clear()
            _row_index[0] = 0
            for entry in ordered:
                _add_row(entry)
            _apply_emu_filter()
            _update_header_titles()

        header = tk.Frame(win, bg=COL_HEADER)
        header.pack(fill="x", padx=10)
        for key, text, w, resizable in col_specs:
            cell = tk.Frame(header, bg=COL_HEADER)
            cell.pack(side="left", padx=(2, 0), pady=6)
            lbl_kwargs = dict(text=text, bg=COL_HEADER, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "bold"),
                               anchor="w", cursor="hand2")
            if w is not None:
                lbl_kwargs["width"] = w
            lbl = tk.Label(cell, **lbl_kwargs)
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda _e, k=key: _sort_by(k))
            Tooltip(lbl, lambda: "Bấm để sắp xếp theo cột này (bấm lại để đảo chiều).")
            col_header_lbl[key] = lbl
            if resizable:
                grip = tk.Frame(cell, bg=COL_BORDER, width=4, cursor="sb_h_double_arrow")
                grip.pack(side="left", fill="y", padx=(2, 4))
                grip._drag_start = None

                def _grip_press(e, g=grip, k=key):
                    g._drag_start = (e.x_root, col_width[k])

                def _grip_drag(e, g=grip, k=key, header_lbl=lbl):
                    if g._drag_start is None:
                        return
                    start_x, start_w = g._drag_start
                    delta_chars = int((e.x_root - start_x) / 7)  # ~7px/ký tự với font hiện tại
                    new_w = max(3, start_w + delta_chars)
                    if new_w == col_width[k]:
                        return
                    col_width[k] = new_w
                    header_lbl.config(width=new_w)
                    for widget in col_widgets[k]:
                        try:
                            widget.config(width=new_w)
                        except Exception:
                            pass

                def _grip_release(_e, g=grip):
                    g._drag_start = None

                grip.bind("<ButtonPress-1>", _grip_press)
                grip.bind("<B1-Motion>", _grip_drag)
                grip.bind("<ButtonRelease-1>", _grip_release)
            else:
                tk.Frame(cell, bg=COL_HEADER, width=8).pack(side="left")

        # ----- Thanh LỌC THEO GIẢ LẬP: khi có vài chục lịch (nhiều lịch
        # dùng chung 1 giả lập xoay nhiều tài khoản), lọc theo giả lập giúp
        # chỉ xem các lịch đang gán cho ĐÚNG giả lập đó, đỡ phải dò cả danh
        # sách. Lọc theo bản gán HIỆN TẠI trên màn hình (kể cả khi vừa đổi
        # qua '🔗 Gán GL/TK' mà CHƯA bấm 💾 lưu), không chỉ theo file đã lưu.
        filter_bar = tk.Frame(win, bg=COL_PANEL)
        filter_bar.pack(fill="x", padx=14, pady=(4, 6))
        tk.Label(filter_bar, text="🔎 Lọc theo Giả Lập:", bg=COL_PANEL, fg=COL_TEXT_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 6))
        filter_values = ["Tất cả giả lập"] + [label for _idx, label in emulator_items]
        filter_var = tk.StringVar(value="Tất cả giả lập")
        filter_combo = ttk.Combobox(filter_bar, textvariable=filter_var, values=filter_values,
                                     state="readonly", width=32, font=("Segoe UI", 8))
        filter_combo.pack(side="left")
        filter_count_lbl = tk.Label(filter_bar, text="", bg=COL_PANEL, fg=COL_TEXT_MUTED, font=("Segoe UI", 8, "italic"))
        filter_count_lbl.pack(side="left", padx=8)

        # all_rows: mỗi phần tử {"frame", "gan"} - "gan" là CHÍNH dict
        # gan_may_tk đang hiển thị của lịch đó (cùng object với bên trong
        # _add_row, luôn được cập nhật ngay khi bấm '🔗 Gán GL/TK', kể cả
        # CHƯA bấm 💾 lưu) - lọc dựa trên object này để phản ánh đúng lựa
        # chọn đang thấy trên màn hình, không chỉ dữ liệu đã lưu file.
        all_rows = []

        def _apply_emu_filter(*_args):
            sel = filter_var.get()
            shown = 0
            if sel.startswith("Tất cả"):
                for r in all_rows:
                    r["frame"].grid()
                shown = len(all_rows)
            else:
                sel_idx = None
                for idx, label in emulator_items:
                    if label == sel:
                        sel_idx = idx
                        break
                for r in all_rows:
                    match = sel_idx is not None and str(sel_idx) in r["gan"]
                    if match:
                        r["frame"].grid()
                        shown += 1
                    else:
                        r["frame"].grid_remove()
            filter_count_lbl.config(text=f"Đang hiện {shown}/{len(all_rows)} lịch")
        filter_combo.bind("<<ComboboxSelected>>", _apply_emu_filter)

        # ----- Thanh nút dưới cùng (➕ Thêm Lịch Mới) - PACK TRƯỚC vùng cuộn
        # (side='bottom') để LUÔN CHIẾM SẴN chỗ, không bị khuất trên cửa sổ
        # nhỏ (xem giải thích trong _open_multi_select_dialog). -----
        bottom_bar = FlowBar(win, bg=COL_PANEL)
        bottom_bar.pack(side="bottom", fill="x", padx=14, pady=10)

        canvas = tk.Canvas(win, bg=COL_PANEL, highlightthickness=0)
        vbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=COL_PANEL)
        # dùng grid (thay vì pack như trước) cho các dòng lịch bên trong -
        # để ẨN/HIỆN (grid_remove()/grid()) khi lọc theo giả lập mà VẪN GIỮ
        # ĐÚNG THỨ TỰ đã sắp theo giờ hẹn (pack lại từ đầu sau khi ẩn 1 dòng
        # ở giữa sẽ làm mất thứ tự, grid thì không).
        inner.columnconfigure(0, weight=1)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=4)
        vbar.pack(side="right", fill="y", padx=(0, 6))

        _row_index = [0]  # dùng list để tăng được trong nested closure (Python 2-tương-thích, khỏi cần "nonlocal")

        def _add_row(entry):
            grid_row = _row_index[0]
            _row_index[0] += 1

            row = tk.Frame(inner, bg=COL_PANEL_ALT)
            row.grid(row=grid_row, column=0, sticky="ew", pady=2)

            # ----- GỘP 1 DÒNG DUY NHẤT (trước đây 2 dòng: 1 dòng Bật/Tên/
            # Giờ/Lặp lại + 1 dòng nút Hoạt Động/Gán GL-TK/hành động) - để
            # xem được nhiều lịch hơn cùng lúc khi có vài chục lịch, đỡ phải
            # cuộn nhiều. "Chạy cuối" rút gọn còn dd/mm HH:MM (bỏ giây) và
            # nhãn chế độ (mode_lbl) rút gọn còn icon để đủ chỗ trên 1 dòng.
            bat_var = tk.BooleanVar(value=bool(entry.get("bat", True)))
            DarkCheck(row, "", bat_var, bg=COL_PANEL_ALT, box_size=14).pack(side="left", padx=(6, 2), pady=4)

            ten_var = tk.StringVar(value=entry.get("ten", ""))
            ten_entry = tk.Entry(row, textvariable=ten_var, width=col_width["ten"], bg=COL_PANEL, fg=COL_TEXT,
                                  insertbackground=COL_TEXT, relief="flat")
            ten_entry.pack(side="left", padx=2, pady=4)
            col_widgets["ten"].append(ten_entry)

            gio_var = tk.StringVar(value=entry.get("gio_hen", "07:00"))
            gio_entry = tk.Entry(row, textvariable=gio_var, width=col_width["gio"], bg=COL_PANEL, fg=COL_TEXT,
                                  insertbackground=COL_TEXT, relief="flat")
            gio_entry.pack(side="left", padx=2, pady=4)
            col_widgets["gio"].append(gio_entry)

            interval_var = tk.StringVar(value=scheduler.hours_to_hhmm(entry.get("interval_hours", 24)))
            interval_entry = tk.Entry(row, textvariable=interval_var, width=col_width["interval"], bg=COL_PANEL,
                                       fg=COL_TEXT, insertbackground=COL_TEXT, relief="flat")
            interval_entry.pack(side="left", padx=2, pady=4)
            col_widgets["interval"].append(interval_entry)

            # 'Chu kỳ xoay tài khoản' RIÊNG của lịch này - 00:00 (mặc định)
            # = TẮT, giữ hành vi CŨ (chạy hết cả danh sách tài khoản ngay
            # trong 1 lượt trigger). Đặt vd 24:00 = mỗi lượt trigger CHỈ
            # chạy 1 tài khoản, và chỉ CHUYỂN sang tài khoản kế tiếp sau khi
            # đã đủ 24 giờ kể từ lần đổi gần nhất (xem scheduler.resolve_
            # rotation_accounts). Chỉ áp dụng cho '⏰ Hẹn Giờ' - không áp
            # dụng cho nút '▶ Chạy Ngay' / '👥 Xoay Vòng Tài Khoản' thủ công.
            xoay_tk_var = tk.StringVar(value=scheduler.hours_to_hhmm(entry.get("chu_ky_xoay_tk_gio", 0)))
            xoay_tk_entry = tk.Entry(row, textvariable=xoay_tk_var, width=col_width["xoay_tk"], bg=COL_PANEL,
                                      fg=COL_TEXT, insertbackground=COL_TEXT, relief="flat")
            xoay_tk_entry.pack(side="left", padx=2, pady=4)
            col_widgets["xoay_tk"].append(xoay_tk_entry)

            def _fmt_last_run(txt):
                if not txt:
                    return "chưa chạy"
                try:
                    return datetime.fromisoformat(txt).strftime("%d/%m %H:%M")
                except Exception:
                    return txt
            last_run_lbl = tk.Label(row, text=f"🕐{_fmt_last_run(entry.get('lan_chay_luc'))}", bg=COL_PANEL_ALT,
                                     fg=COL_TEXT_MUTED, font=("Segoe UI", 8), anchor="w", width=col_width["last_run"])
            last_run_lbl.pack(side="left", padx=(4, 6), pady=4)
            col_widgets["last_run"].append(last_run_lbl)

            # 'Chạy kế tiếp' - mốc SẮP TỚI (không phải mốc đã qua như
            # last_run_lbl) - quan trọng hơn khi 1 lịch có NHIỀU mốc/ngày
            # (vd 7h-9h-14h): giúp biết NGAY mốc nào sắp chạy tiếp theo mà
            # không phải tự nhẩm tính từ chuỗi 'Giờ hẹn'. Tự cập nhật lại
            # mỗi khi bấm 💾/▶ (xem _save_row/_run_now).
            def _next_due_text():
                try:
                    nxt = scheduler.next_due_time(entry, datetime.now())
                    return f"⏭{nxt.strftime('%d/%m %H:%M')}"
                except Exception:
                    return "⏭?"
            next_run_lbl = tk.Label(row, text=_next_due_text(), bg=COL_PANEL_ALT,
                                     fg=COL_TEAL, font=("Segoe UI", 8), anchor="w", width=col_width["next_run"])
            next_run_lbl.pack(side="left", padx=(0, 6), pady=4)
            col_widgets["next_run"].append(next_run_lbl)

            chosen_activities = list(entry.get("hoat_dong_ids", []))
            # Hành Động Cuối RIÊNG của lịch này - độc lập hẳn với Hành Động
            # Cuối GỘP theo giả lập (xem _apply_post_run_options_for_schedule
            # ở trên) - để trống thì lượt chạy của lịch này rơi về dùng
            # Hành Động Cuối chung của giả lập như trước.
            chosen_final_ids = list(entry.get("hanh_dong_cuoi_ids", []))
            # gan_may_tk: {str(emulator_index): [tai_khoan_id, ...]} - giả lập
            # nào KHÔNG có mặt trong dict này = KHÔNG áp dụng lịch. Danh sách
            # tài khoản rỗng cho 1 giả lập = chạy thẳng (không đổi tài khoản).
            gan_may_tk = {str(k): list(v) for k, v in (entry.get("gan_may_tk") or {}).items()}
            row_record = {"frame": row, "gan": gan_may_tk}
            all_rows.append(row_record)

            def _gan_count_text():
                # Hiện THẲNG số hiệu giả lập (vd "#3,#5") thay vì chỉ đếm
                # số lượng - nhìn là biết NGAY dòng lịch này chạy trên giả
                # lập nào mà không cần bấm mở popup. Quá 3 giả lập thì mới
                # rút gọn lại thành số lượng cho đỡ dài dòng (rê chuột xem
                # tooltip _gan_detail_text để có danh sách đầy đủ + tên tài
                # khoản xoay vòng của TỪNG giả lập).
                idx_list = list(gan_may_tk.keys())
                if not idx_list:
                    return "🔗 (chưa gán)"
                if len(idx_list) <= 3:
                    return "🔗 " + ",".join(f"#{i}" for i in idx_list)
                n_tk = sum(1 for v in gan_may_tk.values() if v)
                return f"🔗 {len(idx_list)}GL/{n_tk}TK"

            def _gan_detail_text():
                """Nội dung tooltip khi rê chuột vào nút '🔗' - liệt kê ĐÚNG
                TÊN từng giả lập đã gán + tài khoản xoay vòng trên giả lập
                đó (hoặc 'chạy thẳng' nếu để trống Tài khoản).

                Nếu lịch này có đặt "Chu kỳ xoay tài khoản" (chu_ky_xoay_tk_gio
                > 0, xem scheduler.resolve_rotation_accounts) thì mỗi lượt
                trigger CHỈ chạy ĐÚNG 1 tài khoản đang tới lượt (không chạy
                hết cả danh sách) - trạng thái NÀY (đang ở tài khoản nào +
                lần đổi gần nhất) được LƯU LẠI trong file lịch
                (tk_xoay_trang_thai), nên tắt/mở lại app KHÔNG bị mất, lần
                trigger kế tiếp vẫn nhớ để chạy tiếp đúng chỗ - không phải
                lúc nào cũng quay lại tài khoản đầu danh sách. Tooltip dưới
                đây đọc TRỰC TIẾP trạng thái đã lưu đó để hiện thêm dòng
                "→ đang chạy đến TK: <tên> (còn ...)" cho từng giả lập có
                bật xoay theo chu kỳ."""
                if not gan_may_tk:
                    return "⚠ Chưa gán Giả Lập nào - bấm '🔗 Gán GL/TK' để chọn."
                chu_ky = float(entry.get("chu_ky_xoay_tk_gio", 0) or 0)
                trang_thai_all = entry.get("tk_xoay_trang_thai") or {}
                lines = []
                for idx_str, tk_ids in gan_may_tk.items():
                    emu_lbl = emu_label_by_idx.get(idx_str, f"Giả lập #{idx_str}")
                    if not tk_ids:
                        lines.append(f"{emu_lbl}\n    → chạy thẳng (không đổi TK)")
                        continue
                    names = ", ".join(acc_label_by_id.get(t, t) for t in tk_ids)
                    lines.append(f"{emu_lbl}\n    → xoay vòng TK: {names}")
                    # chu_ky <= 0 hoặc chỉ có 1 TK -> KHÔNG áp dụng cơ chế
                    # "1 lượt = 1 TK" (chạy hết cả danh sách mỗi lượt trigger
                    # như cũ) nên không có "đang chạy đến TK nào" để hiện.
                    if chu_ky > 0 and len(tk_ids) > 1:
                        st = trang_thai_all.get(idx_str) or {}
                        idx_dang_chay = st.get("idx", 0)
                        if not isinstance(idx_dang_chay, int) or not (0 <= idx_dang_chay < len(tk_ids)):
                            idx_dang_chay = 0
                        ten_dang_chay = acc_label_by_id.get(tk_ids[idx_dang_chay], tk_ids[idx_dang_chay])
                        luc_doi_raw = st.get("luc")
                        con_lai_txt = ""
                        if luc_doi_raw:
                            try:
                                last_dt = datetime.fromisoformat(luc_doi_raw)
                                con_lai_giay = chu_ky * 3600 - (datetime.now() - last_dt).total_seconds()
                                if con_lai_giay > 0:
                                    con_lai_txt = f" (còn {scheduler.hours_to_hhmm(con_lai_giay / 3600)} nữa mới đổi)"
                                else:
                                    con_lai_txt = " (đã đủ giờ - lượt chạy TIẾP THEO sẽ đổi sang TK kế)"
                            except Exception:
                                con_lai_txt = ""
                        else:
                            con_lai_txt = " (chưa chạy lượt nào)"
                        lines.append(f"    ⏳ đang chạy đến TK: {ten_dang_chay}{con_lai_txt}")
                return "\n".join(lines)

            def _act_detail_text():
                """Nội dung tooltip khi rê chuột vào nút '🎯' - liệt kê ĐÚNG
                TÊN + THỨ TỰ các Hoạt Động/thao tác hệ thống đã chọn."""
                if not chosen_activities:
                    return "(Chưa chọn Hoạt Động nào - bấm '🎯' để chọn)"
                return "\n".join(f"{i + 1}. {activity_label_by_id.get(aid, aid)}"
                                  for i, aid in enumerate(chosen_activities))

            btn_act = RoundedButton(row, f"🎯{len(chosen_activities)}", bg=COL_BLUE,
                                     container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=6, pady=3)
            btn_act.pack(side="left", padx=2, pady=(0, 0))
            Tooltip(btn_act, _act_detail_text)

            btn_gan = RoundedButton(row, _gan_count_text(), bg=COL_PURPLE,
                                     container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=6, pady=3)
            btn_gan.pack(side="left", padx=2, pady=(0, 0))
            Tooltip(btn_gan, _gan_detail_text)

            def _final_detail_text():
                """Nội dung tooltip khi rê chuột vào nút '🏁' - liệt kê ĐÚNG
                TÊN + THỨ TỰ các bước Hành Động Cuối RIÊNG của lịch này
                (rỗng = đang dùng Hành Động Cuối GỘP theo giả lập)."""
                if not chosen_final_ids:
                    return "(Chưa soạn riêng - đang dùng Hành Động Cuối GỘP theo giả lập, bấm '🏁' để soạn riêng)"
                return "\n".join(f"{i + 1}. {activity_label_by_id.get(aid, aid)}"
                                  for i, aid in enumerate(chosen_final_ids))

            btn_final = RoundedButton(row, f"🏁{len(chosen_final_ids)}" if chosen_final_ids else "🏁(chung)",
                                       bg=COL_GREEN if chosen_final_ids else COL_PANEL,
                                       container_bg=COL_PANEL_ALT, font=("Segoe UI", 8, "bold"), padx=6, pady=3)
            btn_final.pack(side="left", padx=2, pady=(0, 0))
            Tooltip(btn_final, _final_detail_text)

            mode_lbl = tk.Label(row, text="", bg=COL_PANEL_ALT, fg=COL_TEXT_MUTED, font=("Segoe UI", 9))
            mode_lbl.pack(side="left", padx=(4, 2), pady=4)
            Tooltip(mode_lbl, lambda: {"⚠": "⚠ Chưa gán Giả Lập nào cho lịch này",
                                        "🔁": "🔁 Có xoay vòng tài khoản (Đăng Xuất - Đăng Nhập)",
                                        "➡": "➡ Chạy thẳng, không đổi tài khoản"}.get(mode_lbl.cget("text"), ""))

            def _refresh_mode_label():
                if not gan_may_tk:
                    mode_lbl.config(text="⚠")
                elif any(gan_may_tk.values()):
                    mode_lbl.config(text="🔁")
                else:
                    mode_lbl.config(text="➡")
            _refresh_mode_label()

            # ----- CỘT MỚI: hiện thẳng TÊN Hoạt Động/Giả Lập/Tài khoản khi
            # lịch này chỉ chọn ĐÚNG 1 cái (đỡ phải rê chuột/bấm mở popup
            # mới biết là cái nào) - còn chọn NHIỀU thì vẫn hiện SỐ LƯỢNG
            # như cột 🎯/🔗 cũ (giữ nguyên, không đổi) để khỏi dài dòng. -----
            def _smart_summary_full_text():
                if len(chosen_activities) == 1:
                    act_txt = activity_label_by_id.get(chosen_activities[0], chosen_activities[0])
                elif len(chosen_activities) > 1:
                    act_txt = f"{len(chosen_activities)} Hoạt Động"
                else:
                    act_txt = "(chưa chọn HĐ)"
                idx_list = list(gan_may_tk.keys())
                if len(idx_list) == 1:
                    gl_txt = emu_label_by_idx.get(idx_list[0], f"Giả lập #{idx_list[0]}")
                elif len(idx_list) > 1:
                    gl_txt = f"{len(idx_list)} giả lập"
                else:
                    gl_txt = "(chưa gán GL)"
                # Tài khoản: gộp CHUNG tất cả giả lập (loại trùng, giữ thứ
                # tự) - chỉ 1 tài khoản DUY NHẤT trên toàn lịch (dù 1 hay
                # nhiều giả lập) mới hiện tên, nhiều hơn thì hiện số lượng.
                uniq_tk = list(dict.fromkeys(t for v in gan_may_tk.values() for t in v))
                if len(uniq_tk) == 1:
                    tk_txt = acc_label_by_id.get(uniq_tk[0], uniq_tk[0])
                elif len(uniq_tk) > 1:
                    tk_txt = f"{len(uniq_tk)} tài khoản"
                else:
                    tk_txt = "chạy thẳng (không đổi TK)"
                return f"🎯 {act_txt}\n🔗 {gl_txt}\n👤 {tk_txt}"

            def _smart_summary_line():
                # Bản RÚT GỌN 1 DÒNG cho vừa dòng lịch - rê chuột vào để
                # xem đủ 3 dòng (Hoạt Động/Giả Lập/Tài khoản) không bị cắt.
                line = "   ".join(_smart_summary_full_text().split("\n"))
                return line if len(line) <= 46 else line[:45] + "…"

            def _refresh_smart_summary():
                smart_lbl.config(text=_smart_summary_line())

            smart_lbl = tk.Label(row, text="", bg=COL_PANEL_ALT, fg=COL_TEXT, font=("Segoe UI", 8),
                                  anchor="w", width=col_width["smart"])
            smart_lbl.pack(side="left", padx=(6, 4), pady=4)
            col_widgets["smart"].append(smart_lbl)
            Tooltip(smart_lbl, _smart_summary_full_text)
            _refresh_smart_summary()

            def _pick_activities():
                def _on_save(chosen):
                    chosen_activities[:] = chosen
                    btn_act.set_text(f"🎯{len(chosen_activities)}")
                    _refresh_smart_summary()
                self._open_multi_select_dialog(win, "Chọn Hoạt Động cho lịch này",
                                                activity_items, list(chosen_activities), _on_save,
                                                group_of=activity_group_of, allow_duplicates=True,
                                                system_actions=system_actions, extra_labels=sys_extra_labels)
            btn_act.command = _pick_activities

            def _pick_final_actions():
                def _on_save(chosen):
                    chosen_final_ids[:] = chosen
                    # RoundedButton không có set_bg() để đổi màu động sau khi
                    # tạo - chỉ cập nhật lại chữ (số bước), giữ nguyên màu
                    # gốc lúc dựng dòng (không quan trọng bằng số bước).
                    btn_final.set_text(f"🏁{len(chosen_final_ids)}" if chosen_final_ids else "🏁(chung)")
                accounts_full = account_manager.load_accounts()
                self._open_steps_editor(
                    f"Hành Động Cuối RIÊNG của lịch '{entry.get('ten', '')}' (để trống = dùng Hành Động Cuối "
                    f"GỘP theo giả lập)",
                    chosen_final_ids, accounts_full, activity_items, activity_group_of, _on_save)
            btn_final.command = _pick_final_actions

            def _pick_gan():
                # Chuyển key int cho dialog (emulator_items dùng index kiểu int).
                current = {int(k): v for k, v in gan_may_tk.items()}

                def _on_save(result):
                    gan_may_tk.clear()
                    gan_may_tk.update({str(k): v for k, v in result.items()})
                    btn_gan.set_text(_gan_count_text())
                    _refresh_mode_label()
                    _refresh_smart_summary()
                    # Cập nhật ngay thanh lọc (nếu đang lọc theo 1 giả lập cụ
                    # thể) để phản ánh đúng lựa chọn vừa đổi, không cần đóng
                    # mở lại cửa sổ mới thấy.
                    _apply_emu_filter()
                self._open_gan_may_tk_dialog(
                    win, f"Gán Giả Lập ↔ Tài Khoản cho lịch '{entry.get('ten', '')}'",
                    emulator_items, account_items, account_group_of, current, _on_save,
                    allow_toggle_emulator=True,
                    intro_text="Tick chọn (các) giả lập áp dụng cho lịch này, rồi bấm '👤 Chọn TK' của từng giả "
                               "lập để chọn tài khoản xoay vòng trên đúng giả lập đó (để trống = chạy thẳng, "
                               "không đổi tài khoản).")
            btn_gan.command = _pick_gan

            def _save_row(silent=False):
                entry["bat"] = bool(bat_var.get())
                entry["ten"] = ten_var.get().strip() or "Lịch không tên"
                gio_text = gio_var.get().strip() or "07:00"
                try:
                    entry["gio_hen"] = scheduler.hhmm_multi_to_stored(gio_text)
                except ValueError as ve:
                    messagebox.showerror("Giờ hẹn không hợp lệ",
                                          f"{ve}\n\nNhập theo dạng HH:MM, vd 07:00 hoặc 22:30. Muốn nhiều mốc/ngày "
                                          f"thì cách nhau dấu phẩy, vd '07:00, 09:00, 14:00'.", parent=win)
                    return False
                gio_var.set(entry["gio_hen"])
                try:
                    entry["interval_hours"] = scheduler.hhmm_to_hours(interval_var.get())
                except Exception:
                    messagebox.showerror("Giờ lặp lại không hợp lệ",
                                          f"'{interval_var.get()}' không đúng định dạng hh:mm. Nhập vd 24:00 "
                                          f"(hằng ngày), 04:00 (mỗi 4 tiếng), 00:30 (mỗi 30 phút để test).",
                                          parent=win)
                    return False
                try:
                    entry["chu_ky_xoay_tk_gio"] = scheduler.hhmm_to_hours_allow_zero(xoay_tk_var.get())
                except Exception:
                    messagebox.showerror("Chu kỳ xoay tài khoản không hợp lệ",
                                          f"'{xoay_tk_var.get()}' không đúng định dạng hh:mm. Để 00:00 = TẮT "
                                          f"(chạy hết cả danh sách tài khoản trong 1 lượt như trước), hoặc vd "
                                          f"24:00 = mỗi lượt chỉ chạy 1 tài khoản, đổi tài khoản kế tiếp sau mỗi "
                                          f"24 giờ.",
                                          parent=win)
                    return False
                entry["hoat_dong_ids"] = list(chosen_activities)
                entry["hanh_dong_cuoi_ids"] = list(chosen_final_ids)
                entry["gan_may_tk"] = dict(gan_may_tk)
                self.schedules = scheduler.upsert_schedule(self.schedules, entry)
                scheduler.save_schedules(self.schedules)
                next_run_lbl.config(text=_next_due_text())
                _refresh_next_overall()
                trang_thai = "🟢 ĐANG BẬT - sẽ tự chạy đúng giờ" if entry["bat"] else "🔴 ĐANG TẮT - sẽ KHÔNG tự chạy cho tới khi bạn tick lại 'Bật'"
                if not silent:
                    che_do = "có xoay vòng tài khoản" if any(gan_may_tk.values()) else "chạy thẳng giả lập"
                    self._log("success", f"Đã lưu lịch '{entry['ten']}' ({scheduler.describe(entry)}, "
                                          f"{len(chosen_activities)} hoạt động, {len(gan_may_tk)} giả lập, chế độ "
                                          f"{che_do}) - {trang_thai}.")
                    messagebox.showinfo("Đã lưu", f"Đã lưu lịch '{entry['ten']}'.\n\n{trang_thai}.", parent=win)
                return True
            row_record["save"] = _save_row

            def _delete_row():
                if not messagebox.askyesno("Xác nhận", f"Xoá lịch '{entry.get('ten', '')}' này?", parent=win):
                    return
                self.schedules = scheduler.remove_schedule(self.schedules, entry.get("id"))
                scheduler.save_schedules(self.schedules)
                row.destroy()
                all_rows[:] = [r for r in all_rows if r["frame"] is not row]
                filter_count_lbl.config(text=f"Đang hiện {len(all_rows)}/{len(all_rows)} lịch")
                self._log("warn", f"Đã xoá lịch '{entry.get('ten', '')}'.")
                _refresh_next_overall()

            def _run_now():
                if not _save_row(silent=True):
                    return
                if not entry.get("hoat_dong_ids"):
                    messagebox.showwarning("Thiếu Hoạt Động",
                                            "Lịch này chưa chọn Hoạt Động nào - bấm '🎯 HĐ' để chọn trước.",
                                            parent=win)
                    return
                if not entry.get("gan_may_tk"):
                    messagebox.showwarning("Chưa gán Giả Lập",
                                            "Lịch này chưa gán Giả Lập nào - bấm '🔗 Gán GL/TK' để chọn ít nhất 1 "
                                            "giả lập trước (có thể để trống Tài khoản của giả lập đó nếu chỉ "
                                            "muốn chạy thẳng, không đổi tài khoản).",
                                            parent=win)
                    return
                if not entry.get("bat", True):
                    # "Chạy Ngay" vẫn cho chạy thử dù lịch đang TẮT (không tick
                    # 'Bật') - nhưng phải cảnh báo rõ, nếu không người dùng dễ
                    # hiểu nhầm là lịch "vẫn hoạt động bình thường, tự chạy
                    # được" trong khi thực ra _check_schedules() sẽ bỏ qua nó
                    # hoàn toàn (không ghi log gì cả) cho tới khi tick lại Bật.
                    messagebox.showwarning(
                        "Lịch đang TẮT",
                        f"Lịch '{entry.get('ten', '')}' đang ở trạng thái TẮT (cột 'Bật' chưa tick) - "
                        f"nó sẽ KHÔNG tự chạy khi đến giờ hẹn. Lượt chạy thử này vẫn tiếp tục vì bạn bấm "
                        f"'Chạy Ngay' thủ công. Hãy tick 'Bật' rồi bấm 💾 nếu muốn lịch tự chạy sau này.",
                        parent=win)
                scheduler.mark_triggered(entry)
                scheduler.save_schedules(self.schedules)
                last_run_lbl.config(text=f"🕐{_fmt_last_run(entry.get('lan_chay_luc'))}")
                next_run_lbl.config(text=_next_due_text())
                _refresh_next_overall()
                self._log("info", f"▶ Chạy ngay lịch '{entry.get('ten', '')}' theo yêu cầu thủ công.")
                self._trigger_schedule(entry)

            RoundedButton(row, "▶", command=_run_now, bg=COL_TEAL, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 8, "bold"), padx=7, pady=3).pack(side="right", padx=2, pady=4)
            RoundedButton(row, "💾", command=_save_row, bg=COL_GREEN, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 9, "bold"), padx=7, pady=3).pack(side="right", padx=3, pady=4)
            RoundedButton(row, "🗑", command=_delete_row, bg=COL_RED, container_bg=COL_PANEL_ALT,
                          font=("Segoe UI", 9, "bold"), padx=7, pady=3).pack(side="right", padx=2, pady=4)

        # Hiển thị theo THỨ TỰ THỜI GIAN CHẠY trong ngày (giờ hẹn sớm nhất
        # lên đầu) thay vì thứ tự thêm vào file - dễ nhìn tổng quan lịch
        # nào chạy trước/sau trong ngày. KHÔNG đổi thứ tự lưu trong
        # schedules.json, chỉ đổi thứ tự HIỂN THỊ ở đây.
        for entry in sorted(self.schedules, key=scheduler.sort_key):
            _add_row(entry)
        filter_count_lbl.config(text=f"Đang hiện {len(all_rows)}/{len(all_rows)} lịch")

        def _add_new():
            # QUAN TRỌNG: KHÔNG để lan_chay_luc=None cho lịch MỚI TẠO.
            # scheduler._is_due_ignoring_bat() dùng "lưới giờ cố định" (neo
            # từ 2020-01-01 theo gio_hen, lặp lại mỗi interval_hours) để
            # tính mốc lưới GẦN NHẤT đã qua so với hiện tại - việc này đúng
            # cho lịch ĐÃ TỪNG CHẠY (để "chạy bù" nếu app tắt đúng lúc lỡ
            # giờ), nhưng nếu lan_chay_luc=None thì is_due() coi mốc lưới
            # gần nhất đã qua (vd hôm qua, hoặc vài giờ trước) là "CHƯA XỬ
            # LÝ" -> trả về True NGAY, khiến lịch mới tạo bị trigger chạy
            # ngay khi lưu (dù giờ hẹn hôm nay CHƯA tới). Đánh dấu sẵn
            # lan_chay_luc = "bây giờ" khi vừa tạo = coi như mốc lưới quá
            # khứ gần nhất đã "xử lý" rồi, nên is_due() chỉ trả True ở mốc
            # lưới TIẾP THEO trong tương lai - đúng như người dùng mong đợi.
            now = datetime.now()
            entry = {
                "id": scheduler.new_schedule_id(),
                "ten": "Lịch mới",
                "gio_hen": "07:00",
                "interval_hours": 24,
                "chu_ky_xoay_tk_gio": 0,
                "hoat_dong_ids": [],
                "hanh_dong_cuoi_ids": [],
                "gan_may_tk": {},
                "bat": True,
                "lan_chay_ngay": now.strftime("%Y-%m-%d"),
                "lan_chay_luc": now.isoformat(timespec="seconds"),
            }
            _add_row(entry)
            # Lịch mới chưa gán giả lập nào - nếu đang lọc theo 1 giả lập cụ
            # thể, dòng vừa thêm sẽ bị ẩn ngay lập tức trông như "mất tích".
            # Về lại "Tất cả giả lập" để chắc chắn thấy dòng vừa tạo.
            if filter_var.get() != "Tất cả giả lập":
                filter_var.set("Tất cả giả lập")
            _apply_emu_filter()

        # ----- 💾 Lưu Tất Cả: lưu MỘT LƯỢT toàn bộ các dòng lịch đang hiển
        # thị (kể cả những dòng đang gõ dở chưa bấm 💾 riêng từng dòng) -
        # khỏi phải bấm 💾 từng dòng một khi sửa nhiều lịch cùng lúc. Dòng
        # nào lỗi định dạng (Giờ hẹn/Lặp lại/Đổi TK sau) vẫn báo lỗi riêng
        # y hệt bấm 💾 từng dòng (không bị bỏ qua âm thầm), các dòng còn lại
        # vẫn được lưu bình thường rồi mới gộp 1 thông báo tổng kết cuối cùng.
        def _save_all():
            if not all_rows:
                messagebox.showinfo("Lưu Tất Cả", "Chưa có lịch nào để lưu.", parent=win)
                return
            so_luong = len(all_rows)
            so_loi = 0
            for r in list(all_rows):
                save_fn = r.get("save")
                if not save_fn:
                    continue
                try:
                    if not save_fn(silent=True):
                        so_loi += 1
                except Exception:
                    so_loi += 1
            _refresh_next_overall()
            if so_loi:
                self._log("warn", f"Đã bấm 'Lưu Tất Cả': {so_luong - so_loi}/{so_luong} lịch lưu thành công, "
                                   f"{so_loi} lịch bị LỖI (xem hộp thoại báo lỗi riêng từng dòng).")
                messagebox.showwarning("Lưu Tất Cả", f"Đã lưu {so_luong - so_loi}/{so_luong} lịch.\n\n"
                                        f"{so_loi} lịch bị LỖI (thường do 'Giờ hẹn'/'Lặp lại'/'Đổi TK sau' sai "
                                        f"định dạng - xem hộp thoại lỗi riêng của từng dòng vừa hiện) - sửa lại "
                                        f"rồi bấm 'Lưu Tất Cả' lần nữa.", parent=win)
            else:
                self._log("success", f"Đã 'Lưu Tất Cả': {so_luong}/{so_luong} lịch lưu thành công.")
                messagebox.showinfo("Lưu Tất Cả", f"Đã lưu thành công tất cả {so_luong} lịch.", parent=win)

        bottom_bar.add(RoundedButton(bottom_bar, "💾 Lưu Tất Cả", command=_save_all, bg=COL_GREEN,
                                      container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))
        bottom_bar.add(RoundedButton(bottom_bar, "➕ Thêm Lịch Mới", command=_add_new, bg=COL_ACCENT, fg="#241a00",
                                      container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))

        # "🏁 Hành Động Cuối" - shortcut mở THẲNG popup soạn chuỗi bước hậu
        # kỳ theo giả lập (self._post_run_steps_by_emulator, xem
        # _pick_post_run_actions() ở dashboard_run.py) NGAY TỪ cửa sổ Hẹn
        # Giờ, không cần đóng cửa sổ này quay ra thanh công cụ chính. LƯU Ý:
        # đây là cấu hình DÙNG CHUNG theo GIẢ LẬP (không phải riêng theo
        # từng lịch) - 1 giả lập chạy xong bất kỳ lịch nào trên nó (hoặc
        # CHẠY tay/Xoay Vòng) đều tự áp dụng CÙNG chuỗi bước này.
        bottom_bar.add(RoundedButton(bottom_bar, "🏁 Hành Động Cuối Theo Giả Lập", command=self._pick_post_run_actions,
                                      bg=COL_PURPLE, container_bg=COL_PANEL, font=("Segoe UI", 9, "bold")))

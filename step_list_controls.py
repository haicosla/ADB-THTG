import copy


class StepListController:
    """Gắn các tính năng lên bảng danh sách bước (ttk.Treeview):
       1) Kéo-thả để sắp xếp lại thứ tự các bước.
       2) Ctrl+C / Ctrl+X / Ctrl+V để sao chép, cắt, dán bước.
       3) Click chuột phải vào hành động để chỉnh sửa thông số.
    """

    def __init__(self, tree, get_steps, on_changed, on_edit_step=None):
        self.tree = tree
        self.get_steps = get_steps
        self.on_changed = on_changed
        self.on_edit_step = on_edit_step

        self._clipboard = []
        # NHÓM các dòng đang được kéo (trước đây chỉ có 1 "_moving_iid" nên
        # bôi đen nhiều dòng rồi kéo chỉ dòng bấm chuột xuống di chuyển,
        # các dòng còn lại trong nhóm bị "bỏ lại" - xem _on_press/_on_motion
        # bên dưới để biết cách giữ nguyên cả nhóm khi kéo).
        self._moving_group = []
        self._press_row = None
        self._press_xy = None
        self._drag_engaged = False
        # Đánh dấu lúc bấm chuột xuống, dòng vừa bấm có đang nằm trong 1
        # nhóm NHIỀU dòng đã bôi đen từ trước hay không - để biết lúc nhả
        # chuột ra mà KHÔNG kéo đi đâu cả thì có cần thu về chỉ chọn lại
        # đúng 1 dòng đó hay không (giống hành vi click bình thường mà
        # bước _on_press phải tạm chặn lại để nhóm không bị "vỡ" ngay khi
        # vừa bấm xuống).
        self._press_was_multi_member = False

        self._bind_drag_drop()
        self._bind_copy_paste()
        self._bind_right_click()

    _DRAG_THRESHOLD = 5
    # Cờ trạng thái phím Shift/Control trong event.state (Tkinter) - giữ 1
    # trong 2 phím này khi bấm chuột là để MỞ RỘNG/BỚT vùng bôi đen theo
    # kiểu Explorer, không phải để kéo-thả, nên bỏ qua không xử lý kéo.
    _SHIFT_OR_CONTROL_MASK = 0x0005

    def _bind_drag_drop(self):
        self.tree.bind("<ButtonPress-1>", self._on_press, add="+")
        self.tree.bind("<B1-Motion>", self._on_motion, add="+")
        self.tree.bind("<ButtonRelease-1>", self._on_release, add="+")

    def _on_press(self, event):
        self._press_row = None
        self._press_xy = None
        self._drag_engaged = False
        self._press_was_multi_member = False
        if getattr(event, "state", 0) & self._SHIFT_OR_CONTROL_MASK:
            self._moving_group = []
            return
        row = self.tree.identify_row(event.y)
        if not row:
            self._moving_group = []
            return
        self._press_row = row
        self._press_xy = (event.x, event.y)
        cur_sel = self.tree.selection()
        if row in cur_sel and len(cur_sel) > 1:
            # Đang bấm chuột xuống 1 dòng NẰM TRONG nhóm nhiều dòng đã bôi
            # đen từ trước -> giữ NGUYÊN cả nhóm đó để có thể kéo đi cùng
            # nhau, đồng thời "break" để CHẶN hành vi mặc định của
            # Treeview (vốn sẽ tự thu bôi đen về còn đúng 1 dòng NGAY khi
            # bấm chuột xuống, trước cả khi kịp kéo).
            self._moving_group = sorted(cur_sel, key=lambda iid: self.tree.index(iid))
            self._press_was_multi_member = True
            return "break"
        self._moving_group = [row]

    def _on_motion(self, event):
        if not self._moving_group:
            return
        if getattr(event, "state", 0) & self._SHIFT_OR_CONTROL_MASK:
            return

        if not self._drag_engaged:
            dx = abs(event.x - self._press_xy[0]) if self._press_xy else 0
            dy = abs(event.y - self._press_xy[1]) if self._press_xy else 0
            if dx < self._DRAG_THRESHOLD and dy < self._DRAG_THRESHOLD:
                return
            self._drag_engaged = True

        target_row = self.tree.identify_row(event.y)
        if not target_row or target_row in self._moving_group:
            return

        # Dựng lại toàn bộ thứ tự: giữ nguyên các dòng KHÔNG nằm trong nhóm
        # đang kéo, rồi chèn CẢ NHÓM (vẫn giữ đúng thứ tự tương đối với
        # nhau) vào đúng vị trí dòng đang hover tới - nhờ vậy dù kéo 1 hay
        # nhiều dòng cùng lúc, chúng luôn di chuyển CÙNG NHAU thành 1 khối.
        children = list(self.tree.get_children(""))
        group_set = set(self._moving_group)
        remaining = [c for c in children if c not in group_set]
        if target_row not in remaining:
            return
        insert_at = remaining.index(target_row)
        new_order = remaining[:insert_at] + self._moving_group + remaining[insert_at:]
        for i, iid in enumerate(new_order):
            self.tree.move(iid, "", i)

    def _on_release(self, event):
        if not self._moving_group:
            return
        moved_group = self._moving_group
        engaged = self._drag_engaged
        was_multi_member = self._press_was_multi_member
        press_row = self._press_row
        self._moving_group = []
        self._drag_engaged = False
        self._press_was_multi_member = False
        if engaged:
            self._sync_steps_from_tree_order(moved_group)
        elif was_multi_member and press_row:
            # Chỉ bấm chuột rồi thả ra tại chỗ (KHÔNG kéo đi đâu cả) trên 1
            # dòng đang nằm trong nhóm nhiều dòng bôi đen -> coi như 1 cú
            # click bình thường: thu bôi đen lại về đúng 1 dòng vừa bấm,
            # giống hệt hành vi mặc định của Treeview mà _on_press ở trên
            # đã tạm "break" để chặn lại, phòng trường hợp người dùng định
            # kéo cả nhóm chứ không phải chỉ muốn chọn lại 1 dòng.
            self.tree.selection_set(press_row)

    def _sync_steps_from_tree_order(self, moved_group):
        steps = self.get_steps()
        try:
            order = [int(iid) for iid in self.tree.get_children("")]
        except ValueError:
            return
        if len(order) != len(steps) or sorted(order) != list(range(len(steps))):
            return

        new_steps = [steps[i] for i in order]
        steps[:] = new_steps

        try:
            moved_indices = [order.index(int(iid)) for iid in moved_group]
        except (ValueError, TypeError):
            moved_indices = []
        if len(moved_indices) == 1:
            self.on_changed(select_index=moved_indices[0])
        elif moved_indices:
            self.on_changed(select_range=(min(moved_indices), max(moved_indices)))
        else:
            self.on_changed()

    def _bind_copy_paste(self):
        for seq in ("<Control-c>", "<Control-C>"):
            self.tree.bind(seq, self.copy_selected)
        for seq in ("<Control-x>", "<Control-X>"):
            self.tree.bind(seq, self.cut_selected)
        for seq in ("<Control-v>", "<Control-V>"):
            self.tree.bind(seq, self.paste_clipboard)

    def _bind_right_click(self):
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Button-2>", self._on_right_click)

    def _on_right_click(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
            if self.on_edit_step:
                idx = int(row)
                self.on_edit_step(idx, event.x_root, event.y_root)
        else:
            # Click vào khoảng trống (không trúng dòng nào) -> báo về idx=None
            # để phía gui.py hiện menu "Thêm hành động thủ công & logic" thay vì
            # không làm gì như trước đây.
            self.tree.selection_remove(*self.tree.selection())
            if self.on_edit_step:
                self.on_edit_step(None, event.x_root, event.y_root)

    def copy_selected(self, event=None):
        steps = self.get_steps()
        sel = sorted(int(i) for i in self.tree.selection())
        if not sel:
            return "break"
        self._clipboard = copy.deepcopy([steps[i] for i in sel])
        return "break"

    def cut_selected(self, event=None):
        steps = self.get_steps()
        sel = sorted(int(i) for i in self.tree.selection())
        if not sel:
            return "break"
        self._clipboard = copy.deepcopy([steps[i] for i in sel])
        for i in reversed(sel):
            del steps[i]
        self.on_changed()
        return "break"

    def paste_clipboard(self, event=None):
        if not self._clipboard:
            return "break"
        steps = self.get_steps()
        sel = self.tree.selection()
        insert_at = int(sel[-1]) + 1 if sel else len(steps)
        pasted = copy.deepcopy(self._clipboard)
        steps[insert_at:insert_at] = pasted
        self.on_changed(select_range=(insert_at, insert_at + len(pasted) - 1))
        return "break"
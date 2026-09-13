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
        self._moving_iid = None
        self._press_xy = None
        self._drag_engaged = False

        self._bind_drag_drop()
        self._bind_copy_paste()
        self._bind_right_click()

    _DRAG_THRESHOLD = 5

    def _bind_drag_drop(self):
        self.tree.bind("<ButtonPress-1>", self._on_press, add="+")
        self.tree.bind("<B1-Motion>", self._on_motion, add="+")
        self.tree.bind("<ButtonRelease-1>", self._on_release, add="+")

    def _on_press(self, event):
        row = self.tree.identify_row(event.y)
        self._moving_iid = row if row else None
        self._press_xy = (event.x, event.y)
        self._drag_engaged = False

    def _on_motion(self, event):
        if self._moving_iid is None:
            return
        if getattr(event, "state", 0) & 0x0005:
            return

        if not self._drag_engaged:
            dx = abs(event.x - self._press_xy[0]) if self._press_xy else 0
            dy = abs(event.y - self._press_xy[1]) if self._press_xy else 0
            if dx < self._DRAG_THRESHOLD and dy < self._DRAG_THRESHOLD:
                return
            self._drag_engaged = True

        target_row = self.tree.identify_row(event.y)
        if target_row and target_row != self._moving_iid:
            self.tree.move(self._moving_iid, "", self.tree.index(target_row))

    def _on_release(self, event):
        if self._moving_iid is None:
            return
        moved_iid = self._moving_iid
        engaged = self._drag_engaged
        self._moving_iid = None
        self._drag_engaged = False
        if engaged:
            self._sync_steps_from_tree_order(moved_iid)

    def _sync_steps_from_tree_order(self, moved_iid):
        steps = self.get_steps()
        try:
            order = [int(iid) for iid in self.tree.get_children("")]
        except ValueError:
            return
        if len(order) != len(steps) or sorted(order) != list(range(len(steps))):
            return

        new_steps = [steps[i] for i in order]
        steps[:] = new_steps

        new_index = None
        try:
            new_index = order.index(int(moved_iid))
        except (ValueError, TypeError):
            pass
        self.on_changed(select_index=new_index)

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
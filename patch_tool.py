import glob
import os
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class PatchToolApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Quick Patch Manager")
        self.root.geometry("680x520")
        self.root.minsize(580, 420)

        # Lấy thư mục hiện tại nơi đặt script .py
        self.current_dir = os.path.dirname(os.path.abspath(__file__))

        self.create_widgets()
        self.auto_detect_defaults()

    def create_widgets(self):
        pad_opts = {"padx": 10, "pady": 6}

        # Frame cấu hình đường dẫn
        frame_inputs = ttk.LabelFrame(self.root, text="Đường dẫn làm việc")
        frame_inputs.pack(fill="x", **pad_opts)

        # 1. Thư mục code
        ttk.Label(frame_inputs, text="Thư mục code:").grid(
            row=0, column=0, sticky="w", padx=6, pady=4
        )
        self.entry_repo = ttk.Entry(frame_inputs, width=45)
        self.entry_repo.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(
            frame_inputs, text="Đổi...", command=self.browse_repo
        ).grid(row=0, column=2, padx=6, pady=4)

        # 2. File Patch (Hỗ trợ chọn nhanh qua Dropdown + duyệt ngoài)
        ttk.Label(frame_inputs, text="File Patch:").grid(
            row=1, column=0, sticky="w", padx=6, pady=4
        )
        self.cbo_patch = ttk.Combobox(frame_inputs, width=43)
        self.cbo_patch.grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(
            frame_inputs, text="Duyệt...", command=self.browse_patch
        ).grid(row=1, column=2, padx=6, pady=4)

        frame_inputs.columnconfigure(1, weight=1)

        # Frame nút thao tác
        frame_actions = ttk.Frame(self.root)
        frame_actions.pack(fill="x", padx=10, pady=4)

        self.btn_check = ttk.Button(
            frame_actions,
            text="1. Check Patch (Dry Run)",
            command=self.check_patch,
        )
        self.btn_check.pack(side="left", padx=5)

        self.btn_apply = ttk.Button(
            frame_actions, text="2. Apply Patch", command=self.apply_patch
        )
        self.btn_apply.pack(side="left", padx=5)

        self.btn_reload = ttk.Button(
            frame_actions, text="Quét lại file", command=self.scan_patches
        )
        self.btn_reload.pack(side="left", padx=5)

        self.btn_clear = ttk.Button(
            frame_actions, text="Xóa Log", command=self.clear_log
        )
        self.btn_clear.pack(side="right", padx=5)

        # Khung log
        frame_log = ttk.LabelFrame(self.root, text="Nhật ký thực thi")
        frame_log.pack(fill="both", expand=True, **pad_opts)

        self.txt_log = tk.Text(
            frame_log, wrap="word", font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4"
        )
        scrollbar = ttk.Scrollbar(
            frame_log, orient="vertical", command=self.txt_log.yview
        )
        self.txt_log.configure(yscrollcommand=scrollbar.set)

        self.txt_log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def auto_detect_defaults(self):
        # Trỏ thẳng vào thư mục chứa file .py
        self.entry_repo.delete(0, tk.END)
        self.entry_repo.insert(0, self.current_dir)

        # Tự quét các file .patch / .diff tại thư mục này
        self.scan_patches()

    def scan_patches(self):
        repo_dir = self.entry_repo.get().strip() or self.current_dir
        patch_files = glob.glob(os.path.join(repo_dir, "*.patch")) + glob.glob(
            os.path.join(repo_dir, "*.diff")
        )

        self.cbo_patch["values"] = patch_files
        if patch_files:
            self.cbo_patch.current(0)
            self.log(
                f"[Tự động nhận diện] Tìm thấy {len(patch_files)} file patch. Đã chọn: {os.path.basename(patch_files[0])}"
            )
        else:
            self.cbo_patch.set("")
            self.log(
                "[Thông báo] Không tìm thấy file .patch hay .diff nào trong thư mục này. Hãy bấm 'Duyệt...' để chọn."
            )

    def browse_repo(self):
        folder = filedialog.askdirectory(
            title="Chọn thư mục chứa mã nguồn", initialdir=self.current_dir
        )
        if folder:
            self.entry_repo.delete(0, tk.END)
            self.entry_repo.insert(0, os.path.abspath(folder))
            self.scan_patches()

    def browse_patch(self):
        initial_dir = self.entry_repo.get().strip() or self.current_dir
        file_path = filedialog.askopenfilename(
            title="Chọn file patch",
            initialdir=initial_dir,
            filetypes=[
                ("Patch Files", "*.patch *.diff"),
                ("All Files", "*.*"),
            ],
        )
        if file_path:
            abs_path = os.path.abspath(file_path)
            self.cbo_patch.set(abs_path)

    def log(self, text):
        self.txt_log.insert(tk.END, text + "\n")
        self.txt_log.see(tk.END)

    def clear_log(self):
        self.txt_log.delete("1.0", tk.END)

    def validate_inputs(self):
        repo = self.entry_repo.get().strip()
        patch = self.cbo_patch.get().strip()

        if not repo or not os.path.isdir(repo):
            messagebox.showerror("Lỗi", "Thư mục code không hợp lệ.")
            return None, None

        if not patch or not os.path.isfile(patch):
            messagebox.showerror(
                "Lỗi", "Không tìm thấy file patch được chọn."
            )
            return None, None

        return repo, patch

    def run_command(self, cmd, cwd):
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True,
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return -1, "", str(e)

    def check_patch(self):
        repo, patch = self.validate_inputs()
        if not repo or not patch:
            return

        self.log(f"\n--- Đang kiểm tra: {os.path.basename(patch)} ---")

        if shutil.which("git"):
            cmd = f'git apply --check "{patch}"'
            code, out, err = self.run_command(cmd, repo)
            if code == 0:
                self.log("[OK] Patch khớp hoàn toàn với code hiện tại. Sẵn sàng Apply!")
            else:
                self.log("[LỖI] Có xung đột hoặc lệch dòng với code hiện tại:")
                if err:
                    self.log(err.strip())
                if out:
                    self.log(out.strip())
        else:
            cmd = f'patch --dry-run -p1 < "{patch}"'
            code, out, err = self.run_command(cmd, repo)
            if code == 0:
                self.log("[OK] Kiểm tra hoàn tất, patch sẵn sàng áp dụng.")
            else:
                self.log(err.strip() or out.strip())

    def apply_patch(self):
        repo, patch = self.validate_inputs()
        if not repo or not patch:
            return

        self.log(f"\n--- Đang thực thi Apply: {os.path.basename(patch)} ---")

        if shutil.which("git"):
            cmd = f'git apply "{patch}"'
            code, out, err = self.run_command(cmd, repo)
            if code == 0:
                self.log("[THÀNH CÔNG] Đã cập nhật mã nguồn qua patch thành công!")
                messagebox.showinfo("Thành công", "Đã áp dụng patch vào code thành công!")
            else:
                self.log("[THẤT BẠI] Không thể áp dụng patch:")
                if err:
                    self.log(err.strip())
                if out:
                    self.log(out.strip())
        else:
            cmd = f'patch -p1 < "{patch}"'
            code, out, err = self.run_command(cmd, repo)
            if code == 0:
                self.log("[THÀNH CÔNG] Đã cập nhật mã nguồn!")
                messagebox.showinfo("Thành công", "Đã áp dụng patch thành công!")
            else:
                self.log(err.strip() or out.strip())


if __name__ == "__main__":
    root = tk.Tk()
    app = PatchToolApp(root)
    root.mainloop()
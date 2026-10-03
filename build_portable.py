"""
build_portable.py — Dựng bản PORTABLE của dự án (ADB-THTG / LD Macro Studio):
mang theo Python + thư viện ngay trong thư mục dự án, để chép sang máy mới
CHƯA CÀI PYTHON vẫn chạy được, hiệu năng y hệt (vẫn là CPython + cv2/numpy/
numba thật, không phải bản dịch/đóng băng như PyInstaller).

VÌ SAO KHÔNG DÙNG PyInstaller: dashboard_tasks.py mở LD Macro Studio bằng
subprocess.Popen([sys.executable, "main.py"]) - khi đóng thành .exe thì
sys.executable là chính file .exe và main.py không còn là file rời nên nút
"Tạo Hoạt Động" sẽ hỏng; ngoài ra pynput (hook bàn phím/chuột) rất hay bị
antivirus báo nhầm với bản .exe đóng băng.

CÁCH DÙNG (chạy trên 1 máy Windows ĐÃ cài Python, đặt file này ở THƯ MỤC GỐC
dự án, cạnh dashboard.py/main.py):

    python build_portable.py                    dựng thư mục python/ + .bat
    python build_portable.py --zip              ... rồi nén cả bộ để mang đi
    python build_portable.py --zip --tai-vc-redist
    python build_portable.py --lam-lai          xoá python/ dựng lại từ đầu
    python build_portable.py --nguon D:\\build\\python   dùng Python ở đường dẫn khác

Script làm lần lượt:
  1) Tạo requirements.txt nếu chưa có (KHÔNG ghi đè nếu đã có).
  2) Chép bản Python đang chạy script (hoặc --nguon) vào python/ - bỏ Doc,
     Scripts, include, libs, Lib/test, __pycache__ và TOÀN BỘ site-packages
     cũ (để không kéo theo thư viện thừa của máy này).
  3) Cài thư viện vào python/ bằng chính Python portable đó (cần Internet).
  4) Chép Tesseract-OCR từ máy này vào Tesseract-OCR/ nếu tìm thấy.
  5) Tạo Chay_Dashboard.bat, Chay_MacroStudio.bat, Chay_Dashboard_Xem_Loi.bat.
  6) Kiểm tra nhanh: tkinter, cv2, numpy, PIL, pynput, psutil, pywin32,
     pytesseract, numba + biên dịch thử mọi file .py của dự án.
  7) (--zip) nén cả bộ vào xuat_portable/ADB-THTG_portable_<ngày giờ>.zip.

YÊU CẦU Python NGUỒN: bản cài bình thường từ python.org (có tcl/tk), 64-bit.
KHÔNG dùng được: bản Microsoft Store (nằm trong WindowsApps, không chép được),
bản "embeddable" (không có tkinter), hay venv (không di chuyển được).

KHÔNG có trong gói .zip (cố ý - mỗi máy tự sinh/riêng theo máy): data/
window_geometry.json, run_state_today.json, dashboard_settings.json,
config.json, autosave_kichban.json, mọi *.bak/*.tmp/*.corrupted, logs/, .git/.

Máy mới vẫn phải cài riêng LDPlayer (không đóng gói được).
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
PY_DIR = os.path.join(ROOT, "python")
TESS_DIR = os.path.join(ROOT, "Tesseract-OCR")
OUT_DIR = os.path.join(ROOT, "xuat_portable")
REQ_PATH = os.path.join(ROOT, "requirements.txt")

# Thư viện bên thứ ba đúng theo import thật trong dự án (quét bằng AST).
# numba: tuỳ chọn về kỹ thuật nhưng thiếu thì bot 2048 rơi về solver Python
# chậm - để giữ đúng hiệu năng nên vẫn cài.
REQUIREMENTS = """opencv-python
numpy
Pillow
pynput
psutil
pywin32
pytesseract
numba
"""

# Thư mục cấp cao của bản Python cài đặt KHÔNG cần khi chạy.
TOP_SKIP = {"doc", "scripts", "tools", "include", "libs"}

ZIP_PREFIX = "ADB-THTG"
ZIP_SKIP_TOP_DIRS = {".git", "xuat_portable", "xuat_dong_bo", "logs", ".idea", ".vscode"}
ZIP_SKIP_REL_FILES = {
    "data/window_geometry.json",
    "data/run_state_today.json",
    "data/dashboard_settings.json",
    "data/config.json",
    "data/autosave_kichban.json",
}
ZIP_SKIP_SUFFIX = (".bak", ".tmp", ".corrupted")

VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"

SMOKE = r'''
import sys, glob
ok = True
def t(name, fn):
    global ok
    try:
        fn(); print("  OK   ", name)
    except Exception as e:
        ok = False; print("  LOI  ", name, "->", type(e).__name__, e)
def tk():
    import tkinter
    r = tkinter.Tk(); r.destroy()
t("tkinter (mo thu cua so)", tk)
for m in ("cv2", "numpy", "PIL", "pynput", "psutil", "win32gui", "win32con",
          "win32process", "pytesseract", "numba"):
    t(m, lambda m=m: __import__(m))
def comp():
    for f in glob.glob("*.py"):
        compile(open(f, encoding="utf-8").read(), f, "exec")
t("bien dich thu toan bo *.py cua du an", comp)
sys.exit(0 if ok else 1)
'''


def buoc(msg):
    print(f"\n▶ {msg}")


def loi(msg):
    print(f"✖ {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
def tao_requirements():
    if os.path.exists(REQ_PATH):
        print("  requirements.txt đã có - giữ nguyên, không ghi đè.")
        return
    with open(REQ_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(REQUIREMENTS)
    print("  Đã tạo requirements.txt")


def _kiem_tra_nguon(src):
    if "windowsapps" in src.lower():
        loi("Python bản Microsoft Store không chép được. Hãy cài Python từ python.org "
            "rồi chạy lại (hoặc dùng --nguon trỏ tới bản đó).")
    thieu = [p for p in ("python.exe", "pythonw.exe", "Lib", "DLLs", "tcl")
             if not os.path.exists(os.path.join(src, p))]
    if thieu:
        loi(f"Thư mục Python nguồn '{src}' không giống bản cài chuẩn, thiếu: "
            f"{', '.join(thieu)}. (Bản embeddable/venv không dùng được; khi cài Python "
            f"hãy giữ tick 'tcl/tk and IDLE'.)")
    if not os.path.exists(os.path.join(src, "DLLs", "_tkinter.pyd")):
        loi("Bản Python nguồn không có tkinter (DLLs/_tkinter.pyd). Cài lại có tcl/tk.")


def _ignore(src_root):
    def f(dirpath, names):
        rel = os.path.relpath(dirpath, src_root).replace("\\", "/")
        skip = {n for n in names if n == "__pycache__"}
        if rel == ".":
            skip |= {n for n in names if n.lower() in TOP_SKIP}
        elif rel.lower() == "lib":
            skip |= {n for n in names if n.lower() in ("test", "site-packages")}
        return skip
    return f


def dung_python(nguon, lam_lai):
    src = os.path.abspath(nguon or sys.base_prefix)
    da_la_chinh_no = os.path.abspath(PY_DIR) == src
    if os.path.isdir(PY_DIR) and lam_lai:
        if da_la_chinh_no:
            loi("Đang chạy bằng chính python/ nên không thể --lam-lai. Chạy bằng Python cài "
                "ngoài để dựng lại.")
        print("  --lam-lai: xoá python/ cũ...")
        shutil.rmtree(PY_DIR)
    if os.path.isdir(PY_DIR):
        print("  python/ đã có - bỏ qua bước chép (dùng --lam-lai nếu muốn dựng lại từ đầu).")
    else:
        _kiem_tra_nguon(src)
        print(f"  Chép Python từ: {src}")
        shutil.copytree(src, PY_DIR, ignore=_ignore(src))
        os.makedirs(os.path.join(PY_DIR, "Lib", "site-packages"), exist_ok=True)
    py = os.path.join(PY_DIR, "python.exe")
    if not os.path.exists(py):
        loi("Không có python/python.exe sau khi chép.")
    return py


def cai_thu_vien(py):
    print("  Cài pip rồi thư viện vào python/ (cần Internet, có thể vài phút)...")
    try:
        subprocess.run([py, "-m", "ensurepip", "--upgrade"], check=True, cwd=ROOT)
        subprocess.run([py, "-m", "pip", "install", "--no-warn-script-location",
                        "--disable-pip-version-check", "-r", REQ_PATH], check=True, cwd=ROOT)
    except subprocess.CalledProcessError as e:
        loi(f"Cài thư viện thất bại (mã {e.returncode}). Kiểm tra Internet/phiên bản Python "
            f"rồi chạy lại.")


def chep_tesseract():
    if os.path.exists(os.path.join(TESS_DIR, "tesseract.exe")):
        print("  Tesseract-OCR/ đã có trong dự án.")
        return
    ung_vien = [r"C:\Program Files\Tesseract-OCR", r"C:\Program Files (x86)\Tesseract-OCR"]
    w = shutil.which("tesseract")
    if w:
        ung_vien.insert(0, os.path.dirname(w))
    for d in ung_vien:
        if os.path.exists(os.path.join(d, "tesseract.exe")):
            print(f"  Chép Tesseract-OCR từ: {d}")
            shutil.copytree(d, TESS_DIR)
            break
    else:
        print("  ⚠ Không tìm thấy Tesseract-OCR trên máy này. Bước OCR ở máy mới sẽ báo thiếu - "
              "cài Tesseract (UB-Mannheim) rồi chép thư mục cài đặt thành Tesseract-OCR/ cạnh "
              "dashboard.py.")
        return
    td = os.path.join(TESS_DIR, "tessdata")
    if os.path.isdir(td):
        langs = sorted(os.path.splitext(f)[0] for f in os.listdir(td) if f.endswith(".traineddata"))
        print(f"  Ngôn ngữ OCR kèm theo: {', '.join(langs) or '(không có)'}")


def tao_bat():
    bat = {
        "Chay_Dashboard.bat":
            '@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0python\\pythonw.exe" "%~dp0dashboard.py"\r\n',
        "Chay_MacroStudio.bat":
            '@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0python\\pythonw.exe" "%~dp0main.py"\r\n',
        "Chay_Dashboard_Xem_Loi.bat":
            '@echo off\r\ncd /d "%~dp0"\r\n"%~dp0python\\python.exe" "%~dp0dashboard.py"\r\npause\r\n',
    }
    for ten, nd in bat.items():
        with open(os.path.join(ROOT, ten), "w", encoding="ascii", newline="") as f:
            f.write(nd)
        print(f"  Đã tạo {ten}")


def tai_vc_redist():
    dst = os.path.join(ROOT, "vc_redist.x64.exe")
    if os.path.exists(dst):
        print("  vc_redist.x64.exe đã có.")
        return
    try:
        print("  Tải Visual C++ Redistributable...")
        urllib.request.urlretrieve(VC_REDIST_URL, dst)
        print("  Đã tải vc_redist.x64.exe (máy mới chưa có VC++ thì chạy file này 1 lần).")
    except Exception as e:
        print(f"  ⚠ Không tải được vc_redist ({e}). Tự tải tại {VC_REDIST_URL}")


def kiem_tra(py):
    r = subprocess.run([py, "-c", SMOKE], cwd=ROOT)
    return r.returncode == 0


def nen_zip():
    os.makedirs(OUT_DIR, exist_ok=True)
    zip_path = os.path.join(OUT_DIR, f"ADB-THTG_portable_{datetime.now():%Y-%m-%d_%H%M%S}.zip")
    n = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for cur, dirs, files in os.walk(ROOT):
            rel_dir = os.path.relpath(cur, ROOT).replace("\\", "/")
            trong_python = rel_dir == "python" or rel_dir.startswith("python/")
            if rel_dir == ".":
                dirs[:] = [d for d in dirs if d not in ZIP_SKIP_TOP_DIRS]
            # __pycache__ của dự án: bỏ (máy nào tự sinh). Trong python/ thì GIỮ
            # để lần chạy đầu ở máy mới nhanh hơn (.pyc không phụ thuộc đường dẫn).
            dirs[:] = [d for d in dirs if d != "__pycache__" or trong_python]
            for fn in files:
                if fn.endswith(ZIP_SKIP_SUFFIX):
                    continue
                rel = (fn if rel_dir == "." else f"{rel_dir}/{fn}")
                if rel in ZIP_SKIP_REL_FILES:
                    continue
                zf.write(os.path.join(cur, fn), f"{ZIP_PREFIX}/{rel}")
                n += 1
    mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"  Đã nén {n} file -> {zip_path} ({mb:.0f} MB)")
    return zip_path


def main(argv=None):
    p = argparse.ArgumentParser(description="Dựng bản portable (kèm Python) cho ADB-THTG.")
    p.add_argument("--nguon", help="Thư mục cài Python nguồn (mặc định: Python đang chạy script).")
    p.add_argument("--lam-lai", action="store_true", help="Xoá python/ rồi dựng lại từ đầu.")
    p.add_argument("--khong-cai-thu-vien", action="store_true",
                   help="Bỏ qua cài thư viện + kiểm tra nhanh (chỉ chép Python/tạo .bat).")
    p.add_argument("--tai-vc-redist", action="store_true", help="Tải kèm vc_redist.x64.exe.")
    p.add_argument("--zip", action="store_true", help="Nén cả bộ vào xuat_portable/.")
    a = p.parse_args(sys.argv[1:] if argv is None else argv)

    buoc("1/6 requirements.txt")
    tao_requirements()
    buoc("2/6 Dựng thư mục python/")
    py = dung_python(a.nguon, a.lam_lai)
    if a.khong_cai_thu_vien:
        buoc("3/6 Cài thư viện: BỎ QUA (--khong-cai-thu-vien)")
    else:
        buoc("3/6 Cài thư viện vào python/")
        cai_thu_vien(py)
    buoc("4/6 Tesseract-OCR")
    chep_tesseract()
    buoc("5/6 File .bat khởi chạy")
    tao_bat()
    if a.tai_vc_redist:
        tai_vc_redist()
    ket_qua = True
    if not a.khong_cai_thu_vien:
        buoc("6/6 Kiểm tra nhanh bằng Python portable")
        ket_qua = kiem_tra(py)
        if not ket_qua:
            print("  ⚠ Có mục LỖI ở trên - sửa trước khi mang sang máy khác (đừng nén/đem đi vội).")
    if a.zip:
        if ket_qua:
            buoc("Nén cả bộ")
            nen_zip()
        else:
            print("\n⚠ Bỏ qua bước nén vì kiểm tra nhanh còn lỗi.")
    print("\n" + "=" * 60)
    print("XONG. Ở MÁY MỚI: giải nén -> (nếu máy chưa có VC++) chạy vc_redist.x64.exe 1 lần ->")
    print("cài LDPlayer -> bấm Chay_Dashboard.bat. Nếu không lên, bấm")
    print("Chay_Dashboard_Xem_Loi.bat để thấy thông báo lỗi.")
    print("=" * 60)
    return 0 if ket_qua else 1


if __name__ == "__main__":
    sys.exit(main())

"""
build_installer.py — Dựng FILE CÀI ĐẶT (Setup.exe) cho ADB-THTG / LD Macro Studio.

Máy đích KHÔNG cần cài sẵn Python, hiệu năng y hệt (vẫn là CPython + cv2/numpy/numba thật).
Để bộ cài NHẸ (vài MB), các thành phần sau KHÔNG đóng gói mà TỰ TẢI lúc cài bằng
Tai_Them_Thanh_Phan.bat (+ setup_extras.py):
  - Python 3.10 đầy đủ (có tkinter) cài im lặng vào <thư mục cài>\\python + `pip install -r
    requirements.txt` (thêm --kem-python nếu muốn đóng gói sẵn python/ như build_portable.py)
  - Android platform-tools (adb.exe)
  - Tesseract-OCR + gói ngôn ngữ vie/eng
  - Visual C++ Redistributable x64 (chỉ khi máy chưa có)
LDPlayer vẫn phải cài riêng (không đóng gói được).

CÁCH DÙNG (chạy trên máy Windows ĐÃ cài Python + Inno Setup 6.3+, đặt file này
ở THƯ MỤC GỐC dự án, cạnh dashboard.py):

    python build_installer.py                   hiện hộp thoại tick chọn dữ liệu
    python build_installer.py --preset chi_kich_ban
    python build_installer.py --chon kich_ban,anh_mau,hoat_dong
    python build_installer.py --liet-ke         xem các nhóm dữ liệu/preset
    python build_installer.py --khong-bien-dich chỉ sinh installer.iss + thư mục
                                                tạm (tự mở .iss bằng Inno Setup)

Kết quả: xuat_cai_dat/ADB-THTG_Setup_<ngày>.exe

Các bước:
  1) Chọn dữ liệu đưa vào bộ cài (dùng lại đúng các nhóm của dong_goi_dong_bo.py:
     Kịch bản, Nhóm Ngoài, Hoạt Động, Ảnh mẫu, Tài khoản, Lịch Hẹn Giờ...).
     Nhóm không chọn thì máy đích bắt đầu trống phần đó.
  2) Mặc định bỏ qua (máy đích tự tải Python). Chỉ khi --kem-python mới dựng python/ +
     cài thư viện (dùng lại build_portable.py; đã có thì giữ).
  3) Gom mã nguồn + dữ liệu đã chọn vào xuat_cai_dat/stage/.
  4) Sinh installer.iss rồi gọi ISCC.exe (Inno Setup) biên dịch.

Hành vi của bộ cài ở máy đích:
  - Cài vào %LocalAppData%\\Programs\\ADB-THTG (thư mục người dùng ghi được - app
    ghi data/logs ngay trong thư mục cài nên KHÔNG cài vào Program Files).
  - Có ô tick "Tải ADB/Tesseract/VC++ (cần Internet)" mặc định bật; hỏi quyền quản
    trị (UAC) khi cài Tesseract/VC++. Mạng rớt thì chạy lại shortcut
    "Tải thêm thành phần" trong Start Menu.
  - Cài đè bản mới KHÔNG ghi đè tasks/groups/templates/data đã có trên máy đích
    (người dùng đã sửa) - chỉ chép nếu chưa có; mã nguồn .py thì được cập nhật.
  - Gỡ cài đặt xoá python/, platform-tools/, Tesseract-OCR/, logs/; GIỮ dữ liệu
    người dùng (tasks/groups/templates/data) nếu còn file.
"""
import argparse
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime

import build_portable as bp
import dong_goi_dong_bo as dg

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "xuat_cai_dat")
APP_NAME = "ADB-THTG"
APP_PUBLISHER = "ADB-THTG"
# AppId cố định (suy từ tên) để lần cài sau nhận ra là CÙNG ứng dụng và cài đè/nâng cấp.
APP_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "adb-thtg.installer")).upper()

# File .py KHÔNG đưa vào bộ cài (công cụ dựng bộ cài cần Python nguồn của máy dev).
KHONG_CHEP_PY = {"build_installer.py", "build_portable.py"}
# File .py BẮT BUỘC có (thiếu thì bộ cài hỏng).
BAT_BUOC_PY = ("dashboard.py", "main.py", "setup_extras.py")

# Thư mục rỗng luôn tạo ở máy đích (app ghi vào đây).
THU_MUC_RONG = ("data", "tasks", "groups", "templates", "logs")

ISCC_UNG_VIEN = (
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
)

# Python tải về trên máy đích: dùng bộ cài ĐẦY ĐỦ (có tkinter - bản "embeddable" KHÔNG có
# tkinter nên không chạy được Dashboard), cài im lặng vào <thư mục cài>\python, không đụng
# PATH/Python khác của máy. 3.10.11 là bản 3.10 cuối cùng có bộ cài .exe.
PY_VERSION = "3.10.11"
PY_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-amd64.exe"

# Script chạy ở máy đích (cả lúc cài lẫn khi bấm "Tải thêm thành phần" trong Start Menu):
# làm tuần tự Python -> thư viện (pip) -> ADB/Tesseract/VC++; bước nào đã có thì bỏ qua.
# `/auto` (bộ cài gọi) = xong thì tự đóng; không có /auto thì dừng chờ bấm phím.
BAT_TAI_THANH_PHAN = (
    "@echo off\r\n"
    "setlocal\r\n"
    'cd /d "%~dp0"\r\n'
    f'set "PYURL={PY_URL}"\r\n'
    'set "TMPEXE=%TEMP%\\thtg_python_setup.exe"\r\n'
    "echo ============================================================\r\n"
    "echo  TAI THANH PHAN CON THIEU (can Internet)\r\n"
    "echo ============================================================\r\n"
    "echo.\r\n"
    "echo [1/3] Python\r\n"
    'if exist "%~dp0python\\python.exe" if exist "%~dp0python\\pythonw.exe" goto :pyok\r\n'
    f"echo   Dang tai Python {PY_VERSION} ...\r\n"
    'powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference=\'SilentlyContinue\'; '
    "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; "
    "Invoke-WebRequest -UseBasicParsing -Uri '%PYURL%' -OutFile '%TMPEXE%'\"\r\n"
    "if errorlevel 1 goto :loi\r\n"
    "echo   Dang cai Python vao thu muc rieng, khong anh huong Python khac tren may ...\r\n"
    'start /wait "" "%TMPEXE%" /quiet InstallAllUsers=0 TargetDir="%~dp0python" '
    "Include_launcher=0 Include_test=0 Include_doc=0 Shortcuts=0 PrependPath=0 AssociateFiles=0\r\n"
    'del "%TMPEXE%" >nul 2>&1\r\n'
    'if not exist "%~dp0python\\python.exe" goto :loi\r\n'
    '"%~dp0python\\python.exe" -c "import tkinter" >nul 2>&1\r\n'
    "if errorlevel 1 goto :loi\r\n"
    "echo   Da cai Python.\r\n"
    "goto :pip\r\n"
    ":pyok\r\n"
    "echo   Da co Python - bo qua.\r\n"
    ":pip\r\n"
    "echo.\r\n"
    "echo [2/3] Thu vien Python: opencv, numpy, numba ... (co the mat vai phut)\r\n"
    '"%~dp0python\\python.exe" -m pip install --no-warn-script-location '
    '--disable-pip-version-check -r "%~dp0requirements.txt"\r\n'
    "if errorlevel 1 goto :loi\r\n"
    "echo.\r\n"
    "echo [3/3] ADB, Tesseract-OCR, Visual C++\r\n"
    '"%~dp0python\\python.exe" "%~dp0setup_extras.py" --khong-doi\r\n'
    "if errorlevel 1 goto :loi\r\n"
    "echo.\r\n"
    "echo HOAN TAT.\r\n"
    'if /i not "%~1"=="/auto" pause\r\n'
    "exit /b 0\r\n"
    ":loi\r\n"
    "echo.\r\n"
    "echo CO LOI (thuong do mang). Khi co mang, chay lai Tai them thanh phan trong Start Menu.\r\n"
    "pause\r\n"
    "exit /b 1\r\n"
)

BAT_NOI_DUNG = {
    "Chay_Dashboard.bat":
        '@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0python\\pythonw.exe" "%~dp0dashboard.py"\r\n',
    "Chay_MacroStudio.bat":
        '@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0python\\pythonw.exe" "%~dp0main.py"\r\n',
    "Chay_Dashboard_Xem_Loi.bat":
        '@echo off\r\ncd /d "%~dp0"\r\n"%~dp0python\\python.exe" "%~dp0dashboard.py"\r\npause\r\n',
    "Tai_Them_Thanh_Phan.bat": BAT_TAI_THANH_PHAN,
}


def buoc(msg):
    print(f"\n▶ {msg}")


def loi(msg):
    print(f"✖ {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
def tim_iscc():
    w = shutil.which("iscc") or shutil.which("ISCC.exe")
    if w:
        return w
    for p in ISCC_UNG_VIEN:
        if os.path.exists(p):
            return p
    return None


def _dung_dau_cham(n):
    return f"{n / (1024 * 1024):.1f} MB"


def gom_stage(stage, chon):
    """Gom mã nguồn + dữ liệu đã chọn vào `stage`. Trả về dict thống kê."""
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)
    tk = {"py": 0, "tasks": 0, "groups": 0, "templates": 0, "data": 0, "bytes": 0}
    # --- mã nguồn ---
    for fn in sorted(os.listdir(ROOT)):
        if fn.endswith(".py") and fn not in KHONG_CHEP_PY:
            shutil.copy2(os.path.join(ROOT, fn), os.path.join(stage, fn))
            tk["py"] += 1
    for fn in BAT_BUOC_PY:
        if not os.path.exists(os.path.join(stage, fn)):
            loi(f"Thiếu file bắt buộc: {fn}. Đặt build_installer.py ở THƯ MỤC GỐC dự án.")
    bo_sung_requirements()
    shutil.copy2(bp.REQ_PATH, os.path.join(stage, "requirements.txt"))
    for ten, nd in BAT_NOI_DUNG.items():
        with open(os.path.join(stage, ten), "w", encoding="ascii", newline="") as f:
            f.write(nd)

    # --- dữ liệu theo nhóm đã chọn (dùng lại logic của dong_goi_dong_bo) ---
    def chep(abs_path, rel_path, khoa):
        dst = os.path.join(stage, rel_path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(abs_path, dst)
        tk[khoa] += 1
        tk["bytes"] += os.path.getsize(abs_path)

    if "kich_ban" in chon:
        for a, r in dg._iter_files(dg.TASKS_DIR, allowed_exts=(".json",)):
            chep(a, r, "tasks")
    if "nhom_ngoai" in chon:
        for a, r in dg._iter_files(dg.GROUPS_DIR, allowed_exts=(".json",)):
            chep(a, r, "groups")
    if "anh_mau" in chon:
        for a, r in dg._iter_files(dg.TEMPLATES_DIR, allowed_exts=dg.IMAGE_EXTS):
            chep(a, r, "templates")
    thieu = []
    for fname in dg._data_files_cua(chon):
        a = os.path.join(dg.DATA_DIR, fname)
        if os.path.exists(a):
            chep(a, os.path.join("data", fname), "data")
        else:
            thieu.append(fname)
    tk["thieu_data"] = thieu
    return tk


def _q(p):
    """Đường dẫn trong .iss: dùng dấu \\ (Windows) và bao trong ngoặc kép."""
    return '"' + p.replace("/", "\\") + '"'


def viet_iss(iss_path, stage, py_dir, co_python, version, out_dir):
    L = []
    a = L.append
    a("; File này do build_installer.py sinh ra - sửa build_installer.py rồi dựng lại, đừng sửa tay.")
    a("[Setup]")
    a(f"AppId={{{{{APP_ID}}}")
    a(f"AppName={APP_NAME}")
    a(f"AppVersion={version}")
    a(f"AppPublisher={APP_PUBLISHER}")
    a(r"DefaultDirName={autopf}\ADB-THTG")
    a("DefaultGroupName=ADB-THTG")
    a("PrivilegesRequired=lowest")
    a("ArchitecturesAllowed=x64compatible")
    a("ArchitecturesInstallIn64BitMode=x64compatible")
    a(f"OutputDir={out_dir.replace('/', chr(92))}")
    a(f"OutputBaseFilename={APP_NAME}_Setup_{version.replace('.', '')}")
    a("Compression=lzma2/max")
    a("SolidCompression=yes")
    a("DisableProgramGroupPage=yes")
    a("WizardStyle=modern")
    a("UsePreviousAppDir=yes")
    a(r"UninstallDisplayIcon={app}\python\pythonw.exe")
    a("")
    a("[Languages]")
    a('Name: "english"; MessagesFile: "compiler:Default.isl"')
    a("")
    a("[Tasks]")
    a('Name: "extras"; Description: "Tải thành phần còn thiếu: Python, thư viện, ADB, Tesseract-OCR, '
      'Visual C++ (cần Internet)"; Flags: checkedonce')
    a('Name: "desktopicon"; Description: "Tạo biểu tượng Dashboard ngoài Desktop"; Flags: unchecked')
    a("")
    a("[Dirs]")
    for d in THU_MUC_RONG:
        a(f'Name: "{{app}}\\{d}"')
    a("")
    a("[Files]")
    # Mã nguồn + .bat: luôn cập nhật khi cài đè.
    a(f'Source: {_q(os.path.join(stage, "*.py"))}; DestDir: "{{app}}"; Flags: ignoreversion')
    a(f'Source: {_q(os.path.join(stage, "*.bat"))}; DestDir: "{{app}}"; Flags: ignoreversion')
    a(f'Source: {_q(os.path.join(stage, "requirements.txt"))}; DestDir: "{{app}}"; Flags: ignoreversion')
    # Dữ liệu người dùng: chỉ chép nếu máy đích chưa có, và gỡ cài đặt không xoá.
    for d in ("data", "tasks", "groups", "templates"):
        if os.path.isdir(os.path.join(stage, d)):
            a(f'Source: {_q(os.path.join(stage, d, "*"))}; DestDir: "{{app}}\\{d}"; '
              f'Flags: onlyifdoesntexist recursesubdirs createallsubdirs uninsneveruninstall')
    if co_python:
        a(f'Source: {_q(os.path.join(py_dir, "*"))}; DestDir: "{{app}}\\python"; '
          f'Flags: ignoreversion recursesubdirs createallsubdirs')
    a("")
    a("[Icons]")
    a('Name: "{group}\\ADB-THTG Dashboard"; Filename: "{app}\\python\\pythonw.exe"; '
      'Parameters: """{app}\\dashboard.py"""; WorkingDir: "{app}"')
    a('Name: "{group}\\LD Macro Studio"; Filename: "{app}\\python\\pythonw.exe"; '
      'Parameters: """{app}\\main.py"""; WorkingDir: "{app}"')
    a('Name: "{group}\\Dashboard (xem lỗi)"; Filename: "{app}\\Chay_Dashboard_Xem_Loi.bat"; WorkingDir: "{app}"')
    a('Name: "{group}\\Tải thêm thành phần (ADB, OCR, VC++)"; Filename: "{app}\\Tai_Them_Thanh_Phan.bat"; WorkingDir: "{app}"')
    a('Name: "{group}\\Gỡ cài đặt ADB-THTG"; Filename: "{uninstallexe}"')
    a('Name: "{autodesktop}\\ADB-THTG Dashboard"; Filename: "{app}\\python\\pythonw.exe"; '
      'Parameters: """{app}\\dashboard.py"""; WorkingDir: "{app}"; Tasks: desktopicon')
    a("")
    a("[Run]")
    a('Filename: "{app}\\Tai_Them_Thanh_Phan.bat"; Parameters: "/auto"; '
      'WorkingDir: "{app}"; StatusMsg: "Đang tải Python, thư viện, ADB, Tesseract-OCR, Visual C++..."; '
      'Tasks: extras; Flags: waituntilterminated')
    a('Filename: "{app}\\python\\pythonw.exe"; Parameters: """{app}\\dashboard.py"""; WorkingDir: "{app}"; '
      'Description: "Mở ADB-THTG Dashboard"; Flags: postinstall nowait skipifsilent unchecked')
    a("")
    a("[UninstallDelete]")
    for d in ("python", "platform-tools", "Tesseract-OCR", "logs", "__pycache__"):
        a(f'Type: filesandordirs; Name: "{{app}}\\{d}"')
    a("")
    with open(iss_path, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write("\n".join(L))


def _ten_goi(dong):
    """'Pillow>=9' -> 'pillow' (bỏ phiên bản/chú thích để so tên gói)."""
    d = dong.split("#", 1)[0].strip()
    for i, c in enumerate(d):
        if c in "<>=!~[; ":
            d = d[:i]
            break
    return d.lower().replace("_", "-")


def bo_sung_requirements():
    """build_portable.tao_requirements() GIỮ NGUYÊN requirements.txt đã có, nên file
    cũ thiếu gói (vd pymunk) thì pip bỏ sót. Ở đây chỉ THÊM các gói còn thiếu so với
    bp.REQUIREMENTS (không xoá/không đổi dòng nào của người dùng). Trả về danh sách gói đã thêm."""
    bp.tao_requirements()
    with open(bp.REQ_PATH, "r", encoding="utf-8") as f:
        nd = f.read()
    co = {_ten_goi(x) for x in nd.splitlines() if _ten_goi(x)}
    them = [x.strip() for x in bp.REQUIREMENTS.splitlines()
            if x.strip() and _ten_goi(x) not in co]
    if them:
        with open(bp.REQ_PATH, "a", encoding="utf-8", newline="\n") as f:
            if nd and not nd.endswith("\n"):
                f.write("\n")
            f.write("\n".join(them) + "\n")
        print(f"  ⚠ requirements.txt cũ thiếu: {', '.join(them)} - đã thêm vào.")
    return them


def kiem_tra_python(py_dir):
    return os.path.exists(os.path.join(py_dir, "python.exe")) and \
        os.path.exists(os.path.join(py_dir, "pythonw.exe"))


def _doc_tham_so(argv):
    p = argparse.ArgumentParser(
        description="Dựng file cài đặt Setup.exe (Inno Setup) cho ADB-THTG. "
                    "Không truyền --chon/--preset thì hiện hộp thoại tick chọn dữ liệu.")
    p.add_argument("--chon", help="Nhóm dữ liệu đưa vào bộ cài, cách nhau dấu phẩy (xem --liet-ke).")
    p.add_argument("--preset", choices=list(dg.PRESETS), help="Chọn nhanh 1 bộ nhóm dựng sẵn.")
    p.add_argument("--console", action="store_true", help="Dùng menu chữ thay hộp thoại tick chọn.")
    p.add_argument("--liet-ke", action="store_true", help="Liệt kê nhóm/preset rồi thoát.")
    p.add_argument("--kem-python", action="store_true",
                   help="Đóng gói sẵn python/ + thư viện vào bộ cài (nặng hàng trăm MB, cài không cần mạng "
                        "cho phần Python). Mặc định: KHÔNG đóng gói, máy đích tự tải Python + thư viện.")
    p.add_argument("--nguon", help="Thư mục Python nguồn (mặc định: Python đang chạy script).")
    p.add_argument("--lam-lai", action="store_true", help="Xoá python/ rồi dựng lại từ đầu.")
    p.add_argument("--khong-dung-python", action="store_true",
                   help="Không đụng tới python/ (dùng nguyên bản đang có; thiếu thì bộ cài không có Python).")
    p.add_argument("--khong-bien-dich", action="store_true",
                   help="Chỉ sinh thư mục tạm + installer.iss, không gọi Inno Setup.")
    p.add_argument("--out", default=OUT_DIR, help="Thư mục xuất (mặc định xuat_cai_dat/).")
    return p.parse_args(argv)


def main(argv=None):
    a = _doc_tham_so(sys.argv[1:] if argv is None else argv)
    if a.liet_ke:
        dg._in_danh_sach_nhom()
        return 0
    if a.chon:
        chon = dg._chuan_hoa_chon([x.strip() for x in a.chon.split(",") if x.strip()])
    elif a.preset:
        chon = dg._chuan_hoa_chon(dg.PRESETS[a.preset][1])
    else:
        chon = dg.hoi_chon_nhom(dung_console=a.console)
        if chon is None:
            print("Đã huỷ - không dựng bộ cài.")
            return 1
        chon = dg._chuan_hoa_chon(chon)

    out_dir = os.path.abspath(a.out)
    stage = os.path.join(out_dir, "stage")
    iss = os.path.join(out_dir, "installer.iss")
    os.makedirs(out_dir, exist_ok=True)

    buoc("1/4 Dữ liệu đưa vào bộ cài")
    print("  " + ", ".join(dg._NHOM_TEN[k] for k in chon))
    for k in dg._NHOM_KEYS:
        if k not in chon:
            print(f"  (không đưa vào) {dg._NHOM_TEN[k]}")
    for cb in dg._canh_bao_chon(chon):
        print(f"  ⚠ Lưu ý: {cb}")

    if not a.kem_python:
        buoc("2/4 Python: KHÔNG đóng gói (máy đích tự tải)")
        print(f"  Máy đích tự tải Python {PY_VERSION} (có tkinter) + thư viện lúc cài -> bộ cài nhẹ, "
              f"cài lâu hơn và cần Internet. Thêm --kem-python để đóng gói sẵn.")
        bo_sung_requirements()
        co_python = False
    else:
        buoc("2/4 Python portable (python/) - đóng gói sẵn")
        py = os.path.join(bp.PY_DIR, "python.exe")
        if a.khong_dung_python:
            print("  --khong-dung-python: giữ nguyên python/ hiện có.")
        else:
            py = bp.dung_python(a.nguon, a.lam_lai)
            bo_sung_requirements()
            buoc("   Cài thư viện + kiểm tra nhanh")
            bp.cai_thu_vien(py)
            if not bp.kiem_tra(py):
                loi("Kiểm tra nhanh Python portable còn LỖI - sửa trước khi dựng bộ cài.")
        co_python = kiem_tra_python(bp.PY_DIR)
        if not co_python:
            print("  ⚠ Chưa có python/python.exe + pythonw.exe: bộ cài sẽ KHÔNG kèm Python "
                  "(máy đích vẫn tự tải được nếu bấm 'Tải thành phần còn thiếu').")

    buoc("3/4 Gom mã nguồn + dữ liệu vào thư mục tạm")
    tk = gom_stage(stage, chon)
    print(f"  {tk['py']} file .py | tasks {tk['tasks']} | groups {tk['groups']} | "
          f"ảnh mẫu {tk['templates']} | data {tk['data']} ({_dung_dau_cham(tk['bytes'])} dữ liệu)")
    if tk["thieu_data"]:
        print(f"  ⚠ Chưa có trong data/ (bỏ qua): {', '.join(tk['thieu_data'])}")

    buoc("4/4 Sinh installer.iss và biên dịch")
    version = datetime.now().strftime("%Y.%m.%d")
    viet_iss(iss, stage, bp.PY_DIR, co_python, version, out_dir)
    print(f"  Đã tạo {iss}")
    if a.khong_bien_dich:
        print("  --khong-bien-dich: mở installer.iss bằng Inno Setup rồi bấm Compile.")
        return 0
    iscc = tim_iscc()
    if not iscc:
        print("  ⚠ Không tìm thấy Inno Setup (ISCC.exe). Cài Inno Setup 6.3+ (miễn phí) tại "
              "https://jrsoftware.org/isdl.php rồi chạy lại, hoặc mở installer.iss bằng Inno Setup "
              "và bấm Compile.")
        return 1
    print(f"  Biên dịch bằng: {iscc} (vài phút nếu python/ lớn)")
    r = subprocess.run([iscc, iss])
    if r.returncode != 0:
        loi(f"Inno Setup báo lỗi (mã {r.returncode}). Xem thông báo ở trên.")
    exe = [f for f in os.listdir(out_dir) if f.startswith(APP_NAME + "_Setup_") and f.endswith(".exe")]
    exe.sort(key=lambda f: os.path.getmtime(os.path.join(out_dir, f)))
    if exe:
        p = os.path.join(out_dir, exe[-1])
        print("\n" + "=" * 60)
        print(f"✔ Đã tạo bộ cài: {p} ({_dung_dau_cham(os.path.getsize(p))})")
        print("Mang file này sang máy mới, bấm đúp để cài (máy đích cần Internet + LDPlayer).")
        print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

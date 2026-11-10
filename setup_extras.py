"""
setup_extras.py — TỰ TẢI các thành phần bên ngoài cho bản cài đặt (ADB-THTG).

Bộ cài (build_installer.py) cố ý KHÔNG đóng gói các thứ này để file cài nhẹ:
  1) Android platform-tools (adb.exe)  -> <thư mục cài>/platform-tools/
  2) Tesseract-OCR (+ gói ngôn ngữ vie/eng) -> <thư mục cài>/Tesseract-OCR/
  3) Microsoft Visual C++ Redistributable x64 (chỉ khi máy chưa có)

Đúng vị trí mà adb_helper.py dò sẵn (`_project_root_dir()`/platform-tools/adb.exe
và /Tesseract-OCR/tesseract.exe) nên KHÔNG phải sửa gì ở adb_helper.py.

Bộ cài gọi script này bằng Python portable ngay sau khi chép file. Có thể chạy
lại bất cứ lúc nào (vd mạng rớt lúc cài) - thành phần nào đã có thì bỏ qua:

    python\\python.exe setup_extras.py                 tải các thành phần còn thiếu
    python\\python.exe setup_extras.py --force         tải lại tất cả
    python\\python.exe setup_extras.py --chi adb,ocr   chỉ làm vài thành phần
                                                       (adb | ocr | vc)
    python\\python.exe setup_extras.py --tesseract-url <url> --adb-url <url>
    python\\python.exe setup_extras.py --selftest      kiểm logic bằng server giả
                                                       (không cần Internet/Windows)

Chỉ dùng thư viện chuẩn của Python (urllib, zipfile, subprocess...) - không
import tkinter hay module nào của dự án nên chạy được trước cả khi dự án khởi động.
KHÔNG BAO GIỜ làm hỏng bản cài đang có: tải vào file tạm, kiểm tra xong mới
thay; một thành phần lỗi thì in cảnh báo và đi tiếp thành phần khác.
"""
import argparse
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))

ADB_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
# Bản Tesseract cho Windows 64-bit (link lấy từ trang wiki UB-Mannheim/tesseract).
# Nếu link này chết thì _tesseract_urls() tự hỏi GitHub API bản mới nhất;
# vẫn không được thì chạy lại với --tesseract-url <link tự tìm>.
TESSERACT_URL = ("https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/"
                 "tesseract-ocr-w64-setup-5.5.3.20260724.exe")
TESSERACT_API = "https://api.github.com/repos/tesseract-ocr/tesseract/releases/latest"
# Gói ngôn ngữ OCR dự án dùng (adb_helper.ocr_text_in_box mặc định lang="vie+eng").
TESSDATA_BASE = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/"
# Thử lần lượt: link github.com/.../raw rồi tới host raw.githubusercontent.com (dự phòng).
TESSDATA_BASES = (TESSDATA_BASE,
                  "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/")
OCR_LANGS = ("eng", "vie")
VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"

# Cỡ tối thiểu để coi 1 file tải về là hợp lệ (chống tải nhầm trang lỗi HTML).
MIN_ADB_ZIP = 1_000_000
MIN_TESS_EXE = 5_000_000
MIN_VC_EXE = 5_000_000
MIN_TRAINEDDATA = 100_000

USER_AGENT = "ADB-THTG-setup/1.0"


# ---------------------------------------------------------------------------
def log(msg=""):
    print(msg, flush=True)


def _hien_tien_do(da, tong, t0, nhan):
    mb = da / (1024 * 1024)
    if tong:
        pct = int(da * 100 / tong)
        s = f"\r  {nhan}: {pct:3d}%  ({mb:.1f}/{tong / (1024 * 1024):.1f} MB)"
    else:
        s = f"\r  {nhan}: {mb:.1f} MB"
    sys.stdout.write(s)
    sys.stdout.flush()


def _ssl_contexts():
    """Các ngữ cảnh SSL thử lần lượt: mặc định của hệ thống (None) rồi bộ chứng chỉ
    certifi (pip luôn mang theo). KHÔNG BAO GIỜ tắt kiểm tra chứng chỉ."""
    ds = [None]
    for mod in ("certifi", "pip._vendor.certifi"):
        try:
            m = __import__(mod, fromlist=["where"])
            ds.append(ssl.create_default_context(cafile=m.where()))
            break
        except Exception:
            continue
    return ds


def _la_loi_ssl(e):
    return ("CERTIFICATE_VERIFY_FAILED" in str(e)
            or isinstance(e, ssl.SSLError)
            or isinstance(getattr(e, "reason", None), ssl.SSLError))


def _mo_url(req, timeout):
    """urlopen có dự phòng: lỗi chứng chỉ SSL (kho chứng chỉ Windows thiếu CA gốc,
    phần mềm diệt virus chen vào HTTPS...) thì thử lại bằng bộ chứng chỉ certifi."""
    loi = None
    for ctx in _ssl_contexts():
        try:
            return urllib.request.urlopen(req, timeout=timeout, context=ctx)
        except Exception as e:
            loi = e
            if not _la_loi_ssl(e):
                raise
    raise loi


def _tai_powershell(url, dst, toi_thieu=0):
    """Dự phòng cuối khi Python không tin chứng chỉ: nhờ PowerShell tải (dùng kho chứng
    chỉ của Windows, tự lấy thêm CA gốc còn thiếu). Chỉ chạy trên Windows."""
    if os.name != "nt":
        return False
    tmp = dst + ".part"
    q = lambda x: x.replace("'", "''")
    script = ("$ProgressPreference='SilentlyContinue'; "
              "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; "
              f"Invoke-WebRequest -UseBasicParsing -Uri '{q(url)}' -OutFile '{q(tmp)}'")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-Command", script], timeout=900)
        if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) >= toi_thieu:
            os.replace(tmp, dst)
            return True
    except Exception as e:
        log(f"  [!] PowerShell tải lỗi: {e}")
    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass
    return False


def tai_ve(url, dst, toi_thieu=0, nhan="", so_lan=3, im=False):
    """Tải `url` về file `dst` (qua file tạm .part rồi mới đổi tên). Thử lại
    `so_lan` lần. Trả về True nếu tải xong và file >= `toi_thieu` byte."""
    nhan = nhan or os.path.basename(dst)
    loi_cuoi = None
    for lan in range(1, so_lan + 1):
        tmp = dst + ".part"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with _mo_url(req, 30) as r, open(tmp, "wb") as f:
                tong = int(r.headers.get("Content-Length") or 0)
                da, t0, moc = 0, time.time(), 0.0
                while True:
                    buf = r.read(256 * 1024)
                    if not buf:
                        break
                    f.write(buf)
                    da += len(buf)
                    if not im and time.time() - moc > 0.25:
                        _hien_tien_do(da, tong, t0, nhan)
                        moc = time.time()
                if not im:
                    _hien_tien_do(da, tong, t0, nhan)
                    sys.stdout.write("\n")
            kich_thuoc = os.path.getsize(tmp)
            if kich_thuoc < toi_thieu:
                raise IOError(f"file tải về quá nhỏ ({kich_thuoc} byte) - có thể là trang lỗi")
            os.replace(tmp, dst)
            return True
        except Exception as e:  # mạng rớt, 404, hết giờ...
            loi_cuoi = e
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            log(f"\n  [!] Tải {nhan} lần {lan}/{so_lan} lỗi: {type(e).__name__}: {e}")
            if _la_loi_ssl(e):  # thử lại bằng Python vô ích -> sang PowerShell
                log("  Lỗi chứng chỉ SSL - thử tải bằng PowerShell (kho chứng chỉ của Windows)...")
                if _tai_powershell(url, dst, toi_thieu):
                    return True
                break
            if lan < so_lan:
                time.sleep(2 * lan)
    log(f"  [LOI] Không tải được {nhan} từ {url} ({loi_cuoi})")
    return False


# ---------------------------------------------------------------------------
# 1) ADB (platform-tools)
# ---------------------------------------------------------------------------
def adb_co_san(root):
    return os.path.exists(os.path.join(root, "platform-tools", "adb.exe"))


def cai_adb(root, url=ADB_URL, force=False, im=False, toi_thieu=MIN_ADB_ZIP):
    log(">> ADB (Android platform-tools)")
    if adb_co_san(root) and not force:
        log("  Đã có platform-tools/adb.exe - bỏ qua.")
        return True
    with tempfile.TemporaryDirectory(prefix="thtg_adb_") as tmp:
        z = os.path.join(tmp, "platform-tools.zip")
        if not tai_ve(url, z, toi_thieu, "platform-tools", im=im):
            return False
        try:
            with zipfile.ZipFile(z) as zf:
                bad = zf.testzip()
                if bad:
                    raise zipfile.BadZipFile(f"file hỏng: {bad}")
                zf.extractall(os.path.join(tmp, "x"))
        except Exception as e:
            log(f"  [LOI] Giải nén platform-tools lỗi: {e}")
            return False
        src = os.path.join(tmp, "x", "platform-tools")
        if not os.path.exists(os.path.join(src, "adb.exe")):
            log("  [LOI] Gói tải về không có platform-tools/adb.exe.")
            return False
        dst = os.path.join(root, "platform-tools")
        if os.path.isdir(dst):
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)
    log("  [OK] Đã cài platform-tools/adb.exe")
    return True


# ---------------------------------------------------------------------------
# 2) Tesseract-OCR + ngôn ngữ
# ---------------------------------------------------------------------------
def tess_co_san(root):
    return os.path.exists(os.path.join(root, "Tesseract-OCR", "tesseract.exe"))


def _tesseract_urls(url_chi_dinh=None):
    """Danh sách link thử lần lượt: link chỉ định -> link ghim sẵn -> bản mới
    nhất hỏi qua GitHub API (phòng link ghim bị gỡ)."""
    ds = []
    if url_chi_dinh:
        ds.append(url_chi_dinh)
    ds.append(TESSERACT_URL)
    try:
        req = urllib.request.Request(TESSERACT_API, headers={"User-Agent": USER_AGENT})
        with _mo_url(req, 20) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        for a in data.get("assets", []):
            if re.match(r"tesseract-ocr-w64-setup-.*\.exe$", a.get("name", "")):
                u = a.get("browser_download_url")
                if u and u not in ds:
                    ds.append(u)
    except Exception:
        pass  # không có mạng tới API thì thôi, vẫn còn link ghim
    return ds


def cai_ngon_ngu(root, force=False, im=False, base=TESSDATA_BASES, toi_thieu=MIN_TRAINEDDATA):
    """Đảm bảo có đủ eng+vie trong Tesseract-OCR/tessdata (installer chỉ kèm
    sẵn tiếng Anh). `base` là 1 link hoặc nhiều link thử lần lượt. Trả về True nếu đủ."""
    bases = [base] if isinstance(base, str) else list(base)
    td = os.path.join(root, "Tesseract-OCR", "tessdata")
    os.makedirs(td, exist_ok=True)
    ok = True
    for lang in OCR_LANGS:
        f = os.path.join(td, f"{lang}.traineddata")
        if os.path.exists(f) and os.path.getsize(f) >= toi_thieu and not force:
            continue
        log(f"  Tải gói ngôn ngữ OCR '{lang}'...")
        if not any(tai_ve(b + f"{lang}.traineddata", f, toi_thieu, f"{lang}.traineddata", im=im)
                   for b in bases):
            ok = False
    return ok


def cai_tesseract(root, url=None, force=False, im=False, silent_runner=None,
                  toi_thieu=MIN_TESS_EXE, base_lang=TESSDATA_BASES):
    log(">> Tesseract-OCR")
    dst = os.path.join(root, "Tesseract-OCR")
    if tess_co_san(root) and not force:
        log("  Đã có Tesseract-OCR/tesseract.exe - kiểm tra gói ngôn ngữ.")
        return cai_ngon_ngu(root, False, im, base_lang)
    with tempfile.TemporaryDirectory(prefix="thtg_tess_") as tmp:
        exe = os.path.join(tmp, "tesseract-setup.exe")
        da_tai = False
        for u in _tesseract_urls(url):
            if tai_ve(u, exe, toi_thieu, "Tesseract-OCR", so_lan=2, im=im):
                da_tai = True
                break
        if not da_tai:
            return False
        log("  Cài Tesseract (chế độ im lặng, có thể hiện hộp xin quyền quản trị)...")
        chay = silent_runner or _chay_cai_im
        if not chay(exe, dst):
            log("  [LOI] Trình cài Tesseract báo lỗi.")
            return False
    if not tess_co_san(root):
        log("  [LOI] Cài xong nhưng không thấy Tesseract-OCR/tesseract.exe.")
        return False
    log("  [OK] Đã cài Tesseract-OCR")
    return cai_ngon_ngu(root, force, im, base_lang)


def _chay_nang_quyen(exe, tham_so, timeout=900):
    """Chạy `exe` với `tham_so` (CHUỖI dòng lệnh) và trả về mã thoát. Trình cài Tesseract/
    VC++ đòi quyền quản trị: chạy thường bị WinError 740 nên khi đó chạy lại bằng
    PowerShell `Start-Process -Verb RunAs` (hiện hộp UAC, người dùng bấm Yes)."""
    try:
        return subprocess.run(f'"{exe}" {tham_so}', timeout=timeout).returncode
    except OSError as e:
        if getattr(e, "winerror", None) != 740:
            raise
    log("  Cần quyền quản trị - bấm Yes ở hộp thoại Windows vừa hiện ra...")
    q = lambda x: x.replace("'", "''")
    script = (f"$p = Start-Process -FilePath '{q(exe)}' -ArgumentList '{q(tham_so)}' "
              f"-Verb RunAs -Wait -PassThru; exit $p.ExitCode")
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                           "-Command", script], timeout=timeout).returncode


def _chay_cai_im(exe, dst):
    """Chạy trình cài NSIS của Tesseract: /S = im lặng, /D=<thư mục> PHẢI là
    đối số CUỐI và KHÔNG có dấu nháy (quy ước của NSIS)."""
    try:
        return _chay_nang_quyen(exe, "/S /D=" + dst) == 0
    except Exception as e:
        log(f"  [LOI] Không chạy được trình cài: {e}")
        return False


# ---------------------------------------------------------------------------
# 3) Visual C++ Redistributable
# ---------------------------------------------------------------------------
def vc_da_cai():
    """True nếu máy đã có VC++ 2015-2022 x64 (không phải Windows -> coi như có)."""
    if os.name != "nt":
        return True
    try:
        import winreg
        for sub in (r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
                    r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub) as k:
                    if winreg.QueryValueEx(k, "Installed")[0] == 1:
                        return True
            except OSError:
                continue
    except Exception:
        pass
    return False


def cai_vc(url=VC_REDIST_URL, force=False, im=False, da_cai=None, runner=None,
           toi_thieu=MIN_VC_EXE):
    log(">> Microsoft Visual C++ Redistributable (x64)")
    co = vc_da_cai() if da_cai is None else da_cai
    if co and not force:
        log("  Máy đã có VC++ - bỏ qua.")
        return True
    with tempfile.TemporaryDirectory(prefix="thtg_vc_") as tmp:
        exe = os.path.join(tmp, "vc_redist.x64.exe")
        if not tai_ve(url, exe, toi_thieu, "vc_redist.x64", im=im):
            return False
        log("  Cài VC++ (có thể hiện hộp xin quyền quản trị)...")
        try:
            r = (runner or (lambda p: _chay_nang_quyen(p, "/install /quiet /norestart")))(exe)
        except Exception as e:
            log(f"  [LOI] Không chạy được trình cài VC++: {e}")
            return False
    # 0 = xong, 1638 = đã có bản mới hơn, 3010 = xong nhưng cần khởi động lại
    if r in (0, 1638, 3010):
        log("  [OK] VC++ sẵn sàng" + (" (nên khởi động lại máy)" if r == 3010 else ""))
        return True
    log(f"  [LOI] Trình cài VC++ trả mã {r}.")
    return False


# ---------------------------------------------------------------------------
def chay(root=ROOT, chi=("adb", "ocr", "vc"), force=False, adb_url=ADB_URL,
         tesseract_url=None, im=False):
    """Làm các thành phần trong `chi`. Trả về dict {tên: True/False}."""
    kq = {}
    if "vc" in chi:  # VC++ trước vì numba/opencv/Tesseract cần
        kq["vc"] = cai_vc(force=force, im=im)
    if "adb" in chi:
        kq["adb"] = cai_adb(root, adb_url, force, im)
    if "ocr" in chi:
        kq["ocr"] = cai_tesseract(root, tesseract_url, force, im)
    return kq


def _doc_tham_so(argv):
    p = argparse.ArgumentParser(description="Tự tải ADB / Tesseract-OCR / VC++ cho bản cài ADB-THTG.")
    p.add_argument("--chi", default="adb,ocr,vc", help="Thành phần cần làm, cách nhau dấu phẩy: adb, ocr, vc.")
    p.add_argument("--force", action="store_true", help="Tải/cài lại dù đã có.")
    p.add_argument("--adb-url", default=ADB_URL, help="Link platform-tools (zip) thay thế.")
    p.add_argument("--tesseract-url", default=None, help="Link trình cài Tesseract (.exe) thay thế.")
    p.add_argument("--root", default=ROOT, help="Thư mục đặt platform-tools/ và Tesseract-OCR/ (mặc định: cạnh file này).")
    p.add_argument("--khong-doi", action="store_true", help="Không chờ bấm Enter khi xong (dùng cho bộ cài).")
    p.add_argument("--selftest", action="store_true", help="Kiểm logic bằng server giả rồi thoát.")
    return p.parse_args(argv)


def main(argv=None):
    a = _doc_tham_so(sys.argv[1:] if argv is None else argv)
    if a.selftest:
        return selftest()
    chi = [x.strip() for x in a.chi.split(",") if x.strip()]
    la = [x for x in chi if x not in ("adb", "ocr", "vc")]
    if la:
        log(f"[LOI] Thành phần không hợp lệ: {', '.join(la)} (chỉ có adb, ocr, vc).")
        return 2
    log("=" * 60)
    log("TẢI CÁC THÀNH PHẦN BÊN NGOÀI (cần Internet)")
    log("=" * 60)
    kq = chay(a.root, chi, a.force, a.adb_url, a.tesseract_url)
    log("\n" + "=" * 60)
    ten = {"adb": "ADB (platform-tools)", "ocr": "Tesseract-OCR", "vc": "Visual C++"}
    for k, v in kq.items():
        log(f"  {'[OK]' if v else '[LOI]'} {ten[k]}")
    loi = [k for k, v in kq.items() if not v]
    if loi:
        log("\nCó thành phần chưa cài được (thường do mạng). Chạy lại file")
        log("Tai_Them_Thanh_Phan.bat (trong thư mục cài) khi có mạng là được.")
    log("=" * 60)
    if loi and not a.khong_doi and os.name == "nt":
        try:
            input("\nBấm Enter để đóng...")
        except EOFError:
            pass
    return 1 if loi else 0


# ---------------------------------------------------------------------------
# Selftest: server HTTP cục bộ giả lập các link tải
# ---------------------------------------------------------------------------
def selftest():
    import http.server
    import io
    import threading

    ok = True

    def check(cond, msg):
        nonlocal ok
        log(("  OK   " if cond else "  LOI  ") + msg)
        ok = ok and bool(cond)

    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        zf.writestr("platform-tools/adb.exe", b"A" * 2000)
        zf.writestr("platform-tools/AdbWinApi.dll", b"B" * 100)
    zip_bytes = zbuf.getvalue()
    files = {
        "/adb.zip": zip_bytes,
        "/adb_nho.zip": b"<html>404</html>",
        "/tess.exe": b"T" * 3000,
        "/eng.traineddata": b"E" * (MIN_TRAINEDDATA + 1000),
        "/vie.traineddata": b"V" * (MIN_TRAINEDDATA + 1000),
        "/vc.exe": b"C" * 3000,
    }
    dem = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            dem[self.path] = dem.get(self.path, 0) + 1
            d = files.get(self.path)
            if d is None:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(d)))
            self.end_headers()
            self.wfile.write(d)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    root = tempfile.mkdtemp(prefix="thtg_selftest_")
    try:
        log("1) ADB: tải + giải nén + idempotent")
        check(cai_adb(root, base + "/adb.zip", im=True, toi_thieu=100), "cài adb từ zip giả")
        check(adb_co_san(root), "có platform-tools/adb.exe")
        n = dem.get("/adb.zip", 0)
        check(cai_adb(root, base + "/adb.zip", im=True, toi_thieu=100), "chạy lại trả True")
        check(dem.get("/adb.zip", 0) == n, "đã có thì KHÔNG tải lại")
        check(cai_adb(root, base + "/adb.zip", force=True, im=True, toi_thieu=100) and dem["/adb.zip"] == n + 1,
              "--force thì tải lại")

        log("2) ADB: file lỗi/nhỏ không làm hỏng bản đang có")
        gia = os.path.join(root, "platform-tools", "adb.exe")
        check(not cai_adb(root, base + "/adb_nho.zip", force=True, im=True, toi_thieu=100000),
              "file quá nhỏ bị từ chối")
        check(os.path.exists(gia), "adb.exe cũ còn nguyên sau khi tải lỗi")
        check(not cai_adb(tempfile.mkdtemp(prefix="thtg_x_"), base + "/khong_co", im=True, toi_thieu=1),
              "404 -> False (thử lại 3 lần không treo)")

        log("3) Tesseract: gọi trình cài giả + tải ngôn ngữ")
        goi = []

        def gia_cai(exe, dst):
            goi.append((os.path.basename(exe), dst))
            os.makedirs(os.path.join(dst, "tessdata"), exist_ok=True)
            with open(os.path.join(dst, "tesseract.exe"), "wb") as f:
                f.write(b"x")
            return True

        global _tesseract_urls
        goc = _tesseract_urls
        _tesseract_urls = lambda u=None: [base + "/khong_co", base + "/tess.exe"]  # link đầu chết -> thử link sau
        try:
            check(cai_tesseract(root, None, im=True, silent_runner=gia_cai, toi_thieu=100,
                                base_lang=base + "/"), "cài tesseract (link đầu 404, link sau được)")
        finally:
            _tesseract_urls = goc
        check(len(goi) == 1 and goi[0][1] == os.path.join(root, "Tesseract-OCR"), "trình cài nhận đúng thư mục đích")
        for lang in OCR_LANGS:
            check(os.path.exists(os.path.join(root, "Tesseract-OCR", "tessdata", f"{lang}.traineddata")),
                  f"có {lang}.traineddata")
        check(tess_co_san(root), "có Tesseract-OCR/tesseract.exe")
        n = dem.get("/tess.exe", 0)
        check(cai_tesseract(root, None, im=True, silent_runner=gia_cai, toi_thieu=100, base_lang=base + "/"),
              "chạy lại trả True")
        check(dem.get("/tess.exe", 0) == n and len(goi) == 1, "đã có thì không tải/cài lại")
        os.remove(os.path.join(root, "Tesseract-OCR", "tessdata", "vie.traineddata"))
        check(cai_tesseract(root, None, im=True, silent_runner=gia_cai, toi_thieu=100, base_lang=base + "/")
              and os.path.exists(os.path.join(root, "Tesseract-OCR", "tessdata", "vie.traineddata")),
              "thiếu mỗi gói vie thì chỉ tải bù gói đó")
        os.remove(os.path.join(root, "Tesseract-OCR", "tessdata", "vie.traineddata"))
        check(cai_tesseract(root, None, im=True, silent_runner=gia_cai, toi_thieu=100,
                            base_lang=(base + "/khong_co/", base + "/"))
              and os.path.exists(os.path.join(root, "Tesseract-OCR", "tessdata", "vie.traineddata")),
              "link ngôn ngữ đầu chết -> dùng link dự phòng")

        log("4) VC++")
        mac = []
        check(cai_vc(base + "/vc.exe", im=True, da_cai=True, runner=lambda p: mac.append(p) or 0, toi_thieu=100)
              and not mac, "đã có VC++ thì không tải/cài")
        check(cai_vc(base + "/vc.exe", im=True, da_cai=False, runner=lambda p: mac.append(p) or 3010, toi_thieu=100)
              and len(mac) == 1, "chưa có -> tải + chạy trình cài (mã 3010 vẫn coi là xong)")
        check(not cai_vc(base + "/vc.exe", im=True, da_cai=False, runner=lambda p: 1603, toi_thieu=100),
              "trình cài trả lỗi -> False")

        log("5) Lỗi chứng chỉ SSL (kho chứng chỉ Windows thiếu CA gốc...)")
        import urllib.error
        g = globals()
        goc_ctx, goc_ps, goc_open = g["_ssl_contexts"], g["_tai_powershell"], urllib.request.urlopen

        class _Resp(io.BytesIO):
            headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def mo_gia(req, timeout=None, context=None):
            if context is None:
                raise urllib.error.URLError(ssl.SSLCertVerificationError(
                    "CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate"))
            return _Resp(b"D" * 5000)

        try:
            urllib.request.urlopen = mo_gia
            g["_ssl_contexts"] = lambda: [None, "CTX"]
            d1 = os.path.join(root, "ssl1.bin")
            check(tai_ve("http://x/f", d1, 100, im=True, so_lan=1) and os.path.getsize(d1) == 5000,
                  "CA hệ thống lỗi -> tự dùng bộ chứng chỉ certifi")
            g["_ssl_contexts"] = lambda: [None]

            def ps_gia(url, dst, toi_thieu=0):
                with open(dst, "wb") as f:
                    f.write(b"P" * 300)
                return True

            g["_tai_powershell"] = ps_gia
            d2 = os.path.join(root, "ssl2.bin")
            check(tai_ve("http://x/f", d2, 100, im=True, so_lan=3) and os.path.getsize(d2) == 300,
                  "certifi cũng lỗi -> dự phòng PowerShell")
            g["_tai_powershell"] = lambda *a, **k: False
            d3 = os.path.join(root, "ssl3.bin")
            check(not tai_ve("http://x/f", d3, 100, im=True, so_lan=3) and not os.path.exists(d3)
                  and not os.path.exists(d3 + ".part"), "mọi cách đều lỗi -> False, không để file dở")
            check(_la_loi_ssl(ssl.SSLError("x")) and not _la_loi_ssl(IOError("404")),
                  "phân biệt lỗi SSL với lỗi mạng thường")
        finally:
            g["_ssl_contexts"], g["_tai_powershell"] = goc_ctx, goc_ps
            urllib.request.urlopen = goc_open

        log("5b) Quyền quản trị (WinError 740)")
        goi = []

        class _R:
            def __init__(self, c):
                self.returncode = c

        def run_740(cmd, timeout=None, **k):
            goi.append(cmd)
            if isinstance(cmd, str):  # lần chạy thường -> Windows đòi quyền
                e = OSError()
                e.winerror = 740
                raise e
            return _R(0)

        goc_run = subprocess.run
        subprocess.run = run_740
        try:
            rc = _chay_nang_quyen(r"C:\x y\t.exe", r"/S /D=C:\a b")
            check(rc == 0 and len(goi) == 2 and isinstance(goi[1], list) and goi[1][0] == "powershell"
                  and "-Verb RunAs" in goi[1][-1] and r"C:\a b" in goi[1][-1],
                  "WinError 740 -> chạy lại bằng PowerShell RunAs, đủ tham số")

            def run_loi(cmd, timeout=None, **k):
                raise OSError(2, "khong thay file")

            subprocess.run = run_loi
            try:
                _chay_nang_quyen("x", "y")
                nem = False
            except OSError:
                nem = True
            check(nem, "lỗi khác 740 thì báo lỗi bình thường (không xin quyền)")
        finally:
            subprocess.run = goc_run

        log("6) Tham số dòng lệnh")
        check(main(["--chi", "xyz"]) == 2, "thành phần sai bị từ chối")
    finally:
        srv.shutdown()
        shutil.rmtree(root, ignore_errors=True)
    log("\n" + ("TẤT CẢ OK" if ok else "CÓ LỖI"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

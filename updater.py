"""
updater.py - TỰ CẬP NHẬT từ GitHub (không cần git / pip / Python cài sẵn trên máy nhận).

Máy "phát hành" bấm nút '🚀 Phát Hành' trong Dashboard (xem publisher.py / dashboard_publish.py): chọn các mục
(code, kịch bản, ảnh mẫu...) -> chương trình tự tạo 1 Release trên GitHub kèm gói ADB-THTG_update.zip.
(Vẫn dùng được kiểu cũ: tự đẩy code rồi tạo Release/tag số, vd v2026.11.16 - khi đó tải zip mã nguồn.)
Các máy khác mở Dashboard sẽ thấy "Có bản mới - Cập Nhật", bấm là xong (xem dashboard_update.py).

CÁCH HOẠT ĐỘNG
  1) check_for_update(): hỏi GitHub bản mới nhất (Release mới nhất; không có Release thì lấy tag có số
     phiên bản lớn nhất), so với phiên bản đã ghi ở data/app_version.json trên máy này.
  2) download() + apply_update(): tải zip mã nguồn của đúng bản đó rồi
       - KIỂM CÚ PHÁP mọi file .py mới TRƯỚC khi ghi đè gì (hỏng 1 file = bỏ cả đợt, không đụng máy);
       - sao lưu file cũ sẽ bị đổi vào backup_cap_nhat/<ngày_giờ>_<bản cũ>/;
       - ghi đè CHỈ những file khác nội dung; lỗi giữa chừng thì TRẢ LẠI file cũ;
       - ghi lại phiên bản mới vào data/app_version.json.
  3) install_requirements(): chỉ khi requirements.txt đổi - cài bằng chính Python đang chạy app.
  4) spawn_restart(): mở lại Dashboard sau khi app này đóng.

CẬP NHẬT NHỮNG GÌ (cố ý hẹp để không phá dữ liệu riêng từng máy) - hàm classify() là NGUỒN DUY NHẤT:
  - 'code': các file *.py ở thư mục gốc (trừ build_installer.py / build_portable.py / tao_license.py / ap_dung_*.py) + requirements.txt + cacert.pem
  - 'kich_ban' / 'nhom_ngoai' / 'anh_mau': thư mục tasks/, groups/, templates/ (CHỈ ghi đè/thêm file có trong bản mới,
    KHÔNG xoá file chỉ có ở máy này)
  - CHỈ với gói có manifest.json do nút '🚀 Phát Hành' tạo: thêm 5 file cấu hình dùng chung trong data/
    (task_registry.json, activity_groups.json, variables.json, data_groups.json, schedules.json) - ghi đè nguyên file.
    Gói zip mã nguồn kiểu cũ (không manifest) thì KHÔNG đụng data/ gì cả.
  KHÔNG BAO GIỜ đụng (dù gói có ghi): tài khoản (accounts*.json...), dashboard_settings.json, token Telegram,
  vị trí cửa sổ, logs/, python/, Tesseract-OCR/, *.md, .gitignore, mọi thứ khác. Gói chứa file ngoài danh sách
  cho phép bị TỪ CHỐI cả gói. Gói manifest còn bị kiểm SHA-256 từng file.

MÁY DEV = thư mục có .git VÀ file data/may_phat_trien.flag -> không tự cập nhật. Máy chỉ có .git vẫn cập nhật bình thường.

Dòng lệnh (không cần giao diện):
    python updater.py --kiem-tra      chỉ xem có bản mới không
    python updater.py --cap-nhat      tải + áp dụng bản mới nhất (không tự mở lại app)
    python updater.py --chan-doan     tìm nguyên nhân khi báo 'không kết nối được GitHub'
"""
import hashlib
import json
import socket
import ssl
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
import urllib.error
import urllib.parse
import urllib.request

GITHUB_REPO = "haicosla/adb-thtg"
API_BASE = "https://api.github.com"          # đổi được khi kiểm thử (server giả)
WEB_BASE = "https://github.com"              # đường dự phòng khi api.github.com không vào được (không tính lượt API)
USER_AGENT = "ADB-THTG-Updater"
HTTP_TIMEOUT = 10                            # giây - hỏi GitHub bản mới nhất
DOWNLOAD_TIMEOUT = 60                        # giây - chờ mỗi lần đọc dữ liệu khi tải zip
MAX_ZIP_BYTES = 600 * 1024 * 1024            # chặn gói quá lớn
MAX_UNPACKED_BYTES = 1200 * 1024 * 1024      # chặn zip "bom" (giải nén phình to)
KEEP_BACKUPS = 5                             # giữ tối đa N thư mục backup_cap_nhat gần nhất

SYNC_DIRS = ("tasks", "groups", "templates")
SYNC_DIR_CATEGORY = {"tasks": "kich_ban", "groups": "nhom_ngoai", "templates": "anh_mau"}
# Chỉ các file cấu hình DÙNG CHUNG này trong data/ mới được phép đi qua gói manifest (khoá = mục phát hành).
DATA_FILE_CATEGORY = {"task_registry.json": "hoat_dong", "activity_groups.json": "nhom_hanh_dong",
                      "variables.json": "bien", "data_groups.json": "nhom_du_lieu", "schedules.json": "lich_hen_gio"}
ASSET_NAME = "ADB-THTG_update.zip"           # tên file đính kèm Release do nút Phát Hành tạo
MANIFEST_NAME = "manifest.json"
SKIP_PY = {"build_installer.py", "build_portable.py", "tao_license.py"}   # tao_license.py = công cụ CỦA NGƯỜI BÁN, không bao giờ gửi khách
SKIP_FILE_NAMES = {".gitkeep", ".gitignore", ".DS_Store", "Thumbs.db"}
SKIP_SUFFIX = (".bak", ".tmp", ".corrupted", ".pyc")
MUST_HAVE = "dashboard.py"                   # gói thiếu file này = không phải gói hợp lệ

VERSION_REL = os.path.join("data", "app_version.json")
STAGE_DIRNAME = "cap_nhat_tmp"
BACKUP_DIRNAME = "backup_cap_nhat"


class UpdateError(Exception):
    """Lỗi có thể đọc được bằng tiếng Việt - nơi gọi hiện nguyên văn cho người dùng."""


def app_dir():
    return os.path.dirname(os.path.abspath(__file__))


DEV_FLAG_REL = os.path.join("data", "may_phat_trien.flag")


def has_git(directory=None):
    return os.path.isdir(os.path.join(directory or app_dir(), ".git"))


def is_dev_checkout(directory=None):
    """MÁY PHÁT TRIỂN = có .git VÀ có file data/may_phat_trien.flag (tự tạo, file rỗng) -> không tự cập nhật.
    Máy chỉ có .git (cài git để tải code về) VẪN tự cập nhật bình thường - cập nhật có sao lưu file bị đổi."""
    d = directory or app_dir()
    return has_git(d) and os.path.isfile(os.path.join(d, DEV_FLAG_REL))


def git_dirty_files(directory=None, limit=8):
    """Danh sách file đang bị sửa chưa commit (best-effort; không có git/lỗi -> [])."""
    import subprocess
    d = directory or app_dir()
    if not has_git(d):
        return []
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=d, capture_output=True, text=True, timeout=8).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [ln[3:].strip() for ln in out.splitlines() if ln.strip() and not ln.startswith("??")][:limit]


# ------------------------------------------------------------------ phiên bản
def parse_version(tag):
    """'v2026.11.16' -> (2026, 11, 16); 'v2026.11.16.2' -> (2026, 11, 16, 2); không có số -> ()."""
    return tuple(int(x) for x in re.findall(r"\d+", str(tag or "")))


def read_installed(directory=None):
    """Phiên bản đã cài trên máy này: {'tag': ..., 'updated': ...} (rỗng nếu chưa từng cập nhật)."""
    path = os.path.join(directory or app_dir(), VERSION_REL)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_installed(directory, tag, files_changed=0):
    path = os.path.join(directory, VERSION_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"tag": tag, "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "files_changed": int(files_changed)}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ------------------------------------------------------------------ mạng
CA_BUNDLE = "cacert.pem"    # bộ chứng chỉ gốc Mozilla (từ gói certifi, MPL-2.0) kèm theo chương trình
_ssl_ctx = None


def ssl_context():
    """Ngữ cảnh HTTPS: chứng chỉ của hệ điều hành + file cacert.pem cạnh chương trình (nếu có).
    Python đóng gói kèm / Windows chưa cập nhật chứng chỉ hay thiếu chứng chỉ gốc -> 'unable to get local
    issuer certificate'. KHÔNG BAO GIỜ tắt xác minh chứng chỉ."""
    global _ssl_ctx
    if _ssl_ctx is None:
        ctx = ssl.create_default_context()
        bundle = os.path.join(app_dir(), CA_BUNDLE)
        if os.path.isfile(bundle):
            try:
                ctx.load_verify_locations(cafile=bundle)
            except (ssl.SSLError, OSError):
                pass
        _ssl_ctx = ctx
    return _ssl_ctx


def _open(url, timeout, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    return urllib.request.urlopen(req, timeout=timeout, context=ssl_context())


class NetworkError(UpdateError):
    """Lỗi MẠNG (không phải GitHub trả lỗi) - nơi gọi có thể thử đường dự phòng."""


def describe_net_error(e, host="api.github.com"):
    """Nguyên nhân lỗi mạng bằng tiếng Việt + chi tiết kỹ thuật ngắn (để người dùng gửi lại khi cần)."""
    reason = getattr(e, "reason", None) or e
    detail = f"{type(reason).__name__}: {reason}"[:160]
    if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(reason):
        if "issuer" in str(reason).lower() and not os.path.isfile(os.path.join(app_dir(), CA_BUNDLE)):
            why = ("Python trên máy này THIẾU chứng chỉ gốc để xác minh GitHub (hay gặp ở Python đóng gói kèm / "
                   f"Windows chưa cập nhật chứng chỉ). Chép file {CA_BUNDLE} vào thư mục dự án (cạnh updater.py) rồi thử lại.")
        else:
            why = ("Chứng chỉ bảo mật của GitHub không được tin cậy - thường do phần mềm diệt virus/tường lửa/proxy "
                   "can thiệp HTTPS, hoặc NGÀY GIỜ máy bị sai. Kiểm tra lại ngày giờ máy.")
    elif isinstance(reason, ssl.SSLError):
        why = "Lỗi bắt tay bảo mật (SSL) với GitHub - có thể do mạng/tường lửa chặn hoặc Windows quá cũ."
    elif isinstance(reason, socket.gaierror):
        why = f"Không tìm được địa chỉ của {host} (DNS/mạng bị chặn hoặc chưa có Internet). Thử đổi DNS sang 8.8.8.8 hoặc 1.1.1.1."
    elif isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(reason).lower():
        why = f"Quá thời gian chờ {host} - mạng chậm hoặc bị chặn."
    elif isinstance(reason, ConnectionRefusedError):
        why = f"{host} từ chối kết nối (tường lửa/proxy chặn?)."
    elif isinstance(reason, (ConnectionResetError, ConnectionAbortedError)):
        why = f"Kết nối tới {host} bị ngắt giữa chừng (nhà mạng/tường lửa chặn?)."
    else:
        why = f"Không kết nối được {host} (kiểm tra mạng)."
    return f"{why} [{detail}]"


def _get_json(url):
    last = None
    for attempt in (1, 2):                      # lỗi mạng thoáng qua: thử lại 1 lần
        try:
            with _open(url, HTTP_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if e.code in (403, 429):
                raise UpdateError("GitHub từ chối (có thể đã hết lượt hỏi trong giờ này) - thử lại sau ít phút.")
            raise UpdateError(f"GitHub trả lỗi HTTP {e.code}.")
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            last = e
            if attempt == 1:
                time.sleep(1.5)
        except ValueError:
            raise UpdateError("GitHub trả dữ liệu không đọc được.")
    raise NetworkError(describe_net_error(last))


def _fetch_latest_web(repo):
    """Đường DỰ PHÒNG khi api.github.com lỗi mạng: hỏi trang github.com/<repo>/releases/latest (tự chuyển hướng
    sang .../releases/tag/<tag>) rồi lấy file đính kèm của Release đó, không có thì dùng gói mã nguồn của tag."""
    try:
        with _open(f"{WEB_BASE}/{repo}/releases/latest", HTTP_TIMEOUT, accept="text/html") as resp:
            final = resp.geturl()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    m = re.search(r"/releases/tag/([^/?#]+)", final)
    if not m:
        return None                                   # chưa có Release nào
    tag = urllib.parse.unquote(m.group(1))
    asset = f"{WEB_BASE}/{repo}/releases/download/{urllib.parse.quote(tag)}/{ASSET_NAME}"
    try:
        with _open(asset, HTTP_TIMEOUT, accept="application/octet-stream"):
            pass
        has_asset = True
    except urllib.error.HTTPError:
        has_asset = False
    zip_url = asset if has_asset else f"{WEB_BASE}/{repo}/archive/refs/tags/{urllib.parse.quote(tag)}.zip"
    return {"tag": tag, "name": tag, "notes": "", "zip_url": zip_url,
            "source": "web+goi" if has_asset else "web", "has_asset": has_asset}


def fetch_latest(repo=None):
    """Bản mới nhất trên GitHub. API lỗi MẠNG thì thử đường dự phòng github.com (nếu cũng lỗi: báo lỗi của API)."""
    repo = repo or GITHUB_REPO
    try:
        return _fetch_latest_api(repo)
    except NetworkError as first:
        try:
            return _fetch_latest_web(repo)
        except Exception:
            raise first


def _fetch_latest_api(repo):
    """{'tag','name','notes','zip_url','source'} hoặc None nếu repo chưa có Release/tag nào."""
    try:
        rel = _get_json(f"{API_BASE}/repos/{repo}/releases/latest")
        tag = str(rel.get("tag_name") or "")
        if tag:
            asset_url = ""
            for a in rel.get("assets") or []:
                if isinstance(a, dict) and a.get("name") == ASSET_NAME and a.get("browser_download_url"):
                    asset_url = str(a["browser_download_url"])
                    break
            return {"tag": tag, "name": str(rel.get("name") or tag), "notes": str(rel.get("body") or "")[:1500],
                    "zip_url": asset_url or str(rel.get("zipball_url") or f"{API_BASE}/repos/{repo}/zipball/{tag}"),
                    "source": "release+goi" if asset_url else "release", "has_asset": bool(asset_url)}
    except urllib.error.HTTPError:
        pass  # 404 = chưa có Release nào -> thử tag
    try:
        tags = _get_json(f"{API_BASE}/repos/{repo}/tags?per_page=50")
    except urllib.error.HTTPError:
        raise UpdateError(f"Không thấy repo {repo} trên GitHub (sai tên, hoặc repo đã chuyển sang riêng tư nên máy không "
                          "có token thì không xem được).")
    best = None
    for t in tags if isinstance(tags, list) else []:
        name = str(t.get("name") or "")
        v = parse_version(name)
        if v and (best is None or v > best[0]):
            best = (v, name)
    if not best:
        return None
    return {"tag": best[1], "name": best[1], "notes": "",
            "zip_url": f"{API_BASE}/repos/{repo}/zipball/{best[1]}", "source": "tag"}


def check_for_update(directory=None):
    """Không bao giờ ném lỗi. status: 'dev' | 'error' | 'none' | 'up_to_date' | 'available'."""
    directory = directory or app_dir()
    installed = str(read_installed(directory).get("tag") or "")
    out = {"status": "error", "installed": installed, "latest": None, "message": ""}
    if is_dev_checkout(directory):
        out.update(status="dev", message="Máy này được đánh dấu là máy phát triển (data/may_phat_trien.flag) - cập nhật bằng 'git pull', "
                                         "không dùng tự cập nhật.")
        return out
    try:
        latest = fetch_latest()
    except UpdateError as e:
        out["message"] = str(e)
        return out
    except Exception as e:  # chốt an toàn: kiểm tra bản mới không được làm sập app
        out["message"] = f"Lỗi khi kiểm tra bản mới: {e}"
        return out
    if latest is None:
        out.update(status="none", message="Trên GitHub chưa có Release/tag phiên bản nào.")
        return out
    out["latest"] = latest
    if parse_version(latest["tag"]) > parse_version(installed):
        out.update(status="available", message=f"Có bản mới {latest['tag']}.")
    else:
        out.update(status="up_to_date", message=f"Đang dùng bản mới nhất ({installed or latest['tag']}).")
    return out


def download(url, dest_path, progress=None, should_stop=None):
    """Tải zip về dest_path. progress(đã_tải, tổng_hoặc_0). Lỗi/huỷ -> UpdateError và xoá file dở."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        with _open(url, DOWNLOAD_TIMEOUT, accept="application/octet-stream") as resp, open(dest_path, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            if total > MAX_ZIP_BYTES:
                raise UpdateError("Gói cập nhật quá lớn - bỏ qua.")
            done = 0
            while True:
                if should_stop and should_stop():
                    raise UpdateError("Đã huỷ tải.")
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                done += len(chunk)
                if done > MAX_ZIP_BYTES:
                    raise UpdateError("Gói cập nhật quá lớn - bỏ qua.")
                out.write(chunk)
                if progress:
                    progress(done, total)
    except UpdateError:
        _silent_remove(dest_path)
        raise
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        _silent_remove(dest_path)
        raise UpdateError("Tải bản cập nhật thất bại: " + describe_net_error(e, "github.com"))
    return dest_path


# ------------------------------------------------------------------ áp dụng
def _silent_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _clean_parts(name):
    """Tách đường dẫn trong zip thành các phần an toàn; None nếu tuyệt đối/có '..'/ổ đĩa (chống zip-slip)."""
    name = name.replace("\\", "/")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        return None
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    return parts


def _skip_py(leaf):
    return leaf in SKIP_PY or leaf.startswith("ap_dung_")


def classify(parts):
    """Mục phát hành của 1 đường dẫn tương đối (list các phần) hoặc None nếu KHÔNG được phép cập nhật.
    Đây là nguồn DUY NHẤT quyết định file nào được ghi vào máy (cả publisher.py lẫn gói zip mã nguồn kiểu cũ đều dùng)."""
    if not parts:
        return None
    leaf = parts[-1]
    if len(parts) == 1:
        if leaf in ("requirements.txt", CA_BUNDLE) or (leaf.endswith(".py") and not _skip_py(leaf)):
            return "code"
        return None
    if parts[0] == "data":
        return DATA_FILE_CATEGORY.get(leaf) if len(parts) == 2 else None
    if parts[0] in SYNC_DIR_CATEGORY and "backup" not in parts[1:-1]:
        if leaf in SKIP_FILE_NAMES or leaf.endswith(SKIP_SUFFIX):
            return None
        return SYNC_DIR_CATEGORY[parts[0]]
    return None


def read_manifest(zf):
    """manifest.json ở gốc zip (gói do nút Phát Hành tạo) hoặc None nếu là zip mã nguồn kiểu cũ."""
    info = next((i for i in zf.infolist() if i.filename == MANIFEST_NAME), None)
    if info is None:
        return None
    if info.file_size > 8 * 1024 * 1024:
        raise UpdateError("manifest.json quá lớn - gói không hợp lệ.")
    try:
        m = json.loads(zf.read(info).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, zipfile.BadZipFile):
        raise UpdateError("manifest.json trong gói bị hỏng.")
    if not isinstance(m, dict) or m.get("format") != 1 or not isinstance(m.get("files"), list):
        raise UpdateError("Gói có định dạng mới mà phiên bản chương trình này chưa hiểu - hãy cập nhật code bằng "
                          "cách khác (chép tay) rồi thử lại.")
    return m


def plan_manifest(zf, manifest):
    """Kế hoạch cho gói có manifest: CHỈ các file liệt kê trong manifest VÀ nằm trong danh sách cho phép (classify).
    Gói chứa file ngoài danh sách cho phép (vd data/accounts.json) bị từ chối cả gói. Trả (plan, {rel: sha256})."""
    members = {i.filename: i for i in zf.infolist() if not i.is_dir()}
    plan, expected = [], {}
    for ent in manifest["files"]:
        if not isinstance(ent, dict):
            raise UpdateError("manifest.json có mục không hợp lệ.")
        rel = str(ent.get("path") or "")
        parts = _clean_parts(rel)
        if parts is None:
            raise UpdateError(f"Gói có đường dẫn không an toàn: {rel!r} - dừng cập nhật.")
        if classify(parts) is None:
            raise UpdateError(f"Gói chứa file không nằm trong danh sách cho phép ({rel}) - dừng cập nhật.")
        key = "/".join(parts)
        sha = str(ent.get("sha256") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise UpdateError(f"manifest.json thiếu mã SHA-256 hợp lệ cho {rel}.")
        if key not in members:
            raise UpdateError(f"Gói thiếu file {rel} đã ghi trong manifest.")
        plan.append((members[key], parts))
        expected[key] = sha
    return plan, expected


def plan_files(zf):
    """[(ZipInfo, [phần đường dẫn tương đối trong app])] theo danh sách trắng ở đầu file."""
    infos = [i for i in zf.infolist() if not i.is_dir()]
    firsts = set()
    for i in infos:
        p = _clean_parts(i.filename)
        if p is None:
            raise UpdateError(f"Gói có đường dẫn không an toàn: {i.filename!r} - dừng cập nhật.")
        firsts.add(p[0])
    strip = len(firsts) == 1 and all(len(_clean_parts(i.filename)) > 1 for i in infos)
    plan = []
    for i in infos:
        parts = _clean_parts(i.filename)[1:] if strip else _clean_parts(i.filename)
        if not parts:
            continue
        leaf = parts[-1]
        if leaf in SKIP_FILE_NAMES or leaf.endswith(SKIP_SUFFIX):
            continue
        if parts[0] == "data":      # zip mã nguồn kiểu cũ KHÔNG BAO GIỜ đụng data/
            continue
        if classify(parts):
            plan.append((i, parts))
    return plan


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def apply_update(zip_path, directory, tag, installed_tag="", on_log=None):
    """Áp dụng gói zip vào `directory`. Trả {'added','modified','changed','backup_dir','needs_pip'}.
    Mọi lỗi -> UpdateError và máy ở nguyên trạng cũ."""
    log = on_log or (lambda msg: None)
    # Thư mục giải nén riêng (cap_nhat_tmp/stage) - KHÔNG chung với nơi chứa file zip tải về (cap_nhat_tmp/dl),
    # nếu không việc dọn thư mục này ở đầu hàm sẽ xoá luôn file zip đang cần đọc.
    stage = os.path.join(directory, STAGE_DIRNAME, "stage")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage, exist_ok=True)
    try:
        try:
            zf = zipfile.ZipFile(zip_path)
        except zipfile.BadZipFile:
            raise UpdateError("File tải về không phải zip hợp lệ.")
        with zf:
            manifest = read_manifest(zf)
            expected = {}
            if manifest is not None:        # gói do nút '🚀 Phát Hành' tạo
                plan, expected = plan_manifest(zf, manifest)
                if not plan:
                    raise UpdateError("Gói không có file nào để cập nhật.")
                if any(classify(p) == "code" for _i, p in plan) and not any(p == [MUST_HAVE] for _i, p in plan):
                    raise UpdateError(f"Gói không hợp lệ (có code nhưng thiếu {MUST_HAVE}) - bỏ qua.")
            else:                           # zip mã nguồn kiểu cũ
                plan = plan_files(zf)
                if not any(p == [MUST_HAVE] for _i, p in plan):
                    raise UpdateError(f"Gói không hợp lệ (thiếu {MUST_HAVE}) - bỏ qua.")
            if sum(i.file_size for i, _p in plan) > MAX_UNPACKED_BYTES:
                raise UpdateError("Gói giải nén quá lớn - bỏ qua.")
            staged = []   # [(đường dẫn tạm, đường dẫn đích, rel dạng 'a/b')]
            for n, (info, parts) in enumerate(plan):
                tmp = os.path.join(stage, f"{n}.part")
                with zf.open(info) as src, open(tmp, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                rel = "/".join(parts)
                if rel in expected and _sha256(tmp) != expected[rel]:
                    raise UpdateError(f"Gói bị hỏng hoặc bị sửa (sai mã SHA-256 ở {rel}) - không cập nhật, máy giữ nguyên.")
                staged.append((tmp, os.path.join(directory, *parts), rel))

        # 1) KIỂM CÚ PHÁP mọi .py mới trước khi đụng vào máy
        for tmp, _dst, rel in staged:
            if rel.endswith(".py"):
                with open(tmp, "rb") as f:
                    data = f.read()
                try:
                    compile(data, rel, "exec", dont_inherit=True)
                except (SyntaxError, ValueError) as e:
                    raise UpdateError(f"Bản mới có file lỗi cú pháp ({rel}: {e}) - không cập nhật, máy giữ nguyên.")

        # 2) chỉ giữ file THỰC SỰ khác (mới hoặc đổi nội dung)
        changes = []  # (tmp, dst, rel, existed)
        for tmp, dst, rel in staged:
            if os.path.isfile(dst):
                if _sha256(dst) == _sha256(tmp):
                    continue
                changes.append((tmp, dst, rel, True))
            else:
                changes.append((tmp, dst, rel, False))

        # 3) sao lưu file cũ sắp bị đổi
        stamp = time.strftime("%Y%m%d_%H%M%S")
        label = re.sub(r"[^\w.\-]", "_", installed_tag or "cu")
        backup_dir = os.path.join(directory, BACKUP_DIRNAME, f"{stamp}_{label}")
        for _tmp, dst, rel, existed in changes:
            if existed:
                b = os.path.join(backup_dir, *rel.split("/"))
                os.makedirs(os.path.dirname(b), exist_ok=True)
                shutil.copy2(dst, b)

        # 4) ghi đè; lỗi giữa chừng -> trả lại
        done = []
        try:
            for tmp, dst, rel, existed in changes:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.replace(tmp, dst)
                done.append((dst, rel, existed))
        except OSError as e:
            for dst, rel, existed in reversed(done):
                try:
                    if existed:
                        shutil.copy2(os.path.join(backup_dir, *rel.split("/")), dst)
                    else:
                        os.remove(dst)
                except OSError:
                    pass
            raise UpdateError(f"Ghi file thất bại ({e}) - đã trả lại bản cũ. "
                              "Đóng LD Macro Studio / chương trình khác đang mở rồi thử lại.")

        write_installed(directory, tag, files_changed=len(changes))
        _prune_backups(os.path.join(directory, BACKUP_DIRNAME))
        rels = [rel for _t, _d, rel, _e in changes]
        added = sum(1 for *_x, existed in changes if not existed)
        log(f"Đã cập nhật {len(changes)} file ({added} mới).")
        return {"added": added, "modified": len(changes) - added, "changed": rels,
                "backup_dir": backup_dir if any(e for *_x, e in changes) else "",
                "needs_pip": "requirements.txt" in rels,
                "categories": list(manifest.get("categories") or []) if manifest else [],
                "has_data": any(r.startswith("data/") for r in rels)}
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        try:
            os.rmdir(os.path.join(directory, STAGE_DIRNAME))   # chỉ xoá được khi đã rỗng (zip tải về còn thì giữ)
        except OSError:
            pass


def _prune_backups(root):
    try:
        names = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    except OSError:
        return
    for d in names[:-KEEP_BACKUPS] if len(names) > KEEP_BACKUPS else []:
        shutil.rmtree(os.path.join(root, d), ignore_errors=True)


def update_to_latest(info, directory=None, progress=None, should_stop=None, on_log=None):
    """Tải + áp dụng bản `info` (phần 'latest' của check_for_update). Trả kết quả apply_update."""
    directory = directory or app_dir()
    zip_path = os.path.join(directory, STAGE_DIRNAME, "dl", "release.zip")
    installed = str(read_installed(directory).get("tag") or "")
    try:
        download(info["zip_url"], zip_path, progress=progress, should_stop=should_stop)
        return apply_update(zip_path, directory, info["tag"], installed_tag=installed, on_log=on_log)
    finally:
        shutil.rmtree(os.path.join(directory, STAGE_DIRNAME), ignore_errors=True)


# ------------------------------------------------------------------ thư viện + mở lại app
def _python_exe():
    exe = sys.executable
    if os.name == "nt" and os.path.basename(exe).lower() == "pythonw.exe":
        alt = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.isfile(alt):
            return alt
    return exe


def install_requirements(directory=None, timeout=900):
    """pip install -r requirements.txt bằng Python đang chạy app. Trả (ok, thông báo ngắn)."""
    directory = directory or app_dir()
    req = os.path.join(directory, "requirements.txt")
    if not os.path.isfile(req):
        return True, "không có requirements.txt"
    try:
        p = subprocess.run([_python_exe(), "-m", "pip", "install", "--disable-pip-version-check", "-r", req],
                           cwd=directory, capture_output=True, text=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"không chạy được pip ({e})"
    if p.returncode != 0:
        tail = (p.stderr or p.stdout or "").strip().splitlines()[-3:]
        return False, "pip báo lỗi: " + " | ".join(tail)
    return True, "đã cài thư viện"


def spawn_restart(directory=None, delay_s=3):
    """Mở lại Dashboard SAU `delay_s` giây (chờ app hiện tại đóng xong và lưu cài đặt)."""
    directory = directory or app_dir()
    exe = sys.executable
    code = ("import subprocess,sys,time; time.sleep(float(sys.argv[4])); "
            "subprocess.Popen([sys.argv[1], sys.argv[2]], cwd=sys.argv[3])")
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0x8) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200) \
            | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    subprocess.Popen([_python_exe() if os.name == "nt" else exe, "-c", code, exe,
                      os.path.join(directory, MUST_HAVE), directory, str(delay_s)],
                     creationflags=flags, close_fds=True)


# ------------------------------------------------------------------ dòng lệnh
def diagnose(print_fn=print):
    """Thử từng tầng mạng tới GitHub và in kết quả - gửi nguyên văn cho người hỗ trợ khi cập nhật lỗi."""
    import platform
    out = print_fn
    out(f"Python {platform.python_version()} | {ssl.OPENSSL_VERSION} | {platform.platform()}")
    out("Giờ máy: " + time.strftime("%Y-%m-%d %H:%M:%S") + "  (sai ngày giờ làm HTTPS lỗi)")
    prox = {}
    try:
        prox = {k: v[:80] for k, v in urllib.request.getproxies().items() if k in ("http", "https", "all")}
    except Exception:
        pass
    out("Proxy: " + (str(prox) if prox else "không có"))
    for host in ("api.github.com", "github.com"):
        try:
            ips = sorted({a[4][0] for a in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)})
            out(f"[DNS] {host} -> {', '.join(ips[:3])}")
        except OSError as e:
            out(f"[DNS] {host} LỖI: {e}")
            continue
        try:
            with socket.create_connection((host, 443), timeout=8):
                out(f"[TCP 443] {host} OK")
        except OSError as e:
            out(f"[TCP 443] {host} LỖI: {e}")
            continue
        try:
            with _open(f"https://{host}/", 10, accept="text/html") as r:
                out(f"[HTTPS] {host} OK (HTTP {r.status})")
        except urllib.error.HTTPError as e:
            out(f"[HTTPS] {host} OK (máy chủ trả HTTP {e.code})")
        except Exception as e:
            out(f"[HTTPS] {host} LỖI: {describe_net_error(e, host)}")
    try:
        latest = fetch_latest()
        out("[Bản mới nhất] " + (f"{latest['tag']} (nguồn: {latest['source']})" if latest else "chưa có Release nào"))
    except UpdateError as e:
        out(f"[Bản mới nhất] LỖI: {e}")
    return 0


def _main(argv):
    if "--chan-doan" in argv:
        return diagnose()
    if "--kiem-tra" in argv or "--cap-nhat" in argv:
        res = check_for_update()
        print(res["message"], f"(đang cài: {res['installed'] or 'chưa ghi'}"
                              + (f", mới nhất: {res['latest']['tag']}" if res["latest"] else "") + ")")
        if "--cap-nhat" in argv and res["status"] == "available":
            try:
                r = update_to_latest(res["latest"], on_log=print)
            except UpdateError as e:
                print("LỖI:", e)
                return 1
            print(f"Xong: {len(r['changed'])} file đổi. Backup: {r['backup_dir'] or '(không có file cũ bị đổi)'}")
            if r["needs_pip"]:
                print("requirements.txt đổi ->", install_requirements()[1])
            print("Mở lại Dashboard để dùng bản mới.")
        return 0 if res["status"] != "error" else 1
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))

"""
publisher.py - PHÁT HÀNH bản cập nhật lên GitHub (logic thuần, chỉ thư viện chuẩn, không dùng tkinter).

Nút '🚀 Phát Hành' trong Dashboard (dashboard_publish.py) gọi file này. Bạn chọn các MỤC muốn phát hành
(code, kịch bản, ảnh mẫu, ...) -> chương trình:
  1) kiểm token + quyền ghi + repo công khai hay riêng tư;
  2) dựng 1 gói zip ADB-THTG_update.zip có manifest.json (danh sách file + SHA-256 từng file);
  3) tạo Release (bản NHÁP) với tag số phiên bản tự tăng vYYYY.MM.DD (.2, .3 nếu phát hành nhiều lần/ngày);
  4) tải gói lên làm file đính kèm của Release, rồi mới CÔNG BỐ (máy khác không bao giờ thấy bản thiếu gói;
     lỗi giữa chừng thì xoá bản nháp);
  5) ghi phiên bản này vào data/app_version.json của chính máy phát hành (khỏi báo 'có bản mới' cho chính nó).
Các máy khác mở Dashboard sẽ thấy nút '🔄 Có bản mới' (xem updater.py / dashboard_update.py).

MỤC BỊ KHOÁ (không bao giờ phát hành qua GitHub, kể cả khi gọi bằng code): 'tai_khoan' (mật khẩu game của người dùng)
và 'cai_dat_dashboard' (đường dẫn máy + token Telegram). Repo công khai = ai cũng tải được gói. Muốn chuyển tài khoản
giữa các máy hãy dùng dong_goi_dong_bo.py (file zip tự mang đi).

TOKEN GITHUB: lưu ở data/publish_config.json (thư mục data/ không được đẩy lên GitHub và không bao giờ nằm trong gói).
Nên dùng Fine-grained personal access token, chỉ cấp cho repo này, quyền 'Contents: Read and write'.
Không bao giờ ghi token ra nhật ký/thông báo lỗi.

Dòng lệnh:
    python publisher.py --liet-ke                         xem các mục + số file hiện có
    python publisher.py --phat-hanh --chon code,kich_ban  phát hành (cần token đã lưu); thêm --ghi-chu "nội dung"
"""
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
import zipfile

import updater

REPO = updater.GITHUB_REPO
API_BASE = "https://api.github.com"          # đổi được khi kiểm thử (server giả)
USER_AGENT = "ADB-THTG-Publisher"
HTTP_TIMEOUT = 30
UPLOAD_TIMEOUT = 900
MAX_PACKAGE_BYTES = 250 * 1024 * 1024        # chặn gói quá lớn (zip)
MAX_UNPACKED_BYTES = 600 * 1024 * 1024
CONFIG_REL = os.path.join("data", "publish_config.json")
TMP_DIRNAME = os.path.join(updater.STAGE_DIRNAME, "publish")

# key, tên hiển thị, gợi ý, tick sẵn?, lý do khoá ("" = không khoá). Khoá khớp dong_goi_dong_bo.py.
CATEGORIES = [
    {"key": "code", "label": "Code chương trình", "default": True, "locked": "",
     "hint": "Các file .py ở thư mục gốc + requirements.txt (trừ build_installer/build_portable/ap_dung_*)."},
    {"key": "kich_ban", "label": "Kịch bản / Hoạt Động (tasks/)", "default": True, "locked": "",
     "hint": "Toàn bộ tasks/*.json - nội dung các Hoạt Động."},
    {"key": "nhom_ngoai", "label": "Nhóm Ngoài (groups/)", "default": True, "locked": "",
     "hint": "groups/*.json - nhóm thao tác dùng cho bước 'Nhóm'."},
    {"key": "anh_mau", "label": "Ảnh mẫu (templates/)", "default": True, "locked": "",
     "hint": "Ảnh dùng cho wait_image / if_image. Có thể nặng."},
    {"key": "hoat_dong", "label": "Tuỳ chỉnh Hoạt Động", "default": True, "locked": "",
     "hint": "data/task_registry.json - tên hiển thị, mục, thứ tự, bật mặc định. GHI ĐÈ nguyên file trên máy nhận."},
    {"key": "nhom_hanh_dong", "label": "Nhóm Hành Động", "default": True, "locked": "",
     "hint": "data/activity_groups.json. GHI ĐÈ nguyên file trên máy nhận."},
    {"key": "bien", "label": "Quản Lý Biến", "default": False, "locked": "",
     "hint": "data/variables.json - có thể là giá trị riêng từng máy. GHI ĐÈ nguyên file trên máy nhận."},
    {"key": "nhom_du_lieu", "label": "Nhóm Dữ Liệu", "default": False, "locked": "",
     "hint": "data/data_groups.json. GHI ĐÈ nguyên file trên máy nhận."},
    {"key": "lich_hen_gio", "label": "Lịch Hẹn Giờ", "default": False, "locked": "",
     "hint": "data/schedules.json - gán giả lập theo SỐ THỨ TỰ, dễ sai nếu 2 máy khác nhau. GHI ĐÈ nguyên file."},
    {"key": "tai_khoan", "label": "Tài khoản", "default": False,
     "locked": "Không phát hành qua GitHub: repo công khai thì ai cũng tải được mật khẩu game. "
               "Dùng dong_goi_dong_bo.py để chuyển tài khoản giữa các máy.",
     "hint": ""},
    {"key": "cai_dat_dashboard", "label": "Cài đặt Dashboard", "default": False,
     "locked": "Không phát hành: chứa đường dẫn riêng từng máy và token Telegram.", "hint": ""},
]
CATEGORY_BY_KEY = {c["key"]: c for c in CATEGORIES}


class PublishError(Exception):
    """Lỗi đọc được bằng tiếng Việt - nơi gọi hiện nguyên văn. Không bao giờ chứa token."""


def app_dir():
    return updater.app_dir()


# ------------------------------------------------------------------ cấu hình + token
def load_config(directory=None):
    path = os.path.join(directory or app_dir(), CONFIG_REL)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(directory, token=None, repo=None):
    """Lưu token/repo vào data/publish_config.json (giữ giá trị cũ nếu tham số là None)."""
    directory = directory or app_dir()
    cfg = load_config(directory)
    if token is not None:
        cfg["token"] = token.strip()
    if repo is not None:
        cfg["repo"] = repo.strip()
    path = os.path.join(directory, CONFIG_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    return cfg


def mask(token):
    token = token or ""
    return "(chưa có)" if not token else (token[:4] + "…" + token[-2:] if len(token) > 10 else "•" * len(token))


# ------------------------------------------------------------------ quét các mục
def scan(directory=None):
    """{key: {'files': [(rel 'a/b', đường dẫn tuyệt đối, bytes)], 'count': n, 'bytes': n}} cho MỌI mục không khoá.
    Mỗi file đều đã qua updater.classify() - cùng bộ lọc mà máy nhận dùng."""
    directory = directory or app_dir()
    out = {c["key"]: {"files": [], "count": 0, "bytes": 0} for c in CATEGORIES if not c["locked"]}

    def _add(rel_parts, abspath):
        if os.path.islink(abspath) or not os.path.isfile(abspath):
            return
        cat = updater.classify(rel_parts)
        if cat in out:
            size = os.path.getsize(abspath)
            e = out[cat]
            e["files"].append(("/".join(rel_parts), abspath, size))
            e["count"] += 1
            e["bytes"] += size

    try:
        for name in sorted(os.listdir(directory)):
            _add([name], os.path.join(directory, name))
    except OSError:
        pass
    for top in updater.SYNC_DIRS:
        base = os.path.join(directory, top)
        for d, dirs, files in os.walk(base):
            dirs[:] = sorted(x for x in dirs if x not in ("backup", "__pycache__"))
            for fn in sorted(files):
                rel = os.path.relpath(os.path.join(d, fn), directory).replace("\\", "/").split("/")
                _add(rel, os.path.join(d, fn))
    for fn in sorted(updater.DATA_FILE_CATEGORY):
        _add(["data", fn], os.path.join(directory, "data", fn))
    return out


def _check_keys(keys):
    keys = list(dict.fromkeys(keys or []))
    if not keys:
        raise PublishError("Chưa chọn mục nào để phát hành.")
    for k in keys:
        c = CATEGORY_BY_KEY.get(k)
        if c is None:
            raise PublishError(f"Mục không hợp lệ: {k}.")
        if c["locked"]:
            raise PublishError(f"Mục '{c['label']}' bị khoá: {c['locked']}")
    return keys


def selected_files(directory, keys):
    keys = _check_keys(keys)
    found = scan(directory)
    files = []
    for k in keys:
        files.extend(found[k]["files"])
    return keys, files


# ------------------------------------------------------------------ dựng gói
def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_package(directory, keys, tag, notes, dest_path):
    """Ghi gói zip (manifest.json + các file đã chọn) vào dest_path. Trả thông tin để hiển thị."""
    keys, files = selected_files(directory, keys)
    if not files:
        raise PublishError("Các mục đã chọn hiện không có file nào để phát hành.")
    total = sum(s for _r, _a, s in files)
    if total > MAX_UNPACKED_BYTES:
        raise PublishError(f"Dung lượng quá lớn ({total // (1024 * 1024)} MB) - bỏ bớt mục (vd ảnh mẫu).")
    manifest_files = []
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for rel, ab, _size in files:
                if updater.classify(rel.split("/")) is None:       # chốt chặn thứ 2, không bao giờ nên xảy ra
                    raise PublishError(f"File không nằm trong danh sách cho phép: {rel}")
                sha = _sha256_file(ab)
                zf.write(ab, rel)
                manifest_files.append({"path": rel, "sha256": sha, "size": os.path.getsize(ab)})
            manifest = {"format": 1, "tag": tag, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "categories": keys, "notes": (notes or "")[:2000], "files": manifest_files}
            zf.writestr(updater.MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=1))
    except OSError as e:
        raise PublishError(f"Không đóng gói được ({e}).")
    zsize = os.path.getsize(dest_path)
    if zsize > MAX_PACKAGE_BYTES:
        os.remove(dest_path)
        raise PublishError(f"Gói nén quá lớn ({zsize // (1024 * 1024)} MB, tối đa {MAX_PACKAGE_BYTES // (1024 * 1024)} MB).")
    return {"files": len(files), "bytes": total, "zip_bytes": zsize, "categories": keys}


# ------------------------------------------------------------------ GitHub API
def _api(method, url, token, body=None, raw=None, ctype=None, timeout=HTTP_TIMEOUT):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json",
               "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif raw is not None:
        data = raw
        headers["Content-Type"] = ctype or "application/octet-stream"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
            return json.loads(payload.decode("utf-8")) if payload else {}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = str(json.loads(e.read().decode("utf-8")).get("message") or "")
        except Exception:
            pass
        detail = detail.replace(token, "***")[:200]
        if e.code == 401:
            raise PublishError("Token sai hoặc đã hết hạn. Tạo token mới và dán lại.")
        if e.code == 403:
            raise PublishError("Token không đủ quyền (cần 'Contents: Read and write' cho repo này) hoặc GitHub "
                               "đang giới hạn lượt gọi." + (f" ({detail})" if detail else ""))
        if e.code == 404:
            raise PublishError("Không thấy repo, hoặc token không có quyền vào repo này.")
        if e.code == 422:
            raise PublishError("GitHub từ chối dữ liệu" + (f": {detail}" if detail else "") + ".")
        raise PublishError(f"GitHub trả lỗi HTTP {e.code}." + (f" ({detail})" if detail else ""))
    except (urllib.error.URLError, OSError, TimeoutError):
        raise PublishError("Không kết nối được GitHub (kiểm tra mạng).")
    except ValueError:
        raise PublishError("GitHub trả dữ liệu không đọc được.")


def check_access(token, repo=None):
    """Kiểm token + quyền ghi. Trả {'full_name','private','can_push','default_branch'}."""
    if not (token or "").strip():
        raise PublishError("Chưa có token GitHub. Dán token vào ô 'Token' rồi thử lại.")
    repo = repo or REPO
    info = _api("GET", f"{API_BASE}/repos/{repo}", token)
    perms = info.get("permissions")
    can_push = bool(perms.get("push") or perms.get("admin")) if isinstance(perms, dict) else True
    if not can_push:
        raise PublishError("Token này chỉ ĐỌC được repo, không có quyền ghi. Cần quyền 'Contents: Read and write'.")
    return {"full_name": str(info.get("full_name") or repo), "private": bool(info.get("private")),
            "can_push": can_push, "default_branch": str(info.get("default_branch") or "main")}


def next_tag(token, repo=None, today=None):
    """Tag số phiên bản kế tiếp: vYYYY.MM.DD, rồi .2, .3 ... - luôn LỚN HƠN mọi tag số đang có."""
    repo = repo or REPO
    existing = set()
    for ep in ("tags", "releases"):
        items = _api("GET", f"{API_BASE}/repos/{repo}/{ep}?per_page=100", token)
        for it in items if isinstance(items, list) else []:
            n = it.get("name") if ep == "tags" else it.get("tag_name")
            if n:
                existing.add(str(n))
    maxv = max((updater.parse_version(t) for t in existing if updater.parse_version(t)), default=())
    base = time.strftime("v%Y.%m.%d", today or time.localtime())
    for n in range(1, 60):
        cand = base if n == 1 else f"{base}.{n}"
        if cand not in existing and updater.parse_version(cand) > maxv:
            return cand
    raise PublishError("Đã có tag mới hơn hoặc quá nhiều lần phát hành trong ngày - kiểm tra lại các tag trên GitHub.")


def _delete_release(token, repo, rid):
    try:
        _api("DELETE", f"{API_BASE}/repos/{repo}/releases/{rid}", token)
    except PublishError:
        pass


def publish(directory, keys, notes, token, repo=None, progress=None, should_stop=None):
    """Phát hành. Trả {'tag','url','files','zip_bytes','categories','private'}. Mọi lỗi -> PublishError
    (đã dọn bản nháp; không để lại Release hỏng trên GitHub)."""
    directory = directory or app_dir()
    repo = repo or load_config(directory).get("repo") or REPO
    say = progress or (lambda m: None)
    stop = should_stop or (lambda: False)
    keys = _check_keys(keys)
    tmpdir = os.path.join(directory, TMP_DIRNAME)
    zip_path = os.path.join(tmpdir, updater.ASSET_NAME)
    rid = None
    try:
        say("Kiểm tra token và quyền ghi...")
        acc = check_access(token, repo)
        tag = next_tag(token, repo)
        if stop():
            raise PublishError("Đã huỷ.")
        say(f"Đóng gói các mục đã chọn ({tag})...")
        pkg = build_package(directory, keys, tag, notes, zip_path)
        labels = ", ".join(CATEGORY_BY_KEY[k]["label"] for k in keys)
        body = ((notes or "").strip() + "\n\n" if (notes or "").strip() else "") + \
               f"Gồm: {labels} ({pkg['files']} file)."
        if stop():
            raise PublishError("Đã huỷ.")
        say("Tạo bản nháp trên GitHub...")
        rel = _api("POST", f"{API_BASE}/repos/{repo}/releases", token,
                   body={"tag_name": tag, "name": tag, "body": body, "draft": True, "prerelease": False})
        rid = rel.get("id")
        upload_url = str(rel.get("upload_url") or "").split("{")[0]
        if not rid or not upload_url:
            raise PublishError("GitHub không trả thông tin bản nháp hợp lệ.")
        say(f"Tải gói lên ({pkg['zip_bytes'] // 1024} KB)...")
        with open(zip_path, "rb") as f:
            blob = f.read()
        asset = _api("POST", f"{upload_url}?name={updater.ASSET_NAME}", token, raw=blob,
                     ctype="application/zip", timeout=UPLOAD_TIMEOUT)
        if str(asset.get("name")) != updater.ASSET_NAME or str(asset.get("state", "uploaded")) != "uploaded":
            raise PublishError("GitHub chưa nhận đủ gói tải lên.")
        if stop():
            raise PublishError("Đã huỷ.")
        say("Công bố bản phát hành...")
        pub = _api("PATCH", f"{API_BASE}/repos/{repo}/releases/{rid}", token,
                   body={"draft": False, "make_latest": "true"})
        rid = None      # đã công bố - không xoá nữa
        try:
            updater.write_installed(directory, tag, files_changed=0)   # chính máy này không cần 'cập nhật' bản vừa phát hành
        except OSError:
            pass
        return {"tag": tag, "url": str(pub.get("html_url") or ""), "files": pkg["files"], "zip_bytes": pkg["zip_bytes"],
                "categories": keys, "private": acc["private"]}
    except PublishError:
        if rid:
            _delete_release(token, repo, rid)
        raise
    except Exception as e:                 # lỗi lạ: dọn rồi báo bằng tiếng Việt, không lộ token
        if rid:
            _delete_release(token, repo, rid)
        raise PublishError(f"Lỗi không mong đợi khi phát hành: {str(e).replace(token or 'x', '***')[:200]}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
        try:
            os.rmdir(os.path.join(directory, updater.STAGE_DIRNAME))
        except OSError:
            pass


# ------------------------------------------------------------------ dòng lệnh
def _main(argv):
    d = app_dir()
    if "--liet-ke" in argv:
        found = scan(d)
        for c in CATEGORIES:
            if c["locked"]:
                print(f"  🔒 {c['key']:18} {c['label']}  - KHOÁ")
            else:
                e = found[c["key"]]
                print(f"  {'[x]' if c['default'] else '[ ]'} {c['key']:18} {c['label']:34} {e['count']:5} file  {e['bytes'] // 1024:8} KB")
        return 0
    if "--phat-hanh" in argv:
        keys = []
        notes = ""
        if "--chon" in argv:
            keys = [x for x in argv[argv.index("--chon") + 1].split(",") if x]
        if "--ghi-chu" in argv:
            notes = argv[argv.index("--ghi-chu") + 1]
        try:
            r = publish(d, keys, notes, load_config(d).get("token", ""), progress=print)
        except PublishError as e:
            print("LỖI:", e)
            return 1
        print(f"XONG: {r['tag']} - {r['files']} file - {r['url']}")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))

"""
notifier.py — Thông báo ra NGOÀI máy qua Telegram Bot (chỉ dùng thư viện chuẩn
urllib, không cần cài thêm gì).

Dùng ở bất kỳ đâu bằng 1 dòng, KHÔNG BAO GIỜ làm chương trình đứng/lỗi:

    import notifier
    notifier.notify("emu_hung", "Giả lập Clone01 treo...", key="hung:3")

  - notify() chạy NGẦM trong luồng riêng, có timeout, nuốt mọi lỗi (mất mạng,
    token sai...) - chỉ ghi lỗi gần nhất vào notifier.last_error để màn hình
    Cài Đặt hiển thị khi bấm "Gửi thử".
  - Chỉ gửi khi: đã bật Telegram + loại sự kiện đó đang được tick.
  - Chống ngập chat: cùng 1 `key` chỉ gửi tối đa 1 tin / min_interval_sec giây;
    các tin bị bỏ qua được cộng dồn và báo ở tin kế tiếp.

Cấu hình lưu ở data/telegram_config.json (CHỨA TOKEN BÍ MẬT - đã nằm trong
.gitignore, đừng đưa lên GitHub).
"""
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import paths

CONFIG_PATH = paths.resolve_data_path("telegram_config.json")
API_BASE = "https://api.telegram.org"   # có thể ghi đè (vd khi test)

# Loại sự kiện: key -> (nhãn hiển thị ở màn hình Cài Đặt, mặc định bật?)
EVENTS = {
    "task_start": ("Bắt đầu chạy Hoạt Động (kèm giả lập + giờ bắt đầu)", True),
    "task_done": ("Hoàn thành Hoạt Động (kèm giờ bắt đầu/xong + thời gian chạy)", True),
    "task_error": ("Tác vụ lỗi / không chạy được", True),
    "emu_hung": ("Giả lập TREO giữa lúc đang chạy", True),
    "emu_restarted": ("Đã tự khởi động lại giả lập và chạy lại", True),
    "emu_recover_failed": ("KHÔNG cứu được giả lập (đã bỏ cuộc)", True),
    "schedule_done": ("Xong lịch hẹn giờ (tổng kết riêng từng lịch/giả lập: chạy gì, mất bao lâu)", True),
    "all_done": ("Chạy xong toàn bộ phiên (kèm danh sách: chạy gì, giả lập/tài khoản nào, mất bao lâu)", False),
}

DEFAULT_CONFIG = {
    "enabled": False,
    "token": "",
    "chat_id": "",
    "send_screenshot": True,
    "min_interval_sec": 30,
    "events": {k: v[1] for k, v in EVENTS.items()},
}

last_error = None
_rate_lock = threading.Lock()
_last_sent = {}      # key -> thời điểm gửi gần nhất
_suppressed = {}     # key -> số tin đã bị gộp


# ---------------------------------------------------------------- cấu hình
def load_config():
    raw, _warn = paths.load_json_with_recovery(CONFIG_PATH, {})
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if isinstance(raw, dict):
        for k in ("enabled", "token", "chat_id", "send_screenshot", "min_interval_sec"):
            if k in raw:
                cfg[k] = raw[k]
        if isinstance(raw.get("events"), dict):
            for k, v in raw["events"].items():
                if k in cfg["events"]:
                    cfg["events"][k] = bool(v)
    cfg["token"] = str(cfg["token"]).strip()
    cfg["chat_id"] = str(cfg["chat_id"]).strip()
    try:
        cfg["min_interval_sec"] = max(0, int(cfg["min_interval_sec"]))
    except (TypeError, ValueError):
        cfg["min_interval_sec"] = DEFAULT_CONFIG["min_interval_sec"]
    return cfg


def save_config(cfg):
    paths.save_json(CONFIG_PATH, cfg)


# ---------------------------------------------------------------- gọi API
def _mask(text, token):
    text = str(text)
    return text.replace(token, "<token>") if token else text


def _post(method, token, fields, files=None, timeout=12):
    """Gọi 1 method của Telegram Bot API. Trả về (ok, thông_báo)."""
    if not token:
        return False, "Chưa nhập Bot Token."
    url = f"{API_BASE}/bot{token}/{method}"
    try:
        if files:
            boundary = "----thtg" + uuid.uuid4().hex
            body = bytearray()
            for name, value in fields.items():
                body += (f"--{boundary}\r\nContent-Disposition: form-data; "
                         f'name="{name}"\r\n\r\n{value}\r\n').encode("utf-8")
            for name, (fname, data, ctype) in files.items():
                body += (f"--{boundary}\r\nContent-Disposition: form-data; "
                         f'name="{name}"; filename="{fname}"\r\n'
                         f"Content-Type: {ctype}\r\n\r\n").encode("utf-8")
                body += data + b"\r\n"
            body += f"--{boundary}--\r\n".encode("utf-8")
            req = urllib.request.Request(url, data=bytes(body), method="POST", headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}"})
        else:
            req = urllib.request.Request(
                url, data=urllib.parse.urlencode(fields).encode("utf-8"), method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")
        if payload.get("ok"):
            return True, "OK"
        return False, _mask(payload.get("description", "Telegram trả về lỗi"), token)
    except urllib.error.HTTPError as e:
        try:
            desc = json.loads(e.read().decode("utf-8", errors="ignore")).get("description", "")
        except Exception:
            desc = ""
        return False, _mask(f"HTTP {e.code} {desc}".strip(), token)
    except Exception as e:
        return False, _mask(f"{type(e).__name__}: {e}", token)


def send_message(text, token, chat_id, timeout=12):
    if not chat_id:
        return False, "Chưa nhập Chat ID."
    return _post("sendMessage", token,
                 {"chat_id": chat_id, "text": text[:4000]}, timeout=timeout)


def send_photo(jpeg_bytes, caption, token, chat_id, timeout=20):
    if not chat_id:
        return False, "Chưa nhập Chat ID."
    return _post("sendPhoto", token,
                 {"chat_id": chat_id, "caption": caption[:1000]},
                 files={"photo": ("screen.jpg", jpeg_bytes, "image/jpeg")}, timeout=timeout)


def encode_jpeg(img_bgr, quality=70):
    """Ảnh OpenCV BGR -> bytes JPEG (None nếu lỗi/không có ảnh)."""
    if img_bgr is None:
        return None
    try:
        import cv2
        ok, buf = cv2.imencode(".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        return bytes(buf) if ok else None
    except Exception:
        return None


def send_test(token, chat_id):
    """Gửi tin thử (dùng cho nút 'Gửi thử' - chạy ĐỒNG BỘ, gọi từ luồng nền)."""
    ok, msg = send_message(f"✅ ADB-THTG kết nối Telegram thành công ({socket.gethostname()}).",
                           token, chat_id)
    return ok, msg


# ---------------------------------------------------------------- gửi nền
def notify(event, text, key=None, photo_jpeg=None, force=False):
    """Gửi 1 thông báo NGẦM (không chặn, không ném lỗi). Xem docstring đầu file.
    force=True: bỏ qua chống ngập (dùng cho tin bắt đầu/hoàn thành - mỗi lần
    chạy đều phải có tin riêng, dù tác vụ chỉ chạy vài giây)."""
    try:
        cfg = load_config()
        if not cfg["enabled"] or not cfg["token"] or not cfg["chat_id"]:
            return False
        if not cfg["events"].get(event, False):
            return False
        rl_key = key or event
        now = time.time()
        extra = ""
        with _rate_lock:
            last = _last_sent.get(rl_key)
            if not force and last is not None and now - last < cfg["min_interval_sec"]:
                _suppressed[rl_key] = _suppressed.get(rl_key, 0) + 1
                return False
            n = _suppressed.pop(rl_key, 0)
            _last_sent[rl_key] = now
        if n:
            extra = f"\n(+{n} thông báo giống nhau đã được gộp)"
        msg = f"[{socket.gethostname()}] {text}{extra}"
        send_photo_flag = bool(photo_jpeg) and cfg["send_screenshot"]
        threading.Thread(target=_worker, args=(cfg, msg, photo_jpeg if send_photo_flag else None),
                         daemon=True).start()
        return True
    except Exception:
        return False


def fmt_time(ts=None):
    """'14:05:33 01/10' - giờ máy, dùng cho nội dung tin nhắn."""
    return time.strftime("%H:%M:%S %d/%m", time.localtime(ts if ts is not None else time.time()))


def fmt_duration(seconds):
    """Số giây -> '2p13s' / '1g05p' / '8s'."""
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}g{m:02d}p"
    if m:
        return f"{m}p{sec:02d}s"
    return f"{sec}s"


def wants_photo(event):
    """True nếu 'event' sẽ được gửi VÀ có kèm ảnh chụp màn hình - để nơi gọi
    chỉ tốn công chụp ảnh khi thật sự cần."""
    try:
        cfg = load_config()
        return bool(cfg["enabled"] and cfg["token"] and cfg["chat_id"]
                    and cfg["events"].get(event, False) and cfg["send_screenshot"])
    except Exception:
        return False


def _worker(cfg, msg, photo_jpeg):
    global last_error
    try:
        if photo_jpeg:
            ok, info = send_photo(photo_jpeg, msg, cfg["token"], cfg["chat_id"])
            if not ok:   # gửi ảnh lỗi -> thử lại chỉ bằng chữ
                ok, info = send_message(msg, cfg["token"], cfg["chat_id"])
        else:
            ok, info = send_message(msg, cfg["token"], cfg["chat_id"])
        last_error = None if ok else info
    except Exception as e:
        last_error = _mask(f"{type(e).__name__}: {e}", cfg.get("token", ""))

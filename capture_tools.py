import os
import time
import cv2


def build_capture_step(kind, filename, default_timeout=8, default_conf=0.80):
    """Dựng dict bước dạng wait_image (Tìm & Click) hoặc if_image (điều kiện IF)
    từ tên file ảnh mẫu vừa cắt được."""
    if kind == "if_image":
        return {
            "action": "if_image",
            "template": filename,
            "timeout": 2,
            "conf": 0.80,
            "repeat": 1,
            "delay": 0.2,
            "comment": f"Nếu thấy [{filename}]"
        }
    return {
        "action": "wait_image",
        "template": filename,
        "timeout": default_timeout,
        "conf": default_conf,
        "click": True,
        "repeat": 1,
        "delay": 1.0,
        "comment": f"Click ảnh: {filename}"
    }


def crop_fixed_box(screen_img, cx, cy, cw, ch):
    """Tính khung cắt cố định kích thước (cw x ch) quanh tâm (cx, cy),
    tự động kẹp trong biên ảnh. Trả về (x1, y1, x2, y2)."""
    scr_h, scr_w = screen_img.shape[:2]
    x1 = max(0, cx - cw // 2)
    y1 = max(0, cy - ch // 2)
    x2 = min(scr_w, x1 + cw)
    y2 = min(scr_h, y1 + ch)
    if x2 - x1 < cw:
        x1 = max(0, x2 - cw)
    if y2 - y1 < ch:
        y1 = max(0, y2 - ch)
    return x1, y1, x2, y2


def save_crop(screen_img, box, templates_dir="templates"):
    """Cắt ảnh theo box (x1,y1,x2,y2) và lưu vào thư mục templates.
    Trả về tên file đã lưu."""
    x1, y1, x2, y2 = box
    crop_img = screen_img[y1:y2, x1:x2]
    cw, ch = x2 - x1, y2 - y1
    filename = f"icon_{cw}x{ch}_{int(time.time() * 10) % 100000}.png"
    cv2.imwrite(os.path.join(templates_dir, filename), crop_img)
    return filename

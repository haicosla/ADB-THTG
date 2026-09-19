"""
script_validator.py — Quét TOÀN BỘ 1 kịch bản (danh sách bước) để tìm các
tham chiếu ảnh mẫu (template) / file Nhóm ngoài (group) / nhãn (label) BỊ
THIẾU TRƯỚC KHI CHẠY, thay vì chỉ phát hiện giữa chừng lúc CHẠY THỬ (trước
đây logic_engine chỉ ghi "warn" vào Nhật Ký rồi bỏ qua bước đó, rất dễ
không ai để ý cho tới khi kịch bản chạy sai giữa chừng).

Dùng cho nút "🔍 Kiểm Tra Kịch Bản" (xem gui_run.py::validate_current_task).

Duyệt ĐỆ QUY vào cả các Nhóm Ngoài (action="group", group_file="...") để
không bỏ sót ảnh nằm sâu bên trong 1 nhóm được nạp từ file khác - các Khối
Nhóm nội bộ (group_start/group_end) KHÔNG cần xử lý riêng vì bản thân
chúng vẫn nằm chung trong CÙNG 1 danh sách phẳng (flat list) với các bước
khác, không tách thành danh sách con trong file JSON.
"""
import os
import json


def _check_step_templates(step, templates_dir, missing_templates):
    tpl = step.get("template")
    if tpl:
        if not os.path.exists(os.path.join(templates_dir, tpl)):
            missing_templates.add(tpl)
    for tpl in (step.get("templates") or []):
        if not os.path.exists(os.path.join(templates_dir, tpl)):
            missing_templates.add(tpl)


def validate_steps(steps, templates_dir="templates", groups_dir="groups", _seen_group_files=None):
    """Trả về dict:
      {
        "missing_templates": [tên file ảnh thiếu, đã sắp xếp theo A-Z],
        "missing_groups":    [tên file Nhóm ngoài thiếu / lỗi đọc],
        "missing_labels":    [tên nhãn được on_fail="skip_to_label" tham
                               chiếu nhưng không có bước 'label' tương ứng
                               trong CÙNG kịch bản/nhóm],
      }
    Không bao giờ ném lỗi ra ngoài - luôn trả về kết quả (rỗng nếu kịch bản
    hợp lệ hoàn toàn), để nơi gọi (GUI) tự quyết định hiển thị ra sao.
    """
    if _seen_group_files is None:
        _seen_group_files = set()

    missing_templates = set()
    missing_groups = set()
    missing_labels = set()

    # skip_to_label chỉ tìm nhãn TRONG CÙNG 1 danh sách steps (đúng như
    # LogicEngine.find_label_index thật sự làm khi chạy) - nên chỉ cần xét
    # các nhãn có mặt NGAY TRONG danh sách steps hiện tại đang được duyệt.
    label_names_here = {s.get("name") for s in steps if s.get("action") == "label" and s.get("name")}

    for step in steps:
        act = step.get("action")
        _check_step_templates(step, templates_dir, missing_templates)

        if step.get("on_fail") == "skip_to_label":
            label_name = step.get("skip_to_label_name")
            if label_name and label_name not in label_names_here:
                missing_labels.add(label_name)

        if act == "group":
            g_file = step.get("group_file", "")
            if g_file:
                g_path = os.path.join(groups_dir, g_file)
                if not os.path.exists(g_path):
                    missing_groups.add(g_file)
                elif g_file not in _seen_group_files:
                    # Đánh dấu ĐÃ XÉT trước khi đệ quy để tránh lặp vô hạn
                    # nếu 2 file Nhóm ngoài lỡ tham chiếu vòng tròn lẫn nhau.
                    _seen_group_files.add(g_file)
                    try:
                        with open(g_path, "r", encoding="utf-8") as f:
                            sub_steps = json.load(f)
                        sub_result = validate_steps(sub_steps, templates_dir, groups_dir, _seen_group_files)
                        missing_templates.update(sub_result["missing_templates"])
                        missing_groups.update(sub_result["missing_groups"])
                        missing_labels.update(sub_result["missing_labels"])
                    except Exception as e:
                        missing_groups.add(f"{g_file} (lỗi đọc file JSON: {e})")

    return {
        "missing_templates": sorted(missing_templates),
        "missing_groups": sorted(missing_groups),
        "missing_labels": sorted(missing_labels),
    }


def has_issues(result):
    return bool(result["missing_templates"] or result["missing_groups"] or result["missing_labels"])


def format_validation_report(result):
    """Định dạng kết quả validate_steps() thành 1 chuỗi văn bản dễ đọc để
    hiển thị trong messagebox/log. Trả về '' nếu không có gì thiếu."""
    lines = []
    if result["missing_templates"]:
        lines.append(f"🖼️ Thiếu {len(result['missing_templates'])} file ảnh mẫu (trong thư mục templates/):")
        lines.extend(f"   - {t}" for t in result["missing_templates"])
    if result["missing_groups"]:
        lines.append(f"📦 Thiếu {len(result['missing_groups'])} file Nhóm ngoài (trong thư mục groups/):")
        lines.extend(f"   - {g}" for g in result["missing_groups"])
    if result["missing_labels"]:
        lines.append(f"🏷️ Thiếu {len(result['missing_labels'])} nhãn (label) được on_fail=skip_to_label tham chiếu nhưng không tồn tại:")
        lines.extend(f"   - {l}" for l in result["missing_labels"])
    return "\n".join(lines)

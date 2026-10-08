"""
safe_calc.py — Tính biểu thức số học ĐƠN GIẢN và AN TOÀN (KHÔNG dùng eval()).

Dùng cho các ô số có thể chứa biến, vd 'Sửa Lặp' = '{sach}-1' hay
'{so_phut}*60000' (xem LogicEngine._resolve_step_number trong
logic_engine.py và _parse_repeat_input trong gui_manual_steps.py). Chỉ nhận:
số (nguyên/thực), + - * /, dấu ngoặc (), dấu +/- đứng trước số. Bất kỳ thứ gì
khác (tên biến còn sót, hàm, luỹ thừa...) đều bị từ chối bằng ValueError.
Tách thành module riêng (không import cv2/tkinter) để cả engine lẫn giao diện
soạn kịch bản cùng dùng được mà không kéo theo thư viện nặng.
"""
import ast
import operator

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_MAX_LEN = 200


def safe_calc(text):
    """Trả về kết quả (float) của biểu thức `text`. Ném ValueError nếu biểu
    thức không hợp lệ/không an toàn, ZeroDivisionError nếu chia cho 0."""
    text = str(text).strip()
    if not text or len(text) > _MAX_LEN:
        raise ValueError("biểu thức rỗng hoặc quá dài")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"sai cú pháp: {e}")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = ev(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        raise ValueError("chỉ hỗ trợ số và các phép + - * / ( )")

    return ev(tree)

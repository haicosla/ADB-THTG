# -*- coding: utf-8 -*-
"""
Bot auto-play cho game giải đố dạng "merge 2048" trên lưới 4x4, điều khiển qua ADB.

Cơ chế game (suy từ ảnh mẫu "Tạo Dựng Ngôi Sao"):
- 16 ô, mỗi ô chứa vật phẩm có nhãn "cấp độ" (1, 2, 3, ..., 11).
- Hai ô cùng cấp độ L khi gộp lại tạo ra 1 ô cấp độ L+1 (bản chất 2048: value = 2^level).
- Ô cấp 11 là cấp tối đa, không thể gộp thêm.

Tích hợp chế độ test:
- Khi step có "max_moves": 0, bot chỉ chụp 1 frame, phân tích bàn cờ,
  in ma trận 4x4 ra log và lưu ảnh kết quả vào thư mục debug_merge2048/, tuyệt đối không vuốt.
"""

from __future__ import annotations

import os
import time
import copy
import json
from collections import Counter
import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import cv2


# =====================================================================================
# 1) BoardDetector
# =====================================================================================
class BoardDetector:
    """
    Nhận ảnh full màn hình -> cắt vùng bàn cờ (ROI) -> chia lưới 4x4 -> đọc "level"
    của từng ô (badge số ở góc trên-trái mỗi ô).
    """

    GRID_SIZE = 4

    def __init__(
        self,
        top_left: tuple[int, int],
        bottom_right: tuple[int, int],
        templates_dir: Optional[str] = None,
        badge_frac: tuple[float, float] = (0.42, 0.42),
        badge_anchor: str = "top-left",
        match_threshold: float = 0.8,
        empty_match_threshold: float = 0.35,
        empty_std_threshold: float = 6.0,
        debug: bool = False,
    ):
        self.top_left = top_left
        self.bottom_right = bottom_right
        self.templates_dir = templates_dir
        self.badge_frac = badge_frac
        self.badge_anchor = badge_anchor
        self.match_threshold = match_threshold
        self.empty_match_threshold = empty_match_threshold
        self.empty_std_threshold = empty_std_threshold
        self.debug = debug

        self._templates: dict[int, np.ndarray] = {}
        if templates_dir and os.path.isdir(templates_dir):
            self._load_templates(templates_dir)

        self._ocr = None
        try:
            import pytesseract  # type: ignore
            self._ocr = pytesseract
        except ImportError:
            self._ocr = None

        if self.debug:
            os.makedirs("debug_cells", exist_ok=True)

    def can_identify(self) -> bool:
        """True nếu có ít nhất 1 template số (khác 0)."""
        return any(lv != 0 for lv in self._templates)

    def diagnostics(self) -> str:
        levels = sorted(lv for lv in self._templates if lv != 0)
        return f"template số: {len(levels)} ảnh {levels if levels else '(không có)'}"

    def _load_templates(self, folder: str) -> None:
        for fname in os.listdir(folder):
            name, ext = os.path.splitext(fname)
            if ext.lower() not in (".png", ".jpg", ".jpeg", ".bmp"):
                continue
            if not name.isdigit():
                continue
            img = cv2.imread(os.path.join(folder, fname), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                self._templates[int(name)] = img

    def _crop_roi(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        x1, y1 = max(0, self.top_left[0]), max(0, self.top_left[1])
        x2, y2 = min(w, self.bottom_right[0]), min(h, self.bottom_right[1])
        if x2 - x1 < 8 or y2 - y1 < 8:
            raise ValueError(f"ROI nằm ngoài ảnh {w}x{h}: {self.top_left}->{self.bottom_right}")
        return frame[y1:y2, x1:x2]

    def _cell_crops(self, roi: np.ndarray) -> list[np.ndarray]:
        h, w = roi.shape[:2]
        cell_h, cell_w = h / self.GRID_SIZE, w / self.GRID_SIZE
        cells = []
        for r in range(self.GRID_SIZE):
            for c in range(self.GRID_SIZE):
                y1, y2 = int(r * cell_h), int((r + 1) * cell_h)
                x1, x2 = int(c * cell_w), int((c + 1) * cell_w)
                cells.append(roi[y1:y2, x1:x2])
        return cells

    def _badge_crop(self, cell: np.ndarray) -> np.ndarray:
        h, w = cell.shape[:2]
        bw = max(1, int(w * self.badge_frac[0]))
        bh = max(1, int(h * self.badge_frac[1]))
        if self.badge_anchor == "top-left":
            return cell[0:bh, 0:bw]
        if self.badge_anchor == "top-right":
            return cell[0:bh, w - bw:w]
        if self.badge_anchor == "bottom-left":
            return cell[h - bh:h, 0:bw]
        return cell[h - bh:h, w - bw:w]

    def _is_empty_cell(self, cell: np.ndarray) -> bool:
        gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY) if cell.ndim == 3 else cell
        return float(np.std(gray)) < self.empty_std_threshold

    def _badge_window(self):
        f = 0.6
        fx = (0.0, f) if "left" in self.badge_anchor else (1.0 - f, 1.0)
        fy = (0.0, f) if "top" in self.badge_anchor else (1.0 - f, 1.0)
        return fx[0], fx[1], fy[0], fy[1]

    def _find_levels(self, roi_gray: np.ndarray):
        H, W = roi_gray.shape[:2]
        ch, cw = H / self.GRID_SIZE, W / self.GRID_SIZE
        fx0, fx1, fy0, fy1 = self._badge_window()
        per_cell = {}
        for level, t in self._templates.items():
            if level == 0:
                continue
            th, tw = t.shape[:2]
            if th > H or tw > W or th < 3 or tw < 3:
                continue
            if float(t.std()) < 1e-3:
                res = 1.0 - cv2.matchTemplate(roi_gray, t, cv2.TM_SQDIFF_NORMED)
            else:
                res = cv2.matchTemplate(roi_gray, t, cv2.TM_CCOEFF_NORMED)
            rh, rw = res.shape
            for r in range(self.GRID_SIZE):
                for c in range(self.GRID_SIZE):
                    x0 = int(c * cw + fx0 * cw - tw / 2)
                    x1 = int(c * cw + fx1 * cw - tw / 2)
                    y0 = int(r * ch + fy0 * ch - th / 2)
                    y1 = int(r * ch + fy1 * ch - th / 2)
                    x0, x1 = max(0, x0), min(rw, x1 + 1)
                    y0, y1 = max(0, y0), min(rh, y1 + 1)
                    if x1 <= x0 or y1 <= y0:
                        continue
                    win = res[y0:y1, x0:x1]
                    idx = np.nanargmax(win)
                    sc = float(win.flat[idx])
                    if sc >= self.match_threshold:
                        yy, xx = divmod(idx, win.shape[1])
                        per_cell.setdefault((r, c), []).append(
                            (level, sc, th * tw, (x0 + xx, y0 + yy, tw, th))
                        )
        found = {}
        for key, cands in per_cell.items():
            cands.sort(key=lambda x: -x[1])
            top = cands[0][1]
            if top >= 0.9:
                near = [x for x in cands if x[1] >= top - 0.10]
                best = max(near, key=lambda x: (x[2], x[1]))
            else:
                if len(cands) >= 2 and cands[0][0] != cands[1][0] and cands[0][1] - cands[1][1] < 0.05:
                    continue
                best = cands[0]
            found[key] = best
        return found

    def detect(self, frame_bgr: np.ndarray) -> np.ndarray:
        roi = self._crop_roi(frame_bgr)
        self.last_roi = roi
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
        matrix = np.zeros((self.GRID_SIZE, self.GRID_SIZE), dtype=int)
        self.last_scores = [[None] * self.GRID_SIZE for _ in range(self.GRID_SIZE)]
        self.last_hits = {}

        found = self._find_levels(roi_gray) if self._templates else {}
        for (r, c), (level, sc, _, box) in found.items():
            matrix[r, c] = level
            self.last_hits[(r, c)] = (level, sc, box)
        for r in range(self.GRID_SIZE):
            for c in range(self.GRID_SIZE):
                f = found.get((r, c))
                self.last_scores[r][c] = (
                    int(matrix[r, c]),
                    f[0] if f else None,
                    round(f[1], 2) if f else None,
                    None,
                )
        return matrix

    def score_report(self) -> str:
        rows = []
        for r in range(self.GRID_SIZE):
            cells = []
            for c in range(self.GRID_SIZE):
                s = getattr(self, "last_scores", None)
                if not s or s[r][c] is None:
                    cells.append("?")
                    continue
                lv, bl, bs, es = s[r][c]
                cells.append(f"{lv}({bl}:{bs})")
            rows.append("  ".join(cells))
        return "\n".join(rows)

    def save_debug(self, folder: str = "debug_merge2048") -> str:
        os.makedirs(folder, exist_ok=True)
        roi = getattr(self, "last_roi", None)
        if roi is None:
            return os.path.abspath(folder)
        cv2.imwrite(os.path.join(folder, "roi.png"), roi)
        ann = roi.copy() if roi.ndim == 3 else cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
        H, W = ann.shape[:2]
        ch, cw = H / self.GRID_SIZE, W / self.GRID_SIZE
        for i in range(1, self.GRID_SIZE):
            cv2.line(ann, (int(i * cw), 0), (int(i * cw), H), (0, 0, 255), 2)
            cv2.line(ann, (0, int(i * ch)), (W, int(i * ch)), (0, 0, 255), 2)
        for (r, c), (lv, sc, (x, y, w, h)) in getattr(self, "last_hits", {}).items():
            cv2.rectangle(ann, (x, y), (x + w, y + h), (0, 255, 0), 2)
        s = getattr(self, "last_scores", None)
        if s:
            for r in range(self.GRID_SIZE):
                for c in range(self.GRID_SIZE):
                    if s[r][c] is not None:
                        val_str = str(s[r][c][0]) if s[r][c][0] > 0 else "."
                        color = (255, 0, 0) if s[r][c][0] > 0 else (128, 128, 128)
                        cv2.putText(
                            ann,
                            val_str,
                            (int(c * cw + cw * 0.35), int(r * ch + ch * 0.65)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.5,
                            color,
                            3,
                        )
        cv2.imwrite(os.path.join(folder, "roi_annotated.png"), ann)
        for idx, cell in enumerate(self._cell_crops(roi)):
            r, c = divmod(idx, self.GRID_SIZE)
            cv2.imwrite(os.path.join(folder, f"cell_{r}_{c}.png"), cell)
        return os.path.abspath(folder)


# =====================================================================================
# 2) ExpectimaxSolver
# =====================================================================================
DIRECTIONS = ("UP", "DOWN", "LEFT", "RIGHT")
MAX_LEVEL = 11  # Cấp 11 không gộp thêm được theo luật game[cite: 2]


def _value_of(level: int) -> int:
    return 0 if level <= 0 else (1 << level)


class _SearchTimeout(Exception):
    pass


def _compress_and_merge(line: np.ndarray, max_level: int = MAX_LEVEL) -> tuple[np.ndarray, bool, int]:
    vals = [v for v in line if v != 0]
    merged: list[int] = []
    gained = 0
    i = 0
    while i < len(vals):
        can_merge = (
            i + 1 < len(vals)
            and vals[i] == vals[i + 1]
            and vals[i] < max_level
        )
        if can_merge:
            new_level = vals[i] + 1
            merged.append(new_level)
            gained += _value_of(new_level)
            i += 2
        else:
            merged.append(vals[i])
            i += 1
    merged.extend([0] * (len(line) - len(merged)))
    new_line = np.array(merged, dtype=line.dtype)
    changed = not np.array_equal(new_line, line)
    return new_line, changed, gained


def simulate_move(matrix: np.ndarray, direction: str) -> tuple[np.ndarray, bool, int]:
    m = matrix.copy()
    total_gain = 0
    changed_any = False

    if direction == "LEFT":
        for r in range(4):
            new_row, changed, gained = _compress_and_merge(m[r])
            m[r] = new_row
            changed_any |= changed
            total_gain += gained
    elif direction == "RIGHT":
        for r in range(4):
            new_row, changed, gained = _compress_and_merge(m[r][::-1])
            m[r] = new_row[::-1]
            changed_any |= changed
            total_gain += gained
    elif direction == "UP":
        for c in range(4):
            new_col, changed, gained = _compress_and_merge(m[:, c])
            m[:, c] = new_col
            changed_any |= changed
            total_gain += gained
    elif direction == "DOWN":
        for c in range(4):
            new_col, changed, gained = _compress_and_merge(m[:, c][::-1])
            m[:, c] = new_col[::-1]
            changed_any |= changed
            total_gain += gained
    else:
        raise ValueError(f"Hướng không hợp lệ: {direction}")

    return m, changed_any, total_gain


_LOST_PENALTY = 200000.0
_MONO_POWER, _MONO_WEIGHT = 4.0, 47.0
_SUM_POWER, _SUM_WEIGHT = 3.5, 11.0
_MERGES_WEIGHT = 700.0
_EMPTY_WEIGHT = 270.0
_DEAD_VALUE = -1.0e7
_TABLES = None


def _transpose(x: int) -> int:
    a1 = x & 0xF0F00F0FF0F00F0F
    a2 = x & 0x0000F0F00000F0F0
    a3 = x & 0x0F0F00000F0F0000
    a = a1 | (a2 << 12) | (a3 >> 12)
    b1 = a & 0xFF00FF0000FF00FF
    b2 = a & 0x00FF00FF00000000
    b3 = a & 0x00000000FF00FF00
    return b1 | (b2 >> 24) | (b3 << 24)


def _merge_line(line: list, max_level: int) -> list:
    vals = [v for v in line if v]
    out: list = []
    i = 0
    while i < len(vals):
        if i + 1 < len(vals) and vals[i] == vals[i + 1] and vals[i] < max_level:
            out.append(vals[i] + 1)
            i += 2
        else:
            out.append(vals[i])
            i += 1
    out.extend([0] * (len(line) - len(out)))
    return out


def _build_tables():
    global _TABLES
    if _TABLES is not None:
        return _TABLES
    pw_sum = [float(r) ** _SUM_POWER for r in range(16)]
    pw_mono = [float(r) ** _MONO_POWER for r in range(16)]
    n = 1 << 16
    left, right, heur, nempty, shifts = [0] * n, [0] * n, [0.0] * n, [0] * n, [()] * n
    for row in range(n):
        line = [row & 0xF, (row >> 4) & 0xF, (row >> 8) & 0xF, row >> 12]
        s, empty, merges, prev, counter = 0.0, 0, 0, 0, 0
        for rank in line:
            s += pw_sum[rank]
            if rank == 0:
                empty += 1
            else:
                if prev == rank and rank < MAX_LEVEL:
                    counter += 1
                elif counter > 0:
                    merges += 1 + counter
                    counter = 0
                prev = rank
        if counter > 0:
            merges += 1 + counter
        mono_l = mono_r = 0.0
        for i in range(1, 4):
            a, b = line[i - 1], line[i]
            if a > b:
                mono_l += pw_mono[a] - pw_mono[b]
            else:
                mono_r += pw_mono[b] - pw_mono[a]
        heur[row] = (
            _LOST_PENALTY
            + _EMPTY_WEIGHT * empty
            + _MERGES_WEIGHT * merges
            - _MONO_WEIGHT * min(mono_l, mono_r)
            - _SUM_WEIGHT * s
        )
        m = _merge_line(line, MAX_LEVEL)
        left[row] = m[0] | (m[1] << 4) | (m[2] << 8) | (m[3] << 12)
        m = _merge_line(line[::-1], MAX_LEVEL)[::-1]
        right[row] = m[0] | (m[1] << 4) | (m[2] << 8) | (m[3] << 12)
        nempty[row] = empty
        shifts[row] = tuple(4 * i for i in range(4) if line[i] == 0)
    _TABLES = (left, right, heur, nempty, shifts)
    return _TABLES


def _matrix_to_board(matrix: np.ndarray) -> int:
    b = 0
    for i, v in enumerate(np.clip(matrix, 0, 15).ravel().tolist()):
        b |= v << (4 * i)
    return b


def _move_board(b: int, direction: str) -> int:
    left, right = _build_tables()[:2]
    if direction in ("UP", "DOWN"):
        b = _transpose(b)
    tbl = left if direction in ("LEFT", "UP") else right
    nb = (
        tbl[b & 0xFFFF]
        | (tbl[(b >> 16) & 0xFFFF] << 16)
        | (tbl[(b >> 32) & 0xFFFF] << 32)
        | (tbl[b >> 48] << 48)
    )
    return _transpose(nb) if direction in ("UP", "DOWN") else nb


class ExpectimaxSolver:
    def __init__(
        self,
        max_depth: int = 8,
        time_limit: Optional[float] = 0.5,
        spawn_low_level: int = 1,
        spawn_high_level: int = 2,
        spawn_high_prob: float = 0.1,
        cprob_threshold: float = 0.002,
        **_legacy,
    ):
        self.max_depth = max(1, int(max_depth))
        self.time_limit = time_limit
        self.spawn_low_level = spawn_low_level
        self.spawn_high_level = spawn_high_level
        self.spawn_high_prob = spawn_high_prob
        self.cprob_threshold = cprob_threshold
        self.last_depth = 0
        self.last_scores: dict = {}
        self._eval_root, self._tt = self._make_engine()

    def _make_engine(self):
        LEFT, RIGHT, HEUR, NEMPTY, EMPTY_SHIFTS = _build_tables()
        transpose = _transpose
        perf = time.perf_counter
        DEAD = _DEAD_VALUE
        p_high = self.spawn_high_prob
        p_low = 1.0 - p_high
        lv_low, lv_high = self.spawn_low_level, self.spawn_high_level
        thr = self.cprob_threshold

        tt: dict = {}
        deadline = None
        nodes = 0

        def heur(b):
            t = transpose(b)
            return (
                HEUR[b & 0xFFFF]
                + HEUR[(b >> 16) & 0xFFFF]
                + HEUR[(b >> 32) & 0xFFFF]
                + HEUR[b >> 48]
                + HEUR[t & 0xFFFF]
                + HEUR[(t >> 16) & 0xFFFF]
                + HEUR[(t >> 32) & 0xFFFF]
                + HEUR[t >> 48]
            )

        def chance(b, d, cprob):
            nonlocal nodes
            if d <= 0 or cprob < thr:
                return heur(b)
            hit = tt.get(b)
            if hit is not None and hit[0] >= d:
                return hit[1]
            nodes += 1
            if not (nodes & 127) and deadline is not None and perf() > deadline:
                raise _SearchTimeout()
            r0, r1, r2, r3 = b & 0xFFFF, (b >> 16) & 0xFFFF, (b >> 32) & 0xFFFF, b >> 48
            n = NEMPTY[r0] + NEMPTY[r1] + NEMPTY[r2] + NEMPTY[r3]
            if n == 0:
                return heur(b)
            inv = 1.0 / n
            c_lo, c_hi = cprob * p_low * inv, cprob * p_high * inv
            acc_lo = acc_hi = 0.0
            for base, row in ((0, r0), (16, r1), (32, r2), (48, r3)):
                for s in EMPTY_SHIFTS[row]:
                    sh = base + s
                    acc_lo += max_node(b | (lv_low << sh), d, c_lo)
                    acc_hi += max_node(b | (lv_high << sh), d, c_hi)
            val = (acc_lo * p_low + acc_hi * p_high) * inv
            if len(tt) > 1_500_000:
                tt.clear()
            tt[b] = (d, val)
            return val

        def max_node(b, d, cprob):
            best = DEAD
            d1 = d - 1
            t = transpose(b)
            nb = (
                LEFT[b & 0xFFFF]
                | (LEFT[(b >> 16) & 0xFFFF] << 16)
                | (LEFT[(b >> 32) & 0xFFFF] << 32)
                | (LEFT[b >> 48] << 48)
            )
            if nb != b:
                v = chance(nb, d1, cprob)
                if v > best:
                    best = v
            nb = (
                RIGHT[b & 0xFFFF]
                | (RIGHT[(b >> 16) & 0xFFFF] << 16)
                | (RIGHT[(b >> 32) & 0xFFFF] << 32)
                | (RIGHT[b >> 48] << 48)
            )
            if nb != b:
                v = chance(nb, d1, cprob)
                if v > best:
                    best = v
            nt = (
                LEFT[t & 0xFFFF]
                | (LEFT[(t >> 16) & 0xFFFF] << 16)
                | (LEFT[(t >> 32) & 0xFFFF] << 32)
                | (LEFT[t >> 48] << 48)
            )
            if nt != t:
                v = chance(transpose(nt), d1, cprob)
                if v > best:
                    best = v
            nt = (
                RIGHT[t & 0xFFFF]
                | (RIGHT[(t >> 16) & 0xFFFF] << 16)
                | (RIGHT[(t >> 32) & 0xFFFF] << 32)
                | (RIGHT[t >> 48] << 48)
            )
            if nt != t:
                v = chance(transpose(nt), d1, cprob)
                if v > best:
                    best = v
            return best

        def eval_root(root_moves, depth, dl):
            nonlocal deadline
            deadline = dl
            return {name: chance(nb, depth - 1, 1.0) for name, nb in root_moves}

        return eval_root, tt

    def rank_moves(self, matrix: np.ndarray, exclude=()) -> dict:
        b = _matrix_to_board(matrix)
        ex = set(exclude)
        root = []
        for name in DIRECTIONS:
            if name in ex:
                continue
            nb = _move_board(b, name)
            if nb != b:
                root.append((name, nb))
        self.last_depth = 0
        if not root:
            self.last_scores = {}
            return {}
        if len(root) == 1:
            self.last_scores = {root[0][0]: 0.0}
            return dict(self.last_scores)

        budget = self.time_limit
        if budget is not None and int(np.count_nonzero(np.asarray(matrix) == 0)) >= 8:
            budget *= 0.4
        deadline = time.perf_counter() + budget if budget else None

        self._tt.clear()
        best_scores = None
        for depth in range(1, self.max_depth + 1):
            try:
                best_scores = self._eval_root(root, depth, None if depth == 1 else deadline)
            except _SearchTimeout:
                break
            self.last_depth = depth
            if deadline is not None and time.perf_counter() > deadline:
                break
        self._tt.clear()
        self.last_scores = best_scores or {}
        return dict(self.last_scores)

    def get_best_move(self, matrix: np.ndarray, exclude=()) -> Optional[str]:
        scores = self.rank_moves(matrix, exclude)
        return max(scores, key=scores.get) if scores else None


# =====================================================================================
# 2b) FastExpectimaxSolver - cùng thuật toán expectimax nhưng biên dịch bằng numba
#     (nhanh gấp ~50-100 lần bản Python thuần => tìm sâu hơn nhiều trong cùng thời gian)
# =====================================================================================
try:
    import numba as _nb

    HAS_NUMBA = True
except Exception:  # numba chưa cài -> tự động dùng ExpectimaxSolver Python
    _nb = None
    HAS_NUMBA = False

if HAS_NUMBA:
    _U = np.uint64
    _K1, _K2, _K3 = _U(0xF0F00F0FF0F00F0F), _U(0x0000F0F00000F0F0), _U(0x0F0F00000F0F0000)
    _K4, _K5, _K6 = _U(0xFF00FF0000FF00FF), _U(0x00FF00FF00000000), _U(0x00000000FF00FF00)
    _S12, _S16, _S24, _S32, _S48 = _U(12), _U(16), _U(24), _U(32), _U(48)
    _S44 = _U(44)
    _MASK, _N15 = _U(0xFFFF), _U(15)
    _GOLD = _U(0x9E3779B97F4A7C15)
    _TT_BITS = 20

    @_nb.njit(cache=True)
    def _tr(x):
        a = (x & _K1) | ((x & _K2) << _S12) | ((x & _K3) >> _S12)
        return (a & _K4) | ((a & _K5) >> _S24) | ((a & _K6) << _S24)

    @_nb.njit(cache=True)
    def _mv(b, T):
        return (
            T[b & _MASK]
            | (T[(b >> _S16) & _MASK] << _S16)
            | (T[(b >> _S32) & _MASK] << _S32)
            | (T[b >> _S48] << _S48)
        )

    @_nb.njit(cache=True)
    def _heur(b, H):
        t = _tr(b)
        return (
            H[b & _MASK] + H[(b >> _S16) & _MASK] + H[(b >> _S32) & _MASK] + H[b >> _S48]
            + H[t & _MASK] + H[(t >> _S16) & _MASK] + H[(t >> _S32) & _MASK] + H[t >> _S48]
        )

    @_nb.njit  # không dùng cache=True: numba + đệ quy + cache dễ segfault
    def _search(b, d, is_chance, cprob, LEFT, RIGHT, H, st, tk, td, tv, thr, plow, phigh, lo, hi):
        st[0] += 1
        if st[0] > st[1]:
            st[2] = 1
            return 0.0
        if is_chance:
            if d <= 0 or cprob < thr:
                return _heur(b, H)
            idx = (b * _GOLD) >> _S44
            if tk[idx] == b and td[idx] >= d:
                return tv[idx]
            n = 0
            for i in range(16):
                if ((b >> _U(4 * i)) & _N15) == _U(0):
                    n += 1
            if n == 0:
                return _heur(b, H)
            inv = 1.0 / n
            clo = cprob * plow * inv
            chi = cprob * phigh * inv
            acc_lo = 0.0
            acc_hi = 0.0
            for i in range(16):
                sh = _U(4 * i)
                if ((b >> sh) & _N15) == _U(0):
                    acc_lo += _search(b | (lo << sh), d, False, clo, LEFT, RIGHT, H, st, tk, td, tv, thr, plow, phigh, lo, hi)
                    acc_hi += _search(b | (hi << sh), d, False, chi, LEFT, RIGHT, H, st, tk, td, tv, thr, plow, phigh, lo, hi)
            val = (acc_lo * plow + acc_hi * phigh) * inv
            if st[2] == 0:
                tk[idx] = b
                td[idx] = d
                tv[idx] = val
            return val
        best = -1.0e7
        d1 = d - 1
        t = _tr(b)
        nb_ = _mv(b, LEFT)
        if nb_ != b:
            v = _search(nb_, d1, True, cprob, LEFT, RIGHT, H, st, tk, td, tv, thr, plow, phigh, lo, hi)
            if v > best:
                best = v
        nb_ = _mv(b, RIGHT)
        if nb_ != b:
            v = _search(nb_, d1, True, cprob, LEFT, RIGHT, H, st, tk, td, tv, thr, plow, phigh, lo, hi)
            if v > best:
                best = v
        nt = _mv(t, LEFT)
        if nt != t:
            v = _search(_tr(nt), d1, True, cprob, LEFT, RIGHT, H, st, tk, td, tv, thr, plow, phigh, lo, hi)
            if v > best:
                best = v
        nt = _mv(t, RIGHT)
        if nt != t:
            v = _search(_tr(nt), d1, True, cprob, LEFT, RIGHT, H, st, tk, td, tv, thr, plow, phigh, lo, hi)
            if v > best:
                best = v
        return best

    @_nb.njit
    def _root(b, depth, excl, LEFT, RIGHT, H, st, tk, td, tv, thr, plow, phigh, lo, hi, out):
        # thứ tự out: UP, DOWN, LEFT, RIGHT (khớp DIRECTIONS)
        t = _tr(b)
        for k in range(4):
            out[k] = -1.0e18
        nbs = np.empty(4, dtype=np.uint64)
        nbs[0] = _tr(_mv(t, LEFT))
        nbs[1] = _tr(_mv(t, RIGHT))
        nbs[2] = _mv(b, LEFT)
        nbs[3] = _mv(b, RIGHT)
        for k in range(4):
            if nbs[k] != b and excl[k] == 0:
                out[k] = _search(nbs[k], depth - 1, True, 1.0, LEFT, RIGHT, H, st, tk, td, tv, thr, plow, phigh, lo, hi)


class FastExpectimaxSolver:
    """Giao diện y hệt ExpectimaxSolver (rank_moves / get_best_move / last_depth / last_scores)."""

    def __init__(
        self,
        max_depth: int = 12,
        time_limit: Optional[float] = 0.3,
        spawn_low_level: int = 1,
        spawn_high_level: int = 2,
        spawn_high_prob: float = 0.1,
        cprob_threshold: float = 0.0004,
        **_legacy,
    ):
        if not HAS_NUMBA:
            raise RuntimeError("Chưa cài numba (pip install numba)")
        left, right, heur, _, _ = _build_tables()
        self._L = np.array(left, dtype=np.uint64)
        self._R = np.array(right, dtype=np.uint64)
        self._H = np.array(heur, dtype=np.float64)
        n = 1 << _TT_BITS
        self._tk = np.zeros(n, dtype=np.uint64)
        self._td = np.zeros(n, dtype=np.int64)
        self._tv = np.zeros(n, dtype=np.float64)
        self.max_depth = max(1, int(max_depth))
        self.time_limit = time_limit if time_limit else 0.3
        self.lo = np.uint64(spawn_low_level)
        self.hi = np.uint64(spawn_high_level)
        self.phigh = float(spawn_high_prob)
        self.plow = 1.0 - self.phigh
        self.thr = float(cprob_threshold)
        self.last_depth = 0
        self.last_scores: dict = {}
        self._nps = 1.0e6
        self._calibrate()

    def _run(self, b: int, depth: int, excl, node_cap: int):
        st = np.zeros(3, dtype=np.int64)
        st[1] = node_cap
        out = np.zeros(4, dtype=np.float64)
        return st, out

    def _calibrate(self) -> None:
        """Biên dịch JIT + đo tốc độ (node/giây) để đổi time_limit -> số node."""
        demo = np.array([[1, 2, 3, 4], [0, 1, 2, 3], [1, 6, 1, 2], [3, 1, 2, 1]])
        b = np.uint64(_matrix_to_board(demo))
        excl = np.zeros(4, dtype=np.int64)
        out = np.zeros(4, dtype=np.float64)
        st = np.array([0, 10, 0], dtype=np.int64)
        self._tk[:] = 0
        _root(b, 2, excl, self._L, self._R, self._H, st, self._tk, self._td, self._tv,
              self.thr, self.plow, self.phigh, self.lo, self.hi, out)  # compile
        self._tk[:] = 0
        st = np.array([0, 300000, 0], dtype=np.int64)
        t0 = time.perf_counter()
        _root(b, 4, excl, self._L, self._R, self._H, st, self._tk, self._td, self._tv,
              self.thr, self.plow, self.phigh, self.lo, self.hi, out)
        dt = max(time.perf_counter() - t0, 1e-4)
        self._nps = max(2.0e5, st[0] / dt)

    def rank_moves(self, matrix: np.ndarray, exclude=()) -> dict:
        b = np.uint64(_matrix_to_board(matrix))
        excl = np.array([1 if d in set(exclude) else 0 for d in DIRECTIONS], dtype=np.int64)
        empties = int(np.count_nonzero(np.asarray(matrix) == 0))
        budget = self.time_limit * (0.5 if empties >= 8 else 1.0)
        st = np.array([0, int(self._nps * budget), 0], dtype=np.int64)
        self._tk[:] = 0
        best = None
        self.last_depth = 0
        out = np.zeros(4, dtype=np.float64)
        t_start = time.perf_counter()
        for depth in range(1, self.max_depth + 1):
            out = np.zeros(4, dtype=np.float64)
            _root(b, depth, excl, self._L, self._R, self._H, st, self._tk, self._td, self._tv,
                  self.thr, self.plow, self.phigh, self.lo, self.hi, out)
            if st[2] and depth > 1:
                break
            best = out.copy()
            self.last_depth = depth
            if st[2]:
                break
        dt = time.perf_counter() - t_start
        if st[2] and dt > 0.005:  # tự hiệu chỉnh tốc độ theo lần chạy thật
            self._nps = 0.5 * self._nps + 0.5 * (st[0] / dt)
        scores = {}
        if best is not None:
            for k, name in enumerate(DIRECTIONS):
                if best[k] > -1.0e17:
                    scores[name] = float(best[k])
        self.last_scores = scores
        return dict(scores)

    def get_best_move(self, matrix: np.ndarray, exclude=()) -> Optional[str]:
        scores = self.rank_moves(matrix, exclude)
        return max(scores, key=scores.get) if scores else None


def make_solver(max_depth: int = 8, time_limit: float = 0.5, log=None, **spawn):
    """Ưu tiên bản numba; nếu chưa cài numba thì dùng bản Python."""
    if HAS_NUMBA:
        try:
            s = FastExpectimaxSolver(max_depth=max(max_depth, 12), time_limit=time_limit, **spawn)
            if log:
                log("info", f"🧠 Solver: numba (~{s._nps/1e6:.1f}M node/s)")
            return s
        except Exception as e:  # noqa: BLE001
            if log:
                log("warn", f"Không dùng được numba ({e}) -> dùng solver Python")
    elif log:
        log("warn", "Chưa cài numba -> dùng solver Python (chậm). Cài: pip install numba")
    return ExpectimaxSolver(max_depth=max_depth, time_limit=time_limit, **spawn)


# =====================================================================================
# 3) GameController
# =====================================================================================
@dataclass
class GameController:
    detector: BoardDetector
    solver: ExpectimaxSolver
    get_screenshot: callable
    adb_swipe: callable

    top_left: tuple[int, int]
    bottom_right: tuple[int, int]

    swipe_duration_ms: int = 120
    merge_wait_s: tuple[float, float] = (0.15, 0.25)
    max_stall_reads: int = 20
    fallback_priority: tuple[str, ...] = ("DOWN", "LEFT", "RIGHT", "UP")
    logger: Optional[callable] = None
    max_unknown_as_blocker: int = 2
    retry_wait_s: float = 0.35
    max_dead_rounds: int = 2
    max_swipe_retries: int = 4
    settle_tries: int = 6
    settle_wait_s: float = 0.12
    record_path: Optional[str] = None
    stats_every: int = 25

    _last_matrix: Optional[np.ndarray] = field(default=None, init=False, repr=False)
    _stall_reads: int = field(default=0, init=False, repr=False)
    _pending_dir: Optional[str] = field(default=None, init=False, repr=False)
    _pending_matrix: Optional[np.ndarray] = field(default=None, init=False, repr=False)
    _blocked: set = field(default_factory=set, init=False, repr=False)
    _fail_count: dict = field(default_factory=dict, init=False, repr=False)
    _dead_rounds: int = field(default=0, init=False, repr=False)
    _moves_done: int = field(default=0, init=False, repr=False)
    failed_swipes: int = field(default=0, init=False)
    _stats: dict = field(default_factory=dict, init=False, repr=False)

    def _log(self, level: str, msg: str) -> None:
        if self.logger is not None:
            self.logger(level, msg)
        else:
            print(f"[GameController][{level}] {msg}")

    def _swipe_vector(self, direction: str) -> tuple[int, int, int, int]:
        x1, y1 = self.top_left
        x2, y2 = self.bottom_right
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        w, h = x2 - x1, y2 - y1
        margin_x, margin_y = int(w * 0.40), int(h * 0.40)

        if direction == "UP":
            return cx, cy + margin_y, cx, cy - margin_y
        if direction == "DOWN":
            return cx, cy - margin_y, cx, cy + margin_y
        if direction == "LEFT":
            return cx + margin_x, cy, cx - margin_x, cy
        if direction == "RIGHT":
            return cx - margin_x, cy, cx + margin_x, cy
        raise ValueError(f"Hướng không hợp lệ: {direction}")

    def _do_swipe(self, direction: str) -> None:
        x1, y1, x2, y2 = self._swipe_vector(direction)
        self.adb_swipe(x1, y1, x2, y2, self.swipe_duration_ms)

    def _read_matrix(self) -> np.ndarray:
        frame = self.get_screenshot()
        if frame is None:
            raise RuntimeError("get_screenshot() trả về None (mất kết nối ADB)")
        return self.detector.detect(frame)

    def _read_clean(self) -> np.ndarray:
        matrix = self._read_matrix()
        n_unk = int(np.sum(matrix == -1))
        if 0 < n_unk <= self.max_unknown_as_blocker:
            if self._moves_done % 20 == 0:
                self._log("warn", f"Có {n_unk} ô lạ -> tạm coi là vật cản.")
            matrix = np.where(matrix == -1, MAX_LEVEL + 1, matrix)
        return matrix

    def _settle(self, matrix: np.ndarray) -> np.ndarray:
        """
        Sau khi vuốt, ta biết chính xác bàn cờ phải thành gì (simulate_move) + đúng 1 ô mới sinh.
        Nếu ảnh chụp không khớp (đang chạy hiệu ứng gộp/sinh ô) -> đợi rồi chụp lại,
        thay vì ra quyết định trên khung hình dở dang.
        """
        if self._pending_dir is None or self._pending_matrix is None:
            return matrix
        before = self._pending_matrix
        expected, changed, _ = simulate_move(before, self._pending_dir)
        if not changed:
            return matrix
        for _ in range(self.settle_tries):
            if np.array_equal(matrix, before):
                return matrix  # vuốt không ăn -> để _learn_from_last_swipe xử lý
            occupied = expected != 0
            new_cells = (~occupied) & (matrix != 0)
            if np.array_equal(matrix[occupied], expected[occupied]) and int(new_cells.sum()) == 1:
                return matrix
            time.sleep(self.settle_wait_s)
            try:
                again = self._read_clean()
            except Exception:
                break
            if np.any(again == -1):
                continue
            matrix = again
        return matrix

    def _learn_from_last_swipe(self, matrix: np.ndarray) -> Optional[np.ndarray]:
        direction = self._pending_dir
        if direction is None:
            return matrix
        before = self._pending_matrix
        self._pending_dir = None

        if not np.array_equal(matrix, before):
            self._blocked.clear()
            self._fail_count.clear()
            self._dead_rounds = 0
            self._record(before, direction, matrix)
            return matrix

        time.sleep(self.retry_wait_s)
        try:
            again = self._read_clean()
        except Exception:
            again = matrix
        if np.any(again == -1):
            self._blocked.clear()
            return None
        if not np.array_equal(again, before):
            self._blocked.clear()
            self._fail_count.clear()
            self._dead_rounds = 0
            self._record(before, direction, again)
            return again

        # Solver chỉ chọn nước HỢP LỆ theo luật => vuốt không ăn gần như chắc chắn là game bỏ qua thao tác
        # (đang chạy hiệu ứng / lag). Vuốt lại CHÍNH nước tốt nhất, chỉ cấm hướng đó sau nhiều lần liên tiếp thất bại.
        self.failed_swipes += 1
        n = self._fail_count.get(direction, 0) + 1
        self._fail_count[direction] = n
        if n >= self.max_swipe_retries:
            self._blocked.add(direction)
            self._log("warn", f"Vuốt {direction} thất bại {n} lần liên tiếp -> tạm cấm hướng này.")
        else:
            time.sleep(self.retry_wait_s)
        return again

    def _record(self, before: np.ndarray, direction: str, after: np.ndarray) -> None:
        try:
            st = self._stats
            expected, _, _ = simulate_move(before, direction)
            spawned = [
                int(after[r, c])
                for r in range(4)
                for c in range(4)
                if expected[r, c] == 0 and after[r, c] != 0
            ]
            bad = int(np.sum((expected != 0) & (after != expected)))
            st["n"] += 1
            st["spawn_count"][len(spawned)] += 1
            st["spawn_level"].update(spawned)
            if bad:
                st["mismatch"] += 1
            if self.record_path:
                with open(self.record_path, "a", encoding="utf-8") as f:
                    f.write(
                        json.dumps(
                            {
                                "before": before.tolist(),
                                "dir": direction,
                                "after": after.tolist(),
                                "spawned": spawned,
                                "mismatch_cells": bad,
                            }
                        )
                        + "\n"
                    )
        except Exception:
            pass

    def _choose_direction(self, matrix: np.ndarray) -> tuple[Optional[str], str]:
        best = self.solver.get_best_move(matrix, exclude=tuple(self._blocked))
        if best is not None:
            return best, "ai"
        for direction in self.fallback_priority:
            if direction not in self._blocked:
                return direction, "probe"
        return None, "dead"

    def _tick(self) -> str:
        t0 = time.time()
        try:
            matrix = self._read_clean()
        except Exception as e:
            self._log("error", f"Lỗi đọc màn hình: {e}")
            time.sleep(0.5)
            self._stall_reads += 1
            if self._stall_reads >= self.max_stall_reads:
                return "stop"
            return "retry"

        if np.any(matrix == -1):
            self._stall_reads += 1
            if self._stall_reads >= self.max_stall_reads:
                return "stop"
            time.sleep(0.15)
            return "retry"
        self._stall_reads = 0

        matrix = self._settle(matrix)
        matrix = self._learn_from_last_swipe(matrix)
        if matrix is None:
            return "retry"

        self._last_matrix = matrix
        t1 = time.time()
        direction, mode = self._choose_direction(matrix)
        t2 = time.time()

        if direction is None:
            self._dead_rounds += 1
            if self._dead_rounds >= self.max_dead_rounds:
                self._log("info", "Hết nước đi (game over) -> dừng.")
                return "stop"
            self._blocked.clear()
            time.sleep(1.0)
            return "retry"

        self._pending_dir = direction
        self._pending_matrix = matrix.copy()
        self._do_swipe(direction)
        t3 = time.time()
        self._moves_done += 1
        tag = "" if mode == "ai" else "  [thăm dò]"
        self._log(
            "info",
            f"🧩 Nước {self._moves_done}: {direction}{tag} (đọc {t1 - t0:.2f}s | tính {t2 - t1:.2f}s "
            f"sâu {getattr(self.solver, 'last_depth', '?')} | vuốt {t3 - t2:.2f}s)",
        )
        time.sleep(random.uniform(*self.merge_wait_s))
        return "moved"

    def _reset_state(self) -> None:
        self._stall_reads = 0
        self._pending_dir = None
        self._pending_matrix = None
        self._blocked = set()
        self._fail_count = {}
        self._dead_rounds = 0
        self._moves_done = 0
        self.failed_swipes = 0
        self._stats = {"n": 0, "mismatch": 0, "spawn_count": Counter(), "spawn_level": Counter()}
        if self.record_path:
            try:
                open(self.record_path, "w", encoding="utf-8").close()
            except OSError:
                self.record_path = None

    def run(
        self,
        max_steps: Optional[int] = None,
        max_seconds: Optional[float] = None,
        should_stop: Optional[callable] = None,
    ) -> int:
        should_stop = should_stop or (lambda: False)
        start_t = time.time()
        self._reset_state()
        self._log("info", f"Cấu hình nhận diện: {self.detector.diagnostics()}")

        while not should_stop():
            if max_steps is not None and self._moves_done >= max_steps:
                break
            if max_seconds is not None and (time.time() - start_t) >= max_seconds:
                break
            if self._tick() == "stop":
                break

        st = self._stats
        if st.get("n"):
            self._log(
                "info",
                f"📊 Thống kê {st['n']} nước: số ô sinh mỗi nước={dict(st['spawn_count'])} | "
                f"cấp ô sinh={dict(st['spawn_level'])} | lệch mô phỏng={st['mismatch']} nước",
            )
        self._log(
            "info",
            f"🧩 Auto Merge2048: kết thúc, tổng {self._moves_done} lần vuốt ({self.failed_swipes} lần vô hiệu).",
        )
        return self._moves_done


# =====================================================================================
# 4) Điểm nối vào LogicEngine (logic_engine.py)
# =====================================================================================
def run_auto_merge2048_step(adb, step: dict, should_stop=None, log=None) -> None:
    """
    Điểm nối thực thi bước auto_merge2048:
    - Nếu step có "max_moves": 0 -> Chế độ TEST: chỉ chụp, in ma trận, lưu ảnh debug, KHÔNG vuốt.
    - Nếu "max_moves" khác 0 -> Tự động chơi bình thường.
    """
    should_stop = should_stop or (lambda: False)
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))

    p1 = step.get("board_from")
    p2 = step.get("board_to")
    if not p1 or not p2:
        log("error", "Bước Auto Merge2048 chưa chọn vùng bàn cờ - hãy chọn lại vùng trên giao diện.")
        return

    try:
        first_frame = adb.screencap_fast()
    except Exception as e:
        log("error", f"🧩 Auto Merge2048: không chụp được màn hình - {e}")
        return
    if first_frame is None:
        log("error", "🧩 Auto Merge2048: screencap_fast() trả về None - kiểm tra ADB kết nối chưa.")
        return

    fh, fw = first_frame.shape[:2]
    top_left = (int(p1[0] * fw), int(p1[1] * fh))
    bottom_right = (int(p2[0] * fw), int(p2[1] * fh))

    if bottom_right[0] - top_left[0] < 40 or bottom_right[1] - top_left[1] < 40:
        log("error", f"🧩 Auto Merge2048: vùng bàn cờ quá nhỏ {top_left}->{bottom_right} (ảnh {fw}x{fh})")
        return

    templates_dir = step.get("templates_dir", "templates/merge2048_levels")
    detector = BoardDetector(
        top_left=top_left,
        bottom_right=bottom_right,
        templates_dir=templates_dir,
        debug=True,
    )

    if not detector.can_identify():
        log(
            "error",
            f"🧩 Auto Merge2048: thư mục '{templates_dir}' chưa có file template số nào (1.png... 11.png)!",
        )
        return

    # ================= CHẾ ĐỘ TEST KHI max_moves == 0 =================
    max_moves = step.get("max_moves")
    if max_moves == 0:
        log("info", "📸 [CHẾ ĐỘ TEST] max_moves = 0: Quét bàn cờ kiểm tra (KHÔNG VUỐT)...")
        matrix = detector.detect(first_frame)

        # 1. In ma trận 4x4
        board_rows = "\n".join("  ".join(f"{matrix[r, c]:2d}" for c in range(4)) for r in range(4))
        log("info", f"🧩 Kích thước màn hình: {fw}x{fh} | ROI: {top_left} -> {bottom_right}")
        log("info", f"🧩 MA TRẬN 4x4 BOT ĐỌC ĐƯỢC:\n{board_rows}")

        # 2. In báo cáo độ tin cậy từng ô
        log("info", f"🧩 Chi tiết độ khớp từng ô:\n{detector.score_report()}")

        # 3. Ép lưu ảnh vẽ lưới và số vào thư mục debug_merge2048/
        out_dir = os.path.abspath("debug_merge2048")
        detector.save_debug(out_dir)
        annotated_path = os.path.join(out_dir, "roi_annotated.png")
        log("info", f"✅ ĐÃ LƯU ẢNH KẾT QUẢ VÀO: {annotated_path}")
        log("info", "👉 Hãy mở file 'roi_annotated.png' kiểm tra số màu xanh có khớp vật phẩm không.")
        return
    # ==================================================================

    log("info", f"🧩 Auto Merge2048: ROI={top_left}->{bottom_right} (ảnh {fw}x{fh}) | {detector.diagnostics()}")

    # Luật sinh ô: mặc định cấp 1 (90%) / cấp 2 (10%).
    # Chế độ VIP (mỗi lượt chỉ sinh 1 ô cấp 3): đặt "vip": true trong step,
    # hoặc tự chỉnh spawn_low_level / spawn_high_level / spawn_high_prob.
    if step.get("vip"):
        spawn_cfg = dict(spawn_low_level=3, spawn_high_level=3, spawn_high_prob=0.0)
    else:
        spawn_cfg = dict(
            spawn_low_level=int(step.get("spawn_low_level", 1)),
            spawn_high_level=int(step.get("spawn_high_level", 2)),
            spawn_high_prob=float(step.get("spawn_high_prob", 0.1)),
        )
    log("info", f"🧩 Luật sinh ô: {spawn_cfg}")
    solver = make_solver(
        max_depth=int(step.get("search_depth", 8)),
        time_limit=float(step.get("search_seconds", 0.15 if HAS_NUMBA else 0.5)),
        log=log,
        **spawn_cfg,
    )
    controller = GameController(
        detector=detector,
        solver=solver,
        get_screenshot=lambda: adb.screencap_fast(),
        adb_swipe=lambda x1, y1, x2, y2, dur: adb.swipe_px(x1, y1, x2, y2, dur),
        top_left=top_left,
        bottom_right=bottom_right,
        swipe_duration_ms=int(step.get("swipe_duration_ms", 120)),
        record_path=step.get("record_path", "merge2048_moves.jsonl"),
        logger=log,
    )

    controller.run(
        max_steps=max_moves,
        max_seconds=step.get("max_seconds"),
        should_stop=should_stop,
    )


if __name__ == "__main__":
    demo = np.array(
        [
            [0, 2, 3, 4],
            [0, 1, 2, 3],
            [1, 6, 1, 2],
            [11, 1, 2, 1],
        ]
    )
    print("Ma trận demo:\n", demo)
    solver = ExpectimaxSolver(max_depth=6, time_limit=0.3)
    t = time.time()
    best = solver.get_best_move(demo)
    print("Nước đi đề xuất:", best, f"(sâu {solver.last_depth}, {time.time() - t:.2f}s)")
    print("Điểm từng hướng:", {k: round(v) for k, v in solver.last_scores.items()})
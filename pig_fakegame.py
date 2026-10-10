# -*- coding: utf-8 -*-
"""
pig_fakegame.py - GAME GIẢ để kiểm tra đường ống auto_pig (bot -> log phiên -> pig_calib.py) mà KHÔNG cần LDPlayer.

Tạo 1 "thế giới thật" có tham số vật lý ẨN (khác mặc định của bot), vẽ ảnh 720x1280 giống game (heo viền màu trên nền tối, con cầm ở giữa phía trên),
giả lập ADB (chụp ảnh, bấm), đồng hồ ảo (sleep không chờ thật). Bot chạy bằng ĐÚNG code thật (nhận diện bằng ảnh, mô phỏng, log, ảnh cmp, trace...).
Sau đó pig_calib.py phải tìm lại gần đúng tham số ẩn -> chứng tỏ đường ống hiệu chỉnh hoạt động.

Chạy:  python pig_fakegame.py [--turns 40] [--out debug_fake] [--seed 1] [--true "friction=0.45,elasticity=0.3,gravity=2.4"] [--think 0.4] [--no-explore]
Kết quả: <out>/sessions/<phiên>/ (giống hệt phiên chơi thật) + <out>/fake_truth.json (tham số ẩn để đối chiếu).
LƯU Ý: đây là sim-to-sim (cùng engine Pymunk, khác tham số) nên chỉ kiểm tra QUY TRÌNH, không thay cho test trên game thật.
"""
import json
import os
import random
import sys
import time as _real_time

import cv2
import numpy as np

import pig_bot as pb


class FakeClock:
    """Đồng hồ ảo: sleep() không chờ thật mà cộng vào độ lệch -> chạy nhanh; thời gian tính toán thật của bot vẫn trôi như thường."""

    def __init__(self):
        self.skip = 0.0

    def time(self):
        return _real_time.time() + self.skip

    def sleep(self, sec):
        self.skip += max(0.0, float(sec))

    def advance(self, sec):
        self.skip += float(sec)

    def __getattr__(self, name):
        return getattr(_real_time, name)


# màu viền theo nhóm (OpenCV HSV) - nằm trong cửa sổ mặt nạ của pig_bot._group_masks
_RING_HSV = {0: (85, 160, 200), 1: (102, 190, 220), 2: (140, 160, 200), 3: (19, 210, 230), 4: (1, 210, 230), 5: (0, 0, 120)}


def _hsv(h, s, v):
    return tuple(int(c) for c in cv2.cvtColor(np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0])


class FakePigGame:
    FW, FH = 720, 1280

    def __init__(self, true_params=None, seed=1, ring_q=0.97, latency=0.12, clock=None, stamina=300):
        self.rnd = random.Random(seed)
        self.sp = pb.SimParams(**(true_params or {}))
        self.clock = clock or FakeClock()
        self.box = pb._board_px({}, self.FW, self.FH)
        self.W = self.box[2] - self.box[0]
        self.H = self.box[3] - self.box[1]
        self.ring_q = ring_q               # bán kính vòng viền thật / danh nghĩa (game thật ~0.9-1.0)
        self.latency = latency             # trễ từ lúc bấm tới lúc heo bắt đầu rơi
        self.balls = []                    # [(lv,x,y,r)] đang nằm yên (toạ độ khung bàn)
        self.stamina = stamina
        self.held = self._next_held()
        self.drop = None                   # dict khi đang rơi: t_tap, snaps, dt, t_settle, final
        self.over = False
        self.taps = 0
        self.bg = _hsv(15, 120, 60)
        self.truth_log = []

    # ---- luật
    def _next_held(self):
        lp = getattr(pb, "LEVEL_PROB", {1: 0.31, 2: 0.28, 3: 0.28, 4: 0.14})      # tỉ lệ con thả theo cấp (đếm từ log thật)
        lv = self.rnd.choices(list(lp), weights=list(lp.values()))[0]
        return lv

    def r_ring(self, lv):
        return pb.R_FRAC[lv - 1] * self.W * self.ring_q

    # ---- ADB giả
    def screencap_fast(self):
        self.clock.advance(0.12)
        return self.render()

    def ocr_text_in_box(self, frame, box, **kw):
        return "%d/300" % self.stamina

    def tap_px(self, x, y):
        self.clock.advance(0.05)
        self._do_drop(x - self.box[0])

    def swipe_hold_px(self, x1, y1, x2, y2, **kw):
        self._do_drop(x2 - self.box[0])

    def _do_drop(self, x):
        if self.drop is not None or self.over or self.held is None:
            return
        self.taps += 1
        self.stamina -= 1
        lv = self.held
        r = self.r_ring(lv)
        x = min(max(x, r), self.W - r)
        y0 = -pb.HELD_TOP * self.W + r                       # tâm con cầm (mép trên cách khung 0.233 W)
        dts = [round(0.05 * k, 3) for k in range(1, 100)]
        tr = {"times": dts}
        final, gain = pb.simulate(self.balls, self.W, self.H, (lv, x, r, y0), self.sp, trace_out=tr)
        snaps = tr["snaps"]
        k_last = 0
        for k, sn in enumerate(snaps):                       # thời điểm heo thực sự yên: lần cuối còn lệch > 0.7px so với trạng thái cuối
            if len(sn) != len(final) or any(abs(a[1] - b[1]) + abs(a[2] - b[2]) > 0.7 for a, b in zip(sorted(sn), sorted(final))):
                k_last = k + 1
        self.drop = {"t_tap": self.clock.time(), "dts": dts, "snaps": snaps, "final": final, "t_settle": self.latency + dts[min(k_last, len(dts) - 1)] + 0.35,
                     "lv": lv, "x": x, "gain": gain}
        self.truth_log.append({"turn": self.taps, "lv": lv, "x": round(x, 1), "gain": gain})
        self.held = None

    def _settle_if_due(self):
        d = self.drop
        if d is not None and self.clock.time() - d["t_tap"] >= d["t_settle"]:
            self.balls = [(lv, x, y, r) for lv, x, y, r in d["final"]]
            self.drop = None
            self.held = self._next_held()
            if any(y - r < -2 for lv, x, y, r in self.balls):    # thua: heo vượt vạch trên
                self.over = True
                self.held = None

    def current_balls(self):
        self._settle_if_due()
        d = self.drop
        if d is None:
            return self.balls
        t = self.clock.time() - d["t_tap"] - self.latency
        if t <= 0:
            return list(self.balls) + [(d["lv"], d["x"], -pb.HELD_TOP * self.W + self.r_ring(d["lv"]), self.r_ring(d["lv"]))]
        k = min(len(d["dts"]) - 1, max(0, int(round(t / 0.05)) - 1))
        return d["snaps"][k]

    # ---- vẽ
    def _pig(self, im, lv, cx, cy, r):
        x1, y1 = self.box[0], self.box[1]
        c = (int(round(cx + x1)), int(round(cy + y1)))
        grp = pb.GROUP[lv - 1]
        ring = _hsv(*_RING_HSV[grp])
        th = max(4, int(0.14 * r))
        if lv == 1:
            body = _hsv(170, 70, 238)
        elif lv == 3:
            body = _hsv(110, 120, 55)                          # thân tối (cấp 3 xanh đen)
        else:
            body = _hsv(5, 60, 240)
        cv2.circle(im, c, int(round(r)), ring, -1, cv2.LINE_AA)
        cv2.circle(im, c, max(1, int(round(r)) - th), body, -1, cv2.LINE_AA)
        # mắt/mũi cho giống thật
        cv2.circle(im, (c[0] - int(0.3 * r), c[1] - int(0.1 * r)), max(2, int(0.07 * r)), (30, 30, 30), -1)
        cv2.circle(im, (c[0] + int(0.3 * r), c[1] - int(0.1 * r)), max(2, int(0.07 * r)), (30, 30, 30), -1)

    def render(self):
        self._settle_if_due()
        im = np.empty((self.FH, self.FW, 3), np.uint8)
        im[:] = self.bg
        for lv, x, y, r in sorted(self.current_balls(), key=lambda b: -b[0]):
            if y + r > 0:
                self._pig(im, lv, x, y, r)
        if self.held is not None and self.drop is None:
            r = self.r_ring(self.held)
            self._pig(im, self.held, self.W / 2.0, -pb.HELD_TOP * self.W + r, r)
        return im


def _parse_kv(txt):
    out = {}
    for part in (txt or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = float(v)
    return out


DEFAULT_TRUE = {"gravity": 2.4, "damping": 0.70, "friction": 0.45, "elasticity": 0.30, "rad_scale": 1.05, "merge_eps": 0.004, "spin_damp": 3.0}


def run(turns=40, out="debug_fake", seed=1, true_params=None, think=0.4, explore=0.25, extra_step=None, quiet=False):
    """Chạy bot (calib_run) trên game giả. Trả (đường dẫn phiên, dict tham số ẩn)."""
    clock = FakeClock()
    pb.time = clock                                           # đồng hồ ảo cho pig_bot (sleep không chờ)
    tp = dict(DEFAULT_TRUE)
    tp.update(true_params or {})
    game = FakePigGame(tp, seed=seed, clock=clock)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "fake_truth.json"), "w", encoding="utf-8") as f:
        json.dump({"true_params": tp, "ring_q": game.ring_q, "latency": game.latency}, f, indent=1)
    step = {"action": "auto_pig", "calib_run": True, "max_turns": turns, "debug_dir": out, "think_s": think, "explore": explore, "seed": seed,
            "held_wait": 0.5, "reset_params": True, "min_stamina": 10}
    step.update(extra_step or {})
    msgs = []

    def log(level, msg):
        msgs.append(msg)
        if not quiet:
            print("[%s] %s" % (level, msg))

    try:
        pb.run_auto_pig_step(game, step, should_stop=lambda: False, log=log)
    finally:
        pb.time = _real_time
    try:
        with open(os.path.join(out, "last_session.txt"), encoding="utf-8") as f:
            sess = f.read().strip()
    except Exception:
        sess = out                                            # bố cục phẳng (session_dir=false): mọi file nằm thẳng trong out
    return sess, tp


if __name__ == "__main__":
    a = sys.argv[1:]

    def opt(name, default):
        return a[a.index(name) + 1] if name in a else default
    sess_dir, tp = run(turns=int(opt("--turns", 40)), out=opt("--out", "debug_fake"), seed=int(opt("--seed", 1)),
                       true_params=_parse_kv(opt("--true", "")), think=float(opt("--think", 0.4)),
                       explore=0.0 if "--no-explore" in a else 0.25)
    print("\nPhiên giả: %s\nTham số ẨN (đáp án): %s\nTiếp theo:  python pig_calib.py \"%s\"" % (sess_dir, json.dumps(tp), sess_dir))

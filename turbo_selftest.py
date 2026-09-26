# -*- coding: utf-8 -*-
"""
turbo_selftest.py - ĐO THỰC TẾ Chế Độ Siêu Tốc trên máy của bạn (không sửa gì).

Chạy (LDPlayer đã mở, đặt file này cạnh adb_helper.py):
    python turbo_selftest.py                       -> đo tốc độ chụp (PNG vs RAW, 1/2/3 luồng)
    python turbo_selftest.py --device emulator-5554
    python turbo_selftest.py --tap 0.5 0.5         -> thử thêm click sendevent vs input tap
                                                      tại điểm (tỉ lệ 0..1) - HÃY NHÌN màn hình
                                                      giả lập xem có thật sự nhận chạm không.
"""
import argparse
import os
import time

import adb_helper
import turbo_engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default=None)
    ap.add_argument("--frames", type=int, default=10)
    ap.add_argument("--tap", nargs=2, type=float, default=None, metavar=("X", "Y"))
    args = ap.parse_args()

    adb = adb_helper.ADBHelper()
    adb.device_id = args.device or (adb.get_devices() or [None])[0]
    print("Thiết bị:", adb.device_id)
    if not adb.device_id:
        print("Không thấy thiết bị nào (adb devices rỗng)."); return

    eng = turbo_engine.TurboEngine(adb)
    time.sleep(1.5)  # đợi khởi động nền (dò cảm ứng + mở shell)

    def avg(fn, n):
        ts = []
        for _ in range(n):
            t = time.perf_counter(); fn(); ts.append((time.perf_counter() - t) * 1000)
        return sum(ts) / len(ts), min(ts)

    eng._grab_png(time.perf_counter())
    a, b = avg(lambda: eng._grab_png(time.perf_counter()), args.frames)
    print("Chụp PNG qua socket : TB %.0f ms (nhanh nhất %.0f)" % (a, b))
    eng.grab()
    fr = eng.grab()
    if fr.kind == "bgr":
        print("Chụp RAW            : KHÔNG dùng được trên giả lập này (tự rơi về PNG)")
    else:
        a, b = avg(eng.grab, args.frames)
        print("Chụp RAW qua socket : TB %.0f ms (nhanh nhất %.0f)  [%dx%d]" % (a, b, fr.arr.shape[1], fr.arr.shape[0]))

    for w in (1, 2, 3):
        eng.workers = w
        pump = turbo_engine._FramePump(eng); pump.start()
        t0 = time.perf_counter(); seq = 0; got = 0
        while time.perf_counter() - t0 < 3.0:
            f = pump.next_frame(seq, 0.2)
            if f is not None:
                seq = f.seq; got += 1
        pump.stop()
        print("Quét %d luồng        : %.1f khung/giây (khoảng %.0f ms/khung)" % (w, got / 3.0, 3000.0 / max(1, got)))
    print("  -> đặt THTG_TURBO_WORKERS = số luồng cho khung/giây CAO NHẤT")

    for n in eng.pop_notes():
        print("  ghi chú:", n)

    if args.tap:
        adb.update_resolution()
        x, y = args.tap[0] * adb.screen_w, args.tap[1] * adb.screen_h
        print("\nThử CLICK tại (%.0f, %.0f) - nhìn màn hình giả lập!" % (x, y))
        t = time.perf_counter(); adb._turbo_transact("exec:input tap %d %d" % (x, y), timeout=3.0)
        print("  input tap : %.0f ms (đến khi lệnh xong)" % ((time.perf_counter() - t) * 1000))
        time.sleep(1.0)
        t = time.perf_counter(); ok = eng.tap(x, y)
        print("  sendevent : %s, %.1f ms để gửi lệnh" % ("đã gửi" if ok else "KHÔNG dùng được (sẽ tự dùng input tap)", (time.perf_counter() - t) * 1000))
        time.sleep(0.5)
        for n in eng.pop_notes():
            print("  ghi chú:", n)
        print("  Nếu input tap có chạm mà sendevent KHÔNG chạm -> đặt THTG_TURBO_TAP=input")


if __name__ == "__main__":
    main()

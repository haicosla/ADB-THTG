# -*- coding: utf-8 -*-
"""
Bot auto "Giao Hàng - Đại Chiến Giành Đơn" (chiếm ô đất trên bản đồ khu thương mại, 4 phe) - điều khiển qua ADB, bước `auto_delivery`.

>>> Bản 1 (08/11): CHƯA chạy thử trên LDPlayer thật. Đã kiểm trên 18 ảnh chụp thật (`python delivery_bot.py --check anh.png`)
>>> và bằng bộ lập kế hoạch/bản đồ giả (`python delivery_bot.py --selftest`). LẦN ĐẦU hãy chạy chế độ TEST (không bấm).
>>> Bản 2: SỬA LỖI GỐC khiến bot "không làm được gì": bản 1 gắn cứng "phe mình = XANH DƯƠNG", còn trong video thật người chơi thuộc
>>> phe VÀNG (Giao Đồ Ăn Ngon) -> bot coi đồng hồ đếm của mình là của địch, không nhận vòng sáng/đồng đội/mũ của mình.
>>> Nay bot TỰ NHẬN DIỆN PHE ĐẦU TIÊN (mục 1b) rồi mới tính toán. Đã kiểm trên khung hình thật của video chơi game.
>>> Bản 3: (a) mỗi lần chạy chỉ nhận ĐÚNG 1 phe rồi KHOÁ (không nhớ file, không đổi giữa chừng); (b) toạ độ 14 ô dựng SẴN từ video
>>> (WORLD_BUILTIN) -> không còn quét bản đồ lần đầu, định vị lại bằng ô nhìn thấy sau mỗi lần vuốt (sai số ~1px, không cộng dồn lệch);
>>> (c) vuốt nhanh (~0,16s), chỉ vuốt khi ô chưa nằm trong tầm bấm, có hiệu chỉnh độ dài vuốt; (d) điểm bấm riêng cho từng ô, tự thử
>>> lệch điểm bấm nếu chưa vào được; (e) thời gian đo từ video: vào ô ~1,8s gồm 2 lần bấm (ô rồi nút "Đến"), mở bản đồ ~0,4s; (f) lập kế hoạch theo
>>> TỐC ĐỘ điểm/giây trong cửa sổ NGẮN (mục 2); (g) đọc số mũ bằng mẫu chữ số (vài ms, trước đây ~360ms/lần bằng tesseract).
>>> Bản 4: (a) vào ô phải bấm 2 lần (ô rồi nút "Đến"); (b) AN TOÀN: chỉ vào ô mà quân ta >= quân địch, kiểm lại số mũ ngay trước khi
>>> bấm; (c) vào ô mà thanh "Số người" KHÔNG phải màu phe ta -> RỜI NGAY, ô đó bị loại 30s; (d) chết ở ô nào thì ô đó bị loại 60s;
>>> (e) ở bản đồ quá `map_budget_s` (20s) thì ép chọn ô an toàn gần nhất để không kẹt; (f) log ghi rõ thời gian bản đồ -> vào ô.

======================================================================================================
1) LUẬT GAME (người dùng mô tả) VÀ CÁCH BOT HIỂU
======================================================================================================
  - Phe của mình: TỰ NHẬN DIỆN (field `my_color` = "auto", xem mục 1b) hoặc ép tay. 14 ô: 8 ô Lv1 (300đ), 4 ô Lv2 (600đ), 2 ô Lv3 (1800đ).
  - Vào ô = BẤM 2 LẦN: bấm ô trên bản đồ -> hiện avatar + nút "Đến" ngay trên nhãn ô -> PHẢI bấm "Đến" mới vào (HUD hiện ~1s sau lần bấm 2;
    cả quá trình `enter_s` ~1,8s, tự đo). Nút "Đến" cũng cho biết lần bấm 1 có trúng ô không (không hiện = bấm hụt -> thử lệch điểm bấm).
    Rời ô: bấm "Bản đồ lớn" -> bản đồ hiện NGAY (~0,4s) và tự căn giữa vào ô vừa rời (nhãn ô ở khoảng (360,775)).
  - Trong ô: thanh "Số người" ở góc phải trên. Thanh đầy 1 màu = chưa ai đếm ngược. Có đếm ngược = thanh chỉ đầy 1 phần,
    chiếm đủ 20s (`capture_s`) là thắng: số giây còn lại = 20 * (1 - độ đầy). Màu thanh = phe đang được đếm (xanh = ta).
    Phe nào ĐÔNG hơn trong ô thì đồng hồ thuộc phe đó (đổi màu).
  - Số giây của từng ô CHỈ thấy khi đang ở trong ô -> bot GHI NHỚ (ô nào, còn bao nhiêu giây, lúc nào thấy) rồi tự trừ dần theo giờ.
  - Chết -> banner "Bị đánh lui" + nút "Đến hồi sinh" -> về phòng chờ -> phải bấm "Bản đồ lớn" để vào ô lại.
  - Bản đồ RỘNG (~2000x700px) hơn màn hình: kéo 1:1 theo ngón tay, dừng ngay khi nhấc tay (không quán tính). Bot biết sẵn toạ độ "thế giới"
    của cả 14 ô (WORLD_BUILTIN) nên chỉ cần thấy 1 ô bất kỳ là biết đang nhìn chỗ nào và kéo thẳng tới ô cần vào (thường 0-1 lần vuốt).
  - Chết: banner "Bị đánh lui" -> "Đến hồi sinh" -> về PHÒNG PHE (thanh tên phe góc trái trên) ~9s mới mở được bản đồ: bot bấm "Bản đồ lớn"
    lặp lại tới khi mở được.

======================================================================================================
1b) NHẬN DIỆN PHE CỦA MÌNH - việc đầu tiên bot làm; MỖI LẦN CHẠY CHỈ NHẬN 1 PHE
======================================================================================================
  4 phe, thứ tự như bảng "Số đơn nền tảng hôm nay": xanh dương "Ăn No Chưa", vàng "Giao Đồ Ăn Ngon",
  hồng "Chuyển Phát Kinh Tây" (khoá màu trong code là "red"), cam "Đào Giao Nhanh".
  Mỗi phe có 1 màu, dùng cho: thanh "Số người", vòng tròn số người, mũ bảo hiểm và vòng sáng quanh ô trên bản đồ, chữ TÊN nhân vật,
  và thanh tên phe ở PHÒNG PHE (nơi hồi sinh). Đồng đội cùng màu với mình, địch khác màu.
  -> Nguồn 1 (sớm nhất, khi bot bắt đầu ở phòng phe/sau khi chết): màu thanh tên phe góc trái trên (`read_room_team`).
  -> Nguồn 2 (khi đã ở trong ô): màu chữ tên nhân vật mình dưới avatar giữa màn hình (`read_my_team`).
  -> 3 lần đọc liên tiếp giống nhau thì CHỐT và KHOÁ phe cho đến hết lần chạy này: không lưu file, không đổi giữa chừng
     (chạy lần sau đọc lại từ đầu, nên đổi tài khoản/phe không bị ảnh hưởng). Đọc khác phe đã khoá chỉ ghi cảnh báo.
  -> Đang ở bản đồ mà chưa biết phe: bot vào thử 1 ô Lv1 gần giữa màn hình để đọc, rồi mới lập kế hoạch.
  -> Muốn ép tay: my_color = "blue" | "yellow" | "red" (hồng) | "orange" (hoặc tên phe, hoặc "pink"). Mặc định "auto".
  Kiểm thử bằng video hoặc ảnh chụp:   python delivery_bot.py --team video.mp4      (hoặc anh.png)

======================================================================================================
2) CHIẾN THUẬT (hàm `plan`) - so sánh các ô trong KHOẢNG NGẮN theo tốc độ điểm/giây, xong ô nào nhảy ô tiếp rồi kiểm tra lại giờ
======================================================================================================
  Mỗi lần quyết định, bot xét các ô ứng viên:
    * ô đã có đồng hồ phe ta (đã ghi nhớ): sẽ XONG lúc `thấy_lúc + còn_lại`; bot phải ĐẾN KỊP (đến trước lúc xong `arrive_margin_s`).
    * ô chưa có đồng hồ: coi như phải chiếm mới = đứng đủ `capture_s`, nhân xác suất thắng theo số quân ta/địch (mũ bảo hiểm ở bản đồ).
    * ô vòng sáng đã là của ta: điểm rất thấp (`hold_factor`).
  Thời gian đi A -> B = mở bản đồ (`open_map_s`) + số lần vuốt * `swipe_s` + vào ô (`enter_s`); số lần vuốt tính theo khoảng cách thật.
  Bot thử mọi thứ tự tối đa `seq_len` (3) ô nhưng CHỈ trong `horizon_s` (30s) kể từ bây giờ, và chấm điểm bằng TỐC ĐỘ = tổng điểm / tổng giây
  (không phải tổng điểm) -> ô sắp xong luôn hơn ô phải chiếm mới 20s.
  Ví dụ 3 ô còn 5s / 5s / 15s, đang ở ô 5s thứ nhất, đi mất 2,5s: ở lại xong ô 5s (+300), ô 5s thứ hai đã xong trước khi tới kịp nên BỎ,
  nhảy sang ô 15s (tới lúc còn ~7s, đứng chờ) -> xong thì LẬP LẠI chu trình: đọc lại giờ ở ô mới, so sánh các ô còn lại, đi tiếp.
  AN TOÀN (ưu tiên trên điểm số): ô có quân địch > quân ta (đọc số mũ trên bản đồ, chỉ tin số đọc trong `info_ttl_s` 45s) bị trừ gần hết điểm;
  ô vừa bị loại (rời vì thanh không phải màu ta / chết ở đó) cũng bị loại `bad_s` giây. Ngay trước lúc bấm ô bot đọc lại số mũ thật; nếu địch > ta
  thì BỎ ô đó và chọn ô khác ngay. Vào ô rồi: sau ~1s mà thanh "Số người" không phải màu phe ta (hoặc địch đông hơn ta) -> rời ngay.
  Đang ở ô nào thì chỉ rời (vì tốc độ) khi chuỗi tốt nhất bắt đầu bằng ô khác và có tốc độ hơn "ở lại" `switch_ratio` (1.25) lần, đã ở >= `min_stay_s` (2,5s).

======================================================================================================
3) ẢNH MẪU (templates/delivery/, tên delivery_<loại>_<số>.png; mỗi loại nhiều file được)
======================================================================================================
  hud      chữ "Số người:" ở thanh góc phải trên (dấu hiệu đang ở TRONG khu chiếm đất).
  map      tiêu đề "Bản đồ khu thương mại".
  dead     banner "Bị đánh lui".          respawn  nút "Đến hồi sinh".
  bigmap   nút "Bản đồ lớn" góc trái dưới (không khớp thì vẫn bấm toạ độ cố định `bigmap_xy`).
  lobby    nút "Đại Chiến Giành Đơn" ở sảnh (bấm để vào).   done  dòng "Chờ nhận thưởng" ở sảnh = hết trận -> DỪNG.
  plot_<slug>  nhãn của từng ô trên bản đồ (14 mẫu: delivery_plot_lv3_toa_nha_ifc.png ...), xem PLOTS bên dưới.
  Cắt mẫu từ ảnh 720x1280:   python delivery_bot.py --add hud anh.png x1 y1 x2 y2
                             python delivery_bot.py --add plot:lv2_cang_so anh.png x1 y1 x2 y2
  Kiểm 1 ảnh:                python delivery_bot.py --check anh.png

======================================================================================================
4) FIELD CỦA BƯỚC `auto_delivery` (đều tuỳ chọn)
======================================================================================================
  test (False: chỉ đọc + log + lưu debug_delivery/, KHÔNG bấm/vuốt), max_seconds (0 = không giới hạn), my_color ("auto"; hoặc blue/yellow/red=hồng/orange),
  capture_s 20, enter_s 1.8, open_map_s 0.4, swipe_s 0.8, arrive_margin_s 0.8, seq_len 3, horizon_s 30, switch_ratio 1.25,
  min_stay_s 2.5, hold_factor 0.05, info_ttl_s 45, bad_s 30, bar_grace_s 1.0, map_budget_s 20, tap_dy (None = điểm bấm riêng từng ô, TAP_DY; số = ép chung), swipe_ms 160, settle_s 0.18, bigmap_xy [60,1115],
  thr 0.80 (ngưỡng nhãn ô), poll_s 0.4, unknown_max 25, tpl_dir, debug.
  Tự đo (trung bình trượt từ lần chạy thật): `enter_s`, `open_map_s`, `swipe_s`, và hệ số vuốt (độ dài thật / độ dài lệnh).
"""
import os
import sys
import json
import time
import itertools
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

REF_W, REF_H = 720, 1280

# (slug, tên hiển thị, cấp). Điểm theo cấp: Lv1 300, Lv2 600, Lv3 1800.
PLOTS = [
    ("lv1_cho_cu", "Lv1 Chợ Cũ", 1),
    ("lv1_pho_an_v", "Lv1 Phố Ăn Vặt", 1),
    ("lv1_trun", "Lv1 Trung Tâm Ăn Thực", 1),
    ("lv1_lang_trong_thanh_pho", "Lv1 Làng Trong Thành Phố", 1),
    ("lv1_lau_uyen_uong", "Lv1 Lầu Uyên Ương", 1),
    ("lv1_khu_dan_cu", "Lv1 Khu Dân Cư", 1),
    ("lv1_pho_di_bo", "Lv1 Phố Đi Bộ", 1),
    ("lv1_cho_ngoai_troi", "Lv1 Chợ Ngoài Trời", 1),
    ("lv2_thung_lung_thong_minh", "Lv2 Thung Lũng Thông Minh", 2),
    ("lv2_khu_sang_tao", "Lv2 Khu Sáng Tạo", 2),
    ("lv2_cang_so", "Lv2 Cảng Số", 2),
    ("lv2_toa_nha_thuong_mai", "Lv2 Tòa Nhà Thương Mại", 2),
    ("lv3_toa_nha_ifc", "Lv3 Tòa Nhà IFC", 3),
    ("lv3_trung_tam_tai_chinh", "Lv3 Trung Tâm Tài Chính", 3),
]
LEVEL_PTS = {1: 300, 2: 600, 3: 1800}
PLOT_LEVEL = {s: lv for s, _n, lv in PLOTS}
PLOT_NAME = {s: n for s, n, _lv in PLOTS}
KINDS = ("hud", "map", "dead", "respawn", "bigmap", "lobby", "done")

# vùng thanh "Số người" (toạ độ 720x1280)
BAR_X0, BAR_X1, BAR_Y = 415, 706, 314
CIRCLE_BOX = (505, 284, 640, 313)      # x0,y0,x1,y1 vùng các vòng tròn phe + số người

# 4 phe, ĐÚNG THỨ TỰ trong bảng "Số đơn nền tảng hôm nay" (trên xuống). Khoá màu: blue / yellow / red (= HỒNG) / orange.
TEAMS = (
    ("blue", "Ăn No Chưa", "xanh dương"),
    ("yellow", "Giao Đồ Ăn Ngon", "vàng"),
    ("red", "Chuyển Phát Kinh Tây", "hồng"),
    ("orange", "Đào Giao Nhanh", "cam"),
)
TEAM_NAME = {c: n for c, n, _v in TEAMS}
TEAM_VN = {c: v for c, _n, v in TEAMS}
COLOR_ALIAS = {"pink": "red", "hong": "red", "hồng": "red", "xanh": "blue", "xanh dương": "blue", "vang": "yellow",
               "vàng": "yellow", "cam": "orange"}
for _c, _n, _v in TEAMS:
    COLOR_ALIAS[_n.lower()] = _c
NAME_BOX = (283, 712, 438, 742)        # tên nhân vật của mình nằm ngay dưới avatar (camera bám theo nên avatar luôn ở giữa màn hình)
# vạch màu đầu mỗi thanh trong bảng điểm 4 phe (x, y, màu): dùng để biết "đang ở TRONG ô" mà không cần ảnh mẫu
SCORE_ROWS = ((533, 192, "yellow"), (533, 221, "red"), (533, 250, "orange"))
ROOM_HDR_BOX = (70, 124, 270, 146)     # thanh tên phe ở PHÒNG PHE (góc trái trên): màu = phe của mình

WORLD_BUILTIN = {   # toạ độ nhãn 14 ô trong hệ toạ độ bản đồ (px), dựng từ video chơi thật; sai số định vị ~1px
    "lv1_cho_cu": (1879.6, 0.0),
    "lv1_lau_uyen_uong": (199.0, 75.7),
    "lv2_khu_sang_tao": (1039.7, 76.6),
    "lv1_pho_an_v": (1975.6, 209.0),
    "lv1_khu_dan_cu": (15.0, 271.7),
    "lv3_trung_tam_tai_chinh": (1293.6, 379.6),
    "lv2_thung_lung_thong_minh": (1626.6, 381.0),
    "lv3_toa_nha_ifc": (858.6, 386.5),
    "lv2_toa_nha_thuong_mai": (459.9, 396.6),
    "lv1_trun": (2006.6, 469.0),
    "lv1_pho_di_bo": (0.0, 536.7),
    "lv1_lang_trong_thanh_pho": (1910.6, 702.0),
    "lv2_cang_so": (892.6, 706.5),
    "lv1_cho_ngoai_troi": (181.0, 706.7),
}

PLOT_THR = {"lv1_trun": 0.84}          # nhãn ngắn dễ khớp nhầm: đo trên video, đúng >= 0.85, sai <= 0.81
# điểm bấm = nhãn + (0, TAP_DY): đo tâm vòng sáng so với nhãn trên video (mặc định -75). Chưa thử trên máy thật -> có thử lệch khi bấm hụt.
TAP_DY = {"lv1_lau_uyen_uong": -70, "lv1_pho_an_v": -78, "lv1_trun": -90, "lv1_lang_trong_thanh_pho": -90,
          "lv2_thung_lung_thong_minh": -70, "lv2_khu_sang_tao": -82, "lv2_cang_so": -79, "lv2_toa_nha_thuong_mai": -79,
          "lv3_toa_nha_ifc": -65, "lv3_trung_tam_tai_chinh": -65}
TAP_DY_DEFAULT = -75
TAP_RETRY = ((0, 0), (12, -20), (-12, 22), (0, -40), (0, 40))     # (dx, dy) cộng thêm ở lần thử 1,2,3...
SAFE_X, SAFE_Y = (90, 640), (230, 1000)       # vùng điểm bấm an toàn (tránh HUD trên, nút/icon góc dưới)
SWIPE_MAX = (600, 840)                         # độ dài tối đa 1 lần vuốt (px)
VIEW_CENTER = (360, 610)

_DIGIT_SEEDS = {   # mẫu chữ số trắng viền tối trên mũ bản đồ (16x10, mức xám 0-9), học từ video
    1: (
        "0000001477000001399800023579984447899999999999999933333347890000002899000000168900000016880000002888000000158800000015880000001578000000158900000015890000001588",
        "0000001899000002589911224699996789999999555555599900000008990000000899000000089900000008990000000899000000089900000008990000000899000000089900000008990000000898",
    ),
    2: (
        "0137898410158755687138520003844830000058772000004833100000580000000285000000279200001798300014886200026874100016851000004851000000772000000098777777767888788888",
        "0013785100027877785116841014843841000057572000002856200000271100000167000000048500000269610001498620003796300003885100002874000000484000000078300000109988888888",
        "1199899910997707779296000000699000000009900000000930000000090000000079000000089900011998800229977000399960000099550000009900000000930000000097777777779999999999",
    ),
    3: (
        "0158986310168755773028510015715820000382561000027112000015710000136830000278883000012248820000000176110000004853000000388620000057685200037416876677410137996200",
    ),
    4: (
        "0000004720000002782000001698200001487820001373272000375016200277201620158400162037510016207841113741998777788633455568650001112621000000162000000016200000001620",
    ),
    5: (
        "0122641100149877894048730026838830000377860000003383100000008127774100988888882086000006916000000074400000006900000000694000000079840000049348500058500498889500",
    ),
}
_DIGIT_CACHE: Dict[bytes, Optional[int]] = {}


def norm_color(v):
    """'auto'/None -> None; 'pink'/'hồng'/'Giao Đồ Ăn Ngon'... -> blue|yellow|red|orange; giá trị lạ -> ValueError."""
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("", "auto", "tự động", "tu dong"):
        return None
    s = COLOR_ALIAS.get(s, s)
    if s not in TEAM_NAME:
        raise ValueError(v)
    return s


def _tpl_dir_default():
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "delivery")
    return here if os.path.isdir(here) else os.path.join("templates", "delivery")


def _imread(p):
    try:
        return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None


def _imwrite(p, img):
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        ok, buf = cv2.imencode(os.path.splitext(p)[1] or ".png", img)
        if ok:
            buf.tofile(p)
        return ok
    except Exception:
        return False


def load_templates(tpl_dir: str) -> Dict[str, List[Tuple[str, np.ndarray]]]:
    """Nạp delivery_<loại>_N.png và delivery_plot_<slug>_N.png -> {loại hoặc 'plot:<slug>': [(tên, ảnh)]}."""
    out: Dict[str, list] = {k: [] for k in KINDS}
    for s, _n, _l in PLOTS:
        out["plot:" + s] = []
    if not os.path.isdir(tpl_dir):
        return out
    for fn in sorted(os.listdir(tpl_dir)):
        low = fn.lower()
        if not (low.startswith("delivery_") and low.endswith((".png", ".jpg", ".jpeg"))):
            continue
        stem = os.path.splitext(fn)[0][len("delivery_"):]
        key = None
        if stem.startswith("plot_"):
            body = stem[len("plot_"):]
            for s, _n, _l in PLOTS:
                if body == s or body.startswith(s + "_"):
                    key = "plot:" + s
                    break
        else:
            for k in KINDS:
                if stem == k or stem.startswith(k + "_"):
                    key = k
                    break
        if key is None:
            continue
        img = _imread(os.path.join(tpl_dir, fn))
        if img is not None:
            out[key].append((fn, img))
    return out


def match_tpl(img, tpl, region=None):
    """Khớp xám. region = (x0,y0,x1,y1) pixel. Trả (cx, cy, điểm) theo toạ độ ảnh gốc."""
    if img is None or tpl is None:
        return None, None, 0.0
    x0, y0 = 0, 0
    sub = img
    if region:
        x0, y0, x1, y1 = [int(v) for v in region]
        sub = img[max(0, y0):y1, max(0, x0):x1]
        x0, y0 = max(0, x0), max(0, y0)
    th, tw = tpl.shape[:2]
    if sub.shape[0] < th or sub.shape[1] < tw:
        return None, None, 0.0
    a = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) if sub.ndim == 3 else sub
    b = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY) if tpl.ndim == 3 else tpl
    res = cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)
    _mn, mx, _ml, loc = cv2.minMaxLoc(res)
    return x0 + loc[0] + tw // 2, y0 + loc[1] + th // 2, float(mx)


def _sh(h):
    """Dịch hue 15 đơn vị để màu HỒNG (hue ~165..179 rồi vắt sang 0..3) không bị gãy ở mốc 0/179 khi lấy trung vị."""
    return (np.asarray(h, dtype=np.int32) + 15) % 180


def median_hue(hs):
    """Hue trung vị theo vòng tròn (đúng cả với hồng)."""
    return int((np.median(_sh(hs)) - 15) % 180)


def hue_masks(h, kind="ui"):
    """Mảng bool cho từng phe theo hue OpenCV (0-179). Ranh giới ĐO TRÊN VIDEO THẬT:
    ui (thanh/vòng số người/chữ tên): vàng ~19, cam ~12, hồng ~175, xanh ~100.  helmet (mũ): vàng ~22, cam ~14."""
    h = np.asarray(h, dtype=np.int32)
    ob = 18 if kind == "helmet" else 16          # ranh giới cam | vàng
    return {
        "blue": (h >= 92) & (h <= 112),
        "red": (h >= 165) | (h <= 3),
        "orange": (h >= 4) & (h < ob),
        "yellow": (h >= ob) & (h <= 34),
    }


def hue_name(h, kind="ui"):
    """Tên phe theo hue. kind: 'ui' | 'helmet' | 'ring' (vòng sáng quanh ô: nhạt, pha trắng nên lệch hue - tính trên hue đã dịch)."""
    h = int(h)
    if kind == "band":                           # thanh tên phe/chủ ô: hồng ~4, cam ~15, vàng ~20.5, xanh ~100 (hue gốc)
        s = (h + 15) % 180
        if s < 24:
            return "red"
        if s < 33:
            return "orange"
        if s < 60:
            return "yellow"
        if 100 <= s <= 130:
            return "blue"
        return "?"
    if kind == "ring":
        s = (h + 15) % 180                       # đo: hồng 13-23, cam 32-36, vàng 40-42, xanh 104-111
        if s < 26:
            return "red"
        if s < 38:
            return "orange"
        if s < 60:
            return "yellow"
        if 100 <= s <= 130:
            return "blue"
        return "?"
    for name, m in hue_masks(np.array([h]), kind).items():
        if m[0]:
            return name
    return "?"


def _tess(binary):
    import pytesseract
    b = cv2.copyMakeBorder(binary, 14, 14, 14, 14, cv2.BORDER_CONSTANT, value=255)
    txt = pytesseract.image_to_string(b, config="--psm 10 -c tessedit_char_whitelist=0123456789").strip()
    return int(txt) if txt.isdigit() else None


def _ocr_digits(crop):
    """Đọc số trong ảnh nhỏ (chữ trắng/kem, viền tối). Hai cách (lọc màu trắng ít bão hoà / Otsu xám); trùng nhau mới tin,
    khác nhau thì trả cách lọc màu. Trả int hoặc None. Cần pytesseract; thiếu thì None."""
    try:
        import pytesseract  # noqa: F401
    except Exception:
        return None
    ckey = b"c" + (crop[::2, ::2] // 40).tobytes()
    if ckey in _DIGIT_CACHE:
        return _DIGIT_CACHE[ckey]
    out = _ocr_digits_raw(crop)
    _DIGIT_CACHE[ckey] = out
    if len(_DIGIT_CACHE) > 400:
        _DIGIT_CACHE.clear()
    return out


def _ocr_digits_raw(crop):
    try:
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        m = ((hsv[:, :, 1] < 85) & (hsv[:, :, 2] > 185)).astype(np.uint8) * 255
        m = cv2.resize(m, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        _t, m = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY)
        r1 = _tess(255 - m)
        g = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
        _t, o = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if o.mean() < 127:                 # chữ phải đen trên nền trắng
            o = 255 - o
        r2 = _tess(o)
        return r1 if r1 == r2 or r2 is None else (r1 if r1 is not None else r2)
    except Exception:
        return None


def _digit_templates():
    t = getattr(_digit_templates, "cache", None)
    if t is None:
        t = [(d, np.array([int(ch) / 9.0 for ch in s], np.float32)) for d, ss in _DIGIT_SEEDS.items() for s in ss]
        _digit_templates.cache = t
    return t


def _digit_feat(mask):
    ys, xs = np.where(mask > 0)
    if len(ys) == 0:
        return None
    m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return cv2.resize(m.astype(np.float32), (10, 16), interpolation=cv2.INTER_AREA).ravel()


def _classify_digit(mask):
    """Chữ số trắng viền tối (mặt nạ nhị phân) -> 0-9. Khớp mẫu (vài ms); chữ số lạ thì nhờ tesseract 1 lần rồi nhớ theo ảnh."""
    f = _digit_feat(mask)
    if f is None:
        return None
    ds = sorted((float(np.abs(f - t).mean()), d) for d, t in _digit_templates())
    best = ds[0]
    other = next((x for x in ds if x[1] != best[1]), (9.0, -1))
    if best[0] <= 0.28 and other[0] - best[0] >= 0.012:
        return best[1]
    key = b"%dx%d" % mask.shape + mask.tobytes()
    if key not in _DIGIT_CACHE:
        try:
            import pytesseract
            big = cv2.resize(mask * 255, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)
            big = cv2.copyMakeBorder(255 - big, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
            t = pytesseract.image_to_string(big, config="--psm 10 -c tessedit_char_whitelist=0123456789").strip()
            _DIGIT_CACHE[key] = int(t) if t.isdigit() and len(t) == 1 else None
        except Exception:
            _DIGIT_CACHE[key] = None
    return _DIGIT_CACHE[key]


def read_count(img, bx, by):
    """Đọc số (1-2 chữ số) ngay bên phải mũ bảo hiểm: (bx, by) = mép phải của mũ, tâm dọc. Trả int hoặc None."""
    crop = img[max(0, by - 15):by + 15, max(0, bx - 1):bx + 33]
    if crop.shape[0] < 20 or crop.shape[1] < 8:
        return None
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    m = ((hsv[:, :, 1] < 80) & (hsv[:, :, 2] > 190)).astype(np.uint8)
    cnt, lab, st, _c = cv2.connectedComponentsWithStats(m, 8)
    comps = []
    for k in range(1, cnt):
        x, y, w, h, a = st[k]
        if 11 <= h <= 26 and 3 <= w <= 18 and a >= 35:
            comps.append((x, w, (lab[y:y + h, x:x + w] == k).astype(np.uint8)))
    comps.sort(key=lambda t: t[0])
    if not comps or comps[0][0] > 12:
        return None
    digits = [comps[0]]
    if len(comps) > 1 and comps[1][0] - (comps[0][0] + comps[0][1]) <= 4:       # chữ số thứ 2 sát chữ số đầu
        digits.append(comps[1])
    val = 0
    for _x, _w, mk in digits:
        d = _classify_digit(mk)
        if d is None:
            return None
        val = val * 10 + d
    return val


# ----------------------------------------------------------------------------
# Đọc màn hình
# ----------------------------------------------------------------------------
def read_hud(img, capture_s=20.0, count_circles=True):
    """Đọc thanh 'Số người'. Trả dict: timer (giây còn lại hoặc None), owner (màu phe đang đếm hoặc None), circles {màu: số}."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    row = hsv[BAR_Y, BAR_X0:BAR_X1].astype(int)
    fill = (row[:, 1] > 70) & (row[:, 2] > 45)
    n = len(fill)
    run = 0
    gap = 0
    for i in range(n):
        if fill[i]:
            run = i + 1
            gap = 0
        else:
            gap += 1
            if gap > 5:
                break
    frac = run / float(n)
    timer = None
    owner = None
    if run > 0:
        hs = row[:run][fill[:run]][:, 0]
        owner = hue_name(median_hue(hs)) if len(hs) else None
        if frac < 0.97:
            timer = round(max(0.0, capture_s * (1.0 - frac)), 1)
    circles: Optional[Dict[str, Optional[int]]] = None      # None = lần này không đọc
    if count_circles:
        circles = {}
        x0, y0, x1, y1 = CIRCLE_BOX
        sub = hsv[y0:y1, x0:x1]
        cand = []
        for name in ("blue", "yellow", "orange", "red"):
            vmin = 172 if name == "blue" else 150      # vòng xanh sáng hơn nền thanh (V 181 so với 156)
            m = (hue_masks(sub[:, :, 0])[name] & (sub[:, :, 1] > 120) & (sub[:, :, 2] > vmin)).astype(np.uint8)
            cnt, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
            for k in range(1, cnt):
                if 120 <= st[k, cv2.CC_STAT_AREA] <= 900 and st[k, cv2.CC_STAT_WIDTH] >= 14:
                    cand.append((int(st[k, cv2.CC_STAT_AREA]), name, int(cen[k][0]) + x0, int(cen[k][1]) + y0))
        taken = []
        for _a, name, cx, cy in sorted(cand, reverse=True):     # cùng 1 vòng tròn không được tính cho 2 màu (viền răng cưa)
            if name in circles or any(abs(cx - tx) < 14 and abs(cy - ty) < 14 for tx, ty in taken):
                continue
            taken.append((cx, cy))
            circles[name] = _ocr_digits(img[cy - 10:cy + 10, cx - 9:cx + 9])
    return {"timer": timer, "owner": owner, "frac": round(frac, 3), "circles": circles}


def helmets_near(img, cx, cy):
    """Đếm mũ bảo hiểm (số người từng phe) ngay dưới nhãn ô tại (cx,cy). Trả {màu: số, không đọc được số thì tính 1}."""
    h, w = img.shape[:2]
    x0, x1 = max(0, cx - 110), min(w, cx + 130)
    y0, y1 = min(h - 1, cy + 14), min(h, cy + 80)
    if y1 - y0 < 10:
        return {}
    hsv = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    hh = hsv[:, :, 0]
    m = (((hh >= 4) & (hh <= 34)) | ((hh >= 92) & (hh <= 112)) | (hh >= 165) | (hh <= 3))
    m = (m & (hsv[:, :, 1] > 140) & (hsv[:, :, 2] > 170)).astype(np.uint8)
    m = cv2.dilate(m, np.ones((3, 3), np.uint8))
    cnt, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    out = {}
    for k in range(1, cnt):
        if not (250 <= st[k, cv2.CC_STAT_AREA] <= 1800):
            continue
        sel = (lab == k) & (hsv[:, :, 1] > 140) & (hsv[:, :, 2] > 170)
        name = hue_name(median_hue(hh[sel]), "helmet") if sel.any() else "?"
        if name == "?":
            continue
        xs = np.where(sel.any(axis=0))[0]
        bx = x0 + (int(xs.max()) if len(xs) else st[k, cv2.CC_STAT_LEFT] + st[k, cv2.CC_STAT_WIDTH])
        by = y0 + int(cen[k][1]) + 4
        num = read_count(img, bx, by)
        if num is not None and not (1 <= num <= 40):
            num = None
        out[name] = out.get(name, 0) + (num if num else 1)
    return out


def ring_owner(img, cx, cy):
    """Màu phe đang giữ ô = màu VÒNG SÁNG quanh ô (nằm ngay trên nhãn). Trả blue|yellow|red|orange hoặc None."""
    h, w = img.shape[:2]
    y0, y1 = max(0, cy - 120), max(1, cy - 22)       # vòng nằm cao thấp tuỳ toà nhà -> lấy dải rộng
    x0, x1 = max(0, cx - 110), min(w, cx + 110)
    reg = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV).reshape(-1, 3)
    m = (reg[:, 1] > 55) & (reg[:, 2] > 190)
    if m.sum() < 300:
        return None
    name = hue_name(median_hue(reg[m][:, 0]), "ring")
    return None if name == "?" else name


def ring_is_blue(img, cx, cy):
    """(giữ để tương thích bản cũ) vòng sáng có phải màu xanh dương không."""
    return ring_owner(img, cx, cy) == "blue"


def read_my_team(img):
    """PHE CỦA MÌNH = màu chữ tên nhân vật mình (dưới avatar, giữa màn hình). Đồng đội cùng màu, địch khác màu.
    Chỉ gọi khi đang ở TRONG ô. Trả blue|yellow|red|orange, hoặc None nếu không chắc (tên bị che, vòng sáng át màu...)."""
    x0, y0, x1, y1 = NAME_BOX
    hsv = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    m = (hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 170)    # đo: chữ vàng S~140 V~235, chữ hồng S~90 V~200 -> ngưỡng đủ lỏng cho cả 4 phe
    n = int(m.sum())
    if n < 25 or n > 0.5 * m.size:                    # quá ít = không thấy tên; phủ quá nửa vùng = đó là NỀN (vd sàn gỗ cam khi đang hồi sinh)
        return None
    cnt = {k: int(v.sum()) for k, v in hue_masks(hsv[:, :, 0][m]).items()}
    top = max(cnt, key=cnt.get)
    return top if cnt[top] >= 0.6 * n else None


def read_room_team(img):
    """PHÒNG PHE (nơi hồi sinh): thanh tên phe góc trái trên có màu phe của MÌNH. Chỉ dùng khi state == 'room'
    (trong ô thì thanh đó là màu CHỦ Ô, không phải phe mình). Trả blue|yellow|red|orange hoặc None."""
    x0, y0, x1, y1 = ROOM_HDR_BOX
    hsv = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    m = (hsv[:, :, 1] > 100) & (hsv[:, :, 2] > 150)
    if m.mean() < 0.35:
        return None
    name = hue_name(median_hue(hsv[:, :, 0][m]), "band")
    return None if name == "?" else name


def find_den_button(img, lx, ly):
    """Nút 'Đến' (viên thuốc xanh ngọc) hiện ngay TRÊN nhãn ô vừa bấm, lệch ~(-4,-53)px so với tâm nhãn (đo trên ảnh chụp + video).
    Chỉ ô vừa bấm mới có nút. Trả (x, y) tâm nút hoặc None."""
    h, w = img.shape[:2]
    x0, x1, y0, y1 = max(0, int(lx - 90)), min(w, int(lx + 90)), max(0, int(ly - 95)), max(1, int(ly - 15))
    hsv = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    m = ((hsv[:, :, 0] >= 82) & (hsv[:, :, 0] <= 102) & (hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 70) & (hsv[:, :, 2] < 200)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 9), np.uint8))
    cnt, lab, st, cen = cv2.connectedComponentsWithStats(m, 8)
    best = None
    for k in range(1, cnt):
        x, y, bw, bh, a = st[k]
        if 70 <= bw <= 140 and 20 <= bh <= 48 and a > 1200 and (best is None or a > best[2]):
            best = (float(cen[k][0] + x0), float(cen[k][1] + y0), int(a))
    return (best[0], best[1]) if best else None


def looks_like_zone(img):
    """Bảng điểm 4 phe (góc phải trên) có vạch màu vàng/hồng/cam đúng thứ tự -> đang ở TRONG ô (không cần ảnh mẫu)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    ok = 0
    for x, y, exp in SCORE_ROWS:
        seg = hsv[y - 1:y + 2, x:x + 4].reshape(-1, 3)
        if (seg[:, 1] > 80).mean() > 0.8 and (seg[:, 2] > 120).mean() > 0.8 and hue_name(median_hue(seg[:, 0])) == exp:
            ok += 1
    return ok >= 2


def measure_shift(a_bgr, b_bgr):
    """Độ dịch (dx, dy) pixel của NỘI DUNG bản đồ từ ảnh a sang b (dương = trôi sang phải/xuống), và độ tin cậy."""
    def prep(im):
        g = cv2.cvtColor(im[140:1040, 130:720], cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, None, fx=0.5, fy=0.5)
        return g.astype(np.float32)
    a, b = prep(a_bgr), prep(b_bgr)
    win = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), resp = cv2.phaseCorrelate(a, b, win)
    return dx * 2.0, dy * 2.0, float(resp)


# ----------------------------------------------------------------------------
# Lập kế hoạch (thuần tính toán, test được)
# ----------------------------------------------------------------------------
def plan(now, cur, known, travel, cfg):
    """
    now: giờ hiện tại (s). cur: slug ô đang đứng hoặc None (đang ở bản đồ/phòng chờ).
    known: {slug: {"owner": "ours"|"enemy"|None, "done_at": giờ xong dự kiến hoặc None, "ours_ring": bool,
                   "allies": int, "enemies": int}}
    travel(a, b): giây đi từ a (hoặc None) sang b.
    Chấm điểm = TỐC ĐỘ (điểm / giây) của chuỗi ô trong cửa sổ NGẮN `horizon_s`: ô sắp xong luôn hơn ô phải chiếm mới 20s.
    Trả (chuỗi tốt nhất, tốc độ của nó, {slug đầu tiên: tốc độ tốt nhất của các chuỗi bắt đầu bằng slug đó}).
    """
    margin = cfg.get("arrive_margin_s", 0.8)
    cap = cfg.get("capture_s", 20.0)
    horizon = cfg.get("horizon_s", 30.0)
    seq_len = int(cfg.get("seq_len", 3))
    hold = cfg.get("hold_factor", 0.05)
    ttl = cfg.get("info_ttl_s", 45.0)

    cands = []
    for slug, _n, lv in PLOTS:
        info = known.get(slug, {})
        pts = LEVEL_PTS[lv]
        if info.get("ours_ring") and not info.get("done_at"):
            pts *= hold
        fresh = now - info.get("seen_t", -1e9) <= ttl           # số quân cũ quá thì coi như chưa biết
        al, en = (info.get("allies", 0) or 0, info.get("enemies", 0) or 0) if fresh else (0, 0)
        if en > al:                                              # ta (+bản thân) không hơn địch -> dễ chết/mất công: gần như loại
            pts *= 0.03
        if info.get("bad_until", 0) > now:                       # vừa rời/chết ở đó
            pts *= 0.02
        done_at = info.get("done_at")
        if done_at is not None and done_at <= now:   # đã xong lúc ta không thấy -> coi như đã thuộc ta
            info = dict(info, done_at=None)
            pts *= hold
            done_at = None
        p = (al + 1.0) / (al + en + 1.5)
        cands.append((slug, pts, done_at, p))
    # chỉ giữ ứng viên đáng xét: ô sắp xong (xếp theo điểm) + ô chiếm mới tốt nhất
    cands.sort(key=lambda c: -(c[1] * (1.0 if c[2] is not None else c[3])))
    full = cands
    cands = cands[:7]
    if cur is not None and all(c[0] != cur for c in cands):     # ô đang đứng luôn được xét (để biết "ở lại" đáng bao nhiêu)
        cands.append(next(c for c in full if c[0] == cur))

    def run(seq):
        t = now
        place = cur
        total = 0.0
        used = []
        for slug in seq:
            c = next(x for x in cands if x[0] == slug)
            tr = 0.0 if slug == place else travel(place, slug)
            arrive = t + tr
            if c[2] is not None:                       # ô đã có đồng hồ phe ta
                if arrive > c[2] - margin:
                    return None                        # đến không kịp -> chuỗi này vô hiệu
                t_end, gain = max(arrive, c[2]), c[1]
            else:                                       # phải chiếm mới: đứng đủ capture_s
                t_end, gain = arrive + cap, c[1] * c[3]
            if used and t_end - now > horizon:          # chỉ nối thêm ô nếu vẫn nằm trong cửa sổ ngắn
                break
            t = t_end
            total += gain
            place = slug
            used.append(slug)
        if not used:
            return None
        return total, t, used

    best = (None, -1.0, 1e9, 0.0)
    first_best: Dict[str, float] = {}
    names = [c[0] for c in cands]
    for L in range(1, seq_len + 1):
        for seq in itertools.permutations(names, L):
            r = run(seq)
            if r is None:
                continue
            total, tend, used = r
            rate = total / max(tend - now, 1.0)
            if used[0] != seq[0]:
                continue
            if rate > first_best.get(seq[0], -1.0):
                first_best[seq[0]] = rate
            if rate > best[1] + 1e-9 or (abs(rate - best[1]) < 1e-9 and total > best[3]):
                best = (used, rate, tend, total)
    return (list(best[0]) if best[0] else []), max(best[1], 0.0), first_best


# ----------------------------------------------------------------------------
# Bot
# ----------------------------------------------------------------------------
class DeliveryBot:
    def __init__(self, adb, tpls, log=None, should_stop=None, **cfg):
        self.adb = adb
        self.tpls = tpls
        self.log = log or (lambda lv, m: print(f"[{lv}] {m}"))
        self.should_stop = should_stop or (lambda: False)
        d = dict(test=False, max_seconds=0, my_color="auto", capture_s=20.0, enter_s=1.8, open_map_s=0.4,
                 swipe_s=0.8, arrive_margin_s=0.8, seq_len=3, horizon_s=30.0, switch_ratio=1.25, min_stay_s=2.5,
                 hold_factor=0.05, tap_dy=None, bigmap_xy=[60, 1115], thr=0.80, poll_s=0.4, unknown_max=25,
                 swipe_ms=160, settle_s=0.18, info_ttl_s=45.0, bad_s=30.0, bar_grace_s=1.0, map_budget_s=20.0, debug=False, map_file=None, team_file=None)
        d.update({k: v for k, v in cfg.items() if v is not None})
        self.c = d
        self._now = time.time
        self._sleep = time.sleep
        self.sx = self.sy = 1.0
        self.known: Dict[str, dict] = {}
        self.world: Dict[str, Tuple[float, float]] = {}    # slug -> (wx, wy) tâm nhãn trong hệ toạ độ bản đồ
        self.off = [0.0, 0.0]                               # độ dịch nội dung tích luỹ (world = màn hình - off)
        self.have_off = False
        self.cur: Optional[str] = None
        self.enter_t: Optional[float] = None
        self.tap_t: Optional[float] = None
        self.stats = {"captures": 0, "deaths": 0, "switches": 0}
        self.my: Optional[str] = None             # phe của mình: blue|yellow|red|orange; None = chưa biết
        self.my_confirmed = False                  # đã CHỐT + KHOÁ cho lần chạy này
        self._streak: Tuple[Optional[str], int] = (None, 0)
        self._conflict = 0
        self._unk_t: Optional[float] = None
        self._unk_warned = False
        self.view_plot: Optional[str] = None       # ô vừa rời = ô nằm giữa bản đồ khi mở
        self.gain = [1.0, 1.0]                     # hệ số vuốt học được: độ dịch thật / độ dịch lệnh
        self._tries: Dict[str, int] = {}           # số lần bấm hụt từng ô (để thử lệch điểm bấm)
        self._circ_t = -9.0
        self._bad_world = 0
        self._room_streak: Tuple[Optional[str], Optional[float], int] = (None, None, 0)
        self._lost_n = 0
        self._last_move = (0.0, 0.0)
        self._last_label = (360.0, 700.0)
        self._gate: Optional[str] = None            # ô vừa bị chặn vì địch đông
        self._img_now = None
        self._bad_bar = 0
        self._map_since: Optional[float] = None
        self._n_swipe = 0
        self._n_tap = 0
        try:
            fixed = norm_color(d.get("my_color"))
        except ValueError:
            self.log("WARN", f"my_color={d.get('my_color')!r} không hợp lệ -> dùng 'auto'")
            fixed = None
        if fixed:
            self.my, self.my_confirmed = fixed, True
        self._load_map()

    # ---- phe của mình: mỗi lần chạy chỉ nhận 1 phe rồi KHOÁ ----
    def _learn_color(self, col):
        """Chưa khoá: 3 lần đọc liên tiếp giống nhau thì CHỐT và KHOÁ cho cả lần chạy. Đã khoá: không đổi, chỉ cảnh báo."""
        if col is None:
            return
        if self.my_confirmed:
            if col != self.my:
                self._conflict += 1
                if self._conflict == 10:
                    self.log("WARN", f"Phe đang khoá = {TEAM_VN[self.my]} nhưng nhiều lần đọc ra màu {TEAM_VN[col]} - "
                                     f"nếu sai hãy dừng và chạy lại bot (hoặc ép my_color)")
            else:
                self._conflict = 0
            return
        self._streak = (col, self._streak[1] + 1) if self._streak[0] == col else (col, 1)
        if self._streak[1] >= 3:
            self._lock_team(col, "chữ tên nhân vật")

    def _lock_team(self, col, why):
        self.my, self.my_confirmed = col, True
        self.log("INFO", f"🎨 Phe của mình: {TEAM_NAME[col]} ({TEAM_VN[col]}) [đọc từ {why}] - khoá cho lần chạy này")

    def _learn_team(self, img):                    # đang ở trong ô: màu chữ tên mình
        self._learn_color(read_my_team(img))

    def _learn_room(self, img):
        """Phòng phe: thanh tên phe = phe của mình. NHƯNG khung chuyển cảnh vào ô cũng bị nhận là 'room' ~1,5s và khi đó thanh tên mang
        màu CHỦ Ô (có thể là địch) -> chỉ tin khi cùng 1 màu liên tục >= 3s và >= 4 lần đọc (phòng phe thật sau khi chết kéo dài ~9s)."""
        col = read_room_team(img)
        now = self._now()
        c0, t0, n = self._room_streak
        if col is None or col != c0:
            self._room_streak = (col, now, 1) if col else (None, None, 0)
            return
        self._room_streak = (c0, t0, n + 1)
        if not self.my_confirmed and now - t0 >= 3.0 and n + 1 >= 4:
            self._lock_team(col, "thanh tên phe ở phòng phe")

    def _probe_slug(self, vis):
        """Chưa biết phe: chọn ô để vào thử = Lv thấp nhất, gần giữa màn hình nhất (chỉ cần vào vài giây để đọc tên)."""
        ok = [(PLOT_LEVEL[s], abs(cx - 360) + abs(cy - 640), s) for s, (cx, cy, _sc) in vis.items()
              if SAFE_X[0] < cx < SAFE_X[1] and SAFE_Y[0] < cy + TAP_DY_DEFAULT < SAFE_Y[1]]
        return min(ok)[2] if ok else None

    # ---- tiện ích ----
    def _grab(self):
        img = self.adb.screencap_fast()
        if img is None:
            return None
        h, w = img.shape[:2]
        self.sx, self.sy = w / float(REF_W), h / float(REF_H)
        if (w, h) != (REF_W, REF_H):
            img = cv2.resize(img, (REF_W, REF_H))
        return img

    def _tap(self, x, y, why=""):
        if self.c["test"]:
            self.log("INFO", f"[TEST] sẽ bấm ({int(x)},{int(y)}) {why}")
            return
        self._n_tap += 1
        self.adb.tap_px(x * self.sx, y * self.sy)

    def _swipe_view(self, dx, dy):
        """Kéo NỘI DUNG bản đồ đi (dx,dy) px. Chia cho hệ số vuốt đã học; quá dài thì chia thành vài lần vuốt liên tiếp (mỗi lần
        <= SWIPE_MAX, không chụp xen giữa vì bản đồ dừng ngay khi nhấc tay). Vuốt ngắn quá (<60px) dễ bị coi là BẤM -> kéo dài ra 60px."""
        gx, gy = self.gain
        cx_, cy_ = dx / gx, dy / gy
        n = min(6, max(1, int(np.ceil(max(abs(cx_) / SWIPE_MAX[0], abs(cy_) / SWIPE_MAX[1]) - 1e-9))))
        for _i in range(n):
            sx, sy = cx_ / n, cy_ / n
            ln = max(abs(sx), abs(sy))
            if ln < 60:
                k = 60.0 / max(ln, 1.0)
                sx, sy = sx * k, sy * k
            x1, y1 = VIEW_CENTER[0] - sx / 2.0, VIEW_CENTER[1] - sy / 2.0
            x2, y2 = VIEW_CENTER[0] + sx / 2.0, VIEW_CENTER[1] + sy / 2.0
            if self.c["test"]:
                self.log("INFO", f"[TEST] sẽ vuốt ({int(x1)},{int(y1)})->({int(x2)},{int(y2)})")
                continue
            self._n_swipe += 1
            self.adb.swipe_px(x1 * self.sx, y1 * self.sy, x2 * self.sx, y2 * self.sy, int(self.c["swipe_ms"]))

    def _has(self, img, kind, thr=None, region=None):
        thr = thr or self.c["thr"]
        best = (None, None, 0.0)
        for _n, t in self.tpls.get(kind, []):
            r = match_tpl(img, t, region)
            if r[2] > best[2]:
                best = r
        return best if best[2] >= thr else (None, None, best[2])

    def detect(self, img):
        thr = 0.70
        if self._has(img, "dead", thr)[0] is not None or self._has(img, "respawn", thr)[0] is not None:
            return "dead"
        if self._has(img, "map", thr)[0] is not None:
            return "map"
        if self._has(img, "hud", thr)[0] is not None:
            return "zone"
        if self._has(img, "done", thr)[0] is not None:
            return "done"
        if self._has(img, "lobby", thr)[0] is not None:
            return "lobby"
        if self._has(img, "bigmap", 0.55)[0] is not None:
            return "room"
        return "unknown"

    # ---- bản đồ ----
    def _load_map(self):
        """Toạ độ 14 ô dựng sẵn từ video (WORLD_BUILTIN). Không đọc/ghi file: không bao giờ lệch do lần quét cũ."""
        self.world = {k: (float(v[0]), float(v[1])) for k, v in WORLD_BUILTIN.items() if k in PLOT_LEVEL}

    def visible_plots(self, img, only=None):
        """Các ô đang thấy: {slug: (cx, cy, điểm)}. `only` = chỉ dò những ô dự đoán nằm trong màn hình (nhanh hơn ~3 lần)."""
        out = {}
        reg = (0, 100, REF_W, 1100)
        for s, _n, _l in PLOTS:
            if only is not None and s not in only:
                continue
            r = self._has(img, "plot:" + s, max(self.c["thr"], PLOT_THR.get(s, 0.0)), region=reg)
            if r[0] is not None:
                out[s] = (r[0], r[1], r[2])
        return self._drop_outliers(out)

    def _drop_outliers(self, vis):
        """Bỏ nhận diện nhầm: các ô thật phải cho cùng 1 độ lệch (màn hình - toạ độ thế giới)."""
        vis = dict(vis)
        ks = [s for s in vis if s in self.world]
        n0 = len(ks)
        while len(ks) >= 2:
            ests = {s: (vis[s][0] - self.world[s][0], vis[s][1] - self.world[s][1]) for s in ks}
            mx = float(np.median([e[0] for e in ests.values()]))
            my = float(np.median([e[1] for e in ests.values()]))
            dev = {s: max(abs(e[0] - mx), abs(e[1] - my)) for s, e in ests.items()}
            worst = max(dev, key=dev.get)
            if dev[worst] <= 12:
                break
            if len(ks) == 2:
                worst = min(ks, key=lambda s: vis[s][2])
            del vis[worst]
            ks.remove(worst)
        if n0 >= 3 and len(ks) <= n0 // 2:          # đa số ô không khớp toạ độ dựng sẵn -> có thể khác độ phân giải/zoom
            self._bad_world += 1
            if self._bad_world >= 3 and self.world:
                self.log("WARN", "Toạ độ ô dựng sẵn không khớp màn hình này (khác zoom/độ phân giải?) -> quét lại bản đồ")
                self.world = {}
                self.have_off = False
        elif n0 >= 2:
            self._bad_world = 0
        return vis

    def _predicted(self, margin=60):
        """Các ô mà toạ độ thế giới + độ lệch hiện tại dự đoán là nằm trong màn hình."""
        out = []
        for s, (wx, wy) in self.world.items():
            x, y = wx + self.off[0], wy + self.off[1]
            if -margin < x < REF_W + margin and 100 - margin < y < 1250 + margin:
                out.append(s)
        return out

    def _update_from_map(self, img, vis):
        my = self.my
        for s, (cx, cy, _sc) in vis.items():
            if self.have_off and s not in self.world:        # ô mới (chỉ khi quét dự phòng); toạ độ dựng sẵn không bị ghi đè
                self.world[s] = (cx - self.off[0], cy - self.off[1])
            k = self.known.setdefault(s, {})
            owner = ring_owner(img, int(cx), int(cy))
            k["ring"] = owner
            k["ours_ring"] = bool(my) and owner == my
            if my:                                   # chưa biết phe thì chưa biết ai là ta/địch
                hm = helmets_near(img, int(cx), int(cy))
                k["allies"] = hm.get(my, 0)
                k["enemies"] = sum(v for kk, v in hm.items() if kk != my)
                k["seen_t"] = self._now()
            if not k["ours_ring"] and k.get("owner") == "ours" and k.get("done_at") is None:
                k["owner"] = None

    def _localize(self, img, vis):
        """Thấy >= 1 ô đã biết toạ độ thế giới -> suy ra độ lệch hiện tại (chính xác ~1px, không cộng dồn)."""
        ests = [(cx - self.world[s][0], cy - self.world[s][1]) for s, (cx, cy, _sc) in vis.items() if s in self.world]
        if ests:
            self.off = [float(np.median([e[0] for e in ests])), float(np.median([e[1] for e in ests]))]
            self.have_off = True
            return True
        return False

    def _move_view(self, dx, dy, prev):
        """Kéo nội dung (dx,dy), chờ `settle_s`, chụp lại, ĐỊNH VỊ LẠI bằng ô nhìn thấy; cập nhật hệ số vuốt và `swipe_s`.
        Trả (ảnh mới, dịch thật dx, dy)."""
        c = self.c
        t0 = self._now()
        had, old = self.have_off, list(self.off)
        self._swipe_view(dx, dy)
        self._sleep(c["settle_s"])
        img = self._grab()
        if img is None:
            return None, 0.0, 0.0
        if had:
            self.off = [old[0] + dx, old[1] + dy]                   # dự đoán -> chỉ dò các ô dự kiến nằm trong màn
            vis = self.visible_plots(img, only=self._predicted()) or self.visible_plots(img)
        else:
            vis = self.visible_plots(img)
        located = self._localize(img, vis)
        if located and had:
            rx, ry = self.off[0] - old[0], self.off[1] - old[1]
            if not c["test"]:
                r = []
                for want, got, i in ((dx, rx, 0), (dy, ry, 1)):
                    if abs(want) >= 150 and 0.3 < got / want < 2.0:                 # học hệ số vuốt (làm mượt)
                        self.gain[i] = min(1.4, max(0.6, self.gain[i] * (1 + 0.6 * (got / want - 1))))
        else:                                        # không thấy ô nào để định vị: suy từ lệnh vuốt; chỉ tin đo pha khi rất khớp lệnh
            rx, ry = dx, dy
            if prev is not None and not c["test"]:
                mx, my, resp = measure_shift(prev, img)
                if resp >= 0.2 and abs(mx - dx) <= 0.35 * abs(dx) + 40 and abs(my - dy) <= 0.35 * abs(dy) + 40:
                    rx, ry = mx, my
            self.off = [old[0] + rx, old[1] + ry]
        if not c["test"] and abs(dx) + abs(dy) > 100:
            c["swipe_s"] = round(0.7 * c["swipe_s"] + 0.3 * max(0.3, self._now() - t0), 2)
        return img, rx, ry

    def _find_view(self, img):
        """Không thấy ô nào để định vị: kéo thăm dò tới khi thấy ít nhất 1 ô."""
        for dx, dy in ((-500, 0), (1000, 0), (-500, 420), (0, -840), (900, 0), (-1800, 0)):
            img2, _a, _b = self._move_view(dx, dy, img)
            if img2 is None:
                return img
            img = img2
            if self._localize(img, self.visible_plots(img)):
                break
        return img

    def scan_map(self, img):
        """Quét toàn bản đồ lần đầu: về góc trên-trái rồi quét từng hàng; ghi toạ độ thế giới của mọi ô tìm thấy."""
        self.log("INFO", "🗺 Quét bản đồ lần đầu (kéo tìm đủ 14 ô)...")
        self.have_off = False
        self.world = {}
        for _ in range(14):                      # về góc trái-trên (nội dung trôi sang phải/xuống)
            img2, rx, ry = self._move_view(450, 600, img)
            if img2 is None:
                return img
            tiny = abs(rx) < 90 and abs(ry) < 120
            img = img2
            if tiny and not self.c["test"]:
                break
        self.off = [0.0, 0.0]
        self.have_off = True
        direction = -1
        for row in range(8):
            vis = self.visible_plots(img)
            self._update_from_map(img, vis)
            for _ in range(10):
                if self.should_stop():
                    return img
                img2, rx, ry = self._move_view(direction * 420, 0, img)
                if img2 is None:
                    return img
                img = img2
                self._update_from_map(img, self.visible_plots(img))
                if abs(rx) < 100 and not self.c["test"]:
                    break
            direction = -direction
            if len(self.world) >= len(PLOTS):
                break
            img2, rx, ry = self._move_view(0, -520, img)
            if img2 is None:
                return img
            img = img2
            if abs(ry) < 120 and not self.c["test"]:
                break
        self.log("INFO", f"🗺 Đã biết toạ độ {len(self.world)}/{len(PLOTS)} ô: " + ", ".join(sorted(self.world)))
        return img

    def _tap_point(self, slug, cx, cy):
        dy = self.c["tap_dy"] if self.c.get("tap_dy") is not None else TAP_DY.get(slug, TAP_DY_DEFAULT)
        ox, oy = TAP_RETRY[self._tries.get(slug, 0) % len(TAP_RETRY)]
        return cx + ox, cy + dy + oy

    def goto_and_tap(self, slug, img):
        """Đưa ô `slug` vào tầm bấm (thường 0-1 lần vuốt; đã thấy sẵn thì bấm luôn) rồi bấm. True nếu đã bấm."""
        self._lost_n = 0
        self._gate = None
        for _ in range(7):
            if self.should_stop():
                return False
            vis = self.visible_plots(img, only=self._predicted()) if self.have_off else {}
            if not vis:
                vis = self.visible_plots(img)
            self._localize(img, vis)
            self._update_from_map(img, vis)
            self._img_now = img
            if slug in vis:
                kk = self.known.get(slug, {})
                if self.my and (kk.get("enemies", 0) or 0) > (kk.get("allies", 0) or 0):     # số mũ VỪA đọc: địch đông hơn ta
                    self.log("WARN", f"⛔ Bỏ {PLOT_NAME[slug]}: địch {kk.get('enemies')} > ta {kk.get('allies')} (vừa đọc mũ) -> chọn ô khác")
                    kk["bad_until"] = self._now() + self.c["bad_s"]
                    self._gate = slug
                    return False
                tx, ty = self._tap_point(slug, vis[slug][0], vis[slug][1])
                if SAFE_X[0] < tx < SAFE_X[1] and SAFE_Y[0] < ty < SAFE_Y[1]:
                    self.tap_t = self._now()
                    self._last_label = (vis[slug][0], vis[slug][1])
                    self._tap(tx, ty, f"chọn {PLOT_NAME[slug]}")
                    return True
            if self.have_off and slug in self.world:
                tx, ty = self._tap_point(slug, self.world[slug][0] + self.off[0], self.world[slug][1] + self.off[1])
                # kéo VỪA ĐỦ: đưa điểm bấm tới mép trong vùng an toàn thay vì về giữa -> ít lần vuốt hơn. Đệm = 40px + 15% quãng kéo
                # (hệ số vuốt chưa học thì vuốt xa dễ hụt ~10%; học xong thì sai số ~0)
                dx0 = min(max(tx, SAFE_X[0] + 40), SAFE_X[1] - 40) - tx
                dy0 = min(max(ty, SAFE_Y[0] + 40), SAFE_Y[1] - 40) - ty
                mx = 40 + min(190, 0.15 * abs(dx0))
                my = 40 + min(190, 0.15 * abs(dy0))
                dx = min(max(tx, SAFE_X[0] + mx), SAFE_X[1] - mx) - tx
                dy = min(max(ty, SAFE_Y[0] + my), SAFE_Y[1] - my) - ty
                if abs(dx) < 1 and abs(dy) < 1:      # tưởng đã trong tầm bấm mà KHÔNG thấy nhãn -> dự đoán lệch: nhích theo hướng vừa đi
                    self._lost_n += 1
                    k = 250 if self._lost_n % 2 else -500
                    dx, dy = k * np.sign(self._last_move[0]), k * np.sign(self._last_move[1])
                    if dx == 0 and dy == 0:
                        dx = k
            else:
                dx, dy = -400, 0
            self._last_move = (dx, dy)
            img2, _rx, _ry = self._move_view(dx, dy, img)
            if img2 is None:
                return False
            img = img2
        return False

    def _await_zone(self, timeout):
        """Sau khi bấm 'Đến' (avatar bay tới ô, ~1s): chờ tới khi thấy HUD hoặc hết giờ -> (trạng thái, ảnh)."""
        t_end = self._now() + timeout
        st, img = "map", None
        while self._now() < t_end and not self.should_stop():
            self._sleep(0.2)
            img = self._grab()
            if img is None:
                continue
            st = self.detect(img)
            if st in ("zone", "dead", "room", "lobby", "done"):
                break
        return st, img

    def _press_den(self, timeout=1.2):
        """Sau lần bấm 1: chờ nút 'Đến' hiện trên nhãn ô vừa bấm rồi BẤM nút. True nếu đã bấm (hoặc đã vào hẳn)."""
        lx, ly = self._last_label
        t_end = self._now() + timeout
        while self._now() < t_end and not self.should_stop():
            self._sleep(0.15)
            img = self._grab()
            if img is None:
                continue
            btn = find_den_button(img, lx, ly)
            if btn:
                self._tap(btn[0], btn[1], "nút Đến")
                return True
            if self.detect(img) in ("zone", "dead", "room", "lobby", "done"):
                return True
        return False

    def _enter_plot(self, slug, img):
        """Bấm ô -> nút 'Đến' hiện -> bấm 'Đến' -> chờ thấy HUD. True nếu đã vào ô."""
        if not self.goto_and_tap(slug, img):
            return False
        if self.c["test"]:
            return False
        if not self._press_den():
            self._tries[slug] = self._tries.get(slug, 0) + 1
            self.log("WARN", f"Bấm {PLOT_NAME[slug]} không hiện nút 'Đến' (bấm hụt) -> lần sau thử lệch điểm bấm (lần {self._tries[slug]})")
            return False
        st, _img = self._await_zone(self.c["enter_s"] + 1.5)
        if st == "zone":
            self.cur, self.target = slug, None
            self._tries[slug] = 0
            return True
        if st == "map":
            self._tries[slug] = self._tries.get(slug, 0) + 1
            self.log("WARN", f"Đã bấm 'Đến' nhưng chưa vào {PLOT_NAME[slug]} -> thử lại (lần {self._tries[slug]})")
        return False

    def travel(self, a, b):
        """Ước lượng giây đi từ ô a (None = đang ở bản đồ, nhìn quanh ô `view_plot`) sang ô b."""
        c = self.c
        t = c["enter_s"] + (c["open_map_s"] if a is not None else 0.0)
        start = a if a is not None else self.view_plot
        sw = c["swipe_s"]
        if start == b:
            return t
        if start in self.world and b in self.world:
            # bản đồ mở với nhãn ô `start` ở (360,775): ô b bấm được nếu lệch ngang <= ~270px, dọc trong [-470,+300]px
            dxs = self.world[b][0] - self.world[start][0]
            dys = self.world[b][1] - self.world[start][1]
            nx = max(0.0, abs(dxs) - 270.0) / 560.0
            ny = max(0.0, -dys - 470.0, dys - 300.0) / 780.0
            t += int(np.ceil(max(nx, ny) - 1e-9)) * sw
        else:
            t += 2 * sw
        return t

    # ---- vòng chính ----
    def _decide(self, now):
        seq, score, first = plan(now, self.cur, self.known, self.travel, self.c)
        return seq, score, first

    def _note_zone(self, hud, now):
        if self.cur is None or self.my is None:
            return
        k = self.known.setdefault(self.cur, {})
        t = hud["timer"]
        mine = hud["owner"] == self.my
        circ = hud["circles"]
        if circ is not None:                         # None = lần này không đọc vòng tròn (đọc 1 lần/giây cho nhẹ)
            k["allies"] = circ.get(self.my) or k.get("allies", 0)
            k["enemies"] = sum((v or 1) for kk, v in circ.items() if kk != self.my)
            k["seen_t"] = now
        if t is not None and mine:
            k["owner"], k["done_at"] = "ours", now + t
        elif t is not None:
            k["owner"], k["done_at"] = "enemy", None
        else:
            if k.get("done_at") is not None and k["done_at"] - now < 2.5:
                self.stats["captures"] += 1
                k["owner"], k["ours_ring"] = "ours", True
                self.log("INFO", f"✅ Xong ô {PLOT_NAME[self.cur]} (+{LEVEL_PTS[PLOT_LEVEL[self.cur]]}đ dự kiến)")
            k["done_at"] = None

    def run(self):
        c = self.c
        t0 = self._now()
        unknown = 0
        last_state = None
        entered = None
        while not self.should_stop():
            now = self._now()
            if c["max_seconds"] and now - t0 > c["max_seconds"]:
                self.log("INFO", "⏱ Hết thời gian tối đa -> dừng")
                break
            img = self._grab()
            if img is None:
                self._sleep(1.0)
                continue
            st = self.detect(img)
            if st != last_state:
                self.log("INFO", f"trạng thái: {st}")
                last_state = st
            if st != "room":
                self._room_streak = (None, None, 0)
            if st not in ("map", "unknown", "zone"):       # rời hẳn bản đồ (chết/phòng phe...) thì đồng hồ bản đồ chạy lại từ đầu
                self._map_since = None
            if st != "unknown":
                unknown = 0
            if st == "done":
                self.log("INFO", "🏁 Sảnh báo 'Chờ nhận thưởng' = hết trận -> dừng")
                break
            if st == "dead":
                self.stats["deaths"] += 1
                if self.cur is not None:                 # chết ở đâu thì tránh chỗ đó
                    self.known.setdefault(self.cur, {}).update(bad_until=now + 2 * c["bad_s"], enemies=9)
                    self.log("WARN", f"☠ Chết ở {PLOT_NAME[self.cur]} -> tránh ô này {2 * c['bad_s']:.0f}s")
                self.cur = None
                x, y, _s = self._has(img, "respawn", 0.60)
                self._tap(x if x else 360, y if y else 1115, "Đến hồi sinh")
                self._sleep(1.5)
            elif st == "lobby":
                x, y, _s = self._has(img, "lobby", 0.60)
                self._tap(x, y, "vào Đại Chiến Giành Đơn")
                self._sleep(2.5)
            elif st == "room":
                self.cur = None
                self.view_plot = None
                self._learn_room(img)                    # phòng phe: thanh tên phe cho biết phe của mình
                bx, by = c["bigmap_xy"]
                x, y, _s = self._has(img, "bigmap", 0.60)
                self._tap(x or bx, y or by, "Bản đồ lớn")  # sau khi chết phải bấm lặp ~9s mới mở được
                self._sleep(0.8)
            elif st == "map":
                if self.cur is not None:
                    self.view_plot, self.cur = self.cur, None
                if self._map_since is None:
                    self._map_since, self._n_swipe, self._n_tap = now, 0, 0
                img = self._on_map(img, now)
            elif st == "zone":
                if c["test"]:
                    hud = read_hud(img, c["capture_s"])
                    self.log("INFO", f"[TEST] HUD {hud}")
                    tc = read_my_team(img)
                    self.log("INFO", "[TEST] phe đọc từ chữ tên: " + (f"{TEAM_NAME[tc]} ({TEAM_VN[tc]})" if tc else
                                                                  "chưa chắc (chụp lúc camera đã đứng yên, tên không bị che)"))
                    self._sleep(1.0)
                    break
                if self.enter_t is None or entered != self.cur:
                    entered = self.cur
                    self.enter_t = now
                    self._bad_bar = 0
                    if self._map_since is not None:
                        self.log("INFO", f"⏱ Mở bản đồ -> vào ô: {now - self._map_since:.1f}s ({self._n_swipe} vuốt, {self._n_tap} bấm)")
                        self._map_since = None
                    if self.tap_t is not None:       # đo thời gian vào ô thật, cập nhật enter_s (trung bình trượt)
                        dt = max(0.5, min(10.0, now - self.tap_t))
                        c["enter_s"] = round(0.7 * c["enter_s"] + 0.3 * dt, 2)
                        self.tap_t = None
                want = now - self._circ_t >= 1.0
                hud = read_hud(img, c["capture_s"], count_circles=want)
                if want:
                    self._circ_t = now
                self._learn_team(img)
                if self.my is None:                  # chưa biết phe: đứng yên đọc tên, CHƯA lập kế hoạch
                    self._unk_t = self._unk_t or now
                    if now - self._unk_t > 20 and not self._unk_warned:
                        self._unk_warned = True
                        self.log("WARN", "Đã 20s trong ô mà chưa đọc được màu tên mình -> đặt tay my_color (blue/yellow/red/orange)")
                else:
                    self._unk_t = None
                    self._note_zone(hud, now)
                    self._zone_decide(img, hud, now)
            else:
                unknown += 1
                if c["test"]:
                    self.log("INFO", "[TEST] màn hình lạ, dừng")
                    break
                if unknown >= c["unknown_max"]:
                    self.log("WARN", "Màn hình lạ quá lâu -> dừng (kiểm ảnh mẫu delivery_*.png)")
                    break
                if unknown % 8 == 0:
                    self.adb.run_cmd(["shell", "input", "keyevent", "4"])
            if c["test"] and st in ("map", "dead", "lobby", "room"):
                break
            self._sleep(c["poll_s"])
        self.log("INFO", f"Kết thúc. {self.stats}")
        return True

    def _leave_zone(self, why, bad_s=None):
        c = self.c
        if self.cur is not None:
            self.known.setdefault(self.cur, {})["bad_until"] = self._now() + (c["bad_s"] if bad_s is None else bad_s)
        self.log("INFO", f"🚪 Rời {PLOT_NAME.get(self.cur)}: {why}")
        self.stats["switches"] += 1
        bx, by = c["bigmap_xy"]
        self._tap(bx, by, "mở Bản đồ lớn")
        self._sleep(c["open_map_s"])

    def _zone_decide(self, img, hud, now):
        c = self.c
        if self.cur is None:
            return
        stay_for = now - (self.enter_t if self.enter_t is not None else now)
        # --- AN TOÀN: vào mà thanh "Số người" không phải màu phe ta (hoặc địch đông hơn ta) -> RỜI NGAY ---
        if self.my and stay_for >= c["bar_grace_s"]:
            circ = hud.get("circles")
            outnum = False
            if circ is not None:
                ours = circ.get(self.my) or 1                         # luôn có ít nhất bản thân
                theirs = sum((v or 1) for kk, v in circ.items() if kk != self.my)
                outnum = theirs > ours
            if hud["owner"] != self.my or outnum:
                self._bad_bar += 1
            else:
                self._bad_bar = 0
            if self._bad_bar >= 2:
                why = (f"thanh không phải màu phe ta (đang là {TEAM_VN.get(hud['owner'], hud['owner'])})" if hud["owner"] != self.my
                       else "địch đông hơn ta")
                self._bad_bar = 0
                self._leave_zone(why)
                return
        seq, rate, first = self._decide(now)
        stay = first.get(self.cur, 0.0)
        best_first = seq[0] if seq else self.cur
        if c.get("debug"):
            self.log("DEBUG", f"HUD {hud} | chuỗi {seq} {rate:.1f}đ/s | ở lại {stay:.1f}đ/s")
        if best_first != self.cur and stay_for >= c["min_stay_s"] and rate >= stay * c["switch_ratio"] + 0.5:
            self.log("INFO", f"➡ Rời {PLOT_NAME[self.cur]} (ở lại {stay:.1f}đ/s) để đi {PLOT_NAME.get(best_first)} "
                             f"(chuỗi {[PLOT_NAME[x] for x in seq]} {rate:.1f}đ/s)")
            self.stats["switches"] += 1
            self.target = best_first
            bx, by = c["bigmap_xy"]
            self._tap(bx, by, "mở Bản đồ lớn")
            self._sleep(c["open_map_s"])

    target: Optional[str] = None

    def _on_map(self, img, now):
        c = self.c
        vis = self.visible_plots(img)
        if c["test"]:
            self._update_from_map(img, vis)
            for s, (cx, cy, sc) in vis.items():
                self.log("INFO", f"[TEST] thấy {PLOT_NAME[s]} tại ({int(cx)},{int(cy)}) {sc:.2f} | vòng={self.known[s].get('ring')} "
                                 f"| ta {self.known[s].get('allies')} / địch {self.known[s].get('enemies')}")
            return img
        if not self.world:                           # toạ độ dựng sẵn bị loại (không khớp) -> quét dự phòng
            img = self.scan_map(img)
            vis = self.visible_plots(img)
        elif not self._localize(img, vis):           # không thấy ô nào -> kéo thăm dò
            img = self._find_view(img)
            vis = self.visible_plots(img)
            self._localize(img, vis)
        self._update_from_map(img, vis)
        if self.my is None:                          # BƯỚC 1: phải biết mình phe nào -> vào thử 1 ô để đọc màu tên
            slug = self._probe_slug(vis)
            if slug:
                self.log("INFO", f"🔎 Chưa biết phe -> vào thử {PLOT_NAME[slug]} để đọc màu tên nhân vật")
                self._enter_plot(slug, img)
                return img
        now = self._now()
        over = self._map_since is not None and now - self._map_since > c["map_budget_s"]
        for attempt in range(4):                     # bị chặn (địch đông) thì chọn ô khác NGAY, không chờ vòng sau
            now = self._now()
            seq, rate, first = self._decide(now)
            slug = seq[0] if seq else PLOTS[-2][0]
            if over:                                 # ở bản đồ quá lâu: ép vào ô an toàn gần nhất đang thấy / dự đoán thấy
                near = sorted(((self.travel(None, sl), sl) for sl, _n, _l in PLOTS
                               if (self.known.get(sl, {}).get("enemies", 0) or 0) <= (self.known.get(sl, {}).get("allies", 0) or 0)
                               and self.known.get(sl, {}).get("bad_until", 0) <= now))
                if near:
                    slug = near[0][1]
                self.log("WARN", f"⏱ Ở bản đồ {now - self._map_since:.0f}s (> {c['map_budget_s']:.0f}s) -> ép vào ô gần nhất an toàn: {PLOT_NAME[slug]}")
            self.log("INFO", f"🎯 Chọn {PLOT_NAME[slug]} (chuỗi {[PLOT_NAME[x] for x in seq]} ~{rate:.1f}đ/s)")
            self._enter_plot(slug, img)
            if self.cur is not None or self._gate is None:
                break
            img = self._img_now if self._img_now is not None else img       # ảnh mới nhất sau khi đã kéo


def run_auto_delivery_step(adb, step: dict, should_stop=None, log=None) -> bool:
    """Chạy 1 bước `auto_delivery` (field xem mục 4 ở docstring đầu file)."""
    log = log or (lambda level, msg: print(f"[{level}] {msg}"))
    tpl_dir = step.get("tpl_dir") or _tpl_dir_default()
    cfg = {k: step.get(k) for k in ("test", "max_seconds", "my_color", "capture_s", "enter_s", "open_map_s", "swipe_s",
                                    "arrive_margin_s", "seq_len", "horizon_s", "switch_ratio", "min_stay_s", "hold_factor",
                                    "tap_dy", "bigmap_xy", "thr", "poll_s", "unknown_max", "swipe_ms", "settle_s", "info_ttl_s", "bad_s", "bar_grace_s", "map_budget_s", "debug")}
    bot = DeliveryBot(adb, load_templates(tpl_dir), log=log, should_stop=should_stop, **cfg)
    return bot.run()


# ----------------------------------------------------------------------------
# Công cụ dòng lệnh
# ----------------------------------------------------------------------------
def _cli_add(kind, img_path, x1, y1, x2, y2):
    valid = set(KINDS) | {"plot:" + s for s, _n, _l in PLOTS}
    if kind not in valid:
        sys.exit("loại phải là một trong: " + ", ".join(sorted(valid)))
    img = _imread(img_path)
    if img is None:
        sys.exit("không đọc được ảnh")
    x1, x2 = sorted((int(x1), int(x2)))
    y1, y2 = sorted((int(y1), int(y2)))
    crop = img[y1:y2, x1:x2]
    d = _tpl_dir_default()
    base = "delivery_plot_" + kind[5:] if kind.startswith("plot:") else "delivery_" + kind
    n = 1
    while os.path.exists(os.path.join(d, f"{base}_{n}.png")):
        n += 1
    p = os.path.join(d, f"{base}_{n}.png")
    _imwrite(p, crop)
    print("đã lưu", p, crop.shape[1], "x", crop.shape[0])


def _cli_check(img_path):
    img = _imread(img_path)
    if img is None:
        sys.exit("không đọc được ảnh")
    if img.shape[1] != REF_W:
        img = cv2.resize(img, (REF_W, REF_H))
    tpls = load_templates(_tpl_dir_default())

    class _A:
        pass
    bot = DeliveryBot(_A(), tpls, log=lambda lv, m: print(f"[{lv}] {m}"), test=True)
    st = bot.detect(img)
    print("trạng thái:", st)
    if st == "zone" or st == "dead":
        print("HUD:", read_hud(img))
    tc = read_my_team(img) if (st == "zone" or looks_like_zone(img)) else None
    rc = read_room_team(img) if st == "room" else None
    if rc:
        print("phe của mình (đọc thanh tên phe ở phòng phe):", f"{TEAM_NAME[rc]} ({TEAM_VN[rc]})")
    print("phe của mình (đọc chữ tên):", f"{TEAM_NAME[tc]} ({TEAM_VN[tc]})" if tc else "không đọc được ở màn này (cần màn TRONG ô)")
    vis = bot.visible_plots(img)
    for s, (cx, cy, sc) in vis.items():
        hm = helmets_near(img, int(cx), int(cy))
        print(f"  ô {PLOT_NAME[s]:34s} ({int(cx)},{int(cy)}) {sc:.2f} vòng={ring_owner(img, int(cx), int(cy))} mũ={hm}")


def _cli_team(path):
    """Đọc phe từ 1 ảnh, hoặc quét cả video (mỗi 0,5s) rồi bỏ phiếu."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".mp4", ".avi", ".mkv", ".mov", ".webm"):
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            sys.exit("không mở được video")
        step = max(1, int((cap.get(cv2.CAP_PROP_FPS) or 30) / 2))
        votes: Dict[Optional[str], int] = {}
        i = zone = 0
        while True:
            ok, img = cap.read()
            if not ok:
                break
            if i % step == 0:
                if img.shape[1] != REF_W:
                    img = cv2.resize(img, (REF_W, REF_H))
                if looks_like_zone(img):
                    zone += 1
                    col = read_my_team(img)
                    votes[col] = votes.get(col, 0) + 1
            i += 1
        cap.release()
        print(f"khung TRONG ô đã đọc: {zone}")
        for col, n in sorted(votes.items(), key=lambda kv: -kv[1]):
            print(f"  {TEAM_NAME[col] + ' (' + TEAM_VN[col] + ')' if col else 'không chắc':34s} {n}")
        sure = {k: v for k, v in votes.items() if k}
        if sure:
            top = max(sure, key=sure.get)
            if sure[top] >= 0.8 * sum(sure.values()):
                print(f"=> PHE CỦA MÌNH: {TEAM_NAME[top]} ({TEAM_VN[top]})  -> my_color = \"{top}\"")
                return
        print("=> chưa kết luận được (không đủ khung trong ô, hoặc kết quả lẫn lộn)")
        return
    img = _imread(path)
    if img is None:
        sys.exit("không đọc được ảnh")
    if img.shape[1] != REF_W:
        img = cv2.resize(img, (REF_W, REF_H))
    col = read_my_team(img)
    print("đang ở trong ô:", looks_like_zone(img))
    print("phe của mình:", f"{TEAM_NAME[col]} ({TEAM_VN[col]}) -> my_color = \"{col}\"" if col else "không đọc được")


def _selftest():
    # 1) phaseCorrelate đúng chiều (chỉ còn dùng làm dự phòng)
    base = np.random.RandomState(1).randint(0, 255, (1280, 720, 3), np.uint8)
    base = cv2.GaussianBlur(base, (0, 0), 3)
    M = np.float32([[1, 0, 40], [0, 1, -30]])
    moved = cv2.warpAffine(base, M, (720, 1280), borderMode=cv2.BORDER_REFLECT)
    dx, dy, resp = measure_shift(base, moved)
    assert abs(dx - 40) < 4 and abs(dy + 30) < 4, (dx, dy)
    # 2) lập kế hoạch theo TỐC ĐỘ trong cửa sổ ngắn. 3 ô đang đếm còn 20s / 10s / 4s, mỗi lần đi 2s
    cfg = dict(arrive_margin_s=1.0, capture_s=20.0, horizon_s=30.0, seq_len=3, hold_factor=0.05)
    def mk(timers):
        kn = {s: {"done_at": 1000.0 + t, "allies": 3} for s, t in timers.items()}
        for sl, _n, _l in PLOTS:        # các ô khác đã là của ta -> không đáng đi
            kn.setdefault(sl, {"ours_ring": True})
        return kn
    known = mk({"lv3_toa_nha_ifc": 20, "lv2_cang_so": 10, "lv1_cho_cu": 4})
    seq, rate, first = plan(1000.0, None, known, lambda a, b: 2.0, cfg)
    assert seq[:3] == ["lv1_cho_cu", "lv2_cang_so", "lv3_toa_nha_ifc"], seq
    seq, rate, first = plan(1000.0, "lv1_cho_cu", known, lambda a, b: 2.0, cfg)    # ô sắp xong mà đang đứng đó -> ở lại
    assert seq[0] == "lv1_cho_cu"
    # 2b) ví dụ của người dùng: 3 ô còn 5s / 5s / 15s (cùng cấp Lv1), đang ở ô 5s thứ nhất, đi mất 2,5s
    kn = mk({"lv1_cho_cu": 5, "lv1_khu_dan_cu": 5, "lv1_pho_di_bo": 15})
    seq, rate, first = plan(1000.0, "lv1_cho_cu", kn, lambda a, b: 2.5, cfg)
    assert seq[0] == "lv1_cho_cu", seq                      # đang ở ô 5s: ở lại xong ô này (60đ/s) thay vì rời đi giữa chừng
    # ... xong ô đầu (+300, đã của ta) và ô 5s kia cũng đã xong -> LẬP LẠI chu trình: nhảy ngay sang ô 15s (lúc này còn 10s)
    kn2 = mk({"lv1_pho_di_bo": 10})
    kn2["lv1_cho_cu"] = {"ours_ring": True}
    seq, rate, first = plan(1005.0, "lv1_cho_cu", kn2, lambda a, b: 2.5, cfg)
    assert seq and seq[0] == "lv1_pho_di_bo", seq
    # ô xa hơn thời gian còn lại bị loại
    known2 = mk({"lv1_cho_cu": 3, "lv3_toa_nha_ifc": 40})
    seq, rate, first = plan(1000.0, "lv3_toa_nha_ifc", known2, lambda a, b: 3.5, cfg)
    assert "lv1_cho_cu" not in seq, seq
    # 2c) AN TOÀN: ô có địch > ta bị loại dù điểm cao; ô vừa bị loại (bad_until) cũng vậy; số quân cũ quá hạn thì coi như chưa biết
    kn = {s_: {"ours_ring": True} for s_, _n, _l in PLOTS}
    kn["lv3_toa_nha_ifc"] = {"allies": 0, "enemies": 3, "seen_t": 1000.0}           # Lv3 nhưng địch đông
    kn["lv2_cang_so"] = {"allies": 0, "enemies": 0, "seen_t": 1000.0, "bad_until": 1030.0}   # vừa rời ở đó
    kn["lv1_cho_cu"] = {"allies": 2, "enemies": 1, "seen_t": 1000.0}                 # Lv1 nhưng ta đông hơn
    seq, rate, first = plan(1001.0, None, kn, lambda a, b: 2.0, cfg)
    assert seq[0] == "lv1_cho_cu", seq
    kn["lv3_toa_nha_ifc"]["seen_t"] = 900.0                                          # số quân đã cũ (>45s) -> coi như chưa biết
    seq, rate, first = plan(1001.0, None, kn, lambda a, b: 2.0, dict(cfg, info_ttl_s=45.0))
    assert seq[0] == "lv3_toa_nha_ifc", seq
    # 2d) vào ô mà thanh không phải màu ta -> rời ngay (sau ~1,2s, 2 lần đọc liên tiếp); thanh đúng màu -> ở lại
    class _R:
        def __init__(self): self.taps = []
        def tap_px(self, x, y): self.taps.append((x, y))
        def swipe_px(self, *a): pass
    r = _R()
    bz = DeliveryBot(r, {}, log=lambda lv, m: None, test=False, my_color="yellow")
    bz._sleep = lambda x: None
    bz.cur, bz.enter_t = "lv1_cho_cu", 100.0
    hud_bad = {"timer": None, "owner": "red", "frac": 0.99, "circles": {"yellow": 1}}
    hud_ok = {"timer": 8.0, "owner": "yellow", "frac": 0.6, "circles": {"yellow": 2}}
    bz._zone_decide(None, hud_bad, 100.6)      # chưa tới 1,2s -> chưa phán
    bz._zone_decide(None, hud_ok, 101.5)
    assert not r.taps
    bz._zone_decide(None, hud_bad, 101.7)
    assert not r.taps                           # mới 1 lần đọc xấu
    bz._zone_decide(None, hud_bad, 102.1)
    assert r.taps and bz.known["lv1_cho_cu"]["bad_until"] > 102.1, (r.taps, bz.known)
    # 3) phân loại màu (số đo từ video thật)
    assert [hue_name(h) for h in (19, 12, 175, 100)] == ["yellow", "orange", "red", "blue"]
    assert hue_name(22, "helmet") == "yellow" and hue_name(14, "helmet") == "orange"
    assert [hue_name(h, "ring") for h in (4, 17, 26, 90)] == ["red", "orange", "yellow", "blue"]
    assert [hue_name(h, "band") for h in (4, 15, 20, 100)] == ["red", "orange", "yellow", "blue"]
    assert hue_name(median_hue(np.array([178, 179, 0, 1, 177]))) == "red"      # hồng vắt qua mốc 0/179
    assert norm_color("pink") == "red" and norm_color("Giao Đồ Ăn Ngon") == "yellow" and norm_color("auto") is None
    # 3b) chữ số: mỗi mẫu học được phải tự nhận ra chính nó
    for d, ss in _DIGIT_SEEDS.items():
        for s in ss:
            f = np.array([int(ch) / 9.0 for ch in s], np.float32)
            best = min((float(np.abs(f - t).mean()), dd) for dd, t in _digit_templates())
            assert best[1] == d, (d, best)
    # 4) nhận diện phe: chốt sau 3 lần giống nhau, rồi KHOÁ (không đổi giữa chừng); ép tay thì không bị đổi
    class _A:
        pass
    quiet = lambda lv, m: None
    b = DeliveryBot(_A(), {}, log=quiet, test=False)
    assert b.my is None
    for col in ("yellow", None, "yellow", "red", "yellow", "yellow", "yellow"):
        b._learn_color(col)
    assert b.my == "yellow" and b.my_confirmed
    for _ in range(30):
        b._learn_color("red")
    assert b.my == "yellow"                         # đã khoá cho lần chạy này
    clk = {"t": 0.0}
    b3 = DeliveryBot(_A(), {}, log=quiet, test=False)
    b3._now = lambda: clk["t"]
    global read_room_team
    _orig = read_room_team
    try:
        seqs = ["blue"] * 3 + [None] + ["yellow"] * 8                      # 3 khung chuyển cảnh màu chủ ô (xanh) rồi phòng phe thật (vàng)
        read_room_team = lambda img: seqs.pop(0)
        for _ in range(12):
            b3._learn_room(None)
            clk["t"] += 0.8
            if b3.my is not None:
                break
        assert b3.my == "yellow", b3.my                                     # khung xanh ngắn không được tin
    finally:
        read_room_team = _orig
    b2 = DeliveryBot(_A(), {}, log=quiet, test=False, my_color="pink")
    for _ in range(10):
        b2._learn_color("yellow")
    assert b2.my == "red" and b2.my_confirmed
    # 5) bản đồ dựng sẵn đủ 14 ô; travel: ô kề nhau 0 lần vuốt, ô xa nhiều lần vuốt
    assert len(b.world) == len(PLOTS)
    b.view_plot = "lv1_khu_dan_cu"
    near, far = b.travel(None, "lv1_pho_di_bo"), b.travel(None, "lv1_cho_cu")
    assert near < far and abs(near - b.c["enter_s"]) < 1e-6, (near, far)
    print("selftest OK")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
    elif a[0] == "--selftest":
        _selftest()
    elif a[0] == "--add" and len(a) == 7:
        _cli_add(*a[1:])
    elif a[0] == "--team" and len(a) == 2:
        _cli_team(a[1])
    elif a[0] == "--check" and len(a) == 2:
        _cli_check(a[1])
    else:
        _cli_check(a[0])

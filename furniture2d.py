# -*- coding: utf-8 -*-
"""
furniture2d.py - رسم الأثاث بشكله الحقيقي في المنظور من فوق (سرير، دولاب، كرسي، طرابيزة، بوتجاز...)
كل قطعة بتترسم مرة واحدة وبتتخزّن (cache) وبتتلف حسب اتجاه وشها.
"""
import math
import pygame
from fp3d import style_of, infer_front

M = 46                                           # هامش حوالين القطعة (للضلف والأدراج المفتوحة)
_CACHE = {}


def sh(c, k):
    return (max(0, min(255, int(c[0] * k))), max(0, min(255, int(c[1] * k))), max(0, min(255, int(c[2] * k))))


def mix(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def rr(sf, col, x, y, w, h, r=3):
    if w > 0 and h > 0:
        pygame.draw.rect(sf, col, (int(x), int(y), int(w), int(h)), 0, border_radius=r)


def bevel(sf, x, y, w, h, col, r=3):
    """سطح بإضاءة من فوق شمال: حرف فاتح وحرف غامق"""
    rr(sf, sh(col, 0.62), x, y, w, h, r)
    rr(sf, col, x + 1, y + 1, w - 2, h - 2, r)
    pygame.draw.line(sf, sh(col, 1.25), (int(x + r), int(y + 1)), (int(x + w - r), int(y + 1)))
    pygame.draw.line(sf, sh(col, 1.18), (int(x + 1), int(y + r)), (int(x + 1), int(y + h - r)))
    pygame.draw.line(sf, sh(col, 0.75), (int(x + r), int(y + h - 2)), (int(x + w - r), int(y + h - 2)))


def grain(sf, x, y, w, h, col, n=None):
    """عروق الخشب"""
    n = n or max(2, int(h // 7))
    for i in range(n):
        yy = y + 4 + i * (h - 8) / max(1, n)
        pygame.draw.line(sf, sh(col, 0.9 if i % 2 else 0.84), (int(x + 3), int(yy)), (int(x + w - 4), int(yy + (i % 3) - 1)))


def knob(sf, x, y, r=2, col=(214, 176, 80)):
    pygame.draw.circle(sf, sh(col, 0.5), (int(x) + 1, int(y) + 1), r)
    pygame.draw.circle(sf, col, (int(x), int(y)), r)
    pygame.draw.circle(sf, (255, 240, 190), (int(x) - 1, int(y) - 1), max(1, r // 2))


def wood(c, k=1.0):
    return sh((min(255, c[0] + 12), min(255, c[1] + 6), c[2]), k)


# --------------------------------------------------------------------- كل نوع
# الإحداثيات: (x, y) أعلى شمال القطعة، w العرض، h العمق. الضهر فوق والوش تحت.

def d_bed(sf, x, y, w, h, c, op):
    fr = wood(c, 0.55)
    bevel(sf, x, y, w, h, fr, 4)                                         # هيكل السرير
    rr(sf, (232, 226, 212), x + 4, y + 7, w - 8, h - 11, 4)               # المرتبة
    bt = y + h * 0.34                                                     # الغطا
    rr(sf, sh(c, 0.7), x + 4, bt, w - 8, y + h - 5 - bt, 4)
    rr(sf, c, x + 5, bt + 1, w - 10, y + h - 7 - bt, 4)
    for i in range(1, 5):                                                 # خطوط الغطا
        xx = x + 5 + (w - 10) * i / 5.0
        pygame.draw.line(sf, sh(c, 0.86), (int(xx), int(bt + 4)), (int(xx), int(y + h - 8)))
    rr(sf, sh(c, 1.25), x + 5, bt, w - 10, 5, 3)                          # ثنية الغطا
    pw = (w - 18) / 2.0
    for i in range(2):                                                    # المخدات
        px = x + 6 + i * (pw + 6)
        rr(sf, (190, 186, 176), px + 1, y + 10, pw, h * 0.26, 6)
        rr(sf, (244, 240, 232), px, y + 8, pw, h * 0.26, 6)
        pygame.draw.line(sf, (214, 208, 198), (int(px + 5), int(y + 8 + h * 0.13)), (int(px + pw - 5), int(y + 8 + h * 0.13)))
    rr(sf, sh(fr, 0.8), x, y, w, 6, 3)                                    # ضهر السرير (الحلق)
    for xx in (x + 2, x + w - 7):
        rr(sf, sh(fr, 1.3), xx, y - 2, 6, 9, 3)


def d_wardrobe(sf, x, y, w, h, c, op):
    b = wood(c, 0.8)
    bevel(sf, x, y, w, h, b, 3)
    grain(sf, x + 2, y + 2, w - 4, h - 12, b)
    rr(sf, sh(b, 1.12), x + 3, y + 3, w - 6, 5, 2)                        # كرنيش
    if op:                                                                # ضلفتين مفتوحين
        ln = w / 2.0 - 2
        ca, sa = math.cos(math.radians(62)), math.sin(math.radians(62))
        for s_ in (1, -1):
            hx = x + 2 if s_ > 0 else x + w - 2
            ex, ey = hx + s_ * ln * ca, y + h + ln * sa
            pygame.draw.polygon(sf, sh(b, 0.85), [(hx, y + h), (ex, ey), (ex - s_ * 3, ey), (hx, y + h - 3)])
            pygame.draw.line(sf, sh(b, 1.3), (int(hx), int(y + h)), (int(ex), int(ey)), 2)
        rr(sf, (20, 16, 14), x + 6, y + h - 5, w - 12, 5, 1)
    else:
        pygame.draw.line(sf, sh(b, 0.45), (int(x + w / 2), int(y + h - 9)), (int(x + w / 2), int(y + h - 1)), 2)
        knob(sf, x + w / 2 - 6, y + h - 5, 2)
        knob(sf, x + w / 2 + 6, y + h - 5, 2)


def d_nightstand(sf, x, y, w, h, c, op):
    b = wood(c, 0.85)
    bevel(sf, x, y, w, h, b, 3)
    grain(sf, x + 1, y + 1, w - 2, h - 2, b, 3)
    pygame.draw.circle(sf, (60, 50, 30), (int(x + w / 2) + 1, int(y + h * 0.42) + 1), int(w * 0.28))
    pygame.draw.circle(sf, (238, 214, 140), (int(x + w / 2), int(y + h * 0.42)), int(w * 0.28))      # أباجورة
    pygame.draw.circle(sf, (255, 240, 190), (int(x + w / 2) - 2, int(y + h * 0.42) - 2), int(w * 0.12))
    if op:
        rr(sf, (24, 18, 16), x + 3, y + h, w - 6, 14, 2)
        rr(sf, wood(c, 1.0), x + 3, y + h + 10, w - 6, 5, 2)
        knob(sf, x + w / 2, y + h + 12, 2)
    else:
        knob(sf, x + w / 2, y + h - 3, 2)


def d_dresser(sf, x, y, w, h, c, op):
    b = wood(c, 0.85)
    bevel(sf, x, y, w, h, b, 3)
    grain(sf, x + 2, y + 2, w - 4, h - 4, b, 3)
    rr(sf, (232, 226, 210), x + w * 0.1, y + h * 0.22, w * 0.3, h * 0.4, 2)                        # دانتيل
    pygame.draw.circle(sf, (90, 150, 180), (int(x + w * 0.72), int(y + h * 0.45)), int(h * 0.22))  # فازة
    pygame.draw.circle(sf, (210, 80, 90), (int(x + w * 0.72), int(y + h * 0.45)), int(h * 0.1))
    if op:
        rr(sf, sh(b, 0.9), x + 4, y + h, w - 8, 16, 2)
        rr(sf, (26, 20, 18), x + 6, y + h + 1, w - 12, 12, 1)
        rr(sf, (150, 130, 96), x + 9, y + h + 4, 12, 6, 1)
        knob(sf, x + w / 2, y + h + 14, 2)
    else:
        for i in (0.3, 0.7):
            knob(sf, x + w * i, y + h - 3, 2)


def d_desk(sf, x, y, w, h, c, op):
    b = wood(c, 0.85)
    bevel(sf, x, y, w, h, b, 3)
    rr(sf, (66, 92, 70), x + w * 0.2, y + h * 0.18, w * 0.6, h * 0.6, 2)                           # سجادة المكتب
    rr(sf, (232, 226, 206), x + w * 0.28, y + h * 0.28, w * 0.2, h * 0.4, 1)                        # ورق
    pygame.draw.line(sf, (60, 60, 150), (int(x + w * 0.31), int(y + h * 0.35)), (int(x + w * 0.44), int(y + h * 0.35)))
    pygame.draw.line(sf, (120, 120, 120), (int(x + w * 0.31), int(y + h * 0.46)), (int(x + w * 0.44), int(y + h * 0.46)))
    pygame.draw.circle(sf, (40, 60, 40), (int(x + w * 0.82), int(y + h * 0.3)), 6)                  # لمبة المكتب
    pygame.draw.circle(sf, (255, 232, 150), (int(x + w * 0.82), int(y + h * 0.3)), 3)
    rr(sf, (120, 40, 36), x + w * 0.58, y + h * 0.4, w * 0.12, h * 0.3, 1)                          # كتاب
    if op:
        rr(sf, (24, 18, 16), x + 6, y + h, w * 0.26, 14, 2)
        rr(sf, wood(c, 1.0), x + 6, y + h + 10, w * 0.26, 5, 2)
    else:
        knob(sf, x + w * 0.14, y + h - 3, 2)
        knob(sf, x + w * 0.86, y + h - 3, 2)


def d_table(sf, x, y, w, h, c, op):
    b = wood(c, 0.9)
    bevel(sf, x, y, w, h, b, 5)
    grain(sf, x + 2, y + 2, w - 4, h - 4, b, 4)
    rr(sf, (232, 226, 212), x + w * 0.18, y + h * 0.4, w * 0.64, h * 0.2, 1)                        # مفرش
    for i in (0.3, 0.7):                                                                             # أطباق
        pygame.draw.circle(sf, (150, 140, 128), (int(x + w * i) + 1, int(y + h * 0.5) + 1), int(min(w, h) * 0.2))
        pygame.draw.circle(sf, (244, 240, 232), (int(x + w * i), int(y + h * 0.5)), int(min(w, h) * 0.2))
        pygame.draw.circle(sf, (214, 208, 198), (int(x + w * i), int(y + h * 0.5)), int(min(w, h) * 0.12), 1)
    pygame.draw.circle(sf, (160, 190, 210), (int(x + w * 0.5), int(y + h * 0.3)), 4)               # كوباية


def d_coffee(sf, x, y, w, h, c, op):
    b = wood(c, 0.8)
    bevel(sf, x, y, w, h, b, 4)
    rr(sf, (120, 160, 180), x + 4, y + 4, w - 8, h - 8, 3)                                           # سطح زجاج
    pygame.draw.line(sf, (210, 236, 244), (int(x + 8), int(y + 8)), (int(x + w * 0.5), int(y + 8)), 2)
    rr(sf, (150, 60, 50), x + w * 0.3, y + h * 0.3, w * 0.22, h * 0.34, 1)                          # مجلة
    pygame.draw.circle(sf, (240, 240, 240), (int(x + w * 0.72), int(y + h * 0.5)), 5)


def d_chest(sf, x, y, w, h, c, op):
    b = wood(c, 0.85)
    bevel(sf, x, y, w, h, b, 3)
    grain(sf, x + 2, y + 2, w - 4, h - 4, b, 3)
    for xx in (x + w * 0.18, x + w * 0.78):
        rr(sf, (70, 60, 40), xx, y, 5, h, 1)
    if op:
        rr(sf, (18, 14, 12), x + 5, y + 5, w - 10, h - 10, 2)
        rr(sf, wood(c, 1.15), x, y - 10, w, 10, 2)
    else:
        rr(sf, (214, 176, 80), x + w / 2 - 4, y + h - 8, 8, 8, 2)


def d_sofa(sf, x, y, w, h, c, op):
    bevel(sf, x, y, w, h, sh(c, 0.6), 6)
    rr(sf, sh(c, 0.8), x + 2, y + 2, w - 4, h * 0.3, 5)                                              # ضهر الكنبة
    rr(sf, sh(c, 0.9), x + 2, y + h * 0.18, w * 0.1, h - h * 0.2, 5)                                  # الدراعات
    rr(sf, sh(c, 0.9), x + w - w * 0.1 - 2, y + h * 0.18, w * 0.1, h - h * 0.2, 5)
    n = max(1, int(round(w / 38.0)))
    cw_ = (w * 0.8 - 4) / n
    for i in range(n):
        cx = x + w * 0.1 + 2 + i * cw_
        rr(sf, sh(c, 0.7), cx + 1, y + h * 0.3 + 1, cw_ - 1, h * 0.66, 5)
        rr(sf, c, cx + 1, y + h * 0.3, cw_ - 2, h * 0.64, 5)
        pygame.draw.line(sf, sh(c, 1.25), (int(cx + 4), int(y + h * 0.3 + 2)), (int(cx + cw_ - 5), int(y + h * 0.3 + 2)))
    rr(sf, (230, 200, 120), x + w * 0.14, y + h * 0.38, 12, 12, 3)                                   # وسادة زينة


def d_shelf(sf, x, y, w, h, c, op):
    b = wood(c, 0.7)
    bevel(sf, x, y, w, h, b, 2)
    rr(sf, sh(b, 0.5), x + 3, y + 3, w - 6, h - 9, 1)
    cols = [(120, 40, 36), (44, 70, 110), (60, 100, 60), (150, 120, 50), (90, 50, 100), (170, 90, 50)]
    bx = x + 4
    i = 0
    while bx < x + w - 8:                                                                              # كتب واقفة بترصّ على الرف
        bw = 3 + (i * 5) % 3
        rr(sf, cols[i % 6], bx, y + h * 0.28 + (i % 3), bw, h * 0.5, 0)
        bx += bw + 1
        i += 1
    rr(sf, b, x, y + h - 6, w, 6, 1)


def d_fridge(sf, x, y, w, h, c, op):
    wh = (210, 214, 218)
    bevel(sf, x, y, w, h, wh, 4)
    rr(sf, (190, 196, 202), x + 3, y + 3, w - 6, h * 0.4, 3)
    pygame.draw.line(sf, (140, 146, 152), (int(x + 3), int(y + h * 0.46)), (int(x + w - 3), int(y + h * 0.46)))
    if op:
        ang = math.radians(60)
        ex = x + w - 2 - w * 0.8 * math.cos(ang)
        ey = y + h + w * 0.8 * math.sin(ang)
        pygame.draw.polygon(sf, (226, 230, 232), [(x + w - 2, y + h), (ex, ey), (ex, ey + 4), (x + w - 2, y + h - 3)])
        rr(sf, (232, 240, 236), x + 4, y + h - 3, w - 8, 3, 1)
    else:
        rr(sf, (120, 126, 132), x + w - 10, y + h - 6, 4, 6, 1)


def d_cupboard(sf, x, y, w, h, c, op):
    b = wood(c, 0.8)
    bevel(sf, x, y, w, h, b, 3)
    grain(sf, x + 2, y + 2, w - 4, h - 10, b, 3)
    pygame.draw.line(sf, sh(b, 0.45), (int(x + w / 2), int(y + h - 8)), (int(x + w / 2), int(y + h - 1)), 2)
    if op:
        pygame.draw.polygon(sf, sh(b, 0.85), [(x + 2, y + h), (x - 10, y + h + 18), (x - 6, y + h + 20), (x + 6, y + h)])
        pygame.draw.polygon(sf, sh(b, 0.85), [(x + w - 2, y + h), (x + w + 10, y + h + 18), (x + w + 6, y + h + 20), (x + w - 6, y + h)])
    else:
        knob(sf, x + w / 2 - 5, y + h - 4, 2)
        knob(sf, x + w / 2 + 5, y + h - 4, 2)


def d_piano(sf, x, y, w, h, c, op):
    bh = h * 0.55
    bevel(sf, x, y, w, bh, (26, 24, 30), 4)
    pygame.draw.polygon(sf, (70, 68, 80), [(x + 6, y + 4), (x + w * 0.6, y + 4), (x + w * 0.35, y + bh - 4), (x + 6, y + bh - 4)])  # لمعة
    rr(sf, (34, 32, 38), x + 4, y + bh - 2, w - 8, h * 0.22, 2)
    kw = (w - 12) / 14.0
    for i in range(14):                                                                                # الكيبورد
        rr(sf, (240, 236, 228), x + 6 + i * kw, y + bh, kw - 0.6, h * 0.18, 0)
    for i in range(14):
        if i % 7 not in (2, 6):
            rr(sf, (14, 14, 16), x + 6 + i * kw + kw * 0.65, y + bh, kw * 0.6, h * 0.11, 0)
    bx = x + w * 0.3
    rr(sf, (40, 24, 18), bx + 1, y + h * 0.82 + 1, w * 0.4, h * 0.16, 4)                                # الكرسي
    rr(sf, (86, 52, 36), bx, y + h * 0.82, w * 0.4, h * 0.16, 4)
    pygame.draw.line(sf, (140, 96, 70), (int(bx + 4), int(y + h * 0.84)), (int(bx + w * 0.4 - 4), int(y + h * 0.84)))


def d_chair(sf, x, y, w, h, c, op):
    b = wood(c, 0.9)
    cx, cy = x + w / 2.0, y + h / 2.0
    sw, sd = w * 0.62, h * 0.56
    for dx in (-1, 1):                                                                                  # القوائم المقوّسة (هزّاز)
        pygame.draw.ellipse(sf, sh(b, 0.5), (int(cx + dx * sw * 0.52 - 3), int(cy - sd * 0.62), 6, int(sd * 1.4)))
    bevel(sf, cx - sw / 2, cy - sd / 2 + 4, sw, sd, wood(c, 1.1), 5)                                  # الكرسي
    pygame.draw.line(sf, sh(b, 0.7), (int(cx - sw / 2 + 4), int(cy)), (int(cx + sw / 2 - 4), int(cy)))
    rr(sf, sh(b, 0.7), cx - sw / 2 - 1, cy - sd / 2 - 4, sw + 2, 7, 3)                                  # الضهر
    for i in range(1, 4):
        xx = cx - sw / 2 + sw * i / 4.0
        pygame.draw.line(sf, sh(b, 1.2), (int(xx), int(cy - sd / 2 - 3)), (int(xx), int(cy - sd / 2 + 2)))
    for dx in (-1, 1):                                                                                  # دراعات
        rr(sf, sh(b, 0.8), cx + dx * (sw / 2 + 2) - 2, cy - sd / 2 + 2, 4, sd * 0.8, 2)


def d_stove(sf, x, y, w, h, c, op):
    wh = (216, 218, 222)
    bevel(sf, x, y, w, h, wh, 3)
    rr(sf, (180, 184, 190), x + 2, y + 2, w - 4, 5, 1)                                                  # ضهر البوتجاز
    for (fx, fy) in ((0.27, 0.35), (0.73, 0.35), (0.27, 0.7), (0.73, 0.7)):                             # الشعلات
        cx, cy = int(x + w * fx), int(y + h * fy)
        r = int(min(w * 0.17, h * 0.18))
        pygame.draw.circle(sf, (30, 30, 34), (cx, cy), r)
        pygame.draw.circle(sf, (70, 70, 76), (cx, cy), r, 1)
        pygame.draw.circle(sf, (150, 150, 156), (cx, cy), max(2, r // 2), 1)
        pygame.draw.circle(sf, (20, 20, 22), (cx, cy), max(1, r // 4))
    for i in range(4):                                                                                   # مقابض
        pygame.draw.circle(sf, (50, 50, 54), (int(x + w * (0.18 + i * 0.21)), int(y + h - 4)), 2)
    pygame.draw.line(sf, (150, 150, 156), (int(x + 5), int(y + h - 8)), (int(x + w - 5), int(y + h - 8)))


def d_sink(sf, x, y, w, h, c, op):
    bevel(sf, x, y, w, h, (204, 208, 212), 3)
    rr(sf, (120, 130, 140), x + w * 0.12, y + h * 0.3, w * 0.76, h * 0.55, 5)                           # الحوض
    rr(sf, (156, 166, 176), x + w * 0.14, y + h * 0.33, w * 0.72, h * 0.49, 4)
    pygame.draw.circle(sf, (70, 76, 84), (int(x + w * 0.5), int(y + h * 0.58)), 3)                      # البلاعة
    pygame.draw.line(sf, (220, 226, 232), (int(x + w * 0.5), int(y + 3)), (int(x + w * 0.5), int(y + h * 0.3)), 3)   # الحنفية
    pygame.draw.circle(sf, (236, 240, 244), (int(x + w * 0.5), int(y + h * 0.3)), 3)
    knob(sf, x + w * 0.35, y + 5, 2, (180, 186, 192))
    knob(sf, x + w * 0.65, y + 5, 2, (180, 186, 192))


def d_safe(sf, x, y, w, h, c, op):
    m = (74, 76, 86)
    bevel(sf, x, y, w, h, m, 3)
    rr(sf, sh(m, 0.75), x + 4, y + 4, w - 8, h - 8, 2)
    pygame.draw.circle(sf, (200, 200, 210), (int(x + w / 2), int(y + h * 0.4)), int(w * 0.22), 2)       # القرص
    pygame.draw.line(sf, (200, 200, 210), (int(x + w / 2), int(y + h * 0.4)), (int(x + w / 2 + w * 0.12), int(y + h * 0.3)), 2)
    if op:
        pygame.draw.polygon(sf, sh(m, 1.1), [(x + w, y + h), (x + w + 14, y + h + 12), (x + w + 14, y + h + 16), (x + w, y + h - 4)])
        rr(sf, (14, 14, 16), x + 6, y + h - 6, w - 12, 6, 1)


def d_portrait(sf, x, y, w, h, c, op):
    rr(sf, (30, 24, 14), x + 1, y + 3, w, 7, 2)                                                          # ضل
    rr(sf, (190, 150, 60), x, y, w, 7, 2)                                                                # البرواز من فوق
    pygame.draw.line(sf, (250, 220, 130), (int(x + 2), int(y + 1)), (int(x + w - 2), int(y + 1)))


def d_mirror(sf, x, y, w, h, c, op):
    rr(sf, (30, 30, 36), x + 1, y + 3, w, 7, 2)
    rr(sf, (110, 84, 52), x, y, w, 7, 2)
    pygame.draw.line(sf, (200, 224, 236), (int(x + 3), int(y + 3)), (int(x + w - 3), int(y + 3)))


def d_doll(sf, x, y, w, h, c, op):
    cx, cy = x + w / 2.0, y + h / 2.0
    pygame.draw.circle(sf, (60, 30, 40), (int(cx) + 2, int(cy) + 2), int(w * 0.36))
    pygame.draw.circle(sf, (216, 150, 168), (int(cx), int(cy)), int(w * 0.36))                           # الفستان
    pygame.draw.circle(sf, (240, 190, 204), (int(cx), int(cy)), int(w * 0.36), 2)
    for dx in (-1, 1):
        pygame.draw.circle(sf, (236, 214, 196), (int(cx + dx * w * 0.32), int(cy)), 3)                   # الإيدين
    pygame.draw.circle(sf, (58, 36, 26), (int(cx), int(cy)), int(w * 0.2))                                # الشعر
    pygame.draw.circle(sf, (236, 214, 196), (int(cx), int(cy + 2)), int(w * 0.15))
    pygame.draw.circle(sf, (230, 40, 40), (int(cx - 2), int(cy + 1)), 1)
    pygame.draw.circle(sf, (230, 40, 40), (int(cx + 3), int(cy + 1)), 1)


def d_door(sf, x, y, w, h, c, op):
    # الباب ممتد على الطول: x..x+w أو y..y+h حسب الأطول (الدوران بيتم برّه)
    fr = sh(c, 0.55)
    th = min(h, 12)
    yy = y + (h - th) / 2.0
    rr(sf, (20, 14, 10), x, yy + 2, w, th, 2)
    bevel(sf, x, yy, w, th, c, 2)
    for i in (0.25, 0.5, 0.75):
        pygame.draw.line(sf, sh(c, 0.7), (int(x + w * i), int(yy + 2)), (int(x + w * i), int(yy + th - 3)))
    rr(sf, fr, x, yy - 1, 6, th + 2, 1)
    rr(sf, fr, x + w - 6, yy - 1, 6, th + 2, 1)
    knob(sf, x + w * 0.82, yy + th / 2, 3)
    rr(sf, (28, 22, 18), x + w * 0.76, yy + th - 3, 12, 2, 1)                                             # لوحة القفل


def d_block(sf, x, y, w, h, c, op):
    b = wood(c, 0.85)
    bevel(sf, x, y, w, h, b, 3)
    grain(sf, x + 2, y + 2, w - 4, h - 4, b, 3)


STYLES = {
    'bed': d_bed, 'wardrobe': d_wardrobe, 'nightstand': d_nightstand, 'dresser': d_dresser, 'desk': d_desk,
    'table': d_table, 'coffee': d_coffee, 'chest': d_chest, 'sofa': d_sofa, 'shelf': d_shelf, 'fridge': d_fridge,
    'cupboard': d_cupboard, 'piano': d_piano, 'chair': d_chair, 'stove': d_stove, 'sink': d_sink, 'safe': d_safe,
    'portrait': d_portrait, 'mirror': d_mirror, 'doll': d_doll, 'door': d_door, 'block': d_block,
}


def topdown(o, lv, opened=False):
    """بيرجّع (Surface, هامش) لقطعة الأثاث من فوق، متلفّة حسب اتجاه وشها."""
    key = (o.id, o.rect.w, o.rect.h, tuple(o.color), bool(opened))
    c = _CACHE.get(key)
    if c is not None:
        return c
    st = style_of(o)
    W, H = o.rect.w, o.rect.h
    if st == 'door':
        horiz = W >= H                                                  # الباب بيتبني أفقي وبيتلف لو رأسي
        front = 'S' if horiz else 'E'
    else:
        front = infer_front(lv, o, st)
    Wl, Dl = (W, H) if front in ('N', 'S') else (H, W)
    sf = pygame.Surface((Wl + 2 * M, Dl + 2 * M), pygame.SRCALPHA)
    fn = STYLES.get(st, d_block)
    col = tuple(o.color)
    if st not in ('portrait', 'mirror', 'door'):
        sh_ = pygame.Surface((Wl + 2 * M, Dl + 2 * M), pygame.SRCALPHA)
        pygame.draw.rect(sh_, (0, 0, 0, 90), (M + 3, M + 4, Wl, Dl), 0, border_radius=5)         # ضل تحت القطعة
        sf.blit(sh_, (0, 0))
    fn(sf, M, M, Wl, Dl, col, opened)
    ang = {'S': 0, 'N': 180, 'E': 90, 'W': 270}[front]
    if ang:
        sf = pygame.transform.rotate(sf, ang)
    if len(_CACHE) > 120:
        _CACHE.clear()
    _CACHE[key] = (sf, M)
    return _CACHE[key]


def clear_cache():
    _CACHE.clear()

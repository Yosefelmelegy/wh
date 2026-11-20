# -*- coding: utf-8 -*-
"""
fp3d.py - منظور أول (Raycasting) للعبة بيت الهمس
الحيطان بتترسم بالـ DDA، والأثاث متركّب من مكعبات (سرير، دولاب بضلف بتتفتح، دُرج بيتسحب...)،
والوحوش والشموع Sprites بتتحجب ورا الحيطان والأثاث.
بيستخدم نفس منطق اللعبة (الخريطة، الأوبجكتس، الوحوش) وبس بيغيّر طريقة الرسم.
"""
import math
import random
import pygame

T = 32.0                      # حجم البلاطة بالبكسل في منطق اللعبة
EYE = 1.6                     # ارتفاع العين (وحدة = بلاطة تقريبًا متر)
WALL_H = 2.6
FOV = math.radians(72)
REACH = 1.75                  # مدى التفاعل بالبلاطات
NEAR = 0.12


def _sh(c, k):
    """تغميق لون"""
    return (max(0, min(255, int(c[0] * k))), max(0, min(255, int(c[1] * k))), max(0, min(255, int(c[2] * k))))


def _mix(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def fog(t):
    return max(0.17, 1.0 / (1.0 + 0.03 * t * t))


# ===================================================== تحديد نوع الأثاث
STYLE_BY_ID = {
    'bed': 'bed', 'wardrobe': 'wardrobe', 'nightstand': 'nightstand', 'drawer': 'dresser', 'desk': 'desk',
    'lib_desk': 'desk', 'hall_table': 'table', 'coffee_table': 'coffee', 'k_table': 'table',
    'bookshelf_l': 'shelf', 'shelf_1': 'shelf', 'shelf_2': 'shelf', 'shelf_3': 'shelf', 'study_shelf': 'shelf',
    'sofa': 'sofa', 'piano': 'piano', 'chair': 'chair', 'stove': 'stove', 'fridge': 'fridge',
    'cabinet': 'cupboard', 'sink': 'sink', 'safe': 'safe', 'portrait': 'portrait', 'mirror': 'mirror',
    'doll': 'doll', 'study_door': 'door', 'front_door': 'door',
}
NAME_KEYS = [                  # (جزء من الاسم بالعربي، النوع)
    ('الدولاب العلوي', 'cupboard'), ('دولاب', 'wardrobe'), ('الخزانة', 'cupboard'), ('كومودينو', 'nightstand'),
    ('سرير', 'bed'), ('الدُرج', 'dresser'), ('درج', 'dresser'), ('رف', 'shelf'), ('مكتب', 'desk'),
    ('كنبة', 'sofa'), ('ترابيزة', 'table'), ('صندوق', 'chest'), ('تلاجة', 'fridge'), ('بيانو', 'piano'),
    ('كرسي', 'chair'), ('مراية', 'mirror'), ('صورة', 'portrait'), ('دُمية', 'doll'), ('دمية', 'doll'),
    ('بوتجاز', 'stove'), ('حوض', 'sink'), ('خزنة', 'safe'), ('باب', 'door'),
]
OPENABLE = ('wardrobe', 'nightstand', 'dresser', 'desk', 'chest', 'fridge', 'cupboard', 'safe')


def raw_name(o):
    n = getattr(o, 'name', '')
    k = getattr(n, 'key', None)
    return str(k if k is not None else n)


def style_of(o):
    st = getattr(o, '_fpstyle', None)
    if st:
        return st
    st = STYLE_BY_ID.get(getattr(o, 'id', ''))
    if not st:
        nm = raw_name(o)
        for key, v in NAME_KEYS:
            if key in nm:
                st = v
                break
    if not st:
        st = 'door' if getattr(o, 'kind', '') in ('door', 'exit') else 'block'
    if getattr(o, 'kind', '') in ('door', 'exit'):
        st = 'door'
    try:
        o._fpstyle = st
    except Exception:
        pass
    return st


# ===================================================== أشكال هندسية
class Box:
    __slots__ = ('x0', 'y0', 'x1', 'y1', 'z0', 'z1', 'cs', 'cf', 'ct', 'face', 'panels', 'topf', 'rider', 'emit')

    def __init__(self, x0, y0, x1, y1, z0, z1, cs, cf=None, ct=None, face='S', panels=None, topf=None, rider=None):
        self.x0, self.y0, self.x1, self.y1 = min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
        self.z0, self.z1 = z0, z1
        self.cs = cs
        self.cf = cf or cs
        self.ct = ct or _sh(cs, 1.15)
        self.face = face
        self.panels = panels
        self.topf = topf
        self.rider = rider
        self.emit = None


class Quad:
    """لوح رأسي رفيع (ضلفة باب) بيتشاف من الوشين"""
    __slots__ = ('ax', 'ay', 'bx', 'by', 'z0', 'z1', 'c', 'panels', 'c2')

    def __init__(self, ax, ay, bx, by, z0, z1, c, panels=None, c2=None):
        self.ax, self.ay, self.bx, self.by = ax, ay, bx, by
        self.z0, self.z1, self.c, self.panels = z0, z1, c, panels
        self.c2 = c2 or c


class Frame:
    """بيحوّل إحداثيات محلية (u شمال-يمين، v ورا-قدام) لإحداثيات العالم حسب اتجاه وش القطعة"""

    def __init__(self, x0, y0, x1, y1, front):
        self.x0, self.y0, self.x1, self.y1, self.front = x0, y0, x1, y1, front
        W, D = x1 - x0, y1 - y0
        if front in ('N', 'S'):
            self.Wl, self.Dl = W, D
        else:
            self.Wl, self.Dl = D, W

    def pt(self, u, v):
        x0, y0, x1, y1, fr = self.x0, self.y0, self.x1, self.y1, self.front
        W, D = x1 - x0, y1 - y0
        if fr == 'S':
            return x0 + u * W, y0 + v * D
        if fr == 'N':
            return x1 - u * W, y1 - v * D
        if fr == 'E':
            return x0 + v * W, y1 - u * D
        return x1 - v * W, y0 + u * D

    def box(self, u0, u1, v0, v1, z0, z1, cs, **kw):
        ax, ay = self.pt(u0, v0)
        bx, by = self.pt(u1, v1)
        return Box(ax, ay, bx, by, z0, z1, cs, face=self.front, **kw)

    def quad(self, u0, v0, u1, v1, z0, z1, c, panels=None):
        ax, ay = self.pt(u0, v0)
        bx, by = self.pt(u1, v1)
        return Quad(ax, ay, bx, by, z0, z1, c, panels)


def wood(c, k=1.0):
    return _sh((min(255, c[0] + 10), min(255, c[1] + 4), c[2]), k)


def handle(u, z, col=(210, 170, 70), w=0.025, h=0.09):
    return (u - w, u + w, z - h / 2, z + h / 2, col)


def door_panels(u0, u1, z0, z1, base, inset=0.07):
    """ضلفة بإطار غاطس: إطار غامق + لوح أفتح شوية"""
    dk = _sh(base, 0.62)
    lt = _sh(base, 1.12)
    return [(u0, u1, z0, z1, dk), (u0 + inset * 0.5, u1 - inset * 0.5, z0 + inset, z1 - inset, lt)]


# ===================================================== بناء الأثاث
def build_parts(o, fr, p, G=None):
    """بيرجّع (boxes, quads) للقطعة. p = مدى فتح الدُرج/الضلفة من 0 لـ 1"""
    st = style_of(o)
    c = tuple(o.color)
    Wl, Dl = fr.Wl, fr.Dl
    B = []
    Q = []
    bx = fr.box

    if st == 'bed':
        frame = _sh(c, 0.55)
        sheet = (226, 220, 205)
        B.append(bx(0, 1, 0, 1, 0.0, 0.30, frame))                                  # الهيكل
        B.append(bx(0.02, 0.98, 0.02, 0.98, 0.30, 0.50, sheet))                     # المرتبة
        B.append(bx(0.02, 0.98, 0.30, 0.98, 0.50, 0.57, c, topf=_stripes(c), rider=1))   # الغطا
        B.append(bx(0.06, 0.47, 0.04, 0.26, 0.50, 0.64, (238, 234, 224), rider=1))    # مخدّة
        B.append(bx(0.53, 0.94, 0.04, 0.26, 0.50, 0.64, (238, 234, 224), rider=1))
        B.append(bx(0, 1, 0, 0.05, 0.0, 1.25, frame, cf=_sh(frame, 1.1)))            # ضهر السرير
        B.append(bx(0, 1, 0.95, 1, 0.0, 0.46, frame))                                 # ناحية الرجلين
    elif st in ('wardrobe', 'cupboard'):
        h = 2.1 if st == 'wardrobe' else 1.75
        w = wood(c, 0.8)
        inner = _sh(c, 0.28)
        B.append(bx(0, 1, 0, 0.05, 0.0, h, inner))                                    # الضهر
        B.append(bx(0, 0.04, 0, 1, 0.0, h, w))                                        # جنب شمال
        B.append(bx(0.96, 1, 0, 1, 0.0, h, w))
        B.append(bx(0, 1, 0, 1, h - 0.06, h, w, ct=_sh(c, 1.2)))                      # السقف
        B.append(bx(0, 1, 0, 1, 0.0, 0.10, _sh(c, 0.6)))                              # القاعدة
        B.append(bx(0.04, 0.96, 0.05, 0.9, 1.1, 1.14, _sh(c, 0.5), ct=_sh(c, 0.6)))   # رف
        B.append(bx(0.10, 0.42, 0.2, 0.7, 0.35, 1.1, (52, 44, 60)))                   # هدوم متعلّقة
        B.append(bx(0.52, 0.9, 0.2, 0.7, 0.35, 1.1, (70, 46, 44)))
        ang = p * 1.75
        L = 0.5
        for side in (0, 1):
            hu = 0.04 if side == 0 else 0.96
            s_ = 1 if side == 0 else -1
            du = L * math.cos(ang)                        # الضلفة بتلف حوالين المفصلة
            dv = (L * Wl / max(Dl, 0.1)) * math.sin(ang)
            Q.append(fr.quad(hu, 1.0, hu + s_ * du, 1.0 + dv, 0.06, h - 0.05, w,
                             panels=door_panels(0, 1, 0.06, h - 0.05, w) + [handle(0.88, 1.0)]))
    elif st == 'nightstand':
        b = wood(c, 0.85)
        B.append(bx(0, 1, 0, 1, 0.0, 0.56, b, cf=wood(c, 0.95), panels=[
            (0.08, 0.92, 0.32, 0.52, _sh(c, 0.6)), (0.1, 0.9, 0.34, 0.5, wood(c, 1.1)), handle(0.5, 0.42),
            (0.08, 0.92, 0.06, 0.28, _sh(c, 0.6)), (0.1, 0.9, 0.08, 0.26, wood(c, 1.1)), handle(0.5, 0.17)]))
        B.append(bx(-0.04, 1.04, -0.04, 1.04, 0.56, 0.6, wood(c, 1.1)))
        B.append(bx(0.35, 0.65, 0.3, 0.6, 0.6, 0.68, (230, 215, 150)))                # أباجورة صغيرة
        if p > 0.02:
            ext = 0.55 * p
            B.append(bx(0.1, 0.9, 1.0, 1.0 + ext, 0.3, 0.5, wood(c, 0.9), cf=wood(c, 1.0), ct=(28, 22, 20),
                        panels=[handle(0.5, 0.4)]))
    elif st == 'dresser':
        b = wood(c, 0.85)
        rows = 3
        pan = []
        for i in range(rows):
            z0 = 0.06 + i * 0.3
            pan += [(0.05, 0.95, z0, z0 + 0.26, _sh(c, 0.58)), (0.07, 0.93, z0 + 0.02, z0 + 0.24, wood(c, 1.08)),
                    handle(0.35, z0 + 0.13), handle(0.65, z0 + 0.13)]
        B.append(bx(0, 1, 0, 1, 0.0, 1.0, b, cf=wood(c, 0.95), panels=pan))
        B.append(bx(-0.02, 1.02, -0.02, 1.02, 1.0, 1.05, wood(c, 1.12)))
        if p > 0.02:
            ext = 0.5 * p
            B.append(bx(0.07, 0.93, 1.0, 1.0 + ext, 0.68, 0.9, wood(c, 1.0), cf=wood(c, 1.05), ct=(30, 24, 22),
                        panels=[handle(0.5, 0.79)]))
            B.append(bx(0.1, 0.9, 1.04, 0.95 + ext, 0.7, 0.76, (120, 100, 70), ct=(120, 100, 70)))   # حاجات جوه الدُرج
    elif st == 'desk':
        b = wood(c, 0.85)
        B.append(bx(0, 1, 0, 1, 0.70, 0.76, wood(c, 1.15), cf=b, ct=wood(c, 1.1)))                  # سطح المكتب
        pan_l = [(0.1, 0.9, 0.38, 0.66, _sh(c, 0.58)), (0.12, 0.88, 0.4, 0.64, wood(c, 1.08)), handle(0.5, 0.52),
                 (0.1, 0.9, 0.06, 0.34, _sh(c, 0.58)), (0.12, 0.88, 0.08, 0.32, wood(c, 1.08)), handle(0.5, 0.2)]
        B.append(bx(0.02, 0.28, 0.06, 0.96, 0.0, 0.70, b, cf=wood(c, 0.95), panels=pan_l))
        B.append(bx(0.72, 0.98, 0.06, 0.96, 0.0, 0.70, b, cf=wood(c, 0.95), panels=[
            (0.1, 0.9, 0.38, 0.66, _sh(c, 0.58)), (0.12, 0.88, 0.4, 0.64, wood(c, 1.08)), handle(0.5, 0.52)]))
        B.append(bx(0.28, 0.72, 0.04, 0.1, 0.25, 0.70, _sh(c, 0.7)))
        B.append(bx(0.4, 0.62, 0.35, 0.6, 0.76, 0.8, (215, 205, 180)))                                # ورق على المكتب
        if p > 0.02:
            ext = 0.5 * p
            B.append(bx(0.04, 0.26, 0.96, 0.96 + ext, 0.38, 0.62, wood(c, 1.0), cf=wood(c, 1.05), ct=(28, 22, 20),
                        panels=[handle(0.5, 0.5)]))
    elif st in ('table', 'coffee'):
        h = 0.72 if st == 'table' else 0.42
        b = wood(c, 0.9)
        B.append(bx(0, 1, 0, 1, h - 0.07, h, wood(c, 1.15), cf=b, ct=wood(c, 1.2)))
        lg = 0.07
        for (u_, v_) in ((0.04, 0.08), (0.96 - lg, 0.08), (0.04, 0.92 - lg), (0.96 - lg, 0.92 - lg)):
            B.append(bx(u_, u_ + lg, v_, v_ + lg * 0.9, 0.0, h - 0.07, b))
        if st == 'table':
            B.append(bx(0.4, 0.55, 0.4, 0.55, h, h + 0.1, (200, 190, 170)))               # كوباية/حاجة على الترابيزة
        else:
            B.append(bx(0.42, 0.52, 0.42, 0.52, h, h + 0.08, (235, 235, 235)))
    elif st == 'chest':
        b = wood(c, 0.85)
        B.append(bx(0, 1, 0, 1, 0.0, 0.40, b, cf=wood(c, 0.95), panels=[
            (0.0, 1.0, 0.28, 0.32, (70, 60, 40)), (0.46, 0.54, 0.18, 0.34, (200, 160, 60))]))
        lift = 0.18 * p
        B.append(bx(0, 1, 0, 1, 0.40 + lift, 0.5 + lift, wood(c, 1.1), cf=wood(c, 1.0), ct=wood(c, 1.25)))
        if p > 0.02:
            B.append(bx(0.05, 0.95, 0.05, 0.95, 0.36, 0.40, (24, 20, 18)))
    elif st == 'sofa':
        sofa = c
        n = max(1, int(round(Wl / 1.15)))
        B.append(bx(0, 1, 0, 1, 0.0, 0.2, _sh(sofa, 0.5)))                                  # القاعدة
        B.append(bx(0, 1, 0, 0.26, 0.0, 0.98, _sh(sofa, 0.85)))                            # ضهر الكنبة
        B.append(bx(0, 0.09, 0, 1, 0.0, 0.66, _sh(sofa, 0.9)))                              # ذراع
        B.append(bx(0.91, 1, 0, 1, 0.0, 0.66, _sh(sofa, 0.9)))
        for i in range(n):
            u0 = 0.09 + (0.82 / n) * i + 0.004
            u1 = 0.09 + (0.82 / n) * (i + 1) - 0.004
            B.append(bx(u0, u1, 0.26, 1.0, 0.2, 0.5, sofa, ct=_sh(sofa, 1.2), rider=None))
    elif st == 'shelf':
        w = wood(c, 0.75)
        h = 2.1
        books = (0.0, 1.0, 0.3, 2.0, None, 'books', hash(o.id) if hasattr(o, 'id') else 1)
        B.append(bx(0.0, 1.0, 0.0, 0.12, 0.0, h, _sh(c, 0.45), cf=_sh(c, 0.5), panels=[
            (0.02, 0.98, 0.18, 0.5, None, 'books', 1), (0.02, 0.98, 0.56, 0.9, None, 'books', 2),
            (0.02, 0.98, 0.96, 1.3, None, 'books', 3), (0.02, 0.98, 1.36, 1.7, None, 'books', 4),
            (0.02, 0.98, 1.76, 2.04, None, 'books', 5)]))
        B.append(bx(0, 0.04, 0, 1, 0.0, h, w))
        B.append(bx(0.96, 1, 0, 1, 0.0, h, w))
        B.append(bx(0, 1, 0, 1, h - 0.05, h, w))
        for z in (0.02, 0.52, 0.92, 1.32, 1.72):
            B.append(bx(0.04, 0.96, 0, 1, z, z + 0.04, wood(c, 0.95)))
    elif st == 'fridge':
        wh = (206, 210, 214)
        B.append(bx(0, 1, 0, 1, 0.0, 1.85, _sh(wh, 0.85), cf=wh, panels=([
            (0.0, 1.0, 1.18, 1.21, (110, 114, 120)), (0.06, 0.12, 1.25, 1.62, (130, 134, 140)), (0.06, 0.12, 0.7, 1.1, (130, 134, 140))]
            if p < 0.02 else [(0.04, 0.96, 0.05, 1.8, (232, 238, 236)), (0.04, 0.96, 0.58, 0.6, (160, 170, 170)),
                              (0.04, 0.96, 1.0, 1.02, (160, 170, 170)), (0.04, 0.96, 1.4, 1.42, (160, 170, 170)),
                              (0.1, 0.3, 0.1, 0.5, (190, 120, 90)), (0.5, 0.8, 0.62, 0.95, (120, 150, 110))])))
        if p > 0.02:
            ang = p * 1.6
            du = math.cos(ang) * 0.92
            dv = (Wl / Dl) * math.sin(ang) * 0.92
            Q.append(fr.quad(0.0, 1.0, du, 1.0 + dv, 0.05, 1.8, wh, panels=[(0.0, 1.0, 1.15, 1.2, (150, 154, 160)),
                                                                          handle(0.9, 1.5, (150, 154, 160))]))
    elif st == 'piano':
        blk = (26, 24, 28)
        B.append(bx(0, 1, 0, 0.5, 0.0, 1.3, blk, cf=(34, 32, 36), panels=[
            (0.06, 0.94, 0.9, 1.22, (46, 42, 40)), (0.2, 0.8, 0.5, 0.58, (200, 170, 70))]))
        B.append(bx(0.0, 1.0, 0.5, 0.78, 0.66, 0.74, blk, ct=(236, 232, 224), topf=_keys()))   # الكيبورد
        B.append(bx(0.04, 0.08, 0.52, 0.76, 0.0, 0.66, blk))
        B.append(bx(0.92, 0.96, 0.52, 0.76, 0.0, 0.66, blk))
        B.append(bx(0.35, 0.65, 0.86, 1.0, 0.36, 0.44, (60, 40, 30)))                            # الكرسي
    elif st == 'chair':
        w = wood(c, 0.9)
        sw = math.sin(G.t * 2.2) * 0.04 if G else 0.0
        B.append(bx(0.1, 0.9, 0.2 + sw, 0.9 + sw, 0.42, 0.48, wood(c, 1.1)))
        B.append(bx(0.1, 0.9, 0.16 + sw, 0.22 + sw, 0.48, 1.05, w, panels=[
            (0.15, 0.2, 0.5, 1.0, wood(c, 1.2)), (0.4, 0.45, 0.5, 1.0, wood(c, 1.2)), (0.6, 0.65, 0.5, 1.0, wood(c, 1.2)),
            (0.8, 0.85, 0.5, 1.0, wood(c, 1.2))]))
        for u_ in (0.1, 0.84):
            B.append(bx(u_, u_ + 0.06, 0.2 + sw, 0.9 + sw, 0.42, 0.7, w))
            B.append(bx(u_, u_ + 0.06, 0.1 + sw, 1.0 + sw, 0.0, 0.06, w))
    elif st == 'stove':
        wh = (216, 218, 222)
        B.append(bx(0, 1, 0, 1, 0.0, 0.86, _sh(wh, 0.8), cf=wh, panels=[
            (0.1, 0.9, 0.1, 0.6, (40, 40, 44)), (0.14, 0.86, 0.14, 0.56, (70, 80, 90)), (0.2, 0.8, 0.66, 0.7, (150, 150, 156)),
            (0.1, 0.16, 0.76, 0.82, (30, 30, 30)), (0.3, 0.36, 0.76, 0.82, (30, 30, 30)), (0.5, 0.56, 0.76, 0.82, (30, 30, 30)),
            (0.7, 0.76, 0.76, 0.82, (30, 30, 30))], ct=(40, 40, 44)))
        for (u_, v_) in ((0.2, 0.3), (0.65, 0.3), (0.2, 0.7), (0.65, 0.7)):
            B.append(bx(u_, u_ + 0.15, v_ - 0.08, v_ + 0.1, 0.86, 0.89, (20, 20, 22)))
        B.append(bx(0.0, 1.0, 0.0, 0.1, 0.86, 1.3, (190, 190, 196)))
    elif st == 'sink':
        b = wood(c, 0.7)
        B.append(bx(0, 1, 0, 1, 0.0, 0.84, (200, 204, 208), cf=(206, 210, 214), panels=[
            (0.06, 0.48, 0.08, 0.78, (180, 186, 192)), (0.52, 0.94, 0.08, 0.78, (180, 186, 192)),
            handle(0.44, 0.7, (120, 124, 130)), handle(0.56, 0.7, (120, 124, 130))]))
        B.append(bx(0.1, 0.9, 0.15, 0.85, 0.84, 0.88, (150, 156, 164), ct=(70, 76, 84)))
        B.append(bx(0.47, 0.53, 0.08, 0.14, 0.88, 1.15, (170, 176, 182)))
        B.append(bx(0.47, 0.6, 0.08, 0.14, 1.1, 1.15, (170, 176, 182)))
    elif st == 'safe':
        m = (70, 72, 80)
        B.append(bx(0, 1, 0, 1, 0.0, 0.95, _sh(m, 0.8), cf=m, panels=[
            (0.1, 0.9, 0.08, 0.87, (56, 58, 66)), (0.36, 0.64, 0.42, 0.58, (190, 190, 200)),
            (0.44, 0.56, 0.47, 0.53, (50, 50, 56)), (0.78, 0.84, 0.3, 0.7, (170, 170, 176))] if p < 0.02 else [
            (0.1, 0.9, 0.08, 0.87, (18, 18, 20)), (0.12, 0.88, 0.45, 0.48, (90, 90, 96))]))
    elif st == 'portrait':
        fm = (110, 84, 34)
        B.append(bx(0.0, 1.0, 0.0, 0.07, 0.8, 2.15, fm, cf=fm, panels=[
            (0.06, 0.94, 0.9, 2.05, (22, 18, 16)), (0.14, 0.86, 1.0, 1.95, (60, 56, 50)),
            (0.36, 0.64, 1.45, 1.85, (150, 130, 110)), (0.3, 0.7, 1.0, 1.45, (30, 26, 30)),
            (0.43, 0.48, 1.62, 1.68, (240, 240, 235)), (0.52, 0.57, 1.62, 1.68, (240, 240, 235))]))
    elif st == 'mirror':
        fm = (88, 66, 40)
        shim = 0.55 + 0.1 * math.sin(G.t * 1.3) if G else 0.55
        mb = bx(0.0, 1.0, 0.0, 0.07, 0.1, 2.15, fm, cf=fm, panels=[
            (0.08, 0.92, 0.2, 2.05, _mix((150, 170, 180), (210, 225, 235), shim)),
            (0.12, 0.5, 0.3, 2.0, (190, 205, 215)), (0.5, 0.9, 0.2, 1.4, (120, 140, 152))])
        mb.emit = 'mirror'                                  # المراية بتعكس المكان بجد (مع الوحوش)
        B.append(mb)
        B.append(bx(0.35, 0.65, 0.02, 0.2, 0.0, 0.1, fm))
    elif st == 'doll':
        dress = (216, 150, 168)
        B.append(bx(0.28, 0.72, 0.28, 0.72, 0.0, 0.34, dress))
        B.append(bx(0.34, 0.66, 0.34, 0.66, 0.34, 0.6, _sh(dress, 1.08)))
        B.append(bx(0.38, 0.62, 0.38, 0.62, 0.6, 0.82, (236, 214, 196), cf=(240, 220, 204), panels=[
            (0.18, 0.4, 0.62, 0.74, (250, 250, 250)), (0.6, 0.82, 0.62, 0.74, (250, 250, 250)),
            (0.26, 0.34, 0.65, 0.71, (20, 20, 24)), (0.68, 0.76, 0.65, 0.71, (20, 20, 24)),
            (0.36, 0.64, 0.5, 0.54, (150, 40, 50))]))
        B.append(bx(0.36, 0.64, 0.36, 0.64, 0.78, 0.86, (58, 36, 26)))
    elif st == 'door':
        # الباب بيتبني في build_door
        pass
    else:
        B.append(bx(0, 1, 0, 1, 0.0, 0.9, wood(c, 0.85), cf=wood(c, 1.0)))
    return B, Q


def _stripes(c):
    a = _sh(c, 1.0)
    b = _sh(c, 0.78)

    def f(hx, hy):
        return a if (int(hx * 6 + hy * 6) & 1) == 0 else b
    return f


def _keys():
    def f(hx, hy):
        return (236, 232, 224) if (int(hx * 7) % 2) == 0 else (60, 58, 56)
    return f


def build_door(o, rect, p, wallc, solid_open=False):
    """باب بإطار ولوح بيتفتح. rect = (x0,y0,x1,y1) بالبلاطات"""
    x0, y0, x1, y1 = rect
    W, D = x1 - x0, y1 - y0
    c = tuple(o.color)
    boxes, quads = [], []
    horiz = W >= D                                  # الباب ممتد على x
    th = 0.14
    if horiz:
        cy = (y0 + y1) / 2
        ya, yb = cy - th / 2, cy + th / 2
        lint = Box(x0, ya - 0.04, x1, yb + 0.04, 2.25, WALL_H, wallc, face='S')
        fr = Frame(x0, ya, x1, yb, 'S')
        post_a = Box(x0, ya - 0.04, x0 + 0.1, yb + 0.04, 0.0, 2.25, _sh(c, 0.6), face='S')
        post_b = Box(x1 - 0.1, ya - 0.04, x1, yb + 0.04, 0.0, 2.25, _sh(c, 0.6), face='S')
        boxes += [lint, post_a, post_b]
        if p < 0.98:
            ang = p * 1.5
            hx, hy = x0 + 0.1, cy
            L = (W - 0.2)
            ex, ey = hx + L * math.cos(ang), hy + L * math.sin(ang)
            pan = door_panels(0, 1, 0.06, 2.2, c) + [(0.06, 0.94, 1.1, 1.14, _sh(c, 0.5)), handle(0.9, 1.05, (210, 170, 70), 0.03, 0.14)]
            quads.append(Quad(hx, hy, ex, ey, 0.0, 2.2, c, pan))
    else:
        cx = (x0 + x1) / 2
        xa, xb = cx - th / 2, cx + th / 2
        lint = Box(xa - 0.04, y0, xb + 0.04, y1, 2.25, WALL_H, wallc, face='E')
        post_a = Box(xa - 0.04, y0, xb + 0.04, y0 + 0.1, 0.0, 2.25, _sh(c, 0.6), face='E')
        post_b = Box(xa - 0.04, y1 - 0.1, xb + 0.04, y1, 0.0, 2.25, _sh(c, 0.6), face='E')
        boxes += [lint, post_a, post_b]
        if p < 0.98:
            ang = p * 1.5
            hx, hy = cx, y0 + 0.1
            L = (D - 0.2)
            ex, ey = hx + L * math.sin(ang), hy + L * math.cos(ang)
            pan = door_panels(0, 1, 0.06, 2.2, c) + [(0.06, 0.94, 1.1, 1.14, _sh(c, 0.5)), handle(0.9, 1.05, (210, 170, 70), 0.03, 0.14)]
            quads.append(Quad(hx, hy, ex, ey, 0.0, 2.2, c, pan))
    return boxes, quads


# ===================================================== اتجاه وش القطعة
OPP = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}


def _wall_count(lv, x0, y0, x1, y1, side):
    n = 0
    tot = 0
    if side in ('N', 'S'):
        yy = y0 - 1 if side == 'N' else y1
        for xx in range(x0, x1):
            tot += 1
            if yy < 0 or yy >= lv.H or xx < 0 or xx >= lv.W or lv.grid[yy][xx] == 1:
                n += 1
    else:
        xx = x0 - 1 if side == 'W' else x1
        for yy in range(y0, y1):
            tot += 1
            if yy < 0 or yy >= lv.H or xx < 0 or xx >= lv.W or lv.grid[yy][xx] == 1:
                n += 1
    return n / max(1, tot)


def infer_front(lv, o, style):
    r = o.rect
    x0, y0, x1, y1 = int(r.left // T), int(r.top // T), int(r.right // T), int(r.bottom // T)
    W, H = x1 - x0, y1 - y0
    cnt = {sd: _wall_count(lv, x0, y0, x1, y1, sd) for sd in 'NSEW'}
    if style == 'bed':
        ends = ('W', 'E') if W >= H else ('N', 'S')
        head = max(ends, key=lambda sd: (cnt[sd], sd == ends[0]))
        return OPP[head]
    if style in ('portrait', 'mirror'):
        back = max('NSEW', key=lambda sd: cnt[sd])
        return OPP[back]
    best = max('NSEW', key=lambda sd: (cnt[sd], sd == 'N'))
    if cnt[best] > 0:
        return OPP[best]
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    for nm, (rx, ry, rw, rh), _c in getattr(lv, 'rooms', []):
        if rx <= cx < rx + rw and ry <= cy < ry + rh:
            vx, vy = rx + rw / 2.0 - cx, ry + rh / 2.0 - cy
            if abs(vx) > abs(vy):
                return 'E' if vx > 0 else 'W'
            return 'S' if vy > 0 else 'N'
    return 'S'


# ===================================================== المحرك
BOOK_COLS = [(120, 40, 36), (44, 70, 110), (60, 100, 60), (150, 120, 50), (90, 50, 100), (170, 90, 50),
             (50, 50, 56), (130, 110, 90)]


def _bookcol(u, seed):
    i = int(u * 46)
    h = (i * 7 + seed * 13 + (i // 5) * 3) % len(BOOK_COLS)
    c = BOOK_COLS[h]
    if i % 5 == 0:
        return (24, 18, 14)
    return c


class FP:
    # (عرض العمود بالبكسل، مستوى المؤثرات): 3 = كل حاجة (ظلال + انعكاسات + مراية + توهّج)، 0 = بدون مؤثرات
    STATES = ((2, 3), (3, 3), (3, 2), (4, 2), (4, 1), (6, 1), (6, 0), (8, 0))
    MODES = ('auto', 'ultra', 'high', 'low')

    def __init__(self, SW, SH, touch=False):
        self.SW, self.SH = SW, SH
        self.f = (SW / 2.0) / math.tan(FOV / 2)
        self.si = 5 if touch else 1
        self.mode = 'auto'
        self.cw, self.fx = self.STATES[self.si]
        self._small = self._big = self._big2 = self._beam = None
        self._mirror_ok = True
        self._surf = None
        self._bloom_ok = True
        self._G = self._lv = None
        self._vis = []
        self._mir_sprites = []
        self._occ = []
        self._L = (0.0, 0.0)
        self.anim = {}
        self.front = {}
        self.ema = 0.016
        self.qt = 0.0
        self.uid = 0
        self.zwall = []
        self._lastt = None
        self._wallc = {}
        self._decos = {}
        self.auto = True
        self.debug = False
        self.dust = [(random.random(), random.random(), 0.2 + random.random() * 0.8, random.random() * 6.28) for _ in range(46)]
        self._grade = None
        self.last_sp = []
        self.horizon = SH // 2

    # ---------- تحويل نقطة عالم لشاشة
    def proj(self, X, Y, Z, px, py, dx, dy, rx, ry, horizon):
        relx, rely = X - px, Y - py
        cz = relx * dx + rely * dy
        if cz < NEAR:
            return None
        cx = relx * rx + rely * ry
        return (self.SW / 2.0 + cx / cz * self.f, horizon + (EYE - Z) / cz * self.f, cz)

    # ---------- الجودة التلقائية
    def adapt(self, dtms, dt):
        self.ema += (dtms - self.ema) * 0.08
        self.qt += dt
        if self.auto and self.mode == 'auto' and self.qt > 1.2:
            self.qt = 0.0
            if self.ema > 27 and self.si < len(self.STATES) - 1:
                self.si += 1
            elif self.ema < 10 and self.si > 0:
                self.si -= 1

    def cycle_quality(self):
        """زرار G: تلقائي ← أعلى جودة ← عالي ← منخفض"""
        i = (self.MODES.index(self.mode) + 1) % len(self.MODES)
        self.mode = self.MODES[i]
        if self.mode == 'ultra':
            self.si = 0
        elif self.mode == 'high':
            self.si = 2
        elif self.mode == 'low':
            self.si = 5
        return self.mode

    # ---------- ألوان الحيطان حسب الأوضة
    def wall_style(self, fc):
        w = self._wallc.get(fc)
        if w is None:
            base = _mix(fc, (170, 152, 128), 0.55)
            paper = (min(255, int(base[0] * 1.2)), min(255, int(base[1] * 1.12)), min(255, int(base[2] * 1.06)))
            wain = _sh(_mix(fc, (96, 62, 40), 0.5), 0.9)
            w = dict(paper=paper, paper2=_sh(paper, 0.88), wain=wain, wain_lt=_sh(wain, 1.2), wain_dk=_sh(wain, 0.6),
                     base=_sh(wain, 0.45), rail=_sh(wain, 1.35), crown=_sh(paper, 0.75))
            self._wallc[fc] = w
        return w

    def deco_of(self, tx, ty, side):
        key = (tx, ty, side)
        d = self._decos.get(key, 0)
        if d == 0:
            h = (tx * 73856093 ^ ty * 19349663 ^ (side + 1) * 83492791) & 0xFFFF
            d = None
            if h % 9 == 0:
                d = 'frame'
            elif h % 9 == 1:
                d = 'window'
            self._decos[key] = d
        return d

    # ---------- الواجهة الرئيسية
    def draw(self, s, G, sprites, light, glow, bob=0, shx=0, shy=0):
        import time
        t0 = time.perf_counter()
        SW, SH, f = self.SW, self.SH, self.f
        lv = G.lv
        px, py = G.px / T, G.py / T
        ang = G.ang
        dx, dy = math.cos(ang), math.sin(ang)
        rx, ry = -dy, dx
        horizon = SH // 2 + int(bob) + int(shy)
        self.cw, self.fx = self.STATES[self.si]
        cw = self.cw
        fxl = self.fx
        N = (SW + cw - 1) // cw
        now = G.t
        dt = 0.016 if self._lastt is None else max(0.0, min(0.1, now - self._lastt))
        self._lastt = now

        self.horizon = horizon
        vis = self._visible_objects(G, lv, px, py, dx, dy, rx, ry, N, cw, dt)
        # الظلال الحقيقية من الكشاف: الأثاث اللي بيحجب النور بيرمي ضل على الحيطان والأرض
        occ = []
        Lx = Ly = 0.0
        if fxl >= 3 and G.flash_ok() and not self.debug:
            Lx, Ly = px + rx * 0.32, py + ry * 0.32
            for v in vis:
                if v[8] in ('door', 'portrait', 'mirror'):
                    continue
                x0_, y0_, x1_, y1_ = v[9]
                occ.append((x0_, y0_, x1_, y1_, max([b.z1 for b in v[6]] or [0.5])))
        self._occ, self._L = occ, (Lx, Ly)
        self._G, self._lv, self._vis = G, lv, vis
        self._surf = s
        self._mir_sprites = sprites
        self._backdrop(s, horizon)
        self._ceiling(s, px, py, dx, dy, rx, ry, horizon, lv)
        self._floor(s, G, lv, px, py, dx, dy, rx, ry, horizon)
        self._shadows(s, vis, lv, px, py, dx, dy, rx, ry, horizon)

        items = [[] for _ in range(N)]
        zwall = [30.0] * N
        self.uid = 0
        grid, GW, GH = lv.grid, lv.W, lv.H
        invf = 1.0 / f
        cams = [((i * cw + cw / 2.0) - SW / 2.0) * invf for i in range(N)]
        maxd = 17.0
        uid = 0
        # --- الحيطان
        for i in range(N):
            cam = cams[i]
            rdx, rdy = dx + rx * cam, dy + ry * cam
            mx, my = int(px), int(py)
            ddx = abs(1.0 / rdx) if rdx else 1e30
            ddy = abs(1.0 / rdy) if rdy else 1e30
            if rdx < 0:
                stx, sdx = -1, (px - mx) * ddx
            else:
                stx, sdx = 1, (mx + 1.0 - px) * ddx
            if rdy < 0:
                sty, sdy = -1, (py - my) * ddy
            else:
                sty, sdy = 1, (my + 1.0 - py) * ddy
            side = 0
            hit = False
            for _ in range(48):
                if sdx < sdy:
                    sdx += ddx
                    mx += stx
                    side = 0
                else:
                    sdy += ddy
                    my += sty
                    side = 1
                if mx < 0 or my < 0 or mx >= GW or my >= GH:
                    hit = True
                    break
                if grid[my][mx] == 1:
                    hit = True
                    break
                if (sdx if sdx < sdy else sdy) > maxd + 2:
                    break
            if not hit:
                continue
            t = (sdx - ddx) if side == 0 else (sdy - ddy)
            if t < 0.02:
                t = 0.02
            if side == 0:
                wu = py + t * rdy
                pcx, pcy = mx - stx, my
            else:
                wu = px + t * rdx
                pcx, pcy = mx, my - sty
            if 0 <= pcx < GW and 0 <= pcy < GH:
                fc = lv.floorc[pcy][pcx]
            else:
                fc = (60, 50, 44)
            zwall[i] = t
            shz = 0.0
            if occ and t < 9.0:
                shz = self._wall_shadow(px + t * rdx, py + t * rdy, Lx, Ly, occ)
            uid += 1
            items[i].append((t, uid, 0, side, wu, fc, mx, my, shz))
        self.zwall = zwall

        # --- الأثاث
        for (bx0, by0, bx1, by1, c0, c1, boxes, quads, _st, _rc) in vis:
            for i in range(c0, c1):
                cam = cams[i]
                rdx, rdy = dx + rx * cam, dy + ry * cam
                tw = zwall[i]
                if not self._ray_aabb(px, py, rdx, rdy, bx0, by0, bx1, by1, tw):
                    continue
                base_t = {}
                for bi, b in enumerate(boxes):
                    r = self._ray_aabb(px, py, rdx, rdy, b.x0, b.y0, b.x1, b.y1, tw)
                    if not r:
                        continue
                    t1, t2, axis = r
                    if b.rider is not None and b.rider in base_t:
                        ts = base_t[b.rider] - 1e-3
                    else:
                        ts = t1
                    base_t[bi] = t1
                    uid += 1
                    items[i].append((ts, uid, 1, b, t1, t2, axis, rdx, rdy))
                for q in quads:
                    r = self._ray_seg(px, py, rdx, rdy, q.ax, q.ay, q.bx, q.by)
                    if r and r[0] < tw:
                        uid += 1
                        items[i].append((r[0], uid, 2, q, r[1], r[2]))

        # --- الـ Sprites (وحوش، شموع، لاعبين)
        sp_draw = []
        for sp in sprites:
            pr = self._sprite_screen(sp, px, py, dx, dy, rx, ry, horizon)
            if not pr:
                continue
            surf, x0, y0, wpx, hpx, cz, refl = pr
            c0 = max(0, int(x0 // cw))
            c1 = min(N, int((x0 + wpx) // cw) + 1)
            for i in range(c0, c1):
                if zwall[i] < cz:
                    continue
                if refl:
                    uid += 1
                    items[i].append((cz + 0.002, uid, 3, refl[0], x0, refl[1]))
                uid += 1
                items[i].append((cz, uid, 3, surf, x0, y0))
            sp_draw.append((sp, x0, y0, wpx, hpx, cz))

        # --- الرسم عمود عمود (من البعيد للقريب)
        for i in range(N):
            lst = items[i]
            if not lst:
                continue
            lst.sort(reverse=True)
            x = i * cw
            for it in lst:
                kind = it[2]
                if kind == 0:
                    self._wall(s, x, cw, it, horizon)
                elif kind == 1:
                    self._box(s, x, cw, it, px, py, horizon)
                elif kind == 2:
                    self._quad(s, x, cw, it, horizon)
                else:
                    surf, sx0, sy0 = it[3], it[4], it[5]
                    off = x - int(sx0)
                    sw_ = surf.get_width()
                    if 0 <= off < sw_:
                        s.blit(surf, (x, int(sy0)), (off, 0, min(cw, sw_ - off), surf.get_height()))

        self.last_sp = sp_draw
        # --- الضلمة والإضاءة
        self._lighting(s, G, lv, px, py, dx, dy, rx, ry, horizon, zwall, cw, light, glow, sp_draw)
        self.adapt((time.perf_counter() - t0) * 1000.0, dt)

    # ---------- الخلفية: سقف وأرض
    def _backdrop(self, s, horizon):
        SW, SH = self.SW, self.SH
        n = 14
        top = (58, 52, 56)
        mid = (26, 23, 26)
        if horizon > 0:
            for i in range(n):
                y0 = int(horizon * i / n)
                y1 = int(horizon * (i + 1) / n)
                c = _mix(top, mid, (i / (n - 1)) ** 0.8)
                s.fill(c, (0, y0, SW, y1 - y0 + 1))
        fl0 = (18, 14, 13)
        fl1 = (70, 54, 44)
        if horizon < SH:
            H = SH - horizon
            for i in range(n):
                y0 = horizon + int(H * i / n)
                y1 = horizon + int(H * (i + 1) / n)
                c = _mix(fl0, fl1, (i / (n - 1)) ** 1.3)
                s.fill(c, (0, y0, SW, y1 - y0 + 1))

    # ---------- الأرضية: بلاط حقيقي بمنظور
    def _clip_poly(self, pts):
        """pts = [(cx,cz)] بنقص اللي ورا الكاميرا (cz < NEAR)"""
        out = []
        n = len(pts)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            ina, inb = a[1] >= NEAR, b[1] >= NEAR
            if ina:
                out.append(a)
            if ina != inb:
                tt = (NEAR - a[1]) / (b[1] - a[1])
                out.append((a[0] + (b[0] - a[0]) * tt, NEAR))
        return out

    def _floor_poly(self, s, col, corners, px, py, dx, dy, rx, ry, horizon, outline=None, Z=0.0):
        pts = []
        for (X, Y) in corners:
            relx, rely = X - px, Y - py
            pts.append((relx * rx + rely * ry, relx * dx + rely * dy))
        if all(p[1] < NEAR for p in pts):
            return
        pts = self._clip_poly(pts)
        if len(pts) < 3:
            return
        SW, f = self.SW, self.f
        sp = []
        for (cx, cz) in pts:
            sp.append((max(-9000.0, min(9000.0, SW / 2.0 + cx / cz * f)), max(-9000.0, min(9000.0, horizon + (EYE - Z) / cz * f))))
        if max(p[0] for p in sp) < -20 or min(p[0] for p in sp) > SW + 20:
            return
        pygame.draw.polygon(s, col, sp)
        if outline:
            pygame.draw.polygon(s, outline, sp, 1)

    def _floor(self, s, G, lv, px, py, dx, dy, rx, ry, horizon):
        R = 11
        cx0, cy0 = int(px), int(py)
        tiles = []
        for ty in range(max(0, cy0 - R), min(lv.H, cy0 + R + 1)):
            row = lv.grid[ty]
            for tx in range(max(0, cx0 - R), min(lv.W, cx0 + R + 1)):
                if row[tx] == 1:
                    continue
                mx, my = tx + 0.5 - px, ty + 0.5 - py
                cz = mx * dx + my * dy
                if cz < -1.6:
                    continue
                d2 = mx * mx + my * my
                if d2 > R * R:
                    continue
                tiles.append((cz, tx, ty, d2))
        tiles.sort(reverse=True)
        occ = self._occ
        for cz, tx, ty, d2 in tiles:
            c = lv.floorc[ty][tx]
            v = (tx * 7 + ty * 13) % 5 * 3
            k = fog(math.sqrt(d2)) * 1.25
            if d2 < 30:                                 # ألواح الخشب بدرجات مختلفة + ظلال
                xs = ((0.0, 0.5), (0.5, 1.0)) if (occ and d2 < 16) else ((0.0, 1.0),)
                for qi_, (qa, qb) in enumerate(((0.0, 0.34), (0.34, 0.67), (0.67, 1.0))):
                    vv = ((tx * 5 + ty * 11 + qi_ * 7) % 4) * 5 - 6
                    for (xa, xb) in xs:
                        kk = k
                        if occ and self._floor_shadowed(tx + (xa + xb) / 2, ty + (qa + qb) / 2):
                            kk = k * 0.5
                        pc = _sh((c[0] + v + vv, c[1] + v + vv, c[2] + v + vv), kk)
                        self._floor_poly(s, pc, ((tx + xa, ty + qa), (tx + xb, ty + qa), (tx + xb, ty + qb), (tx + xa, ty + qb)),
                                         px, py, dx, dy, rx, ry, horizon, _sh(c, 0.3 * kk) if (d2 < 16 and xa == 0.0) else None)
            else:
                kk = k * 0.5 if (occ and d2 < 64 and self._floor_shadowed(tx + 0.5, ty + 0.5)) else k
                col = _sh((c[0] + v, c[1] + v, c[2] + v), kk)
                self._floor_poly(s, col, ((tx, ty), (tx + 1, ty), (tx + 1, ty + 1), (tx, ty + 1)), px, py, dx, dy, rx, ry,
                                 horizon, _sh(c, 0.35 * kk) if d2 < 64 else None)
        for (rx_, ry_, rw, rh, rc) in lv.rugs:
            mx, my = rx_ + rw / 2.0 - px, ry_ + rh / 2.0 - py
            d = math.hypot(mx, my)
            if d > R + 3:
                continue
            k = fog(d) * 1.2
            self._floor_poly(s, _sh(rc, k), ((rx_, ry_), (rx_ + rw, ry_), (rx_ + rw, ry_ + rh), (rx_, ry_ + rh)),
                             px, py, dx, dy, rx, ry, horizon, _sh((200, 170, 90), k * 0.5))
            e = 0.18
            self._floor_poly(s, _sh(rc, k * 0.72), ((rx_ + e, ry_ + e), (rx_ + rw - e, ry_ + e), (rx_ + rw - e, ry_ + rh - e),
                                                  (rx_ + e, ry_ + rh - e)), px, py, dx, dy, rx, ry, horizon)

    @staticmethod
    def _seg_entry(ox, oy, dx, dy, x0, y0, x1, y1):
        """الكسر s (0..1) اللي القطعة بتدخل منه المربع، أو None"""
        if abs(dx) < 1e-9:
            if ox < x0 or ox > x1:
                return None
            ta, tb = -1e30, 1e30
        else:
            inv = 1.0 / dx
            ta, tb = (x0 - ox) * inv, (x1 - ox) * inv
            if ta > tb:
                ta, tb = tb, ta
        if abs(dy) < 1e-9:
            if oy < y0 or oy > y1:
                return None
            ya, yb = -1e30, 1e30
        else:
            inv = 1.0 / dy
            ya, yb = (y0 - oy) * inv, (y1 - oy) * inv
            if ya > yb:
                ya, yb = yb, ya
        t1 = ta if ta > ya else ya
        t2 = tb if tb < yb else yb
        if t2 <= t1 or t1 < 0.02 or t1 > 0.985:
            return None
        return t1

    def _wall_shadow(self, Px, Py, Lx, Ly, occ):
        """أعلى ارتفاع على الحيطة واقع في ضل (من نور الكشاف)"""
        ddx, ddy = Px - Lx, Py - Ly
        best = 0.0
        for (x0, y0, x1, y1, hm) in occ:
            s_ = self._seg_entry(Lx, Ly, ddx, ddy, x0, y0, x1, y1)
            if s_ is None:
                continue
            zc = 1.15 + (hm - 1.15) / s_
            if zc > best:
                best = zc
        return min(best, WALL_H) if best > 0.05 else 0.0

    def _floor_shadowed(self, X, Y):
        Lx, Ly = self._L
        ddx, ddy = X - Lx, Y - Ly
        for (x0, y0, x1, y1, hm) in self._occ:
            s_ = self._seg_entry(Lx, Ly, ddx, ddy, x0, y0, x1, y1)
            if s_ is not None and 1.15 * (1.0 - s_) < hm:
                return True
        return False

    def _shadows(self, s, vis, lv, px, py, dx, dy, rx, ry, horizon):
        for (_a, _b, _c, _d, _c0, _c1, _bx, _qs, st, rc) in vis:
            if st in ('door', 'portrait', 'mirror'):
                continue
            x0, y0, x1, y1 = rc
            tx, ty = int((x0 + x1) / 2), int((y0 + y1) / 2)
            if not (0 <= tx < lv.W and 0 <= ty < lv.H):
                continue
            fc = lv.floorc[ty][tx]
            d = math.hypot((x0 + x1) / 2 - px, (y0 + y1) / 2 - py)
            e = 0.16
            self._floor_poly(s, _sh(fc, 0.3 * fog(d)), ((x0 - e, y0 - e), (x1 + e, y0 - e), (x1 + e, y1 + e), (x0 - e, y1 + e)),
                             px, py, dx, dy, rx, ry, horizon)

    def _ceiling(self, s, px, py, dx, dy, rx, ry, horizon, lv):
        """عوارض خشب في السقف (بتدّي إحساس بالعمق والارتفاع)"""
        R = 9
        cx0, cy0 = int(px), int(py)
        for gx in range((cx0 - R) // 3 * 3, cx0 + R + 1, 3):
            self._floor_poly(s, _sh((70, 52, 40), fog(abs(gx - px) + 3)), ((gx - 0.12, cy0 - R), (gx + 0.12, cy0 - R), (gx + 0.12, cy0 + R), (gx - 0.12, cy0 + R)),
                             px, py, dx, dy, rx, ry, horizon, None, WALL_H)
        for gy in range((cy0 - R) // 3 * 3, cy0 + R + 1, 3):
            self._floor_poly(s, _sh((62, 46, 36), fog(abs(gy - py) + 3)), ((cx0 - R, gy - 0.12), (cx0 + R, gy - 0.12), (cx0 + R, gy + 0.12), (cx0 - R, gy + 0.12)),
                             px, py, dx, dy, rx, ry, horizon, None, WALL_H)

    def _plank(self, s, col, x0, y0, x1, y1, px, py, dx, dy, rx, ry, horizon):
        a = ((x0 - px) * rx + (y0 - py) * ry, (x0 - px) * dx + (y0 - py) * dy)
        b = ((x1 - px) * rx + (y1 - py) * ry, (x1 - px) * dx + (y1 - py) * dy)
        if a[1] < NEAR and b[1] < NEAR:
            return
        if a[1] < NEAR:
            tt = (NEAR - a[1]) / (b[1] - a[1])
            a = (a[0] + (b[0] - a[0]) * tt, NEAR)
        elif b[1] < NEAR:
            tt = (NEAR - b[1]) / (a[1] - b[1])
            b = (b[0] + (a[0] - b[0]) * tt, NEAR)
        SW, f = self.SW, self.f
        def cl(v):
            return max(-9000.0, min(9000.0, v))
        pygame.draw.line(s, col, (cl(SW / 2.0 + a[0] / a[1] * f), cl(horizon + EYE / a[1] * f)),
                         (cl(SW / 2.0 + b[0] / b[1] * f), cl(horizon + EYE / b[1] * f)), 1)

    # ---------- قطع الأثاث اللي ظاهرة
    def _visible_objects(self, G, lv, px, py, dx, dy, rx, ry, N, cw, dt):
        out = []
        f, SW = self.f, self.SW
        for o in G.objs:
            r = o.rect
            x0, y0, x1, y1 = r.left / T, r.top / T, r.right / T, r.bottom / T
            mx, my = (x0 + x1) / 2 - px, (y0 + y1) / 2 - py
            if mx * mx + my * my > 17 * 17:
                continue
            st = style_of(o)
            if st == 'door' and False:
                continue
            # نطاق الأعمدة
            cmin, cmax = 1e9, -1e9
            anyfront = False
            behind = 0
            for (X, Y) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                relx, rely = X - px, Y - py
                cz = relx * dx + rely * dy
                cx = relx * rx + rely * ry
                if cz < 0.2:
                    behind += 1
                    continue
                anyfront = True
                sx = SW / 2.0 + cx / cz * f
                cmin, cmax = min(cmin, sx), max(cmax, sx)
            if behind == 4:
                continue
            if behind:
                c0, c1 = 0, N
            else:
                c0 = max(0, int(cmin // cw) - 1)
                c1 = min(N, int(cmax // cw) + 2)
                if c1 <= c0:
                    continue
            # حالة الفتح
            fr_ch = self.front.get(o.id)
            if fr_ch is None:
                fr_ch = self.front[o.id] = infer_front(lv, o, st)
            if st == 'door':
                tgt = 1.0 if (o.id in G.opened or not o.solid) else 0.0
            else:
                pk = getattr(G, 'fp_peek', {}).get(o.id, 0.0)
                opened = (o.id in G.done and st in OPENABLE) or (st in OPENABLE and pk > G.t)
                tgt = 1.0 if opened else 0.0
            p = self.anim.get(o.id, tgt if st == 'door' else 0.0)
            step = dt * 2.2
            if abs(tgt - p) <= step:
                np_ = tgt
            else:
                np_ = p + step if tgt > p else p - step
            if p <= 0.02 < np_:
                cb = getattr(G, 'fp_event', None)
                if cb:
                    cb(o, 'open')
            elif p >= 0.98 > np_ and tgt == 0.0:
                cb = getattr(G, 'fp_event', None)
                if cb:
                    cb(o, 'close')
            self.anim[o.id] = np_
            fr = Frame(x0, y0, x1, y1, fr_ch)
            if st == 'door':
                wallc = self.wall_style(self._room_color(lv, o))['paper']
                boxes, quads = build_door(o, (x0, y0, x1, y1), np_, wallc)
            else:
                boxes, quads = build_parts(o, fr, np_, G)
            # صندوق إحاطة (لو في حاجة بتبرز برّه الـ rect زي الدُرج المسحوب)
            bx0 = min([x0] + [b.x0 for b in boxes] + [min(q.ax, q.bx) for q in quads])
            by0 = min([y0] + [b.y0 for b in boxes] + [min(q.ay, q.by) for q in quads])
            bx1 = max([x1] + [b.x1 for b in boxes] + [max(q.ax, q.bx) for q in quads])
            by1 = max([y1] + [b.y1 for b in boxes] + [max(q.ay, q.by) for q in quads])
            if bx0 < x0 - 0.01 or by0 < y0 - 0.01 or bx1 > x1 + 0.01 or by1 > y1 + 0.01:
                c0, c1 = 0, N
            out.append((bx0, by0, bx1, by1, c0, c1, boxes, quads, st, (x0, y0, x1, y1)))
        return out

    def _room_color(self, lv, o):
        r = o.rect
        for (tx, ty) in ((int(r.left // T) - 1, int(r.centery // T)), (int(r.right // T), int(r.centery // T)),
                         (int(r.centerx // T), int(r.top // T) - 1), (int(r.centerx // T), int(r.bottom // T))):
            if 0 <= tx < lv.W and 0 <= ty < lv.H and lv.grid[ty][tx] == 0:
                return lv.floorc[ty][tx]
        return (80, 66, 56)

    # ---------- تقاطعات
    @staticmethod
    def _ray_aabb(ox, oy, rdx, rdy, x0, y0, x1, y1, tmax_lim):
        if abs(rdx) < 1e-9:
            if ox < x0 or ox > x1:
                return None
            txa, txb = -1e30, 1e30
        else:
            inv = 1.0 / rdx
            txa, txb = (x0 - ox) * inv, (x1 - ox) * inv
            if txa > txb:
                txa, txb = txb, txa
        if abs(rdy) < 1e-9:
            if oy < y0 or oy > y1:
                return None
            tya, tyb = -1e30, 1e30
        else:
            inv = 1.0 / rdy
            tya, tyb = (y0 - oy) * inv, (y1 - oy) * inv
            if tya > tyb:
                tya, tyb = tyb, tya
        if txa > tya:
            t1, axis = txa, 0
        else:
            t1, axis = tya, 1
        t2 = txb if txb < tyb else tyb
        if t2 <= t1 or t2 <= NEAR or t1 >= tmax_lim:
            return None
        if t1 < NEAR:
            return None
        return (t1, t2, axis)

    @staticmethod
    def _ray_seg(ox, oy, rdx, rdy, ax, ay, bx, by):
        ex, ey = bx - ax, by - ay
        den = rdx * ey - rdy * ex
        if abs(den) < 1e-9:
            return None
        awx, awy = ax - ox, ay - oy
        t = (awx * ey - awy * ex) / den
        u = (awx * rdy - awy * rdx) / den
        if t < NEAR or u < 0.0 or u > 1.0:
            return None
        return (t, u, den > 0)

    # ---------- رسم عناصر العمود
    def _wall(self, s, x, cw, it, horizon):
        _t, _u, _k, side, wu, fc, mx, my, zc = it
        t = _t
        f = self.f
        st = self.wall_style(fc)
        k = fog(t) * (0.78 if side == 0 else 1.0)
        k *= 0.965 + 0.07 * ((((int(wu * 37) * 40503) >> 5) & 15) / 15.0)       # حبيبات الدهان
        inv = f / t
        u = wu - math.floor(wu)
        SH_ = self.SH

        def Y(z):
            return int(horizon + (EYE - z) * inv)
        y_top, y_bot = Y(WALL_H), Y(0.0)
        if y_bot < 0 or y_top > SH_:
            return

        def band(z0, z1, col, km=1.0):
            if z1 <= z0:
                return
            if zc > z0:                                                       # جزء واقع في الضل
                zm = z1 if z1 < zc else zc
                ya, yb = Y(zm), Y(z0)
                if yb > ya:
                    s.fill(_sh(col, k * km * 0.5), (x, ya, cw, yb - ya))
                if z1 > zm:
                    ya, yb = Y(z1), Y(zm)
                    if yb > ya:
                        s.fill(_sh(col, k * km), (x, ya, cw, yb - ya))
            else:
                ya, yb = Y(z1), Y(z0)
                if yb > ya:
                    s.fill(_sh(col, k * km), (x, ya, cw, yb - ya))
        band(0.0, 0.14, st['base'])                                          # بوردة الأرض
        band(0.14, 0.95, st['wain'])
        band(0.14, 0.34, st['wain'], 0.82)                                   # ضل قريب من الأرض
        pu = (u * 2.0) % 1.0
        if pu < 0.04 or pu > 0.96:                                           # فواصل ألواح الدادو
            band(0.2, 0.9, st['wain_dk'])
        else:
            band(0.2, 0.22, st['wain_dk'])
            band(0.88, 0.9, st['wain_lt'])
            band(0.52, 0.54, st['wain_lt'], 0.9)
        band(0.95, 1.0, st['rail'])                                          # الشريط
        pp = st['paper'] if (int(wu * 6.0) & 1) == 0 else st['paper2']
        band(1.0, 2.5, pp)                                                   # ورق الحيطان
        if (int(wu * 6.0) & 1) == 0 and 0.35 < (wu * 6.0) % 1.0 < 0.65:      # زخرفة صغيرة في الورق
            for zz in (1.3, 1.75, 2.2):
                band(zz, zz + 0.07, pp, 1.14)
        band(1.0, 1.35, pp, 0.93)                                            # تدرّج بسيط
        band(2.26, 2.5, pp, 0.86)                                            # ضل تحت السقف
        band(2.4, 2.5, pp, 0.76)
        band(2.5, WALL_H, st['crown'])                                       # كرنيش
        band(2.5, 2.54, st['crown'], 1.3)
        d = self.deco_of(mx, my, side)
        if d == 'frame' and 0.28 < u < 0.72:
            band(1.15, 1.95, (92, 66, 30))
            band(1.15, 1.19, (150, 112, 52))
            if 0.33 < u < 0.67:
                band(1.22, 1.88, (26, 24, 30) if (mx + my) % 2 else (46, 40, 34))
                if 0.42 < u < 0.58:
                    band(1.5, 1.75, (150, 130, 110))
        elif d == 'window' and 0.1 < u < 0.9:
            ke = 0.75 + 0.25 * k

            def emit(z0, z1, col):                                           # الزجاج منوّر بنفسه (القمر)
                ya, yb = Y(z1), Y(z0)
                if yb > ya:
                    s.fill(_sh(col, ke), (x, ya, cw, yb - ya))
            if 0.18 < u < 0.82:
                band(0.95, 2.2, (206, 202, 192))
                if 0.22 < u < 0.78:
                    emit(1.0, 2.15, (36, 52, 98))
                    emit(1.6, 2.15, (52, 72, 120))
                    if abs(u - 0.5) < 0.02:
                        band(1.0, 2.15, (206, 202, 192))
                    band(1.55, 1.6, (206, 202, 192))
                band(0.9, 0.95, (190, 186, 176))                              # عتبة الشباك
            fold = 1.0 if (int(wu * 55) & 1) else 0.8                          # ستارة
            cc = (128, 40, 50) if (mx + my) % 2 else (150, 136, 108)
            if u < 0.2 or u > 0.8:
                band(0.8, 2.34, cc, fold)
                band(2.28, 2.34, cc, 0.6)
        if self.fx >= 2 and t < 12.0:                                        # انعكاس الحيطة على الأرضية اللامعة
            Y0 = y_bot
            if Y0 < SH_:
                flc = _sh((60, 44, 36), fog(t))
                for (z0, z1, col, m1) in ((0.0, 0.14, st['base'], 0.7), (0.14, 0.5, st['wain'], 0.72), (0.5, 0.95, st['wain'], 0.86),
                                          (0.95, 1.0, st['rail'], 0.86)):
                    ya, yb = 2 * Y0 - Y(z0), 2 * Y0 - Y(z1)
                    if yb > ya and ya < SH_:
                        s.fill(_mix(_sh(col, k), flc, m1), (x, ya, cw, yb - ya))

    def _box(self, s, x, cw, it, px, py, horizon):
        ts, _u, _k, b, t1, t2, axis, rdx, rdy = it
        f = self.f
        if axis == 0:
            face = 'W' if rdx > 0 else 'E'
            hy = py + rdy * t1
            hx = b.x0 if rdx > 0 else b.x1
        else:
            face = 'N' if rdy > 0 else 'S'
            hx = px + rdx * t1
            hy = b.y0 if rdy > 0 else b.y1
        W, H = b.x1 - b.x0, b.y1 - b.y0
        if face == 'S':
            u = (hx - b.x0) / W if W else 0.5
        elif face == 'N':
            u = (b.x1 - hx) / W if W else 0.5
        elif face == 'E':
            u = (b.y1 - hy) / H if H else 0.5
        else:
            u = (hy - b.y0) / H if H else 0.5
        k = fog(t1) * (0.8 if axis == 0 else 1.0)
        inv = f / t1
        ytop = int(horizon + (EYE - b.z1) * inv)
        ybot = int(horizon + (EYE - b.z0) * inv)
        SH = self.SH
        if EYE > b.z1:                                       # السطح العلوي
            yfar = int(horizon + (EYE - b.z1) * f / t2)
            if yfar < ytop:
                tm = (t1 + t2) * 0.5
                if b.topf:
                    tc = b.topf(px + rdx * tm, py + rdy * tm)
                else:
                    tc = b.ct
                if ytop > 0 and yfar < SH:
                    s.fill(_sh(tc, fog(tm) * 1.05), (x, yfar, cw, ytop - yfar + 1))
        if ybot <= ytop or ybot < 0 or ytop > SH:
            return
        isf = (face == b.face)
        col = b.cf if isf else b.cs
        hh = ybot - ytop
        s.fill(_sh(col, k), (x, ytop, cw, hh))
        if hh > 12:
            s.fill(_sh(col, k * 0.8), (x, ybot - int(hh * 0.18), cw, int(hh * 0.18)))   # ضل تحت
            s.fill(_sh(col, k * 1.3), (x, ytop, cw, 2))                               # حرف فاتح فوق
        if u < 0.03 or u > 0.97:
            s.fill(_sh(col, k * 0.68), (x, ytop, cw, hh))                              # ركن القطعة
        if self.fx >= 2 and b.z0 < 0.7 and t1 < 11.0:                                  # انعكاس على الأرضية
            Y0 = int(horizon + EYE * inv)
            zt = b.z1 if b.z1 < 1.25 else 1.25
            ra, rb = 2 * Y0 - int(horizon + (EYE - b.z0) * inv), 2 * Y0 - int(horizon + (EYE - zt) * inv)
            if rb > ra and ra < SH:
                flc = _sh((60, 44, 36), fog(t1))
                hr = rb - ra
                s.fill(_mix(_sh(col, k), flc, 0.72), (x, ra, cw, hr // 2 + 1))
                s.fill(_mix(_sh(col, k), flc, 0.86), (x, ra + hr // 2, cw, hr - hr // 2))
        if b.emit == 'mirror' and isf and self.fx >= 3 and self._mirror_ok and 0.1 < u < 0.9 and t1 < 12.0:
            try:
                self._mirror_col(s, x, cw, b, face, hx, hy, rdx, rdy, t1, horizon)
                return
            except Exception:
                self._mirror_ok = False
        if isf and b.panels:
            self._panels(s, x, cw, b.panels, u, horizon, inv, k)

    def _panels(self, s, x, cw, panels, u, horizon, inv, k):
        for pn in panels:
            if pn[0] <= u < pn[1]:
                ya = int(horizon + (EYE - pn[3]) * inv)
                yb = int(horizon + (EYE - pn[2]) * inv)
                if yb <= ya:
                    continue
                if len(pn) > 5 and pn[5] == 'books':
                    c = _bookcol((u - pn[0]) / (pn[1] - pn[0]), pn[6])
                else:
                    c = pn[4]
                s.fill(_sh(c, k), (x, ya, cw, yb - ya))

    def _quad(self, s, x, cw, it, horizon):
        t, _u, _k, q, su, front = it
        inv = self.f / t
        ytop = int(horizon + (EYE - q.z1) * inv)
        ybot = int(horizon + (EYE - q.z0) * inv)
        if ybot <= ytop or ybot < 0 or ytop > self.SH:
            return
        k = fog(t) * 0.9
        col = q.c if front else q.c2
        s.fill(_sh(col, k), (x, ytop, cw, ybot - ytop))
        if q.panels:
            self._panels(s, x, cw, q.panels, su if front else 1.0 - su, horizon, inv, k)

    # ---------- المراية: تتبّع شعاع منعكس
    def _trace_wall(self, lv, ox, oy, rdx, rdy):
        grid, GW, GH = lv.grid, lv.W, lv.H
        mx, my = int(ox), int(oy)
        ddx = abs(1.0 / rdx) if rdx else 1e30
        ddy = abs(1.0 / rdy) if rdy else 1e30
        if rdx < 0:
            stx, sdx = -1, (ox - mx) * ddx
        else:
            stx, sdx = 1, (mx + 1.0 - ox) * ddx
        if rdy < 0:
            sty, sdy = -1, (oy - my) * ddy
        else:
            sty, sdy = 1, (my + 1.0 - oy) * ddy
        side = 0
        for _ in range(40):
            if sdx < sdy:
                sdx += ddx
                mx += stx
                side = 0
            else:
                sdy += ddy
                my += sty
                side = 1
            if mx < 0 or my < 0 or mx >= GW or my >= GH or grid[my][mx] == 1:
                t = (sdx - ddx) if side == 0 else (sdy - ddy)
                wu = (oy + t * rdy) if side == 0 else (ox + t * rdx)
                pcx, pcy = (mx - stx, my) if side == 0 else (mx, my - sty)
                fc = lv.floorc[pcy][pcx] if (0 <= pcx < GW and 0 <= pcy < GH) else (60, 50, 44)
                return (max(t, 0.02), side, wu, fc, mx, my)
            if (sdx if sdx < sdy else sdy) > 14:
                return None
        return None

    def _mirror_col(self, s, x, cw, b, face, hx, hy, rdx, rdy, t1, horizon):
        f = self.f
        if face in ('N', 'S'):
            rdx2, rdy2 = rdx, -rdy
        else:
            rdx2, rdy2 = -rdx, rdy
        nx, ny = {'N': (0, -1), 'S': (0, 1), 'E': (1, 0), 'W': (-1, 0)}[face]
        ox, oy = hx + nx * 0.02, hy + ny * 0.02
        inv = f / t1
        ymt = int(horizon + (EYE - 2.03) * inv)
        ymb = int(horizon + (EYE - 0.22) * inv)
        if ymb <= ymt:
            return
        s = self._surf
        s.set_clip((x, max(0, ymt), cw, min(self.SH, ymb) - max(0, ymt)))
        try:
            s.fill((46, 44, 52), (x, ymt, cw, ymb - ymt))
            s.fill((26, 24, 30), (x, ymt, cw, max(1, int((ymb - ymt) * 0.12))))
            wl = self._trace_wall(self._lv, ox, oy, rdx2, rdy2)
            tw = wl[0] if wl else 30.0
            items = []
            if wl:
                items.append((t1 + tw, 0, 0, wl[1], wl[2], wl[3], wl[4], wl[5], 0.0))
            uid = 1
            for v in self._vis:
                bl = v[6]
                if b in bl:
                    continue
                for bb in bl:
                    r = self._ray_aabb(ox, oy, rdx2, rdy2, bb.x0, bb.y0, bb.x1, bb.y1, tw)
                    if r:
                        items.append((t1 + r[0], uid, 1, bb, t1 + r[0], t1 + r[1], r[2], rdx2, rdy2))
                        uid += 1
            items.sort(reverse=True)
            pxe, pye = ox - rdx2 * t1, oy - rdy2 * t1
            for it in items:
                if it[2] == 0:
                    self._wall(s, x, cw, it, horizon)
                else:
                    self._box(s, x, cw, it, pxe, pye, horizon)
            rr = rdx2 * rdx2 + rdy2 * rdy2
            for sp in self._mir_sprites:                                      # الوحش اللي وراك بيبان في المراية
                if sp.get('floor'):
                    continue
                wx, wy = sp['x'] - ox, sp['y'] - oy
                tp = (wx * rdx2 + wy * rdy2) / rr
                if tp < 0.1 or tp >= tw:
                    continue
                cr = (rdx2 * wy - rdy2 * wx) / math.sqrt(rr)
                img = sp['img']
                iw, ih = img.get_size()
                hw = sp['h'] * iw / float(ih) / 2.0
                if abs(cr) >= hw:
                    continue
                D = t1 + tp
                hpx = int(sp['h'] * f / D)
                if hpx < 4 or hpx > 2000:
                    continue
                ix = max(0, min(iw - 1, int((0.5 + cr / (2 * hw)) * iw)))
                sc = pygame.transform.scale(img.subsurface((ix, 0, 1, ih)), (cw, hpx))
                a = sp.get('alpha', 255)
                if a < 255:
                    sc.set_alpha(a)
                ybot = horizon + (EYE - sp.get('z0', 0.0)) * f / D
                s.blit(sc, (x, int(ybot) - hpx))
        finally:
            s.set_clip(None)

    # ---------- Sprites
    def _sprite_screen(self, sp, px, py, dx, dy, rx, ry, horizon):
        relx, rely = sp['x'] - px, sp['y'] - py
        cz = relx * dx + rely * dy
        if cz < 0.25 or cz > 18:
            return None
        cx = relx * rx + rely * ry
        f = self.f
        img = sp['img']
        iw, ih = img.get_size()
        if sp.get('floor'):                                  # بصمات وكتابة على الأرض (بتتضغط بالمنظور)
            if cz < 0.7:
                return None
            wpx = sp['w'] * f / cz
            hpx = max(2.0, sp['h'] * f * EYE / (cz * cz))
            if wpx < 3 or wpx > 2200:
                return None
        else:
            hpx = sp['h'] * f / cz
            if hpx < 3 or hpx > 2200:
                return None
            wpx = hpx * iw / float(ih)
        sx = self.SW / 2.0 + cx / cz * f
        if sx + wpx / 2 < 0 or sx - wpx / 2 > self.SW:
            return None
        wpx_i, hpx_i = max(1, int(wpx)), max(1, int(hpx))
        if wpx_i > 2600:
            return None
        key = (id(img), wpx_i // 2, hpx_i // 2)
        surf = pygame.transform.scale(img, (wpx_i, hpx_i))
        a = sp.get('alpha', 255)
        if a < 255:
            surf.set_alpha(max(0, min(255, int(a))))
        refl = None
        if sp.get('floor'):
            ycenter = horizon + EYE * f / cz
            y0 = ycenter - hpx_i / 2.0
        else:
            ybot = horizon + (EYE - sp.get('z0', 0.0)) * f / cz
            y0 = ybot - hpx_i
            if self.fx >= 2 and cz < 11 and a > 20:                       # انعكاس على الأرضية
                try:
                    rs = pygame.transform.flip(surf, False, True)
                    rs.set_alpha(int(a * 0.30))
                    Y0 = horizon + EYE * f / cz
                    refl = (rs, 2 * Y0 - ybot)
                except Exception:
                    refl = None
        return surf, sx - wpx_i / 2.0, y0, wpx_i, hpx_i, cz, refl

    # ---------- الإضاءة
    def _lighting(self, s, G, lv, px, py, dx, dy, rx, ry, horizon, zwall, cw, light, glow, sp_draw):
        SW, SH, f = self.SW, self.SH, self.f
        if self.debug:
            return
        dk = G.dark
        dk.fill((0, 0, 8, 255 if G.blackout > 0 else 214))
        if G.blackout <= 0:
            for ci, (tx, ty) in enumerate(lv.candles):
                if ci in G.out_c:
                    continue
                X, Y = tx + 0.5, ty + 0.5
                pr = self.proj(X, Y, 1.0, px, py, dx, dy, rx, ry, horizon)
                if not pr:
                    continue
                sx, sy, cz = pr
                if cz > 14:
                    continue
                col = int(sx // cw)
                if 0 <= col < len(zwall) and zwall[col] < cz - 0.5:
                    continue
                r = int(max(60, min(420, f * 2.4 / cz)) * (1 + 0.06 * math.sin(G.t * 9 + tx)))
                light(dk, int(sx), int(sy), r, 215)
        tv = 1.0 - 0.35 * max(0.0, (G.fear - 45) / 55)
        light(dk, SW // 2, SH - 20, int(300 * tv), 175)                       # نور خفيف حوالين رجلك
        if G.flash_ok():
            m = tv
            near_g = any(g['a'] > 0.3 and math.hypot(g['x'] - G.px, g['y'] - G.py) < 230 for g in G.ghosts)
            if G.battery < 20 or G.fear > 70 or near_g:
                m = tv * G.rand_choice((1, 1, 1, 0.85, 0.55))
            light(dk, SW // 2, horizon + 30, int(500 * m), 214)
            light(dk, SW // 2, horizon + 30, int(290 * m), 240)
        s.blit(dk, (0, 0))
        if G.blackout <= 0:
            if self._grade is None:                                      # تدرّج لوني سينمائي (أزرق خفيف)
                self._grade = pygame.Surface((SW, SH))
                self._grade.fill((22, 32, 62))
                self._grade.set_alpha(20)
            s.blit(self._grade, (0, 0))
            if G.flash_ok():                                             # غبار بيطير في شعاع الكشاف
                cxm, cym = SW / 2.0, horizon + 30
                tt = G.t
                for (ux, uy, sp_, ph) in self.dust:
                    mxp = (ux * SW + tt * 9 * sp_ + math.sin(tt * 0.5 + ph) * 14) % SW
                    myp = (uy * SH + tt * 4 * sp_ + math.cos(tt * 0.7 + ph) * 10) % SH
                    dd = math.hypot(mxp - cxm, myp - cym)
                    if dd < 330:
                        a_ = int(210 * (1 - dd / 330.0) * (0.6 + 0.4 * math.sin(tt * 2 + ph)))
                        if a_ > 20:
                            s.fill((a_, a_, int(a_ * 0.92)), (int(mxp), int(myp), 2, 2))
        # --- لهب الشموع (بيشع فوق الضلمة)
        if G.blackout <= 0:
            for ci, (tx, ty) in enumerate(lv.candles):
                if ci in G.out_c:
                    continue
                pr = self.proj(tx + 0.5, ty + 0.5, 1.12, px, py, dx, dy, rx, ry, horizon)
                if not pr:
                    continue
                sx, sy, cz = pr
                col = int(sx // cw)
                if cz > 14 or (0 <= col < len(zwall) and zwall[col] < cz - 0.2):
                    continue
                fl = max(2, int(f * 0.05 / cz))
                glow(s, int(sx), int(sy), max(10, int(f * 0.28 / cz)), (255, 170, 60), 110)
                pygame.draw.ellipse(s, (255, 214, 120), (int(sx) - fl // 2, int(sy) - fl, fl, int(fl * 1.7)))
        mfl = locals().get('m', 0.0) if G.flash_ok() else 0.0
        # --- عيون الوحوش
        for (sp, x0, y0, wpx, hpx, cz) in sp_draw:
            eyes = sp.get('eyes')
            if not eyes:
                continue
            for (fx_, fy_) in eyes:
                ex, ey = int(x0 + fx_ * wpx), int(y0 + fy_ * hpx)
                col = int(ex // cw)
                if 0 <= col < len(zwall) and zwall[col] < cz:
                    continue
                R = max(6, int(hpx * 0.075))
                glow(s, ex, ey, R, sp.get('ecol', (255, 40, 30)), min(255, int(sp.get('epow', 150))))
        if G.blackout <= 0:
            self._post(s, G, horizon, mfl)

    def project(self, G, X, Y, Z):
        """نقطة في العالم (بلاطات) -> (x, y, عمق) على الشاشة، أو None لو ورا الكاميرا"""
        a = G.ang
        dx, dy = math.cos(a), math.sin(a)
        return self.proj(X, Y, Z, G.px / T, G.py / T, dx, dy, -dy, dx, self.horizon)

    # ---------- مؤثرات ما بعد الرسم: شعاع الكشاف + التوهّج (Bloom)
    def _post(self, s, G, horizon, mfl):
        SW, SH = self.SW, self.SH
        try:
            if mfl > 0 and self.fx >= 3:                                  # شعاع الكشاف في الجو (ضباب/غبار)
                if self._beam is None:
                    self._beam = pygame.Surface((SW // 8, SH // 8))
                    self._big2 = pygame.Surface((SW, SH))
                b = self._beam
                b.fill((0, 0, 0))
                hx, hy = (SW - 118) / 8.0, (SH - 130) / 8.0
                tx, ty = SW / 16.0 + 4, (horizon + 25) / 8.0
                ax, ay = tx - hx, ty - hy
                ln = math.hypot(ax, ay) or 1.0
                nx, ny = -ay / ln, ax / ln
                for wd, col in ((190, (6, 6, 5)), (140, (9, 9, 7)), (95, (13, 13, 10)), (55, (17, 17, 13))):
                    w4 = wd * mfl / 8.0
                    pygame.draw.polygon(b, col, [(hx - nx * 2, hy - ny * 2), (hx + nx * 2, hy + ny * 2),
                                                (tx + nx * w4, ty + ny * w4), (tx - nx * w4, ty - ny * w4)])
                try:
                    pygame.transform.smoothscale(b, (SW, SH), self._big2)
                    big = self._big2
                except Exception:
                    big = pygame.transform.smoothscale(b, (SW, SH))
                s.blit(big, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            if self._bloom_ok and self.fx >= 1:                           # توهّج الحاجات المنوّرة (شموع، شبابيك، كشاف)
                if self._small is None:
                    self._small = pygame.Surface((SW // 6, SH // 6))
                    self._big = pygame.Surface((SW, SH))
                sm = self._small
                try:
                    pygame.transform.smoothscale(s, sm.get_size(), sm)
                except Exception:
                    sm = pygame.transform.smoothscale(s, (SW // 6, SH // 6))
                sm.fill((58, 58, 58), special_flags=pygame.BLEND_RGB_SUB)
                try:
                    pygame.transform.smoothscale(sm, (SW, SH), self._big)
                    big = self._big
                except Exception:
                    big = pygame.transform.smoothscale(sm, (SW, SH))
                s.blit(big, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        except Exception:
            self._bloom_ok = False

    # ---------- اختيار القطعة اللي اللاعب بيبصلها
    def pick(self, G):
        px, py = G.px / T, G.py / T
        rdx, rdy = math.cos(G.ang), math.sin(G.ang)
        best, bt = None, REACH
        for o in G.objs:
            if not o.can:
                continue
            r = o.rect
            h = self._ray_aabb(px, py, rdx, rdy, r.left / T - 0.12, r.top / T - 0.12, r.right / T + 0.12, r.bottom / T + 0.12, bt)
            if h is None:
                # الراي ممكن يبدأ جوه المنطقة الموسّعة
                x0, y0, x1, y1 = r.left / T - 0.12, r.top / T - 0.12, r.right / T + 0.12, r.bottom / T + 0.12
                if x0 <= px <= x1 and y0 <= py <= y1:
                    h = (0.0, 0.0, 0)
            if h is not None and h[0] < bt:
                best, bt = o, h[0]
        return best

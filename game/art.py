"""All graphics are drawn by code, so the game needs no image files."""
import json
import math
import os
import random

import pygame

import data as D
import paths

OUTLINE = (44, 32, 26)
_cache = {}
SCALE = 1      # how many screen pixels make one canvas pixel
HIRES = {}     # id of a canvas image: the same image at full screen resolution
_sharpening = False


def set_scale(scale):
    """A new screen size: every image is made again at the new resolution."""
    global SCALE
    if scale != SCALE:
        SCALE = scale
        _cache.clear()
        HIRES.clear()


# ---- remembering drawings ---------------------------------------------------
def cached(fn):
    """Decorator: remember what a drawing function returned for these arguments, so it is drawn only once."""
    def wrapper(*args):
        """Return the remembered picture, drawing it the first time."""
        key = (fn.__name__,) + args
        if key not in _cache:
            _cache[key] = fn(*args)
        return _cache[key]
    return wrapper


def sized(*sizes):
    """Like cached, for an image whose size is in these arguments. It is also
    drawn at full screen resolution, so that it stays sharp when scaled up."""
    def decorate(fn):
        """Wrap a drawing function so it also gets a sharp version at screen resolution."""
        plain = cached(fn)

        def wrapper(*args):
            """Draw at canvas size, and remember a sharp full-screen copy for Screen.blit."""
            global _sharpening
            new = (fn.__name__,) + args not in _cache
            result = plain(*args)
            if new and SCALE != 1 and not _sharpening and result is not None:
                image = result[0] if isinstance(result, tuple) else result
                _sharpening = True
                try:
                    if sizes:
                        big = tuple(round(a * SCALE) if i in sizes else a for i, a in enumerate(args))
                        sharp = fn(*big)
                        HIRES[id(image)] = sharp[0] if isinstance(sharp, tuple) else sharp
                    else:
                        w, h = image.get_size()
                        HIRES[id(image)] = pygame.transform.smoothscale(image, (round(w * SCALE), round(h * SCALE)))
                finally:
                    _sharpening = False
            return result
        return wrapper
    return decorate


# ---- drawing helpers --------------------------------------------------------
def shade(color, factor):
    """A color made darker (factor < 1) or lighter (factor > 1)."""
    return tuple(max(0, min(255, int(c * factor))) for c in color[:3])


def poly(surf, color, points, outline=True):
    """A filled polygon with an optional dark outline."""
    pygame.draw.polygon(surf, color, points)
    if outline:
        pygame.draw.polygon(surf, OUTLINE, points, 1)


# ---- resources --------------------------------------------------------------
RES_COLORS = {
    "wood": (168, 108, 58), "stone": (160, 160, 168), "food": (226, 74, 58),
    "iron": (104, 122, 142), "herbs": (84, 178, 86), "amber": (240, 160, 40),
    "pearl": (238, 232, 246), "crystal": (108, 220, 240), "mithril": (176, 160, 250),
    "relic": (216, 90, 170), "gold": (250, 204, 60),
}


def asset(*parts):
    """Load an image from the assets folder, or None if it is missing."""
    path = os.path.join(ROOT, *parts)
    if not os.path.exists(path):
        return None
    return prepared(pygame.image.load(path))


def prepared(image):
    """Faster to draw, when pygame knows the screen format."""
    try:
        return image.convert_alpha()
    except pygame.error:
        return image.convert(32, pygame.SRCALPHA) if image.get_bitsize() != 32 else image


def fill_size(image, w, h):
    """Cover the size without stretching: the sides or the top are cut off."""
    iw, ih = image.get_size()
    scale = max(w / iw, h / ih)
    cw, ch = max(1, round(w / scale)), max(1, round(h / scale))
    part = image.subsurface(((iw - cw) // 2, (ih - ch) // 2, cw, ch))
    return pygame.transform.smoothscale(part, (w, h))


@sized(1)
def ui_icon(name, size):
    """An icon from assets/icons at this size, or None."""
    image = asset("icons", f"{name}.png")
    return pygame.transform.smoothscale(image, (size, size)) if image else None


def mouse_cursor():
    """The pointer from the texture pack, or None without art."""
    image = asset("ui", "cursor.png")
    if not image:
        return None
    small = pygame.transform.smoothscale(image, (16, 16 * image.get_height() // image.get_width()))
    return pygame.cursors.Cursor((1, 1), small)


@sized(1)
def turn_face(team, size):
    """The knight's face that marks whose turn it is, or None without art."""
    image = asset("ui", f"turn_{team}.png")
    return pygame.transform.smoothscale(image, (size, size * image.get_height() // image.get_width())) if image else None


@sized(1)
def faded_icon(res, size):
    """A pale resource icon that keeps its transparency."""
    image = resource_icon(res, size).copy()
    image.fill((255, 255, 255, 70), special_flags=pygame.BLEND_RGBA_MULT)
    return image


@sized(1)
def resource_icon(res, size):
    """The icon of a resource, or a little drawing of it if the image is missing."""
    image = ui_icon(res, size)
    if image:
        return image
    scale = 4
    n = size * scale
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    c = RES_COLORS[res]
    dark = shade(c, 0.6)
    light = shade(c, 1.3)
    line = max(2, n // 18)
    m = n // 2

    def outlined(points):
        """A filled shape with a dark outline."""
        pygame.draw.polygon(s, c, points)
        pygame.draw.polygon(s, OUTLINE, points, line)

    if res == "wood":
        rect = pygame.Rect(n * .12, n * .32, n * .76, n * .36)
        pygame.draw.rect(s, c, rect, border_radius=n // 8)
        pygame.draw.rect(s, OUTLINE, rect, line, border_radius=n // 8)
        end = pygame.Rect(n * .66, n * .32, n * .24, n * .36)
        pygame.draw.ellipse(s, (226, 184, 130), end)
        pygame.draw.ellipse(s, OUTLINE, end, line)
    elif res == "stone":
        outlined([(n*.15, n*.72), (n*.25, n*.32), (n*.55, n*.2), (n*.85, n*.42), (n*.82, n*.75), (n*.45, n*.84)])
        pygame.draw.line(s, dark, (n*.3, n*.45), (n*.55, n*.6), line)
    elif res == "food":
        pygame.draw.circle(s, c, (m, int(n*.57)), int(n*.32))
        pygame.draw.circle(s, OUTLINE, (m, int(n*.57)), int(n*.32), line)
        pygame.draw.line(s, (90, 60, 30), (m, int(n*.28)), (int(n*.56), int(n*.12)), line * 2)
        pygame.draw.ellipse(s, (90, 180, 80), (n*.56, n*.12, n*.26, n*.15))
    elif res == "iron":
        outlined([(n*.1, n*.68), (n*.28, n*.34), (n*.9, n*.34), (n*.72, n*.68)])
        poly_top = [(n*.28, n*.34), (n*.38, n*.26), (n*.96, n*.26), (n*.9, n*.34)]
        pygame.draw.polygon(s, light, poly_top)
        pygame.draw.polygon(s, OUTLINE, poly_top, line)
    elif res == "herbs":
        pygame.draw.line(s, shade(c, .5), (m, n*.9), (m, n*.3), line * 2)
        for dx, y in ((-.26, .4), (.26, .4), (-.24, .62), (.24, .62)):
            rect = pygame.Rect(0, 0, n*.34, n*.2)
            rect.center = (m + n * dx, n * y)
            pygame.draw.ellipse(s, c, rect)
            pygame.draw.ellipse(s, OUTLINE, rect, line)
    elif res == "pearl":
        pygame.draw.circle(s, c, (m, m), int(n*.34))
        pygame.draw.circle(s, OUTLINE, (m, m), int(n*.34), line)
        pygame.draw.circle(s, (255, 255, 255), (int(n*.4), int(n*.4)), int(n*.09))
    elif res == "gold":
        pygame.draw.circle(s, c, (m, m), int(n*.4))
        pygame.draw.circle(s, OUTLINE, (m, m), int(n*.4), line)
        pygame.draw.circle(s, shade(c, .75), (m, m), int(n*.27), line)
    elif res == "relic":
        pygame.draw.circle(s, c, (m, m), int(n*.36))
        pygame.draw.circle(s, OUTLINE, (m, m), int(n*.36), line)
        star = []
        for i in range(10):
            r = n * (.24 if i % 2 == 0 else .1)
            a = -math.pi / 2 + i * math.pi / 5
            star.append((m + r * math.cos(a), m + r * math.sin(a)))
        pygame.draw.polygon(s, (255, 236, 150), star)
    else:  # gems: amber, crystal, mithril
        outlined([(m, n*.08), (n*.82, n*.38), (m, n*.92), (n*.18, n*.38)])
        pygame.draw.polygon(s, light, [(m, n*.08), (n*.82, n*.38), (m, n*.46)])
        pygame.draw.line(s, OUTLINE, (n*.18, n*.38), (n*.82, n*.38), line)
    return pygame.transform.smoothscale(s, (size, size))


# ---- pawns ------------------------------------------------------------------
def _mark(s, kind_mark, cx, cy, u):
    """Small emblem on the pawn's chest or head, showing its job."""
    c = (255, 244, 214)
    m = kind_mark
    if m == "axe":
        pygame.draw.line(s, c, (cx - u, cy + u), (cx + u, cy - u), max(2, u // 2))
        pygame.draw.circle(s, c, (cx + u, cy - u), u)
    elif m in ("straw", "helmet", "wizard", "hood", "crown", "halo"):
        pass  # worn on the head
    elif m == "leaf":
        pygame.draw.ellipse(s, (130, 230, 120), (cx - u, cy - u * 2, u * 2, u * 4))
    elif m == "feather":
        pygame.draw.line(s, c, (cx - u, cy + 2 * u), (cx + u, cy - 2 * u), max(2, u // 2))
    elif m == "sword":
        pygame.draw.line(s, c, (cx, cy - 2 * u), (cx, cy + 2 * u), max(2, u // 2))
        pygame.draw.line(s, c, (cx - u, cy + u), (cx + u, cy + u), max(2, u // 2))
    elif m == "bow":
        pygame.draw.arc(s, c, (cx - u, cy - 2 * u, u * 2, u * 4), -1.6, 1.6, max(2, u // 2))
        pygame.draw.line(s, c, (cx, cy - 2 * u), (cx, cy + 2 * u), 2)
    elif m == "shield":
        poly(s, c, [(cx - u * 1.3, cy - u * 1.5), (cx + u * 1.3, cy - u * 1.5), (cx + u * 1.3, cy + u * .3),
                    (cx, cy + u * 2), (cx - u * 1.3, cy + u * .3)], False)
    elif m == "cross":
        pygame.draw.rect(s, (240, 70, 70), (cx - u // 2 - 1, cy - 2 * u, u + 2, 4 * u))
        pygame.draw.rect(s, (240, 70, 70), (cx - 2 * u, cy - u // 2 - 1, 4 * u, u + 2))
    elif m == "coin":
        pygame.draw.circle(s, (250, 204, 60), (cx, cy), int(u * 1.6))
    elif m == "scroll":
        pygame.draw.rect(s, c, (cx - 2 * u, cy - u, 4 * u, 2 * u))
    elif m == "hammer":
        pygame.draw.line(s, c, (cx, cy - u), (cx, cy + 2 * u), max(2, u // 2))
        pygame.draw.rect(s, c, (cx - int(1.5 * u), cy - 2 * u, 3 * u, u + 2))
    elif m == "flask":
        poly(s, (120, 240, 200), [(cx - u // 2, cy - 2 * u), (cx + u // 2, cy - 2 * u),
                                  (cx + int(1.6 * u), cy + 2 * u), (cx - int(1.6 * u), cy + 2 * u)], False)
    elif m == "note":
        pygame.draw.circle(s, c, (cx - u // 2, cy + u), u)
        pygame.draw.line(s, c, (cx + u // 2, cy + u), (cx + u // 2, cy - 2 * u), max(2, u // 2))
    elif m == "map":
        pygame.draw.rect(s, (236, 212, 150), (cx - 2 * u, cy - int(1.5 * u), 4 * u, 3 * u))
        pygame.draw.line(s, (200, 50, 40), (cx - u // 2, cy - u // 2), (cx + u, cy + u), 2)
    elif m == "paw":
        pygame.draw.circle(s, c, (cx, cy + u // 2), u)
        for dx in (-u, 0, u):
            pygame.draw.circle(s, c, (cx + dx, cy - u), max(1, u // 2))
    elif m == "star":
        pts = []
        for i in range(10):
            r = u * (2.2 if i % 2 == 0 else 1)
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        pygame.draw.polygon(s, (255, 226, 110), pts)


def _head_mark(s, m, cx, cy, r):
    """What a hand-drawn pawn wears on its head (straw hat, helmet, hood...)."""
    if m == "straw":
        pygame.draw.ellipse(s, (236, 204, 110), (cx - r * 1.5, cy - r * .9, r * 3, r * .9))
        pygame.draw.ellipse(s, (236, 204, 110), (cx - r * .7, cy - r * 1.4, r * 1.4, r))
    elif m == "helmet":
        pygame.draw.arc(s, (250, 210, 70), (cx - r, cy - r, 2 * r, 2 * r), 0, math.pi, r // 2 + 2)
    elif m == "wizard":
        poly(s, (70, 60, 170), [(cx - r * 1.2, cy - r * .4), (cx + r * 1.2, cy - r * .4), (cx, cy - r * 2.5)])
    elif m == "hood":
        pygame.draw.arc(s, (40, 40, 50), (cx - r, cy - r, 2 * r, 2 * r), 0, math.pi, r // 2 + 2)
    elif m == "crown":
        poly(s, (250, 204, 60), [(cx - r, cy - r * .6), (cx - r, cy - r * 1.6), (cx - r * .4, cy - r * 1.05),
                                 (cx, cy - r * 1.8), (cx + r * .4, cy - r * 1.05), (cx + r, cy - r * 1.6),
                                 (cx + r, cy - r * .6)])
    elif m == "halo":
        pygame.draw.ellipse(s, (255, 226, 110), (cx - r, cy - r * 1.7, 2 * r, r * .8), 2)


@sized(2)
def pawn(kind, color, height):
    """A board-game pawn: base, tapered body, round head."""
    scale = 4
    w, h = int(height * .8) * scale, height * scale
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    cx = w // 2
    dark, light = shade(color, .62), shade(color, 1.28)
    line = scale * 2 // 2 + 1
    head_r = int(h * .155)
    head_y = int(h * .3)
    base = pygame.Rect(0, 0, int(w * .86), int(h * .17))
    base.midbottom = (cx, h - 3)
    pygame.draw.ellipse(s, dark, base)
    pygame.draw.ellipse(s, OUTLINE, base, line)
    body = [(cx - h * .1, head_y + head_r * .6), (cx + h * .1, head_y + head_r * .6),
            (cx + h * .25, base.centery), (cx - h * .25, base.centery)]
    pygame.draw.polygon(s, color, body)
    pygame.draw.polygon(s, OUTLINE, body, line)
    pygame.draw.line(s, light, (cx - h * .05, head_y + head_r), (cx - h * .14, base.centery - 4), scale)
    collar = pygame.Rect(0, 0, int(h * .28), int(h * .07))
    collar.center = (cx, head_y + head_r)
    pygame.draw.ellipse(s, dark, collar)
    pygame.draw.circle(s, color, (cx, head_y), head_r)
    pygame.draw.circle(s, OUTLINE, (cx, head_y), head_r, line)
    pygame.draw.circle(s, light, (cx - head_r // 3, head_y - head_r // 3), head_r // 3)
    mark = D.PAWNS[kind]["mark"]
    _mark(s, mark, cx, int(h * .62), max(3, h // 18))
    _head_mark(s, mark, cx, head_y, head_r)
    pad = height // 3
    final = pygame.Surface((w, h + pad * scale), pygame.SRCALPHA)
    final.blit(s, (0, pad * scale))
    return pygame.transform.smoothscale(final, (w // scale, height + pad))


# ---- buildings --------------------------------------------------------------
def box(s, cx, by, w, h, color):
    """Isometric box. (cx, by) is the front bottom corner; w the half-width."""
    d = w / 2
    left = (cx - w, by - d)
    right = (cx + w, by - d)
    front = (cx, by)
    back = (cx, by - w)
    up = lambda p: (p[0], p[1] - h)
    poly(s, shade(color, .78), [left, front, up(front), up(left)])
    poly(s, shade(color, .6), [front, right, up(right), up(front)])
    poly(s, shade(color, 1.08), [up(left), up(front), up(right), up(back)])
    return up(left), up(front), up(right), up(back)


def pyramid(s, top, height, color):
    """A pointed roof on top of a box."""
    left, front, right, back = top
    apex = ((left[0] + right[0]) / 2, (front[1] + back[1]) / 2 - height)
    poly(s, shade(color, 1.02), [left, front, apex])
    poly(s, shade(color, .76), [front, right, apex])


def gable(s, top, height, color):
    """A two-sided roof on top of a box."""
    left, front, right, back = top
    a = ((left[0] + back[0]) / 2, (left[1] + back[1]) / 2 - height)
    b = ((front[0] + right[0]) / 2, (front[1] + right[1]) / 2 - height)
    poly(s, shade(color, 1.05), [left, front, b, a])
    poly(s, shade(color, .72), [front, right, b])


def door(s, cx, by, w, h, color=(70, 44, 30)):
    """A door on the front of a box."""
    x = cx - w * .5
    y = by - w * .25
    poly(s, color, [(x - 3, y - 2), (x + 3, y + 1), (x + 3, y + 1 - h), (x - 3, y - 2 - h)])


def window(s, cx, by, w, h, color=(255, 222, 130)):
    """A lit window on the side of a box."""
    x = cx + w * .5
    y = by - w * .25
    poly(s, color, [(x - 3, y + 1 - h), (x + 3, y - 2 - h), (x + 3, y - 7 - h), (x - 3, y - 4 - h)])


def flag(s, x, y, color, height=16):
    """A small flag on a pole."""
    pygame.draw.line(s, OUTLINE, (x, y), (x, y - height), 2)
    poly(s, color, [(x, y - height), (x + 11, y - height + 3), (x, y - height + 7)])


def ground_patch(s, cx, by, w, color):
    """A diamond of ground under a hand-drawn building."""
    d = w / 2
    pts = [(cx - w, by - d), (cx, by), (cx + w, by - d), (cx, by - w)]
    pygame.draw.polygon(s, color, pts)
    pygame.draw.polygon(s, shade(color, .7), pts, 1)


WOOD = (156, 106, 66)
STONE = (168, 166, 164)
PLASTER = (236, 216, 178)
RED = (200, 72, 56)
TEAL = (64, 146, 150)
SLATE = (82, 92, 118)
THATCH = (216, 176, 92)
GOLD = (248, 198, 56)
GREEN = (96, 170, 84)


def _house_like(s, cx, by, wall, roof, w=18, h=14, rh=13, kind="gable"):
    """A simple house: walls, door, window and a roof."""
    top = box(s, cx, by, w, h, wall)
    door(s, cx, by, w, 9)
    window(s, cx, by, w, 5)
    (gable if kind == "gable" else pyramid)(s, top, rh, roof)


def _coins(s, cx, y, n=3):
    """A little pile of gold coins."""
    for i in range(n):
        pygame.draw.circle(s, GOLD, (cx - 6 + i * 6, y - (i % 2) * 3), 4)
        pygame.draw.circle(s, OUTLINE, (cx - 6 + i * 6, y - (i % 2) * 3), 4, 1)


def _tower(s, cx, by, w, h, wall, roof):
    """A square tower with a pointed roof."""
    top = box(s, cx, by, w, h, wall)
    pyramid(s, top, w, roof)


def _columns(s, cx, by, w, h):
    """Four columns in front of a temple-like building."""
    for dx in (-.75, -.25, .25, .75):
        x = cx + dx * w
        y = by - abs(dx) * w / 2
        pygame.draw.rect(s, (246, 240, 226), (x - 2, y - h, 4, h))
        pygame.draw.rect(s, OUTLINE, (x - 2, y - h, 4, h), 1)


def draw_style(s, style, cx, by, color):
    """Draw a building by code, in one of the styles of data.BUILDINGS (used if its image is missing)."""
    if style == "hall":
        box(s, cx, by, 24, 8, STONE)
        top = box(s, cx, by - 8, 19, 20, PLASTER)
        door(s, cx, by - 8, 19, 12)
        window(s, cx, by - 8, 19, 9)
        gable(s, top, 15, color)
        _tower(s, cx + 17, by - 13, 7, 26, STONE, color)
        flag(s, cx, by - 46, color, 16)
    elif style == "farm":
        ground_patch(s, cx, by, 28, (150, 112, 62))
        for i in range(5):
            for j in range(3):
                x = cx - 18 + i * 6 + j * 8
                y = by - 18 - i * 3 + j * 4 + 3
                pygame.draw.line(s, (232, 200, 80), (x, y), (x, y - 5), 2)
        _house_like(s, cx - 8, by - 2, PLASTER, RED, 11, 8, 9)
    elif style == "camp":
        pygame.draw.line(s, WOOD, (cx - 22, by - 8), (cx + 6, by + 3), 5)
        pygame.draw.line(s, shade(WOOD, 1.2), (cx - 16, by - 14), (cx + 10, by - 2), 5)
        poly(s, (214, 196, 150), [(cx - 18, by - 12), (cx + 4, by - 2), (cx + 2, by - 30)])
        poly(s, (172, 150, 110), [(cx + 4, by - 2), (cx + 24, by - 12), (cx + 2, by - 30)])
        poly(s, (70, 50, 40), [(cx - 3, by - 5), (cx + 4, by - 2), (cx + 3, by - 17)])
    elif style == "quarry":
        ground_patch(s, cx, by, 28, (128, 124, 120))
        ground_patch(s, cx, by - 6, 16, (84, 82, 84))
        box(s, cx - 16, by - 7, 7, 8, STONE)
        box(s, cx + 14, by - 6, 8, 6, shade(STONE, 1.1))
        box(s, cx + 2, by - 1, 6, 5, STONE)
        pygame.draw.line(s, WOOD, (cx - 6, by - 26), (cx + 10, by - 8), 3)
    elif style in ("mine", "goldmine"):
        poly(s, (136, 122, 106), [(cx - 26, by - 10), (cx, by + 1), (cx + 26, by - 10), (cx + 2, by - 36)])
        poly(s, (30, 26, 28), [(cx - 11, by - 7), (cx + 3, by - 2), (cx + 3, by - 20), (cx - 11, by - 25)])
        pygame.draw.line(s, WOOD, (cx - 12, by - 7), (cx - 12, by - 26), 3)
        pygame.draw.line(s, WOOD, (cx + 4, by - 2), (cx + 4, by - 21), 3)
        pygame.draw.line(s, WOOD, (cx - 14, by - 26), (cx + 6, by - 20), 3)
        if style == "goldmine":
            _coins(s, cx + 14, by - 6, 3)
            _coins(s, cx + 15, by - 11, 2)
        else:
            pygame.draw.circle(s, (120, 136, 156), (cx + 15, by - 8), 5)
    elif style == "garden":
        ground_patch(s, cx, by, 26, (120, 92, 58))
        rnd = random.Random(4)
        for _ in range(16):
            x, y = cx + rnd.randint(-15, 15), by - 13 + rnd.randint(-6, 7)
            pygame.draw.circle(s, rnd.choice([(84, 178, 86), (120, 206, 96), (236, 120, 160)]), (x, y), 3)
    elif style == "bank":
        box(s, cx, by, 22, 5, STONE)
        top = box(s, cx, by - 5, 19, 16, (232, 226, 206))
        _columns(s, cx, by - 5, 19, 16)
        pyramid(s, top, 11, TEAL)
        _coins(s, cx, by - 35, 2)
    elif style == "stall":
        box(s, cx, by, 18, 8, WOOD)
        poly(s, RED, [(cx - 21, by - 20), (cx, by - 9), (cx, by - 26), (cx - 21, by - 36)])
        poly(s, (246, 236, 214), [(cx, by - 9), (cx + 21, by - 20), (cx + 21, by - 36), (cx, by - 26)])
        pygame.draw.line(s, OUTLINE, (cx - 20, by - 19), (cx - 20, by - 9), 2)
        pygame.draw.line(s, OUTLINE, (cx + 20, by - 19), (cx + 20, by - 9), 2)
        _coins(s, cx, by - 13, 2)
    elif style == "warehouse":
        top = box(s, cx, by, 22, 17, shade(WOOD, 1.15))
        door(s, cx, by, 22, 12, (56, 38, 28))
        gable(s, top, 10, SLATE)
    elif style == "barracks":
        top = box(s, cx, by, 21, 15, (150, 120, 96))
        door(s, cx, by, 21, 10)
        gable(s, top, 12, (120, 58, 50))
        flag(s, cx + 13, by - 30, color, 15)
    elif style == "armory":
        top = box(s, cx, by, 19, 18, SLATE)
        door(s, cx, by, 19, 11, (34, 34, 42))
        pyramid(s, top, 8, (60, 66, 86))
        pygame.draw.line(s, (230, 230, 240), (cx + 7, by - 18), (cx + 13, by - 6), 2)
    elif style == "tower":
        _tower(s, cx, by, 12, 34, STONE, TEAL)
        window(s, cx, by - 18, 12, 2, (40, 36, 44))
        flag(s, cx, by - 54, color, 12)
    elif style == "training":
        ground_patch(s, cx, by, 26, (202, 172, 116))
        pygame.draw.line(s, WOOD, (cx - 6, by - 10), (cx - 6, by - 30), 4)
        pygame.draw.line(s, WOOD, (cx - 14, by - 25), (cx + 2, by - 25), 3)
        pygame.draw.circle(s, THATCH, (cx - 6, by - 32), 5)
        pygame.draw.circle(s, RED, (cx + 12, by - 14), 8)
        pygame.draw.circle(s, (246, 240, 226), (cx + 12, by - 14), 5)
        pygame.draw.circle(s, RED, (cx + 12, by - 14), 2)
    elif style == "infirmary":
        top = box(s, cx, by, 19, 15, (240, 238, 232))
        door(s, cx, by, 19, 9)
        gable(s, top, 10, (226, 90, 90))
        pygame.draw.rect(s, (226, 60, 60), (cx + 8, by - 21, 4, 12))
        pygame.draw.rect(s, (226, 60, 60), (cx + 4, by - 17, 12, 4))
    elif style == "house":
        _house_like(s, cx, by, PLASTER, THATCH)
    elif style == "tavern":
        _house_like(s, cx, by, (206, 170, 120), (146, 76, 48), 20, 17, 12)
        pygame.draw.rect(s, GOLD, (cx + 16, by - 24, 8, 8))
        pygame.draw.rect(s, OUTLINE, (cx + 16, by - 24, 8, 8), 1)
    elif style == "guild":
        top = box(s, cx, by, 22, 20, (120, 96, 150))
        door(s, cx, by, 22, 12)
        window(s, cx, by, 22, 9)
        pyramid(s, top, 16, GOLD)
    elif style == "workshop":
        _house_like(s, cx, by, WOOD, SLATE, 20, 14, 10)
        pygame.draw.rect(s, (90, 86, 86), (cx + 6, by - 42, 7, 16))
        for i in range(3):
            pygame.draw.circle(s, (210, 210, 210), (cx + 10 + i * 3, by - 47 - i * 6), 3 + i)
    elif style == "caravan":
        box(s, cx - 7, by - 4, 12, 11, (232, 218, 182))
        poly(s, (246, 236, 214), [(cx - 19, by - 21), (cx - 7, by - 15), (cx + 5, by - 21), (cx - 7, by - 33)])
        for dx in (-13, 2):
            pygame.draw.circle(s, WOOD, (cx + dx, by - 5), 6)
            pygame.draw.circle(s, OUTLINE, (cx + dx, by - 5), 6, 1)
        pygame.draw.line(s, WOOD, (cx + 5, by - 10), (cx + 22, by - 14), 3)
    elif style == "library":
        top = box(s, cx, by, 20, 20, (140, 82, 66))
        door(s, cx, by, 20, 11)
        window(s, cx, by, 20, 10)
        window(s, cx, by, 20, 3)
        gable(s, top, 11, (70, 90, 120))
    elif style == "lab":
        _tower(s, cx - 3, by, 15, 20, (112, 150, 136), (70, 60, 130))
        poly(s, (120, 240, 200), [(cx + 16, by - 22), (cx + 20, by - 22), (cx + 26, by - 6), (cx + 10, by - 6)])
    elif style == "trophy":
        top = box(s, cx, by, 20, 17, (176, 90, 70))
        door(s, cx, by, 20, 10)
        gable(s, top, 9, GOLD)
        pygame.draw.circle(s, GOLD, (cx + 10, by - 16), 5)
    elif style == "temple":
        box(s, cx, by, 24, 5, (230, 226, 216))
        box(s, cx, by - 5, 20, 4, (230, 226, 216))
        top = box(s, cx, by - 9, 16, 15, (246, 242, 232))
        _columns(s, cx, by - 9, 16, 15)
        gable(s, top, 12, (120, 200, 210))
    elif style == "statue":
        box(s, cx, by, 16, 9, STONE)
        pygame.draw.rect(s, GOLD, (cx - 5, by - 34, 10, 22), border_radius=3)
        pygame.draw.circle(s, GOLD, (cx, by - 39), 6)
        pygame.draw.line(s, GOLD, (cx + 4, by - 30), (cx + 13, by - 42), 3)
        pygame.draw.rect(s, OUTLINE, (cx - 5, by - 34, 10, 22), 1, border_radius=3)
        pygame.draw.circle(s, OUTLINE, (cx, by - 39), 6, 1)
    elif style == "castle":
        box(s, cx, by, 25, 15, STONE)
        for dx, dy in ((-19, -9), (19, -9)):
            _tower(s, cx + dx, by + dy, 7, 28, shade(STONE, .95), color)
        top = box(s, cx, by - 7, 13, 26, shade(STONE, 1.1))
        pyramid(s, top, 13, color)
        door(s, cx, by, 25, 11, (40, 30, 30))
        flag(s, cx, by - 46, color, 14)


TILE_W, TILE_H = 60, 30


ROOT = os.path.join(paths.ROOT, "assets")
ASSETS = os.path.join(ROOT, "buildings")


# ---- building pictures ------------------------------------------------------
@cached
def building(style, color, scale=1):
    """A building image. Drawn by code, in the player's color, if its image is missing."""
    w, h = 74 * scale, 86 * scale
    path = os.path.join(ASSETS, f"{style}.png")
    if not os.path.exists(path):
        small = pygame.Surface((74, 86), pygame.SRCALPHA)
        draw_style(small, style, 37, 81, color)
        return pygame.transform.smoothscale(small, (w, h))
    image = prepared(pygame.image.load(path))
    fit = min(w * 0.86 / image.get_width(), h * 0.82 / image.get_height())
    size = (int(image.get_width() * fit), int(image.get_height() * fit))
    sprite = pygame.Surface((w, h), pygame.SRCALPHA)
    place = pygame.Rect(0, 0, *size)
    place.midbottom = (w // 2, h - 2)
    sprite.blit(pygame.transform.smoothscale(image, size), place)
    return sprite


@sized(2, 3)
def building_at(style, color, w, h):
    """A building at a fixed size, so it is only scaled once."""
    return pygame.transform.smoothscale(building(style, color, 2), (w, h))


# ---- environments -----------------------------------------------------------
def _tree(s, x, y, size, leaf=(62, 138, 72)):
    """A small pine tree."""
    pygame.draw.rect(s, (98, 66, 42), (x - 2, y - size // 3, 4, size // 3))
    for i, grow in enumerate((1.0, .8, .6)):
        top = y - size // 3 - int(size * .27 * (i + 1))
        base = y - size // 3 - int(size * .27 * i) + 4
        poly(s, shade(leaf, 1 + i * .1), [(x - size * .34 * grow, base), (x + size * .34 * grow, base), (x, top)])


def _peak(s, x, y, w, h, color, snow=True):
    """A mountain peak, with snow on top."""
    poly(s, color, [(x - w, y), (x, y - h), (x + w, y)])
    poly(s, shade(color, .75), [(x, y - h), (x + w, y), (x + w * .15, y)], False)
    if snow:
        poly(s, (244, 246, 250), [(x - w * .3, y - h * .7), (x, y - h), (x + w * .3, y - h * .7),
                                  (x + w * .1, y - h * .62), (x - w * .1, y - h * .7)], False)


@sized(1, 2)
def environment(eid, w, h):
    """A zone's picture filling w x h, or a drawing of it if the image is missing."""
    image = asset("environments", f"{eid}.png") or asset("environments", f"{eid}.jpg")
    if image:
        return fill_size(image, w, h)
    s = pygame.Surface((w, h))
    rnd = random.Random(eid)
    if eid == "forest":
        s.fill((86, 150, 84))
        for _ in range(34):
            _tree(s, rnd.randint(4, w - 4), rnd.randint(36, h), rnd.randint(26, 40))
    elif eid == "mountain":
        s.fill((150, 180, 206))
        pygame.draw.rect(s, (112, 138, 96), (0, h * .7, w, h))
        for x, wid, hei in ((40, 70, 92), (180, 76, 86), (110, 90, 128)):
            _peak(s, x, int(h * .8), wid, hei, (118, 110, 112))
    elif eid == "lake":
        s.fill((122, 178, 96))
        pygame.draw.ellipse(s, (226, 208, 150), (-10, h * .2, w + 20, h))
        pygame.draw.ellipse(s, (64, 150, 206), (6, h * .28, w - 12, h))
        for _ in range(16):
            x, y = rnd.randint(30, w - 50), rnd.randint(int(h * .42), h - 6)
            pygame.draw.line(s, (156, 214, 240), (x, y), (x + rnd.randint(10, 22), y), 2)
    elif eid == "mine":
        s.fill((96, 84, 76))
        for _ in range(14):
            _peak(s, rnd.randint(0, w), rnd.randint(40, 70), 34, 36, (116, 102, 92), False)
        poly(s, (28, 24, 28), [(w * .36, h), (w * .36, h * .48), (w * .5, h * .36), (w * .64, h * .48), (w * .64, h)])
        pygame.draw.line(s, (150, 104, 62), (w * .34, h), (w * .34, h * .46), 6)
        pygame.draw.line(s, (150, 104, 62), (w * .66, h), (w * .66, h * .46), 6)
        pygame.draw.line(s, (150, 104, 62), (w * .32, h * .46), (w * .68, h * .46), 6)
    elif eid == "swamp":
        s.fill((86, 106, 66))
        for _ in range(12):
            x, y = rnd.randint(-10, w), rnd.randint(30, h)
            pygame.draw.ellipse(s, (60, 92, 76), (x, y, rnd.randint(40, 90), rnd.randint(12, 24)))
        for _ in range(7):
            x, y = rnd.randint(8, w - 8), rnd.randint(50, h)
            pygame.draw.line(s, (60, 44, 34), (x, y), (x + rnd.randint(-8, 8), y - 34), 4)
            pygame.draw.circle(s, (92, 116, 60), (x, y - 38), 13)
    elif eid == "ruins":
        s.fill((184, 170, 130))
        for _ in range(9):
            x, y = rnd.randint(14, w - 14), rnd.randint(56, h)
            hei = rnd.randint(18, 50)
            pygame.draw.rect(s, (220, 214, 196), (x - 6, y - hei, 12, hei))
            pygame.draw.rect(s, OUTLINE, (x - 6, y - hei, 12, hei), 1)
            pygame.draw.rect(s, (200, 194, 176), (x - 9, y - hei - 4, 18, 5))
    else:  # plains
        s.fill((170, 196, 96))
        for _ in range(70):
            x, y = rnd.randint(0, w), rnd.randint(0, h)
            pygame.draw.line(s, (136, 170, 74), (x, y), (x + 2, y - 6), 2)
        for _ in range(16):
            pygame.draw.circle(s, (246, 226, 96), (rnd.randint(0, w), rnd.randint(30, h)), 2)
    shadow = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 80), (0, 0, w, 26))
    s.blit(shadow, (0, 0))
    return s


@sized(0, 1)
def home_ground(w, h):
    """The grass where a player's buildings stand, or None without the picture."""
    image = asset("environments", "home.png")
    return fill_size(image, w, h) if image else None


@sized(0, 1)
def town_tile(w, h):
    """The Town's picture filling w x h, or a drawing of it."""
    image = asset("environments", "town.png") or asset("environments", "town.jpg")
    if image:
        return fill_size(image, w, h)
    s = pygame.Surface((w, h))
    s.fill((188, 168, 130))
    rnd = random.Random(2)
    for _ in range(90):
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        pygame.draw.rect(s, (172, 150, 112), (x, y, 11, 6), 1)
    spots = [("tavern", 34, 76), ("bank", 186, 76), ("stall", 66, 120), ("house", 158, 122),
             ("library", 110, 74)]
    for style, x, y in spots:
        b = building(style, (200, 170, 70))
        s.blit(b, (x - b.get_width() // 2, y - b.get_height() + 10))
    return s


@sized(1)
def die(value, size, tint=(250, 246, 234)):
    """A six-sided die showing value."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(s, tint, s.get_rect(), border_radius=size // 6)
    pygame.draw.rect(s, OUTLINE, s.get_rect(), 2, border_radius=size // 6)
    a, m, b = size // 4, size // 2, size - size // 4
    spots = {1: [(m, m)], 2: [(a, a), (b, b)], 3: [(a, a), (m, m), (b, b)],
             4: [(a, a), (b, a), (a, b), (b, b)], 5: [(a, a), (b, a), (m, m), (a, b), (b, b)],
             6: [(a, a), (b, a), (a, m), (b, m), (a, b), (b, b)]}[value]
    for p in spots:
        pygame.draw.circle(s, OUTLINE, p, max(2, size // 10))
    return s


# ---- animated characters ----------------------------------------------------
_index = {}
IDLE, RUN, ATTACK = 0, 1, 2
BODY_SCALE = {"knight": 1.45, "warrior": 1.1, "champion": 1.2, "guide": 1.2, "noble": 1.15, "beast_tamer": 0.8,
              "archer": 1.05, "monk": 0.85, "spearman": 1.3, "stone_bull": 1.3, "panda": 1.15,
              "mob_bear": 1.25, "mob_snake": 0.8, "mob_gnoll": 1.05, "mob_spider": 1.0, "mob_skull": 1.0}


# ---- loading the character sheets -------------------------------------------
def units():
    """The animated characters' index (cell size, frames, foot position), read once."""
    if not _index:
        path = os.path.join(ROOT, "units", "index.json")
        if os.path.exists(path):
            with open(path) as f:
                _index.update(json.load(f))
    return _index


def frame_count(kind, anim):
    """How many frames an animation of this character has."""
    return units()[kind]["frames"][anim]


@cached
def _sheet(kind, team):
    """The sprite sheet of a character in a team color."""
    return asset("units", kind, f"{team}.png") or asset("units", kind, "all.png")


def unit_frame(kind, team, anim, index, height, flip=False, gray=False):
    """One animation frame. Returns (image, foot x, foot y), or None without art."""
    info = units().get(kind)
    if not info:
        return None
    return _frame(kind, team, anim, index % info["frames"][anim], height, flip, gray)


@sized(4)
def _frame(kind, team, anim, index, height, flip, gray):
    """One frame of an animation, cut from the sheet and sized (cached by unit_frame)."""
    info = units()[kind]
    sheet = _sheet(kind, team)
    if not sheet:
        return None
    w, h = info["cell"]
    frame = sheet.subsurface((index * w, anim * h, w, h))
    scale = height * BODY_SCALE.get(kind, 1) / info["idle_h"]
    size = (max(1, int(w * scale)), max(1, int(h * scale)))
    image = pygame.transform.smoothscale(frame, size)
    foot_x = info["foot"][0] * scale
    if flip:
        image = pygame.transform.flip(image, True, False)
        foot_x = size[0] - foot_x
    if gray:
        image = image.copy()
        image.fill((130, 130, 130, 190), special_flags=pygame.BLEND_RGBA_MULT)
    return image, int(foot_x), int(info["foot"][1] * scale)


# ---- medieval interface -----------------------------------------------------
@sized()
def table():
    """The wooden table picture behind the board."""
    image = asset("ui", "table.jpg")
    return image


@cached
def menu_actors():
    """Everything that moves in the menu picture (made with the picture, 2560 x 1600)."""
    path = os.path.join(ROOT, "menu", "actors.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


@sized(0, 1)
def menu_ground(w, h):
    """The menu picture without its moving parts."""
    image = asset("menu", "ground.png")
    return pygame.transform.smoothscale(image, (w, h)) if image else None


@cached
def menu_strip(sheet):
    """One animation strip of the menu picture."""
    return asset("menu", sheet + ".png")


@sized(3, 4)
def menu_frame(sheet, frames, index, w, h):
    """One frame of a moving part, at the size it is drawn."""
    strip = menu_strip(sheet)
    if strip is None:
        return None
    fw = strip.get_width() // frames
    return pygame.transform.smoothscale(strip.subsurface((index * fw, 0, fw, strip.get_height())), (w, h))


@sized(0, 1)
def menu_picture(w, h):
    """The menu landscape, with the title written in water."""
    image = asset("ui", "menu.png")
    return pygame.transform.smoothscale(image, (w, h)) if image else None


@sized(0, 1)
def paper(w, h):
    """A plain parchment sheet of any size."""
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, (241, 228, 200), s.get_rect(), border_radius=9)
    pygame.draw.rect(s, (214, 192, 150), s.get_rect().inflate(-8, -8), 2, border_radius=7)
    pygame.draw.rect(s, OUTLINE, s.get_rect(), 2, border_radius=9)
    return s


@sized(0, 1)
def wood_frame(w, h):
    """The wooden frame with metal bolts, for windows."""
    sheet = asset("ui", "frame.png")
    if not sheet:
        return None
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    sw, sh = sheet.get_size()
    c, k = 15, 2
    d = c * k
    xs = [(0, c, 0, d), (c, sw - 2 * c, d, w - 2 * d), (sw - c, c, w - d, d)]
    ys = [(0, c, 0, d), (c, sh - 2 * c, d, h - 2 * d), (sh - c, c, h - d, d)]
    for sy, ssh, ty, th in ys:
        for sx, ssw, tx, tw in xs:
            piece = sheet.subsurface((sx, sy, ssw, ssh))
            s.blit(pygame.transform.scale(piece, (tw, th)), (tx, ty))
    return s


BUTTONS = {"button": ((226, 202, 156), (246, 228, 190)), "button_red": ((168, 58, 44), (204, 92, 70)),
           "button_off": ((208, 196, 172), (216, 206, 184))}


@sized(1, 2)
def button_face(style, w, h):
    """A clean wooden button."""
    base, light = BUTTONS[style]
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, shade(base, .72), (0, 2, w, h - 2), border_radius=7)
    pygame.draw.rect(s, base, (0, 0, w, h - 3), border_radius=7)
    pygame.draw.line(s, light, (6, 2), (w - 7, 2), 2)
    pygame.draw.rect(s, OUTLINE, s.get_rect(), 2, border_radius=7)
    return s


RIBBON_ROWS = {"blue": 0, "red": 1, "yellow": 2, "purple": 3}


@sized(1, 2)
def ribbon(team, w, h):
    """A cloth banner in the player's color: two ends around a stretched middle."""
    sheet = asset("ui", "ribbons.png")
    if not sheet:
        return None
    y = RIBBON_ROWS.get(team, 0) * 128
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    left = sheet.subsurface((0, y, 128, 128))
    right = sheet.subsurface((320, y, 128, 128))
    middle = sheet.subsurface((192, y, 64, 128))
    lb, rb, mb = left.get_bounding_rect(), right.get_bounding_rect(), middle.get_bounding_rect()
    side = h * lb.w // lb.h
    s.blit(pygame.transform.scale(middle.subsurface(mb), (w - side, h)), (side // 2, 0))
    s.blit(pygame.transform.scale(left.subsurface(lb), (side, h)), (0, 0))
    s.blit(pygame.transform.scale(right.subsurface(rb), (side, h)), (w - side, 0))
    return s


@sized(0, 1)
def top_fade(w, h):
    """A dark shadow that fades out downwards."""
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        pygame.draw.line(s, (20, 12, 8, 190 - y * 190 // h), (0, y), (w, y))
    return s


@sized(1, 2)
def hover_face(style, w, h):
    """A button under the mouse: slightly lighter."""
    face = button_face(style, w, h).copy()
    face.fill((24, 24, 24, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return face

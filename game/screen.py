"""Sharp drawing at any screen size. The game keeps thinking in a 1280 x 800 canvas:
Screen and draw multiply every position and size just before pixels are written."""
import math

import pygame

import art


# ---- the sharp canvas -------------------------------------------------------
class Screen(pygame.Surface):
    """The real picture, `scale` times the size of the 1280 x 800 canvas."""

    def __init__(self, size, scale=1):
        """size: the real picture in pixels. scale: how much bigger it is than 1280 x 800."""
        super().__init__(size)
        self.scale = scale
        self.veils = {}

    def rect(self, rect):
        """A canvas rectangle in real pixels, without gaps between neighbours."""
        s = self.scale
        x, y, w, h = pygame.Rect(rect)
        left, top = round(x * s), round(y * s)
        return pygame.Rect(left, top, round((x + w) * s) - left, round((y + h) * s) - top)

    def blit(self, image, pos, *rest):
        """Draw an image at a canvas position, using its sharp large version when there is one."""
        s = self.scale
        if s == 1:
            return super().blit(image, pos, *rest)
        sharp = art.HIRES.get(id(image))
        if sharp is None:
            w, h = image.get_size()
            sharp = pygame.transform.smoothscale(image, (math.ceil(w * s), math.ceil(h * s)))
        return super().blit(sharp, (round(pos[0] * s), round(pos[1] * s)), *rest)

    def blit_opaque(self, image, pos):
        """A picture without any see-through pixel, like the menu's ground: copied without blending, which
        is several times faster for a picture as big as the screen."""
        sharp = art.HIRES.get(id(image), image) if self.scale != 1 else image
        key = ("opaque", id(sharp))
        if key not in self.veils:
            if sharp is image and self.scale != 1:
                w, h = image.get_size()
                sharp = pygame.transform.smoothscale(image, (math.ceil(w * self.scale), math.ceil(h * self.scale)))
            try:
                self.veils[key] = sharp.convert()
            except pygame.error:  # no window yet
                self.veils[key] = sharp
        pygame.Surface.blit(self, self.veils[key], (round(pos[0] * self.scale), round(pos[1] * self.scale)))

    def fill(self, color, rect=None, special_flags=0):
        """Fill a canvas rectangle, or everything."""
        area = self.rect(rect) if rect is not None else None
        return super().fill(color, area, special_flags)

    def shade(self, rect, color, radius=0):
        """A see-through dark layer."""
        area = self.rect(rect)
        key = (area.size, tuple(color), radius)
        if key not in self.veils:
            if len(self.veils) > 400:
                self.veils.clear()
            layer = pygame.Surface(area.size, pygame.SRCALPHA)
            pygame.draw.rect(layer, color, layer.get_rect(), border_radius=round(radius * self.scale))
            self.veils[key] = layer
        pygame.Surface.blit(self, self.veils[key], area)

    def thick(self, width):
        """A line width in real pixels (at least 1)."""
        return max(1, round(width * self.scale)) if width else 0

    def point(self, pos):
        """A canvas point in real pixels."""
        return (round(pos[0] * self.scale), round(pos[1] * self.scale))


# ---- drawing shapes on it ---------------------------------------------------
class draw:
    """pygame.draw for a Screen. Anything else is passed through unchanged."""

    @staticmethod
    def rect(s, color, rect, width=0, **corners):
        """pygame.draw.rect, scaled."""
        if not isinstance(s, Screen):
            return pygame.draw.rect(s, color, rect, width, **corners)
        corners = {k: round(v * s.scale) for k, v in corners.items()}
        return pygame.draw.rect(s, color, s.rect(rect), s.thick(width), **corners)

    @staticmethod
    def ellipse(s, color, rect, width=0):
        """pygame.draw.ellipse, scaled."""
        if not isinstance(s, Screen):
            return pygame.draw.ellipse(s, color, rect, width)
        return pygame.draw.ellipse(s, color, s.rect(rect), s.thick(width))

    @staticmethod
    def circle(s, color, center, radius, width=0):
        """pygame.draw.circle, scaled."""
        if not isinstance(s, Screen):
            return pygame.draw.circle(s, color, center, radius, width)
        return pygame.draw.circle(s, color, s.point(center), round(radius * s.scale), s.thick(width))

    @staticmethod
    def line(s, color, start, end, width=1):
        """pygame.draw.line, scaled."""
        if not isinstance(s, Screen):
            return pygame.draw.line(s, color, start, end, width)
        return pygame.draw.line(s, color, s.point(start), s.point(end), s.thick(width))

    @staticmethod
    def lines(s, color, closed, points, width=1):
        """pygame.draw.lines, scaled."""
        if not isinstance(s, Screen):
            return pygame.draw.lines(s, color, closed, points, width)
        return pygame.draw.lines(s, color, closed, [s.point(p) for p in points], s.thick(width))

    @staticmethod
    def arc(s, color, rect, start, stop, width=1):
        """pygame.draw.arc, scaled."""
        if not isinstance(s, Screen):
            return pygame.draw.arc(s, color, rect, start, stop, width)
        return pygame.draw.arc(s, color, s.rect(rect), start, stop, s.thick(width))

    @staticmethod
    def polygon(s, color, points, width=0):
        """pygame.draw.polygon, scaled."""
        if not isinstance(s, Screen):
            return pygame.draw.polygon(s, color, points, width)
        return pygame.draw.polygon(s, color, [s.point(p) for p in points], s.thick(width))

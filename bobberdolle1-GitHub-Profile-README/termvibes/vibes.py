#!/usr/bin/env python3
"""termvibes — animated ASCII/ANSI eye candy, no dependencies.

Run it: python3 vibes.py
Keys:   1 matrix rain   2 fire   3 plasma   4 starfield   5 dvd bounce
        space pause     q / ctrl-c quit
"""
import math
import os
import random
import select
import sys
import termios
import time
import tty

HIDE_CURSOR = "\x1b[?25l"
SHOW_CURSOR = "\x1b[?25h"
HOME = "\x1b[H"
CLEAR = "\x1b[2J"
RESET = "\x1b[0m"

MATRIX_CHARS = "アイウエオカキクケコサシスセソタチツテト0123456789"


def fg(r, g, b):
    return f"\x1b[38;2;{r};{g};{b}m"


def render_rows(rows):
    """rows: list of list[(char, (r,g,b) or None)] -> collapse into escape-efficient lines."""
    out = []
    for row in rows:
        line = []
        last_color = None
        for ch, color in row:
            if color != last_color:
                line.append(fg(*color) if color else RESET)
                last_color = color
            line.append(ch)
        line.append(RESET)
        out.append("".join(line))
    return HOME + "\n".join(out)


class Matrix:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.drops = [random.randint(-h, 0) for _ in range(w)]
        self.speed = [random.choice([1, 1, 2]) for _ in range(w)]

    def resize(self, w, h):
        self.__init__(w, h)

    def frame(self, t):
        rows = [[(" ", None) for _ in range(self.w)] for _ in range(self.h)]
        for x in range(self.w):
            self.drops[x] += self.speed[x]
            if self.drops[x] - self.h > random.randint(0, 20):
                self.drops[x] = random.randint(-10, 0)
            tail = self.drops[x]
            for k in range(14):
                y = tail - k
                if 0 <= y < self.h:
                    ch = random.choice(MATRIX_CHARS)
                    if k == 0:
                        color = (200, 255, 200)
                    else:
                        fade = max(0, 255 - k * 20)
                        color = (0, fade, 0)
                    rows[y][x] = (ch, color)
        return rows


class Fire:
    RAMP = " .:-=+*#%@"

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.buf = [[0] * w for _ in range(h + 1)]

    def resize(self, w, h):
        self.__init__(w, h)

    def frame(self, t):
        w, h = self.w, self.h
        for x in range(w):
            self.buf[h][x] = 255 if random.random() > 0.15 else 0
        for y in range(h):
            for x in range(w):
                src = self.buf[min(y + 1, h)]
                decay = random.randint(0, 3)
                left = src[(x - 1) % w]
                mid = src[x]
                right = src[(x + 1) % w]
                below = self.buf[min(y + 2, h)][x] if y + 2 <= h else mid
                val = (left + mid + right + below) // 4 - decay
                self.buf[y][x] = max(0, val)
        rows = []
        for y in range(h):
            row = []
            for x in range(w):
                v = self.buf[y][x]
                ch = self.RAMP[min(len(self.RAMP) - 1, v * len(self.RAMP) // 256)]
                r = min(255, v * 3)
                g = min(255, max(0, v * 2 - 60))
                b = max(0, v - 200)
                row.append((ch, (r, g, b)) if v > 4 else (" ", None))
            rows.append(row)
        return rows


class Plasma:
    RAMP = " .:-=+*#%@"

    def __init__(self, w, h):
        self.w, self.h = w, h

    def resize(self, w, h):
        self.w, self.h = w, h

    def frame(self, t):
        rows = []
        for y in range(self.h):
            row = []
            for x in range(self.w):
                v = (
                    math.sin(x * 0.2 + t)
                    + math.sin(y * 0.2 + t * 1.3)
                    + math.sin((x + y) * 0.1 + t * 0.7)
                    + math.sin(math.sqrt((x - self.w / 2) ** 2 + (y - self.h / 2) ** 2) * 0.2)
                )
                v = (v + 4) / 8  # normalize 0..1
                hue = (v + t * 0.05) % 1.0
                r, g, b = hsv_to_rgb(hue, 0.85, 1.0)
                ch = self.RAMP[min(len(self.RAMP) - 1, int(v * len(self.RAMP)))]
                row.append((ch, (r, g, b)))
            rows.append(row)
        return rows


class Starfield:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.stars = [self._new_star() for _ in range(min(220, w * h // 6))]

    def resize(self, w, h):
        self.__init__(w, h)

    def _new_star(self):
        return [random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(0.05, 1.0)]

    def frame(self, t):
        rows = [[(" ", None) for _ in range(self.w)] for _ in range(self.h)]
        cx, cy = self.w / 2, self.h / 2
        for s in self.stars:
            s[2] -= 0.02
            if s[2] <= 0.02:
                s[0], s[1], s[2] = self._new_star()
            x = int(cx + (s[0] / s[2]) * cx)
            y = int(cy + (s[1] / s[2]) * cy * 0.5)
            if 0 <= x < self.w and 0 <= y < self.h:
                brightness = 1 - s[2]
                shade = int(brightness * 255)
                ch = "." if s[2] > 0.6 else ("*" if s[2] > 0.3 else "@")
                rows[y][x] = (ch, (shade, shade, shade))
        return rows


LOGO = [
    " __     __ ___ ____  ____ ",
    " \\ \\   / /|_ _|| __ )| ___|",
    "  \\ \\ / /  | | |  _ \\|  _| ",
    "   \\ V /   | | | |_) | |___",
    "    \\_/   |___||____/|____|",
]

BOUNCE_COLORS = [
    (255, 60, 60),
    (60, 255, 90),
    (80, 140, 255),
    (255, 220, 40),
    (255, 90, 220),
    (60, 230, 230),
]


class DvdBounce:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.logo_h = len(LOGO)
        self.logo_w = max(len(line) for line in LOGO)
        self.x = random.uniform(0, max(1, w - self.logo_w))
        self.y = random.uniform(0, max(1, h - self.logo_h))
        self.dx = random.choice([-1, 1]) * random.uniform(0.6, 1.0)
        self.dy = random.choice([-1, 1]) * random.uniform(0.4, 0.7)
        self.color = random.choice(BOUNCE_COLORS)
        self.hits = 0
        self.flash = 0

    def resize(self, w, h):
        old_w, old_h = self.w, self.h
        self.w, self.h = w, h
        self.x = min(self.x, max(1, w - self.logo_w))
        self.y = min(self.y, max(1, h - self.logo_h))

    def frame(self, t):
        max_x = max(1, self.w - self.logo_w)
        max_y = max(1, self.h - self.logo_h)
        self.x += self.dx
        self.y += self.dy
        bounced = False
        if self.x <= 0 or self.x >= max_x:
            self.x = max(0, min(self.x, max_x))
            self.dx *= -1
            bounced = True
        if self.y <= 0 or self.y >= max_y:
            self.y = max(0, min(self.y, max_y))
            self.dy *= -1
            bounced = True
        if bounced:
            self.hits += 1
            self.color = random.choice(BOUNCE_COLORS)
            self.flash = 4  # corner-hit style flash for a few frames

        rows = [[(" ", None) for _ in range(self.w)] for _ in range(self.h)]
        ix, iy = int(self.x), int(self.y)
        color = (255, 255, 255) if self.flash > 0 else self.color
        if self.flash > 0:
            self.flash -= 1
        for ly, line in enumerate(LOGO):
            ry = iy + ly
            if not (0 <= ry < self.h):
                continue
            for lx, ch in enumerate(line):
                rx = ix + lx
                if ch != " " and 0 <= rx < self.w:
                    rows[ry][rx] = (ch, color)
        counter = f" hits: {self.hits} "
        for i, ch in enumerate(counter):
            if i < self.w:
                rows[0][i] = (ch, (120, 120, 120))
        return rows


def hsv_to_rgb(h, s, v):
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    tt = v * (1 - (1 - f) * s)
    i %= 6
    r, g, b = [
        (v, tt, p),
        (q, v, p),
        (p, v, tt),
        (p, q, v),
        (tt, p, v),
        (v, p, q),
    ][i]
    return int(r * 255), int(g * 255), int(b * 255)


EFFECTS = {
    "1": ("matrix rain", Matrix),
    "2": ("fire", Fire),
    "3": ("plasma", Plasma),
    "4": ("starfield", Starfield),
    "5": ("dvd bounce", DvdBounce),
}


def read_key(timeout):
    if select.select([sys.stdin], [], [], timeout)[0]:
        return sys.stdin.read(1)
    return None


def main():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    sys.stdout.write(HIDE_CURSOR + CLEAR)
    sys.stdout.flush()

    key = "3"
    w, h = os.get_terminal_size()
    name, cls = EFFECTS[key]
    effect = cls(w, h - 1)
    t = 0.0
    paused = False

    try:
        while True:
            cw, ch_ = os.get_terminal_size()
            if (cw, ch_ - 1) != (effect.w, effect.h):
                effect.resize(cw, ch_ - 1)

            if not paused:
                rows = effect.frame(t)
                label = f" termvibes :: {name}  [1 matrix 2 fire 3 plasma 4 starfield 5 dvd  space pause  q quit]"
                label = label[: effect.w].ljust(effect.w)
                sys.stdout.write(render_rows(rows) + f"\n{RESET}{label}")
                sys.stdout.flush()
                t += 0.08

            pressed = read_key(0.04)
            if pressed:
                if pressed == "q" or pressed == "\x03":
                    break
                if pressed == " ":
                    paused = not paused
                elif pressed in EFFECTS:
                    key = pressed
                    name, cls = EFFECTS[key]
                    effect = cls(cw, ch_ - 1)
                    t = 0.0
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        sys.stdout.write(SHOW_CURSOR + RESET + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

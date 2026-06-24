"""Screencast engine for the repo quickstart guide video.

Renders a list of "slides" (a PIL image + a hold duration in seconds) and assembles
them into an MP4 per module via ffmpeg's concat demuxer, then concatenates modules
into one final MP4.

Pure-Python (Pillow) frame composition + ffmpeg. No browser, no external services.
Captions are Korean (Apple SD Gothic Neo); terminal text is monospace (Menlo).
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

W, H = 1920, 1080
FPS = 30

MENLO = "/System/Library/Fonts/Menlo.ttc"
GOTHIC = "/System/Library/Fonts/AppleSDGothicNeo.ttc"

# Brand-ish palette (from repo SVG assets).
BG_TOP = (10, 16, 28)
BG_BOT = (17, 24, 39)
PANEL = (13, 20, 33)
PANEL_HEAD = (24, 33, 51)
PANEL_LINE = (38, 50, 71)
TERM_BG = (11, 17, 28)
INK = (226, 232, 240)
DIM = (124, 138, 161)
FAINT = (84, 98, 121)
BLUE = (91, 176, 255)
BLUE_DK = (37, 99, 235)
GREEN = (134, 239, 172)
GREEN_DK = (22, 101, 52)
ORANGE = (253, 186, 116)
ORANGE_DK = (154, 52, 18)
RED = (248, 113, 113)
YELLOW = (250, 204, 21)
WHITE = (255, 255, 255)
CAPTION_BG = (8, 13, 23)

MARGIN = 84


# ---------------------------------------------------------------------------
# Language / i18n
# ---------------------------------------------------------------------------

LANG = "ko"  # set by build_guide_video.main(); "ko" or "en"


def tr(ko: str, en: str) -> str:
    """Return the string for the active language. Display strings only —
    real command output / JSON / file contents stay identical across builds."""
    return en if LANG == "en" else ko


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

_font_cache: dict[tuple[str, int, int], ImageFont.FreeTypeFont] = {}


def _f(path: str, size: int, index: int = 0) -> ImageFont.FreeTypeFont:
    key = (path, size, index)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size, index=index)
    return _font_cache[key]


def mono(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return _f(MENLO, size, 1 if bold else 0)


def kr(size: int, weight: str = "medium") -> ImageFont.FreeTypeFont:
    idx = {"regular": 0, "medium": 2, "semibold": 4, "bold": 6}.get(weight, 2)
    return _f(GOTHIC, size, idx)


# ---------------------------------------------------------------------------
# Low-level drawing helpers
# ---------------------------------------------------------------------------

def _bg() -> Image.Image:
    img = Image.new("RGB", (W, H), BG_TOP)
    top = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        # ease the gradient a touch toward the bottom
        t = t ** 1.15
        c = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
        top.putpixel((0, y), c)
    img.paste(top.resize((W, H)), (0, 0))
    # subtle vignette glow at top-center
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W // 2 - 720, -460, W // 2 + 720, 360], fill=46)
    img.paste(Image.new("RGB", (W, H), (30, 58, 110)), (0, 0), glow)
    return img


_BG_CACHE = None


def fresh_bg() -> Image.Image:
    global _BG_CACHE
    if _BG_CACHE is None:
        _BG_CACHE = _bg()
    return _BG_CACHE.copy()


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text_width(font, s: str) -> float:
    return font.getlength(s)


def wrap(font, s: str, max_w: float) -> list[str]:
    """Greedy wrap that also breaks long unbroken tokens (e.g., Korean)."""
    out: list[str] = []
    for para in s.split("\n"):
        words = para.split(" ")
        line = ""
        for w in words:
            cand = w if not line else line + " " + w
            if text_width(font, cand) <= max_w:
                line = cand
                continue
            if line:
                out.append(line)
            # word itself too long -> break by chars
            if text_width(font, w) <= max_w:
                line = w
            else:
                chunk = ""
                for ch in w:
                    if text_width(font, chunk + ch) <= max_w:
                        chunk += ch
                    else:
                        out.append(chunk)
                        chunk = ch
                line = chunk
        out.append(line)
    return out


# ---------------------------------------------------------------------------
# Chrome: chapter chip, progress, caption, scene title
# ---------------------------------------------------------------------------

@dataclass
class Ctx:
    chapter_idx: int
    chapter_total: int
    chapter_label: str
    step: str = ""
    caption: str = ""
    caption_sub: str = ""
    scene_title: str = ""


def draw_chrome(img: Image.Image, ctx: Ctx):
    d = ImageDraw.Draw(img, "RGBA")

    # Chapter chip (top-left)
    chip_font = mono(24, bold=True)
    lbl_font = kr(28, "semibold")
    tag = f"CHAPTER {ctx.chapter_idx}/{ctx.chapter_total}"
    tw = text_width(chip_font, tag)
    chip_w = tw + 36
    rounded(d, [MARGIN, 60, MARGIN + chip_w, 60 + 44], 12, fill=(*BLUE_DK, 235))
    d.text((MARGIN + 18, 60 + 8), tag, font=chip_font, fill=WHITE)
    d.text((MARGIN + chip_w + 20, 60 + 4), ctx.chapter_label, font=lbl_font, fill=INK)

    # Progress dots (top-right)
    n = ctx.chapter_total
    r = 7
    gap = 26
    total_w = (n - 1) * gap
    x1 = W - MARGIN
    x0 = x1 - total_w
    cy = 82
    for i in range(n):
        cx = x0 + i * gap
        on = (i + 1) <= ctx.chapter_idx
        col = BLUE if (i + 1) == ctx.chapter_idx else (INK if on else FAINT)
        rr = r + 2 if (i + 1) == ctx.chapter_idx else r
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)

    # Scene title (above content)
    if ctx.scene_title:
        d.text((MARGIN, 128), ctx.scene_title, font=kr(40, "bold"), fill=WHITE)

    # Caption lower-third
    if ctx.caption:
        cap_top = 940
        rounded(d, [MARGIN, cap_top, W - MARGIN, cap_top + 104], 16,
                fill=(*CAPTION_BG, 232), outline=(*PANEL_LINE, 255), width=2)
        # accent bar
        rounded(d, [MARGIN, cap_top, MARGIN + 8, cap_top + 104], 4, fill=(*BLUE, 255))
        cf = kr(34, "semibold")
        lines = wrap(cf, ctx.caption, W - 2 * MARGIN - 90)[:2]
        ty = cap_top + (30 if len(lines) == 1 and not ctx.caption_sub else 18)
        for ln in lines:
            d.text((MARGIN + 36, ty), ln, font=cf, fill=INK)
            ty += 40
        if ctx.caption_sub:
            draw_mixed(d, (MARGIN + 36, ty + 2), ctx.caption_sub, 23, DIM)


# ---------------------------------------------------------------------------
# Content widgets
# ---------------------------------------------------------------------------

TERM_BOX = (MARGIN, 196, W - MARGIN, 904)  # x0,y0,x1,y1


def terminal_window(img: Image.Image, title: str = "bash", body_top_pad: int = 24,
                    box_bottom: int | None = None):
    d = ImageDraw.Draw(img, "RGBA")
    x0, y0, x1, y1 = TERM_BOX
    if box_bottom is not None:
        y1 = max(y0 + 150, min(TERM_BOX[3], int(box_bottom)))
    # shadow
    rounded(d, [x0 + 6, y0 + 10, x1 + 6, y1 + 12], 18, fill=(0, 0, 0, 70))
    rounded(d, [x0, y0, x1, y1], 18, fill=(*TERM_BG, 255), outline=(*PANEL_LINE, 255), width=2)
    # title bar
    rounded(d, [x0, y0, x1, y0 + 52], 18, fill=(*PANEL_HEAD, 255))
    d.rectangle([x0, y0 + 30, x1, y0 + 52], fill=(*PANEL_HEAD, 255))
    for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = x0 + 30 + i * 26
        d.ellipse([cx - 8, y0 + 18, cx + 8, y0 + 34], fill=col)
    draw_mixed(d, (x0 + 130, y0 + 14), title, 22, DIM)
    return (x0 + 34, y0 + 52 + body_top_pad)  # content origin (x, y)


def term_box_bottom(n_lines: int, lh: int = 38, top_pad: int = 24,
                    bottom_pad: int = 30, min_lines: int = 5) -> int:
    """Compute an adaptive terminal-box bottom that hugs the content height so
    short scenes don't leave a large empty void. Clamped to the canonical box."""
    content_top = TERM_BOX[1] + 52 + top_pad
    n = max(n_lines, min_lines)
    return min(TERM_BOX[3], content_top + n * lh + bottom_pad)


def draw_term_lines(img, origin, lines, font_size=27, lh=38):
    """lines: list of (text, color) or (segments) where segments is list of (text,color)."""
    d = ImageDraw.Draw(img, "RGBA")
    ox, oy = origin
    f = mono(font_size)
    y = oy
    for ln in lines:
        if ln is None:
            y += lh
            continue
        if isinstance(ln, str):
            d.text((ox, y), ln, font=f, fill=INK)
        else:
            x = ox
            for seg in ln:
                txt, col = seg[0], seg[1]
                bold = len(seg) > 2 and seg[2]
                ff = mono(font_size, bold=bold)
                d.text((x, y), txt, font=ff, fill=col)
                x += text_width(ff, txt)
        y += lh
    return y


def cursor_block(img, x, y, font_size=27, on=True):
    if not on:
        return
    d = ImageDraw.Draw(img, "RGBA")
    f = mono(font_size)
    w = text_width(f, "M")
    d.rectangle([x, y + 3, x + w, y + font_size + 6], fill=(*BLUE, 230))


def _needs_kr(ch: str) -> bool:
    return ord(ch) >= 0x1100


def draw_mixed(d: ImageDraw.ImageDraw, xy, text: str, size: int, fill,
               bold: bool = False, kr_weight: str = "medium") -> float:
    """Draw a string switching between Menlo (ASCII/code) and the Korean font
    for Hangul/CJK runs, so mixed Korean+code never renders as tofu boxes."""
    x, y = xy
    if not text:
        return x
    runs: list[tuple[str, bool]] = []
    cur, cur_kr = "", _needs_kr(text[0])
    for ch in text:
        k = _needs_kr(ch)
        if k == cur_kr:
            cur += ch
        else:
            runs.append((cur, cur_kr))
            cur, cur_kr = ch, k
    runs.append((cur, cur_kr))
    for run, is_kr in runs:
        font = kr(size, kr_weight) if is_kr else mono(size, bold=bold)
        # nudge Korean down a hair to sit on the mono baseline
        oy = 1 if is_kr else 0
        d.text((x, y + oy), run, font=font, fill=fill)
        x += font.getlength(run)
    return x


def mixed_width(text: str, size: int, bold: bool = False, kr_weight: str = "medium") -> float:
    x = 0.0
    if not text:
        return 0.0
    runs: list[tuple[str, bool]] = []
    cur, cur_kr = "", _needs_kr(text[0])
    for ch in text:
        k = _needs_kr(ch)
        if k == cur_kr:
            cur += ch
        else:
            runs.append((cur, cur_kr))
            cur, cur_kr = ch, k
    runs.append((cur, cur_kr))
    for run, is_kr in runs:
        font = kr(size, kr_weight) if is_kr else mono(size, bold=bold)
        x += font.getlength(run)
    return x


def wrap_mixed(text: str, size: int, max_w: float, bold: bool = False) -> list[str]:
    out: list[str] = []
    for para in text.split("\n"):
        words = para.split(" ")
        line = ""
        for w in words:
            cand = w if not line else line + " " + w
            if mixed_width(cand, size, bold) <= max_w:
                line = cand
                continue
            if line:
                out.append(line)
            line = w
        out.append(line)
    return out


# ---------------------------------------------------------------------------
# Slides + scene builders
# ---------------------------------------------------------------------------

@dataclass
class Module:
    key: str
    slides: list[tuple[Image.Image, float]] = field(default_factory=list)

    def add(self, img: Image.Image, dur: float):
        self.slides.append((img, dur))

    def hold(self, dur: float):
        if self.slides:
            self.slides.append((self.slides[-1][0], dur))


def ease(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


# ---------------------------------------------------------------------------
# Rendering pipeline
# ---------------------------------------------------------------------------

def render_module(mod: Module, workdir: Path, outdir: Path) -> Path:
    frames_dir = workdir / mod.key
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)

    listing = []
    # Dedup consecutive identical images by reference to cut PNG count.
    idx = 0
    last_ref = None
    last_path = None
    for img, dur in mod.slides:
        if img is last_ref and last_path is not None:
            path = last_path
        else:
            path = frames_dir / f"f{idx:05d}.png"
            img.save(path)
            idx += 1
            last_ref = img
            last_path = path
        listing.append((path, dur))

    concat = frames_dir / "list.txt"
    with concat.open("w") as fh:
        for path, dur in listing:
            fh.write(f"file '{path.name}'\n")
            fh.write(f"duration {dur:.4f}\n")
        # concat demuxer needs the last file repeated
        fh.write(f"file '{listing[-1][0].name}'\n")

    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{mod.key}.mp4"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", "list.txt",
        "-fps_mode", "cfr", "-r", str(FPS),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-g", str(FPS * 2),
        "-movflags", "+faststart",
        str(out.resolve()),
    ]
    subprocess.run(cmd, cwd=frames_dir, check=True)
    return out


def concat_modules(mod_paths: list[Path], final: Path):
    lst = final.parent / "_modules.txt"
    with lst.open("w") as fh:
        for p in mod_paths:
            fh.write(f"file '{p.resolve()}'\n")
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c", "copy", "-movflags", "+faststart",
        str(final.resolve()),
    ]
    subprocess.run(cmd, check=True)
    lst.unlink(missing_ok=True)

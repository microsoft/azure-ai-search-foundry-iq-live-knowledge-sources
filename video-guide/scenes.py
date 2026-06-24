"""High-level scene builders that append slides to a Module."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageDraw

import engine as E
from engine import (
    BLUE, BLUE_DK, DIM, FAINT, GREEN, INK, ORANGE, PANEL, PANEL_HEAD, PANEL_LINE,
    RED, TERM_BG, TERM_BOX, WHITE, YELLOW, GREEN_DK, CAPTION_BG,
    Ctx, Module, W, H, MARGIN, FPS, ease, fresh_bg, draw_chrome, kr, mono,
    rounded, terminal_window, draw_term_lines, text_width, wrap,
)

STEP = 1.0 / FPS


# ---------------------------------------------------------------------------
# compose: bg + chrome + terminal + lines (+ optional cursor)
# ---------------------------------------------------------------------------

def compose(ctx: Ctx, term_title: str, lines, cursor_last: str | None = None,
            font_size=27, lh=38, chrome=True) -> Image.Image:
    img = fresh_bg()
    if chrome:
        draw_chrome(img, ctx)
    origin = terminal_window(img, term_title)
    end_y = draw_term_lines(img, origin, lines, font_size=font_size, lh=lh)
    if cursor_last is not None:
        # place cursor after the last rendered line
        ox, _ = origin
        last_y = origin[1] + (len(lines) - 1) * lh
        cx = ox + text_width(mono(font_size), cursor_last)
        E.cursor_block(img, cx, last_y, font_size=font_size, on=True)
    return img


# ---------------------------------------------------------------------------
# Title / section card
# ---------------------------------------------------------------------------

def title_card(mod: Module, ctx: Ctx, title: str, subtitle: str = "",
               bullets: list[str] | None = None, code: str = "",
               hold=2.4, big=False):
    bullets = bullets or []

    def frame(n_bul: int, code_on: bool) -> Image.Image:
        img = fresh_bg()
        c = replace(ctx, scene_title="")
        draw_chrome(img, c)
        cx = W // 2
        ty = 300 if big else 330
        tf = kr(96 if big else 68, "bold")
        tw = text_width(tf, title)
        d = ImageDraw.Draw(img, "RGBA")
        # accent kicker
        if subtitle:
            sf = kr(34, "semibold")
            sw = text_width(sf, subtitle)
            rounded(d, [cx - sw // 2 - 22, ty - 70, cx + sw // 2 + 22, ty - 18], 14,
                    fill=(*BLUE_DK, 60), outline=(*BLUE, 200), width=2)
            d.text((cx - sw // 2, ty - 64), subtitle, font=sf, fill=BLUE)
        for ln in E.wrap(tf, title, W - 360):
            lw = text_width(tf, ln)
            d.text((cx - lw // 2, ty), ln, font=tf, fill=WHITE)
            ty += (104 if big else 80)
        ty += 12
        bf = kr(38, "medium")
        for i, b in enumerate(bullets[:n_bul]):
            by = ty + i * 64
            d.ellipse([cx - 300, by + 16, cx - 286, by + 30], fill=BLUE)
            d.text((cx - 264, by), b, font=bf, fill=INK)
        if code and code_on:
            cf = mono(30, bold=True)
            cw = text_width(cf, code)
            bx0 = cx - cw // 2 - 30
            byy = ty + max(1, len(bullets)) * 64 + 28
            rounded(d, [bx0, byy, cx + cw // 2 + 30, byy + 64], 12,
                    fill=(*TERM_BG, 255), outline=(*PANEL_LINE, 255), width=2)
            d.text((cx - cw // 2, byy + 14), code, font=cf, fill=GREEN)
        return img

    # reveal bullets one at a time
    mod.add(frame(0, False), 0.7)
    for i in range(1, len(bullets) + 1):
        mod.add(frame(i, False), 0.5)
    if code:
        mod.add(frame(len(bullets), True), hold)
    else:
        mod.hold(hold)


# ---------------------------------------------------------------------------
# Terminal scene: type a command, reveal output, return final image
# ---------------------------------------------------------------------------

def terminal_scene(mod: Module, ctx: Ctx, prompt: str, command: str,
                   output: list, term_title="bash — live-knowledge-sources",
                   type_speed=0.028, line_reveal=0.10, settle=2.4,
                   pre_lines: list | None = None, font_size=27, lh=38,
                   explains: list | None = None, explain_hold=4.1) -> tuple:
    """pre_lines: already-shown lines (history) above the prompt.
    explains: list of (caption, caption_sub) shown after output, each held to let
    the viewer read what each part of the output means."""
    pre_lines = pre_lines or []
    promptseg = [(prompt, GREEN, True)]

    # ---- type the command ----
    full = command
    step = max(1, len(full) // 36)
    i = 0
    while i < len(full):
        i = min(len(full), i + step)
        typed = full[:i]
        line = list(promptseg) + [(typed, INK)]
        cursor_text = prompt + typed
        img = compose(ctx, term_title, pre_lines + [line], cursor_last=cursor_text,
                      font_size=font_size, lh=lh)
        mod.add(img, type_speed)
    # blink hold on full command
    full_cmd_line = list(promptseg) + [(full, INK)]
    img = compose(ctx, term_title, pre_lines + [full_cmd_line],
                  cursor_last=prompt + full, font_size=font_size, lh=lh)
    mod.add(img, 0.5)

    # ---- reveal output ----
    shown: list = pre_lines + [full_cmd_line]
    # group reveal: a few lines per slide for long outputs
    chunk = 1 if len(output) <= 14 else 2
    k = 0
    final_img = img
    while k < len(output):
        grp = output[k:k + chunk]
        k += chunk
        shown = shown + grp
        final_img = compose(ctx, term_title, shown, font_size=font_size, lh=lh)
        mod.add(final_img, line_reveal)
    mod.hold(settle)
    # explanatory caption walk over the same final output
    for cap, sub in (explains or []):
        ectx = replace(ctx, caption=cap, caption_sub=sub)
        eimg = compose(ectx, term_title, shown, font_size=font_size, lh=lh)
        mod.add(eimg, explain_hold)
    return final_img, shown, term_title


def term_caption_hold(mod: Module, base_img: Image.Image, ctx: Ctx, dur: float):
    """Re-stamp the same terminal body with a different caption (ctx)."""
    # We can't easily strip the old caption; instead rebuild requires the lines.
    # Simpler: caller passes a freshly composed image. This helper just adds it.
    mod.add(base_img, dur)


# ---------------------------------------------------------------------------
# Zoom-crop callout
# ---------------------------------------------------------------------------

def zoom_term(mod: Module, scene_result, roi, explain: str, sub: str = "",
              tag="확대 / ZOOM", settle=2.8, font_size=27, lh=38):
    """Compose a chrome-free terminal base from a terminal_scene result, then zoom."""
    _final, lines, term_title = scene_result
    ctx = Ctx(1, 1, "")  # chrome disabled, so labels are irrelevant
    clean = compose(ctx, term_title, lines, font_size=font_size, lh=lh, chrome=False)
    zoom_callout(mod, clean, roi, explain, sub=sub, tag=tag, settle=settle)


def _roi_169(roi):
    x0, y0, x1, y1 = roi
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = x1 - x0, y1 - y0
    if w / h < W / H:
        w = h * W / H
    else:
        h = w * H / W
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - h / 2, cy + h / 2
    # clamp
    if x0 < 0:
        x1 -= x0; x0 = 0
    if y0 < 0:
        y1 -= y0; y0 = 0
    if x1 > W:
        x0 -= (x1 - W); x1 = W
    if y1 > H:
        y0 -= (y1 - H); y1 = H
    return (max(0, x0), max(0, y0), min(W, x1), min(H, y1))


def _lerp_rect(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(4))


def zoom_callout(mod: Module, base_img: Image.Image, roi, explain: str,
                 sub: str = "", tag="확대 / ZOOM", steps=12, settle=2.8,
                 zoom_out=False):
    full = (0, 0, W, H)
    target = _roi_169(roi)

    def crop_at(rect):
        r = tuple(int(round(v)) for v in rect)
        return base_img.crop(r).resize((W, H), Image.LANCZOS)

    # zoom in
    for s in range(steps):
        t = ease(s / (steps - 1))
        img = crop_at(_lerp_rect(full, target, t))
        mod.add(img, STEP)

    # settle frame with explanation overlay
    final = crop_at(target).copy()
    d = ImageDraw.Draw(final, "RGBA")
    # zoom tag chip
    tf = kr(28, "bold")
    tw = text_width(tf, tag)
    rounded(d, [MARGIN, 56, MARGIN + tw + 70, 56 + 50], 14,
            fill=(*ORANGE, 235))
    d.ellipse([MARGIN + 16, 68, MARGIN + 40, 92], outline=(40, 24, 8), width=4)
    d.line([MARGIN + 38, 90, MARGIN + 50, 102], fill=(40, 24, 8), width=4)
    d.text((MARGIN + 58, 64), tag, font=tf, fill=(40, 24, 8))
    # explanation panel (lower third)
    cap_top = 900
    rounded(d, [MARGIN, cap_top, W - MARGIN, cap_top + 128], 16,
            fill=(*CAPTION_BG, 240), outline=(*ORANGE, 255), width=2)
    rounded(d, [MARGIN, cap_top, MARGIN + 8, cap_top + 128], 4, fill=(*ORANGE, 255))
    ef = kr(36, "semibold")
    lines = wrap(ef, explain, W - 2 * MARGIN - 80)[:2]
    ty = cap_top + (24 if not sub else 18)
    for ln in lines:
        d.text((MARGIN + 36, ty), ln, font=ef, fill=INK)
        ty += 42
    if sub:
        d.text((MARGIN + 36, ty + 2), sub, font=mono(24, bold=True), fill=ORANGE)
    mod.add(final, settle)

    if zoom_out:
        for s in range(steps):
            t = ease(s / (steps - 1))
            img = crop_at(_lerp_rect(target, full, t))
            mod.add(img, STEP)


# ---------------------------------------------------------------------------
# File viewer (editor-like)
# ---------------------------------------------------------------------------

def file_view(mod: Module, ctx: Ctx, filename: str, numbered_lines: list,
              highlights: set | None = None, start_no=1, reveal=True,
              settle=2.6, font_size=24, lh=34) -> Image.Image:
    """numbered_lines: list of (text, color)."""
    highlights = highlights or set()

    def frame(n: int) -> Image.Image:
        img = fresh_bg()
        draw_chrome(img, ctx)
        ox, oy = terminal_window(img, f"{filename}")
        d = ImageDraw.Draw(img, "RGBA")
        gutter_w = 64
        x_code = ox + gutter_w + 18
        f = mono(font_size)
        gf = mono(font_size - 2)
        y = oy
        for i, (text, col) in enumerate(numbered_lines[:n]):
            no = start_no + i
            if no in highlights:
                d.rounded_rectangle([ox - 6, y - 4, TERM_BOX[2] - 24, y + lh - 6], 6,
                                    fill=(*BLUE_DK, 46))
                d.rectangle([ox - 6, y - 4, ox - 1, y + lh - 6], fill=(*BLUE, 255))
            d.text((ox + gutter_w - text_width(gf, str(no)), y),
                   str(no), font=gf, fill=FAINT if no not in highlights else BLUE)
            d.text((x_code, y), text, font=f, fill=col)
            y += lh
        return img

    total = len(numbered_lines)
    if reveal:
        block = max(1, total // 6)
        n = 0
        img = frame(0)
        while n < total:
            n = min(total, n + block)
            img = frame(n)
            mod.add(img, 0.16)
        mod.hold(settle)
        return img
    else:
        img = frame(total)
        mod.add(img, settle)
        return img


# ---------------------------------------------------------------------------
# Tree view
# ---------------------------------------------------------------------------

def tree_view(mod: Module, ctx: Ctx, header: str, entries: list, settle=2.8,
              reveal=True):
    """entries: list of dict(indent, name, comment, kind)."""

    def frame(n: int) -> Image.Image:
        img = fresh_bg()
        draw_chrome(img, ctx)
        ox, oy = terminal_window(img, header)
        d = ImageDraw.Draw(img, "RGBA")
        f = mono(26)
        cf = mono(22)
        y = oy
        for e in entries[:n]:
            indent = e["indent"]
            x = ox + indent * 40
            glyph = "├─ " if not e.get("last") else "└─ "
            if indent == 0:
                glyph = ""
            kind = e.get("kind", "file")
            name = e["name"]
            col = {"dir": BLUE, "emph": ORANGE, "file": INK, "root": WHITE}.get(kind, INK)
            d.text((x, y), glyph, font=f, fill=FAINT)
            gx = x + text_width(f, glyph)
            nm = name + ("/" if kind in ("dir", "root") else "")
            d.text((gx, y), nm, font=mono(26, bold=(kind in ("emph", "root", "dir"))), fill=col)
            comment = e.get("comment", "")
            if comment:
                E.draw_mixed(d, (ox + 760, y + 2), "→ " + comment, 22, DIM)
            y += 40
        return img

    total = len(entries)
    if reveal:
        n = 0
        img = frame(0)
        while n < total:
            n += 1
            img = frame(n)
            mod.add(img, 0.12)
        mod.hold(settle)
    else:
        mod.add(frame(total), settle)


# ---------------------------------------------------------------------------
# Pipeline summary card
# ---------------------------------------------------------------------------

def pipeline_card(mod: Module, ctx: Ctx, title: str, steps: list, footer: list,
                  settle=3.4):
    """steps: list of (label_en, label_kr, color). footer: list of (label, value)."""

    def frame(n: int, n_foot: int) -> Image.Image:
        img = fresh_bg()
        draw_chrome(img, replace(ctx, scene_title=title))
        d = ImageDraw.Draw(img, "RGBA")
        cy = 300
        chip_h = 92
        gap = 24
        arrow = 38
        ef = mono(26, bold=True)
        kf = kr(23, "medium")
        widths = []
        for en, krl, _ in steps:
            widths.append(max(text_width(ef, en), text_width(kf, krl)) + 48)
        total_w = sum(widths) + (gap + arrow) * (len(steps) - 1)
        x = (W - total_w) / 2
        for i, (en, krl, col) in enumerate(steps):
            on = i < n
            cw = widths[i]
            rounded(d, [x, cy, x + cw, cy + chip_h], 16,
                    fill=(*PANEL, 255) if on else (*PANEL, 120),
                    outline=(*col, 255) if on else (*FAINT, 110), width=3)
            if on:
                rounded(d, [x, cy, x + cw, cy + 7], 4, fill=(*col, 255))
                ew = text_width(ef, en)
                d.text((x + (cw - ew) / 2, cy + 18), en, font=ef, fill=col)
                kw = text_width(kf, krl)
                d.text((x + (cw - kw) / 2, cy + 52), krl, font=kf, fill=INK)
            else:
                ew = text_width(ef, en)
                d.text((x + (cw - ew) / 2, cy + 34), en, font=ef, fill=FAINT)
            x += cw
            if i < len(steps) - 1:
                acol = steps[i][2] if i < n - 1 else FAINT
                midy = cy + chip_h / 2
                d.line([x + 6, midy, x + gap + arrow - 8, midy], fill=(*acol, 255), width=4)
                d.polygon([(x + gap + arrow - 8, midy - 8),
                           (x + gap + arrow + 4, midy),
                           (x + gap + arrow - 8, midy + 8)], fill=(*acol, 255))
                x += gap + arrow
        # footer panel
        if n_foot:
            fy0 = 500
            rounded(d, [MARGIN + 40, fy0, W - MARGIN - 40, fy0 + 60 + 56 * len(footer)], 16,
                    fill=(*E.CAPTION_BG, 230), outline=(*PANEL_LINE, 255), width=2)
            ff = kr(29, "medium")
            mf = mono(25, bold=True)
            fy = fy0 + 34
            for j, (label, val) in enumerate(footer[:n_foot]):
                d.text((MARGIN + 80, fy), "▸", font=ff, fill=GREEN)
                d.text((MARGIN + 116, fy), label, font=ff, fill=DIM)
                d.text((MARGIN + 116 + text_width(ff, label) + 16, fy - 1), val, font=mf, fill=INK)
                fy += 56
        return img

    for i in range(1, len(steps) + 1):
        mod.add(frame(i, 0), 0.45)
    mod.hold(0.5)
    for j in range(1, len(footer) + 1):
        mod.add(frame(len(steps), j), 0.5)
    mod.hold(settle)


# ---------------------------------------------------------------------------
# Key-value card (inputs / checklist values)
# ---------------------------------------------------------------------------

def kv_card(mod: Module, ctx: Ctx, panel_title: str, rows: list, note: str = "",
            settle=3.0, reveal=True):
    """rows: list of (key, value, hint). value colored green, hint dim."""

    def frame(n: int) -> Image.Image:
        img = fresh_bg()
        draw_chrome(img, ctx)
        ox, oy = terminal_window(img, panel_title)
        d = ImageDraw.Draw(img, "RGBA")
        kf = mono(27, bold=True)
        vf = mono(27)
        hf = kr(23, "medium")
        col_k = ox
        col_v = ox + 520
        y = oy + 6
        for i, row in enumerate(rows[:n]):
            key, val, hint = (row + ("",))[:3] if len(row) < 3 else row
            E.draw_mixed(d, (col_k, y), key, 27, BLUE, bold=True)
            E.draw_mixed(d, (col_v, y), val, 27, GREEN)
            if hint:
                E.draw_mixed(d, (col_v, y + 34), hint, 23, DIM)
                y += 80
            else:
                y += 56
        if note:
            ny = TERM_BOX[3] - 92
            d.line([ox, ny - 14, TERM_BOX[2] - 30, ny - 14], fill=(*PANEL_LINE, 255), width=2)
            for k, ln in enumerate(wrap(kr(26, "medium"), note, TERM_BOX[2] - ox - 60)[:2]):
                d.text((ox, ny + k * 36), ln, font=kr(26, "medium"), fill=ORANGE)
        return img

    total = len(rows)
    if reveal:
        for n in range(1, total + 1):
            mod.add(frame(n), 0.4)
        mod.hold(settle)
    else:
        mod.add(frame(total), settle)


# ---------------------------------------------------------------------------
# Note / checklist card (info / warn / ok bullets)
# ---------------------------------------------------------------------------

def note_card(mod: Module, ctx: Ctx, panel_title: str, items: list,
              settle=3.0, reveal=True):
    """items: list of (kind, text) where kind in ok|warn|info|step|bad."""
    icon_col = {"ok": GREEN, "warn": ORANGE, "info": BLUE, "step": INK, "bad": RED}

    def draw_icon(d, kind, x, y, s=34):
        col = icon_col.get(kind, BLUE)
        d.ellipse([x, y, x + s, y + s], outline=(*col, 255), width=3)
        cx, cy = x + s / 2, y + s / 2
        if kind == "ok":
            d.line([(x + 9, cy + 1), (cx - 2, y + s - 9), (x + s - 7, y + 9)],
                   fill=(*col, 255), width=4, joint="curve")
        elif kind == "bad":
            d.line([(x + 10, y + 10), (x + s - 10, y + s - 10)], fill=(*col, 255), width=4)
            d.line([(x + s - 10, y + 10), (x + 10, y + s - 10)], fill=(*col, 255), width=4)
        elif kind == "warn":
            d.line([(cx, y + 8), (cx, y + s - 13)], fill=(*col, 255), width=4)
            d.ellipse([cx - 2.5, y + s - 11, cx + 2.5, y + s - 6], fill=(*col, 255))
        elif kind == "info":
            d.ellipse([cx - 2.5, y + 8, cx + 2.5, y + 13], fill=(*col, 255))
            d.line([(cx, y + 16), (cx, y + s - 8)], fill=(*col, 255), width=4)
        else:  # step
            d.line([(x + 12, y + 9), (x + s - 10, cy), (x + 12, y + s - 9)],
                   fill=(*col, 255), width=4, joint="curve")

    def frame(n: int) -> Image.Image:
        img = fresh_bg()
        draw_chrome(img, ctx)
        ox, oy = terminal_window(img, panel_title)
        d = ImageDraw.Draw(img, "RGBA")
        size = 30
        y = oy + 6
        for kind, text in items[:n]:
            draw_icon(d, kind, ox, y, 34)
            tx = ox + 56
            wl = E.wrap_mixed(text, size, TERM_BOX[2] - tx - 50)[:2]
            for li, ln in enumerate(wl):
                E.draw_mixed(d, (tx, y + li * 38), ln, size, INK)
            y += 40 + 38 * (max(1, min(len(wl), 2)) - 1) + 26
        return img

    total = len(items)
    if reveal:
        for n in range(1, total + 1):
            mod.add(frame(n), 0.5)
        mod.hold(settle)
    else:
        mod.add(frame(total), settle)

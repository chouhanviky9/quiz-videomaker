"""
Video renderer — builds each 13-second question clip.

Layout (1920×1080):
  ┌─────────────────────────────────────┐
  │  ① QUESTION TEXT (red header bar)   │  ~300px
  ├─────────────────────────────────────┤
  │  [A] Option A     [B] Option B      │
  │  [C] Option C     [D] Option D      │  ~550px
  ├─────────────────────────────────────┤
  │         ██████░░░ timer bar         │  ~80px
  └─────────────────────────────────────┘

Timeline:
  0s–10s   Question displayed + countdown bar shrinks + TTS plays
  10s–13s  Correct answer highlighted green, wrong ones red
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    AudioFileClip,
    VideoClip,
    CompositeVideoClip,
    CompositeAudioClip,
    concatenate_videoclips,
)

from config.config import config
from config.constant import (
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
)
from sheets import Question

logger = logging.getLogger(__name__)

# ── Logo loader (cached) ────────────────────────────────────────────────────
_logo_cache: dict[str, Image.Image | None] = {}


def _load_logo_from_url(url: str) -> Image.Image | None:
    """Load a logo image from a URL (https:// or data:image/... base64).
    Returns an RGBA PIL Image or None on failure."""
    if url in _logo_cache:
        return _logo_cache[url]

    img = None
    try:
        if url.startswith("data:image"):
            # data:image/png;base64,iVBOR...
            header, b64data = url.split(",", 1)
            img = Image.open(io.BytesIO(base64.b64decode(b64data))).convert("RGBA")
        elif url.startswith(("http://", "https://")):
            import urllib.request
            with urllib.request.urlopen(url, timeout=10) as resp:
                img = Image.open(io.BytesIO(resp.read())).convert("RGBA")
        else:
            logger.warning(f"Unsupported logo URL scheme: {url[:60]}...")
    except Exception as e:
        logger.warning(f"Failed to load logo from URL: {e}")

    _logo_cache[url] = img
    return img


def clear_render_caches():
    """Clear all per-question render caches between batches."""
    global _clock_tick_loaded
    _badge_cache.clear()
    _qtext_cache.clear()
    _option_card_cache.clear()
    _static_layer_cache.clear()
    _timer_mask_cache.clear()
    _timer_pattern_cache.clear()

# ── Layout constants ─────────────────────────────────────────────────────────
HEADER_HEIGHT = 280
HEADER_Y = 0
OPTIONS_Y = 435
OPTION_W = 850
OPTION_H = 150
OPTION_GAP_X = 40
OPTION_GAP_Y = 30
OPTION_GRID_LEFT = (VIDEO_WIDTH - (2 * OPTION_W + OPTION_GAP_X)) // 2
TIMER_Y = 920
TIMER_H = 65
TIMER_W = 1104
TIMER_X = (VIDEO_WIDTH - TIMER_W) // 2
TIMER_RADIUS = 25
BADGE_RADIUS = 45
NUMBER_BADGE_RADIUS = 38


# ── Pillow helpers ───────────────────────────────────────────────────────────

def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a TTF font, falling back to default if file is missing."""
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        logger.warning(f"Font not found: {path} — using default")
        return ImageFont.load_default()


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, ...],
    outline: Optional[tuple[int, ...]] = None,
    width: int = 0,
) -> None:
    """Draw a rounded rectangle on a Pillow ImageDraw."""
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _draw_circle(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    radius: int,
    fill: tuple[int, ...],
) -> None:
    """Draw a filled circle."""
    x, y = center
    draw.ellipse(
        [x - radius, y - radius, x + radius, y + radius],
        fill=fill,
    )


def _draw_gradient_circle(
    img: Image.Image,
    center: tuple[int, int],
    radius: int,
    color_top: tuple[int, ...],
    color_bottom: tuple[int, ...],
) -> None:
    """Draw a circle with a vertical gradient (top to bottom) using fast numpy ops."""
    cx, cy = center
    size = radius * 2
    if size <= 0:
        return
    # Build circular mask using numpy
    yy, xx = np.ogrid[:size, :size]
    dist_sq = (xx - radius + 0.5) ** 2 + (yy - radius + 0.5) ** 2
    mask_arr = (dist_sq <= radius ** 2).astype(np.uint8) * 255
    # Build vertical gradient RGBA array
    t = np.linspace(0, 1, size).reshape(-1, 1)  # (size, 1)
    ct = np.array(color_top[:3], dtype=np.float32)
    cb = np.array(color_bottom[:3], dtype=np.float32)
    grad_colors = (ct + (cb - ct) * t).astype(np.uint8)  # (size, 3)
    # Expand to full image: (size, size, 4)
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[:, :, :3] = grad_colors[:, np.newaxis, :]
    arr[:, :, 3] = mask_arr
    gradient_img = Image.fromarray(arr, "RGBA")
    paste_x = cx - radius
    paste_y = cy - radius
    img.paste(gradient_img, (paste_x, paste_y), mask=gradient_img)


def _text_center(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    area: tuple[int, int, int, int],
    fill: tuple[int, ...],
    shadow_offset: int = 0,
    shadow_color: tuple[int, ...] = (0, 0, 0),
) -> None:
    """Draw text centered within a bounding box with optional 3D embossed shadow."""
    x1, y1, x2, y2 = area
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    # Use exact font height based on metrics instead of bbox offset to ensure perfect vertical center
    th = font.getbbox("A")[3] - font.getbbox("A")[1] 
    
    tx = x1 + (x2 - x1 - tw) // 2
    ty = y1 + (y2 - y1 - th) // 2 - 5 # slight 5px adjustment for montserrat baseline
    # 3D embossed shadow
    if shadow_offset > 0:
        draw.text((tx + shadow_offset, ty + shadow_offset), text, font=font, fill=shadow_color)
    draw.text((tx, ty), text, font=font, fill=fill)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    """Wrap text to fit within max_width pixels."""
    words = text.split()
    lines: list[str] = []
    current_line = ""

    dummy_img = Image.new("RGB", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = dummy_draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return "\n".join(lines)


# ── Frame renderers ──────────────────────────────────────────────────────────


_bg_cache = None

def _get_background_layer() -> tuple:
    # Removed generic _bg_cache so background color changes reflect dynamically
    SCALE = 2  # Supersampling factor for anti-aliasing shapes/text
    
    def s(val: int | float) -> int:
        return int(val * SCALE)

    img = Image.new("RGB", (s(VIDEO_WIDTH), s(VIDEO_HEIGHT)), config.get("COLOR_BG_BLUE"))
    draw = ImageDraw.Draw(img)

    # ── Header bar (red gradient) with raised effect ─────────────────────
    half = s(HEADER_HEIGHT) // 2
    draw.rectangle([0, 0, s(VIDEO_WIDTH), half], fill=config.get("COLOR_HEADER_RED"))
    draw.rectangle([0, half, s(VIDEO_WIDTH), s(HEADER_HEIGHT)], fill=config.get("COLOR_HEADER_RED_DARK"))
    # Thick white divider line
    draw.rectangle([0, s(HEADER_HEIGHT), s(VIDEO_WIDTH), s(HEADER_HEIGHT + 8)], fill=config.get("COLOR_WHITE"))
    # Dark bottom shadow under header for 3D raised effect
    shadow_dark = config.get("COLOR_SHADOW_DARK")
    draw.rectangle([0, s(HEADER_HEIGHT + 8), s(VIDEO_WIDTH), s(HEADER_HEIGHT + 20)], fill=shadow_dark)
    # Softer shadow fade
    shadow_mid = (shadow_dark[0], shadow_dark[1], shadow_dark[2] + 30)
    draw.rectangle([0, s(HEADER_HEIGHT + 20), s(VIDEO_WIDTH), s(HEADER_HEIGHT + 28)], fill=shadow_mid)

    # Downscale for smooth anti-aliased output
    final_img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.Resampling.LANCZOS)
    return final_img

_badge_cache = {}

def _get_badge_layer(text: str, is_logo: bool = False) -> Image.Image:
    if is_logo:
        try:
            logo_img = None
            # 1) Try loading from config URL (set via Google Sheet)
            logo_url = config.get("VIDEO_TOPRIGHT_LOGO", "")
            if logo_url:
                logo_img = _load_logo_from_url(logo_url)

            # 2) Fallback to local file
            if logo_img is None:
                logo_path = Path("assets/logos/video-maker-logo.png")
                if logo_path.exists():
                    logo_img = Image.open(logo_path).convert("RGBA")

            if logo_img is not None:
                size = (NUMBER_BADGE_RADIUS + 5) * 2
                logo_img.thumbnail((size, size))
                return logo_img
        except Exception as e:
            logger.warning(f"Could not load logo in renderer: {e}")
            
    if text in _badge_cache:
        return _badge_cache[text]

    SCALE = 2
    def s(val: int | float) -> int:
        return int(val * SCALE)
        
    margin = 10
    total_radius = s(NUMBER_BADGE_RADIUS + 5)
    size = total_radius * 2 + s(margin) * 2
    img = Image.new("RGBA", (size, size), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2

    # Dark bottom shadow for raised 3D effect
    shadow_offset = s(2)
    _draw_circle(draw, (cx, cy + shadow_offset), s(NUMBER_BADGE_RADIUS + 6), (10, 10, 40, 160))
    # White outer ring
    _draw_circle(draw, (cx, cy), s(NUMBER_BADGE_RADIUS + 5), config.get("COLOR_WHITE"))
    # Inner fill
    _draw_circle(draw, (cx, cy), s(NUMBER_BADGE_RADIUS), config.get("COLOR_NUMBER_BADGE_BG"))
    # Thick dark border
    # draw.ellipse(
    #     [cx - s(NUMBER_BADGE_RADIUS + 5), cy - s(NUMBER_BADGE_RADIUS + 5), cx + s(NUMBER_BADGE_RADIUS + 5), cy + s(NUMBER_BADGE_RADIUS + 5)],
    #     outline=config.get("COLOR_BLACK"),
    #     width=s(5)
    # )
    num_font = _load_font(config.get("FONT_EXTRABOLD"), s(36))
    _text_center(draw, text, num_font, (cx - s(25), cy - s(24), cx + s(25), cy + s(16)), config.get("COLOR_WHITE"),
                 shadow_offset=s(2), shadow_color=(0, 0, 0))

    final_img = img.resize((size // 2, size // 2), Image.Resampling.LANCZOS)
    _badge_cache[text] = final_img
    return final_img

_qtext_cache = {}

def _get_question_text_layer(question: Question) -> Image.Image:
    if question.row_index in _qtext_cache:
        return _qtext_cache[question.row_index]

    SCALE = 2
    def s(val: int | float) -> int:
        return int(val * SCALE)

    img = Image.new("RGBA", (s(VIDEO_WIDTH), s(HEADER_HEIGHT)), (0,0,0,0))
    draw = ImageDraw.Draw(img)

    max_font_size = 56
    min_font_size = 20
    font_size = max_font_size
    max_w = s(VIDEO_WIDTH - 200)
    max_h = s(HEADER_HEIGHT - 60) # leave some padding top and bottom
    
    while font_size >= min_font_size:
        q_font = _load_font(config.get("FONT_EXTRABOLD"), s(font_size))
        wrapped = _wrap_text(question.text.upper(), q_font, max_w)
        bbox = draw.textbbox((0, 0), wrapped, font=q_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        
        if th <= max_h:
            break
        font_size -= 2

    # Draw centered in the header with 3D embossed shadow
    tx = (s(VIDEO_WIDTH) - tw) // 2
    ty = s(30) + (s(HEADER_HEIGHT - 30) - th) // 2
    # Dark shadow offset for 3D emboss
    shadow_off = s(3)
    draw.text((tx + shadow_off, ty + shadow_off), wrapped, font=q_font, fill=(0, 0, 0))
    draw.text((tx, ty), wrapped, font=q_font, fill=config.get("COLOR_WHITE"))

    final_img = img.resize((VIDEO_WIDTH, HEADER_HEIGHT), Image.Resampling.LANCZOS)
    _qtext_cache[question.row_index] = final_img
    return final_img


_timer_pattern_cache = {}

def _interpolate_color(c1: tuple[int, ...], c2: tuple[int, ...], t: float) -> tuple[int, int, int, int]:
    """Interpolate between two RGBA colors."""
    t = max(0.0, min(1.0, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

def _get_timer_colors(progress: float) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Return (base_color, stripe_color) RGBA based on progress (0.0 to 1.0)."""
    GREEN_BASE = (25, 190, 25, 255)
    GREEN_STRIPE = (45, 225, 45, 255)

    YELLOW_BASE = (210, 160, 0, 255)
    YELLOW_STRIPE = (240, 190, 0, 255)

    RED_BASE = (200, 30, 30, 255)
    RED_STRIPE = (230, 50, 50, 255)

    # Convert 1.0 -> 0.0 ranges
    # > 0.40 : Green
    # 0.40 -> 0.30 : Transitiion Green -> Yellow
    # 0.30 -> 0.15 : Yellow
    # 0.15 -> 0.10 : Transition Yellow -> Red
    # < 0.10 : Red
    
    if progress > 0.40:
        return GREEN_BASE, GREEN_STRIPE
    elif progress > 0.30:
        t = (0.40 - progress) / 0.10
        return _interpolate_color(GREEN_BASE, YELLOW_BASE, t), _interpolate_color(GREEN_STRIPE, YELLOW_STRIPE, t)
    elif progress > 0.15:
        return YELLOW_BASE, YELLOW_STRIPE
    elif progress > 0.10:
        t = (0.15 - progress) / 0.05
        return _interpolate_color(YELLOW_BASE, RED_BASE, t), _interpolate_color(YELLOW_STRIPE, RED_STRIPE, t)
    else:
        return RED_BASE, RED_STRIPE


def _get_timer_pattern(progress: float) -> Image.Image:
    """Generates and caches a glossy diagonally striped texture for the timer bar based on progress."""
    base_color, stripe_color = _get_timer_colors(progress)
    cache_key = (base_color, stripe_color)
    
    if cache_key in _timer_pattern_cache:
        return _timer_pattern_cache[cache_key]
        
    pad = 6
    inner_w = TIMER_W - 2 * pad
    inner_h = TIMER_H - 2 * pad
    
    # Base pattern (RGBA to easily composite highlights)
    pattern = Image.new("RGBA", (inner_w, inner_h), base_color)
    draw = ImageDraw.Draw(pattern)
    stripe_w = 25
    # Draw diagonal stripes (\ shape from top-left to bottom-right)
    for x in range(-inner_h * 2, inner_w, stripe_w * 2):
        pts = [
            (x, 0),
            (x + stripe_w, 0),
            (x + stripe_w + inner_h, inner_h),
            (x + inner_h, inner_h)
        ]
        draw.polygon(pts, fill=stripe_color)
        
    # Overlay for a glossy pill effect
    overlay = Image.new("RGBA", (inner_w, inner_h), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    # Highlight top
    overlay_draw.rectangle([0, 0, inner_w, inner_h // 2], fill=(255, 255, 255, 50))
    # Shadow bottom
    overlay_draw.rectangle([0, inner_h - inner_h // 3, inner_w, inner_h], fill=(0, 0, 0, 30))
    
    pattern = Image.alpha_composite(pattern, overlay)
    
    # Convert to RGB since destination image is RGB
    pattern_rgb = pattern.convert("RGB")
    _timer_pattern_cache[cache_key] = pattern_rgb
    return pattern_rgb


_option_card_cache = {}

def _get_option_card_layer(letter: str, text: str, card_state: str = "normal") -> Image.Image:
    key = (letter, text, card_state)
    if key in _option_card_cache:
        return _option_card_cache[key]
        
    SCALE = 2
    def s(val: int | float) -> int:
        return int(val * SCALE)

    margin = 16  # increased margin for shadow room
    card_w_2x = s(OPTION_W + margin*2)
    card_h_2x = s(OPTION_H + margin*2)
    
    img_2x = Image.new("RGBA", (card_w_2x, card_h_2x), (0,0,0,0))
    draw = ImageDraw.Draw(img_2x)
    
    ox = s(margin)
    oy = s(margin)
    pill_radius = s(OPTION_H) // 2  # fully rounded pill shape
    
    if card_state == "correct":
        card_fill = config.get("COLOR_CORRECT_GREEN")
        text_color = config.get("COLOR_WHITE")
        outline = config.get("COLOR_BLACK")
        border_w = s(4)
    elif card_state == "wrong":
        card_fill = config.get("COLOR_WRONG_RED")
        text_color = config.get("COLOR_WHITE")
        outline = config.get("COLOR_BLACK")
        border_w = s(4)
    else:
        card_fill = (255, 255, 255)
        text_color = config.get("COLOR_OPTION_TEXT")
        outline = config.get("COLOR_BLACK")
        border_w = s(4)

    opt_font = _load_font(config.get("FONT_BOLD"), s(42))
    badge_font = _load_font(config.get("FONT_EXTRABOLD"), s(36))

    # ── Dark bottom shadow for raised 3D depth ──
    shadow_offset = s(6)
    shadow_color = (10, 10, 40, 140)
    _draw_rounded_rect(draw, (ox + s(2), oy + shadow_offset, ox + s(OPTION_W) + s(2), oy + s(OPTION_H) + shadow_offset),
                       radius=pill_radius, fill=shadow_color)

    # ── Main card pill shape with thick border ──
    _draw_rounded_rect(draw, (ox, oy, ox + s(OPTION_W), oy + s(OPTION_H)),
                       radius=pill_radius, fill=card_fill, outline=outline, width=border_w)

    # ── Badge circle with gradient ──
    badge_cx = ox + s(65)
    badge_cy = oy + s(OPTION_H) // 2
    
    if card_state != "normal":
        _draw_circle(draw, (badge_cx, badge_cy), s(BADGE_RADIUS + 3), config.get("COLOR_BLACK"))
    else:
        _draw_circle(draw, (badge_cx, badge_cy), s(BADGE_RADIUS + 8), config.get("COLOR_WHITE"))
        draw.ellipse(
            [badge_cx - s(BADGE_RADIUS + 8), badge_cy - s(BADGE_RADIUS + 8), badge_cx + s(BADGE_RADIUS + 8), badge_cy + s(BADGE_RADIUS + 8)],
            fill=None,
            outline=config.get("COLOR_BLACK"),
            width=s(4)
        )

    # Red-orange gradient fill for badge circle
    grad_top = config.get("COLOR_BADGE_GRADIENT_TOP")
    grad_bottom = config.get("COLOR_BADGE_GRADIENT_BOTTOM")
    _draw_gradient_circle(img_2x, (badge_cx, badge_cy), s(BADGE_RADIUS), grad_top, grad_bottom)
    # Re-acquire draw after pasting gradient
    draw = ImageDraw.Draw(img_2x)
    # Thick dark border on badge
    draw.ellipse(
        [badge_cx - s(BADGE_RADIUS), badge_cy - s(BADGE_RADIUS), badge_cx + s(BADGE_RADIUS), badge_cy + s(BADGE_RADIUS)],
        fill=None, outline=config.get("COLOR_BLACK"), width=s(3)
    )
    _text_center(draw, letter, badge_font, (badge_cx - s(20), badge_cy - s(22), badge_cx + s(20), badge_cy + s(14)), config.get("COLOR_WHITE"),
                 shadow_offset=s(2), shadow_color=(0, 0, 0))

    text_area_left = ox + s(140)
    text_area_right = ox + s(OPTION_W - 20)
    text_shadow = s(2)
    _text_center(draw, text.upper(), opt_font, (text_area_left, oy, text_area_right, oy + s(OPTION_H)), text_color,
                 shadow_offset=text_shadow, shadow_color=(0, 0, 0, 60) if card_state == "normal" else (0, 0, 0))

    card_1x = img_2x.resize((OPTION_W + margin*2, OPTION_H + margin*2), Image.Resampling.LANCZOS)
    _option_card_cache[key] = card_1x
    return card_1x


# ── Cached static layer per question (badges + text + options at final position) ──
_static_layer_cache: dict[int, Image.Image] = {}

def _get_static_question_layer(question: Question) -> Image.Image:
    """Build and cache the RGBA overlay with badges, question text, and option cards
    at their final (post-intro) positions. This avoids re-compositing ~270+ frames."""
    if question.row_index in _static_layer_cache:
        return _static_layer_cache[question.row_index]

    img = Image.new("RGBA", (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))

    # Badges
    qnum = _get_badge_layer(str(question.row_index))
    logo = _get_badge_layer("Logo", is_logo=True)

    badge_w, badge_h = qnum.size
    qx = 60 - badge_w // 2
    qy = 60 - badge_h // 2
    img.paste(qnum, (qx, qy), mask=qnum)

    logo_w, logo_h = logo.size
    lx = 1860 - logo_w // 2
    ly = 60 - logo_h // 2
    img.paste(logo, (lx, ly), mask=logo)

    # Question text
    qtext = _get_question_text_layer(question)
    img.paste(qtext, (0, 0), mask=qtext)

    # Option cards at final positions
    margin = 16
    options = [
        ("A", question.option_a),
        ("B", question.option_b),
        ("C", question.option_c),
        ("D", question.option_d),
    ]
    positions = [
        (OPTION_GRID_LEFT, OPTIONS_Y),
        (OPTION_GRID_LEFT + OPTION_W + OPTION_GAP_X, OPTIONS_Y),
        (OPTION_GRID_LEFT, OPTIONS_Y + OPTION_H + OPTION_GAP_Y),
        (OPTION_GRID_LEFT + OPTION_W + OPTION_GAP_X, OPTIONS_Y + OPTION_H + OPTION_GAP_Y),
    ]
    for (letter, text), (tgt_x, tgt_y) in zip(options, positions):
        card = _get_option_card_layer(letter, text)
        img.paste(card, (tgt_x - margin, tgt_y - margin), mask=card)

    _static_layer_cache[question.row_index] = img
    return img


# ── Timer bar drawing (extracted for reuse) ──────────────────────────────────
_timer_mask_cache: dict[int, Image.Image] = {}

def _draw_timer_bar(draw: ImageDraw.ImageDraw, img: Image.Image, timer_y: int, timer_progress: float) -> None:
    """Draw the timer bar at the given Y position with the given progress."""
    # Dark bottom shadow for 3D raised timer
    shadow_offset = 5
    _draw_rounded_rect(
        draw,
        (TIMER_X + 2, timer_y + shadow_offset, TIMER_X + TIMER_W + 2, timer_y + TIMER_H + shadow_offset),
        radius=TIMER_RADIUS,
        fill=(10, 10, 40),
    )
    # White track with thick dark border
    _draw_rounded_rect(
        draw,
        (TIMER_X, timer_y, TIMER_X + TIMER_W, timer_y + TIMER_H),
        radius=TIMER_RADIUS,
        fill=config.get("COLOR_WHITE"),
        outline=config.get("COLOR_BLACK"),
        width=3,
    )
    pad = 6
    fill_w = int((TIMER_W - 2 * pad) * max(0.0, min(1.0, timer_progress)))

    if fill_w > (TIMER_RADIUS - pad) * 2:
        inner_h = TIMER_H - 2 * pad
        pattern = _get_timer_pattern(timer_progress)

        # Cache the rounded-rect mask by fill_w to avoid redrawing
        if fill_w not in _timer_mask_cache:
            mask = Image.new("L", (fill_w, inner_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle((0, 0, fill_w, inner_h), radius=TIMER_RADIUS - pad, fill=255)
            _timer_mask_cache[fill_w] = mask
        else:
            mask = _timer_mask_cache[fill_w]

        pattern_cropped = pattern.crop((0, 0, fill_w, inner_h))
        img.paste(pattern_cropped, (TIMER_X + pad, timer_y + pad), mask=mask)


def render_question_frame(
    question: Question,
    timer_progress: float = 1.0,
    state: str = "options",
    reveal_progress: float = 0.0,
    intro_progress: float = 1.0,
) -> np.ndarray:
    """
    Render a single quiz frame as a numpy array (H, W, 3).
    """
    img = _get_background_layer().copy()
    draw = ImageDraw.Draw(img)

    options = [
        ("A", question.option_a),
        ("B", question.option_b),
        ("C", question.option_c),
        ("D", question.option_d),
    ]
    positions = [
        (OPTION_GRID_LEFT, OPTIONS_Y),
        (OPTION_GRID_LEFT + OPTION_W + OPTION_GAP_X, OPTIONS_Y),
        (OPTION_GRID_LEFT, OPTIONS_Y + OPTION_H + OPTION_GAP_Y),
        (OPTION_GRID_LEFT + OPTION_W + OPTION_GAP_X, OPTIONS_Y + OPTION_H + OPTION_GAP_Y),
    ]
    margin = 16

    # ── During intro animation, elements move — cannot use cached static layer ──
    if intro_progress < 1.0:
        # 1. Question number and Logo (left to right / right to left)
        qnum = _get_badge_layer(str(question.row_index))
        logo = _get_badge_layer("Logo", is_logo=True)
        badge_w, badge_h = qnum.size
        tgt_qx = 60 - badge_w // 2
        qx = int(-badge_w + (tgt_qx + badge_w) * intro_progress)
        qy = 60 - badge_h // 2
        img.paste(qnum, (qx, qy), mask=qnum)

        logo_w, logo_h = logo.size
        tgt_lx = 1860 - logo_w // 2
        lx = int(VIDEO_WIDTH + logo_w - (VIDEO_WIDTH + logo_w - tgt_lx) * intro_progress)
        logo_qy = 60 - logo_h // 2
        img.paste(logo, (lx, logo_qy), mask=logo)

        # 2. Question text layer (top to down)
        qtext = _get_question_text_layer(question)
        qw, qh = qtext.size
        ty = int(-qh + qh * intro_progress)
        img.paste(qtext, (0, ty), mask=qtext)

        if state == "options":
            for (letter, text), (tgt_x, tgt_y) in zip(options, positions):
                card = _get_option_card_layer(letter, text)
                startY = HEADER_HEIGHT
                cy = int(startY + (tgt_y - margin - startY) * intro_progress)
                img.paste(card, (tgt_x - margin, cy), mask=card)

            # Timer bar
            tgt_timer_y = TIMER_Y
            startY = VIDEO_HEIGHT
            timer_y_anim = int(startY + (tgt_timer_y - startY) * intro_progress)
            _draw_timer_bar(draw, img, timer_y_anim, timer_progress)

        return np.array(img)

    # ── After intro: use cached static layer (badges + question + options) ──
    static = _get_static_question_layer(question)
    img.paste(static, (0, 0), mask=static)

    if state == "options":
        _draw_timer_bar(draw, img, TIMER_Y, timer_progress)

    elif state in ("reveal", "empty"):
        # Reveal animation: scale up correct option
        for (letter, text), (tgt_x, tgt_y) in zip(options, positions):
            is_correct = (letter == question.letter)
            card_state = "correct" if is_correct else "wrong"
            card = _get_option_card_layer(letter, text, card_state)

            if is_correct:
                scale = 1.0 + 0.05 * reveal_progress
                card_w, card_h = card.size
                scaled_w, scaled_h = int(card_w * scale), int(card_h * scale)
                scaled_card = card.resize((scaled_w, scaled_h), Image.Resampling.BILINEAR)

                cx = tgt_x - margin + card_w // 2
                cy = tgt_y - margin + card_h // 2
                px = cx - scaled_w // 2
                py = cy - scaled_h // 2

                img.paste(scaled_card, (px, py), mask=scaled_card)
            else:
                img.paste(card, (tgt_x - margin, tgt_y - margin), mask=card)

    return np.array(img)

# ── Clip builders ────────────────────────────────────────────────────────────

# Cache the clock tick audio clip (loaded once, reused for all questions)
_clock_tick_cache: list[AudioFileClip | None] = [None]
_clock_tick_loaded: bool = False

def _get_clock_tick_audio() -> AudioFileClip | None:
    global _clock_tick_loaded
    if not _clock_tick_loaded:
        _clock_tick_loaded = True
        try:
            music_path = Path(__file__).resolve().parent / "assets" / "sound" / "clock-tick-second.mp3"
            if music_path.exists():
                _clock_tick_cache[0] = AudioFileClip(str(music_path))
        except Exception as e:
            logger.warning(f"Could not load clock tick audio: {e}")
    return _clock_tick_cache[0]

def _make_countdown_clip(question: Question) -> VideoClip:
    """
    Build the 10-second countdown phase as a video clip.
    Timer bar smoothly shrinks from full to empty.
    """
    INTRO_DURATION = config.get("INTRO_DURATION")
    countdown_dur = config.get("COUNTDOWN_DURATION")
    def make_frame(t):
        progress = 1.0 - (t / countdown_dur)
        if t <= INTRO_DURATION:
            intro_p = 1.0 - (1.0 - (t / INTRO_DURATION))**3
            return render_question_frame(question, timer_progress=progress, state="options", intro_progress=intro_p)
        return render_question_frame(question, timer_progress=progress, state="options", intro_progress=1.0)

    frames_clip = VideoClip(make_frame, duration=countdown_dur)
    return frames_clip


def _make_reveal_clip(question: Question) -> VideoClip:
    """Build the 3-second answer reveal phase as a video clip."""
    ANIMATION_DURATION = 0.5
    # Cache the final frame (reveal_progress=1.0) — reused for ~2.5s of the 3s reveal
    _final_frame = [None]

    def make_frame(t):
        if t < ANIMATION_DURATION:
            progress = t / ANIMATION_DURATION
            eased = 1.0 - (1.0 - progress)**3
            return render_question_frame(question, reveal_progress=eased, state="reveal")
        else:
            if _final_frame[0] is None:
                _final_frame[0] = render_question_frame(question, reveal_progress=1.0, state="reveal")
            return _final_frame[0]

    reveal_dur = config.get("ANSWER_REVEAL_DURATION")
    return VideoClip(make_frame, duration=reveal_dur)


def build_question_clip(
    question: Question,
    audio_path: Optional[Path] = None,
) -> CompositeVideoClip:
    """
    Build a complete 13-second clip for one quiz question.

    Phases:
        0–10s: Question displayed, countdown timer, TTS narration
        10–13s: Correct answer highlighted green, wrong answers red
    """
    countdown_dur = config.get("COUNTDOWN_DURATION")

    # Phase 1: countdown (10s)
    countdown_clip = _make_countdown_clip(question)

    # Phase 2: answer reveal (3s)
    reveal_clip = _make_reveal_clip(question)

    # Concatenate phases
    video = concatenate_videoclips([countdown_clip, reveal_clip])

    # ── Audio layers ─────────────────────────────────────────────────────
    audio_clips = []

    # TTS narration (starts at t=0)
    if audio_path and audio_path.exists():
        try:
            tts_audio = AudioFileClip(str(audio_path))
            # Trim if longer than countdown
            if tts_audio.duration > countdown_dur:
                tts_audio = tts_audio.subclipped(0, countdown_dur)
            audio_clips.append(tts_audio)
        except Exception as e:
            logger.warning(f"Could not load TTS audio {audio_path}: {e}")

    # Clock tick sound effect (plays every second during countdown with increasing volume)
    try:
        clock_tick = _get_clock_tick_audio()
        if clock_tick is not None:
            import moviepy as mp
            for sec in range(int(countdown_dur)-1):
                volume = 0.05 + (0.05 * sec)
                tick_at_sec = clock_tick.with_start(sec)
                tick_at_sec = tick_at_sec.with_effects([mp.afx.MultiplyVolume(volume)])
                audio_clips.append(tick_at_sec)
    except Exception as e:
        logger.debug(f"clock-tick-second.mp3 not found or error — skipping: {e}")

    # Correct / Wrong SFX at reveal
    try:
        sfx_path = config.get("SFX_CORRECT")
        correct_sfx = AudioFileClip(sfx_path).with_start(countdown_dur)
        audio_clips.append(correct_sfx)
    except Exception:
        logger.debug("Correct SFX not found — skipping")

    # Mix all audio
    if audio_clips:
        mixed_audio = CompositeAudioClip(audio_clips)
        video = video.with_audio(mixed_audio)

    return video

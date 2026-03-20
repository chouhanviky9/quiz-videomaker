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
TIMER_H = 50
TIMER_W = 800
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


def _text_center(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    area: tuple[int, int, int, int],
    fill: tuple[int, ...],
) -> None:
    """Draw text centered within a bounding box, aligned exactly by font ascender/descender."""
    x1, y1, x2, y2 = area
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    # Use exact font height based on metrics instead of bbox offset to ensure perfect vertical center
    th = font.getbbox("A")[3] - font.getbbox("A")[1] 
    
    tx = x1 + (x2 - x1 - tw) // 2
    ty = y1 + (y2 - y1 - th) // 2 - 5 # slight 5px adjustment for montserrat baseline
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

    # ── Header bar (red gradient) ────────────────────────────────────────
    half = s(HEADER_HEIGHT) // 2
    draw.rectangle([0, 0, s(VIDEO_WIDTH), half], fill=config.get("COLOR_HEADER_RED"))
    draw.rectangle([0, half, s(VIDEO_WIDTH), s(HEADER_HEIGHT)], fill=config.get("COLOR_HEADER_RED_DARK"))
    draw.rectangle([0, s(HEADER_HEIGHT), s(VIDEO_WIDTH), s(HEADER_HEIGHT + 8)], fill=config.get("COLOR_WHITE"))

    # Downscale for smooth anti-aliased output
    final_img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.Resampling.LANCZOS)
    return final_img

_badge_cache = {}

def _get_badge_layer(text: str, is_logo: bool = False) -> Image.Image:
    if is_logo:
        try:
            logo_path = Path("assets/logos/video-maker-logo.png")
            if logo_path.exists():
                logo_img = Image.open(logo_path).convert("RGBA")
                size = (NUMBER_BADGE_RADIUS + 5) * 2
                logo_img.thumbnail((size, size))
                # Create exactly square container if needed, but returning logo_img is fine 
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

    _draw_circle(draw, (cx, cy), s(NUMBER_BADGE_RADIUS + 5), config.get("COLOR_WHITE"))
    _draw_circle(draw, (cx, cy), s(NUMBER_BADGE_RADIUS), config.get("COLOR_NUMBER_BADGE_BG"))
    draw.ellipse(
        [cx - s(NUMBER_BADGE_RADIUS + 5), cy - s(NUMBER_BADGE_RADIUS + 5), cx + s(NUMBER_BADGE_RADIUS + 5), cy + s(NUMBER_BADGE_RADIUS + 5)],
        outline=config.get("COLOR_BLACK"),
        width=s(4)
    )
    num_font = _load_font(config.get("FONT_EXTRABOLD"), s(36))
    _text_center(draw, text, num_font, (cx - s(25), cy - s(24), cx + s(25), cy + s(16)), config.get("COLOR_WHITE"))

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

    # Draw centered in the header
    tx = (s(VIDEO_WIDTH) - tw) // 2
    ty = s(30) + (s(HEADER_HEIGHT - 30) - th) // 2
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

    margin = 8
    card_w_2x = s(OPTION_W + margin*2)
    card_h_2x = s(OPTION_H + margin*2)
    
    img_2x = Image.new("RGBA", (card_w_2x, card_h_2x), (0,0,0,0))
    draw = ImageDraw.Draw(img_2x)
    
    ox = s(margin)
    oy = s(margin)
    
    if card_state == "correct":
        card_fill = config.get("COLOR_CORRECT_GREEN")
        text_color = config.get("COLOR_OPTION_TEXT")
        outline = config.get("COLOR_BLACK")
        width = s(4)
    elif card_state == "wrong":
        card_fill = config.get("COLOR_WRONG_RED")
        text_color = config.get("COLOR_WHITE")
        outline = config.get("COLOR_BLACK")
        width = s(4)
    else:
        card_fill = config.get("COLOR_WHITE")
        text_color = config.get("COLOR_OPTION_TEXT")
        outline = None
        width = 0

    opt_font = _load_font(config.get("FONT_BOLD"), s(42))
    badge_font = _load_font(config.get("FONT_EXTRABOLD"), s(36))

    _draw_rounded_rect(draw, (ox, oy, ox + s(OPTION_W), oy + s(OPTION_H)), radius=s(55 if card_state != "normal" else 65), fill=card_fill, outline=outline, width=width)

    badge_color = config.get("COLOR_BADGE_ORANGE") if letter in ("A", "B") else config.get("COLOR_BADGE_RED")
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
        
    _draw_circle(draw, (badge_cx, badge_cy), s(BADGE_RADIUS), badge_color)
    _text_center(draw, letter, badge_font, (badge_cx - s(20), badge_cy - s(22), badge_cx + s(20), badge_cy + s(14)), config.get("COLOR_WHITE"))

    text_area_left = ox + s(140)
    text_area_right = ox + s(OPTION_W - 20)
    _text_center(draw, text.upper(), opt_font, (text_area_left, oy, text_area_right, oy + s(OPTION_H)), text_color)

    card_1x = img_2x.resize((OPTION_W + margin*2, OPTION_H + margin*2), Image.Resampling.LANCZOS)
    _option_card_cache[key] = card_1x
    return card_1x

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

    # 1. Question number and Logo (left to right / right to left)
    qnum = _get_badge_layer(str(question.row_index))
    logo = _get_badge_layer("Logo", is_logo=True)
    
    badge_w, badge_h = qnum.size
    tgt_qx = 60 - badge_w // 2
    qx = int(-badge_w + (tgt_qx + badge_w) * intro_progress)
    qy = 60 - badge_h // 2
    img.paste(qnum, (qx, qy), mask=qnum)

    tgt_lx = 1800 - badge_w // 2
    lx = int(VIDEO_WIDTH + badge_w - (VIDEO_WIDTH + badge_w - tgt_lx) * intro_progress)
    img.paste(logo, (lx, qy), mask=logo)

    # 2. Question text layer (top to down)
    qtext = _get_question_text_layer(question)
    qw, qh = qtext.size
    ty = int(-qh + qh * intro_progress)
    img.paste(qtext, (0, ty), mask=qtext)

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
    margin = 8

    if state == "options":
        # 3. Options (top to down)
        for (letter, text), (tgt_x, tgt_y) in zip(options, positions):
            card = _get_option_card_layer(letter, text)
            # Start animation from the bottom of the header (top of the second section)
            startY = HEADER_HEIGHT
            cy = int(startY + (tgt_y - margin - startY) * intro_progress)
            img.paste(card, (tgt_x - margin, cy), mask=card)

        # 4. Timer bar (bottom to top)
        tgt_timer_y = TIMER_Y
        startY = VIDEO_HEIGHT
        timer_y_anim = int(startY + (tgt_timer_y - startY) * intro_progress)

        _draw_rounded_rect(
            draw,
            (TIMER_X, timer_y_anim, TIMER_X + TIMER_W, timer_y_anim + TIMER_H),
            radius=TIMER_RADIUS,
            fill=config.get("COLOR_WHITE"),
        )
        pad = 6
        fill_w = int((TIMER_W - 2 * pad) * max(0.0, min(1.0, timer_progress)))

        if fill_w > (TIMER_RADIUS - pad) * 2:
            inner_h = TIMER_H - 2 * pad
            pattern = _get_timer_pattern(timer_progress)
            
            mask = Image.new("L", (fill_w, inner_h), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle((0, 0, fill_w, inner_h), radius=TIMER_RADIUS - pad, fill=255)
            
            pattern_cropped = pattern.crop((0, 0, fill_w, inner_h))
            img.paste(pattern_cropped, (TIMER_X + pad, timer_y_anim + pad), mask=mask)

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
    
    def make_frame(t):
        if t < ANIMATION_DURATION:
            # Ease out interpolator
            progress = t / ANIMATION_DURATION
            eased = 1.0 - (1.0 - progress)**3
            return render_question_frame(question, reveal_progress=eased, state="reveal")
        else:
            return render_question_frame(question, reveal_progress=1.0, state="reveal")

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
        # Use absolute path to ensure it always finds the file
        music_path = Path(__file__).resolve().parent / "assets" / "sound" / "clock-tick-second.mp3"
        clock_tick = AudioFileClip(str(music_path))
        
        # Iterate through each second of the countdown
        for sec in range(int(countdown_dur)-1):
            # Volume starts at 5% (0.05) and increases by 5% (0.05) each second
            volume = 0.05 + (0.05 * sec)
            
            # Create a clip for this second, and set start time
            tick_at_sec = clock_tick.with_start(sec)
            
            # Apply volume (MoviePy v2 applies effects differently)
            import moviepy as mp
            tick_at_sec = tick_at_sec.with_effects([mp.afx.MultiplyVolume(volume)])
                
            audio_clips.append(tick_at_sec)
            
    except Exception as e:
        import traceback
        print("\n\n=== MOVIEPY AUDIO ERROR ===")
        print(f"Failed to load: clock-tick-second.mp3")
        print(f"File exists: {music_path.exists()}")
        print(f"Exact error: {e}")
        print("===========================\n\n")
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

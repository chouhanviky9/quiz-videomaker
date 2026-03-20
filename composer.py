"""
Video composer — concatenates all question clips into one final video,
adds intro/end screens, background music, and exports as MP4.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)

from config.config import config
from config.constant import (
    VIDEO_WIDTH,
    VIDEO_HEIGHT,
    FPS,
    FONT_EXTRABOLD,
    FONT_BOLD,
    SFX_INTRO,
    LOGOS_DIR,
    OUTPUT_DIR,
)
from sheets import Question, BatchConfig
from renderer import build_question_clip, _load_font

logger = logging.getLogger(__name__)


# ── Intro / End screen builders ──────────────────────────────────────────────

def _build_intro_clip(title: str, logo_path: Optional[str] = None) -> ImageClip:
    """
    Build an intro screen: blue background, title text, optional logo.
    """
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), config.get("COLOR_BG_BLUE", (26, 58, 138)))
    draw = ImageDraw.Draw(img)

    # Title
    title_font = _load_font(FONT_EXTRABOLD, 72)
    # Word wrap
    words = title.upper().split()
    lines: list[str] = []
    current = ""
    for w in words:
        test = f"{current} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=title_font)
        if bbox[2] - bbox[0] <= VIDEO_WIDTH - 200:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    wrapped_title = "\n".join(lines)

    bbox = draw.textbbox((0, 0), wrapped_title, font=title_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    ty = (VIDEO_HEIGHT - th) // 2 - 50
    tx = (VIDEO_WIDTH - tw) // 2
    draw.text((tx, ty), wrapped_title, font=title_font, fill=config.get("COLOR_WHITE", (255, 255, 255)))

    # Optional logo (centered below title)
    if logo_path and Path(logo_path).exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((200, 200))
            lx = (VIDEO_WIDTH - logo.width) // 2
            ly = ty + th + 40
            img.paste(logo, (lx, ly), logo)
        except Exception as e:
            logger.warning(f"Could not load logo: {e}")

    return ImageClip(np.array(img), duration=config.get("INTRO_DURATION", 5))


def _build_endscreen_clip(
    title: str = "THANKS FOR WATCHING!",
    logo_path: Optional[str] = None,
) -> ImageClip:
    """
    Build an end screen: red background, thank-you text, logo.
    """
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), config.get("COLOR_HEADER_RED", (239, 68, 68)))
    draw = ImageDraw.Draw(img)

    # Main text
    font = _load_font(FONT_EXTRABOLD, 64)
    bbox = draw.textbbox((0, 0), title.upper(), font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (VIDEO_WIDTH - tw) // 2
    ty = (VIDEO_HEIGHT - th) // 2 - 80
    draw.text((tx, ty), title.upper(), font=font, fill=config.get("COLOR_WHITE", (255, 255, 255)))

    # Subtitle
    sub_font = _load_font(FONT_BOLD, 36)
    sub = "SUBSCRIBE & LIKE FOR MORE QUIZZES"
    bbox2 = draw.textbbox((0, 0), sub, font=sub_font)
    sw = bbox2[2] - bbox2[0]
    draw.text(((VIDEO_WIDTH - sw) // 2, ty + th + 30), sub, font=sub_font, fill=config.get("COLOR_WHITE", (255, 255, 255))      )

    # Optional logo
    if logo_path and Path(logo_path).exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((180, 180))
            lx = (VIDEO_WIDTH - logo.width) // 2
            ly = ty + th + 100
            img.paste(logo, (lx, ly), logo)
        except Exception as e:
            logger.warning(f"Could not load logo: {e}")

    return ImageClip(np.array(img), duration=config.get("ENDSCREEN_DURATION", 5))


# ── Main composer ────────────────────────────────────────────────────────────

def compose_video(
    batch_config: BatchConfig,
    questions: list[Question],
    audio_paths: list[Path],
    logo_path: Optional[str] = None,
    bg_music_path: Optional[str] = None,
    output_filename: Optional[str] = None,
) -> Path:
    """
    Compose the full quiz video for a batch.

    Steps:
        1. Build per-question clips (with TTS audio + SFX)
        2. Build end screen clip
        3. Concatenate all clips
        4. Optionally overlay background music
        5. Export as MP4

    Returns:
        Path to the rendered MP4 file.
    """
    clips = []

    # ── Question clips ───────────────────────────────────────────────────
    for i, question in enumerate(questions):
        logger.info(f"Building clip for Q{i + 1} ({i + 1}/{len(questions)})")
        audio_path = audio_paths[i] if i < len(audio_paths) else None
        clip = build_question_clip(question, audio_path)
        clips.append(clip)

    # ── Combine Question Clips First ─────────────────────────────────────
    logger.info(f"Concatenating {len(clips)} question clips…")
    main_video = concatenate_videoclips(clips, method="compose")

    # ── Background music (low volume) ────────────────────────────────────
    if bg_music_path and Path(bg_music_path).exists():
        try:
            from moviepy import concatenate_audioclips
            import moviepy as mp
            bg_music = AudioFileClip(bg_music_path)
            # Loop if shorter than video
            if bg_music.duration < main_video.duration:
                loops_needed = int(main_video.duration / bg_music.duration) + 1
                bg_music = concatenate_audioclips([bg_music] * loops_needed)
            bg_music = bg_music.subclipped(0, main_video.duration)
            
            # Mix with existing audio
            if main_video.audio:
                mixed = CompositeAudioClip([main_video.audio, bg_music.with_volume_scaled(0.20)])
                main_video = main_video.with_audio(mixed)
            else:
                main_video = main_video.with_audio(bg_music.with_volume_scaled(0.20))

            logger.info("Background music added")
        except Exception as e:
            logger.warning(f"Could not add background music: {e}")

    # ── End screen ───────────────────────────────────────────────────────
    logger.info("Building end screen")
    endscreen = _build_endscreen_clip(logo_path=logo_path)
    
    end_music_path = "assets/sound/quizEnd.mpeg"
    if Path(end_music_path).exists():
        try:
            end_music = AudioFileClip(end_music_path)
            if end_music.duration > endscreen.duration:
                end_music = end_music.subclipped(0, endscreen.duration)
            else:
                # If song is shorter than end screen, extend end screen? Or just let it play.
                # Actually, can also just loop, but typically end screen is just 5 seconds
                from moviepy import concatenate_audioclips
                loops_needed = int(endscreen.duration / end_music.duration) + 1
                end_music = concatenate_audioclips([end_music] * loops_needed)
                end_music = end_music.subclipped(0, endscreen.duration)
            endscreen = endscreen.with_audio(end_music.with_volume_scaled(0.20))
            logger.info("End screen music added")
        except Exception as e:
            logger.warning(f"Could not add end screen music: {e}")

    # ── Final Concatenation ──────────────────────────────────────────────
    final = concatenate_videoclips([main_video, endscreen], method="compose")

    # ── Export ────────────────────────────────────────────────────────────
    if output_filename is None:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in batch_config.title)
        safe_title = safe_title.strip().replace(" ", "_")
        output_filename = f"output_{timestamp}_{safe_title}.mp4"

    output_path = OUTPUT_DIR / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Rendering video → {output_path}")
    final.write_videofile(
        str(output_path),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        preset="ultrafast",
        threads=8,
        logger="bar",
    )

    logger.info(f"✅ Video saved: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return output_path

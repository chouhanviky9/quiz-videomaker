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
    VideoFileClip,
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
) -> VideoFileClip | ImageClip:
    """
    Build an end screen using assets/ending.mp4 video.
    Falls back to a static image end screen if the file is missing.
    """
    ending_video_path = Path("assets/ending.mp4")
    if ending_video_path.exists():
        try:
            clip = VideoFileClip(str(ending_video_path))
            # Resize to match video dimensions if needed
            if list(clip.size) != [VIDEO_WIDTH, VIDEO_HEIGHT]:
                clip = clip.resized((VIDEO_WIDTH, VIDEO_HEIGHT))
            
            # Overlay logo — try dynamic config URL first, fallback to local file
            logo_img = None
            try:
                from renderer import _load_logo_from_url
                logo_url = config.get("VIDEO_TOPRIGHT_LOGO", "")
                if logo_url:
                    logo_img = _load_logo_from_url(logo_url)
            except Exception:
                pass

            if logo_img is None and logo_path and Path(logo_path).exists():
                try:
                    logo_img = Image.open(logo_path).convert("RGBA")
                except Exception:
                    pass

            if logo_img is not None:
                try:
                    new_w = 300
                    w, h = logo_img.size
                    new_h = int(h * (new_w / w))
                    logo_img = logo_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                    # Convert PIL RGBA image to a MoviePy ImageClip via numpy
                    logo_clip = ImageClip(np.array(logo_img)).with_duration(clip.duration)
                    lx = (VIDEO_WIDTH - new_w) // 2
                    ly = int(VIDEO_HEIGHT * 0.15)
                    logo_clip = logo_clip.with_position((lx, ly))

                    orig_audio = clip.audio
                    clip = CompositeVideoClip([clip, logo_clip])
                    clip = clip.with_audio(orig_audio)
                except Exception as e:
                    logger.warning(f"Could not overlay logo on ending video: {e}")

            logger.info(f"Loaded ending video: {ending_video_path} ({clip.duration:.1f}s)")
            return clip
        except Exception as e:
            logger.warning(f"Could not load ending video: {e}, falling back to static end screen")

    # Fallback: static image end screen
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), config.get("COLOR_HEADER_RED", (239, 68, 68)))
    draw = ImageDraw.Draw(img)
    font = _load_font(FONT_EXTRABOLD, 64)
    bbox = draw.textbbox((0, 0), title.upper(), font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (VIDEO_WIDTH - tw) // 2
    ty = (VIDEO_HEIGHT - th) // 2
    draw.text((tx, ty), title.upper(), font=font, fill=config.get("COLOR_WHITE", (255, 255, 255)))
    return ImageClip(np.array(img), duration=config.get("ENDSCREEN_DURATION", 5))


# ── Main composer ────────────────────────────────────────────────────────────

def _render_raw_h264_clip(args):
    """
    Worker function to render a SINGLE question using a pure FFmpeg pipe to a temporary file.
    This avoids Python IPC bottlenecks by saving directly to the NVMe disk natively.
    """
    idx, question, tmp_dir = args
    import logging
    from pathlib import Path
    import subprocess
    import imageio_ffmpeg
    from renderer import build_question_clip
    from config.constant import VIDEO_WIDTH, VIDEO_HEIGHT, FPS

    logger = logging.getLogger("worker")
    logger.setLevel(logging.INFO)
    logger.info(f"Worker building video for Q{idx+1}...")

    # Build clip strictly for video rendering (ignore audio, added later via Master track)
    clip = build_question_clip(question, audio_path=None)

    out_path = Path(tmp_dir) / f"q_{idx:03d}.mp4"
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}", "-pix_fmt", "rgb24", "-r", str(FPS),
        "-i", "-", # stdin
        "-an", # No audio yet
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        str(out_path)
    ]

    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for frame in clip.iter_frames(fps=FPS, dtype="uint8"):
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        proc.wait()
    except Exception as e:
        logger.error(f"Worker {idx} failed: {e}")
        if proc.stdin:
            proc.stdin.close()
        proc.terminate()
        raise

    # Also make sure renderer caches don't bloat worker memory
    from renderer import clear_render_caches
    clear_render_caches()

    return idx, out_path

def compose_video(
    batch_config: BatchConfig,
    questions: list[Question],
    audio_paths: list[Path],
    logo_path: Optional[str] = None,
    bg_music_path: Optional[str] = None,
    output_filename: Optional[str] = None,
) -> Path:
    """
    Compose the full quiz video utilizing ProcessPoolExecutor for true CPU parallelization
    and FFmpeg zero-encode `concat` copy for immediate compilation.
    """
    import datetime
    import tempfile
    import shutil
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import subprocess
    import imageio_ffmpeg

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    if output_filename is None:
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in batch_config.title)
        safe_title = safe_title.strip().replace(" ", "_")
        output_filename = f"output_{timestamp}_{safe_title}.mp4"

    output_path = OUTPUT_DIR / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    master_audio_path = OUTPUT_DIR / f"temp_master_audio_{timestamp}.mp3"

    # ── Phase A: Build Master Audio ─────────────────────────────────
    # MoviePy handles Audio trees insanely fast in a single thread thread
    clips_for_audio = []
    for i, question in enumerate(questions):
        audio_path = audio_paths[i] if i < len(audio_paths) else None
        clips_for_audio.append(build_question_clip(question, audio_path))

    logger.info("Compiling master audio track...")
    main_video = concatenate_videoclips(clips_for_audio, method="compose")
    endscreen = _build_endscreen_clip(logo_path=logo_path)
    final = concatenate_videoclips([main_video, endscreen], method="compose")

    if bg_music_path and Path(bg_music_path).exists():
        try:
            from moviepy import concatenate_audioclips
            import moviepy as mp
            bg_music = AudioFileClip(bg_music_path)
            if bg_music.duration < final.duration:
                loops_needed = int(final.duration / bg_music.duration) + 1
                bg_music = concatenate_audioclips([bg_music] * loops_needed)
            bg_music = bg_music.subclipped(0, final.duration)
            bg_music = bg_music.with_effects([mp.afx.MultiplyVolume(1.0)])
            if final.audio:
                mixed = CompositeAudioClip([final.audio, bg_music])
                final = final.with_audio(mixed)
            else:
                final = final.with_audio(bg_music)
        except Exception as e:
            logger.warning(f"Could not add background music: {e}")

    if final.audio is not None:
        final.audio.write_audiofile(str(master_audio_path), fps=44100, logger=None)

    # ── Phase B: Parallel Multiprocessing for Video Frames ─────────────────────────
    # Distribute the video rendering workload seamlessly across physical cores
    tmp_dir = Path(tempfile.mkdtemp(prefix="quiz_tmp_raw_"))
    logger.info(f"Spinning up multicore processes for {len(questions)} elements...")
    
    worker_args = [(i, q, str(tmp_dir)) for i, q in enumerate(questions)]
    rendered_paths = {}

    max_w = min(2, len(questions))
    
    if len(questions) > 1:
        with ProcessPoolExecutor(max_workers=max_w) as pool:
            futures = {pool.submit(_render_raw_h264_clip, arg): arg for arg in worker_args}
            for future in as_completed(futures):
                idx, p = future.result()
                rendered_paths[idx] = p
                logger.info(f"✓ Q{idx + 1} built -> {p.name}")
    else:
        # Fallback for benchmarking single questions
        idx, p = _render_raw_h264_clip(worker_args[0])
        rendered_paths[idx] = p
        logger.info(f"✓ Q{idx + 1} built -> {p.name}")

    # Build endscreen instantly in main thread
    logger.info("Building endscreen video...")
    endscreen_out = tmp_dir / "endscreen.mp4"
    cmd_e = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}", "-pix_fmt", "rgb24", "-r", str(FPS),
        "-i", "-", "-an",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        str(endscreen_out)
    ]
    proc_e = subprocess.Popen(cmd_e, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for frame in endscreen.iter_frames(fps=FPS, dtype="uint8"):
        proc_e.stdin.write(frame.tobytes())
    proc_e.stdin.close()
    proc_e.wait()

    # ── Phase C: The Zero-Loss Demux Concat ───────────────────────────────────────
    logger.info("Executing instantaneous FFmpeg Concat Phase...")
    concat_txt = tmp_dir / "concat.txt"
    lines = []
    # VERY IMPORTANT: FFmpeg concat lists must be ordered exactly correctly
    for i in range(len(questions)):
        lines.append(f"file '{rendered_paths[i].resolve()}'")
    lines.append(f"file '{endscreen_out.resolve()}'")
    concat_txt.write_text("\n".join(lines))

    cmd_wrap = [
        ffmpeg_exe, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_txt),
    ]

    if master_audio_path.exists():
        cmd_wrap.extend(["-i", str(master_audio_path)])
        
    cmd_wrap.extend([
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
    ])
    
    if master_audio_path.exists():
        cmd_wrap.extend(["-map", "1:a:0"])

    cmd_wrap.extend([
        "-shortest",
        str(output_path)
    ])

    subprocess.run(cmd_wrap, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)
    if master_audio_path.exists():
        master_audio_path.unlink()

    logger.info(f"✅ Video saved: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return output_path

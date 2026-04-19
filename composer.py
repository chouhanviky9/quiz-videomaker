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
from renderer import _load_font
import subprocess
import json

ROOT_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

def get_video_duration(file_path: str) -> float:
    """Uses ffprobe to get the exact duration of a video file."""
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffprobe_exe = ffmpeg_exe.replace("ffmpeg", "ffprobe")
        if not Path(ffprobe_exe).exists():
            ffprobe_exe = "ffprobe"
        
        cmd = [
            ffprobe_exe, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"Could not determine video duration with ffprobe: {e}")
        return 0.0


# ── Intro / End screen builders ──────────────────────────────────────────────

def _build_intro_clip(title: str, logo_path: Optional[str] = None) -> np.ndarray:
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

    return np.array(img)


def _build_endscreen_clip(logo_path: Optional[str] = None):
    """
    Returns only the static image of the endscreen for processing later.
    Bypasses MoviePy's ImageClip.
    """
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), config.get("COLOR_BG_BLUE", (1, 65, 164)))
    draw = ImageDraw.Draw(img)

    if logo_path and Path(logo_path).exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((310, 310))
            lx = (VIDEO_WIDTH - logo.width) // 2
            ly = (VIDEO_HEIGHT - logo.height) // 2 - 212
            img.paste(logo, (lx, ly), mask=logo)
        except Exception as e:
            logger.warning(f"Could not load logo for endscreen: {e}")

    try:
        font = ImageFont.truetype(config.get("FONT_BOLD"), 80)
    except Exception:
        font = ImageFont.load_default()

    title = config.get("ENDSCREEN_TITLE", "MERCI D'AVOIR REGARDÉ")
    bbox = draw.textbbox((0, 0), title.upper(), font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    tx = (VIDEO_WIDTH - tw) // 2
    ty = (VIDEO_HEIGHT - th) // 2
    draw.text((tx, ty), title.upper(), font=font, fill=config.get("COLOR_WHITE", (255, 255, 255)))
    return img


# ── Main composer ────────────────────────────────────────────────────────────

def _render_raw_h264_clip(args):
    """
    Worker function to render a SINGLE question using a pure FFmpeg pipe to a temporary file.
    This avoids Python IPC bottlenecks by saving directly to the NVMe disk natively.
    """
    idx, question, tmp_dir, config_state = args
    from config.config import config
    config.update_from_dict(config_state)
    
    import logging
    from pathlib import Path
    import subprocess
    import imageio_ffmpeg
    from renderer import generate_question_frames_bytes
    from config.constant import VIDEO_WIDTH, VIDEO_HEIGHT, FPS

    logger = logging.getLogger("worker")
    logger.setLevel(logging.INFO)
    logger.info(f"Worker building video for Q{idx+1}...")

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
        for frame_bytes in generate_question_frames_bytes(question, fps=FPS):
            proc.stdin.write(frame_bytes)
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
    from moviepy import concatenate_audioclips, AudioClip, CompositeAudioClip, AudioFileClip
    import moviepy as mp
    from renderer import build_question_audio_moviepy
    
    logger.info("Compiling master audio track via native Audio...")
    clips_for_audio = []
    
    for i, question in enumerate(questions):
        audio_path = audio_paths[i] if i < len(audio_paths) else None
        clips_for_audio.append(build_question_audio_moviepy(question, audio_path))

    # Append endscreen audio (from ending.mp4 if it exists, else silence)
    custom_outro = ROOT_DIR / "assets" / "ending.mp4"
    logger.info(f"Checking for custom outro audio at: {custom_outro.absolute()}")
    if custom_outro.exists():
        actual_dur = get_video_duration(str(custom_outro))
        if actual_dur > 0:
            logger.info(f"Detected actual duration of {custom_outro.name}: {actual_dur:.2f}s")
        else:
            actual_dur = config.get("ENDSCREEN_DURATION", 15)

        try:
            logger.info(f"Attempting to load outro audio from {custom_outro.name}...")
            outro_audio = AudioFileClip(str(custom_outro))
            # Ensure it matches the video duration exactly
            outro_audio = outro_audio.with_duration(actual_dur)
            logger.info(f"Custom outro audio duration: {outro_audio.duration:.2f}s")
            clips_for_audio.append(outro_audio)
        except Exception as e:
            logger.warning(f"Could not load audio from ending.mp4, using silence for {actual_dur:.2f}s: {e}")
            silence = AudioClip(lambda t: [0, 0], duration=actual_dur, fps=44100)
            clips_for_audio.append(silence)
    else:
        endscreen_dur = config.get("ENDSCREEN_DURATION", 5)
        logger.info(f"No custom ending.mp4 found. Using {endscreen_dur}s static silence.")
        silence = AudioClip(lambda t: [0, 0], duration=endscreen_dur, fps=44100)
        clips_for_audio.append(silence)

    master_track = concatenate_audioclips(clips_for_audio)

    if bg_music_path and Path(bg_music_path).exists():
        try:
            bg_music = AudioFileClip(bg_music_path)
            
            # Loop bg_music if shorter than master_track
            if bg_music.duration < master_track.duration:
                loops_needed = int(master_track.duration / bg_music.duration) + 1
                bg_music = concatenate_audioclips([bg_music] * loops_needed)
            
            # Trim to exact length and overlay at 50% volume
            bg_music = bg_music.subclipped(0, master_track.duration)
            bg_music = bg_music.with_effects([mp.afx.MultiplyVolume(0.5)])
            
            master_track = CompositeAudioClip([master_track, bg_music])
        except Exception as e:
            logger.warning(f"Could not add background music: {e}")

    # Export fast raw MP3 via MoviePy
    master_track.write_audiofile(str(master_audio_path), fps=44100, logger=None, bitrate="128k")

    # ── Phase B: Parallel Multiprocessing for Video Frames ─────────────────────────
    # Distribute the video rendering workload seamlessly across physical cores
    tmp_dir = Path(tempfile.mkdtemp(prefix="quiz_tmp_raw_"))
    logger.info(f"Spinning up multicore processes for {len(questions)} elements...")
    
    worker_args = [(i, q, str(tmp_dir), config._data.copy()) for i, q in enumerate(questions)]
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

    # Build endscreen
    logger.info("Building endscreen video...")
    endscreen_out = tmp_dir / "endscreen.mp4"
    custom_outro = ROOT_DIR / "assets" / "ending.mp4"

    if custom_outro.exists():
        logger.info("Using custom assets/ending.mp4 video file...")
        cmd_e = [ffmpeg_exe, "-y", "-i", str(custom_outro)]
        
        if logo_path and Path(logo_path).exists():
            logger.info("Overlaying logo onto custom ending.mp4...")
            cmd_e.extend(["-i", str(logo_path)])
            cmd_e.extend([
                "-filter_complex",
                f"[1:v]scale=310:310:force_original_aspect_ratio=decrease[logo];[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},setsar=1[bg];[bg][logo]overlay=(W-w)/2:(H-h)/2-212[v]",
                "-map", "[v]"
            ])
        else:
            cmd_e.extend(["-s", f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}"])

        cmd_e.extend([
            "-an", # No audio (handled in Phase A)
            "-r", str(FPS),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            str(endscreen_out)
        ])
        subprocess.run(cmd_e, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        logger.info("Generating static blue endscreen...")
        endscreen_img = _build_endscreen_clip(logo_path=logo_path)
        cmd_e = [
            ffmpeg_exe, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}", "-pix_fmt", "rgb24", "-r", str(FPS),
            "-i", "-", "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            str(endscreen_out)
        ]
        proc_e = subprocess.Popen(cmd_e, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        endscreen_dur = config.get("ENDSCREEN_DURATION", 5)
        endscreen_frames = int(endscreen_dur * FPS)
        endscreen_bytes = endscreen_img.tobytes()
        
        for f in range(endscreen_frames):
            proc_e.stdin.write(endscreen_bytes)
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

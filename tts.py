"""
Gemini TTS — generates narration audio for quiz questions.

Uses the gemini-2.5-flash-preview-tts model to produce 24 kHz WAV files.
"""

from __future__ import annotations

import io
import logging
import struct
import time
import wave
from pathlib import Path

from google import genai
from google.genai import types

from config.constant import (
    GEMINI_API_KEY,
    TTS_MODEL,
    TTS_SAMPLE_RATE,
    AUDIO_DIR,
    DEFAULT_VOICES,
)
from sheets import Question

logger = logging.getLogger(__name__)

# ── Language prompt templates ────────────────────────────────────────────────
# The model auto-detects language from text, but an explicit prompt helps
# with pronunciation, pacing, and style.

LANGUAGE_PROMPTS = {
    "en": "Read this quiz question clearly and at a steady pace: {text}",
    "fr": "Lis cette question de quiz clairement et à un rythme régulier : {text}",
    "es": "Lee esta pregunta de quiz de forma clara y a un ritmo constante: {text}",
    "de": "Lies diese Quizfrage klar und in gleichmäßigem Tempo vor: {text}",
    "ar": "اقرأ سؤال الاختبار هذا بوضوح وبوتيرة ثابتة: {text}",
    "pt": "Leia esta pergunta do quiz de forma clara e em ritmo constante: {text}",
    "hi": "इस क्विज़ प्रश्न को स्पष्ट और स्थिर गति से पढ़ें: {text}",
    "ja": "このクイズの質問をはっきりと、一定のペースで読んでください：{text}",
    "ko": "이 퀴즈 질문을 명확하고 일정한 속도로 읽어주세요: {text}",
    "tr": "Bu sınav sorusunu net ve sabit bir tempoda okuyun: {text}",
}

# Fallback for unknown languages
DEFAULT_PROMPT = "Read this quiz question clearly: {text}"


def _build_prompt(question: Question, language: str) -> str:
    """Build the full TTS prompt including question + options."""
    template = LANGUAGE_PROMPTS.get(language, DEFAULT_PROMPT)

    # Include options so the voice reads them out
    full_text = (
        f"{question.text}\n"
        f"A: {question.option_a}\n"
        f"B: {question.option_b}\n"
        f"C: {question.option_c}\n"
        f"D: {question.option_d}"
    )
    return template.format(text=full_text)


def _save_wav(pcm_data: bytes, output_path: Path) -> None:
    """Save raw PCM bytes (24 kHz, 16-bit, mono) as a WAV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(TTS_SAMPLE_RATE)
        wf.writeframes(pcm_data)


def generate_question_audio(
    question: Question,
    language: str,
    voice: str | None = None,
) -> Path:
    """
    Generate TTS audio for a single question and save as WAV.

    Returns the path to the saved WAV file.
    """
    voice_name = voice or DEFAULT_VOICES.get(language, "Puck")
    prompt = _build_prompt(question, language)
    output_path = AUDIO_DIR / f"q_row{question.row_index:03d}.wav"

    # Skip if already generated (idempotent)
    if output_path.exists():
        logger.info(f"Audio already exists: {output_path.name} — skipping")
        return output_path

    logger.info(f"Generating TTS for row {question.row_index} ({voice_name}/{language})…")

    client = genai.Client(api_key=GEMINI_API_KEY)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=TTS_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name,
                            )
                        )
                    ),
                ),
            )

            # Extract raw PCM audio from response
            if not response.candidates:
                raise ValueError("No candidates returned from Gemini.")

            candidate = response.candidates[0]

            if not candidate.content or not candidate.content.parts:
                logger.error(f"TTS Model returned unexpected structure: {candidate}")
                raise ValueError("No audio parts found in response.")

            audio_data = candidate.content.parts[0].inline_data.data
            _save_wav(audio_data, output_path)
            logger.info(f"Saved: {output_path.name} ({len(audio_data)} bytes)")
            return output_path

        except Exception as e:
            if attempt < max_retries:
                wait = 2 ** attempt  # 2s, 4s, 8s
                logger.warning(f"TTS attempt {attempt}/{max_retries} failed for row {question.row_index}: {e} — retrying in {wait}s…")
                time.sleep(wait)
            else:
                logger.error(f"TTS failed after {max_retries} attempts for row {question.row_index}: {e}")
                return output_path  # return path even if file doesn't exist; renderer handles missing audio

    return output_path


def generate_batch_audio(
    questions: list[Question],
    language: str,
    voice: str | None = None,
) -> list[Path]:
    """Generate TTS audio for all questions. Returns list of WAV paths."""
    paths: list[Path] = []
    for q in questions:
        path = generate_question_audio(q, language, voice)
        paths.append(path)
    return paths

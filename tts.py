"""
Google Cloud TTS — generates narration audio for quiz questions.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from google.cloud import texttospeech

from config.constant import (
    GEMINI_API_KEY,
    TTS_SAMPLE_RATE,
    AUDIO_DIR,
    DEFAULT_VOICES,
    GOOGLE_CREDENTIALS_TTS_PATH,
)
from sheets import Question

logger = logging.getLogger(__name__)

# ── Language prompt templates ────────────────────────────────────────────────
LANGUAGE_PROMPTS = {
    "en": "Read this quiz question clearly and at a steady pace: {text}",
    "fr": "Lis cette question de quiz clairement et à un rythme régulier : {text}",
    "es": "Lee esta pregunta de quiz de forma clara y a un rythme constante: {text}",
    "de": "Lies diese Quizfrage klar und in gleichmäßigem Tempo vor: {text}",
    "ar": "اقرأ سؤال الاختبار هذا بوضوح وبوتيرة ثابتة: {text}",
    "pt": "Leia esta pergunta do quiz de forma clara e em ritmo constante: {text}",
    "hi": "इस क्विज़ प्रश्न को स्पष्ट और स्थिर गति से पढ़ें: {text}",
    "ja": "このクイズの質問をはっきりと、一定のペースで読んでください：{text}",
    "ko": "이 퀴즈 질문을 명확하고 일정한 속도로 읽어주세요: {text}",
    "tr": "Bu sınav sorusunu net ve sabit bir tempoda okuyun: {text}",
}

def _build_prompt(question: Question, language: str) -> str:
    return f"{question.text}\n"

def _build_answer_prompt(question: Question, language: str) -> str:
    return question.answer

def _get_voice_params(voice: str | None, language: str) -> texttospeech.VoiceSelectionParams:
    voice_name = voice or DEFAULT_VOICES.get(language, "en-US-Journey-F")
    
    # Extract language code from voice_name (e.g. 'en-US' from 'en-US-Journey-F')
    lang_code = "-".join(voice_name.split("-")[:2]) if "-" in voice_name else language

    return texttospeech.VoiceSelectionParams(
        language_code=lang_code,
        name=voice_name
    )

from google.oauth2 import service_account

def _generate_audio_cloud(
    text: str,
    output_path: Path,
    row_index: int,
    language: str,
    voice: str | None = None,
) -> Path:
    if output_path.exists() and output_path.stat().st_size > 0:
        logger.info(f"Audio already exists: {output_path.name} — skipping")
        return output_path

    voice_params = _get_voice_params(voice, language)
    logger.info(f"Generating TTS for row {row_index} ({voice_params.name}/{language})…")

    # Initialize client using Service Account JSON
    credentials = service_account.Credentials.from_service_account_file(GOOGLE_CREDENTIALS_TTS_PATH)
    client = texttospeech.TextToSpeechClient(credentials=credentials)

    synthesis_input = texttospeech.SynthesisInput(text=text)
    
    # LINEAR16 includes the WAV header natively
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=TTS_SAMPLE_RATE,
    )

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.synthesize_speech(
                input=synthesis_input, 
                voice=voice_params, 
                audio_config=audio_config
            )

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.audio_content)
            
            logger.info(f"Saved: {output_path.name} ({len(response.audio_content)} bytes)")
            return output_path

        except Exception as e:
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(f"TTS attempt {attempt}/{max_retries} failed for row {row_index}: {e} — retrying in {wait}s…")
                time.sleep(wait)
            else:
                logger.error(f"TTS failed after {max_retries} attempts for row {row_index}: {e}")
                raise RuntimeError(f"TTS failed for Question Row {row_index}: {e}")

    return output_path

def generate_question_audio(
    question: Question,
    language: str,
    voice: str | None = None,
) -> Path:
    prompt = _build_prompt(question, language)
    output_path = AUDIO_DIR / f"q_row{question.row_index:03d}.wav"
    return _generate_audio_cloud(prompt, output_path, question.row_index, language, voice)

def generate_answer_audio(
    question: Question,
    language: str,
    voice: str | None = None,
) -> Path:
    prompt = _build_answer_prompt(question, language)
    output_path = AUDIO_DIR / f"a_row{question.row_index:03d}.wav"
    return _generate_audio_cloud(prompt, output_path, question.row_index, language, voice)

def generate_batch_audio(
    questions: list[Question],
    language: str,
    voice: str | None = None,
) -> list[Path]:
    paths: list[Path] = []
    
    for i, q in enumerate(questions):
        logger.info(f"Processing TTS for question {i+1}/{len(questions)}...")
        
        generate_answer_audio(q, language, voice)
        # Small delay to keep it polite, but no longer 7s
        time.sleep(0.05)
        path = generate_question_audio(q, language, voice)
        time.sleep(0.05)
        
        paths.append(path)
        logger.info(f"TTS {i + 1}/{len(questions)} done → {path.name}")

    return paths

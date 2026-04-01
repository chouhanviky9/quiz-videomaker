import time
from pathlib import Path
from sheets import Question
from composer import compose_video, BatchConfig

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def run_benchmark():
    # Setup 40 dummy questions
    questions = []
    audio_paths = []
    
    # We will use an existing audio file to simulate TTS audio
    dummy_audio = Path("./assets/sound/quizSong1.mp3")
    
    for i in range(1, 5):
        q = Question(
            text=f"This is dummy question {i} for benchmarking?",
            option_a="A",
            option_b="B",
            option_c="C",
            option_d="D",
            answer="C",
            letter="C",
            processed=False,
            row_index=i+1
        )
        questions.append(q)
        audio_paths.append(dummy_audio if dummy_audio.exists() else None)
        
    print(f"Generated {len(questions)} dummy questions.")
    
    batch_config = BatchConfig(title="Benchmark_40Q", language="en", batch=1, batch_size=40, voice="A", status="PENDING", video_url="", row_index=1)
    
    print("Starting benchmark with 40 questions and audio...")
    start_time = time.time()
    
    output_path = compose_video(
        batch_config=batch_config,
        questions=questions,
        audio_paths=audio_paths,
        logo_path=None,
        bg_music_path=None,
        output_filename="benchmark_output_40q.mp4"
    )
    
    end_time = time.time()
    print(f"Benchmark finished in {end_time - start_time:.2f} seconds.")
    print(f"Output saved to: {output_path}")

if __name__ == "__main__":
    run_benchmark()

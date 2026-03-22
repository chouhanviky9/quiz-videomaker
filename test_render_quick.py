import sys
sys.path.insert(0, r'c:\Users\chouh\quiz-video-maker')
from renderer import render_question_frame
from sheets import Question
from PIL import Image

q = Question(
    text='Test question about something?',
    option_a='Option A', option_b='Option B',
    option_c='Option C', option_d='Option D',
    answer='A', letter='A', processed=False, row_index=1
)
frame = render_question_frame(q, timer_progress=0.7, state='options', intro_progress=1.0)
img = Image.fromarray(frame)
img.save(r'c:\Users\chouh\quiz-video-maker\test_frame.png')
print('SUCCESS: Frame rendered and saved')

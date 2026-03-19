import sys

with open("renderer.py", "r", encoding="utf-8") as f:
    orig_code = f.read()

# We need to construct the new functions to replace Lines 167 to 290 and 371 to 484.

NEW_LAYOUT = '''
_bg_cache = None

def _get_background_layer() -> tuple:
    global _bg_cache
    if _bg_cache is not None:
        return _bg_cache

    SCALE = 2  # Supersampling factor for anti-aliasing shapes/text
    
    def s(val: int | float) -> int:
        return int(val * SCALE)

    img = Image.new("RGB", (s(VIDEO_WIDTH), s(VIDEO_HEIGHT)), COLOR_BG_BLUE)
    draw = ImageDraw.Draw(img)

    # ── Header bar (red gradient) ────────────────────────────────────────
    half = s(HEADER_HEIGHT) // 2
    draw.rectangle([0, 0, s(VIDEO_WIDTH), half], fill=COLOR_HEADER_RED)
    draw.rectangle([0, half, s(VIDEO_WIDTH), s(HEADER_HEIGHT)], fill=COLOR_HEADER_RED_DARK)
    draw.rectangle([0, s(HEADER_HEIGHT), s(VIDEO_WIDTH), s(HEADER_HEIGHT + 8)], fill=COLOR_WHITE)

    # Downscale for smooth anti-aliased output
    final_img = img.resize((VIDEO_WIDTH, VIDEO_HEIGHT), Image.Resampling.LANCZOS)
    _bg_cache = final_img
    return final_img

_badge_cache = {}

def _get_badge_layer(text: str, is_logo: bool = False) -> Image.Image:
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

    _draw_circle(draw, (cx, cy), s(NUMBER_BADGE_RADIUS + 5), COLOR_WHITE)
    _draw_circle(draw, (cx, cy), s(NUMBER_BADGE_RADIUS), COLOR_NUMBER_BADGE_BG)
    draw.ellipse(
        [cx - s(NUMBER_BADGE_RADIUS + 5), cy - s(NUMBER_BADGE_RADIUS + 5), cx + s(NUMBER_BADGE_RADIUS + 5), cy + s(NUMBER_BADGE_RADIUS + 5)],
        outline=COLOR_BLACK,
        width=s(4)
    )
    num_font = _load_font(FONT_EXTRABOLD, s(36))
    _text_center(draw, text, num_font, (cx - s(25), cy - s(20), cx + s(25), cy + s(20)), COLOR_WHITE)

    final_img = img.resize((size // 2, size // 2), Image.Resampling.LANCZOS)
    _badge_cache[text] = final_img
    return final_img

_qtext_cache = {}

def _get_question_text_layer(question: Question) -> Image.Image:
    if question.number in _qtext_cache:
        return _qtext_cache[question.number]

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
        q_font = _load_font(FONT_EXTRABOLD, s(font_size))
        wrapped = _wrap_text(question.text.upper(), q_font, max_w)
        bbox = draw.textbbox((0, 0), wrapped, font=q_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        
        if th <= max_h:
            break
        font_size -= 2

    # Draw centered in the header
    tx = (s(VIDEO_WIDTH) - tw) // 2
    ty = s(30) + (s(HEADER_HEIGHT - 30) - th) // 2
    draw.text((tx, ty), wrapped, font=q_font, fill=COLOR_WHITE)

    final_img = img.resize((VIDEO_WIDTH, HEADER_HEIGHT), Image.Resampling.LANCZOS)
    _qtext_cache[question.number] = final_img
    return final_img

'''

NEW_CARD_AND_RENDER = '''
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
        card_fill = (100, 240, 60, 255) # bright green
        text_color = COLOR_OPTION_TEXT
        outline = COLOR_BLACK
        width = s(4)
    elif card_state == "wrong":
        card_fill = (240, 80, 80, 255) # bright red
        text_color = COLOR_WHITE
        outline = COLOR_BLACK
        width = s(4)
    else:
        card_fill = COLOR_WHITE
        text_color = COLOR_OPTION_TEXT
        outline = None
        width = 0

    opt_font = _load_font(FONT_BOLD, s(42))
    badge_font = _load_font(FONT_EXTRABOLD, s(36))

    _draw_rounded_rect(draw, (ox, oy, ox + s(OPTION_W), oy + s(OPTION_H)), radius=s(55 if card_state != "normal" else 65), fill=card_fill, outline=outline, width=width)

    badge_color = COLOR_BADGE_ORANGE if letter in ("A", "B") else COLOR_BADGE_RED
    badge_cx = ox + s(65)
    badge_cy = oy + s(OPTION_H) // 2
    
    if card_state != "normal":
        _draw_circle(draw, (badge_cx, badge_cy), s(BADGE_RADIUS + 3), COLOR_BLACK)
    else:
        _draw_circle(draw, (badge_cx, badge_cy), s(BADGE_RADIUS + 8), COLOR_WHITE)
        draw.ellipse(
            [badge_cx - s(BADGE_RADIUS + 8), badge_cy - s(BADGE_RADIUS + 8), badge_cx + s(BADGE_RADIUS + 8), badge_cy + s(BADGE_RADIUS + 8)],
            fill=None,
            outline=COLOR_BLACK,
            width=s(4)
        )
        
    _draw_circle(draw, (badge_cx, badge_cy), s(BADGE_RADIUS), badge_color)
    _text_center(draw, letter, badge_font, (badge_cx - s(20), badge_cy - s(18), badge_cx + s(20), badge_cy + s(18)), COLOR_WHITE)

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
    qnum = _get_badge_layer(str(question.number))
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
            startY = -card.size[1]
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
            fill=COLOR_WHITE,
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
                scaled_card = card.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
                
                cx = tgt_x - margin + card_w // 2
                cy = tgt_y - margin + card_h // 2
                px = cx - scaled_w // 2
                py = cy - scaled_h // 2
                
                img.paste(scaled_card, (px, py), mask=scaled_card)
            else:
                img.paste(card, (tgt_x - margin, tgt_y - margin), mask=card)

    return np.array(img)
'''

import re

# Replace _base_image_cache up to end of _get_static_base_layer
start_bg = orig_code.find("_base_image_cache = {}")
end_bg = orig_code.find("_timer_pattern_cache = {}")

print("Found start_bg:", start_bg)
print("Found end_bg:", end_bg)

mod_code = orig_code[:start_bg] + NEW_LAYOUT + "\n" + orig_code[end_bg:]

# Replace _card_cache up to end of render_question_frame
start_card = mod_code.find("_card_cache = {}")
end_card = mod_code.find("# ── Clip builders ────────────────────────────────────────────────────────────")

print("Found start_card:", start_card)
print("Found end_card:", end_card)

mod_code2 = mod_code[:start_card] + NEW_CARD_AND_RENDER + "\n\n" + mod_code[end_card:]

# Update _make_countdown_clip
old_countdown = """def _make_countdown_clip(question: Question) -> VideoClip:
    \"\"\"
    Build the 10-second countdown phase as a video clip.
    Timer bar smoothly shrinks from full to empty.
    \"\"\"
    def make_frame(t):
        progress = 1.0 - (t / COUNTDOWN_DURATION)
        return render_question_frame(question, timer_progress=progress, state="options")

    frames_clip = VideoClip(make_frame, duration=COUNTDOWN_DURATION)
    return frames_clip"""

new_countdown = """def _make_countdown_clip(question: Question) -> VideoClip:
    \"\"\"
    Build the 10-second countdown phase as a video clip.
    Timer bar smoothly shrinks from full to empty.
    \"\"\"
    INTRO_DURATION = 1.0
    def make_frame(t):
        progress = 1.0 - (t / COUNTDOWN_DURATION)
        if t <= INTRO_DURATION:
            intro_p = 1.0 - (1.0 - (t / INTRO_DURATION))**3
            return render_question_frame(question, timer_progress=progress, state="options", intro_progress=intro_p)
        return render_question_frame(question, timer_progress=progress, state="options", intro_progress=1.0)

    frames_clip = VideoClip(make_frame, duration=COUNTDOWN_DURATION)
    return frames_clip"""

mod_code3 = mod_code2.replace(old_countdown, new_countdown)

# Update _make_reveal_clip
old_reveal = """def _make_reveal_clip(question: Question) -> VideoClip:
    \"\"\"Build the 3-second answer reveal phase as a video clip sliding up.\"\"\"
    ANIMATION_DURATION = 0.5 
    
    def make_frame(t):
        if t < ANIMATION_DURATION:
            # Ease out interpolator
            progress = t / ANIMATION_DURATION
            eased = 1.0 - (1.0 - progress)**3
            return render_question_frame(question, reveal_progress=eased, state="empty")
        else:
            return render_question_frame(question, reveal_progress=1.0, state="empty")

    return VideoClip(make_frame, duration=ANSWER_REVEAL_DURATION)"""

new_reveal = """def _make_reveal_clip(question: Question) -> VideoClip:
    \"\"\"Build the 3-second answer reveal phase as a video clip.\"\"\"
    ANIMATION_DURATION = 0.5 
    
    def make_frame(t):
        if t < ANIMATION_DURATION:
            # Ease out interpolator
            progress = t / ANIMATION_DURATION
            eased = 1.0 - (1.0 - progress)**3
            return render_question_frame(question, reveal_progress=eased, state="reveal")
        else:
            return render_question_frame(question, reveal_progress=1.0, state="reveal")

    return VideoClip(make_frame, duration=ANSWER_REVEAL_DURATION)"""

mod_code4 = mod_code3.replace(old_reveal, new_reveal)

with open("renderer.py", "w", encoding="utf-8") as f:
    f.write(mod_code4)

print("Patch applied.")

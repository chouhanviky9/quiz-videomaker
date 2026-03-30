from renderer import _get_badge_layer
from config.config import config
import os

# Set dummy text and generate
config.set("COLOR_NUMBER_BADGE_BG", "#0141a4")
img = _get_badge_layer("2")
img.save("test_badge.png")
print("Saved test_badge.png")

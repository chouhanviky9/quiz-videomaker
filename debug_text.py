from PIL import Image, ImageDraw, ImageFont
import sys

def draw_it(offset):
    img = Image.new("RGBA", (200, 200), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("assets/fonts/Atma-Bold.ttf", 96)
    
    text = "2"
    
    # Simulation of area logic
    cx, cy = 100, 100
    cy -= offset
    
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    tx = cx - tw / 2 - bbox[0]
    ty = cy - th / 2 - bbox[1]
    
    print(f"Offset {offset}: tx={tx}, ty={ty}, bbox={bbox}")
    
    draw.ellipse([cx-50, cy-50, cx+50, cy+50], fill=(0,0,255))
    draw.text((tx, ty), text, font=font, fill=(255,255,255))
    
    img.save(f"test_offset_{offset}.png")

draw_it(0)
draw_it(105)
print("Done writing tests.")

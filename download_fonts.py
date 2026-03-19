import urllib.request
import os

fonts = {
    "Montserrat-Bold.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf",
    "Montserrat-ExtraBold.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-ExtraBold.ttf",
    "Montserrat-Regular.ttf": "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Regular.ttf",
}

os.makedirs(r"c:\Users\chouh\quiz-video-maker\assets\fonts", exist_ok=True)

for name, url in fonts.items():
    path = os.path.join(r"c:\Users\chouh\quiz-video-maker\assets\fonts", name)
    print(f"Downloading {name}...")
    urllib.request.urlretrieve(url, path)
    
print("Done!")

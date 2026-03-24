import urllib.request
import shutil
url = "https://thumbs.dreamstime.com/b/black-abstract-logo-black-abstract-logo-icon-design-template-elements-vector-sign-175285636.jpg"

req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as response, open("logo_test.jpg", 'wb') as out_file:
    shutil.copyfileobj(response, out_file)
print("Finished!")

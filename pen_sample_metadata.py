import os
import json
from bot import ImageHandler

os.chdir(os.path.dirname(os.path.abspath(__file__)))

image = ImageHandler()
filename = '038974.37f0e5eb.3349772249.postprocessed.png'
prompt = image.get_prompt(filename)

print(prompt)